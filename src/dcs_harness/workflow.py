"""Private mission runs with hash-bound specification/build/evidence gates."""
from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from .archives import digest, inspect_miz
from .core import HarnessError, load_document, require_valid, result, write_new


def run_path(root: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", run_id):
        raise HarnessError("INVALID_RUN_ID")
    path = root / "runs" / run_id
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise HarnessError("RUN_PATH_ESCAPE")
    return path


def save_state(path: Path, state: dict) -> None:
    temporary = path / "state.pending"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path / "state.json")


@contextmanager
def locked_run(root: Path, run_id: str):
    path = run_path(root, run_id)
    if not path.is_dir():
        raise HarnessError("RUN_NOT_FOUND", "BLOCKED")
    lock = path / ".lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise HarnessError("RUN_LOCKED", "BLOCKED") from None
    os.close(descriptor)
    try:
        yield path, load_document(path / "state.json")
    finally:
        lock.unlink()


def start(root: Path, run_id: str, brief: Path) -> dict:
    if brief.stat().st_size > 100_000:
        raise HarnessError("BRIEF_TOO_LARGE")
    text = brief.read_text(encoding="utf-8-sig")
    if len(text.strip()) < 10:
        raise HarnessError("BRIEF_TOO_SHORT")
    path = run_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        raise HarnessError("RUN_ALREADY_EXISTS") from None
    write_new(path / "brief.md", text)
    state = {"schema_version": "1.0", "classification": "private", "id": run_id,
             "phase": "SPECIFICATION_PENDING", "brief_sha256": digest(path / "brief.md")}
    save_state(path, state)
    return result("PASS", "mission.start", run=run_id, phase=state["phase"],
                  next_skill="mission-functional-spec",
                  skill_file=".agents/skills/mission-functional-spec/SKILL.md",
                  files={"brief": f"runs/{run_id}/brief.md", "spec": f"runs/{run_id}/functional-spec.yaml"},
                  agent_action="Read the skill; review date and year-based aircraft/weapon restrictions, communications, support, air defence, victory, aircraft/loadouts and any carrier escort/placement. Apply veteran AI defaults and verify exact installed unit types.")


def status(root: Path, run_id: str) -> dict:
    with locked_run(root, run_id) as (_, state):
        # No private brief, source names or operational paths in the summary.
        return result("PASS", "mission.status", run=run_id, phase=state["phase"],
                      hashes={key: value for key, value in state.items() if key.endswith("sha256")},
                      runtime="NOT_TESTED")


def specification(root: Path, run_id: str, file: Path) -> dict:
    spec = load_document(file)
    require_valid("functional-spec", spec)
    if spec['temporal']['status'] == 'proposed':
        raise HarnessError('TEMPORAL_REVIEW_REQUIRED', 'BLOCKED')
    if spec["open_questions"]:
        raise HarnessError("SPEC_HAS_OPEN_QUESTIONS", "BLOCKED")
    if any(d["status"] == "proposed" for d in spec["design_decisions"]):
        raise HarnessError("DESIGN_REVIEW_REQUIRED", "BLOCKED")
    if any(f["status"] == "proposed" for f in spec["support_flights"]):
        raise HarnessError("SUPPORT_FLIGHT_REVIEW_REQUIRED", "BLOCKED")
    if spec["communications"]["decision"] == "pending":
        raise HarnessError("COMM_PLAN_DECISION_REQUIRED", "BLOCKED")
    if spec["liveries"]["decision"] == "pending":
        raise HarnessError("LIVERY_DECISION_REQUIRED", "BLOCKED")
    if spec['navigation']['status'] == 'proposed':
        raise HarnessError('NAVIGATION_REVIEW_REQUIRED', 'BLOCKED')
    if spec["mission"]["id"] != run_id:
        raise HarnessError("SPEC_RUN_ID_MISMATCH")
    with locked_run(root, run_id) as (path, state):
        if state["phase"] != "SPECIFICATION_PENDING":
            raise HarnessError("SPEC_TRANSITION_NOT_ALLOWED")
        if digest(path / "brief.md") != state["brief_sha256"]:
            raise HarnessError("BRIEF_CHANGED_RESTART_REQUIRED")
        spec["classification"] = "private"
        spec["mission"]["classification"] = "private"
        write_new(path / "spec.accepted.json", spec)
        state.update(phase="IMPLEMENTATION_PENDING", spec_sha256=digest(path / "spec.accepted.json"))
        save_state(path, state)
    return result("PASS", "mission.spec", run=run_id, phase=state["phase"],
                  spec_sha256=state["spec_sha256"], next_action="Implement the accepted functional spec.",
                  human_approval="NOT_IMPLIED")


def review(root: Path, run_id: str, file: Path) -> dict:
    from .design_review import decision_review
    spec = load_document(file)
    document, pending = decision_review(spec)
    if spec['mission']['id'] != run_id:
        raise HarnessError('SPEC_RUN_ID_MISMATCH')
    with locked_run(root, run_id) as (path, state):
        if state['phase'] != 'SPECIFICATION_PENDING':
            raise HarnessError('SPEC_REVIEW_TRANSITION_NOT_ALLOWED')
        target = path / 'functional-spec.review.md'
        history = path / 'reviews'
        if target.is_symlink() or history.is_symlink():
            raise HarnessError('RUN_PATH_ESCAPE')
        history.mkdir(exist_ok=True)
        sequence = len(list(history.glob('*.md'))) + 1
        write_new(history / f'{sequence:04d}.md', document)
        target.write_text(document, encoding='utf-8')
    return result('PASS', 'mission.review', run=run_id, proposed=pending,
                  document=f'runs/{run_id}/functional-spec.review.md',
                  human_approval='NOT_IMPLIED', phase=state['phase'])


