#!/usr/bin/env python3
"""Publish or verify Benchmark Implementation Campaign V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.benchmark_implementation_campaign_v001 import run_campaign, verify_campaign


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    function = verify_campaign if args.verify_only else run_campaign
    result = function(
        output_root=args.output_root,
        config_path=args.config,
        library_path=args.library,
        repository_root=args.repository_root.resolve(),
    )
    summary = {
        "assessment_count": result["assessment_count"],
        "blocked_count": result["blocked_count"],
        "campaign_identity": result["campaign_identity"],
        "capability_class_counts": result["capability_class_counts"],
        "complete_chain_count": result["complete_chain_count"],
        "manifest_identity": result["manifest_identity"],
        "verified": result["verified"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
