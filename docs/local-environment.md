# Local setup and export

On first use run `dcs-harness init`. Without configured paths it returns BLOCKED
and routes the agent to environment-setup to ask for DCS, Saved Games/DCS and
optional reference directories. Mission start/export and doctor require this
setup. Offline validation/tests/publication checks remain usable without DCS,
including on Linux CI. Setup prompts are handled by the current agent, not by a
blocking stdin prompt inside a machine-readable CLI.

```text
dcs-harness init --dcs-path <installation> --saved-games-path <profile> --reference-root <references> --private-root <private-workspace>
```

Repeat `--reference-root` for multiple collections. A later init can update
individual paths while preserving other settings. The reference list is replaced
when these arguments are supplied. With no configured collections, explicit
`corpus index --source <directory>` remains available.

`.env` stores DCS_HARNESS_DCS_PATH, DCS_HARNESS_SAVED_GAMES_PATH,
DCS_HARNESS_REFERENCE_ROOTS (a JSON list encoded as a dotenv string) and
DCS_HARNESS_PRIVATE_ROOT. Default private storage is a sibling directory named
after the checkout with `-private`; users can choose another location outside it.
The CLI verifies `.env` is Git-ignored and untracked before writing. `.env.example`
contains placeholders only. Reports omit path values. Preserve unrelated dotenv
lines, but load only the four known settings. No shell execution or variable
interpolation occurs; explicit process variables take precedence.

The installation root must contain a recognized DCS executable. Saved Games
must identify a DCS profile; it is a different location from the installation.
Profiles and private workspaces cannot be inside the public checkout. If a path
becomes unavailable, fix the local configuration instead of choosing another
installation/profile silently. Inspect DCS definitions read-only. Never execute
Lua from a reference mission just because the corpus path is trusted.

`corpus index` without `--source` indexes all configured collections into separate
private files. Indexes and mission contents remain outside Git and CI output.

`mission export --run <id>` copies a locally verified artifact to the configured
Saved Games profile's Missions folder. It verifies spec/artifact hashes, the
latest local verification evidence and archive integrity. Revision-required runs
cannot export. A run/hash filename prevents overwrites, identical re-export is
idempotent and a different-file collision blocks. Paths escaping the configured
profile are rejected. Export creates no public release or server deployment;
client/runtime checks still need DCS observations.
