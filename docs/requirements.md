# Requirements — working baseline

Status: Phase 0 in progress. Project scope is recorded; equipment availability and numerical acceptance targets remain open. Source: project owner’s brief, Jeremy’s update, and the [roadmap](../BUILD-ROADMAP.md).

## First demonstration

One real camera → Wi-Fi AP → Pi Ethernet → USB network interface → radio pair → command-post laptop displaying live video.

Start with WRAITH 10 MHz if available. Jeremy reports 16 Mbps at this bandwidth; usable application throughput remains unmeasured. WRAITH 20 MHz and TSM 40 MHz are alternative configurations to validate separately. The radio has a DHCP server; its actual settings and scope must be collected.

| ID | Requirement | Verification |
| --- | --- | --- |
| R01 | Pi recognises the radio as a stable network interface | Enumeration, driver and reconnect evidence |
| R02 | Addressing and return paths support the selected topology | Lease/address/route evidence and application reachability |
| R03 | Real camera video reaches the CP across both radios | Viewer demonstration and dated run record |
| R04 | Video traffic fits measured capacity with a documented reserve | RF measurements and selected stream settings |
| R05 | Configuration and service recover after expected interruptions | USB, AP, RF and Pi restart tests |
| R06 | Build can be reproduced on a clean installation | Installation record and repeated video test |
| R07 | Required position and video workflow works in deployed SitaWare | Version-specific integration demonstration |

R01–R04 define the first demo. R05–R07 are subsequent milestones. A bridge or router is selected after interface testing; transcoding is conditional on measured need. SitaWare protocol support is not yet established for this deployment.

Source review, 24 September: the handheld sell sheets advertise IP over USB/Ethernet, but do not establish the USB class or Linux procedure. They list bandwidth up to 20 MHz, while Jeremy reports a 40 MHz TSM option; the separate embeddable model lists 40 MHz. Resolve the actual model/firmware support before that trial. See [PDF findings](reference-notes.md).

## Open decisions

| Decision | Working proposal | Resolution needed from |
| --- | --- | --- |
| First-demo camera count | One | Project owner; final deployment count also needed |
| Camera quality, frame rate and latency | Collect baseline before selecting final settings | Project owner |
| Bench soak | 60 minutes, proposed | Project owner |
| Recovery target and repetitions | Measure first; numerical acceptance target pending | Project owner |
| Power/runtime/environment | Pending equipment and use conditions | Project owner |
| SitaWare workflow | Operator position plus viewable video; georeferenced imagery is additional scope | Project owner and deployment administrator |
| Radio configuration access | Unknown | Project owner; Jeremy is an information source, not an assigned owner |

Do not label a run accepted while its applicable pass criteria remain undefined. Use the [acceptance record](../test-results/acceptance.md).
