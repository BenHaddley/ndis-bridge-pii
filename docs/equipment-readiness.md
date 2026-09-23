# Equipment readiness and work without hardware

The project owner confirmed on 23 September 2026 that **no equipment is currently available**. Phase 0 is in progress; hardware-dependent phases are awaiting equipment. There is no known Pi SSH endpoint. A [Debian PC development VM](../vm/README.md) is now available locally; it does not replace physical equipment.

## Minimum kit by checkpoint

This is an access/loan checklist, not a purchase recommendation. Exact models and compatible radio cables must be established before ordering anything.

| Checkpoint | Required kit/access | What it enables |
| --- | --- | --- |
| USB gate | One target radio, vendor-supported USB host cable, Pi with Ethernet/USB host, boot media, suitable power and console access | Real driver enumeration, DHCP inspection and local connectivity |
| Local LAN gate | AP with documented bridge mode, Ethernet cable, laptop | Bridge/routing and local DHCP testing |
| RF gate | Second compatible radio, configured radio pair, CP endpoint and documented host attachment | Actual end-to-end routing, throughput and RF recovery tests |
| Video gate | One camera with documented stream and bitrate controls | First real video demonstration |
| Integration gate | SitaWare deployment details and test access | Version-specific position/video integration |

Radio access and the correct host cable are the first dependency. A borrowed Pi or other Linux host can help initial investigation, but another host cannot pass the Pi-specific acceptance gate.

## Work available now

- [x] Record the first-demo scope and supplied radio information.
- [x] Create equipment and acceptance records with unknowns explicit.
- [x] Prepare a read-only diagnostic collector and offline checks.
- [x] Prepare [network design/rollback](network-design.md), [RF measurement/reporting](rf-measurement.md), [video profile](video-profile.md), integration discovery and operator worksheets.
- [x] Re-read the existing public PDFs; record [page-level findings](reference-notes.md) and the unresolved 20/40 MHz discrepancy.
- [ ] Collect full radio/camera/AP documentation when exact equipment is identified.
- [ ] Define numerical quality, latency, recovery and runtime targets with the project owner.
- [x] Implement an [isolated virtual Linux network lab](../lab/README.md) for bridge/routing, DHCP and recovery checks. See the [virtual validation record](../test-results/virtual-validation.md) for passing execution results.

A virtual lab can exercise Linux bridge/routing configuration, DHCP placement and recovery procedures. It cannot establish RNDIS device compatibility, RF capacity or SitaWare support. Keep virtual evidence separately labelled; do not mark hardware gates passed from virtual results.

## Information to obtain with radio access

Ask the equipment provider for full model and firmware, enabled waveform options, host USB mode and cable part number, DHCP configuration instructions, host addressing and route support. Jeremy’s 16 Mbps report should be accompanied by its test conditions if available.

No equipment has been ordered and no messages have been sent to equipment providers. The next physical milestone is access to one radio and its supported host cable, followed by a Pi bench.
