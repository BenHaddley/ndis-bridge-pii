"""Protect direction, payload accounting and evidence integrity in RF reports."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/summarize-rf.py'
SPEC = importlib.util.spec_from_file_location('summarize_rf', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(mbps=16, reverse=0, seconds=60):
    return {
        'start': {'connecting_to': {'host': '192.0.2.2', 'port': 5201},
                  'test_start': {'protocol': 'TCP', 'reverse': reverse, 'num_streams': 1}},
        'end': {'sum_received': {'seconds': seconds, 'bits_per_second': mbps * 1e6,
                                 'bytes': mbps * 1e6 * seconds / 8, 'sender': not bool(reverse)},
                'sum_sent': {'bits_per_second': 999e6}},
    }


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conditions = self.root / 'conditions.md'
        self.conditions.write_text('Synthetic fixture; no radio attached.\n')

    def write_run(self, name='normal.json', **kwargs):
        path = self.root / name
        path.write_text(json.dumps(fixture(**kwargs)))
        return path

    def cli(self, *inputs, extra=()):
        return subprocess.run([
            sys.executable, str(SCRIPT), *map(str, inputs), '--output', str(self.root / 'report'),
            '--environment', 'synthetic', '--conditions', str(self.conditions),
            '--waveform', 'fixture', '--channel-mhz', '10', *extra,
        ], capture_output=True, text=True)

    def test_receiver_direction_and_budget(self):
        normal = self.write_run()
        reverse = self.write_run('reverse.json', mbps=8, reverse=1)
        result = self.cli(normal, reverse, extra=('--other-mbps', '1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / 'report/report.json').read_text())
        self.assertEqual(report['directions']['camera-to-cp']['provisional_budget_mbps'], 11)
        self.assertEqual(report['directions']['cp-to-camera']['provisional_budget_mbps'], 5)
        self.assertEqual(report['hardware_gate_verdict'], 'NOT DETERMINED')
        self.assertEqual(report['environment'], 'synthetic')
        self.assertEqual((self.root / 'report/conditions.txt').read_bytes(), self.conditions.read_bytes())
        self.assertEqual(len(report['warnings']), 2)
        self.assertEqual((self.root / 'report').stat().st_mode & 0o777, 0o700)

    def test_uses_minimum_and_clamps_insufficient_budget(self):
        runs = [MODULE.load_run(self.write_run(f'{rate}.json', mbps=rate)) for rate in (16, 10, 14)]
        result = MODULE.summarize(runs, 25, 8)['camera-to-cp']
        self.assertEqual(result['minimum_received_mbps'], 10)
        self.assertEqual(result['median_received_mbps'], 14)
        self.assertEqual(result['provisional_budget_mbps'], 0)

    def test_existing_evidence_is_preserved(self):
        output = self.root / 'report'
        output.mkdir()
        marker = output / 'report.json'
        marker.write_text('keep')
        result = self.cli(self.write_run())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(list(output.iterdir()), [marker])

    def test_bad_measurements_create_no_output(self):
        bad = []
        for key, value in [('seconds', 0), ('seconds', float('nan')),
                           ('bits_per_second', float('inf')), ('bytes', -1),
                           ('bytes', 1), ('seconds', True)]:
            data = fixture()
            data['end']['sum_received'][key] = value
            bad.append(data)
        for key, value in [('protocol', 'UDP'), ('reverse', 'false'), ('bidir', 1)]:
            data = fixture()
            data['start']['test_start'][key] = value
            bad.append(data)
        data = fixture()
        del data['start']['connecting_to']
        bad.extend([data, {'error': 'connection refused'}, {}, [], {'start': []}])
        for data in bad:
            with self.subTest(data=data):
                path = self.root / 'bad.json'
                path.write_text(json.dumps(data))
                result = self.cli(path)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'report').exists())

    def test_duplicate_evidence_is_not_a_repetition(self):
        original = self.write_run()
        copy = self.root / 'copy.json'
        copy.write_bytes(original.read_bytes())
        result = self.cli(original, copy)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate', result.stderr)
        self.assertFalse((self.root / 'report').exists())

    def test_invalid_budget_rejected(self):
        path = self.write_run()
        for flag, value in [('--reserve-percent', '100'), ('--reserve-percent', 'nan'),
                            ('--other-mbps', '-1'), ('--channel-mhz', 'inf')]:
            with self.subTest(flag=flag, value=value):
                result = self.cli(path, extra=(flag, value))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / 'report').exists())

    def test_short_and_zero_runs_are_visible(self):
        result = self.cli(self.write_run(mbps=0, seconds=10))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / 'report/report.json').read_text())
        self.assertTrue(any('shorter' in warning for warning in report['warnings']))
        self.assertTrue(any('Zero' in warning for warning in report['warnings']))
        self.assertEqual(report['directions']['camera-to-cp']['provisional_budget_mbps'], 0)

    def test_real_iperf318_client_role_does_not_change_receiver_metric(self):
        fixtures = Path(__file__).parent / 'fixtures'
        forward = MODULE.load_run(fixtures / 'iperf318-forward.json')
        reverse = MODULE.load_run(fixtures / 'iperf318-reverse.json')
        self.assertEqual(forward['direction'], 'camera-to-cp')
        self.assertEqual(reverse['direction'], 'cp-to-camera')
        self.assertAlmostEqual(forward['received_mbps'], 2.0900156415917845)
        self.assertAlmostEqual(reverse['received_mbps'], 2.095743660260305)


if __name__ == '__main__':
    unittest.main()
