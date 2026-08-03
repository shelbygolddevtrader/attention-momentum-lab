#!/usr/bin/env python3
"""Validate the design-only Olympics V007 runtime-boundary contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_runtime_boundary_v007 import validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    sys.stdout.buffer.write(validation_report(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
