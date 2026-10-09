# Mission configuration and DCS feedback

Functional-spec 1.7 includes recorded date/era, aircraft/loadout, battlegroup and placement
decisions, explicit carrier/AWACS presence and an AI skill policy. Proposed choices
block registration. Carrier choices cannot be marked inapplicable when a carrier
is present. Aircraft/loadout review is mandatory, including for unarmed training.
Veteran means `High` under harness policy; user overrides require a user source.
Old runs remain historical; use a new run to review and implement a revision.

## Calendar date and historical availability

Initial design asks for year/month/day and separately whether the year restricts
aircraft and armaments. `temporal` records the quoted ISO date, `restrict_by_year`,
status, source and evidence. Both choices appear in the readable review; proposed
choices block registration. Dates are checked as real calendar dates, including
leap years. Never infer a historical policy from the year alone.

Always include local criterion `MISSION-DATE`: inspect the final archive's saved
calendar date and compare it to the accepted spec, independently of start time.
If `restrict_by_year` is true, include local `ERA-AVAILABILITY`. Keep a private
table of exact aircraft variants and weapons, operators/countries, availability
at the selected date, sources and any user-approved exceptions. Include player,
hostile and support aircraft and applicable rearm stock. Catalog availability or
presence in installed module code proves DCS compatibility, not historical use.
Unknown or conflicting availability requires source research or user clarification;
do not invent dates, silently substitute equipment or mark an unknown check PASS.
Record reviewed exceptions as `parameter:era-exception-<slug>` decisions.

Verify the target editor/server's actual year filters and inventory behavior when
applicable; a mission date alone is not evidence of enforcement. The harness has
no universal historical catalog or automatic era filter. The agent implements
the accepted limits and supplies hash-bound evidence; runtime rearm enforcement,
when required, needs a separate runtime/client criterion. When restrictions are
off, module compatibility still applies. New mandatory fields require old specs
to be reviewed under 1.7 before continuing; do not invent retrospective approval.

## Visible decision provenance

The final readable spec labels mission choices `[Proposed]` for agent proposals
and `[Decided]` for explicit user choices/confirmation. Delegation authorizes
preparing a proposal, not approving the resulting value. Include each delegated
setting's actual value in the spec and collect review of those choices before
implementation. Features outside the scenario use `[NotApplicable]`.

`design_decisions` accepts the six mandatory topics plus unique
`parameter:<slug>` topics for other mission parameters. Examples include weather,
timing, port and trigger distance. Agent-selected mission defaults also belong
here unless explicitly preapproved. All proposed entries block `mission spec`;
confirmed entries require a user source and actual evidence. After confirmation,
show `[Decided]` and retain the earlier proposal in private revision history.
An explicit approval of the complete presented spec can confirm its displayed
proposals together; record the reviewed revision and do not extend approval to
subsequent edits or ask again for unchanged, already confirmed choices.
Technical implementation details that do not change mission design can remain
assumptions; that is not a way to conceal a mission-setting proposal.

`mission review --run <id> --file <spec>` writes a private
`functional-spec.review.md` appendix with derived tags, choices, sources and
evidence for design topics, date/era, navigation, support profiles, communications and liveries.
Include the appendix in the final readable spec alongside full plan details.
Review generation can run with proposed choices, leaves the run in
SPECIFICATION_PENDING, and does not imply acceptance or a human reply. The
command preserves numbered appendices under the private run's `reviews/` folder.
The schema checks the records, not their truth; the agent must keep every selected
mission parameter represented and never manufacture confirmation evidence.

Offer aircraft livery selection, including keeping defaults. The `liveries`
record stores pending/default/custom, user source and evidence. Here custom
means user-selected, including built-in skins; it does not require an external
skin. Custom selections name group, exact aircraft variant, optional unit and
actual livery ID. Apply group selections first, then explicit unit overrides;
leave other aircraft on defaults. Reject ambiguous duplicate targets. Verify
the selected livery is available for the aircraft/country on target installations,
and describe any external-skin client dependency. An unavailable selection is
BLOCKED until resolved, not permission to silently substitute a different skin.
Keep personal assets and source paths private.