def unchanged_spec(path: Path, state: dict) -> dict:
    if digest(path / "spec.accepted.json") != state["spec_sha256"]:
        raise HarnessError("ACCEPTED_SPEC_CHANGED")
    spec = load_document(path / "spec.accepted.json")
    # Historical runs remain readable but cannot bypass the new review gate.
    require_valid("functional-spec", spec)
    if spec['temporal']['status'] == 'proposed':
        raise HarnessError('TEMPORAL_REVIEW_REQUIRED', 'BLOCKED')
    if any(d["status"] == "proposed" for d in spec["design_decisions"]) or spec["communications"]["decision"] == "pending":
        raise HarnessError("DESIGN_REVIEW_REQUIRED", "BLOCKED")
    if any(f["status"] == "proposed" for f in spec["support_flights"]):
        raise HarnessError("SUPPORT_FLIGHT_REVIEW_REQUIRED", "BLOCKED")
    if spec["liveries"]["decision"] == "pending":
        raise HarnessError("LIVERY_DECISION_REQUIRED", "BLOCKED")
    if spec['navigation']['status'] == 'proposed':
        raise HarnessError('NAVIGATION_REVIEW_REQUIRED', 'BLOCKED')
    return spec


def implementation(root: Path, run_id: str, artifact: Path) -> dict:
    report = inspect_miz(artifact)
    if report["status"] != "PASS":
        return result(report["status"], "mission.implement", findings=report["findings"])
    with locked_run(root, run_id) as (path, state):
        if state["phase"] != "IMPLEMENTATION_PENDING":
            raise HarnessError("IMPLEMENTATION_TRANSITION_NOT_ALLOWED")
        spec = unchanged_spec(path, state)
        if report["theatre"] != spec["mission"]["theatre"]:
            raise HarnessError("ARTIFACT_THEATRE_MISMATCH")
        if spec["communications"]["decision"] == "enabled":
            from .communications import check_archive
            check_archive(artifact, spec["communications"]["plan"])
        target = path / "mission.miz"
        if target.exists():
            raise HarnessError("REGISTERED_ARTIFACT_ALREADY_EXISTS")
        shutil.copyfile(artifact, target)
        if digest(target) != report["sha256"]:
            raise HarnessError("ARTIFACT_CHANGED_DURING_COPY")
        state.update(phase="VERIFICATION_PENDING", artifact_sha256=report["sha256"])
        save_state(path, state)
    return result("PASS", "mission.implement", run=run_id, phase=state["phase"],
                  artifact_sha256=state["artifact_sha256"], runtime="NOT_TESTED",
                  next_action="Run implementation checks and submit hash-bound verification evidence.")


def verify(root: Path, run_id: str, evidence_file: Path) -> dict:
    evidence = load_document(evidence_file)
    require_valid("verification", evidence)
    with locked_run(root, run_id) as (path, state):
        if state["phase"] not in {"VERIFICATION_PENDING", "LOCAL_VERIFIED"}:
            raise HarnessError("VERIFICATION_TRANSITION_NOT_ALLOWED")
        spec = unchanged_spec(path, state)
        if digest(path / "mission.miz") != state["artifact_sha256"]:
            raise HarnessError("REGISTERED_ARTIFACT_CHANGED")
        if spec["communications"]["decision"] == "enabled":
            from .communications import check_archive
            check_archive(path / "mission.miz", spec["communications"]["plan"])
        if any(evidence[key] != state[key] for key in ("spec_sha256", "artifact_sha256")):
            raise HarnessError("EVIDENCE_HASH_MISMATCH")
        criteria = {item["id"]: item for item in spec["criteria"]}
        checks = {item["criterion"]: item for item in evidence["checks"]}
        if len(checks) != len(evidence["checks"]) or set(checks) != set(criteria):
            raise HarnessError("EVIDENCE_CRITERIA_MISMATCH")
        # This slice cannot certify runtime/client evidence. Such claims are rejected.
        if any(checks[key]["status"] == "PASS" for key, item in criteria.items() if item["level"] != "local"):
            raise HarnessError("RUNTIME_EVIDENCE_ADAPTER_NOT_AVAILABLE", "BLOCKED")
        local_pass = all(checks[key]["status"] == "PASS" for key, item in criteria.items() if item["level"] == "local")
        any_fail = any(item["status"] == "FAIL" for item in checks.values())
        operation_status = "FAIL" if any_fail else ("PASS" if local_pass else "BLOCKED")
        state["phase"] = "LOCAL_VERIFIED" if operation_status == "PASS" else "VERIFICATION_PENDING"
        save_state(path, state)
        summary = result(operation_status, "mission.verify", run=run_id, phase=state["phase"],
                         local_checks=sum(item["level"] == "local" for item in criteria.values()),
                         pending_runtime_or_client=sum(item["level"] != "local" for item in criteria.values()),
                         runtime="NOT_TESTED", mission_validation="INCONCLUSIVE")
        # Preserve retry history without overwriting previous evidence.
        evidence_dir = path / "verifications"
        evidence_dir.mkdir(exist_ok=True)
        sequence = len(list(evidence_dir.glob("*.json"))) + 1
        write_new(evidence_dir / f"{sequence:04d}.json", {"summary": summary, "evidence": evidence})
        return summary
