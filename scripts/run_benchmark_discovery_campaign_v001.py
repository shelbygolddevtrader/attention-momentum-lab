#!/usr/bin/env python3
"""Publish or verify Benchmark Discovery Campaign V001.

The committed V001 campaign has no authorized executors, so its canonical run
publishes blocked readiness evidence only.  Future executable registrations
must be code-bound through the Python API; this CLI never imports a callable
from user-controlled configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.benchmark_discovery_campaign_v001 import run_campaign, verify_campaign


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify_campaign(
            args.output_root,
            config_path=args.config,
            library_path=args.library,
        )
    else:
        result = run_campaign(
            config_path=args.config,
            library_path=args.library,
            output_root=args.output_root,
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
