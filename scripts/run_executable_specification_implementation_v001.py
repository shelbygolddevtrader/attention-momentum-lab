#!/usr/bin/env python3
"""Build or verify the claim-limited executable-specification campaign."""

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
    CANDIDATE_ID as EXISTING_CANDIDATE_ID,
    build_candidate_bundle as build_existing_candidate_bundle,
)
from aml.benchmark_executable_specification_v001 import (
    build_bundle,
)
from aml.benchmark_candidate_opening_drive_first_pullback_v001 import CANDIDATE_ID


NEW_ADAPTER_ID = "opening-drive-first-pullback-adapter-v001"
NEW_ADAPTER_VERSION = "1.0.0"
EXISTING_ADAPTER_ID = "high-of-day-breakout-candidate-adapter-v001"
EXISTING_ADAPTER_VERSION = "1.0.0"


def registrations(
    *,
    repository_root: Path,
    implementation_config: Path,
    existing_plan: Path,
    library: Path,
    specification_campaign: Path,
) -> tuple[ExecutorRegistration, ...]:
    """Return the exact code-owned registry for this campaign."""

    def execute_existing(output_root: Path) -> None:
        build_existing_candidate_bundle(
            repository_root=repository_root,
            plan_path=existing_plan,
            library_path=library,
            output_root=output_root,
        )

    def execute_new(output_root: Path) -> None:
        build_bundle(
            repository_root=repository_root,
            config_path=implementation_config,
            library_path=library,
            specification_campaign_path=specification_campaign,
            output_root=output_root,
        )

    return (
        ExecutorRegistration(
            library_entry_id=EXISTING_CANDIDATE_ID,
            adapter_id=EXISTING_ADAPTER_ID,
            adapter_version=EXISTING_ADAPTER_VERSION,
            source_root=repository_root,
            execute=execute_existing,
        ),
        ExecutorRegistration(
            library_entry_id=CANDIDATE_ID,
            adapter_id=NEW_ADAPTER_ID,
            adapter_version=NEW_ADAPTER_VERSION,
            source_root=repository_root,
            execute=execute_new,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-config", type=Path, required=True)
    parser.add_argument("--implementation-config", type=Path, required=True)
    parser.add_argument("--existing-plan", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--specification-campaign", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    if args.verify_only:
        result = verify_campaign(
            args.output_root,
            config_path=args.campaign_config,
            library_path=args.library,
            repository_root=root,
        )
    else:
        result = run_campaign(
            config_path=args.campaign_config,
            library_path=args.library,
            output_root=args.output_root,
            registrations=registrations(
                repository_root=root,
                implementation_config=args.implementation_config,
                existing_plan=args.existing_plan,
                library=args.library,
                specification_campaign=args.specification_campaign,
            ),
            repository_root=root,
        )
    print(
        json.dumps(
            {
                "blocked_count": result["blocked_count"],
                "campaign_identity": result["campaign_identity"],
                "executed_count": result["executed_count"],
                "manifest_identity": result["manifest_identity"],
                "result_count": result["result_count"],
                "verified": result["verified"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
