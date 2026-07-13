#!/usr/bin/env python3
"""Run a synthetic three-strategy shared-capital demonstration."""

from __future__ import annotations

import argparse

import pandas as pd

from aml.portfolio_simulator import (
    Direction,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)


def bars(symbol: str, target: bool = False) -> pd.DataFrame:
    """Build deterministic synthetic bars; these are not performance evidence."""

    timestamps = pd.date_range(
        "2024-01-02 09:30", periods=35, freq="min", tz="America/New_York"
    )
    frame = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": symbol,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
    })
    if target:
        frame.loc[5, "high"] = 103.0
    return frame


def proposal(employee: str, symbol: str, confidence: float) -> StrategyProposal:
    """Create a synthetic strategy-employee proposal."""

    signal = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")
    return StrategyProposal(
        strategy_identifier=employee,
        strategy_version="1.0.0",
        symbol=symbol,
        signal_timestamp=signal,
        direction=Direction.LONG,
        score_or_confidence=confidence,
        intended_entry_timestamp=signal + pd.Timedelta(1, unit="min"),
        intended_entry_price=100.0,
        stop=PriceLevel.fraction(0.02),
        target=PriceLevel.fraction(0.02),
        maximum_holding_minutes=10,
        provenance={"source": "synthetic_demonstration", "outcome_free": True},
    )


def parser() -> argparse.ArgumentParser:
    """Build the demonstration CLI without adding acquisition or live options."""

    return argparse.ArgumentParser(
        description=(
            "Run a deterministic synthetic three-strategy portfolio demonstration; "
            "results are not performance evidence."
        )
    )


def main(argv: list[str] | None = None) -> None:
    """Print deterministic proposal, trade, ledger, and portfolio results."""

    parser().parse_args(argv)
    employees = (
        StrategyAllocation("attention_employee", "1.0.0", 1_000.0),
        StrategyAllocation("momentum_employee", "1.0.0", 1_000.0),
        StrategyAllocation("volume_employee", "1.0.0", 1_000.0),
    )
    config = PortfolioConfig(
        total_capital=3_000.0,
        strategy_allocations=employees,
        maximum_position_risk_fraction=0.02,
        maximum_concurrent_positions=2,
        maximum_symbol_concentration_fraction=0.60,
        maximum_strategy_concentration_fraction=0.40,
    )
    proposals = [
        proposal("attention_employee", "AAA", 80),
        proposal("momentum_employee", "BBB", 0.75),
        proposal("volume_employee", "CCC", 0.70),
    ]
    result = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA", target=True), "BBB": bars("BBB"), "CCC": bars("CCC")},
        config,
    )
    print("Synthetic proposal decisions (not performance evidence):")
    print(result.proposal_audit[[
        "strategy_identifier", "symbol", "status", "reason", "capital_used"
    ]].to_string(index=False))
    print("\nStrategy ledgers:")
    print(result.strategy_ledgers.to_string(index=False))
    print("\nPortfolio reconciliation:")
    print(dict(result.portfolio_summary))


if __name__ == "__main__":
    main()
