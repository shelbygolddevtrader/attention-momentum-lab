"""Fail-closed, strategy-independent validation of quarantined vendor samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_halts import load_verified_halts


CHECKER_SCHEMA_VERSION = "1.0.0"
NY = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")
MISSING_MINUTE_SEMANTICS = {
    "omitted_when_no_eligible_trade",
    "explicit_missing_status_records",
}
ZERO_TRADE_MINUTE_SEMANTICS = {
    "explicit_zero_volume_bar",
    "zero_trade_minutes_not_emitted_and_not_equated_with_delivery_failure",
    "separate_zero_trade_status_records",
}
MARKET_COLUMNS = (
    "timestamp", "symbol", "segment", "open", "high", "low", "close", "volume",
)


class SampleProfile(str, Enum):
    """Supported, intentionally separate sample contracts."""

    MARKET_DATA = "market_data"
    REFERENCE_DATA = "reference_data"


@dataclass(frozen=True)
class Finding:
    """One deterministic validation observation."""

    code: str
    severity: str
    message: str
    context: Mapping[str, Any]


@dataclass(frozen=True)
class AcceptanceResult:
    """Machine-readable result; acceptance requires technical and legal passes."""

    schema_version: str
    run_id: str
    profile: str
    provider: str
    sample_id: str
    accepted: bool
    technical_pass: bool
    licensing_pass: bool
    findings: tuple[Finding, ...]
    input_hashes: Mapping[str, str]
    summary: Mapping[str, Any]


def file_sha256(path: Path) -> str:
    """Hash finalized local sample bytes."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_input_hash(path: Path, label: str) -> str:
    if path.is_file() and not _has_symlink_component(path):
        try:
            return file_sha256(path)
        except OSError:
            pass
    return hashlib.sha256(f"invalid:{label}".encode()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _has_symlink_component(path: Path) -> bool:
    """Return whether any existing component in an absolute path is a symlink."""

    absolute = Path(path).absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            return True
    return False


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or _has_symlink_component(path):
        raise ValueError(f"{label} must be a regular local file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is malformed JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _sample_file(manifest_path: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a relative sample file path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} cannot escape the sample directory")
    root = manifest_path.parent.resolve()
    unresolved = manifest_path.parent / relative
    current = manifest_path.parent
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f"{label} cannot traverse a symlink")
    resolved = unresolved.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"{label} escapes the sample directory")
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist: {relative}")
    return resolved


def _finding(
    findings: list[Finding], code: str, severity: str, message: str, **context: Any
) -> None:
    findings.append(Finding(code, severity, message, dict(sorted(context.items()))))


def _require_text(
    manifest: Mapping[str, Any],
    field: str,
    findings: list[Finding],
    *,
    prefix: str = "manifest",
) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        _finding(findings, f"{prefix}.{field}", "error", f"Missing {field} evidence")
        return ""
    normalized = value.strip()
    if normalized.lower().startswith(("replace_", "yyyy-")):
        _finding(findings, f"{prefix}.{field}", "error", f"Placeholder is not evidence for {field}")
    return normalized


def _required_fields(
    manifest: Mapping[str, Any], fields: tuple[str, ...], findings: list[Finding]
) -> None:
    for field in fields:
        if field not in manifest:
            _finding(findings, f"manifest.{field}", "error", f"Missing required field: {field}")


def _exact_fields(
    value: Mapping[str, Any], fields: tuple[str, ...], findings: list[Finding], label: str
) -> None:
    """Reject undeclared fields so schema drift cannot pass silently."""

    observed = set(value)
    expected = set(fields)
    if observed != expected:
        _finding(
            findings,
            f"{label}.schema",
            "error",
            f"{label} fields must match the versioned schema exactly",
            missing=sorted(expected.difference(observed)),
            unexpected=sorted(observed.difference(expected)),
        )


def _require_safe_identifier(
    manifest: Mapping[str, Any], field: str, findings: list[Finding]
) -> None:
    value = _require_text(manifest, field, findings)
    if value and not _SAFE.fullmatch(value):
        _finding(
            findings,
            f"manifest.{field}.format",
            "error",
            f"{field} must be a machine-independent safe identifier",
        )


def _parse_timestamp(
    value: Any, label: str, findings: list[Finding], *, optional: bool = False
) -> pd.Timestamp | None:
    if optional and (value is None or (isinstance(value, str) and not value.strip())):
        return None
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        timestamp = pd.NaT
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        _finding(findings, f"timestamp.{label}", "error", f"{label} must be timezone-aware")
        return None
    return timestamp.as_unit("ns")


def _validate_declared_hashes(
    manifest: Mapping[str, Any], files: Mapping[str, Path], findings: list[Finding]
) -> dict[str, str]:
    declared = manifest.get("source_sha256")
    actual: dict[str, str] = {}
    if not isinstance(declared, dict):
        _finding(findings, "hash.manifest", "error", "source_sha256 must map every logical file to SHA-256")
        declared = {}
    if set(declared) != set(files):
        _finding(
            findings,
            "hash.coverage",
            "error",
            "Declared hashes must cover exactly the referenced sample files",
            declared=sorted(declared),
            expected=sorted(files),
        )
    for logical_name, path in sorted(files.items()):
        try:
            digest = file_sha256(path)
        except OSError as exc:
            digest = hashlib.sha256(
                f"unreadable:{logical_name}".encode()
            ).hexdigest()
            _finding(
                findings,
                f"hash.{logical_name}.unreadable",
                "error",
                f"Sample file cannot be hashed: {type(exc).__name__}",
            )
        actual[logical_name] = digest
        if declared.get(logical_name) != digest:
            _finding(
                findings,
                f"hash.{logical_name}",
                "error",
                "Declared sample hash does not match finalized bytes",
            )
    return actual


def _market_files(
    manifest_path: Path, manifest: Mapping[str, Any], findings: list[Finding]
) -> dict[str, Path]:
    try:
        return {"bars": _sample_file(manifest_path, manifest.get("bars_file"), "bars_file")}
    except ValueError as exc:
        _finding(findings, "market.bars_file", "error", str(exc))
        return {}


