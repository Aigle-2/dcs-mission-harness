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

Write `functional-spec.yaml` plus a readable `functional-spec.md` in the user's
language. Define purpose, intended player experience, progression, success and
failure conditions, constraints, declared assumptions and unresolved questions.
Include the mission's map, multiplayer slots, departures, objectives and
integration requirements. Keep implementation details for the implementation
step except where they express a real player requirement.

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

Record non-blocking implementation defaults as assumptions. If an answer is
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
If the user requested only a spec, finish after the spec. Public examples must
be synthetic, selected and checked separately from private run artifacts.
