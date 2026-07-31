#!/usr/bin/env python3
"""Validate and print the canonical design-only V004 scoring bundle."""

from __future__ import annotations

import argparse
from pathlib import Path

from aml.professional_strategy_olympics_final_scoring_v004 import (
    canonical_bundle_bytes,
    validate_repository_lineage,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--skip-tag-check", action="store_true")
    args = parser.parse_args()
    bundle = validate_repository_lineage(
        args.repository_root.resolve(), check_tag=not args.skip_tag_check
    )
    print(canonical_bundle_bytes(bundle).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
