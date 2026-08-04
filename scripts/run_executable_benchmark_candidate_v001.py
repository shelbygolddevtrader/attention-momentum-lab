#!/usr/bin/env python3
"""Run or verify the one-candidate Benchmark Discovery Campaign V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.benchmark_discovery_campaign_v001 import (
    ExecutorRegistration,
    run_campaign,
    verify_campaign,
)
from aml.benchmark_executable_candidate_v001 import (
    CANDIDATE_ID,
    build_candidate_bundle,
)


ADAPTER_ID = "high-of-day-breakout-candidate-adapter-v001"
ADAPTER_VERSION = "1.0.0"


def _registration(
    *,
    repository_root: Path,
    plan_path: Path,
    library_path: Path,
) -> ExecutorRegistration:
    """Return the sole code-owned runtime registration for this campaign."""

    def execute(output_root: Path) -> None:
        build_candidate_bundle(
            repository_root=repository_root,
            plan_path=plan_path,
            library_path=library_path,
            output_root=output_root,
        )

    return ExecutorRegistration(
        library_entry_id=CANDIDATE_ID,
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        source_root=repository_root,
        execute=execute,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    if args.verify_only:
        result = verify_campaign(
            args.output_root,
            config_path=args.config,
            library_path=args.library,
            repository_root=repository_root,
        )
    else:
        result = run_campaign(
            config_path=args.config,
            library_path=args.library,
            output_root=args.output_root,
            registrations=(
                _registration(
                    repository_root=repository_root,
                    plan_path=args.plan,
                    library_path=args.library,
                ),
            ),
            repository_root=repository_root,
        )
    summary = {
        "blocked_count": result["blocked_count"],
        "campaign_identity": result["campaign_identity"],
        "executed_count": result["executed_count"],
        "manifest_identity": result["manifest_identity"],
        "result_count": result["result_count"],
        "verified": result["verified"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
