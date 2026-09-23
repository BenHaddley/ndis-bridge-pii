# SitaWare integration — discovery and test contract

Status: **discovery prepared; deployed interface unknown**. Phase 6 implementation is blocked on version-specific documentation and test access. A standalone CP viewer remains the first demo.

| Required answer | Evidence to obtain | Initial information contact |
| --- | --- | --- |
| Headquarters version/build and licensed modules | Deployment inventory | Project owner to identify administrator |
| Is Edge present, and does existing radio PLI already create the operator track? | Demonstration and configuration reference | Deployment administrator |
| Required outcome: operator position plus video link, or georeferenced imagery? | Written workflow and acceptance criteria | Project owner |
| Supported position input and identity model | Licensed interface guide, revision and sections | Deployment administrator/vendor |
| Position source, timestamps and freshness | Actual device output and stale-data rules | Radio/system administrator |
| Supported video opening/ingest workflow | Version-specific guide and working sample | Deployment administrator/vendor |
| Stream transport, authentication and network reachability | Test endpoint and access arrangement | Deployment administrator |
| Track-to-camera association method | Supported workflow/API example | Deployment administrator/vendor |

The local Headquarters and Edge flyers are product overviews. They do not establish a specific API contract for the deployed system. The wiki's public Edge standards list must not be treated as Headquarters configuration instructions. Use the [reference review](reference-notes.md) to select reading and record what remains missing.

## Implement the smallest supported workflow

First check whether existing position reporting supplies the required track. Add a new adapter only when needed and supported. Define identity mapping, coordinate representation, timestamps, update cadence, stale position handling and duplicate-source behaviour before writing it. Do not generate fictitious positions to make a demonstration appear complete.

Next open the Phase 4 stream using the deployed system's supported mechanism. Determine whether the system ingests media or launches a viewer, then associate it with the intended operator/camera through the supported workflow. Fully georeferenced imagery requires a separate metadata and synchronisation requirement.

## Acceptance scenarios

- Correct operator identity and position update using the real source.
- Lost position input becomes stale according to the agreed threshold; restored input recovers without duplicate tracks.
- Intended video opens from the agreed entry and remains associated with the correct camera/operator.
- Video loss, credential failure and restored service produce the documented operator behaviour.
- Evidence records system version, licences, configuration revision and interface-document references.

No messages have been sent to an administrator or vendor. Record assigned contacts and access when supplied; no protocol implementation is selected by this document.
