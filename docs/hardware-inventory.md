# Hardware and access inventory

Status: project owner confirmed **no equipment currently available** on 23 September 2026. All physical items below are unavailable; specifications remain to be collected. No purchase or deployed configuration is implied.

| Item | Needed for | Known | Availability / next action |
| --- | --- | --- | --- |
| Raspberry Pi | Phase 1 | Model and OS unknown | Record model, OS, power supply and access method |
| Radio A | Phase 1 | Wiki identifies RF-9820S / AN/PRC-171; handheld PDFs advertise IP over USB/Ethernet | Confirm actual unit, firmware, USB protocol and host-interface instructions; reconcile reported 40 MHz TSM with handheld PDF's 20 MHz entry |
| USB data cable | Phase 1 | Connector/pinout unknown | Identify vendor-supported radio-to-host cable |
| Local console or Pi SSH access | Phase 1 | Not supplied | Record hostname/user or local console arrangement; no passwords in this file |
| Radio B | Phase 3 | Required for RF path | Confirm availability, firmware and compatible waveform configuration |
| AP and Ethernet cable | Phase 2 | Model unknown | Confirm AP/bridge mode and management access |
| Camera | Phase 4 | Model/protocol unknown | Obtain model, stream instructions and bitrate controls |
| CP laptop / network interface | Phase 3 | OS and radio attachment unknown | Confirm endpoint and addressing arrangement |
| Power supplies / field battery | Bench / Phase 7 | Ratings and runtime unknown | Record specifications for all equipment |
| SitaWare deployment | Phase 6 | Headquarters named in wiki | Record version, licences and administrator contact/role |

Jeremy’s supplied details: radio DHCP server; WRAITH 10/20 MHz and/or TSM 40 MHz; 16 Mbps reported for WRAITH 10 MHz. Installed support, DHCP scope and measured throughput remain unverified.

The project owner is the initial information contact; task owners will be recorded when identified. Next dependency: obtain equipment access using the [readiness checklist](equipment-readiness.md); no Pi access exists yet. Do not infer availability from the presence of this development workspace.

## Development environment

A Debian 13 amd64 VM has been created on the current x86 host with QEMU software emulation, 2 virtual CPUs, 2 GiB RAM and a 24 GiB sparse disk. Its SSH endpoint is host-local `127.0.0.1:2222`; use the [VM helper](../vm/README.md) for the dedicated key and known-hosts file. This is development infrastructure, not an available physical Pi or radio.
