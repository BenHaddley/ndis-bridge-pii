#!/usr/bin/env python3
"""Project-local Debian development VM: prepare, start, provision, test, ssh, stop."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import uuid

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
STATE = HERE / 'runtime'
TOOLS = STATE / 'tools'
IMAGE_URL = 'https://cloud.debian.org/images/cloud/trixie/latest/'
IMAGE_NAME = 'debian-13-genericcloud-amd64.qcow2'
PORT = 2222


def env():
    value = os.environ.copy()
    value['LD_LIBRARY_PATH'] = str(TOOLS / 'usr/lib')
    value['QEMU_MODULE_DIR'] = str(TOOLS / 'usr/lib/qemu')
    return value


def tool(name):
    local = TOOLS / 'usr/bin' / name
    installed = shutil.which(name)
    if local.exists():
        return str(local)
    if installed:
        return installed
    raise RuntimeError(f'Missing {name}; install QEMU/xorriso or run bootstrap-local-qemu.py on Manjaro/Arch')


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def download(url, path):
    partial = path.with_name(path.name + '.part')
    run(['curl', '--fail', '--location', '--retry', '2', '--silent', '--show-error',
         '--max-time', '600', url, '-o', str(partial)])
    partial.replace(path)


def prepare():
    os.umask(0o077)
    STATE.mkdir(exist_ok=True)
    STATE.chmod(0o700)
    config = STATE / 'config.json'
    if config.exists():
        print('VM already prepared. Existing disk and identity left unchanged.')
        return
    for name in ('qemu-system-x86_64', 'qemu-img', 'xorriso'):
        tool(name)
    checksums = STATE / 'SHA512SUMS'
    if not checksums.exists():
        download(IMAGE_URL + 'SHA512SUMS', checksums)
    entries = [line.split() for line in checksums.read_text().splitlines()]
    expected = next(row[0] for row in entries if len(row) == 2 and row[1].lstrip('*') == IMAGE_NAME)
    base = STATE / IMAGE_NAME
    if not base.exists():
        print('Downloading official Debian 13 amd64 cloud image...', flush=True)
        download(IMAGE_URL + IMAGE_NAME, base)
    with base.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha512').hexdigest()
    if actual != expected:
        raise RuntimeError('Debian image SHA-512 mismatch. No VM will be booted; inspect the cached image/checksums.')
    (STATE / 'image-manifest.json').write_text(json.dumps({'url': IMAGE_URL + IMAGE_NAME,
         'sha512': actual, 'verification': 'SHA512SUMS retrieved from official HTTPS source'}, indent=2) + '\n')
    key = STATE / 'id_ed25519'
    if not key.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'rndis-lab-vm', '-f', str(key)])
    identity = str(uuid.uuid4())
    seed = STATE / 'seed'
    seed.mkdir(exist_ok=True)
    user_data = {'hostname': 'rndis-lab', 'manage_etc_hosts': True, 'ssh_pwauth': False,
                 'disable_root': True,
                 'users': [{'name': 'lab', 'shell': '/bin/bash', 'groups': ['sudo'],
                            'sudo': ['ALL=(ALL) NOPASSWD:ALL'], 'lock_passwd': True,
                            'ssh_authorized_keys': [key.with_suffix('.pub').read_text().strip()]}],
                 'package_update': True, 'package_upgrade': False,
                 'packages': ['python3', 'iproute2', 'dnsmasq-base', 'curl', 'util-linux', 'ethtool', 'usbutils'],
                 'write_files': [{'path': '/etc/rndis-lab-vm', 'permissions': '0644', 'content': identity + '\n'},
                                 {'path': '/etc/apt/apt.conf.d/99-rndis-lab', 'permissions': '0644',
                                  'content': 'Acquire::IndexTargets::deb-src::Sources::DefaultEnabled "false";\nAcquire::Languages "none";\nAcquire::Retries "1";\n'}]}
    (seed / 'user-data').write_text('#cloud-config\n' + json.dumps(user_data, indent=2) + '\n')
    (seed / 'meta-data').write_text(json.dumps({'instance-id': identity, 'local-hostname': 'rndis-lab'}) + '\n')
    run([tool('xorriso'), '-as', 'mkisofs', '-quiet', '-V', 'CIDATA', '-J', '-r',
         '-o', str(STATE / 'seed.iso'), str(seed)], env=env())
    disk = STATE / 'system.qcow2'
    if disk.exists():
        raise RuntimeError('An untracked writable disk already exists; refusing to replace it')
    run([tool('qemu-img'), 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(disk), '24G'], env=env())
    config.write_text(json.dumps({'instance_id': identity, 'ssh_port': PORT, 'user': 'lab',
                                 'memory_mb': 2048, 'cpus': 2}, indent=2) + '\n')
    print('Prepared Debian VM: 2 vCPUs, 2 GiB RAM, 24 GiB sparse writable disk.')


def qmp(command, arguments=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(str(STATE / 'qmp.sock'))
        stream = sock.makefile('rwb')
        json.loads(stream.readline())
        def request(name, values=None):
            message = {'execute': name}
            if values is not None:
                message['arguments'] = values
            stream.write(json.dumps(message).encode() + b'\n')
            stream.flush()
            while True:
                line = stream.readline()
                if not line:
                    raise RuntimeError('QMP closed before responding')
                reply = json.loads(line)
                if 'error' in reply:
                    raise RuntimeError(str(reply['error']))
                if 'return' in reply:
                    return reply['return']
        request('qmp_capabilities')
        return request(command, arguments)


def start():
    if not (STATE / 'config.json').exists():
        raise RuntimeError('Run prepare first')
    try:
        state = qmp('query-status')
    except (OSError, RuntimeError):
        state = None
    if state:
        print('VM is already running:', state)
        return
    with socket.socket() as check:
        check.bind(('127.0.0.1', PORT))
    bios = TOOLS / 'usr/share/seabios/bios.bin'
    command = [tool('qemu-system-x86_64'), '-name', 'rndis-debian-lab', '-machine', 'pc,smm=off',
               '-accel', 'tcg', '-cpu', 'qemu64', '-smp', '2', '-m', '2048', '-nodefaults',
               '-display', 'none', '-serial', f'file:{STATE / "serial.log"}', '-daemonize',
               '-pidfile', str(STATE / 'qemu.pid'),
               '-qmp', f'unix:{STATE / "qmp.sock"},server=on,wait=off',
               '-drive', f'file={STATE / "system.qcow2"},if=virtio,format=qcow2',
               '-drive', f'file={STATE / "seed.iso"},if=virtio,format=raw,readonly=on',
               '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{PORT}-:22',
               '-device', 'virtio-net-pci,netdev=net0,romfile=']
    if (TOOLS / 'usr/share/qemu').exists():
        command += ['-L', str(TOOLS / 'usr/share/qemu')]
    if bios.exists():
        command += ['-bios', str(bios)]
    run(command, env=env())
    print('VM started with software CPU emulation. SSH: lab@127.0.0.1 port 2222.')
    print('First boot installs lab packages; inspect vm/runtime/serial.log for progress.')


def ssh_command(remote):
    return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
            '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'UserKnownHostsFile={STATE / "known_hosts"}', '-i', str(STATE / 'id_ed25519'),
            '-p', str(PORT), 'lab@127.0.0.1', remote]


def verify_guest():
    expected = json.loads((STATE / 'config.json').read_text())['instance_id']
    result = run(ssh_command('cat /etc/rndis-lab-vm'), capture_output=True, text=True)
    if result.stdout.strip() != expected:
        raise RuntimeError('SSH target identity does not match the prepared VM')


def provision():
    verify_guest()
    status = subprocess.run(ssh_command('sudo cloud-init status --wait --format json'),
                            capture_output=True, text=True, timeout=900)
    raw = status.stdout[status.stdout.find('{'):]
    cloud = json.loads(raw)
    (STATE / 'cloud-init-status.json').write_text(json.dumps(cloud, indent=2) + '\n')
    if cloud.get('status') != 'done' or cloud.get('errors'):
        raise RuntimeError(f'Cloud-init has unresolved errors: {cloud}')
    if status.returncode == 2:
        warnings = [message for messages in cloud.get('recoverable_errors', {}).values() for message in messages]
        if not warnings or not all('Failed to update package using apt:' in message for message in warnings):
            raise RuntimeError('Cloud-init reported an unexpected warning; inspect cloud-init-status.json')
        # A previously interrupted index refresh is acceptable only after a fresh
        # successful update. Preserve its warning and the recovery output.
        recovered = run(ssh_command('sudo apt-get update'), capture_output=True, text=True, timeout=300)
        (STATE / 'cloud-init-recovery.log').write_text(recovered.stdout + recovered.stderr)
        print('Recovered package-index warning retained in cloud-init-status.json; fresh apt update passed.')
    elif status.returncode != 0:
        raise RuntimeError(f'Cloud-init exited {status.returncode}: {status.stderr}')
    dependency_check = "import shutil, os; os.environ['PATH'] += ':/usr/sbin:/sbin'; required=['python3','ip','tc','dnsmasq','curl','unshare','nsenter']; missing=[x for x in required if not shutil.which(x)]; assert not missing, missing"
    run(ssh_command(shlex.join(['python3', '-c', dependency_check])))
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode='w:gz') as archive:
        for directory in ('lab', 'scripts', 'tests'):
            for path in (PROJECT / directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.add(path, arcname=str(path.relative_to(PROJECT)))
        # Include only VM helper source for its offline tests, never runtime keys/disks.
        archive.add(HERE / 'debian-vm.py', arcname='vm/debian-vm.py')
    run(ssh_command('mkdir -p ~/rndis-lab/test-results && tar -xzf - -C ~/rndis-lab'), input=bundle.getvalue())
    print('Copied lab, diagnostics and offline tests to ~/rndis-lab inside the VM.')


def test():
    verify_guest()
    run_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    remote = ('cd ~/rndis-lab && python3 -m unittest discover -s tests -v'
              f' && python3 lab/network_lab.py --mode bridge --output test-results/virtual-bridge-{run_id}'
              f' && python3 lab/network_lab.py --mode route --output test-results/virtual-route-{run_id}')
    completed = subprocess.run(ssh_command(remote), capture_output=True, text=True, timeout=600)
    (STATE / f'validation-{run_id}.log').write_text(completed.stdout + completed.stderr)
    print(completed.stdout, end='')
    print(completed.stderr, file=sys.stderr, end='')
    if completed.returncode:
        raise RuntimeError(f'Guest validation failed; inspect validation-{run_id}.log')
    for mode in ('bridge', 'route'):
        result = run(ssh_command(f'cat ~/rndis-lab/test-results/virtual-{mode}-{run_id}/result.json'), capture_output=True, text=True)
        report = json.loads(result.stdout)
        if report['status'] != 'PASS':
            raise RuntimeError(f'{mode} guest report did not pass')
        (STATE / f'{mode}-result-{run_id}.json').write_text(result.stdout)
    print('Guest validation passed. Hardware compatibility remains untested.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'start', 'status', 'provision', 'test', 'ssh', 'stop', 'diagnose'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == 'prepare': prepare()
        elif args.action == 'start': start()
        elif args.action == 'status': print(json.dumps(qmp('query-status'), indent=2))
        elif args.action == 'diagnose':
            print(json.dumps(qmp('query-blockstats'), indent=2))
            print(qmp('human-monitor-command', {'command-line': 'info registers'}))
        elif args.action == 'provision': provision()
        elif args.action == 'test': test()
        elif args.action == 'ssh':
            verify_guest()
            command = ssh_command(shlex.join(args.command)) if args.command else ssh_command('')[:-1]
            return subprocess.call(command)
        elif args.action == 'stop':
            if args.command == ['--force']:
                qmp('quit')
                print('Emulator stopped immediately; use this only for a stuck guest.')
            else:
                verify_guest()
                run(ssh_command('sudo shutdown -h now'))
                print('Guest shutdown requested. Use status to check it has stopped.')
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'VM operation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
