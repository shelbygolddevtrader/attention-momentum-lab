"""Point-in-time observational context and zero-capital shadow records.

Nothing in this module is an input to a strategy evaluator or portfolio simulator.
It produces parallel, explicitly non-decision records for future research.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from aml.tournament_strategies import NormalizedSignal


CONTEXT_SCHEMA_VERSION = "aml.attention-shadow-context.v001"
EVENT_SCHEMA_VERSION = "aml.attention-event-context.v001"
SHADOW_SCHEMA_VERSION = "aml.attention-shadow-strategy.v001"


class EventType(str, Enum):
    EARNINGS_GUIDANCE = "earnings_or_guidance"
    CORPORATE_ACTION = "merger_acquisition_or_corporate_action"
    REGULATORY_LEGAL = "regulatory_or_legal_news"
    ANALYST_PRODUCT = "analyst_or_product_news"
    SECTOR_EVENT = "sector_wide_event"
    MACRO_INDEX = "macro_or_index_shock"
    SOCIAL_RETAIL = "social_media_or_retail_attention"
    SHORT_SQUEEZE = "short_squeeze_context"
    HALT_RESUMPTION = "halt_or_resumption"
    UNKNOWN = "unknown"


class PnlClassification(str, Enum):
    DEPLOYED = "deployed"
    REJECTED_SHADOW = "rejected_shadow"
    STRATEGY_SHADOW = "strategy_shadow"


def _timestamp(value: Any, name: str) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return result.as_unit("ns")


def _finite_optional(value: float | int | None, name: str) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite when present")
    return result


def canonical_context_json(value: object) -> str:
    def convert(item: object) -> object:
        if isinstance(item, pd.Timestamp):
            return item.isoformat()
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, Mapping):
            return {str(key): convert(child) for key, child in sorted(item.items())}
        if isinstance(item, (tuple, list)):
            return [convert(child) for child in item]
        return item

    return json.dumps(convert(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class EventContext:
    decision_timestamp: pd.Timestamp
    event_type: EventType = EventType.UNKNOWN
    source_id: str | None = None
    source_uri: str | None = None
    source_published_at: pd.Timestamp | None = None
    observed_at: pd.Timestamp | None = None
    missing_source_reason: str | None = "no_valid_decision_time_source"
    schema_version: str = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        decision = _timestamp(self.decision_timestamp, "decision_timestamp")
        object.__setattr__(self, "decision_timestamp", decision)
        object.__setattr__(self, "event_type", EventType(self.event_type))
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError("Unsupported event-context schema")
        if self.event_type is EventType.UNKNOWN:
            if not self.missing_source_reason:
                raise ValueError("Unknown events require an explicit missing-source reason")
            if self.source_id or self.source_uri or self.source_published_at:
                raise ValueError("Unknown events cannot claim unavailable provenance")
            return
        if not self.source_id or not self.source_uri or self.source_published_at is None:
            raise ValueError("Known events require decision-time source provenance")
        published = _timestamp(self.source_published_at, "source_published_at")
        observed = _timestamp(
            self.observed_at if self.observed_at is not None else published, "observed_at"
        )
        if published > decision or observed > decision:
            raise ValueError("Event provenance cannot arrive after the decision timestamp")
        if self.missing_source_reason:
            raise ValueError("Known events cannot have a missing-source reason")
        object.__setattr__(self, "source_published_at", published)
        object.__setattr__(self, "observed_at", observed)


@dataclass(frozen=True)
class AttentionBreadthContext:
    qualifying_stocks_date_to_decision: int
    qualifying_stocks_same_hour_to_decision: int
    eligible_universe_count: int
    eligible_universe_qualifying_fraction: float
    concurrent_signal_count: int
    aggregate_qualifying_premarket_dollar_volume: float | None
    median_qualifying_gap: float | None
    maximum_qualifying_gap: float | None
    same_direction_fraction: float | None
    premarket_source_status: str


@dataclass(frozen=True)
class CrossSectionalContext:
    spy_return_at_decision: float | None
    qqq_return_at_decision: float | None
    relative_return_vs_spy: float | None
    relative_return_vs_qqq: float | None
    qualifying_return_dispersion: float | None
    qualifying_gap_dispersion: float | None
    sector: str | None
    industry: str | None
    classification_source_status: str


@dataclass(frozen=True)
class CrowdingContext:
    proposals_competing_at_entry: int
    frozen_order_rank: int
    score_difference_from_top_frozen_order_proposal: float
    existing_portfolio_exposure: float | None
    rejection_reason: str | None
    rejected_only_for_position_limit: bool


@dataclass(frozen=True)
class IntradayConfirmationContext:
    price_relative_to_vwap: float | None
    vwap_slope_5m: float | None
    opening_range_position: float | None
    opening_range_state: str
    distance_from_session_high: float | None
    minutes_since_session_high: float | None
    pullback_depth: float | None
    recent_higher_high_count: int
    recent_higher_low_count: int
    volume_persistence: float | None
    spread_or_liquidity_proxy: float | None
    liquidity_proxy_source: str
    intended_entry_delay_minutes: float | None
    actual_entry_delay_minutes: float | None
    adverse_price_movement_before_fill: float | None


@dataclass(frozen=True)
class ExitPathDiagnostics:
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    minutes_to_maximum_favorable_excursion: float | None
    minutes_to_maximum_adverse_excursion: float | None
    pnl_at_fixed_intervals: Mapping[str, float | None]
    stopped_then_recovered_before_boundary: bool | None
    target_then_continued_before_boundary: bool | None
    path_start: pd.Timestamp
    path_end: pd.Timestamp
    path_row_count: int
    path_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "pnl_at_fixed_intervals",
            MappingProxyType(dict(sorted(self.pnl_at_fixed_intervals.items()))),
        )


@dataclass(frozen=True)
class SignalObservationRecord:
    signal_context_id: str
    proposal_id: str | None
    strategy_id: str
    strategy_version: str
    symbol: str
    decision_timestamp: pd.Timestamp
    context_available: bool
    missing_context_reasons: tuple[str, ...]
    breadth: AttentionBreadthContext | None = None
    cross_sectional: CrossSectionalContext | None = None
    crowding: CrowdingContext | None = None
    intraday: IntradayConfirmationContext | None = None
    event: EventContext | None = None
    schema_version: str = CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_SCHEMA_VERSION:
            raise ValueError("Unsupported observational-context schema")
        object.__setattr__(
            self, "decision_timestamp", _timestamp(self.decision_timestamp, "decision_timestamp")
        )
        if not self.context_available and not self.missing_context_reasons:
            raise ValueError("Missing context requires an explicit reason")
        if self.event is not None and self.event.decision_timestamp != self.decision_timestamp:
            raise ValueError("Event and signal decision timestamps must match")

    def canonical_json(self) -> str:
        return canonical_context_json(asdict(self))


@dataclass(frozen=True)
class ShadowOutcomeRecord:
    proposal_id: str
    shadow_strategy_id: str
    shadow_strategy_version: str
    classification: PnlClassification
    shadow_net_pnl: float | None
    rejection_reason: str | None
    deployed: bool = False
    capital_allocation: float = 0.0
    included_in_portfolio_pnl: bool = False
    schema_version: str = SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        classification = PnlClassification(self.classification)
        object.__setattr__(self, "classification", classification)
        if classification is PnlClassification.DEPLOYED:
            raise ValueError("Shadow outcome records cannot represent deployed P&L")
        if self.deployed or self.capital_allocation != 0 or self.included_in_portfolio_pnl:
            raise ValueError("Shadow outcomes must remain zero-capital and non-portfolio")
        object.__setattr__(
            self, "shadow_net_pnl", _finite_optional(self.shadow_net_pnl, "shadow_net_pnl")
        )


@dataclass(frozen=True)
class ShadowStrategySpecification:
    strategy_id: str
    version: str
    research_hypothesis: str
    required_observations: tuple[str, ...]
    unresolved_definitions: tuple[str, ...]
    capital_allocation: float = 0.0
    affects_v011: bool = False
    implementation_status: str = "specification_only"

    def __post_init__(self) -> None:
        if self.capital_allocation != 0 or self.affects_v011:
            raise ValueError("Shadow specifications cannot receive capital or affect V0.1.1")
        if not self.unresolved_definitions:
            raise ValueError("Outcome-independent thresholds must remain explicitly unresolved")


SHADOW_STRATEGY_SPECS = (
    ShadowStrategySpecification(
        "attention_continuation_shadow", "0.1.0-spec",
        "Observe sustained attention, consolidation, and renewed continuation above VWAP.",
        ("attention_breadth", "vwap_position", "consolidation", "renewed_breakout"),
        ("sustained-attention horizon", "consolidation bounds", "renewed-breakout confirmation"),
    ),
    ShadowStrategySpecification(
        "attention_first_pullback_shadow", "0.1.0-spec",
        "Observe the first controlled pullback and subsequent continuation confirmation.",
        ("pullback_depth", "volume_contraction", "continuation_confirmation"),
        ("controlled-pullback bounds", "volume-contraction measure", "confirmation rule"),
    ),
    ShadowStrategySpecification(
        "failed_attention_reversal_shadow", "0.1.0-spec",
        "Observe failure of an attention move through VWAP or opening support.",
        ("attention_breadth", "opening_range_state", "vwap_position", "reversal_path"),
        ("major-attention definition", "support-loss confirmation", "reversal entry semantics"),
    ),
    ShadowStrategySpecification(
        "broad_event_leader_shadow", "0.1.0-spec",
        "Observe relative leaders when many names qualify contemporaneously.",
        ("breadth", "relative_strength", "liquidity", "volume_persistence", "crowding"),
        ("high-breadth definition", "leader ranking weights", "proposal timing"),
    ),
)


def observation_for_signal(
    signal: NormalizedSignal,
    *,
    proposal_id: str | None = None,
    breadth: AttentionBreadthContext | None = None,
    cross_sectional: CrossSectionalContext | None = None,
    crowding: CrowdingContext | None = None,
    intraday: IntradayConfirmationContext | None = None,
    event: EventContext | None = None,
    missing_context_reasons: Sequence[str] = (),
) -> SignalObservationRecord:
    """Build a parallel record without mutating the frozen signal or its identity."""
    available = any(value is not None for value in (breadth, cross_sectional, crowding, intraday))
    reasons = tuple(sorted(set(str(reason) for reason in missing_context_reasons if reason)))
    if event is None:
        event = EventContext(signal.signal_timestamp)
        reasons = tuple(sorted({*reasons, "event_source_unavailable"}))
    context_id = hashlib.sha256(
            canonical_context_json({
                "strategy_id": signal.strategy_id,
                "strategy_version": signal.strategy_version,
                "parameter_hash": signal.parameter_hash,
                "symbol": signal.symbol,
                "signal_timestamp": signal.signal_timestamp,
                "confidence": signal.confidence,
            }).encode()
        ).hexdigest()[:20]
    return SignalObservationRecord(
        signal_context_id=context_id,
        proposal_id=proposal_id,
        strategy_id=signal.strategy_id,
        strategy_version=signal.strategy_version,
        symbol=signal.symbol,
        decision_timestamp=signal.signal_timestamp,
        context_available=available,
        missing_context_reasons=reasons or (("context_source_unavailable",) if not available else ()),
        breadth=breadth,
        cross_sectional=cross_sectional,
        crowding=crowding,
        intraday=intraday,
        event=event,
    )


def _causal_bars(bars: pd.DataFrame, decision_timestamp: pd.Timestamp) -> pd.DataFrame:
    decision = _timestamp(decision_timestamp, "decision_timestamp")
    frame = bars.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("Context bars require unique timestamps")
    return frame.loc[frame["timestamp"].lt(decision)].sort_values("timestamp").reset_index(drop=True)


def causal_elapsed_return(
    bars: pd.DataFrame, decision_timestamp: pd.Timestamp, minutes: int = 5
) -> float | None:
    """Exact elapsed-minute return using only completed bars before decision time."""
    frame = _causal_bars(bars, decision_timestamp)
    if frame.empty:
        return None
    latest = pd.Timestamp(frame.iloc[-1]["timestamp"])
    prior_time = latest - pd.Timedelta(minutes, unit="min")
    prior = frame.loc[frame["timestamp"].eq(prior_time), "close"]
    if len(prior) != 1:
        return None
    return float(frame.iloc[-1]["close"] / prior.iloc[0] - 1)


def compute_attention_breadth_context(
    qualifying_signals: pd.DataFrame,
    *,
    decision_timestamp: pd.Timestamp,
    eligible_universe_count: int,
    direction: str,
) -> AttentionBreadthContext:
    """Summarize qualifying names observed no later than the decision timestamp."""
    if eligible_universe_count < 1:
        raise ValueError("eligible_universe_count must be positive")
    required = {"symbol", "signal_timestamp", "direction"}
    if missing := required.difference(qualifying_signals.columns):
        raise ValueError(f"Breadth source is missing: {', '.join(sorted(missing))}")
    decision = _timestamp(decision_timestamp, "decision_timestamp")
    frame = qualifying_signals.copy()
    frame["signal_timestamp"] = pd.to_datetime(frame["signal_timestamp"], utc=True)
    frame = frame.loc[frame["signal_timestamp"].le(decision)]
    frame = frame.loc[frame["signal_timestamp"].dt.date.eq(decision.date())]
    date_names = frame["symbol"].astype(str).str.upper().nunique()
    same_hour = frame.loc[
        frame["signal_timestamp"].dt.floor("h").eq(decision.floor("h"))
    ]
    concurrent = frame.loc[frame["signal_timestamp"].eq(decision)]
    premarket_status = "unavailable"
    premarket_total = None
    if "premarket_dollar_volume" in frame:
        values = pd.to_numeric(frame["premarket_dollar_volume"], errors="coerce")
        if len(frame) and values.notna().all():
            premarket_total = float(
                frame.assign(_value=values).groupby("symbol", sort=True)["_value"].last().sum()
            )
            premarket_status = "complete_point_in_time"
        elif values.notna().any():
            premarket_status = "partial_rejected_from_aggregate"
    gaps = (
        pd.to_numeric(frame["gap"], errors="coerce").dropna()
        if "gap" in frame else pd.Series(dtype=float)
    )
    same_direction = frame["direction"].astype(str).eq(direction)
    return AttentionBreadthContext(
        qualifying_stocks_date_to_decision=int(date_names),
        qualifying_stocks_same_hour_to_decision=int(
            same_hour["symbol"].astype(str).str.upper().nunique()
        ),
        eligible_universe_count=eligible_universe_count,
        eligible_universe_qualifying_fraction=date_names / eligible_universe_count,
        concurrent_signal_count=int(len(concurrent)),
        aggregate_qualifying_premarket_dollar_volume=premarket_total,
        median_qualifying_gap=float(gaps.median()) if not gaps.empty else None,
        maximum_qualifying_gap=float(gaps.max()) if not gaps.empty else None,
        same_direction_fraction=float(same_direction.mean()) if len(frame) else None,
        premarket_source_status=premarket_status,
    )


def compute_cross_sectional_context(
    qualifying_signals: pd.DataFrame,
    *,
    decision_timestamp: pd.Timestamp,
    signal_return: float,
    spy_bars: pd.DataFrame | None = None,
    qqq_bars: pd.DataFrame | None = None,
    sector: str | None = None,
    industry: str | None = None,
    classification_source_status: str = "unavailable",
) -> CrossSectionalContext:
    """Compute causal benchmark and dispersion observations for qualifying names."""
    decision = _timestamp(decision_timestamp, "decision_timestamp")
    frame = qualifying_signals.copy()
    if "signal_timestamp" not in frame:
        raise ValueError("Cross-sectional source requires signal_timestamp")
    frame["signal_timestamp"] = pd.to_datetime(frame["signal_timestamp"], utc=True)
    frame = frame.loc[frame["signal_timestamp"].le(decision)]
    returns = (
        pd.to_numeric(frame["raw_return_feature"], errors="coerce").dropna()
        if "raw_return_feature" in frame else pd.Series(dtype=float)
    )
    gaps = (
        pd.to_numeric(frame["gap"], errors="coerce").dropna()
        if "gap" in frame else pd.Series(dtype=float)
    )
    spy_return = causal_elapsed_return(spy_bars, decision) if spy_bars is not None else None
    qqq_return = causal_elapsed_return(qqq_bars, decision) if qqq_bars is not None else None
    if (sector or industry) and classification_source_status != "point_in_time_verified":
        raise ValueError("Classifications require a point-in-time verified source")
    return CrossSectionalContext(
        spy_return_at_decision=spy_return,
        qqq_return_at_decision=qqq_return,
        relative_return_vs_spy=None if spy_return is None else signal_return - spy_return,
        relative_return_vs_qqq=None if qqq_return is None else signal_return - qqq_return,
        qualifying_return_dispersion=float(returns.std(ddof=0)) if len(returns) else None,
        qualifying_gap_dispersion=float(gaps.std(ddof=0)) if len(gaps) else None,
        sector=sector,
        industry=industry,
        classification_source_status=classification_source_status,
    )


def compute_intraday_confirmation(
    bars: pd.DataFrame,
    decision_timestamp: pd.Timestamp,
    *,
    opening_range_minutes: int = 15,
    intended_entry_timestamp: pd.Timestamp | None = None,
    actual_entry_timestamp: pd.Timestamp | None = None,
) -> IntradayConfirmationContext:
    """Calculate causal context; fill diagnostics are labeled post-decision observations."""
    frame = _causal_bars(bars, decision_timestamp)
    if frame.empty:
        return IntradayConfirmationContext(
            None, None, None, "unavailable", None, None, None, 0, 0, None, None,
            "unavailable", None, None, None,
        )
    volume = frame["volume"].astype(float)
    price = frame["bar_vwap"].fillna(frame["close"]) if "bar_vwap" in frame else frame["close"]
    session_vwap = (price * volume).cumsum() / volume.cumsum().replace(0, np.nan)
    close = float(frame.iloc[-1]["close"])
    current_vwap = float(session_vwap.iloc[-1]) if pd.notna(session_vwap.iloc[-1]) else None
    vwap_distance = close / current_vwap - 1 if current_vwap else None
    vwap_slope = None
    if len(session_vwap) >= 6 and session_vwap.iloc[-6] != 0:
        vwap_slope = float(session_vwap.iloc[-1] / session_vwap.iloc[-6] - 1)
    opening = frame.iloc[:opening_range_minutes]
    opening_position = None
    opening_state = "opening_range_incomplete"
    if len(opening) == opening_range_minutes:
        opening_high = float(opening["high"].max())
        opening_low = float(opening["low"].min())
        width = opening_high - opening_low
        opening_position = (close - opening_low) / width if width > 0 else None
        opening_state = (
            "breakout_above" if close > opening_high else
            "failure_below" if close < opening_low else "inside"
        )
    session_high = float(frame["high"].max())
    high_rows = frame.loc[frame["high"].eq(session_high)]
    high_time = pd.Timestamp(high_rows.iloc[-1]["timestamp"])
    latest_time = pd.Timestamp(frame.iloc[-1]["timestamp"])
    distance_high = close / session_high - 1 if session_high else None
    pullback = (session_high - close) / session_high if session_high else None
    recent = frame.tail(6)
    higher_highs = int(recent["high"].diff().gt(0).sum())
    higher_lows = int(recent["low"].diff().gt(0).sum())
    persistence = None
    if len(frame) >= 10:
        earlier = volume.iloc[:-5].tail(20).median()
        if earlier > 0:
            persistence = float(volume.tail(5).median() / earlier)
    liquidity = float((frame.iloc[-1]["high"] - frame.iloc[-1]["low"]) / close)
    intended_delay = actual_delay = adverse = None
    if intended_entry_timestamp is not None:
        intended = _timestamp(intended_entry_timestamp, "intended_entry_timestamp")
        intended_delay = (intended - _timestamp(decision_timestamp, "decision_timestamp")).total_seconds() / 60
    if actual_entry_timestamp is not None:
        actual = _timestamp(actual_entry_timestamp, "actual_entry_timestamp")
        decision = _timestamp(decision_timestamp, "decision_timestamp")
        if actual < decision:
            raise ValueError("actual_entry_timestamp precedes decision")
        actual_delay = (actual - decision).total_seconds() / 60
        all_bars = bars.copy()
        all_bars["timestamp"] = pd.to_datetime(all_bars["timestamp"], utc=True)
        prefill = all_bars.loc[
            all_bars["timestamp"].ge(decision) & all_bars["timestamp"].le(actual)
        ]
        if not prefill.empty:
            adverse = float(prefill["low"].min() / close - 1)
    return IntradayConfirmationContext(
        vwap_distance, vwap_slope, opening_position, opening_state,
        distance_high, (latest_time - high_time).total_seconds() / 60, pullback,
        higher_highs, higher_lows, persistence, liquidity, "bar_range_fraction",
        intended_delay, actual_delay, adverse,
    )


def compute_exit_path_diagnostics(
    bars: pd.DataFrame,
    *,
    entry_timestamp: pd.Timestamp,
    entry_price: float,
    exit_timestamp: pd.Timestamp,
    exit_reason: str,
    maximum_holding_minutes: int,
    direction: str = "long",
    fixed_intervals: tuple[int, ...] = (5, 10, 15, 30),
) -> ExitPathDiagnostics:
    """Describe a completed path without altering its already-fixed exit."""
    entry = _timestamp(entry_timestamp, "entry_timestamp")
    exit_time = _timestamp(exit_timestamp, "exit_timestamp")
    boundary = entry + pd.Timedelta(maximum_holding_minutes, unit="min")
    frame = bars.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    path = frame.loc[frame["timestamp"].ge(entry) & frame["timestamp"].le(boundary)].copy()
    if path.empty:
        raise ValueError("Exit diagnostics require bars within the holding boundary")
    sign = 1 if direction == "long" else -1
    favorable = sign * (path["high" if sign == 1 else "low"] / entry_price - 1)
    adverse = sign * (path["low" if sign == 1 else "high"] / entry_price - 1)
    mfe_index, mae_index = favorable.idxmax(), adverse.idxmin()
    intervals: dict[str, float | None] = {}
    for minute in fixed_intervals:
        if minute > maximum_holding_minutes:
            intervals[f"{minute}m"] = None
            continue
        target = entry + pd.Timedelta(minute, unit="min")
        known = path.loc[path["timestamp"].le(target)]
        intervals[f"{minute}m"] = (
            None if known.empty else sign * (float(known.iloc[-1]["close"]) / entry_price - 1)
        )
    after_exit = path.loc[path["timestamp"].gt(exit_time)]
    recovered = continued = None
    if exit_reason == "stop":
        recovered = bool(
            not after_exit.empty
            and (after_exit["high"] if sign == 1 else after_exit["low"]).ge(entry_price).any()
        )
    if exit_reason == "target":
        exit_rows = path.loc[path["timestamp"].le(exit_time)]
        exit_reference = float(exit_rows.iloc[-1]["close"]) if not exit_rows.empty else entry_price
        continued = bool(
            not after_exit.empty
            and (
                after_exit["high"].gt(exit_reference).any()
                if sign == 1 else after_exit["low"].lt(exit_reference).any()
            )
        )
    path_bytes = path[["timestamp", "open", "high", "low", "close", "volume"]].to_csv(
        index=False, lineterminator="\n", float_format="%.17g"
    ).encode()
    return ExitPathDiagnostics(
        float(favorable.loc[mfe_index]), float(adverse.loc[mae_index]),
        (pd.Timestamp(path.loc[mfe_index, "timestamp"]) - entry).total_seconds() / 60,
        (pd.Timestamp(path.loc[mae_index, "timestamp"]) - entry).total_seconds() / 60,
        intervals, recovered, continued, pd.Timestamp(path.iloc[0]["timestamp"]),
        pd.Timestamp(path.iloc[-1]["timestamp"]), len(path),
        hashlib.sha256(path_bytes).hexdigest(),
    )


def deterministic_competition_context(
    signals: Sequence[NormalizedSignal], existing_exposure: float | None = None
) -> Mapping[str, CrowdingContext]:
    """Record the frozen engine's deterministic order; score does not alter that order."""
    records: dict[str, CrowdingContext] = {}
    groups: dict[pd.Timestamp, list[NormalizedSignal]] = {}
    for signal in signals:
        groups.setdefault(signal.signal_timestamp, []).append(signal)
    for group in groups.values():
        ordered = sorted(
            group,
            key=lambda signal: (
                signal.signal_timestamp, signal.strategy_id, signal.strategy_version,
                signal.symbol, signal.direction.value,
                observation_for_signal(signal).signal_context_id,
            ),
        )
        top_score = ordered[0].confidence
        for rank, signal in enumerate(ordered, start=1):
            key = observation_for_signal(signal).signal_context_id
            records[key] = CrowdingContext(
                proposals_competing_at_entry=len(ordered),
                frozen_order_rank=rank,
                score_difference_from_top_frozen_order_proposal=signal.confidence - top_score,
                existing_portfolio_exposure=_finite_optional(existing_exposure, "existing_exposure"),
                rejection_reason=None,
                rejected_only_for_position_limit=False,
            )
    return MappingProxyType(dict(sorted(records.items())))


def segregate_shadow_pnl(
    records: Sequence[ShadowOutcomeRecord], deployed_pnl: float
) -> Mapping[str, float]:
    """Return separated totals; shadow values never enter deployed portfolio P&L."""
    rejected = sum(
        record.shadow_net_pnl or 0 for record in records
        if record.classification is PnlClassification.REJECTED_SHADOW
    )
    strategy = sum(
        record.shadow_net_pnl or 0 for record in records
        if record.classification is PnlClassification.STRATEGY_SHADOW
    )
    return MappingProxyType({
        "deployed_portfolio_pnl": float(deployed_pnl),
        "rejected_shadow_pnl": float(rejected),
        "strategy_shadow_pnl": float(strategy),
    })
