# Debian VM validation

Validated on 23 September 2026. The project owner chose a Debian PC VM for networking development.

| Item | Observed result |
| --- | --- |
| Guest | Debian GNU/Linux 13, amd64 |
| Kernel | `6.12.107+deb13-cloud-amd64` |
| Emulator | QEMU 11.1.1; TCG; `qemu64`; emulated SMM disabled |
| Resources | 2 vCPUs, 2 GiB RAM, 24 GiB sparse writable disk |
| Management | SSH on host `127.0.0.1:2222`, guest user `lab` |
| Offline tests | 15 passed inside the guest |
| Bridge scenario | 10 checks passed inside the guest |
| Routing scenario | 12 checks passed inside the guest |
| Physical hardware acceptance | NOT RUN |

The Debian image SHA-512 was checked against the official HTTPS checksum file:

```text
95e110dfcdbd0ed8a82a75ed9579802f9950cabf51a810dcc6388e81bc778188713878b9f28d583a0ea602fbf48b35996ae9ad37f584166d8fbd6489df248f53
```

Image source: [Debian 13 genericcloud amd64](https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2). Exact provenance and the local tool package hashes are retained in `vm/runtime/image-manifest.json` and `vm/runtime/tools-manifest.json`.

## Evidence

The full test log is in `vm/runtime/validation-20260923T083145Z.log`. The local copies of guest verdicts are:

- `vm/runtime/bridge-result-20260923T083145Z.json`
- `vm/runtime/route-result-20260923T083145Z.json`

Full namespace snapshots, DHCP logs and payload evidence remain in the guest at `~/rndis-lab/test-results/virtual-bridge-20260923T083145Z/` and `~/rndis-lab/test-results/virtual-route-20260923T083145Z/`.

The checks cover DHCP placement, two-way HTTP traffic, a checksum-verified 1 MiB payload, link interruption/recovery with explicit route reconciliation, and missing-route recovery. This is the synthetic lab, not a real video or radio demonstration.

## Setup findings

The initial maximal emulated CPU/SMM configuration stalled in firmware before guest disk writes. The final launcher uses `qemu64` with SMM disabled; Debian booted with that configuration.

The first package update retried an optional source index. Unneeded source/translation indexes were disabled inside the VM; the interrupted index refresh was retried and required packages installed. A subsequent `apt-get update` completed successfully and all required commands were checked. Cloud-init retains a recovered warning from the interrupted refresh, preserved in `vm/runtime/cloud-init-status.json`; recovery output is in `vm/runtime/cloud-init-recovery.log`. Fresh VM seed configuration includes the index settings. No unresolved package-install error was accepted.

Debian's ordinary user PATH omitted administrative tools. The lab now appends `/usr/sbin` and `/sbin` before dependency checks, allowing rootless namespace tests to find `tc` and `dnsmasq`.

## Use

The VM was left running after validation. Connect from the project root:

```bash
python3 vm/debian-vm.py ssh
```

For controls, reprovisioning, tests and shutdown, see the [VM guide](../vm/README.md).

Guest state persists in its writable disk. VM startup and functional tests were verified; graceful shutdown/restart persistence has not been separately exercised in this validation run. Hardware USB, RF performance, real camera video and SitaWare remain untested.
