# RNDIS radio bridge — build roadmap

_Last updated: 24 September 2026. Status: Phase 0 in progress; Phase 1 evidence collection and Phases 2–4 bench procedures prepared. No hardware gates passed._

Build a repeatable Raspberry Pi appliance that carries camera traffic from an Ethernet-connected Wi-Fi AP into the radio’s USB network interface, across the radio link, and to a command-post viewer. Then integrate the required position and video functions with the deployed SitaWare system.

Technical background and command examples: [project wiki](RNDIS-Bridge-Wiki.md). This roadmap uses the project information already collected; it does not establish new vendor compatibility claims.

## Current work

- [Network design and rollback](docs/network-design.md) — bridge/routing decision criteria, address/DHCP plan and [site worksheet](config/examples/site.example.json) prepared; topology not selected.
- [RF baseline workflow](docs/rf-measurement.md) — collection procedure and [TCP report tool](scripts/summarize-rf.py) implemented; real RF data pending.
- [Video profile](docs/video-profile.md), [SitaWare discovery contract](docs/sitaware-integration.md) and [operator guide draft](docs/operator-guide.md) — prepared for hardware and deployment access.
- [PDF source review](docs/reference-notes.md) — all 11 existing PDF hashes verified and text extracted. Handheld IP-over-USB support is advertised; RNDIS/Linux operation is untested. Resolve the handheld 20 MHz versus reported TSM 40 MHz discrepancy before testing that configuration.

- [Debian development VM](vm/README.md) — available; original validation passed 15 offline tests plus 22 live lab checks inside Debian. [VM validation record](test-results/debian-vm-validation.md). The 24 September loopback checks are recorded separately below.

- [Virtual network lab](lab/README.md) — implemented and validated: 10 bridge checks and 12 routing checks passed. [Validation record](test-results/virtual-validation.md); hardware gates remain separate.

- [Working requirements](docs/requirements.md) — scope recorded; numerical targets pending.
- [Hardware inventory](docs/hardware-inventory.md) — no equipment available, confirmed by project owner.
- [Acceptance record](test-results/acceptance.md) — all hardware tests NOT RUN.
- [Radio bench procedure](docs/radio-interface.md) and [diagnostic collector](scripts/collect-diagnostics.sh) — ready for target-side evidence collection.

The project owner currently has no equipment. Follow the [equipment readiness plan](docs/equipment-readiness.md) while progressing offline preparation. Phase 0 remains open until equipment/access and acceptance decisions are supplied. Phase 1 remains untested until evidence is collected on the actual Pi and radio.

### Offline work completed on 24 September

- [x] Prepare Phase 2 network/address/DHCP decisions and console rollback procedure.
- [x] Prepare Phase 3 measurement conditions, directional TCP reporting and provisional budget calculation with automated checks.
- [x] Prepare Phase 4 camera/viewer profile and video/recovery evidence requirements.
- [x] Prepare Phase 6 version-specific integration questions and acceptance scenarios.
- [x] Prepare Phase 7 operator fault and handover worksheet.
- [x] Re-read the saved PDFs, add page-level citations and correct unsupported statements in the wiki/manifest.

These checkmarks cover preparation only. Phase 5 installation and health-check implementation still depend on a configuration and endpoints proven in Phases 1–4; no production installer or recovery guarantee is claimed. See the [offline preparation validation](test-results/offline-preparation.md).

## Starting assumptions

| Item | Current basis | Still to establish |
| --- | --- | --- |
| Radio | RF-9820S / AN/PRC-171 in the wiki; handheld PDFs p. 2 advertise IP over USB/Ethernet | Actual unit, firmware, host cable, USB protocol and Linux driver |
| Waveforms | Jeremy: WRAITH 10/20 MHz and/or TSM 40 MHz; handheld PDFs list bandwidth only up to 20 MHz | Resolve model/firmware support and discrepancy; simultaneous operation is not assumed |
| Throughput | Jeremy: WRAITH 10 MHz can give 16 Mbps | Nominal rate versus usable IP throughput and test conditions |
| DHCP | Jeremy confirms a server in the radio | Pool, subnet, gateway options, enabled state and scope |
| Pi role | Network forwarding first | Bridge or routing; additional video software only if required |
| Destination | CP viewer, followed by SitaWare | Deployed version, licences, supported interfaces and credentials |

