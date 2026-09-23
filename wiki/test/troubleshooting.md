[← Wiki index](../README.md)

# Packet tracing and troubleshooting

Start with addressing and link state, then trace one connection from both interfaces. Run these captures in separate terminals while initiating traffic from the laptop:

```bash
sudo tcpdump -ni eth0 -e 'arp or icmp'
sudo tcpdump -ni usb0 -e 'arp or icmp'
```

For a short capture of traffic to/from the example 9820 address:

```bash
sudo timeout 30 tcpdump -ni usb0 -s 0 -w rndis-test.pcap 'host 192.168.1.10'
```

Packet captures can contain video and credentials; keep bench captures local and redact before sharing.

| Symptom | Check next | Reference document |
| --- | --- | --- |
| Nothing in `lsusb` | Data cable, power, USB host/peripheral roles, correct device port | [Pi 4 datasheet](../../references/pdf/raspberry-pi-4-datasheet.pdf) §4.1 p. 8 (5 V 3 A supply) |
| USB enumerates but no NIC | USB mode/descriptors, kernel log, available driver and device support | [MS-RNDIS](../../references/pdf/MS-RNDIS.pdf) §2.2.2 p. 12 and §2.2.9 p. 18 (the initialize handshake that must complete); [CDC-ECM](../../references/pdf/usb-cdc-ecm-120.pdf) if the descriptors say ECM, not RNDIS |
| NIC appears then disappears | Kernel USB reset messages, power supply, cable, reconnect behaviour | [Pi 4 datasheet](../../references/pdf/raspberry-pi-4-datasheet.pdf) §5.3 p. 11 (~1.1 A aggregate downstream limit); [MS-RNDIS](../../references/pdf/MS-RNDIS.pdf) §2.2.6 p. 15 (reset) and §2.2.8 p. 17 (keepalive) |
| Link never comes up, or flaps | Whether the device ever signals media connect | [MS-RNDIS](../../references/pdf/MS-RNDIS.pdf) §2.2.7 p. 16 with status values `RNDIS_STATUS_MEDIA_CONNECT` / `_DISCONNECT` in §2.2.1.2 p. 12 |
| Pi reaches 9820 but remote end cannot | Bridge membership/state, client isolation, ARP on both ports, device MAC filtering — **and whether the radio link forwards Layer 2 at all** | [Linux bridge documentation](https://docs.kernel.org/networking/bridge.html); [Transport link](../concepts/transport-link.md) |
| No address on a DHCP client | DHCP server presence, scope, competing servers, UDP 67/68 captures. A routed radio link will not relay DHCP without explicit configuration | [Transport link](../concepts/transport-link.md) |
| IP access works; discovery fails | Discovery protocol, client isolation, multicast memberships, application firewall. Broadcast/multicast discovery is the first thing a tactical radio link drops | Radio and switch documentation (not yet obtained) |
| Stream starts then stalls | Loss, bitrate bursts, USB resets, multicast membership expiry, thermal/power state, **radio link capacity and contention** | [Pi 4 datasheet](../../references/pdf/raspberry-pi-4-datasheet.pdf) §5.6 p. 11 (0–50 °C recommended ambient; CPU throttles to stay under 85 °C) |
| Works until reboot | Profile autoconnect, competing old profiles, interface name changes | [Bullseye-to-Bookworm whitepaper](../../references/pdf/transitioning-bullseye-to-bookworm.pdf) if the Pi was upgraded in place and still has `dhcpcd` remnants |
| Ping fails but application works | Endpoint may block ICMP; validate the actual application protocol | — |

Additional observations:

```bash
bridge fdb show br br0
bridge mdb show dev br0
ip -s link show dev eth0
ip -s link show dev usb0
sudo nft list ruleset
```

## Multicast and discovery

The Linux bridge enables multicast snooping by default and tracks group membership. Check `bridge mdb show` while clients are active. A network using snooping needs appropriate membership refresh/query behaviour; do not assume the upstream switch or radio supplies a querier. For a controlled diagnostic comparison, record the current setting with `ip -d link show br0`, temporarily run `sudo ip link set dev br0 type bridge mcast_snooping 0`, and restore the recorded value afterward. This is a runtime test and can increase multicast flooding. See [Linux bridge multicast documentation](https://docs.kernel.org/networking/bridge.html).

A successful comparison points toward multicast handling, not proof of a permanent fix. Check the switch and the radio link as well as the Pi. Routing needs separate treatment for multicast media and each discovery protocol; no single IGMP setting forwards all broadcast or service discovery traffic.

## Isolating which hop broke

With a switch and a radio link in the path, test hop by hop rather than end to end:

1. Pi ↔ 9820 across `usb0` only.
2. Pi ↔ a laptop plugged directly into the switch (same VLAN, no radio).
3. Pi ↔ a laptop across the radio link.

Step 2 passing and step 3 failing points at the radio link, not the bridge. See [Transport link](../concepts/transport-link.md).

---

Previous: [Testing without a Pi](vm-testing.md) · Next: [Throughput and acceptance tests](throughput-and-acceptance.md)
