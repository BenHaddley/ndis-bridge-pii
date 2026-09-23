# RNDIS Bridge on Raspberry Pi

_Last updated: Sep 23, 2026_


## Contents

- [Overview](#overview)
- [What RNDIS actually is](#what-rndis-actually-is)
- [Full architecture](#full-architecture)
- [Bridge vs. route](#bridge-vs-route)
- [Hardware test plan](#hardware-test-plan)
- [DHCP: pick exactly one server](#dhcp-pick-exactly-one-server)
- [Testing without a Pi: an ARM64 VM](#testing-without-a-pi-an-arm64-vm)
- [Open risks and unknowns](#open-risks-and-unknowns)
- [Next steps checklist](#next-steps-checklist)
- [Device facts to collect](#device-facts-to-collect-before-configuration)
- [Bench preparation](#bench-preparation-and-evidence-collection)
- [Persistent NetworkManager bridge](#persistent-networkmanager-bridge)
- [Packet tracing and troubleshooting](#packet-tracing-and-troubleshooting)
- [Routing fallback design](#routing-fallback-design)
- [Throughput and acceptance tests](#throughput-and-acceptance-tests)
- [Reference library and PDF resources](#reference-library-and-pdf-resources)
- [Test record template](#test-record-template)

## Overview

The goal is to connect the 9820’s USB network interface to a camera LAN through a Raspberry Pi and an Ethernet-connected Wi-Fi access point. This provides network connectivity in both directions; it does not itself export or re-stream video received by the 9820. Viewing that video on another device requires a camera stream or a documented streaming service on the 9820.

The working assumption is that the 9820 exposes a network connection over **USB, using RNDIS** (a USB-to-Ethernet protocol). A Raspberry Pi sits in the middle and does the translation: it takes the RNDIS "virtual Ethernet" coming in over USB and connects it to a real Ethernet port, which then feeds a Wi-Fi access point.

Target data path:

```
Camera 1 ─┐
Camera 2 ─┼──► Wi-Fi AP ──Ethernet──► [eth0  Raspberry Pi  usb0] ──USB/RNDIS──► 9820
Camera N ─┘
```

The Pi does no video processing — it is purely a network bridge/router joining two interfaces (`usb0` from the 9820, `eth0` to the AP) so traffic flows transparently between them.

**Verdict: the Linux architecture is feasible; this particular device is not yet validated.** Linux has a mature host-side RNDIS driver, and bridging or routing between interfaces is a well-worn technique — the Raspberry Pi is a reasonable box to run it on. The main unknown is whether the 9820's specific RNDIS implementation behaves like a clean, standard Ethernet NIC once plugged in — that has to be confirmed on real hardware.

## What RNDIS actually is

**RNDIS (Remote NDIS)** is a Microsoft-originated protocol that lets a USB connection carry Ethernet frames. Instead of the 9820 presenting itself as USB storage or a serial device, it presents itself as a **network adapter over USB**.

Linux provides the host-side `rndis_host` driver, with USB networking helpers including `usbnet` and `cdc_ether`. Availability depends on the installed kernel configuration and device matching. A supported device can appear as `usb0` or `enx001122334455`; record the actual name rather than assuming it. See the [upstream driver source](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c).

Once that interface exists, it behaves like any other Linux network interface (`eth0`, `wlan0`, etc.) for the purposes of bridging, routing, `iptables`, DHCP, and so on. That's what makes the whole idea work: nothing about the rest of the setup needs to know or care that the 9820's "cable" is actually USB underneath.

**Caveat:** "should" is doing some work in that sentence. RNDIS is a spec, but implementations vary, and some devices have quirks (odd MTU behaviour, flaky link-state reporting, etc.). This is the first thing to verify on real hardware — see [Hardware test plan](#hardware-test-plan).

## Full architecture

```
   Wi-Fi
              ┌───────────────┐
Camera 1 ────►│               │
              │  Wi-Fi Access │
Camera 2 ────►│     Point     │
              │               │
              └───────┬───────┘
                      │ Ethernet
                    eth0
              ┌───────┴───────┐
              │ Raspberry Pi  │
              │    (Linux)    │
              │  eth0 ↔ usb0  │
              └───────┬───────┘
                    usb0
                      │ USB (RNDIS)
                ┌─────┴─────┐
                │   9820    │
                │ (receives │
                │  video)   │
                └───────────┘
```

The Pi has exactly two jobs:

1. **See the 9820 as a network interface** (`usb0`) via the RNDIS host driver.
2. **Join `usb0` and `eth0`** so packets flow between them, either as one flat Layer-2 network (bridge) or as two routed subnets (router). See [Bridge vs. route](#bridge-vs-route) below.

The Pi forwards network traffic without decoding video. Discovery and streaming still depend on endpoint compatibility, AP forwarding, multicast handling, and sufficient bandwidth.

## Bridge vs. route

There are two ways to join `usb0` and `eth0`.

### Option 1: Layer-2 bridge (try this first)

```
         br0
      /       \
   usb0       eth0
    |           |
  9820        Wi-Fi AP
```

Linux joins the two interfaces into `br0`, acting like a simple two-port Ethernet switch. The 9820 and every Wi-Fi client end up on the **same LAN/subnet** — e.g. everything on `192.168.1.0/24`.

Raspberry Pi OS supports this through NetworkManager, and it's the officially documented way to join interfaces into one Layer-2 network.

**Why it's the better first attempt for video systems:** things like broadcast discovery, multicast, UDP streaming, and "auto-discover devices on my subnet" all assume everyone is on the same LAN segment. A bridge preserves the shared LAN, but multicast filtering and AP client isolation still need testing.

### Option 2: Layer-3 routing

```
9820                          Wi-Fi AP
192.168.10.x                  192.168.20.x
     |                             |
    usb0    Raspberry Pi    eth0
     \____ (IP forwarding) ______/
```

The 9820 and the Wi-Fi clients sit on **two separate subnets**, and the Pi forwards packets between them (`net.ipv4.ip_forward=1`, plus `iptables`/`nftables` rules as needed).

This is often easier to reason about and troubleshoot — you can firewall between the two sides, see traffic clearly per-interface, etc. — but if the video system leans on multicast or broadcast discovery, that traffic doesn't cross a router boundary by default, and you'd need protocol-specific configuration (multicast routing for multicast streams, and suitable discovery relays where available) to make it work.

### Recommendation

Start with the bridge. It's the simplest way to make the 9820 and the Wi-Fi clients "just see each other," which is almost certainly what a video/discovery system expects. Fall back to routing only if there's a specific reason (isolation, address-plan constraints) to keep the two sides separate.

## Hardware test plan

Use a Pi 4 or Pi 5. Steps, in order:

**1. Confirm Linux sees the 9820 as a NIC**

Plug the 9820 into a Pi USB host port, then check:

```bash
lsusb
ip link
dmesg | tail -50
```

Look for a new interface — `usb0`, or a MAC-derived name like `enx001234567890` — alongside the usual `lo`, `eth0`, `wlan0`. If that interface shows up, the biggest unknown (does Linux treat the 9820 as a normal network adapter over USB) is answered.

**2. Bring up the bridge**

Use the persistent [NetworkManager bridge procedure](#persistent-networkmanager-bridge) below. Do not mix temporary `ip link` configuration with active NetworkManager profiles on the same interfaces.

**3. Connect the Wi-Fi AP**

Wire the AP to the Pi's `eth0`. Set the AP to operate in **AP/bridge mode**, not as its own NAT router — keeping it a dumb Layer-2 device is what keeps the topology simple and avoids double-NAT surprises.

**4. Ping test**

Connect a laptop to the Wi-Fi AP and try to ping the 9820 (and vice versa). If that works, the core mechanism is proven.

**5. Real traffic**

Only once step 4 works, try an actual video feed / whatever protocol the real system uses end-to-end.

## DHCP: pick exactly one server

On this isolated bridge, use one DHCP server, or none for an all-static test. Check whether the 9820 has an embedded DHCP server; its capability is unknown. The Pi only serves DHCP if configured to do so, and AP behaviour depends on its model. Multiple DHCP servers on the same broadcast domain cause random address conflicts and clients silently picking the wrong gateway/DNS.

A workable static plan for a small setup:

| Device | Address |
| --- | --- |
| 9820 | `192.168.1.10` |
| Pi (`br0`) | `192.168.1.20` |
| Camera 1 | `192.168.1.101` |
| Camera 2 | `192.168.1.102` |

Everything on one flat `/24`, one designated DHCP server (or all-static, as above, if the device count is small and fixed).

## Testing without a Pi: an ARM64 VM

You can test most of the Linux networking side on an ordinary x86/AMD64 PC first, using QEMU to emulate an ARM64 CPU. This is a good way to de-risk the software side before hardware is in hand.

```
Physical PC
   |
   +-- ARM64 VM (QEMU TCG on an x86 host)
        +-- NIC 1 = simulated Ethernet/LAN
        +-- NIC 2 = second simulated network
        +-- USB passthrough = 9820 RNDIS device
```

**OS choice:** use **Ubuntu Server ARM64** or **Debian ARM64**, not Raspberry Pi OS — Raspberry Pi OS expects Pi-specific hardware (firmware, bootloader, SoC drivers) that a generic ARM VM doesn't provide. The features being tested (RNDIS host driver, bridging, `usb0`/`eth0`, `ip link`) are all standard Linux, not Pi-specific, so a generic ARM64 distro is the right fit.

**The key trick is USB passthrough.** If the hypervisor can pass the real 9820 USB device into the VM, you can test whether ARM Linux recognizes it as an RNDIS network interface (`usb0` / `enx...`) before ever touching a Raspberry Pi. Inside the VM, the same commands apply: `lsusb`, `ip link`, `ip addr` — and the same bridge (`br0` joining `usb0` and `eth0`) can be built and tested exactly as it would be on the Pi.

**Choose the simplest useful VM:** on an x86 host, an x86 Linux VM with KVM and USB passthrough is sufficient for initial driver and bridge tests. ARM64 on x86 requires QEMU software emulation (TCG), not KVM acceleration. Use QEMU’s generic `virt` machine and a compatible ARM64 guest image if testing that architecture matters. An ARM host can use KVM for a compatible ARM guest. See [QEMU ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) and [USB passthrough](https://www.qemu.org/docs/master/system/devices/usb.html).

USB passthrough gives the guest ownership of the device: the host cannot simultaneously use its RNDIS interface. A virtual NIC attached to QEMU user-mode NAT is not a transparent connection to the physical camera LAN; use a suitable host bridge/TAP arrangement or pass through a dedicated Ethernet adapter when testing the full Layer-2 path.

**Caveat:** a VM is not a Pi. It emulates a generic ARM computer, not the Pi's specific USB controller, Ethernet controller, or firmware. A pass here proves "Linux-in-general can do this"; it doesn't guarantee the Pi's specific hardware will behave identically — but it's a solid, fast way to validate the software plan before committing to real hardware.

## Open risks and unknowns

- **9820's RNDIS behaviour is unproven.** RNDIS is a spec, and implementations can have device-specific quirks (link-state reporting, MTU, throughput ceilings). Nothing here substitutes for plugging the real device into real Linux and watching what `dmesg` says.
- **AP mode matters.** If the Wi-Fi AP insists on acting as its own NAT router rather than a plain bridge/AP, it introduces a second layer of address translation that fights with the Pi's bridge. Check the AP has a genuine "bridge" or "AP" mode, not just "router" mode.
- **Multiple DHCP servers.** Covered above, but worth repeating as a risk: any combination of the 9820, AP, and Pi serving DHCP is a common source of hard-to-diagnose bugs if more than one is left enabled.
- **Multicast/broadcast dependence, if routing is chosen instead of bridging.** If the video/discovery protocol relies on multicast or broadcast (very common for camera discovery protocols), Option 2 (routing) needs protocol-specific relaying or multicast routing; an IGMP proxy does not relay arbitrary broadcast discovery that Option 1 (bridging) avoids by construction.
- **VM results don't fully transfer to the Pi.** A working ARM64 VM test proves the Linux networking approach is sound, not that the Pi's specific USB/Ethernet silicon will behave identically.

## Next steps checklist

- [ ] Plug the 9820 into a Linux box (Pi or ARM64 VM) and confirm `usb0`/`enx...` appears in `ip link`
- [ ] Build `br0` joining `usb0` and `eth0`
- [ ] Set the Wi-Fi AP to AP/bridge mode, connect it to `eth0`
- [ ] Disable DHCP everywhere except one designated server (or go fully static)
- [ ] Ping test: laptop on Wi-Fi ↔ 9820
- [ ] Once ping works, test a real video feed end-to-end
- [ ] If bridging has problems, fall back to routing (Option 2) and re-test


## Device facts to collect before configuration

“9820” alone does not identify a manufacturer or protocol. No vendor manual has been matched to this device. Treat the following as a bench worksheet, not confirmed specifications.

| Item | Record or verify |
| --- | --- |
| Identity | Manufacturer, full model number, firmware, manual revision |
| USB role | 9820 is the USB peripheral; Pi is the USB host |
| USB identity | Vendor/product IDs from `lsusb`; descriptors; driver binding |
| Network | Actual interface name, MAC, address/mask, MTU, link speed |
| Address assignment | Fixed address, DHCP client, or embedded DHCP server |
| Ethernet behaviour | Can it exchange traffic with multiple remote MAC addresses? |
| Video | Receives, serves, or both? Protocol, port, codec, authentication, client limit |
| Discovery | Manual IP, broadcast, multicast, or vendor-specific mechanism |
| AP | Model, firmware, bridge mode, client isolation, multicast options |

A working RNDIS interface is only the first checkpoint. Test laptop-to-9820 traffic **through** the bridge: successful Pi-to-9820 traffic alone does not prove transparent forwarding works.

## Bench preparation and evidence collection

Use a Pi with Ethernet and a USB host port, a suitable power supply, a data-capable USB cable, an AP with a LAN port, and a laptop. A Pi 4 has Gigabit Ethernet and USB 2/3 ports; these interface ratings do not guarantee device throughput. See the [official Pi 4 specifications](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/).

On Raspberry Pi OS, install diagnostic utilities if needed:

```bash
sudo apt update
sudo apt install usbutils iproute2 ethtool tcpdump iperf3
```

Record the starting state before changing networking:

```bash
cat /etc/os-release
uname -a
nmcli --version
nmcli device status
nmcli -f NAME,UUID,TYPE,DEVICE connection show
ip -br address
ip route
lsusb
lsusb -t
sudo journalctl -k -b --no-pager | tail -100
```

Replace `usb0` and `eth0` throughout this wiki with the real interface names. Inspect the USB NIC:

```bash
sudo ethtool -i usb0
ip -s link show dev usb0
sudo journalctl -k -f
```

Stop the live log with Ctrl-C. If no interface appears, inspect the USB descriptors and kernel messages before assuming the device uses RNDIS. `sudo modprobe rndis_host` can load an available module; it cannot make an unsupported USB interface compatible. The Pi is the **host** here, so USB gadget instructions for making the Pi impersonate a network device address a different setup. [Linux RNDIS implementation](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c), [Microsoft RNDIS introduction](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2).

## Persistent NetworkManager bridge

This is an **IPv4, isolated bench example**, adapted from the [NetworkManager bridge examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html). It assumes the 9820 accepts `192.168.1.10/24`, the Pi can use `192.168.1.20/24`, and neither address conflicts with an existing network. If the 9820 has a fixed subnet, adapt the entire plan to it first.

Run the cutover at a local console: moving the Ethernet interface into a bridge can interrupt SSH. Record the existing profile names/UUIDs and autoconnect settings for recovery. Raspberry Pi OS uses NetworkManager by default from Bookworm onward; verify that it manages your interfaces. See [Raspberry Pi configuration](https://www.raspberrypi.com/documentation/computers/configuration.html).

### Create the profiles

Check that these profile names and `br0` do not already exist. Run once:

```bash
sudo nmcli connection add type bridge ifname br0 con-name rndis-br0 \
  ipv4.method manual ipv4.addresses 192.168.1.20/24 \
  ipv4.never-default yes ipv6.method disabled
sudo nmcli connection add type ethernet ifname eth0 \
  con-name rndis-lan-port master br0
sudo nmcli connection add type ethernet ifname usb0 \
  con-name rndis-usb-port master br0
sudo nmcli connection modify rndis-br0 bridge.stp yes
```

`master` is the compatibility alias for newer `controller` terminology. The Pi’s management address belongs on `br0`; its member ports should not retain independent IP configuration. No gateway or DNS is needed for same-subnet bench traffic. Disabling IPv6 on this profile does not filter IPv6 frames passing through the bridge. Settings are documented in [NetworkManager’s property reference](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

### Activate and check

For each existing standalone profile bound to these ports, first record its UUID and original autoconnect setting. At the local console, replace the placeholder below and repeat only for the relevant profiles:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect no
sudo nmcli connection down uuid <OLD_PROFILE_UUID>
```

Then activate the bridge and ports:

```bash
sudo nmcli connection up rndis-br0
sudo nmcli connection up rndis-lan-port
sudo nmcli connection up rndis-usb-port
nmcli device status
ip -br address
bridge link show
```

Allow STP convergence before testing. Verify that both ports belong to `br0` and eventually enter forwarding state. Connect the AP’s designated LAN/uplink port according to its bridge-mode manual. For the all-static example, disable DHCP on the test LAN and assign the laptop `192.168.1.30/24` and cameras `.101/24`, `.102/24`. No default gateway is needed for these local tests.

If using DHCP instead, select one server, exclude static addresses from its pool, and configure clients accordingly. Do not select NetworkManager `ipv4.method shared` for this transparent bridge example; it introduces connection-sharing behaviour.

### Recovery

From the local console, remove only the profiles created by this procedure:

```bash
sudo nmcli connection down rndis-br0
sudo nmcli connection delete rndis-lan-port rndis-usb-port rndis-br0
```

Restore each old profile’s recorded autoconnect value, then reactivate the profiles that were previously active:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect yes
sudo nmcli connection up uuid <OLD_PROFILE_UUID>
```

Use `no` instead of `yes` if that was the recorded value. Reboot is not a rollback for persistent NetworkManager configuration.

## Packet tracing and troubleshooting

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

| Symptom | Check next |
| --- | --- |
| Nothing in `lsusb` | Data cable, power, USB host/peripheral roles, correct device port |
| USB enumerates but no NIC | USB mode/descriptors, kernel log, available driver and device support |
| NIC appears then disappears | Kernel USB reset messages, power supply, cable, reconnect behaviour |
| Pi reaches 9820 but laptop cannot | Bridge membership/state, AP isolation, ARP on both ports, device MAC filtering |
| No address on a DHCP client | DHCP server presence, scope, competing servers, UDP 67/68 captures |
| IP access works; discovery fails | Discovery protocol, AP filtering, multicast memberships, application firewall |
| Stream starts then stalls | Loss, bitrate bursts, USB resets, multicast membership expiry, thermal/power state |
| Works until reboot | Profile autoconnect, competing old profiles, interface name changes |
| Ping fails but application works | Endpoint may block ICMP; validate the actual application protocol |

Additional observations:

```bash
bridge fdb show br br0
bridge mdb show dev br0
ip -s link show dev eth0
ip -s link show dev usb0
sudo nft list ruleset
```

### Multicast and discovery

The Linux bridge enables multicast snooping by default and tracks group membership. Check `bridge mdb show` while clients are active. A network using snooping needs appropriate membership refresh/query behaviour; do not assume an isolated AP supplies a querier. For a controlled diagnostic comparison, record the current setting with `ip -d link show br0`, temporarily run `sudo ip link set dev br0 type bridge mcast_snooping 0`, and restore the recorded value afterward. This is a runtime test and can increase multicast flooding. See [Linux bridge multicast documentation](https://docs.kernel.org/networking/bridge.html).

A successful comparison points toward multicast handling, not proof of a permanent fix. Check the AP as well as the Pi. Routing needs separate treatment for multicast media and each discovery protocol; no single IGMP setting forwards all broadcast or service discovery traffic.

## Routing fallback design

Use routing when the USB device cannot support transparent bridging or when separate subnets are required. First confirm the 9820 can use a gateway or suitable static routes.

| Segment | Example addressing | Required return path |
| --- | --- | --- |
| USB | Pi `192.168.10.1/24`, 9820 `192.168.10.2/24` | 9820 route to `192.168.20.0/24` through `.10.1` |
| Camera LAN | Pi `192.168.20.1/24`, cameras `.20.101/24` onward | Camera/laptop route to `192.168.10.0/24` through `.20.1` |

These are alternative addresses, not additions to the bridge configuration. Remove bridge membership before configuring independent routed interfaces. Enable IPv4 forwarding and add narrowly scoped forwarding rules in the existing firewall, including reply traffic. Do not flush an existing ruleset. The final rules depend on traffic direction and application ports, which remain unknown.

NAT may help when an endpoint cannot install a return route, but changes peer addresses and can complicate incoming connections and discovery. It is a separate design choice, not a requirement for routing. Routing is not yet a copy-and-run deployment recipe in this wiki.

## Throughput and acceptance tests

Estimate load before choosing stream settings. For example, four 8 Mbit/s streams total **32 Mbit/s of encoded video payload** on a link carrying all four. Budget additional capacity for packet overhead, bitrate peaks, retransmissions and concurrent viewers. This is a planning example, not a measurement of the 9820.

Measure with endpoints that can run `iperf3`; do not assume the 9820 can. A laptop-to-Pi test checks that partial path only. To validate the USB path, use a supported test service on the device or measure real streaming across USB.

| Test | Proposed pass evidence |
| --- | --- |
| Enumeration | Stable NIC, correct driver, no recurring USB errors |
| Addressing | Unique addresses; expected DHCP server or fully static setup |
| Connectivity | Laptop reaches the 9820 application through both bridge ports |
| Discovery | Actual required discovery works, if the application needs it |
| Video | All intended streams work simultaneously at required resolution/bitrate |
| Soak | Suggested first bench run: 60 minutes; record loss, stalls and errors |
| Recovery | USB reconnect, AP restart and Pi reboot restore service |
| Persistence | Ports rejoin `br0`; no old profile steals an interface |

Agree acceptable latency, frame loss, reconnect time and test duration before calling the system production-ready. Record firmware, kernel, OS, topology and stream settings with every result.

## Reference library and PDF resources

Sources below were consulted on **23 September 2026**. They establish general platform behaviour, not compatibility with the unidentified 9820. Upstream `latest` and `master` pages change; record the deployed versions when reproducing results.

### Official web references and source code

| Resource | What to pull from it |
| --- | --- |
| [Microsoft: Introduction to RNDIS](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2) | Protocol purpose and host/device concepts |
| [Linux: rndis_host.c](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c) | Driver matching, implementation, quirks; compare with the installed kernel |
| [Linux: Ethernet bridging](https://docs.kernel.org/networking/bridge.html) | Forwarding, STP, multicast snooping and bridge attributes |
| [NetworkManager: nmcli examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html) | Bridge/port profiles and recovery checkpoints |
| [NetworkManager: connection properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html) | IP methods, controller/port settings, autoconnect behaviour |
| [Raspberry Pi: configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) | OS networking and NetworkManager setup |
| [Raspberry Pi: hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) | Board ports, power and hardware constraints |
| [QEMU: ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) | ARM machine selection and acceleration constraints |
| [QEMU: USB emulation/passthrough](https://www.qemu.org/docs/master/system/devices/usb.html) | Passing a real USB device to a guest |

### Downloadable PDFs

| PDF | Useful material | Status and limitation |
| --- | --- | --- |
| [Raspberry Pi 4 Model B product brief](https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS/raspberry-pi-4-product-brief) | USB/Ethernet interfaces, power, dimensions | Opened as a 7-page PDF, April 2026 edition; hardware reference, not an RNDIS guarantee |
| [Raspberry Pi: Transitioning from Bullseye to Bookworm](https://pip.raspberrypi.com/categories/685-whitepapers-app-notes-compliance-guides/documents/RP-006519-WP/Transitioning-from-Bullseye-to-Bookworm.pdf) | Historical NetworkManager migration context | Official PDF indexed in search; full document could not be fetched by the research tool; use current configuration docs for deployment |
| [Microsoft: MS-RNDIS specification](https://download.microsoft.com/download/5/0/1/501ED102-E53F-4CE0-AA6B-B0F93629DDC6/Windows/%5BMS-RNDIS%5D.pdf) | Message structures and protocol terminology | Archived official PDF indexed in search; research tool rejected its binary content type; not verified as the newest revision |

The PDF links are external resources; copies are not bundled with this wiki. To pull a reviewed PDF locally, use this example from the project directory:

```bash
mkdir -p references/pdf
curl --fail --location --output references/pdf/raspberry-pi-4-product-brief.pdf \
  'https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS/raspberry-pi-4-product-brief'
file references/pdf/raspberry-pi-4-product-brief.pdf
sha256sum references/pdf/raspberry-pi-4-product-brief.pdf
```

Confirm the download is a PDF before relying on it. For each saved source, record the publisher, title, revision/date, URL, retrieval date, checksum and relevant pages. Keep original documents separate from your notes and check publisher terms before redistributing copies.

### Vendor documents still needed

- **9820 user/service manual:** full manufacturer and model must be identified first; collect USB modes, IP defaults, stream access and firmware notes.
- **Camera manuals:** supported stream/discovery protocols, bitrate controls and simultaneous-client limits.
- **AP manual:** actual bridge-mode wiring, DHCP controls, client isolation and multicast settings.

Add exact document titles, revisions and page references here when identified. Do not substitute a manual for an unrelated product sharing the number “9820”.

## Test record template

```text
Date / operator:
9820 manufacturer / full model / firmware:
Pi model / OS / kernel / NetworkManager version:
AP model / firmware / mode:
USB VID:PID / driver / interface / negotiated speed:
Address plan / DHCP owner:
Camera models / stream protocol / bitrate / number of viewers:
Bridge or routing configuration:
Tests performed / duration:
Observed throughput / loss / stalls / recovery time:
Logs or capture filenames:
Source documents / revision / relevant pages:
Result / remaining issue / next action:
```
