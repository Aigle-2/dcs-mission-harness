---
name: environment-setup
description: Configure a DCS mission harness on first use by collecting local DCS, Saved Games and reference mission paths and saving them privately in an ignored dotenv file.
---

# First-run environment setup

Use when `dcs-harness init`, `doctor` or mission creation reports
`LOCAL_SETUP_REQUIRED`. Read docs/local-environment.md.

Ask for the DCS installation root (containing bin/DCS.exe or bin-mt/DCS.exe)
and the actual Saved Games/DCS profile. Also offer one or more reference mission
directories; users can add other collections beyond Saved Games missions.
Use already supplied paths without asking again. Detected paths may be proposed
to help the user, but do not silently select a profile or installation.

Run `dcs-harness init --dcs-path <root> --saved-games-path <profile>` with repeated
`--reference-root <directory>` arguments and optional `--private-root <directory>`.
The CLI validates paths and verifies `.env` is ignored and untracked before saving.
Paths are local private data: never paste values into tracked docs, issues or CI.
Use `.env.example` only as a placeholder template. Do not source or execute dotenv.

Subsequent CLI calls load the known settings automatically; process environment
overrides remain possible. If a location changes or becomes unavailable, ask only
for the missing/corrected value. `corpus index` without `--source` reads configured
reference roots and writes private indexes. Read reference Lua as data only.
For module investigation use the configured DCS root; never modify installed code.

Finish by reporting configuration success without echoing private values into
public output. Setup does not deploy a server or certify a mission in DCS.
