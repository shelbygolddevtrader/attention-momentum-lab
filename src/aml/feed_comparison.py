"""Deterministic, feed-isolated comparison of historical minute bars."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import pandas as pd

from aml.batch_evaluation import QualityPolicy
from aml.market_halts import CompletenessMode, HaltSchedule
from aml.portfolio_artifacts import canonical_json_bytes, file_sha256


COMPARISON_SCHEMA_VERSION = "1.0.0"
FEEDS = ("iex", "sip")
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
ROW_COLUMNS = (
    "timestamp",
    *(f"{feed}_{column}" for feed in FEEDS for column in OHLCV_COLUMNS),
    "ohlcv_differs",
)


def _validated_frame(frame: pd.DataFrame, feed: str) -> pd.DataFrame:
    missing = {"timestamp", *OHLCV_COLUMNS}.difference(frame.columns)
    if missing:
        raise ValueError(
            f"{feed.upper()} bars are missing comparison columns: "
            + ", ".join(sorted(missing))
        )
    value = frame.loc[:, ["timestamp", *OHLCV_COLUMNS]].copy()
    value["timestamp"] = pd.to_datetime(value["timestamp"], errors="raise")
    if value["timestamp"].dt.tz is None:
        raise ValueError(f"{feed.upper()} timestamps must be timezone-aware")
    for column in OHLCV_COLUMNS:
        value[column] = pd.to_numeric(value[column], errors="raise")
    return value.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def _dataset_metrics(
    frame: pd.DataFrame,
    expected_minutes: pd.DatetimeIndex,
    quality_policy: QualityPolicy,
    halt_schedule: HaltSchedule,
    completeness_mode: CompletenessMode,
) -> dict[str, Any]:
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    duplicates = int(timestamps.duplicated(keep=False).sum())
    unique_observed = timestamps.drop_duplicates()
    expected = pd.DatetimeIndex(expected_minutes)
    if expected.tz is None:
        raise ValueError("Expected market-calendar minutes must be timezone-aware")
    expected = expected.tz_convert(timestamps.tz)
    raw_missing = expected.difference(unique_observed.intersection(expected))
    effective_expected = expected
    if completeness_mode is CompletenessMode.HALT_AWARE and len(
        halt_schedule.full_halt_minutes
    ):
        effective_expected = expected.difference(
            halt_schedule.full_halt_minutes.tz_convert(expected.tz)
        )
    effective_missing = effective_expected.difference(
        unique_observed.intersection(effective_expected)
    )
    missing_percentage = (
        len(effective_missing) / len(effective_expected)
        if len(effective_expected)
        else None
    )
    passes = (
        duplicates == 0
        and missing_percentage is not None
        and missing_percentage
        <= quality_policy.usable_session_maximum_missing_percentage
    )
    return {
        "row_count": len(frame),
        "first_timestamp": (
            frame["timestamp"].iloc[0].isoformat() if not frame.empty else None
        ),
        "last_timestamp": (
            frame["timestamp"].iloc[-1].isoformat() if not frame.empty else None
        ),
        "duplicate_timestamp_count": duplicates,
        "missing_minute_count": len(raw_missing),
        "effective_missing_minute_count": len(effective_missing),
        "effective_missing_percentage": missing_percentage,
        "total_volume": int(frame["volume"].sum()),
        "passes_existing_completeness_checks": passes,
    }


def compare_historical_feeds(
    iex_bars: pd.DataFrame,
    sip_bars: pd.DataFrame,
    *,
    symbol: str,
    trading_date: str,
    expected_minutes: pd.DatetimeIndex,
    quality_policy: QualityPolicy,
    halt_schedule: HaltSchedule,
    completeness_mode: CompletenessMode | str = CompletenessMode.HALT_AWARE,
    input_hashes: dict[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Return deterministic summary and timestamp-aligned OHLCV differences."""
    mode = CompletenessMode(completeness_mode)
    frames = {
        "iex": _validated_frame(iex_bars, "iex"),
        "sip": _validated_frame(sip_bars, "sip"),
    }
    aligned = {
        feed: frame.drop_duplicates("timestamp", keep="first")
        for feed, frame in frames.items()
    }
    merged = aligned["iex"].rename(
        columns={column: f"iex_{column}" for column in OHLCV_COLUMNS}
    ).merge(
        aligned["sip"].rename(
            columns={column: f"sip_{column}" for column in OHLCV_COLUMNS}
        ),
        on="timestamp",
        how="outer",
        validate="one_to_one",
        sort=True,
    )
    differences = pd.Series(False, index=merged.index)
    for column in OHLCV_COLUMNS:
        differences |= merged[f"iex_{column}"].ne(merged[f"sip_{column}"])
    merged["ohlcv_differs"] = differences
    merged = merged.loc[:, ROW_COLUMNS].sort_values(
        "timestamp", kind="mergesort"
    ).reset_index(drop=True)
    hashes = dict(sorted((input_hashes or {}).items()))
    summary = {
        "status": "completed",
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "provider": "alpaca",
        "symbol": symbol.upper(),
        "trading_date": str(trading_date),
        "requested_feeds": list(FEEDS),
        "completeness_mode": mode.value,
        "quality_policy_fingerprint": quality_policy.fingerprint(),
        "input_hashes": hashes,
        "feeds": {
            feed: _dataset_metrics(
                frame, expected_minutes, quality_policy, halt_schedule, mode
            )
            for feed, frame in frames.items()
        },
        "rows_where_ohlcv_values_differ": int(merged["ohlcv_differs"].sum()),
    }
    identity = {
        key: value for key, value in summary.items() if key != "status"
    }
    summary["comparison_id"] = hashlib.sha256(
        canonical_json_bytes(identity)
    ).hexdigest()[:20]
    return summary, merged


