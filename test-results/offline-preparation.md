# Offline roadmap preparation — 24 September 2026

Status: **software preparation validated; all hardware acceptance gates remain NOT RUN**.

## Deliverables

- Phase 2: network decision table, DHCP/address worksheet, traffic contract and console rollback procedure.
- Phase 3: measurement procedure, conditions template, TCP JSON summarizer and tests.
- Phase 4: camera/viewer profile, soak and interruption evidence requirements.
- Phase 6: deployment discovery and position/video acceptance contract.
- Phase 7: draft operator start/fault/recovery/handover guide.
- References: all 11 saved PDF checksums verified; text extracted from each, page-level radio findings recorded and wiki/manifest corrected.

No topology, stream profile, installer or deployment configuration has been declared hardware-proven. Phase 5 packaging still waits for the Phase 1–4 results.

## Verification

`python3 -m unittest discover -s tests -v`: **23 tests passed**, including eight RF report checks. Coverage includes receiver-rate accounting, normal/reverse direction, minimum-based budget arithmetic, invalid/error results, non-finite values, duplicate evidence, existing-output preservation and explicit warnings for incomplete measurement series.

Two actual iperf3 3.18 TCP client runs were collected over **guest loopback only** inside Debian 13 amd64, under QEMU software emulation. Each used a two-second duration and a 2 Mbps offered-rate cap; the second used reverse mode. The temporary server bound only to loopback and was terminated after collection. These runs verify tool interoperability, not throughput of the virtual topology or the radio.

The real JSON showed that `sum_received.sender` describes the reporting endpoint's role, so normal client output can contain `true`. The parser uses `sum_received` for receiver accounting and `test_start.reverse` for direction. Reduced actual outputs are retained as [regression fixtures](../tests/fixtures/README.md).

The report command completed against both actual samples and produced CSV, JSON, Markdown and copied conditions. Its environment is `synthetic`, hardware verdict is `NOT DETERMINED`, and warnings identify short runs and fewer than three repetitions per direction. Local untracked evidence:

- `vm/runtime/rf-parser-smoke.json`
- `test-results/rf-raw-parser-smoke-20260924/`
- `test-results/rf-report-parser-smoke-20260924/`

The existing bridge/routing lab was not changed or rerun by this preparation work; its earlier validation is recorded separately. No real Pi, radio, RF path, camera or SitaWare deployment was tested.

All 101 checked local documentation links resolved; the site worksheet parsed as valid JSON and `git diff --check` passed. iperf3 and its two library dependencies were installed in the development guest for the smoke test. Graceful guest shutdown was requested after collection; saved VM disks and evidence were retained.

## Remaining dependencies

Obtain the actual radio/cable/Pi, resolve the handheld 20 MHz versus reported TSM 40 MHz configuration, and agree numerical acceptance criteria. Capture Phase 1 evidence before selecting a persistent topology. Source-specific missing manuals and administrator access are listed in the [reference review](../docs/reference-notes.md) and [integration discovery](../docs/sitaware-integration.md).
