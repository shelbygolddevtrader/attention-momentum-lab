#!/usr/bin/env python3
"""Validate the design-only V010 execution-runtime contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_execution_runtime_v010 import (
    diagnostic_report,
    validation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = validation_report(args.root.resolve())
    except Exception as exc:  # deterministic fail-closed CLI boundary
        sys.stderr.buffer.write(diagnostic_report(exc))
        return 2
    sys.stdout.buffer.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
