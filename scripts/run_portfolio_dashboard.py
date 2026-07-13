#!/usr/bin/env python3
"""Launch a plain read-only dashboard over completed portfolio artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from aml.portfolio_artifacts import discover_completed_runs, load_portfolio_run


def parser() -> argparse.ArgumentParser:
    """Build dashboard arguments without importing Streamlit."""

    result = argparse.ArgumentParser(
        description="Read completed portfolio-run artifacts in a local Streamlit dashboard"
    )
    result.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/portfolio"),
        help="Directory containing immutable portfolio run directories",
    )
    return result


def _searchable_table(st: Any, frame: pd.DataFrame, key: str) -> None:
    """Display one persisted table with a display-only substring filter."""

    query = st.text_input("Search", key=f"search_{key}").strip()
    displayed = frame
    if query and not frame.empty:
        mask = frame.astype(str).apply(
            lambda column: column.str.contains(query, case=False, regex=False, na=False)
        ).any(axis=1)
        displayed = frame.loc[mask]
    st.dataframe(displayed, use_container_width=True, hide_index=True)


def main(argv: list[str] | None = None) -> None:
    """Render only hash-verified persisted outputs; never run the simulator."""

    args = parser().parse_args(argv)
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - environment-specific message
        raise RuntimeError(
            "Streamlit is not installed; install the project dashboard extra first"
        ) from exc

    st.set_page_config(page_title="Portfolio Simulation Runs", layout="wide")
    st.title("Portfolio Simulation Runs")
    runs = discover_completed_runs(args.artifact_root)
    if not runs:
        st.warning(f"No completed, valid runs found under {args.artifact_root}")
        return
    labels = {path.name: path for path in runs}
    selected = st.sidebar.selectbox("Completed run", options=list(labels))
    run = load_portfolio_run(labels[selected])
    metadata = dict(run.metadata)
    label = str(metadata["run_label"]).upper()
    st.warning(f"{label} RUN — persisted simulation output only")

    overview, employees, proposals, rejections, trades, equity, drawdown, strategy_pnl, allocation, provenance = st.tabs([
        "Portfolio overview", "Strategy employees", "Proposals", "Rejections",
        "Trades", "Equity curve", "Drawdown", "Strategy P&L", "Fixed allocation",
        "Metadata & provenance",
    ])
    with overview:
        summary = dict(run.portfolio_summary)
        summary.pop("reconciliation", None)
        _searchable_table(st, pd.DataFrame([summary]), "overview")
        st.subheader("Reconciliation")
        _searchable_table(
            st, pd.DataFrame([run.portfolio_summary["reconciliation"]]), "reconciliation"
        )
    with employees:
        _searchable_table(st, run.strategy_ledgers, "employees")
    with proposals:
        _searchable_table(st, run.proposals, "proposals")
        st.subheader("Accepted proposals")
        _searchable_table(st, run.accepted_proposals, "accepted")
    with rejections:
        _searchable_table(st, run.rejected_proposals, "rejections")
    with trades:
        _searchable_table(st, run.portfolio_trades, "trades")
    with equity:
        st.line_chart(run.equity_curve, x="timestamp", y="portfolio_equity")
        _searchable_table(st, run.equity_curve, "equity")
    with drawdown:
        st.line_chart(run.drawdown_curve, x="timestamp", y="drawdown_fraction")
        _searchable_table(st, run.drawdown_curve, "drawdown")
    with strategy_pnl:
        st.line_chart(
            run.portfolio_trades,
            x="exit_timestamp",
            y="cumulative_strategy_pnl",
            color="strategy_identifier",
        )
        _searchable_table(
            st,
            run.portfolio_trades[[
                "exit_timestamp", "strategy_identifier", "strategy_version",
                "proposal_id", "net_pnl", "cumulative_strategy_pnl",
            ]],
            "strategy_pnl",
        )
    with allocation:
        _searchable_table(st, pd.DataFrame(metadata["fixed_allocations"]), "allocation")
    with provenance:
        st.json(metadata)


if __name__ == "__main__":
    main()
