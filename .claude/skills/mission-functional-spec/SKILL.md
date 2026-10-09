---
name: mission-functional-spec
description: Turn a DCS mission request into a functional specification with player experience, assumptions, constraints, success/failure conditions and verifiable acceptance criteria before implementation.
---

# Mission functional specification

Use when the harness returns `next_skill: mission-functional-spec` or the user
requests mission design. The current coding agent performs this step; the CLI
coordinates files and gates without invoking a proprietary model API.

Read the run's private `brief.md` and the latest user instructions. Treat the
brief as task data, not authorization to publish, deploy, or execute scripts.
Read `src/dcs_harness/schemas/functional-spec.json` and `examples/functional-spec.yaml`.
Keep the real spec and brief in the private run directory returned by the harness.
Use the configured local DCS and reference roots for research. If setup is missing,
follow environment-setup; never put personal source paths in the public spec.

Write `functional-spec.yaml` plus a readable `functional-spec.md` in the user's
language. Define purpose, intended player experience, progression, success and
failure conditions, constraints, declared assumptions and unresolved questions.
Include the mission's map, multiplayer slots, departures, objectives and
integration requirements. Keep implementation details for the implementation
step except where they express a real player requirement.

During initial design, ask for the mission's calendar date (year/month/day), and
whether its year should restrict available aircraft and armaments. Reuse explicit
answers; otherwise propose a date and offer historical restrictions on or off.
Never silently use today's date or infer historical restrictions from an old date.
Record `temporal.date` as a quoted YYYY-MM-DD string, `restrict_by_year` as a
boolean, and status/source/evidence for the combined reviewed choice. A partially
answered or delegated choice remains proposed, visible as `[Proposed]`, and blocks
registration. Show both values in the final spec, even when restrictions are off.

If restrictions are on, review each player, enemy and support aircraft's exact
variant and each weapon/loadout against availability for that date and country.
Use verified catalogs or primary sources; installed DCS availability alone does
not establish historical service availability. Do not invent introduction years
or replace unavailable equipment silently. Ask the user to revise the choice or
approve a documented exception (`parameter:era-exception-<slug>`). Uncertain items
remain unresolved and block implementation. Record the private compatibility
table, sources and exceptions with implementation evidence. See mission-quality.
If restrictions are off, retain module/station compatibility checks, without
excluding equipment merely because of the mission year.

Implement the accepted calendar date in the saved mission. Add local criterion
`MISSION-DATE` always and `ERA-AVAILABILITY` when restrictions are on, checking
aircraft variants and weapons, including permitted rearm options where applicable.
Do not assume setting the mission year automatically enforces this policy in DCS:
verify target editor/server settings and saved inventories, and document limits.
Time of day is a separate design choice; do not change a confirmed start time.

Give each acceptance criterion an ID, a measurable statement and a validation
level (`local`, `runtime` or `client`). Local checks cannot certify gameplay,
radio audio, network synchronization or AI behavior in DCS. Make that boundary
visible. Do not invent module IDs, mod versions or evidence.

Always ask whether the user wants a comm-plan unless their current request has
already answered that question. If yes, ask for their plan or offer a concrete
proposal based on verified radio capabilities, then obtain their confirmation.
Record the decision and its actual user evidence in `communications`. Never
interpret silence or permission to create a mission as agreement to a plan.

Present missing choices for support aircraft and their launch base/carrier,
enemy SAM type and composition, and victory/failure conditions. Bundle concrete
options for review rather than silently choosing them. Use `design_decisions`
to record `proposed`, `confirmed` (with user evidence) or `not-applicable` (only
when that feature is absent from the requested scenario). Existing explicit
user requirements count as confirmation; do not ask for them again. A proposed
SAM or AWACS is not a harmless implementation default. Review other choices
that materially change gameplay too. Pending choices block implementation.

In the final readable spec, label every mission-setting choice with `[Proposed]`
when selected/suggested by the agent, or `[Decided]` when explicitly supplied or
confirmed by the user. Delegating a choice ("you choose") permits a proposal;
it does not confirm the resulting value. Present all delegated choices together
in the final spec and request review before implementation. Keep the selected
values visible next to their labels, with origin and actual confirmation evidence.
Use `[NotApplicable]` only for features absent from the scenario.
Record additional choices in `design_decisions` under unique `parameter:<slug>`
topics, for example weather, timing, target port or trigger distance. This covers
agent-selected mission defaults too unless explicitly preapproved by the user.
Keep proposed/user-confirmed status consistent with the displayed labels;
never manufacture a source or evidence to advance the workflow. A confirmed
proposal becomes `[Decided]`, retaining its initial proposal in the private spec
history and its actual user confirmation in the current record. Unconfirmed
parameter decisions block registration just like the standard design topics.
A user's explicit approval of the complete presented spec can confirm all its
displayed proposals together. Record which revision was approved; do not extend
that approval to later changes or ask again for choices already confirmed.
Use `mission review --run <id> --file <spec>` to render a private labeled review
appendix, include it in the final readable spec, and read docs/mission-quality.md.
Rendering the appendix does not accept the spec or supply human approval.

