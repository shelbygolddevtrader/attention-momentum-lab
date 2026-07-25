"""Deterministic attention-momentum coverage and provenance diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

from aml.tournament_config import DatasetSplit
from aml.tournament_strategies import (
    ConfiguredStrategy,
    attention_momentum_feature_frame,
)

AUDIT_COLUMNS = [
    "split", "symbol", "available_session_count", "processed_session_count",
    "missing_session_count", "signal_count", "executed_trade_count",
    "rejected_signal_count", "first_available_date", "last_available_date",
    "first_signal_date", "last_signal_date", "rows_with_valid_return_feature",
    "rows_with_valid_relative_volume_feature", "rows_with_valid_vwap_feature",
    "rows_with_valid_acceleration_feature", "rows_with_all_required_features",
    "rows_above_return_threshold", "rows_above_relative_volume_threshold",
    "rows_above_vwap_threshold", "rows_above_acceleration_threshold",
    "rows_above_score_threshold", "average_score", "maximum_score",
    "rejection_reason_counts", "warning_codes",
]

DIAGNOSTIC_COLUMNS = [
    "trading_date", "signal_timestamp", "symbol", "split", "proposal_id",
    "source_bar_timestamp", "information_cutoff",
    "raw_return_feature", "relative_volume_feature", "vwap_distance_feature",
    "acceleration_feature", "return_score_component",
    "relative_volume_score_component", "vwap_score_component",
    "acceleration_score_component", "total_score", "eligibility_threshold",
    "eligible", "execution_status", "execution_reason",
]

SESSION_DIAGNOSTIC_COLUMNS = [
    "split", "symbol", "trading_date", "processed", "row_count",
    "rows_with_valid_return_feature", "rows_with_valid_relative_volume_feature",
    "rows_with_valid_vwap_feature", "rows_with_valid_acceleration_feature",
    "rows_with_all_required_features", "rows_above_return_threshold",
    "rows_above_relative_volume_threshold", "rows_above_vwap_threshold",
    "rows_above_acceleration_threshold", "rows_above_score_threshold",
    "score_sum", "score_count", "maximum_score", "warning_codes",
]

_FEATURES = {
    "return": "return_5m",
    "relative_volume": "relative_volume",
    "vwap": "vwap_distance",
    "acceleration": "volume_acceleration",
}


def _codes(values: Iterable[str]) -> str:
    return ";".join(sorted(set(filter(None, values))))


def session_feature_diagnostics(
    bars: pd.DataFrame,
    strategy: ConfiguredStrategy,
    *,
    split: str,
    symbol: str,
    trading_date: str,
    processed: bool,
    exact_elapsed_return: bool = True,
) -> dict[str, Any]:
    """Summarize exact feature availability and threshold passage for one session."""
    frame = attention_momentum_feature_frame(
        bars, strategy, exact_elapsed_return=exact_elapsed_return
    )
    required = list(_FEATURES.values())
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"Unparseable bar timestamps: {symbol} {trading_date}")
    elapsed = timestamps.diff().dt.total_seconds().div(60)
    warnings = []
    if elapsed.dropna().ne(1).any():
        warnings.append("non_contiguous_minute_rows")
    if not processed:
        warnings.append("quality_excluded_session")
    if not exact_elapsed_return:
        warnings.append("legacy_row_return_semantics")
    p = strategy.parameters

    def count(values: pd.Series) -> int:
        return int(values.sum()) if processed else 0

    return {
        "split": split,
        "symbol": symbol,
        "trading_date": trading_date,
        "processed": bool(processed),
        "row_count": len(frame),
        "rows_with_valid_return_feature": count(frame[_FEATURES["return"]].notna()),
        "rows_with_valid_relative_volume_feature": count(frame[_FEATURES["relative_volume"]].notna()),
        "rows_with_valid_vwap_feature": count(frame[_FEATURES["vwap"]].notna()),
        "rows_with_valid_acceleration_feature": count(frame[_FEATURES["acceleration"]].notna()),
        "rows_with_all_required_features": count(frame[required].notna().all(axis=1)),
        "rows_above_return_threshold": count(frame[_FEATURES["return"]].ge(p["return_threshold"])),
        "rows_above_relative_volume_threshold": count(
            frame[_FEATURES["relative_volume"]].ge(p["relative_volume_threshold"])
        ),
        "rows_above_vwap_threshold": count(frame[_FEATURES["vwap"]].ge(p["vwap_threshold"])),
        "rows_above_acceleration_threshold": count(
            frame[_FEATURES["acceleration"]].ge(p["acceleration_threshold"])
        ),
        "rows_above_score_threshold": count(frame["score"].ge(p["eligible_score_threshold"])),
        "score_sum": float(frame["score"].sum()) if processed else 0.0,
        "score_count": int(frame["score"].notna().sum()) if processed else 0,
        "maximum_score": float(frame["score"].max()) if processed and not frame.empty else 0.0,
        "warning_codes": _codes(warnings),
    }


def _metadata(provenance_json: Any) -> Mapping[str, Any]:
    if not isinstance(provenance_json, str):
        return {}
    try:
        value = json.loads(provenance_json)
    except json.JSONDecodeError:
        return {}
    metadata = value.get("signal_metadata", {}) if isinstance(value, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def build_signal_diagnostics(signals: pd.DataFrame) -> pd.DataFrame:
    """Flatten point-in-time attention signal metadata in stable order."""
    selected = signals.loc[signals["strategy_id"].eq("attention_momentum")].copy()
    records = []
    for row in selected.itertuples(index=False):
        metadata = _metadata(row.provenance_json)
        record = {column: getattr(row, column, None) for column in DIAGNOSTIC_COLUMNS}
        for column in DIAGNOSTIC_COLUMNS:
            if column in metadata:
                record[column] = metadata[column]
        records.append(record)
    frame = pd.DataFrame(records, columns=DIAGNOSTIC_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(
            ["split", "symbol", "trading_date", "signal_timestamp", "proposal_id"],
            kind="mergesort",
        ).reset_index(drop=True)
    return frame


def _reason_counts(frame: pd.DataFrame) -> str:
    counts = Counter(
        str(value) if pd.notna(value) and str(value) else "unspecified"
        for value in frame.get("execution_reason", pd.Series(dtype=object))
    )
    return json.dumps(dict(sorted(counts.items())), sort_keys=True, separators=(",", ":"))


def build_attention_audit(
    session_diagnostics: pd.DataFrame,
    signals: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate one deterministic row per split and symbol."""
    if session_diagnostics.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    selected_signals = signals.loc[signals["strategy_id"].eq("attention_momentum")].copy()
    selected_trades = trades.loc[trades["strategy_id"].eq("attention_momentum")].copy()
    records = []
    count_columns = [column for column in SESSION_DIAGNOSTIC_COLUMNS if column.startswith("rows_")]
    for (split, symbol), group in session_diagnostics.groupby(["split", "symbol"], sort=True):
        signal_group = selected_signals.loc[
            selected_signals["split"].eq(split) & selected_signals["symbol"].eq(symbol)
        ]
        trade_group = selected_trades.loc[
            selected_trades["split"].eq(split) & selected_trades["symbol"].eq(symbol)
        ]
        rejected = signal_group.loc[signal_group["execution_status"].eq("rejected")]
        warnings = [code for value in group["warning_codes"] for code in str(value).split(";")]
        if not signal_group.shape[0]:
            warnings.append("zero_signals")
        if (~group["processed"].astype(bool)).any():
            warnings.append("missing_or_quality_excluded_sessions")
        score_count = int(group["score_count"].sum())
        record = {
            "split": split,
            "symbol": symbol,
            "available_session_count": len(group),
            "processed_session_count": int(group["processed"].astype(bool).sum()),
            "missing_session_count": int((~group["processed"].astype(bool)).sum()),
            "signal_count": len(signal_group),
            "executed_trade_count": len(trade_group),
            "rejected_signal_count": len(rejected),
            "first_available_date": str(group["trading_date"].min()),
            "last_available_date": str(group["trading_date"].max()),
            "first_signal_date": "" if signal_group.empty else str(signal_group["trading_date"].min()),
            "last_signal_date": "" if signal_group.empty else str(signal_group["trading_date"].max()),
            "rows_above_score_threshold": int(group["rows_above_score_threshold"].sum()),
            "average_score": float(group["score_sum"].sum() / score_count) if score_count else np.nan,
            "maximum_score": float(group["maximum_score"].max()),
            "rejection_reason_counts": _reason_counts(rejected),
            "warning_codes": _codes(warnings),
        }
        record.update({column: int(group[column].sum()) for column in count_columns})
        records.append(record)
    return pd.DataFrame(records, columns=AUDIT_COLUMNS).sort_values(
        ["split", "symbol"], kind="mergesort"
    ).reset_index(drop=True)


