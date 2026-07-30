"""Explicit non-empirical fixtures for professional strategy executor tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HistoricalClockVolume,
    LiquidityHistory,
    MinuteBar,
    NextBarOpen,
    PremarketHistory,
    PriorClose,
)


NY = ZoneInfo("America/New_York")
SESSION = date(2026, 7, 28)


def stamp(clock: str, session: date = SESSION) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(session, time(hour, minute), NY)


def make_bars(
    end: str = "10:00",
    *,
    symbol: str = "SYN",
    modifications: dict[str, dict[str, float]] | None = None,
    closes: list[float] | None = None,
) -> tuple[MinuteBar, ...]:
    modifications = modifications or {}
    start = stamp("09:30")
    final = stamp(end)
    count = int((final - start).total_seconds() // 60) + 1
    values: list[MinuteBar] = []
    for index in range(count):
        timestamp = start + timedelta(minutes=index)
        close = closes[index] if closes is not None else 100.0
        prior_close = closes[index - 1] if closes is not None and index else close
        default = {
            "open": prior_close,
            "high": max(prior_close, close) + (0.1 if closes is not None else 1.0),
            "low": min(prior_close, close) - (0.1 if closes is not None else 1.0),
            "close": close,
            "volume": 100.0,
        }
        default.update(modifications.get(timestamp.strftime("%H:%M"), {}))
        values.append(
            MinuteBar(
                security_id=f"synthetic-{symbol}",
                symbol=symbol,
                session=SESSION,
                timestamp=timestamp,
                **default,
            )
        )
    return tuple(values)


def histories(clock: str = "10:00"):
    dates = []
    cursor = SESSION - timedelta(days=1)
    while len(dates) < 30:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    same_clock = tuple(
        HistoricalClockVolume(item, clock, 100.0) for item in dates[:20]
    )
    liquidity = tuple(
        LiquidityHistory(item, 10_000_000.0) for item in dates[:20]
    )
    premarket = tuple(
        PremarketHistory(item, 200_000.0) for item in dates[:20]
    )
    return same_clock, liquidity, premarket


def make_premarket() -> tuple[MinuteBar, ...]:
    values = []
    timestamp = stamp("04:00")
    end = stamp("09:29")
    while timestamp <= end:
        values.append(
            MinuteBar(
                security_id="synthetic-SYN",
                symbol="SYN",
                session=SESSION,
                timestamp=timestamp,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10.0,
            )
        )
        timestamp += timedelta(minutes=1)
    return tuple(values)


def make_input(
    bars: tuple[MinuteBar, ...],
    *,
    next_open: float = 101.0,
    spy_bars: tuple[MinuteBar, ...] = (),
    premarket_bars: tuple[MinuteBar, ...] = (),
    same_clock: tuple[HistoricalClockVolume, ...] | None = None,
    liquidity: tuple[LiquidityHistory, ...] | None = None,
    premarket_history: tuple[PremarketHistory, ...] | None = None,
    prior_close: PriorClose | None = None,
) -> EvaluationInput:
    clock_history, liquidity_history, premarket_baseline = histories(
        bars[-1].timestamp.strftime("%H:%M")
    )
    cutoff = bars[-1].timestamp + timedelta(minutes=1)
    return EvaluationInput(
        symbol_bars=bars,
        next_bar=NextBarOpen(
            bars[-1].security_id,
            bars[-1].symbol,
            SESSION,
            cutoff,
            next_open,
        ),
        scheduled_open=stamp("09:30"),
        scheduled_close=stamp("16:00"),
        decision_cutoff=cutoff,
        spy_bars=spy_bars,
        premarket_bars=premarket_bars,
        same_clock_history=clock_history if same_clock is None else same_clock,
        liquidity_history=(
            liquidity_history if liquidity is None else liquidity
        ),
        premarket_history=(
            premarket_baseline if premarket_history is None else premarket_history
        ),
        prior_close=prior_close,
    )


def positive_fixture(strategy_id: str) -> EvaluationInput:
    if strategy_id == "failed_downside_breakdown_reclaim_long_v002":
        bars = make_bars(
            modifications={
                "09:58": {"open": 99.0, "high": 99.4, "low": 98.0, "close": 98.4},
                "09:59": {"open": 98.4, "high": 99.5, "low": 98.3, "close": 99.2},
                "10:00": {"open": 99.2, "high": 99.7, "low": 99.0, "close": 99.3},
            }
        )
        return make_input(bars, next_open=99.5)
    if strategy_id == "first_pullback_continuation_long_v002":
        volume = {
            clock: {"volume": 200.0}
            for clock in ("09:51", "09:52", "09:53", "09:54")
        }
        volume.update(
            {
                "09:55": {
                    "open": 102.0, "high": 103.0, "low": 101.8,
                    "close": 102.0, "volume": 200.0,
                },
                "09:56": {
                    "open": 102.0, "high": 102.5, "low": 101.5,
                    "close": 102.0, "volume": 50.0,
                },
                "09:57": {
                    "open": 102.0, "high": 102.3, "low": 101.2,
                    "close": 101.8, "volume": 50.0,
                },
                "09:58": {
                    "open": 101.8, "high": 102.8, "low": 101.4,
                    "close": 102.5, "volume": 50.0,
                },
            }
        )
        return make_input(make_bars("09:58", modifications=volume), next_open=102.6)
    if strategy_id in {
        "five_minute_orb_long_v002", "fifteen_minute_orb_long_v002",
    }:
        bars = make_bars(
            "09:55",
            modifications={
                "09:55": {
                    "open": 100.0, "high": 101.5, "low": 99.8,
                    "close": 101.2, "volume": 150.0,
                }
            },
        )
        return make_input(bars, next_open=101.3)
    if strategy_id == "gap_and_go_long_v002":
        modifications = {
            clock: {"volume": 150.0}
            for clock in ("09:51", "09:52", "09:53", "09:54")
        }
        modifications["09:55"] = {
            "open": 100.0, "high": 102.3, "low": 99.8,
            "close": 102.0, "volume": 150.0,
        }
        return make_input(
            make_bars("09:55", modifications=modifications),
            next_open=102.1,
            premarket_bars=make_premarket(),
            prior_close=PriorClose(SESSION - timedelta(days=1), 96.0, 96.0),
        )
    if strategy_id == "high_of_day_breakout_long_v002":
        modifications = {
            clock: {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0}
            for clock in ("09:55", "09:56", "09:57", "09:58", "09:59")
        }
        modifications["10:00"] = {
            "open": 100.0, "high": 101.5, "low": 99.8,
            "close": 101.2, "volume": 150.0,
        }
        return make_input(make_bars(modifications=modifications), next_open=101.3)
    if strategy_id == "market_relative_momentum_long_v002":
        bars = make_bars(
            modifications={
                "10:00": {
                    "open": 100.0, "high": 103.2, "low": 99.8,
                    "close": 103.0, "volume": 150.0,
                }
            }
        )
        return make_input(bars, next_open=103.1, spy_bars=make_bars(symbol="SPY"))
    if strategy_id == "rsi_exhaustion_reversion_long_v002":
        closes = [100.0 - 0.18 * index for index in range(30)]
        closes.append(closes[-1] + 0.5)
        bars = make_bars(closes=closes)
        spy = make_bars(symbol="SPY")
        return make_input(bars, next_open=closes[-1] + 0.05, spy_bars=spy)
    if strategy_id == "vwap_mean_reversion_fade_long_v002":
        closes = [100.0] * 27 + [99.0, 98.4, 98.1, 98.3]
        bars = make_bars(closes=closes)
        return make_input(bars, next_open=98.4)
    if strategy_id == "vwap_reclaim_long_v002":
        closes = [100.0] * 26 + [99.0, 99.0, 99.0, 101.0, 101.2]
        bars = make_bars(
            closes=closes,
            modifications={"10:00": {"volume": 120.0}},
        )
        return make_input(bars, next_open=101.3)
    raise KeyError(strategy_id)


def changed(value: EvaluationInput, **changes) -> EvaluationInput:
    return replace(value, **changes)
