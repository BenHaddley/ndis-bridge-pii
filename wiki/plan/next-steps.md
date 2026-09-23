[← Wiki index](../README.md)

# Next steps checklist

**Answer these before building**

- [ ] Record the Harris radio model and waveform, and establish whether the link **bridges Layer 2 or routes Layer 3** — [Transport link](../concepts/transport-link.md)
- [ ] Measure the radio's usable throughput at representative range, and re-derive the [video budget](../test/throughput-and-acceptance.md) from it
- [ ] Confirm the 9820's actual manufacturer and model; if it is a Garmin marine unit, check for a native Ethernet port before committing to USB/RNDIS
- [ ] Decide whether a router is needed in-path at all — [Switch and router selection](../build/switch-and-router.md)

**Then build and test**

- [ ] Plug the 9820 into a Linux box (Pi or [ARM64 VM](../test/vm-testing.md)) and confirm `usb0`/`enx...` appears in `ip link`
- [ ] Build `br0` joining `usb0` and `eth0` — [procedure](../build/networkmanager-bridge.md)
- [ ] Configure the switch: camera VLAN, IGMP snooping, querier, no port isolation on the Pi's port
- [ ] Disable DHCP everywhere except one designated server (or [go fully static](dhcp.md))
- [ ] Ping test **wired only**: laptop on the switch ↔ 9820
- [ ] Ping test **across the radio link**, from the far end
- [ ] Once ping works, test a real video feed end-to-end
- [ ] If bridging cannot cross the radio link, move to [routing (Option 2)](../build/routing-fallback.md) and re-test

Record each run against the [test record template](../test/test-record-template.md).

---

Previous: [Open risks and unknowns](risks-and-unknowns.md) · Next: [Bench preparation](../build/bench-preparation.md)
