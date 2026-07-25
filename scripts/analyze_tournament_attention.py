"""Audit attention-momentum coverage, provenance, and distribution by run ID."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Any

import pandas as pd

from aml.tournament_attention import (
    DIAGNOSTIC_COLUMNS,
    SESSION_DIAGNOSTIC_COLUMNS,
    build_attention_audit,
    session_feature_diagnostics,
    validate_attention_integrity,
)
from aml.tournament_analysis_artifacts import (
    AnalysisProvenance,
    PublishedAnalysis,
    publish_tournament_analysis,
    verify_finalized_tournament,
)
from aml.tournament_config import DatasetSplit
from aml.tournament_runner import _load_session
from aml.tournament_strategies import attention_momentum_feature_frame, build_strategy


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--run-id", required=True)
    value.add_argument("--artifacts-root", type=Path, default=Path("artifacts/tournaments"))
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--analysis-version", default="1.0.0")
    return value


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.is_file() else pd.DataFrame()


def _signal_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    metadata = parsed.get("signal_metadata", {}) if isinstance(parsed, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _month(frame: pd.DataFrame) -> pd.Series:
    """Use exchange trading dates so DST offsets never affect month grouping."""
    if frame.empty or "trading_date" not in frame:
        return pd.Series(index=frame.index, dtype="string")
    parsed = pd.to_datetime(frame["trading_date"], errors="coerce")
    if parsed.isna().any():
        raise ValueError("Unparseable trading_date values")
    return parsed.dt.to_period("M").astype(str)


def _table(frame: pd.DataFrame, group: list[str], value: str | None = None) -> pd.DataFrame:
    if frame.empty:
        columns = [*group, "value"]
        return pd.DataFrame(columns=columns)
    working = frame.copy()
    if "month" in group:
        working["month"] = _month(working)
    if value is None:
        output = working.groupby(group, dropna=False, sort=True).size().rename("value")
    else:
        output = working.groupby(group, dropna=False, sort=True)[value].sum().rename("value")
    return output.reset_index()


def _diagnostic_rows(
    signals: pd.DataFrame,
    frames: dict[tuple[str, str, str], pd.DataFrame],
    threshold: float,
) -> pd.DataFrame:
    records = []
    for row in signals.itertuples(index=False):
        metadata = _signal_metadata(row.provenance_json)
        source_text = metadata.get("source_bar_timestamp")
        source = pd.to_datetime(source_text, utc=True, errors="coerce")
        if pd.isna(source):
            raise ValueError(f"Unparseable source timestamp for proposal {row.proposal_id}")
        key = (row.split, row.symbol, str(row.trading_date))
        frame = frames.get(key)
        if frame is None:
            raise ValueError(f"Missing feature frame for signal {row.proposal_id}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        matches = frame.loc[timestamps.eq(source)]
        if len(matches) != 1:
            raise ValueError(f"Signal source row does not reconcile: {row.proposal_id}")
        feature = matches.iloc[0]
        record = {
            "trading_date": row.trading_date,
            "signal_timestamp": row.signal_timestamp,
            "symbol": row.symbol,
            "split": row.split,
            "proposal_id": row.proposal_id,
            "source_bar_timestamp": source_text,
            "information_cutoff": metadata.get("information_cutoff"),
            "raw_return_feature": feature["return_5m"],
            "relative_volume_feature": feature["relative_volume"],
            "vwap_distance_feature": feature["vwap_distance"],
            "acceleration_feature": feature["volume_acceleration"],
            "return_score_component": feature["return_score_component"],
            "relative_volume_score_component": feature["relative_volume_score_component"],
            "vwap_score_component": feature["vwap_score_component"],
            "acceleration_score_component": feature["acceleration_score_component"],
            "total_score": feature["score"],
            "eligibility_threshold": threshold,
            "eligible": bool(feature["eligible"]),
            "execution_status": row.execution_status,
            "execution_reason": row.execution_reason,
        }
        records.append(record)
    return pd.DataFrame(records, columns=DIAGNOSTIC_COLUMNS).sort_values(
        ["split", "symbol", "trading_date", "signal_timestamp", "proposal_id"],
        kind="mergesort",
    ).reset_index(drop=True) if records else pd.DataFrame(columns=DIAGNOSTIC_COLUMNS)


def _render(title: str, frame: pd.DataFrame) -> list[str]:
    return [f"\n{title}", "(none)" if frame.empty else frame.to_string(index=False)]


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    output = io.StringIO()
    frame.to_csv(
        output, index=False, lineterminator="\n", na_rep="", float_format="%.17g"
    )
    return output.getvalue().encode()


def _source_state(root: Path) -> tuple[str, bool, str]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()
    porcelain = subprocess.run(
        ["git", "status", "--porcelain", "-z"], cwd=root, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    digest = hashlib.sha256(porcelain)
    records = [record for record in porcelain.decode().split("\0") if record]
    for record in records:
        logical = record[3:].split(" -> ")[-1]
        path = root / logical
        digest.update(logical.encode())
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return commit, bool(porcelain), digest.hexdigest()


def analyze_run(
    root: Path, artifacts_root: Path, run_id: str, *, analysis_version: str = "1.0.0"
) -> tuple[pd.DataFrame, pd.DataFrame, str, PublishedAnalysis]:
    root = root.resolve()
    artifacts_root = artifacts_root if artifacts_root.is_absolute() else root / artifacts_root
    source = verify_finalized_tournament(artifacts_root, run_id)
    final = source.final_directory
    manifest = dict(source.manifest)
    signals = _read(final / "signals.csv")
    trades = _read(final / "trades.csv")
    sessions = _read(final / "session_results.csv")
    signals = signals.loc[signals.get("strategy_id", "").eq("attention_momentum")].copy()
    trades = trades.loc[trades.get("strategy_id", "").eq("attention_momentum")].copy()
    sessions = sessions.loc[sessions.get("strategy_id", "").eq("attention_momentum")].copy()
    strategy_record = next(
        item for item in manifest["strategies"] if item["strategy_id"] == "attention_momentum"
    )
    strategy = build_strategy(
        strategy_record["strategy_id"], strategy_record["strategy_version"],
        strategy_record["parameters"],
    )
    exact_elapsed_return = "attention_momentum_diagnostics.csv" in manifest.get(
        "artifact_hashes", {}
    )
    grouped_signals = {
        key: value for key, value in signals.groupby(["split", "symbol", "trading_date"], sort=False)
    } if not signals.empty else {}
    session_rows = []
    signal_frames: dict[tuple[str, str, str], pd.DataFrame] = {}
    for row in sessions.sort_values(["split", "symbol", "trading_date"]).itertuples(index=False):
        bars, _ = _load_session(
            root, manifest["dataset_vintage"], row.symbol, str(row.trading_date)
        )
        session_rows.append(session_feature_diagnostics(
            bars, strategy, split=row.split, symbol=row.symbol,
            trading_date=str(row.trading_date), processed=row.status != "quality_excluded",
            exact_elapsed_return=exact_elapsed_return,
        ))
        key = (row.split, row.symbol, str(row.trading_date))
        if key in grouped_signals:
            signal_frames[key] = attention_momentum_feature_frame(
                bars, strategy, exact_elapsed_return=exact_elapsed_return
            )
    session_frame = pd.DataFrame(session_rows, columns=SESSION_DIAGNOSTIC_COLUMNS)
    diagnostics = _diagnostic_rows(
        signals, signal_frames, float(strategy.parameters["eligible_score_threshold"])
    )
    audit = build_attention_audit(session_frame, signals, trades)
    split_objects = tuple(
        DatasetSplit(
            name, pd.Timestamp(value["start"]).date(), pd.Timestamp(value["end"]).date()
        )
        for name, value in manifest["splits"].items()
    )
    integrity_warnings = validate_attention_integrity(audit, diagnostics, split_objects)

    signal_symbol = _table(signals, ["split", "symbol"])
    trade_symbol = _table(trades, ["split", "symbol"])
    active = signal_symbol.groupby("split").size().rename("active_symbol_count").reset_index() if not signal_symbol.empty else pd.DataFrame(columns=["split", "active_symbol_count"])
    concentration = []
    for split, group in signal_symbol.groupby("split", sort=True):
        total = float(group["value"].sum())
        shares = group["value"] / total if total else pd.Series(dtype=float)
        concentration.append({
            "split": split, "largest_symbol_share": float(shares.max()) if total else 0.0,
            "symbol_hhi": float((shares ** 2).sum()) if total else 0.0,
        })
    feature_summary = audit.groupby("split", sort=True).agg(
        available_sessions=("available_session_count", "sum"),
        processed_sessions=("processed_session_count", "sum"),
        valid_feature_rows=("rows_with_all_required_features", "sum"),
        return_threshold_rows=("rows_above_return_threshold", "sum"),
        volume_threshold_rows=("rows_above_relative_volume_threshold", "sum"),
        score_threshold_rows=("rows_above_score_threshold", "sum"),
    ).reset_index()
    comparison = audit.groupby("split", sort=True).agg(
        signals=("signal_count", "sum"), trades=("executed_trade_count", "sum"),
        active_symbols=("signal_count", lambda value: int(value.gt(0).sum())),
        available_sessions=("available_session_count", "sum"),
        processed_sessions=("processed_session_count", "sum"),
    ).reset_index()
    lines = [
        f"Attention Momentum Tournament Audit: {run_id}",
        "Return semantics: " + (
            "exact elapsed minutes" if exact_elapsed_return else "legacy row window"
        ),
        f"Integrity warnings: {';'.join(integrity_warnings) or 'none'}",
    ]
    sections = [
        ("Signals by split", _table(signals, ["split"])),
        ("Trades by split", _table(trades, ["split"])),
        ("Signals by split and symbol", signal_symbol),
        ("Trades by split and symbol", trade_symbol),
        ("Signals by month", _table(signals, ["split", "month"])),
        ("Trades by month", _table(trades, ["split", "month"])),
        ("P&L by month", _table(trades, ["split", "month"], "net_pnl")),
        ("Execution status counts", _table(signals, ["split", "execution_status"])),
        ("Execution reason counts", _table(signals.fillna({"execution_reason": "unspecified"}), ["split", "execution_reason"])),
        ("Active-symbol counts", active),
        ("Zero-signal symbols", audit.loc[audit["signal_count"].eq(0), ["split", "symbol"]]),
        ("Feature-coverage summary", feature_summary),
        ("Concentration metrics", pd.DataFrame(concentration)),
        ("Development-versus-validation comparison", comparison),
    ]
    for title, frame in sections:
        lines.extend(_render(title, frame))
    report = "\n".join(lines) + "\n"
    commit, dirty, fingerprint = _source_state(root)
    published = publish_tournament_analysis(
        artifacts_root,
        run_id,
        AnalysisProvenance(
            analysis_name="attention-momentum-audit",
            analysis_version=analysis_version,
            source_commit=commit,
            source_worktree_dirty=dirty,
            source_worktree_fingerprint=fingerprint,
            deterministic_configuration={
                "calendar_grouping": "trading_date",
                "exact_elapsed_return": exact_elapsed_return,
                "strategy_id": "attention_momentum",
                "strategy_version": strategy.strategy_version,
                "source_manifest_sha256": hashlib.sha256(
                    (final / "run_manifest.json").read_bytes()
                ).hexdigest(),
            },
        ),
        {
            "attention_momentum_audit.csv": _csv_bytes(audit),
            "attention_momentum_diagnostics.csv": _csv_bytes(diagnostics),
            "attention_momentum_analysis.txt": report.encode(),
        },
    )
    return audit, diagnostics, report, published


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    _, _, report, published = analyze_run(
        args.root, args.artifacts_root, args.run_id,
        analysis_version=args.analysis_version,
    )
    print(report, end="")
    print(f"Analysis directory: {published.directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
