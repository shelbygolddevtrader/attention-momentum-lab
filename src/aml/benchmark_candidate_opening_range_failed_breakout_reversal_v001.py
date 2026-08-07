"""Prospectively frozen opening-range failed-breakout reversal child V001."""

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


PARENT_LIBRARY_ENTRY_ID = "opening-range-failed-breakout-reversal-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "05d6ca28058f9807985eba7054afa30e5f580ce49d07d088320b6fbdd638a20c"
)
PARENT_REGISTRATION_IDENTITY = (
    "41eb9c5242835187f26911816f07d4945ef5a08d443de5825129a2553d3fea0a"
)
CHILD_HYPOTHESIS_ID = "opening-range-failed-downside-reclaim-long-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 5)


class OpeningRangeFailedBreakoutError(ValueError):
    """The child contract or deterministic input is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.opening-range-failed-breakout-specification.v001",
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
        "opening_range": "09:30 through 09:34 inclusive",
        "decision_window": "09:49 through 11:00 inclusive",
        "entry_window": "09:50 through 11:01 inclusive",
    },
    "eligibility": {
        "decision_close_minimum_inclusive": 2.0,
        "decision_close_maximum_inclusive": 500.0,
        "maximum_proposals_per_symbol_session": 1,
        "reentry": "prohibited after first emitted proposal",
        "post_halt_signal_block_complete_bars": 5,
    },
    "indicators": {
        "opening_range": (
            "maximum high and minimum low of the exact five completed bars "
            "09:30 through 09:34; equal extremes use earliest timestamp"
        ),
        "atr20": (
            "frozen Wilder ATR20 over consecutive completed regular bars; "
            "the breakdown bar ATR is used"
        ),
        "same_clock_volume": (
            "reclaim-bar volume divided by median volume at the identical minute "
            "from exactly the 20 most recent prior eligible sessions"
        ),
    },
    "setup": {
        "breakdown_bar": "completed bar immediately preceding reclaim bar",
        "downside_excursion": (
            "breakdown low at or below opening-range low minus 0.25 times "
            "ATR20 at the breakdown bar"
        ),
        "breakdown_close": "strictly below opening-range low",
        "reclaim": (
            "immediately adjacent completed bar closes strictly above opening-range "
            "low and strictly below opening-range high"
        ),
        "relative_volume_threshold_inclusive": 1.0,
        "signal_timestamp": "exclusive end of completed reclaim bar",
    },
    "entry": {
        "raw_price": "exact next complete bar open",
        "intended_timestamp": "exactly signal timestamp",
        "adverse_friction_basis_points_per_side": 10,
        "pre_entry_invalidation": [
            "next exact bar missing",
            "next bar halted",
            "entry timestamp outside frozen entry window",
            "raw or cost-adjusted entry at or below rounded stop",
            "opening-range midpoint target at or below cost-adjusted entry",
        ],
    },
    "stop": {
        "unrounded": (
            "minimum low of breakdown and reclaim bars minus 0.05 times "
            "ATR20 at the reclaim bar"
        ),
        "rounding": "floor to one cent",
    },
    "target": {
        "unrounded": "opening-range midpoint (range low plus half range width)",
        "rounding": "ceil to one cent",
    },
    "lifecycle": {
        "maximum_complete_bars": 90,
        "same_bar_precedence": (
            "gap stop, intrabar stop, gap target, intrabar target, timeout, "
            "session liquidation"
        ),
        "shared_cost_and_risk_model": "professional_strategy_lifecycle_v001 unchanged",
    },
    "rule_precedence": [
        "integrity_failure",
        "common_or_state_no_signal",
        "outside_window_no_signal",
        "opening_range_or_indicator_unavailable",
        "breakdown_no_signal",
        "adjacent_reclaim_no_signal",
        "volume_confirmation_no_signal",
        "pre_entry_no_trade_or_unavailable",
        "proposal",
    ],
    "tie_breaking": [
        "earliest opening-range high timestamp for equal highs",
        "earliest opening-range low timestamp for equal lows",
        "earliest adjacent reclaim timestamp",
        "immutable child strategy identity",
    ],
    "missing_data": {
        "forward_fill": "prohibited",
        "interpolation": "prohibited",
        "opening_range_incomplete": "unavailable",
        "atr20_warmup_incomplete": "unavailable",
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
            "convert binary64 through shortest round-trip decimal string before "
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
        "reclaim is a pause before downside continuation",
        "opening-range midpoint is not reached",
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
        "domain": "aml.opening-range-failed-breakout-specification.v001",
        "specification": FROZEN_SPECIFICATION,
    }
)
CHILD_STRATEGY_IDENTITY = canonical_hash(
    {
        "domain": "aml.opening-range-failed-breakout-strategy.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
    }
)


def _source_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


EXECUTOR_IDENTITY = canonical_hash(
    {
        "domain": "aml.opening-range-failed-breakout-executor.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
        "source_sha256": _source_identity(),
    }
)

CHILD_STRATEGY: Mapping[str, object] = {
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_identity": CHILD_STRATEGY_IDENTITY,
    "entry_window": {"first_entry": "09:50", "last_entry": "11:01"},
    "target": {"type": "indicator"},
    "timeout": {"complete_bars": 90},
    "invalidation": {
        "rules": [
            "downside_excursion_absent",
            "adjacent_reclaim_absent",
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


def evaluate_opening_range_failed_breakout_reversal(
    value: EvaluationInput,
) -> EvaluationResult:
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
    if any(
        strategy_id == CHILD_HYPOTHESIS_ID
        for strategy_id, _timestamp in value.prior_strategy_entries
    ):
        return _decision(value, "no_signal", "maximum_proposals_reached")
    if not "09:49" <= clock <= "11:00":
        return _decision(value, "no_signal", "outside_observation_window")
    if len(bars) < 6:
        return _decision(value, "unavailable", "opening_range_incomplete")
    expected_opening_clocks = [f"09:{minute:02d}" for minute in range(30, 35)]
    if [bar.timestamp.strftime("%H:%M") for bar in bars[:5]] != expected_opening_clocks:
        return _decision(value, "unavailable", "opening_range_incomplete")
    index = len(bars) - 1
    breakdown_index = index - 1
    atr = atr20_series(bars)
    breakdown_atr = atr[breakdown_index]
    current_atr = atr[index]
    if breakdown_atr is None or current_atr is None:
        return _decision(value, "unavailable", "atr20_warmup_incomplete")
    volume_ratio = same_clock_volume_ratio(current, value.same_clock_history)
    if volume_ratio is None:
        return _decision(value, "unavailable", "same_clock_volume_warmup_incomplete")
    opening_range = bars[:5]
    range_high = max(bar.high for bar in opening_range)
    range_low = min(bar.low for bar in opening_range)
    range_high_timestamp = next(
        bar.timestamp for bar in opening_range if bar.high == range_high
    )
    range_low_timestamp = next(
        bar.timestamp for bar in opening_range if bar.low == range_low
    )
    breakdown = bars[breakdown_index]
    if breakdown.low > range_low - 0.25 * breakdown_atr:
        return _decision(value, "no_signal", "downside_excursion_below_threshold")
    if breakdown.close >= range_low:
        return _decision(value, "no_signal", "breakdown_close_not_below_range")
    if not range_low < current.close < range_high:
        return _decision(value, "no_signal", "adjacent_reclaim_absent")
    if volume_ratio < 1.0:
        return _decision(value, "no_signal", "same_clock_volume_below_threshold")
    return build_proposal(
        value,
        CHILD_STRATEGY,
        EXECUTOR_IDENTITY,
        unrounded_stop=min(breakdown.low, current.low) - 0.05 * current_atr,
        frozen_indicator_target=range_low + 0.5 * (range_high - range_low),
        indicator_snapshots={
            "atr20_at_breakdown": breakdown_atr,
            "atr20_at_reclaim": current_atr,
            "breakdown_timestamp": breakdown.timestamp.isoformat(),
            "opening_range_high": range_high,
            "opening_range_high_timestamp": range_high_timestamp.isoformat(),
            "opening_range_low": range_low,
            "opening_range_low_timestamp": range_low_timestamp.isoformat(),
            "same_clock_volume_ratio": volume_ratio,
        },
    )


EXECUTOR_REGISTRY = {
    CHILD_HYPOTHESIS_ID: evaluate_opening_range_failed_breakout_reversal,
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
        _bar(
            f"09:{minute:02d}",
            high=101.0 if minute == 31 else 100.5,
            low=99.0 if minute == 32 else 99.5,
            close=100.0,
        )
        for minute in range(30, 50)
    ]
    bars.extend(
        [
            _bar("09:50", open_=99.2, high=99.3, low=98.5, close=98.8),
            _bar(
                "09:51",
                open_=98.9,
                high=100.2,
                low=98.7,
                close=99.8,
                volume=100.0,
            ),
            _bar("09:52", open_=99.9, high=100.5, low=99.8, close=100.3),
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
        raise OpeningRangeFailedBreakoutError("bars are required")
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
    no_excursion = list(bars[:22])
    no_excursion[20] = replace(no_excursion[20], low=98.95, close=98.96)
    no_reclaim = list(bars[:22])
    no_reclaim[21] = replace(no_reclaim[21], close=98.9)
    low_volume = list(bars[:22])
    low_volume[21] = replace(low_volume[21], volume=99.999)
    duplicate = list(bars[:22])
    duplicate[10] = replace(duplicate[10], timestamp=duplicate[9].timestamp)
    return {
        "adjacent-reclaim-absent": evaluation_input(tuple(no_reclaim), next_bar=bars[22]),
        "duplicate-signal": evaluation_input(
            bars[:22],
            next_bar=bars[22],
            prior_entries=((CHILD_HYPOTHESIS_ID, _stamp("09:40")),),
        ),
        "excursion-absent": evaluation_input(tuple(no_excursion), next_bar=bars[22]),
        "integrity-failure": evaluation_input(tuple(duplicate), next_bar=bars[22]),
        "positive": evaluation_input(bars[:22], next_bar=bars[22]),
        "volume-absent": evaluation_input(tuple(low_volume), next_bar=bars[22]),
        "volume-unavailable": evaluation_input(
            bars[:22], next_bar=bars[22], history=same_clock_history(count=19)
        ),
        "warmup-unavailable": evaluation_input(bars[:20], next_bar=bars[20]),
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_opening_range_failed_breakout_reversal(
        evaluation_input(bars[:22], next_bar=bars[22])
    )
    changed_future = replace(
        bars[22], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_opening_range_failed_breakout_reversal(
        evaluation_input(bars[:22], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_opening_range_failed_breakout_reversal(
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
