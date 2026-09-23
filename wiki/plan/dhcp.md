[← Wiki index](../README.md)

# DHCP: pick exactly one server

On this isolated bridge, use one DHCP server, or none for an all-static test. Check whether the 9820 has an embedded DHCP server; its capability is unknown. The Pi only serves DHCP if configured to do so. The router and the Harris radio may each be capable of serving DHCP as well — check both. Multiple DHCP servers on the same broadcast domain cause random address conflicts and clients silently picking the wrong gateway/DNS.

**All-static is the stronger default here.** If the [radio link routes rather than bridges](../concepts/transport-link.md), DHCP will not cross it without explicit relay configuration, so relying on a single server at one end stops working the moment the far end is involved. Static addressing sidesteps that entirely for a small, fixed device count.

A workable static plan for a small setup:

| Device | Address |
| --- | --- |
| 9820 | `192.168.1.10` |
| Pi (`br0`) | `192.168.1.20` |
| Camera 1 | `192.168.1.101` |
| Camera 2 | `192.168.1.102` |

Everything on one flat `/24`, one designated DHCP server (or all-static, as above, if the device count is small and fixed).

---

Previous: [Hardware test plan](hardware-test-plan.md) · Next: [Device facts to collect](device-facts.md)
