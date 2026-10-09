# Mission configuration and DCS feedback

Functional-spec 1.3 includes recorded aircraft/loadout, battlegroup and placement
decisions, explicit carrier/AWACS presence and an AI skill policy. Proposed choices
block registration. Carrier choices cannot be marked inapplicable when a carrier
is present. Aircraft/loadout review is mandatory, including for unarmed training.
Veteran means `High` under harness policy; user overrides require a user source.
Old runs remain historical; use a new run to review and implement a revision.

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
| AI-SKILL | Compare every AI unit with the default `High` or its reviewed override; preserve Client/Player skills. |
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

When a user reports a defect, retain the existing artifact and verification
history. Record feedback privately, identify the affected criterion, reproduce
the defect locally when possible and create a new run for changed approved
specifications. Keep unresolved choices open. Convert generalizable findings
into focused skill rules and regression checks; ingest a bounded private lesson
candidate rather than appending raw mission reports to shared instructions.
