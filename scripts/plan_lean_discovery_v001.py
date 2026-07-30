#!/usr/bin/env python3
"""Validate and print the non-empirical lean discovery plan."""

from __future__ import annotations

import argparse
from pathlib import Path

from aml.lean_discovery_protocol import build_readiness, canonical_protocol_bytes, cost_plan, load_protocol
from aml.winner_archetype_contracts import canonical_json


ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "command",
        choices=("validate", "readiness", "cost-plan"),
    )
    result.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/lean_discovery_protocol_v001.json"),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    protocol = load_protocol(path)
    if args.command == "validate":
        print(canonical_protocol_bytes(path).decode("utf-8"), end="")
        return 0
    if args.command == "cost-plan":
        print(canonical_json(cost_plan(protocol)).decode("utf-8"), end="")
        return 0
    readiness = build_readiness(protocol)
    print(canonical_json(readiness).decode("utf-8"), end="")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
