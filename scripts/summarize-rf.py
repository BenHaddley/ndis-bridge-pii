#!/usr/bin/env python3
"""Summarize saved client-side iperf3 TCP runs; never probes or configures a network."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a number')
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f'{label} must be finite and >= {minimum}')
    return value


def load_run(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or 'error' in data:
        raise ValueError(f'{path}: not a successful iperf3 result')
    try:
        start = data['start']
        spec = start['test_start']
        receiver = data['end']['sum_received']
        if not start.get('connecting_to'):
            raise ValueError('use client-side JSON, not server-side JSON')
        if spec['protocol'] != 'TCP':
            raise ValueError('only TCP baseline runs are supported; retain UDP evidence separately')
        if spec.get('bidir') or any('bidir' in key for key in data['end']):
            raise ValueError('use separate normal and reverse runs, not --bidir')
        reverse = spec['reverse']
        if type(reverse) not in (int, bool) or reverse not in (0, 1):
            raise ValueError('reverse must be 0 or 1')
        # sum_received selects receiver metrics. Its `sender` flag describes the
        # reporting endpoint's role and is true in a normal client-side TCP run.
        seconds = number(receiver['seconds'], 'receiver seconds', 0.001)
        bps = number(receiver['bits_per_second'], 'receiver bits_per_second')
        received_bytes = number(receiver['bytes'], 'receiver bytes')
        if not math.isclose(bps, received_bytes * 8 / seconds, rel_tol=0.01, abs_tol=1):
            raise ValueError('receiver rate does not agree with bytes and duration')
        streams = number(spec['num_streams'], 'num_streams', 1)
        if int(streams) != streams:
            raise ValueError('num_streams must be an integer')
        return {
            'source': str(path.resolve()),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'direction': 'cp-to-camera' if reverse else 'camera-to-cp',
            'seconds': seconds,
            'received_mbps': bps / 1_000_000,
            'received_bytes': received_bytes,
            'streams': streams,
        }
    except (KeyError, TypeError) as exc:
        raise ValueError(f'{path}: missing or malformed iperf3 TCP fields') from exc


def summarize(runs, reserve_percent, other_mbps):
    groups = {}
    for direction in ('camera-to-cp', 'cp-to-camera'):
        samples = [r['received_mbps'] for r in runs if r['direction'] == direction]
        if not samples:
            continue
        baseline = min(samples)
        groups[direction] = {
            'runs': len(samples),
            'minimum_received_mbps': baseline,
            'median_received_mbps': statistics.median(samples),
            'maximum_received_mbps': max(samples),
            'provisional_budget_mbps': max(0, baseline * (1 - reserve_percent / 100) - other_mbps),
        }
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path, help='client JSON; client must be at the camera end')
    parser.add_argument('--output', required=True, type=Path, help='new report directory (never overwritten)')
    parser.add_argument('--environment', required=True, choices=('synthetic', 'bench', 'field'))
    parser.add_argument('--conditions', required=True, type=Path, help='operator-written run conditions file')
    parser.add_argument('--waveform', required=True)
    parser.add_argument('--channel-mhz', required=True, type=float)
    parser.add_argument('--reserve-percent', type=float, default=25)
    parser.add_argument('--other-mbps', type=float, default=0,
                        help='additional traffic allowance per direction, not already present during measurement')
    args = parser.parse_args(argv)
    try:
        number(args.channel_mhz, 'channel-mhz', 0.001)
        number(args.reserve_percent, 'reserve-percent')
        if args.reserve_percent >= 100:
            raise ValueError('reserve-percent must be less than 100')
        number(args.other_mbps, 'other-mbps')
        if not args.waveform.strip():
            raise ValueError('waveform must not be empty')
        conditions = args.conditions.read_bytes()
        if not conditions.strip():
            raise ValueError('conditions file must not be empty')
        runs = [load_run(path) for path in args.inputs]
        if len({r['sha256'] for r in runs}) != len(runs):
            raise ValueError('duplicate input evidence; copies are not independent repetitions')
        if len({r['streams'] for r in runs}) != 1:
            raise ValueError('do not mix different parallel-stream counts in one report')
        groups = summarize(runs, args.reserve_percent, args.other_mbps)
        warnings = []
        for direction in ('camera-to-cp', 'cp-to-camera'):
            if groups.get(direction, {}).get('runs', 0) < 3:
                warnings.append(f'{direction}: fewer than three independent runs')
        if any(r['seconds'] < 60 for r in runs):
            warnings.append('At least one run is shorter than the proposed 60-second baseline')
        if any(r['received_mbps'] == 0 for r in runs):
            warnings.append('Zero throughput observed; investigate connectivity before media testing')
        report = {
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'environment': args.environment,
            'hardware_gate_verdict': 'NOT DETERMINED',
            'waveform': args.waveform,
            'channel_mhz': args.channel_mhz,
            'conditions_sha256': hashlib.sha256(conditions).hexdigest(),
            'reserve_percent': args.reserve_percent,
            'additional_other_mbps_per_direction': args.other_mbps,
            'directions': groups,
            'warnings': warnings,
            'runs': runs,
        }
        # Validate everything before creating any output. mkdir rejects existing paths/symlinks.
        args.output.mkdir(mode=0o700)
        (args.output / 'conditions.txt').write_bytes(conditions)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        with (args.output / 'rf-baseline.csv').open('w', newline='') as handle:
            fields = ['environment', 'waveform', 'channel_mhz', *runs[0].keys()]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for run in runs:
                writer.writerow(dict(environment=args.environment, waveform=args.waveform,
                                     channel_mhz=args.channel_mhz, **run))
        lines = [
            '# TCP baseline report', '',
            f'Environment: {args.environment}. Hardware gate verdict: NOT DETERMINED.', '',
            'The client must be at the camera end for these direction labels to be correct.', '',
            '| Direction | Runs | Minimum Mbps | Median Mbps | Maximum Mbps | Provisional budget Mbps |',
            '| --- | --- | --- | --- | --- | --- |',
        ]
        for direction, group in groups.items():
            lines.append(f"| {direction} | {group['runs']} | {group['minimum_received_mbps']:.3f} | "
                         f"{group['median_received_mbps']:.3f} | {group['maximum_received_mbps']:.3f} | "
                         f"{group['provisional_budget_mbps']:.3f} |")
        lines.extend([
            '', f'Budget = max(0, minimum received Mbps × (1 − {args.reserve_percent}/100) − {args.other_mbps}).',
            '', 'This is a project planning calculation from TCP payload throughput, not RF capacity or a '
            'camera encoder setting. Validate actual stream overhead, bursts, loss, delay and competing traffic. '
            'Separate directional tests do not establish simultaneous bidirectional capacity.',
            '', 'Conditions are copied into conditions.txt. Source paths and hashes are in report.json; '
            'retain the original JSON files. The environment label is operator supplied and does not verify hardware.',
            '', 'Warnings:', '',
        ])
        lines.extend(f'- {warning}' for warning in warnings)
        if not warnings:
            lines.append('- No repetition/duration warnings; acceptance still requires separate evidence.')
        (args.output / 'report.md').write_text('\n'.join(lines) + '\n')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f'Cannot summarize: {exc}', file=sys.stderr)
        return 1
    print(f'Report saved to {args.output}; no hardware gate has been passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
