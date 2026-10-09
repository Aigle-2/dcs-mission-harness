"""Generate the Claude discovery copy from the canonical agent skill."""
from __future__ import annotations

import argparse
from pathlib import Path


def sync(root: Path, check: bool = False) -> bool:
    source = root / ".agents" / "skills"
    destination = root / ".claude" / "skills"
    expected = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    actual = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    if check:
        return expected == actual
    for relative, content in expected.items():
        target = destination / relative
        if target.exists() and actual[relative] != content:
            # Generated copies only; the canonical source is always retained.
            target.write_bytes(content)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return not (set(actual) - set(expected))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if sync(Path(__file__).resolve().parents[1], args.check) else 1)
