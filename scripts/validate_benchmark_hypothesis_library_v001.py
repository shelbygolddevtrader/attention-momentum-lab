#!/usr/bin/env python3
"""Validate the immutable Benchmark Hypothesis Library V001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.benchmark_hypothesis_library_v001 import load_library


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()
    value = load_library(args.library)
    print(
        json.dumps(
            {
                "library_identity": value["library_identity"],
                "source_count": value["source_count"],
                "hypothesis_count": value["hypothesis_count"],
                "registration_status": value["policy"]["registration_scope"],
                "discovery_authorized": False,
                "valid": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