Do not extrapolate throughput for WRAITH 20 MHz or TSM 40 MHz. The public SitaWare Edge material referenced in the wiki does not establish Headquarters compatibility; obtain the deployed system’s interface documentation before selecting an integration protocol.

## Milestones and order

Effort ranges below are planning estimates for one engineer with the equipment available. They exclude procurement, vendor responses, access approvals and unavailable test facilities. Re-estimate after the first hardware gate.

| Phase | Deliverable | Depends on | Estimated hands-on effort |
| --- | --- | --- | --- |
| 0. Freeze the first demo | Equipment inventory, requirements and test plan | Project owner and kit details | 0.5–1 day |
| 1. Prove the USB interface | Stable Linux NIC and documented radio addressing | One radio, Pi and correct cable | 0.5–2 days |
| 2. Build the local network | Persistent AP–Pi–radio connectivity | Phase 1 | 1–2 days |
| 3. Prove the RF path | Bidirectional reachability and measured capacity | Phase 2, second radio and CP endpoint | 1–3 days |
| 4. Deliver the video MVP | One live camera stream at the CP | Phase 3 and camera | 1–3 days |
| 5. Make it repeatable | Install/configure/rollback workflow and recovery tests | Phase 4 | 2–4 days |
| 6. Integrate SitaWare | Agreed map presence and video workflow | Phase 4 plus confirmed integration access | Estimate after interface review |
| 7. Validate field operation | Acceptance evidence and operator handover | Phase 5; Phase 6 if required for acceptance | 2–5 days |

Phases 0–4 are the critical path to the first video demo: approximately **4–11 engineer-days**, subject to the hardware gates. Vendor/interface discovery for SitaWare can begin during Phase 0; it need not delay a standalone CP video demonstration.

## Phase 0 — define the first demonstration

**First-demo scope:** one camera → Wi-Fi AP → Pi Ethernet → USB radio interface → two-radio link → CP laptop displaying live video. Begin with WRAITH 10 MHz if available, because it has a reported throughput reference.

- [ ] Inventory the Pi, two radios, firmware/waveform loads, USB cables, AP, camera, CP laptop and power supplies.
- [ ] Obtain radio host-interface instructions, camera stream details and AP configuration instructions.
- [ ] Record the camera count and quality ultimately required; use one camera for the first demo.
- [ ] Define whether SitaWare needs operator position plus a video link, or fully georeferenced imagery. Treat the latter as additional scope.
- [ ] Identify who can configure the radios and who can provide SitaWare access.
- [ ] Agree latency, reconnect time, video quality, runtime and test conditions. Until agreed, use the provisional bench checks below.

**Deliverable:** `docs/requirements.md`, `docs/hardware-inventory.md`, and an acceptance checklist.

**Exit gate:** the first-demo topology, test equipment, access needs and expected viewer behaviour are written down. Missing equipment has an owner and next action.

## Phase 1 — prove radio USB networking

