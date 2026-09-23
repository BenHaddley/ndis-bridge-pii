# Virtual lab validation

Validation date: 23 September 2026. This record concerns virtual Linux networking only. All physical equipment gates remain **NOT RUN**.

Implementation and reproduction instructions: [lab README](../lab/README.md).

| Scenario | Result | Passed checks | Local evidence |
| --- | --- | --- | --- |
| Bridge | PASS | 10 | `virtual-bridge-03/result.json` |
| Routing | PASS | 12 | `virtual-route-01/result.json` |

Both scenarios used the default illustrative 16 Mbps per-direction queue cap. This is not a WRAITH/TSM throughput measurement. The generated payload is not real camera video.

Verified behaviour:

- Radio DHCP traverses the local AP/Pi bridges in bridge mode.
- Routed mode uses a radio-side lease for the Pi and a separate Pi DHCP server for the camera subnet; the radio's DHCP offers do not cross that routed boundary.
- HTTP requests work in both directions and a 1 MiB payload matches its checksum after transfer.
- USB-side and radio-to-radio link outages interrupt traffic; restoring links and explicitly reconciling routes recovers it.
- Removing and restoring the remote camera-subnet route produces the expected failure and recovery.

The live tests exposed the need to restore next-hop routes after administrative link-down. The lab now explicitly reapplies its fixture routes. A real NetworkManager deployment must separately validate equivalent recovery; no production network configuration has been applied.

Eleven offline tests passed with `python3 -m unittest discover -s tests -v`, covering protocol parsing, invalid inputs, preservation of existing evidence, the worker isolation guard and diagnostic collection behaviour.

Raw run directories are ignored by Git and remain available locally. Earlier development runs are retained as failed evidence, not counted as passing validation. The final successful runs above establish the current lab result.

Still unvalidated: actual radio USB/driver behaviour, real DHCP configuration, USB re-enumeration, NetworkManager persistence, Wi-Fi/RF performance, streaming quality, power/runtime and SitaWare integration.
