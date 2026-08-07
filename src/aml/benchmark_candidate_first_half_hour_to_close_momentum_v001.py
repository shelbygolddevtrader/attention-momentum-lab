"""Prospectively frozen first-half-hour-to-close momentum child V001.

The immutable parent is hypothesis-only. This candidate-specific long-SPY child
uses one decision at 10:00 ET and the unchanged proposal/lifecycle simulator.
Every discretionary rule is a prospective human-authorized design choice and
was fixed before candidate outcome access.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
import hashlib
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    EvaluationResult,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_indicators_v001 import validate_evaluation_input
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    build_proposal,
)
from aml.winner_archetype_contracts import canonical_hash


PARENT_LIBRARY_ENTRY_ID = "first-half-hour-to-close-momentum-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "8e7191ca4dd6f479b44522b28b62514761af398d5dbeb250c8f5fb0a22a55713"
)
PARENT_REGISTRATION_IDENTITY = (
    "c9a867cc579069c1fa34e82f258f7063bd5d8b86e05d2d9414980b5113f60394"
)
PARENT_OBSERVATION_IDENTITY = (
    "51085c203cda2121b8c37864f89beb487566f90011de8151d8896703be1ac277"
)
CHILD_HYPOTHESIS_ID = "first-half-hour-positive-momentum-to-close-long-spy-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
SIMULATION_STRATEGY_ID = "five_minute_orb_long_v002"
NON_OPERATIVE_TARGET_SENTINEL = 1_000_000_000_000.0
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 5)


class FirstHalfHourToCloseError(ValueError):
    """The candidate contract or deterministic input is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.first-half-hour-to-close-momentum-specification.v001",
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_version": CHILD_VERSION,
    "parent_library_entry_id": PARENT_LIBRARY_ENTRY_ID,
    "parent_framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    "revision": CHILD_REVISION,
    "design_authority": {
        "classification": "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES",
        "parent_is_exact_specification": False,
        "parent_late_session_entry_preserved": False,
        "authorized_descendant_intent": (
            "test persistence from the completed first half-hour through the "
            "remainder of the regular session"
        ),
        "outcome_access_before_freeze": False,
        "optimization_count": 0,
        "parameter_search_count": 0,
    },
    "direction": "long_only",
    "universe": "SPY only as the market proxy named by the parent mechanism",
    "session": {
        "calendar": "XNYS",
        "segment": "regular_only",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "signal_window": "exactly 09:30 through 09:59 America/New_York",
        "decision_timestamp": "10:00 America/New_York",
        "entry_timestamp": "10:00 America/New_York exact next bar open",
        "normal_liquidation": "15:55 completed-bar close reported at 15:56",
        "early_close_liquidation": "fifth completed bar before scheduled close",
    },
    "signal": {
        "return_formula": "close_09:59 / open_09:30 - 1",
        "threshold_inclusive": 0.005,
        "required_bar_count": 30,
        "direction_condition": "first-half-hour return at least positive 0.50 percent",
        "volume_confirmation": "none",
        "signal_count_per_symbol_session": 1,
    },
    "entry": {
        "raw_price": "exact 10:00 complete bar open",
        "adverse_friction_basis_points_per_side": 10,
        "pre_entry_invalidation": [
            "10:00 exact bar missing",
            "10:00 bar halted",
            "raw or cost-adjusted entry at or below rounded stop",
        ],
    },
    "stop": {
        "unrounded": "minimum low of exact 09:30 through 09:59 signal window",
        "rounding": "floor to one cent",
    },
    "target": {
        "economic_profit_target": "none",
        "interface_value": NON_OPERATIVE_TARGET_SENTINEL,
        "interface_reason": (
            "unchanged StrategyProposal requires a finite target; this frozen "
            "sentinel is not a profit objective and is outside the permitted price domain"
        ),
    },
    "lifecycle": {
        "maximum_complete_bars": 390,
        "intended_exit": "unchanged session liquidation unless structure stop occurs first",
        "same_bar_precedence": (
            "gap stop, intrabar stop, unreachable sentinel target checks, timeout, "
            "session liquidation"
        ),
        "maximum_proposals_per_symbol_session": 1,
        "reentry": "prohibited",
        "shared_cost_and_risk_model": "professional_strategy_lifecycle_v001 unchanged",
    },
    "rule_precedence": [
        "integrity_failure",
        "wrong_symbol_no_signal",
        "outside_exact_decision_no_signal",
        "duplicate_no_signal",
        "signal_window_unavailable",
        "threshold_no_signal",
        "pre_entry_no_trade_or_unavailable",
        "proposal",
    ],
    "tie_breaking": [
        "one fixed decision per symbol-session",
        "immutable child strategy identity",
    ],
    "missing_data": {
        "forward_fill": "prohibited",
        "interpolation": "prohibited",
        "missing_09:30_open_or_any_signal_bar": "unavailable",
        "missing_10:00_entry_bar": "unavailable",
        "unclassified_minute_gap": "integrity_failure",
        "malformed_or_nonfinite_ohlcv": "integrity_failure",
        "incomplete_provenance": "integrity_failure",
        "missing_session_liquidation_bar": "integrity_failure",
    },
    "numeric_semantics": {
        "representation": "IEEE-754 binary64",
        "operation_rounding": "round to nearest ties to even",
        "comparison_tolerance": "none",
        "cent_rounding": "shared lifecycle floor-cent stop semantics",
    },
    "decision_states": ["integrity_failure", "no_signal", "no_trade", "proposal", "unavailable"],
    "expected_holding_period": "approximately 356 minutes on a normal session unless stopped",
    "expected_maximum_trades_per_symbol_session": 1,
    "expected_failure_modes": [
        "early directional movement reverses during the remaining session",
        "the first-half-hour low produces an impractically wide stop",
        "overnight or opening information is fully incorporated by 10:00",
        "modeled costs and adverse selection exceed any gross effect",
    ],
    "claim_boundary": (
        "contaminated exploratory diagnostics and candidate-only economic POC; not "
        "empirical evidence, validation, holdout, production, or capital eligibility"
    ),
}


