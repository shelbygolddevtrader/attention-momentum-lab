#!/usr/bin/env python3
"""Validate and print the design-only lean capital governance contract."""

from pathlib import Path

from aml.lean_capital_governance import canonical_governance_bytes


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "config/lean_discovery_capital_governance_v001.json"
    print(canonical_governance_bytes(path).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