Follow [bench preparation](RNDIS-Bridge-Wiki.md#bench-preparation) with one radio attached directly to the Pi.

- [ ] Save OS/kernel/NetworkManager versions, `lsusb`, `lsusb -t`, kernel logs and interface details.
- [ ] Identify the driver and actual interface name; verify that reconnecting the radio does not invalidate the intended configuration.
- [ ] Inspect the radio’s DHCP settings. Record the assigned lease, subnet, gateway and any DNS information without assuming the wiki’s example addresses are defaults.
- [ ] Confirm Pi-to-radio IP/application connectivity using a documented radio endpoint.
- [ ] Repeat USB disconnect/reconnect and a Pi reboot; save the outcomes.

**Deliverable:** `docs/radio-interface.md` and dated diagnostic evidence under `test-results/`.

**Exit gate:** a stable Linux network interface and repeatable local IP connectivity.

**If it fails:** resolve the cable, USB mode, driver or vendor host-interface requirement. Do not build around an assumed RNDIS interface. A VM may help diagnose driver behaviour, but does not pass the Pi hardware gate.

## Phase 2 — choose the topology and persist it

Test the local network before involving the RF path. Keep console access available during network changes.

| Finding | Implementation choice |
| --- | --- |
| Radio host interface accepts the camera LAN’s multiple MAC addresses and local DHCP behaviour is suitable | Trial `br0` joining Ethernet and USB |
| Radio expects a host subnet and supports a route to the camera LAN | Separate subnets with Pi routing and explicit return routes |
| Return routes cannot be configured | Evaluate scoped NAT against the actual streaming direction; document inbound access requirements |
| Behaviour remains unclear | Capture traffic and obtain the host-interface documentation before selecting a permanent topology |

- [ ] Put the AP into its documented AP/bridge mode and verify camera-to-Pi communication.
- [ ] Record the chosen subnet plan, management address and DHCP ownership for each broadcast domain.
- [ ] Use the radio’s DHCP server where it is reachable and appropriate; disable competing servers on that same LAN.
- [ ] For routing, provide address assignment on the separate camera LAN and verify both directions of traffic.
- [ ] Persist the selected configuration in NetworkManager and disable only conflicting profiles.
- [ ] Record rollback steps and test a reboot and USB reconnect.

**Deliverable:** `docs/network-design.md`, reviewed configuration templates, and a verified recovery procedure.

**Exit gate:** the laptop/camera side reaches the required radio-side endpoint, the addressing is stable, and configuration survives restart. A local bridge does not prove the radio carries Layer 2 across RF.

## Phase 3 — measure the radio path

Connect the second radio and CP endpoint. Establish addressing and return paths at both ends before testing media.

- [ ] Prove application connectivity in both directions and record routes.
- [ ] Measure each segment separately, then the complete path. Use test endpoints that can run the measurement tools; do not assume the radio can run them.
- [ ] Record achieved throughput, latency, packet loss, direction, duration, waveform, channel bandwidth and concurrent load.
- [ ] Establish path MTU and test the intended unicast stream path. Test multicast only if the selected application requires it.
- [ ] Start with a bench baseline; repeat in representative conditions with normal traffic present.
- [ ] Test WRAITH 20 MHz or TSM 40 MHz separately if those configurations are in scope.

**Deliverable:** `test-results/rf-baseline.csv` plus a short capacity report identifying the usable video budget and measurement conditions.

**Exit gate:** stable end-to-end connectivity and enough measured capacity for the proposed single-camera stream, including overhead and a recorded reserve.

**Budget rule:** derive capacity from measured usable throughput. The reported 16 Mbps is a starting reference. For example, if 16 Mbps usable throughput is measured, a provisional 25% reserve leaves 12 Mbps for video traffic including transport overhead; this is a planning choice, not a guaranteed radio capability.

## Phase 4 — deliver one live video stream

- [ ] Prove the camera stream locally using its documented protocol and credentials.
- [ ] Configure the camera’s own bitrate, resolution and frame rate to fit the Phase 3 budget.
- [ ] Open that stream from the CP over the radio path.
- [ ] Record displayed quality, observed latency, bandwidth, freezes and reconnect behaviour.
- [ ] Add a Pi proxy/relay only if stable addressing, client access or stream selection requires it.
- [ ] Add transcoding only if camera controls cannot meet the agreed quality/capacity requirement; first measure Pi CPU, temperature and power under that workload.

**Deliverable:** a recorded demo result and `docs/video-profile.md` describing reproducible camera and viewer settings.

**Exit gate — video MVP:** one real camera is watchable at the CP for the provisional 60-minute bench run, within the agreed quality/latency criteria, with stalls and recoveries recorded. IP reachability or a synthetic throughput test alone does not pass this gate.

## Phase 5 — make the build repeatable and recoverable

Package only the configuration proven in Phases 1–4.

- [ ] Separate site-specific settings from installation logic: interface identity, addresses, DHCP choice, camera endpoints and waveform notes.
- [ ] Create an installer/configuration workflow that detects existing profiles, backs up settings and supports a preview before applying changes.
- [ ] Keep credentials out of repository templates and diagnostic bundles.
- [ ] If a relay is required, run it as a supervised service with bounded logs and explicit restart behaviour.
- [ ] Provide a health check covering USB NIC presence, network state, radio-path reachability and the video endpoint.
- [ ] Test radio reconnect, AP restart, RF interruption and Pi reboot. Record recovery time and required operator actions.
- [ ] Build a second SD card or clean installation from the documented procedure and verify it behaves the same way.

**Deliverable:** versioned configuration, installation/recovery instructions, health checks and a reproducible release record.

**Exit gate:** a clean installation passes the video MVP test, and each agreed interruption recovers within its acceptance target without unexplained manual fixes.

## Phase 6 — integrate with the deployed SitaWare system

Discovery starts in Phase 0; implementation waits for the deployed interface details.

- [ ] Confirm Headquarters version, licences, integration documentation and a test environment with its administrator.
- [ ] Check whether existing radio PLI or SitaWare Edge already provides the required operator track.
- [ ] If a new position adapter is necessary, select a supported interface, identify the real position source, and define identity, timestamps and stale-track handling.
- [ ] Confirm the supported video ingest/opening workflow and test the Phase 4 stream through it.
- [ ] Associate the agreed camera/video entry with the correct operator or track using supported mechanisms.
- [ ] Pursue STANAG/KLV or other georeferenced imagery work only if required and supported; estimate that work separately.

**Deliverable:** `docs/sitaware-integration.md`, the minimal required adapter configuration/code, and an operator demonstration.

**Exit gate:** the correct operator appears with valid position updates and the intended video can be opened in the agreed SitaWare workflow. Verify stale position and video-loss behaviour. A separate media player demo does not establish SitaWare integration.

## Phase 7 — field validation and handover

- [ ] Repeat the approved tests at representative range, terrain, hop count and network load.
- [ ] Increase camera count one at a time, measuring the aggregate traffic after each addition.
- [ ] Validate the agreed operating duration, power source, thermal conditions and physical cable retention.
- [ ] Confirm permitted access to camera/radio management and required forwarding rules in the deployment network.
- [ ] Record limits: tested waveform/bandwidth, supported camera count/settings, conditions and recovery times.
- [ ] Deliver an operator quick start, fault checklist, rollback/reimage instructions and a known-good configuration backup.

**Deliverable:** signed-off acceptance record and a versioned deployment package.

**Exit gate:** agreed requirements pass with saved evidence; remaining limitations are explicit. Completion of this roadmap’s documents is not completion of the hardware build.

## Acceptance worksheet

These are proposed initial checks. The project owner must set the missing numerical targets before field acceptance.

| Area | Initial check | Final target to record |
| --- | --- | --- |
| USB/network | Repeat enumeration, reconnect and reboot successfully | Recovery time and repeat count |
| Video stability | One stream for 60 minutes on the bench | Allowed stalls, loss and image quality |
| Latency | Measure camera-to-display delay | Maximum acceptable delay |
| Capacity | Stream plus overhead fits measured budget | Reserve, camera count and other traffic |
| RF interruption | Interrupt and restore the path; observe recovery | Maximum outage/reconnect time |
| Runtime | Measure full-kit power and temperature | Required battery duration and environment |
| SitaWare | Correct track identity and agreed video workflow | Position freshness and stale-data behaviour |

## Proposed repository deliverables

The following is the target structure. Preparation documents, diagnostic collection and RF report tooling are present. Production installation, health checks, measured RF data and accepted release records remain planned.

```text
BUILD-ROADMAP.md
RNDIS-Bridge-Wiki.md
docs/
  requirements.md
  hardware-inventory.md
  radio-interface.md
  network-design.md
  rf-measurement.md
  reference-notes.md
  video-profile.md
  sitaware-integration.md
  operator-guide.md
config/
  examples/
scripts/
  install.sh
  health-check.sh
  collect-diagnostics.sh
  summarize-rf.py
test-results/
  rf-baseline.csv
  acceptance.md
references/
  pdf/
```

Use the wiki’s [reference library](RNDIS-Bridge-Wiki.md#reference-library-and-pdf-resources) and [test record template](RNDIS-Bridge-Wiki.md#test-record-template). Record source revision/page numbers when a vendor document resolves an assumption. Store large captures separately and reference their filenames from test records.

## First work session

1. Put one Pi and one radio on the bench; identify the firmware, waveform, cable and USB mode.
2. Capture USB enumeration, driver binding and network state.
3. Inspect the radio DHCP configuration and establish Pi-to-radio connectivity.
4. Save the evidence and choose the next topology test based on what the hardware actually supports.
5. Arrange the second radio, camera and CP endpoint for the end-to-end test; request the SitaWare deployment details in parallel.
