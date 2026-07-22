#!/usr/bin/env python3
"""Dry-run or execute the fixed zero-cost Alpaca SIP engineering rehearsal."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pandas as pd

from aml.alpaca_rest import AlpacaREST
from aml.engineering_rehearsal import (
    EngineeringRehearsalScope,
    rehearsal_scope_manifest,
    run_engineering_rehearsal,
)
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.settings import Settings


def parser() -> argparse.ArgumentParser:
    """Build the deliberately bounded rehearsal CLI."""

    value = argparse.ArgumentParser(
        description=(
            "Plan the fixed AAPL 2026-07-15 Alpaca SIP engineering rehearsal; "
            "network access requires --execute"
        )
    )
    value.add_argument(
        "--execute",
        action="store_true",
        help="Use normally configured Alpaca credentials for the fixed two-segment scope",
    )
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--artifact-root", type=Path, default=Path("artifacts/portfolio")
    )
    value.add_argument(
        "--execution-timestamp",
        help="Timezone-aware artifact publication timestamp; defaults to current UTC",
    )
    return value


def main(argv: list[str] | None = None) -> int:
    """Print a no-secret plan, or execute only after an explicit flag."""

    args = parser().parse_args(argv)
    scope = EngineeringRehearsalScope()
    if not args.execute:
        print(json.dumps(rehearsal_scope_manifest(scope), indent=2, sort_keys=True))
        print("Dry run only: no credentials loaded and no network request made.")
        print("Execute with: .venv/bin/python scripts/run_engineering_rehearsal.py --execute")
        return 0

    timestamp = pd.Timestamp(args.execution_timestamp or datetime.now(timezone.utc))
    if timestamp.tzinfo is None:
        parser().error("--execution-timestamp must be timezone-aware")
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    source_worktree_dirty = bool(subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout)
    result = run_engineering_rehearsal(
        AlpacaREST(Settings.from_env()),
        ExchangeCalendarsAdapter(),
        args.root,
        args.artifact_root,
        source_commit=source_commit,
        source_worktree_dirty=source_worktree_dirty,
        execution_timestamp=timestamp,
        scope=scope,
    )
    print(
        f"Engineering rehearsal run={result.run_id} label=development "
        f"scope={scope.symbol}:{scope.trading_date}:sip "
        f"cache_reused={result.acquisition_cache_reused} "
        f"premarket_bars={result.premarket_bar_count} "
        f"regular_bars={result.regular_bar_count} proposals={result.proposal_count} "
        f"accepted={result.accepted_count} rejected={result.rejected_count} "
        f"trades={result.trade_count} net_pnl={result.realized_pnl:.12f}"
    )
    print(f"Completed artifacts: {result.artifact_directory}")
    print("Evidence boundary: engineering only; not validation or profitability evidence.")
    print("Incremental cost incurred by this workflow: $0; no purchase is performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
