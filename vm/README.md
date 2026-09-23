# Debian development VM

The project owner selected a **Debian PC VM** for networking development. This runs a complete Debian 13 amd64 guest, with the existing virtual network lab inside it. It is not ARM Raspberry Pi OS and does not emulate a physical radio.

Validation: [guest test results and setup findings](../test-results/debian-vm-validation.md).

## VM layout

```text
Linux host
└── QEMU: Debian 13 amd64, 2 vCPUs, 2 GiB RAM, 24 GiB sparse disk
    ├── Management NIC: QEMU user networking (outbound NAT)
    ├── SSH: host 127.0.0.1:2222 → guest port 22
    └── Disposable lab namespaces
        camera → AP → Pi → radio A → radio B → CP
```

The management NIC is independent of the test topology. The lab namespaces have no path to it. Guest package installation uses the management connection. QEMU's user networking does not attach to a host bridge or change the host firewall. Only SSH is forwarded, and it is bound to host loopback.

The launcher uses the conservative `qemu64` CPU model and disables emulated SMM for this TCG setup. CPU execution currently uses TCG software emulation because `/dev/kvm` is unavailable in the working environment. Functional networking tests are useful; guest throughput/timing measurements are not representative of a Pi or the real RF link.

## Host requirements and local tools

Python 3.11+, SSH client/key generator, curl, QEMU x86 system emulator, qemu-img and xorriso are required. The local launcher uses Python `hashlib.file_digest`.

On the current Manjaro host, QEMU was not installed and administrator access required a password. A project-local tool bootstrap is provided:

```bash
python3 vm/bootstrap-local-qemu.py
```

This reads the host's existing pacman repository metadata, downloads the QEMU/ISO packages and missing dependencies, verifies their SHA-256 checksums against that metadata, and extracts them into `vm/runtime/tools`. It does not refresh package databases, install system packages, run package hooks or modify `/usr`. This bootstrap is specific to a compatible Arch/Manjaro x86_64 host; stale repository metadata may require user-managed system maintenance. Other hosts can use their normally installed QEMU/xorriso tools.

## Prepare and start

From the project root:

```bash
python3 vm/debian-vm.py prepare
python3 vm/debian-vm.py start
python3 vm/debian-vm.py status
```

Preparation downloads the official Debian 13 genericcloud amd64 image and checks its SHA-512 against the publisher's checksum file fetched over HTTPS. This is checksum verification, not an independent signature-verification chain. The exact URL/hash are saved in `vm/runtime/image-manifest.json`.

An SSH key is generated for this VM only. Password login is disabled; the guest account is `lab`, with passwordless sudo **inside the guest**. A NoCloud seed ISO creates the account and installs the tools needed by the lab. A writable qcow2 overlay references the untouched downloaded base disk.

`prepare` does not overwrite an existing configured VM. It refuses an unexpected writable disk. If an initial download fails, inspect the `.part` file and checksum metadata before retrying. The helper downloads again rather than assuming a partial file is complete.

First boot and package installation can take several minutes under TCG. Follow progress with:

```bash
tail -f vm/runtime/serial.log
```

## Copy and test the lab

Once SSH is available:

```bash
python3 vm/debian-vm.py provision
python3 vm/debian-vm.py test
```

Provisioning verifies the guest's generated instance identifier over SSH, waits for cloud-init, checks dependencies, and copies `lab/`, `scripts/`, `tests/` and the VM helper source needed by its offline tests to `~/rndis-lab`. It excludes Python caches and does not copy VM keys/disks, host runtime files or hardware captures. Re-running provisioning updates project code and preserves guest test results.

A recoverable cloud-init package-index warning is retained and accepted only after a fresh successful `apt-get update`; unexpected warnings or unresolved cloud-init errors stop provisioning.

`test` runs offline tests followed by live bridge and route scenarios in fresh output directories. It saves a combined log and copies both JSON verdicts back into `vm/runtime`. Full DHCP/network/HTTP evidence remains inside the guest under `~/rndis-lab/test-results/`.

The initial SSH host key is accepted into a dedicated known-hosts file. Subsequent host-key changes are rejected. Rebuilding a guest requires an intentional identity/known-host update; do not disable host-key checks to hide a mismatch.

## Use and stop

```bash
# Interactive shell
python3 vm/debian-vm.py ssh

# One command; arguments are shell-quoted by the helper
python3 vm/debian-vm.py ssh uname -a

# Graceful shutdown; disk and results are retained
python3 vm/debian-vm.py stop
```

For a guest stuck before SSH becomes available, `python3 vm/debian-vm.py diagnose` reads CPU/disk state. As a last resort, `python3 vm/debian-vm.py stop --force` terminates this emulator through QMP immediately; it is equivalent to cutting guest power and may lose guest writes. Prefer graceful shutdown once Debian is running.

The VM persists until stopped, unlike the lab's temporary namespaces. It uses roughly its configured 2 GiB RAM plus emulator overhead while running. Start it again with `start`; the writable disk preserves installed packages and results.

QEMU control is through a project-local QMP socket. The helper does not terminate arbitrary host PIDs. Keep `vm/runtime` together: the overlay has an absolute backing-file path, so moving the checkout requires updating that path before booting. No delete/reset command is supplied.

## Files and limitations

All disks, downloaded tools, package/image manifests, SSH material, cloud-init seed, serial logs and runtime evidence are stored under `vm/runtime/`, which is ignored by Git. Do not commit or share that directory as a source-code bundle; it contains the VM's private SSH key.

This VM can validate Debian userspace, namespace networking, DHCP and the project's tools. It does not establish Raspberry Pi architecture/kernel compatibility, RNDIS radio enumeration, real Wi-Fi/RF performance, USB reconnect behaviour or SitaWare integration. Hardware acceptance remains separate.

Sources: [Debian cloud images](https://cloud.debian.org/images/cloud/trixie/latest/), [cloud-init NoCloud datasource](https://docs.cloud-init.io/en/latest/reference/datasources/nocloud.html), and [QEMU system emulation](https://www.qemu.org/docs/master/system/introduction.html).
