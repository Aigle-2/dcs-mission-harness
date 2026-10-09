"""Shared contracts. Validation never prints rejected private values."""
from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


class HarnessError(Exception):
    def __init__(self, code: str, status: str = "FAIL"):
        self.code, self.status = code, status
        super().__init__(code)


class StrictLoader(yaml.SafeLoader):
    """Reject ambiguous duplicate keys instead of silently overriding them."""


def strict_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise HarnessError("DUPLICATE_DOCUMENT_KEY")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, strict_mapping)


def result(status: str, operation: str, **data) -> dict:
    return {"schema_version": "1.0", "status": status, "operation": operation, **data}


def load_document(path: Path) -> dict:
    if path.stat().st_size > 1_000_000:
        raise HarnessError("DOCUMENT_TOO_LARGE")
    try:
        data = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=StrictLoader)
    except (yaml.YAMLError, UnicodeError):
        raise HarnessError("INVALID_DOCUMENT") from None
    if not isinstance(data, dict):
        raise HarnessError("EXPECTED_OBJECT")
    return data


def validate(kind: str, data: dict) -> list[dict]:
    schema = json.loads(files("dcs_harness").joinpath("schemas", f"{kind}.json").read_text(encoding="utf-8"))
    errors = [{"code": f"SCHEMA_{e.validator.upper()}", "location": list(e.absolute_path)}
              for e in Draft202012Validator(schema).iter_errors(data)]
    if kind == "lesson" and not errors:
        words = len((data["problem"] + " " + data["recommendation"]).split())
        if words > 200:
            errors.append({"code": "LESSON_WORD_BUDGET", "location": []})
    if kind == "mission" and not errors:
        ids = [i["id"] for i in data["integrations"]]
        if len(set(ids)) != len(ids):
            errors.append({"code": "DUPLICATE_INTEGRATION", "location": ["integrations"]})
    return errors


def require_valid(kind: str, data: dict) -> None:
    if validate(kind, data):
        raise HarnessError(f"INVALID_{kind.upper()}")


def compatibility(mission: dict, profile: dict) -> list[dict]:
    failures = []
    if mission["theatre"] not in profile["theatres"]:
        failures.append({"code": "THEATRE_UNAVAILABLE"})
    for slot in mission["slots"]:
        if slot["aircraft"] not in profile["aircraft"]:
            failures.append({"code": "AIRCRAFT_UNAVAILABLE"})
    for integration in mission["integrations"]:
        if profile["integrations"].get(integration["id"]) != integration["version"]:
            failures.append({"code": "INTEGRATION_VERSION_UNAVAILABLE"})
    return failures


def private_root(repo: Path | None = None) -> Path:
    value = os.environ.get("DCS_HARNESS_PRIVATE_ROOT")
    if not value:
        raise HarnessError("PRIVATE_ROOT_NOT_CONFIGURED", "BLOCKED")
    path = Path(value).expanduser().resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise HarnessError("PRIVATE_ROOT_TOO_BROAD", "BLOCKED")
    checkout = (repo or Path.cwd()).resolve()
    if path.is_relative_to(checkout) or checkout.is_relative_to(path):
        raise HarnessError("PRIVATE_ROOT_OVERLAPS_CHECKOUT", "BLOCKED")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_new(path: Path, data: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
