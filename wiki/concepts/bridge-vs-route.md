[← Wiki index](../README.md)

# Bridge vs. route

There are two ways to join `usb0` and `eth0`.

> **This choice is no longer the Pi's alone to make.** With a [Harris radio data link](transport-link.md) as the wireless transport instead of a Wi-Fi AP, the radio may itself present a routed Layer-3 interface. If it does, a Layer-2 bridge on the Pi is still correct locally but cannot extend across the radio, and Option 2 becomes the primary design rather than the fallback. Settle the radio's link mode before following the recommendation at the bottom of this page.

## Option 1: Layer-2 bridge (try this first)

```
         br0
      /       \
   usb0       eth0
    |           |
  9820      switch → radio link
```

Linux joins the two interfaces into `br0`, acting like a simple two-port Ethernet switch. The 9820 and every client on the camera segment end up on the **same LAN/subnet** — e.g. everything on `192.168.1.0/24` — provided the radio link carries Layer 2.

Raspberry Pi OS supports this through NetworkManager, and it's the officially documented way to join interfaces into one Layer-2 network. The procedure is in [Persistent NetworkManager bridge](../build/networkmanager-bridge.md).

**Why it's the better first attempt for video systems:** things like broadcast discovery, multicast, UDP streaming, and "auto-discover devices on my subnet" all assume everyone is on the same LAN segment. A bridge preserves the shared LAN, but multicast filtering on the switch, IGMP querier presence, and the radio link's own Layer-2 behaviour all still need testing.

## Option 2: Layer-3 routing

```
9820                       switch / radio link
192.168.10.x                  192.168.20.x
     |                             |
    usb0    Raspberry Pi    eth0
     \____ (IP forwarding) ______/
```

The 9820 and the camera-side clients sit on **two separate subnets**, and the Pi forwards packets between them (`net.ipv4.ip_forward=1`, plus `iptables`/`nftables` rules as needed). Addressing details are in [Routing fallback design](../build/routing-fallback.md).

This is often easier to reason about and troubleshoot — you can firewall between the two sides, see traffic clearly per-interface, etc. — but if the video system leans on multicast or broadcast discovery, that traffic doesn't cross a router boundary by default, and you'd need protocol-specific configuration (multicast routing for multicast streams, and suitable discovery relays where available) to make it work.

## Recommendation

**If the radio link bridges Layer 2:** start with the bridge. It's the simplest way to make the 9820 and the camera-side clients "just see each other," which is almost certainly what a video/discovery system expects.

**If the radio link routes Layer 3:** build the bridge on the Pi anyway — it is still the right way to join `usb0` and `eth0` locally, and it keeps the 9820 on the local segment — but plan for routing across the radio, and treat every discovery protocol as something that needs explicit configuration rather than something that will just work.

Either way, do not discover which case you are in by debugging a failed video test. Establish it from the radio's documentation first — see [Transport link](transport-link.md).

---

Previous: [Full architecture](architecture.md) · Next: [Transport link](transport-link.md)
