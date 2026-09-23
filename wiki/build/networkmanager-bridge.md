[← Wiki index](../README.md)

# Persistent NetworkManager bridge

This is an **IPv4, isolated bench example**, adapted from the [NetworkManager bridge examples](https://networkmanager.dev/docs/api/latest/nmcli-examples.html). It assumes the 9820 accepts `192.168.1.10/24`, the Pi can use `192.168.1.20/24`, and neither address conflicts with an existing network. If the 9820 has a fixed subnet, adapt the entire plan to it first.

Run the cutover at a local console: moving the Ethernet interface into a bridge can interrupt SSH. Record the existing profile names/UUIDs and autoconnect settings for recovery. Raspberry Pi OS uses NetworkManager by default from Bookworm onward; verify that on your own system with `nmcli device status` rather than trusting the version number, because a Pi upgraded in place from Bullseye may still be running `dhcpcd`. Background on that transition is in the local copy of Raspberry Pi's migration whitepaper, [`references/pdf/transitioning-bullseye-to-bookworm.pdf`](../../references/pdf/transitioning-bullseye-to-bookworm.pdf) (19 pages, 15 August 2024) — its text could not be machine-extracted for section-level citation here, so read it directly rather than quoting it second-hand. For deployment, prefer the current [Raspberry Pi configuration](https://www.raspberrypi.com/documentation/computers/configuration.html) documentation over the 2024 whitepaper.

If `nmcli device status` shows the interfaces as unmanaged, or `dhcpcd` is still driving them, resolve that before creating any bridge profile: the procedure below assumes NetworkManager owns both ports.

## Create the profiles

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

`master` is the compatibility alias for newer `controller` terminology. The Pi's management address belongs on `br0`; its member ports should not retain independent IP configuration. No gateway or DNS is needed for same-subnet bench traffic. Disabling IPv6 on this profile does not filter IPv6 frames passing through the bridge. Settings are documented in [NetworkManager's property reference](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

## Activate and check

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

Allow STP convergence before testing. Verify that both ports belong to `br0` and eventually enter forwarding state. Connect `eth0` to an access port on the camera VLAN of the [switch](switch-and-router.md). For the all-static example, disable DHCP on the test LAN and assign the laptop `192.168.1.30/24` and cameras `.101/24`, `.102/24`. No default gateway is needed for these local tests.

If using DHCP instead, select one server, exclude static addresses from its pool, and configure clients accordingly — see [DHCP: pick exactly one server](../plan/dhcp.md). Do not select NetworkManager `ipv4.method shared` for this transparent bridge example; it introduces connection-sharing behaviour.

## Recovery

From the local console, remove only the profiles created by this procedure:

```bash
sudo nmcli connection down rndis-br0
sudo nmcli connection delete rndis-lan-port rndis-usb-port rndis-br0
```

Restore each old profile's recorded autoconnect value, then reactivate the profiles that were previously active:

```bash
sudo nmcli connection modify uuid <OLD_PROFILE_UUID> connection.autoconnect yes
sudo nmcli connection up uuid <OLD_PROFILE_UUID>
```

Use `no` instead of `yes` if that was the recorded value. Reboot is not a rollback for persistent NetworkManager configuration.

---

Previous: [Bench preparation](bench-preparation.md) · Next: [Routing fallback design](routing-fallback.md)
