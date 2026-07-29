#!/usr/bin/env python3
"""Validate Winner Archetype V0.1 contracts using local or synthetic inputs only."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


sys.dont_write_bytecode = True

from aml.winner_archetype import (  # noqa: E402
    CandidateEvent,
    MinuteBar,
    calculate_outcome,
    plan_chronological_partitions,
    plan_matched_controls,
)
from aml.winner_archetype_contracts import (  # noqa: E402
    HYPOTHESIS_SCHEMA,
    OUTCOME_DEFINITION_SCHEMA,
    HypothesisRecord,
    OutcomeDefinition,
    canonical_hash,
    load_experiment_spec,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "config/winner_archetype_experiment_v001.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-spec")
    partition = commands.add_parser("partition-plan")
    partition.add_argument("--sessions", type=int, default=60)
    outcome = commands.add_parser("synthetic-outcome")
    outcome.add_argument(
        "--case", choices=("winner", "non-winner", "ambiguous"), default="winner"
    )
    commands.add_parser("synthetic-match")
    hypothesis = commands.add_parser("validate-hypothesis")
    hypothesis.add_argument("path", type=Path)
    return value


def _synthetic_sessions(count: int) -> list[str]:
    if count < 30 or count > 252:
        raise ValueError("Synthetic session count must be within [30, 252]")
    current = date(2024, 6, 3)
    sessions: list[str] = []
    while len(sessions) < count:
        if current.weekday() < 5:
            sessions.append(current.isoformat())
        current += timedelta(days=1)
    return sessions


def _outcome_definition() -> OutcomeDefinition:
    return OutcomeDefinition(
        schema_version=OUTCOME_DEFINITION_SCHEMA,
        definition_version="synthetic-cli-v001",
        direction="long",
        reference_price_semantics="bar_open",
        reference_time="09:30",
        evaluation_start="09:30",
        evaluation_end="09:34",
        session_timezone="America/New_York",
        upside_threshold=0.1,
        downside_threshold=0.05,
        reward_to_risk_multiple=2.0,
        sustained_momentum_threshold=0.05,
        sustained_minutes=2,
        close_above_reference="evaluation_close",
        ambiguity_rule="downside_first_conservative",
        missing_minute_rule="no_forward_fill_mark_incomplete",
        halt_treatment="exclude_verified_halt_minutes_and_report",
    )


def _synthetic_bars(case: str) -> list[MinuteBar]:
    zone = ZoneInfo("America/New_York")
    start = datetime(2024, 6, 3, 9, 30, tzinfo=zone)
    if case == "winner":
        prices = [(100, 101, 99, 100), (100, 106, 100, 105), (105, 111, 104, 110), (110, 112, 109, 111), (111, 113, 110, 112)]
    elif case == "ambiguous":
        prices = [(100, 111, 94, 100)] + [(100, 101, 99, 100)] * 4
    else:
        prices = [(100, 101, 99, 100), (100, 100, 94, 95), (95, 96, 93, 94), (94, 95, 93, 94), (94, 95, 93, 94)]
    return [
        MinuteBar(
            (start + timedelta(minutes=index)).isoformat(), "SYNTH",
            "2024-06-03", "America/New_York", *values, 1_000,
        )
        for index, values in enumerate(prices)
    ]


def _events() -> list[CandidateEvent]:
    def event(identifier: str, symbol: str, winner: bool, shift: float) -> CandidateEvent:
        return CandidateEvent(
            event_id=identifier,
            session="2024-06-03",
            symbol=symbol,
            security_identifier=f"SYNTHETIC-{symbol}",
            winner=winner,
            pre_outcome_features={
                "price": 10 + shift,
                "premarket_gap": .10 + shift / 100,
                "premarket_dollar_volume": 2_000_000 + shift * 10_000,
                "premarket_relative_volume": 8 + shift / 10,
                "atr_percent_20": .08 + shift / 1000,
                "spread_bps": 20 + shift,
            },
        )
    return [
        event("synthetic-winner-001", "AAA", True, 0),
        event("synthetic-control-001", "BBB", False, 1),
        event("synthetic-control-002", "CCC", False, 2),
    ]


def _load_hypothesis(path: Path) -> HypothesisRecord:
    normalized_parts = {part.casefold().replace("_", "-") for part in path.parts}
    if normalized_parts & {"holdout", "sealed", "validation-extension", "forward-validation"}:
        raise ValueError("Hypothesis CLI cannot access protected outcome paths")
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Hypothesis path contains a symlink")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("Hypothesis path is unsafe")
    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"Duplicate hypothesis key: {key}")
            result[key] = item
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if not isinstance(value, dict) or value.get("schema_version") != HYPOTHESIS_SCHEMA:
        raise ValueError("Hypothesis file has an unsupported schema")
    return HypothesisRecord.from_mapping(value)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    spec = load_experiment_spec(args.spec)
    if args.command == "validate-spec":
        print(json.dumps({"experiment_id": spec.identity, "valid": True}, sort_keys=True))
    elif args.command == "partition-plan":
        plan = plan_chronological_partitions(
            _synthetic_sessions(args.sessions), spec.partition_spec
        )
        print(json.dumps(plan.to_dict(), sort_keys=True))
    elif args.command == "synthetic-outcome":
        outcome = calculate_outcome(
            symbol="SYNTH",
            security_identifier="SYNTHETIC-SYNTH",
            session="2024-06-03",
            definition=_outcome_definition(),
            bars=_synthetic_bars(args.case),
            input_manifest_hash=canonical_hash({"synthetic": True, "case": args.case}),
        )
        print(json.dumps(asdict(outcome), sort_keys=True))
    elif args.command == "synthetic-match":
        matches = plan_matched_controls(_events(), spec.control_matching_spec)
        print(json.dumps([asdict(item) for item in matches], sort_keys=True))
    else:
        hypothesis = _load_hypothesis(args.path)
        print(json.dumps({"hypothesis_identity": canonical_hash(hypothesis.identity_payload()), "valid": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
