[← Wiki index](../README.md)

# Testing without a Pi: an ARM64 VM

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

**Choose the simplest useful VM:** on an x86 host, an x86 Linux VM with KVM and USB passthrough is sufficient for initial driver and bridge tests. ARM64 on x86 requires QEMU software emulation (TCG), not KVM acceleration. Use QEMU's generic `virt` machine and a compatible ARM64 guest image if testing that architecture matters. An ARM host can use KVM for a compatible ARM guest. See [QEMU ARM system emulation](https://www.qemu.org/docs/master/system/target-arm.html) and [USB passthrough](https://www.qemu.org/docs/master/system/devices/usb.html).

USB passthrough gives the guest ownership of the device: the host cannot simultaneously use its RNDIS interface. A virtual NIC attached to QEMU user-mode NAT is not a transparent connection to the physical camera LAN; use a suitable host bridge/TAP arrangement or pass through a dedicated Ethernet adapter when testing the full Layer-2 path.

**Caveat:** a VM is not a Pi. It emulates a generic ARM computer, not the Pi's specific USB controller, Ethernet controller, or firmware. A pass here proves "Linux-in-general can do this"; it doesn't guarantee the Pi's specific hardware will behave identically — but it's a solid, fast way to validate the software plan before committing to real hardware.

---

Previous: [Routing fallback design](../build/routing-fallback.md) · Next: [Packet tracing and troubleshooting](troubleshooting.md)
