"""Adapters from historical attention signals to portfolio proposals.

This module does not calculate scores or alter execution parameters. It accepts
an already-produced replay frame, carries session and halt provenance into the
standard proposal contract, and can mark signals suppressed by the established
single-session simulator as invalidated before shared-portfolio admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Collection

import pandas as pd

from aml.market_halts import CompletenessMode, HaltSchedule
from aml.portfolio_simulator import (
    Direction,
    DuplicateSignalPolicy,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
)
from aml.trade_simulator import SimulationConfig


ATTENTION_STRATEGY_IDENTIFIER = "baseline_price_volume_momentum"
DEVELOPMENT_EVIDENCE_CLASS = "retrospective_development_only_not_validation"


@dataclass(frozen=True)
class HistoricalSessionProvenance:
    """Outcome-free provenance for one local historical development session."""

    symbol: str
    trading_date: date
    feed: str
    dataset_vintage: str
    session_class: str
    cohort_id: str
    data_source: str
    selection_rule: str
    input_sha256: str
    completeness_mode: CompletenessMode
    halt_schedule: HaltSchedule

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("Historical session symbol is required")
        object.__setattr__(self, "symbol", symbol)
        day = date.fromisoformat(str(self.trading_date))
        object.__setattr__(self, "trading_date", day)
        if self.feed not in {"sip", "iex", "legacy"}:
            raise ValueError("Historical session feed is unsupported")
        for field in (
            "dataset_vintage", "session_class", "cohort_id", "data_source",
            "selection_rule",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Historical session {field} is required")
        if (
            not isinstance(self.input_sha256, str)
            or len(self.input_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.input_sha256)
        ):
            raise ValueError("Historical session input_sha256 must be a SHA-256 digest")
        mode = CompletenessMode(self.completeness_mode)
        object.__setattr__(self, "completeness_mode", mode)
        if (
            self.halt_schedule.symbol != symbol
            or self.halt_schedule.trading_date != day
        ):
            raise ValueError("Halt schedule does not match historical session")


def attention_proposals_from_replay(
    replay: pd.DataFrame,
    session: HistoricalSessionProvenance,
    simulation_config: SimulationConfig | None = None,
    *,
    admitted_signal_timestamps: Collection[pd.Timestamp] | None = None,
) -> list[StrategyProposal]:
    """Convert eligible replay rows into deterministic attention proposals.

    Scores and ``eligible`` are consumed exactly as produced by the existing
    replay pipeline. When ``admitted_signal_timestamps`` is supplied, eligible
    rows omitted by the established legacy simulator are retained as explicitly
    invalidated audit records. This preserves its cooldown/entry-data admission
    behavior without duplicating those rules here.
    """

    config = simulation_config or SimulationConfig()
    required = {"timestamp", "symbol", "score", "eligible"}
    if missing := required.difference(replay.columns):
        raise ValueError(f"Replay is missing proposal columns: {', '.join(sorted(missing))}")
    frame = replay.loc[:, ["timestamp", "symbol", "score", "eligible"]].copy(deep=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if frame["timestamp"].dt.tz is None:
        raise ValueError("Replay timestamps must be timezone-aware")
    if frame["timestamp"].duplicated().any():
        raise ValueError("Replay timestamps must be unique within a session")
    if not frame["symbol"].astype(str).str.upper().eq(session.symbol).all():
        raise ValueError("Replay symbol does not match session provenance")
    if not frame["timestamp"].dt.date.eq(session.trading_date).all():
        raise ValueError("Replay timestamps do not match session trading date")
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    eligible = frame.loc[
        frame["score"].ge(config.eligible_score_threshold)
        & frame["eligible"].fillna(False).astype(bool)
    ]
    admitted = None
    if admitted_signal_timestamps is not None:
        admitted = {
            pd.Timestamp(timestamp).as_unit("ns") for timestamp in admitted_signal_timestamps
        }
        if any(timestamp.tzinfo is None for timestamp in admitted):
            raise ValueError("Admitted signal timestamps must be timezone-aware")

    proposals: list[StrategyProposal] = []
    for row in eligible.itertuples(index=False):
        signal = pd.Timestamp(row.timestamp).as_unit("ns")
        suppressed = admitted is not None and signal not in admitted
        proposals.append(StrategyProposal(
            strategy_identifier=ATTENTION_STRATEGY_IDENTIFIER,
            strategy_version=config.strategy_version,
            symbol=session.symbol,
            signal_timestamp=signal,
            direction=Direction.LONG,
            score_or_confidence=float(row.score),
            intended_entry_timestamp=signal + pd.Timedelta(
                config.entry_delay_minutes, unit="min"
            ),
            intended_entry_price=None,
            stop=PriceLevel.fraction(config.stop_fraction),
            target=PriceLevel.fraction(config.target_fraction),
            maximum_holding_minutes=config.maximum_holding_minutes,
            invalidation_reason=(
                "legacy_simulator_admission_suppressed" if suppressed else None
            ),
            provenance={
                "adapter": "historical_attention_v001",
                "strategy_identifier": ATTENTION_STRATEGY_IDENTIFIER,
                "strategy_version": config.strategy_version,
                "symbol": session.symbol,
                "trading_date": session.trading_date.isoformat(),
                "feed": session.feed,
                "dataset_vintage": session.dataset_vintage,
                "session_class": session.session_class,
                "cohort_id": session.cohort_id,
                "data_source": session.data_source,
                "selection_rule": session.selection_rule,
                "source_input_sha256": session.input_sha256,
                "completeness_mode": session.completeness_mode.value,
                "verified_halt_count": len(session.halt_schedule.records),
                "verified_full_halt_minute_count": len(
                    session.halt_schedule.full_halt_minutes
                ),
                "halt_data_source": session.halt_schedule.source_path,
                "eligible_score_threshold": config.eligible_score_threshold,
                "cooldown_minutes": config.cooldown_minutes,
                "legacy_admission_checked": admitted is not None,
                "not_validation_evidence": True,
            },
        ))
    return proposals


def historical_portfolio_config(
    simulation_config: SimulationConfig | None = None,
) -> PortfolioConfig:
    """Map unchanged legacy risk/execution settings to one fixed strategy sleeve."""

    config = simulation_config or SimulationConfig()
    return PortfolioConfig(
        total_capital=config.starting_equity,
        strategy_allocations=(StrategyAllocation(
            ATTENTION_STRATEGY_IDENTIFIER,
            config.strategy_version,
            config.starting_equity,
        ),),
        maximum_position_risk_fraction=config.risk_fraction,
        maximum_concurrent_positions=1,
        maximum_symbol_concentration_fraction=1.0,
        maximum_strategy_concentration_fraction=1.0,
        daily_loss_limit_fraction=1.0,
        slippage_fraction=config.slippage_fraction,
        maximum_entry_delay_minutes=config.maximum_entry_delay_minutes,
        duplicate_signal_policy=DuplicateSignalPolicy.REJECT_SAME_SYMBOL,
    )


def order_historical_proposals(
    proposals: Collection[StrategyProposal],
) -> list[StrategyProposal]:
    """Return deterministic cross-symbol, cross-session proposal ordering."""

    if any(not isinstance(item, StrategyProposal) for item in proposals):
        raise ValueError("Historical proposals must be StrategyProposal values")
    return sorted(proposals, key=lambda item: (
        item.signal_timestamp,
        item.symbol,
        item.strategy_identifier,
        item.strategy_version,
        item.proposal_id,
    ))


def assert_legacy_trade_parity(legacy: pd.DataFrame, portfolio: pd.DataFrame) -> None:
    """Fail unless shared-portfolio trades preserve legacy execution fields."""

    if len(legacy) != len(portfolio):
        raise RuntimeError("Historical portfolio trade count differs from legacy simulation")
    if legacy.empty:
        return
    old = legacy.sort_values(
        ["signal_timestamp", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    new = portfolio.sort_values(
        ["signal_timestamp", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    for column in (
        "symbol", "signal_timestamp", "actual_entry_timestamp", "exit_timestamp",
        "exit_reason", "quantity",
    ):
        if old[column].astype(str).tolist() != new[column].astype(str).tolist():
            raise RuntimeError(f"Historical portfolio parity failed for {column}")
    for column in ("adjusted_entry_price", "adjusted_exit_price", "net_pnl"):
        differences = (
            old[column].astype(float).to_numpy()
            - new[column].astype(float).to_numpy()
        )
        if abs(differences).max() > 1e-9:
            raise RuntimeError(f"Historical portfolio parity failed for {column}")
