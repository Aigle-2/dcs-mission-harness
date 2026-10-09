# Publication boundary

Private by default: personal/reference missions, player identities, private
endpoints, credentials, source paths, recordings, raw logs and lessons learned
from those inputs. Keep them under DCS_HARNESS_PRIVATE_ROOT outside the checkout.
Do not use the home directory or the repository as the private root.
Local installation/profile/reference paths are saved in the checkout's ignored,
untracked `.env` as an explicit configuration exception. Do not commit that file;
`.env.example` contains placeholders only. Local mission export writes to the
configured Saved Games profile, not a public release.

Public content needs explicit selection, review and redistribution rights.
Technical validation and publication approval are separate. Scanners cannot
detect every private hostname, contextual fact, obfuscated secret or identity.
Their PASS means no supported detector triggered, not a privacy guarantee.

`publish check --tracked --history` checks the working content and reachable
Git history, including commit/tag messages. It rejects unknown/binary content
requiring review and reports only detector codes, locations and object IDs.
It does not upload anything. Scan before push: CI cannot prevent a first leak.
Git-ignore and Git LFS do not protect content already tracked or published.

For release artifacts create a candidate folder with publication.json:

```json
{
  "schema_version": "1.0",
  "classification": "public-approved",
  "files": [
    {
      "path": "guide.md",
      "sha256": "<64 hexadecimal characters>",
      "license": "MIT",
      "classification": "public-approved"
    }
  ]
}
```

Every file must be listed and match its approved hash. Paths cannot escape the
candidate directory. Text is scanned; ZIP/MIZ members are inspected recursively
under size/depth limits. Media, encrypted content and unsupported encodings
block publication. v0.1 has no automatic approval bypass for such files.
Structured JSON/YAML documents must themselves be marked public-approved.

Use `publish export` to create a new checked folder. Review that exact export
before uploading it, including private hostnames and contextual details that
generic detection cannot identify. The tool does not automatically redact data:
redaction without context can destroy useful evidence or miss a disclosure.

Public CI uses only synthetic fixtures, no cloud credentials. Real DCS runs
will remain private and export an aggregated report. CI output, issue/PR text,
release descriptions, screenshots and links are part of the publication surface.
