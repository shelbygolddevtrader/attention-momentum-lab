"""Alias adapter for the specified opening-drive first-pullback hypothesis.

The adapter intentionally delegates every signal and proposal decision to the
frozen V002 first-pullback evaluator.  It adds no trading rule.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_executors_v001 import (
    EXECUTOR_IDENTITIES,
    STRATEGIES,
    evaluate,
)


CANDIDATE_ID = "opening-drive-first-pullback-v001"
CANDIDATE_VERSION = "1.0.0"
REFERENCE_STRATEGY_ID = "first_pullback_continuation_long_v002"
REFERENCE_STRATEGY_IDENTITY = (
    "1013ee3c7c57ae6cb5326aa22e09ba980dfbe4bc2815fb40c0596db4f09b7c82"
)
REFERENCE_EXECUTOR_IDENTITY = (
    "9affc9b5496498c3c1371674af8b7b0e83a4a5d68672e869827cbf35a2babacd"
)
NY = ZoneInfo("America/New_York")
SESSION = date(2026, 1, 5)


class OpeningDriveAdapterError(ValueError):
    """The alias or frozen reference binding is invalid."""


def verify_reference_binding() -> None:
    strategy = STRATEGIES.get(REFERENCE_STRATEGY_ID)
    if (
        strategy is None
        or strategy.get("strategy_identity") != REFERENCE_STRATEGY_IDENTITY
        or EXECUTOR_IDENTITIES.get(REFERENCE_STRATEGY_ID)
        != REFERENCE_EXECUTOR_IDENTITY
    ):
        raise OpeningDriveAdapterError("frozen reference contract changed")


def evaluate_opening_drive_first_pullback(value: EvaluationInput):
    """Evaluate through the unchanged frozen reference executor."""

    verify_reference_binding()
    return evaluate(REFERENCE_STRATEGY_ID, value)


def _stamp(clock: str) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(SESSION, time(hour, minute), NY)


def _bar(
    timestamp: datetime,
    *,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
    volume: float = 100.0,
) -> MinuteBar:
    return MinuteBar(
        security_id="synthetic-TEST",
        symbol="TEST",
        session=SESSION,
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def conformance_bars() -> tuple[MinuteBar, ...]:
    """Return deterministic in-memory bars; these are not research data."""

    modifications: dict[str, dict[str, float]] = {
        clock: {"volume": 200.0}
        for clock in ("09:51", "09:52", "09:53", "09:54")
    }
    modifications.update(
        {
            "09:55": {
                "open_": 102.0,
                "high": 103.0,
                "low": 101.8,
                "close": 102.0,
                "volume": 200.0,
            },
            "09:56": {
                "open_": 102.0,
                "high": 102.5,
                "low": 101.5,
                "close": 102.0,
                "volume": 50.0,
            },
            "09:57": {
                "open_": 102.0,
                "high": 102.3,
                "low": 101.2,
                "close": 101.8,
                "volume": 50.0,
            },
            "09:58": {
                "open_": 101.8,
                "high": 102.8,
                "low": 101.4,
                "close": 102.5,
                "volume": 50.0,
            },
            "09:59": {
                "open_": 102.6,
                "high": 106.0,
                "low": 102.5,
                "close": 105.8,
                "volume": 100.0,
            },
        }
    )
    values: list[MinuteBar] = []
    timestamp = _stamp("09:30")
    while timestamp <= _stamp("09:59"):
        values.append(_bar(timestamp, **modifications.get(timestamp.strftime("%H:%M"), {})))
        timestamp += timedelta(minutes=1)
    return tuple(values)


def evaluation_input(
    bars: tuple[MinuteBar, ...],
    *,
    next_bar: MinuteBar | None,
) -> EvaluationInput:
    cutoff = bars[-1].timestamp + timedelta(minutes=1)
    next_open = (
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
        next_bar=next_open,
        scheduled_open=_stamp("09:30"),
        scheduled_close=_stamp("16:00"),
        decision_cutoff=cutoff,
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    positive = evaluation_input(bars[:29], next_bar=bars[29])
    negative_bars = list(bars[:29])
    negative_bars[-1] = replace(
        negative_bars[-1], high=102.0, close=101.9
    )
    unavailable = evaluation_input(bars[:19], next_bar=bars[19])
    duplicate = list(bars[:29])
    duplicate[-1] = replace(duplicate[-1], timestamp=duplicate[-2].timestamp)
    return {
        "integrity-failure": evaluation_input(tuple(duplicate), next_bar=bars[29]),
        "negative": evaluation_input(tuple(negative_bars), next_bar=bars[29]),
        "positive": positive,
        "unavailable": unavailable,
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_opening_drive_first_pullback(
        evaluation_input(bars[:29], next_bar=bars[29])
    )
    changed_future = replace(
        bars[29], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_opening_drive_first_pullback(
        evaluation_input(bars[:29], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_opening_drive_first_pullback(
        evaluation_input(bars[:29], next_bar=bars[29])
    )
    if result.status != "proposal" or result.proposal is None:
        return False
    calendar = CalendarSession(SESSION, _stamp("09:30"), _stamp("16:00"), False)
    trades, rejections = simulate_strategy(
        REFERENCE_STRATEGY_ID,
        [result.proposal],
        {("TEST", SESSION): bars},
        {SESSION: calendar},
    )
    return len(trades) == 1 and not rejections


def frame_to_bars(frame: pd.DataFrame) -> tuple[MinuteBar, ...]:
    """Normalize an already-authorized synthetic frame for frozen execution."""

    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    if not isinstance(frame, pd.DataFrame) or frame.empty or not required.issubset(frame):
        raise OpeningDriveAdapterError("authorized frame is incomplete")
    timestamps = pd.to_datetime(frame["timestamp"])
    if timestamps.dt.tz is None:
        raise OpeningDriveAdapterError("authorized frame timestamps are naive")
    result: list[MinuteBar] = []
    for row, timestamp in zip(frame.itertuples(index=False), timestamps, strict=True):
        local = pd.Timestamp(timestamp).tz_convert(NY)
        result.append(
            MinuteBar(
                security_id=f"synthetic-{row.symbol}",
                symbol=str(row.symbol),
                session=local.date(),
                timestamp=local.to_pydatetime(),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                source_manifest_identity="executable-candidate-v001-fixture",
            )
        )
    return tuple(result)


def evaluate_authorized_bars(bars: Iterable[MinuteBar]):
    """Evaluate every causal prefix with only the exact next open exposed."""

    values = tuple(bars)
    decisions = []
    for index in range(len(values) - 1):
        decisions.append(
            evaluate_opening_drive_first_pullback(
                evaluation_input(values[: index + 1], next_bar=values[index + 1])
            )
        )
    return tuple(decisions)