def _validate_market_manifest(
    manifest: Mapping[str, Any], findings: list[Finding]
) -> tuple[date | None, pd.Timestamp | None, pd.Timestamp | None]:
    required = (
        "schema_version", "profile", "provider", "sample_id", "bars_file",
        "trading_date", "expected_symbols", "requested_feed",
        "consolidated_sip_asserted", "feed_identity_evidence_reference",
        "timeframe", "timestamp_timezone", "interval_label",
        "premarket_start_inclusive", "premarket_end_exclusive",
        "premarket_status_by_symbol", "regular_start_inclusive",
        "regular_end_exclusive",
        "regular_calendar_id", "adjustment_semantics",
        "adjustment_policy_reference", "delivery_complete_asserted",
        "missing_minute_semantics", "zero_trade_minute_semantics",
        "interpolation_performed", "interpolation_policy_reference",
        "condition_policy_reference", "correction_policy_reference",
        "pagination_complete", "page_count", "page_record_counts",
        "delivered_record_count", "delivery_id", "release_id", "dataset_vintage",
        "source_sha256",
    )
    _required_fields(manifest, required, findings)
    _exact_fields(manifest, required, findings, "manifest")
    for field in (
        "provider", "sample_id", "feed_identity_evidence_reference",
        "timestamp_timezone", "adjustment_policy_reference",
        "missing_minute_semantics", "zero_trade_minute_semantics",
        "interpolation_policy_reference",
        "condition_policy_reference", "correction_policy_reference", "delivery_id",
        "release_id", "dataset_vintage",
    ):
        _require_text(manifest, field, findings)
    for field in ("provider", "sample_id", "delivery_id", "release_id", "dataset_vintage"):
        _require_safe_identifier(manifest, field, findings)
    try:
        ZoneInfo(str(manifest.get("timestamp_timezone")))
    except (KeyError, ValueError):
        _finding(findings, "market.timestamp_timezone", "error", "timestamp_timezone must be a valid IANA zone")
    if manifest.get("schema_version") != CHECKER_SCHEMA_VERSION:
        _finding(findings, "manifest.schema_version", "error", "Unsupported market manifest schema")
    if manifest.get("profile") != SampleProfile.MARKET_DATA.value:
        _finding(findings, "manifest.profile", "error", "Manifest profile must be market_data")
    if str(manifest.get("requested_feed", "")).lower() != "sip" or manifest.get("consolidated_sip_asserted") is not True:
        _finding(findings, "market.feed", "error", "Consolidated SIP must be explicitly requested and asserted")
    if manifest.get("timeframe") != "1Min" or manifest.get("interval_label") != "left":
        _finding(findings, "market.interval", "error", "Bars must be left-labeled one-minute intervals")
    if manifest.get("regular_calendar_id") != "XNYS":
        _finding(findings, "market.calendar", "error", "regular_calendar_id must be XNYS")
    if manifest.get("adjustment_semantics") not in {"unadjusted", "adjusted_all"}:
        _finding(findings, "market.adjustment", "error", "Adjustment semantics must be unadjusted or adjusted_all")
    if manifest.get("delivery_complete_asserted") is not True:
        _finding(findings, "market.delivery_complete", "error", "Complete bounded delivery must be asserted")
    if manifest.get("interpolation_performed") is not False:
        _finding(findings, "market.interpolation", "error", "Vendor sample bars must not be filled or interpolated")
    if manifest.get("missing_minute_semantics") == manifest.get("zero_trade_minute_semantics"):
        _finding(findings, "market.missing_vs_zero", "error", "Missing and zero-trade semantics must be distinguishable")
    if manifest.get("missing_minute_semantics") not in MISSING_MINUTE_SEMANTICS:
        _finding(findings, "market.missing_semantics", "error", "Unsupported or unresolved missing-minute semantics")
    if manifest.get("zero_trade_minute_semantics") not in ZERO_TRADE_MINUTE_SEMANTICS:
        _finding(findings, "market.zero_trade_semantics", "error", "Unsupported or unresolved zero-trade semantics")
    if manifest.get("pagination_complete") is not True:
        _finding(findings, "market.pagination", "error", "Pagination or bulk delivery must be asserted complete")
    page_count = manifest.get("page_count")
    if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1:
        _finding(findings, "market.page_count", "error", "page_count must be a positive integer")
    page_counts = manifest.get("page_record_counts")
    delivered_count = manifest.get("delivered_record_count")
    if (
        not isinstance(page_counts, list)
        or isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or len(page_counts) != page_count
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in page_counts)
    ):
        _finding(
            findings,
            "market.page_record_counts",
            "error",
            "page_record_counts must contain one non-negative integer per page",
        )
    if isinstance(delivered_count, bool) or not isinstance(delivered_count, int) or delivered_count < 1:
        _finding(
            findings,
            "market.delivered_record_count",
            "error",
            "delivered_record_count must be a positive integer",
        )
    elif isinstance(page_counts, list) and all(
        isinstance(item, int) and not isinstance(item, bool) for item in page_counts
    ) and sum(page_counts) != delivered_count:
        _finding(
            findings,
            "market.delivery_count_reconciliation",
            "error",
            "Page record counts must sum to delivered_record_count",
        )
    symbols = manifest.get("expected_symbols")
    normalized_symbols = (
        [item.strip().upper() for item in symbols]
        if isinstance(symbols, list)
        and all(isinstance(item, str) for item in symbols)
        else []
    )
    if (
        not isinstance(symbols, list)
        or not symbols
        or any(not isinstance(item, str) or not item.strip() for item in symbols)
        or any(not _SAFE.fullmatch(item) for item in normalized_symbols)
        or len(set(normalized_symbols)) != len(symbols)
    ):
        _finding(findings, "market.expected_symbols", "error", "expected_symbols must be a unique non-empty list")
    statuses = manifest.get("premarket_status_by_symbol")
    expected_symbol_set = (
        set(normalized_symbols)
    )
    if (
        not isinstance(statuses, dict)
        or any(not isinstance(key, str) for key in statuses)
        or len({str(key).strip().upper() for key in statuses}) != len(statuses)
        or {str(key).strip().upper() for key in statuses} != expected_symbol_set
        or any(value not in {"observed", "verified_no_trades"} for value in statuses.values())
    ):
        _finding(findings, "market.premarket_status", "error", "Every expected symbol needs observed or verified_no_trades premarket status")
    try:
        trading_date = date.fromisoformat(str(manifest.get("trading_date")))
    except ValueError:
        _finding(findings, "market.trading_date", "error", "trading_date must be YYYY-MM-DD")
        trading_date = None
    start = _parse_timestamp(manifest.get("premarket_start_inclusive"), "premarket_start", findings)
    end = _parse_timestamp(manifest.get("premarket_end_exclusive"), "premarket_end", findings)
    if trading_date and start is not None:
        local = start.tz_convert(NY)
        if local.date() != trading_date or (local.hour, local.minute, local.second) != (4, 0, 0):
            _finding(findings, "market.premarket_start", "error", "Premarket coverage must begin at 04:00 ET")
    if trading_date and end is not None:
        local = end.tz_convert(NY)
        if local.date() != trading_date or (local.hour, local.minute, local.second) != (9, 25, 0):
            _finding(findings, "market.premarket_end", "error", "Premarket coverage must end exclusively at 09:25 ET")
    return trading_date, start, end