SPECIFICATION_IDENTITY = canonical_hash(
    {"domain": "aml.first-half-hour-to-close-momentum-specification.v001", "specification": FROZEN_SPECIFICATION}
)
CHILD_STRATEGY_IDENTITY = canonical_hash(
    {"domain": "aml.first-half-hour-to-close-momentum-strategy.v001", "specification_identity": SPECIFICATION_IDENTITY}
)


def _source_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


EXECUTOR_IDENTITY = canonical_hash(
    {
        "domain": "aml.first-half-hour-to-close-momentum-executor.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
        "source_sha256": _source_identity(),
    }
)

CHILD_STRATEGY: Mapping[str, object] = {
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_identity": CHILD_STRATEGY_IDENTITY,
    "entry_window": {"first_entry": "10:00", "last_entry": "10:00"},
    "target": {"type": "non_operative_close_exit_sentinel"},
    "timeout": {"complete_bars": 390},
    "invalidation": {
        "rules": [
            "first_half_hour_threshold_absent",
            "required_signal_window_unavailable",
            "next_exact_bar_unavailable",
        ]
    },
}


def _decision(value: EvaluationInput, status: str, reason: str) -> EvaluationResult:
    return EvaluationResult(CHILD_HYPOTHESIS_ID, value.decision_cutoff.isoformat(), status, (reason,))


def evaluate_first_half_hour_to_close_momentum(value: EvaluationInput) -> EvaluationResult:
    """Evaluate the single causal 10:00 decision under the frozen child."""

    validate_evaluation_input(value)
    bars = value.symbol_bars
    current = bars[-1]
    if current.symbol != "SPY":
        return _decision(value, "no_signal", "symbol_outside_frozen_universe")
    if value.decision_cutoff.strftime("%H:%M") != "10:00":
        return _decision(value, "no_signal", "outside_exact_decision_timestamp")
    if any(strategy_id == CHILD_HYPOTHESIS_ID for strategy_id, _ in value.prior_strategy_entries):
        return _decision(value, "no_signal", "maximum_proposals_reached")
    if len(bars) != 30:
        return _decision(value, "unavailable", "first_half_hour_window_incomplete")
    expected = value.scheduled_open
    for index, bar in enumerate(bars):
        if bar.timestamp != expected + timedelta(minutes=index):
            return _decision(value, "unavailable", "first_half_hour_window_incomplete")
    first_half_hour_return = current.close / bars[0].open - 1.0
    if first_half_hour_return < 0.005:
        return _decision(value, "no_signal", "signal_strength_below_threshold")
    return build_proposal(
        value,
        CHILD_STRATEGY,
        EXECUTOR_IDENTITY,
        unrounded_stop=min(bar.low for bar in bars),
        frozen_indicator_target=NON_OPERATIVE_TARGET_SENTINEL,
        indicator_snapshots={
            "first_half_hour_open": bars[0].open,
            "first_half_hour_close": current.close,
            "first_half_hour_low": min(bar.low for bar in bars),
            "first_half_hour_return": first_half_hour_return,
            "target_interface_semantics": "non_operative_close_exit_sentinel",
        },
    )


