[← Wiki index](../README.md)

# Device facts to collect before configuration

"9820" alone does not identify a manufacturer or protocol. The topology diagram names it a **Garmin 9820**; treat that as a lead to confirm, not a recorded fact, because no vendor manual has yet been matched to this device. Treat the following as a bench worksheet, not confirmed specifications.

> If the 9820 turns out to be a Garmin marine unit, check whether it has a native Ethernet marine-network port. A device with its own Ethernet interface may not need the Pi, the RNDIS bridge, or most of this wiki. That check is worth ten minutes before building anything.

| Item | Record or verify |
| --- | --- |
| Identity | Manufacturer, full model number, firmware, manual revision |
| Native networking | Does it have an Ethernet / marine-network port as well as USB? If so, why use USB at all? |
| USB role | 9820 is the USB peripheral; Pi is the USB host |
| USB identity | Vendor/product IDs from `lsusb`; descriptors; driver binding |
| Network | Actual interface name, MAC, address/mask, MTU, link speed |
| Address assignment | Fixed address, DHCP client, or embedded DHCP server |
| Ethernet behaviour | Can it exchange traffic with multiple remote MAC addresses? |
| Video | Receives, serves, or both? Protocol, port, codec, authentication, client limit |
| Discovery | Manual IP, broadcast, multicast, or vendor-specific mechanism |
| Radio link | Model, waveform, L2-bridged or L3-routed, throughput, MTU, multicast handling — see [Transport link](../concepts/transport-link.md) |
| Switch / router | Model, firmware, VLAN and IGMP querier config, port isolation, PoE budget |

When filling in the **USB identity** and **Network** rows, read the descriptors against the protocol documents in [`references/pdf/`](../../references/pdf/): [`MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf) if the device claims RNDIS, [`usb-cdc-ecm-120.pdf`](../../references/pdf/usb-cdc-ecm-120.pdf) if it claims CDC-ECM. Record which of the two it actually is; that single fact determines which driver, which quirks and which specification apply to everything downstream.

A working RNDIS interface is only the first checkpoint. Test laptop-to-9820 traffic **through** the bridge: successful Pi-to-9820 traffic alone does not prove transparent forwarding works.

Vendor documents still needed are listed in the [reference library](../reference/library.md#vendor-documents-still-needed).

---

Previous: [DHCP: pick exactly one server](dhcp.md) · Next: [Open risks and unknowns](risks-and-unknowns.md)
