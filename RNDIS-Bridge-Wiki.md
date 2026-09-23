# RNDIS Bridge on Raspberry Pi

_Last updated: Sep 23, 2026_


> This wiki also exists as a folder of linked pages under [`wiki/`](wiki/README.md). Both carry the same content; update them together or pick one as canonical.

## Contents

- [Overview](#overview)
- [What RNDIS actually is](#what-rndis-actually-is)
- [Full architecture](#full-architecture)
- [Transport link: Harris radio data link](#transport-link-harris-radio-data-link)
- [Bridge vs. route](#bridge-vs-route)
- [SitaWare HQ integration](#sitaware-hq-integration)
- [Switch and router selection](#switch-and-router-selection)
- [Hardware test plan](#hardware-test-plan)
- [DHCP: pick exactly one server](#dhcp-pick-exactly-one-server)
- [Testing without a Pi: an ARM64 VM](#testing-without-a-pi-an-arm64-vm)
- [Open risks and unknowns](#open-risks-and-unknowns)
- [Next steps checklist](#next-steps-checklist)
- [Device facts to collect](#device-facts-to-collect-before-configuration)
- [Bench preparation](#bench-preparation-and-evidence-collection)
- [Persistent NetworkManager bridge](#persistent-networkmanager-bridge)
- [Packet tracing and troubleshooting](#packet-tracing-and-troubleshooting)
- [Routing fallback design](#routing-fallback-design)
- [Throughput and acceptance tests](#throughput-and-acceptance-tests)
- [Reference library and PDF resources](#reference-library-and-pdf-resources)
- [Test record template](#test-record-template)

## Overview

> ## ⚠ The "9820" has been identified — and it changes the architecture
>
> The device this wiki called "the 9820" is the **L3Harris RF-9820S Compact Team Radio, designated AN/PRC-171**. It is the same box as the data link. There is no separate mystery video device and separate radio: **they are one radio.**
>
> Earlier drafts of this wiki treated the 9820 as an unidentified video receiver, and a topology diagram guessed it was a Garmin chartplotter. Both readings were wrong. Every statement below has been re-read against the correct identification, but treat anything that still sounds like "the radio receives video" as a leftover to delete rather than a requirement to design for.
>
> The practical consequence: the Pi is not bridging a camera LAN *to a video device*. It is putting a camera LAN *onto a tactical MANET radio*. See [Transport link](#transport-link-harris-radio-data-link).

The goal is to get camera traffic from a dismounted operator onto an L3Harris AN/PRC-171 (RF-9820S) tactical radio, across the MANET RF link, and into a **SitaWare Headquarters** instance at the command post, so the operator and their video appear on the SitaWare map for server-side and user-side clients. A Raspberry Pi does the join: it takes the camera LAN on `eth0` and connects it to the network interface the radio presents over USB.

> **Connectivity is not integration.** Bridging or routing packets gets bytes to the command post. It does **not** make anything appear on a SitaWare map. Something must emit position reports and video in formats SitaWare ingests — see [SitaWare HQ integration](#sitaware-hq-integration). This is additional work on the Pi, not a side effect of the bridge.

The working assumption — **still unconfirmed** — is that the RF-9820S exposes a network connection to a host over **USB, using RNDIS or CDC-ECM**. The public L3Harris material does not state the host data interface at all (see [Reference library](#reference-library-and-pdf-resources)), so this is the first thing to verify, and the whole design rests on it.

Target data path:

```
  Field / dismounted                                    Command post
  ───────────────────────────────────────────           ──────────────────────────

  Camera 1 ─┐
  Camera 2 ─┼─► switch ─► [eth0  Raspberry Pi  usb0] ──USB──► [ AN/PRC-171 ]
  Camera N ─┘                  │                                     ┊
                               │ also emits:                  MANET RF link
                               │  • CoT position reports             ┊
                               │  • RTSP / STANAG 4609 video  [ AN/PRC-171 ]
                               │                                     │
                               └────────────────────────────►  switch/router
                                                                     │
                                                              SitaWare HQ server
                                                                     │
                                                          SitaWare clients (map)
```

The Pi does no video processing — it is purely a network bridge/router joining two interfaces (`usb0` to the radio, `eth0` to the camera switch).

**Verdict: the Linux side is feasible; the radio interface is unproven, and the RF link is now the dominant constraint.** Linux has a mature host-side RNDIS driver, and joining two interfaces is a well-worn technique — the Pi is a reasonable box for it. Three things must be confirmed before this design is real:

1. **Does the RF-9820S present a USB network interface to a host at all**, and if so is it RNDIS, CDC-ECM, or something proprietary requiring L3Harris software? Public material does not say.
2. **Does it bridge Layer 2, or route Layer 3?** A MANET radio is a routing node by design, so expect routed. That likely makes [routing](#option-2-layer-3-routing), not bridging, the correct architecture — inverting this wiki's original recommendation.
3. **How much usable throughput does the MANET link give at operational range?** Tactical wideband MANET is typically low single-digit Mbit/s *shared across the net*. The 32 Mbit/s video example in this wiki is a Wi-Fi-era figure and is almost certainly unachievable.

Start with the [transport link section](#transport-link-harris-radio-data-link): the radio decides more about the final architecture than anything on the Pi does.

## What RNDIS actually is

**RNDIS (Remote NDIS)** is a Microsoft-originated protocol that lets a USB connection carry Ethernet frames. Instead of the radio presenting itself as USB storage or a serial device, it presents itself as a **network adapter over USB**.

The protocol itself is documented in the local copy of the Microsoft specification, [`references/pdf/MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf). Useful orientation from it:

- The bus transport is split into a **control channel** (control messages) and a **data channel** (network packet data) — glossary, §1.1, p. 6.
- The host opens with `REMOTE_NDIS_INITIALIZE_MSG` (§2.2.2, p. 12), which carries a `MaxTransferSize`, and the device answers with `REMOTE_NDIS_INITIALIZE_CMPLT` (§2.2.9, p. 18). A device that fails this handshake never becomes a usable NIC.
- Ethernet frames ride inside `REMOTE_NDIS_PACKET_MSG` (§2.2.14, p. 22).
- Link state is reported by the device through `REMOTE_NDIS_INDICATE_STATUS_MSG` (§2.2.7, p. 16), using `RNDIS_STATUS_MEDIA_CONNECT` (`0x4001000B`) and `RNDIS_STATUS_MEDIA_DISCONNECT` (`0x4001000C`) from the common status values table (§2.2.1.2, p. 12). This is the mechanism behind the "link flaps / carrier never comes up" class of problem below.

Linux provides the host-side `rndis_host` driver, with USB networking helpers including `usbnet` and `cdc_ether`. Availability depends on the installed kernel configuration and device matching. A supported device can appear as `usb0` or `enx001122334455`; record the actual name rather than assuming it. See the [upstream driver source](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c).

RNDIS is not the only way a device does Ethernet-over-USB. If the descriptors show a CDC-ECM interface instead, `cdc_ether` handles it and the governing document is the USB-IF subclass specification saved at [`references/pdf/usb-cdc-ecm-120.pdf`](references/pdf/usb-cdc-ecm-120.pdf) — keep both to hand until the radio's descriptors have actually been read.

Once that interface exists, it behaves like any other Linux network interface (`eth0`, `wlan0`, etc.) for the purposes of bridging, routing, `iptables`, DHCP, and so on. That's what makes the whole idea work: nothing about the rest of the setup needs to know or care that the radio's "cable" is actually USB underneath.

**Caveat:** "should" is doing some work in that sentence. RNDIS is a spec, but implementations vary, and some devices have quirks (odd MTU behaviour, flaky link-state reporting, etc.). The specification's own revision summary ([`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf), pp. 3–4) runs through several "significantly changed the technical content" revisions, which is a fair hint that implementations built against different revisions differ in practice. This is the first thing to verify on real hardware — see [Hardware test plan](#hardware-test-plan).

## Full architecture

Cameras sit with the dismounted operator; the command post is at the far end of the RF link.

```
  FIELD (dismounted operator)                          COMMAND POST
  ════════════════════════════════════════             ══════════════════════════════

  Camera 1 ──┐
             │
  Camera 2 ──┼──► ┌──────────────┐
             │    │ small rugged │
  Camera N ──┘    │    switch    │
                  └──────┬───────┘
                         │ Ethernet
                       eth0
                  ┌──────┴───────┐
                  │ Raspberry Pi │
                  │   (Linux)    │
                  │ eth0 ↔ usb0  │
                  └──────┬───────┘
                       usb0
                         │ USB  ← interface type UNCONFIRMED
                  ┌──────┴───────┐                      ┌──────────────┐
                  │  AN/PRC-171  │┄┄┄┄ MANET RF ┄┄┄┄┄┄┄►│  AN/PRC-171  │
                  │  (RF-9820S)  │                      │  (RF-9820S)  │
                  └──────────────┘                      └──────┬───────┘
                                                               │ Ethernet
                                                        ┌──────┴───────┐
                                                        │   switch /   │
                                                        │    router    │
                                                        └──────┬───────┘
                                                               │
                                                            viewers
```

The Pi has exactly two jobs:

1. **See the radio as a network interface** (`usb0`) — via `rndis_host`, `cdc_ether`, or whatever the RF-9820S actually presents.
2. **Join `usb0` and `eth0`** so camera traffic reaches the radio, either as one flat Layer-2 network (bridge) or as two routed subnets (router). See [Bridge vs. route](#bridge-vs-route) below. **Expect routing to be required** — see the transport link section.

The Pi forwards network traffic without decoding video. Whether the video actually gets through depends far more on the MANET link than on the Pi.

### The devices that are not the Pi

| Device | Role | Where covered |
| --- | --- | --- |
| AN/PRC-171 (RF-9820S) ×2 | The radio the Pi plugs into, **and** the transport. One in the field, one at the CP | [Transport link](#transport-link-harris-radio-data-link) |
| Field switch | Aggregates the cameras into the Pi. Must be small, DC-powered, rugged | [Switch and router selection](#switch-and-router-selection) |
| CP switch/router | Distributes to viewers at the command post. Benign environment, conventional hardware | [Switch and router selection](#switch-and-router-selection) |

Of these, the radio decides the architecture.

### SWaP note for the field end

The field end rides on a person. Every watt and every gram is a real cost, and the Pi plus a switch plus their power is a meaningful addition to a dismounted load. Before committing:

- If there are only one or two cameras, consider whether a switch is needed at all — a second USB-Ethernet adapter on the Pi, or a direct camera-to-Pi connection, may remove a box.
- Confirm the power source for the Pi and switch. The radio has its own battery; the Pi does not get to share it without a deliberate, documented arrangement.
- PoE cameras on a battery-powered field switch will dominate the power budget. Check this early.

## Transport link: Harris radio data link

The wireless leg is an **L3Harris AN/PRC-171 (RF-9820S) Compact Team Radio** at each end — a single-channel, low-SWaP handheld from the Falcon IV family, running wideband MANET plus narrowband voice and PLI. It is also the device this wiki previously called "the radio".

### What the public material does and does not say

Downloaded to [`references/pdf/`](references/pdf/) and catalogued in [`MANIFEST.md`](references/pdf/MANIFEST.md):

| Document | Local copy |
| --- | --- |
| AN/PRC-171 Compact Team Radio sell sheet | `l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf` |
| RF-9820S Compact Team Radio sell sheet | `l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf` |
| RF-9820S-ER Embeddable Modular Radio sell sheet | `l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf` |

These are two-page marketing sell sheets. **Their text is not machine-extractable**, so nothing here is cited to a page or section — read them directly. From L3Harris's public product pages, the radio is described as single-channel and low-SWaP, supporting wideband MANET and narrowband voice/PLI, with in-field waveform upgrades (including the Wraith resilient wideband waveform) and over 20 hours of operation on a battery. The separate **RF-9820S-ER** embeddable variant is described with 225 MHz–2.6 GHz hardware coverage and AES-256 — do not assume those figures transfer to the handheld you are holding.

**What the public material does not state, and what this design depends on:**

- The **host data interface**. Nothing public says the radio presents USB Ethernet to a connected computer, let alone that it is RNDIS. This entire wiki assumes it does.
- **Data rates.** No throughput figure appears on the public pages.
- Whether the host interface **bridges Layer 2 or routes Layer 3**.
- MTU, multicast handling, and DHCP behaviour on the host interface.

All of that lives in the radio's Interface Control Document, operator manual or programming guide — documents obtained through your programme's L3Harris channel, not the public web. **Getting that documentation is now the critical path for this project.** Until it exists, the design below is a plan, not a specification.

### Why this changes the design

A Wi-Fi access point in bridge mode is a transparent Layer-2 device on a fast link. A tactical MANET radio is neither. Three properties decide the whole architecture.

**1. Does the link bridge Layer 2, or route Layer 3?**

This is the first question to answer, because the default recommendation below — bridge first — depends on it.

| If the radio link… | Then… |
| --- | --- |
| Presents a **transparent Layer-2 Ethernet bridge** (typical of broadband line-of-sight Ethernet radios) | The flat-LAN bridge design still works end to end. Broadcast and multicast discovery have a chance of crossing |
| Presents a **routed Layer-3 IP interface** (typical of MANET and tactical waveforms generally) | The Layer-2 bridge **stops at the radio**. Broadcast discovery does not cross it. [Routing (Option 2)](#option-2-layer-3-routing) becomes the primary design, not the fallback, and every discovery protocol needs individual treatment |

**A MANET radio is a routing node by design** — that is what the "ad hoc network" part means. Each radio maintains routes to other radios in the net. So the second row is the expected case here, and the Pi should be planned as a **router** with the radio's USB interface as one side, not as a transparent bridge spanning the RF link.

Two consequences worth stating plainly:

- The radio will likely expect the attached host to sit on a small subnet with the radio as its gateway, not to present a bridge full of foreign MAC addresses. Bridging `eth0` into `usb0` may simply not work.
- Camera discovery protocols that rely on broadcast or multicast will not cross the RF link without explicit configuration, and may not be supportable at all. Plan on **static, unicast, manually-configured** camera addressing and stream URLs.

Confirm against the ICD before building either design.

**2. What is the usable throughput, at range, under contention?**

**This is the question most likely to kill the concept as currently scoped.** L3Harris publishes no throughput figure for this radio publicly. Tactical wideband MANET waveforms generally deliver low single-digit Mbit/s *shared across every radio in the net*, degrading with range, terrain, hop count and the number of participants — and the net is also carrying voice and PLI, which will be prioritised over your video.

The Ethernet segments either side are effectively free by comparison. **The RF link is the bottleneck and nothing else on this path is close.**

The video budget in [Throughput and acceptance tests](#throughput-and-acceptance-tests) uses a 32 Mbit/s example inherited from a Wi-Fi-era version of this design. Treat it as void. Re-derive from a *measured* figure over the actual radios at operational range — not a datasheet maximum, and not a bench test with the two radios on a desk a metre apart.

If the measured link is, say, 1–2 Mbit/s usable, then multiple simultaneous camera streams is not a tuning problem, it is a different system. Realistic options at that point:

- One stream at a time, operator-selected, rather than all cameras continuously.
- Heavily compressed low-resolution video (H.265, low frame rate, small GOP) sized to the measured link.
- Still images on demand instead of continuous video.
- Store locally on the Pi at full quality, transmit selectively — the Pi is well suited to this, and it decouples capture quality from link capacity.

Decide this from measurements before buying cameras or committing to a streaming protocol.

**3. What does it do to MTU, multicast and DHCP?**

- **MTU.** Tactical links commonly run a reduced MTU. A path MTU smaller than the LAN's causes fragmentation or silent drops of full-size frames, which typically shows up as "small packets work, video does not." Record the radio's MTU and set interfaces consistently. This interacts with the RNDIS `MaxTransferSize` negotiated at the USB end ([`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12).
- **Multicast.** Confirm explicitly whether the radio forwards multicast, and on what groups. Many tactical links restrict or suppress it by default because it is expensive on a shared channel.
- **DHCP.** A routed radio link will not relay DHCP between ends without explicit configuration. This strengthens the case for the all-static address plan below.

### Facts to record about the radio

| Item | Record or verify |
| --- | --- |
| Identity | Confirmed model (AN/PRC-171 / RF-9820S), waveform(s) in use, firmware/software version |
| Host interface | Does a host USB network interface exist? Connector, USB mode, whether a cable/adapter is required |
| Driver | Does Linux bind `rndis_host`, `cdc_ether`, or nothing? Record VID:PID and `dmesg` output |
| Link mode | Transparent Layer-2 bridge, or routed Layer-3 interface |
| Addressing | Radio's own IP, whether it acts as gateway, whether it serves DHCP to the host |
| Route injection | Can the camera subnet be advertised into the MANET, or must the Pi NAT behind the radio's host address? |
| Throughput | Measured usable rate at operational range, with the net carrying its normal voice/PLI load |
| MTU | Configured and effective path MTU |
| Multicast | Forwarded or suppressed; any group restrictions; IGMP behaviour |
| Latency / jitter | Typical and worst case — matters for streaming, not just for ping |
| Behaviour on link loss | Reacquire time; whether the host interface drops carrier when the RF link drops |
| Concurrent use | Does attaching a data host affect voice/PLI service? Is there a priority or QoS control? |

Two rows deserve emphasis. **Route injection** decides whether the CP can reach cameras by their own addresses or whether everything has to be NATed behind the Pi. **Behaviour on link loss** decides whether the Pi's interface flaps every time the RF link drops, and whether the network recovers cleanly when it does.

### Documentation note

L3Harris tactical radio documentation beyond the public sell sheets is frequently export-controlled or distribution-restricted. Obtain the ICD, operator manual and programming guide through the proper channel for your programme rather than a general web search, and **do not commit restricted documents into this repository** — the three sell sheets held locally are public marketing material and were downloaded from l3harris.com.

## Bridge vs. route

There are two ways to join `usb0` and `eth0`.

> **Expect Option 2.** The AN/PRC-171 is a MANET radio, and MANET radios route. A Layer-2 bridge spanning the RF link is very unlikely to work, and bridging `eth0` into the radio's host interface may not work either. Option 1 is retained below because it is still the right answer *if* the radio turns out to present a transparent Layer-2 host interface — but plan for Option 2 and be pleasantly surprised. Confirm against the radio's ICD before building either.

### Option 1: Layer-2 bridge (try this first)

```
         br0
      /       \
   usb0       eth0
    |           |
  radio      switch → radio link
```

Linux joins the two interfaces into `br0`, acting like a simple two-port Ethernet switch. The radio's host interface and every client on the camera segment end up on the **same LAN/subnet** — e.g. everything on `192.168.1.0/24` — provided the radio link carries Layer 2.

Raspberry Pi OS supports this through NetworkManager, and it's the officially documented way to join interfaces into one Layer-2 network.

**Why it's the better first attempt for video systems:** things like broadcast discovery, multicast, UDP streaming, and "auto-discover devices on my subnet" all assume everyone is on the same LAN segment. A bridge preserves the shared LAN, but multicast filtering on the switch, IGMP querier presence, and the radio link's own Layer-2 behaviour all still need testing.

### Option 2: Layer-3 routing

```
radio                       switch / radio link
192.168.10.x                  192.168.20.x
     |                             |
    usb0    Raspberry Pi    eth0
     \____ (IP forwarding) ______/
```

The radio's host interface and the camera-side clients sit on **two separate subnets**, and the Pi forwards packets between them (`net.ipv4.ip_forward=1`, plus `iptables`/`nftables` rules as needed).

This is often easier to reason about and troubleshoot — you can firewall between the two sides, see traffic clearly per-interface, etc. — but if the video system leans on multicast or broadcast discovery, that traffic doesn't cross a router boundary by default, and you'd need protocol-specific configuration (multicast routing for multicast streams, and suitable discovery relays where available) to make it work.

### Recommendation

**If the radio link bridges Layer 2:** start with the bridge. It's the simplest way to make the radio and the camera-side clients "just see each other," which is almost certainly what a video/discovery system expects.

**If the radio link routes Layer 3:** build the bridge on the Pi anyway — it is still the right way to join `usb0` and `eth0` locally, and it keeps the radio on the local segment — but plan for routing across the radio, and treat every discovery protocol as something that needs explicit configuration rather than something that will just work.

Either way, do not discover which case you are in by debugging a failed video test. Establish it from the radio's documentation first.

## SitaWare HQ integration

The command post runs **SitaWare Headquarters** (Systematic). The requirement is that the operator and their cameras are visible on the SitaWare map, server-side and on user clients.

> **The single most important point in this wiki:** a network bridge moves packets; it does not create tracks or video feeds in a C4ISR system. Getting IP connectivity to the CP is necessary and nowhere near sufficient. Something has to *speak SitaWare's languages*. On this architecture, that something is the Raspberry Pi, and it is a materially larger piece of work than the bridge.

### What SitaWare accepts

From Systematic's public open-architecture material (see [Reference library](#reference-library-and-pdf-resources)), the SitaWare suite is documented as supporting:

| Purpose | Mechanism |
| --- | --- |
| Position / tracks on the map | **Cursor-on-Target (CoT)** metadata messaging |
| Location input from a device | **NMEA 0183**, **ICD-GPS-153**, **GPSD** |
| Video streaming | **RTSP**, **RTMP**, DirectShow |
| Geo-referenced motion imagery with metadata | **NATO STANAG 4609** (with MISB KLV metadata) |
| Anything else | Published **APIs** and an **SDK** for third-party integration |

Systematic also states that STANAG 4609-compliant live video feeds play in SitaWare Frontline and Edge, carrying viewshed and platform position into the app, and that SitaWare Headquarters ingests intelligence streams including full-motion video.

**Verify all of this against your own SitaWare version, licence and deployment.** The list above comes from public marketing pages, not from an interface specification. Which mechanisms are enabled in your instance is a question for your SitaWare administrator and for Systematic — not something to infer from a product page.

### Two things must be produced, and they are separate problems

**1. Getting the operator onto the map — the easy part.**

CoT messages are tiny (a fraction of a kbit/s), survive a constrained tactical link comfortably, and are the natural way to place a track. The Pi needs a position source:

- If the AN/PRC-171 already reports **PLI** into the network, the operator may *already* appear on the map through the radio's own reporting. **Check this before building anything** — the requirement may be half-solved already.
- Otherwise, give the Pi a GPS receiver and read it via `gpsd`, then emit CoT.

**2. Getting video into SitaWare — the hard part.**

Ordered from least to most work:

| Approach | What it gives | Cost |
| --- | --- | --- |
| **Pass the camera's RTSP stream through** | A video feed SitaWare can open, if RTSP is enabled in your instance | Lowest. May need the Pi to re-serve or proxy the stream so the CP sees one stable address |
| **Transcode on the Pi, then serve RTSP** | A stream sized to the RF link rather than to the camera's defaults | Moderate. Encoding on a Pi is possible but watch CPU, heat and power |
| **Produce STANAG 4609 with KLV metadata** | Properly geo-referenced FMV — video tied to a position and viewshed on the map | Highest. Requires correct MISB KLV construction and a geo-referenced, ideally pointing-aware camera |

**Choose based on what you actually need on the map.** If the requirement is "see the operator's position and be able to open their camera", RTSP plus CoT is far cheaper than full STANAG 4609 and is probably the right answer. If the requirement is "video footprint drawn on the map with viewshed", that is STANAG 4609 and a significantly bigger project.

### Consider whether SitaWare Edge removes most of this

Systematic's dismounted product is **SitaWare Edge**. If the operator carries an end-user device running Edge:

- Position reporting and map presence are solved by Edge, not by your Pi.
- Edge is documented as playing STANAG 4609 feeds.
- The Pi's job shrinks back to what it is good at: getting camera video onto the network.

This is worth pricing against the integration work above **before** committing to building a CoT/FMV pipeline on a Raspberry Pi. Ask whether Edge is already licensed in your programme.

### Bandwidth reality check

| Traffic | Approximate load |
| --- | --- |
| CoT position reports | Negligible — well under 1 kbit/s |
| One heavily compressed low-rate video stream | Hundreds of kbit/s to ~1 Mbit/s |
| Multiple full-rate camera streams | Tens of Mbit/s — **not viable on this link** |

Position on the map is essentially free. Video is the entire problem, and it collides directly with the [MANET throughput constraint](#transport-link-harris-radio-data-link). Size the video to the measured link, not the other way round.

### Open questions for the SitaWare side

- Which SitaWare Headquarters version, and which integration mechanisms are licensed and enabled?
- Does the CP already receive PLI from the AN/PRC-171 net? If so, is the operator already on the map?
- Is CoT ingestion enabled, and what address/port should the Pi send to?
- For video: is RTSP sufficient, or is STANAG 4609 geo-referenced FMV actually required?
- Is SitaWare Edge available for the dismounted end?
- Who owns the SitaWare integration — your team, Systematic, or a systems integrator? API/SDK access usually requires a commercial arrangement.

## Switch and router selection

The requirement is a device to act as the switch and router into the Pi.

### First: do you need the router at all?

Probably not in-path. Check this before choosing hardware.

The whole point of the Layer-2 bridge design is that the radio and the camera-side clients sit on one flat subnet. **A router placed in-path between the switch and the Pi defeats that** — it makes a routed hop in the middle of what was supposed to be a single broadcast domain, and broadcast discovery dies at it.

Three valid arrangements:

| Arrangement | When it applies |
| --- | --- |
| **Switch only, in-path; no router** | The radio link bridges Layer 2, or the radio does the routing itself. Simplest, and the best match for the bridge design |
| **Switch in-path; router hanging off it, upstream-only** | You need upstream/Internet access or services (NTP, management) but the camera↔radio path stays flat. This is what a topology diagram's "optional — for upstream network" note describes |
| **Router in-path, doing Layer 3** | The radio presents a routed interface and you need policy, firewalling or address separation. This is the [routing fallback design](#routing-fallback-design), not the bridge design |

Which one you are in is decided by the radio, not by the switch.

### What the device actually has to do

Ranked by how much it matters here, not by marketing prominence:

1. **IGMP snooping with a configurable querier.** The most important feature on the list. Camera discovery and streaming are typically multicast. On an isolated segment there is no router to send IGMP queries, so group memberships expire and streams stop after a minute or two — the classic "stream starts then stalls" symptom below. The switch must be able to act as querier.
2. **VLAN support**, to separate the camera segment from management traffic.
3. **No forced client/port isolation**, so the Pi's bridge can see the camera MACs.
4. **Port count and PoE budget.** If the cameras are PoE, size the budget properly — PoE+ at 30 W per port adds up fast, and this is the most common reason a switch choice has to be redone.
5. **Power input.** Field and vehicle installations usually mean DC input (12/24 V), not mains.
6. **Environmental rating.** Fanless, temperature range, shock/vibration — relevant if this is deployed alongside tactical radios rather than sitting on a bench.

Raw switching throughput is not on this list. Every option below is orders of magnitude faster than the radio link.

### Two ends, two very different requirements

There is a device at each end, and they should not be the same product.

**Field end — with the cameras, on a person**

The binding constraints are weight, power and ruggedness, not features. Realistic options, cheapest first:

| Option | Notes |
| --- | --- |
| **No switch at all** | With one or two cameras, use the Pi's own Ethernet plus a USB-Ethernet adapter, or connect a single camera directly. Removes a box, its weight and its power draw. **Try this first** |
| **Small unmanaged DC switch** (5-port, 12 V, fanless) | Cheap, light, low power. Acceptable if you do not need VLANs or an IGMP querier — and with static unicast addressing across a routed radio link, you may not |
| **Cisco IE-1000 / IE-3200** industrial Ethernet | Managed, rugged, DIN-rail, DC input. Heavier and hungrier than a dismounted role usually justifies — appropriate if this ends up vehicle-mounted rather than carried |

Be honest about the dismounted load. A managed industrial switch on a person to serve two cameras is hard to defend; a 60 g unmanaged switch, or no switch, usually wins.

**Command post end — with the SitaWare server**

Mains power, rack or desk, benign environment. Conventional hardware is right:

| Option | Notes |
| --- | --- |
| **Cisco Catalyst 9200 / 9200CX** | Managed switch with IGMP snooping and querier, VLANs. The straightforward choice if the CP already routes |
| **Cisco ISR 1100 series** (e.g. ISR1111X-8P) | Router with integrated 8-port managed switch — one box doing both roles |
| **Cisco IR1101 / ESR-6300** | Rugged, DC-powered. Appropriate only if the "CP" is a vehicle or deployable shelter rather than a building |
| **MikroTik RB5009, Ubiquiti EdgeRouter** | Low-cost, entirely adequate for proving the design before committing |

The CP switch has to reach the SitaWare HQ server, so its configuration is likely constrained by an existing CP network you do not control. Check what is already there before buying anything.

**Cheapest path to a working answer:** prove the design on bench hardware you already own, confirm which of the three arrangements above you are actually in, then buy once. The radio's Layer-2-versus-Layer-3 behaviour and the SitaWare integration will each decide more about the final design than the switch model does.

### Configuration checklist

Whatever device is chosen:

- [ ] Put the camera segment on its own VLAN; keep switch management off it or on a separate tagged VLAN
- [ ] Enable IGMP snooping on that VLAN
- [ ] Configure the switch as **IGMP querier** on that VLAN (there is no router on an isolated segment to do it)
- [ ] Confirm no port isolation / protected-port setting is enabled on the Pi's port or the camera ports
- [ ] Record port assignments and MAC addresses for the test record
- [ ] Set exactly one DHCP server, or go fully static
- [ ] If PoE: confirm total draw against the switch's PoE budget, not just per-port capability
- [ ] Verify the Pi's `eth0` link comes up at expected speed/duplex after the bridge is built

### Where the Pi sits

The Pi's `eth0` is an ordinary access port in the camera VLAN. The Pi bridges that to `usb0`. From the switch's point of view the Pi is a two-port device that will source frames with the radio's MAC — which is exactly why port security or MAC-limiting on that port will break it. Leave both off on the Pi's port.

## Hardware test plan

Use a Pi 4 or Pi 5 — board details in [`references/pdf/raspberry-pi-4-datasheet.pdf`](references/pdf/raspberry-pi-4-datasheet.pdf) and [`references/pdf/raspberry-pi-5-product-brief.pdf`](references/pdf/raspberry-pi-5-product-brief.pdf). Steps, in order:

**1. Confirm Linux sees the radio as a NIC**

Plug the radio into a Pi USB host port, then check:

```bash
lsusb
ip link
dmesg | tail -50
```

Look for a new interface — `usb0`, or a MAC-derived name like `enx001234567890` — alongside the usual `lo`, `eth0`, `wlan0`. If that interface shows up, the biggest unknown (does Linux treat the radio as a normal network adapter over USB) is answered.

**2. Bring up the bridge**

Use the persistent [NetworkManager bridge procedure](#persistent-networkmanager-bridge) below. Do not mix temporary `ip link` configuration with active NetworkManager profiles on the same interfaces.

**3. Connect the switch**

Wire the Pi's `eth0` to the switch. Keep the camera segment on one VLAN with IGMP snooping and a querier configured, and no port isolation on the Pi's port — see [Switch and router selection](#switch-and-router-selection). Do not put a router in-path between the switch and the Pi unless you have deliberately chosen the [routing design](#routing-fallback-design).

**4. Ping test, wired only**

Plug a laptop into the same VLAN on the switch and ping the radio (and vice versa). Keep the radio link out of the path for this step. If that works, the core mechanism — RNDIS NIC plus Layer-2 bridge — is proven.

**5. Add the radio link**

Only now bring the [Harris radio data link](#transport-link-harris-radio-data-link) into the path and repeat the ping test from the far end. If step 4 passed and step 5 fails, the radio is the problem, not the bridge — which is exactly why these are separate steps.

**6. Real traffic**

Only once step 5 works, try an actual video feed / whatever protocol the real system uses end-to-end. Measure the radio link's usable throughput before assuming the intended stream count fits.

## DHCP: pick exactly one server

On this isolated bridge, use one DHCP server, or none for an all-static test. Check whether the radio has an embedded DHCP server; its capability is unknown. The Pi only serves DHCP if configured to do so. The router and the Harris radio may each be capable of serving DHCP as well — check both. Multiple DHCP servers on the same broadcast domain cause random address conflicts and clients silently picking the wrong gateway/DNS.

**All-static is the stronger default here.** If the radio link routes rather than bridges, DHCP will not cross it without explicit relay configuration, so relying on a single server at one end stops working the moment the far end is involved. Static addressing sidesteps that entirely for a small, fixed device count.

A workable static plan for a small setup:

| Device | Address |
| --- | --- |
| Radio host interface | `192.168.1.10` |
| Pi (`br0`) | `192.168.1.20` |
| Camera 1 | `192.168.1.101` |
| Camera 2 | `192.168.1.102` |

Everything on one flat `/24`, one designated DHCP server (or all-static, as above, if the device count is small and fixed).

## Testing without a Pi: an ARM64 VM

You can test most of the Linux networking side on an ordinary x86/AMD64 PC first, using QEMU to emulate an ARM64 CPU. This is a good way to de-risk the software side before hardware is in hand.

```
Physical PC
   |
   +-- ARM64 VM (QEMU TCG on an x86 host)
        +-- NIC 1 = simulated Ethernet/LAN
        +-- NIC 2 = second simulated network
        +-- USB passthrough = radio RNDIS device
```

**OS choice:** use **Ubuntu Server ARM64** or **Debian ARM64**, not Raspberry Pi OS — Raspberry Pi OS expects Pi-specific hardware (firmware, bootloader, SoC drivers) that a generic ARM VM doesn't provide. The features being tested (RNDIS host driver, bridging, `usb0`/`eth0`, `ip link`) are all standard Linux, not Pi-specific, so a generic ARM64 distro is the right fit.

**The key trick is USB passthrough.** If the hypervisor can pass the real radio USB device into the VM, you can test whether ARM Linux recognizes it as an RNDIS network interface (`usb0` / `enx...`) before ever touching a Raspberry Pi. Inside the VM, the same commands apply: `lsusb`, `ip link`, `ip addr` — and the same bridge (`br0` joining `usb0` and `eth0`) can be built and tested exactly as it would be on the Pi.

**Choose the simplest useful VM:** on an x86 host, an x86 Linux VM with KVM and USB passthrough is sufficient for initial driver and bridge tests. ARM64 on x86 requires QEMU software emulation (TCG), not KVM acceleration. Use QEMU’s generic `virt` machine and a compatible ARM64 guest image if testing that architecture matters. An ARM host can use KVM for a compatible ARM guest. See [QEMU ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) and [USB passthrough](https://www.qemu.org/docs/master/system/devices/usb.html).

USB passthrough gives the guest ownership of the device: the host cannot simultaneously use its RNDIS interface. A virtual NIC attached to QEMU user-mode NAT is not a transparent connection to the physical camera LAN; use a suitable host bridge/TAP arrangement or pass through a dedicated Ethernet adapter when testing the full Layer-2 path.

**Caveat:** a VM is not a Pi. It emulates a generic ARM computer, not the Pi's specific USB controller, Ethernet controller, or firmware. A pass here proves "Linux-in-general can do this"; it doesn't guarantee the Pi's specific hardware will behave identically — but it's a solid, fast way to validate the software plan before committing to real hardware.

## Open risks and unknowns

- **radio's RNDIS behaviour is unproven.** RNDIS is a spec, and implementations can have device-specific quirks (link-state reporting, MTU, throughput ceilings). The specification defines what correct behaviour looks like — the initialize handshake and its `MaxTransferSize` ([`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12, §2.2.9 p. 18) and media connect/disconnect signalling (§2.2.7 p. 16) — but having the document does not tell you whether this device honours it. Nothing here substitutes for plugging the real device into real Linux and watching what `dmesg` says.
- **USB power budget.** The Pi 4 limits downstream USB current to roughly 1.1 A in aggregate across its four sockets ([Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.3 p. 11), and wants a 5 V 3 A supply itself (§4.1 p. 8). An underfed bus shows up as resets and disappearing interfaces, not as an obvious power error.
- **The RF-9820S may not present a host network interface at all.** The entire design assumes the radio gives an attached computer a USB Ethernet interface. No public L3Harris material states this. If it does not — or if it requires proprietary L3Harris host software rather than a standard RNDIS/ECM interface — the architecture needs rethinking from the start. **This is the highest-priority unknown**, and only the radio's ICD answers it.
- **SitaWare integration is a separate project from the bridge, and larger.** Packets reaching the CP do not produce map tracks or video feeds. CoT emission, a position source, and a SitaWare-consumable video path all have to be built and tested. Scope and resource this explicitly rather than treating it as the last step of a networking task. See [SitaWare HQ integration](#sitaware-hq-integration).
- **The radio link almost certainly does not carry Layer 2.** A MANET radio is a routing node by design, so the flat-LAN bridge design likely stops at the radio, broadcast discovery will not cross it, and routing becomes the primary architecture. Confirm from the ICD before building.
- **MANET throughput may not carry the video at all.** Tactical wideband MANET is typically low single-digit Mbit/s shared across the net, and the net is also carrying voice and PLI. The 32 Mbit/s planning example below is a Wi-Fi-era figure and should be treated as void until a measured radio figure replaces it. If the gap is large — and it probably is — the fix is a different video design (one stream, heavy compression, stills on demand, or store-and-forward), not network tuning.
- **In-path router defeats the bridge.** Putting a router between the switch and the Pi creates a routed hop inside what was supposed to be one broadcast domain. Keep the router upstream-only unless routing is the deliberate design.
- **No IGMP querier on an isolated segment.** With no router on the camera VLAN, multicast group memberships expire and streams stall a minute or two in. The switch must be configured as querier.
- **Multiple DHCP servers.** Covered above, but worth repeating as a risk: any combination of the radio, the CP router, a field switch and the Pi serving DHCP is a common source of hard-to-diagnose bugs if more than one is left enabled.
- **SWaP on the dismounted end.** A Pi, a switch, cameras and their power all ride on a person alongside the radio. This is a real constraint that networking diagrams hide. Weigh and power-budget the whole field kit before committing; consider whether SitaWare Edge on an existing EUD removes the need for part of it.
- **Two things could make most of this wiki unnecessary.** If the AN/PRC-171 already puts the operator on the SitaWare map via PLI, and if SitaWare Edge is already licensed for the dismounted end, the remaining problem is only "get camera video onto the link" — a much smaller task than what is documented here. Check both before building.
- **Multicast/broadcast dependence, if routing is chosen instead of bridging.** If the video/discovery protocol relies on multicast or broadcast (very common for camera discovery protocols), Option 2 (routing) needs protocol-specific relaying or multicast routing; an IGMP proxy does not relay arbitrary broadcast discovery that Option 1 (bridging) avoids by construction.
- **VM results don't fully transfer to the Pi.** A working ARM64 VM test proves the Linux networking approach is sound, not that the Pi's specific USB/Ethernet silicon will behave identically.

## Next steps checklist

**Answer these before building — in this order**

- [ ] Obtain the AN/PRC-171 / RF-9820S **ICD or programming guide** through your L3Harris channel. Nothing below is answerable without it
- [ ] Confirm the radio presents a **host USB network interface**, and whether Linux binds `rndis_host`, `cdc_ether` or nothing
- [ ] Establish whether that interface **bridges Layer 2 or routes Layer 3** (expect routed)
- [ ] Measure usable MANET throughput at operational range, with the net carrying normal voice/PLI load
- [ ] Ask the SitaWare owner: which HQ version, which of CoT / RTSP / STANAG 4609 are licensed and enabled, and what addresses to send to
- [ ] Check whether the radio's **PLI already puts the operator on the SitaWare map** — this may already be solved
- [ ] Check whether **SitaWare Edge** is available for the dismounted end
- [ ] Re-derive the video budget from the measured link, and decide the video approach it supports
- [ ] Weigh and power-budget the full field kit (Pi + switch + cameras + power)

**Then build and test**

- [ ] Plug the radio into a Linux box (Pi or ARM64 VM) and confirm `usb0`/`enx...` appears in `ip link`
- [ ] Join `usb0` and `eth0` — bridge if the radio allows it, routing if not
- [ ] Configure the field switch (or remove it, if the Pi can take the cameras directly)
- [ ] Go fully static; do not rely on DHCP crossing the RF link
- [ ] Ping test **local only**: camera ↔ Pi ↔ radio host interface
- [ ] Ping test **across the RF link**, CP end to field end
- [ ] Emit CoT from the Pi and confirm the track appears on the SitaWare map
- [ ] Get one video stream into SitaWare at a bitrate the measured link supports
- [ ] Only then add further cameras or streams


## Device facts to collect before configuration

**Identity resolved:** the "9820" is the **L3Harris RF-9820S / AN/PRC-171 Compact Team Radio** — the same device as the data link. Earlier guesses in this wiki (an unidentified video receiver; a Garmin chartplotter) were wrong and have been removed. Throughout this wiki, "the radio" now means this device. What remains unconfirmed is not *what* the device is, but *what interface it presents to a host*.

Treat the following as a bench worksheet, not confirmed specifications.

| Item | Record or verify |
| --- | --- |
| Identity | Confirmed: L3Harris RF-9820S (AN/PRC-171). Record firmware/software version and waveform loadout |
| Host interface | Does a USB host network interface exist at all? Connector, cable, required mode. **Everything depends on this** |
| USB role | The radio is the USB peripheral; the Pi is the USB host |
| USB identity | Vendor/product IDs from `lsusb`; descriptors; driver binding |
| Network | Actual interface name, MAC, address/mask, MTU, link speed |
| Address assignment | Fixed address, DHCP client, or embedded DHCP server |
| Ethernet behaviour | Can it exchange traffic with multiple remote MAC addresses? |
| Video | Camera side only — the radio transports video, it does not serve it. Record camera protocol, port, codec, authentication, client limit |
| SitaWare | HQ version; CoT/RTSP/STANAG 4609 enabled?; target addresses and ports; whether PLI already reaches the map |
| Discovery | Manual IP, broadcast, multicast, or vendor-specific mechanism |
| Radio link | Model, waveform, L2-bridged or L3-routed, throughput, MTU, multicast handling |
| Switch / router | Model, firmware, VLAN and IGMP querier config, port isolation, PoE budget |

When filling in the **USB identity** and **Network** rows, read the descriptors against the protocol documents in [references/pdf/](references/pdf/): [`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf) if the device claims RNDIS, [`usb-cdc-ecm-120.pdf`](references/pdf/usb-cdc-ecm-120.pdf) if it claims CDC-ECM. Record which of the two it actually is; that single fact determines which driver, which quirks and which specification apply to everything downstream.

A working RNDIS interface is only the first checkpoint. Test laptop-to-9820 traffic **through** the bridge: successful Pi-to-9820 traffic alone does not prove transparent forwarding works.

## Bench preparation and evidence collection

Use a Pi with Ethernet and a USB host port, a suitable power supply, a data-capable USB cable, the switch, and a laptop. Keep the radio link out of the bench path until the wired case works.

Three figures from the local [Raspberry Pi 4 Model B datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) (Release 1.1) shape the bench setup:

| Datasheet reference | Figure | Why it matters here |
| --- | --- | --- |
| §2.2 Interfaces, p. 6 | 2× USB2 and 2× USB3 type-A sockets; 1× Gigabit Ethernet port | The two interfaces the bridge joins. These are interface ratings, not a guarantee of radio throughput |
| §4.1 Power Requirements, p. 8 | A good-quality USB-C supply delivering **5 V at 3 A**; a 5 V, 2.5 A supply only if downstream USB devices draw under 500 mA | The radio is a downstream USB device, so the 2.5 A allowance likely does not apply |
| §5.3 USB, p. 11 | Downstream USB current limited to **approximately 1.1 A in aggregate** across all four sockets | A device drawing near that ceiling is a prime suspect for resets and vanishing interfaces |

If using a Pi 5 instead, take its port and power figures from [`references/pdf/raspberry-pi-5-product-brief.pdf`](references/pdf/raspberry-pi-5-product-brief.pdf) rather than assuming the Pi 4 numbers carry over. The [Pi 4 product brief](references/pdf/raspberry-pi-4-product-brief.pdf) is a shorter summary of the same board; prefer the datasheet when the two differ in detail.

On Raspberry Pi OS, install diagnostic utilities if needed:

```bash
sudo apt update
sudo apt install usbutils iproute2 ethtool tcpdump iperf3
```

Record the starting state before changing networking:

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

Replace `usb0` and `eth0` throughout this wiki with the real interface names. Inspect the USB NIC:

```bash
sudo ethtool -i usb0
ip -s link show dev usb0
sudo journalctl -k -f
```

Stop the live log with Ctrl-C. If no interface appears, inspect the USB descriptors and kernel messages before assuming the device uses RNDIS. `sudo modprobe rndis_host` can load an available module; it cannot make an unsupported USB interface compatible. The Pi is the **host** here, so USB gadget instructions for making the Pi impersonate a network device address a different setup. [Linux RNDIS implementation](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c), [Microsoft RNDIS introduction](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2), and the specification itself at [`references/pdf/MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf) — the host/device split it describes (§1.1 glossary, p. 6) is the same split as Pi/radio here.

## Persistent NetworkManager bridge

This is an **IPv4, isolated bench example**, adapted from the [NetworkManager bridge examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html). It assumes the radio accepts `192.168.1.10/24`, the Pi can use `192.168.1.20/24`, and neither address conflicts with an existing network. If the radio has a fixed subnet, adapt the entire plan to it first.

Run the cutover at a local console: moving the Ethernet interface into a bridge can interrupt SSH. Record the existing profile names/UUIDs and autoconnect settings for recovery. Raspberry Pi OS uses NetworkManager by default from Bookworm onward; verify that on your own system with `nmcli device status` rather than trusting the version number, because a Pi upgraded in place from Bullseye may still be running `dhcpcd`. Background on that transition is in the local copy of Raspberry Pi's migration whitepaper, [`references/pdf/transitioning-bullseye-to-bookworm.pdf`](references/pdf/transitioning-bullseye-to-bookworm.pdf) (19 pages, 15 August 2024) — its text could not be machine-extracted for section-level citation here, so read it directly rather than quoting it second-hand. For deployment, prefer the current [Raspberry Pi configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) documentation over the 2024 whitepaper.

If `nmcli device status` shows the interfaces as unmanaged, or `dhcpcd` is still driving them, resolve that before creating any bridge profile: the procedure below assumes NetworkManager owns both ports.

### Create the profiles

Check that these profile names and `br0` do not already exist. Run once:

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

`master` is the compatibility alias for newer `controller` terminology. The Pi’s management address belongs on `br0`; its member ports should not retain independent IP configuration. No gateway or DNS is needed for same-subnet bench traffic. Disabling IPv6 on this profile does not filter IPv6 frames passing through the bridge. Settings are documented in [NetworkManager’s property reference](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

### Activate and check

For each existing standalone profile bound to these ports, first record its UUID and original autoconnect setting. At the local console, replace the placeholder below and repeat only for the relevant profiles:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect no
sudo nmcli connection down uuid <OLD_PROFILE_UUID>
```

Then activate the bridge and ports:

```bash
sudo nmcli connection up rndis-br0
sudo nmcli connection up rndis-lan-port
sudo nmcli connection up rndis-usb-port
nmcli device status
ip -br address
bridge link show
```

Allow STP convergence before testing. Verify that both ports belong to `br0` and eventually enter forwarding state. Connect `eth0` to an access port on the camera VLAN of the switch. For the all-static example, disable DHCP on the test LAN and assign the laptop `192.168.1.30/24` and cameras `.101/24`, `.102/24`. No default gateway is needed for these local tests.

If using DHCP instead, select one server, exclude static addresses from its pool, and configure clients accordingly. Do not select NetworkManager `ipv4.method shared` for this transparent bridge example; it introduces connection-sharing behaviour.

### Recovery

From the local console, remove only the profiles created by this procedure:

```bash
sudo nmcli connection down rndis-br0
sudo nmcli connection delete rndis-lan-port rndis-usb-port rndis-br0
```

Restore each old profile’s recorded autoconnect value, then reactivate the profiles that were previously active:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect yes
sudo nmcli connection up uuid <OLD_PROFILE_UUID>
```

Use `no` instead of `yes` if that was the recorded value. Reboot is not a rollback for persistent NetworkManager configuration.

## Packet tracing and troubleshooting

Start with addressing and link state, then trace one connection from both interfaces. Run these captures in separate terminals while initiating traffic from the laptop:

```bash
sudo tcpdump -ni eth0 -e 'arp or icmp'
sudo tcpdump -ni usb0 -e 'arp or icmp'
```

For a short capture of traffic to/from the example radio address:

```bash
sudo timeout 30 tcpdump -ni usb0 -s 0 -w rndis-test.pcap 'host 192.168.1.10'
```

Packet captures can contain video and credentials; keep bench captures local and redact before sharing.

| Symptom | Check next | Reference document |
| --- | --- | --- |
| Nothing in `lsusb` | Data cable, power, USB host/peripheral roles, correct device port | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §4.1 p. 8 (5 V 3 A supply) |
| USB enumerates but no NIC | USB mode/descriptors, kernel log, available driver and device support | [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12 and §2.2.9 p. 18 (the initialize handshake that must complete); [CDC-ECM](references/pdf/usb-cdc-ecm-120.pdf) if the descriptors say ECM, not RNDIS |
| NIC appears then disappears | Kernel USB reset messages, power supply, cable, reconnect behaviour | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.3 p. 11 (~1.1 A aggregate downstream limit); [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.6 p. 15 (reset) and §2.2.8 p. 17 (keepalive) |
| Link never comes up, or flaps | Whether the device ever signals media connect | [MS-RNDIS](references/pdf/MS-RNDIS.pdf) §2.2.7 p. 16 with status values `RNDIS_STATUS_MEDIA_CONNECT` / `_DISCONNECT` in §2.2.1.2 p. 12 |
| Pi reaches the radio but the CP cannot | Bridge membership/state, client isolation, ARP on both ports, device MAC filtering — **and whether the radio link forwards Layer 2 at all** | [Linux bridge documentation](https://docs.kernel.org/networking/bridge.html); [Transport link](#transport-link-harris-radio-data-link) |
| No address on a DHCP client | DHCP server presence, scope, competing servers, UDP 67/68 captures. A routed radio link will not relay DHCP without explicit configuration | [Transport link](#transport-link-harris-radio-data-link) |
| IP access works; discovery fails | Discovery protocol, client isolation, multicast memberships, application firewall. Broadcast/multicast discovery is the first thing a tactical radio link drops | Radio and switch documentation (not yet obtained) |
| Stream starts then stalls | Loss, bitrate bursts, USB resets, multicast membership expiry, thermal/power state, **radio link capacity and contention** | [Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §5.6 p. 11 (0–50 °C recommended ambient; CPU throttles to stay under 85 °C) |
| Works until reboot | Profile autoconnect, competing old profiles, interface name changes | [Bullseye-to-Bookworm whitepaper](references/pdf/transitioning-bullseye-to-bookworm.pdf) if the Pi was upgraded in place and still has `dhcpcd` remnants |
| Ping fails but application works | Endpoint may block ICMP; validate the actual application protocol | — |

Additional observations:

```bash
bridge fdb show br br0
bridge mdb show dev br0
ip -s link show dev eth0
ip -s link show dev usb0
sudo nft list ruleset
```

### Multicast and discovery

The Linux bridge enables multicast snooping by default and tracks group membership. Check `bridge mdb show` while clients are active. A network using snooping needs appropriate membership refresh/query behaviour; do not assume the upstream switch or radio supplies a querier. For a controlled diagnostic comparison, record the current setting with `ip -d link show br0`, temporarily run `sudo ip link set dev br0 type bridge mcast_snooping 0`, and restore the recorded value afterward. This is a runtime test and can increase multicast flooding. See [Linux bridge multicast documentation](https://docs.kernel.org/networking/bridge.html).

A successful comparison points toward multicast handling, not proof of a permanent fix. Check the switch and the radio link as well as the Pi. Routing needs separate treatment for multicast media and each discovery protocol; no single IGMP setting forwards all broadcast or service discovery traffic.

### Isolating which hop broke

With a switch and a radio link in the path, test hop by hop rather than end to end:

1. Pi ↔ radio across `usb0` only.
2. Pi ↔ a laptop plugged directly into the switch (same VLAN, no radio).
3. Pi ↔ a laptop across the radio link.

Step 2 passing and step 3 failing points at the radio link, not the bridge.

## Routing fallback design

Use routing when the USB device cannot support transparent bridging or when separate subnets are required. First confirm the radio can use a gateway or suitable static routes.

| Segment | Example addressing | Required return path |
| --- | --- | --- |
| USB | Pi `192.168.10.1/24`, radio host interface `192.168.10.2/24` | Radio's route to `192.168.20.0/24` through `.10.1` |
| Camera LAN | Pi `192.168.20.1/24`, cameras `.20.101/24` onward | Camera/laptop route to `192.168.10.0/24` through `.20.1` |

These are alternative addresses, not additions to the bridge configuration. Remove bridge membership before configuring independent routed interfaces. Enable IPv4 forwarding and add narrowly scoped forwarding rules in the existing firewall, including reply traffic. Do not flush an existing ruleset. The final rules depend on traffic direction and application ports, which remain unknown.

NAT may help when an endpoint cannot install a return route, but changes peer addresses and can complicate incoming connections and discovery. It is a separate design choice, not a requirement for routing. Routing is not yet a copy-and-run deployment recipe in this wiki.

## Throughput and acceptance tests

Estimate load before choosing stream settings. For example, four 8 Mbit/s streams total **32 Mbit/s of encoded video payload** on a link carrying all four. Budget additional capacity for packet overhead, bitrate peaks, retransmissions and concurrent viewers. This is a planning example, not a measurement of the radio.

The Pi 4's Gigabit Ethernet port and USB 2/3 sockets ([Pi 4 datasheet](references/pdf/raspberry-pi-4-datasheet.pdf) §2.2, p. 6) are interface ceilings only. Two things on this path are far more likely to bind:

1. **Whatever the radio's RNDIS implementation sustains over USB**, which no datasheet in this library covers.
2. **The Harris radio data link**, which on most tactical waveforms is one to three orders of magnitude slower than the Ethernet segments either side of it.

> **The 32 Mbit/s planning example above assumes a Wi-Fi-class link and is almost certainly wrong for a tactical radio data link.** Re-derive the video budget from the radio's actual usable throughput, measured under representative range and contention, before choosing any stream setting. If the link delivers, say, 2 Mbit/s usable, four simultaneous 8 Mbit/s streams is not a tuning problem — it is a different system design.

Measure with endpoints that can run `iperf3`; do not assume the radio can. A laptop-to-Pi test checks that partial path only. To validate the USB path, use a supported test service on the device or measure real streaming across USB.

Measure each segment separately, because a single end-to-end number will not tell you which hop is the ceiling:

| Segment | How to measure |
| --- | --- |
| Pi ↔ radio (USB/RNDIS) | Device test service, or real streaming across USB |
| Pi ↔ switch (Ethernet) | `iperf3` between Pi and a wired laptop |
| Across the radio link | `iperf3` between wired laptop and remote laptop, at representative range |

| Test | Proposed pass evidence |
| --- | --- |
| Enumeration | Stable NIC, correct driver, no recurring USB errors |
| Addressing | Unique addresses; expected DHCP server or fully static setup |
| Connectivity | CP end reaches the camera streams through the full path |
| SitaWare | Operator track appears on the map; video opens from a SitaWare client |
| Discovery | Actual required discovery works, if the application needs it |
| Radio link budget | Measured usable throughput at representative range meets the video budget with margin |
| Video | All intended streams work simultaneously at required resolution/bitrate |
| Soak | Suggested first bench run: 60 minutes; record loss, stalls and errors |
| Recovery | USB reconnect, radio link drop/reacquire and Pi reboot restore service |
| Persistence | Ports rejoin `br0`; no old profile steals an interface |

Agree acceptable latency, frame loss, reconnect time and test duration before calling the system production-ready. Record firmware, kernel, OS, topology and stream settings with every result.

## Reference library and PDF resources

Sources below were consulted on **23 September 2026**. They establish general platform behaviour and product positioning — not that the RF-9820S presents a Linux-compatible USB network interface, which remains unverified. Upstream `latest` and `master` pages change; record the deployed versions when reproducing results.

### Official web references and source code

| Resource | What to pull from it |
| --- | --- |
| [Microsoft: Introduction to RNDIS](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2) | Protocol purpose and host/device concepts; the normative detail is in the local [`MS-RNDIS.pdf`](references/pdf/MS-RNDIS.pdf) |
| [Linux: rndis_host.c](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c) | Driver matching, implementation, quirks; compare with the installed kernel |
| [Linux: Ethernet bridging](https://docs.kernel.org/networking/bridge.html) | Forwarding, STP, multicast snooping and bridge attributes |
| [NetworkManager: nmcli examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html) | Bridge/port profiles and recovery checkpoints |
| [NetworkManager: connection properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html) | IP methods, controller/port settings, autoconnect behaviour |
| [Raspberry Pi: configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) | OS networking and NetworkManager setup |
| [Raspberry Pi: hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) | Board ports, power and hardware constraints |
| [QEMU: ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) | ARM machine selection and acceleration constraints |
| [QEMU: USB emulation/passthrough](https://www.qemu.org/docs/master/system/devices/usb.html) | Passing a real USB device to a guest |
| [L3Harris: AN/PRC-171 product page](https://www.l3harris.com/all-capabilities/an-prc-171-compact-team-radio) | Radio role, waveforms (wideband MANET, narrowband voice/PLI), battery life |
| [Systematic: SitaWare open architecture](https://systematic.com/int/industries/defence/products/sitaware-suite/sitaware-edge/open-architecture/) | **The most useful integration page found.** Names CoT, RTSP, RTMP, STANAG 4609, NMEA 0183, GPSD, and the APIs/SDK |
| [Systematic: SitaWare Headquarters](https://systematic.com/int/industries/defence/products/sitaware-suite/sitaware-headquarters/) | HQ capabilities, FMV as an intelligence stream, map overlay and WMS-T ingestion |

### Downloadable PDFs

These were downloaded on **23 September 2026** into [references/pdf/](references/pdf/), verified to be real PDFs, and checksummed. Publisher, document number, revision, page count, source URL and SHA-256 for each one are recorded in [references/pdf/MANIFEST.md](references/pdf/MANIFEST.md). They establish platform and protocol behaviour in general; none of them says anything about the radio.

| PDF | Local copy | Useful material | Status and limitation |
| --- | --- | --- | --- |
| [Raspberry Pi 4 Model B product brief](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS/raspberry-pi-4-product-brief) | `raspberry-pi-4-product-brief.pdf` | USB/Ethernet interfaces, power, dimensions | 7 pages, April 2026 edition; marketing-level summary, not an RNDIS guarantee |
| [Raspberry Pi 4 Model B datasheet](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf) | `raspberry-pi-4-datasheet.pdf` | Section-level USB (§5.3) and Ethernet detail, power requirements, mechanicals | 13 pages, Release 1.1 (12 March 2024); the board-level reference to use over the product brief |
| [Raspberry Pi 5 product brief](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf) | `raspberry-pi-5-product-brief.pdf` | Port layout and power budget if a Pi 5 is used instead of a Pi 4 | 6 pages, April 2026 edition; no Pi 5 datasheet equivalent is included here |
| [Raspberry Pi: Transitioning from Bullseye to Bookworm](https://pip-assets.raspberrypi.com/categories/1261-transitioning/documents/RP-006519-WP-1-Transitioning%20from%20Bullseye%20to%20Bookworm.pdf) | `transitioning-bullseye-to-bookworm.pdf` | NetworkManager migration context behind the Bookworm default | 19 pages, 15 August 2024. **The URL previously cited here now 404s**; this is the working location. Use current configuration docs for deployment |
| [Microsoft: MS-RNDIS specification](https://download.microsoft.com/download/5/0/1/501ED102-E53F-4CE0-AA6B-B0F93629DDC6/Windows/%5BMS-RNDIS%5D.pdf) | `MS-RNDIS.pdf` | Message structures, control/data channels, protocol terminology | 46 pages; release stamp 1 May 2014, revision summary ending at revision 5.0 (15 May 2014). Not verified as the newest revision |
| [USB-IF: CDC Ethernet Control Model subclass](https://www.usb.org/sites/default/files/CDC1.2_WMC1.1_012011.zip) | `usb-cdc-ecm-120.pdf` | Descriptor layout and control requests for CDC-ECM | 23 pages, from the CDC 1.2 / WMC 1.1 package (January 2011). Relevant if the radio presents ECM (Linux `cdc_ether`) rather than RNDIS. Extracted from the USB-IF archive, which also carries an adopters agreement — check those terms before redistributing |
| [L3Harris: AN/PRC-171 Compact Team Radio sell sheet](https://www.l3harris.com/all-capabilities/an-prc-171-compact-team-radio) | `l3harris-an-prc-171-compact-team-radio-sell-sheet.pdf` | Product positioning, waveform and role summary for the radio in use | 2 pages, public marketing sell sheet. **Text not machine-extractable**, so nothing is cited to a page here. States nothing about the host data interface or data rates |
| [L3Harris: RF-9820S Compact Team Radio sell sheet](https://www.l3harris.com/resources/rf-9820s-compact-team-radio-sell-sheet) | `l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf` | Same radio under its commercial designation | 2 pages, public marketing sell sheet. Text not machine-extractable |
| [L3Harris: RF-9820S-ER Embeddable Modular Radio sell sheet](https://www.l3harris.com/sites/default/files/2025-04/l3harris-rf-9820s-er-sell-sheet-cs-tcom.pdf) | `l3harris-rf-9820s-er-embeddable-modular-radio-sell-sheet.pdf` | The **embeddable variant** — different product | 2 pages. Do not transfer its figures (e.g. 225 MHz–2.6 GHz, AES-256) to the handheld without checking |
| [Systematic: SitaWare Headquarters sales flyer](https://systematic.com/int/industries/defence/news-knowledge/downloads/flyers/sitaware-headquarters-flyer/) | `sitaware-headquarters-sales-flyer.pdf` | What HQ does; FFT and interoperability positioning | 2 pages, public marketing flyer. Text not machine-extractable. Not an interface specification |
| [Systematic: SitaWare Edge sales flyer](https://systematic.com/int/industries/defence/news-knowledge/downloads/flyers/sitaware-edge-flyer/) | `sitaware-edge-sales-flyer.pdf` | The dismounted product — relevant to whether Edge removes work from the Pi | 2 pages, public marketing flyer |

**On the L3Harris and Systematic documents:** all five are *public marketing material*. They establish what the products are; they do not specify interfaces, throughput, or how to integrate. The documents that would answer this project's real questions — the radio's ICD/programming guide, and SitaWare's integration/API documentation — are obtained through programme and vendor channels, not the public web. Neither is held here.

To re-fetch or verify a copy from the project directory:

```bash
mkdir -p references/pdf
curl --fail --location --output references/pdf/raspberry-pi-4-datasheet.pdf \
  'https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008341-DS-1-raspberry-pi-4-datasheet.pdf'
file references/pdf/raspberry-pi-4-datasheet.pdf
sha256sum references/pdf/raspberry-pi-4-datasheet.pdf
```

Confirm the download is a PDF before relying on it — a portal that has moved a document may return an HTML error page with a `.pdf` URL. For each saved source, record the publisher, title, revision/date, URL, retrieval date, checksum and relevant pages, as the manifest does. Raspberry Pi documents are published under a Creative Commons Attribution-NoDerivatives licence: keep the originals unmodified and separate from bench notes, and check publisher terms before redistributing copies.

### Vendor documents still needed

- **AN/PRC-171 / RF-9820S Interface Control Document, operator manual and programming guide.** **This is the critical path.** Needed for: whether a host USB network interface exists, what it presents (RNDIS / CDC-ECM / proprietary), L2 versus L3 behaviour, addressing and route injection, MTU, multicast, throughput per waveform, and PLI reporting behaviour. Obtain through your programme's L3Harris channel.
- **SitaWare integration documentation:** HQ version and licensed interfaces, CoT ingestion configuration, RTSP/FMV handling, STANAG 4609 requirements, and API/SDK access terms. Obtain from your SitaWare administrator or Systematic.
- **Switch documentation:** for whichever field and CP devices are chosen.
- **Camera manuals:** supported stream protocols, codecs, bitrate controls, and whether the bitrate can be driven low enough for the measured RF link.

Add exact document titles, revisions and page references here when identified. Do not substitute a manual for an unrelated product sharing the number “radio”.

Note that these vendor documents are distributed under their own terms. Harris/L3Harris tactical radio documentation in particular is frequently export-controlled or distribution-restricted; obtain it through the proper channel for your programme rather than from a general web search, and do not commit restricted documents into this repository.

## Test record template

```text
Date / operator:
9820 manufacturer / full model / firmware:
Pi model / OS / kernel / NetworkManager version:
Switch model / firmware / VLAN / port config:
Router model / firmware / role (in-path or upstream-only):
Harris radio model / waveform / bandwidth setting / firmware:
Radio link mode (bridged L2 or routed L3) / measured usable throughput / range:
USB VID:PID / driver / interface / negotiated speed:
Address plan / DHCP owner:
Camera models / stream protocol / bitrate / number of viewers:
Bridge or routing configuration:
Tests performed / duration:
Observed throughput / loss / stalls / recovery time:
Logs or capture filenames:
Source documents / revision / relevant pages (see references/pdf/MANIFEST.md):
Result / remaining issue / next action:
```
