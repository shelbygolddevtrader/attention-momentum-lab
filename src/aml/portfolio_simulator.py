"""Deterministic, research-only multi-strategy portfolio simulation.

This module is additive: the established single-strategy simulator remains the
execution engine for existing workflows.  Strategy proposals are admitted here
under fixed virtual allocations and shared portfolio risk limits.  No brokerage
or live-order behavior is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from numbers import Integral, Real
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


class Direction(str, Enum):
    """Supported proposal directions."""

    LONG = "long"
    SHORT = "short"


class LevelKind(str, Enum):
    """How a proposed stop or target is expressed."""

    FRACTION_FROM_ENTRY = "fraction_from_entry"
    ABSOLUTE_PRICE = "absolute_price"


class DuplicateSignalPolicy(str, Enum):
    """Portfolio treatment of overlapping related proposals."""

    ALLOW = "allow"
    REJECT_EXACT = "reject_exact"
    REJECT_SAME_SYMBOL_DIRECTION = "reject_same_symbol_direction"
    REJECT_SAME_SYMBOL = "reject_same_symbol"


def _finite_number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    if positive and normalized <= 0:
        raise ValueError(f"{name} must be positive")
    return normalized


@dataclass(frozen=True)
class PriceLevel:
    """A positive absolute price or positive fraction from the eventual fill."""

    kind: LevelKind
    value: float

    def __post_init__(self) -> None:
        try:
            kind = LevelKind(self.kind)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported price-level kind") from exc
        value = _finite_number(self.value, "Price-level value", positive=True)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "value", value)
        if kind is LevelKind.FRACTION_FROM_ENTRY and value >= 1:
            raise ValueError("Fractional price levels must be less than one")

    @classmethod
    def fraction(cls, value: float) -> PriceLevel:
        """Construct a level as a fraction away from the eventual fill."""

        return cls(LevelKind.FRACTION_FROM_ENTRY, value)

    @classmethod
    def absolute(cls, value: float) -> PriceLevel:
        """Construct a level as an absolute price."""

        return cls(LevelKind.ABSOLUTE_PRICE, value)

    def resolve(self, entry: float, direction: Direction, *, is_stop: bool) -> float:
        """Resolve this level without reading any future bar."""

        if self.kind is LevelKind.ABSOLUTE_PRICE:
            return self.value
        sign = -1 if (direction is Direction.LONG) == is_stop else 1
        return entry * (1 + sign * self.value)


def _aware_timestamp(value: Any, name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a valid timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return timestamp.as_unit("ns")


def _freeze_provenance(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("Provenance keys must be non-empty strings")
            frozen[key] = _freeze_provenance(item)
        return MappingProxyType(dict(sorted(frozen.items())))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_provenance(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Provenance numbers must be finite")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"Provenance value is not deterministically serializable: {type(value).__name__}")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@dataclass(frozen=True)
class StrategyProposal:
    """Immutable strategy intent supplied to the shared portfolio simulator.

    ``intended_entry_price`` is optional point-in-time intent metadata. Historical
    fills always use the first observed bar open at or after
    ``intended_entry_timestamp``; the optional price never overrides market data.
    Stops and targets can be absolute prices or fractions from that eventual fill.
    """

    strategy_identifier: str
    strategy_version: str
    symbol: str
    signal_timestamp: pd.Timestamp
    direction: Direction
    score_or_confidence: float
    intended_entry_timestamp: pd.Timestamp
    intended_entry_price: float | None
    stop: PriceLevel
    target: PriceLevel
    maximum_holding_minutes: int
    invalidation_reason: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    proposal_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("strategy_identifier", "strategy_version", "symbol"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        object.__setattr__(self, "strategy_identifier", self.strategy_identifier.strip())
        object.__setattr__(self, "strategy_version", self.strategy_version.strip())
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        signal = _aware_timestamp(self.signal_timestamp, "signal_timestamp")
        intended = _aware_timestamp(self.intended_entry_timestamp, "intended_entry_timestamp")
        if intended < signal:
            raise ValueError("intended_entry_timestamp cannot precede the signal")
        object.__setattr__(self, "signal_timestamp", signal)
        object.__setattr__(self, "intended_entry_timestamp", intended)
        try:
            direction = Direction(self.direction)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported proposal direction") from exc
        object.__setattr__(self, "direction", direction)
        score = _finite_number(self.score_or_confidence, "score_or_confidence")
        object.__setattr__(self, "score_or_confidence", score)
        if self.intended_entry_price is not None:
            intended_price = _finite_number(
                self.intended_entry_price, "intended_entry_price", positive=True
            )
            object.__setattr__(self, "intended_entry_price", intended_price)
        if not isinstance(self.stop, PriceLevel) or not isinstance(self.target, PriceLevel):
            raise ValueError("stop and target must be PriceLevel instances")
        if (
            isinstance(self.maximum_holding_minutes, bool)
            or not isinstance(self.maximum_holding_minutes, Integral)
            or self.maximum_holding_minutes < 1
        ):
            raise ValueError("maximum_holding_minutes must be a positive integer")
        object.__setattr__(self, "maximum_holding_minutes", int(self.maximum_holding_minutes))
        if self.invalidation_reason is not None:
            if not isinstance(self.invalidation_reason, str) or not self.invalidation_reason.strip():
                raise ValueError("invalidation_reason must be non-empty when supplied")
            object.__setattr__(self, "invalidation_reason", self.invalidation_reason.strip())
        if not isinstance(self.provenance, Mapping):
            raise ValueError("proposal provenance must be a mapping")
        provenance = _freeze_provenance(dict(self.provenance))
        if not provenance:
            raise ValueError("proposal provenance is required")
        object.__setattr__(self, "provenance", provenance)
        payload = {
            "strategy_identifier": self.strategy_identifier,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "signal_timestamp": signal.isoformat(),
            "direction": self.direction.value,
            "score_or_confidence": self.score_or_confidence,
            "intended_entry_timestamp": intended.isoformat(),
            "intended_entry_price": self.intended_entry_price,
            "stop": {"kind": self.stop.kind.value, "value": self.stop.value},
            "target": {"kind": self.target.kind.value, "value": self.target.value},
            "maximum_holding_minutes": self.maximum_holding_minutes,
            "invalidation_reason": self.invalidation_reason,
            "provenance": _jsonable(provenance),
        }
        encoded = _canonical_json(payload).encode()
        object.__setattr__(self, "proposal_id", hashlib.sha256(encoded).hexdigest()[:20])

    @property
    def strategy_key(self) -> tuple[str, str]:
        """Return the independently versioned strategy identity."""

        return self.strategy_identifier, self.strategy_version


@dataclass(frozen=True)
class StrategyAllocation:
    """Fixed capital allocation for one independently versioned strategy."""

    strategy_identifier: str
    strategy_version: str
    allocated_capital: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.strategy_identifier, str)
            or not self.strategy_identifier.strip()
            or not isinstance(self.strategy_version, str)
            or not self.strategy_version.strip()
        ):
            raise ValueError("Strategy allocation identity must be non-empty")
        object.__setattr__(self, "strategy_identifier", self.strategy_identifier.strip())
        object.__setattr__(self, "strategy_version", self.strategy_version.strip())
        object.__setattr__(
            self, "allocated_capital",
            _finite_number(self.allocated_capital, "allocated_capital", positive=True),
        )

    @property
    def strategy_key(self) -> tuple[str, str]:
        """Return the independently versioned strategy identity."""

        return self.strategy_identifier, self.strategy_version


@dataclass(frozen=True)
class PortfolioConfig:
    """Fixed-allocation shared risk configuration.

    ``allocation_policy`` is an explicit future extension hook. Only ``fixed`` is
    accepted in this foundation; adaptive allocation is intentionally absent.
    """

    total_capital: float
    strategy_allocations: tuple[StrategyAllocation, ...]
    maximum_position_risk_fraction: float = 0.005
    maximum_concurrent_positions: int = 5
    maximum_symbol_concentration_fraction: float = 0.50
    maximum_strategy_concentration_fraction: float = 0.50
    daily_loss_limit_fraction: float = 0.05
    slippage_fraction: float = 0.001
    maximum_entry_delay_minutes: int = 5
    duplicate_signal_policy: DuplicateSignalPolicy = DuplicateSignalPolicy.REJECT_EXACT
    allocation_policy: str = "fixed"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "total_capital",
            _finite_number(self.total_capital, "total_capital", positive=True),
        )
        try:
            allocations = tuple(self.strategy_allocations)
        except TypeError as exc:
            raise ValueError("strategy_allocations must be an iterable") from exc
        object.__setattr__(self, "strategy_allocations", allocations)
        if not allocations:
            raise ValueError("At least one fixed strategy allocation is required")
        if any(not isinstance(item, StrategyAllocation) for item in allocations):
            raise ValueError("strategy_allocations must contain StrategyAllocation values")
        keys = [allocation.strategy_key for allocation in allocations]
        if len(keys) != len(set(keys)):
            raise ValueError("Strategy allocations must be unique by identifier and version")
        if sum(item.allocated_capital for item in allocations) > self.total_capital + 1e-9:
            raise ValueError("Fixed strategy allocations cannot exceed total capital")
        for name in (
            "maximum_position_risk_fraction",
            "maximum_symbol_concentration_fraction",
            "maximum_strategy_concentration_fraction",
            "daily_loss_limit_fraction",
        ):
            value = _finite_number(getattr(self, name), name, positive=True)
            if value > 1:
                raise ValueError("Portfolio risk fractions must be within (0, 1]")
            object.__setattr__(self, name, value)
        if (
            isinstance(self.maximum_concurrent_positions, bool)
            or not isinstance(self.maximum_concurrent_positions, Integral)
            or self.maximum_concurrent_positions < 1
        ):
            raise ValueError("maximum_concurrent_positions must be positive")
        object.__setattr__(self, "maximum_concurrent_positions", int(self.maximum_concurrent_positions))
        slippage = _finite_number(self.slippage_fraction, "slippage_fraction")
        if not 0 <= slippage < 1:
            raise ValueError("slippage_fraction must be within [0, 1)")
        object.__setattr__(self, "slippage_fraction", slippage)
        if (
            isinstance(self.maximum_entry_delay_minutes, bool)
            or not isinstance(self.maximum_entry_delay_minutes, Integral)
            or self.maximum_entry_delay_minutes < 0
        ):
            raise ValueError("maximum_entry_delay_minutes cannot be negative")
        object.__setattr__(self, "maximum_entry_delay_minutes", int(self.maximum_entry_delay_minutes))
        try:
            duplicate_policy = DuplicateSignalPolicy(self.duplicate_signal_policy)
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported duplicate_signal_policy") from exc
        object.__setattr__(self, "duplicate_signal_policy", duplicate_policy)
        if self.allocation_policy != "fixed":
            raise ValueError("Only fixed allocation is implemented")


@dataclass(frozen=True)
class PortfolioSimulationResult:
    """Auditable portfolio decisions, closed trades, ledgers, and reconciliation."""

    proposal_audit: pd.DataFrame
    trades: pd.DataFrame
    strategy_ledgers: pd.DataFrame
    portfolio_summary: Mapping[str, float | int]


@dataclass
class _LedgerState:
    allocated: float
    realized: float = 0.0
    open_capital: float = 0.0
    unrealized: float = 0.0
    trade_count: int = 0
    wins: int = 0
    losses: int = 0
    peak_equity: float = 0.0
    maximum_drawdown: float = 0.0

    def __post_init__(self) -> None:
        self.peak_equity = self.allocated

    @property
    def available(self) -> float:
        return max(self.allocated + self.realized - self.open_capital, 0.0)

    def close(self, net_pnl: float) -> tuple[float, float]:
        before = self.allocated + self.realized
        self.realized += net_pnl
        self.trade_count += 1
        self.wins += int(net_pnl > 0)
        self.losses += int(net_pnl < 0)
        after = self.allocated + self.realized
        self.peak_equity = max(self.peak_equity, after)
        drawdown = after / self.peak_equity - 1 if self.peak_equity else 0.0
        self.maximum_drawdown = min(self.maximum_drawdown, drawdown)
        return before, after


@dataclass(frozen=True)
class _TradePath:
    proposal: StrategyProposal
    actual_entry_timestamp: pd.Timestamp
    entry_delay_minutes: int
    raw_entry_price: float
    adjusted_entry_price: float
    stop_price: float
    target_price: float
    exit_timestamp: pd.Timestamp
    exit_reason: str
    raw_exit_price: float
    adjusted_exit_price: float
    risk_per_share: float


@dataclass
class _OpenPosition:
    path: _TradePath
    quantity: int
    capital_used: float
    position_risk: float


AUDIT_COLUMNS = [
    "proposal_id", "strategy_identifier", "strategy_version", "symbol",
    "signal_timestamp", "direction", "score_or_confidence",
    "intended_entry_timestamp", "decision_timestamp", "status", "reason",
    "invalidation_reason",
    "actual_entry_timestamp", "quantity", "capital_used", "position_risk",
    "provenance_json",
]

TRADE_COLUMNS = [
    "proposal_id", "strategy_identifier", "strategy_version", "symbol",
    "signal_timestamp", "direction", "score_or_confidence",
    "intended_entry_timestamp", "actual_entry_timestamp", "entry_delay_minutes",
    "intended_entry_price", "raw_entry_price", "adjusted_entry_price", "quantity",
    "capital_used", "position_risk", "stop_price", "target_price",
    "maximum_holding_minutes", "exit_timestamp", "exit_reason", "raw_exit_price",
    "adjusted_exit_price", "gross_pnl", "net_pnl", "return_on_capital",
    "portfolio_equity_before_exit", "portfolio_equity_after_exit",
    "strategy_equity_before_exit", "strategy_equity_after_exit", "provenance_json",
]

LEDGER_COLUMNS = [
    "strategy_identifier", "strategy_version", "allocated_capital",
    "available_capital", "realized_pnl", "unrealized_pnl", "trade_count",
    "wins", "losses", "maximum_drawdown",
]


def _prepare_bars(bars_by_symbol: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if not isinstance(bars_by_symbol, Mapping):
        raise ValueError("bars_by_symbol must be a mapping")
    prepared: dict[str, pd.DataFrame] = {}
    required = {"timestamp", "open", "high", "low", "close"}
    items: list[tuple[str, pd.DataFrame]] = []
    for raw_symbol, caller_frame in bars_by_symbol.items():
        if not isinstance(raw_symbol, str) or not raw_symbol.strip():
            raise ValueError("Bar symbols must be non-empty strings")
        if not isinstance(caller_frame, pd.DataFrame):
            raise ValueError(f"{raw_symbol} bars must be a DataFrame")
        items.append((raw_symbol, caller_frame))
    for raw_symbol, caller_frame in sorted(items, key=lambda item: item[0]):
        symbol = raw_symbol.strip().upper()
        if not symbol or symbol in prepared:
            raise ValueError("Bar symbols must be unique and non-empty")
        if missing := required.difference(caller_frame.columns):
            raise ValueError(f"Missing {symbol} bar columns: {', '.join(sorted(missing))}")
        frame = caller_frame.copy(deep=True)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        if frame["timestamp"].dt.tz is None:
            raise ValueError(f"{symbol} bar timestamps must be timezone-aware")
        if not frame["timestamp"].is_monotonic_increasing:
            raise ValueError(f"{symbol} bars must be chronological")
        if frame["timestamp"].duplicated().any():
            raise ValueError(f"{symbol} bar timestamps must be unique")
        prices = frame[["open", "high", "low", "close"]]
        if prices.isna().any().any() or not np.isfinite(prices.to_numpy()).all():
            raise ValueError(f"{symbol} bar prices must be finite and non-missing")
        if (prices <= 0).any().any():
            raise ValueError(f"{symbol} bar prices must be positive")
        malformed_range = (
            prices["high"].lt(prices[["open", "close"]].max(axis=1))
            | prices["low"].gt(prices[["open", "close"]].min(axis=1))
            | prices["high"].lt(prices["low"])
        )
        if malformed_range.any():
            raise ValueError(f"{symbol} bars contain malformed OHLC ranges")
        if "symbol" in frame and not frame["symbol"].astype(str).str.upper().eq(symbol).all():
            raise ValueError(f"{symbol} bars contain a mismatched symbol")
        prepared[symbol] = frame.reset_index(drop=True)
    return prepared


def _trade_path(
    proposal: StrategyProposal,
    bars: pd.DataFrame,
    config: PortfolioConfig,
) -> tuple[_TradePath | None, str | None]:
    bar_timezone = bars["timestamp"].dt.tz
    intended_local = proposal.intended_entry_timestamp.tz_convert(bar_timezone)
    same_day = bars["timestamp"].dt.date.eq(intended_local.date())
    candidates = bars.index[same_day & (bars["timestamp"] >= intended_local)]
    if candidates.empty:
        return None, "incomplete_entry_data"
    entry_index = int(candidates[0])
    entry_time = pd.Timestamp(bars.at[entry_index, "timestamp"]).as_unit("ns")
    delay = int((entry_time - intended_local).total_seconds() // 60)
    if delay > config.maximum_entry_delay_minutes:
        return None, "entry_delay_exceeded"
    raw_entry = float(bars.at[entry_index, "open"])
    slip_sign = 1 if proposal.direction is Direction.LONG else -1
    adjusted_entry = raw_entry * (1 + slip_sign * config.slippage_fraction)
    stop = proposal.stop.resolve(adjusted_entry, proposal.direction, is_stop=True)
    target = proposal.target.resolve(adjusted_entry, proposal.direction, is_stop=False)
    levels_valid = (
        stop < adjusted_entry < target
        if proposal.direction is Direction.LONG
        else target < adjusted_entry < stop
    )
    if not levels_valid:
        return None, "invalid_stop_target"

    deadline = entry_time + pd.Timedelta(proposal.maximum_holding_minutes, unit="min")
    session_indices = bars.index[same_day & (bars.index >= entry_index)]
    final_index = int(session_indices[-1])
    exit_index = final_index
    reason = "session_end"
    raw_exit = float(bars.at[final_index, "close"])
    for index in session_indices:
        row = bars.loc[index]
        timestamp = pd.Timestamp(row["timestamp"])
        if timestamp > deadline:
            exit_index, reason, raw_exit = int(index), "time_limit", float(row["open"])
            break
        if proposal.direction is Direction.LONG:
            if row["low"] <= stop:
                exit_index, reason, raw_exit = int(index), "stop", min(float(row["open"]), stop)
                break
            if row["high"] >= target:
                exit_index, reason, raw_exit = int(index), "target", target
                break
        else:
            if row["high"] >= stop:
                exit_index, reason, raw_exit = int(index), "stop", max(float(row["open"]), stop)
                break
            if row["low"] <= target:
                exit_index, reason, raw_exit = int(index), "target", target
                break
        if timestamp == deadline:
            exit_index, reason, raw_exit = int(index), "time_limit", float(row["close"])
            break
    exit_time = pd.Timestamp(bars.at[exit_index, "timestamp"]).as_unit("ns")
    adjusted_exit = raw_exit * (1 - slip_sign * config.slippage_fraction)
    return _TradePath(
        proposal, entry_time, delay, raw_entry, adjusted_entry, stop, target,
        exit_time, reason, raw_exit, adjusted_exit, abs(adjusted_entry - stop),
    ), None


def _audit_record(
    proposal: StrategyProposal,
    status: str,
    reason: str,
    *,
    decision_timestamp: pd.Timestamp | None = None,
    path: _TradePath | None = None,
    quantity: int | None = None,
    capital_used: float | None = None,
    position_risk: float | None = None,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id,
        "strategy_identifier": proposal.strategy_identifier,
        "strategy_version": proposal.strategy_version,
        "symbol": proposal.symbol,
        "signal_timestamp": proposal.signal_timestamp,
        "direction": proposal.direction.value,
        "score_or_confidence": proposal.score_or_confidence,
        "intended_entry_timestamp": proposal.intended_entry_timestamp,
        "decision_timestamp": decision_timestamp or proposal.intended_entry_timestamp,
        "status": status,
        "reason": reason,
        "invalidation_reason": proposal.invalidation_reason,
        "actual_entry_timestamp": path.actual_entry_timestamp if path else pd.NaT,
        "quantity": quantity,
        "capital_used": capital_used,
        "position_risk": position_risk,
        "provenance_json": _canonical_json(proposal.provenance),
    }


def _gross_and_net(position: _OpenPosition) -> tuple[float, float]:
    path = position.path
    if path.proposal.direction is Direction.LONG:
        gross = (path.raw_exit_price - path.raw_entry_price) * position.quantity
        net = (path.adjusted_exit_price - path.adjusted_entry_price) * position.quantity
    else:
        gross = (path.raw_entry_price - path.raw_exit_price) * position.quantity
        net = (path.adjusted_entry_price - path.adjusted_exit_price) * position.quantity
    return gross, net


def simulate_portfolio(
    proposals: Sequence[StrategyProposal],
    bars_by_symbol: Mapping[str, pd.DataFrame],
    config: PortfolioConfig,
) -> PortfolioSimulationResult:
    """Simulate strategy proposals under fixed allocations and shared risk.

    Entries are ordered by actual fill time, signal time, versioned strategy ID,
    symbol, direction, and deterministic proposal hash. Positions exiting at an
    entry timestamp release their capital before proposals at that timestamp are
    evaluated. Stop checks precede target checks on the same bar, matching the
    conservative legacy convention.
    """

    if not isinstance(config, PortfolioConfig):
        raise ValueError("config must be a PortfolioConfig")
    if isinstance(proposals, (str, bytes)) or not isinstance(proposals, Sequence):
        raise ValueError("proposals must be a sequence of StrategyProposal values")
    if any(not isinstance(proposal, StrategyProposal) for proposal in proposals):
        raise ValueError("proposals must contain StrategyProposal values")
    bars = _prepare_bars(bars_by_symbol)
    allocation_map = {item.strategy_key: item for item in config.strategy_allocations}
    ledgers = {
        key: _LedgerState(allocation.allocated_capital)
        for key, allocation in allocation_map.items()
    }
    audit_records: list[dict[str, Any]] = []
    paths: list[_TradePath] = []
    for proposal in proposals:
        if proposal.invalidation_reason:
            audit_records.append(
                _audit_record(proposal, "rejected", "strategy_invalidated")
            )
            continue
        if proposal.strategy_key not in allocation_map:
            audit_records.append(
                _audit_record(proposal, "rejected", "strategy_allocation_missing")
            )
            continue
        symbol_bars = bars.get(proposal.symbol)
        if symbol_bars is None:
            audit_records.append(_audit_record(proposal, "rejected", "symbol_data_missing"))
            continue
        path, error = _trade_path(proposal, symbol_bars, config)
        if error:
            audit_records.append(_audit_record(proposal, "rejected", error))
            continue
        paths.append(path)

    paths.sort(key=lambda path: (
        path.actual_entry_timestamp,
        path.proposal.signal_timestamp,
        path.proposal.strategy_identifier,
        path.proposal.strategy_version,
        path.proposal.symbol,
        path.proposal.direction.value,
        path.proposal.proposal_id,
    ))
    open_positions: list[_OpenPosition] = []
    trade_records: list[dict[str, Any]] = []
    portfolio_realized = 0.0
    portfolio_peak = config.total_capital
    portfolio_maximum_drawdown = 0.0
    daily_realized: dict[object, float] = {}
    seen_exact: set[tuple[Any, ...]] = set()

    def close_position(position: _OpenPosition) -> None:
        nonlocal portfolio_realized, portfolio_peak, portfolio_maximum_drawdown
        path = position.path
        proposal = path.proposal
        ledger = ledgers[proposal.strategy_key]
        gross, net = _gross_and_net(position)
        portfolio_before = config.total_capital + portfolio_realized
        strategy_before, strategy_after = ledger.close(net)
        ledger.open_capital -= position.capital_used
        portfolio_realized += net
        portfolio_after = config.total_capital + portfolio_realized
        portfolio_peak = max(portfolio_peak, portfolio_after)
        portfolio_drawdown = portfolio_after / portfolio_peak - 1
        portfolio_maximum_drawdown = min(portfolio_maximum_drawdown, portfolio_drawdown)
        day = path.exit_timestamp.date()
        daily_realized[day] = daily_realized.get(day, 0.0) + net
        trade_records.append({
            "proposal_id": proposal.proposal_id,
            "strategy_identifier": proposal.strategy_identifier,
            "strategy_version": proposal.strategy_version,
            "symbol": proposal.symbol,
            "signal_timestamp": proposal.signal_timestamp,
            "direction": proposal.direction.value,
            "score_or_confidence": proposal.score_or_confidence,
            "intended_entry_timestamp": proposal.intended_entry_timestamp,
            "actual_entry_timestamp": path.actual_entry_timestamp,
            "entry_delay_minutes": path.entry_delay_minutes,
            "intended_entry_price": proposal.intended_entry_price,
            "raw_entry_price": path.raw_entry_price,
            "adjusted_entry_price": path.adjusted_entry_price,
            "quantity": position.quantity,
            "capital_used": position.capital_used,
            "position_risk": position.position_risk,
            "stop_price": path.stop_price,
            "target_price": path.target_price,
            "maximum_holding_minutes": proposal.maximum_holding_minutes,
            "exit_timestamp": path.exit_timestamp,
            "exit_reason": path.exit_reason,
            "raw_exit_price": path.raw_exit_price,
            "adjusted_exit_price": path.adjusted_exit_price,
            "gross_pnl": gross,
            "net_pnl": net,
            "return_on_capital": net / position.capital_used,
            "portfolio_equity_before_exit": portfolio_before,
            "portfolio_equity_after_exit": portfolio_after,
            "strategy_equity_before_exit": strategy_before,
            "strategy_equity_after_exit": strategy_after,
            "provenance_json": _canonical_json(proposal.provenance),
        })

    for path in paths:
        due = sorted(
            (position for position in open_positions if position.path.exit_timestamp <= path.actual_entry_timestamp),
            key=lambda position: (position.path.exit_timestamp, position.path.proposal.proposal_id),
        )
        for position in due:
            close_position(position)
            open_positions.remove(position)

        proposal = path.proposal
        day = path.actual_entry_timestamp.date()
        rejection: str | None = None
        # Exact execution intent deliberately ignores score and provenance. Two
        # proposals that resolve to the same fill and levels cannot evade the
        # duplicate guard through metadata or sub-minute signal differences.
        exact_key = (
            proposal.symbol, proposal.direction, path.actual_entry_timestamp,
            path.stop_price, path.target_price, proposal.maximum_holding_minutes,
        )
        if config.duplicate_signal_policy is DuplicateSignalPolicy.REJECT_EXACT and exact_key in seen_exact:
            rejection = "duplicate_signal"
        elif config.duplicate_signal_policy is DuplicateSignalPolicy.REJECT_SAME_SYMBOL_DIRECTION and any(
            position.path.proposal.symbol == proposal.symbol
            and position.path.proposal.direction is proposal.direction
            for position in open_positions
        ):
            rejection = "correlated_signal"
        elif config.duplicate_signal_policy is DuplicateSignalPolicy.REJECT_SAME_SYMBOL and any(
            position.path.proposal.symbol == proposal.symbol
            for position in open_positions
        ):
            rejection = "symbol_conflict"
        elif daily_realized.get(day, 0.0) <= -config.total_capital * config.daily_loss_limit_fraction:
            rejection = "daily_loss_limit"
        elif len(open_positions) >= config.maximum_concurrent_positions:
            rejection = "maximum_concurrent_positions"

        ledger = ledgers[proposal.strategy_key]
        portfolio_open = sum(position.capital_used for position in open_positions)
        strategy_open = sum(
            position.capital_used
            for position in open_positions
            if position.path.proposal.strategy_key == proposal.strategy_key
        )
        symbol_open = sum(
            position.capital_used
            for position in open_positions
            if position.path.proposal.symbol == proposal.symbol
        )
        portfolio_available = config.total_capital + portfolio_realized - portfolio_open
        symbol_capacity = config.total_capital * config.maximum_symbol_concentration_fraction - symbol_open
        strategy_capacity = config.total_capital * config.maximum_strategy_concentration_fraction - strategy_open
        maximum_risk = config.total_capital * config.maximum_position_risk_fraction
        entry = path.adjusted_entry_price
        if rejection is None:
            if path.risk_per_share > maximum_risk:
                rejection = "maximum_position_risk"
            elif portfolio_available < entry:
                rejection = "insufficient_portfolio_capital"
            elif ledger.available < entry:
                rejection = "insufficient_strategy_capital"
            elif symbol_capacity < entry:
                rejection = "symbol_concentration_limit"
            elif strategy_capacity < entry:
                rejection = "strategy_concentration_limit"
        if rejection:
            audit_records.append(
                _audit_record(
                    proposal, "rejected", rejection,
                    decision_timestamp=path.actual_entry_timestamp, path=path,
                )
            )
            continue

        quantity = min(
            math.floor(maximum_risk / path.risk_per_share),
            math.floor(ledger.available / entry),
            math.floor(portfolio_available / entry),
            math.floor(symbol_capacity / entry),
            math.floor(strategy_capacity / entry),
        )
        if quantity < 1:
            audit_records.append(
                _audit_record(
                    proposal, "rejected", "insufficient_portfolio_capital",
                    decision_timestamp=path.actual_entry_timestamp, path=path,
                )
            )
            continue
        capital_used = entry * quantity
        position_risk = path.risk_per_share * quantity
        position = _OpenPosition(path, quantity, capital_used, position_risk)
        open_positions.append(position)
        ledger.open_capital += capital_used
        seen_exact.add(exact_key)
        audit_records.append(
            _audit_record(
                proposal, "accepted", "accepted",
                decision_timestamp=path.actual_entry_timestamp, path=path,
                quantity=quantity, capital_used=capital_used, position_risk=position_risk,
            )
        )

    for position in sorted(
        open_positions,
        key=lambda item: (item.path.exit_timestamp, item.path.proposal.proposal_id),
    ):
        close_position(position)

    audit = pd.DataFrame.from_records(audit_records, columns=AUDIT_COLUMNS)
    if not audit.empty:
        audit = audit.sort_values(
            ["decision_timestamp", "strategy_identifier", "strategy_version", "symbol", "proposal_id"],
            kind="stable",
        ).reset_index(drop=True)
    trades = pd.DataFrame.from_records(trade_records, columns=TRADE_COLUMNS)
    if not trades.empty:
        trades = trades.sort_values(
            ["exit_timestamp", "strategy_identifier", "strategy_version", "symbol", "proposal_id"],
            kind="stable",
        ).reset_index(drop=True)
    ledger_records = [{
        "strategy_identifier": key[0],
        "strategy_version": key[1],
        "allocated_capital": state.allocated,
        "available_capital": state.available,
        "realized_pnl": state.realized,
        "unrealized_pnl": state.unrealized,
        "trade_count": state.trade_count,
        "wins": state.wins,
        "losses": state.losses,
        "maximum_drawdown": state.maximum_drawdown,
    } for key, state in sorted(ledgers.items())]
    strategy_ledgers = pd.DataFrame.from_records(ledger_records, columns=LEDGER_COLUMNS)
    pnl = trades["net_pnl"] if not trades.empty else pd.Series(dtype=float)
    summary: dict[str, float | int] = {
        "total_capital": config.total_capital,
        "available_capital": config.total_capital + portfolio_realized,
        "realized_pnl": portfolio_realized,
        "unrealized_pnl": 0.0,
        "ending_equity": config.total_capital + portfolio_realized,
        "trade_count": len(trades),
        "wins": int((pnl > 0).sum()),
        "losses": int((pnl < 0).sum()),
        "maximum_drawdown": portfolio_maximum_drawdown,
        "accepted_proposal_count": int(audit["status"].eq("accepted").sum()),
        "rejected_proposal_count": int(audit["status"].eq("rejected").sum()),
    }
    return PortfolioSimulationResult(
        audit, trades, strategy_ledgers, MappingProxyType(summary)
    )
