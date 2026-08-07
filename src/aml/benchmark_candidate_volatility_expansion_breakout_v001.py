"""Prospectively frozen volatility-expansion breakout child V001.

This is a candidate-specific evaluator.  It reuses the frozen indicator,
proposal, and lifecycle primitives without modifying any downstream contract.
The rule choices are explicitly human-authorized; they are not represented as
uniquely implied by the immutable parent hypothesis.
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
    HistoricalClockVolume,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_indicators_v001 import (
    atr20_series,
    post_halt_signal_blocked,
    same_clock_volume_ratio,
    validate_evaluation_input,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    build_proposal,
)
from aml.winner_archetype_contracts import canonical_hash


PARENT_LIBRARY_ENTRY_ID = "volatility-expansion-breakout-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "b0fac2d106396657709dce6924b485c1b496bc290b1d38ce3b0ae870e11efc5a"
)
PARENT_REGISTRATION_IDENTITY = (
    "cea672a290c7c88eed47d413af575266b62c0cdbb2fa147a8855b677bc14b142"
)
CHILD_HYPOTHESIS_ID = "volatility-expansion-breakout-long-adjacent-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 5)


class VolatilityExpansionError(ValueError):
    """The candidate contract or deterministic input is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.volatility-expansion-breakout-specification.v001",
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_version": CHILD_VERSION,
    "parent_library_entry_id": PARENT_LIBRARY_ENTRY_ID,
    "parent_framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    "revision": CHILD_REVISION,
    "design_authority": {
        "classification": "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES",
        "parent_is_exact_specification": False,
        "outcome_access_before_freeze": False,
        "optimization_count": 0,
        "parameter_search_count": 0,
    },
    "direction": "long_only",
    "universe": "config/liquid_day_trading_universe_v001.csv exact membership",
    "session": {
        "calendar": "XNYS",
        "segment": "regular_only",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "scheduled_open": "09:30 America/New_York",
        "normal_scheduled_close": "16:00 America/New_York",
        "decision_window": "09:35 through 14:30 inclusive",
        "entry_window": "09:36 through 14:31 inclusive",
    },
    "eligibility": {
        "decision_close_minimum_inclusive": 2.0,
        "decision_close_maximum_inclusive": 500.0,
        "maximum_proposals_per_symbol_session": 1,
        "reentry": "prohibited after the first emitted proposal",
        "post_halt_signal_block_complete_bars": 5,
    },
    "indicators": {
        "atr20": (
            "Frozen Wilder ATR20 over consecutive completed regular bars; seed is "
            "the arithmetic mean of the first 20 true ranges and later values are "
            "(19*prior_ATR+TR)/20; gaps reset the series."
        ),
        "true_range": (
            "max(high-low, abs(high-previous_close), abs(low-previous_close))"
        ),
        "breakout_reference": (
            "maximum high of the exact 15 completed bars immediately preceding "
            "the expansion bar; equal highs use the earliest timestamp"
        ),
        "same_clock_volume": (
            "trigger-bar volume divided by the median volume at the identical "
            "minute label from exactly the 20 most recent prior eligible sessions"
        ),
    },
    "setup": {
        "expansion_bar": "the completed bar immediately preceding the trigger bar",
        "expansion_threshold_inclusive": 1.5,
        "expansion_atr_reference": (
            "ATR20 at the completed bar immediately preceding the expansion bar"
        ),
        "expansion_direction": "expansion close strictly above expansion open",
        "breakout": (
            "expansion close strictly above the unrounded prior-15-bar high"
        ),
        "continuation": (
            "trigger-bar close strictly above the unrounded expansion-bar high"
        ),
        "volume_threshold_inclusive": 1.5,
        "signal_timestamp": "exclusive end of the completed trigger bar",
    },
    "entry": {
        "raw_price": "exact next complete bar open",
        "intended_timestamp": "exactly the signal timestamp",
        "adverse_friction_basis_points_per_side": 10,
        "pre_entry_invalidation": [
            "next exact bar missing",
            "next bar halted",
            "entry timestamp outside the frozen entry window",
            "raw or cost-adjusted entry at or below rounded stop",
        ],
    },
    "stop": {
        "unrounded": "minimum low of expansion bar and trigger bar",
        "rounding": "floor to one cent",
    },
    "target": {
        "rule": "cost-adjusted entry plus 2 times initial per-share risk",
        "rounding": "ceil to one cent",
    },
    "lifecycle": {
        "maximum_complete_bars": 120,
        "same_bar_precedence": (
            "gap stop, intrabar stop, gap target, intrabar target, timeout, "
            "session liquidation"
        ),
        "gap_through": (
            "long stop exits at min(open,stop); long target exits at max(open,target)"
        ),
        "session_exit": (
            "earlier of the 120th held bar or 15:55 completed-bar close; early "
            "close uses the fifth completed bar before scheduled close"
        ),
        "shared_cost_and_risk_model": "professional_strategy_lifecycle_v001 unchanged",
    },
    "rule_precedence": [
        "integrity_failure",
        "common_or_state_no_signal",
        "outside_window_no_signal",
        "indicator_or_history_unavailable",
        "expansion_no_signal",
        "breakout_or_continuation_no_signal",
        "volume_confirmation_no_signal",
        "pre_entry_no_trade_or_unavailable",
        "proposal",
    ],
    "tie_breaking": [
        "earliest expansion timestamp",
        "earliest prior-15-bar high timestamp for equal highs",
        "earliest trigger timestamp",
        "immutable child strategy identity",
    ],
    "missing_data": {
        "forward_fill": "prohibited",
        "interpolation": "prohibited",
        "atr20_warmup_incomplete": "unavailable",
        "prior_15_bar_window_incomplete": "unavailable",
        "same_clock_history_incomplete": "unavailable",
        "next_exact_bar_missing": "unavailable",
        "unclassified_minute_gap": "integrity_failure",
        "malformed_or_nonfinite_ohlcv": "integrity_failure",
        "incomplete_provenance": "integrity_failure",
    },
    "numeric_semantics": {
        "representation": "IEEE-754 binary64",
        "operation_rounding": "round to nearest ties to even",
        "comparison_tolerance": "none",
        "cent_rounding": (
            "convert binary64 through its shortest round-trip decimal string before "
            "floor or ceiling quantization to 0.01"
        ),
    },
    "decision_states": [
        "integrity_failure",
        "no_signal",
        "no_trade",
        "proposal",
        "unavailable",
    ],
    "expected_failure_modes": [
        "one-bar volatility shock does not continue",
        "breakout is a temporary liquidity sweep",
        "same-clock volume history is incomplete",
        "modeled costs and adverse selection exceed any gross effect",
    ],
    "claim_boundary": (
        "exploratory diagnostics only; not empirical evidence, validation, holdout, "
        "production, trading authorization, or capital eligibility"
    ),
}


