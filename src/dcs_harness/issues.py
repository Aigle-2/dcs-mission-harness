"""Structured issue rendering and argument-safe GitHub CLI access."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .core import HarnessError, require_valid, result, write_new
from .privacy import scan_text


def repository(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise HarnessError("INVALID_REPOSITORY")
    return value


def render(data: dict) -> str:
    require_valid("issue", data)
    if scan_text(json.dumps(data, ensure_ascii=False)):
        raise HarnessError("ISSUE_CONTAINS_SENSITIVE_DATA")
    parts = [f"Type: {data['kind']}\n"]
    for field, title in (("context", "Context"), ("expected", "Expected behavior"),
                         ("actual", "Observed behavior"), ("reproduction", "Reproduction"),
                         ("evidence", "Evidence"), ("acceptance", "Acceptance criteria"), ("scope", "Scope")):
        if field not in data:
            continue
        content = data[field]
        if isinstance(content, list):
            prefix = "- [ ] " if field == "acceptance" else "- "
            content = "\n".join(prefix + item for item in content)
        parts.append(f"## {title}\n\n{content}\n")
    return "\n".join(parts)


def run_gh(arguments: list[str]) -> str:
    try:
        process = subprocess.run(["gh", *arguments], capture_output=True, text=True, timeout=60, check=False)
    except FileNotFoundError:
        raise HarnessError("GITHUB_CLI_UNAVAILABLE", "BLOCKED") from None
    if process.returncode:
        # gh stderr can contain endpoints, accounts and rejected input.
        raise HarnessError("GITHUB_OPERATION_FAILED", "BLOCKED")
    return process.stdout


def read(repo: str, number: int | None = None) -> dict:
    repo = repository(repo)
    if number is not None:
        if number <= 0:
            raise HarnessError("INVALID_ISSUE_NUMBER")
        args = ["issue", "view", str(number), "--repo", repo, "--json", "number,title,body,state,url,labels,comments"]
    else:
        args = ["issue", "list", "--repo", repo, "--limit", "30", "--json", "number,title,state,url,labels"]
    return result("PASS", "issues.read" if number else "issues.list",
                  trust="UNTRUSTED_EXTERNAL_DATA", data=json.loads(run_gh(args)))


def draft(data: dict, destination: Path) -> dict:
    body = render(data)
    write_new(destination, body)
    return result("PASS", "issues.draft", published=False)


def create(repo: str, data: dict, publish: bool = False) -> dict:
    repo = repository(repo)
    body = render(data)
    if not publish:
        return result("PASS", "issues.create.plan", published=False, repository=repo,
                      title=data["title"], body=body, labels=data.get("labels", []))
    # --publish records the caller's authorized intent. It is not an approval UI.
    with tempfile.TemporaryDirectory(prefix="dcs-issue-") as directory:
        path = Path(directory) / "body.md"
        path.write_text(body, encoding="utf-8", newline="\n")
        args = ["issue", "create", "--repo", repo, "--title", data["title"], "--body-file", str(path)]
        for label in data.get("labels", []):
            args.extend(["--label", label])
        url = run_gh(args).strip()
    return result("PASS", "issues.create", published=True, url=url)
