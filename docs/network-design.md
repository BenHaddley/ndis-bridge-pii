# Network design — Phase 2 bench plan

Status: **prepared, topology not selected or deployed**. The virtual lab has exercised both alternatives; the actual radio USB protocol, routing controls and multi-MAC behaviour remain untested. Complete [Phase 1](radio-interface.md) first.

## Select from evidence

| Observation on the actual radio | Next trial | Evidence to retain |
| --- | --- | --- |
| Multiple camera MACs work through the USB interface and radio DHCP reaches the AP clients | Bridge Ethernet and USB on the Pi | DHCP exchange, bridge forwarding table, camera-to-radio application result |
| Radio accepts a return route to a separate camera LAN | Route between Ethernet and USB | Both endpoint route tables, bidirectional application tests |
| Radio cannot accept or advertise the camera subnet | Evaluate scoped NAT or a required relay after defining the stream direction | CP-initiated connection test and explicit inbound mapping, if needed |
| USB networking does not bind a supported driver | Return to interface discovery | USB descriptors, cable/mode and vendor instructions |

IP-over-USB is listed on page 2 of the [RF-9820S sell sheet](../references/pdf/l3harris-rf-9820s-compact-team-radio-sell-sheet.pdf). That does not select a Linux driver or prove transparent forwarding. See the [source review](reference-notes.md).

## Address and DHCP worksheet

Copy [site.example.json](../config/examples/site.example.json) into your local installation record and replace its nulls with observed/agreed values. It is a worksheet, not installer input. Keep device credentials outside it.

The following addresses match the existing **virtual fixture only**; they are not radio defaults. The older wiki's isolated static examples use different addresses and must not be combined with this plan.

| Segment | Bridged Pi | Routed Pi |
| --- | --- | --- |
| Radio A host network | `192.168.10.0/24`; radio `.1` | Same |
| Pi USB-side address | `br0` `.10.2`, reserved/excluded from DHCP | USB `.10.2`, static or stable reservation after vendor confirmation |
| Camera LAN | Same `.10.0/24`; radio owns DHCP | `192.168.20.0/24`; Pi `.20.1`; local DHCP or static assignment |
| Camera gateway | Radio `.10.1` | Pi `.20.1` |
| AP management | Reserved address in camera subnet | Reserved address in camera subnet |
| CP subnet | `192.168.30.0/24`, via radio A | Same |

Use a stable Pi USB address for any radio return route. A changing DHCP lease would invalidate that next hop. Check all subnets against existing radio and CP networks before selecting them. Record lease duration and renewal behaviour, not just the first assigned address.

For the bridge trial, put the Pi management address and any route to the CP on `br0`; keep member ports without their own IP configuration. The radio supplies DHCP only if the test proves its scope is suitable. The AP supplies neither NAT nor DHCP in this trial.

For routing, the camera subnet needs its own address assignment. The Pi needs a route toward the CP through radio A, and the radio/CP path needs a route back to the camera subnet through the Pi. Confirm the camera has the correct gateway too. Configure IPv4 forwarding and application-specific firewall allowances only after recording the existing settings. Record any IPv6 requirement separately; an IPv4 plan does not define IPv6 forwarding policy.

## Traffic contract before firewall/NAT work

| Flow | Initiator | Destination | Ports / return path |
| --- | --- | --- | --- |
| Camera management | Bench operator | Camera | Vendor documentation required |
| Video control | Usually viewer for a pull stream; confirm | Camera or relay | Actual protocol and authentication required |
| Media | Depends on negotiated transport | Viewer or receiver | Document TCP interleaving or UDP port ranges |
| DHCP | Local client | Server in its own LAN | Keep server ownership explicit per subnet |
| Pi/radio management | Named administration endpoint | Pi/radio | Keep reachable during cutover |

Do not choose masquerading as a substitute for understanding an incoming viewer connection. A successful outgoing ping does not show that a CP viewer can open a camera. Test the actual stream, including negotiated media ports. Begin with unicast and direct addresses; discovery and multicast are separate requirements.

## Cutover and recovery procedure

1. Use the Pi console. Save a new diagnostic bundle, current profile UUIDs, each profile's autoconnect value, current routes, forwarding settings and firewall rules. Privately back up configuration files that may contain secrets.
2. Fill the address worksheet and traffic contract. Confirm a management path and record exactly which existing profiles conflict with the planned ports.
3. Prepare uniquely named trial profiles. Review settings before activation; the [wiki bridge procedure](../RNDIS-Bridge-Wiki.md#persistent-networkmanager-bridge) is an example to adapt, not a detected configuration. Leave unrelated profiles alone.
4. Disable autoconnect only on the recorded conflicting profiles, then activate the trial. Verify address uniqueness, DHCP owner, local application access and both directions through the selected topology.
5. If a check fails, deactivate and remove only profiles created by this trial, restore each old profile's recorded autoconnect value and reactivate the profiles that were previously active. Restore only changed forwarding/firewall settings from the pre-change record. Do not flush the firewall or delete unrelated profiles.
6. After local checks pass, test reboot, USB removal/re-enumeration, and DHCP renewal. Save before/after bundles and elapsed recovery times. Repeat the rollback from the console and demonstrate the previous management path still works.

NetworkManager also provides a timed checkpoint around a command; if confirmation is not given it restores the checkpoint. Check local support before using it as an extra guard. It does not replace the project's configuration backup or console recovery procedure. [Official nmcli reference](https://networkmanager.dev/docs/api/latest/nmcli.html).

**Exit record:** selected topology, approved addresses, profile UUIDs, DHCP owners, return routes, firewall changes, recovery results and evidence filenames. Until these exist, Phase 2 remains open and there is no production configuration to package.
