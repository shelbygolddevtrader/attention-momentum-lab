"""Bounded-memory, resumable orchestration for strategy tournaments."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable

import pandas as pd

from aml.market_halts import load_verified_halts
from aml.portfolio_artifacts import (
    PERSISTED_TRADE_COLUMNS, PortfolioRunContext, RunLabel, canonical_json_bytes, discover_completed_runs,
    file_sha256, load_portfolio_run, write_portfolio_run,
)
from aml.portfolio_simulator import PriceLevel, StrategyProposal, simulate_portfolio
from aml.tournament_config import DatasetSplit, TournamentConfig, execution_payload
from aml.tournament_metrics import build_metric_tables
from aml.tournament_strategies import ConfiguredStrategy, NormalizedSignal


TOURNAMENT_SCHEMA_VERSION = "aml.strategy-tournament.v1"
SIMULATOR_VERSION = "aml.portfolio_simulator.simulate_portfolio"
CORE_ARTIFACTS = (
    "leaderboard.csv", "strategy_symbol_metrics.csv", "strategy_month_metrics.csv",
    "trades.csv", "signals.csv", "session_results.csv",
)
FINAL_ARTIFACTS = CORE_ARTIFACTS + ("summary.md",)
TOURNAMENT_TRADE_COLUMNS = [
    "strategy_id", "parameter_hash", "split", "trading_date", *PERSISTED_TRADE_COLUMNS,
]


@dataclass(frozen=True)
class SourceState:
    commit: str
    dirty: bool
    worktree_fingerprint: str
    dirty_paths: tuple[str, ...]


@dataclass(frozen=True)
class TournamentUnit:
    strategy: ConfiguredStrategy
    split: str
    symbol: str
    trading_date: str
    unit_id: str


@dataclass(frozen=True)
class TournamentPlan:
    run_id: str
    dataset_vintage: str
    dataset_fingerprint: str
    symbols: tuple[str, ...]
    splits: tuple[DatasetSplit, ...]
    strategies: tuple[ConfiguredStrategy, ...]
    dates_by_split: dict[str, tuple[str, ...]]
    units: tuple[TournamentUnit, ...]
    holdout_used: bool


@dataclass(frozen=True)
class TournamentResult:
    run_id: str
    final_directory: Path
    resumed_units: int
    completed_units: int
    runtime_seconds: float
    deterministic_artifact_hashes: dict[str, str]


def _digest(value: Any, length: int = 20) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:length]


def load_dataset_manifest(root: Path, logical_path: str) -> dict:
    path = Path(root) / logical_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unreadable dataset manifest: {exc}") from exc
    required = {"dataset_vintage", "dataset_fingerprint_sha256", "coverage", "partitions"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("Dataset manifest is incomplete")
    if value["coverage"].get("feed") != "sip" or value["coverage"].get("timeframe") != "1Min":
        raise ValueError("Tournament requires the one-minute SIP dataset")
    return value


def _available_dates(root: Path, vintage: str, symbol: str) -> tuple[str, ...]:
    directory = root / "data" / "research" / vintage / "sip" / symbol
    if not directory.is_dir():
        raise FileNotFoundError(f"Dataset symbol partition is absent: {symbol}")
    return tuple(sorted(path.name for path in directory.iterdir() if path.is_dir()))


def build_plan(
    root: Path, config: TournamentConfig, dataset_manifest: dict,
    source: SourceState, splits: tuple[DatasetSplit, ...],
    *, strategy_ids: Iterable[str] | None = None,
    symbols: Iterable[str] | None = None,
    max_dates_per_split: int | None = None,
) -> TournamentPlan:
    configured = {strategy.strategy_id: strategy for strategy in config.strategies}
    selected_strategy_ids = tuple(strategy_ids or configured)
    unknown = set(selected_strategy_ids).difference(configured)
    if unknown:
        raise ValueError(f"Unknown selected strategies: {', '.join(sorted(unknown))}")
    strategies = tuple(configured[name] for name in selected_strategy_ids)
    manifest_symbols = tuple(dataset_manifest["coverage"]["symbols"])
    selected_symbols = tuple(symbol.upper() for symbol in (symbols or manifest_symbols))
    unknown_symbols = set(selected_symbols).difference(manifest_symbols)
    if unknown_symbols:
        raise ValueError(f"Symbols absent from dataset manifest: {', '.join(sorted(unknown_symbols))}")
    if len(selected_symbols) != len(set(selected_symbols)):
        raise ValueError("Selected symbols must be unique")
    if max_dates_per_split is not None and max_dates_per_split < 1:
        raise ValueError("max_dates_per_split must be positive")
    dates = _available_dates(root, dataset_manifest["dataset_vintage"], selected_symbols[0])
    for symbol in selected_symbols[1:]:
        if _available_dates(root, dataset_manifest["dataset_vintage"], symbol) != dates:
            raise RuntimeError(f"Dataset session coverage differs for {symbol}")
    dates_by_split = {}
    for split in splits:
        selected = tuple(value for value in dates if split.start <= date.fromisoformat(value) <= split.end)
        if max_dates_per_split is not None:
            selected = selected[:max_dates_per_split]
        if not selected:
            raise ValueError(f"No dataset sessions selected for split {split.name}")
        dates_by_split[split.name] = selected
    identity = {
        "schema_version": TOURNAMENT_SCHEMA_VERSION,
        "configuration_hash": config.configuration_hash,
        "dataset_fingerprint": dataset_manifest["dataset_fingerprint_sha256"],
        "source_commit": source.commit, "source_dirty": source.dirty,
        "source_worktree_fingerprint": source.worktree_fingerprint,
        "strategies": [
            {"id": item.strategy_id, "version": item.strategy_version, "parameter_hash": item.parameter_hash}
            for item in strategies
        ],
        "symbols": list(selected_symbols),
        "splits": {name: list(values) for name, values in dates_by_split.items()},
        "execution": execution_payload(config.execution),
    }
    run_id = _digest(identity)
    units = []
    for strategy in strategies:
        for split in splits:
            for symbol in selected_symbols:
                for trading_date in dates_by_split[split.name]:
                    unit_payload = {
                        "tournament_run_id": run_id, "strategy_id": strategy.strategy_id,
                        "strategy_version": strategy.strategy_version,
                        "parameter_hash": strategy.parameter_hash, "split": split.name,
                        "symbol": symbol, "trading_date": trading_date,
                    }
                    units.append(TournamentUnit(
                        strategy, split.name, symbol, trading_date, _digest(unit_payload)
                    ))
    return TournamentPlan(
        run_id, dataset_manifest["dataset_vintage"],
        dataset_manifest["dataset_fingerprint_sha256"], selected_symbols, splits,
        strategies, dates_by_split, tuple(units), any(split.name == "holdout" for split in splits),
    )


def plan_summary(plan: TournamentPlan, artifact_root: Path) -> dict:
    return {
        "run_id": plan.run_id,
        "selected_strategies": [strategy.strategy_id for strategy in plan.strategies],
        "symbols": list(plan.symbols), "splits": [split.name for split in plan.splits],
        "date_ranges": {
            name: {"start": dates[0], "end": dates[-1], "trading_days": len(dates)}
            for name, dates in plan.dates_by_split.items()
        },
        "parameter_sets": {
            strategy.strategy_id: {
                "version": strategy.strategy_version,
                "parameter_hash": strategy.parameter_hash,
                "parameters": dict(strategy.parameters),
            }
            for strategy in plan.strategies
        },
        "estimated_symbol_days": sum(len(values) for values in plan.dates_by_split.values()) * len(plan.symbols),
        "estimated_strategy_symbol_days": len(plan.units),
        "holdout_used": plan.holdout_used,
        "output_location": (Path(artifact_root) / plan.run_id / "final").as_posix(),
    }


def _load_session(root: Path, vintage: str, symbol: str, trading_date: str) -> tuple[pd.DataFrame, dict]:
    base = root / "data" / "research" / vintage / "sip" / symbol / trading_date
    bars_path = base / "processed" / "regular_1min.csv"
    metadata_path = base / "metadata" / "regular_acquisition.json"
    if not bars_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Incomplete regular-session partition: {symbol} {trading_date}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = {
        "status": "success", "requested_feed": "sip", "timeframe": "1Min",
        "dataset_vintage": vintage, "symbol": symbol, "trading_date": trading_date,
        "segment": "regular",
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Acquisition identity mismatch: {symbol} {trading_date}")
    if file_sha256(bars_path) != metadata.get("processed_sha256"):
        raise ValueError(f"Processed partition hash mismatch: {symbol} {trading_date}")
    bars = pd.read_csv(bars_path)
    if len(bars) != metadata.get("record_count"):
        raise ValueError(f"Processed partition row drift: {symbol} {trading_date}")
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    return bars, metadata


def _proposals(
    signals: tuple[NormalizedSignal, ...], unit: TournamentUnit,
    config: TournamentConfig, plan: TournamentPlan,
) -> list[StrategyProposal]:
    return [StrategyProposal(
        strategy_identifier=signal.strategy_id,
        strategy_version=signal.strategy_version,
        symbol=signal.symbol,
        signal_timestamp=signal.signal_timestamp,
        direction=signal.direction,
        score_or_confidence=signal.confidence,
        intended_entry_timestamp=signal.signal_timestamp,
        intended_entry_price=None,
        stop=PriceLevel.fraction(config.execution.stop_fraction),
        target=PriceLevel.fraction(config.execution.target_fraction),
        maximum_holding_minutes=config.execution.maximum_holding_minutes,
        provenance={
            "tournament_run_id": plan.run_id, "unit_id": unit.unit_id,
            "split": unit.split, "parameter_hash": signal.parameter_hash,
            "signal_metadata": dict(signal.metadata), "research_only": True,
        },
    ) for signal in signals]


def _unit_root(run_root: Path, unit: TournamentUnit) -> Path:
    return run_root / "units" / unit.strategy.strategy_id / unit.split / unit.symbol / unit.trading_date


def _compatible_unit(directory: Path, unit: TournamentUnit, plan: TournamentPlan):
    loaded = load_portfolio_run(directory)
    provenance = loaded.metadata.get("provenance", {})
    expected = {
        "tournament_run_id": plan.run_id, "unit_id": unit.unit_id,
        "split": unit.split, "symbol": unit.symbol, "trading_date": unit.trading_date,
        "parameter_hash": unit.strategy.parameter_hash,
    }
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Resume artifact is incompatible: {directory}")
    return loaded


def _run_unit(
    root: Path, run_root: Path, unit: TournamentUnit, plan: TournamentPlan,
    config: TournamentConfig, source: SourceState, execution_timestamp: pd.Timestamp,
    *, resume: bool,
) -> tuple[Any, dict, bool]:
    unit_root = _unit_root(run_root, unit)
    completed = discover_completed_runs(unit_root) if unit_root.exists() else []
    if completed:
        if len(completed) != 1:
            raise RuntimeError(f"Multiple completed artifacts exist for unit {unit.unit_id}")
        if not resume:
            raise FileExistsError(f"Unit already exists; rerun with --resume: {unit.unit_id}")
        loaded = _compatible_unit(completed[0], unit, plan)
        return loaded, _session_record(unit, loaded, None), True
    if unit_root.exists() and any(unit_root.iterdir()):
        raise RuntimeError(f"Incomplete or corrupt unit output blocks resume: {unit_root}")

    bars, metadata = _load_session(root, plan.dataset_vintage, unit.symbol, unit.trading_date)
    normalization = metadata["normalization"]
    expected_minutes = int(normalization["expected_minute_count"])
    missing_minutes = int(normalization["missing_timestamp_count"])
    halt_schedule = load_verified_halts(unit.symbol, unit.trading_date, root / "data" / "market_halts")
    verified_halt_minutes = len(halt_schedule.full_halt_minutes)
    effective_missing = max(0, missing_minutes - verified_halt_minutes)
    quality_excluded = effective_missing / expected_minutes > config.execution.maximum_missing_regular_fraction
    signals = () if quality_excluded else unit.strategy.evaluate(bars)
    proposals = _proposals(signals, unit, config, plan)
    portfolio_config = config.execution.portfolio_config(unit.strategy)
    result = simulate_portfolio(proposals, {unit.symbol: bars}, portfolio_config)
    context = PortfolioRunContext(
        source_commit=source.commit, source_worktree_dirty=source.dirty,
        execution_timestamp=execution_timestamp,
        run_label=RunLabel.VALIDATION if unit.split in {"validation", "holdout"} else RunLabel.DEVELOPMENT,
        simulator_configuration={
            "engine": SIMULATOR_VERSION, "entry_semantics": "next_minute_open",
            "configuration": execution_payload(config.execution),
        },
        input_hashes={
            "regular_processed_bars": metadata["processed_sha256"],
            "dataset_fingerprint": plan.dataset_fingerprint,
            "strategy_parameters": unit.strategy.parameter_hash,
        },
        provenance={
            "tournament_run_id": plan.run_id, "unit_id": unit.unit_id,
            "split": unit.split, "symbol": unit.symbol, "trading_date": unit.trading_date,
            "parameter_hash": unit.strategy.parameter_hash,
            "quality_excluded": quality_excluded, "missing_regular_minutes": missing_minutes,
            "expected_regular_minutes": expected_minutes,
            "verified_halt_minutes": verified_halt_minutes, "research_only": True,
        },
    )
    destination = write_portfolio_run(unit_root, result, proposals, portfolio_config, context)
    loaded = load_portfolio_run(destination)
    quality = {
        "expected": expected_minutes, "missing": missing_minutes,
        "effective_missing": effective_missing, "halts": verified_halt_minutes,
        "excluded": quality_excluded,
    }
    return loaded, _session_record(unit, loaded, quality), False


def _session_record(unit: TournamentUnit, loaded: Any, quality: dict | None) -> dict:
    provenance = loaded.metadata["provenance"]
    quality = quality or {
        "expected": int(provenance.get("expected_regular_minutes", 0)),
        "missing": int(provenance.get("missing_regular_minutes", 0)),
        "effective_missing": int(provenance.get("missing_regular_minutes", 0))
        - int(provenance.get("verified_halt_minutes", 0)),
        "halts": int(provenance.get("verified_halt_minutes", 0)),
        "excluded": bool(provenance.get("quality_excluded", False)),
    }
    accepted = int(loaded.accepted_proposals.shape[0])
    trade_count = int(loaded.portfolio_trades.shape[0])
    return {
        "strategy_id": unit.strategy.strategy_id,
        "strategy_version": unit.strategy.strategy_version,
        "parameter_hash": unit.strategy.parameter_hash,
        "split": unit.split, "symbol": unit.symbol, "trading_date": unit.trading_date,
        "status": "quality_excluded" if quality["excluded"] else (
            "completed" if trade_count else "zero_trades" if accepted else "zero_signals"
        ),
        "signal_count": int(loaded.proposals.shape[0]), "accepted_signal_count": accepted,
        "trade_count": trade_count,
        "net_pnl": float(loaded.portfolio_trades["net_pnl"].sum()) if trade_count else 0.0,
        "available_regular_minutes": int(quality["expected"]),
        "missing_regular_minutes": int(quality["missing"]),
        "effective_missing_regular_minutes": max(0, int(quality["effective_missing"])),
        "verified_halt_minutes_excluded": int(quality["halts"]),
        "unit_id": unit.unit_id, "portfolio_run_id": loaded.metadata["run_id"],
    }


def _signal_rows(unit: TournamentUnit, loaded: Any) -> list[dict]:
    if loaded.proposals.empty:
        return []
    audit = loaded.accepted_proposals.copy()
    rejected = loaded.rejected_proposals.copy()
    audits = (
        rejected.copy() if audit.empty else audit.copy() if rejected.empty
        else pd.concat([audit, rejected], ignore_index=True)
    )
    status = audits.set_index("proposal_id")[["status", "reason"]].to_dict("index")
    return [{
        "strategy_id": unit.strategy.strategy_id,
        "strategy_version": unit.strategy.strategy_version,
        "parameter_hash": unit.strategy.parameter_hash,
        "split": unit.split, "symbol": unit.symbol, "trading_date": unit.trading_date,
        "proposal_id": row.proposal_id, "signal_timestamp": row.signal_timestamp,
        "direction": row.direction, "confidence": row.score_or_confidence,
        "execution_status": status[row.proposal_id]["status"],
        "execution_reason": status[row.proposal_id]["reason"],
        "provenance_json": row.provenance_json,
    } for row in loaded.proposals.itertuples(index=False)]


def _trade_rows(unit: TournamentUnit, loaded: Any) -> list[dict]:
    records = []
    for record in loaded.portfolio_trades.to_dict("records"):
        record.update({
            "strategy_id": unit.strategy.strategy_id,
            "strategy_version": unit.strategy.strategy_version,
            "parameter_hash": unit.strategy.parameter_hash,
            "split": unit.split, "trading_date": unit.trading_date,
        })
        records.append(record)
    return records


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    output = frame.copy()
    for column in output.columns:
        if isinstance(output[column].dtype, pd.DatetimeTZDtype):
            output[column] = output[column].map(lambda value: pd.Timestamp(value).isoformat())
    return output.to_csv(
        index=False, lineterminator="\n", na_rep="", float_format="%.17g"
    ).encode()


def _summary_markdown(
    plan: TournamentPlan, leaderboard: pd.DataFrame, sessions: pd.DataFrame,
    *, runtime_seconds: float,
) -> str:
    validation = leaderboard.loc[leaderboard["split"].eq("validation")].sort_values(
        "composite_research_score", ascending=False, na_position="last"
    )
    lines = [
        "# Strategy Tournament Summary", "",
        "Simulated research results only; this is not real-money performance.", "",
        f"- Run ID: `{plan.run_id}`",
        f"- Holdout used: **{'yes' if plan.holdout_used else 'no'}**",
        f"- Runtime: {runtime_seconds:.3f} seconds",
        f"- Strategy-symbol-day units: {len(plan.units)}",
        f"- Quality exclusions: {int(sessions['status'].eq('quality_excluded').sum())}", "",
        "## Validation leaderboard", "",
        "| Rank | Strategy | Score | Trades | Net P&L | Warnings |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(validation.itertuples(index=False), start=1):
        score = "" if pd.isna(row.composite_research_score) else f"{row.composite_research_score:.3f}"
        lines.append(
            f"| {rank} | {row.strategy_id} | {score} | {row.number_of_trades} | "
            f"{row.net_pnl:.2f} | {row.warning_codes} |"
        )
    lines.extend([
        "", "## Development versus validation", "",
    ])
    for strategy_id in sorted(leaderboard["strategy_id"].unique()):
        selected = leaderboard.loc[leaderboard["strategy_id"].eq(strategy_id)].set_index("split")
        development = selected.loc["development", "net_pnl"] if "development" in selected.index else None
        validation_pnl = selected.loc["validation", "net_pnl"] if "validation" in selected.index else None
        lines.append(f"- {strategy_id}: development P&L={development}; validation P&L={validation_pnl}")
    lines.extend(["", "## Consistency by year", ""])
    year_frame = sessions.assign(year=pd.to_datetime(sessions["trading_date"]).dt.year)
    for (strategy_id, year), group in year_frame.groupby(["strategy_id", "year"], sort=True):
        lines.append(f"- {strategy_id} {year}: P&L={group['net_pnl'].sum():.2f}, trades={group['trade_count'].sum()}")
    lines.extend(["", "## Consistency by symbol", ""])
    symbol_frame = sessions.groupby(["strategy_id", "symbol"], sort=True)["net_pnl"].sum()
    for strategy_id in sorted(sessions["strategy_id"].unique()):
        selected = symbol_frame.loc[strategy_id]
        lines.append(f"- {strategy_id}: best={selected.idxmax()} ({selected.max():.2f}), worst={selected.idxmin()} ({selected.min():.2f})")
    lines.extend(["", "## Major drawdowns and sample-size warnings", ""])
    for row in leaderboard.itertuples(index=False):
        if row.split in {"development", "validation"}:
            lines.append(
                f"- {row.strategy_id} {row.split}: max drawdown={row.maximum_drawdown:.4f}, "
                f"trades={row.number_of_trades}, warnings={row.warning_codes}"
            )
    lines.extend([
        "", "## Interpretation cautions", "",
        "- Development and validation use fixed parameters and identical execution assumptions.",
        "- Holdout is excluded unless explicitly requested and never affects the composite score.",
        "- No statistical significance claim is made.",
        "- Missing-minute, concentration, low-trade-count, unstable-ratio, and degradation warnings must be reviewed.",
    ])
    return "\n".join(lines) + "\n"


def _verify_final(final: Path) -> dict:
    manifest_path = final / "run_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Tournament final artifact is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise ValueError("Tournament final artifact is not completed")
    for name, digest in manifest["artifact_hashes"].items():
        if file_sha256(final / name) != digest:
            raise ValueError(f"Tournament artifact hash mismatch: {name}")
    return manifest


def _publish_final(
    run_root: Path, plan: TournamentPlan, config: TournamentConfig, source: SourceState,
    dataset_manifest: dict, sessions: pd.DataFrame, trades: pd.DataFrame,
    signals: pd.DataFrame, leaderboard: pd.DataFrame, symbol_metrics: pd.DataFrame,
    month_metrics: pd.DataFrame, started: datetime, completed: datetime,
) -> tuple[Path, dict[str, str]]:
    final = run_root / "final"
    if final.exists():
        raise FileExistsError(f"Completed tournament already exists: {final}")
    run_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".final.", dir=run_root))
    frames = {
        "leaderboard.csv": leaderboard,
        "strategy_symbol_metrics.csv": symbol_metrics,
        "strategy_month_metrics.csv": month_metrics,
        "trades.csv": trades,
        "signals.csv": signals,
        "session_results.csv": sessions,
    }
    try:
        for name, frame in frames.items():
            (temporary / name).write_bytes(_csv_bytes(frame))
        runtime = (completed - started).total_seconds()
        (temporary / "summary.md").write_text(
            _summary_markdown(plan, leaderboard, sessions, runtime_seconds=runtime), encoding="utf-8"
        )
        artifact_hashes = {name: file_sha256(temporary / name) for name in FINAL_ARTIFACTS}
        deterministic = {name: artifact_hashes[name] for name in CORE_ARTIFACTS}
        manifest = {
            "status": "completed", "schema_version": TOURNAMENT_SCHEMA_VERSION,
            "run_id": plan.run_id, "source_commit": source.commit,
            "source_worktree_dirty": source.dirty,
            "source_worktree_fingerprint": source.worktree_fingerprint,
            "source_dirty_paths": list(source.dirty_paths),
            "dataset_identity": plan.dataset_fingerprint,
            "dataset_vintage": plan.dataset_vintage,
            "dataset_date_range": {
                "start": dataset_manifest["coverage"]["start_date"],
                "end": dataset_manifest["coverage"]["end_date"],
            },
            "symbols": list(plan.symbols),
            "splits": {name: {"start": dates[0], "end": dates[-1], "trading_days": len(dates)} for name, dates in plan.dates_by_split.items()},
            "holdout_used": plan.holdout_used,
            "strategies": [{
                "strategy_id": strategy.strategy_id, "strategy_version": strategy.strategy_version,
                "description": strategy.description, "direction_support": strategy.direction_support.value,
                "required_lookback": strategy.required_lookback,
                "parameter_hash": strategy.parameter_hash, "parameters": dict(strategy.parameters),
            } for strategy in plan.strategies],
            "configuration_hash": config.configuration_hash,
            "execution_assumptions": execution_payload(config.execution),
            "simulator_version": SIMULATOR_VERSION,
            "artifact_hashes": artifact_hashes,
            "deterministic_artifact_hashes": deterministic,
            "started_at": started.isoformat(), "completed_at": completed.isoformat(),
            "runtime_seconds": runtime,
            "warnings": sorted(set(filter(None, ";".join(leaderboard["warning_codes"].fillna("")).split(";")))),
            "exclusions": sessions["status"].value_counts().sort_index().to_dict(),
        }
        (temporary / "run_manifest.json").write_bytes(canonical_json_bytes(manifest))
        os.rename(temporary, final)
        return final, deterministic
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


@contextmanager
def tournament_lock(artifact_root: Path, run_id: str):
    locks = Path(artifact_root) / ".locks"
    locks.mkdir(parents=True, exist_ok=True)
    path = locks / f"{run_id}.lock"
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Tournament run is already active: {run_id}") from exc
        yield
        fcntl.flock(handle, fcntl.LOCK_UN)


def run_tournament(
    root: Path, artifact_root: Path, config: TournamentConfig, plan: TournamentPlan,
    dataset_manifest: dict, source: SourceState, *, resume: bool,
) -> TournamentResult:
    started = datetime.now(timezone.utc)
    run_root = Path(artifact_root) / plan.run_id
    final = run_root / "final"
    with tournament_lock(artifact_root, plan.run_id):
        if final.exists():
            if not resume:
                raise FileExistsError("Completed tournament exists; use --resume to verify and reuse it")
            manifest = _verify_final(final)
            return TournamentResult(
                plan.run_id, final, len(plan.units), 0, 0.0,
                manifest["deterministic_artifact_hashes"],
            )
        session_rows, trade_rows, signal_rows = [], [], []
        resumed = completed_units = 0
        timestamp = pd.Timestamp(started)
        for unit in plan.units:
            loaded, session, reused = _run_unit(
                root, run_root, unit, plan, config, source, timestamp, resume=resume
            )
            resumed += int(reused)
            completed_units += int(not reused)
            session_rows.append(session)
            trade_rows.extend(_trade_rows(unit, loaded))
            signal_rows.extend(_signal_rows(unit, loaded))
        sessions = pd.DataFrame(session_rows).sort_values(
            ["strategy_id", "split", "symbol", "trading_date"], kind="mergesort"
        ).reset_index(drop=True)
        trades = pd.DataFrame(trade_rows, columns=TOURNAMENT_TRADE_COLUMNS)
        if not trades.empty:
            trades = trades.sort_values(
                ["strategy_id", "split", "symbol", "trading_date", "actual_entry_timestamp", "proposal_id"],
                kind="mergesort",
            ).reset_index(drop=True)
        signals = pd.DataFrame(signal_rows, columns=[
            "strategy_id", "strategy_version", "parameter_hash", "split", "symbol",
            "trading_date", "proposal_id", "signal_timestamp", "direction", "confidence",
            "execution_status", "execution_reason", "provenance_json",
        ]).sort_values(
            ["strategy_id", "split", "symbol", "trading_date", "signal_timestamp", "proposal_id"],
            kind="mergesort",
        ).reset_index(drop=True)
        identities = [
            (strategy.strategy_id, strategy.strategy_version, strategy.parameter_hash)
            for strategy in plan.strategies
        ]
        leaderboard, symbol_metrics, month_metrics = build_metric_tables(
            sessions, trades, identities, [split.name for split in plan.splits],
            starting_capital=config.execution.starting_capital, scoring=config.scoring,
        )
        completed = datetime.now(timezone.utc)
        final, deterministic = _publish_final(
            run_root, plan, config, source, dataset_manifest, sessions, trades, signals,
            leaderboard, symbol_metrics, month_metrics, started, completed,
        )
        return TournamentResult(
            plan.run_id, final, resumed, completed_units,
            (completed - started).total_seconds(), deterministic,
        )
