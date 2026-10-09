---
name: mission-export
description: Export a locally verified DCS mission into the user's configured Saved Games/DCS/Missions folder for local use or DCS validation, preserving existing files.
---

# Local mission export

Use when the user requests a local export or when an authorized mission creation
workflow is ready to deliver its verified mission for DCS testing.
Read docs/local-environment.md. If setup is missing, use environment-setup and ask
for the profile path; do not guess a destination.

Run `dcs-harness mission export --run <id>` from the harness checkout. Export
requires LOCAL_VERIFIED, unchanged accepted spec/artifact, matching verification
evidence, archive integrity, and no recorded revision requirement. Unreviewed
proposals or failed checks must be resolved first; do not edit state to bypass them.

The CLI copies to the configured profile's Missions folder using a run/hash
filename. It never overwrites an existing different file. Re-exporting identical
bytes is idempotent. Keep the source and private evidence; export does not alter
the accepted run. A mission may be exported for client/runtime testing while
those checks remain pending; do not describe this as DCS validation success.

Tell the user which filename to open and give the private runtime/client checklist.
No public GitHub release, server upload or paid provisioning is implied by local
export. Personal archives and local paths must stay outside public artifacts.
