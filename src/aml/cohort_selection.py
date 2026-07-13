"""Point-in-time selection and immutable audits for Research Cohort V001."""

from datetime import date, datetime, time
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


NY = ZoneInfo("America/New_York")
PREMARKET_OPEN = time(4, 0)
SELECTION_CUTOFF = time(9, 25)

SELECTION_INPUT_COLUMNS = (
    "symbol", "trading_date", "prerequisite_status", "exclusion_reason",
    "previous_close", "median_dollar_volume_20", "atr_pct_20",
    "median_premarket_volume_20", "premarket_volume_inputs_20",
    "daily_dollar_volume_inputs_20", "true_range_inputs_20",
    "premarket_last_price", "premarket_gap", "premarket_share_volume", "premarket_dollar_volume",
    "premarket_relative_volume", "premarket_baseline_valid", "data_feed",
    "dataset_vintage", "corporate_action_status", "corporate_action_source",
    "corporate_action_effective_date", "latest_input_timestamp",
)

FORBIDDEN_OUTCOME_COLUMNS = {
    "forward_return", "net_pnl", "gross_pnl", "exit_price", "exit_reason",
    "mfe", "mae", "trade_outcome",
}

SELECTION_OUTPUT_COLUMNS = (
    *SELECTION_INPUT_COLUMNS,
    "universe_considered", "event_qualifies", "selected_event", "selected_control",
    "event_rank", "matched_event_symbol", "matched_group_id", "control_distance",
    "selection_status", "status_detail", "gap_direction", "selection_timestamp",
    "observation_cutoff",
)


def selection_audit_path(
    root: Path,
    cohort_id: str,
    trading_date: date,
) -> Path:
    """Return the canonical, versionable path for a frozen daily audit."""
    if not cohort_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in cohort_id):
        raise ValueError("cohort_id must be a safe, non-empty identifier")
    return Path(root) / "data" / "selection_audits" / cohort_id / f"{trading_date}.csv"


def _outcome_columns(columns: pd.Index | list[str] | tuple[str, ...]) -> set[str]:
    forbidden: set[str] = set()
    prefixes = (
        "forward_", "future_", "return_", "mfe", "mae", "pnl", "exit_",
        "target_", "stop_",
    )
    for column in columns:
        normalized = str(column).strip().lower()
        if (
            normalized in FORBIDDEN_OUTCOME_COLUMNS
            or normalized.startswith(prefixes)
            or "outcome" in normalized
        ):
            forbidden.add(str(column))
    return forbidden


