#!/usr/bin/env python3
"""Print the fail-closed Winner Archetype V001 discovery readiness plan."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from aml.winner_archetype_contracts import canonical_json, load_experiment_spec
from aml.winner_archetype_execution import (
    build_discovery_readiness_plan,
    load_discovery_input_binding,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument(
        "--experiment",
        type=Path,
        default=Path("config/winner_archetype_experiment_v001.json"),
    )
    result.add_argument("--input-binding", type=Path)
    result.add_argument(
        "--as-of",
        help="Required RFC-3339 instant when validating an input binding.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    binding = None
    if args.input_binding:
        if not args.as_of:
            raise SystemExit("--as-of is required with --input-binding")
        spec = load_experiment_spec(args.experiment)
        binding = load_discovery_input_binding(
            args.input_binding,
            expected_experiment_identity=spec.identity,
            as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
        )
    plan = build_discovery_readiness_plan(args.experiment, input_binding=binding)
    print(canonical_json(plan).decode("utf-8"), end="")
    return 2 if plan["status"].startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