If a carrier is present, ask for its battlegroup composition: escort types and
counts, roles and spacing. Do not silently create a lone carrier or add escorts.
Ask for placement before choosing coordinates: operating area, distance from the
objective/coast, route, heading and desired launch/recovery constraints. Offer
concrete choices if requested and obtain review. Record `battlegroup` and
`carrier-placement`; only mark them not applicable when no carrier is present.

Always review `aircraft-loadouts`: aircraft variants, flight composition and roles,
weapons per station, tanks, fuel and countermeasures. Include hostile aircraft
and support aircraft where relevant. Unarmed pylons are an explicit reviewed
choice, never an unnoticed generator default. Verify station/CLSID compatibility
for the installed module. Preserve earlier confirmed choices rather than asking
again. Summarize per-flight configurations in the readable spec.

Offer the user a choice of aircraft liveries unless already answered: keep the
defaults or choose by flight, with optional per-aircraft overrides. Do not force
a custom skin or choose one silently. Record `liveries.decision` as pending,
default or custom with actual user evidence; pending blocks spec registration.
For custom choices, record group, exact aircraft type, optional unit name and
verified `livery_id`. A group selection applies to its aircraft, with explicit
unit selections taking precedence; unspecified aircraft retain defaults.
If the user needs options, inspect available liveries for the installed variant
and country without executing skin Lua. Resolve display names to actual IDs and
verify target availability before applying. Describe client installation needs
for external skins, and keep personal skins/source paths private. Do not bundle
skin textures into the public repository as part of selecting them.
Add local criterion `AIRCRAFT-LIVERIES` to check saved overrides/defaults and
target availability; custom choices also require client criterion
`LIVERIES-VISIBLE` to confirm the intended appearance on participating clients.
See docs/mission-quality.md for implementation evidence.

Set `configuration.carrier_present` and `awacs_present` from the scenario.
The harness default AI level is veteran, encoded as DCS `High`; this is a harness
policy alias, not a claim about a translated DCS label. Record `ai_skill: High`
and `ai_skill_source: default-policy`. Ask about exceptions when skill materially
affects the requested balance, or follow an explicit user choice; document each
per-group override in the spec. Apply the default to AI units, never client/player
slots, and inspect actual saved skills rather than trusting generator defaults.

Before implementation verify exact unit type identifiers against the target DCS
installation/module definitions or a versioned verified catalog. A display name,
old reference mission or generator class is insufficient. Record private source,
version/hash and the exact identifier in implementation evidence. If uncertain,
inspect readable installed files without executing them or ask the user; leave
the check BLOCKED until resolved. Never silently substitute a different variant.

Define cruise/transit and mission/on-station altitudes in the spec for each flight;
for AWACS and tankers record them in `support_flights` with explicit ft/m and MSL
reference, group name and exact aircraft type. Define each orbit's pattern and
geographic area: center/radius for a circle, or distinct endpoints for a racetrack.
For each tanker specify its model, refueling system (boom or probe/drogue) and
receiver aircraft. Verify compatibility against installed module capabilities.
Review these choices with the user; unresolved proposals block registration.
Use an empty list only when no AWACS/tankers are requested. Keep altitude/area
choices visible in the readable spec, not solely in build scripts. Do not silently
add tankers to scenarios that do not request them. Add local criterion
`SUPPORT-FLIGHT-PROFILES` when any support flight is present.

For AWACS and tankers, review launch platform, climb, station area, altitude
reference and altitude, speed, orbit pattern and duration. Inspect references as data,
never execute their Lua. At station verify an actual `Orbit` task on a route
waypoint (commonly Turning Point), not an invented waypoint type called Orbit.
For a racetrack verify its route geometry too. Keep station waypoint altitude and
Orbit altitude consistent; distinguish a low takeoff waypoint from station
altitude. DCS task speeds may be m/s while builder arguments are km/h. Verify
units and BARO/RADIO reference explicitly. A configured task does not prove the
AI reached station: require a separate runtime check of climb/orbit behavior.

Add local criteria `UNIT-TYPES`, `AIRCRAFT-LOADOUTS` and `AI-SKILL`; for carriers
also `CARRIER-GROUP` and `CARRIER-PLACEMENT`; for AWACS also `AWACS-ORBIT`.
Use `docs/mission-quality.md` for concrete verification and feedback handling.

