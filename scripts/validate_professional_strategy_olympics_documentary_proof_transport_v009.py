#!/usr/bin/env python3
"""Pure validator for the design-only V009 documentary-proof transport."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_documentary_proof_transport_v009 import (
    validation_report,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path.cwd())
    return value


def main() -> int:
    args = parser().parse_args()
    sys.stdout.buffer.write(validation_report(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
