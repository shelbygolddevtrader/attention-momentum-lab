#!/usr/bin/env python3
"""Publish a real-data, development-only attention portfolio run."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pandas as pd

from aml.historical_portfolio import (
    ATTENTION_STRATEGY_IDENTIFIER,
    DEVELOPMENT_EVIDENCE_CLASS,
    HistoricalSessionProvenance,
    assert_legacy_trade_parity,
    attention_proposals_from_replay,
    historical_portfolio_config,
    order_historical_proposals,
)
from aml.market_halts import CompletenessMode, halt_path, load_verified_halts
from aml.portfolio_artifacts import (
    PortfolioRunContext,
    RunLabel,
    file_sha256,
    load_portfolio_run,
    write_portfolio_run,
)
from aml.portfolio_simulator import simulate_portfolio
from aml.replay import replay_to_frame
from aml.trade_simulator import SimulationConfig, simulate_trades


DEFAULT_MANIFEST = Path(
    "artifacts/research_cohort_v001/local_development_manifest.csv"
)
DEFAULT_FEASIBILITY_METADATA = Path(
    "artifacts/research_cohort_v001/local_feasibility/"
    "edda8465c68398200f47/run_metadata.json"
)


def parser() -> argparse.ArgumentParser:
    """Build the development-only historical portfolio CLI."""

    result = argparse.ArgumentParser(
        description=(
            "Publish a development-only portfolio run from the existing local "
            "historical feasibility sessions"
        )
    )
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    result.add_argument(
        "--feasibility-metadata", type=Path, default=DEFAULT_FEASIBILITY_METADATA
    )
    result.add_argument(
        "--artifact-root", type=Path, default=Path("artifacts/portfolio")
    )
    result.add_argument(
        "--execution-timestamp",
        help="Timezone-aware publication timestamp; defaults to the current UTC time",
    )
    return result


def _resolve_hashed_source(
    root: Path,
    symbol: str,
    trading_date: str,
    feed: str,
    expected_sha256: str,
    recorded_path: str | None,
) -> Path:
    candidates = [
        root / "data" / "processed" / symbol / f"{trading_date}_{feed}_1min.csv",
        root / "artifacts" / "data_quality" / "refetch" / feed
        / f"{symbol}_{trading_date}_1min.csv",
    ]
    if recorded_path:
        recorded = Path(recorded_path).resolve()
        if recorded.is_relative_to(root):
            candidates.append(recorded)
    for path in candidates:
        if path.is_file() and file_sha256(path) == expected_sha256:
            return path
    raise FileNotFoundError(
        f"No local {feed} input matches the registered hash for {symbol} {trading_date}"
    )


def _load_session_bars(path: Path, symbol: str, trading_date: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Historical bars are missing: {', '.join(sorted(missing))}")
    frame = frame.copy(deep=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if frame["timestamp"].dt.tz is None:
        raise ValueError("Historical bar timestamps must be timezone-aware")
    if frame["timestamp"].duplicated().any():
        raise ValueError(f"Duplicate bars for {symbol} {trading_date}")
    if not frame["timestamp"].dt.date.eq(pd.Timestamp(trading_date).date()).all():
        raise ValueError(f"Cross-date bars for {symbol} {trading_date}")
    if "symbol" in frame and not frame["symbol"].astype(str).str.upper().eq(symbol).all():
        raise ValueError(f"Symbol mismatch in {symbol} {trading_date} bars")
    frame["symbol"] = symbol
    return frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    """Build proposals, verify legacy parity, and publish one development run."""

    args = parser().parse_args(argv)
    root = Path.cwd().resolve()
    manifest_path = args.manifest.resolve()
    feasibility_path = args.feasibility_metadata.resolve()
    manifest = pd.read_csv(manifest_path)
    required_manifest = {
        "symbol", "trading_date", "session_class", "cohort_id", "selection_rule",
        "data_source", "data_feed", "dataset_vintage",
    }
    if missing := required_manifest.difference(manifest.columns):
        raise ValueError(f"Development manifest is missing: {', '.join(sorted(missing))}")
    manifest["symbol"] = manifest["symbol"].astype(str).str.upper()
    manifest["trading_date"] = manifest["trading_date"].astype(str)
    manifest = manifest.sort_values(
        ["trading_date", "symbol"], kind="mergesort"
    ).reset_index(drop=True)
    feasibility = json.loads(feasibility_path.read_text(encoding="utf-8"))
    if feasibility.get("evidence_class") != DEVELOPMENT_EVIDENCE_CLASS:
        raise ValueError("Feasibility inputs are not labeled development-only")
    registered_hashes = feasibility.get("input_hashes", {})
    recorded_paths = feasibility.get("source_paths", {})
    simulation_config = SimulationConfig()
    completeness_mode = CompletenessMode.HALT_AWARE

    proposals = []
    legacy_trades = []
    bars_by_symbol: dict[str, list[pd.DataFrame]] = {}
    session_metadata = []
    input_hashes = {
        "development_manifest": file_sha256(manifest_path),
        "development_feasibility_metadata": file_sha256(feasibility_path),
        "strategy_configuration": file_sha256(root / "config/strategy_v001.yaml"),
    }
    for row in manifest.itertuples(index=False):
        symbol, day, feed = row.symbol, row.trading_date, str(row.data_feed).lower()
        key = f"{symbol}:{day}"
        expected_hash = registered_hashes.get(key)
        if expected_hash is None:
            raise ValueError(f"No registered input hash for {key}")
        path = _resolve_hashed_source(
            root, symbol, day, feed, expected_hash, recorded_paths.get(key)
        )
        bars = _load_session_bars(path, symbol, day)
        replay = replay_to_frame(bars)
        halts = load_verified_halts(symbol, day)
        session_legacy, _ = simulate_trades(
            replay, bars, simulation_config, completeness_mode, halts
        )
        admitted = set(session_legacy.get("signal_timestamp", []))
        session = HistoricalSessionProvenance(
            symbol=symbol,
            trading_date=pd.Timestamp(day).date(),
            feed=feed,
            dataset_vintage=row.dataset_vintage,
            session_class=row.session_class,
            cohort_id=row.cohort_id,
            data_source=row.data_source,
            selection_rule=row.selection_rule,
            input_sha256=expected_hash,
            completeness_mode=completeness_mode,
            halt_schedule=halts,
        )
        session_proposals = attention_proposals_from_replay(
            replay,
            session,
            simulation_config,
            admitted_signal_timestamps=admitted,
        )
        proposals.extend(session_proposals)
        if not session_legacy.empty:
            legacy_trades.append(session_legacy)
        bars_by_symbol.setdefault(symbol, []).append(bars)
        input_hashes[f"bars:{symbol}:{day}:{feed}"] = expected_hash
        halt_file = halt_path(symbol, day)
        if halt_file.exists():
            input_hashes[f"verified_halts:{symbol}:{day}"] = file_sha256(halt_file)
        session_metadata.append({
            "symbol": symbol,
            "trading_date": day,
            "feed": feed,
            "dataset_vintage": row.dataset_vintage,
            "session_class": row.session_class,
            "cohort_id": row.cohort_id,
            "bar_count": len(bars),
            "research_candidate_count": int(replay["score"].ge(
                simulation_config.candidate_score_threshold
            ).sum()),
            "eligible_signal_count": len(session_proposals),
            "legacy_trade_count": len(session_legacy),
            "completeness_mode": completeness_mode.value,
            "verified_halt_count": len(halts.records),
            "verified_full_halt_minute_count": len(halts.full_halt_minutes),
            "halt_data_source": halts.source_path,
            "source_input_sha256": expected_hash,
        })

    proposals = order_historical_proposals(proposals)
    combined_bars = {
        symbol: pd.concat(frames, ignore_index=True).sort_values(
            "timestamp", kind="mergesort"
        ).reset_index(drop=True)
        for symbol, frames in sorted(bars_by_symbol.items())
    }
    portfolio_config = historical_portfolio_config(simulation_config)
    result = simulate_portfolio(proposals, combined_bars, portfolio_config)
    expected_trades = (
        pd.concat(legacy_trades, ignore_index=True)
        if legacy_trades else pd.DataFrame()
    )
    assert_legacy_trade_parity(expected_trades, result.trades)

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
        run_label=RunLabel.DEVELOPMENT,
        simulator_configuration={
            "engine": "simulate_portfolio",
            "proposal_adapter": "historical_attention_v001",
            "legacy_simulation_config": asdict(simulation_config),
            "completeness_mode": completeness_mode.value,
        },
        input_hashes=input_hashes,
        provenance={
            "evidence_class": DEVELOPMENT_EVIDENCE_CLASS,
            "not_validation_evidence": True,
            "strategy_employee": {
                "strategy_identifier": ATTENTION_STRATEGY_IDENTIFIER,
                "strategy_version": simulation_config.strategy_version,
            },
            "cohort_id": "local_feasibility_v001",
            "session_count": len(session_metadata),
            "sessions": session_metadata,
            "feeds": sorted(set(manifest["data_feed"].astype(str).str.lower())),
            "completeness_mode": completeness_mode.value,
        },
    )
    destination = write_portfolio_run(
        args.artifact_root, result, proposals, portfolio_config, context
    )
    loaded = load_portfolio_run(destination)
    print(
        f"Development run={loaded.metadata['run_id']} label={loaded.metadata['run_label']} "
        f"sessions={len(session_metadata)} proposals={len(loaded.proposals)} "
        f"accepted={len(loaded.accepted_proposals)} "
        f"rejected={len(loaded.rejected_proposals)} trades={len(loaded.portfolio_trades)} "
        f"net_pnl={loaded.portfolio_summary['realized_pnl']:.12f}"
    )
    print(f"Saved completed development portfolio artifacts: {destination}")


if __name__ == "__main__":
    main()
