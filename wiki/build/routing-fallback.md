[← Wiki index](../README.md)

# Routing fallback design

Use routing when the USB device cannot support transparent bridging or when separate subnets are required — see [Bridge vs. route](../concepts/bridge-vs-route.md) for why this is the fallback rather than the first attempt. First confirm the 9820 can use a gateway or suitable static routes.

| Segment | Example addressing | Required return path |
| --- | --- | --- |
| USB | Pi `192.168.10.1/24`, 9820 `192.168.10.2/24` | 9820 route to `192.168.20.0/24` through `.10.1` |
| Camera LAN | Pi `192.168.20.1/24`, cameras `.20.101/24` onward | Camera/laptop route to `192.168.10.0/24` through `.20.1` |

These are alternative addresses, not additions to the bridge configuration. Remove bridge membership before configuring independent routed interfaces. Enable IPv4 forwarding and add narrowly scoped forwarding rules in the existing firewall, including reply traffic. Do not flush an existing ruleset. The final rules depend on traffic direction and application ports, which remain unknown.

NAT may help when an endpoint cannot install a return route, but changes peer addresses and can complicate incoming connections and discovery. It is a separate design choice, not a requirement for routing. Routing is not yet a copy-and-run deployment recipe in this wiki.

---

Previous: [Persistent NetworkManager bridge](networkmanager-bridge.md) · Next: [Testing without a Pi](../test/vm-testing.md)
