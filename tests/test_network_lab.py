"""Protocol parser and CLI guard checks; live namespace tests are separate."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from lab.dhcp_client import COOKIE, HEADER, dhcp_payload, options, packet, reply

SCRIPT = Path(__file__).resolve().parents[1] / 'lab/network_lab.py'


class DhcpTests(unittest.TestCase):
    mac = b'\x02\x00\x00\x00\x00\x01'
    xid = 12345

    def response(self, xid=None):
        fields = list(HEADER.unpack(packet(self.xid, self.mac, 1)[:236]))
        fields[0] = 2
        fields[4] = self.xid if xid is None else xid
        fields[8] = b'\xc0\xa8\x0a\x64'
        return HEADER.pack(*fields) + COOKIE + b'\x35\x01\x02\x00\x36\x04\xc0\xa8\x0a\x01\xff'

    def test_discover_and_request_options(self):
        discover = packet(self.xid, self.mac, 1)
        self.assertGreaterEqual(len(discover), 300)
        self.assertEqual(options(discover[240:])[53], b'\x01')
        request = packet(self.xid, self.mac, 3, b'\xc0\xa8\x0a\x64', b'\xc0\xa8\x0a\x01')
        parsed = options(request[240:])
        self.assertEqual(parsed[50], b'\xc0\xa8\x0a\x64')
        self.assertEqual(parsed[54], b'\xc0\xa8\x0a\x01')
        self.assertEqual(HEADER.unpack(request[:236])[6], 0x8000)

    def test_reply_matches_client_transaction(self):
        address, opts = reply(self.response(), self.xid, self.mac)
        self.assertEqual(address, b'\xc0\xa8\x0a\x64')
        self.assertEqual(opts[53], b'\x02')
        self.assertIsNone(reply(self.response(999), self.xid, self.mac))
        self.assertIsNone(reply(self.response(), self.xid, b'\x00' * 6))
        self.assertIsNone(reply(b'truncated', self.xid, self.mac))

    def test_raw_reply_filtering(self):
        payload = self.response()
        udp = struct.pack('!HHHH', 67, 68, 8 + len(payload), 0) + payload
        ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
                         b'\xc0\xa8\x0a\x01', b'\xff' * 4)
        self.assertEqual(dhcp_payload(ip + udp), payload)
        self.assertIsNone(dhcp_payload(ip + udp[:7]))
        self.assertIsNone(dhcp_payload(ip + struct.pack('!HHHH', 68, 67, 8, 0)))
        fragmented = bytearray(ip + udp)
        fragmented[6] = 0x20
        self.assertIsNone(dhcp_payload(fragmented))


    def test_truncated_options_rejected(self):
        for value in (b'\x35', b'\x36\x04\x01'):
            with self.assertRaises(ValueError):
                options(value)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_existing_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'result.json'
            marker.write_text('{"existing": true}')
            result = self.run_cli('--output', root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(marker.read_text()), {'existing': True})

    def test_direct_worker_does_not_touch_network(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_cli('--worker', '--output', root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('fresh PID and network namespace', result.stderr)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_invalid_rate_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'new'
            result = self.run_cli('--output', str(output), '--rate-mbps', '0')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
