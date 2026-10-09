"""A shared CLI for agents; JSON is the stable reporting interface."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import archives, issues, lessons, publication, workflow
from .core import HarnessError, compatibility, load_document, private_root, result, validate
from .privacy import scan_text, scan_tracked


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="dcs-harness")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    command = commands.add_parser("validate")
    command.add_argument("--kind", choices=["mission", "functional-spec", "verification", "comm-plan", "profile", "lesson", "issue", "publication"], required=True)
    command.add_argument("--file", type=Path, required=True)
    command.add_argument("--profile", type=Path)
    command = commands.add_parser("miz")
    sub = command.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check")
    check.add_argument("--file", type=Path, required=True)
    command = commands.add_parser("corpus")
    sub = command.add_subparsers(dest="action", required=True)
    index = sub.add_parser("index")
    index.add_argument("--source", type=Path, required=True)
    command = commands.add_parser("lessons")
    sub = command.add_subparsers(dest="action", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--file", type=Path, required=True)
    compact = sub.add_parser("compact")
    compact.add_argument("--check", action="store_true", required=True)
    command = commands.add_parser("issues")
    sub = command.add_subparsers(dest="action", required=True)
    for action in ("list", "read", "create"):
        child = sub.add_parser(action)
        child.add_argument("--repo", required=True)
        if action == "read":
            child.add_argument("--number", type=int, required=True)
        if action == "create":
            child.add_argument("--file", type=Path, required=True)
            child.add_argument("--publish", action="store_true")
    child = sub.add_parser("draft")
    child.add_argument("--file", type=Path, required=True)
    command = commands.add_parser("publish")
    sub = command.add_subparsers(dest="action", required=True)
    child = sub.add_parser("check")
    source = child.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate", type=Path)
    source.add_argument("--tracked", action="store_true")
    child.add_argument("--history", action="store_true")
    child = sub.add_parser("export")
    child.add_argument("--candidate", type=Path, required=True)
    child.add_argument("--destination", type=Path, required=True)
    command = commands.add_parser("lua")
    sub = command.add_subparsers(dest="action", required=True)
    child = sub.add_parser("check")
    child.add_argument("--file", type=Path, required=True)
    commands.add_parser("test")
    command = commands.add_parser("mission")
    sub = command.add_subparsers(dest="action", required=True)
    for action in ("start", "status", "review", "spec", "implement", "verify"):
        child = sub.add_parser(action)
        child.add_argument("--run", required=True)
        if action == "start":
            child.add_argument("--brief-file", type=Path, required=True)
        elif action in {"review", "spec", "verify"}:
            child.add_argument("--file", type=Path, required=True)
        elif action == "implement":
            child.add_argument("--artifact", type=Path, required=True)
    return root


def execute(args: argparse.Namespace) -> dict:
    if args.command == "mission":
        root = private_root()
        if args.action == "start":
            return workflow.start(root, args.run, args.brief_file)
        if args.action == "status":
            return workflow.status(root, args.run)
        if args.action == "spec":
            return workflow.specification(root, args.run, args.file)
        if args.action == "review":
            return workflow.review(root, args.run, args.file)
        if args.action == "implement":
            return workflow.implementation(root, args.run, args.artifact)
        return workflow.verify(root, args.run, args.file)
    if args.command == "doctor":
        checks = {name: bool(shutil.which(name)) for name in ("git", "gh", "luac5.1")}
        try:
            private_root()
            checks["private_workspace"] = True
        except HarnessError:
            checks["private_workspace"] = False
        return result("PASS" if all(checks.values()) else "BLOCKED", "doctor", checks=checks,
                      runtime="NOT_CONFIGURED", version=__version__)
    if args.command == "validate":
        data = load_document(args.file)
        failures = validate(args.kind, data)
        if args.profile:
            if args.kind != "mission":
                raise HarnessError("PROFILE_REQUIRES_MISSION")
            profile = load_document(args.profile)
            failures.extend(validate("profile", profile))
            if not failures:
                failures.extend(compatibility(data, profile))
        return result("FAIL" if failures else "PASS", "validate", kind=args.kind,
                      level="specification", findings=failures, runtime="NOT_TESTED")
    if args.command == "miz":
        return archives.inspect_miz(args.file)
    if args.command == "corpus":
        return archives.index_corpus(args.source, private_root() / "corpus-index.json")
    if args.command == "lessons":
        return lessons.ingest(private_root(), load_document(args.file)) if args.action == "ingest" else lessons.budget_report(private_root())
    if args.command == "issues":
        if args.action in {"list", "read"}:
            return issues.read(args.repo, getattr(args, "number", None))
        data = load_document(args.file)
        if args.action == "draft":
            issues.render(data)
            return issues.draft(data, private_root() / "issue-drafts" / (data["kind"] + "-draft.md"))
        return issues.create(args.repo, data, args.publish)
    if args.command == "publish":
        if args.action == "export":
            return publication.export(args.candidate, args.destination)
        if args.history and not args.tracked:
            raise HarnessError("HISTORY_REQUIRES_TRACKED")
        if args.tracked:
            findings = scan_tracked(Path.cwd(), args.history)
            return result("FAIL" if findings else "PASS", "publish.check", findings=findings)
        return publication.check(args.candidate)
    if args.command == "lua":
        compiler = shutil.which("luac5.1")
        if not compiler:
            raise HarnessError("LUA_51_COMPILER_UNAVAILABLE", "BLOCKED")
        process = subprocess.run([compiler, "-p", str(args.file.resolve())], capture_output=True, timeout=30)
        return result("PASS" if process.returncode == 0 else "FAIL", "lua.check", level="syntax", runtime="NOT_TESTED")
    if args.command == "test":
        if not Path("tests").is_dir():
            raise HarnessError("TESTS_REQUIRE_CHECKOUT", "BLOCKED")
        process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], capture_output=True, text=True, timeout=120)
        # Test output may contain rejected input: emit only a summary by default.
        return result("PASS" if process.returncode == 0 else "FAIL", "test", level="local",
                      runtime="NOT_TESTED", command="python -m unittest discover -s tests -v")
    raise HarnessError("UNSUPPORTED_COMMAND")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = execute(args)
    except HarnessError as error:
        report = result(error.status, args.command, findings=[{"code": error.code}])
    except (OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.TimeoutExpired):
        report = result("BLOCKED", args.command, findings=[{"code": "OPERATION_FAILED_NO_PRIVATE_DETAILS"}])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else (2 if report["status"] == "FAIL" else 3)
