[← Wiki index](../README.md)

# Switch and router selection

The requirement is a device to act as the switch and router into the Pi. This page covers what that device actually has to do, where it sits, and what to buy.

## First: do you need the router at all?

Probably not in-path. Check this before choosing hardware.

The whole point of the [Layer-2 bridge design](../concepts/bridge-vs-route.md) is that the 9820 and the camera-side clients sit on one flat subnet. **A router placed in-path between the switch and the Pi defeats that** — it makes a routed hop in the middle of what was supposed to be a single broadcast domain, and broadcast discovery dies at it.

Three valid arrangements:

| Arrangement | When it applies |
| --- | --- |
| **Switch only, in-path; no router** | The radio link bridges Layer 2, or the radio does the routing itself. Simplest, and the best match for the bridge design |
| **Switch in-path; router hanging off it, upstream-only** | You need upstream/Internet access or services (NTP, management) but the camera↔9820 path stays flat. This is what the topology diagram's "Optional — for upstream network/Internet" note describes |
| **Router in-path, doing Layer 3** | The radio presents a routed interface and you need policy, firewalling or address separation. This is [routing fallback design](routing-fallback.md), not the bridge design |

Which one you are in is decided by the radio, not by the switch. Settle [Transport link](../concepts/transport-link.md) question 1 first.

## What the device actually has to do

Ranked by how much it matters here, not by marketing prominence:

1. **IGMP snooping with a configurable querier.** The most important feature on the list. Camera discovery and streaming are typically multicast. On an isolated segment there is no router to send IGMP queries, so group memberships expire and streams stop after a minute or two — the classic "stream starts then stalls" symptom in [troubleshooting](../test/troubleshooting.md). The switch must be able to act as querier.
2. **VLAN support**, to separate the camera segment from management traffic.
3. **No forced client/port isolation**, so the Pi's bridge can see the camera MACs.
4. **Port count and PoE budget.** If the cameras are PoE, size the budget properly — PoE+ at 30 W per port adds up fast, and this is the most common reason a switch choice has to be redone.
5. **Power input.** Field and vehicle installations usually mean DC input (12/24 V), not mains.
6. **Environmental rating.** Fanless, temperature range, shock/vibration — relevant if this is deployed alongside tactical radios rather than sitting on a bench.

Raw switching throughput is not on this list. Every option below is orders of magnitude faster than the radio link.

## Options

| Option | What it is | Fits when |
| --- | --- | --- |
| **Cisco ISR 1100 series** (e.g. ISR1111X-8P) | Router with an integrated 8-port managed switch — one box, both roles | You genuinely want a single device doing switch **and** router, in a benign environment |
| **Cisco IR1101** | Industrial/rugged modular router, DIN-rail, wide temperature range, DC input, expansion modules | Field or vehicle installation next to tactical radios. The usual choice in this kind of deployment |
| **Cisco ESR-6300** | Embedded Services Router, designed for vehicle and tactical integration, DC powered | Same as above, where the install is inside a platform rather than a rack |
| **Cisco Catalyst 9200CX compact** | Compact fanless managed switch, no routing | The radio routes, so you only need the switch — the common case |
| **MikroTik RB5009 / hEX, Ubiquiti EdgeRouter** | Low-cost managed switch/router | Proving the design on the bench before committing to the deployed hardware |

The topology diagram's Catalyst 9200 + ISR 1100 pairing is a perfectly reasonable managed-network answer. For a field deployment alongside Harris radios, an IR1101 or ESR-6300 is the more natural fit, and it collapses switch and router into one rugged box.

**Cheapest path to a working answer:** prove the design on a bench switch you already have, confirm which of the three arrangements above you are actually in, then buy the deployed hardware once. The radio's Layer-2-versus-Layer-3 behaviour will decide more about the final design than the switch model does.

## Configuration checklist

Whatever device is chosen:

- [ ] Put the camera segment on its own VLAN; keep switch management off it or on a separate tagged VLAN
- [ ] Enable IGMP snooping on that VLAN
- [ ] Configure the switch as **IGMP querier** on that VLAN (there is no router on an isolated segment to do it)
- [ ] Confirm no port isolation / protected-port setting is enabled on the Pi's port or the camera ports
- [ ] Record port assignments and MAC addresses for the [test record](../test/test-record-template.md)
- [ ] Set exactly one DHCP server, or go fully static — see [DHCP](../plan/dhcp.md)
- [ ] If PoE: confirm total draw against the switch's PoE budget, not just per-port capability
- [ ] Verify the Pi's `eth0` link comes up at expected speed/duplex after the bridge is built

## Where the Pi sits

The Pi's `eth0` is an ordinary access port in the camera VLAN. The Pi bridges that to `usb0` ([procedure](networkmanager-bridge.md)). From the switch's point of view the Pi is a two-port device that will source frames with the 9820's MAC — which is exactly why port security or MAC-limiting on that port will break it. Leave both off on the Pi's port.

---

Previous: [Routing fallback design](routing-fallback.md) · Next: [Testing without a Pi](../test/vm-testing.md)
