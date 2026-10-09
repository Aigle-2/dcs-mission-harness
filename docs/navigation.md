# Navigation and identification during design

Functional-spec 1.7 requires `navigation` even when no radio plan is requested.
Comm-plan 1.1 contains the identical record so briefing, kneeboards and mission
configuration share the same choices. A proposed navigation plan blocks spec
registration. User approval can cover the complete displayed plan; unresolved
ship capabilities cannot be hidden inside a confirmed plan.

- TACAN: station/unit, platform, channel 1–126, X/Y band and ident. Harness
  convention uses X for ground/ships and Y for aircraft. This is an allocation
  convention, not a claim that other combinations are impossible in DCS.
- Yardstick: flight, leader and wingmen, same Y band and exactly 63 channels
  separation, e.g. leader 3Y and wingmen 66Y. Channel assignments must remain
  within 1–126; the lower/higher orientation may be reversed. Check duplicates
  and overlap with active beacon allocations. This schema uses distinct
  allocations; deliberate reuse needs a reviewed extension with time/area scope.
- Callsigns: each flight specifies an exact aircraft and either user-selected
  name/flight number or `dcs-default`. When unspecified use DCS defaults, then
  read the builder's resolved callsign into briefing/kneeboards. Verify names or
  numeric formats against the installed aircraft/country catalog. Schema values
  do not certify a callsign is available.
- Naval systems: identify each relevant ship and explicitly review ICLS and
  datalink frequency applicability. ICLS uses a channel, not a voice frequency.
  For tunable datalink use system name and MHz. `not-applicable` means no tunable
  frequency is required here; it does not mean the ship has no networking at all.
  Do not invent a fixed frequency for a network configured differently.

## Implementation and verification

The implementing agent checks actual module/ship capabilities before enabling
beacons or datalink. For a frequency-based system, verify both ship and receiver
tuning range/step. Do not extrapolate F-14A/B Link-4 behavior to F-14BU or to
another module without checking its implementation. Record supporting sources
and target version privately. Unknown capabilities are BLOCKED.

`NAVIGATION` is required as a local criterion. Inspect saved beacon/ICLS/datalink
tasks, unit linkage, channels, idents, unit conversions and resolved callsigns.
The existing voice-radio adapter does not create/check navigation tasks. Do not
claim implementation because a plan parses or appears in the briefing.

Yardstick may require crew TACAN selections. Verify what can be preset in each
module and brief manual actions rather than inventing mission-table fields.
The phase plan must show when TACAN is used for yardstick, tanker or carrier:
do not imply one receiver tracks every assignment simultaneously. Crew-selected
yardstick numbers are distinct from a tanker's broadcast beacon channel.

Briefing and embedded kneeboards include radio nets, frequencies/modulation,
presets, callsigns, TACAN channel/band/ident, yardstick leader/wingman settings,
ICLS channels and applicable datalink system/frequency. Include flight-specific
labels and switching instructions, generated from the accepted records.

When navigation beacons, yardstick or enabled naval systems are present,
`NAVIGATION-RECEPTION` is a required client criterion. In DCS check TACAN
ident/range, A/A yardstick range, ICLS indications and datalink reception on the
intended modules. Local allocation checks do not certify reception.

Primary references:
[Heatblur F-14 TACAN](https://f14.manuals.heatblur.se/f14ab/systems/nav_com/tacan.html),
[Heatblur F-4E A/A TACAN pairing](https://f4.manuals.heatblur.se/systems/nav_com/tacan.html),
[Heatblur F-14 ICLS controls](https://f14.manuals.heatblur.se/f14ab/cockpit/pilot/right_console.html),
[Heatblur F-14A/B Link-4](https://f14.manuals.heatblur.se/f14ab/systems/nav_com/link4.html),
and [pydcs task serialization](https://github.com/pydcs/dcs/blob/55dc18adbd6907ea17d87de559445c4f9bc39146/dcs/task.py).
