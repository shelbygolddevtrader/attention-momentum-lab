"""Exact frozen-evaluator adapter for the prospective VWAP-deviation child V001.

The immutable library parent is hypothesis-only.  This revision-2 child is an
explicit prospective human-authorized choice that delegates every trading
decision to the already-frozen ``vwap_mean_reversion_fade_long_v002`` executor.
It adds no trading rule and publishes no economic conclusion.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from aml.benchmark_strategy_research_v001 import canonical_hash
from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HaltInterval,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_executors_v001 import (
    EXECUTOR_IDENTITIES,
    STRATEGIES,
    evaluate,
)
from aml.professional_strategy_indicators_v001 import (
    SHARED_INDICATOR_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
)


PARENT_LIBRARY_ENTRY_ID = "vwap-deviation-mean-reversion-v001"
PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY = (
    "52b611750ebb7dccb2b5d2bbca3075681b167c9ae76c3fc3dc52ae10ef033663"
)
PARENT_REGISTRATION_IDENTITY = (
    "5891e8b9570de2b64bf7ebb494deea96ffb2e0c38c604d919029db7917a0ca00"
)
CHILD_HYPOTHESIS_ID = "vwap-downside-deviation-deceleration-reversion-long-v001"
CHILD_REVISION = 2
CHILD_VERSION = "1.0.0"
REFERENCE_STRATEGY_ID = "vwap_mean_reversion_fade_long_v002"
REFERENCE_STRATEGY_IDENTITY = (
    "bb1be7654ed9cdb59d59a51e7538bebc39886411d6c68fb5b23010edc24a8737"
)
REFERENCE_EXECUTOR_IDENTITY = EXECUTOR_IDENTITIES[REFERENCE_STRATEGY_ID]
REFERENCE_LIFECYCLE_IDENTITY = SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY
EXECUTOR_IDENTITY = REFERENCE_EXECUTOR_IDENTITY
NY = ZoneInfo("America/New_York")
SYNTHETIC_SESSION = date(2026, 1, 5)


class VwapDeviationMeanReversionAdapterError(ValueError):
    """The child-to-reference binding or deterministic input is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.vwap-deviation-mean-reversion-specification.v001",
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
    "reference_contract": {
        "binding_kind": "exact_semantic_alias",
        "strategy_id": REFERENCE_STRATEGY_ID,
        "strategy_identity": REFERENCE_STRATEGY_IDENTITY,
        "executor_identity": REFERENCE_EXECUTOR_IDENTITY,
        "lifecycle_identity": REFERENCE_LIFECYCLE_IDENTITY,
    },
    "session": {
        "calendar": "XNYS",
        "segment": "regular_only",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "observation_window": "09:50 through 15:00 inclusive",
        "entry_window": "09:51 through 15:01 inclusive",
    },
    "eligibility": {
        "decision_close_minimum_inclusive": 2.0,
        "decision_close_maximum_inclusive": 500.0,
        "maximum_entries_per_symbol_session": 2,
        "cooldown_complete_bars": 20,
        "post_halt_signal_block_complete_bars": 5,
    },
    "indicators": {
        "regular_vwap": (
            "frozen cumulative regular-session HLC3-volume VWAP, reset at the "
            "scheduled XNYS regular open; current completed bar included"
        ),
        "atr20": (
            "frozen Wilder ATR20 over consecutive completed regular-session bars; "
            "current completed bar included"
        ),
    },
    "setup": {
        "deviation": "(regular_VWAP_at_trigger-close_at_trigger)/ATR20_at_trigger",
        "deviation_threshold_inclusive": 1.5,
        "deceleration": (
            "the three immediately preceding completed bars each close below the "
            "prior completed bar and their positive decline magnitudes strictly "
            "decrease oldest to newest"
        ),
        "reversal_confirmation": (
            "current completed bar closes strictly above the immediately prior "
            "completed bar while deviation remains at least 1.5"
        ),
        "signal_timestamp": "exclusive end of the completed confirmation bar",
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
            "frozen signal-time VWAP target at or below cost-adjusted entry",
        ],
    },
    "stop": {
        "unrounded": (
            "minimum low of the three decline bars and confirmation bar minus "
            "0.25 times ATR20 at confirmation"
        ),
        "rounding": "floor to one cent",
    },
    "target": {
        "unrounded": "regular-session VWAP at signal, frozen for lifecycle",
        "rounding": "frozen indicator price under shared lifecycle",
    },
    "lifecycle": {
        "maximum_complete_bars": 60,
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
        "deceleration_or_indicator_unavailable",
        "deceleration_no_signal",
        "reversal_no_signal",
        "deviation_no_signal",
        "pre_entry_no_trade_or_unavailable",
        "proposal",
    ],
    "tie_breaking": [
        "earliest eligible deceleration sequence",
        "earliest eligible confirmation",
        "immutable child strategy identity",
    ],
    "missing_data": {
        "forward_fill": "prohibited",
        "interpolation": "prohibited",
        "deceleration_history_incomplete": "unavailable",
        "atr20_warmup_incomplete": "unavailable",
        "regular_vwap_unavailable": "unavailable",
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
        "VWAP follows rather than anchors a directional session",
        "deceleration does not precede durable convergence",
        "the frozen VWAP target is not reached before timeout",
        "modeled costs and adverse selection exceed any gross effect",
    ],
    "claim_boundary": (
        "exploratory diagnostics only; not empirical evidence, validation, holdout, "
        "production, trading authorization, or capital eligibility"
    ),
}


