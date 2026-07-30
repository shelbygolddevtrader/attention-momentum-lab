#!/usr/bin/env python3
"""Validate and print the design-only executable Olympics V002 contract bundle."""

from pathlib import Path

from aml.professional_strategy_olympics_v002 import canonical_bundle_bytes, load_bundle


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    bundle = load_bundle(ROOT / "config/professional_strategy_olympics_v002.json")
    print(canonical_bundle_bytes(bundle).decode("utf-8"), end="")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
