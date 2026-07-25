"""Conservative, non-overlapping historical long-share simulation."""

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from aml.thresholds import (
    CANDIDATE_SCORE_THRESHOLD, ELIGIBLE_SCORE_THRESHOLD, UNSET_THRESHOLD,
    resolve_deprecated_threshold_alias,
)
from aml.market_halts import (
    CompletenessMode, HaltSchedule, completeness_metadata, expected_minutes,
)


@dataclass(frozen=True, init=False)
class SimulationConfig:
    strategy_version: str = "0.1.1"
    candidate_score_threshold: int = CANDIDATE_SCORE_THRESHOLD
    eligible_score_threshold: int = ELIGIBLE_SCORE_THRESHOLD
    starting_equity: float = 2_000.0
    risk_fraction: float = 0.005
    stop_fraction: float = 0.03
    target_fraction: float = 0.06
    entry_delay_minutes: int = 1
    maximum_entry_delay_minutes: int = 5
    maximum_holding_minutes: int = 30
    slippage_fraction: float = 0.001
    cooldown_minutes: int = 30

    def __init__(
        self, strategy_version="0.1.1",
        candidate_score_threshold=CANDIDATE_SCORE_THRESHOLD,
        eligible_score_threshold=UNSET_THRESHOLD,
        starting_equity=2_000.0, risk_fraction=0.005, stop_fraction=0.03,
        target_fraction=0.06, entry_delay_minutes=1,
        maximum_entry_delay_minutes=5, maximum_holding_minutes=30,
        slippage_fraction=0.001, cooldown_minutes=30, *,
        minimum_score=UNSET_THRESHOLD,
    ):
        """Build simulation config; ``minimum_score`` is a deprecated alias."""
        eligible = resolve_deprecated_threshold_alias(
            eligible_score_threshold, minimum_score, ELIGIBLE_SCORE_THRESHOLD,
            "eligible_score_threshold", "minimum_score",
        )
        values = locals()
        for name in (
            "strategy_version", "candidate_score_threshold", "starting_equity",
            "risk_fraction", "stop_fraction", "target_fraction",
            "entry_delay_minutes", "maximum_entry_delay_minutes",
            "maximum_holding_minutes", "slippage_fraction", "cooldown_minutes",
        ):
            object.__setattr__(self, name, values[name])
        object.__setattr__(self, "eligible_score_threshold", eligible)


TRADE_COLUMNS = [
    "symbol", "strategy_version", "signal_timestamp", "signal_score",
    "intended_entry_timestamp", "actual_entry_timestamp", "entry_delay_minutes",
    "raw_entry_price", "adjusted_entry_price", "quantity", "capital_used",
    "stop_price", "target_price", "exit_timestamp", "exit_reason",
    "raw_exit_price", "adjusted_exit_price", "gross_pnl", "net_pnl",
    "return_on_capital", "equity_before_trade", "equity_after_trade",
    "missing_minute_count", "complete_window", "risk_fraction",
    "entry_slippage_fraction", "exit_slippage_fraction", "stop_fraction",
    "target_fraction", "maximum_holding_minutes", "cooldown_minutes",
    "completeness_mode", "verified_halt_count",
    "verified_halt_minutes_excluded", "halt_data_path",
]


def _validate(signals: pd.DataFrame, bars: pd.DataFrame):
    signal_required = {"timestamp", "score"}
    bar_required = {"timestamp", "open", "high", "low", "close"}
    if missing := signal_required.difference(signals.columns):
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    if missing := bar_required.difference(bars.columns):
        raise ValueError(f"Missing bar columns: {', '.join(sorted(missing))}")
    for name, frame in (("Signals", signals), ("Bars", bars)):
        if not frame["timestamp"].is_monotonic_increasing:
            raise ValueError(f"{name} must be chronological")
        if frame["timestamp"].duplicated().any():
            raise ValueError(f"{name} timestamps must be unique")


