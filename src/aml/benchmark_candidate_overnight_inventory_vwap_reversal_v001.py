"""Prospectively frozen overnight-inventory/VWAP reversal child V001.

The immutable library parent is intentionally broad. This revision-2 child is
an explicit prospective human-authorized experiment. It uses one causal 09:45
decision, existing minute OHLCV/VWAP primitives, and the unchanged lifecycle.
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
    PriorClose,
)
from aml.professional_strategy_indicators_v001 import (
    regular_vwap_series,
    validate_evaluation_input,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    build_proposal,
)
from aml.winner_archetype_contracts import canonical_hash


PARENT_LIBRARY_ENTRY_ID = "overnight-inventory-reversal-to-vwap-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "727be5ce5c0c85581c62e94e22a5dc10c5385191b313d755d0556d20cc055337"
)
PARENT_REGISTRATION_IDENTITY = (
    "bbc2deaa6c9f0281fa68472f7bd8bac43f4dbe17b7761e137bbb6c8b8d5c8069"
)
PARENT_OBSERVATION_IDENTITY = (
    "1ba0e932a6be432539fb94c9d7d22f73c5d43eaf00c82a1a57c71aff3e9226b6"
)
CHILD_HYPOTHESIS_ID = "gap-down-inventory-reversal-to-vwap-long-liquid-etfs-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
SIMULATION_STRATEGY_ID = "five_minute_orb_long_v002"
FROZEN_SYMBOLS = ("DIA", "IWM", "QQQ", "SPY")
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 6)
SYNTHETIC_PRIOR_SESSION = date(2026, 1, 5)


class OvernightInventoryVwapReversalError(ValueError):
    """The candidate contract or deterministic input is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.overnight-inventory-vwap-reversal-specification.v001",
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_version": CHILD_VERSION,
    "parent_library_entry_id": PARENT_LIBRARY_ENTRY_ID,
    "parent_framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    "revision": CHILD_REVISION,
    "design_authority": {
        "classification": "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES",
        "parent_is_exact_specification": False,
        "authorized_descendant_intent": (
            "test whether a material gap-down that shows an adjacent upside reversal "
            "during the first fifteen regular-session minutes reverts to developing VWAP"
        ),
        "outcome_access_before_freeze": False,
        "optimization_count": 0,
        "parameter_search_count": 0,
    },
    "direction": "long_only_gap_down_reversal",
    "universe": "exactly DIA, IWM, QQQ, and SPY",
    "session": {
        "calendar": "XNYS",
        "segment": "regular_only",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "signal_window": "exactly 09:30 through 09:44 America/New_York",
        "decision_timestamp": "09:45 America/New_York",
        "entry_timestamp": "09:45 America/New_York exact next bar open",
        "normal_liquidation": "15:55 completed-bar close reported at 15:56",
        "early_close_liquidation": "fifth completed bar before scheduled close",
    },
    "prior_close": {
        "definition": (
            "final completed regular-session minute-bar close from the immediately "
            "preceding XNYS session in the same adjustment and source lineage"
        ),
        "development_limitation": (
            "Alpaca adjustment=all historical bar value is contaminated development-only "
            "and is not an independently authoritative PIT official close"
        ),
        "maximum_calendar_age_days": 5,
    },
    "gap": {
        "formula": "open_09:30 / adjusted_prior_regular_close - 1",
        "threshold_inclusive": -0.005,
        "condition": "gap return less than or equal to negative 0.50 percent",
    },
    "indicators": {
        "regular_vwap": (
            "frozen cumulative regular-session HLC3-volume VWAP reset at 09:30; "
            "bars 09:30 through 09:44 included"
        ),
    },
    "signal": {
        "required_bar_count": 15,
        "failure_confirmation": (
            "09:44 close strictly exceeds 09:43 high while remaining strictly below "
            "the 09:44 developing VWAP"
        ),
        "signal_count_per_symbol_session": 1,
        "volume_confirmation": "none beyond volume required to calculate VWAP",
    },
    "entry": {
        "raw_price": "exact 09:45 complete bar open",
        "adverse_friction_basis_points_per_side": 10,
        "pre_entry_invalidation": [
            "09:45 exact bar missing",
            "09:45 bar halted",
            "raw or cost-adjusted entry at or below rounded stop",
            "frozen signal-time VWAP target at or below cost-adjusted entry",
        ],
    },
    "stop": {
        "unrounded": "minimum low of exact 09:30 through 09:44 signal window",
        "rounding": "floor to one cent",
    },
    "target": {
        "unrounded": "regular-session VWAP at 09:44, frozen for lifecycle",
        "rounding": "ceiling to one cent under shared lifecycle",
    },
    "lifecycle": {
        "maximum_complete_bars": 120,
        "intended_exit": "frozen VWAP target, structure stop, timeout, or session liquidation",
        "same_bar_precedence": (
            "gap stop, intrabar stop, gap target, intrabar target, timeout, session liquidation"
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
        "prior_close_unavailable_or_invalid",
        "gap_threshold_no_signal",
        "vwap_unavailable",
        "reversal_confirmation_no_signal",
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
        "missing_prior_close": "unavailable",
        "stale_prior_close": "unavailable",
        "missing_signal_bar": "unavailable",
        "regular_vwap_unavailable": "unavailable",
        "missing_09:45_entry_bar": "unavailable",
        "unclassified_minute_gap": "integrity_failure",
        "malformed_or_nonfinite_ohlcv": "integrity_failure",
        "invalid_prior_close_adjustment": "integrity_failure",
        "incomplete_provenance": "integrity_failure",
    },
    "numeric_semantics": {
        "representation": "IEEE-754 binary64",
        "operation_rounding": "round to nearest ties to even",
        "comparison_tolerance": "none",
        "cent_rounding": "shared lifecycle floor-cent stop and ceiling-cent target semantics",
    },
    "decision_states": [
        "integrity_failure",
        "no_signal",
        "no_trade",
        "proposal",
        "unavailable",
    ],
    "expected_holding_period": "minutes to 120 complete bars, with session fallback",
    "expected_maximum_trades_per_symbol_session": 1,
    "expected_failure_modes": [
        "fundamental information makes the overnight repricing persistent",
        "the developing VWAP follows price rather than serving as a useful consensus reference",
        "the fixed 09:45 observation misses later inventory normalization",
        "modeled costs and adverse selection exceed any gross effect",
    ],
    "claim_boundary": (
        "contaminated exploratory diagnostics and conditional candidate-only economic POC; "
        "not empirical evidence, validation, holdout, production, or capital eligibility"
    ),
}