SPECIFICATION_IDENTITY = canonical_hash(
    {
        "domain": "aml.vwap-deviation-mean-reversion-specification.v001",
        "specification": FROZEN_SPECIFICATION,
    }
)
CHILD_STRATEGY_IDENTITY = canonical_hash(
    {
        "domain": "aml.vwap-deviation-mean-reversion-strategy.v001",
        "specification_identity": SPECIFICATION_IDENTITY,
    }
)


def frozen_dependency_identities() -> dict[str, str]:
    return {
        "indicator": SHARED_INDICATOR_IMPLEMENTATION_IDENTITY,
        "lifecycle": REFERENCE_LIFECYCLE_IDENTITY,
        "reference_executor": REFERENCE_EXECUTOR_IDENTITY,
        "reference_strategy": REFERENCE_STRATEGY_IDENTITY,
    }


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
        raise VwapDeviationMeanReversionAdapterError("frozen reference contract changed")


def evaluate_vwap_deviation_mean_reversion(value: EvaluationInput):
    """Evaluate only through the unchanged frozen reference executor."""

    verify_reference_binding()
    return evaluate(REFERENCE_STRATEGY_ID, value)


EXECUTOR_REGISTRY = {
    CHILD_HYPOTHESIS_ID: evaluate_vwap_deviation_mean_reversion,
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
        _bar(f"09:{minute:02d}", close=100.0, volume=100.0)
        for minute in range(30, 50)
    ]
    bars.extend(
        [
            _bar("09:50", open_=100.0, high=100.1, low=97.8, close=98.0),
            _bar("09:51", open_=98.0, high=98.1, low=95.8, close=96.0),
            _bar("09:52", open_=96.0, high=96.1, low=94.8, close=95.0),
            _bar("09:53", open_=95.0, high=95.1, low=94.3, close=94.5),
            _bar("09:54", open_=94.5, high=95.2, low=94.4, close=95.0),
            _bar("09:55", open_=95.1, high=100.0, low=95.0, close=99.0),
        ]
    )
    return tuple(bars)