def validate_attention_integrity(
    audit: pd.DataFrame,
    diagnostics: pd.DataFrame,
    splits: Iterable[DatasetSplit],
) -> tuple[str, ...]:
    """Fail on coverage/integrity defects and warn on distribution changes."""
    split_map = {split.name: split for split in splits}
    ordered = sorted(split_map.values(), key=lambda value: value.start)
    for prior, current in pairwise(ordered):
        if current.start <= prior.end:
            raise ValueError(f"Tournament split boundaries overlap: {prior.name}/{current.name}")
    if audit.empty:
        return ()
    if ((audit["available_session_count"] > 0) & (audit["processed_session_count"] == 0)).any():
        raise ValueError("Attention audit found source sessions but zero processed sessions")
    available_rows = audit["rows_with_valid_vwap_feature"].clip(lower=1)
    coverage = audit["rows_with_all_required_features"] / available_rows
    if coverage.lt(0.80).any():
        failed = audit.loc[coverage.lt(0.80), ["split", "symbol"]].to_dict("records")
        raise ValueError(f"Required attention feature coverage collapsed: {failed}")
    ratios = audit.groupby("split").agg(
        available=("available_session_count", "sum"), processed=("processed_session_count", "sum")
    )
    ratios["ratio"] = ratios["processed"] / ratios["available"]
    if len(ratios) > 1 and ratios["ratio"].max() - ratios["ratio"].min() > 0.10:
        raise ValueError("Materially different attention input coverage across splits")
    if not diagnostics.empty:
        parsed = pd.to_datetime(diagnostics["signal_timestamp"], utc=True, errors="coerce")
        if parsed.isna().any():
            raise ValueError("Serialized attention signal timestamps cannot be parsed")
        sources = pd.to_datetime(
            diagnostics["source_bar_timestamp"], utc=True, errors="coerce"
        )
        cutoffs = pd.to_datetime(
            diagnostics["information_cutoff"], utc=True, errors="coerce"
        )
        if sources.isna().any() or cutoffs.isna().any():
            raise ValueError("Attention signal provenance timestamps cannot be parsed")
        if (sources >= parsed).any() or (cutoffs > parsed).any():
            raise ValueError("Attention signal feature provenance uses a future timestamp")
        dates = pd.to_datetime(diagnostics["trading_date"], errors="coerce").dt.date
        for split_name, group in diagnostics.groupby("split", sort=True):
            if split_name not in split_map:
                raise ValueError(f"Signal uses unknown split: {split_name}")
            boundary = split_map[split_name]
            selected_dates = dates.loc[group.index]
            if ((selected_dates < boundary.start) | (selected_dates > boundary.end)).any():
                raise ValueError(f"Attention signal dates fall outside split {split_name}")
        if diagnostics["eligible"].notna().any() and not diagnostics["eligible"].fillna(False).astype(bool).all():
            raise ValueError("Ineligible attention signal was serialized")
        feature_columns = [
            "raw_return_feature", "relative_volume_feature",
            "vwap_distance_feature", "acceleration_feature",
        ]
        if diagnostics[feature_columns].isna().any().any():
            raise ValueError("Attention signal was emitted before feature warm-up completed")
    if (audit["signal_count"] != audit["executed_trade_count"] + audit["rejected_signal_count"]).any():
        raise ValueError("Attention signal/trade/rejection counts do not reconcile")
    if (audit["signal_count"] != audit["rows_above_score_threshold"]).any():
        raise ValueError("Attention eligible-row and serialized-signal counts do not reconcile")
    warnings = []
    active = audit.assign(active=audit["signal_count"].gt(0)).groupby("split")["active"].sum()
    if len(active) > 1 and active.max() >= max(3, 2 * max(1, int(active.min()))):
        warnings.append("active_symbol_distribution_shift")
    return tuple(sorted(warnings))