EXECUTOR_REGISTRY = {CHILD_HYPOTHESIS_ID: evaluate_first_half_hour_to_close_momentum}


def _stamp(clock: str, session: date = SYNTHETIC_SESSION) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(session, time(hour, minute), NY)


def _bar(clock: str, *, open_: float = 100.0, high: float = 100.4, low: float = 99.8, close: float = 100.0) -> MinuteBar:
    return MinuteBar(
        security_id="synthetic-SPY", symbol="SPY", session=SYNTHETIC_SESSION,
        timestamp=_stamp(clock), open=open_, high=high, low=low, close=close,
        volume=100_000.0,
    )


def conformance_bars() -> tuple[MinuteBar, ...]:
    values = []
    for index in range(30):
        clock = (datetime.combine(SYNTHETIC_SESSION, time(9, 30), NY) + timedelta(minutes=index)).strftime("%H:%M")
        close = 100.0 + 0.02 * index
        values.append(_bar(clock, open_=100.0 if index == 0 else close - 0.01, high=close + 0.1, low=99.7 if index == 4 else close - 0.1, close=close))
    values.append(_bar("10:00", open_=100.60, high=100.8, low=100.5, close=100.7))
    for index in range(1, 357):
        timestamp = datetime.combine(SYNTHETIC_SESSION, time(10, 0), NY) + timedelta(minutes=index)
        if timestamp.strftime("%H:%M") > "15:55":
            break
        values.append(_bar(timestamp.strftime("%H:%M"), open_=100.7, high=100.9, low=100.5, close=100.7))
    return tuple(values)


def evaluation_input(
    bars: tuple[MinuteBar, ...], *, next_bar: MinuteBar | None,
    prior_entries: tuple[tuple[str, datetime], ...] = (),
) -> EvaluationInput:
    if not bars:
        raise FirstHalfHourToCloseError("bars are required")
    entry = None if next_bar is None else NextBarOpen(
        next_bar.security_id, next_bar.symbol, next_bar.session, next_bar.timestamp, next_bar.open
    )
    return EvaluationInput(
        symbol_bars=bars, next_bar=entry, scheduled_open=_stamp("09:30"),
        scheduled_close=_stamp("16:00"), decision_cutoff=bars[-1].timestamp + timedelta(minutes=1),
        prior_strategy_entries=prior_entries,
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    below = list(bars[:30])
    below[-1] = replace(below[-1], close=100.49, high=max(below[-1].high, 100.49))
    malformed = list(bars[:30])
    malformed[5] = replace(malformed[5], high=malformed[5].low - 1.0)
    missing_open = bars[1:30]
    return {
        "positive": evaluation_input(bars[:30], next_bar=bars[30]),
        "threshold-absent": evaluation_input(tuple(below), next_bar=bars[30]),
        "missing-open": evaluation_input(missing_open, next_bar=bars[30]),
        "missing-entry": evaluation_input(bars[:30], next_bar=None),
        "duplicate-signal": evaluation_input(
            bars[:30], next_bar=bars[30], prior_entries=((CHILD_HYPOTHESIS_ID, _stamp("09:59")),)
        ),
        "integrity-failure": evaluation_input(tuple(malformed), next_bar=bars[30]),
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_first_half_hour_to_close_momentum(evaluation_input(bars[:30], next_bar=bars[30]))
    changed_future = replace(bars[30], high=500.0, low=1.0, close=400.0, volume=9_999_999.0)
    changed = evaluate_first_half_hour_to_close_momentum(evaluation_input(bars[:30], next_bar=changed_future))
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_first_half_hour_to_close_momentum(evaluation_input(bars[:30], next_bar=bars[30]))
    if result.proposal is None:
        return False
    completed, rejected = simulate_strategy(
        SIMULATION_STRATEGY_ID, [result.proposal], {("SPY", SYNTHETIC_SESSION): bars},
        {SYNTHETIC_SESSION: CalendarSession(SYNTHETIC_SESSION, _stamp("09:30"), _stamp("16:00"), False)},
    )
    return len(completed) == 1 and not rejected and completed[0].exit_reason == "session_liquidation"


def frozen_dependency_identities() -> dict[str, str]:
    return {
        "lifecycle": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
        "return_formula": canonical_hash({"formula": "close_09:59/open_09:30-1", "threshold": 0.005}),
    }