def evaluation_input(
    bars: tuple[MinuteBar, ...],
    *,
    next_bar: MinuteBar | None,
    prior_entries: tuple[tuple[str, datetime], ...] = (),
    halts: tuple[HaltInterval, ...] = (),
) -> EvaluationInput:
    if not bars:
        raise VwapDeviationMeanReversionAdapterError("bars are required")
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
        prior_strategy_entries=prior_entries,
        halts=halts,
    )


def conformance_inputs() -> dict[str, EvaluationInput]:
    bars = conformance_bars()
    positive = evaluation_input(bars[:25], next_bar=bars[25])
    negative_bars = list(bars[:25])
    negative_bars[22] = replace(negative_bars[22], close=95.8)
    extension_bars = list(bars[:25])
    extension_bars[24] = replace(
        extension_bars[24], high=99.2, low=94.4, close=99.0
    )
    confirmation_bars = list(bars[:25])
    confirmation_bars[24] = replace(confirmation_bars[24], close=94.4)
    zero_volume_bars = tuple(replace(bar, volume=0.0) for bar in bars[:25])
    unavailable = evaluation_input(bars[:25], next_bar=None)
    duplicate = list(bars[:25])
    duplicate[20] = replace(duplicate[20], timestamp=duplicate[19].timestamp)
    warmup_bars = [
        _bar(f"09:{minute:02d}") for minute in range(30, 35)
    ] + [
        _bar(f"09:{minute:02d}") for minute in range(41, 50)
    ] + list(bars[20:25])
    warmup_halt = HaltInterval(
        start=_stamp("09:35"),
        resume=_stamp("09:41"),
        first_known_at=_stamp("09:35"),
    )
    return {
        "integrity-failure": evaluation_input(tuple(duplicate), next_bar=bars[25]),
        "atr-warmup-unavailable": evaluation_input(
            tuple(warmup_bars), next_bar=bars[25], halts=(warmup_halt,)
        ),
        "confirmation-absent": evaluation_input(
            tuple(confirmation_bars), next_bar=bars[25]
        ),
        "cooldown-active": evaluation_input(
            bars[:25],
            next_bar=bars[25],
            prior_entries=((REFERENCE_STRATEGY_ID, _stamp("09:50")),),
        ),
        "duplicate-signal": evaluation_input(
            bars[:25],
            next_bar=bars[25],
            prior_entries=(
                (REFERENCE_STRATEGY_ID, _stamp("09:30")),
                (REFERENCE_STRATEGY_ID, _stamp("09:31")),
            ),
        ),
        "extension-absent": evaluation_input(tuple(extension_bars), next_bar=bars[25]),
        "negative": evaluation_input(tuple(negative_bars), next_bar=bars[25]),
        "positive": positive,
        "unavailable": unavailable,
        "vwap-unavailable": evaluation_input(zero_volume_bars, next_bar=bars[25]),
    }


def no_lookahead_conformance() -> bool:
    bars = conformance_bars()
    baseline = evaluate_vwap_deviation_mean_reversion(
        evaluation_input(bars[:25], next_bar=bars[25])
    )
    changed_future = replace(
        bars[25], high=500.0, low=1.0, close=400.0, volume=9_999_999.0
    )
    changed = evaluate_vwap_deviation_mean_reversion(
        evaluation_input(bars[:25], next_bar=changed_future)
    )
    return baseline.canonical_bytes() == changed.canonical_bytes()


def proposal_pipeline_conformance() -> bool:
    bars = conformance_bars()
    result = evaluate_vwap_deviation_mean_reversion(
        evaluation_input(bars[:25], next_bar=bars[25])
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


def evaluate_causal_prefixes(bars: Iterable[MinuteBar]):
    values = tuple(bars)
    decisions = []
    for index, bar in enumerate(values[:-1]):
        clock = bar.timestamp.strftime("%H:%M")
        if not "09:50" <= clock <= "15:00":
            continue
        decisions.append(
            evaluate_vwap_deviation_mean_reversion(
                evaluation_input(values[: index + 1], next_bar=values[index + 1])
            )
        )
    return tuple(decisions)