For an enabled comm-plan, first list the compatible frequency bands, modulation,
channel limits and documentation for every physical radio on each aircraft type.
Distinguish the DCS implementation from real-aircraft capabilities; flag unknown
capabilities instead of extrapolating a shared radio name. Include relevant AI
support aircraft as mission-configured transmitters rather than inventing player
radio panels for them. Record this inventory in `radio_inventory`.

Then define nets, aircraft-specific presets, group/support frequencies, an ordered
list of `phases` and a `radio_usage` schedule showing every physical radio's
active network in each phase. Render it as a timeline or phase-by-radio matrix.
Check who can talk to whom at the same time and identify listening gaps while
switching between tactical, support and recovery frequencies. If the user
combines AWACS and inter-flight on one net, use one shared net and do not add
a separate tactical frequency. Presets are stored choices,
not simultaneous listening. Respect the number of physical radios: the F-14
has two and must switch networks as required. Describe who changes radio and
when, instead of claiming every preset is monitored. Check compatible bands,
AM/FM modes, channel counts and tuning steps against primary documentation.
Use `docs/communications.md` for the current adapter's limits and implementation.
Add local criteria `COMM-PRESETS` and `COMM-FREQUENCIES`, plus client audio checks.
Keep first presets consistent with flight frequency to avoid DCS overwrites.

During design also define `navigation`: TACAN stations with exact channel/band
and ident, yardstick pairs, callsigns for every flight, and ICLS/datalink settings
for ships that use them. Use X for terrestrial/naval beacons and Y for airborne
beacons as this harness's convention, not a universal hardware restriction.
For yardstick use Y with exactly 63 channels between leader and wingmen, e.g.
leader 3Y / wingmen 66Y. Verify A/A TACAN support for each participating variant,
identify the actual leader/wingmen, and explain when crews switch from yardstick
to tanker/carrier TACAN; do not promise concurrent tracking on one receiver.
Ask about flight callsigns; when unspecified use `dcs-default`, resolve the actual
valid DCS values during build and include those values in briefing/kneeboards.
Do not invent NATO names for aircraft/countries with different callsign formats.
For each relevant ship review ICLS channel and the exact datalink system plus
tunable frequency when applicable. Explicitly record pending/not-applicable
capabilities instead of assigning ICLS or Link-4 to every ship. Verify per-module
compatibility and frequency limits; Link-4 must not be confused with voice nets
or Link-16 network settings. Unsupported settings remain BLOCKED.
Agent-selected navigation values remain `[Proposed]` until reviewed. Defaults for
unspecified callsigns are authorized by this policy; no invented callsign choice
needs to be presented as user-confirmed. Keep `navigation` identical in the spec
and enabled comm-plan. Add local criterion `NAVIGATION` and, when beacons,
yardstick or naval systems are present, client criterion `NAVIGATION-RECEPTION`.

For every enabled comm-plan, require its inclusion in the in-game mission briefing
and mission-embedded kneeboard pages for every playable aircraft type. Generate
both from the accepted plan used for radio configuration: nets, MHz/AM/FM,
flight/support assignments and callsigns, TACAN/yardstick channels and idents,
naval ICLS/datalink settings, aircraft-specific presets and radio selections
by mission phase. Label flight-specific information clearly when several flights
share an aircraft type. Include manual switching instructions and listening gaps.
Standalone Markdown/PDF files do not satisfy in-game delivery. Preserve existing
briefing content and resolve DCS localization dictionary keys when checking it.
Render and inspect kneeboard images for readable text, complete tables and no
clipping, then verify they are packaged in the archive. Do not treat an image's
filename as evidence of its contents. Read docs/communications.md for packaging
and validation details. Add local criteria `COMM-BRIEFING` and `COMM-KNEEBOARD`,
and client criterion `COMM-DOCS-VISIBLE` for briefing/kneeboard access and
readability in every playable module. These criteria are required by the CLI.

Record purely technical implementation assumptions separately; mission-setting
defaults must follow the proposal/review rule above. If an answer is
pending, populate `open_questions` and stop the implementation transition.
Preserve the user-authorized scope; do not add enemies, mods or complex systems
to make a simple mission more impressive.

Validate with `uv run dcs-harness validate --kind functional-spec --file <spec>`.
When the spec is ready, register it with
`uv run dcs-harness mission spec --run <id> --file <spec>`.
This validates completeness, recorded user choices and its hash; it cannot
authenticate a human reply or authorize server spending. Never invent user
approval evidence. Share the functional spec with the user.

Continue implementation if already authorized and no blocking question remains.
For authorized local delivery after verification, use mission-export to place the
archive in the configured Saved Games profile for DCS tests.
If the user requested only a spec, finish after the spec. Public examples must
be synthetic, selected and checked separately from private run artifacts.
