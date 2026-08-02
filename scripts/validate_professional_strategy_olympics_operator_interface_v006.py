#!/usr/bin/env python3
"""Validate and print the design-only V006 operator-interface report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_operator_interface_v006 import validation_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    sys.stdout.buffer.write(validation_report(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
