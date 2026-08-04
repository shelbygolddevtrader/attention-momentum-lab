"""Exact alias adapter for opening-range expansion continuation V001.

The library parent intentionally leaves direction, range length, and numeric
thresholds unresolved.  This module implements a revision-2 long-only child by
delegating every decision to the already-frozen five-minute ORB V002 executor.
It adds no trading rule.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HistoricalClockVolume,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_executors_v001 import (
    EXECUTOR_IDENTITIES,
    STRATEGIES,
    evaluate,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
)


PARENT_LIBRARY_ENTRY_ID = "opening-range-expansion-continuation-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "c17be56b215a4726a6a6e90c4193b2e41a9d04ea1bf6f125e28be7c3578d6ef3"
)
PARENT_REGISTRATION_IDENTITY = (
    "640a2116f0f61faefb4665df777b9a1b38093b3063b00326c17b9683a8451168"
)
CHILD_HYPOTHESIS_ID = "opening-range-expansion-continuation-long-five-minute-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
REFERENCE_STRATEGY_ID = "five_minute_orb_long_v002"
REFERENCE_STRATEGY_IDENTITY = (
    "8092124c58649e112e0c8c1d137583fdcf926ec0ad6bc6397bf36db09294bedb"
)
REFERENCE_EXECUTOR_IDENTITY = (
    "5e3b8f85ba8a0a369cc857b5968afc3b79a3ccdcbe9bb467200a53e80dc38977"
)
REFERENCE_LIFECYCLE_IDENTITY = (
    "b10c659118861f3818fc2b1f034a2700e055fdcc19bd51651969f660af94e384"
)
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 5)


class OpeningRangeExpansionAdapterError(ValueError):
    """The child-to-reference binding or normalized input is invalid."""


def verify_reference_binding() -> None:
    strategy = STRATEGIES.get(REFERENCE_STRATEGY_ID)
    if (
        strategy is None
        or strategy.get("strategy_identity") != REFERENCE_STRATEGY_IDENTITY
        or EXECUTOR_IDENTITIES.get(REFERENCE_STRATEGY_ID)
        != REFERENCE_EXECUTOR_IDENTITY
        or SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY
        != REFERENCE_LIFECYCLE_IDENTITY
    ):
        raise OpeningRangeExpansionAdapterError("frozen reference contract changed")


def evaluate_opening_range_expansion(value: EvaluationInput):
    """Evaluate only through the unchanged frozen reference executor."""

    verify_reference_binding()
    return evaluate(REFERENCE_STRATEGY_ID, value)


EXECUTOR_REGISTRY = {CHILD_HYPOTHESIS_ID: evaluate_opening_range_expansion}


def _stamp(clock: str, session: date = SYNTHETIC_SESSION) -> datetime:
    hour, minute = (int(item) for item in clock.split(":"))
    return datetime.combine(session, time(hour, minute), NY)


def _bar(
    clock: str,
    *,
    session: date = SYNTHETIC_SESSION,
    open_: float = 100.0,
    high: float = 100.8,
    low: float = 99.2,
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
    """Return deterministic in-memory bars; these are not research data."""

    return (
        _bar("09:30", high=101.0, low=99.0),
        _bar("09:31"),
        _bar("09:32"),
        _bar("09:33"),
        _bar("09:34"),
        _bar(
            "09:35",
            open_=100.8,
            high=102.0,
            low=100.5,
            close=101.5,
            volume=200.0,
        ),
        _bar(
            "09:36",
            open_=101.6,
            high=108.0,
            low=101.5,
            close=107.5,
            volume=150.0,
        ),
    )


def same_clock_history(
    *,
    count: int = 20,
    minute: str = "09:35",
    volume: float = 100.0,
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
) -> EvaluationInput:
    if not bars:
        raise OpeningRangeExpansionAdapterError("bars are required")
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
    session = bars[-1].session
    return EvaluationInput(
        symbol_bars=bars,
        next_bar=next_open,
        scheduled_open=_stamp("09:30", session),
        scheduled_close=_stamp("16:00", session),
        decision_cutoff=bars[-1].timestamp + timedelta(minutes=1),
        same_clock_history=(same_clock_history() if history is None else history),
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    positive = evaluation_input(bars[:6], next_bar=bars[6])
    negative_bars = list(bars[:6])
    negative_bars[-1] = replace(
        negative_bars[-1], high=101.0, close=101.0, volume=200.0
    )
    unavailable = evaluation_input(
        bars[:6], next_bar=bars[6], history=same_clock_history(count=19)
    )
    duplicate = list(bars[:6])
    duplicate[4] = replace(duplicate[4], timestamp=duplicate[3].timestamp)
    return {
        "integrity-failure": evaluation_input(tuple(duplicate), next_bar=bars[6]),
        "negative": evaluation_input(tuple(negative_bars), next_bar=bars[6]),
        "positive": positive,
        "unavailable": unavailable,
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=bars[6])
    )
    changed_future = replace(
        bars[6], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=bars[6])
    )
    if result.status != "proposal" or result.proposal is None:
        return False
    calendar = CalendarSession(
        SYNTHETIC_SESSION,
        _stamp("09:30"),
        _stamp("16:00"),
        False,
    )
    trades, rejections = simulate_strategy(
        REFERENCE_STRATEGY_ID,
        [result.proposal],
        {("TEST", SYNTHETIC_SESSION): bars},
        {SYNTHETIC_SESSION: calendar},
    )
    return len(trades) == 1 and not rejections


def evaluate_causal_prefixes(
    bars: Iterable[MinuteBar],
    histories: dict[str, tuple[HistoricalClockVolume, ...]],
):
    """Evaluate causal prefixes with only the exact next open exposed."""

    values = tuple(bars)
    decisions = []
    for index, bar in enumerate(values[:-1]):
        clock = bar.timestamp.strftime("%H:%M")
        if not "09:35" <= clock <= "10:59":
            continue
        decisions.append(
            evaluate_opening_range_expansion(
                evaluation_input(
                    values[: index + 1],
                    next_bar=values[index + 1],
                    history=histories.get(clock, ()),
                )
            )
        )
    return tuple(decisions)
