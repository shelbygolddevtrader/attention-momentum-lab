"""Proposal-only lifecycle adapter for frozen Olympics V002 rules."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_executor_models_v001 import (
    EVIDENCE_CLASS,
    EXECUTOR_PROTOCOL_VERSION,
    EvaluationInput,
    EvaluationResult,
    StrategyProposal,
    proposal_identity,
)
from aml.winner_archetype_contracts import canonical_hash


V002_PROTOCOL_IDENTITY = "fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583"
FRICTION_BASIS_POINTS_PER_SIDE = 10
COMMISSION_PER_SHARE_PER_ORDER = 0.005
MINIMUM_COMMISSION_PER_ORDER = 1.0
RISK_BUDGET_USD = 250.0
INITIAL_CAPITAL_USD = 100_000.0
MAXIMUM_GROSS_EXPOSURE_FRACTION = 0.5
MAXIMUM_CONCURRENT_POSITIONS = 3
DAILY_NEW_ENTRY_LOSS_STOP_FRACTION = 0.01


def _implementation_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def floor_cent(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def ceil_cent(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def _clock_allowed(timestamp, window: Mapping[str, object]) -> bool:
    clock = timestamp.strftime("%H:%M")
    return str(window["first_entry"]) <= clock <= str(window["last_entry"])


def build_proposal(
    value: EvaluationInput,
    strategy: Mapping[str, object],
    executor_identity: str,
    *,
    unrounded_stop: float,
    indicator_snapshots: Mapping[str, float | str],
    frozen_indicator_target: float | None = None,
) -> EvaluationResult:
    """Apply the next-open, rounding, fixed-target, and invalidation boundary."""

    strategy_id = str(strategy["strategy_id"])
    decision = value.decision_cutoff.isoformat()
    if value.next_bar is None:
        return EvaluationResult(strategy_id, decision, "unavailable", ("missing_next_bar",))
    if value.next_bar.halted:
        return EvaluationResult(strategy_id, decision, "no_trade", ("halt_before_entry",))
    if not _clock_allowed(value.next_bar.timestamp, strategy["entry_window"]):
        return EvaluationResult(strategy_id, decision, "no_trade", ("entry_outside_window",))
    normal_liquidation = value.scheduled_open.replace(hour=15, minute=55)
    early_close_liquidation = (
        value.scheduled_close.replace(second=0, microsecond=0) - timedelta(minutes=5)
    )
    liquidation_bar = min(normal_liquidation, early_close_liquidation)
    if value.next_bar.timestamp > liquidation_bar:
        return EvaluationResult(strategy_id, decision, "no_trade", ("entry_outside_window",))
    stop = floor_cent(unrounded_stop)
    raw_entry = value.next_bar.open
    adjusted_entry = raw_entry * 1.001
    if raw_entry <= stop or adjusted_entry <= stop:
        return EvaluationResult(strategy_id, decision, "no_trade", ("nonpositive_risk",))
    fixed_target = adjusted_entry + 2 * (adjusted_entry - stop)
    selected_target = (
        min(frozen_indicator_target, fixed_target)
        if frozen_indicator_target is not None and strategy["target"]["type"]
        == "frozen_indicator_or_2R_whichever_lower"
        else frozen_indicator_target if frozen_indicator_target is not None else fixed_target
    )
    target = ceil_cent(selected_target)
    if target <= adjusted_entry:
        return EvaluationResult(strategy_id, decision, "no_trade", ("target_not_above_entry",))
    snapshots = tuple(sorted(indicator_snapshots.items()))
    base: dict[str, object] = {
        "protocol_identity": V002_PROTOCOL_IDENTITY,
        "strategy_id": strategy_id,
        "strategy_identity": str(strategy["strategy_identity"]),
        "executor_version": EXECUTOR_PROTOCOL_VERSION,
        "executor_identity": executor_identity,
        "symbol": value.symbol_bars[-1].symbol,
        "session": value.symbol_bars[-1].session.isoformat(),
        "signal_timestamp": value.decision_cutoff.isoformat(),
        "intended_entry_timestamp": value.next_bar.timestamp.isoformat(),
        "direction": "long",
        "entry_rule": "shared_next_exact_bar_open",
        "raw_entry_open": raw_entry,
        "cost_adjusted_entry": adjusted_entry,
        "stop": stop,
        "target": target,
        "timeout_complete_bars": int(strategy["timeout"]["complete_bars"]),
        "session_liquidation_rule": "close_of_Nth_bar_or_15:55_bar_close_whichever_first_calendar_early_close_fifth_bar_before_close",
        "stop_target_precedence": "gap_stop_then_intrabar_stop_before_gap_or_intrabar_target",
        "gap_through_rule": "long_stop_min_open_or_stop_long_target_max_open_or_target",
        "invalidation_rules": tuple(strategy["invalidation"]["rules"]),
        "indicator_snapshots": snapshots,
        "evidence_class": EVIDENCE_CLASS,
        "friction_basis_points_per_side": FRICTION_BASIS_POINTS_PER_SIDE,
        "commission_per_share_per_order": COMMISSION_PER_SHARE_PER_ORDER,
        "minimum_commission_per_order": MINIMUM_COMMISSION_PER_ORDER,
        "risk_budget_usd": RISK_BUDGET_USD,
        "initial_capital_usd": INITIAL_CAPITAL_USD,
        "maximum_gross_exposure_fraction": MAXIMUM_GROSS_EXPOSURE_FRACTION,
        "maximum_concurrent_positions": MAXIMUM_CONCURRENT_POSITIONS,
        "daily_new_entry_loss_stop_fraction": DAILY_NEW_ENTRY_LOSS_STOP_FRACTION,
    }
    identity = proposal_identity(base)
    proposal = StrategyProposal(**base, proposal_identity=identity)
    assert proposal_identity({
        key: item for key, item in asdict(proposal).items() if key != "proposal_identity"
    }) == identity
    return EvaluationResult(strategy_id, decision, "proposal", (), proposal)


SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY = canonical_hash(
    {
        "schema": "aml.professional-strategy-lifecycle.implementation.v001",
        "v002_lifecycle_identity": (
            "b61fa2557718cdf1dbebc0e91990bb27be3d880111bea424d967dd96253dfe12"
        ),
        "v002_cost_model_identity": (
            "ba239ed1b835d91be06a674433559c2b679c07fd37b9820f0c4fe7cf7ada4570"
        ),
        "source_sha256": _implementation_identity(),
    }
)
