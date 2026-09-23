# Acceptance record

Status: **NOT RUN**. No Pi, radio, RF or camera test has been executed by this workspace session. Documentation and diagnostic-script checks do not count as hardware evidence.

| Test | Requirement | Pass condition | Status / evidence |
| --- | --- | --- | --- |
| USB enumeration | R01 | Radio NIC and bound driver identified | NOT RUN |
| Local addressing | R02 | Actual DHCP/address/route settings recorded; required endpoint reachable | NOT RUN |
| USB reconnect | R01, R05 | Interface returns and connectivity recovers; timing target pending | NOT RUN |
| Pi reboot | R05 | Configuration returns and required connectivity recovers | NOT RUN |
| RF path | R02, R04 | Both directions work; usable capacity and conditions recorded | NOT RUN |
| Camera demonstration | R03, R04 | Real video at CP; quality/latency targets pending; proposed 60-minute soak | NOT RUN |
| AP/RF recovery | R05 | Service recovers; allowed recovery time pending | NOT RUN |
| Clean installation | R06 | Reproduced build passes the camera test | NOT RUN |
| SitaWare | R07 | Correct operator position and agreed video workflow; freshness target pending | NOT RUN |

Virtual preparation has passed its separate [lab validation](virtual-validation.md). These results do not change the hardware statuses above.

## Run record — copy for each actual test

```text
Run ID / UTC date / operator:
Requirement and test:
Equipment / firmware / OS / kernel:
Waveform / channel bandwidth / range / hop count:
Topology / addresses / DHCP scope:
Commands or procedure:
Expected result and agreed threshold:
Observed result / throughput / latency / loss / recovery:
Evidence paths:
PASS / FAIL / INCONCLUSIVE and reason:
Next action:
```

Use INCONCLUSIVE when a target is unspecified or evidence is incomplete. Keep raw diagnostic directories local; review network identifiers and logs before sharing.
