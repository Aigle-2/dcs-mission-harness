"""Read-only archive inspection. Never evaluate embedded Lua."""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from .core import HarnessError, result, write_new
from .privacy import MAX_ARCHIVE, MAX_FILE, safe_archive_name


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def inspect_miz(path: Path) -> dict:
    failures, scripts, theatre = [], [], None
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_ARCHIVE:
                raise HarnessError("ARCHIVE_BUDGET_EXCEEDED", "BLOCKED")
            names = [e.filename for e in entries]
            if len(set(names)) != len(names):
                failures.append({"code": "DUPLICATE_ARCHIVE_MEMBER"})
            for entry in entries:
                if not safe_archive_name(entry.filename) or entry.flag_bits & 1:
                    failures.append({"code": "UNSAFE_ARCHIVE_MEMBER"})
                if entry.file_size > MAX_FILE:
                    failures.append({"code": "ARCHIVE_MEMBER_TOO_LARGE"})
            if failures:
                status = "FAIL" if any(f["code"] != "ARCHIVE_MEMBER_TOO_LARGE" for f in failures) else "BLOCKED"
                return result(status, "miz.check", level="archive", findings=failures,
                              runtime="NOT_TESTED", lua_syntax="NOT_TESTED")
            if "mission" not in names:
                failures.append({"code": "MISSION_ENTRY_MISSING"})
            else:
                mission = archive.read("mission").decode("utf-8-sig")
                if not re.search(r"\bmission\s*=\s*\{", mission):
                    failures.append({"code": "MISSION_TABLE_MISSING"})
                match = re.search(r'\["theatre"\]\s*=\s*"([^"\n]+)"', mission)
                if match:
                    theatre = match.group(1)
                else:
                    failures.append({"code": "THEATRE_UNIDENTIFIED"})
            for entry in entries:
                if entry.filename.endswith(".lua"):
                    scripts.append({"name": entry.filename, "sha256": hashlib.sha256(archive.read(entry)).hexdigest()})
                if Path(entry.filename).name == "mapResource":
                    mapping = archive.read(entry).decode("utf-8-sig")
                    for resource in re.findall(r'=\s*"([^"\n]+)"', mapping):
                        target = str(Path(entry.filename).parent / resource).replace("\\", "/")
                        if target not in names:
                            failures.append({"code": "RESOURCE_MISSING"})
            # Reading every member makes CRC failures observable without extracting.
            if archive.testzip() is not None:
                failures.append({"code": "ARCHIVE_CRC_FAILURE"})
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, NotImplementedError):
        failures.append({"code": "UNREADABLE_ARCHIVE"})
    return result("FAIL" if failures else "PASS", "miz.check", level="archive",
                  sha256=digest(path), theatre=theatre, scripts=scripts, findings=failures,
                  runtime="NOT_TESTED", lua_syntax="NOT_TESTED")


def index_corpus(source: Path, destination: Path) -> dict:
    if not source.is_dir():
        raise HarnessError("CORPUS_DIRECTORY_MISSING", "BLOCKED")
    records = []
    for path in sorted(source.rglob("*.miz")):
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise HarnessError("CORPUS_SYMLINK_FORBIDDEN")
        try:
            inspected = inspect_miz(path)
        except HarnessError as error:
            inspected = result(error.status, "miz.check", findings=[{"code": error.code}])
        records.append({"reference": path.relative_to(source).as_posix(), **inspected})
    write_new(destination, {"schema_version": "1.0", "classification": "private", "missions": records})
    return result("PASS", "corpus.index", count=len(records),
                  valid_archives=sum(r["status"] == "PASS" for r in records),
                  failed_archives=sum(r["status"] == "FAIL" for r in records),
                  blocked_archives=sum(r["status"] == "BLOCKED" for r in records),
                  output="private/corpus-index.json")
