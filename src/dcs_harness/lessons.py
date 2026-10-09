"""Bounded private lesson ingestion with conservative exact deduplication."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .core import HarnessError, require_valid, write_new, result, validate


def fingerprint(lesson: dict) -> str:
    context = {key: lesson.get(key) for key in ("category", "problem", "recommendation", "versions")}
    context["tags"] = sorted(lesson["tags"])
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def ingest(root: Path, lesson: dict) -> dict:
    require_valid("lesson", lesson)
    directory = root / "lessons"
    directory.mkdir(parents=True, exist_ok=True)
    # An exclusive lock prevents two agents from violating the memory budgets.
    lock = directory / ".lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise HarnessError("LESSONS_LOCKED", "BLOCKED") from None
    os.close(descriptor)
    try:
        existing = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")]
        incoming = {**lesson, "classification": "private", "status": "candidate"}
        for record in existing:
            if fingerprint(record) == fingerprint(incoming):
                return result("PASS", "lessons.ingest", outcome="duplicate", destination="private")
            if record["id"] == incoming["id"]:
                raise HarnessError("LESSON_ID_CONFLICT")
        if sum(r["status"] == "candidate" for r in existing) >= 100:
            raise HarnessError("LESSON_CANDIDATE_BUDGET", "BLOCKED")
        if sum(r["status"] in {"validated", "disputed"} for r in existing) > 100:
            raise HarnessError("LESSON_ACTIVE_BUDGET", "BLOCKED")
        write_new(directory / f"{incoming['id']}.json", incoming)
        return result("PASS", "lessons.ingest", outcome="candidate", destination="private")
    finally:
        lock.unlink()


def budget_report(root: Path) -> dict:
    directory = root / "lessons"
    records = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")]
    candidates = sum(r.get("status") == "candidate" for r in records)
    active = sum(r.get("status") in {"validated", "disputed"} for r in records)
    failures = sum(bool(validate("lesson", r)) for r in records)
    return result("PASS" if candidates <= 100 and active <= 100 and not failures else "FAIL",
                  "lessons.compact.check", candidates=candidates, active=active,
                  invalid=failures, candidate_limit=100, active_limit=100,
                  automatic_deletion=False)