def _prepare(signals: pd.DataFrame, bars: pd.DataFrame):
    signals = signals.copy()
    bars = bars.copy()
    signals["timestamp"] = pd.to_datetime(signals["timestamp"])
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    _validate(signals, bars)
    prices = bars[["open", "high", "low", "close"]]
    if prices.isna().any().any() or not np.isfinite(prices.to_numpy()).all():
        raise ValueError("Bar prices must be finite and non-missing")
    if (prices <= 0).any().any():
        raise ValueError("Bar prices must be positive")
    bar_dates = bars["timestamp"].dt.date.unique()
    if len(bar_dates) != 1:
        raise ValueError("Each simulation must contain exactly one trading session")
    if not signals.empty and not signals["timestamp"].dt.date.eq(bar_dates[0]).all():
        raise ValueError("Signals and bars must belong to the same trading session")
    return signals.reset_index(drop=True), bars.reset_index(drop=True)


def _exit_position(bars, entry_index, adjusted_entry, config):
    entry_time = bars.at[entry_index, "timestamp"]
    deadline = entry_time + pd.Timedelta(config.maximum_holding_minutes, unit="min")
    stop = adjusted_entry * (1 - config.stop_fraction)
    target = adjusted_entry * (1 + config.target_fraction)
    final_index = len(bars) - 1

    for index in range(entry_index, len(bars)):
        row = bars.iloc[index]
        timestamp = row["timestamp"]
        if timestamp > deadline:
            return index, "time_limit", float(row["open"]), stop, target
        if row["low"] <= stop:
            raw_exit = min(float(row["open"]), stop)
            return index, "stop", raw_exit, stop, target
        if row["high"] >= target:
            return index, "target", target, stop, target
        if timestamp == deadline:
            return index, "time_limit", float(row["close"]), stop, target
    return final_index, "session_end", float(bars.at[final_index, "close"]), stop, target