SPECIFICATION_IDENTITY = canonical_hash(
    {
        "domain": "aml.overnight-inventory-vwap-reversal-specification.v001",
        "specification": FROZEN_SPECIFICATION,
    }
)
CHILD_STRATEGY_IDENTITY = canonical_hash(
    {
        "domain": "aml.overnight-inventory-vwap-reversal-strategy.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
    }
)


def _source_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


EXECUTOR_IDENTITY = canonical_hash(
    {
        "domain": "aml.overnight-inventory-vwap-reversal-executor.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
        "source_sha256": _source_identity(),
    }
)

CHILD_STRATEGY: Mapping[str, object] = {
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_identity": CHILD_STRATEGY_IDENTITY,
    "entry_window": {"first_entry": "09:45", "last_entry": "09:45"},
    "target": {"type": "frozen_session_vwap"},
    "timeout": {"complete_bars": 120},
    "invalidation": {
        "rules": [
            "gap_down_threshold_absent",
            "adjacent_upside_reversal_absent",
            "signal_close_not_below_vwap",
            "required_input_unavailable",
        ]
    },
}


def _decision(value: EvaluationInput, status: str, reason: str) -> EvaluationResult:
    return EvaluationResult(
        CHILD_HYPOTHESIS_ID,
        value.decision_cutoff.isoformat(),
        status,
        (reason,),
    )


