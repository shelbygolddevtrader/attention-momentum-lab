"""Deterministic, authorization-gated orchestration for Olympics V004.

The public default is validation-only.  Trial execution requires both an
explicit execute request and an identity-bound authorization artifact.  No
network, market-data, broker, forward-validation, or holdout interface exists.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from functools import cmp_to_key
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from aml.professional_strategy_executor_registry_v001 import implementation_bundle
from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY as V004_BUNDLE_IDENTITY,
    EVENT_IDS,
    SyntheticCapitalTrade,
    capital_efficiency,
    compare_downside_adjusted,
    exact_median,
    validate_repository_lineage,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


SCHEMA = "aml.professional-strategy-olympics.orchestrator.v001"
VERSION = "professional-strategy-olympics-orchestrator-v001"
ORCHESTRATOR_IDENTITY = "9e1af13518bc4c6588ce4faaf302e15182f9d42e5dd8c453fc6d27dd257b8d3e"
INPUT_SCHEMA = "aml.professional-strategy-olympics.synthetic-input-manifest.v001"
AUTHORIZATION_SCHEMA = "aml.professional-strategy-olympics.synthetic-trial-authorization.v001"
EXECUTOR_BUNDLE_IDENTITY = "9c03677ce4ea4e56256f6873c00a4cdc502e23b2780f36af6b3f2a0b3b45bf5d"
EXECUTOR_REGISTRY_IDENTITY = "01c0efa7b35707ddbc837609f99051cdc3db63064410de9d10e334d601787111"
SCENARIOS = ("base_1x", "stress_1_5x", "stress_2x")
DISQUALIFICATION_CONDITIONS = frozenset({
    "schema_violation_or_non_finite_source_value",
    "nondeterministic_executor_output",
    "lookahead_or_prohibited_data_access",
    "capital_risk_or_negative_cash_breach",
    "invalid_post_fill_price_or_missing_nonhalt_open_position_bar",
    "entrant_identity_mismatch_or_unauthorized_strategy_mutation",
    "manifest_mismatch_or_unreconciled_entrant_ledger",
    "duplicate_proposal_identity",
})
ARTIFACT_NAMES = (
    "run_manifest.json",
    "input_manifest.json",
    "identity_manifest.json",
    "raw_event_registry.json",
    "eligibility_disqualification_ledger.json",
    "event_score_ledger.json",
    "aggregate_score_ledger.json",
    "ranking_ledger.json",
    "integrity_report.json",
    "SUMMARY.md",
)
TRADE_FIELDS = {
    "proposal_identity", "symbol", "entry_nanoseconds", "exit_nanoseconds",
    "quantity", "raw_entry_microdollars", "raw_exit_microdollars",
    "entry_price_microdollars", "target_microdollars",
    "entry_commission_microdollars", "exit_commission_microdollars",
    "risk_budget_microdollars", "net_pnl_microdollars", "net_R",
    "exit_month_new_york", "regime_label",
}
ENTRANT_FIELDS = {
    "strategy_id", "strategy_identity", "executor_identity", "disqualified",
    "disqualification_reasons", "active_dates", "trades",
    "sensitivity_variant_expectancies",
}
INPUT_FIELDS = {
    "schema_version", "manifest_identity", "scoring_bundle_identity", "synthetic",
    "fixture_identity", "opened_stages", "entrants",
}


class OlympicsOrchestratorV001Error(ValueError):
    """An orchestrator identity, input, authorization, or integrity rule failed."""


@dataclass(frozen=True)
class EventValue:
    event_id: str
    eligible: bool
    reason: str
    raw: object | None
    tie: object | None = None


def _strict_json(path: Path, *, maximum_bytes: int = 5_000_000) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > maximum_bytes:
        raise OlympicsOrchestratorV001Error("JSON input is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsOrchestratorV001Error("JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OlympicsOrchestratorV001Error(item)
            ),
        )
        canonical_json(value)
    except OlympicsOrchestratorV001Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsOrchestratorV001Error("input must be strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OlympicsOrchestratorV001Error("JSON root must be an object")
    return value


def _identity(value: Mapping[str, object], field: str) -> str:
    identity = value.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsOrchestratorV001Error(f"{field} must be a SHA-256 identity")
    payload = {key: item for key, item in value.items() if key != field}
    if canonical_hash(payload) != identity:
        raise OlympicsOrchestratorV001Error(f"{field} is stale or tampered")
    return identity


def implementation_identity(root: Path) -> str:
    """Bind the exact contract, module, and CLI bytes without self-reference."""
    files = (
        root / "src/aml/professional_strategy_olympics_orchestrator_v001.py",
        root / "scripts/run_professional_strategy_olympics_orchestrator_v001.py",
    )
    if any(not path.is_file() for path in files):
        raise OlympicsOrchestratorV001Error("orchestrator implementation file is missing")
    return canonical_hash({
        "orchestrator_contract_identity": ORCHESTRATOR_IDENTITY,
        "module_sha256": hashlib.sha256(files[0].read_bytes()).hexdigest(),
        "cli_sha256": hashlib.sha256(files[1].read_bytes()).hexdigest(),
    })


def load_orchestrator_contract(root: Path) -> dict[str, object]:
    path = root / "config/professional_strategy_olympics_orchestrator_v001.json"
    value = _strict_json(path)
    if value.get("schema_version") != SCHEMA or value.get("orchestrator_version") != VERSION:
        raise OlympicsOrchestratorV001Error("unsupported orchestrator contract")
    if _identity(value, "orchestrator_identity") != ORCHESTRATOR_IDENTITY:
        raise OlympicsOrchestratorV001Error("orchestrator identity changed")
    if value["lineage"]["v004_scoring_bundle_identity"] != V004_BUNDLE_IDENTITY:
        raise OlympicsOrchestratorV001Error("V004 scoring identity changed")
    if value["lineage"]["v002_executor_bundle_identity"] != EXECUTOR_BUNDLE_IDENTITY:
        raise OlympicsOrchestratorV001Error("executor bundle binding changed")
    if any(flag is not False for flag in value["authorization"].values()):
        raise OlympicsOrchestratorV001Error("trial or production authorization changed")
    readiness = value["readiness"]
    closed = (
        "trial_authorized", "synthetic_trial_executed", "historical_trial_authorized",
        "historical_trial_executed", "validation_opened", "holdout_opened",
        "performance_result_exists",
    )
    if any(readiness[field] is not False for field in closed):
        raise OlympicsOrchestratorV001Error("readiness must remain execution-blocked")
    if tuple(value["artifact_bundle"]["artifacts"]) != ARTIFACT_NAMES:
        raise OlympicsOrchestratorV001Error("artifact bundle changed")
    return value


def _fraction(value: object, field: str) -> Fraction:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise OlympicsOrchestratorV001Error(f"{field} must be a canonical fraction")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise OlympicsOrchestratorV001Error(f"{field} fraction atoms are invalid")
    result = Fraction(numerator, denominator)
    if (result.numerator, result.denominator) != (numerator, denominator):
        raise OlympicsOrchestratorV001Error(f"{field} fraction must be reduced")
    return result


def fraction_record(value: Fraction) -> dict[str, int | str]:
    value = Fraction(value)
    return {
        "kind": "fraction",
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def _record_fraction(value: Mapping[str, object]) -> Fraction:
    if value.get("kind") != "fraction":
        raise OlympicsOrchestratorV001Error("scored value is not an exact fraction")
    return Fraction(value["numerator"], value["denominator"])


def executor_bindings() -> tuple[dict[str, str], ...]:
    bundle = implementation_bundle()
    if bundle["implementation_bundle_identity"] != EXECUTOR_BUNDLE_IDENTITY:
        raise OlympicsOrchestratorV001Error("executor implementation identity changed")
    if bundle["executor_registry_identity"] != EXECUTOR_REGISTRY_IDENTITY:
        raise OlympicsOrchestratorV001Error("executor registry identity changed")
    return tuple(
        {
            "strategy_id": item["strategy_id"],
            "strategy_identity": item["strategy_identity"],
            "executor_identity": item["executor_identity"],
        }
        for item in bundle["executors"]
    )


def validate_input_manifest(value: Mapping[str, object]) -> dict[str, object]:
    if set(value) != INPUT_FIELDS or value.get("schema_version") != INPUT_SCHEMA:
        raise OlympicsOrchestratorV001Error("synthetic input manifest schema is invalid")
    if value.get("synthetic") is not True or value.get("opened_stages") != ["discovery"]:
        raise OlympicsOrchestratorV001Error("only explicit discovery synthetic input is accepted")
    if value.get("scoring_bundle_identity") != V004_BUNDLE_IDENTITY:
        raise OlympicsOrchestratorV001Error("input is bound to the wrong V004 identity")
    _identity(value, "manifest_identity")
    fixture_identity = value.get("fixture_identity")
    if not isinstance(fixture_identity, str) or not HASH_PATTERN.fullmatch(fixture_identity):
        raise OlympicsOrchestratorV001Error("fixture identity is invalid")
    entrants = value.get("entrants")
    if fixture_identity != canonical_hash({
        "opened_stages": value["opened_stages"], "entrants": entrants,
    }):
        raise OlympicsOrchestratorV001Error("fixture identity does not bind entrant inputs")
    bindings = executor_bindings()
    if not isinstance(entrants, list) or len(entrants) != len(bindings):
        raise OlympicsOrchestratorV001Error("all ten frozen entrants are required")
    if [
        {key: entrant.get(key) for key in ("strategy_id", "strategy_identity", "executor_identity")}
        for entrant in entrants
    ] != list(bindings):
        raise OlympicsOrchestratorV001Error("entrant or executor identity order changed")
    proposal_ids: set[str] = set()
    for entrant in entrants:
        _validate_entrant(entrant, proposal_ids)
    return dict(value)


def _validate_entrant(entrant: object, proposal_ids: set[str]) -> None:
    if not isinstance(entrant, Mapping) or set(entrant) != ENTRANT_FIELDS:
        raise OlympicsOrchestratorV001Error("entrant schema is invalid")
    if type(entrant["disqualified"]) is not bool:
        raise OlympicsOrchestratorV001Error("disqualification flag must be boolean")
    reasons = entrant["disqualification_reasons"]
    if not isinstance(reasons, list) or reasons != sorted(set(reasons)):
        raise OlympicsOrchestratorV001Error("disqualification reasons must be unique and sorted")
    if bool(reasons) != entrant["disqualified"]:
        raise OlympicsOrchestratorV001Error("disqualification status does not reconcile")
    if not set(reasons).issubset(DISQUALIFICATION_CONDITIONS):
        raise OlympicsOrchestratorV001Error("unknown strategy-disqualification reason")
    active_dates = entrant["active_dates"]
    if not isinstance(active_dates, list) or active_dates != sorted(set(active_dates)):
        raise OlympicsOrchestratorV001Error("active dates must be unique and sorted")
    variants = entrant["sensitivity_variant_expectancies"]
    if not isinstance(variants, list):
        raise OlympicsOrchestratorV001Error("sensitivity variants must be a list")
    for index, value in enumerate(variants):
        _fraction(value, f"sensitivity_variant_expectancies[{index}]")
    trades = entrant["trades"]
    if not isinstance(trades, list):
        raise OlympicsOrchestratorV001Error("trades must be a list")
    ordered = sorted(
        trades,
        key=lambda trade: (
            trade.get("exit_nanoseconds", -1), trade.get("entry_nanoseconds", -1),
            str(trade.get("symbol", "")).encode("utf-8"),
            str(trade.get("proposal_identity", "")).encode("utf-8"),
        ),
    )
    if trades != ordered:
        raise OlympicsOrchestratorV001Error("trade atoms are not canonically ordered")
    for trade in trades:
        _validate_trade(trade, proposal_ids)


def _validate_trade(trade: object, proposal_ids: set[str]) -> None:
    if not isinstance(trade, Mapping) or set(trade) != TRADE_FIELDS:
        raise OlympicsOrchestratorV001Error("completed-trade atom schema is invalid")
    proposal_id = trade["proposal_identity"]
    if not isinstance(proposal_id, str) or not HASH_PATTERN.fullmatch(proposal_id):
        raise OlympicsOrchestratorV001Error("proposal identity is invalid")
    if proposal_id in proposal_ids:
        raise OlympicsOrchestratorV001Error("duplicate proposal identity")
    proposal_ids.add(proposal_id)
    if not isinstance(trade["symbol"], str) or not trade["symbol"]:
        raise OlympicsOrchestratorV001Error("trade symbol is invalid")
    integer_fields = (
        "entry_nanoseconds", "exit_nanoseconds", "quantity",
        "raw_entry_microdollars", "raw_exit_microdollars",
        "entry_price_microdollars", "target_microdollars",
        "entry_commission_microdollars", "exit_commission_microdollars",
        "risk_budget_microdollars", "net_pnl_microdollars",
    )
    if any(type(trade[field]) is not int for field in integer_fields):
        raise OlympicsOrchestratorV001Error("trade atoms must be integers")
    if trade["entry_nanoseconds"] >= trade["exit_nanoseconds"]:
        raise OlympicsOrchestratorV001Error("trade interval must be positive")
    positive_fields = (
        "quantity", "raw_entry_microdollars", "raw_exit_microdollars",
        "entry_price_microdollars", "target_microdollars", "risk_budget_microdollars",
    )
    if any(trade[field] <= 0 for field in positive_fields):
        raise OlympicsOrchestratorV001Error("filled quantity and prices must be positive")
    if trade["entry_commission_microdollars"] < 0 or trade["exit_commission_microdollars"] < 0:
        raise OlympicsOrchestratorV001Error("commission atoms cannot be negative")
    net_r = _fraction(trade["net_R"], "net_R")
    expected_entry = round(Fraction(trade["raw_entry_microdollars"] * 1001, 1000))
    expected_exit = round(Fraction(trade["raw_exit_microdollars"] * 999, 1000))
    expected_pnl = (
        trade["quantity"] * (expected_exit - expected_entry)
        - trade["entry_commission_microdollars"]
        - trade["exit_commission_microdollars"]
    )
    if trade["entry_price_microdollars"] != expected_entry:
        raise OlympicsOrchestratorV001Error("baseline cost-adjusted entry does not reconcile")
    if trade["net_pnl_microdollars"] != expected_pnl:
        raise OlympicsOrchestratorV001Error("baseline net P&L does not reconcile")
    if net_r != Fraction(trade["net_pnl_microdollars"], trade["risk_budget_microdollars"]):
        raise OlympicsOrchestratorV001Error("net R does not reconcile with net P&L and risk")
    if trade["entry_price_microdollars"] >= trade["target_microdollars"]:
        raise OlympicsOrchestratorV001Error("baseline entry is infeasible against target")
    seconds, _nanoseconds = divmod(trade["exit_nanoseconds"], 1_000_000_000)
    instant = datetime.fromtimestamp(seconds, tz=timezone.utc)
    expected_month = instant.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m")
    if trade["exit_month_new_york"] != expected_month:
        raise OlympicsOrchestratorV001Error("New York exit month does not reconcile")
    if not isinstance(trade["regime_label"], str) or not trade["regime_label"]:
        raise OlympicsOrchestratorV001Error("prospectively frozen regime label is missing")


def load_input_manifest(path: Path) -> dict[str, object]:
    return validate_input_manifest(_strict_json(path))


def load_authorization(path: Path) -> dict[str, object]:
    """Load a strict authorization artifact; identity binding occurs at use."""
    return _strict_json(path)


def _eligible(event_id: str, raw: object, tie: object | None = None) -> EventValue:
    return EventValue(event_id, True, "eligible", raw, tie)


def _ineligible(event_id: str, reason: str) -> EventValue:
    return EventValue(event_id, False, reason, None, None)


def cost_stress_expectancies(
    trades: Sequence[Mapping[str, object]],
) -> tuple[Fraction, ...] | None:
    """Reprice fixed V002 trade atoms under the exact V004 cost multipliers."""
    if not trades:
        return None
    multipliers = (Fraction(1), Fraction(3, 2), Fraction(2))
    totals = [Fraction() for _ in multipliers]
    for trade in trades:
        baseline_pnl = Fraction(trade["net_pnl_microdollars"])
        risk = trade["risk_budget_microdollars"]
        for index, multiplier in enumerate(multipliers):
            stressed_entry = Fraction(trade["raw_entry_microdollars"]) * (
                1 + multiplier / 1000
            )
            if stressed_entry >= trade["target_microdollars"]:
                return None
            increment = multiplier - 1
            incremental_friction = (
                trade["quantity"]
                * (trade["raw_entry_microdollars"] + trade["raw_exit_microdollars"])
                * Fraction(1, 1000)
                * increment
            )
            incremental_fees = (
                trade["entry_commission_microdollars"]
                + trade["exit_commission_microdollars"]
            ) * increment
            totals[index] += (baseline_pnl - incremental_friction - incremental_fees) / risk
    return tuple(total / len(trades) for total in totals)


def compute_raw_events(entrant: Mapping[str, object]) -> tuple[EventValue, ...]:
    """Calculate all 15 V004 raw events from validated synthetic trade atoms."""
    if entrant["disqualified"]:
        return tuple(_ineligible(event, "strategy_disqualified") for event in EVENT_IDS)
    trades = entrant["trades"]
    count = len(trades)
    net_r = [_fraction(trade["net_R"], "net_R") for trade in trades]
    pnl = [trade["net_pnl_microdollars"] for trade in trades]
    expectancy = sum(net_r, Fraction()) / count if count else None
    results: dict[str, EventValue] = {}

    def minimum(event_id: str, needed: int) -> bool:
        if count < needed:
            results[event_id] = _ineligible(event_id, f"minimum_observations_{needed}")
            return False
        return True

    if minimum("net_expectancy", 30):
        results["net_expectancy"] = _eligible("net_expectancy", expectancy)
    if minimum("downside_adjusted_return", 30):
        q = sum((min(value, Fraction()) ** 2 for value in net_r), Fraction()) / count
        if q == 0:
            results["downside_adjusted_return"] = _ineligible(
                "downside_adjusted_return", "no_downside_sample"
            )
        else:
            results["downside_adjusted_return"] = _eligible(
                "downside_adjusted_return", (expectancy, q), expectancy
            )
    if minimum("maximum_drawdown", 30):
        timestamp_sums: dict[int, Fraction] = defaultdict(Fraction)
        for trade, value in zip(trades, net_r, strict=True):
            timestamp_sums[trade["exit_nanoseconds"]] += value
        cumulative = Fraction()
        peak = Fraction()
        drawdown = Fraction()
        for timestamp in sorted(timestamp_sums):
            cumulative += timestamp_sums[timestamp]
            drawdown = max(drawdown, peak - cumulative)
            peak = max(peak, cumulative)
        results["maximum_drawdown"] = _eligible(
            "maximum_drawdown", drawdown, expectancy
        )
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    if minimum("profit_factor", 30):
        results["profit_factor"] = (
            _eligible("profit_factor", Fraction(sum(wins), abs(sum(losses))), expectancy)
            if wins and losses
            else _ineligible("profit_factor", "no_wins_or_no_losses")
        )
    if minimum("payoff_ratio", 30):
        results["payoff_ratio"] = (
            _eligible(
                "payoff_ratio",
                Fraction(sum(wins) * len(losses), abs(sum(losses)) * len(wins)),
            )
            if wins and losses
            else _ineligible("payoff_ratio", "no_wins_or_no_losses")
        )
    if minimum("hit_rate", 30):
        results["hit_rate"] = _eligible("hit_rate", Fraction(len(wins), count))
    if minimum("tail_loss", 40):
        tail_count = (count + 19) // 20
        results["tail_loss"] = _eligible(
            "tail_loss", -sum(sorted(net_r)[:tail_count], Fraction()) / tail_count
        )

    by_month: dict[str, list[Fraction]] = defaultdict(list)
    by_regime: dict[str, list[Fraction]] = defaultdict(list)
    for trade, value in zip(trades, net_r, strict=True):
        by_month[trade["exit_month_new_york"]].append(value)
        by_regime[trade["regime_label"]].append(value)
    if minimum("monthly_stability", 30):
        monthly = [
            sum(values, Fraction()) / len(values)
            for month, values in sorted(by_month.items())
            if len(values) >= 5
        ]
        if len(monthly) < 3:
            results["monthly_stability"] = _ineligible(
                "monthly_stability", "fewer_than_three_qualifying_months"
            )
        else:
            median = exact_median(monthly)
            mad = exact_median([abs(value - median) for value in monthly])
            results["monthly_stability"] = _eligible(
                "monthly_stability", median - mad, len(monthly)
            )
    if minimum("regime_stability", 30):
        regimes = [
            sum(values, Fraction()) / len(values)
            for label, values in sorted(by_regime.items())
            if len(values) >= 10
        ]
        if len(regimes) < 2:
            results["regime_stability"] = _ineligible(
                "regime_stability", "fewer_than_two_qualifying_regimes"
            )
        else:
            results["regime_stability"] = _eligible(
                "regime_stability", min(regimes), exact_median(regimes)
            )
    results["validation_consistency"] = _ineligible(
        "validation_consistency", "validation_stage_unopened"
    )
    results["holdout_consistency"] = _ineligible(
        "holdout_consistency", "holdout_stage_unopened"
    )
    if minimum("capital_efficiency", 30):
        capital = capital_efficiency([
            SyntheticCapitalTrade(
                trade["proposal_identity"], trade["net_pnl_microdollars"],
                trade["quantity"], trade["entry_price_microdollars"],
                trade["entry_nanoseconds"], trade["exit_nanoseconds"],
            )
            for trade in trades
        ])
        results["capital_efficiency"] = (
            _eligible("capital_efficiency", capital, expectancy)
            if capital is not None
            else _ineligible("capital_efficiency", "zero_deployed_time")
        )
    if count:
        results["trade_sufficiency"] = _eligible(
            "trade_sufficiency", 100 * min(Fraction(1), Fraction(count, 100)),
            len(entrant["active_dates"]),
        )
    else:
        results["trade_sufficiency"] = _ineligible("trade_sufficiency", "zero_trades")
    if minimum("execution_robustness", 30):
        scenario_expectancies = cost_stress_expectancies(trades)
        if scenario_expectancies is None:
            results["execution_robustness"] = _ineligible(
                "execution_robustness", "cost_stress_infeasible_fill"
            )
        else:
            results["execution_robustness"] = _eligible(
                "execution_robustness",
                min(scenario_expectancies),
                scenario_expectancies[-1],
            )
    if minimum("sensitivity_robustness", 30):
        variants = [
            _fraction(value, "sensitivity_variant_expectancy")
            for value in entrant["sensitivity_variant_expectancies"]
        ]
        values = [expectancy, *variants]
        results["sensitivity_robustness"] = _eligible(
            "sensitivity_robustness", min(values), max(values) - min(values)
        )
    tie_sources = {
        "net_expectancy": "maximum_drawdown",
        "payoff_ratio": "hit_rate",
        "hit_rate": "payoff_ratio",
        "tail_loss": "maximum_drawdown",
    }
    for event_id, source_id in tie_sources.items():
        event = results[event_id]
        source = results[source_id]
        if event.eligible and source.eligible:
            results[event_id] = EventValue(
                event.event_id, event.eligible, event.reason, event.raw, source.raw
            )
    return tuple(results[event_id] for event_id in EVENT_IDS)


def _compare_raw(left: EventValue, right: EventValue, direction: str) -> int:
    if left.event_id == "downside_adjusted_return":
        comparison = compare_downside_adjusted(
            left.raw[0], left.raw[1], right.raw[0], right.raw[1]
        )
    else:
        comparison = (left.raw > right.raw) - (left.raw < right.raw)
    if direction == "lower_is_better":
        comparison = -comparison
    return comparison


def rank_events(
    entrant_events: Mapping[str, Sequence[EventValue]],
    event_contracts: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Apply V003 unique ordinal percentiles to exact V004 raw values."""
    output: list[dict[str, object]] = []
    for contract in event_contracts:
        event_id = contract["event_id"]
        values = {
            identity: next(value for value in events if value.event_id == event_id)
            for identity, events in entrant_events.items()
        }
        eligible = [(identity, value) for identity, value in values.items() if value.eligible]

        def compare(left: tuple[str, EventValue], right: tuple[str, EventValue]) -> int:
            primary = _compare_raw(left[1], right[1], contract["direction"])
            if primary:
                return primary
            if left[1].tie is not None and right[1].tie is not None:
                tie = (left[1].tie > right[1].tie) - (left[1].tie < right[1].tie)
                if "lower" in " ".join(contract["tie_fields"]):
                    tie = -tie
                if tie:
                    return tie
            return (left[0].encode("utf-8") > right[0].encode("utf-8")) - (
                left[0].encode("utf-8") < right[0].encode("utf-8")
            )

        ordered = sorted(eligible, key=cmp_to_key(compare))
        cohort_size = len(ordered)
        eligible_records: dict[str, dict[str, object]] = {}
        for rank, (identity, value) in enumerate(ordered, start=1):
            percentile = Fraction(1, 2) if cohort_size == 1 else Fraction(rank - 1, cohort_size - 1)
            eligible_records[identity] = {
                "eligible": True,
                "reason": "eligible",
                "ordinal_rank": rank,
                "eligible_cohort_size": cohort_size,
                "event_score": fraction_record(100 * percentile),
            }
        for identity in sorted(values, key=lambda item: item.encode("utf-8")):
            value = values[identity]
            record = eligible_records.get(identity, {
                "eligible": False,
                "reason": value.reason,
                "ordinal_rank": None,
                "eligible_cohort_size": cohort_size,
                "event_score": fraction_record(Fraction()),
            })
            output.append({"event_id": event_id, "strategy_identity": identity, **record})
    return tuple(output)


