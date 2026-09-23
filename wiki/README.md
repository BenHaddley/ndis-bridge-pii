# RNDIS Bridge on Raspberry Pi

_Last updated: Sep 23, 2026_

Connecting the 9820's USB network interface to a camera LAN through a Raspberry Pi, a switch, and a Harris radio data link.

## Contents

**Concepts — what this is and how it works**

- [What RNDIS actually is](concepts/what-rndis-is.md)
- [Full architecture](concepts/architecture.md)
- [Bridge vs. route](concepts/bridge-vs-route.md)
- [Transport link: Harris radio data link](concepts/transport-link.md) ← **read before treating the bridge design as settled**

**Plan — decide before touching hardware**

- [Hardware test plan](plan/hardware-test-plan.md)
- [DHCP: pick exactly one server](plan/dhcp.md)
- [Device facts to collect before configuration](plan/device-facts.md)
- [Open risks and unknowns](plan/risks-and-unknowns.md)
- [Next steps checklist](plan/next-steps.md)

**Build — the actual configuration**

- [Bench preparation and evidence collection](build/bench-preparation.md)
- [Persistent NetworkManager bridge](build/networkmanager-bridge.md)
- [Switch and router selection](build/switch-and-router.md)
- [Routing fallback design](build/routing-fallback.md)

**Test — prove it works, then prove it keeps working**

- [Testing without a Pi: an ARM64 VM](test/vm-testing.md)
- [Packet tracing and troubleshooting](test/troubleshooting.md)
- [Throughput and acceptance tests](test/throughput-and-acceptance.md)
- [Test record template](test/test-record-template.md)

**Reference**

- [Reference library and PDF resources](reference/library.md)
- Local PDF copies live in [`references/pdf/`](../references/pdf/), catalogued in [`MANIFEST.md`](../references/pdf/MANIFEST.md)

## Overview

The goal is to connect the 9820's USB network interface to a camera LAN through a Raspberry Pi, a switch, and a Harris radio data link. This provides network connectivity in both directions; it does not itself export or re-stream video received by the 9820. Viewing that video on another device requires a camera stream or a documented streaming service on the 9820.

The working assumption is that the 9820 exposes a network connection over **USB, using RNDIS** (a USB-to-Ethernet protocol). A Raspberry Pi sits in the middle and does the translation: it takes the RNDIS "virtual Ethernet" coming in over USB and connects it to a real Ethernet port, which feeds a switch and, beyond it, the radio data link.

Target data path:

```
Camera 1 ─┐
Camera 2 ─┼──► Harris radio ))) RF ((( Harris radio ──► switch ──Ethernet──►
Camera N ─┘                                            [eth0  Raspberry Pi  usb0] ──USB/RNDIS──► 9820
```

The Pi does no video processing — it is purely a network bridge/router joining two interfaces (`usb0` from the 9820, `eth0` to the switch) so traffic flows transparently between them.

**Verdict: the Linux architecture is feasible; this particular device is not yet validated, and the transport is now the dominant unknown.** Linux has a mature host-side RNDIS driver, and bridging or routing between interfaces is a well-worn technique — the Raspberry Pi is a reasonable box to run it on. Two things still have to be confirmed on real hardware:

1. Whether the 9820's specific RNDIS implementation behaves like a clean, standard Ethernet NIC.
2. Whether the [Harris radio data link](concepts/transport-link.md) carries Layer 2 and enough throughput for the intended video. This replaced a Wi-Fi AP, and it is not a like-for-like substitution.

## Where to start

Start with [Transport link](concepts/transport-link.md) — the radio's behaviour decides more about the final architecture than anything on the Pi does.

Then, if hardware is in hand, go to [Bench preparation](build/bench-preparation.md) and the [Hardware test plan](plan/hardware-test-plan.md). If it is not, [Testing without a Pi](test/vm-testing.md) de-risks the software side first.

## Repository layout

```
.
├── wiki/
│   ├── README.md                  ← you are here
│   ├── concepts/                  what RNDIS is, architecture, bridge vs. route
│   ├── plan/                      test plan, DHCP, device facts, risks, checklist
│   ├── build/                     bench prep, NetworkManager bridge, routing fallback
│   ├── test/                      VM testing, troubleshooting, throughput, record template
│   └── reference/                 reference library and PDF resources
└── references/
    └── pdf/                       local PDF copies + MANIFEST.md
```
