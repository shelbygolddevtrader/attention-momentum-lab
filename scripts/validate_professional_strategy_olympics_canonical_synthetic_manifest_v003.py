#!/usr/bin/env python3
"""Validate the committed canonical V003 synthetic input without execution."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    integrity_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    sys.stdout.buffer.write(integrity_report(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
