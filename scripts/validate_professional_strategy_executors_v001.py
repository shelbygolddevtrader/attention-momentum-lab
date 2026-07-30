#!/usr/bin/env python3
"""Print the deterministic synthetic executor manifest; never run empirical data."""

from __future__ import annotations

import sys

from aml.professional_strategy_executor_registry_v001 import canonical_bundle_bytes


def main() -> int:
    sys.stdout.buffer.write(canonical_bundle_bytes())
    sys.stdout.buffer.write(b"\n")
    return 2  # Empirical readiness is intentionally blocked.


if __name__ == "__main__":
    raise SystemExit(main())
