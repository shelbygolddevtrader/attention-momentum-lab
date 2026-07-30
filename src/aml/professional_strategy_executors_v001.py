"""Synthetic-only, timestamp-local evaluators for ten frozen V002 strategies."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import inspect
from pathlib import Path
from typing import Callable, Mapping

from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    EvaluationResult,
    ExecutorIntegrityError,
)
from aml.professional_strategy_indicators_v001 import (
    atr20_series,
    exact_elapsed_return,
    historical_liquidity,
    local_five_volume_ratio,
    post_halt_signal_blocked,
    premarket_dollar_volume,
    premarket_volume_ratio,
    prior_volume_ratio,
    regular_vwap_series,
    rsi14_series,
    same_clock_volume_ratio,
    validate_evaluation_input,
)
from aml.professional_strategy_lifecycle_v001 import build_proposal
from aml.professional_strategy_olympics_v002 import STRATEGY_IDS, load_bundle
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[2]
V002_PATH = ROOT / "config/professional_strategy_olympics_v002.json"
V002_BUNDLE = load_bundle(V002_PATH)
STRATEGIES = {
    str(item["strategy_id"]): item for item in V002_BUNDLE["strategies"]
}


def _decision(strategy_id: str, value: EvaluationInput, status: str, *reasons: str):
    return EvaluationResult(
        strategy_id,
        value.decision_cutoff.isoformat(),
        status,
        tuple(reasons),
    )


def _clock(timestamp: datetime, start: str, end: str) -> bool:
    current = timestamp.strftime("%H:%M")
    return start <= current <= end


def _state_gate(strategy: Mapping[str, object], value: EvaluationInput) -> str | None:
    strategy_id = str(strategy["strategy_id"])
    entries = [
        timestamp for item_id, timestamp in value.prior_strategy_entries
        if item_id == strategy_id
    ]
    if len(entries) >= int(strategy["maximum_entries_per_symbol_day"]):
        return "maximum_entries_reached"
    if entries:
        cooldown = int(strategy["cooldown_complete_bars"])
        if value.decision_cutoff < entries[-1] + timedelta(minutes=cooldown):
            return "cooldown_active"
    return None


def _common(strategy_id: str, value: EvaluationInput) -> EvaluationResult | None:
    validate_evaluation_input(value)
    strategy = STRATEGIES[strategy_id]
    current = value.symbol_bars[-1]
    if post_halt_signal_blocked(value):
        return _decision(strategy_id, value, "no_signal", "post_halt_signal_block")
    price_min = strategy["eligibility"].get("price_min")
    price_max = strategy["eligibility"].get("price_max")
    if price_min is not None and current.close < float(price_min):
        return _decision(strategy_id, value, "no_signal", "price_below_minimum")
    if price_max is not None and current.close > float(price_max):
        return _decision(strategy_id, value, "no_signal", "price_above_maximum")
    state_reason = _state_gate(strategy, value)
    if state_reason:
        return _decision(strategy_id, value, "no_signal", state_reason)
    return None


def _unavailable(strategy_id: str, value: EvaluationInput, reason: str):
    return _decision(strategy_id, value, "unavailable", reason)


def _no_signal(strategy_id: str, value: EvaluationInput, reason: str):
    return _decision(strategy_id, value, "no_signal", reason)


def _proposal(
    strategy_id: str,
    value: EvaluationInput,
    *,
    stop: float,
    indicators: Mapping[str, float | str],
    frozen_target: float | None = None,
) -> EvaluationResult:
    return build_proposal(
        value,
        STRATEGIES[strategy_id],
        EXECUTOR_IDENTITIES[strategy_id],
        unrounded_stop=stop,
        indicator_snapshots=indicators,
        frozen_indicator_target=frozen_target,
    )


def _liquidity(strategy_id: str, value: EvaluationInput) -> float | EvaluationResult:
    current = value.symbol_bars[-1]
    liquidity = historical_liquidity(value.liquidity_history, current.session)
    if liquidity is None:
        return _unavailable(strategy_id, value, "unavailable_liquidity_history")
    return liquidity


def evaluate_failed_downside_breakdown_reclaim(
    value: EvaluationInput,
) -> EvaluationResult:
    strategy_id = "failed_downside_breakdown_reclaim_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:46", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    atr = atr20_series(bars)
    current_atr = atr[index]
    relative_volume = prior_volume_ratio(bars, index)
    if current_atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    if relative_volume is None:
        return _unavailable(strategy_id, value, "relative_volume_unavailable")
    reclaim_index = index - 1
    candidates: list[tuple[int, float]] = []
    for breach_index in range(max(0, reclaim_index - 3), reclaim_index):
        breach = bars[breach_index]
        if not _clock(breach.timestamp, "09:45", "15:00"):
            continue
        cutoff = breach.timestamp - timedelta(minutes=15)
        prior = [bar for bar in bars[:breach_index] if bar.timestamp <= cutoff]
        breach_atr = atr[breach_index]
        if not prior or breach_atr is None:
            continue
        prior_low = min(bar.low for bar in prior)
        if (
            breach.low <= prior_low - 0.25 * breach_atr
            and breach.close < prior_low
            and all(bar.close <= prior_low for bar in bars[breach_index + 1:reclaim_index])
            and bars[reclaim_index].close > prior_low
        ):
            candidates.append((breach_index, prior_low))
    if not candidates:
        return _no_signal(strategy_id, value, "breach_reclaim_sequence_absent")
    breach_index, prior_low = candidates[0]
    prior_cutoff = bars[breach_index].timestamp - timedelta(minutes=15)
    prior_low_timestamp = next(
        bar.timestamp
        for bar in bars[:breach_index]
        if bar.timestamp <= prior_cutoff and bar.low == prior_low
    )
    if current.close <= prior_low or relative_volume < 1:
        return _no_signal(strategy_id, value, "confirmation_failed")
    for cursor in range(breach_index + 1, index + 1):
        cursor_atr = atr[cursor]
        if (
            cursor_atr is not None
            and bars[cursor].low <= prior_low - 0.25 * cursor_atr
            and bars[cursor].close < prior_low
        ):
            return _no_signal(strategy_id, value, "second_distinct_breach")
    structure_low = min(bar.low for bar in bars[breach_index:index + 1])
    return _proposal(
        strategy_id,
        value,
        stop=structure_low - 0.05 * current_atr,
        indicators={
            "atr20": current_atr,
            "breach_timestamp": bars[breach_index].timestamp.isoformat(),
            "prior_low": prior_low,
            "prior_low_timestamp": prior_low_timestamp.isoformat(),
            "relative_volume": relative_volume,
        },
    )


def evaluate_first_pullback_continuation(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "first_pullback_continuation_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:35", "11:30"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    atr = atr20_series(bars)
    current_atr = atr[index]
    if current_atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    anchor_index = 0
    impulse: tuple[int, int] | None = None
    impulse_indicator_unavailable = False
    for cursor in range(1, index):
        if bars[cursor].timestamp.strftime("%H:%M") > "10:00":
            break
        if bars[cursor].low < bars[anchor_index].low:
            anchor_index = cursor
        ratio = local_five_volume_ratio(bars, cursor)
        if bars[cursor].high / bars[anchor_index].low - 1 >= 0.03 and ratio is None:
            impulse_indicator_unavailable = True
        if (
            bars[cursor].high / bars[anchor_index].low - 1 >= 0.03
            and ratio is not None
            and ratio >= 2
        ):
            impulse = (anchor_index, cursor)
            break
    if impulse is None:
        if impulse_indicator_unavailable:
            return _unavailable(strategy_id, value, "local_volume_unavailable")
        return _no_signal(strategy_id, value, "eligible_impulse_absent")
    anchor_index, impulse_end = impulse
    if impulse_end < 4:
        return _unavailable(strategy_id, value, "impulse_volume_window_unavailable")
    pullback_start = next(
        (
            cursor for cursor in range(impulse_end + 1, index + 1)
            if bars[cursor].low < bars[cursor - 1].low
        ),
        None,
    )
    if pullback_start is None:
        return _no_signal(strategy_id, value, "pullback_absent")
    duration = index - pullback_start + 1
    if duration < 2:
        return _no_signal(strategy_id, value, "pullback_too_short")
    if duration > 10:
        return _no_signal(strategy_id, value, "pullback_too_long")
    impulse_low = bars[anchor_index].low
    impulse_high = bars[impulse_end].high
    pullback = bars[pullback_start:index + 1]
    pullback_low = min(bar.low for bar in pullback)
    depth = (impulse_high - pullback_low) / (impulse_high - impulse_low)
    midpoint = impulse_high - 0.5 * (impulse_high - impulse_low)
    if not 0.20 <= depth <= 0.50:
        return _no_signal(strategy_id, value, "pullback_depth_outside_bounds")
    if any(bar.close < midpoint for bar in pullback):
        return _no_signal(strategy_id, value, "pullback_structure_broken")
    if any(bar.low < impulse_low for bar in bars[impulse_end + 1:index + 1]):
        return _no_signal(strategy_id, value, "second_impulse_anchor")
    impulse_volume = sum(bar.volume for bar in bars[impulse_end - 4:impulse_end + 1]) / 5
    pullback_volume = sum(bar.volume for bar in pullback) / len(pullback)
    if pullback_volume >= impulse_volume:
        return _no_signal(strategy_id, value, "volume_not_contracted")
    if current.close <= bars[index - 1].high:
        return _no_signal(strategy_id, value, "continuation_trigger_absent")
    return _proposal(
        strategy_id,
        value,
        stop=pullback_low - 0.05 * current_atr,
        indicators={
            "atr20": current_atr,
            "impulse_anchor_timestamp": bars[anchor_index].timestamp.isoformat(),
            "impulse_end_timestamp": bars[impulse_end].timestamp.isoformat(),
            "impulse_return": impulse_high / impulse_low - 1,
            "pullback_depth": depth,
            "pullback_duration": float(duration),
            "pullback_volume_mean": pullback_volume,
        },
    )


def _evaluate_orb(value: EvaluationInput, minutes: int) -> EvaluationResult:
    strategy_id = (
        "five_minute_orb_long_v002" if minutes == 5
        else "fifteen_minute_orb_long_v002"
    )
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    if index < minutes:
        return _unavailable(strategy_id, value, "required_range_bar_missing")
    expected = tuple(
        value.scheduled_open + timedelta(minutes=offset) for offset in range(minutes)
    )
    if tuple(bar.timestamp for bar in bars[:minutes]) != expected:
        raise ExecutorIntegrityError("orb:range_timestamp_integrity")
    current = bars[index]
    latest = "10:59" if minutes == 5 else "11:29"
    if not _clock(current.timestamp, f"09:{30 + minutes:02d}", latest):
        return _no_signal(strategy_id, value, "outside_observation_window")
    range_high = max(bar.high for bar in bars[:minutes])
    range_low = min(bar.low for bar in bars[:minutes])
    range_high_timestamp = next(bar.timestamp for bar in bars[:minutes] if bar.high == range_high)
    range_low_timestamp = next(bar.timestamp for bar in bars[:minutes] if bar.low == range_low)
    if any(bar.close < range_low for bar in bars[minutes:index]):
        return _no_signal(strategy_id, value, "range_invalidated")
    relative_volume = same_clock_volume_ratio(current, value.same_clock_history)
    if relative_volume is None:
        return _unavailable(strategy_id, value, "unavailable_same_clock_history")
    if current.close <= range_high:
        return _no_signal(strategy_id, value, "breakout_close_not_above_range")
    if relative_volume < 1.5:
        return _no_signal(strategy_id, value, "relative_volume_below_threshold")
    return _proposal(
        strategy_id,
        value,
        stop=range_low,
        indicators={
            "opening_range_high": range_high,
            "opening_range_high_timestamp": range_high_timestamp.isoformat(),
            "opening_range_low": range_low,
            "opening_range_low_timestamp": range_low_timestamp.isoformat(),
            "relative_volume": relative_volume,
        },
    )


def evaluate_five_minute_orb(value: EvaluationInput) -> EvaluationResult:
    return _evaluate_orb(value, 5)


def evaluate_fifteen_minute_orb(value: EvaluationInput) -> EvaluationResult:
    return _evaluate_orb(value, 15)


def evaluate_gap_and_go(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "gap_and_go_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:55", "10:59"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    if value.prior_close is None:
        return _unavailable(strategy_id, value, "prior_close_missing")
    prior = value.prior_close
    if current.session - prior.prior_session > timedelta(days=5):
        return _unavailable(strategy_id, value, "prior_close_stale")
    if prior.adjusted_prior_close <= 0 or not prior.adjustment_identity:
        raise ExecutorIntegrityError("prior_close:invalid_adjustment")
    if not value.premarket_bars:
        return _unavailable(strategy_id, value, "premarket_missing")
    current_premarket = premarket_dollar_volume(value.premarket_bars)
    premarket_ratio = premarket_volume_ratio(
        current_premarket, value.premarket_history, current.session
    )
    if premarket_ratio is None:
        return _unavailable(strategy_id, value, "premarket_history_unavailable")
    liquidity = _liquidity(strategy_id, value)
    if isinstance(liquidity, EvaluationResult):
        return liquidity
    gap = bars[0].open / prior.adjusted_prior_close - 1
    if gap < 0.04:
        return _no_signal(strategy_id, value, "gap_below_threshold")
    if current_premarket < 250_000:
        return _no_signal(strategy_id, value, "premarket_dollar_volume_below_threshold")
    if premarket_ratio < 1.5:
        return _no_signal(strategy_id, value, "premarket_ratio_below_threshold")
    if liquidity < 5_000_000:
        return _no_signal(strategy_id, value, "liquidity_below_threshold")
    atr = atr20_series(bars)[index]
    vwap = regular_vwap_series(bars)[index]
    local_volume = local_five_volume_ratio(bars, index)
    if atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    if vwap is None:
        return _unavailable(strategy_id, value, "regular_vwap_unavailable")
    if local_volume is None:
        return _unavailable(strategy_id, value, "local_volume_unavailable")
    opening_low = min(bar.low for bar in bars[:5])
    consolidations = []
    for duration in range(min(10, index - 5), 1, -1):
        candidate = bars[index - duration:index]
        width = max(bar.high for bar in candidate) - min(bar.low for bar in candidate)
        if width <= atr and all(bar.close >= opening_low for bar in candidate):
            consolidations.append(candidate)
    if not consolidations:
        return _no_signal(strategy_id, value, "eligible_consolidation_absent")
    consolidation = consolidations[0]
    premarket_high = max(bar.high for bar in value.premarket_bars)
    premarket_high_timestamp = next(
        bar.timestamp for bar in value.premarket_bars if bar.high == premarket_high
    )
    if current.close <= premarket_high or current.close <= vwap:
        return _no_signal(strategy_id, value, "premarket_high_or_vwap_not_broken")
    if local_volume < 1.5:
        return _no_signal(strategy_id, value, "local_volume_below_threshold")
    structure_low = min(bar.low for bar in consolidation + (current,))
    if value.next_bar is not None and value.next_bar.open <= opening_low:
        return _decision(strategy_id, value, "no_trade", "setup_invalidated")
    return _proposal(
        strategy_id,
        value,
        stop=structure_low,
        indicators={
            "atr20": atr,
            "gap": gap,
            "historical_liquidity": liquidity,
            "local_volume_ratio": local_volume,
            "premarket_dollar_volume": current_premarket,
            "premarket_high": premarket_high,
            "premarket_high_timestamp": premarket_high_timestamp.isoformat(),
            "premarket_ratio": premarket_ratio,
            "regular_vwap": vwap,
        },
    )


def evaluate_high_of_day_breakout(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "high_of_day_breakout_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:45", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    cutoff_timestamp = current.timestamp - timedelta(minutes=15)
    mature = [(cursor, bar) for cursor, bar in enumerate(bars[:index]) if bar.timestamp <= cutoff_timestamp]
    if not mature:
        return _unavailable(strategy_id, value, "mature_hod_unavailable")
    hod = max(bar.high for _, bar in mature)
    hod_index = next(cursor for cursor, bar in mature if bar.high == hod)
    if index < 5:
        return _unavailable(strategy_id, value, "consolidation_incomplete")
    consolidation = bars[index - 5:index]
    if any(bar.high > hod for bar in consolidation):
        return _no_signal(strategy_id, value, "consolidation_above_hod")
    atr = atr20_series(bars)[index]
    relative_volume = prior_volume_ratio(bars, index)
    if atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    if relative_volume is None:
        return _unavailable(strategy_id, value, "relative_volume_unavailable")
    width = max(bar.high for bar in consolidation) - min(bar.low for bar in consolidation)
    if width > 0.75 * atr:
        return _no_signal(strategy_id, value, "consolidation_too_wide")
    failures = sum(
        bar.high > hod and bar.close <= hod for bar in bars[hod_index + 1:index]
    )
    if failures > 2:
        return _no_signal(strategy_id, value, "third_failed_attempt")
    if current.close <= hod:
        return _no_signal(strategy_id, value, "hod_not_broken")
    if relative_volume < 1.5:
        return _no_signal(strategy_id, value, "relative_volume_below_threshold")
    return _proposal(
        strategy_id,
        value,
        stop=min(bar.low for bar in consolidation),
        indicators={
            "atr20": atr,
            "failed_attempts": float(failures),
            "hod": hod,
            "hod_timestamp": bars[hod_index].timestamp.isoformat(),
            "relative_volume": relative_volume,
        },
    )


def _spy_return_and_vwap(
    strategy_id: str, value: EvaluationInput, minutes: int,
) -> tuple[float, float] | EvaluationResult:
    if not value.spy_bars:
        return _unavailable(strategy_id, value, "SPY_bars_missing")
    spy_index = len(value.spy_bars) - 1
    if value.spy_bars[spy_index].timestamp != value.symbol_bars[-1].timestamp:
        raise ExecutorIntegrityError("spy:timestamp_misaligned")
    spy_return = exact_elapsed_return(value.spy_bars, spy_index, minutes)
    if spy_return is None:
        return _unavailable(strategy_id, value, "SPY_exact_endpoint_missing")
    spy_vwap = regular_vwap_series(value.spy_bars)[spy_index]
    if spy_vwap is None:
        return _unavailable(strategy_id, value, "SPY_vwap_unavailable")
    return spy_return, spy_vwap


def evaluate_market_relative_momentum(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "market_relative_momentum_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:45", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    symbol_return = exact_elapsed_return(bars, index, 15)
    if symbol_return is None:
        return _unavailable(strategy_id, value, "symbol_exact_endpoint_missing")
    spy = _spy_return_and_vwap(strategy_id, value, 15)
    if isinstance(spy, EvaluationResult):
        return spy
    spy_return, spy_vwap = spy
    relative_volume = prior_volume_ratio(bars, index)
    if relative_volume is None:
        return _unavailable(strategy_id, value, "relative_volume_unavailable")
    liquidity = _liquidity(strategy_id, value)
    if isinstance(liquidity, EvaluationResult):
        return liquidity
    relative_return = symbol_return - spy_return
    if symbol_return <= 0:
        return _no_signal(strategy_id, value, "symbol_return_not_positive")
    if relative_return < 0.02:
        return _no_signal(strategy_id, value, "relative_return_below_threshold")
    if relative_volume < 1.5:
        return _no_signal(strategy_id, value, "relative_volume_below_threshold")
    if liquidity < 5_000_000:
        return _no_signal(strategy_id, value, "liquidity_below_threshold")
    if value.spy_bars[-1].close < spy_vwap:
        return _no_signal(strategy_id, value, "SPY_below_vwap")
    start = current.timestamp - timedelta(minutes=15)
    interval = [bar for bar in bars if start <= bar.timestamp <= current.timestamp]
    return _proposal(
        strategy_id,
        value,
        stop=min(bar.low for bar in interval),
        indicators={
            "historical_liquidity": liquidity,
            "relative_return": relative_return,
            "relative_volume": relative_volume,
            "SPY_return_15m": spy_return,
            "SPY_vwap": spy_vwap,
            "symbol_return_15m": symbol_return,
        },
    )


def evaluate_rsi_exhaustion_reversion(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "rsi_exhaustion_reversion_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:50", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    rsi = rsi14_series(bars)
    atr = atr20_series(bars)[index]
    vwap = regular_vwap_series(bars)[index]
    symbol_return = exact_elapsed_return(bars, index, 20)
    if index < 1 or rsi[index] is None or rsi[index - 1] is None:
        return _unavailable(strategy_id, value, "rsi14_unavailable")
    if atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    if vwap is None:
        return _unavailable(strategy_id, value, "regular_vwap_unavailable")
    if symbol_return is None:
        return _unavailable(strategy_id, value, "symbol_exact_endpoint_missing")
    spy = _spy_return_and_vwap(strategy_id, value, 20)
    if isinstance(spy, EvaluationResult):
        return spy
    spy_return, _ = spy
    liquidity = _liquidity(strategy_id, value)
    if isinstance(liquidity, EvaluationResult):
        return liquidity
    if rsi[index] > 25:
        return _no_signal(strategy_id, value, "rsi_above_threshold")
    if current.close >= vwap:
        return _no_signal(strategy_id, value, "close_not_below_vwap")
    if symbol_return > -0.02:
        return _no_signal(strategy_id, value, "symbol_return_not_exhausted")
    if spy_return <= -0.01:
        return _no_signal(strategy_id, value, "SPY_return_below_threshold")
    if liquidity < 5_000_000:
        return _no_signal(strategy_id, value, "liquidity_below_threshold")
    if current.close <= bars[index - 1].high or rsi[index] <= rsi[index - 1]:
        return _no_signal(strategy_id, value, "reversal_confirmation_absent")
    return _proposal(
        strategy_id,
        value,
        stop=current.low - 0.25 * atr,
        frozen_target=vwap,
        indicators={
            "atr20": atr,
            "historical_liquidity": liquidity,
            "regular_vwap": vwap,
            "rsi14": rsi[index],
            "rsi14_prior": rsi[index - 1],
            "SPY_return_20m": spy_return,
            "symbol_return_20m": symbol_return,
        },
    )


def evaluate_vwap_mean_reversion_fade(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "vwap_mean_reversion_fade_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:50", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    if index < 4:
        return _unavailable(strategy_id, value, "deceleration_history_unavailable")
    atr = atr20_series(bars)[index]
    vwap = regular_vwap_series(bars)[index]
    if atr is None:
        return _unavailable(strategy_id, value, "atr20_unavailable")
    if vwap is None:
        return _unavailable(strategy_id, value, "regular_vwap_unavailable")
    declines = [
        bars[cursor - 1].close - bars[cursor].close
        for cursor in range(index - 3, index)
    ]
    if not all(item > 0 for item in declines) or not (
        declines[0] > declines[1] > declines[2]
    ):
        return _no_signal(strategy_id, value, "decline_sequence_not_strict")
    extension = (vwap - current.close) / atr
    if current.close <= bars[index - 1].close:
        return _no_signal(strategy_id, value, "positive_confirmation_absent")
    if extension < 1.5:
        return _no_signal(strategy_id, value, "extension_below_threshold")
    structure = bars[index - 3:index + 1]
    return _proposal(
        strategy_id,
        value,
        stop=min(bar.low for bar in structure) - 0.25 * atr,
        frozen_target=vwap,
        indicators={
            "atr20": atr,
            "decline_1": declines[0],
            "decline_2": declines[1],
            "decline_3": declines[2],
            "extension_atr": extension,
            "regular_vwap": vwap,
        },
    )


def evaluate_vwap_reclaim(value: EvaluationInput) -> EvaluationResult:
    strategy_id = "vwap_reclaim_long_v002"
    common = _common(strategy_id, value)
    if common:
        return common
    bars = value.symbol_bars
    index = len(bars) - 1
    current = bars[index]
    if not _clock(current.timestamp, "09:50", "15:00"):
        return _no_signal(strategy_id, value, "outside_observation_window")
    if index < 4:
        return _unavailable(strategy_id, value, "below_sequence_unavailable")
    vwaps = regular_vwap_series(bars)
    relative_volume = prior_volume_ratio(bars, index)
    if relative_volume is None:
        return _unavailable(strategy_id, value, "relative_volume_unavailable")
    if vwaps[index] is None or vwaps[index - 1] is None:
        return _unavailable(strategy_id, value, "regular_vwap_unavailable")
    if not (
        bars[index - 1].close > vwaps[index - 1]
        and current.close > vwaps[index]
    ):
        return _no_signal(strategy_id, value, "two_bar_reclaim_absent")
    sequence_end = index - 2
    sequence_start = sequence_end
    while (
        sequence_start >= 0
        and vwaps[sequence_start] is not None
        and bars[sequence_start].close < vwaps[sequence_start]
    ):
        sequence_start -= 1
    sequence_start += 1
    sequence = bars[sequence_start:sequence_end + 1]
    if len(sequence) < 3:
        return _no_signal(strategy_id, value, "selected_sequence_shorter_than_3")
    if relative_volume < 1.2:
        return _no_signal(strategy_id, value, "relative_volume_below_threshold")
    sequence_low = min(bar.low for bar in sequence)
    low_timestamp = next(bar.timestamp for bar in sequence if bar.low == sequence_low)
    return _proposal(
        strategy_id,
        value,
        stop=sequence_low,
        indicators={
            "below_sequence_bars": float(len(sequence)),
            "regular_vwap": vwaps[index],
            "relative_volume": relative_volume,
            "sequence_low": sequence_low,
            "sequence_low_timestamp": low_timestamp.isoformat(),
        },
    )


Evaluator = Callable[[EvaluationInput], EvaluationResult]


EXECUTOR_FUNCTIONS: dict[str, Evaluator] = {
    "failed_downside_breakdown_reclaim_long_v002": evaluate_failed_downside_breakdown_reclaim,
    "first_pullback_continuation_long_v002": evaluate_first_pullback_continuation,
    "five_minute_orb_long_v002": evaluate_five_minute_orb,
    "fifteen_minute_orb_long_v002": evaluate_fifteen_minute_orb,
    "gap_and_go_long_v002": evaluate_gap_and_go,
    "high_of_day_breakout_long_v002": evaluate_high_of_day_breakout,
    "market_relative_momentum_long_v002": evaluate_market_relative_momentum,
    "rsi_exhaustion_reversion_long_v002": evaluate_rsi_exhaustion_reversion,
    "vwap_mean_reversion_fade_long_v002": evaluate_vwap_mean_reversion_fade,
    "vwap_reclaim_long_v002": evaluate_vwap_reclaim,
}


def _executor_identity(strategy_id: str, evaluator: Evaluator) -> str:
    return canonical_hash(
        {
            "schema": "aml.professional-strategy-executor.v001",
            "strategy_id": strategy_id,
            "strategy_identity": STRATEGIES[strategy_id]["strategy_identity"],
            "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "function_source_sha256": hashlib.sha256(
                inspect.getsource(evaluator).encode("utf-8")
            ).hexdigest(),
        }
    )


EXECUTOR_IDENTITIES = {
    strategy_id: _executor_identity(strategy_id, EXECUTOR_FUNCTIONS[strategy_id])
    for strategy_id in STRATEGY_IDS
}


def evaluate(strategy_id: str, value: EvaluationInput) -> EvaluationResult:
    """Run one registered executor and encode integrity failures as audit output."""

    evaluator = EXECUTOR_FUNCTIONS.get(strategy_id)
    if evaluator is None:
        raise KeyError(f"Unknown frozen strategy: {strategy_id}")
    try:
        return evaluator(value)
    except ExecutorIntegrityError as exc:
        return EvaluationResult(
            strategy_id,
            value.decision_cutoff.isoformat(),
            "integrity_failure",
            (str(exc),),
        )
