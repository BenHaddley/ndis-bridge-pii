# Reference reading guide and evidence review

Reviewed **24 September 2026** against the existing, unmodified PDF copies. `pdftotext -layout` now extracts text from all 11 PDFs; the earlier extraction limitation no longer applies. The RF-9820S page-2 interface and bandwidth tables were also checked in a rendered page image. Checksums remain in the [PDF manifest](../references/pdf/MANIFEST.md).

## Findings that change the working assumptions

| Source and location | What the document supports | What remains unresolved |
| --- | --- | --- |
| [RF-9820S handheld sell sheet](../references/pdf/l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf), p. 2, Interfaces; footer 08/2026, L33495 | Lists USB 2.0 and IP carried over USB and Ethernet | USB protocol/class, Linux driver, host cable/pinout, mode selection, L2 behaviour and host addressing |
| Same PDF, p. 2, General and Optional Modes and Waveforms | Lists 25 kHz–20 MHz channel spacing/bandwidth, optional Wraith and TSM variants, and a wideband marketing maximum of 50 Mbps | Installed licences/firmware, applicable waveform for that maximum, usable IP throughput, and support for the reported 40 MHz TSM plan |
| [AN/PRC-171 handheld sell sheet](../references/pdf/l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf), p. 2; footer 06/2026, L33158 | Also lists IP over USB/Ethernet and the 20 MHz upper bandwidth entry | Actual unit/configuration and supported host procedure |
| [RF-9820S-ER embeddable sell sheet](../references/pdf/l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf), p. 2, waveform table; footer 04/2025, L28998 | Lists 40 MHz among optional TSM bandwidths | Applicability to the handheld; this is a separate product and is not evidence of handheld 40 MHz support |

**Action for radio discovery:** reconcile Jeremy's handheld/40 MHz plan with the actual model, firmware, waveform licence and vendor configuration guide. Preserve both the supplied information and the PDF entries until resolved. Do not substitute the 50 Mbps marketing maximum for Jeremy's 16 Mbps report or for a measurement.

The public material now supports a narrower unknown: how to use the advertised IP-over-USB interface with the Pi. It does not prove RNDIS. Phase 1 must still identify descriptors and the bound driver on real hardware.

## What to read for each phase

| Phase / question | Local reading | Pull into the bench record |
| --- | --- | --- |
| 0–1: physical Pi interface | [Pi 4 datasheet](../references/pdf/raspberry-pi-4-datasheet.pdf), §§4.1 and 5.3; [Pi 5 brief](../references/pdf/raspberry-pi-5-product-brief.pdf) for that model | Correct ports and model-specific power/interface constraints |
| 1: RNDIS descriptors/initialisation | [MS-RNDIS](../references/pdf/MS-RNDIS.pdf), §1.1 and §§2.2.2, 2.2.9 | Compare host/device role and initialisation with actual enumeration; this is the archived 2014 copy |
| 1: alternate USB Ethernet class | [CDC-ECM 1.2](../references/pdf/usb-cdc-ecm-120.pdf) | Use only when the real descriptors/driver indicate ECM |
| 2: OS networking transition | [Bookworm migration guide](../references/pdf/transitioning-bullseye-to-bookworm.pdf), PDF p. 12, Networking | NetworkManager background; verify the installed image separately |
| 3: radio feature boundaries | Three L3Harris PDFs in the table above | Model, revision, page and conflicting capability statements |
| 6: product/workflow discovery | [Headquarters flyer](../references/pdf/sitaware-headquarters-sales-flyer.pdf) and [Edge flyer](../references/pdf/sitaware-edge-sales-flyer.pdf) | Product questions for the administrator; obtain deployed integration documentation before implementation |

## Additional primary web references

| Resource | Use |
| --- | --- |
| [iperf3 official invocation manual](https://software.es.net/iperf/invoking.html) | Test direction, duration, JSON output and transport options |
| [RFC 6349](https://www.rfc-editor.org/rfc/rfc6349.html), §§3.1, 3.2, 5.2 | TCP measurement context: MTU, RTT and interpretation |
| [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html), §4.4.5 | DHCP lease reacquisition/renewal background for reconnect testing |
| [NetworkManager nmcli reference](https://networkmanager.dev/docs/api/latest/nmcli.html) | Profile inspection and checkpoint command |

RFC links are web references only: attempted RFC Editor PDF downloads returned 404 during this review, so no RFC PDF is claimed in the local collection. Existing vendor/platform PDFs were retained unchanged.

## Obtain and cite a new document

1. Identify the exact model, publisher, document number, revision and distribution permission. Obtain missing radio host-interface and SitaWare guides through the equipment/deployment contacts.
2. Download public originals to a new temporary filename. Check HTTP success, `%PDF-` signature and readability with `pdfinfo`; an extension alone is insufficient.
3. Compute SHA-256, record the exact source URL and retrieval date, and add the file to the manifest. Preserve the previous revision under a distinct filename if it is used by existing evidence.
4. Extract text for searching, then inspect the relevant page layout before interpreting a table. Record section and PDF page number, particularly when printed numbering differs.
5. Write the source claim and the project inference separately. If sources conflict, record the conflict and required resolution.

Keep restricted manuals outside the public repository; reference their approved location and revision in the private bench record. Page citations here refer to the saved copies, not whichever revision a publisher serves later.
