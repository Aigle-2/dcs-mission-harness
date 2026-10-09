"""Apply approved communications to parsed DCS tables; never evaluate mission Lua."""
from __future__ import annotations

import copy
import zipfile
from decimal import Decimal
from pathlib import Path
from .core import HarnessError, require_valid

# Conservative verified subset, not a universal DCS radio capability database.
# Sources and extension procedure: docs/communications.md.
UHF_AIRCRAFT = {"FA-18C_hornet", "F-14BU"}

def keyed(table: dict, key: int):
    if key in table:
        return key
    if str(key) in table:
        return str(key)
    raise HarnessError("RADIO_OR_PRESET_UNAVAILABLE", "BLOCKED")

def groups(table: dict) -> dict:
    found = {}
    for side in table.get("coalition", {}).values():
        for country in side.get("country", {}).values():
            for category in ("plane", "helicopter", "ship"):
                for group in country.get(category, {}).get("group", {}).values():
                    if group["name"] in found:
                        raise HarnessError("AMBIGUOUS_COMM_GROUP")
                    found[group["name"]] = (category, group)
    return found

def compatible(unit: dict, radio: int, net: dict):
    if unit["type"] not in UHF_AIRCRAFT or radio not in (1, 2):
        raise HarnessError("RADIO_CAPABILITY_NOT_VERIFIED", "BLOCKED")
    freq = Decimal(str(net["frequency_mhz"]))
    if net["modulation"] != "AM" or not Decimal("225") <= freq <= Decimal("399.975") or freq * 1000 % 25:
        raise HarnessError("RADIO_FREQUENCY_NOT_SUPPORTED", "BLOCKED")

def set_frequency_tasks(value, frequency, modulation):
    if isinstance(value, dict):
        if value.get("id") == "SetFrequency":
            value["params"].update(frequency=frequency * 1_000_000, modulation=modulation)
        for child in value.values():
            set_frequency_tasks(child, frequency, modulation)
    elif isinstance(value, list):
        for child in value:
            set_frequency_tasks(child, frequency, modulation)

def apply_plan(mission: dict, plan: dict) -> dict:
    require_valid("comm-plan", plan)
    output = copy.deepcopy(mission)
    available = groups(output)
    nets = {n["id"]: n for n in plan["nets"]}
    touched = {p["group"] for p in [*plan["assignments"], *plan["presets"], *plan["radio_usage"]]}
    if not touched.issubset(available):
        raise HarnessError("COMM_GROUP_NOT_FOUND")
    client_groups = {name for name, (_, g) in available.items()
                     if any(u.get("skill") in {"Client", "Player"} for u in g["units"].values())}
    assigned = {a["group"] for a in plan["assignments"]}
    preset_groups = {p["group"] for p in plan["presets"]}
    usage_groups = {p["group"] for p in plan["radio_usage"]}
    if not client_groups.issubset(assigned & preset_groups & usage_groups):
        raise HarnessError("COMM_CLIENT_COVERAGE_REQUIRED")
    for name in client_groups:
        inventory = [r for r in plan["radio_inventory"] if r["group"] == name]
        _, group = available[name]
        # Current adapter supports precisely these two-radio player aircraft.
        if {r["radio"] for r in inventory} != {1, 2} or any(u["type"] not in UHF_AIRCRAFT for u in group["units"].values()):
            raise HarnessError("COMPLETE_AIRCRAFT_RADIO_INVENTORY_REQUIRED", "BLOCKED")
        if any(r["aircraft"] != u["type"] for r in inventory for u in group["units"].values()):
            raise HarnessError("RADIO_INVENTORY_AIRCRAFT_MISMATCH")
    for item in plan["assignments"]:
        category, group = available[item["group"]]
        net = nets[item["net"]]
        modulation = 0 if net["modulation"] == "AM" else 1
        if category == "ship":
            if modulation != 0:
                raise HarnessError("SHIP_MODULATION_NOT_SUPPORTED", "BLOCKED")
            for unit in group["units"].values():
                unit["frequency"] = net["frequency_mhz"] * 1_000_000
        else:
            group.update(frequency=net["frequency_mhz"], modulation=modulation, radioSet=True)
            set_frequency_tasks(group.get("route", {}), net["frequency_mhz"], modulation)
    for item in plan["presets"]:
        category, group = available[item["group"]]
        if category == "ship":
            raise HarnessError("SHIP_PRESETS_NOT_SUPPORTED", "BLOCKED")
        for unit in group["units"].values():
            compatible(unit, item["radio"], nets[item["net"]])
            radios = unit.get("Radio", {})
            radio = radios[keyed(radios, item["radio"])]
            channels = radio["channels"]
            channels[keyed(channels, item["channel"])] = nets[item["net"]]["frequency_mhz"]
    for usage in plan["radio_usage"]:
        if not any(p["group"] == usage["group"] and p["radio"] == usage["radio"] and p["net"] == usage["net"] for p in plan["presets"]):
            raise HarnessError("ACTIVE_NET_PRESET_REQUIRED")
    # DCS can overwrite the first compatible preset with the group's frequency.
    for name in client_groups:
        _, group = available[name]
        assignment = next(a for a in plan["assignments"] if a["group"] == name)
        for radio in {p["radio"] for p in plan["presets"] if p["group"] == name}:
            preset = next((p for p in plan["presets"] if p["group"] == name and p["radio"] == radio and p["channel"] == 1), None)
            if not preset or nets[preset["net"]]["frequency_mhz"] != nets[assignment["net"]]["frequency_mhz"]:
                raise HarnessError("FIRST_PRESET_FLIGHT_FREQUENCY_CONFLICT", "BLOCKED")
    return output

def check_plan(mission: dict, plan: dict) -> None:
    expected = apply_plan(mission, plan)
    actual_groups, expected_groups = groups(mission), groups(expected)
    for name in {p["group"] for p in [*plan["assignments"], *plan["presets"]]}:
        if actual_groups[name] != expected_groups[name]:
            raise HarnessError("COMM_PLAN_NOT_APPLIED")

def check_archive(artifact: Path, plan: dict) -> None:
    try:
        from dcs.lua import loads
    except ImportError:
        raise HarnessError("DCS_TABLE_PARSER_UNAVAILABLE", "BLOCKED") from None
    try:
        with zipfile.ZipFile(artifact) as archive:
            table = loads(archive.read("mission").decode("utf-8-sig"))["mission"]
        check_plan(table, plan)
    except HarnessError:
        raise
    except Exception:
        # Parser diagnostics can echo mission contents or private paths.
        raise HarnessError("MISSION_COMM_TABLE_UNREADABLE") from None
