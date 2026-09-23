# Video profile — Phase 4 worksheet

Status: **NOT RUN**. No camera, protocol, credentials or measured bitrate has been selected. Fill one profile per camera configuration; preserve the profile used for each run.

| Field | Value / evidence |
| --- | --- |
| Camera model / firmware | Pending hardware |
| AP model / firmware / mode | Pending hardware |
| Camera address / stream endpoint without credentials | Pending |
| Credential storage location and permitted viewer role | Pending; no passwords in this document |
| Documented protocol / media transport / ports / connection initiator | Pending |
| Codec / resolution / frame rate / keyframe interval | Pending |
| Rate control mode / target bitrate / maximum bitrate | Pending |
| Audio enabled / audio bitrate | Pending |
| Viewer application / version / settings | Pending |
| RF report / waveform / bandwidth / conditions | Pending |
| Reserve and other-traffic allowance | Pending |
| Measured stream average and peaks at the radio-bound interface | Pending |
| Agreed quality / latency / stall / recovery criteria | Pending owner decisions |

## Test sequence

1. Open the documented stream locally through the AP. Confirm authentication, media transport and the camera's client limit. Record whether the viewer pulls or the camera pushes.
2. Set the camera's own encoder controls using the [RF baseline](rf-measurement.md) as a starting constraint. Include audio, multiple viewers and protocol overhead in observations. A second independent pull may create a second full-rate stream.
3. Open the same stream at the CP. Verify the complete media path, not just a login page or control connection. Record time to first image.
4. Measure camera-to-display delay with a repeatable visual timing method; document its precision. Network ping is not a substitute for this measurement.
5. Run the proposed 60-minute bench soak. Record freezes, their durations, reconnects, peak traffic and the viewer's displayed quality. Undefined thresholds mean INCONCLUSIVE, not PASS.
6. Interrupt USB, AP and RF separately, then reboot the Pi. Record interruption duration, recovery time and every manual action. The fixture's link toggles do not replace these physical tests.

Start with direct forwarding. Consider a relay only for a demonstrated address/client/selection problem. Consider transcoding only after proving camera controls cannot meet the requirement; then measure CPU, temperature, power and additional delay on the actual Pi. Document the reason before adding either dependency.

Use a dated copy of the [acceptance run record](../test-results/acceptance.md). Phase 4 closes only with real camera video across the two-radio path and agreed criteria satisfied.
