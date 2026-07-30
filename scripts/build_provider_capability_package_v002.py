#!/usr/bin/env python3
"""Print deterministic V002 provider capability contract or decision matrix."""

import argparse
from pathlib import Path

from aml.provider_capability_v002 import canonical_contract_files


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", choices=("contract", "matrix"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    contract, matrix = canonical_contract_files(
        ROOT / "config/winner_archetype_protocol_v002.json",
        ROOT / "config/winner_archetype_source_requirements_v002.json",
    )
    payload = contract if args.artifact == "contract" else matrix
    if args.output is None:
        print(payload.decode("utf-8"), end="")
        return 0
    output = (ROOT / args.output).resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Capability-package output must remain in the repository") from exc
    if output.exists():
        if output.read_bytes() != payload:
            raise ValueError("Immutable capability-package output differs")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
