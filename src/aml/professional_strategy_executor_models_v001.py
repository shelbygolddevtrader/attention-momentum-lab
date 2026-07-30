"""Canonical synthetic-only inputs and outputs for Olympics V002 executors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Mapping

from aml.winner_archetype_contracts import canonical_hash, canonical_json


EXECUTOR_PROTOCOL_VERSION = "professional-strategy-executors-v001"
EVIDENCE_CLASS = "synthetic_fixture_non_empirical"


class ExecutorIntegrityError(ValueError):
    """Canonical input violates a fail-closed integrity invariant."""


@dataclass(frozen=True, slots=True)
class MinuteBar:
    """A complete, adjusted, left-labeled one-minute bar."""

    security_id: str
    symbol: str
    session: date
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    feed: str = "sip"
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-manifest-v001"


@dataclass(frozen=True, slots=True)
class NextBarOpen:
    """The only next-bar information visible to proposal construction."""

    security_id: str
    symbol: str
    session: date
    timestamp: datetime
    open: float
    halted: bool = False
    feed: str = "sip"
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-entry-open-v001"


@dataclass(frozen=True, slots=True)
class HaltInterval:
    start: datetime
    resume: datetime
    first_known_at: datetime
    source_record_identity: str = "synthetic-halt-v001"


@dataclass(frozen=True, slots=True)
class HistoricalClockVolume:
    session: date
    minute: str
    volume: float
    eligible: bool = True
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-clock-volume-v001"


@dataclass(frozen=True, slots=True)
class PremarketHistory:
    session: date
    dollar_volume: float
    complete: bool = True
    halted: bool = False
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-premarket-history-v001"


@dataclass(frozen=True, slots=True)
class LiquidityHistory:
    session: date
    regular_dollar_volume: float
    complete_session: bool = True
    early_close: bool = False
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-liquidity-history-v001"


@dataclass(frozen=True, slots=True)
class PriorClose:
    prior_session: date
    official_close: float
    adjusted_prior_close: float
    adjustment_identity: str = "synthetic-adjustment-v001"
    source_manifest_identity: str = "synthetic-prior-close-v001"


@dataclass(frozen=True, slots=True)
class EvaluationInput:
    """Already-normalized information available at one exact decision cutoff."""

    symbol_bars: tuple[MinuteBar, ...]
    next_bar: NextBarOpen | None
    scheduled_open: datetime
    scheduled_close: datetime
    decision_cutoff: datetime
    premarket_bars: tuple[MinuteBar, ...] = ()
    spy_bars: tuple[MinuteBar, ...] = ()
    same_clock_history: tuple[HistoricalClockVolume, ...] = ()
    premarket_history: tuple[PremarketHistory, ...] = ()
    liquidity_history: tuple[LiquidityHistory, ...] = ()
    prior_close: PriorClose | None = None
    halts: tuple[HaltInterval, ...] = ()
    spy_halts: tuple[HaltInterval, ...] = ()
    prior_strategy_entries: tuple[tuple[str, datetime], ...] = ()
    halt_coverage_complete: bool = True
    spy_halt_coverage_complete: bool = True
    halt_manifest_identity: str = "synthetic-halt-manifest-v001"
    spy_halt_manifest_identity: str = "synthetic-spy-halt-manifest-v001"
    corporate_action_coverage_complete: bool = True
    corporate_action_lineage_valid: bool = True
    corporate_action_manifest_identity: str = "synthetic-action-manifest-v001"
    calendar_identity: str = "synthetic-xnys-calendar-v001"


@dataclass(frozen=True, slots=True)
class StrategyProposal:
    protocol_identity: str
    strategy_id: str
    strategy_identity: str
    executor_version: str
    executor_identity: str
    symbol: str
    session: str
    signal_timestamp: str
    intended_entry_timestamp: str
    direction: str
    entry_rule: str
    raw_entry_open: float
    cost_adjusted_entry: float
    stop: float
    target: float
    timeout_complete_bars: int
    session_liquidation_rule: str
    stop_target_precedence: str
    gap_through_rule: str
    invalidation_rules: tuple[str, ...]
    indicator_snapshots: tuple[tuple[str, float | str], ...]
    evidence_class: str
    friction_basis_points_per_side: int
    commission_per_share_per_order: float
    minimum_commission_per_order: float
    risk_budget_usd: float
    initial_capital_usd: float
    maximum_gross_exposure_fraction: float
    maximum_concurrent_positions: int
    daily_new_entry_loss_stop_fraction: float
    proposal_identity: str

    def canonical_bytes(self) -> bytes:
        return canonical_json(asdict(self))


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    strategy_id: str
    decision_timestamp: str
    status: str
    reason_codes: tuple[str, ...]
    proposal: StrategyProposal | None = None

    def canonical_bytes(self) -> bytes:
        return canonical_json(asdict(self))


PROTOCOL_CONTRACT: Mapping[str, object] = MappingProxyType(
    {
        "schema": "aml.professional-strategy-executors.protocol.v001",
        "version": EXECUTOR_PROTOCOL_VERSION,
        "input": "complete_left_labeled_bars_plus_next_bar_open_only",
        "output": "immutable_auditable_strategy_proposal_or_fail_closed_decision",
        "evidence": EVIDENCE_CLASS,
        "empirical_authorized": False,
    }
)
EXECUTOR_PROTOCOL_IDENTITY = canonical_hash(dict(PROTOCOL_CONTRACT))


def proposal_identity(payload: Mapping[str, object]) -> str:
    """Return the complete deterministic identity of a proposal payload."""

    return canonical_hash(payload)
