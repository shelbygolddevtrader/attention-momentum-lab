#!/usr/bin/env python3
"""Preflight and run the bounded nine-strategy V002 discovery screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.discovery_screen_v001 import build_preflight, run_discovery_screen, write_json_exclusive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    preflight = build_preflight(
        dataset_root=args.dataset_root,
        manifest_path=args.dataset_manifest,
        evidence_root=args.evidence_root,
        output_path=root / "preflight.csv",
    )
    write_json_exclusive(root / "preflight_summary.json", preflight)
    if args.preflight_only:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 0
    screen = run_discovery_screen(
        dataset_root=args.dataset_root,
        manifest_path=args.dataset_manifest,
        evidence_root=args.evidence_root,
        output_root=root / "screen",
    )
    print(json.dumps({
        "preflight_identity": preflight["identity"],
        "screen_identity": screen["summary"]["identity"],
        "artifact_identity": screen["manifest"]["identity"],
        "classifications": screen["summary"]["classifications"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
