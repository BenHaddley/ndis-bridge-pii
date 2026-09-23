[← Wiki index](../README.md)

# Throughput and acceptance tests

Estimate load before choosing stream settings. For example, four 8 Mbit/s streams total **32 Mbit/s of encoded video payload** on a link carrying all four. Budget additional capacity for packet overhead, bitrate peaks, retransmissions and concurrent viewers. This is a planning example, not a measurement of the 9820.

The Pi 4's Gigabit Ethernet port and USB 2/3 sockets ([Pi 4 datasheet](../../references/pdf/raspberry-pi-4-datasheet.pdf) §2.2, p. 6) are interface ceilings only. Two things on this path are far more likely to bind:

1. **Whatever the 9820's RNDIS implementation sustains over USB**, which no datasheet in this library covers.
2. **The Harris radio data link**, which on most tactical waveforms is one to three orders of magnitude slower than the Ethernet segments either side of it. See [Transport link](../concepts/transport-link.md).

> **The 32 Mbit/s planning example above assumes a Wi-Fi-class link and is almost certainly wrong for a tactical radio data link.** Re-derive the video budget from the radio's actual usable throughput, measured under representative range and contention, before choosing any stream setting. If the link delivers, say, 2 Mbit/s usable, four simultaneous 8 Mbit/s streams is not a tuning problem — it is a different system design.

Measure with endpoints that can run `iperf3`; do not assume the 9820 can. A laptop-to-Pi test checks that partial path only. To validate the USB path, use a supported test service on the device or measure real streaming across USB.

Measure each segment separately, because a single end-to-end number will not tell you which hop is the ceiling:

| Segment | How to measure |
| --- | --- |
| Pi ↔ 9820 (USB/RNDIS) | Device test service, or real streaming across USB |
| Pi ↔ switch (Ethernet) | `iperf3` between Pi and a wired laptop |
| Across the radio link | `iperf3` between wired laptop and remote laptop, at representative range |

| Test | Proposed pass evidence |
| --- | --- |
| Enumeration | Stable NIC, correct driver, no recurring USB errors |
| Addressing | Unique addresses; expected DHCP server or fully static setup |
| Connectivity | Remote end reaches the 9820 application through the full path |
| Discovery | Actual required discovery works, if the application needs it |
| Radio link budget | Measured usable throughput at representative range meets the video budget with margin |
| Video | All intended streams work simultaneously at required resolution/bitrate |
| Soak | Suggested first bench run: 60 minutes; record loss, stalls and errors |
| Recovery | USB reconnect, radio link drop/reacquire and Pi reboot restore service |
| Persistence | Ports rejoin `br0`; no old profile steals an interface |

Agree acceptable latency, frame loss, reconnect time and test duration before calling the system production-ready. Record firmware, kernel, OS, topology and stream settings with every result.

---

Previous: [Packet tracing and troubleshooting](troubleshooting.md) · Next: [Test record template](test-record-template.md)
