#!/usr/bin/env python3
"""Build, publish, or verify Benchmark Specification Campaign V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.benchmark_specification_campaign_v001 import (
    build_config,
    publish_campaign,
    verify_campaign,
)
from aml.benchmark_strategy_research_v001 import canonical_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config", type=Path,
        default=Path("config/benchmark_specification_campaign_v001.json"),
    )
    parser.add_argument(
        "--library", type=Path,
        default=Path("config/benchmark_hypothesis_library_v001.json"),
    )
    parser.add_argument(
        "--readiness", type=Path,
        default=Path("config/benchmark_implementation_campaign_v001.json"),
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--bootstrap-config", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--created-at")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    library_path = args.library if args.library.is_absolute() else root / args.library
    readiness_path = args.readiness if args.readiness.is_absolute() else root / args.readiness
    if args.bootstrap_config:
        if not args.source_commit or not args.created_at:
            parser.error("--bootstrap-config requires --source-commit and --created-at")
        if config_path.exists() or config_path.is_symlink():
            raise SystemExit("refusing to overwrite existing canonical config")
        config_path.write_bytes(
            canonical_json(
                build_config(
                    repository_root=root,
                    source_commit=args.source_commit,
                    created_at=args.created_at,
                )
            )
        )
        print(config_path)
        return 0
    if args.output_root is None:
        parser.error("--output-root is required unless --bootstrap-config is used")
    output_root = args.output_root if args.output_root.is_absolute() else root / args.output_root
    function = verify_campaign if args.verify_only else publish_campaign
    result = function(
        config_path=config_path,
        library_path=library_path,
        readiness_path=readiness_path,
        output_root=output_root,
        repository_root=root,
    )
    print(
        json.dumps(
            {
                "campaign_identity": result["campaign_identity"],
                "classification": result["classification"],
                "manifest_identity": result["manifest_identity"],
                "selected_library_entry_id": result["selected_library_entry_id"],
                "specification_identity": result["specification_identity"],
                "verified": result["verified"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
