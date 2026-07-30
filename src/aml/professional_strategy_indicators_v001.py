"""Exact, causal indicator primitives frozen by Olympics V002."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import math
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    ExecutorIntegrityError,
    HaltInterval,
    HistoricalClockVolume,
    LiquidityHistory,
    MinuteBar,
    PremarketHistory,
)
from aml.winner_archetype_contracts import canonical_hash


NY = ZoneInfo("America/New_York")
ONE_MINUTE = timedelta(minutes=1)


def _implementation_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _require_ny(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExecutorIntegrityError(f"{name}:timezone_missing")
    if getattr(value.tzinfo, "key", None) != "America/New_York":
        raise ExecutorIntegrityError(f"{name}:timezone_not_America_New_York")


def _finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value):
        raise ExecutorIntegrityError(f"{name}:nonfinite")


def in_halt(timestamp: datetime, halts: tuple[HaltInterval, ...], cutoff: datetime) -> bool:
    return any(
        halt.first_known_at <= cutoff and halt.start <= timestamp < halt.resume
        for halt in halts
    )


def _validate_halts(halts: tuple[HaltInterval, ...], cutoff: datetime) -> None:
    ordered = sorted(halts, key=lambda item: (item.start, item.resume))
    if tuple(ordered) != halts:
        raise ExecutorIntegrityError("halts:not_stably_sorted")
    previous_resume: datetime | None = None
    for halt in halts:
        _require_ny(halt.start, "halt_start")
        _require_ny(halt.resume, "halt_resume")
        _require_ny(halt.first_known_at, "halt_first_known")
        if halt.start >= halt.resume or halt.first_known_at > cutoff:
            raise ExecutorIntegrityError("halts:invalid_or_future_evidence")
        if previous_resume is not None and halt.start < previous_resume:
            raise ExecutorIntegrityError("halts:overlap")
        if not halt.source_record_identity:
            raise ExecutorIntegrityError("halts:missing_provenance")
        previous_resume = halt.resume


def _validate_bars(
    bars: tuple[MinuteBar, ...],
    *,
    cutoff: datetime,
    expected_symbol: str | None,
    segment_start: datetime,
    segment_end: datetime,
    halts: tuple[HaltInterval, ...],
    require_from_start: bool,
) -> None:
    if not bars:
        raise ExecutorIntegrityError("bars:empty")
    if require_from_start and bars[0].timestamp != segment_start:
        raise ExecutorIntegrityError("bars:missing_segment_start")
    seen: set[datetime] = set()
    previous: MinuteBar | None = None
    security_id = bars[0].security_id
    symbol = bars[0].symbol
    session = bars[0].session
    if expected_symbol is not None and symbol != expected_symbol:
        raise ExecutorIntegrityError("bars:unexpected_symbol")
    for bar in bars:
        _require_ny(bar.timestamp, "bar_timestamp")
        if bar.timestamp.second or bar.timestamp.microsecond:
            raise ExecutorIntegrityError("bars:noncanonical_minute_label")
        if bar.timestamp in seen:
            raise ExecutorIntegrityError("bars:duplicate_timestamp")
        seen.add(bar.timestamp)
        if bar.security_id != security_id or bar.symbol != symbol or bar.session != session:
            raise ExecutorIntegrityError("bars:mixed_security_or_session")
        if not bar.security_id or not bar.symbol:
            raise ExecutorIntegrityError("bars:missing_security_identity")
        if bar.timestamp.date() != session:
            raise ExecutorIntegrityError("bars:session_timestamp_mismatch")
        if not segment_start <= bar.timestamp < segment_end:
            raise ExecutorIntegrityError("bars:outside_declared_segment")
        if bar.timestamp + ONE_MINUTE > cutoff:
            raise ExecutorIntegrityError("bars:incomplete_or_future_bar")
        if bar.feed != "sip" or not bar.adjustment_identity or not bar.source_manifest_identity:
            raise ExecutorIntegrityError("bars:missing_feed_or_provenance")
        for field, value in (
            ("open", bar.open), ("high", bar.high), ("low", bar.low),
            ("close", bar.close), ("volume", bar.volume),
        ):
            _finite(value, f"bar_{field}")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise ExecutorIntegrityError("bars:nonpositive_price")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise ExecutorIntegrityError("bars:invalid_ohlc")
        if bar.volume < 0:
            raise ExecutorIntegrityError("bars:negative_volume")
        if in_halt(bar.timestamp, halts, cutoff):
            raise ExecutorIntegrityError("bars:observed_during_halt")
        if previous is not None:
            if bar.timestamp <= previous.timestamp:
                raise ExecutorIntegrityError("bars:nonmonotonic")
            cursor = previous.timestamp + ONE_MINUTE
            while cursor < bar.timestamp:
                if not in_halt(cursor, halts, cutoff):
                    raise ExecutorIntegrityError("bars:unclassified_minute_gap")
                cursor += ONE_MINUTE
        previous = bar


def validate_evaluation_input(value: EvaluationInput) -> None:
    """Validate canonical input without consulting providers or implicit defaults."""

    _require_ny(value.scheduled_open, "scheduled_open")
    _require_ny(value.scheduled_close, "scheduled_close")
    _require_ny(value.decision_cutoff, "decision_cutoff")
    if (
        value.scheduled_open.strftime("%H:%M:%S.%f") != "09:30:00.000000"
        or value.scheduled_close.second
        or value.scheduled_close.microsecond
        or value.decision_cutoff.second
        or value.decision_cutoff.microsecond
    ):
        raise ExecutorIntegrityError("calendar:noncanonical_minute_boundary")
    if value.scheduled_open >= value.scheduled_close:
        raise ExecutorIntegrityError("calendar:invalid_session")
    if not value.calendar_identity:
        raise ExecutorIntegrityError("calendar:missing_identity")
    if not value.halt_coverage_complete:
        raise ExecutorIntegrityError("halts:coverage_incomplete")
    if not value.halt_manifest_identity:
        raise ExecutorIntegrityError("halts:missing_manifest_identity")
    if value.spy_bars and not value.spy_halt_coverage_complete:
        raise ExecutorIntegrityError("spy_halts:coverage_incomplete")
    if value.spy_bars and not value.spy_halt_manifest_identity:
        raise ExecutorIntegrityError("spy_halts:missing_manifest_identity")
    if not value.corporate_action_coverage_complete:
        raise ExecutorIntegrityError("corporate_actions:coverage_incomplete")
    if not value.corporate_action_lineage_valid:
        raise ExecutorIntegrityError("corporate_actions:lineage_invalid")
    if not value.corporate_action_manifest_identity:
        raise ExecutorIntegrityError("corporate_actions:missing_manifest_identity")
    _validate_halts(value.halts, value.decision_cutoff)
    _validate_halts(value.spy_halts, value.decision_cutoff)
    _validate_bars(
        value.symbol_bars,
        cutoff=value.decision_cutoff,
        expected_symbol=None,
        segment_start=value.scheduled_open,
        segment_end=value.scheduled_close,
        halts=value.halts,
        require_from_start=True,
    )
    last = value.symbol_bars[-1]
    if last.timestamp + ONE_MINUTE != value.decision_cutoff:
        raise ExecutorIntegrityError("decision_cutoff:not_source_bar_end")
    if value.next_bar is not None:
        entry = value.next_bar
        _require_ny(entry.timestamp, "next_bar_timestamp")
        if entry.timestamp != value.decision_cutoff:
            raise ExecutorIntegrityError("next_bar:not_exact_signal_timestamp")
        if (entry.security_id, entry.symbol, entry.session) != (
            last.security_id, last.symbol, last.session,
        ):
            raise ExecutorIntegrityError("next_bar:mixed_security_or_session")
        _finite(entry.open, "next_bar_open")
        if entry.open <= 0:
            raise ExecutorIntegrityError("next_bar:nonpositive_open")
        if entry.halted != in_halt(entry.timestamp, value.halts, value.decision_cutoff):
            raise ExecutorIntegrityError("next_bar:halt_state_mismatch")
        if (
            entry.feed != "sip"
            or not entry.adjustment_identity
            or not entry.source_manifest_identity
        ):
            raise ExecutorIntegrityError("next_bar:missing_feed_or_provenance")
    if value.spy_bars:
        _validate_bars(
            value.spy_bars,
            cutoff=value.decision_cutoff,
            expected_symbol="SPY",
            segment_start=value.scheduled_open,
            segment_end=value.scheduled_close,
            halts=value.spy_halts,
            require_from_start=True,
        )
        if value.spy_bars[-1].timestamp != last.timestamp:
            raise ExecutorIntegrityError("spy:latest_timestamp_misaligned")
    if value.premarket_bars:
        premarket_start = value.scheduled_open.replace(hour=4, minute=0)
        _validate_bars(
            value.premarket_bars,
            cutoff=value.scheduled_open,
            expected_symbol=last.symbol,
            segment_start=premarket_start,
            segment_end=value.scheduled_open,
            halts=value.halts,
            require_from_start=True,
        )
        expected_last = value.scheduled_open - ONE_MINUTE
        if value.premarket_bars[-1].timestamp != expected_last:
            raise ExecutorIntegrityError("premarket:incomplete_interval")
    seen_clock: set[tuple[date, str]] = set()
    for item in value.same_clock_history:
        key = (item.session, item.minute)
        if key in seen_clock:
            raise ExecutorIntegrityError("same_clock_history:duplicate_session_minute")
        seen_clock.add(key)
        try:
            parsed_minute = datetime.strptime(item.minute, "%H:%M")
        except ValueError as exc:
            raise ExecutorIntegrityError("same_clock_history:invalid_minute") from exc
        if parsed_minute.strftime("%H:%M") != item.minute:
            raise ExecutorIntegrityError("same_clock_history:noncanonical_minute")
        _finite(item.volume, "same_clock_history_volume")
        if item.volume < 0 or not item.adjustment_identity or not item.source_manifest_identity:
            raise ExecutorIntegrityError("same_clock_history:invalid_value_or_provenance")
    seen_premarket: set[date] = set()
    for item in value.premarket_history:
        if item.session in seen_premarket:
            raise ExecutorIntegrityError("premarket_history:duplicate_session")
        seen_premarket.add(item.session)
        _finite(item.dollar_volume, "premarket_history_dollar_volume")
        if (
            item.dollar_volume < 0
            or not item.adjustment_identity
            or not item.source_manifest_identity
        ):
            raise ExecutorIntegrityError("premarket_history:invalid_value_or_provenance")
    seen_liquidity: set[date] = set()
    for item in value.liquidity_history:
        if item.session in seen_liquidity:
            raise ExecutorIntegrityError("liquidity_history:duplicate_session")
        seen_liquidity.add(item.session)
        _finite(item.regular_dollar_volume, "liquidity_history_dollar_volume")
        if (
            item.regular_dollar_volume < 0
            or not item.adjustment_identity
            or not item.source_manifest_identity
        ):
            raise ExecutorIntegrityError("liquidity_history:invalid_value_or_provenance")
    if value.prior_close is not None:
        prior = value.prior_close
        _finite(prior.official_close, "prior_official_close")
        _finite(prior.adjusted_prior_close, "prior_adjusted_close")
        if (
            min(prior.official_close, prior.adjusted_prior_close) <= 0
            or not prior.adjustment_identity
            or not prior.source_manifest_identity
            or prior.prior_session >= value.symbol_bars[-1].session
        ):
            raise ExecutorIntegrityError("prior_close:invalid_value_or_provenance")
    previous_entry: datetime | None = None
    for strategy_id, timestamp in value.prior_strategy_entries:
        if not strategy_id:
            raise ExecutorIntegrityError("entry_history:missing_strategy")
        _require_ny(timestamp, "prior_signal_timestamp")
        if timestamp.date() != value.symbol_bars[-1].session:
            raise ExecutorIntegrityError("entry_history:wrong_session")
        if timestamp >= value.decision_cutoff:
            raise ExecutorIntegrityError("entry_history:future_entry")
        if previous_entry is not None and timestamp < previous_entry:
            raise ExecutorIntegrityError("entry_history:not_stably_sorted")
        previous_entry = timestamp


def consecutive_tail(bars: tuple[MinuteBar, ...]) -> tuple[MinuteBar, ...]:
    if not bars:
        return ()
    start = len(bars) - 1
    while start > 0 and bars[start].timestamp - bars[start - 1].timestamp == ONE_MINUTE:
        start -= 1
    return bars[start:]


def atr20_series(bars: tuple[MinuteBar, ...]) -> tuple[float | None, ...]:
    """Wilder ATR20 reset after every timestamp gap and at each supplied session."""

    result: list[float | None] = [None] * len(bars)
    segment_start = 0
    for index, bar in enumerate(bars):
        if index and (
            bar.session != bars[index - 1].session
            or bar.timestamp - bars[index - 1].timestamp != ONE_MINUTE
        ):
            segment_start = index
        offset = index - segment_start
        previous = bars[index - 1] if offset else None
        true_range = (
            bar.high - bar.low
            if previous is None
            else max(
                bar.high - bar.low,
                abs(bar.high - previous.close),
                abs(bar.low - previous.close),
            )
        )
        if offset == 19:
            values: list[float] = []
            for cursor in range(segment_start, index + 1):
                current = bars[cursor]
                prior = bars[cursor - 1] if cursor > segment_start else None
                values.append(
                    current.high - current.low
                    if prior is None
                    else max(
                        current.high - current.low,
                        abs(current.high - prior.close),
                        abs(current.low - prior.close),
                    )
                )
            result[index] = sum(values) / 20
        elif offset > 19:
            prior_atr = result[index - 1]
            if prior_atr is not None:
                result[index] = (19 * prior_atr + true_range) / 20
    return tuple(result)


def rsi14_series(bars: tuple[MinuteBar, ...]) -> tuple[float | None, ...]:
    """Wilder RSI14 reset after every timestamp gap and at each supplied session."""

    result: list[float | None] = [None] * len(bars)
    average_gain: float | None = None
    average_loss: float | None = None
    segment_start = 0
    for index, bar in enumerate(bars):
        if index and (
            bar.session != bars[index - 1].session
            or bar.timestamp - bars[index - 1].timestamp != ONE_MINUTE
        ):
            segment_start = index
            average_gain = average_loss = None
        offset = index - segment_start
        if offset < 14:
            continue
        delta = bar.close - bars[index - 1].close
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        if offset == 14:
            deltas = [
                bars[cursor].close - bars[cursor - 1].close
                for cursor in range(segment_start + 1, index + 1)
            ]
            average_gain = sum(max(item, 0.0) for item in deltas) / 14
            average_loss = sum(max(-item, 0.0) for item in deltas) / 14
        else:
            assert average_gain is not None and average_loss is not None
            average_gain = (13 * average_gain + gain) / 14
            average_loss = (13 * average_loss + loss) / 14
        if average_gain == 0 and average_loss == 0:
            result[index] = 50.0
        elif average_loss == 0:
            result[index] = 100.0
        elif average_gain == 0:
            result[index] = 0.0
        else:
            ratio = average_gain / average_loss
            result[index] = 100 - 100 / (1 + ratio)
    return tuple(result)


def regular_vwap_series(bars: tuple[MinuteBar, ...]) -> tuple[float | None, ...]:
    numerator = 0.0
    denominator = 0.0
    result: list[float | None] = []
    session: date | None = None
    for bar in bars:
        if bar.session != session:
            numerator = denominator = 0.0
            session = bar.session
        numerator += ((bar.high + bar.low + bar.close) / 3) * bar.volume
        denominator += bar.volume
        result.append(numerator / denominator if denominator > 0 else None)
    return tuple(result)


def premarket_vwap(bars: tuple[MinuteBar, ...]) -> float | None:
    numerator = sum(((bar.high + bar.low + bar.close) / 3) * bar.volume for bar in bars)
    denominator = sum(bar.volume for bar in bars)
    return numerator / denominator if denominator > 0 else None


def prior_volume_ratio(bars: tuple[MinuteBar, ...], index: int) -> float | None:
    if index < 20:
        return None
    window = bars[index - 20:index]
    if any(window[i].timestamp - window[i - 1].timestamp != ONE_MINUTE for i in range(1, 20)):
        return None
    baseline = median(item.volume for item in window)
    if baseline <= 0:
        return None
    return bars[index].volume / baseline


def local_five_volume_ratio(bars: tuple[MinuteBar, ...], index: int) -> float | None:
    if index < 24:
        return None
    window = bars[index - 24:index + 1]
    if any(window[i].timestamp - window[i - 1].timestamp != ONE_MINUTE for i in range(1, 25)):
        return None
    baseline = median(item.volume for item in window[:20])
    if baseline <= 0:
        return None
    return sum(item.volume for item in window[20:]) / (5 * baseline)


def same_clock_volume_ratio(
    current: MinuteBar,
    history: tuple[HistoricalClockVolume, ...],
) -> float | None:
    minute = current.timestamp.strftime("%H:%M")
    searched = [
        item for item in sorted(history, key=lambda item: item.session, reverse=True)
        if item.session < current.session and item.minute == minute
    ][:40]
    eligible = [
        item for item in searched
        if item.eligible and item.adjustment_identity and item.source_manifest_identity
    ]
    values = [item.volume for item in eligible[:20]]
    if len(values) < 20 or any(not math.isfinite(item) or item < 0 for item in values):
        return None
    baseline = median(values)
    return current.volume / baseline if baseline > 0 else None


def premarket_dollar_volume(bars: tuple[MinuteBar, ...]) -> float:
    return sum(((bar.high + bar.low + bar.close) / 3) * bar.volume for bar in bars)


def premarket_volume_ratio(
    current_total: float,
    history: tuple[PremarketHistory, ...],
    session: date,
) -> float | None:
    searched = [
        item for item in sorted(history, key=lambda item: item.session, reverse=True)
        if item.session < session
    ][:40]
    eligible = [
        item for item in searched
        if item.complete and not item.halted
        and item.adjustment_identity and item.source_manifest_identity
    ]
    values = [item.dollar_volume for item in eligible[:20]]
    if len(values) < 20 or any(not math.isfinite(item) or item < 0 for item in values):
        return None
    baseline = median(values)
    return current_total / baseline if baseline > 0 else None


def historical_liquidity(
    history: tuple[LiquidityHistory, ...], session: date,
) -> float | None:
    searched = [
        item for item in sorted(history, key=lambda item: item.session, reverse=True)
        if item.session < session
    ][:40]
    eligible = [
        item for item in searched
        if item.complete_session and not item.early_close
        and item.adjustment_identity and item.source_manifest_identity
    ]
    values = [item.regular_dollar_volume for item in eligible[:20]]
    if len(values) < 20 or any(not math.isfinite(item) or item < 0 for item in values):
        return None
    return median(values)


def exact_elapsed_return(
    bars: tuple[MinuteBar, ...], index: int, minutes: int,
) -> float | None:
    target = bars[index].timestamp - timedelta(minutes=minutes)
    lookup = {bar.timestamp: cursor for cursor, bar in enumerate(bars[:index + 1])}
    start_index = lookup.get(target)
    if start_index is None:
        return None
    interval = bars[start_index:index + 1]
    if any(
        interval[cursor].timestamp - interval[cursor - 1].timestamp != ONE_MINUTE
        for cursor in range(1, len(interval))
    ):
        return None
    start = bars[start_index].close
    return bars[index].close / start - 1 if start > 0 else None


def post_halt_signal_blocked(value: EvaluationInput) -> bool:
    source_timestamp = value.symbol_bars[-1].timestamp
    return any(
        halt.resume <= source_timestamp < halt.resume + timedelta(minutes=5)
        for halt in value.halts
    )


SHARED_INDICATOR_IMPLEMENTATION_IDENTITY = canonical_hash(
    {
        "schema": "aml.professional-strategy-indicators.implementation.v001",
        "v002_indicators_identity": (
            "3d1427872fc8d55e3cacc321f710a6a2b260d0a1d01259147b6ff3a422a6f852"
        ),
        "source_sha256": _implementation_identity(),
    }
)