def _validate_market_bars(
    path: Path,
    manifest: Mapping[str, Any],
    trading_date: date | None,
    premarket_start: pd.Timestamp | None,
    premarket_end: pd.Timestamp | None,
    calendar: Any,
    findings: list[Finding],
) -> dict[str, Any]:
    summary: dict[str, Any] = {"bar_count": 0, "symbols": [], "sessions": []}
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        _finding(findings, "market.csv", "error", f"Bars CSV cannot be read: {type(exc).__name__}")
        return summary
    if tuple(frame.columns) != MARKET_COLUMNS:
        _finding(
            findings,
            "market.schema",
            "error",
            "Bars CSV columns must exactly match the versioned schema and order",
            expected=list(MARKET_COLUMNS),
            observed=list(frame.columns),
        )
        return summary
    summary["bar_count"] = len(frame)
    delivered_count = manifest.get("delivered_record_count")
    if (
        not isinstance(delivered_count, bool)
        and isinstance(delivered_count, int)
        and len(frame) != delivered_count
    ):
        _finding(
            findings,
            "market.delivered_record_count_mismatch",
            "error",
            "Bars CSV row count differs from the delivery manifest",
            expected=delivered_count,
            observed=len(frame),
        )
    original_timestamps = frame["timestamp"].copy()
    try:
        parsed = pd.to_datetime(frame["timestamp"], errors="raise")
    except (TypeError, ValueError):
        _finding(findings, "market.timestamp_parse", "error", "Bar timestamps are malformed")
        return summary
    if not isinstance(parsed.dtype, pd.DatetimeTZDtype):
        _finding(findings, "market.timezone", "error", "Bar timestamps must be timezone-aware")
        return summary
    try:
        declared_zone = ZoneInfo(str(manifest.get("timestamp_timezone")))
    except (KeyError, ValueError):
        declared_zone = None
    if declared_zone is not None and any(
        pd.Timestamp(value).utcoffset()
        != pd.Timestamp(value).tz_convert(declared_zone).utcoffset()
        for value in original_timestamps
    ):
        _finding(
            findings,
            "market.timestamp_timezone_mismatch",
            "error",
            "Bar timestamp offsets contradict timestamp_timezone",
        )
    frame = frame.copy()
    frame["timestamp"] = parsed.dt.tz_convert(NY)
    if not (
        frame["timestamp"].dt.second.eq(0)
        & frame["timestamp"].dt.microsecond.eq(0)
    ).all():
        _finding(
            findings,
            "market.minute_alignment",
            "error",
            "One-minute left-labeled timestamps must align exactly to a minute",
        )
    if frame.duplicated(["symbol", "timestamp"]).any():
        _finding(findings, "market.duplicates", "error", "Duplicate symbol/timestamp bars are forbidden")
    order = frame.sort_values(["timestamp", "symbol"], kind="mergesort").index
    if not order.equals(frame.index):
        _finding(findings, "market.order", "error", "Bars must be deterministically chronological")
    if original_timestamps.isna().any():
        _finding(findings, "market.timestamp_null", "error", "Bar timestamps cannot be null")
    numeric = ["open", "high", "low", "close", "volume"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[numeric].to_numpy(dtype=float)
    if frame[numeric].isna().any().any() or not np.isfinite(values).all():
        _finding(findings, "market.numeric", "error", "OHLCV values must be finite numeric values")
    elif (
        frame[["open", "high", "low", "close"]].le(0).any().any()
        or frame["volume"].lt(0).any()
        or frame["high"].lt(frame[["open", "close"]].max(axis=1)).any()
        or frame["low"].gt(frame[["open", "close"]].min(axis=1)).any()
        or frame["high"].lt(frame["low"]).any()
    ):
        _finding(findings, "market.ohlcv", "error", "OHLCV values violate price or range constraints")
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    observed_symbols = sorted(frame["symbol"].unique())
    expected_symbols = sorted(
        str(item).strip().upper() for item in manifest.get("expected_symbols", [])
    )
    summary["symbols"] = observed_symbols
    if observed_symbols != expected_symbols:
        _finding(findings, "market.symbol_scope", "error", "Observed symbol scope differs from manifest", observed=observed_symbols, expected=expected_symbols)
    if trading_date and not frame["timestamp"].dt.date.eq(trading_date).all():
        _finding(findings, "market.date_scope", "error", "Bars contain cross-date observations")
    if not frame["segment"].isin({"premarket", "regular"}).all():
        _finding(findings, "market.segment", "error", "segment must be premarket or regular")
        return summary
    if trading_date is None or premarket_start is None or premarket_end is None:
        return summary
    premarket = frame.loc[frame["segment"].eq("premarket")]
    if not premarket["timestamp"].ge(premarket_start.tz_convert(NY)).all() or not premarket["timestamp"].lt(premarket_end.tz_convert(NY)).all():
        _finding(findings, "market.premarket_boundary", "error", "Premarket bars must remain in [04:00, 09:25) ET")
    try:
        schedule = calendar.schedule(trading_date, "XNYS")
    except Exception as exc:
        _finding(findings, "market.schedule", "error", f"Cannot resolve authoritative XNYS session: {type(exc).__name__}")
        return summary
    declared_regular_start = _parse_timestamp(
        manifest.get("regular_start_inclusive"), "regular_start", findings
    )
    declared_regular_end = _parse_timestamp(
        manifest.get("regular_end_exclusive"), "regular_end", findings
    )
    if (
        declared_regular_start is None
        or declared_regular_start.tz_convert(NY) != schedule.open_timestamp
        or declared_regular_end is None
        or declared_regular_end.tz_convert(NY) != schedule.close_timestamp
    ):
        _finding(findings, "market.regular_coverage", "error", "Declared regular boundaries must match the authoritative XNYS session")
    expected_regular = schedule.expected_minutes
    regular = frame.loc[frame["segment"].eq("regular")]
    if not regular["timestamp"].isin(expected_regular).all():
        _finding(findings, "market.regular_boundary", "error", "Regular bars include a non-XNYS left-labeled minute")
    explicit_zeros = manifest.get("zero_trade_minute_semantics") == "explicit_zero_volume_bar"
    statuses_by_symbol = {
        str(key).strip().upper(): value
        for key, value in manifest.get("premarket_status_by_symbol", {}).items()
    } if isinstance(manifest.get("premarket_status_by_symbol"), dict) else {}
    for symbol in expected_symbols:
        symbol_premarket = premarket.loc[premarket["symbol"].eq(symbol)]
        status = statuses_by_symbol.get(symbol)
        if status == "observed" and symbol_premarket.empty:
            _finding(findings, "market.premarket_observation", "error", "Premarket status says observed but no bar exists", symbol=symbol)
        if status == "verified_no_trades" and not symbol_premarket.empty:
            _finding(findings, "market.premarket_no_trade", "error", "Premarket status says no trades but bars exist", symbol=symbol)
        observed = pd.DatetimeIndex(
            regular.loc[regular["symbol"].eq(symbol), "timestamp"]
        )
        if observed.empty:
            _finding(findings, "market.regular_observation", "error", "No regular bar exists for an expected symbol", symbol=symbol)
        raw_missing = expected_regular.difference(observed)
        halts = load_verified_halts(symbol, trading_date)
        halt_covered = raw_missing.intersection(halts.full_halt_minutes)
        unexplained = raw_missing.difference(halts.full_halt_minutes)
        summary["sessions"].append({
            "symbol": symbol,
            "expected_regular_minutes": len(expected_regular),
            "observed_regular_minutes": len(observed),
            "raw_missing_minutes": len(raw_missing),
            "verified_halt_covered_minutes": len(halt_covered),
            "unexplained_missing_minutes": len(unexplained),
        })
        if explicit_zeros and len(unexplained):
            _finding(findings, "market.zero_trade_contradiction", "error", "Manifest promises explicit zero-volume bars but regular minutes are absent", symbol=symbol, missing=len(unexplained))
        elif len(unexplained):
            _finding(findings, "market.missing_visible", "warning", "Regular minutes are absent and remain visible under documented omission semantics", symbol=symbol, missing=len(unexplained))
    return summary


REFERENCE_FILE_FIELDS = {
    "universe": "universe_file",
    "listings": "listings_file",
    "symbol_history": "symbol_history_file",
    "corporate_actions": "corporate_actions_file",
}

REFERENCE_COLUMNS = {
    "universe": (
        "as_of_timestamp", "symbol", "stable_identifier", "security_type",
        "security_type_code", "security_type_description", "common_stock_eligible",
        "exchange", "calendar_id", "active", "source", "dataset_vintage",
        "release_id",
    ),
    "listings": (
        "stable_identifier", "symbol", "listing_start_timestamp",
        "listing_end_timestamp", "exchange", "calendar_id", "known_at_timestamp",
        "source", "dataset_vintage", "release_id",
    ),
    "symbol_history": (
        "stable_identifier", "canonical_symbol", "historical_symbol",
        "effective_start_timestamp", "effective_end_timestamp",
        "known_at_timestamp", "source", "dataset_vintage", "release_id",
    ),
    "corporate_actions": (
        "stable_identifier", "symbol", "record_type", "coverage_start_timestamp",
        "coverage_end_timestamp", "effective_timestamp", "action_type",
        "adjustment_factor", "adjustment_method", "publication_timestamp",
        "known_at_timestamp", "correction_status", "correction_timestamp",
        "source", "dataset_vintage", "release_id",
    ),
}

REFERENCE_SORT_COLUMNS = {
    "universe": ("as_of_timestamp", "stable_identifier", "symbol"),
    "listings": ("stable_identifier", "listing_start_timestamp", "symbol"),
    "symbol_history": (
        "stable_identifier", "effective_start_timestamp", "historical_symbol",
    ),
    "corporate_actions": (
        "stable_identifier", "coverage_start_timestamp", "effective_timestamp",
        "publication_timestamp", "symbol",
    ),
}


def _reference_files(
    manifest_path: Path, manifest: Mapping[str, Any], findings: list[Finding]
) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for logical, field in REFERENCE_FILE_FIELDS.items():
        try:
            files[logical] = _sample_file(manifest_path, manifest.get(field), field)
        except ValueError as exc:
            _finding(findings, f"reference.{field}", "error", str(exc))
    return files


def _read_reference_frames(
    files: Mapping[str, Path], findings: list[Finding]
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for logical, path in sorted(files.items()):
        try:
            frame = pd.read_csv(path)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            _finding(findings, f"reference.{logical}.csv", "error", f"CSV cannot be read: {type(exc).__name__}")
            continue
        expected = REFERENCE_COLUMNS[logical]
        if tuple(frame.columns) != expected:
            _finding(
                findings,
                f"reference.{logical}.schema",
                "error",
                "Reference CSV columns must exactly match the versioned schema and order",
                expected=list(expected),
                observed=list(frame.columns),
            )
            continue
        frames[logical] = frame.copy()
    return frames


def _boolean_series(series: pd.Series, label: str, findings: list[Finding]) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        _finding(findings, f"reference.{label}", "error", f"{label} must contain true or false")
    return values.eq("true")


def _timestamp_columns(
    frame: pd.DataFrame,
    required: tuple[str, ...],
    optional: tuple[str, ...],
    label: str,
    findings: list[Finding],
) -> pd.DataFrame:
    result = frame.copy()
    for column in required + optional:
        malformed = False
        naive = False
        for value in result[column]:
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                continue
            try:
                timestamp = pd.Timestamp(value)
            except (TypeError, ValueError, OverflowError):
                malformed = True
                continue
            if pd.isna(timestamp):
                malformed = True
            elif timestamp.tzinfo is None:
                naive = True
        if malformed:
            _finding(
                findings,
                f"reference.{label}.{column}",
                "error",
                f"{label} contains invalid {column}",
            )
        if naive:
            _finding(
                findings,
                f"reference.{label}.{column}.timezone",
                "error",
                f"{label} {column} values must be timezone-aware",
            )
        result[column] = pd.to_datetime(result[column], utc=True, errors="coerce")
    for column in required:
        if result[column].isna().any():
            _finding(findings, f"reference.{label}.{column}", "error", f"{label} contains invalid {column}")
    return result


def _validate_reference_order_and_duplicates(
    label: str, frame: pd.DataFrame, findings: list[Finding]
) -> None:
    if frame.duplicated().any():
        _finding(
            findings,
            f"reference.{label}.duplicates",
            "error",
            f"{label} contains duplicate records",
        )
    order = frame.sort_values(
        list(REFERENCE_SORT_COLUMNS[label]), kind="mergesort", na_position="last"
    ).index
    if not order.equals(frame.index):
        _finding(
            findings,
            f"reference.{label}.order",
            "error",
            f"{label} records must use canonical deterministic ordering",
        )


def _overlaps(
    frame: pd.DataFrame, group: str, start: str, end: str
) -> bool:
    for _, values in frame.sort_values([group, start], kind="mergesort").groupby(group):
        previous_end: pd.Timestamp | None = None
        for row in values.itertuples(index=False):
            current_start = getattr(row, start)
            current_end = getattr(row, end)
            if previous_end is not None and current_start < previous_end:
                return True
            previous_end = current_end if pd.notna(current_end) else pd.Timestamp.max.tz_localize("UTC")
    return False


def _validate_reference(
    manifest: Mapping[str, Any], frames: Mapping[str, pd.DataFrame], findings: list[Finding]
) -> dict[str, Any]:
    summary: dict[str, Any] = {"universe_count": 0, "listing_count": 0, "symbol_history_count": 0, "corporate_action_count": 0}
    required = (
        "schema_version", "profile", "provider", "sample_id", "decision_timestamp",
        "coverage_start_timestamp", "coverage_end_timestamp",
        "complete_bounded_universe_asserted", "expected_universe_count",
        "universe_scope", "security_type_dictionary_reference",
        "correction_policy_reference", "delivery_id", "release_id",
        "dataset_vintage", "source_sha256",
    ) + tuple(REFERENCE_FILE_FIELDS.values())
    _required_fields(manifest, required, findings)
    _exact_fields(manifest, required, findings, "manifest")
    for field in (
        "provider", "sample_id", "universe_scope",
        "security_type_dictionary_reference", "correction_policy_reference",
        "delivery_id", "release_id", "dataset_vintage",
    ):
        _require_text(manifest, field, findings)
    for field in ("provider", "sample_id", "delivery_id", "release_id", "dataset_vintage"):
        _require_safe_identifier(manifest, field, findings)
    if manifest.get("schema_version") != CHECKER_SCHEMA_VERSION:
        _finding(findings, "manifest.schema_version", "error", "Unsupported reference manifest schema")
    if manifest.get("profile") != SampleProfile.REFERENCE_DATA.value:
        _finding(findings, "manifest.profile", "error", "Manifest profile must be reference_data")
    if manifest.get("complete_bounded_universe_asserted") is not True:
        _finding(findings, "reference.universe_assertion", "error", "Complete bounded universe must be explicitly asserted")
    expected_count = manifest.get("expected_universe_count")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int) or expected_count < 1:
        _finding(findings, "reference.expected_count", "error", "expected_universe_count must be positive")
    cutoff = _parse_timestamp(manifest.get("decision_timestamp"), "decision_timestamp", findings)
    coverage_start = _parse_timestamp(manifest.get("coverage_start_timestamp"), "coverage_start", findings)
    coverage_end = _parse_timestamp(manifest.get("coverage_end_timestamp"), "coverage_end", findings)
    if coverage_start is not None and coverage_end is not None and coverage_end <= coverage_start:
        _finding(findings, "reference.coverage_interval", "error", "Reference coverage interval is invalid")
    if (
        cutoff is not None
        and coverage_start is not None
        and coverage_end is not None
        and not (coverage_start <= cutoff < coverage_end)
    ):
        _finding(
            findings,
            "reference.coverage_cutoff",
            "error",
            "Reference coverage must contain the decision timestamp",
        )
    if cutoff is not None:
        local_cutoff = cutoff.tz_convert(NY)
        if (local_cutoff.hour, local_cutoff.minute, local_cutoff.second) != (9, 25, 0):
            _finding(findings, "reference.decision_cutoff", "error", "decision_timestamp must be exactly 09:25 ET")
    if set(frames) != set(REFERENCE_FILE_FIELDS):
        return summary
    universe = _timestamp_columns(frames["universe"], ("as_of_timestamp",), (), "universe", findings)
    listings = _timestamp_columns(frames["listings"], ("listing_start_timestamp", "known_at_timestamp"), ("listing_end_timestamp",), "listings", findings)
    symbols = _timestamp_columns(frames["symbol_history"], ("effective_start_timestamp", "known_at_timestamp"), ("effective_end_timestamp",), "symbol_history", findings)
    actions = _timestamp_columns(frames["corporate_actions"], ("coverage_start_timestamp", "coverage_end_timestamp", "publication_timestamp", "known_at_timestamp"), ("effective_timestamp", "correction_timestamp"), "corporate_actions", findings)
    summary.update(
        universe_count=len(universe), listing_count=len(listings),
        symbol_history_count=len(symbols), corporate_action_count=len(actions),
    )
    for label, frame in (("universe", universe), ("listings", listings), ("symbol_history", symbols), ("corporate_actions", actions)):
        _validate_reference_order_and_duplicates(label, frame, findings)
        for column in ("stable_identifier", "source", "dataset_vintage", "release_id"):
            if column in frame and frame[column].astype("string").str.strip().replace("", pd.NA).isna().any():
                _finding(findings, f"reference.{label}.{column}", "error", f"{label} requires non-empty {column}")
        if not frame["dataset_vintage"].astype(str).eq(str(manifest.get("dataset_vintage"))).all():
            _finding(findings, f"reference.{label}.vintage", "error", f"{label} dataset_vintage differs from manifest")
        if not frame["release_id"].astype(str).eq(str(manifest.get("release_id"))).all():
            _finding(findings, f"reference.{label}.release", "error", f"{label} release_id differs from manifest")
        if not frame["source"].astype(str).eq(str(manifest.get("provider"))).all():
            _finding(
                findings,
                f"reference.{label}.source_identity",
                "error",
                f"{label} source differs from the manifest provider",
            )
    required_text_columns = {
        "universe": (
            "symbol", "stable_identifier", "security_type", "exchange", "calendar_id",
        ),
        "listings": ("stable_identifier", "symbol", "exchange", "calendar_id"),
        "symbol_history": (
            "stable_identifier", "canonical_symbol", "historical_symbol",
        ),
        "corporate_actions": ("stable_identifier", "symbol", "record_type"),
    }
    for label, frame in (
        ("universe", universe),
        ("listings", listings),
        ("symbol_history", symbols),
        ("corporate_actions", actions),
    ):
        for column in required_text_columns[label]:
            values = frame[column].astype("string").str.strip()
            if values.isna().any() or values.eq("").any():
                _finding(
                    findings,
                    f"reference.{label}.{column}",
                    "error",
                    f"{label} requires non-empty {column}",
                )
    if len(universe) != expected_count:
        _finding(findings, "reference.universe_count", "error", "Universe row count differs from bounded assertion", observed=len(universe), expected=expected_count)
    if universe["stable_identifier"].duplicated().any() or universe["symbol"].astype(str).str.upper().duplicated().any():
        _finding(findings, "reference.universe_unique", "error", "Universe stable identifiers and symbols must be unique")
    active = _boolean_series(universe["active"], "universe.active", findings)
    eligible = _boolean_series(universe["common_stock_eligible"], "universe.common_stock_eligible", findings)
    if not active.all() or not eligible.all():
        _finding(findings, "reference.universe_eligibility", "error", "Bounded universe must contain active eligible common stocks only")
    if (
        not universe["security_type"].astype(str).eq("common_stock").all()
        or universe["security_type_code"].astype("string").str.strip().replace("", pd.NA).isna().any()
        or universe["security_type_description"].astype("string").str.strip().replace("", pd.NA).isna().any()
    ):
        _finding(findings, "reference.security_type", "error", "Historical security-type evidence is incomplete")
    if universe["exchange"].astype("string").str.strip().replace("", pd.NA).isna().any() or not universe["calendar_id"].eq("XNYS").all():
        _finding(findings, "reference.exchange_calendar", "error", "Exchange and XNYS calendar identity are required")
    if cutoff is not None:
        decision_day = cutoff.tz_convert(NY).date()
        if not universe["as_of_timestamp"].dt.tz_convert(NY).dt.date.eq(decision_day).all():
            _finding(findings, "reference.universe_date", "error", "Universe as-of timestamps must match the decision date")
        if universe["as_of_timestamp"].ge(cutoff.tz_convert("UTC")).any():
            _finding(findings, "reference.lookahead.universe", "error", "Universe knowledge is not strictly before the decision cutoff")
        for label, frame in (("listings", listings), ("symbol_history", symbols), ("corporate_actions", actions)):
            if frame["known_at_timestamp"].ge(cutoff.tz_convert("UTC")).any():
                _finding(findings, f"reference.lookahead.{label}", "error", f"{label} contains knowledge at or after the cutoff")
        if actions["publication_timestamp"].ge(cutoff.tz_convert("UTC")).any() or actions["correction_timestamp"].dropna().ge(cutoff.tz_convert("UTC")).any():
            _finding(findings, "reference.lookahead.actions", "error", "Action publication/correction evidence is at or after the cutoff")
    for label, frame, start, end in (
        ("listings", listings, "listing_start_timestamp", "listing_end_timestamp"),
        ("symbol_history", symbols, "effective_start_timestamp", "effective_end_timestamp"),
    ):
        if (frame[end].notna() & frame[end].le(frame[start])).any():
            _finding(findings, f"reference.{label}.interval", "error", f"{label} contains an invalid interval")
        if _overlaps(frame, "stable_identifier", start, end):
            _finding(findings, f"reference.{label}.overlap", "error", f"{label} intervals overlap for a stable identifier")
    if _overlaps(listings, "symbol", "listing_start_timestamp", "listing_end_timestamp"):
        _finding(findings, "reference.listings.recycled_overlap", "error", "Listing-symbol intervals overlap across securities")
    if _overlaps(symbols, "historical_symbol", "effective_start_timestamp", "effective_end_timestamp"):
        _finding(findings, "reference.symbol_history.recycled_overlap", "error", "Historical symbol intervals overlap across securities")
    universe_ids = set(universe["stable_identifier"].astype(str))
    for label, frame in (("listings", listings), ("symbol_history", symbols), ("corporate_actions", actions)):
        observed_ids = set(frame["stable_identifier"].astype(str))
        if observed_ids != universe_ids:
            _finding(
                findings,
                f"reference.{label}.coverage",
                "error",
                f"{label} stable-identifier scope differs from the bounded universe",
                missing=sorted(universe_ids.difference(observed_ids)),
                unexpected=sorted(observed_ids.difference(universe_ids)),
            )
    universe_symbols = {
        str(row.stable_identifier): str(row.symbol).upper()
        for row in universe.itertuples(index=False)
    }
    for row in symbols.itertuples(index=False):
        expected_symbol = universe_symbols.get(str(row.stable_identifier))
        if expected_symbol is not None and str(row.canonical_symbol).upper() != expected_symbol:
            _finding(
                findings,
                "reference.symbol_history.canonical_identity",
                "error",
                "Symbol-history canonical symbol differs from the bounded universe identity",
                stable_identifier=str(row.stable_identifier),
            )
        if pd.isna(row.effective_start_timestamp):
            continue
        matching_listings = listings.loc[
            listings["stable_identifier"].astype(str).eq(str(row.stable_identifier))
            & listings["symbol"].astype(str).str.upper().eq(
                str(row.historical_symbol).upper()
            )
            & listings["listing_start_timestamp"].le(row.effective_start_timestamp)
            & (
                listings["listing_end_timestamp"].isna()
                | (
                    pd.notna(row.effective_end_timestamp)
                    & listings["listing_end_timestamp"].ge(
                        row.effective_end_timestamp
                    )
                )
                | (
                    pd.isna(row.effective_end_timestamp)
                    & listings["listing_end_timestamp"].isna()
                )
            )
        ]
        if len(matching_listings) != 1:
            _finding(
                findings,
                "reference.symbol_history.listing_coverage",
                "error",
                "Each ticker-history interval requires one covering listing interval for the same stable identifier",
                stable_identifier=str(row.stable_identifier),
                historical_symbol=str(row.historical_symbol),
            )
    if cutoff is not None:
        instant = cutoff.tz_convert("UTC")
        for row in universe.itertuples(index=False):
            stable = str(row.stable_identifier)
            listing = listings.loc[
                listings["stable_identifier"].astype(str).eq(stable)
                & listings["listing_start_timestamp"].le(instant)
                & (listings["listing_end_timestamp"].isna() | listings["listing_end_timestamp"].gt(instant))
            ]
            history = symbols.loc[
                symbols["stable_identifier"].astype(str).eq(stable)
                & symbols["effective_start_timestamp"].le(instant)
                & (symbols["effective_end_timestamp"].isna() | symbols["effective_end_timestamp"].gt(instant))
            ]
            if len(listing) != 1 or len(history) != 1:
                _finding(findings, "reference.active_identity", "error", "Listing and symbol history must uniquely cover each universe security", stable_identifier=stable)
            elif str(history.iloc[0]["canonical_symbol"]).upper() != str(row.symbol).upper():
                _finding(findings, "reference.symbol_mapping", "error", "Active canonical symbol differs from universe symbol", stable_identifier=stable)
            elif str(listing.iloc[0]["symbol"]).upper() != str(history.iloc[0]["historical_symbol"]).upper():
                _finding(findings, "reference.listing_symbol_mapping", "error", "Active listing symbol differs from active symbol-history record", stable_identifier=stable)
            elif (
                str(listing.iloc[0]["calendar_id"]) != "XNYS"
                or str(listing.iloc[0]["exchange"]) != str(row.exchange)
            ):
                _finding(
                    findings,
                    "reference.listing_exchange_mapping",
                    "error",
                    "Active listing exchange/calendar differs from the bounded universe",
                    stable_identifier=stable,
                )
    if not actions["record_type"].isin({"action", "verified_none"}).all():
        _finding(findings, "reference.actions.record_type", "error", "record_type must be action or verified_none")
    if not actions["correction_status"].isin({"original", "corrected"}).all():
        _finding(findings, "reference.actions.correction_status", "error", "correction_status must be original or corrected")
    corrected = actions["correction_status"].eq("corrected")
    if actions.loc[corrected, "correction_timestamp"].isna().any() or actions.loc[~corrected, "correction_timestamp"].notna().any():
        _finding(findings, "reference.actions.correction_time", "error", "Correction timestamps must match correction status")
    if actions["known_at_timestamp"].lt(actions["publication_timestamp"]).any():
        _finding(findings, "reference.actions.knowledge_order", "error", "Action knowledge cannot precede publication")
    if actions.loc[corrected, "known_at_timestamp"].lt(actions.loc[corrected, "correction_timestamp"]).any():
        _finding(findings, "reference.actions.correction_order", "error", "Corrected action knowledge cannot precede its correction")
    if (actions["coverage_end_timestamp"] <= actions["coverage_start_timestamp"]).any():
        _finding(
            findings,
            "reference.actions.coverage_interval",
            "error",
            "Corporate-action coverage intervals must have positive duration",
        )
    effective_actions = actions.loc[
        actions["record_type"].eq("action") & actions["effective_timestamp"].notna()
    ]
    if (
        effective_actions["effective_timestamp"].lt(
            effective_actions["coverage_start_timestamp"]
        )
        | effective_actions["effective_timestamp"].ge(
            effective_actions["coverage_end_timestamp"]
        )
    ).any():
        _finding(
            findings,
            "reference.actions.effective_boundary",
            "error",
            "Action effective timestamps must fall within their declared coverage interval",
        )
    action_rows = actions.loc[actions["record_type"].eq("action")]
    if action_rows.duplicated(
        ["stable_identifier", "effective_timestamp", "action_type"], keep=False
    ).any():
        _finding(
            findings,
            "reference.actions.conflict",
            "error",
            "Multiple action records claim the same stable identifier, effective time, and type",
        )
    for stable, group in actions.groupby(actions["stable_identifier"].astype(str)):
        if group["record_type"].nunique() != 1:
            _finding(findings, "reference.actions.mixed_coverage", "error", "Action and verified_none evidence cannot be mixed for one bounded security", stable_identifier=stable)
        if coverage_start is not None and coverage_end is not None and (
            group["coverage_start_timestamp"].gt(coverage_start.tz_convert("UTC")).any()
            or group["coverage_end_timestamp"].lt(coverage_end.tz_convert("UTC")).any()
        ):
            _finding(findings, "reference.actions.coverage_bounds", "error", "Corporate-action evidence does not cover the declared interval", stable_identifier=stable)
        if group["record_type"].eq("verified_none").all():
            if len(group) != 1:
                _finding(
                    findings,
                    "reference.actions.verified_none_duplicate",
                    "error",
                    "Exactly one bounded verified_none record is required per security",
                    stable_identifier=stable,
                )
            forbidden = (
                group["effective_timestamp"].notna()
                | group["action_type"].astype("string").fillna("").str.strip().ne("")
                | pd.to_numeric(group["adjustment_factor"], errors="coerce").notna()
                | group["adjustment_method"].astype("string").fillna("").str.strip().ne("")
            )
            if forbidden.any():
                _finding(findings, "reference.actions.verified_none", "error", "verified_none cannot contain action values", stable_identifier=stable)
        else:
            factors = pd.to_numeric(group["adjustment_factor"], errors="coerce")
            if (
                group["effective_timestamp"].isna().any()
                or group["action_type"].astype("string").str.strip().replace("", pd.NA).isna().any()
                or factors.isna().any()
                or factors.le(0).any()
                or group["adjustment_method"].astype("string").str.strip().replace("", pd.NA).isna().any()
            ):
                _finding(findings, "reference.actions.provenance", "error", "Action records require effective time, type, positive factor, and adjustment method", stable_identifier=stable)
        for action in group.itertuples(index=False):
            identity_time = (
                action.effective_timestamp
                if action.record_type == "action" and pd.notna(action.effective_timestamp)
                else cutoff.tz_convert("UTC") if cutoff is not None else None
            )
            if identity_time is None:
                continue
            history = symbols.loc[
                symbols["stable_identifier"].astype(str).eq(stable)
                & symbols["effective_start_timestamp"].le(identity_time)
                & (
                    symbols["effective_end_timestamp"].isna()
                    | symbols["effective_end_timestamp"].gt(identity_time)
                )
            ]
            if (
                len(history) != 1
                or str(history.iloc[0]["historical_symbol"]).upper()
                != str(action.symbol).upper()
            ):
                _finding(
                    findings,
                    "reference.actions.symbol_identity",
                    "error",
                    "Corporate-action symbol is not the stable identifier's active historical symbol",
                    stable_identifier=stable,
                )
    return summary


MANDATORY_RIGHTS = (
    "internal_research", "raw_storage", "normalized_storage", "backups",
    "cloud_processing", "contractor_access", "post_termination_retention",
    "derived_works", "subscriber_dashboard_display",
    "subscriber_conversational_display",
)
RESOLVED_RESTRICTIONS = (
    "raw_display", "reconstructable_display", "downloads", "api", "alerts",
)
RESOLVED_FEES = ("exchange_fees", "display_fees", "non_display_fees")
EVIDENCE_TYPES = {"executed_order_form", "executed_amendment", "written_vendor_confirmation"}
LICENSING_FIELDS = (
    "schema_version", "provider", "contracting_entity", "agreement_id",
    "effective_date", "rights", "restrictions", "fees",
)
EVIDENCE_FIELDS = ("status", "evidence_type", "evidence_reference")


def _validate_licensing(
    licensing: Mapping[str, Any], provider: str, findings: list[Finding]
) -> bool:
    _exact_fields(licensing, LICENSING_FIELDS, findings, "licensing")
    if licensing.get("schema_version") != CHECKER_SCHEMA_VERSION:
        _finding(findings, "licensing.schema_version", "error", "Unsupported licensing manifest schema")
    if licensing.get("provider") != provider:
        _finding(findings, "licensing.provider", "error", "Licensing provider differs from sample provider")
    for field in ("contracting_entity", "agreement_id", "effective_date"):
        _require_text(licensing, field, findings, prefix="licensing")
    try:
        date.fromisoformat(str(licensing.get("effective_date")))
    except ValueError:
        _finding(findings, "licensing.effective_date", "error", "effective_date must be YYYY-MM-DD")
    rights = licensing.get("rights")
    restrictions = licensing.get("restrictions")
    fees = licensing.get("fees")
    if not isinstance(rights, dict):
        _finding(findings, "licensing.rights", "error", "rights must be an object")
        rights = {}
    if not isinstance(restrictions, dict):
        _finding(findings, "licensing.restrictions", "error", "restrictions must be an object")
        restrictions = {}
    if not isinstance(fees, dict):
        _finding(findings, "licensing.fees", "error", "fees must be an object")
        fees = {}
    for section, observed, expected in (
        ("rights", rights, set(MANDATORY_RIGHTS)),
        ("restrictions", restrictions, set(RESOLVED_RESTRICTIONS)),
        ("fees", fees, set(RESOLVED_FEES)),
    ):
        if set(observed) != expected:
            _finding(
                findings,
                f"licensing.{section}.schema",
                "error",
                f"Licensing {section} must match the versioned schema exactly",
                missing=sorted(expected.difference(observed)),
                unexpected=sorted(set(observed).difference(expected)),
            )

    def evidence(name: str, item: Any, allowed: set[str], section: str) -> None:
        if not isinstance(item, dict):
            _finding(findings, f"licensing.{section}.{name}", "error", "Licensing item must be an evidence object")
            return
        if set(item) != set(EVIDENCE_FIELDS):
            _finding(
                findings,
                f"licensing.{section}.{name}.schema",
                "error",
                "Licensing evidence fields must match the versioned schema exactly",
                missing=sorted(set(EVIDENCE_FIELDS).difference(item)),
                unexpected=sorted(set(item).difference(EVIDENCE_FIELDS)),
            )
        if item.get("status") not in allowed:
            _finding(findings, f"licensing.{section}.{name}.status", "error", f"{name} is unresolved or unsupported")
        if item.get("evidence_type") not in EVIDENCE_TYPES:
            _finding(findings, f"licensing.{section}.{name}.evidence_type", "error", "Marketing or undocumented evidence is not contractual permission")
        reference = item.get("evidence_reference")
        if (
            not isinstance(reference, str)
            or not reference.strip()
            or reference.strip().lower().startswith("replace_")
        ):
            _finding(findings, f"licensing.{section}.{name}.evidence_reference", "error", "Written evidence reference is required")

    for name in MANDATORY_RIGHTS:
        evidence(name, rights.get(name), {"granted"}, "rights")
    for name in RESOLVED_RESTRICTIONS:
        evidence(name, restrictions.get(name), {"permitted", "prohibited"}, "restrictions")
    for name in RESOLVED_FEES:
        evidence(name, fees.get(name), {"applicable", "not_applicable"}, "fees")
    return not any(item.severity == "error" and item.code.startswith("licensing.") for item in findings)


def evaluate_vendor_sample(
    profile: SampleProfile | str,
    manifest_path: Path,
    licensing_manifest_path: Path,
    *,
    calendar: Any | None = None,
) -> AcceptanceResult:
    """Validate local quarantined inputs without copying data into research paths."""

    profile = SampleProfile(profile)
    manifest_path = Path(manifest_path).absolute()
    licensing_manifest_path = Path(licensing_manifest_path).absolute()
    findings: list[Finding] = []
    initial_manifest_hash = _safe_input_hash(manifest_path, "sample_manifest")
    initial_licensing_hash = _safe_input_hash(
        licensing_manifest_path, "licensing_manifest"
    )
    try:
        manifest = _load_json(manifest_path, "Sample manifest")
    except ValueError as exc:
        manifest = {}
        _finding(findings, "manifest.json", "error", str(exc))
    try:
        licensing = _load_json(licensing_manifest_path, "Licensing manifest")
    except ValueError as exc:
        licensing = {}
        _finding(findings, "licensing.json", "error", str(exc))
    provider = str(manifest.get("provider", "")).strip()
    sample_id = str(manifest.get("sample_id", "")).strip()
    if not provider or not _SAFE.fullmatch(provider):
        _finding(findings, "manifest.provider", "error", "provider must be a safe non-empty identifier")
    if not sample_id or not _SAFE.fullmatch(sample_id):
        _finding(findings, "manifest.sample_id", "error", "sample_id must be a safe non-empty identifier")
    files = (
        _market_files(manifest_path, manifest, findings)
        if profile is SampleProfile.MARKET_DATA
        else _reference_files(manifest_path, manifest, findings)
    )
    file_hashes = _validate_declared_hashes(manifest, files, findings) if files else {}
    if profile is SampleProfile.MARKET_DATA:
        day, start, end = _validate_market_manifest(manifest, findings)
        summary = (
            _validate_market_bars(
                files["bars"], manifest, day, start, end,
                calendar or ExchangeCalendarsAdapter(), findings,
            )
            if "bars" in files else {"bar_count": 0, "symbols": [], "sessions": []}
        )
    else:
        frames = _read_reference_frames(files, findings)
        summary = _validate_reference(manifest, frames, findings)
    final_file_hashes: dict[str, str] = {}
    for logical, path in sorted(files.items()):
        try:
            final_file_hashes[logical] = file_sha256(path)
        except OSError as exc:
            final_file_hashes[logical] = hashlib.sha256(
                f"unreadable-final:{logical}".encode()
            ).hexdigest()
            _finding(
                findings,
                f"hash.{logical}.unreadable_final",
                "error",
                f"Sample file cannot be re-hashed after validation: {type(exc).__name__}",
            )
    for logical, initial in file_hashes.items():
        if final_file_hashes.get(logical) != initial:
            _finding(
                findings,
                f"hash.{logical}.mutated",
                "error",
                "Sample file changed while it was being validated",
            )
    final_manifest_hash = _safe_input_hash(manifest_path, "sample_manifest")
    final_licensing_hash = _safe_input_hash(
        licensing_manifest_path, "licensing_manifest"
    )
    if final_manifest_hash != initial_manifest_hash:
        _finding(findings, "manifest.mutated", "error", "Sample manifest changed during validation")
    if final_licensing_hash != initial_licensing_hash:
        _finding(findings, "licensing.mutated", "error", "Licensing manifest changed during validation")
    technical_pass = not any(item.severity == "error" and not item.code.startswith("licensing.") for item in findings)
    licensing_pass = _validate_licensing(licensing, provider, findings)
    findings.sort(key=lambda item: (item.severity, item.code, item.message, json.dumps(item.context, sort_keys=True)))
    input_hashes = {
        "sample_manifest": final_manifest_hash,
        "licensing_manifest": final_licensing_hash,
        **{
            f"sample:{key}": digest
            for key, digest in sorted(final_file_hashes.items())
        },
    }
    identity = {
        "checker_schema_version": CHECKER_SCHEMA_VERSION,
        "profile": profile.value,
        "provider": provider,
        "sample_id": sample_id,
        "input_hashes": input_hashes,
        "findings": [asdict(item) for item in findings],
        "summary": summary,
    }
    run_id = hashlib.sha256(_json_bytes(identity)).hexdigest()[:20]
    return AcceptanceResult(
        CHECKER_SCHEMA_VERSION,
        run_id,
        profile.value,
        provider,
        sample_id,
        technical_pass and licensing_pass,
        technical_pass,
        licensing_pass,
        tuple(findings),
        dict(sorted(input_hashes.items())),
        summary,
    )


def _result_payload(result: AcceptanceResult) -> dict[str, Any]:
    return {
        **{key: value for key, value in asdict(result).items() if key != "findings"},
        "findings": [asdict(item) for item in result.findings],
    }


def _human_report(result: AcceptanceResult) -> str:
    status = "ACCEPTED" if result.accepted else "REJECTED"
    lines = [
        f"# Vendor Sample Acceptance: {status}",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Profile: `{result.profile}`",
        f"- Provider: `{result.provider or 'missing'}`",
        f"- Sample: `{result.sample_id or 'missing'}`",
        f"- Technical pass: `{str(result.technical_pass).lower()}`",
        f"- Licensing pass: `{str(result.licensing_pass).lower()}`",
        "",
        "This report validates quarantined sample evidence only. It does not copy",
        "or admit source data into canonical research storage.",
        "",
        "## Findings",
        "",
    ]
    if not result.findings:
        lines.append("- No findings.")
    else:
        for item in result.findings:
            lines.append(f"- **{item.severity.upper()} `{item.code}`:** {item.message}")
    lines.extend(("", "## Summary", "", "```json", json.dumps(result.summary, indent=2, sort_keys=True), "```", ""))
    return "\n".join(lines)


def write_acceptance_report(result: AcceptanceResult, output_root: Path) -> Path:
    """Atomically publish deterministic reports outside canonical data paths."""

    unresolved_output_root = Path(output_root).absolute()
    if _has_symlink_component(unresolved_output_root):
        raise ValueError("Vendor sample report root cannot be a symlink")
    output_root = unresolved_output_root.resolve()
    data_root = (PROJECT_ROOT / "data").resolve()
    if output_root == data_root or data_root in output_root.parents:
        raise ValueError("Vendor sample reports cannot be written beneath canonical data/")
    output_root.mkdir(parents=True, exist_ok=True)
    profile_root = output_root / result.profile
    if profile_root.is_symlink():
        raise ValueError("Vendor sample profile report root cannot be a symlink")
    destination = profile_root / result.run_id
    if destination.resolve().parent != profile_root.resolve():
        raise ValueError("Vendor sample report destination escapes its profile root")
    if destination.is_symlink():
        raise ValueError("Vendor sample report destination cannot be a symlink")
    if destination.exists():
        expected = _json_bytes(_result_payload(result))
        expected_report = _human_report(result).encode("utf-8")
        result_path = destination / "acceptance_result.json"
        report_path = destination / "report.md"
        if (
            set(item.name for item in destination.iterdir())
            != {"acceptance_result.json", "report.md"}
            or not result_path.is_file()
            or result_path.is_symlink()
            or result_path.read_bytes() != expected
            or not report_path.is_file()
            or report_path.is_symlink()
            or report_path.read_bytes() != expected_report
        ):
            raise FileExistsError("Existing vendor-sample report conflicts with deterministic run")
        return destination
    profile_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{result.run_id}.", dir=profile_root))
    try:
        report = _human_report(result).encode("utf-8")
        with (temporary / "report.md").open("xb") as handle:
            handle.write(report)
            handle.flush()
            os.fsync(handle.fileno())
        with (temporary / "acceptance_result.json").open("xb") as handle:
            handle.write(_json_bytes(_result_payload(result)))
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
