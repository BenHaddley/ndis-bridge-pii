# Phase 1 — radio USB bench record

Status: **NOT RUN — project owner has no equipment available; no Pi access exists.**

## Collect evidence

Run the collector on the Pi, not on the development computer. It reads USB/network state and creates a new evidence directory without installing packages, changing networking, sending probes or requesting sudo. Some kernel logs may be unavailable to an unprivileged user; the summary records failures, and apparently empty logs should also be reviewed for permissions.

From a copy of this project on the Pi, with the `test-results` parent present:

```bash
bash scripts/collect-diagnostics.sh test-results/pi-before-radio
```

Attach the radio using its documented USB host cable/mode, then run:

```bash
bash scripts/collect-diagnostics.sh test-results/pi-radio-attached
```

Compare `usb.txt`, `usb-tree.txt`, `links.txt` and `kernel-log.txt`. Once the actual radio interface is identified, collect a fresh directory with its name as the second argument. Example only, if it really is `usb0`:

```bash
bash scripts/collect-diagnostics.sh test-results/pi-radio-interface usb0
```

Use new output names for repeat tests. Read `summary.txt` for missing tools or command errors; a successful collection does not mean the radio works. Keep logs local and review identifiers before sharing. The collector does not request NetworkManager secrets, but kernel logs and device details still need review.

## Observations to fill from hardware

| Field | Value |
| --- | --- |
| Pi model / OS / kernel | Pending |
| Radio model / firmware / USB mode | Pending |
| Cable / connector | Pending |
| USB VID:PID / bus speed | Pending |
| Interface / driver / MAC | Pending |
| Radio DHCP enabled / pool / subnet | Pending |
| Pi lease / gateway / DNS | Pending |
| Documented radio endpoint | Pending |
| Local application connectivity | NOT RUN |
| Reconnect identity / recovery time | NOT RUN |
| Reboot result | NOT RUN |
| Evidence directories | None collected from target |

Next, inspect the radio’s DHCP configuration and select a documented endpoint for a connectivity test. Do not guess the radio address from the wiki’s example subnet. Select bridging or routing only after this evidence is available.