`support_flights` explicitly lists every requested AWACS and tanker. Each entry
records group, exact aircraft type, cruise/transit altitude, mission/on-station
altitude and orbit area. Altitudes contain a numeric value, ft or m, and MSL
reference; convert to DCS meters/BARO during implementation. A circle records
center coordinates and desired radius in nautical miles; a racetrack records two
distinct geographic endpoints. Coordinates use decimal latitude/longitude, to
convert through the chosen theatre projection. A desired circle radius is a
functional requirement to verify, not a claim that DCS Orbit exposes a radius
parameter. If an adapter cannot realize a requirement, report BLOCKED and review
an alternative instead of silently dropping it.

Tankers also require a refueling system (boom or probe/drogue) and receiver types.
Verify the selected tanker variant and receivers' compatibility in the installed
modules; the schema checks completeness, not aircraft capabilities. Proposed
support entries block registration, and confirmed entries require a user source.
AWACS presence must agree with the support list. For other flights, describe
cruise and mission altitude profiles in the functional spec's flow and constraints.

The schema requires relevant local criteria. It validates specification records,
not the truth of approval evidence or the resulting aircraft configuration.
The implementing agent must write reproducible checks against the saved mission
table and submit hash-bound evidence. Archive integrity alone is insufficient.

| Local criterion | Check in the saved artifact |
| --- | --- |
| UNIT-TYPES | Every aircraft, ship, vehicle and static type matches a catalog verified for the target installation; record source/version/hash privately. Unknown types are BLOCKED, invalid types FAIL. |
| AIRCRAFT-LOADOUTS | Every flight has the reviewed variant, count, roles, per-station CLSIDs, fuel and countermeasures. Verify pylon compatibility against the installed module. Empty pylons pass only when reviewed as clean. |
| AIRCRAFT-LIVERIES | Compare saved per-unit livery IDs/defaults with the reviewed selections, including unit overrides; verify aircraft/country and installed skin availability. |
| AI-SKILL | Compare every AI unit with the default `High` or its reviewed override; preserve Client/Player skills. |
| NAVIGATION | Compare saved TACAN/ICLS/datalink tasks and resolved callsigns with the reviewed navigation plan; verify module capability and yardstick crew instructions. See [navigation](navigation.md). |
| CARRIER-GROUP | Match reviewed escort types/counts, coalition, spacing and route behavior; a solo carrier requires an explicit user choice. |
| CARRIER-PLACEMENT | Match reviewed start area, distance, route and heading. Check water/coast clearance using available terrain data or mark that part pending DCS inspection. |
| AWACS-ORBIT | Verify launch platform, climb route, station waypoint and nested Orbit task, altitude/reference, speed units, pattern and racetrack geometry against the reviewed plan. |
| SUPPORT-FLIGHT-PROFILES | For every AWACS/tanker, compare saved type, transit and station altitudes, orbit area/geometry and task against its support entry; verify tanker system/receiver compatibility. |

Read installed definitions and reference mission tables without executing their
Lua. A pinned generator catalog may still contain stale identifiers. Treat aircraft
names and variants distinctly. At station an Orbit task may be nested inside a
WrappedAction inside a ComboTask; waypoint type itself can remain Turning Point.
Check the route and task together. Do not infer an AWACS's station altitude from
its deck/runway starting altitude or assume every reference uses the same height.

Client/runtime checks cover valid slot loading, visible payloads, launch and deck
traffic, carrier/escort navigation, AWACS climb and stable station flight, combat,
radio audio and victory behavior. Keep them pending until observed in DCS.
For user-selected liveries, `LIVERIES-VISIBLE` is a required client criterion:
check the appearance on participating clients. A saved ID cannot prove that a
client has the required textures. The CLI checks choice/criterion records;
the implementing agent performs the artifact and installation checks.

When a user reports a defect, retain the existing artifact and verification
history. Record feedback privately, identify the affected criterion, reproduce
the defect locally when possible and create a new run for changed approved
specifications. Keep unresolved choices open. Convert generalizable findings
into focused skill rules and regression checks; ingest a bounded private lesson
candidate rather than appending raw mission reports to shared instructions.
