#!/usr/bin/env python3
"""Run or verify the write-once Contaminated Economic POC V001 bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.contaminated_economic_poc_v001 import (
    run_contaminated_economic_poc,
    verify_poc_directory,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.repository_root.resolve()
    output = (
        args.output_root.resolve()
        if args.output_root
        else root / "manifests/exploratory_economic_poc/v001"
    )
    if args.verify_only:
        result = verify_poc_directory(output)
    else:
        if args.dataset_root is None:
            raise SystemExit("--dataset-root is required for execution")
        result = run_contaminated_economic_poc(
            repository_root=root,
            dataset_root=args.dataset_root.resolve(),
            output_root=output,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