SPECIFICATION_IDENTITY = canonical_hash(
    {
        "domain": "aml.volatility-expansion-breakout-specification.v001",
        "specification": FROZEN_SPECIFICATION,
    }
)
CHILD_STRATEGY_IDENTITY = canonical_hash(
    {
        "domain": "aml.volatility-expansion-breakout-strategy.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
    }
)


def _source_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


EXECUTOR_IDENTITY = canonical_hash(
    {
        "domain": "aml.volatility-expansion-breakout-executor.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
        "source_sha256": _source_identity(),
    }
)

CHILD_STRATEGY: Mapping[str, object] = {
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_identity": CHILD_STRATEGY_IDENTITY,
    "entry_window": {"first_entry": "09:36", "last_entry": "14:31"},
    "target": {"type": "fixed_2R"},
    "timeout": {"complete_bars": 120},
    "invalidation": {
        "rules": [
            "expansion_threshold_absent",
            "breakout_or_continuation_absent",
            "volume_confirmation_absent",
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


def _true_range(bar: MinuteBar, previous: MinuteBar) -> float:
    return max(
        bar.high - bar.low,
        abs(bar.high - previous.close),
        abs(bar.low - previous.close),
    )


def evaluate_volatility_expansion_breakout(value: EvaluationInput) -> EvaluationResult:
    """Evaluate one causal prefix under the frozen child specification."""

    validate_evaluation_input(value)
    bars = value.symbol_bars
    current = bars[-1]
    clock = current.timestamp.strftime("%H:%M")
    if post_halt_signal_blocked(value):
        return _decision(value, "no_signal", "post_halt_signal_block")
    if current.close < 2.0:
        return _decision(value, "no_signal", "price_below_minimum")
    if current.close > 500.0:
        return _decision(value, "no_signal", "price_above_maximum")
    prior_entries = [
        timestamp
        for strategy_id, timestamp in value.prior_strategy_entries
        if strategy_id == CHILD_HYPOTHESIS_ID
    ]
    if prior_entries:
        return _decision(value, "no_signal", "maximum_proposals_reached")
    if not "09:35" <= clock <= "14:30":
        return _decision(value, "no_signal", "outside_observation_window")
    index = len(bars) - 1
    expansion_index = index - 1
    if expansion_index < 1:
        return _decision(value, "unavailable", "expansion_bar_unavailable")
    atr = atr20_series(bars)
    prior_atr = atr[expansion_index - 1]
    if prior_atr is None:
        return _decision(value, "unavailable", "atr20_warmup_incomplete")
    if expansion_index < 15:
        return _decision(value, "unavailable", "breakout_lookback_incomplete")
    volume_ratio = same_clock_volume_ratio(current, value.same_clock_history)
    if volume_ratio is None:
        return _decision(value, "unavailable", "same_clock_volume_warmup_incomplete")
    expansion = bars[expansion_index]
    previous = bars[expansion_index - 1]
    expansion_ratio = _true_range(expansion, previous) / prior_atr
    breakout_window = bars[expansion_index - 15 : expansion_index]
    breakout_high = max(bar.high for bar in breakout_window)
    breakout_high_timestamp = next(
        bar.timestamp for bar in breakout_window if bar.high == breakout_high
    )
    if expansion_ratio < 1.5:
        return _decision(value, "no_signal", "expansion_ratio_below_threshold")
    if expansion.close <= expansion.open:
        return _decision(value, "no_signal", "expansion_bar_not_bullish")
    if expansion.close <= breakout_high:
        return _decision(value, "no_signal", "expansion_close_not_above_breakout")
    if current.close <= expansion.high:
        return _decision(value, "no_signal", "continuation_close_not_above_expansion")
    if volume_ratio < 1.5:
        return _decision(value, "no_signal", "same_clock_volume_below_threshold")
    return build_proposal(
        value,
        CHILD_STRATEGY,
        EXECUTOR_IDENTITY,
        unrounded_stop=min(expansion.low, current.low),
        indicator_snapshots={
            "atr20_before_expansion": prior_atr,
            "breakout_high": breakout_high,
            "breakout_high_timestamp": breakout_high_timestamp.isoformat(),
            "expansion_ratio": expansion_ratio,
            "expansion_timestamp": expansion.timestamp.isoformat(),
            "same_clock_volume_ratio": volume_ratio,
        },
    )


EXECUTOR_REGISTRY = {
    CHILD_HYPOTHESIS_ID: evaluate_volatility_expansion_breakout,
}


def _stamp(clock: str, session: date = SYNTHETIC_SESSION) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(session, time(hour, minute), NY)


def _bar(
    clock: str,
    *,
    session: date = SYNTHETIC_SESSION,
    open_: float = 100.0,
    high: float = 100.25,
    low: float = 99.75,
    close: float = 100.0,
    volume: float = 100.0,
) -> MinuteBar:
    return MinuteBar(
        security_id="synthetic-TEST",
        symbol="TEST",
        session=session,
        timestamp=_stamp(clock, session),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def conformance_bars() -> tuple[MinuteBar, ...]:
    bars = [
        _bar(f"09:{minute:02d}", close=100.0 + (minute % 2) * 0.01)
        for minute in range(30, 50)
    ]
    bars.extend(
        [
            _bar(
                "09:50",
                open_=100.0,
                high=101.20,
                low=99.80,
                close=101.10,
                volume=100.0,
            ),
            _bar(
                "09:51",
                open_=101.05,
                high=101.50,
                low=101.00,
                close=101.40,
                volume=200.0,
            ),
            _bar(
                "09:52",
                open_=101.50,
                high=106.0,
                low=101.40,
                close=105.8,
                volume=100.0,
            ),
        ]
    )
    return tuple(bars)


def same_clock_history(
    *, count: int = 20, minute: str = "09:51", volume: float = 100.0
) -> tuple[HistoricalClockVolume, ...]:
    start = SYNTHETIC_SESSION - timedelta(days=count + 5)
    return tuple(
        HistoricalClockVolume(
            session=start + timedelta(days=index),
            minute=minute,
            volume=volume,
            eligible=True,
            source_manifest_identity=f"synthetic-history-{index:02d}",
        )
        for index in range(count)
    )


def evaluation_input(
    bars: tuple[MinuteBar, ...],
    *,
    next_bar: MinuteBar | None,
    history: tuple[HistoricalClockVolume, ...] | None = None,
    prior_entries: tuple[tuple[str, datetime], ...] = (),
) -> EvaluationInput:
    if not bars:
        raise VolatilityExpansionError("bars are required")
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
    session = bars[-1].session
    return EvaluationInput(
        symbol_bars=bars,
        next_bar=entry,
        scheduled_open=_stamp("09:30", session),
        scheduled_close=_stamp("16:00", session),
        decision_cutoff=bars[-1].timestamp + timedelta(minutes=1),
        same_clock_history=(same_clock_history() if history is None else history),
        prior_strategy_entries=prior_entries,
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    positive = evaluation_input(bars[:22], next_bar=bars[22])
    absent_expansion = list(bars[:22])
    absent_expansion[20] = replace(
        absent_expansion[20],
        open=100.0,
        high=100.30,
        low=99.70,
        close=100.20,
    )
    absent_breakout = list(bars[:22])
    absent_breakout[20] = replace(
        absent_breakout[20],
        open=99.5,
        high=100.30,
        low=98.8,
        close=100.20,
    )
    absent_volume = list(bars[:22])
    absent_volume[21] = replace(absent_volume[21], volume=149.999)
    duplicate = list(bars[:22])
    duplicate[10] = replace(duplicate[10], timestamp=duplicate[9].timestamp)
    return {
        "breakout-absent": evaluation_input(
            tuple(absent_breakout), next_bar=bars[22]
        ),
        "duplicate-signal": evaluation_input(
            bars[:22],
            next_bar=bars[22],
            prior_entries=((CHILD_HYPOTHESIS_ID, _stamp("09:40")),),
        ),
        "expansion-absent": evaluation_input(
            tuple(absent_expansion), next_bar=bars[22]
        ),
        "integrity-failure": evaluation_input(tuple(duplicate), next_bar=bars[22]),
        "positive": positive,
        "volume-absent": evaluation_input(tuple(absent_volume), next_bar=bars[22]),
        "volume-unavailable": evaluation_input(
            bars[:22], next_bar=bars[22], history=same_clock_history(count=19)
        ),
        "warmup-unavailable": evaluation_input(bars[:10], next_bar=bars[10]),
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_volatility_expansion_breakout(
        evaluation_input(bars[:22], next_bar=bars[22])
    )
    changed_future = replace(
        bars[22], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_volatility_expansion_breakout(
        evaluation_input(bars[:22], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_volatility_expansion_breakout(
        evaluation_input(bars[:22], next_bar=bars[22])
    )
    if result.proposal is None:
        return False
    calendar = {
        SYNTHETIC_SESSION: CalendarSession(
            SYNTHETIC_SESSION,
            _stamp("09:30"),
            _stamp("16:00"),
            False,
        )
    }
    completed, rejected = simulate_strategy(
        "five_minute_orb_long_v002",
        [result.proposal],
        {("TEST", SYNTHETIC_SESSION): bars},
        calendar,
    )
    return len(completed) == 1 and not rejected


def frozen_dependency_identities() -> dict[str, str]:
    return {
        "indicator": canonical_hash(
            {
                "atr20": "aml.professional_strategy_indicators_v001.atr20_series",
                "same_clock_volume": (
                    "aml.professional_strategy_indicators_v001.same_clock_volume_ratio"
                ),
            }
        ),
        "lifecycle": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    }
