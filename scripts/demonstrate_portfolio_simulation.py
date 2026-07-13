#!/usr/bin/env python3
"""Run a synthetic three-strategy shared-capital demonstration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pandas as pd

from aml.portfolio_simulator import (
    Direction,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)
from aml.portfolio_artifacts import (
    PortfolioRunContext,
    RunLabel,
    dataframe_sha256,
    write_portfolio_run,
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

    result = argparse.ArgumentParser(
        description=(
            "Run a deterministic synthetic three-strategy portfolio demonstration; "
            "results are not performance evidence."
        )
    )
    result.add_argument(
        "--artifact-root",
        type=Path,
        help="Persist an immutable synthetic run beneath this directory",
    )
    result.add_argument(
        "--execution-timestamp",
        help="Timezone-aware timestamp to record; defaults to the current UTC time",
    )
    return result


def main(argv: list[str] | None = None) -> None:
    """Print deterministic proposal, trade, ledger, and portfolio results."""

    args = parser().parse_args(argv)
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
    inputs = {"AAA": bars("AAA", target=True), "BBB": bars("BBB"), "CCC": bars("CCC")}
    result = simulate_portfolio(proposals, inputs, config)
    print("Synthetic proposal decisions (not performance evidence):")
    print(result.proposal_audit[[
        "strategy_identifier", "symbol", "status", "reason", "capital_used"
    ]].to_string(index=False))
    print("\nStrategy ledgers:")
    print(result.strategy_ledgers.to_string(index=False))
    print("\nPortfolio reconciliation:")
    print(dict(result.portfolio_summary))
    if args.artifact_root is not None:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        source_worktree_dirty = bool(subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout)
        execution_timestamp = pd.Timestamp(
            args.execution_timestamp or datetime.now(timezone.utc)
        )
        context = PortfolioRunContext(
            source_commit=source_commit,
            source_worktree_dirty=source_worktree_dirty,
            execution_timestamp=execution_timestamp,
            run_label=RunLabel.SYNTHETIC,
            simulator_configuration={
                "engine": "simulate_portfolio",
                "execution_model": "deterministic_historical_bars",
            },
            input_hashes={
                f"synthetic_bars:{symbol}": dataframe_sha256(frame)
                for symbol, frame in sorted(inputs.items())
            },
            provenance={
                "purpose": "three_strategy_demonstration",
                "performance_evidence": False,
            },
        )
        destination = write_portfolio_run(
            args.artifact_root, result, proposals, config, context
        )
        print(f"\nPersisted immutable synthetic run: {destination}")


if __name__ == "__main__":
    main()
