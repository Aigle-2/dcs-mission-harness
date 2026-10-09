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
dcs-harness validate --kind mission|profile|lesson|issue|publication --file <document>
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
