#!/usr/bin/env python3
"""Validate the prospective Olympics V002 contract or a test-only fixture."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.professional_strategy_olympics_input_manifest_v002 import (
    load_contract,
    load_manifest,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v002 import (
    adapter_implementation_identity,
    validation_only,
)
from aml.professional_strategy_olympics_orchestrator_v001 import executor_bindings
from aml.winner_archetype_contracts import canonical_json


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Validate V002 synthetic input; never authorize or execute a trial."
    )
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--input", type=Path)
    value.add_argument("--validation-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract = load_contract(root)
    if args.input is None:
        sys.stdout.buffer.write(canonical_json({
            "contract_identity": contract["contract_identity"],
            "status": "V002_CONTRACT_VALID",
            "trial_authorized": False,
            "trial_executed": False,
        }))
        return 0
    if not args.validation_only:
        raise SystemExit("fixture input requires --validation-only; execution is unavailable")
    implementation = adapter_implementation_identity(root)
    manifest = load_manifest(
        args.input, adapter_implementation_identity=implementation,
        bindings=executor_bindings(), canonical_mode=True,
    )
    sys.stdout.buffer.write(validation_only(manifest, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