def _serialize_raw(value: EventValue) -> object:
    if not value.eligible:
        return None
    if value.event_id == "downside_adjusted_return":
        return {
            "kind": "downside_algebraic",
            "mu": fraction_record(value.raw[0]),
            "q": fraction_record(value.raw[1]),
        }
    return fraction_record(value.raw)


def _run_identity(input_identity: str, implementation: str) -> str:
    return canonical_hash({
        "orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "orchestrator_implementation_identity": implementation,
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "input_manifest_identity": input_identity,
        "opened_stages": ["discovery"],
        "trial_kind": "synthetic",
    })


def validate_authorization(
    value: Mapping[str, object] | None, *, execute_requested: bool,
    input_identity: str, implementation: str,
) -> str:
    run_identity = _run_identity(input_identity, implementation)
    if not execute_requested:
        raise OlympicsOrchestratorV001Error("trial execution requires explicit execute flag")
    if value is None:
        raise OlympicsOrchestratorV001Error("trial authorization artifact is required")
    expected = {
        "schema_version", "authorization_identity", "trial_authorized",
        "trial_kind", "orchestrator_identity", "scoring_bundle_identity",
        "orchestrator_implementation_identity", "input_manifest_identity",
        "run_identity", "human_approval_reference",
    }
    if set(value) != expected or value.get("schema_version") != AUTHORIZATION_SCHEMA:
        raise OlympicsOrchestratorV001Error("authorization schema is invalid")
    if _identity(value, "authorization_identity") != value["authorization_identity"]:
        raise OlympicsOrchestratorV001Error("authorization identity is invalid")
    required = {
        "trial_authorized": True,
        "trial_kind": "synthetic",
        "orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "orchestrator_implementation_identity": implementation,
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "input_manifest_identity": input_identity,
        "run_identity": run_identity,
    }
    if any(value.get(field) != expected_value for field, expected_value in required.items()):
        raise OlympicsOrchestratorV001Error("authorization binding is invalid")
    if not isinstance(value["human_approval_reference"], str) or not value["human_approval_reference"]:
        raise OlympicsOrchestratorV001Error("human approval reference is required")
    return run_identity


