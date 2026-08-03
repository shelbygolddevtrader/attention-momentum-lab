#!/usr/bin/env python3
"""Publish deterministic summaries for one immutable discovery screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.discovery_screen_v001 import publish_derived_analysis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-root", type=Path, required=True)
    parser.add_argument("--preflight-summary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = publish_derived_analysis(
        screen_root=args.screen_root,
        preflight_summary_path=args.preflight_summary,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
