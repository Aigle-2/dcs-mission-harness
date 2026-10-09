"""Allowlisted, hash-bound publication candidates. This does not upload."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .core import HarnessError, load_document, require_valid, result
from .privacy import scan_bytes, safe_archive_name


def checked_content(candidate: Path) -> tuple[dict, dict[str, bytes], list[dict]]:
    if candidate.is_symlink():
        raise HarnessError("CANDIDATE_SYMLINK_FORBIDDEN")
    manifest = load_document(candidate / "publication.json")
    require_valid("publication", manifest)
    names, folded_names, contents, findings = set(), set(), {}, []
    for item in manifest["files"]:
        name = item["path"]
        if not safe_archive_name(name) or name.casefold() in folded_names or name.casefold() == "publication.json":
            raise HarnessError("UNSAFE_OR_DUPLICATE_PUBLICATION_PATH")
        names.add(name)
        folded_names.add(name.casefold())
        path = candidate / name
        if path.is_symlink() or not path.resolve().is_relative_to(candidate.resolve()):
            raise HarnessError("PUBLICATION_PATH_ESCAPE")
        if path.stat().st_size > 8 * 1024 * 1024:
            findings.append({"code": "FILE_REVIEW_REQUIRED"})
            continue
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            findings.append({"code": "PUBLICATION_HASH_MISMATCH"})
        findings.extend(scan_bytes(name, content))
        if Path(name).suffix in {".json", ".yaml", ".yml"}:
            document = load_document(path)
            if document.get("classification") != "public-approved":
                findings.append({"code": "DOCUMENT_NOT_PUBLIC_APPROVED"})
        contents[name] = content
    for path in candidate.rglob("*"):
        if path.is_symlink():
            findings.append({"code": "SYMLINK_FORBIDDEN"})
        elif path.is_file() and path.relative_to(candidate).as_posix() not in names | {"publication.json"}:
            findings.append({"code": "UNLISTED_PUBLICATION_FILE"})
    findings.extend(scan_bytes("publication.json", (candidate / "publication.json").read_bytes()))
    return manifest, contents, findings


def check(candidate: Path) -> dict:
    _, contents, findings = checked_content(candidate)
    return result("FAIL" if findings else "PASS", "publish.check", files=len(contents), findings=findings)


def export(candidate: Path, destination: Path) -> dict:
    manifest, contents, findings = checked_content(candidate)
    if findings:
        return result("FAIL", "publish.export", findings=findings)
    if destination.exists():
        raise HarnessError("EXPORT_DESTINATION_EXISTS")
    destination.mkdir(parents=True)
    for name, content in contents.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (destination / "publication.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result("PASS", "publish.export", files=len(contents), uploaded=False)