def validate_only(root: Path, input_manifest: Mapping[str, object] | None = None) -> bytes:
    """Validate contracts and optional synthetic input without executing a trial."""
    contract = load_orchestrator_contract(root)
    validate_repository_lineage(root)
    input_identity = None
    entrant_count = 0
    if input_manifest is not None:
        validated = validate_input_manifest(input_manifest)
        input_identity = validated["manifest_identity"]
        entrant_count = len(validated["entrants"])
    report = {
        "schema_version": "aml.professional-strategy-olympics.orchestrator-preflight.v001",
        "status": "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED",
        "orchestrator_identity": contract["orchestrator_identity"],
        "orchestrator_implementation_identity": implementation_identity(root),
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "input_manifest_identity": input_identity,
        "entrant_count": entrant_count,
        "specification_vector_count": contract["specification_vectors"]["count"],
        "trial_executed": False,
        "performance_result": False,
    }
    return canonical_json(report)


def build_artifact_bundle(
    root: Path,
    input_manifest: Mapping[str, object],
    authorization: Mapping[str, object] | None,
    *,
    execute_requested: bool,
) -> dict[str, bytes]:
    """Build canonical trial artifacts only after the dual authorization gate."""
    load_orchestrator_contract(root)
    validate_repository_lineage(root)
    manifest = validate_input_manifest(input_manifest)
    run_identity = validate_authorization(
        authorization, execute_requested=execute_requested,
        input_identity=manifest["manifest_identity"],
        implementation=implementation_identity(root),
    )
    events = {
        entrant["strategy_identity"]: compute_raw_events(entrant)
        for entrant in manifest["entrants"]
    }
    scoring_contract = validate_repository_lineage(root)["raw_event_registry"]["events"]
    score_records = rank_events(events, scoring_contract)
    score_by_strategy: dict[str, Fraction] = defaultdict(Fraction)
    weights = {item["event_id"]: item["weight"] for item in scoring_contract}
    for record in score_records:
        score = _record_fraction(record["event_score"])
        score_by_strategy[record["strategy_identity"]] += score * weights[record["event_id"]] / 100
    drawdowns = {
        identity: next(value for value in values if value.event_id == "maximum_drawdown")
        for identity, values in events.items()
    }
    disqualified = {
        identity: all(value.reason == "strategy_disqualified" for value in values)
        for identity, values in events.items()
    }

    def compare_overall(left: str, right: str) -> int:
        if disqualified[left] != disqualified[right]:
            return 1 if disqualified[left] else -1
        if score_by_strategy[left] != score_by_strategy[right]:
            return -1 if score_by_strategy[left] > score_by_strategy[right] else 1
        if drawdowns[left].eligible and drawdowns[right].eligible:
            if drawdowns[left].raw != drawdowns[right].raw:
                return -1 if drawdowns[left].raw < drawdowns[right].raw else 1
        return (left.encode("utf-8") > right.encode("utf-8")) - (
            left.encode("utf-8") < right.encode("utf-8")
        )

    ordered = sorted(score_by_strategy, key=cmp_to_key(compare_overall))
    raw_records = [
        {
            "strategy_identity": identity,
            "event_id": value.event_id,
            "eligible": value.eligible,
            "reason": value.reason,
            "raw": _serialize_raw(value),
        }
        for identity in sorted(events, key=lambda item: item.encode("utf-8"))
        for value in events[identity]
    ]
    aggregates = [
        {"strategy_identity": identity, "aggregate_score": fraction_record(score_by_strategy[identity])}
        for identity in sorted(score_by_strategy, key=lambda item: item.encode("utf-8"))
    ]
    rankings = [
        {"rank": rank, "strategy_identity": identity,
         "aggregate_score": fraction_record(score_by_strategy[identity])}
        for rank, identity in enumerate(ordered, start=1)
    ]
    identity_manifest = {
        "run_identity": run_identity,
        "orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "orchestrator_implementation_identity": implementation_identity(root),
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "input_manifest_identity": manifest["manifest_identity"],
        "strategy_identities": [item["strategy_identity"] for item in manifest["entrants"]],
        "executor_identities": [item["executor_identity"] for item in manifest["entrants"]],
    }
    values: dict[str, object] = {
        "run_manifest.json": {
            "run_identity": run_identity, "trial_kind": "synthetic",
            "opened_stages": ["discovery"], "status": "complete",
        },
        "input_manifest.json": manifest,
        "identity_manifest.json": identity_manifest,
        "raw_event_registry.json": raw_records,
        "eligibility_disqualification_ledger.json": [
            {"strategy_identity": item["strategy_identity"],
             "disqualified": item["disqualified"],
             "reasons": item["disqualification_reasons"]}
            for item in manifest["entrants"]
        ],
        "event_score_ledger.json": list(score_records),
        "aggregate_score_ledger.json": aggregates,
        "ranking_ledger.json": rankings,
        "integrity_report.json": {
            "run_identity": run_identity, "status": "passed",
            "failure_count": 0, "live_orders": False,
            "external_data_accessed": False,
        },
    }
    artifacts = {
        name: canonical_json(value)
        for name, value in values.items()
    }
    summary = (
        "# Synthetic Professional Strategy Olympics\n\n"
        f"Run identity: `{run_identity}`\n\n"
        "This canonical synthetic result is not economic or performance evidence.\n"
    ).encode("utf-8")
    artifacts["SUMMARY.md"] = summary
    if tuple(artifacts) != ARTIFACT_NAMES:
        raise OlympicsOrchestratorV001Error("artifact assembly is incomplete")
    return artifacts


