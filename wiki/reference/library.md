[← Wiki index](../README.md)

# Reference library and PDF resources

Sources below were consulted on **23 September 2026**. They establish general platform behaviour, not compatibility with the 9820. Upstream `latest` and `master` pages change; record the deployed versions when reproducing results.

## Official web references and source code

| Resource | What to pull from it |
| --- | --- |
| [Microsoft: Introduction to RNDIS](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2) | Protocol purpose and host/device concepts; the normative detail is in the local [`MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf) |
| [Linux: rndis_host.c](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c) | Driver matching, implementation, quirks; compare with the installed kernel |
| [Linux: Ethernet bridging](https://docs.kernel.org/networking/bridge.html) | Forwarding, STP, multicast snooping and bridge attributes |
| [NetworkManager: nmcli examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html) | Bridge/port profiles and recovery checkpoints |
| [NetworkManager: connection properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html) | IP methods, controller/port settings, autoconnect behaviour |
| [Raspberry Pi: configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) | OS networking and NetworkManager setup |
| [Raspberry Pi: hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) | Board ports, power and hardware constraints |
| [QEMU: ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) | ARM machine selection and acceleration constraints |
| [QEMU: USB emulation/passthrough](https://www.qemu.org/docs/master/system/devices/usb.html) | Passing a real USB device to a guest |

## Downloadable PDFs

These were downloaded on **23 September 2026** into [`references/pdf/`](../../references/pdf/), verified to be real PDFs, and checksummed. Publisher, document number, revision, page count, source URL and SHA-256 for each one are recorded in [`MANIFEST.md`](../../references/pdf/MANIFEST.md). They establish platform and protocol behaviour in general; none of them says anything about the 9820, the Harris radios or the switch.

| PDF | Local copy | Useful material | Status and limitation |
| --- | --- | --- | --- |
| [Raspberry Pi 4 Model B product brief](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS/raspberry-pi-4-product-brief) | `raspberry-pi-4-product-brief.pdf` | USB/Ethernet interfaces, power, dimensions | 7 pages, April 2026 edition; marketing-level summary, not an RNDIS guarantee |
| [Raspberry Pi 4 Model B datasheet](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf) | `raspberry-pi-4-datasheet.pdf` | Section-level USB (§5.3) and Ethernet detail, power requirements, mechanicals | 13 pages, Release 1.1 (12 March 2024); the board-level reference to use over the product brief |
| [Raspberry Pi 5 product brief](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf) | `raspberry-pi-5-product-brief.pdf` | Port layout and power budget if a Pi 5 is used instead of a Pi 4 | 6 pages, April 2026 edition; no Pi 5 datasheet equivalent is included here |
| [Raspberry Pi: Transitioning from Bullseye to Bookworm](https://pip-assets.raspberrypi.com/categories/1261-transitioning/documents/RP-006519-WP-1-Transitioning%20from%20Bullseye%20to%20Bookworm.pdf) | `transitioning-bullseye-to-bookworm.pdf` | NetworkManager migration context behind the Bookworm default | 19 pages, 15 August 2024. **The URL previously cited here now 404s**; this is the working location. Use current configuration docs for deployment |
| [Microsoft: MS-RNDIS specification](https://download.microsoft.com/download/5/0/1/501ED102-E53F-4CE0-AA6B-B0F93629DDC6/Windows/%5BMS-RNDIS%5D.pdf) | `MS-RNDIS.pdf` | Message structures, control/data channels, protocol terminology | 46 pages; release stamp 1 May 2014, revision summary ending at revision 5.0 (15 May 2014). Not verified as the newest revision |
| [USB-IF: CDC Ethernet Control Model subclass](https://www.usb.org/sites/default/files/CDC1.2_WMC1.1_012011.zip) | `usb-cdc-ecm-120.pdf` | Descriptor layout and control requests for CDC-ECM | 23 pages, from the CDC 1.2 / WMC 1.1 package (January 2011). Relevant if the 9820 turns out to be ECM (Linux `cdc_ether`) rather than RNDIS. Extracted from the USB-IF archive, which also carries an adopters agreement — check those terms before redistributing |

To re-fetch or verify a copy from the project directory:

```bash
mkdir -p references/pdf
curl --fail --location --output references/pdf/raspberry-pi-4-datasheet.pdf \
  'https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf'
file references/pdf/raspberry-pi-4-datasheet.pdf
sha256sum references/pdf/raspberry-pi-4-datasheet.pdf
```

Confirm the download is a PDF before relying on it — a portal that has moved a document may return an HTML error page with a `.pdf` URL. For each saved source, record the publisher, title, revision/date, URL, retrieval date, checksum and relevant pages, as the manifest does. Raspberry Pi documents are published under a Creative Commons Attribution-NoDerivatives licence: keep the originals unmodified and separate from bench notes, and check publisher terms before redistributing copies.

## Vendor documents still needed

- **9820 user/service manual:** the topology diagram names it as a **Garmin 9820**; confirm the full manufacturer and model, then collect USB modes, IP defaults, stream access and firmware notes. If it is a Garmin marine unit, check whether it has a native Ethernet marine-network port — that would change the design substantially. See [Device facts to collect](../plan/device-facts.md).
- **Harris radio documentation:** model, waveform, IP service description, whether it bridges Layer 2 or routes Layer 3, usable throughput per waveform/bandwidth setting, MTU, multicast handling, and DHCP behaviour. This is now the **highest-value missing document** — see [Transport link](../concepts/transport-link.md).
- **Switch and router documentation:** VLAN and trunking configuration, IGMP snooping and querier settings, port isolation, and whether the router sits in-path or upstream-only.
- **Camera manuals:** supported stream/discovery protocols, bitrate controls and simultaneous-client limits.

Add exact document titles, revisions and page references here when identified. Do not substitute a manual for an unrelated product sharing the number "9820".

Note that these vendor documents are distributed under their own terms. Harris/L3Harris tactical radio documentation in particular is frequently export-controlled or distribution-restricted; obtain it through the proper channel for your programme rather than from a general web search, and do not commit restricted documents into this repository.

---

Previous: [Test record template](../test/test-record-template.md)