def simulate_trades(
    signals, bars, config=None,
    completeness_mode: str | CompletenessMode = CompletenessMode.STRICT,
    halt_schedule: HaltSchedule | None = None,
):
    """Simulate one long position at a time from point-in-time signal rows."""
    config = config or SimulationConfig()
    completeness_mode = CompletenessMode(completeness_mode)
    signals, bars = _prepare(signals, bars)
    # Execution is intentionally stricter than research-candidate selection.
    candidates = signals.loc[signals["score"] >= config.eligible_score_threshold]
    # Replays normally include this point-in-time strategy decision. When it is
    # supplied, preserve it as an additional execution guard.
    if "eligible" in signals.columns:
        candidates = candidates.loc[candidates["eligible"].fillna(False).astype(bool)]
    equity = config.starting_equity
    cooldown_until = None
    records = []

    for signal in candidates.itertuples(index=False):
        signal_time = pd.Timestamp(signal.timestamp).as_unit("ns")
        if cooldown_until is not None and signal_time < cooldown_until:
            continue
        intended_entry = signal_time + pd.Timedelta(config.entry_delay_minutes, unit="min")
        available = bars.index[bars["timestamp"] >= intended_entry]
        if available.empty:
            continue
        entry_index = int(available[0])
        entry_time = pd.Timestamp(bars.at[entry_index, "timestamp"]).as_unit("ns")
        delay = int((entry_time - signal_time).total_seconds() // 60)
        if delay > config.maximum_entry_delay_minutes:
            continue

        raw_entry = float(bars.at[entry_index, "open"])
        adjusted_entry = raw_entry * (1 + config.slippage_fraction)
        risk_budget = equity * config.risk_fraction
        risk_per_share = adjusted_entry * config.stop_fraction
        risk_quantity = math.floor(risk_budget / risk_per_share)
        cash_quantity = math.floor(equity / adjusted_entry)
        quantity = min(risk_quantity, cash_quantity)
        if quantity < 1:
            continue

        exit_index, reason, raw_exit, stop, target = _exit_position(
            bars, entry_index, adjusted_entry, config
        )
        exit_time = pd.Timestamp(bars.at[exit_index, "timestamp"]).as_unit("ns")
        adjusted_exit = raw_exit * (1 - config.slippage_fraction)
        capital_used = adjusted_entry * quantity
        gross_pnl = (raw_exit - raw_entry) * quantity
        net_pnl = (adjusted_exit - adjusted_entry) * quantity
        equity_before = equity
        equity += net_pnl

        raw_expected_during_trade = pd.date_range(
            entry_time + pd.Timedelta(1, unit="min"), exit_time, freq="min"
        )
        expected_during_trade = (
            expected_minutes(raw_expected_during_trade[0], raw_expected_during_trade[-1], completeness_mode, halt_schedule)
            if len(raw_expected_during_trade) else raw_expected_during_trade
        )
        observed_during_trade = pd.DatetimeIndex(
            bars.loc[(bars["timestamp"] > entry_time) & (bars["timestamp"] <= exit_time), "timestamp"]
        )
        deadline = entry_time + pd.Timedelta(config.maximum_holding_minutes, unit="min")
        raw_intended_window = pd.date_range(entry_time, deadline, freq="min")
        intended_window = expected_minutes(
            raw_intended_window[0], raw_intended_window[-1], completeness_mode, halt_schedule
        )
        observed_window = pd.DatetimeIndex(
            bars.loc[(bars["timestamp"] >= entry_time) & (bars["timestamp"] <= deadline), "timestamp"]
        )
        records.append({
            "symbol": getattr(signal, "symbol", bars.at[entry_index, "symbol"] if "symbol" in bars else ""),
            "strategy_version": config.strategy_version,
            "signal_timestamp": signal_time,
            "signal_score": int(signal.score),
            "intended_entry_timestamp": intended_entry,
            "actual_entry_timestamp": entry_time,
            "entry_delay_minutes": delay,
            "raw_entry_price": raw_entry,
            "adjusted_entry_price": adjusted_entry,
            "quantity": quantity,
            "capital_used": capital_used,
            "stop_price": stop,
            "target_price": target,
            "exit_timestamp": exit_time,
            "exit_reason": reason,
            "raw_exit_price": raw_exit,
            "adjusted_exit_price": adjusted_exit,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "return_on_capital": net_pnl / capital_used,
            "equity_before_trade": equity_before,
            "equity_after_trade": equity,
            "missing_minute_count": len(expected_during_trade.difference(observed_during_trade)),
            "complete_window": len(intended_window.difference(observed_window)) == 0,
            "risk_fraction": config.risk_fraction,
            "entry_slippage_fraction": config.slippage_fraction,
            "exit_slippage_fraction": config.slippage_fraction,
            "stop_fraction": config.stop_fraction,
            "target_fraction": config.target_fraction,
            "maximum_holding_minutes": config.maximum_holding_minutes,
            "cooldown_minutes": config.cooldown_minutes,
            **completeness_metadata(completeness_mode, halt_schedule, raw_intended_window),
        })
        cooldown_until = exit_time + pd.Timedelta(config.cooldown_minutes, unit="min")

    trades = pd.DataFrame.from_records(records, columns=TRADE_COLUMNS)
    return trades, summarize_trades(trades, config.starting_equity)


def summarize_trades(trades, starting_equity=2_000.0):
    pnl = trades["net_pnl"] if not trades.empty else pd.Series(dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    equity_curve = pd.Series([starting_equity, *trades.get("equity_after_trade", [])], dtype=float)
    drawdowns = equity_curve / equity_curve.cummax() - 1
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    ending_equity = float(equity_curve.iloc[-1])
    largest_winner = float(wins.max()) if not wins.empty else 0.0
    return {
        "number_of_trades": int(len(trades)),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": float(len(wins) / len(trades)) if len(trades) else 0.0,
        "average_win": float(wins.mean()) if not wins.empty else 0.0,
        "average_loss": float(losses.mean()) if not losses.empty else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0),
        "expectancy_per_trade": float(pnl.mean()) if len(trades) else 0.0,
        "total_return": ending_equity / starting_equity - 1,
        "ending_equity": ending_equity,
        "maximum_drawdown": float(drawdowns.min()),
        "largest_winner": largest_winner,
        "largest_loser": float(losses.min()) if not losses.empty else 0.0,
        "percentage_total_profit_largest_winner": (
            largest_winner / gross_profit * 100 if gross_profit else 0.0
        ),
    }
