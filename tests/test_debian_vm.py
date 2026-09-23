"""VM control guard tests; never launch an emulator or access the network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

SPEC = importlib.util.spec_from_file_location('debian_vm', Path(__file__).resolve().parents[1] / 'vm/debian-vm.py')
vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vm)


class VmControlTests(unittest.TestCase):
    def test_ssh_is_localhost_with_dedicated_identity(self):
        with patch.object(vm, 'STATE', Path('/tmp/path with spaces')):
            command = vm.ssh_command('uname -a')
        self.assertIn('lab@127.0.0.1', command)
        self.assertIn('StrictHostKeyChecking=accept-new', command)
        self.assertIn('IdentitiesOnly=yes', command)
        self.assertIn('UserKnownHostsFile=/tmp/path with spaces/known_hosts', command)
        self.assertIn('/tmp/path with spaces/id_ed25519', command)
        self.assertEqual(command[-1], 'uname -a')

    def test_existing_vm_prepare_preserves_configuration(self):
        with tempfile.TemporaryDirectory() as root:
            state = Path(root)
            config = state / 'config.json'
            config.write_text('{"existing": true}')
            with patch.object(vm, 'STATE', state), patch.object(vm, 'download') as download, patch.object(vm, 'run') as run:
                vm.prepare()
                download.assert_not_called()
                run.assert_not_called()
            self.assertEqual(json.loads(config.read_text()), {'existing': True})

    def test_wrong_guest_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            state = Path(root)
            (state / 'config.json').write_text('{"instance_id":"expected"}')
            with patch.object(vm, 'STATE', state), patch.object(vm, 'run', return_value=Mock(stdout='wrong\n')):
                with self.assertRaisesRegex(RuntimeError, 'identity does not match'):
                    vm.verify_guest()

    def test_start_requires_prepared_vm(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(vm, 'STATE', Path(root)), patch.object(vm, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'prepare first'):
                    vm.start()
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
