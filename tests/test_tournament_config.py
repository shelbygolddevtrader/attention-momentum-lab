import pytest
from dataclasses import asdict
from pathlib import Path

from aml.tournament_config import FIXED_SPLITS, load_tournament_config, select_splits


def test_fixed_split_boundaries_and_default_order():
    assert str(FIXED_SPLITS["development"].start) == "2023-07-24"
    assert str(FIXED_SPLITS["development"].end) == "2024-12-31"
    assert str(FIXED_SPLITS["validation"].start) == "2025-01-01"
    assert str(FIXED_SPLITS["validation"].end) == "2025-12-31"
    assert str(FIXED_SPLITS["holdout"].start) == "2026-01-01"
    assert str(FIXED_SPLITS["holdout"].end) == "2026-07-23"
    assert [item.name for item in select_splits([], include_holdout=False)] == [
        "development", "validation"
    ]


def test_holdout_requires_explicit_flag_and_is_appended_only_then():
    with pytest.raises(ValueError, match="protected"):
        select_splits(["holdout"], include_holdout=False)
    selected = select_splits(["development"], include_holdout=True)
    assert [item.name for item in selected] == ["development", "holdout"]


def test_all_strategies_receive_identical_execution_assumptions():
    config = load_tournament_config(
        Path(__file__).parents[1] / "config" / "strategy_tournament_baseline.yaml"
    )
    payloads = []
    for strategy in config.strategies:
        portfolio = asdict(config.execution.portfolio_config(strategy))
        portfolio.pop("strategy_allocations")
        payloads.append(portfolio)
    assert all(payload == payloads[0] for payload in payloads)
