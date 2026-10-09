# Communications and design review

Functional specs use version 1.4. Support aircraft and launch platform, air
defence composition, and victory/failure conditions need recorded user choices.
An explicit request already supplies a choice; an agent's proposal does not.
Features absent from the scenario may be marked not applicable. Ask whether a
comm-plan is wanted. Also review aircraft loadouts and applicable carrier escort
and placement choices; see [mission quality](mission-quality.md).
Pending decisions block `mission spec`. Older specs
cannot continue implementation/verification; create a new run and review them.
The CLI checks records, not the identity of the person supplying them. Agents
must never manufacture approval quotes or treat silence as confirmation.

For an enabled comm-plan, build the radio inventory before choosing frequencies:
each aircraft, each physical radio, compatible bands and modulation, channel
limits, tuning steps and primary source. Distinguish real hardware, the DCS
module and the adapter's verified subset. Then draw a matrix of ordered mission
phases against aircraft/radios. One radio has one active mission net per phase;
presets are stored choices. Record any listening gap during frequency changes.
The inventory and timeline are mandatory in the comm-plan schema. AI support
and ships receive group/unit frequencies, not invented player-radio controls.

`dcs_harness.communications.apply_plan(mission_table, plan)` returns a copy of
an already parsed DCS mission table with group frequencies, ship frequencies,
existing SetFrequency tasks and per-unit presets changed. It preserves other
fields and rejects missing groups, radios, channels or incomplete client coverage.
The source table is not changed on failure. Mission tables can be parsed and
serialized by the mission builder; no archive Lua is executed by this adapter.

The initial preset adapter deliberately verifies only UHF AM 225–399.975 MHz
on radios 1 and 2 of `FA-18C_hornet` and `F-14BU`, on a 25 kHz grid. This is a
common compatible subset, not the full capability of those aircraft. Other
aircraft, bands or preset modes return BLOCKED until implemented with primary
sources and tests. Existing radio tables determine available preset slots.

Sources: [Heatblur ARC-159](https://f14.manuals.heatblur.se/f14ab/systems/nav_com/com/uhf.html),
[Heatblur ARC-182](https://f14.manuals.heatblur.se/f14ab/systems/nav_com/com/vuhf.html),
[F-14 B/U radio controls](https://f14.manuals.heatblur.se/f14bu/cockpit/pilot/left_console.html),
and the [official DCS Hornet guide](https://www.digitalcombatsimulator.com/upload/iblock/8d7/2s3e89jqknz7xmti8hrhe1bjt2uw1s3e/DCS%20FA-18C%20Early%20Access%20Guide%20EN.pdf).
The DCS table representation and first-preset overwrite behavior are described
in [pydcs flyingunit.py](https://github.com/pydcs/dcs/blob/55dc18adbd6907ea17d87de559445c4f9bc39146/dcs/flyingunit.py).

Keep channel 1 on every configured radio consistent with the flight frequency;
DCS can overwrite the first compatible preset. The timeline describes crew
selections during flight; writing presets does not move cockpit selectors or
automate retuning. Brief the required selections. Guard monitoring is distinct
from adding another tactical radio. Combining AWACS and tactical/inter-flight
traffic means sharing one net, rather than duplicating it under another name.

`mission implement` and `mission verify` independently check the registered
archive's presets and frequencies for an enabled plan. They require an optional
read-only table parser, currently pydcs at commit
`55dc18adbd6907ea17d87de559445c4f9bc39146` (LGPL-3.0), in the executing Python
environment. A missing parser returns BLOCKED. The core package and synthetic
unit tests do not depend on pydcs. The spec must include COMM-PRESETS and
COMM-FREQUENCIES local criteria. Connectivity, radio audio, crew selections and
SRS operation require client/runtime checks; local table checks cannot certify them.

## Briefing and kneeboards

Every enabled comm-plan must appear in the DCS briefing and in mission-embedded
kneeboard images for all playable aircraft types. Generate both from the same
accepted plan used to configure radios. Include nets/frequencies in MHz,
modulation, flight/support assignments, per-aircraft preset numbers and the
phase-by-radio schedule, with manual selections and listening gaps. Label each
flight so two flights of the same aircraft type can identify their own presets.
Preserve the existing scenario briefing when adding communications.

Kneeboards are packaged under `KNEEBOARD/<exact-aircraft-type>/IMAGES/` in the
mission ZIP by the current builder. Pages are shared by aircraft type, not an
individual flight, and may cross coalition boundaries. For PvP, review what can
be shared before distributing radio plans this way; do not assume type-specific
pages protect coalition information. The representation is documented in
[pydcs mission.py](https://github.com/pydcs/dcs/blob/55dc18adbd6907ea17d87de559445c4f9bc39146/dcs/mission.py).

Required acceptance criteria for enabled plans:

| Criterion | Level | Evidence |
| --- | --- | --- |
| COMM-BRIEFING | local | Read the saved mission's briefing fields and referenced localization dictionary; compare the visible comm-plan with the accepted plan. An unattached sidecar document is insufficient. |
| COMM-KNEEBOARD | local | Inspect the actual rendered images, record their hashes, verify all playable aircraft types have the intended pages inside the ZIP, and compare text/tables with the accepted plan. Check font size, clipping and multipage completeness. Filenames alone are insufficient. |
| COMM-DOCS-VISIBLE | client | Open the briefing and kneeboard in DCS for each playable module; confirm readability, correct flight labels and matching presets/phase selections. |

The schema enforces these criteria's presence and levels. The implementing agent
must execute the artifact/content checks and provide hash-bound evidence; the
radio adapter itself does not render or validate kneeboard image contents.
Local image inspection does not certify in-cockpit display.
