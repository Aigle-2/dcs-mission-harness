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
    if kind == "functional-spec" and not errors:
        errors.extend({**error, "location": ["mission", *error["location"]]}
                      for error in validate("mission", data["mission"]))
        ids = [criterion["id"] for criterion in data["criteria"]]
        if len(ids) != len(set(ids)):
            errors.append({"code": "DUPLICATE_CRITERION", "location": ["criteria"]})
        if not any(criterion["level"] == "local" for criterion in data["criteria"]):
            errors.append({"code": "LOCAL_CRITERION_REQUIRED", "location": ["criteria"]})
        topics = [decision["topic"] for decision in data["design_decisions"]]
        required_topics = {"support", "air-defence", "victory", "battlegroup", "carrier-placement", "aircraft-loadouts"}
        if len(topics) != len(set(topics)) or not required_topics.issubset(topics):
            errors.append({"code": "DESIGN_TOPICS_REQUIRED_ONCE", "location": ["design_decisions"]})
        configuration = data["configuration"]
        nav_errors = validate('navigation', data['navigation'])
        errors.extend({**e, 'location': ['navigation', *e['location']]} for e in nav_errors)
        support = data["support_flights"]
        groups = [flight["group"] for flight in support]
        if len(set(groups)) != len(groups):
            errors.append({"code": "DUPLICATE_SUPPORT_GROUP", "location": ["support_flights"]})
        if configuration["awacs_present"] != any(f["role"] == "awacs" for f in support):
            errors.append({"code": "AWACS_PRESENCE_MISMATCH", "location": ["support_flights"]})
        for index, flight in enumerate(support):
            if flight["status"] == "confirmed" and flight["source"] == "agent-proposal":
                errors.append({"code": "USER_CONFIRMATION_REQUIRED", "location": ["support_flights", index]})
            orbit = flight["orbit"]
            if orbit["pattern"] == "Race-Track" and orbit["start"] == orbit["end"]:
                errors.append({"code": "DEGENERATE_SUPPORT_ORBIT", "location": ["support_flights", index, "orbit"]})
        if configuration["ai_skill_source"] == "default-policy" and configuration["ai_skill"] != "High":
            errors.append({"code": "VETERAN_DEFAULT_REQUIRED", "location": ["configuration", "ai_skill"]})
        local_ids = {c["id"] for c in data["criteria"] if c["level"] == "local"}
        required_checks = {"UNIT-TYPES", "AIRCRAFT-LOADOUTS", "AI-SKILL", "NAVIGATION"}
        if configuration["carrier_present"]:
            required_checks.update({"CARRIER-GROUP", "CARRIER-PLACEMENT"})
        if configuration["awacs_present"]:
            required_checks.add("AWACS-ORBIT")
        if support:
            required_checks.add("SUPPORT-FLIGHT-PROFILES")
        if not required_checks.issubset(local_ids):
            errors.append({"code": "CONFIGURATION_CRITERIA_REQUIRED", "location": ["criteria"]})
        liveries = data["liveries"]
        if liveries["decision"] != "pending" and liveries["source"] == "unanswered":
            errors.append({"code": "LIVERY_USER_DECISION_REQUIRED", "location": ["liveries"]})
        selections = liveries.get("selections", [])
        targets = [(s["group"], s.get("unit")) for s in selections]
        if len(targets) != len(set(targets)):
            errors.append({"code": "DUPLICATE_LIVERY_TARGET", "location": ["liveries", "selections"]})
        if "AIRCRAFT-LIVERIES" not in local_ids:
            errors.append({"code": "LIVERY_LOCAL_CRITERION_REQUIRED", "location": ["criteria"]})
        if liveries["decision"] == "custom" and not any(c["id"] == "LIVERIES-VISIBLE" and c["level"] == "client" for c in data["criteria"]):
            errors.append({"code": "LIVERY_CLIENT_CRITERION_REQUIRED", "location": ["criteria"]})
        for index, decision in enumerate(data["design_decisions"]):
            if decision["status"] == "confirmed" and decision["source"] == "agent-proposal":
                errors.append({"code": "USER_CONFIRMATION_REQUIRED", "location": ["design_decisions", index]})
            if decision["status"] == "not-applicable" and (
                decision["topic"] == "aircraft-loadouts"
                or (configuration["carrier_present"] and decision["topic"] in {"battlegroup", "carrier-placement"})
                or (support and decision["topic"] == "support")
            ):
                errors.append({"code": "APPLICABLE_DESIGN_CHOICE_REQUIRED", "location": ["design_decisions", index]})
        comm = data["communications"]
        if comm["decision"] != "pending" and comm["source"] == "unanswered":
            errors.append({"code": "COMM_USER_DECISION_REQUIRED", "location": ["communications"]})
        if "plan" in comm:
            errors.extend({**error, "location": ["communications", "plan", *error["location"]]}
                          for error in validate("comm-plan", comm["plan"]))
            if comm['plan'].get('navigation') != data['navigation']:
                errors.append({'code': 'COMM_NAVIGATION_MISMATCH', 'location': ['communications', 'plan', 'navigation']})
        if not nav_errors:
            nav = data['navigation']
            if configuration['carrier_present'] and not nav['naval_systems']:
                errors.append({'code': 'NAVAL_SYSTEMS_REQUIRED', 'location': ['navigation', 'naval_systems']})
            active_nav = bool(nav['tacan'] or nav['yardstick'] or any(
                ship[s]['decision'] == 'enabled' for ship in nav['naval_systems'] for s in ('icls', 'datalink')))
            if active_nav and not any(c['id'] == 'NAVIGATION-RECEPTION' and c['level'] == 'client' for c in data['criteria']):
                errors.append({'code': 'NAVIGATION_CLIENT_CRITERION_REQUIRED', 'location': ['criteria']})
        if comm["decision"] == "enabled":
            local_ids = {c["id"] for c in data["criteria"] if c["level"] == "local"}
            if not {"COMM-PRESETS", "COMM-FREQUENCIES", "COMM-BRIEFING", "COMM-KNEEBOARD"}.issubset(local_ids):
                errors.append({"code": "COMM_LOCAL_CRITERIA_REQUIRED", "location": ["criteria"]})
            if not any(c["id"] == "COMM-DOCS-VISIBLE" and c["level"] == "client" for c in data["criteria"]):
                errors.append({"code": "COMM_DOCUMENT_CLIENT_CRITERION_REQUIRED", "location": ["criteria"]})
    if kind == "comm-plan" and not errors:
        nav_errors = validate('navigation', data['navigation'])
        errors.extend({**e, 'location': ['navigation', *e['location']]} for e in nav_errors)
        if not nav_errors:
            nav_groups = {c['group'] for c in data['navigation']['callsigns']}
            if not {r['group'] for r in data['radio_inventory']}.issubset(nav_groups):
                errors.append({'code': 'COMM_CALLSIGN_COVERAGE_REQUIRED', 'location': ['navigation', 'callsigns']})
        net_ids = [net["id"] for net in data["nets"]]
        assignment_ids = [item["group"] for item in data["assignments"]]
        preset_ids = [(item["group"], item["radio"], item["channel"]) for item in data["presets"]]
        usage_ids = [(item["group"], item["phase"], item["radio"]) for item in data["radio_usage"]]
        inventory_ids = [(item["group"], item["radio"]) for item in data["radio_inventory"]]
        if any(len(set(ids)) != len(ids) for ids in (net_ids, assignment_ids, preset_ids, usage_ids, inventory_ids)):
            errors.append({"code": "DUPLICATE_COMM_ENTRY", "location": []})
        if any(item["net"] not in net_ids for item in [*data["assignments"], *data["presets"], *data["radio_usage"]]):
            errors.append({"code": "UNKNOWN_COMM_NET", "location": []})
        expected_usage = {(group, phase, radio) for group, radio in inventory_ids for phase in data["phases"]}
        if set(usage_ids) != expected_usage:
            errors.append({"code": "COMPLETE_RADIO_TIMELINE_REQUIRED", "location": ["radio_usage"]})
        if any((item["group"], item["radio"]) not in inventory_ids for item in data["presets"]):
            errors.append({"code": "RADIO_INVENTORY_REQUIRED", "location": ["presets"]})
    if kind == 'navigation' and not errors:
        from .navigation import findings
        errors.extend(findings(data))
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
