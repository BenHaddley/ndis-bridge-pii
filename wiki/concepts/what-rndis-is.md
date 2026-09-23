[← Wiki index](../README.md)

# What RNDIS actually is

**RNDIS (Remote NDIS)** is a Microsoft-originated protocol that lets a USB connection carry Ethernet frames. Instead of the 9820 presenting itself as USB storage or a serial device, it presents itself as a **network adapter over USB**.

The protocol itself is documented in the local copy of the Microsoft specification, [`references/pdf/MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf). Useful orientation from it:

- The bus transport is split into a **control channel** (control messages) and a **data channel** (network packet data) — glossary, §1.1, p. 6.
- The host opens with `REMOTE_NDIS_INITIALIZE_MSG` (§2.2.2, p. 12), which carries a `MaxTransferSize`, and the device answers with `REMOTE_NDIS_INITIALIZE_CMPLT` (§2.2.9, p. 18). A device that fails this handshake never becomes a usable NIC.
- Ethernet frames ride inside `REMOTE_NDIS_PACKET_MSG` (§2.2.14, p. 22).
- Link state is reported by the device through `REMOTE_NDIS_INDICATE_STATUS_MSG` (§2.2.7, p. 16), using `RNDIS_STATUS_MEDIA_CONNECT` (`0x4001000B`) and `RNDIS_STATUS_MEDIA_DISCONNECT` (`0x4001000C`) from the common status values table (§2.2.1.2, p. 12). This is the mechanism behind the "link flaps / carrier never comes up" class of problem in [Packet tracing and troubleshooting](../test/troubleshooting.md).

Linux provides the host-side `rndis_host` driver, with USB networking helpers including `usbnet` and `cdc_ether`. Availability depends on the installed kernel configuration and device matching. A supported device can appear as `usb0` or `enx001122334455`; record the actual name rather than assuming it. See the [upstream driver source](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c).

RNDIS is not the only way a device does Ethernet-over-USB. If the descriptors show a CDC-ECM interface instead, `cdc_ether` handles it and the governing document is the USB-IF subclass specification saved at [`references/pdf/usb-cdc-ecm-120.pdf`](../../references/pdf/usb-cdc-ecm-120.pdf) — keep both to hand until the 9820's descriptors have actually been read.

Once that interface exists, it behaves like any other Linux network interface (`eth0`, `wlan0`, etc.) for the purposes of bridging, routing, `iptables`, DHCP, and so on. That's what makes the whole idea work: nothing about the rest of the setup needs to know or care that the 9820's "cable" is actually USB underneath.

**Caveat:** "should" is doing some work in that sentence. RNDIS is a spec, but implementations vary, and some devices have quirks (odd MTU behaviour, flaky link-state reporting, etc.). The specification's own revision summary ([`MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf), pp. 3–4) runs through several "significantly changed the technical content" revisions, which is a fair hint that implementations built against different revisions differ in practice. This is the first thing to verify on real hardware — see the [Hardware test plan](../plan/hardware-test-plan.md).

---

Next: [Full architecture](architecture.md)