def evaluate_overnight_inventory_vwap_reversal(
    value: EvaluationInput,
) -> EvaluationResult:
    """Evaluate the single causal 09:45 decision under the frozen child."""

    validate_evaluation_input(value)
    bars = value.symbol_bars
    current = bars[-1]
    if current.symbol not in FROZEN_SYMBOLS:
        return _decision(value, "no_signal", "symbol_outside_frozen_universe")
    if value.decision_cutoff.strftime("%H:%M") != "09:45":
        return _decision(value, "no_signal", "outside_exact_decision_timestamp")
    if any(
        strategy_id == CHILD_HYPOTHESIS_ID
        for strategy_id, _ in value.prior_strategy_entries
    ):
        return _decision(value, "no_signal", "maximum_proposals_reached")
    if len(bars) != 15:
        return _decision(value, "unavailable", "opening_window_incomplete")
    for index, bar in enumerate(bars):
        if bar.timestamp != value.scheduled_open + timedelta(minutes=index):
            return _decision(value, "unavailable", "opening_window_incomplete")
    prior = value.prior_close
    if prior is None:
        return _decision(value, "unavailable", "prior_close_missing")
    if current.session - prior.prior_session > timedelta(days=5):
        return _decision(value, "unavailable", "prior_close_stale")
    if prior.adjusted_prior_close <= 0 or not prior.adjustment_identity:
        raise OvernightInventoryVwapReversalError("prior close adjustment is invalid")
    gap_return = bars[0].open / prior.adjusted_prior_close - 1.0
    if gap_return > -0.005:
        return _decision(value, "no_signal", "gap_down_threshold_absent")
    vwap = regular_vwap_series(bars)[-1]
    if vwap is None:
        return _decision(value, "unavailable", "regular_vwap_unavailable")
    if current.close <= bars[-2].high:
        return _decision(value, "no_signal", "adjacent_upside_reversal_absent")
    if current.close >= vwap:
        return _decision(value, "no_signal", "signal_close_not_below_vwap")
    return build_proposal(
        value,
        CHILD_STRATEGY,
        EXECUTOR_IDENTITY,
        unrounded_stop=min(bar.low for bar in bars),
        frozen_indicator_target=vwap,
        indicator_snapshots={
            "adjusted_prior_regular_close": prior.adjusted_prior_close,
            "gap_return": gap_return,
            "opening_window_low": min(bar.low for bar in bars),
            "signal_close": current.close,
            "signal_time_regular_vwap": vwap,
        },
    )


EXECUTOR_REGISTRY = {
    CHILD_HYPOTHESIS_ID: evaluate_overnight_inventory_vwap_reversal,
}


def _stamp(clock: str, session: date = SYNTHETIC_SESSION) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(session, time(hour, minute), NY)


