#!/usr/bin/env python3
"""Validate and print the design-only Olympics scoring clarification V003."""

from __future__ import annotations

from pathlib import Path
import sys

from aml.professional_strategy_olympics_scoring_v003 import (
    canonical_bundle_bytes,
    validate_repository_lineage,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    bundle = validate_repository_lineage(ROOT)
    sys.stdout.buffer.write(canonical_bundle_bytes(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
