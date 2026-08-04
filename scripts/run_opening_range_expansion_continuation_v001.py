#!/usr/bin/env python3
"""Build, verify, or exploratorily exercise Opening Range Expansion V001."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.benchmark_strategy_research_v001 import canonical_json
from aml.opening_range_expansion_continuation_v001 import (
    build_evidence,
    load_config,
    run_bounded_exploratory,
    verify_evidence_directory,
    write_evidence,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/opening_range_expansion_continuation_v001.json"),
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("config/benchmark_hypothesis_library_v001.json"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("manifests/opening_range_expansion_continuation_v001"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--exploratory-output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    config = load_config((root / args.config).resolve(), root)
    evidence_root = (root / args.evidence_root).resolve()
    if args.verify_only:
        if args.dataset_root is not None or args.exploratory_output_root is not None:
            raise SystemExit("--verify-only cannot execute an exploratory run")
        result = verify_evidence_directory(
            evidence_root,
            repository_root=root,
            config=config,
        )
    else:
        artifacts = build_evidence(
            repository_root=root,
            config=config,
            library_path=(root / args.library).resolve(),
        )
        manifest = write_evidence(evidence_root, artifacts)
        result = {
            "evidence_manifest_identity": manifest["identity"],
            "specification_identity": manifest["specification_identity"],
            "verified": True,
        }
        if (args.dataset_root is None) != (args.exploratory_output_root is None):
            raise SystemExit(
                "--dataset-root and --exploratory-output-root must be provided together"
            )
        if args.dataset_root is not None:
            result["exploratory"] = run_bounded_exploratory(
                repository_root=root,
                config=config,
                evidence_artifacts=artifacts,
                dataset_root=args.dataset_root.resolve(),
                output_root=args.exploratory_output_root.resolve(),
            )
    sys.stdout.buffer.write(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
