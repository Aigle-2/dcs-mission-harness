"""Conservative text/archive checks; findings omit matched values."""
from __future__ import annotations

import io
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from .core import HarnessError

MAX_FILE = 8 * 1024 * 1024
MAX_ARCHIVE = 64 * 1024 * 1024
TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".toml", ".lock", ".txt", ".lua", ".ps1", ".sh", ".example"}
TEXT_NAMES = {"LICENSE", "AGENTS.md", "CLAUDE.md", "mission", "dictionary", "mapResource", "options", "warehouses", "description"}
RULES = {
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "TOKEN": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
    "PERSONAL_PATH": re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+[^\s\\/]+|/h[o]me/[^/\s]+/|/U[s]ers/[^/\s]+/)", re.I),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ENDPOINT_IPV4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "CREDENTIAL_ASSIGNMENT": re.compile(r"(?:password|api[_-]?key|access[_-]?token|secret)\s*[=:]\s*[\"']?[A-Za-z0-9_+/=-]{12,}", re.I),
    "PLAYER_IDENTIFIER": re.compile(r"\b(?:ucid|player[_-]?id)\s*[=:]\s*[\"']?[a-f0-9]{16,}", re.I),
}


def scan_text(text: str) -> list[dict]:
    findings = []
    for code, pattern in RULES.items():
        for match in pattern.finditer(text):
            if code == "EMAIL" and match.group().endswith(("@example.com", "@example.org", "@example.net", "@users.noreply.github.com")):
                continue
            if code == "ENDPOINT_IPV4" and match.group() in {"127.0.0.1", "0.0.0.0"}:
                continue
            findings.append({"code": code, "line": text.count("\n", 0, match.start()) + 1})
    return findings


def safe_archive_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and ":" not in name


def scan_bytes(name: str, content: bytes, depth: int = 0) -> list[dict]:
    if len(content) > MAX_FILE:
        return [{"code": "FILE_REVIEW_REQUIRED"}]
    suffix = Path(name).suffix.lower()
    if suffix in {".miz", ".zip"}:
        if depth >= 2:
            return [{"code": "ARCHIVE_DEPTH_EXCEEDED"}]
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_ARCHIVE:
                    return [{"code": "ARCHIVE_BUDGET_EXCEEDED"}]
                findings = []
                names = set()
                for entry in entries:
                    if not safe_archive_name(entry.filename) or entry.filename in names:
                        findings.append({"code": "UNSAFE_ARCHIVE_MEMBER"})
                        continue
                    names.add(entry.filename)
                    if entry.is_dir():
                        continue
                    if entry.file_size > MAX_FILE or entry.flag_bits & 1:
                        findings.append({"code": "ARCHIVE_MEMBER_REVIEW_REQUIRED"})
                        continue
                    findings.extend(scan_bytes(entry.filename, archive.read(entry), depth + 1))
                return findings
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
            return [{"code": "UNREADABLE_ARCHIVE"}]
    if suffix not in TEXT_SUFFIXES and Path(name).name not in TEXT_NAMES and not Path(name).name.startswith(".git"):
        return [{"code": "BINARY_OR_UNKNOWN_REVIEW_REQUIRED"}]
    try:
        return scan_text(content.decode("utf-8-sig"))
    except UnicodeError:
        return [{"code": "NON_UTF8_REVIEW_REQUIRED"}]


def scan_file(path: Path) -> list[dict]:
    if path.is_symlink():
        return [{"code": "SYMLINK_FORBIDDEN"}]
    if path.stat().st_size > MAX_FILE:
        return [{"code": "FILE_REVIEW_REQUIRED"}]
    return scan_bytes(path.name, path.read_bytes())


def git(repo: Path, *args: str) -> bytes:
    process = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False, timeout=60)
    if process.returncode:
        raise HarnessError("GIT_OPERATION_FAILED", "BLOCKED")
    return process.stdout


def scan_tracked(repo: Path, history: bool = False) -> list[dict]:
    findings = []
    names = git(repo, "ls-files", "-z").decode("utf-8").split("\0")
    for name in filter(None, names):
        path = repo / name
        if not path.exists():
            findings.append({"code": "TRACKED_FILE_MISSING", "file": name})
            continue
        if not path.resolve().is_relative_to(repo.resolve()):
            findings.append({"code": "PATH_ESCAPE", "file": name})
            continue
        findings.extend({**finding, "file": name} for finding in scan_file(path))
    # Scan the index too: a clean working file can mask a staged secret.
    staged = git(repo, "ls-files", "--stage", "-z").decode("utf-8").split("\0")
    for record in filter(None, staged):
        metadata, name = record.split("\t", 1)
        mode, oid, stage = metadata.split()
        if mode != "100644" and mode != "100755":
            findings.append({"code": "UNSUPPORTED_INDEX_MODE", "file": name})
            continue
        if stage != "0":
            findings.append({"code": "UNMERGED_INDEX", "file": name})
            continue
        size = int(git(repo, "cat-file", "-s", oid))
        detected = scan_bytes(name, git(repo, "cat-file", "blob", oid)) if size <= MAX_FILE else [{"code": "FILE_REVIEW_REQUIRED"}]
        findings.extend({**f, "file": name, "source": "index"} for f in detected)
    if history:
        objects = git(repo, "rev-list", "--objects", "--all").decode("utf-8").splitlines()
        if len(objects) > 5000:
            raise HarnessError("HISTORY_BUDGET_EXCEEDED", "BLOCKED")
        budget = 0
        for record in objects:
            oid, _, name = record.partition(" ")
            objtype = git(repo, "cat-file", "-t", oid).decode().strip()
            if objtype in {"commit", "tag"}:
                findings.extend({**f, "object": oid[:12]} for f in scan_text(git(repo, "cat-file", "-p", oid).decode("utf-8", errors="replace")))
            elif objtype == "blob":
                size = int(git(repo, "cat-file", "-s", oid))
                budget += size
                if budget > MAX_ARCHIVE:
                    raise HarnessError("HISTORY_BUDGET_EXCEEDED", "BLOCKED")
                content = git(repo, "cat-file", "blob", oid) if size <= MAX_FILE else b""
                detected = scan_bytes(name, content) if size <= MAX_FILE else [{"code": "FILE_REVIEW_REQUIRED"}]
                findings.extend({**f, "object": oid[:12]} for f in detected)
    return findings
