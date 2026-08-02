#!/usr/bin/env python3
"""Validate and print the design-only V005 authorization governance report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    OlympicsAuthorizationGovernanceV005Error,
    validation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        sys.stdout.buffer.write(validation_report(args.root.resolve()))
    except OlympicsAuthorizationGovernanceV005Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