def _bar(
    clock: str,
    *,
    open_: float = 99.0,
    high: float = 99.2,
    low: float = 98.8,
    close: float = 99.0,
    volume: float = 100_000.0,
) -> MinuteBar:
    return MinuteBar(
        security_id="synthetic-SPY",
        symbol="SPY",
        session=SYNTHETIC_SESSION,
        timestamp=_stamp(clock),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def conformance_bars() -> tuple[MinuteBar, ...]:
    values: list[MinuteBar] = []
    for index in range(14):
        clock = _stamp("09:30") + timedelta(minutes=index)
        close = 99.9 - 0.025 * index
        values.append(
            _bar(
                clock.strftime("%H:%M"),
                open_=close - 0.02 if index == 0 else close + 0.02,
                high=close + 0.08,
                low=98.5 if index == 8 else close - 0.08,
                close=close,
            )
        )
    values.append(
        _bar("09:44", open_=99.58, high=99.72, low=99.52, close=99.68)
    )
    values.append(
        _bar("09:45", open_=99.55, high=99.78, low=99.50, close=99.70)
    )
    for index in range(1, 121):
        timestamp = _stamp("09:45") + timedelta(minutes=index)
        values.append(
            _bar(
                timestamp.strftime("%H:%M"),
                open_=99.70,
                high=99.90,
                low=99.65,
                close=99.82,
            )
        )
    return tuple(values)


def evaluation_input(
    bars: tuple[MinuteBar, ...],
    *,
    next_bar: MinuteBar | None,
    prior_close: PriorClose | None = None,
    prior_entries: tuple[tuple[str, datetime], ...] = (),
) -> EvaluationInput:
    if not bars:
        raise OvernightInventoryVwapReversalError("bars are required")
    entry = (
        None
        if next_bar is None
        else NextBarOpen(
            next_bar.security_id,
            next_bar.symbol,
            next_bar.session,
            next_bar.timestamp,
            next_bar.open,
        )
    )
    return EvaluationInput(
        symbol_bars=bars,
        next_bar=entry,
        scheduled_open=_stamp("09:30"),
        scheduled_close=_stamp("16:00"),
        decision_cutoff=bars[-1].timestamp + timedelta(minutes=1),
        prior_close=prior_close
        or PriorClose(
            SYNTHETIC_PRIOR_SESSION,
            100.5,
            100.5,
            "synthetic-adjustment-v001",
            "synthetic-prior-close-v001",
        ),
        prior_strategy_entries=prior_entries,
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    insufficient_gap = PriorClose(
        SYNTHETIC_PRIOR_SESSION,
        99.8,
        99.8,
        "synthetic-adjustment-v001",
        "synthetic-prior-close-v001",
    )
    no_reversal = list(bars[:15])
    no_reversal[-1] = replace(no_reversal[-1], close=99.55, high=99.72)
    no_vwap = tuple(replace(bar, volume=0.0) for bar in bars[:15])
    malformed = list(bars[:15])
    malformed[5] = replace(malformed[5], high=malformed[5].low - 1.0)
    return {
        "positive": evaluation_input(bars[:15], next_bar=bars[15]),
        "gap-threshold-absent": evaluation_input(
            bars[:15], next_bar=bars[15], prior_close=insufficient_gap
        ),
        "reversal-absent": evaluation_input(tuple(no_reversal), next_bar=bars[15]),
        "vwap-unavailable": evaluation_input(no_vwap, next_bar=bars[15]),
        "prior-close-missing": replace(
            evaluation_input(bars[:15], next_bar=bars[15]), prior_close=None
        ),
        "missing-entry": evaluation_input(bars[:15], next_bar=None),
        "duplicate-signal": evaluation_input(
            bars[:15],
            next_bar=bars[15],
            prior_entries=((CHILD_HYPOTHESIS_ID, _stamp("09:44")),),
        ),
        "integrity-failure": evaluation_input(tuple(malformed), next_bar=bars[15]),
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(bars[:15], next_bar=bars[15])
    )
    changed_future = replace(
        bars[15], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(bars[:15], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(bars[:15], next_bar=bars[15])
    )
    if result.proposal is None:
        return False
    completed, rejected = simulate_strategy(
        SIMULATION_STRATEGY_ID,
        [result.proposal],
        {("SPY", SYNTHETIC_SESSION): bars},
        {
            SYNTHETIC_SESSION: CalendarSession(
                SYNTHETIC_SESSION,
                _stamp("09:30"),
                _stamp("16:00"),
                False,
            )
        },
    )
    return len(completed) == 1 and not rejected


def frozen_dependency_identities() -> dict[str, str]:
    return {
        "lifecycle": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
        "regular_vwap_formula": canonical_hash(
            {
                "formula": "cumulative_HLC3_times_volume_over_volume",
                "window": "09:30_through_09:44",
            }
        ),
    }
