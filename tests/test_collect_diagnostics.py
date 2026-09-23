"""Offline collector checks using fake commands; these do not validate hardware."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/collect-diagnostics.sh'


class CollectorTests(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(['bash', str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('No package installs', result.stdout)

    def test_existing_directory_is_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'keep.txt'
            marker.write_text('original')
            result = subprocess.run(['bash', str(SCRIPT), root], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(root).iterdir()), [marker])
            self.assertEqual(marker.read_text(), 'original')

    def test_invalid_interface_creates_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'evidence'
            result = subprocess.run(['bash', str(SCRIPT), str(out), '../bad'], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())

    def test_failed_observation_keeps_other_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            fake_bin = root / 'bin'
            fake_bin.mkdir()
            # Stub every observation command; only date/mkdir use the local system.
            for tool in ['cat', 'uname', 'lsusb', 'ip', 'nmcli', 'journalctl', 'ethtool', 'udevadm']:
                fake = fake_bin / tool
                exit_code = 13 if tool == 'journalctl' else 0
                fake.write_text(f'#!/bin/sh\nprintf "mock {tool}\\n"\nexit {exit_code}\n')
                fake.chmod(0o700)
            out = root / 'evidence with spaces'
            env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', str(SCRIPT), str(out), 'usb0'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = (out / 'summary.txt').read_text()
            self.assertIn('kernel-log: exit 13', summary)
            self.assertIn('Unavailable/failed observations: 1', summary)
            self.assertIn('Hardware test verdict: NOT DETERMINED', summary)
            self.assertEqual((out / 'driver.txt').read_text(), 'mock ethtool\n')
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            self.assertEqual((out / 'summary.txt').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