def _comparison_csv_bytes(rows: pd.DataFrame) -> bytes:
    return rows.loc[:, ROW_COLUMNS].to_csv(
        index=False,
        lineterminator="\n",
        na_rep="",
        float_format="%.17g",
    ).encode("utf-8")


def write_feed_comparison(root: Path, summary: dict, rows: pd.DataFrame) -> Path:
    """Atomically publish an immutable comparison with metadata written last."""
    comparison_id = summary.get("comparison_id")
    if (
        not isinstance(comparison_id, str)
        or len(comparison_id) != 20
        or any(character not in "0123456789abcdef" for character in comparison_id)
    ):
        raise ValueError("Invalid deterministic comparison ID")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / comparison_id
    if destination.exists():
        metadata, _ = load_feed_comparison(destination)
        expected_summary = dict(summary)
        existing_summary = dict(metadata)
        existing_summary.pop("artifact_hashes", None)
        if existing_summary != expected_summary or (
            destination / "ohlcv_differences.csv"
        ).read_bytes() != _comparison_csv_bytes(rows):
            raise FileExistsError(
                f"Feed comparison ID conflicts with existing content: {destination}"
            )
        return destination
    lock_path = root / f".{comparison_id}.lock"
    try:
        lock_descriptor = os.open(
            lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
    except FileExistsError as exc:
        raise FileExistsError(
            f"Feed comparison is locked or already publishing: {comparison_id}"
        ) from exc
    os.close(lock_descriptor)
    temporary = None
    try:
        if destination.exists():
            raise FileExistsError(
                f"Completed feed comparison already exists: {destination}"
            )
        temporary = Path(tempfile.mkdtemp(prefix=f".{comparison_id}.", dir=root))
        csv_content = _comparison_csv_bytes(rows)
        csv_path = temporary / "ohlcv_differences.csv"
        with csv_path.open("xb") as handle:
            handle.write(csv_content)
            handle.flush()
            os.fsync(handle.fileno())
        finalized = dict(summary)
        finalized["artifact_hashes"] = {
            "ohlcv_differences.csv": hashlib.sha256(csv_content).hexdigest()
        }
        metadata_path = temporary / "comparison.json"
        with metadata_path.open("xb") as handle:
            handle.write(canonical_json_bytes(finalized))
            handle.flush()
            os.fsync(handle.fileno())
        directory_descriptor = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        os.rename(temporary, destination)
        root_descriptor = os.open(root, os.O_RDONLY)
        try:
            os.fsync(root_descriptor)
        finally:
            os.close(root_descriptor)
    except Exception:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        lock_path.unlink(missing_ok=True)
    return destination


def load_feed_comparison(directory: Path) -> tuple[dict, pd.DataFrame]:
    """Load only a completed comparison whose fixed artifacts still hash."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Feed comparison directory is absent or unsafe")
    expected_files = {"comparison.json", "ohlcv_differences.csv"}
    if {path.name for path in directory.iterdir()} != expected_files:
        raise ValueError("Feed comparison is incomplete or contains unexpected files")
    metadata = json.loads((directory / "comparison.json").read_text(encoding="utf-8"))
    if metadata.get("status") != "completed":
        raise ValueError("Feed comparison is not marked completed")
    if metadata.get("schema_version") != COMPARISON_SCHEMA_VERSION:
        raise ValueError("Feed comparison schema is incompatible")
    if metadata.get("requested_feeds") != list(FEEDS):
        raise ValueError("Feed comparison does not record explicit IEX and SIP feeds")
    if metadata.get("comparison_id") != directory.name:
        raise ValueError("Feed comparison ID does not match its directory")
    expected_hash = metadata.get("artifact_hashes", {}).get("ohlcv_differences.csv")
    if expected_hash != file_sha256(directory / "ohlcv_differences.csv"):
        raise ValueError("Feed comparison artifact hash mismatch")
    rows = pd.read_csv(directory / "ohlcv_differences.csv")
    return metadata, rows
