"""Design-only capital release and self-funding governance contracts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Mapping

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


GOVERNANCE_SCHEMA = "aml.lean-discovery.capital-governance.v001"
GOVERNANCE_VERSION = "lean-capital-governance-v001"
STAGE_ORDER = (
    "discovery_research",
    "untouched_validation",
    "one_time_holdout",
    "prospective_paper_forward",
    "tiny_live_capital_test",
    "limited_self_funding",
    "controlled_scaling",
)
LIVE_STAGES = set(STAGE_ORDER[4:])
REVENUE_INELIGIBLE_SOURCES = {
    "backtest_gain",
    "deposit",
    "paper_gain",
    "recovered_loss",
    "unrealized_gain",
}


class CapitalGovernanceError(ValueError):
    """A capital release, risk, claim, or funding boundary was violated."""


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise CapitalGovernanceError("Capital governance input is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CapitalGovernanceError("Capital governance JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(CapitalGovernanceError(item)),
        )
        canonical_json(result)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise CapitalGovernanceError("Capital governance input is not strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise CapitalGovernanceError("Capital governance root must be an object")
    return result


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise CapitalGovernanceError(f"{field} must be a SHA-256 digest")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise CapitalGovernanceError(f"{field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CapitalGovernanceError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CapitalGovernanceError(f"{field} must include a timezone")
    return parsed


def validate_governance(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version", "governance_version", "prospective_as_of",
        "governance_identity", "lean_protocol_identity", "status",
        "universal_prohibitions", "stage_order", "stages", "scaling_policy",
        "funding_reserve", "claim_ladder", "authorization",
    }
    if set(value) != expected:
        raise CapitalGovernanceError("Capital governance contains missing or unexpected fields")
    if value["schema_version"] != GOVERNANCE_SCHEMA or value["governance_version"] != GOVERNANCE_VERSION:
        raise CapitalGovernanceError("Unsupported capital governance version")
    _timestamp(value["prospective_as_of"], "prospective_as_of")
    identity = _hash(value["governance_identity"], "governance_identity")
    payload = {key: item for key, item in value.items() if key != "governance_identity"}
    if canonical_hash(payload) != identity:
        raise CapitalGovernanceError("Capital governance identity is stale or tampered")
    _hash(value["lean_protocol_identity"], "lean_protocol_identity")
    if value["status"] != "design_only_all_execution_unauthorized":
        raise CapitalGovernanceError("Capital governance must remain design-only")
    if tuple(value["stage_order"]) != STAGE_ORDER:
        raise CapitalGovernanceError("Capital stages are missing, reordered, or renamed")
    if value["authorization"] != {
        "paper_authorized": False,
        "live_authorized": False,
        "reserve_transfer_authorized": False,
        "provider_purchase_authorized": False,
        "activation_requires_separate_versioned_human_approval": True,
    }:
        raise CapitalGovernanceError("Tracked governance cannot authorize execution or spending")

    stages = value["stages"]
    if not isinstance(stages, list) or [stage.get("id") for stage in stages] != list(STAGE_ORDER):
        raise CapitalGovernanceError("Capital stage definitions must follow the frozen order")
    stage_fields = {
        "id", "entry_requirements", "minimum_observation_period",
        "minimum_signals", "minimum_completed_trades", "allowable_strategy_changes",
        "net_expectancy_threshold", "maximum_drawdown", "execution_quality_threshold",
        "data_quality_threshold", "risk_per_trade_limit", "daily_loss_limit_pct",
        "weekly_loss_limit_pct", "shutdown_conditions", "human_approval_evidence",
        "regression_conditions",
    }
    for index, stage in enumerate(stages):
        if not isinstance(stage, Mapping) or set(stage) != stage_fields:
            raise CapitalGovernanceError("Capital stage contains missing or unexpected fields")
        if type(stage["minimum_signals"]) is not int or stage["minimum_signals"] < 0:
            raise CapitalGovernanceError("minimum_signals must be non-negative")
        if type(stage["minimum_completed_trades"]) is not int or stage["minimum_completed_trades"] < 0:
            raise CapitalGovernanceError("minimum_completed_trades must be non-negative")
        if index < 4 and stage["risk_per_trade_limit"]["maximum_equity_pct"] != 0.0:
            raise CapitalGovernanceError("Pre-live stages cannot risk capital")
    tiny = stages[4]
    if tiny["risk_per_trade_limit"] != {
        "rule": "lower_of_account_equity_pct_or_frozen_validated_strategy_limit",
        "maximum_equity_pct": 0.25,
        "validated_strategy_limit_required": True,
    }:
        raise CapitalGovernanceError("Tiny-live risk must be capped at the lower frozen limit")
    if tiny["daily_loss_limit_pct"] != 0.5 or tiny["weekly_loss_limit_pct"] != 1.5:
        raise CapitalGovernanceError("Tiny-live daily and weekly loss caps changed")
    policy = value["scaling_policy"]
    if policy["maximum_capital_or_risk_increase_pct_per_gate"] != 25.0:
        raise CapitalGovernanceError("Scaling step cannot exceed 25 percent")
    reserve = value["funding_reserve"]
    if reserve["allocation_defaults_pct"] != {
        "retained_trading_capital": 50,
        "data_platform_reserve": 30,
        "tax_and_operational_uncertainty": 20,
    }:
        raise CapitalGovernanceError("Profit allocation defaults changed")
    if reserve["eligible_source"] != "settled_realized_net_trading_profit_above_prior_high_water_mark":
        raise CapitalGovernanceError("Reserve source must be settled realized profit")
    return dict(value)


def load_governance(path: Path) -> dict[str, object]:
    return validate_governance(_strict_json(path))


def canonical_governance_bytes(path: Path) -> bytes:
    return canonical_json(load_governance(path))


def stage_by_id(governance: Mapping[str, object], stage_id: str) -> Mapping[str, object]:
    validated = validate_governance(governance)
    for stage in validated["stages"]:
        if stage["id"] == stage_id:
            return stage
    raise CapitalGovernanceError("Unknown capital stage")


def assess_stage_entry(
    governance: Mapping[str, object], stage_id: str, evidence: Mapping[str, object]
) -> dict[str, object]:
    """Assess evidence for human review; never activate execution in this version."""
    validated = validate_governance(governance)
    stage = stage_by_id(validated, stage_id)
    index = STAGE_ORDER.index(stage_id)
    required_prior = set(STAGE_ORDER[:index])
    completed_prior = set(evidence.get("completed_stages", ()))
    failures: list[str] = []
    if not required_prior <= completed_prior:
        failures.append("prior_stages_incomplete")
    period = stage["minimum_observation_period"]
    if int(evidence.get("observation_calendar_days", -1)) < period["calendar_days"]:
        failures.append("minimum_observation_period_not_met")
    if int(evidence.get("observation_trading_sessions", -1)) < period["trading_sessions"]:
        failures.append("minimum_observation_sessions_not_met")
    if int(evidence.get("signals", -1)) < stage["minimum_signals"]:
        failures.append("minimum_signals_not_met")
    if int(evidence.get("completed_trades", -1)) < stage["minimum_completed_trades"]:
        failures.append("minimum_completed_trades_not_met")
    expectancy = stage["net_expectancy_threshold"]
    if expectancy["minimum_r_per_trade"] is not None:
        if float(evidence.get("net_expectancy_r", float("-inf"))) < expectancy["minimum_r_per_trade"]:
            failures.append("net_expectancy_below_threshold")
        if float(evidence.get("expectancy_interval_lower_r", float("-inf"))) < expectancy["minimum_interval_lower_r"]:
            failures.append("expectancy_interval_below_threshold")
    drawdown = stage["maximum_drawdown"]
    if drawdown["maximum_equity_pct"] is not None and float(evidence.get("maximum_drawdown_pct", float("inf"))) > drawdown["maximum_equity_pct"]:
        failures.append("maximum_drawdown_breached")
    if drawdown["maximum_r"] is not None and float(evidence.get("maximum_drawdown_r", float("inf"))) > drawdown["maximum_r"]:
        failures.append("maximum_drawdown_r_breached")
    execution = stage["execution_quality_threshold"]
    if execution["minimum_signal_capture_rate"] is not None:
        if float(evidence.get("signal_capture_rate", -1.0)) < execution["minimum_signal_capture_rate"]:
            failures.append("execution_capture_below_threshold")
        if float(evidence.get("median_implementation_shortfall_bps", float("inf"))) > execution["maximum_median_shortfall_bps"]:
            failures.append("median_execution_shortfall_breached")
        if float(evidence.get("p95_implementation_shortfall_bps", float("inf"))) > execution["maximum_p95_shortfall_bps"]:
            failures.append("p95_execution_shortfall_breached")
    data = stage["data_quality_threshold"]
    if float(evidence.get("data_completeness_rate", -1.0)) < data["minimum_completeness_rate"]:
        failures.append("data_quality_below_threshold")
    if int(evidence.get("integrity_failures", 1)) != 0:
        failures.append("integrity_failure")
    if evidence.get("strategy_identity_matches") is not True:
        failures.append("strategy_identity_drift")
    if stage_id in LIVE_STAGES:
        if evidence.get("disposable_risk_declaration") is not True:
            failures.append("disposable_risk_not_declared")
        if evidence.get("prohibited_capital_source_present") is not False:
            failures.append("prohibited_capital_source")
        if evidence.get("prohibited_sizing_or_leverage_detected") is not False:
            failures.append("prohibited_sizing_or_leverage")
        risk = stage["risk_per_trade_limit"]
        validated_limit = float(evidence.get("validated_strategy_risk_limit_pct", -1.0))
        maximum_risk = min(risk["maximum_equity_pct"], validated_limit)
        if validated_limit <= 0.0 or float(evidence.get("maximum_risk_per_trade_pct", float("inf"))) > maximum_risk:
            failures.append("risk_per_trade_limit_breached")
        if float(evidence.get("maximum_daily_loss_pct", float("inf"))) >= stage["daily_loss_limit_pct"]:
            failures.append("daily_loss_limit_breached")
        if float(evidence.get("maximum_weekly_loss_pct", float("inf"))) >= stage["weekly_loss_limit_pct"]:
            failures.append("weekly_loss_limit_breached")
    approval_hashes = evidence.get("human_approval_evidence_hashes", ())
    if not isinstance(approval_hashes, Mapping) or set(approval_hashes) != set(stage["human_approval_evidence"]):
        failures.append("human_approval_evidence_incomplete")
    elif any(
        not isinstance(item, str) or not HASH_PATTERN.fullmatch(item)
        for item in approval_hashes.values()
    ):
        failures.append("human_approval_evidence_invalid")
    failures = sorted(set(failures))
    payload = {
        "stage_id": stage_id,
        "eligible_for_human_review": not failures,
        "failures": failures,
        "execution_authorized": False,
        "design_only": True,
    }
    return {**payload, "assessment_identity": canonical_hash(payload)}


def runtime_authorization_survives(
    *, authorization_active: bool, daily_loss_pct: float, weekly_loss_pct: float,
    stage_daily_limit_pct: float, stage_weekly_limit_pct: float,
    integrity_failures: int, identity_matches: bool, strategy_drift: bool,
    execution_threshold_breached: bool,
) -> bool:
    """A pure kill-switch model that can revoke, but never create, authorization."""
    if not authorization_active:
        return False
    return not (
        daily_loss_pct >= stage_daily_limit_pct
        or weekly_loss_pct >= stage_weekly_limit_pct
        or integrity_failures != 0
        or not identity_matches
        or strategy_drift
        or execution_threshold_breached
    )


def regression_stage(change_type: str) -> str:
    mapping = {
        "strategy_logic": "discovery_research",
        "signal_threshold": "discovery_research",
        "stop_target_holding_period": "discovery_research",
        "sizing_or_risk": "discovery_research",
        "market_data_semantics": "discovery_research",
        "execution_adapter_material": "prospective_paper_forward",
        "broker_routing_material": "prospective_paper_forward",
        "documentation_only": "controlled_scaling",
    }
    try:
        return mapping[change_type]
    except KeyError as exc:
        raise CapitalGovernanceError("Unknown strategy change type fails closed") from exc


def validate_scaling_step(
    governance: Mapping[str, object], *, previous_risk_units: int, proposed_risk_units: int,
    new_completed_trades: int, observation_days: int, human_approved: bool,
) -> dict[str, object]:
    validated = validate_governance(governance)
    policy = validated["scaling_policy"]
    if previous_risk_units <= 0 or proposed_risk_units <= 0:
        raise CapitalGovernanceError("Scaling units must be positive integers")
    maximum = previous_risk_units * 125 // 100
    if proposed_risk_units > maximum:
        raise CapitalGovernanceError("Scaling step exceeds 25 percent")
    if new_completed_trades < policy["minimum_new_completed_trades_per_gate"]:
        raise CapitalGovernanceError("Scaling review trade count is incomplete")
    if observation_days < policy["minimum_calendar_days_per_gate"]:
        raise CapitalGovernanceError("Scaling review observation period is incomplete")
    if human_approved is not True:
        raise CapitalGovernanceError("Scaling requires explicit human approval")
    payload = {
        "previous_risk_units": previous_risk_units,
        "approved_risk_units": proposed_risk_units,
        "increase_basis_points": (proposed_risk_units - previous_risk_units) * 10_000 // previous_risk_units,
        "execution_authorized": False,
    }
    return {**payload, "scaling_identity": canonical_hash(payload)}


def allocate_realized_profit(
    governance: Mapping[str, object], request: Mapping[str, object]
) -> dict[str, object]:
    validate_governance(governance)
    required = {
        "stage_id", "source_type", "eligible_profit_cents", "ending_equity_cents",
        "prior_high_water_equity_cents", "external_deposit_cents",
        "unrealized_pnl_cents", "recovered_loss_cents", "completed_trade_hashes",
        "reconciliation_manifest_hash", "account_statement_hash",
    }
    if set(request) != required:
        raise CapitalGovernanceError("Reserve transfer request contains missing or unexpected fields")
    if request["stage_id"] not in {"limited_self_funding", "controlled_scaling"}:
        raise CapitalGovernanceError("Reserve funding is unavailable before limited self-funding")
    if request["source_type"] != "settled_realized_net_trading_profit":
        raise CapitalGovernanceError("Only settled realized net trading profit is eligible")
    amount = request["eligible_profit_cents"]
    if type(amount) is not int or amount <= 0:
        raise CapitalGovernanceError("Eligible realized profit must be positive integer cents")
    for field in ("external_deposit_cents", "unrealized_pnl_cents", "recovered_loss_cents"):
        if request[field] != 0:
            raise CapitalGovernanceError(f"{field} cannot fund the reserve")
    high_water_gain = request["ending_equity_cents"] - request["prior_high_water_equity_cents"]
    if amount > high_water_gain:
        raise CapitalGovernanceError("Recovered losses or deposits cannot masquerade as new profit")
    trades = request["completed_trade_hashes"]
    if not isinstance(trades, list) or not trades or trades != sorted(set(trades)):
        raise CapitalGovernanceError("Completed trade hashes must be non-empty, sorted, and unique")
    for digest in trades:
        _hash(digest, "completed_trade_hash")
    _hash(request["reconciliation_manifest_hash"], "reconciliation_manifest_hash")
    _hash(request["account_statement_hash"], "account_statement_hash")
    retained = amount * 50 // 100
    reserve = amount * 30 // 100
    uncertainty = amount - retained - reserve
    payload = {
        "source_type": request["source_type"],
        "eligible_profit_cents": amount,
        "retained_trading_capital_cents": retained,
        "data_platform_reserve_cents": reserve,
        "tax_and_operational_uncertainty_cents": uncertainty,
        "completed_trade_hashes": trades,
        "reconciliation_manifest_hash": request["reconciliation_manifest_hash"],
        "account_statement_hash": request["account_statement_hash"],
        "transfer_authorized": False,
        "human_review_required": True,
    }
    return {**payload, "allocation_identity": canonical_hash(payload)}


def validate_reserve_purchase_plan(
    *, available_reserve_cents: int, proposed_cost_cents: int,
    forecast_profit_cents: int, human_approved: bool,
) -> None:
    if available_reserve_cents < 0 or proposed_cost_cents <= 0:
        raise CapitalGovernanceError("Reserve and purchase amounts are invalid")
    if forecast_profit_cents != 0:
        raise CapitalGovernanceError("Provider purchases cannot rely on forecast profits")
    if proposed_cost_cents > available_reserve_cents:
        raise CapitalGovernanceError("Purchase exceeds settled reserve cash")
    if human_approved is not True:
        raise CapitalGovernanceError("Reserve purchase requires human approval")


def validate_capital_claim(
    *, achieved_stage: str, source_type: str, text: str,
    separate_business_evidence: bool = False,
) -> None:
    if achieved_stage not in STAGE_ORDER:
        raise CapitalGovernanceError("Unknown achieved stage")
    normalized = " ".join(text.casefold().split())
    index = STAGE_ORDER.index(achieved_stage)
    if "revenue" in normalized:
        if source_type in REVENUE_INELIGIBLE_SOURCES:
            raise CapitalGovernanceError("Backtest, paper, deposit, recovery, or unrealized gains are not revenue")
        if index < 6 or not separate_business_evidence:
            raise CapitalGovernanceError("Scalable business revenue requires stage seven and separate evidence")
    if "self-funding" in normalized and index < 5:
        raise CapitalGovernanceError("Self-funding language requires limited self-funding evidence")
    if "realized trading profit" in normalized:
        if index < 4 or source_type != "settled_realized_net_trading_profit":
            raise CapitalGovernanceError("Realized-profit language requires reconciled live records")
    if "live execution evidence" in normalized and index < 4:
        raise CapitalGovernanceError("Live-execution language requires the tiny-live stage")
    if "paper-forward performance" in normalized and index < 3:
        raise CapitalGovernanceError("Paper-forward language requires completed paper evidence")
