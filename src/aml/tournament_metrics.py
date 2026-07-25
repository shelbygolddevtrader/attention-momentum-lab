"""Deterministic tournament metrics, cautions, and transparent research score."""

import math
from typing import Any

import numpy as np
import pandas as pd

from aml.tournament_config import ScoringConfig


METRIC_COLUMNS = [
    "strategy_id", "strategy_version", "parameter_hash", "split",
    "number_of_trades", "winning_trades", "losing_trades", "win_rate",
    "gross_profit", "gross_loss", "net_pnl", "average_trade", "median_trade",
    "expectancy", "profit_factor", "maximum_drawdown", "total_return",
    "sharpe_ratio", "sortino_ratio", "average_holding_minutes", "exposure",
    "profitable_day_percentage", "profitable_month_percentage",
    "number_of_profitable_symbols", "number_of_losing_symbols", "worst_symbol",
    "best_symbol", "trade_count_confidence", "largest_symbol_profit_share",
    "largest_month_profit_share", "composite_research_score", "warning_codes",
]


def maximum_drawdown(pnl: pd.Series, starting_capital: float) -> float:
    equity = pd.Series([starting_capital, *(starting_capital + pnl.cumsum()).tolist()], dtype=float)
    peaks = equity.cummax()
    return float((equity / peaks - 1).min())


def _ratio(returns: pd.Series, *, downside: bool = False) -> float | None:
    values = returns.dropna().astype(float)
    if len(values) < 2:
        return None
    denominator = values[values < 0].std(ddof=1) if downside else values.std(ddof=1)
    if denominator is None or not math.isfinite(float(denominator)) or denominator <= 1e-12:
        return None
    return float(values.mean() / denominator * math.sqrt(252))


def _profit_share(grouped: pd.Series) -> float:
    positive = grouped[grouped > 0]
    return float(positive.max() / positive.sum()) if len(positive) and positive.sum() else 0.0


