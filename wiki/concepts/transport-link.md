[← Wiki index](../README.md)

# Transport link: Harris radio data link

The wireless leg of this system is a **Harris (L3Harris) radio data link**, not a Wi-Fi access point. That substitution is not like-for-like, and it is the single largest change to the assumptions the rest of this wiki was originally written against.

> **Status:** the specific radio model and waveform have not yet been recorded. Everything below is written as questions to answer against the radio's own documentation, not as claims about your radio. Fill in [Device facts to collect](../plan/device-facts.md) and the [test record](../test/test-record-template.md) before committing to a design.

## Why this changes the design

A Wi-Fi access point in bridge mode is a transparent Layer-2 device on a fast link. A tactical radio data link generally is neither. Three properties decide the whole architecture:

### 1. Does the link bridge Layer 2, or route Layer 3?

This is the first question to answer, because [the wiki's default recommendation — bridge first](bridge-vs-route.md) — depends on it.

| If the radio link… | Then… |
| --- | --- |
| Presents a **transparent Layer-2 Ethernet bridge** (typical of broadband line-of-sight Ethernet radios) | The flat-LAN bridge design in [Persistent NetworkManager bridge](../build/networkmanager-bridge.md) still works end to end. Broadcast and multicast discovery have a chance of crossing |
| Presents a **routed Layer-3 IP interface** (typical of narrowband and wideband tactical waveforms) | The Layer-2 bridge **stops at the radio**. Broadcast discovery does not cross it. [Routing (Option 2)](../build/routing-fallback.md) becomes the primary design, not the fallback, and every discovery protocol needs individual treatment |

Most tactical waveforms fall in the second row. Do not assume the first without confirming it.

### 2. What is the usable throughput, at range, under contention?

Tactical radio data links span a very wide range — from well under 1 Mbit/s on narrowband waveforms to tens of Mbit/s on broadband line-of-sight links. The Ethernet segments either side of the radio are effectively free by comparison; **the radio is the bottleneck and nothing else on this path is close.**

The video budget in [Throughput and acceptance tests](../test/throughput-and-acceptance.md) uses a 32 Mbit/s example that came from Wi-Fi-era assumptions. Re-derive it from a *measured* radio figure at representative range, not a datasheet maximum. If the measured link cannot carry the intended streams, the answer is a change to the video design — fewer streams, lower resolution, harder compression, or on-demand rather than continuous — not bridge tuning.

### 3. What does it do to MTU, multicast and DHCP?

- **MTU.** Tactical links commonly run a reduced MTU. A path MTU smaller than the LAN's causes fragmentation or silent drops of full-size frames, which typically shows up as "small packets work, video does not." Record the radio's MTU and set interfaces consistently. Note this interacts with the RNDIS `MaxTransferSize` negotiated at the USB end ([`MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12).
- **Multicast.** Confirm explicitly whether the radio forwards multicast, and on what groups. Many tactical links restrict or suppress it by default because it is expensive on a shared channel.
- **DHCP.** A routed radio link will not relay DHCP between ends without explicit configuration. This strengthens the case for the all-static address plan in [DHCP: pick exactly one server](../plan/dhcp.md).

## Facts to record about the radio

| Item | Record or verify |
| --- | --- |
| Identity | Model, waveform(s) in use, firmware/software version |
| Host interface | Ethernet or USB; port type; negotiated speed |
| Link mode | Transparent Layer-2 bridge, or routed Layer-3 interface |
| Addressing | Radio's own IP, whether it acts as gateway, whether it serves DHCP |
| Throughput | Datasheet figure **and** measured usable rate at representative range |
| MTU | Configured and effective path MTU |
| Multicast | Forwarded or suppressed; any group restrictions; IGMP behaviour |
| Latency / jitter | Typical and worst case — matters for streaming, not just for ping |
| Behaviour on link loss | Reacquire time; whether the Ethernet port drops carrier when the RF link drops |

That last row matters more than it looks. If the radio drops Ethernet carrier when the RF link drops, the Pi's bridge port will go down and come back, and you need to know that STP reconverges cleanly rather than blackholing traffic.

## Documentation note

Harris/L3Harris tactical radio documentation is frequently export-controlled or distribution-restricted. Obtain it through the proper channel for your programme rather than a general web search, and do not commit restricted documents into this repository. The [reference library](../reference/library.md) lists it as needed but deliberately holds no copy.

---

Previous: [Bridge vs. route](bridge-vs-route.md) · Next: [Switch and router selection](../build/switch-and-router.md)