def _exclusive_publish_text(path: Path, content: str) -> None:
    """Atomically publish text without replacing an existing audit file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def cutoff_timestamp(trading_date: date) -> pd.Timestamp:
    """Return the registered 09:25 ET exclusive selection cutoff."""
    return pd.Timestamp(datetime.combine(trading_date, SELECTION_CUTOFF, NY))


def compute_premarket_metrics(
    bars: pd.DataFrame,
    trading_date: date,
    previous_close: float,
    prior_20_premarket_volumes: Iterable[float],
) -> dict[str, object]:
    """Calculate cutoff-safe metrics from 04:00 <= timestamp < 09:25.

    For minute bars, ``bar_vwap * volume`` is the provider-aggregated equivalent
    of summing trade price times trade size within each minute.
    """
    if not np.isfinite(previous_close) or previous_close <= 0:
        raise ValueError("previous_close must be positive")
    baseline = pd.Series(prior_20_premarket_volumes, dtype=float)
    if (
        len(baseline) != 20
        or baseline.isna().any()
        or not np.isfinite(baseline).all()
        or (baseline < 0).any()
    ):
        raise ValueError("Exactly 20 non-missing prior premarket volumes are required")
    if missing := {"timestamp", "close", "volume", "bar_vwap"}.difference(bars.columns):
        raise ValueError(f"Missing premarket columns: {', '.join(sorted(missing))}")
    frame = bars.copy()
    if frame.empty:
        frame["timestamp"] = pd.Series(pd.DatetimeIndex([], tz=NY), index=frame.index)
    else:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        if not isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype):
            raise ValueError("Premarket timestamps must be timezone-aware")
        frame["timestamp"] = frame["timestamp"].dt.tz_convert(NY)
    for column in ("close", "volume", "bar_vwap"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if (
        frame[["close", "volume", "bar_vwap"]].isna().any().any()
        or not np.isfinite(frame[["close", "volume", "bar_vwap"]]).all().all()
        or frame["close"].le(0).any()
        or frame["bar_vwap"].le(0).any()
        or frame["volume"].lt(0).any()
    ):
        raise ValueError("Premarket bars contain invalid price or volume values")
    start = pd.Timestamp(datetime.combine(trading_date, PREMARKET_OPEN, NY))
    cutoff = cutoff_timestamp(trading_date)
    valid = frame["timestamp"].ge(start) & frame["timestamp"].lt(cutoff)
    if not valid.all():
        raise ValueError("Premarket selection input contains a bar outside [04:00, 09:25)")
    if frame["timestamp"].duplicated().any() or not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Premarket bars must be unique and chronological")
    median_volume = float(baseline.median())
    if median_volume <= 0:
        raise ValueError("Median prior premarket volume must be positive")
    share_volume = float(frame["volume"].sum()) if not frame.empty else 0.0
    dollar_volume = float((frame["bar_vwap"] * frame["volume"]).sum()) if not frame.empty else 0.0
    last_price = float(frame.iloc[-1]["close"]) if not frame.empty else np.nan
    gap = last_price / previous_close - 1 if not frame.empty else np.nan
    return {
        "premarket_last_price": last_price,
        "premarket_gap": gap,
        "gap_direction": "positive" if gap > 0 else ("negative" if gap < 0 else "flat") if not pd.isna(gap) else "no_trade",
        "premarket_share_volume": share_volume,
        "premarket_dollar_volume": dollar_volume,
        "premarket_relative_volume": share_volume / median_volume,
        "premarket_baseline_valid": True,
        "median_premarket_volume_20": median_volume,
        "observation_cutoff": cutoff.isoformat(),
    }


def _base_eligibility_reason(row) -> str:
    if row.prerequisite_status != "verified":
        return row.exclusion_reason or "prerequisites_not_verified"
    if row.corporate_action_status != "verified":
        return "corporate_action_not_verified"
    if not bool(row.premarket_baseline_valid):
        return "premarket_baseline_invalid"
    if (
        pd.isna(row.median_premarket_volume_20)
        or float(row.median_premarket_volume_20) <= 0
    ):
        return "premarket_baseline_invalid"
    if pd.isna(row.previous_close) or not 2 <= float(row.previous_close) <= 100:
        return "previous_close_outside_2_to_100"
    if pd.isna(row.median_dollar_volume_20) or float(row.median_dollar_volume_20) < 10_000_000:
        return "median_dollar_volume_below_10m"
    if pd.isna(row.atr_pct_20) or float(row.atr_pct_20) <= 0:
        return "atr20_invalid"
    for field in (
        "premarket_volume_inputs_20", "daily_dollar_volume_inputs_20",
        "true_range_inputs_20",
    ):
        try:
            values = json.loads(getattr(row, field))
            numeric = pd.Series(values, dtype=float)
        except (TypeError, ValueError, json.JSONDecodeError):
            return f"{field}_invalid"
        if (
            len(values) != 20
            or numeric.isna().any()
            or not np.isfinite(numeric).all()
            or numeric.lt(0).any()
        ):
            return f"{field}_invalid"
    return ""


def build_daily_selection_audit(metrics: pd.DataFrame) -> pd.DataFrame:
    """Apply the preregistered event and control rules deterministically."""
    if forbidden := _outcome_columns(metrics.columns):
        raise ValueError(
            f"Selection inputs contain outcome columns: {', '.join(sorted(forbidden))}"
        )
    required = set(SELECTION_INPUT_COLUMNS)
    if missing := required.difference(metrics.columns):
        raise ValueError(f"Missing selection inputs: {', '.join(sorted(missing))}")
    if unexpected := set(metrics.columns).difference(required):
        raise ValueError(f"Unexpected selection inputs: {', '.join(sorted(unexpected))}")
    frame = (
        metrics.loc[:, SELECTION_INPUT_COLUMNS].copy()
        .sort_values("symbol", kind="mergesort")
        .reset_index(drop=True)
    )
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    if frame["symbol"].str.strip().eq("").any():
        raise ValueError("Daily universe symbols must be non-empty")
    if len(set(frame["trading_date"].astype(str))) != 1:
        raise ValueError("A daily selection audit must contain exactly one trading date")
    if frame["symbol"].duplicated().any():
        raise ValueError("Daily universe symbols must be unique")
    if not frame["data_feed"].eq("sip").all():
        raise ValueError("Research Cohort V001 selection requires SIP inputs")
    for provenance_column in (
        "dataset_vintage", "corporate_action_source", "latest_input_timestamp"
    ):
        values = frame[provenance_column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ValueError(f"Selection inputs require {provenance_column} provenance")
    trading_date = str(frame.iloc[0]["trading_date"])
    cutoff = cutoff_timestamp(date.fromisoformat(trading_date))
    latest = pd.to_datetime(frame["latest_input_timestamp"], utc=True, errors="coerce")
    if latest.isna().any() or not latest.lt(cutoff.tz_convert("UTC")).all():
        raise ValueError("Selection inputs must be timestamped strictly before 09:25 ET")

    reasons = [_base_eligibility_reason(row) for row in frame.itertuples(index=False)]
    frame["universe_considered"] = True
    frame["exclusion_reason"] = reasons
    eligible = pd.Series([not reason for reason in reasons], index=frame.index)
    event_qualifies = (
        eligible
        & frame["premarket_gap"].ge(0.08)
        & frame["premarket_dollar_volume"].ge(1_000_000)
        & frame["premarket_relative_volume"].ge(5.0)
    )
    frame["event_qualifies"] = event_qualifies
    frame["selected_event"] = False
    frame["selected_control"] = False
    frame["event_rank"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["matched_event_symbol"] = ""
    frame["matched_group_id"] = ""
    frame["control_distance"] = np.nan
    frame["selection_status"] = "excluded"
    frame["status_detail"] = frame["exclusion_reason"]

    event_indices = (
        frame.loc[event_qualifies]
        .sort_values(["premarket_dollar_volume", "symbol"], ascending=[False, True], kind="mergesort")
        .head(5).index.tolist()
    )
    used_controls: set[int] = set()
    for rank, event_index in enumerate(event_indices, start=1):
        event = frame.loc[event_index]
        group_id = f"{trading_date}-E{rank:02d}-{event.symbol}"
        frame.loc[event_index, ["selected_event", "event_rank", "matched_group_id", "selection_status", "status_detail"]] = [
            True, rank, group_id, "selected_event", "",
        ]
        pool = frame.loc[eligible & ~event_qualifies & ~frame.index.isin(used_controls)].copy()
        if not pool.empty:
            price_ratio = pool["previous_close"] / float(event.previous_close)
            liquidity_ratio = pool["median_dollar_volume_20"] / float(event.median_dollar_volume_20)
            atr_ratio = pool["atr_pct_20"] / float(event.atr_pct_20)
            pool = pool.loc[
                price_ratio.between(0.7, 1.3)
                & liquidity_ratio.between(0.5, 2.0)
                & atr_ratio.between(0.7, 1.3)
            ].copy()
        if not pool.empty:
            pool["control_distance"] = (
                np.log(pool["previous_close"] / float(event.previous_close)).abs()
                + np.log(pool["median_dollar_volume_20"] / float(event.median_dollar_volume_20)).abs()
                + (pool["atr_pct_20"] - float(event.atr_pct_20)).abs() / float(event.atr_pct_20)
            )
            chosen = pool.sort_values(["control_distance", "symbol"], kind="mergesort").head(2)
        else:
            chosen = pool
        for control_index, control in chosen.iterrows():
            used_controls.add(control_index)
            frame.loc[control_index, [
                "selected_control", "matched_event_symbol", "matched_group_id",
                "control_distance", "selection_status", "status_detail",
            ]] = [True, event.symbol, group_id, control.control_distance, "selected_control", ""]
        if len(chosen) < 2:
            frame.loc[event_index, "status_detail"] = f"control_shortage:{2 - len(chosen)}"

    below_cap = event_qualifies & ~frame["selected_event"]
    frame.loc[below_cap, ["selection_status", "status_detail"]] = [
        "qualified_below_daily_cap", "daily_event_cap",
    ]
    eligible_unselected = eligible & ~event_qualifies & ~frame["selected_control"]
    frame.loc[eligible_unselected, ["selection_status", "status_detail"]] = [
        "eligible_not_selected", "not_selected_as_control",
    ]
    frame["gap_direction"] = np.select(
        [frame["premarket_gap"].gt(0), frame["premarket_gap"].lt(0), frame["premarket_gap"].eq(0)],
        ["positive", "negative", "flat"],
        default="no_trade",
    )
    day = date.fromisoformat(trading_date)
    frame["selection_timestamp"] = cutoff_timestamp(day).isoformat()
    frame["observation_cutoff"] = cutoff_timestamp(day).isoformat()
    return (
        frame.loc[:, SELECTION_OUTPUT_COLUMNS]
        .sort_values("symbol", kind="mergesort")
        .reset_index(drop=True)
    )


def freeze_selection_audit(
    audit: pd.DataFrame,
    path: Path,
    *,
    frozen_at: pd.Timestamp | str,
    protocol_version: str = "v0.1",
) -> tuple[Path, Path]:
    """Atomically freeze an audit after selection and before outcome evaluation.

    ``frozen_at`` is the actual artifact-generation time, not a fabricated
    historical market timestamp. Historical backfills may therefore be frozen
    long after the session, but downstream evaluation must consume only the
    already-frozen artifact.
    """
    forbidden = _outcome_columns(audit.columns)
    if forbidden:
        raise ValueError(f"Selection audit contains outcome columns: {', '.join(sorted(forbidden))}")
    required = set(SELECTION_OUTPUT_COLUMNS)
    if missing := required.difference(audit.columns):
        raise ValueError(f"Selection audit is missing columns: {', '.join(sorted(missing))}")
    if unexpected := set(audit.columns).difference(required):
        raise ValueError(f"Selection audit contains unexpected columns: {', '.join(sorted(unexpected))}")
    frame = (
        audit.loc[:, SELECTION_OUTPUT_COLUMNS].copy()
        .sort_values("symbol", kind="mergesort")
        .reset_index(drop=True)
    )
    days = set(frame["trading_date"].astype(str))
    if len(days) != 1:
        raise ValueError("Frozen selection audit must contain one trading date")
    day = date.fromisoformat(next(iter(days)))
    cutoff = cutoff_timestamp(day)
    frozen = pd.Timestamp(frozen_at)
    if frozen.tzinfo is None:
        raise ValueError("frozen_at must be timezone-aware")
    frozen = frozen.tz_convert(NY)
    if frozen < cutoff:
        raise ValueError("Selection audit cannot be frozen before 09:25 ET")
    if not frame["observation_cutoff"].eq(cutoff.isoformat()).all():
        raise ValueError("Selection audit observation cutoff is not the registered 09:25 ET cutoff")
    path = Path(path)
    metadata_path = path.with_suffix(".metadata.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        lock_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError("Selection audit is locked or already being frozen") from exc
    os.close(lock_descriptor)
    created: list[Path] = []
    content = frame.to_csv(index=False, lineterminator="\n")
    try:
        if path.exists() or metadata_path.exists():
            raise FileExistsError("Selection audit is immutable and already exists")
        _exclusive_publish_text(path, content)
        created.append(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = {
            "status": "frozen",
            "protocol_version": protocol_version,
            "trading_date": str(day),
            "selection_timestamp": cutoff.isoformat(),
            "observation_cutoff_exclusive": cutoff.isoformat(),
            "frozen_at": frozen.isoformat(),
            "record_count": len(frame),
            "selected_event_count": int(frame["selected_event"].sum()),
            "selected_control_count": int(frame["selected_control"].sum()),
            "audit_file": path.name,
            "audit_sha256": digest,
        }
        _exclusive_publish_text(
            metadata_path, json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )
        created.append(metadata_path)
    except Exception:
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise
    finally:
        lock_path.unlink(missing_ok=True)
    return path, metadata_path
