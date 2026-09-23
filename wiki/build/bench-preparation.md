[← Wiki index](../README.md)

# Bench preparation and evidence collection

Use a Pi with Ethernet and a USB host port, a suitable power supply, a data-capable USB cable, the [switch](switch-and-router.md), and a laptop. Keep the [radio link](../concepts/transport-link.md) out of the bench path until the wired case works.

Three figures from the local [Raspberry Pi 4 Model B datasheet](../../references/pdf/raspberry-pi-4-datasheet.pdf) (Release 1.1) shape the bench setup:

| Datasheet reference | Figure | Why it matters here |
| --- | --- | --- |
| §2.2 Interfaces, p. 6 | 2× USB2 and 2× USB3 type-A sockets; 1× Gigabit Ethernet port | The two interfaces the bridge joins. These are interface ratings, not a guarantee of 9820 throughput |
| §4.1 Power Requirements, p. 8 | A good-quality USB-C supply delivering **5 V at 3 A**; a 5 V, 2.5 A supply only if downstream USB devices draw under 500 mA | The 9820 is a downstream USB device, so the 2.5 A allowance likely does not apply |
| §5.3 USB, p. 11 | Downstream USB current limited to **approximately 1.1 A in aggregate** across all four sockets | A device drawing near that ceiling is a prime suspect for resets and vanishing interfaces |

If using a Pi 5 instead, take its port and power figures from [`references/pdf/raspberry-pi-5-product-brief.pdf`](../../references/pdf/raspberry-pi-5-product-brief.pdf) rather than assuming the Pi 4 numbers carry over. The [Pi 4 product brief](../../references/pdf/raspberry-pi-4-product-brief.pdf) is a shorter summary of the same board; prefer the datasheet when the two differ in detail.

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

Stop the live log with Ctrl-C. If no interface appears, inspect the USB descriptors and kernel messages before assuming the device uses RNDIS. `sudo modprobe rndis_host` can load an available module; it cannot make an unsupported USB interface compatible. The Pi is the **host** here, so USB gadget instructions for making the Pi impersonate a network device address a different setup. [Linux RNDIS implementation](https://github.com/torvalds/linux/blob/master/drivers/net/usb/rndis_host.c), [Microsoft RNDIS introduction](https://learn.microsoft.com/en-us/windows-hardware/drivers/network/remote-ndis--rndis-2), and the specification itself at [`references/pdf/MS-RNDIS.pdf`](../../references/pdf/MS-RNDIS.pdf) — the host/device split it describes (§1.1 glossary, p. 6) is the same split as Pi/9820 here.

---

Previous: [Next steps checklist](../plan/next-steps.md) · Next: [Persistent NetworkManager bridge](networkmanager-bridge.md)