def publish_artifacts(
    destination_root: Path, run_identity: str, artifacts: Mapping[str, bytes]
) -> Path:
    """Publish one complete identity-bound bundle atomically and write-once."""
    if not HASH_PATTERN.fullmatch(run_identity):
        raise OlympicsOrchestratorV001Error("run identity is invalid")
    if tuple(artifacts) != ARTIFACT_NAMES:
        raise OlympicsOrchestratorV001Error("artifact publication set is incomplete")
    destination_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    final = destination_root / run_identity
    if final.exists():
        if not final.is_dir() or any(
            not (final / name).is_file() or (final / name).read_bytes() != artifacts[name]
            for name in ARTIFACT_NAMES
        ):
            raise OlympicsOrchestratorV001Error("write-once output collision")
        return final
    temporary = destination_root / f".{run_identity}.incomplete"
    try:
        temporary.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise OlympicsOrchestratorV001Error("incomplete publication already exists") from exc
    for name in ARTIFACT_NAMES:
        path = temporary / name
        with path.open("xb") as stream:
            stream.write(artifacts[name])
            stream.flush()
            os.fsync(stream.fileno())
    os.replace(temporary, final)
    return final


def validate_specification_vectors(root: Path) -> tuple[dict[str, object], ...]:
    """Bind all V004 worked examples as non-executing mathematical vectors."""
    bundle = validate_repository_lineage(root)
    examples = bundle["worked_examples"]["examples"]
    expected_fields = {"id", "inputs", "intermediate", "raw_events", "ranks", "final_result"}
    if len(examples) != 19 or any(set(example) != expected_fields for example in examples):
        raise OlympicsOrchestratorV001Error("V004 specification vectors changed")
    return tuple({
        **example,
        "classification": "mathematical_specification_test_not_trial_result",
        "vector_identity": canonical_hash(example),
    } for example in examples)
