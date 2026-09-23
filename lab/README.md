# Virtual network lab

This lab runs real Linux networking, DHCP exchanges and HTTP transfers in disposable namespaces. It requires **no Pi, radio, camera, container image or sudo** on a Linux machine that permits unprivileged user/network namespaces. It cannot validate radio USB support, Wi-Fi airtime, RF throughput, video decoding or SitaWare.

To run the same lab inside a complete Debian guest, use the [VM guide](../vm/README.md).

## Run

Required host commands: Python 3, `unshare`, `nsenter`, `ip`, `dnsmasq`, `tc`, and `curl`. The runner reports missing tools; it does not install packages. `unshare`/`nsenter` come from util-linux; `ip`/`tc` come from iproute2. Package names vary by distribution.

From the repository root:

```bash
python3 lab/network_lab.py --mode bridge --output test-results/virtual-bridge-01
python3 lab/network_lab.py --mode route --output test-results/virtual-route-01
```

Choose a **new output directory** for every run. Existing evidence is never overwritten. All tests are automatic; exit code zero means the virtual scenario passed. Inspect `result.json` even if the command fails.

Optional synthetic traffic cap:

```bash
python3 lab/network_lab.py --mode route --rate-mbps 8 --output test-results/virtual-route-8mbps-01
```

Default: 16 Mbps **per direction** on the link between the simulated radios. This is an illustrative Linux queue limit informed by Jeremy’s reported number, not an implementation of WRAITH or TSM. It does not model a shared radio channel, interference, retransmission scheduling, hops, voice priorities or RF modulation. The short payload transfer is an integrity test and diagnostic timing observation, not a throughput benchmark or a stream-capacity guarantee.

## Topology

```text
camera       AP              Pi               radio A        radio B        CP
 eth0 ── wifi0/br0/eth0 ── eth0 / usb0 ─────── usb0 / rf0 ─── rf0 / lan0 ── eth0
           L2 bridge      bridge or router       router          router
```

Every connection is a veth pair. `wifi0`, `usb0` and `rf0` are descriptive names; no Wi-Fi, USB or radio hardware is emulated. The AP has no DHCP server. Both radios are ordinary Linux routers. Their interface/subnet arrangement is a test fixture, not a statement about the real radio.

| Segment | Bridge mode | Route mode |
| --- | --- | --- |
| Camera network | `192.168.10.0/24`; radio A provides DHCP across both bridges | `192.168.20.0/24`; Pi provides local DHCP |
| Pi management / USB | Pi `br0` at `192.168.10.2`; radio A `.10.1` | Pi USB lease from radio A; Pi camera-side `.20.1` |
| Radio-to-radio | `172.31.0.0/30`, endpoints `.1` and `.2` | Same |
| CP network | `192.168.30.0/24`; radio B `.1`, CP `.10` | Same |

DHCP pools are `.100`–`.110` with one-hour leases. The lab client performs DISCOVER/OFFER/REQUEST/ACK, validates key lease options, then the runner applies the address and route. It is **not a production DHCP client**: it does not renew leases or perform conflict detection. Use NetworkManager on the real Pi. Each scenario completes well before lease expiry.

## Automatic checks

- Bridge mode: radio DHCP reaches the camera through the Pi and AP bridges.
- Route mode: radio DHCP reaches the Pi USB side but does **not** reach the camera subnet; separate Pi DHCP serves the camera.
- CP-to-camera and camera-to-CP HTTP requests succeed.
- A 1 MiB synthetic payload crosses the path and matches its SHA-256 checksum.
- Bringing the Pi USB-side link down interrupts traffic; bringing it back up and reconciling fixture routes restores traffic.
- Bringing the radio-to-radio link down interrupts traffic; restoring it and reconciling fixture routes restores traffic.
- Removing the remote route to the camera subnet breaks traffic; restoring it recovers traffic.

The runner explicitly reapplies known routes after a link comes back up because Linux can remove next-hop routes during administrative link-down. This tests that recovery procedure, not unattended NetworkManager behaviour.

Link toggles test forwarding recovery only. They do not test real USB removal/re-enumeration, interface renaming, DHCP renewal after expiry, Pi reboot or persistent NetworkManager profiles. The lab intentionally uses temporary `ip` configuration and loop-free bridges with STP disabled; it is not a production installer.

The HTTP service serves generated test data. A passing run is not a real-camera/video acceptance test. The command-post IP routes are explicitly provisioned; this does not establish the real MANET’s route-advertisement behaviour.

## Isolation and cleanup

The launcher creates new user, network, mount and PID namespaces. The worker rejects direct invocation outside its expected PID/network isolation. All veth devices, addresses, routes, forwarding controls and DHCP services live within the lab namespaces. Nothing is attached to a physical NIC or a host bridge; the lab has no external network route.

Services are terminated after each run. Exiting the private PID namespace removes remaining processes and releases their network namespaces; the namespace launcher also has a kill-child guard. The outer runner applies a 180-second limit and kills its own process group on interruption. It leaves only the requested evidence directory. No persistent `ip netns` entries or system services are created. Evidence paths remain accessible through the host filesystem; this is network isolation, not a filesystem security sandbox.

If user namespaces are disabled or the execution sandbox forbids netlink, the run fails rather than changing host settings or silently dropping tests. Run on a Linux environment where these facilities are permitted. Do not run the internal `--worker` entry point directly.

## Evidence

Each output directory contains:

- `result.json`: scenario verdict, individual checks, synthetic transfer observation and explicit `hardware_validated: false`.
- `commands.jsonl`: node configuration/probe commands.
- Per-node JSON snapshots of links, addresses, routes and queues after recovery.
- DHCP logs, lease files and client lease JSON.
- HTTP service logs, original payload and received payload.

Files are private to the invoking user by default. Failed runs retain whatever evidence was collected before failure. Runtime errors in DHCP/server startup appear in their logs. Keep generated run directories separate from the project’s real hardware acceptance record.

## Offline tests

```bash
python3 -m unittest discover -s tests -v
```

These cover DHCP packet parsing, CLI isolation guards, evidence preservation and the separate Pi diagnostic collector. They do not replace the live namespace runs.

## Sources

Isolation/lifecycle design: [util-linux unshare manual](https://man7.org/linux/man-pages/man1/unshare.1.html). DHCP server flags: [dnsmasq manual](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html). Probe protocol: [RFC 2131](https://www.rfc-editor.org/rfc/rfc2131.html) and [RFC 2132](https://www.rfc-editor.org/rfc/rfc2132.html).
