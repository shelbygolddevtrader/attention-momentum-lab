#!/usr/bin/env python3
"""Build, verify, or exploratorily exercise VWAP Deviation Mean Reversion V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from aml.benchmark_strategy_research_v001 import canonical_json
from aml.vwap_deviation_mean_reversion_child_v001 import (
    EVIDENCE_REQUIRED_ROLES,
    build_evidence,
    default_config,
    load_config,
    run_bounded_exploratory,
    verify_evidence_directory,
    verify_exploratory_bundle,
    write_evidence,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/vwap_deviation_mean_reversion_child_v001.json"),
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("config/benchmark_hypothesis_library_v001.json"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("manifests/vwap_deviation_mean_reversion_child_v001"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--write-default-config", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--exploratory-output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    config_path = (root / args.config).resolve()
    if args.write_default_config:
        if args.verify_only or args.dataset_root or args.exploratory_output_root:
            raise SystemExit("--write-default-config cannot run or verify the candidate")
        if config_path.exists():
            raise SystemExit("configuration already exists")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_bytes(canonical_json(default_config(root)))
        sys.stdout.buffer.write(canonical_json({"written": str(config_path)}))
        return 0

    config = load_config(config_path, root)
    evidence_root = (root / args.evidence_root).resolve()
    if args.verify_only:
        if args.dataset_root is not None:
            raise SystemExit("--verify-only cannot access a dataset")
        result = verify_evidence_directory(
            evidence_root,
            repository_root=root,
            config=config,
        )
        if args.exploratory_output_root is not None:
            result["exploratory"] = verify_exploratory_bundle(
                args.exploratory_output_root.resolve(),
                repository_root=root,
                config=config,
                evidence_root=evidence_root,
            )
    else:
        if evidence_root.exists():
            evidence_status = verify_evidence_directory(
                evidence_root,
                repository_root=root,
                config=config,
            )
            artifacts = {
                name: json.loads((evidence_root / name).read_text(encoding="utf-8"))
                for name in EVIDENCE_REQUIRED_ROLES
            }
            manifest_identity = evidence_status["evidence_manifest_identity"]
        else:
            artifacts = build_evidence(
                repository_root=root,
                config=config,
                library_path=(root / args.library).resolve(),
            )
            manifest = write_evidence(evidence_root, artifacts)
            manifest_identity = manifest["identity"]
        result = {
            "evidence_manifest_identity": manifest_identity,
            "specification_identity": config["specification_identity"],
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
