[← Wiki index](../README.md)

# Hardware test plan

Use a Pi 4 or Pi 5 — board details in [`references/pdf/raspberry-pi-4-datasheet.pdf`](../../references/pdf/raspberry-pi-4-datasheet.pdf) and [`references/pdf/raspberry-pi-5-product-brief.pdf`](../../references/pdf/raspberry-pi-5-product-brief.pdf). Steps, in order:

**1. Confirm Linux sees the 9820 as a NIC**

Plug the 9820 into a Pi USB host port, then check:

```bash
lsusb
ip link
dmesg | tail -50
```

Look for a new interface — `usb0`, or a MAC-derived name like `enx001234567890` — alongside the usual `lo`, `eth0`, `wlan0`. If that interface shows up, the biggest unknown (does Linux treat the 9820 as a normal network adapter over USB) is answered.

**2. Bring up the bridge**

Use the persistent [NetworkManager bridge procedure](../build/networkmanager-bridge.md). Do not mix temporary `ip link` configuration with active NetworkManager profiles on the same interfaces.

**3. Connect the switch**

Wire the Pi's `eth0` to the switch. Keep the camera segment on one VLAN with IGMP snooping and a querier configured, and no port isolation on the Pi's port — see [Switch and router selection](../build/switch-and-router.md). Do not put a router in-path between the switch and the Pi unless you have deliberately chosen the [routing design](../build/routing-fallback.md).

**4. Ping test, wired only**

Plug a laptop into the same VLAN on the switch and ping the 9820 (and vice versa). Keep the radio link out of the path for this step. If that works, the core mechanism — RNDIS NIC plus Layer-2 bridge — is proven.

**5. Add the radio link**

Only now bring the [Harris radio data link](../concepts/transport-link.md) into the path and repeat the ping test from the far end. If step 4 passed and step 5 fails, the radio is the problem, not the bridge — which is exactly why these are separate steps.

**6. Real traffic**

Only once step 5 works, try an actual video feed / whatever protocol the real system uses end-to-end. Measure the radio link's usable throughput before assuming the intended stream count fits — see [Throughput and acceptance tests](../test/throughput-and-acceptance.md).

---

See also: [Bench preparation](../build/bench-preparation.md) for what to have on the bench first, and [Packet tracing and troubleshooting](../test/troubleshooting.md) when a step fails.

Next: [DHCP: pick exactly one server](dhcp.md)
