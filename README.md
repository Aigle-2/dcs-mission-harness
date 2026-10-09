# DCS Mission Harness

Portable tooling for agents creating DCS multiplayer missions. MIT licensed.
The same CLI, contracts and evidence levels work with Codex, Claude Code and
OpenCode. This initial version builds the local validation and privacy foundation.

## Quick start

Requires Python 3.11+ and uv. GitHub commands also require an authenticated gh.

```text
uv sync --locked
uv run dcs-harness validate --kind mission --file examples/mission.yaml --profile examples/profile.yaml
uv run dcs-harness test
uv run dcs-harness issues create --repo owner/repository --file examples/issue.yaml
```

The issue command previews a structured body without posting. To post an issue
authorized by the human request, use the same command with `--publish`.

Reports are JSON with schema_version, operation and status. Exit codes: 0 PASS,
2 FAIL, 3 BLOCKED. Local/archive success never claims DCS runtime success.

## Private workspace

Set DCS_HARNESS_PRIVATE_ROOT in the current shell to a dedicated directory
outside this repository. Example PowerShell using a path you choose:

```powershell
$env:DCS_HARNESS_PRIVATE_ROOT = '<private-workspace>'
```

Never store credentials there as tracked project data. Use session credentials
or a secret manager. See [publication boundaries](docs/privacy.md).

## Implemented commands

```text
dcs-harness doctor
dcs-harness validate --kind mission|profile|lesson|issue|publication|functional-spec|verification|comm-plan|navigation --file <document>
dcs-harness validate --kind mission --file <document> --profile <profile>
dcs-harness miz check --file <mission.miz>
dcs-harness lua check --file <script.lua>
dcs-harness corpus index --source <reference-directory>
dcs-harness lessons ingest --file <lesson.yaml>
dcs-harness lessons compact --check
dcs-harness issues list --repo owner/repository
dcs-harness issues read --repo owner/repository --number 42
dcs-harness issues draft --file <issue.yaml>
dcs-harness issues create --repo owner/repository --file <issue.yaml> [--publish]
dcs-harness publish check --tracked --history
dcs-harness publish check --candidate <candidate-directory>
dcs-harness publish export --candidate <candidate-directory> --destination <new-directory>
dcs-harness test
```

## Specification, implementation and verification

Set the private workspace, then use these commands from the checkout:

```text
dcs-harness mission start --run synthetic-training --brief-file <private-brief.md>
dcs-harness mission review --run synthetic-training --file <private-functional-spec.yaml>
dcs-harness mission spec --run synthetic-training --file <private-functional-spec.yaml>
dcs-harness mission implement --run synthetic-training --artifact <built-mission.miz>
dcs-harness mission verify --run synthetic-training --file <private-verification.json>
dcs-harness mission status --run synthetic-training
```

Start returns `next_skill: mission-functional-spec`. The current coding agent
reads that skill and produces the functional spec before building the mission;
the CLI does not launch an LLM or contain a general mission generator. See the
synthetic functional-spec example. Unresolved questions block implementation.
In the final readable spec, agent-selected and delegated choices use `[Proposed]`;
user-supplied/confirmed choices use `[Decided]`. Additional parameter decisions
are recorded as `parameter:<slug>` topics and block registration until confirmed.
`mission review` generates a private labeled appendix without accepting the spec.
Functional-spec version 1.6 requires user decisions on communications,
support aircraft/launch platform, air defence and victory conditions. Proposed
choices block the transition. For a comm-plan, first list each radio's compatible
bands, then show active frequencies over mission phases. The implementation
adapter changes presets and flight/support frequencies and checks the archive.
See [communications](docs/communications.md) for supported aircraft and limits.
Review aircraft composition/loadouts and, when present, carrier escorts and
placement. Default AI to veteran (`High`). Mandatory configuration criteria cover
installed unit IDs, loadouts, AI skills and relevant naval/AWACS configuration;
see [mission quality](docs/mission-quality.md) for verification requirements.
Offer aircraft liveries by flight or unit, or keep defaults. Record the answer;
unanswered choices block spec registration. Verify selected IDs and client visibility.
AWACS/tanker entries explicitly define cruise and mission altitudes and orbit
areas; tankers also define model, refueling system and receiver types. Proposed
support profiles block spec registration until reviewed.
Enabled comm-plans must also be included in the in-game briefing and embedded
kneeboards, with mandatory local content checks and client readability checks.
Navigation records TACAN, yardstick, flight callsigns and applicable naval
ICLS/datalink; comm-plan 1.1 embeds the same record for briefing/kneeboards.
See [navigation](docs/navigation.md) for conventions and validation boundaries.
Earlier specs need review in a new run before further work.
Keep the source artifact outside the run's reserved `mission.miz` destination.

Accepted specs and registered archives have immutable hashes. Evidence must
cover every criterion once and match both hashes. Verification retries keep
their history. After an artifact or accepted spec changes, start a new run.
`LOCAL_VERIFIED` means local criteria passed; overall mission validation remains
`INCONCLUSIVE` until actual DCS tests. This version has no runtime evidence
adapter and rejects runtime/client PASS claims.

Corpus indexing and draft/lesson writes require the private workspace and never
overwrite existing artifacts. Doctor reports optional missing capabilities such
as Lua 5.1 syntax compilation. The local suite runs without DCS or cloud access.

## Agents and skills

Launch an agent from the repository root. Codex/OpenCode discover the canonical
skill in .agents/skills; Claude discovers the generated .claude/skills copy.
Edit the canonical source, then run `uv run python tools/sync_skills.py`.
CI checks both copies remain identical. See AGENTS.md and
[GitHub structured issues](.agents/skills/github-structured-issues/SKILL.md).

## Development

```text
uv run python -m unittest discover -s tests -v
uv run python tools/sync_skills.py --check
uv run dcs-harness publish check --tracked --history
```

The CI matrix covers Windows/Linux and Python 3.11/3.12 using synthetic data.
Do not commit actual mission archives or private test results. Dependency
licenses remain separate; this repository does not bundle MOOSE, Skynet or SRS.

Mission generation, OVH lifecycle automation, runtime instrumentation and client
tests are the next slices. Current capabilities and limits are documented in
[architecture](docs/architecture.md). No DCS mission is claimed runtime-tested.
