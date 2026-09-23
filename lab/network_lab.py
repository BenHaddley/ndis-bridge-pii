#!/usr/bin/env python3
"""Rootless, disposable Linux network lab. No radio hardware is emulated."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TOOLS = ('unshare', 'nsenter', 'ip', 'dnsmasq', 'tc', 'curl')


def execute(command, timeout=15):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{command!r}: exit {result.returncode}\n{result.stderr or result.stdout}')
    return result.stdout


class Lab:
    def __init__(self, mode, output, rate):
        self.mode, self.output, self.rate = mode, output, rate
        self.nodes, self.processes, self.logs = {}, [], []
        self.results = []
        self.managed_routes = []
        self.command_log = (output / 'commands.jsonl').open('w')

    def command(self, node, *args, timeout=15):
        command = ['nsenter', '--target', str(self.nodes[node].pid), '--net', '--', *args]
        self.command_log.write(json.dumps({'node': node, 'argv': args}) + '\n')
        self.command_log.flush()
        return execute(command, timeout)

    def spawn(self, node, name, *args):
        log = (self.output / f'{name}.log').open('w')
        self.logs.append(log)
        process = subprocess.Popen(['nsenter', '--target', str(self.nodes[node].pid),
                                    '--net', '--', *args], stdout=log, stderr=subprocess.STDOUT)
        self.processes.append(process)
        return process

    def add_node(self, name):
        process = subprocess.Popen(['unshare', '--net', sys.executable, '-u', '-c',
                                    'import sys; print("ready"); sys.stdin.read()'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.processes.append(process)
        if process.stdout.readline().strip() != 'ready':
            raise RuntimeError(f'Network namespace {name} failed to start')
        self.nodes[name] = process
        self.command(name, 'ip', 'link', 'set', 'lo', 'up')

    def wire(self, index, left, left_if, right, right_if):
        a, b = f'wire{index}a', f'wire{index}b'
        execute(['ip', 'link', 'add', a, 'type', 'veth', 'peer', 'name', b])
        for temporary, node, interface in ((a, left, left_if), (b, right, right_if)):
            execute(['ip', 'link', 'set', temporary, 'netns', str(self.nodes[node].pid)])
            self.command(node, 'ip', 'link', 'set', temporary, 'name', interface)
            self.command(node, 'ip', 'link', 'set', interface, 'up')

    def address(self, node, interface, cidr):
        self.command(node, 'ip', 'address', 'add', cidr, 'dev', interface)

    def route(self, node, destination, gateway):
        self.command(node, 'ip', 'route', 'add', destination, 'via', gateway)
        entry = (node, destination, gateway)
        if entry not in self.managed_routes:
            self.managed_routes.append(entry)

    def forwarding(self, node):
        self.command(node, sys.executable, '-c',
                     'from pathlib import Path; Path("/proc/sys/net/ipv4/ip_forward").write_text("1")')

    def bridge(self, node, ports):
        self.command(node, 'ip', 'link', 'add', 'br0', 'type', 'bridge', 'stp_state', '0')
        for port in ports:
            self.command(node, 'ip', 'link', 'set', port, 'master', 'br0')
        self.command(node, 'ip', 'link', 'set', 'br0', 'up')

    def dhcp_server(self, node, interface, prefix):
        process = self.spawn(node, f'{node}-dhcp', 'dnsmasq', '--no-daemon',
                            '--conf-file=/dev/null', '--port=0', '--no-hosts', '--no-resolv',
                            '--bind-interfaces', f'--interface={interface}', '--dhcp-authoritative',
                            f'--dhcp-range={prefix}.100,{prefix}.110,255.255.255.0,1h',
                            f'--dhcp-option=3,{prefix}.1',
                            f'--dhcp-leasefile={self.output / (node + ".leases")}',
                            f'--pid-file={self.output / (node + ".pid")}',
                            '--log-dhcp', '--log-facility=-')
        time.sleep(0.15)
        if process.poll() is not None:
            raise RuntimeError(f'{node} DHCP server exited; see {node}-dhcp.log')

    def lease(self, node, interface, prefix, label):
        lease = json.loads(self.command(node, sys.executable, str(HERE / 'dhcp_client.py'), interface))
        if (lease['server'] != prefix + '.1' or lease['gateway'] != prefix + '.1'
                or lease['prefix'] != 24 or not lease['address'].startswith(prefix + '.')):
            raise RuntimeError(f'Unexpected DHCP lease: {lease}')
        self.address(node, interface, f'{lease["address"]}/{lease["prefix"]}')
        self.route(node, 'default', lease['gateway'])
        (self.output / f'{node}-lease.json').write_text(json.dumps(lease, indent=2) + '\n')
        self.check(label, True, lease)
        return lease['address']

    def check(self, name, passed, details=None):
        self.results.append({'name': name, 'passed': passed, 'details': details})
        print(f'{"PASS" if passed else "FAIL"}: {self.mode}: {name}', flush=True)
        if not passed:
            raise RuntimeError(f'Check failed: {name}: {details}')

    def setup(self):
        for node in ('camera', 'ap', 'pi', 'radio_a', 'radio_b', 'cp'):
            self.add_node(node)
        for index, endpoints in enumerate([
            ('camera', 'eth0', 'ap', 'wifi0'),
            ('ap', 'eth0', 'pi', 'eth0'),
            ('pi', 'usb0', 'radio_a', 'usb0'),
            ('radio_a', 'rf0', 'radio_b', 'rf0'),
            ('radio_b', 'lan0', 'cp', 'eth0'),
        ]):
            self.wire(index, *endpoints)
        self.bridge('ap', ['wifi0', 'eth0'])
        self.address('radio_a', 'usb0', '192.168.10.1/24')
        self.address('radio_a', 'rf0', '172.31.0.1/30')
        self.address('radio_b', 'rf0', '172.31.0.2/30')
        self.address('radio_b', 'lan0', '192.168.30.1/24')
        self.address('cp', 'eth0', '192.168.30.10/24')
        self.route('cp', 'default', '192.168.30.1')
        for node in ('radio_a', 'radio_b'):
            self.forwarding(node)
            self.command(node, 'tc', 'qdisc', 'add', 'dev', 'rf0', 'root', 'tbf',
                         'rate', f'{self.rate}mbit', 'burst', '32kb', 'latency', '100ms')
        self.route('radio_a', '192.168.30.0/24', '172.31.0.2')
        self.route('radio_b', '192.168.10.0/24', '172.31.0.1')
        self.dhcp_server('radio_a', 'usb0', '192.168.10')
        if self.mode == 'bridge':
            self.bridge('pi', ['eth0', 'usb0'])
            self.address('pi', 'br0', '192.168.10.2/24')
            self.route('pi', 'default', '192.168.10.1')
            self.camera_ip = self.lease('camera', 'eth0', '192.168.10', 'radio DHCP crosses AP and Pi bridges')
            self.camera_subnet = '192.168.10.0/24'
        else:
            pi_ip = self.lease('pi', 'usb0', '192.168.10', 'Pi obtains USB-side radio DHCP lease')
            self.address('pi', 'eth0', '192.168.20.1/24')
            self.forwarding('pi')
            # Deliberately no DHCP relay: broadcast must not cross the routed Pi.
            try:
                self.command('camera', sys.executable, str(HERE / 'dhcp_client.py'), 'eth0')
            except RuntimeError as error:
                if 'No DHCP message type 2' not in str(error):
                    raise
                self.check('radio DHCP does not leak into routed camera LAN', True)
            else:
                self.check('radio DHCP does not leak into routed camera LAN', False)
            self.dhcp_server('pi', 'eth0', '192.168.20')
            self.camera_ip = self.lease('camera', 'eth0', '192.168.20', 'camera receives separate LAN DHCP lease')
            self.camera_subnet = '192.168.20.0/24'
            self.route('radio_a', self.camera_subnet, pi_ip)
            self.route('radio_b', self.camera_subnet, '172.31.0.1')

    def http(self, node, address):
        return self.command(node, 'curl', '--noproxy', '*', '--fail', '--silent', '--show-error',
                            '--connect-timeout', '1', '--max-time', '2',
                            f'http://{address}:8080/probe.txt', timeout=4).strip()

    def recovered(self):
        for _ in range(20):
            try:
                if self.http('cp', self.camera_ip) == 'virtual-camera-payload':
                    return True
            except RuntimeError:
                pass
            time.sleep(0.1)
        return False

    def unreachable(self, label):
        try:
            self.http('cp', self.camera_ip)
        except RuntimeError:
            self.check(label, True)
        else:
            self.check(label, False, 'HTTP unexpectedly succeeded')

    def test_path(self):
        media = self.output / 'http'
        media.mkdir()
        (media / 'probe.txt').write_text('virtual-camera-payload\n')
        payload = bytes(range(256)) * 4096
        (media / 'payload.bin').write_bytes(payload)
        for node in ('camera', 'cp'):
            self.spawn(node, f'{node}-http', sys.executable, '-m', 'http.server', '8080',
                       '--bind', '0.0.0.0', '--directory', str(media))
        self.check('CP reaches camera HTTP endpoint', self.recovered())
        self.check('camera reaches CP HTTP endpoint', self.http('camera', '192.168.30.10') == 'virtual-camera-payload')
        received = self.output / 'received.bin'
        transfer = self.command('cp', 'curl', '--noproxy', '*', '--fail', '--silent', '--show-error',
                                '--max-time', '15', '--output', str(received),
                                '--write-out', '%{speed_download}',
                                f'http://{self.camera_ip}:8080/payload.bin', timeout=18)
        digest = hashlib.sha256(received.read_bytes()).hexdigest()
        self.check('1 MiB payload arrives intact', digest == hashlib.sha256(payload).hexdigest(),
                   {'sha256': digest, 'synthetic_transfer_mbps': round(float(transfer) * 8 / 1e6, 3),
                    'not_a_radio_measurement': True})
        for node, interface, label in [('pi', 'usb0', 'USB-side link'), ('radio_a', 'rf0', 'RF-side link')]:
            self.command(node, 'ip', 'link', 'set', interface, 'down')
            try:
                self.unreachable(label + ' outage interrupts traffic')
            finally:
                self.command(node, 'ip', 'link', 'set', interface, 'up')
                # Linux can remove next-hop routes on administrative link-down.
                # Reapply our known fixture routes, as a network manager must.
                for owner, destination, gateway in self.managed_routes:
                    self.command(owner, 'ip', 'route', 'replace', destination, 'via', gateway)
            self.check(label + ' restoration with route reconciliation recovers traffic', self.recovered())
        self.command('radio_b', 'ip', 'route', 'del', self.camera_subnet)
        try:
            self.unreachable('missing camera-subnet route interrupts traffic')
        finally:
            self.route('radio_b', self.camera_subnet, '172.31.0.1')
        self.check('route restoration recovers traffic', self.recovered())

    def snapshot(self):
        for node in self.nodes:
            state = {}
            for name, args in [('links', ('ip', '-j', '-d', 'link', 'show')),
                               ('addresses', ('ip', '-j', 'address', 'show')),
                               ('routes', ('ip', '-j', 'route', 'show')),
                               ('qdiscs', ('tc', '-j', 'qdisc', 'show'))]:
                state[name] = json.loads(self.command(node, *args))
            (self.output / f'{node}-network.json').write_text(json.dumps(state, indent=2) + '\n')

    def close(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(self.processes):
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
        for log in self.logs:
            log.close()
        self.command_log.close()


def worker(args):
    # Reject direct execution in the host's namespaces, even if invoked as root.
    if os.getpid() != 1 or os.readlink('/proc/self/ns/net') == args.host_net:
        raise RuntimeError('Worker requires a fresh PID and network namespace; use the public CLI')
    report = {'mode': args.mode, 'kind': 'VIRTUAL_ONLY', 'hardware_validated': False,
              'rate_limit_mbps_per_direction': args.rate_mbps, 'status': 'FAIL', 'checks': []}
    lab = Lab(args.mode, args.output, args.rate_mbps)
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        lab.setup()
        lab.test_path()
        lab.snapshot()
        report['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = str(error)
        print(f'Lab failed: {error}', file=sys.stderr)
        try:
            lab.snapshot()
        except Exception as snapshot_error:
            report['snapshot_error'] = str(snapshot_error)
    finally:
        report['checks'] = lab.results
        lab.close()
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' else 1


def main():
    # Debian omits administrative binary directories from ordinary users' PATH.
    # The lab needs tc/dnsmasq without requiring host root privileges.
    os.environ['PATH'] = os.environ.get('PATH', os.defpath) + ':/usr/sbin:/sbin'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['bridge', 'route'], default='bridge')
    parser.add_argument('--output', type=Path, required=True, help='New evidence directory; never overwritten')
    parser.add_argument('--rate-mbps', type=int, default=16, help='Synthetic per-direction RF-link cap (1–1000), not RF emulation')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--host-net', default='', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.rate_mbps <= 1000:
        parser.error('--rate-mbps must be between 1 and 1000')
    if args.worker:
        return worker(args)
    missing = [tool for tool in TOOLS if shutil.which(tool) is None]
    if missing:
        parser.error('Missing dependencies: ' + ', '.join(missing))
    args.output = args.output.absolute()
    if args.output.exists():
        parser.error('Output path already exists; choose a new directory')
    os.umask(0o077)
    args.output.mkdir(parents=True)
    command = ['unshare', '--user', '--map-root-user', '--net', '--mount', '--pid',
               '--fork', '--mount-proc', '--kill-child', sys.executable, str(Path(__file__).resolve()),
               '--worker', '--host-net', os.readlink('/proc/self/ns/net'),
               '--mode', args.mode, '--output', str(args.output), '--rate-mbps', str(args.rate_mbps)]
    process = subprocess.Popen(command, start_new_session=True)
    try:
        code = process.wait(timeout=180)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        code = 1
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    result_path = args.output / 'result.json'
    if not result_path.exists():
        result_path.write_text(json.dumps({'status': 'FAIL', 'kind': 'VIRTUAL_ONLY',
                                          'hardware_validated': False,
                                          'error': 'Worker did not finish; check namespace permissions or interruption'}, indent=2) + '\n')
    print(f'Evidence: {args.output}\nVirtual test only; no hardware gate is passed.')
    return code


if __name__ == '__main__':
    sys.exit(main())
