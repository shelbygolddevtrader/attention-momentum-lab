#!/usr/bin/env python3
"""Validate and print design-only Professional Strategy Olympics artifacts."""

import argparse
from pathlib import Path

from aml.professional_strategy_olympics import (
    load_protocol,
    load_readiness_artifact,
    load_registry,
    load_tournament,
)
from aml.winner_archetype_contracts import canonical_json


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", choices=("protocol", "registry", "tournament", "readiness"))
    args = parser.parse_args(argv)
    protocol = load_protocol(ROOT / "config/professional_strategy_olympics_protocol_v001.json")
    registry = load_registry(
        ROOT / "config/professional_strategy_olympics_strategy_registry_v001.json",
        protocol,
    )
    tournament = load_tournament(
        ROOT / "config/professional_strategy_olympics_tournament_v001.json",
        protocol,
        registry,
    )
    readiness = load_readiness_artifact(
        ROOT / "config/professional_strategy_olympics_readiness_v001.json",
        protocol,
        registry,
        tournament,
    )
    values = {
        "protocol": protocol,
        "registry": registry,
        "tournament": tournament,
        "readiness": readiness,
    }
    print(canonical_json(values[args.artifact]).decode("utf-8"), end="")
    return 2 if args.artifact == "readiness" else 0


if __name__ == "__main__":
    raise SystemExit(main())
