# Operator guide — preparation draft

Status: **not a deployment handover**. Replace pending values from an accepted build and rehearse this procedure on the real kit before issuing it to an operator.

## Start a known-good build

1. Match the kit, SD image/configuration revision and cables to the hardware inventory and release record. Confirm approved radio settings with the radio operator.
2. Connect the documented radio host cable, Pi Ethernet to the AP's documented LAN port, and specified power supplies. Start the kit in the order proven in the release record (currently pending).
3. Verify the camera is associated with the AP and the Pi has its recorded management address. Check the radio USB NIC and selected bridge/routing profiles.
4. Open the saved CP viewer entry using the recorded credentials source. Confirm moving video and an acceptable delay. If SitaWare is included, also confirm the correct track and position freshness.

## Find the failing segment

| Symptom | First observation | Record before changes |
| --- | --- | --- |
| Radio NIC absent | USB cable/power/mode and kernel enumeration | Diagnostic bundle, radio status |
| Camera cannot reach Pi | Wi-Fi association, AP mode/isolation, address and DHCP owner | Camera/AP status and Pi addresses |
| Pi reaches radio but CP cannot reach camera | RF status and both directions' routes | Routes and endpoint application result |
| Control/login works but no video | Media transport/ports and viewer error | Stream settings and error text |
| Video freezes under load | Stream traffic, radio conditions and power/temperature | Time, duration, traffic/load conditions |
| Failure after reboot | Profile selection, USB identity and DHCP lease | New diagnostic bundle and active profile UUIDs |

Use `bash scripts/collect-diagnostics.sh NEW_DIRECTORY ACTUAL_USB_INTERFACE` on the Pi. This collector observes state and does not repair it. Save a fresh directory per event and review it before sharing.

## Recover and escalate

Follow the accepted build's tested recovery order and timing targets (pending). Avoid repeated random configuration changes. If a trial network change caused the fault, use the recorded [network rollback](network-design.md#cutover-and-recovery-procedure) at the console. A reboot is not a rollback of saved profiles.

For reimaging, identify the approved image, checksum, configuration backup and exact removable-media device before writing anything. A release image and reimage procedure have not yet been produced; do not treat the development VM as that image.

The handover must supply: known-good image/configuration identifiers, tested camera count/settings, waveform/bandwidth, environmental limits, runtime, recovery targets, credential handoff, spare-media procedure, fault contact and acceptance evidence. All remain dependent on hardware validation.
