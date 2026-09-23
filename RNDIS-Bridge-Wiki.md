# RNDIS Bridge on Raspberry Pi

_Last updated: Sep 24, 2026_

**Build plan:** [Phased implementation roadmap](BUILD-ROADMAP.md) — milestones, dependencies, deliverables and acceptance gates.

**No-hardware development:** [Run the virtual network lab](lab/README.md) to exercise bridging, routing, DHCP and link recovery in isolated Linux namespaces.

**Prepared next steps:** [Network design and rollback](docs/network-design.md), [RF measurement and report tool](docs/rf-measurement.md), [video profile](docs/video-profile.md), and [SitaWare discovery](docs/sitaware-integration.md). These are bench preparation, not completed hardware milestones.

**PDF review:** [Page-level findings and reading guide](docs/reference-notes.md). The RF-9820S sheet advertises IP over USB; its actual USB protocol and Linux compatibility remain untested. The handheld’s listed 20 MHz bandwidth ceiling also needs reconciling with the reported 40 MHz TSM plan.

## Contents

- [The brief](#the-brief)
- [Short answer](#short-answer)
- [What the 9820 turned out to be](#what-the-9820-turned-out-to-be)
- [Architecture](#architecture)
- [What RNDIS actually is](#what-rndis-actually-is)
- [How the Pi interfaces RNDIS to the LAN](#how-the-pi-interfaces-rndis-to-the-lan)
- [The Wi-Fi AP: camera ingest](#the-wi-fi-ap-camera-ingest)
- [Beyond the brief: the radio backhaul](#beyond-the-brief-the-radio-backhaul)
- [Beyond the brief: SitaWare HQ](#beyond-the-brief-sitaware-hq)
- [Bench preparation](#bench-preparation)
- [Persistent NetworkManager bridge](#persistent-networkmanager-bridge)
- [Routing fallback design](#routing-fallback-design)
- [Hardware test plan](#hardware-test-plan)
- [DHCP: pick exactly one server](#dhcp-pick-exactly-one-server)
- [Packet tracing and troubleshooting](#packet-tracing-and-troubleshooting)
- [Throughput and acceptance tests](#throughput-and-acceptance-tests)
- [Testing without a Pi: an ARM64 VM](#testing-without-a-pi-an-arm64-vm)
- [Open risks and unknowns](#open-risks-and-unknowns)
- [Next steps checklist](#next-steps-checklist)
- [Device facts to collect](#device-facts-to-collect)
- [Reference library and PDF resources](#reference-library-and-pdf-resources)
- [Test record template](#test-record-template)

## The brief

> Try this:
> Linux build
> Take the USB RNDIS connection from a 9820 and port it thru the Linux build out the Ethernet socket.
> Could it be done on a Raspberry Pi?
> This Ethernet connection then goes to a wifi access point to ingest video feeds.
> Have a think about how the Pi can interface the RNDIS connection to LAN.
> Your thoughts?

Everything in this wiki traces back to that. Sections are marked where they go **beyond the brief** — the radio backhaul and the SitaWare requirement came later and are much larger pieces of work than the question as originally asked.

## Short answer

**Yes, a Raspberry Pi can do this, and the Linux side is routine.** Linux has a mature host-side RNDIS driver (`rndis_host`); once the 9820 appears as a network interface, joining it to `eth0` is a standard bridge or route. A Pi 4 or Pi 5 is a sensible box for it. See [How the Pi interfaces RNDIS to the LAN](#how-the-pi-interfaces-rndis-to-the-lan) for the direct answer to that question.

**Three things qualify that, in order of how much they matter.**

**1. The 9820 is a radio, not a video device.** It is the L3Harris RF-9820S (AN/PRC-171) Compact Team Radio. The brief reads as though the Pi feeds video *into* the 9820; in fact the Pi puts video *onto a tactical MANET radio* for transport elsewhere. See [What the 9820 turned out to be](#what-the-9820-turned-out-to-be).

**2. IP over USB is advertised, but RNDIS and Linux compatibility are unconfirmed.** The [RF-9820S sell sheet](references/pdf/l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf), p. 2, lists IP over USB and Ethernet. It does not specify the USB class, cable, host setup or Linux driver. Vendor host-interface instructions and real enumeration evidence are still required.

**3. Size the video to the configured waveform and measured link.** Jeremy reports **WRAITH at 10 or 20 MHz**, and/or **TSM at 40 MHz**, with **16 Mbps available from WRAITH at 10 MHz**. This replaces the earlier generic low-single-digit throughput assumption. See [Jeremy’s radio update](#jeremys-radio-update) for provenance and remaining questions.

Transparent forwarding can be sufficient if the combined camera traffic fits the usable link capacity and the radio supports the chosen network arrangement. Camera bitrate settings are the first control; stream selection or transcoding is only needed if the required traffic exceeds the available capacity. The Pi does not automatically need to terminate and re-encode video.

**My recommendation:** do not design further until two cheap tests are done. Plug the radio into a Pi and run `lsusb` / `ip link` — that answers premise 2 in minutes. Then measure real throughput between two radios at operational range — that sizes everything else. Both are quick, and between them they determine whether this is a networking job or a video-engineering job.

## What the 9820 turned out to be

The "9820" is the **L3Harris RF-9820S Compact Team Radio, designated AN/PRC-171** — a single-channel, low-SWaP handheld from the Falcon IV family running wideband MANET plus narrowband voice and PLI.

This matters because it changes how the brief reads:

| The brief implies | Actually |
| --- | --- |
| The 9820 is an endpoint that receives video | It is a radio that transports traffic to other radios |
| "Ingest video feeds" means into the 9820 | It means into the network, *through* the radio, to somewhere else |
| The Pi's job ends at the USB port | The Pi's job is bounded by what the RF link can carry |

An earlier draft of this wiki treated the 9820 as an unidentified video receiver, and a topology diagram guessed it was a Garmin chartplotter. Both were wrong. Throughout this document, **"the radio" means the RF-9820S**.

What remains genuinely unconfirmed is not *what* the device is, but *what interface it presents to a host computer*. See [Device facts to collect](#device-facts-to-collect).

## Architecture

Both wireless links in this system are real and do different jobs. The Wi-Fi AP is **local camera ingest**, as the brief specifies. The radio is **long-haul backhaul**, added later. One does not replace the other.

```
  FIELD (with the operator)                                    COMMAND POST
  ═══════════════════════════════════════════════             ═══════════════════════

  Camera 1 ┐
           │ Wi-Fi
  Camera 2 ┼┄┄┄┄► ┌──────────────┐
           │      │  Wi-Fi AP    │   ← the brief's "wifi access point
  Camera N ┘      │ (bridge mode)│      to ingest video feeds"
                  └──────┬───────┘
                         │ Ethernet
                       eth0
                  ┌──────┴───────┐
                  │ Raspberry Pi │   ← the brief's "Linux build"
                  │   eth0 ↔ usb0│      RNDIS ↔ LAN; rate control if needed
                  └──────┬───────┘
                       usb0
                         │ USB / RNDIS   ← interface type UNCONFIRMED
                  ┌──────┴───────┐                      ┌──────────────┐
                  │  AN/PRC-171  │┄┄┄┄ MANET RF ┄┄┄┄┄┄┄►│  AN/PRC-171  │
                  │  (RF-9820S)  │   ← the bottleneck   │  (RF-9820S)  │
                  └──────────────┘                      └──────┬───────┘
                                                               │ Ethernet
                                                        ┌──────┴───────┐
                                                        │switch/router │
                                                        └──────┬───────┘
                                                               │
                                                        SitaWare HQ ──► clients
```

### What is in the brief and what is not

| Element | In the brief? | Notes |
| --- | --- | --- |
| Raspberry Pi, RNDIS → Ethernet | **Yes** — the whole question | [How the Pi interfaces RNDIS to the LAN](#how-the-pi-interfaces-rndis-to-the-lan) |
| Wi-Fi AP for camera ingest | **Yes**, explicitly | [The Wi-Fi AP](#the-wi-fi-ap-camera-ingest) |
| Cameras | **Yes**, implied by "video feeds" | Assumed Wi-Fi; confirm |
| AN/PRC-171 MANET backhaul | No | [Beyond the brief](#beyond-the-brief-the-radio-backhaul) |
| CP switch/router | No | Conventional kit; see the same section |
| SitaWare HQ integration | No | [Beyond the brief](#beyond-the-brief-sitaware-hq) — the largest addition |

### SWaP: the field kit is not small

Cameras, a Wi-Fi AP, a Pi, the radio, and power for all of it ride on one person. Networking diagrams hide this. Before committing, weigh and power-budget the whole assembly — and note that the AP and Pi both need power the radio's own battery is not there to provide.

If that total is unacceptable, the honest alternatives are fewer cameras, wired cameras (removing the AP), or an integrated device that collapses AP and Pi into one box.

## What RNDIS actually is

**RNDIS (Remote NDIS)** is a Microsoft-originated protocol that lets a USB connection carry Ethernet frames. Instead of presenting as USB storage or a serial device, the peripheral presents as a **network adapter over USB**.

The protocol is documented in the local copy of the Microsoft specification, [`references/pdf/MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf):

- The bus transport splits into a **control channel** (control messages) and a **data channel** (network packet data) — glossary, §1.1, p. 6.
- The host opens with `REMOTE_NDIS_INITIALIZE_MSG` (§2.2.2, p. 12), which carries a `MaxTransferSize`; the device answers with `REMOTE_NDIS_INITIALIZE_CMPLT` (§2.2.9, p. 18). A device that fails this handshake never becomes a usable NIC.
- Ethernet frames ride inside `REMOTE_NDIS_PACKET_MSG` (§2.2.14, p. 22).
- Link state is signalled by `REMOTE_NDIS_INDICATE_STATUS_MSG` (§2.2.7, p. 16), using `RNDIS_STATUS_MEDIA_CONNECT` (`0x4001000B`) and `RNDIS_STATUS_MEDIA_DISCONNECT` (`0x4001000C`) from the common status values table (§2.2.1.2, p. 12). This is the mechanism behind "link flaps / carrier never comes up".

Linux provides the host-side `rndis_host` driver, with USB networking helpers including `usbnet` and `cdc_ether`. A supported device appears as `usb0` or a MAC-derived name like `enx001122334455` — record the actual name rather than assuming. See the [upstream driver source](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c).

**RNDIS is not the only possibility.** If the descriptors show CDC-ECM instead, `cdc_ether` handles it and the governing document is the USB-IF subclass specification at [`references/pdf/usb-cdc-ecm-120.pdf`](references/pdf/usb-cdc-ecm-120.pdf). Keep both to hand until the radio's descriptors have actually been read — and be prepared for a third answer, that it presents nothing standard at all.

Once the interface exists, it behaves like any other Linux network interface for bridging, routing, `iptables` and DHCP. That is what makes the concept work: nothing downstream needs to know the "cable" is USB underneath.

**Caveat:** RNDIS is a spec, but implementations vary — odd MTU behaviour and flaky link-state reporting are common. The specification's own revision summary ([`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf), pp. 3–4) runs through several "significantly changed the technical content" revisions, which is a fair hint that implementations built against different revisions differ in practice.

## How the Pi interfaces RNDIS to the LAN

This is the brief's direct question. There are two mechanisms, and a third thing the Pi must also do.

### Option 1: Layer-2 bridge

```
         br0
      /       \
   usb0       eth0
     |          |
   radio     Wi-Fi AP → cameras
```

Linux joins the two interfaces into `br0`, behaving as a two-port switch. The radio's host interface and every camera end up on the **same subnet** — e.g. `192.168.1.0/24`. Raspberry Pi OS supports this through NetworkManager; see [Persistent NetworkManager bridge](#persistent-networkmanager-bridge).

**Why it is the natural first attempt:** broadcast discovery, multicast, UDP streaming and "find devices on my subnet" all assume a shared LAN segment. A bridge preserves that.

### Option 2: Layer-3 routing

```
radio host iface              camera LAN
192.168.10.x                  192.168.20.x
     |                             |
    usb0    Raspberry Pi    eth0
     \____ (IP forwarding) ______/
```

Two subnets, with the Pi forwarding between them (`net.ipv4.ip_forward=1`, plus `iptables`/`nftables` rules). Easier to reason about and firewall, but broadcast/multicast discovery does not cross a router boundary without protocol-specific help. See [Routing fallback design](#routing-fallback-design).

### Which one

**For the brief as written — Pi between an AP and a local device — bridge first.** It is simplest and preserves discovery.

**For the real system with the radio in it — expect routing.** A MANET radio is a routing node by design; each radio maintains routes to other radios. The radio will likely expect its attached host to sit on a small subnet with the radio as gateway, not to present a bridge full of foreign MAC addresses. Bridging `eth0` into `usb0` may simply not work. Confirm against the radio's ICD before building either.

A reasonable compromise, and the likely end state: **bridge the cameras and the Pi on the `eth0` side, route from there onto the radio.**

### The third job: rate adaptation

Both options must keep aggregate traffic within the measured RF capacity. Jeremy’s reported 16 Mbps at WRAITH 10 MHz provides a starting point, not a measured application budget. If camera settings already fit, forwarding needs no stream termination. Where additional rate control is required, the options are:

| Approach | Notes |
| --- | --- |
| **Configure cameras down** | If the cameras can be driven to a low enough bitrate natively, no transcoding is needed. **Try this first** — it costs nothing |
| **Transcode on the Pi** | `ffmpeg` re-encoding to a target bitrate. Works, but watch CPU, heat and power on a battery-powered Pi |
| **Relay selectively** | Only forward the stream an operator has asked for, rather than all cameras continuously |
| **Store-and-forward** | Record locally at full quality, transmit selectively. Decouples capture quality from link capacity entirely |

## The Wi-Fi AP: camera ingest

This is the brief's element, and it is straightforward.

**Put the AP in bridge/AP mode, not router mode.** If it insists on being its own NAT router it adds a second layer of address translation that fights the Pi's bridge. Check it has a genuine bridge or AP mode.

Points that actually matter:

- **Client isolation must be off.** Many APs isolate wireless clients from each other and from the wired port by default. That will block camera-to-Pi traffic and is a very common cause of "everything looks configured but nothing talks".
- **Multicast handling.** If the cameras use multicast discovery or streaming, check the AP does not suppress or rate-limit it. Wi-Fi multicast is often sent at the lowest basic rate, which is expensive; some APs convert it to unicast, some drop it.
- **One DHCP server only** — see [DHCP](#dhcp-pick-exactly-one-server). The AP is a likely accidental second one.
- **Capacity.** Several simultaneous camera streams over Wi-Fi is usually fine, but confirm the AP and its radio configuration can carry the aggregate. This side is not the bottleneck; the radio is.

**A switch is optional here.** The AP is the aggregation point and plugs straight into the Pi's `eth0`. Add a small switch only if there are wired cameras too, or other wired devices on that segment. If you do, it needs IGMP snooping with a **querier** — on an isolated segment there is no router to send IGMP queries, so multicast group memberships expire and streams stall a minute or two in.

## Beyond the brief: the radio backhaul

> Not in the original brief. Added when the transport was specified as Harris radios.

Two AN/PRC-171 (RF-9820S) radios, one with the operator, one at the command post.

### Jeremy's radio update

**Source:** Jeremy, relayed by the project owner in this conversation on 23 September 2026. These are project-supplied radio details, not claims extracted from the public PDFs or independently measured here.

| Item | Updated project information |
| --- | --- |
| Waveform selection | Use **WRAITH, 10/20 MHz channel bandwidth**, and/or **TSM, 40 MHz channel bandwidth**, in place of ANW2C in the design |
| WRAITH at 10 MHz | Jeremy reports it can deliver **16 Mbps** |
| WRAITH at 20 MHz | Throughput not supplied; do not assume twice the 10 MHz result |
| TSM at 40 MHz | Throughput not supplied; measure separately |
| DHCP | **The radio has a built-in DHCP server**; confirm its enabled state, pool and host-interface scope |

MHz describes RF channel bandwidth; Mbps describes data rate. Confirm whether the reported 16 Mbps is a nominal radio rate or measured usable IP throughput, and record range, hop count, traffic direction and concurrent load. Also confirm the installed firmware/licences support the intended waveform configuration; “and/or” does not establish simultaneous operation.

This update supersedes the earlier generic throughput assumption and the uncertainty about whether a radio DHCP server exists. It does not establish USB driver compatibility, DHCP reach across routed segments, or end-to-end Layer-2 bridging.

### What the public material says

Downloaded to [`references/pdf/`](references/pdf/) and catalogued in [`MANIFEST.md`](references/pdf/MANIFEST.md):

| Document | Local copy |
| --- | --- |
| AN/PRC-171 Compact Team Radio sell sheet | `l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf` |
| RF-9820S Compact Team Radio sell sheet | `l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf` |
| RF-9820S-ER Embeddable Modular Radio sell sheet | `l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf` |

The PDFs are now text-extractable with `pdftotext -layout`. On 24 September 2026, the saved copies were reviewed and the RF-9820S page-2 table was also inspected visually. See the [reference review](docs/reference-notes.md) for exact document identifiers and limitations.

The [RF-9820S handheld sheet](references/pdf/l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf), p. 2, advertises IP over USB and Ethernet, a 25 kHz–20 MHz bandwidth range, optional Wraith/TSM waveforms, and a wideband maximum of 50 Mbps. These are product claims, not measurements of the proposed configuration. The [AN/PRC-171 sheet](references/pdf/l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf), p. 2, also lists IP over USB and the same bandwidth range.

**Open discrepancy:** Jeremy reports TSM at 40 MHz. The separate [RF-9820S-ER embeddable sheet](references/pdf/l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf), p. 2, lists 40 MHz as a TSM option, but that does not establish handheld support. Resolve model, firmware and installed waveform options before including 40 MHz in the hardware test plan.

**What these sheets do not establish:**

- USB class/protocol, compatible Linux driver, cable pinout or host setup.
- Measured usable IP throughput for WRAITH 10/20 MHz or the reported TSM configuration.
- Whether the host interface accepts multiple MAC addresses or supports the required routed camera subnet.
- MTU, multicast handling and DHCP configuration/scope.

Obtain the radio’s Interface Control Document and programming instructions, then confirm them on hardware. The public IP-over-USB entry narrows the Phase 1 question; it does not pass that gate.

### Throughput is the binding constraint

Use **WRAITH 10 MHz: 16 Mbps, as reported by Jeremy**, as the initial reference. WRAITH 20 MHz and TSM 40 MHz need their own throughput figures. Available video capacity must be established with the intended range, terrain, hop count, participants and concurrent voice/PLI traffic; confirm the configured traffic priorities.

Measure it properly: over the actual radios, at operational range, with the net carrying its normal load. Not a datasheet maximum, and not two radios on a desk a metre apart. Then size the video to the result, using the rate-adaptation options above.

### MTU, multicast, DHCP

- **MTU.** Tactical links commonly run reduced MTU. A path MTU smaller than the LAN's causes fragmentation or silent drops of full-size frames — "small packets work, video does not". This interacts with the RNDIS `MaxTransferSize` at the USB end.
- **Multicast.** Confirm whether the radio forwards it at all. Many tactical links suppress it because it is expensive on a shared channel.
- **DHCP.** Jeremy confirms a server in the radio. Use it on the attached LAN if its scope and forwarding behaviour support that arrangement. Separate routed LANs need their own address assignment or an explicitly supported DHCP relay.

### CP end kit

Mains power, benign environment, conventional hardware: a managed switch (Catalyst 9200/9200CX or similar) with IGMP snooping, or an ISR 1100 with integrated switch if you want routing in the same box. Its configuration is likely constrained by an existing CP network you do not control — check what is already there before buying anything.

## Beyond the brief: SitaWare HQ

> Not in the original brief. This is the largest addition, and a separate project from the networking.

The command post runs **SitaWare Headquarters** (Systematic), and the requirement is that the operator and their cameras appear on the SitaWare map.

> **Connectivity is not integration.** A bridge moves packets; it does not create tracks or video feeds in a C4ISR system. Something must *speak SitaWare's languages*. On this architecture that something is the Pi, and it is more work than the bridge.

### What SitaWare accepts

From Systematic's public [open-architecture page](https://systematic.com/int/industries/defence/products/sitaware-suite/sitaware-edge/open-architecture/):

| Purpose | Mechanism |
| --- | --- |
| Position / tracks on the map | **Cursor-on-Target (CoT)** |
| Location input from a device | **NMEA 0183**, **ICD-GPS-153**, **GPSD** |
| Video streaming | **RTSP**, **RTMP**, DirectShow |
| Geo-referenced motion imagery | **NATO STANAG 4609** with MISB KLV metadata |
| Anything else | Published **APIs** and an **SDK** |

Verify against your own version, licence and deployment — that list is from public marketing pages, not an interface specification.

### Two separate problems

**Position on the map — easy.** CoT messages are tiny and survive a constrained link comfortably. But first check whether the radio's own **PLI reporting already puts the operator on the map**. If it does, this is already solved and needs no work at all.

**Video into SitaWare — harder.** Cheapest first: pass the camera's RTSP stream through (possibly proxied by the Pi so the CP sees one stable address); transcode on the Pi and serve RTSP; or produce STANAG 4609 with KLV for properly geo-referenced FMV with viewshed. Choose by what you actually need on the map — "see their position and open their camera" is far cheaper than "video footprint drawn on the map".

### Check SitaWare Edge first

Systematic's dismounted product is **SitaWare Edge**. If the operator carries an EUD running Edge, position reporting and map presence are solved by Edge, and Edge is documented as playing STANAG 4609 feeds. The Pi's job then shrinks back to getting camera video onto the network — much closer to the original brief. Ask whether Edge is already licensed before building a CoT/FMV pipeline on a Raspberry Pi.

## Bench preparation

Use a Pi with Ethernet and a USB host port, a good power supply, a data-capable USB cable, the Wi-Fi AP, and a laptop. Keep the radio link out of the bench path until the wired case works.

Three figures from the local [Raspberry Pi 4 Model B datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) (Release 1.1) shape the setup:

| Datasheet reference | Figure | Why it matters |
| --- | --- | --- |
| §2.2 Interfaces, p. 6 | 2× USB2 and 2× USB3 type-A sockets; 1× Gigabit Ethernet | The two interfaces being joined. Interface ratings only |
| §4.1 Power Requirements, p. 8 | USB-C supply at **5 V, 3 A**; 5 V 2.5 A only if downstream USB draws under 500 mA | The radio is a downstream USB device, so the 2.5 A allowance likely does not apply |
| §5.3 USB, p. 11 | Downstream USB current limited to **~1.1 A aggregate** across all four sockets | A device near that ceiling is a prime suspect for resets and vanishing interfaces |

For a Pi 5, take figures from [`raspberry-pi-5-product-brief.pdf`](references/pdf/raspberry-pi-5-product-brief.pdf) rather than assuming the Pi 4 numbers carry over. The [Pi 4 product brief](references/pdf/raspberry-pi-4-product-brief.pdf) is a shorter summary; prefer the datasheet where they differ.

Install diagnostics:

```bash
sudo apt update
sudo apt install usbutils iproute2 ethtool tcpdump iperf3
```

Record the starting state before changing anything:

```bash
cat /etc/os-release
uname -a
nmcli --version
nmcli device status
nmcli -f NAME,UUID,TYPE,DEVICE connection show
ip -br address
ip route
lsusb
lsusb -t
sudo journalctl -k -b --no-pager | tail -100
```

Replace `usb0` and `eth0` throughout with the real names. Inspect the USB NIC:

```bash
sudo ethtool -i usb0
ip -s link show dev usb0
sudo journalctl -k -f
```

If no interface appears, inspect the USB descriptors and kernel messages before assuming RNDIS. `sudo modprobe rndis_host` loads an available module; it cannot make an unsupported interface compatible. The Pi is the **host** here, so USB *gadget* instructions — making a Pi impersonate a network device — address a different setup entirely. See [MS-RNDIS.pdf](references/pdf/MS-RNDIS.pdf) §1.1 p. 6 for the host/device split, which maps onto Pi/radio here.

## Persistent NetworkManager bridge

An **IPv4, isolated bench example**, adapted from the [NetworkManager bridge examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html). It assumes the radio accepts `192.168.1.10/24` and the Pi can use `192.168.1.20/24`. If the radio has a fixed subnet, adapt the plan to it first.

Run the cutover at a local console — moving `eth0` into a bridge can interrupt SSH. Record existing profile names, UUIDs and autoconnect settings for recovery.

Raspberry Pi OS uses NetworkManager by default from Bookworm onward, but verify with `nmcli device status` rather than trusting the version: a Pi upgraded in place from Bullseye may still be running `dhcpcd`. Background is in [`transitioning-bullseye-to-bookworm.pdf`](references/pdf/transitioning-bullseye-to-bookworm.pdf) (19 pages, 15 August 2024) — see PDF p. 12, Networking; text was successfully extracted during the 24 September review. For deployment prefer the current [Raspberry Pi configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) docs.

### Create the profiles

Check these names and `br0` do not already exist. Run once:

```bash
sudo nmcli connection add type bridge ifname br0 con-name rndis-br0 \
  ipv4.method manual ipv4.addresses 192.168.1.20/24 \
  ipv4.never-default yes ipv6.method disabled
sudo nmcli connection add type ethernet ifname eth0 \
  con-name rndis-lan-port master br0
sudo nmcli connection add type ethernet ifname usb0 \
  con-name rndis-usb-port master br0
sudo nmcli connection modify rndis-br0 bridge.stp yes
```

`master` is the compatibility alias for newer `controller` terminology. The Pi's management address belongs on `br0`; member ports should not retain independent IP configuration. No gateway or DNS is needed for same-subnet bench traffic. Disabling IPv6 on this profile does not filter IPv6 frames passing through the bridge. Properties are documented in [NetworkManager's reference](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

### Activate and check

For each existing standalone profile bound to these ports, record its UUID and autoconnect setting first, then:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect no
sudo nmcli connection down uuid <OLD_PROFILE_UUID>
```

Then bring up the bridge:

```bash
sudo nmcli connection up rndis-br0
sudo nmcli connection up rndis-lan-port
sudo nmcli connection up rndis-usb-port
nmcli device status
ip -br address
bridge link show
```

Allow STP convergence before testing. Verify both ports belong to `br0` and reach forwarding state. Connect the AP's LAN port to `eth0` per its bridge-mode manual. For the all-static example, disable DHCP on the test LAN and assign the laptop `192.168.1.30/24`, cameras `.101/24` and `.102/24`.

Do not use NetworkManager `ipv4.method shared` for this transparent bridge example; it introduces connection-sharing behaviour.

### Recovery

```bash
sudo nmcli connection down rndis-br0
sudo nmcli connection delete rndis-lan-port rndis-usb-port rndis-br0
```

Then restore each old profile's recorded autoconnect value and reactivate those previously active:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect yes
sudo nmcli connection up uuid <OLD_PROFILE_UUID>
```

Use `no` instead of `yes` if that was the recorded value. **A reboot is not a rollback** for persistent NetworkManager configuration.

## Routing fallback design

Use routing when the USB device cannot support transparent bridging, or when separate subnets are required — which, with a MANET radio, is the expected case. First confirm the radio can use a gateway or suitable static routes.

| Segment | Example addressing | Required return path |
| --- | --- | --- |
| USB | Pi `192.168.10.1/24`, radio host interface `192.168.10.2/24` | Radio's route to `192.168.20.0/24` via `.10.1` |
| Camera LAN | Pi `192.168.20.1/24`, cameras `.20.101/24` onward | Camera/laptop route to `192.168.10.0/24` via `.20.1` |

These are alternatives to the bridge addresses, not additions. Remove bridge membership before configuring independent routed interfaces. Enable IPv4 forwarding and add narrowly scoped forwarding rules to the existing firewall, including reply traffic. Do not flush an existing ruleset.

**Route injection is the key question:** can the camera subnet be advertised into the MANET so the CP reaches cameras by their own addresses, or must the Pi NAT everything behind the radio's host address? NAT helps when an endpoint cannot install a return route, but it changes peer addresses and complicates incoming connections and discovery. It is a design choice, not a requirement.

Routing is not yet a copy-and-run recipe in this wiki; the final rules depend on traffic direction and application ports, which remain unknown.

## Hardware test plan

Use a Pi 4 or Pi 5. Steps in order — each one isolates a different unknown, which is the point.

**1. Confirm Linux sees the radio as a NIC**

```bash
lsusb
ip link
dmesg | tail -50
```

Look for `usb0` or `enx...` alongside `lo`, `eth0`, `wlan0`. **This single step answers the project's biggest unknown.** Do it before anything else.

**2. Bring up the bridge**

Use the [NetworkManager procedure](#persistent-networkmanager-bridge). Do not mix temporary `ip link` configuration with active NetworkManager profiles on the same interfaces.

**3. Connect the Wi-Fi AP**

Wire the AP's LAN port to `eth0`, in bridge/AP mode, with client isolation off.

**4. Ping test, local only**

Connect a laptop to the AP's Wi-Fi and ping the radio's host interface, and vice versa. Keep the RF link out of it. If this works, the brief's core mechanism is proven.

**5. Camera ingest**

Bring up one camera on the AP and confirm the Pi can pull its stream. Still no RF link.

**6. Add the RF link**

Now bring the radios in and repeat from the CP end. If step 4 passed and this fails, the radio is the problem, not the bridge — which is why these are separate steps.

**7. Real video within the measured link budget**

Only now try video end to end, at a bitrate derived from the measured RF throughput.

## DHCP: pick exactly one server

Use one DHCP server, or none for an all-static test. Candidates that may each try to serve: the AP, the radio, the Pi, and the CP router. Multiple servers on one broadcast domain cause random address conflicts and clients silently picking the wrong gateway/DNS.

**Preferred starting point: inspect the radio’s built-in DHCP server, confirmed by Jeremy.** Record its pool, subnet mask, gateway, DNS options and lease/reservation controls. On a locally bridged camera LAN, use it as the sole server if DHCP requests reach it; disable competing AP/Pi DHCP services. Give fixed management addresses reservations or addresses outside the pool.

For a routed Pi, the radio’s DHCP server may serve only the USB-side subnet. Cameras on a separate Ethernet subnet need local DHCP, static addresses, or a supported relay. One server per isolated broadcast domain is valid; do not assume a local radio server assigns addresses across the RF network.

The following remains an **alternative all-static bench plan**, not the radio’s known defaults. Disable DHCP for this test, or exclude these addresses from its pool before using them:

| Device | Address |
| --- | --- |
| Radio host interface | `192.168.1.10` |
| Pi (`br0`) | `192.168.1.20` |
| Laptop | `192.168.1.30` |
| Camera 1 | `192.168.1.101` |
| Camera 2 | `192.168.1.102` |

## Packet tracing and troubleshooting

Run captures in separate terminals while initiating traffic:

```bash
sudo tcpdump -ni eth0 -e 'arp or icmp'
sudo tcpdump -ni usb0 -e 'arp or icmp'
```

Short capture to/from the radio's example address:

```bash
sudo timeout 30 tcpdump -ni usb0 -s 0 -w rndis-test.pcap 'host 192.168.1.10'
```

**Packet captures can contain video and credentials.** Keep them local and redact before sharing. They are gitignored in this repo.

| Symptom | Check next | Reference |
| --- | --- | --- |
| Nothing in `lsusb` | Data cable (not charge-only), power, USB host/peripheral roles, correct port | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §4.1 p. 8 |
| USB enumerates but no NIC | USB mode/descriptors, kernel log, driver availability | [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12, §2.2.9 p. 18 (init handshake); [CDC-ECM](references/pdf/usb-cdc-ecm-120.pdf) if descriptors say ECM |
| NIC appears then disappears | USB reset messages, power supply, cable | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.3 p. 11 (~1.1 A limit); [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.6 p. 15 (reset), §2.2.8 p. 17 (keepalive) |
| Link never comes up, or flaps | Whether the device ever signals media connect | [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.7 p. 16, status values §2.2.1.2 p. 12 |
| Cameras associate but cannot reach the Pi | **AP client isolation** — the most common cause. Then bridge membership, ARP | [The Wi-Fi AP](#the-wi-fi-ap-camera-ingest) |
| Pi reaches the radio but the CP cannot | Whether the RF link forwards Layer 2 at all; route injection; NAT | [Radio backhaul](#beyond-the-brief-the-radio-backhaul) |
| No address on a DHCP client | Server presence, scope, competing servers, UDP 67/68 captures | [DHCP](#dhcp-pick-exactly-one-server) |
| IP works; discovery fails | Discovery protocol, AP filtering, multicast memberships, firewall | — |
| Stream starts then stalls | **IGMP querier absence** (memberships expiring), bitrate bursts exceeding the RF link, USB resets, thermals | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.6 p. 11 (0–50 °C; throttles under 85 °C) |
| Video breaks up under load | Rate mismatch — the Pi is forwarding more than the RF link carries | [Rate adaptation](#the-third-job-rate-adaptation) |
| Works until reboot | Profile autoconnect, competing old profiles, interface name changes | [Bookworm whitepaper](references/pdf/transitioning-bullseye-to-bookworm.pdf) |
| Ping fails but application works | Endpoint may block ICMP; validate the real protocol | — |

Additional observations:

```bash
bridge fdb show br br0
bridge mdb show dev br0
ip -s link show dev eth0
ip -s link show dev usb0
sudo nft list ruleset
```

### Multicast and discovery

The Linux bridge enables multicast snooping by default and tracks group membership. Check `bridge mdb show` while clients are active. Snooping needs appropriate query behaviour — do not assume the AP supplies a querier. For a controlled comparison, record the current setting with `ip -d link show br0`, temporarily run `sudo ip link set dev br0 type bridge mcast_snooping 0`, and restore it afterwards. This is a runtime test and can increase flooding.

A successful comparison points toward multicast handling; it is not a permanent fix. Check the AP as well as the Pi.

### Isolating which hop broke

Test hop by hop rather than end to end:

1. Camera ↔ Pi across the AP (no radio).
2. Pi ↔ radio across `usb0` only.
3. Pi ↔ CP across the RF link.

## Throughput and acceptance tests

Use the [RF collection procedure and offline report tool](docs/rf-measurement.md) to preserve raw iperf3 JSON, test conditions and directional planning budgets. Hardware acceptance remains separate.

The Pi 4's Gigabit Ethernet and USB sockets ([Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §2.2, p. 6) are interface ceilings only, and irrelevant here. Measure each segment separately — one end-to-end number will not tell you which hop is the ceiling:

| Segment | How to measure | Expect |
| --- | --- | --- |
| Camera ↔ Pi over Wi-Fi | `iperf3` laptop-to-Pi over the AP | Tens of Mbit/s — not the bottleneck |
| Pi ↔ radio over USB | Device test service, or real streaming | Unknown until tested |
| Across the RF link | `iperf3` between laptops at each end, at operational range | Reference: Jeremy reports **16 Mbps at WRAITH 10 MHz**; measure usable throughput for each selected waveform/bandwidth |

Derive the video budget from **measured usable IP throughput**, allowing for concurrent traffic and bitrate peaks. Do not reserve the entire reported 16 Mbps for encoded video.

Illustrative arithmetic only: if testing establishes 16 Mbps usable throughput, an initial 25% reserve leaves **12 Mbps** for video and its transport overhead. Four streams configured at 2 Mbps total **8 Mbps of encoded payload**; four at 4 Mbps total **16 Mbps** and exceed that provisional budget before transport overhead. The reserve is a planning choice, not a radio specification or acceptance guarantee. Measure bursts, loss and other traffic before selecting final settings.

Measure with endpoints that can run `iperf3` — do not assume the radio can.

| Test | Pass evidence |
| --- | --- |
| Enumeration | Stable NIC, correct driver, no recurring USB errors |
| Addressing | Unique addresses; one DHCP server or fully static |
| Camera ingest | Pi pulls every intended camera stream over the AP |
| Local connectivity | Laptop on Wi-Fi reaches the radio host interface through the bridge |
| RF link budget | Measured usable throughput at operational range, with margin |
| Rate adaptation | Video sized to the RF link survives sustained transmission without breakup |
| SitaWare | Operator track on the map; video opens from a SitaWare client |
| Soak | 60 minutes minimum; record loss, stalls and errors |
| Recovery | USB reconnect, RF link drop/reacquire, AP restart and Pi reboot all restore service |
| Persistence | Ports rejoin `br0`; no old profile steals an interface |

Agree acceptable latency, frame loss, reconnect time and test duration before calling this production-ready. Record firmware, kernel, OS, topology and stream settings with every result.

## Testing without a Pi: an ARM64 VM

**Implemented development environment:** the project owner selected a [Debian amd64 PC VM](vm/README.md). It runs the existing namespace lab inside a complete guest, using software emulation on the current host. ARM emulation and physical USB passthrough are separate future options.

You can test most of the Linux networking on an ordinary x86 PC first using QEMU, de-risking the software before hardware arrives.

```
Physical PC
   |
   +-- VM
        +-- NIC 1 = simulated Ethernet/LAN
        +-- NIC 2 = second simulated network
        +-- USB passthrough = the radio
```

**OS choice:** Ubuntu Server ARM64 or Debian ARM64, not Raspberry Pi OS — the latter expects Pi-specific firmware and drivers a generic ARM VM does not provide. The features being tested (RNDIS host driver, bridging, `ip link`) are standard Linux.

**Choose the simplest useful VM.** On an x86 host, an x86 Linux VM with KVM and USB passthrough is sufficient for driver and bridge tests. ARM64 on x86 needs QEMU software emulation (TCG), not KVM. See [QEMU ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) and [USB passthrough](https://www.qemu.org/docs/master/system/devices/usb.html).

**The key trick is USB passthrough** — it answers "does Linux recognise this radio as a NIC" without a Pi. Note the guest takes ownership of the device; the host cannot use it simultaneously. A virtual NIC on QEMU user-mode NAT is not a transparent path to a physical LAN; use a host bridge/TAP or pass through a dedicated Ethernet adapter for full Layer-2 testing.

**Caveat:** a VM is not a Pi. A pass proves "Linux in general can do this", not that the Pi's specific USB and Ethernet silicon will behave identically.

## Open risks and unknowns

Ordered by how much damage each does if it goes the wrong way.

- **The advertised IP-over-USB interface remains untested on Linux.** The handheld sell sheet lists it on p. 2, but the cable, USB class, firmware mode and driver are unknown. Obtain the host-interface guide and capture actual enumeration before selecting the topology.
- **Usable throughput still needs measurement.** Jeremy reports 16 Mbps at WRAITH 10 MHz; application throughput, operating conditions and competing traffic determine how much video fits. Rates for WRAITH 20 MHz and TSM 40 MHz remain unspecified.
- **Additional rate adaptation may be needed.** First test camera bitrate controls and forwarding. Budget relay/transcoding work only if stream requirements exceed the measured link capacity.
- **SitaWare integration is a separate project.** Packets reaching the CP produce no map tracks. CoT emission, a position source and a video path all have to be built and tested.
- **The radio link probably does not carry Layer 2.** A MANET radio is a routing node by design, so the flat-LAN bridge likely stops at the radio.
- **AP client isolation.** Default-on in many APs, and it silently breaks camera-to-Pi traffic.
- **No IGMP querier on an isolated segment.** Multicast memberships expire, streams stall.
- **Multiple DHCP servers.** AP, radio, Pi and CP router are all candidates.
- **USB power budget.** The Pi 4 limits downstream USB to ~1.1 A aggregate ([datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.3 p. 11) and wants 5 V 3 A itself (§4.1 p. 8). An underfed bus shows up as resets, not an obvious power error.
- **SWaP on the dismounted end.** Cameras, AP, Pi, radio and power all on one person.
- **VM results do not fully transfer to the Pi.**
- **Two things could shrink this a lot.** If the radio's PLI already puts the operator on the map, and if SitaWare Edge is already licensed, the remaining problem is just "get camera video onto the link" — much closer to the original brief.

## Next steps checklist

Use the [build roadmap](BUILD-ROADMAP.md) for the implementation sequence and pass/fail gates.

**Two cheap tests first — they determine everything else**

- [ ] Plug the radio into a Pi and run `lsusb` / `ip link` / `dmesg`. Does a network interface appear, and which driver binds?
- [ ] Measure real throughput between two radios at operational range, with the net under normal load

**Then obtain documentation**

- [ ] AN/PRC-171 / RF-9820S **ICD or programming guide** via your L3Harris channel — the critical path
- [ ] SitaWare: version, licensed interfaces (CoT / RTSP / STANAG 4609), target addresses
- [ ] Check whether radio **PLI already puts the operator on the SitaWare map**
- [ ] Check whether **SitaWare Edge** is available for the dismounted end
- [ ] Camera manuals — can the bitrate be driven low enough?

**Then build**

- [ ] Join `usb0` and `eth0` — bridge if the radio allows it, route if not
- [ ] AP in bridge mode, client isolation off, one DHCP server or fully static
- [ ] Prove camera → Pi ingest with no RF link in the path
- [ ] Add the RF link and prove CP → camera reachability
- [ ] Select WRAITH 10/20 MHz or TSM 40 MHz and record firmware/configuration
- [ ] Verify radio DHCP scope/pool and disable competing servers on that LAN
- [ ] Size camera bitrates to measured throughput; add rate adaptation only if needed
- [ ] Emit CoT and confirm the track appears on the SitaWare map
- [ ] One video stream into SitaWare, then add more only if measurements allow

**Then decide**

- [ ] Weigh and power-budget the full field kit
- [ ] Agree acceptance criteria — latency, loss, reconnect time — before calling it done

## Device facts to collect

A bench worksheet, not confirmed specifications.

| Item | Record or verify |
| --- | --- |
| Radio identity | Confirmed L3Harris RF-9820S (AN/PRC-171). Firmware, waveform loadout |
| Radio host interface | IP over USB advertised on p. 2 of the handheld sheet; confirm actual connector, cable, mode, USB protocol and Linux operation |
| Driver | Does Linux bind `rndis_host`, `cdc_ether`, or nothing? VID:PID, `dmesg` output |
| Link mode | Layer-2 bridge or Layer-3 routed |
| Radio addressing | Built-in DHCP server confirmed by Jeremy; collect enabled state, pool, scope, reservations, own IP and gateway behaviour |
| Waveform / capacity | WRAITH 10/20 MHz and/or TSM 40 MHz; 16 Mbps reported at WRAITH 10 MHz; measure each intended configuration |
| Route injection | Can the camera subnet be advertised into the MANET, or is NAT required? |
| Radio throughput | Measured at operational range under normal net load |
| MTU | Configured and effective path MTU |
| Multicast | Forwarded or suppressed; IGMP behaviour |
| Link loss behaviour | Reacquire time; does the host interface drop carrier with the RF link? |
| AP | Model, bridge mode, **client isolation**, multicast handling, DHCP |
| Cameras | Model, stream protocol, codec, **minimum achievable bitrate**, client limit |
| Discovery | Manual IP, broadcast, multicast, or vendor-specific |
| SitaWare | HQ version; CoT/RTSP/STANAG 4609 enabled; target addresses; PLI already on map? |
| Pi | Model, OS, kernel, NetworkManager version, power source |

## Reference library and PDF resources

Sources collected **23 September 2026**, with PDF text/page review **24 September 2026**. They establish general platform behaviour and product positioning — **not** that the RF-9820S presents a Linux-compatible USB network interface, which remains unverified.

### Web references

| Resource | What to pull from it |
| --- | --- |
| [Microsoft: Introduction to RNDIS](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2) | Protocol purpose and host/device concepts |
| [Linux: rndis_host.c](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c) | Driver matching, quirks; compare with the installed kernel |
| [Linux: Ethernet bridging](https://docs.kernel.org/networking/bridge.html) | Forwarding, STP, multicast snooping |
| [NetworkManager: nmcli examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html) | Bridge/port profiles |
| [NetworkManager: connection properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html) | IP methods, controller/port settings |
| [Raspberry Pi: configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) | OS networking and NetworkManager setup |
| [QEMU: ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) | Machine selection, acceleration constraints |
| [QEMU: USB passthrough](https://www.qemu.org/docs/master/system/devices/usb.html) | Passing a real USB device to a guest |
| [L3Harris: AN/PRC-171](https://www.l3harris.com/all-capabilities/an-prc-171-compact-team-radio) | Radio role, waveforms, battery life |
| [Systematic: SitaWare open architecture](https://systematic.com/int/industries/defence/products/sitaware-suite/sitaware-edge/open-architecture/) | **Most useful integration page found** — names CoT, RTSP, RTMP, STANAG 4609, NMEA 0183, GPSD, APIs/SDK |
| [Systematic: SitaWare Headquarters](https://systematic.com/int/industries/defence/products/sitaware-suite/sitaware-headquarters/) | HQ capabilities, FMV, map overlays |

### Local PDFs

Downloaded **23 September 2026** into [`references/pdf/`](references/pdf/), each verified as a real PDF and checksummed in [`MANIFEST.md`](references/pdf/MANIFEST.md) with publisher, revision, source URL and SHA-256.

| PDF | Local copy | Status and limitation |
| --- | --- | --- |
| [Pi 4 Model B datasheet](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf) | `raspberry-pi-4-datasheet.pdf` | 13 pp, Release 1.1 (12 Mar 2024). **Text extractable** — cited at section/page level. The board reference to use |
| [Pi 4 product brief](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS/raspberry-pi-4-product-brief) | `raspberry-pi-4-product-brief.pdf` | 7 pp, April 2026. Marketing summary; prefer the datasheet |
| [Pi 5 product brief](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf) | `raspberry-pi-5-product-brief.pdf` | 6 pp, April 2026. No Pi 5 datasheet equivalent held |
| [Bullseye → Bookworm](https://pip-assets.raspberrypi.com/categories/1261-transitioning/documents/RP-006519-WP-1-Transitioning%20from%20Bullseye%20to%20Bookworm.pdf) | `transitioning-bullseye-to-bookworm.pdf` | 19 pp, 15 Aug 2024. **The URL previously cited here 404s**; this is the working one |
| [MS-RNDIS specification](https://download.microsoft.com/download/5/0/1/501ED102-E53F-4CE0-AA6B-B0F93629DDC6/Windows/%5BMS-RNDIS%5D.pdf) | `MS-RNDIS.pdf` | 46 pp. **Text extractable** — cited at section/page level. Release stamp 1 May 2014, revision summary to rev 5.0 (15 May 2014). Not verified as newest |
| [USB-IF CDC-ECM subclass](https://www.usb.org/sites/default/files/CDC1.2_WMC1.1_012011.zip) | `usb-cdc-ecm-120.pdf` | 23 pp, from the CDC 1.2 package (Jan 2011). Relevant if the radio presents ECM. Extracted from an archive carrying an adopters agreement — check terms before redistributing |
| [L3Harris AN/PRC-171 sell sheet](https://www.l3harris.com/all-capabilities/an-prc-171-compact-team-radio) | `l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf` | 2 pp. Text extracted; p. 2 lists IP over USB/Ethernet, a bandwidth range and a marketing data-rate maximum. Linux compatibility remains untested |
| [L3Harris RF-9820S sell sheet](https://www.l3harris.com/resources/rf-9820s-compact-team-radio-sell-sheet) | `l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf` | 2 pp. Same radio, commercial designation |
| [L3Harris RF-9820S-ER sell sheet](https://www.l3harris.com/sites/default/files/2025-04/l3harris-rf-9820s-er-sell-sheet-cs-tcom.pdf) | `l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf` | 2 pp. **Different product** — do not transfer its figures to the handheld |
| [SitaWare HQ flyer](https://systematic.com/int/industries/defence/news-knowledge/downloads/flyers/sitaware-headquarters-flyer/) | `sitaware-headquarters-sales-flyer.pdf` | 2 pp. Marketing, not an interface spec |
| [SitaWare Edge flyer](https://systematic.com/int/industries/defence/news-knowledge/downloads/flyers/sitaware-edge-flyer/) | `sitaware-edge-sales-flyer.pdf` | 2 pp. Relevant to whether Edge removes work from the Pi |

**On the vendor documents:** these are public marketing material. The handheld sheets list interface types and headline rates, but do not provide a host-interface procedure or measured throughput for this build. The SitaWare flyers are not integration specifications. See the [page-level review and reading guide](docs/reference-notes.md).

To re-fetch and verify:

```bash
mkdir -p references/pdf
curl --fail --location --output references/pdf/raspberry-pi-4-datasheet.pdf \
  'https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf'
file references/pdf/raspberry-pi-4-datasheet.pdf
sha256sum references/pdf/raspberry-pi-4-datasheet.pdf
```

Confirm a download is a PDF before relying on it — a moved document may return an HTML error page from a `.pdf` URL. Raspberry Pi documents are CC BY-ND: keep originals unmodified.

### Documents still needed

- **AN/PRC-171 / RF-9820S ICD, operator manual and programming guide.** **The critical path.** Advertised IP-over-USB setup and protocol, L2 vs L3, addressing and route injection, MTU, multicast, throughput, PLI behaviour. Via your programme's L3Harris channel.
- **SitaWare integration documentation:** version, licensed interfaces, CoT configuration, RTSP/FMV handling, API/SDK terms. Via your SitaWare administrator or Systematic.
- **AP manual:** bridge mode, client isolation, multicast settings.
- **Camera manuals:** stream protocols, codecs, minimum bitrate.

L3Harris tactical radio documentation is frequently export-controlled or distribution-restricted. Obtain it through the proper channel, and **do not commit restricted documents into this repository** — the sell sheets held here are public marketing material.

## Test record template

```text
Date / operator:
Pi model / OS / kernel / NetworkManager version:
Radio model / waveform / firmware (AN/PRC-171 / RF-9820S):
Channel bandwidth (WRAITH 10/20 MHz or TSM 40 MHz):
Reported rate / measured usable IP throughput / test conditions:
Radio host interface: exists? / USB VID:PID / driver bound / interface name:
Radio link mode (bridged L2 or routed L3):
Measured RF throughput / range / net load at time of test:
AP model / firmware / mode / client isolation state:
Camera models / stream protocol / codec / bitrate:
Rate adaptation method / target bitrate:
Address plan / DHCP owner / radio DHCP pool and scope:
Bridge or routing configuration:
SitaWare version / interfaces used / track visible? / video visible?:
Tests performed / duration:
Observed throughput / loss / stalls / recovery time:
Logs or capture filenames:
Source documents / revision / relevant pages (see references/pdf/MANIFEST.md):
Result / remaining issue / next action:
```
