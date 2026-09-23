[← Wiki index](../README.md)

# Full architecture

```
  Remote / camera side              Local side
  ─────────────────────             ──────────────────────────────────────────

  Camera 1 ─┐
  Camera 2 ─┼─► [ Harris radio ] ))))  RF data link  ((( [ Harris radio ]
  Camera N ─┘                                                   │
                                                                │ Ethernet
                                                        ┌───────┴────────┐
                                                        │ Switch / router│
                                                        │  (VLAN, IGMP   │
                                                        │    querier)    │
                                                        └───────┬────────┘
                                                                │ Ethernet
                                                              eth0
                                                        ┌───────┴────────┐
                                                        │  Raspberry Pi  │
                                                        │    (Linux)     │
                                                        │  eth0 ↔ usb0   │
                                                        │      br0       │
                                                        └───────┬────────┘
                                                              usb0
                                                                │ USB (RNDIS)
                                                          ┌─────┴─────┐
                                                          │   9820    │
                                                          │ (receives │
                                                          │  video)   │
                                                          └───────────┘
```

> **Which side the cameras sit on is not yet settled.** The diagram above assumes the cameras are at the far end of the radio link and the 9820 is local to the Pi. The reverse — cameras local, remote viewing client across the link — changes where the bottleneck bites but not the Pi's job. Confirm this before sizing the [video budget](../test/throughput-and-acceptance.md).

The Pi has exactly two jobs:

1. **See the 9820 as a network interface** (`usb0`) via the RNDIS host driver.
2. **Join `usb0` and `eth0`** so packets flow between them, either as one flat Layer-2 network (bridge) or as two routed subnets (router). See [Bridge vs. route](bridge-vs-route.md).

The Pi forwards network traffic without decoding video. Discovery and streaming still depend on endpoint compatibility, radio link behaviour, multicast handling, and sufficient bandwidth.

## The three devices that are not the Pi

| Device | Role | Page |
| --- | --- | --- |
| Harris radio data link | The wireless transport, and the throughput bottleneck | [Transport link](transport-link.md) |
| Switch (and router, if needed) | Aggregation into the Pi; VLAN and IGMP querier | [Switch and router selection](../build/switch-and-router.md) |
| 9820 | The USB/RNDIS endpoint; identity still unconfirmed | [Device facts](../plan/device-facts.md) |

Of these, the radio is the one that decides the architecture. Read [Transport link](transport-link.md) before treating the bridge design as settled.

---

Previous: [What RNDIS actually is](what-rndis-is.md) · Next: [Bridge vs. route](bridge-vs-route.md)
