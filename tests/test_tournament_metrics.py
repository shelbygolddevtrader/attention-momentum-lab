import pandas as pd
import pytest

from aml.tournament_config import ScoringConfig
from aml.tournament_metrics import (
    apply_composite_scores, calculate_metrics, maximum_drawdown,
)


SCORING = ScoringConfig(10, 0.4, 0.001)
IDENTITY = ("alpha", "1.0.0", "a" * 64)


def sessions(split="validation"):
    return pd.DataFrame([
        {"strategy_id": "alpha", "split": split, "symbol": "AAA", "trading_date": "2025-01-02", "net_pnl": 10.0, "available_regular_minutes": 390},
        {"strategy_id": "alpha", "split": split, "symbol": "BBB", "trading_date": "2025-01-03", "net_pnl": -5.0, "available_regular_minutes": 390},
    ])


def trades(split="validation"):
    return pd.DataFrame([
        {"strategy_id": "alpha", "split": split, "symbol": "AAA", "net_pnl": 10.0, "actual_entry_timestamp": "2025-01-02T15:00:00Z", "exit_timestamp": "2025-01-02T15:10:00Z"},
        {"strategy_id": "alpha", "split": split, "symbol": "BBB", "net_pnl": -5.0, "actual_entry_timestamp": "2025-01-03T15:00:00Z", "exit_timestamp": "2025-01-03T15:20:00Z"},
    ])


def test_drawdown_profit_factor_and_zero_trade_edges():
    assert maximum_drawdown(pd.Series([10.0, -20.0, 5.0]), 100.0) == pytest.approx(-20 / 110)
    result = calculate_metrics(IDENTITY, "validation", sessions(), trades(), starting_capital=2000, scoring=SCORING)
    assert result["profit_factor"] == 2
    assert result["average_holding_minutes"] == 15
    zero = calculate_metrics(IDENTITY, "validation", sessions(), pd.DataFrame(), starting_capital=2000, scoring=SCORING)
    assert zero["number_of_trades"] == 0
    assert zero["profit_factor"] is None
    assert "low_trade_count" in zero["warning_codes"]


def test_composite_scores_validation_only_and_penalizes_low_confidence():
    development = calculate_metrics(IDENTITY, "development", sessions("development"), trades("development"), starting_capital=2000, scoring=SCORING)
    validation = calculate_metrics(IDENTITY, "validation", sessions(), trades(), starting_capital=2000, scoring=SCORING)
    holdout = {**validation, "split": "holdout"}
    scored = apply_composite_scores(pd.DataFrame([development, validation, holdout]), SCORING)
    assert pd.isna(scored.loc[scored["split"] == "development", "composite_research_score"]).all()
    assert pd.isna(scored.loc[scored["split"] == "holdout", "composite_research_score"]).all()
    assert scored.loc[scored["split"] == "validation", "composite_research_score"].notna().all()
