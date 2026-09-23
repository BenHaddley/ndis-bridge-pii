# RF baseline — collection and reporting

Status: **procedure and offline report tool ready; no RF measurements**. Run only after the USB and local-network gates pass. The TCP baseline is one input to Phase 3, not the whole capacity or video acceptance test.

## Record conditions first

Copy [rf-conditions.example.md](../config/examples/rf-conditions.example.md) beside the raw results. Use one condition set per report: equipment, firmware, waveform, channel width, topology, range/hops, endpoints, load and stream count must remain comparable. Repeat after a material change. Include tool versions and UTC start/end times.

Place the iperf3 **client at the camera end**, on a laptop substituting for the camera if necessary. Place its server at the CP. A Pi-originated test bypasses the camera/AP hop: label the measured segment accordingly. Both endpoints need known routes and an allowed test port. Bind the server to its intended test address; use the CP address actually assigned, not a wiki example.

## Capture a TCP baseline in both directions

The commands below are for the future bench. `CP_TEST_IP` must first be assigned the actual CP test address. Use a new directory and keep failed files and stderr for diagnosis.

```bash
# CP terminal; leave this running for the tests, stop with Ctrl-C afterwards.
iperf3 -s -B "$CP_TEST_IP" -p 5201
```

```bash
# Camera-end laptop. Set CP_TEST_IP here too; shell variables do not cross hosts.
umask 077
mkdir test-results/rf-raw-01
set -o noclobber
iperf3 -c "$CP_TEST_IP" -p 5201 -t 60 -J > test-results/rf-raw-01/forward-01.json 2> test-results/rf-raw-01/forward-01.stderr
iperf3 -c "$CP_TEST_IP" -p 5201 -t 60 -R -J > test-results/rf-raw-01/reverse-01.json 2> test-results/rf-raw-01/reverse-01.stderr
```

Check exit status and JSON before continuing. Repeat each direction at least three times, using new filenames (`02`, `03`). This repetition count and duration are project proposals. Keep normal and representative background-load series separate. Do not combine normal and reverse rates into a full-duplex RF rating.

iperf3 normally sends from client to server; `-R` reverses that direction. `-J` produces JSON. This tool deliberately accepts separate TCP client runs, not `--bidir`, server JSON, UDP or JSON streaming output. See [ESnet's iperf3 manual](https://software.es.net/iperf/invoking.html).

## Produce the report offline

```bash
python3 scripts/summarize-rf.py test-results/rf-raw-01/*.json \
  --conditions test-results/rf-raw-01/conditions.md \
  --environment bench --waveform WRAITH --channel-mhz 10 \
  --reserve-percent 25 --other-mbps 0 \
  --output test-results/rf-report-01
```

Use `synthetic` for virtual/fixture results and `field` only for actual field data. The environment is an operator declaration, not automatic verification. Conditions must be filled before use; the script cannot determine whether a narrative is accurate.

The report directory contains `rf-baseline.csv`, `report.json`, `report.md` and a copy of the conditions. Input hashes link each row to the original JSON; preserve those files. Existing report directories are refused. Invalid/error results and duplicate file contents are rejected before output is created. Failed measurements should still be described in the conditions; do not silently exclude outages to improve the result.

For each direction the tool takes the **lowest run-average receiver TCP payload rate**, applies the chosen reserve, then subtracts an allowance for additional traffic. `--other-mbps` applies the same extra allowance to each direction; it should exclude traffic already present during the measurements. The result is clamped at zero. A 16 Mbps baseline with 25% reserve and a further 1 Mbps allowance produces an 11 Mbps provisional planning figure. That arithmetic is not a hardware claim.

A run average can hide long stalls. TCP payload throughput is not encoded camera bitrate or raw RF capacity. Inspect per-interval behaviour, stream peaks and protocol overhead before selecting camera settings. There is no automatic hardware PASS; short runs and missing repetitions produce warnings.

## Evidence still required for Phase 3

| Observation | Save | Decision it supports |
| --- | --- | --- |
| Idle and loaded latency | Timed probes plus viewer observations; identify endpoints | Whether bulk traffic adds unacceptable delay |
| Path MTU | Probe method, address family, largest working size and failures | Packet sizing for the chosen transport |
| UDP delivery if the stream uses UDP | Sender offered rate, receiver rate, loss, jitter, datagram size, duration and direction | Whether intended media survives at its actual offered load |
| Stream bursts and stalls | Interval data and camera/viewer logs | Whether a run average hides outages |
| Concurrent traffic | Voice/PLI/other load and priorities, as configured by radio operator | Capacity remaining in representative use |
| Physical radio conditions | Model, firmware, waveform, bandwidth, range, terrain, hop count | Which deployments the result describes |

For UDP, start below the measured TCP reference and increase the offered load in controlled steps around the intended stream demand; retain the receiver's loss/jitter evidence. A configured sending rate alone is not achieved throughput. The current summarizer intentionally leaves UDP interpretation to this record rather than treating it as interchangeable with TCP.

RFC 6349 describes a TCP test framework, including path MTU (§3.1), RTT (§3.2) and interpretation (§5.2). It provides useful reading; these project steps do not claim RFC 6349 conformance. [Official RFC 6349](https://www.rfc-editor.org/rfc/rfc6349.html).

Finish with the [video profile](video-profile.md) and [acceptance record](../test-results/acceptance.md). No observed capacity or video budget has yet been entered for the real radio.
