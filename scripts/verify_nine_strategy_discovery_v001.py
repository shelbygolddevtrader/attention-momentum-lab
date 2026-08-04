#!/usr/bin/env python3
"""Verify accepted discovery metadata and prose against immutable artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.discovery_screen_v001 import verify_published_discovery_claims


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-root", type=Path, required=True)
    parser.add_argument("--preflight-summary", type=Path, required=True)
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("config/nine_strategy_discovery_screen_v001_metadata.json"),
    )
    parser.add_argument(
        "--documentation",
        type=Path,
        default=Path("docs/NINE_STRATEGY_DISCOVERY_SCREEN_V001.md"),
    )
    args = parser.parse_args()
    result = verify_published_discovery_claims(
        screen_root=args.screen_root,
        preflight_summary_path=args.preflight_summary,
        analysis_root=args.analysis_root,
        metadata_path=args.metadata,
        documentation_path=args.documentation,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
