#!/usr/bin/env python3
"""Run the write-once, non-empirical Exploratory Research Mode V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.exploratory_research_mode_v001 import run_exploratory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("config/exploratory_research_mode_v001.json"),
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("config/benchmark_hypothesis_library_v001.json"),
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    result = run_exploratory(
        repository_root=repository_root,
        plan_path=args.plan.resolve(),
        library_path=args.library.resolve(),
        dataset_root=args.dataset_root.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
