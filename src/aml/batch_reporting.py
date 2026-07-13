"""Dual-scope, session-aware reporting for batch historical evaluations."""

import math

import pandas as pd

PROCESSED_STATUSES = {"completed", "zero_candidates", "zero_trades", "quality_flagged"}
SCOPES = ("all_processed_sessions", "quality_qualified_sessions")


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator else None


def _scope_sessions(sessions, scope):
    processed = sessions.loc[sessions["status"].isin(PROCESSED_STATUSES)]
    return processed if scope == "all_processed_sessions" else processed.loc[processed["included_in_aggregate"]]


def _scope_trades(trades, eligible_sessions):
    if trades.empty:
        return trades
    keys = set(zip(eligible_sessions["symbol"], eligible_sessions["trading_date"]))
    return trades.loc[[key in keys for key in zip(trades["symbol"], trades["trading_date"])]]


def _quality_band_column(sessions: pd.DataFrame, effective: bool):
    column = "effective_data_quality_band" if effective and "effective_data_quality_band" in sessions.columns else "data_quality_band"
    return sessions[column]


def _performance(sessions: pd.DataFrame, trades: pd.DataFrame, scope: str) -> dict:
    eligible = _scope_sessions(sessions, scope)
    trades = _scope_trades(trades, eligible)
    pnl = trades["net_pnl"] if not trades.empty else pd.Series(dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = float(wins.sum())
    gross_loss = max(0.0, float(-losses.sum()))
    positive_sessions = eligible.loc[eligible["session_pnl"] > 0, "session_pnl"]
    largest_trade = float(wins.max()) if not wins.empty else None
    largest_session = float(positive_sessions.max()) if not positive_sessions.empty else None
    trade_without = pnl.drop(wins.idxmax()) if not wins.empty else pnl
    session_without = eligible.drop(positive_sessions.idxmax()) if not positive_sessions.empty else eligible
    return {
        "eligible_session_count": int(len(eligible)),
        "zero_candidate_count": int(eligible["candidate_count"].eq(0).sum()),
        "zero_trade_count": int(eligible["trade_count"].eq(0).sum()),
        "trade_count": int(len(trades)), "wins": int(len(wins)), "losses": int(len(losses)),
        "win_rate": _safe_divide(len(wins), len(trades)),
        "expectancy": float(pnl.mean()) if len(pnl) else None,
        "profit_factor": _safe_divide(gross_profit, gross_loss),
        "gross_profit": gross_profit, "gross_loss": gross_loss,
        "mean_session_return": float(eligible["session_return"].mean()) if len(eligible) else None,
        "median_session_return": float(eligible["session_return"].median()) if len(eligible) else None,
        "profitable_session_rate": _safe_divide(int((eligible["session_pnl"] > 0).sum()), len(eligible)),
        "mean_session_drawdown": float(eligible["session_maximum_drawdown"].mean()) if len(eligible) else None,
        "median_session_drawdown": float(eligible["session_maximum_drawdown"].median()) if len(eligible) else None,
        "worst_session_drawdown": float(eligible["session_maximum_drawdown"].min()) if len(eligible) else None,
        "largest_winning_trade": largest_trade, "largest_winning_session": largest_session,
        "largest_trade_share_gross_positive_profit": _safe_divide(largest_trade, gross_profit) if largest_trade is not None else None,
        "largest_session_share_gross_positive_profit": _safe_divide(largest_session, float(positive_sessions.sum())) if largest_session is not None else None,
        "net_pnl_excluding_largest_winning_trade": float(trade_without.sum()) if largest_trade is not None else None,
        "expectancy_excluding_largest_winning_trade": float(trade_without.mean()) if len(trade_without) and largest_trade is not None else None,
        "net_pnl_excluding_largest_winning_session": float(session_without["session_pnl"].sum()) if largest_session is not None else None,
        "mean_session_return_excluding_largest_winner": float(session_without["session_return"].mean()) if len(session_without) and largest_session is not None else None,
    }


def _top_level(sessions, trades):
    status_counts = sessions["status"].value_counts(dropna=False).to_dict()
    return {
        "total_requested_sessions": int(len(sessions)),
        "completed_valid_sessions": int(sessions["status"].isin(PROCESSED_STATUSES).sum()),
        "failed_sessions": int((~sessions["status"].isin(PROCESSED_STATUSES)).sum()),
        "excluded_sessions": int((sessions["status"].isin(PROCESSED_STATUSES) & ~sessions["included_in_aggregate"]).sum()),
        "counts_by_processing_status": {str(key): int(value) for key, value in status_counts.items()},
        "all_processed_sessions": _performance(sessions, trades, "all_processed_sessions"),
        "quality_qualified_sessions": _performance(sessions, trades, "quality_qualified_sessions"),
    }


def _grouped(sessions, trades, session_column=None, trade_column=None):
    source_frame = _quality_band_column(sessions, effective=session_column == "effective_data_quality_band")
    source = source_frame.drop_duplicates().tolist() if session_column in {"data_quality_band", "effective_data_quality_band"} else (
        sessions[session_column].drop_duplicates().tolist() if session_column else trades[trade_column].drop_duplicates().tolist()
    )
    records = []
    for value in sorted(source, key=str):
        if session_column:
            selected_sessions = sessions.loc[_quality_band_column(sessions, effective=session_column == "effective_data_quality_band") == value] if session_column in {"data_quality_band", "effective_data_quality_band"} else sessions.loc[sessions[session_column] == value]
            keys = set(zip(selected_sessions["symbol"], selected_sessions["trading_date"]))
            selected_trades = trades.loc[[key in keys for key in zip(trades.get("symbol", []), trades.get("trading_date", []))]] if not trades.empty else trades
        else:
            selected_trades = trades.loc[trades[trade_column] == value]
            keys = set(zip(selected_trades["symbol"], selected_trades["trading_date"]))
            selected_sessions = sessions.loc[[key in keys for key in zip(sessions["symbol"], sessions["trading_date"])]]
        for scope in SCOPES:
            record = {session_column or trade_column: value, "aggregation_scope": scope}
            record.update(_performance(selected_sessions, selected_trades, scope))
            records.append(record)
    return pd.DataFrame(records)


def build_reports(session_results: pd.DataFrame, trades: pd.DataFrame):
    trade_frame = trades.copy()
    if not trade_frame.empty:
        entries = pd.to_datetime(trade_frame["actual_entry_timestamp"])
        minutes = entries.dt.hour * 60 + entries.dt.minute
        trade_frame["time_bucket"] = pd.cut(minutes, [0, 600, 720, 840, 1440], labels=["open_to_10", "10_to_noon", "noon_to_14", "14_to_close"], right=False).astype("string")
        trade_frame["score_band"] = pd.cut(trade_frame["signal_score"], [54, 64, 69, 79, math.inf], labels=["55-64", "65-69", "70-79", "80+"], right=True).astype("string")
    reports = {
        "overall": _top_level(session_results, trade_frame),
        "by_session_class": _grouped(session_results, trade_frame, session_column="session_class"),
        "by_symbol": _grouped(session_results, trade_frame, session_column="symbol"),
        "by_date": _grouped(session_results, trade_frame, session_column="trading_date"),
        "by_data_quality": _grouped(session_results, trade_frame, session_column="data_quality_band"),
    }
    if "effective_data_quality_band" in session_results.columns:
        reports["by_effective_data_quality"] = _grouped(session_results, trade_frame, session_column="effective_data_quality_band")
    for name, column in (("by_time_bucket", "time_bucket"), ("by_score_band", "score_band"), ("by_exit_reason", "exit_reason")):
        reports[name] = _grouped(session_results, trade_frame, trade_column=column) if not trade_frame.empty else pd.DataFrame()
    return reports
