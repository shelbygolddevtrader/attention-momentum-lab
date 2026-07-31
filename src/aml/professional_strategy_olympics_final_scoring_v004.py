"""Fail-closed validation for the design-only Olympics V004 scoring contract.

The arithmetic helpers operate only on caller-supplied synthetic atoms.  This
module cannot load market data, execute entrants, rank a tournament, or publish
results.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


SCHEMA = "aml.professional-strategy-olympics.final-scoring-bundle.v004"
VERSION = "professional-strategy-olympics-final-scoring-v004"
BUNDLE_IDENTITY = "205c126be0d3f1af78899b69609a6ba86a0026ec6dd55729112da78eaa4f23bc"
BASE_COMMIT = "ffd76b18d635f22777e26431979037f0965ef1fd"
TAG_NAME = "v0.1.1-research-baseline"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
V003_BUNDLE_IDENTITY = "7f1656ffbd4e577dd1b58019b67a50a48acf0be1d8a05646c8066758644eae81"

SECTION_IDENTITIES = {
    "schema_contract": ("schema_identity", "fedd27dd105a745491467b775f510bd7a32c3b569cd29680f540ca12cb650aa6"),
    "precision_policy": ("precision_identity", "9f2ed50cfbea78323bbde0b6dae7d849c6b691beda49418934296b5c01b53c58"),
    "lifecycle_outcome_semantics": ("lifecycle_outcome_identity", "f0e2f67b1fcc463e469215e45f9310c2fb1cf0c2e8316149da7b623ed30c50db"),
    "portfolio_capital_semantics": ("portfolio_capital_identity", "3b88b780ba933db98701659df59f44e10b962ff1fff9b31762744cdda2ed28ff"),
    "capital_efficiency_semantics": ("capital_efficiency_identity", "11edd9762d8956e9c355e83eff6e33d768f030de35ef06c952b8fb414a1cd68a"),
    "cost_stress_semantics": ("cost_stress_identity", "4373ee78d835a57cb5c5e1e246d49757492c115bc323476fa106032568a2480c"),
    "raw_event_registry": ("raw_event_registry_identity", "094c778707f97ddd3841b55ada4e06c742e348f6886876017376e5aabbb38623"),
    "disqualification_matrix": ("disqualification_identity", "aea0a9decdcf1f5555e9eaa30b0c1ddba7f736ea88836ffbe79448265ad08ccd"),
    "worked_examples": ("worked_examples_identity", "82bd3caabbcdce670fc5eb5d52db757e157930f42e231e04b6c27127a42ea730"),
    "readiness": ("readiness_identity", "59d94ca38ac81bdf1c1bf7591ce5aed7b3781027d6c06022a54410a99cc4390e"),
    "validation_manifest": ("validation_identity", "9024485548fc0a249f22e9e1a17be5d0cf5e7a61e87942777a00ae391f5d9026"),
}
EVENT_IDS = (
    "net_expectancy", "downside_adjusted_return", "maximum_drawdown",
    "profit_factor", "payoff_ratio", "hit_rate", "tail_loss",
    "monthly_stability", "regime_stability", "validation_consistency",
    "holdout_consistency", "capital_efficiency", "trade_sufficiency",
    "execution_robustness", "sensitivity_robustness",
)
EVENT_FIELDS = {
    "event_id", "name", "purpose", "unit", "direction", "domain", "inputs",
    "timestamp_semantics", "population", "formula", "intermediate_rounding",
    "final_rounding", "missing", "zero_denominator", "non_finite",
    "minimum_observations", "disqualification", "aggregation_level",
    "aggregation_order", "weight", "winsorization", "tie_fields",
    "stage_availability", "reference_example",
}


class OlympicsFinalScoringV004Error(ValueError):
    """The V004 contract, identity, or research boundary is invalid."""


@dataclass(frozen=True)
class SyntheticCapitalTrade:
    trade_id: str
    net_pnl_microdollars: int
    quantity: int
    entry_price_microdollars: int
    entry_nanoseconds: int
    exit_nanoseconds: int
    accepted: bool = True
    filled: bool = True
    completed: bool = True


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise OlympicsFinalScoringV004Error("V004 bundle is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsFinalScoringV004Error("V004 JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OlympicsFinalScoringV004Error(item)
            ),
        )
        canonical_json(value)
    except OlympicsFinalScoringV004Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsFinalScoringV004Error("V004 bundle must be strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OlympicsFinalScoringV004Error("V004 root must be an object")
    return value


def _validate_identity(section: Mapping[str, object], field: str, expected: str) -> None:
    identity = section.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsFinalScoringV004Error(f"{field} must be a SHA-256 identity")
    payload = {key: value for key, value in section.items() if key != field}
    if canonical_hash(payload) != identity or identity != expected:
        raise OlympicsFinalScoringV004Error(f"{field} is stale or tampered")


def validate_bundle(value: Mapping[str, object]) -> dict[str, object]:
    if value.get("schema_version") != SCHEMA or value.get("clarification_version") != VERSION:
        raise OlympicsFinalScoringV004Error("V004 schema or version changed")
    for section, (field, expected) in SECTION_IDENTITIES.items():
        item = value.get(section)
        if not isinstance(item, Mapping):
            raise OlympicsFinalScoringV004Error(f"missing V004 section: {section}")
        _validate_identity(item, field, expected)
    bundle_identity = value.get("bundle_identity")
    payload = {key: item for key, item in value.items() if key != "bundle_identity"}
    if bundle_identity != BUNDLE_IDENTITY or canonical_hash(payload) != bundle_identity:
        raise OlympicsFinalScoringV004Error("V004 bundle identity is stale or tampered")

    predecessors = value.get("predecessors")
    if not isinstance(predecessors, Mapping):
        raise OlympicsFinalScoringV004Error("V004 predecessors are missing")
    expected_predecessors = {
        "design_base_commit": BASE_COMMIT,
        "v003_bundle_identity": V003_BUNDLE_IDENTITY,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
    }
    for field, expected in expected_predecessors.items():
        if predecessors.get(field) != expected:
            raise OlympicsFinalScoringV004Error(f"predecessor changed: {field}")

    events = value["raw_event_registry"].get("events")
    if not isinstance(events, list) or tuple(event.get("event_id") for event in events) != EVENT_IDS:
        raise OlympicsFinalScoringV004Error("V004 must freeze exactly 15 ordered events")
    if any(set(event) != EVENT_FIELDS for event in events):
        raise OlympicsFinalScoringV004Error("a V004 raw event is incomplete or has unknown fields")
    if sum(event["weight"] for event in events) != 100:
        raise OlympicsFinalScoringV004Error("V004 event weights must total 100")

    examples = value["worked_examples"].get("examples")
    required_example_fields = {"id", "inputs", "intermediate", "raw_events", "ranks", "final_result"}
    if not isinstance(examples, list) or len(examples) != 19:
        raise OlympicsFinalScoringV004Error("V004 must contain 19 frozen examples")
    if any(set(example) != required_example_fields for example in examples):
        raise OlympicsFinalScoringV004Error("a V004 worked example is incomplete")
    if len({example["id"] for example in examples}) != len(examples):
        raise OlympicsFinalScoringV004Error("V004 worked example ids must be unique")

    authorization = value.get("authorization")
    if not isinstance(authorization, Mapping) or not authorization:
        raise OlympicsFinalScoringV004Error("V004 authorization is missing")
    if any(type(flag) is not bool or flag for flag in authorization.values()):
        raise OlympicsFinalScoringV004Error("every V004 authorization must remain false")
    readiness = value["readiness"]
    forbidden_true = {
        "tournament_runner_implemented", "official_run_authorized",
        "historical_run_authorized", "synthetic_trial_authorized",
        "tournament_scoring_executed", "empirical_data_accessed",
        "validation_opened", "holdout_opened", "performance_claim",
    }
    if any(readiness.get(field) is not False for field in forbidden_true):
        raise OlympicsFinalScoringV004Error("V004 design-only readiness boundary changed")
    return dict(value)


def load_bundle(path: Path) -> dict[str, object]:
    return validate_bundle(_strict_json(path))


def canonical_bundle_bytes(value: Mapping[str, object]) -> bytes:
    validate_bundle(value)
    canonical = canonical_json(value)
    return canonical if canonical.endswith(b"\n") else canonical + b"\n"


def capital_efficiency(trades: Sequence[SyntheticCapitalTrade]) -> Fraction | None:
    """Return exact synthetic capital efficiency; ``None`` means event-ineligible."""
    seen: set[str] = set()
    numerator = 0
    denominator = 0
    for trade in trades:
        if trade.trade_id in seen:
            raise OlympicsFinalScoringV004Error("duplicate synthetic trade identity")
        seen.add(trade.trade_id)
        if type(trade.quantity) is not int or type(trade.entry_price_microdollars) is not int:
            raise OlympicsFinalScoringV004Error("capital atoms must be integers")
        if not (trade.accepted and trade.filled and trade.completed):
            continue
        if trade.quantity <= 0 or trade.entry_price_microdollars <= 0:
            raise OlympicsFinalScoringV004Error("filled quantity and price must be positive")
        if trade.exit_nanoseconds <= trade.entry_nanoseconds:
            raise OlympicsFinalScoringV004Error("capital interval must be positive and half-open")
        numerator += trade.net_pnl_microdollars
        denominator += abs(trade.quantity) * trade.entry_price_microdollars * (
            trade.exit_nanoseconds - trade.entry_nanoseconds
        )
    return None if denominator == 0 else Fraction(numerator, denominator)


def exact_median(values: Sequence[Fraction]) -> Fraction:
    if not values:
        raise OlympicsFinalScoringV004Error("median requires observations")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def compare_downside_adjusted(
    left_mu: Fraction, left_q: Fraction, right_mu: Fraction, right_q: Fraction
) -> int:
    """Compare mu/sqrt(q) exactly without evaluating a square root."""
    if left_q <= 0 or right_q <= 0:
        raise OlympicsFinalScoringV004Error("downside second moments must be positive")
    if left_mu < 0 <= right_mu:
        return -1
    if right_mu < 0 <= left_mu:
        return 1
    left_square = left_mu * left_mu * right_q
    right_square = right_mu * right_mu * left_q
    comparison = (left_square > right_square) - (left_square < right_square)
    return -comparison if left_mu < 0 else comparison


def validate_repository_lineage(root: Path, *, check_tag: bool = True) -> dict[str, object]:
    bundle = load_bundle(root / "config/professional_strategy_olympics_final_scoring_v004.json")
    from aml.professional_strategy_olympics_scoring_v003 import (  # noqa: PLC0415
        validate_repository_lineage as validate_v003_lineage,
    )

    validate_v003_lineage(root, check_tag=check_tag)
    if check_tag:
        object_id = subprocess.run(
            ["git", "rev-parse", TAG_NAME], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        commit_id = subprocess.run(
            ["git", "rev-parse", f"{TAG_NAME}^{{}}"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        if object_id != TAG_OBJECT or commit_id != TAGGED_COMMIT:
            raise OlympicsFinalScoringV004Error("immutable research-baseline tag changed")
    return bundle