def calculate_metrics(
    identity: tuple[str, str, str], split: str,
    sessions: pd.DataFrame, trades: pd.DataFrame,
    *, starting_capital: float, scoring: ScoringConfig,
) -> dict[str, Any]:
    strategy_id, version, parameters = identity
    pnl = trades["net_pnl"].astype(float) if not trades.empty else pd.Series(dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gross_profit, gross_loss = float(wins.sum()), float(-losses.sum())
    day_pnl = (
        sessions.groupby("trading_date", sort=True)["net_pnl"].sum().astype(float)
        if not sessions.empty else pd.Series(dtype=float)
    )
    day_returns = day_pnl / starting_capital
    if not trades.empty:
        months = pd.to_datetime(trades["exit_timestamp"], utc=True).dt.strftime("%Y-%m")
        month_pnl = trades.assign(_month=months).groupby("_month", sort=True)["net_pnl"].sum()
        symbol_pnl = trades.groupby("symbol", sort=True)["net_pnl"].sum()
        holding = (
            pd.to_datetime(trades["exit_timestamp"], utc=True)
            - pd.to_datetime(trades["actual_entry_timestamp"], utc=True)
        ).dt.total_seconds() / 60
    else:
        month_pnl = pd.Series(dtype=float)
        symbol_pnl = pd.Series(dtype=float)
        holding = pd.Series(dtype=float)
    all_months = (
        sorted(pd.to_datetime(sessions["trading_date"]).dt.strftime("%Y-%m").unique())
        if not sessions.empty else []
    )
    month_pnl = month_pnl.reindex(all_months, fill_value=0.0)
    total_available = float(sessions.get("available_regular_minutes", pd.Series(dtype=float)).sum())
    exposure = float(holding.sum() / total_available) if total_available else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss else None
    warning_codes = []
    if len(trades) < scoring.minimum_trades:
        warning_codes.append("low_trade_count")
    if profit_factor is None and gross_profit > 0:
        warning_codes.append("profit_factor_no_losses")
    sharpe, sortino = _ratio(day_returns), _ratio(day_returns, downside=True)
    if sharpe is None:
        warning_codes.append("unstable_sharpe")
    if sortino is None:
        warning_codes.append("unstable_sortino")
    symbol_share, month_share = _profit_share(symbol_pnl), _profit_share(month_pnl)
    if symbol_share > scoring.concentration_warning_fraction:
        warning_codes.append("symbol_profit_concentration")
    if month_share > scoring.concentration_warning_fraction:
        warning_codes.append("month_profit_concentration")
    if exposure < scoring.near_zero_exposure_fraction:
        warning_codes.append("near_zero_exposure")
    session_months = pd.to_datetime(sessions["trading_date"]).dt.to_period("M").nunique() if not sessions.empty else 0
    if session_months >= 3 and len(month_pnl) < session_months / 2:
        warning_codes.append("long_inactive_periods")
    if not trades.empty:
        narrow = trades.loc[trades["symbol"].isin({"GME", "AMC", "TQQQ", "SQQQ", "SPXL", "SPXS", "UVXY"})]
        positive_total = max(float(pnl[pnl > 0].sum()), 0.0)
        if positive_total and float(narrow.loc[narrow["net_pnl"] > 0, "net_pnl"].sum()) / positive_total > 0.5:
            warning_codes.append("narrow_subgroup_dominance")
    return {
        "strategy_id": strategy_id, "strategy_version": version,
        "parameter_hash": parameters, "split": split,
        "number_of_trades": int(len(trades)), "winning_trades": int(len(wins)),
        "losing_trades": int(len(losses)),
        "win_rate": float(len(wins) / len(trades)) if len(trades) else 0.0,
        "gross_profit": gross_profit, "gross_loss": gross_loss, "net_pnl": float(pnl.sum()),
        "average_trade": float(pnl.mean()) if len(pnl) else 0.0,
        "median_trade": float(pnl.median()) if len(pnl) else 0.0,
        "expectancy": float(pnl.mean()) if len(pnl) else 0.0,
        "profit_factor": profit_factor,
        "maximum_drawdown": maximum_drawdown(pnl, starting_capital),
        "total_return": float(pnl.sum() / starting_capital),
        "sharpe_ratio": sharpe, "sortino_ratio": sortino,
        "average_holding_minutes": float(holding.mean()) if len(holding) else 0.0,
        "exposure": exposure,
        "profitable_day_percentage": float((day_pnl > 0).mean()) if len(day_pnl) else 0.0,
        "profitable_month_percentage": float((month_pnl > 0).mean()) if len(month_pnl) else 0.0,
        "number_of_profitable_symbols": int((symbol_pnl > 0).sum()),
        "number_of_losing_symbols": int((symbol_pnl < 0).sum()),
        "worst_symbol": str(symbol_pnl.idxmin()) if len(symbol_pnl) else "",
        "best_symbol": str(symbol_pnl.idxmax()) if len(symbol_pnl) else "",
        "trade_count_confidence": min(len(trades) / scoring.minimum_trades, 1.0),
        "largest_symbol_profit_share": symbol_share,
        "largest_month_profit_share": month_share,
        "composite_research_score": None,
        "warning_codes": ";".join(sorted(set(warning_codes))),
    }


def _bounded(value: Any, scale: float, *, lower: float = 0.0) -> float:
    if value is None or not math.isfinite(float(value)):
        return lower
    return float(np.clip(float(value) / scale, lower, 1.0))


def apply_composite_scores(leaderboard: pd.DataFrame, scoring: ScoringConfig) -> pd.DataFrame:
    """Score validation only; holdout values never enter the formula."""
    output = leaderboard.copy()
    output["composite_research_score"] = np.nan
    development = output.loc[output["split"].eq("development")].set_index("strategy_id")
    for index, row in output.loc[output["split"].eq("validation")].iterrows():
        dev = development.loc[row.strategy_id] if row.strategy_id in development.index else None
        stability = 0.0
        degradation_penalty = 0.0
        if dev is not None:
            denominator = max(abs(float(dev.total_return)), 0.01)
            stability = max(0.0, 1 - abs(float(row.total_return) - float(dev.total_return)) / denominator)
            if float(row.total_return) < float(dev.total_return) * 0.5:
                degradation_penalty = 0.10
        inverse_drawdown = max(0.0, 1 - abs(float(row.maximum_drawdown)) / 0.25)
        components = {
            "profit_factor": _bounded(row.profit_factor, 3.0),
            "sharpe": _bounded(row.sharpe_ratio, 3.0),
            "sortino": _bounded(row.sortino_ratio, 3.0),
            "inverse_drawdown": inverse_drawdown,
            "monthly_consistency": float(row.profitable_month_percentage),
            "cross_symbol_consistency": (
                float(row.number_of_profitable_symbols)
                / max(float(row.number_of_profitable_symbols + row.number_of_losing_symbols), 1)
            ),
            "trade_count": float(row.trade_count_confidence),
            "development_validation_stability": stability,
        }
        weights = {
            "profit_factor": 0.20, "sharpe": 0.15, "sortino": 0.10,
            "inverse_drawdown": 0.15, "monthly_consistency": 0.10,
            "cross_symbol_consistency": 0.10, "trade_count": 0.10,
            "development_validation_stability": 0.10,
        }
        score = sum(components[name] * weight for name, weight in weights.items())
        penalties = degradation_penalty
        symbol_excess = max(0.0, float(row.largest_symbol_profit_share) - scoring.concentration_warning_fraction)
        month_excess = max(0.0, float(row.largest_month_profit_share) - scoring.concentration_warning_fraction)
        concentration_range = max(1 - scoring.concentration_warning_fraction, 1e-9)
        penalties += symbol_excess / concentration_range * 0.20
        penalties += month_excess / concentration_range * 0.15
        if float(row.exposure) < scoring.near_zero_exposure_fraction:
            penalties += 0.10
        if pd.isna(row.profit_factor) or pd.isna(row.sharpe_ratio) or pd.isna(row.sortino_ratio):
            penalties += 0.10
        if int(row.number_of_trades) == 0:
            score, penalties = 0.0, 0.0
        output.at[index, "composite_research_score"] = round(max(0.0, score - penalties) * 100, 6)
        if degradation_penalty:
            warnings = set(filter(None, str(output.at[index, "warning_codes"]).split(";")))
            warnings.add("development_validation_degradation")
            output.at[index, "warning_codes"] = ";".join(sorted(warnings))
    return output.loc[:, METRIC_COLUMNS].sort_values(
        ["split", "composite_research_score", "strategy_id"],
        ascending=[True, False, True], kind="mergesort", na_position="last",
    ).reset_index(drop=True)


def build_metric_tables(
    sessions: pd.DataFrame, trades: pd.DataFrame,
    strategies: list[tuple[str, str, str]], splits: list[str],
    *, starting_capital: float, scoring: ScoringConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, symbol_rows, month_rows = [], [], []
    for identity in strategies:
        strategy_id = identity[0]
        for split in splits:
            session_slice = sessions.loc[(sessions["strategy_id"] == strategy_id) & (sessions["split"] == split)]
            trade_slice = trades.loc[(trades["strategy_id"] == strategy_id) & (trades["split"] == split)] if not trades.empty else trades
            rows.append(calculate_metrics(identity, split, session_slice, trade_slice, starting_capital=starting_capital, scoring=scoring))
            for symbol in sorted(session_slice["symbol"].unique()):
                symbol_sessions = session_slice.loc[session_slice["symbol"] == symbol]
                symbol_trades = trade_slice.loc[trade_slice["symbol"] == symbol] if not trade_slice.empty else trade_slice
                symbol_rows.append({"symbol": symbol, **calculate_metrics(
                    identity, split, symbol_sessions, symbol_trades,
                    starting_capital=starting_capital, scoring=scoring,
                )})
            session_months = sorted(pd.to_datetime(session_slice["trading_date"]).dt.strftime("%Y-%m").unique())
            trade_months = (
                pd.to_datetime(trade_slice["exit_timestamp"], utc=True).dt.strftime("%Y-%m")
                if not trade_slice.empty else pd.Series(dtype="string")
            )
            for month in session_months:
                selected = trade_slice.loc[trade_months == month] if not trade_slice.empty else trade_slice
                month_rows.append({
                    "strategy_id": identity[0], "strategy_version": identity[1],
                    "parameter_hash": identity[2], "split": split, "calendar_month": month,
                    "number_of_trades": len(selected), "net_pnl": float(selected["net_pnl"].sum()) if len(selected) else 0.0,
                    "gross_profit": float(selected.loc[selected["net_pnl"] > 0, "net_pnl"].sum()) if len(selected) else 0.0,
                    "gross_loss": float(-selected.loc[selected["net_pnl"] < 0, "net_pnl"].sum()) if len(selected) else 0.0,
                    "win_rate": float((selected["net_pnl"] > 0).mean()) if len(selected) else 0.0,
                })
    leaderboard = apply_composite_scores(pd.DataFrame(rows, columns=METRIC_COLUMNS), scoring)
    symbols = pd.DataFrame(symbol_rows).sort_values(
        ["strategy_id", "split", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    months = pd.DataFrame(month_rows, columns=[
        "strategy_id", "strategy_version", "parameter_hash", "split", "calendar_month",
        "number_of_trades", "net_pnl", "gross_profit", "gross_loss", "win_rate",
    ]).sort_values(["strategy_id", "split", "calendar_month"], kind="mergesort").reset_index(drop=True)
    return leaderboard, symbols, months
