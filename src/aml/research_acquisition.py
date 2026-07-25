"""Deterministic, segmented acquisition for Research Cohort V001."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from aml.market_calendar import NonTradingSessionError


NY = ZoneInfo("America/New_York")
SELECTION_CUTOFF = time(9, 25)
PREMARKET_OPEN = time(4, 0)
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")
_CANONICAL_BAR_COLUMNS = (
    "timestamp", "symbol", "open", "high", "low", "close", "volume",
    "trade_count", "bar_vwap",
)


class AcquisitionSegment(str, Enum):
    """Non-overlapping market-data windows persisted independently."""

    PREMARKET = "premarket"
    REGULAR = "regular"


@dataclass(frozen=True)
class AcquisitionRequest:
    """Validated request identity, boundaries, feed, calendar, and vintage."""

    symbol: str
    trading_date: date
    segment: AcquisitionSegment
    start_timestamp: pd.Timestamp
    end_timestamp: pd.Timestamp
    requested_feed: str = "sip"
    calendar_id: str = "XNYS"
    dataset_vintage: str = ""

    def __post_init__(self) -> None:
        symbol = self.symbol.upper().strip()
        feed = self.requested_feed.lower().strip()
        segment = AcquisitionSegment(self.segment)
        start = _aware(self.start_timestamp, "start_timestamp")
        end = _aware(self.end_timestamp, "end_timestamp")
        if not symbol or not _SAFE_COMPONENT.fullmatch(symbol):
            raise ValueError("Invalid acquisition symbol")
        if feed not in {"sip", "iex"}:
            raise ValueError("Research acquisition feed must be sip or iex")
        if not self.dataset_vintage or not _SAFE_COMPONENT.fullmatch(self.dataset_vintage):
            raise ValueError("dataset_vintage must be a safe, non-empty identifier")
        if end <= start:
            raise ValueError("Acquisition end must be after start")
        if start.tz_convert(NY).date() != self.trading_date or end.tz_convert(NY).date() != self.trading_date:
            raise ValueError("Acquisition window must remain on its trading date")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "requested_feed", feed)
        object.__setattr__(self, "segment", segment)
        object.__setattr__(self, "start_timestamp", start)
        object.__setattr__(self, "end_timestamp", end)


@dataclass(frozen=True)
class SegmentPaths:
    """Feed- and vintage-qualified paths for one acquisition segment."""

    raw_response: Path
    processed_bars: Path
    metadata: Path


@dataclass(frozen=True)
class NormalizationReport:
    """Auditable validation counts produced without filling missing bars."""

    segment: str
    input_record_count: int
    output_record_count: int
    expected_minute_count: int
    missing_timestamp_count: int
    duplicate_timestamp_count: int
    out_of_order: bool
    cross_date_bar_count: int
    outside_requested_window_count: int
    unexpected_1600_bar_count: int
    requested_feed: str
    actual_feed: str | None
    actual_feed_evidence: str


class AcquisitionDataError(ValueError):
    """Raised when acquired data cannot be trusted or normalized."""


def _aware(value: pd.Timestamp | datetime | str, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return timestamp.tz_convert(NY)


def selection_cutoff(trading_date: date) -> pd.Timestamp:
    """Return the registered 09:25 ET exclusive selection cutoff."""
    return pd.Timestamp(datetime.combine(trading_date, SELECTION_CUTOFF, NY))


def premarket_open(trading_date: date) -> pd.Timestamp:
    """Return the registered 04:00 ET inclusive premarket boundary."""
    return pd.Timestamp(datetime.combine(trading_date, PREMARKET_OPEN, NY))


def requests_for_session(
    symbol: str,
    trading_date: date,
    schedule: Any,
    dataset_vintage: str,
    feed: str = "sip",
) -> tuple[AcquisitionRequest, AcquisitionRequest]:
    """Build non-overlapping premarket and authoritative regular requests."""
    return (
        AcquisitionRequest(
            symbol, trading_date, AcquisitionSegment.PREMARKET,
            premarket_open(trading_date), selection_cutoff(trading_date),
            feed, schedule.calendar_id, dataset_vintage,
        ),
        AcquisitionRequest(
            symbol, trading_date, AcquisitionSegment.REGULAR,
            schedule.open_timestamp, schedule.close_timestamp,
            feed, schedule.calendar_id, dataset_vintage,
        ),
    )


def research_segment_paths(root: Path, request: AcquisitionRequest) -> SegmentPaths:
    """Resolve feed- and vintage-qualified paths for one isolated segment."""
    base = (
        Path(root) / "data" / "research" / request.dataset_vintage /
        request.requested_feed / request.symbol / str(request.trading_date)
    )
    stem = request.segment.value
    return SegmentPaths(
        base / "raw" / f"{stem}_provider_response.json",
        base / "processed" / f"{stem}_1min.csv",
        base / "metadata" / f"{stem}_acquisition.json",
    )


def _timestamps(frame: pd.DataFrame) -> pd.Series:
    if "timestamp" not in frame:
        raise AcquisitionDataError("Provider bars are missing timestamp")
    if frame.empty:
        return pd.Series(pd.DatetimeIndex([], tz=NY), index=frame.index)
    try:
        parsed = pd.to_datetime(frame["timestamp"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise AcquisitionDataError("Provider timestamps are malformed") from exc
    if not isinstance(parsed.dtype, pd.DatetimeTZDtype):
        raise AcquisitionDataError("Provider timestamps must be timezone-aware")
    return parsed.dt.tz_convert(NY)


def normalize_segment_bars(
    bars: pd.DataFrame,
    request: AcquisitionRequest,
    *,
    actual_feed: str | None,
    actual_feed_evidence: str = "provider_response_field",
    regular_expected_minutes: pd.DatetimeIndex | None = None,
) -> tuple[pd.DataFrame, NormalizationReport]:
    """Validate and normalize observed bars without filling absent minutes.

    The end timestamp is exclusive. Regular bars are additionally restricted to
    the authoritative exchange-calendar minute index. Missing observations stay
    absent so downstream completeness checks can see them.
    """
    frame = bars.copy()
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if missing := required.difference(frame.columns):
        raise AcquisitionDataError(f"Provider bars are missing columns: {', '.join(sorted(missing))}")
    actual_feed = str(actual_feed).lower() if actual_feed is not None else None
    if actual_feed is not None and actual_feed != request.requested_feed:
        raise AcquisitionDataError(
            f"Feed mismatch: requested {request.requested_feed}, provider metadata records {actual_feed}"
        )
    if actual_feed is not None and actual_feed_evidence != "provider_response_field":
        raise AcquisitionDataError(
            "Confirmed actual feed requires an explicit provider response field"
        )
    if actual_feed is None and actual_feed_evidence != "explicit_request_parameter_provider_did_not_echo_feed":
        raise AcquisitionDataError("Provider feed identity is unavailable without explicit provenance")
    numeric_columns = ["open", "high", "low", "close", "volume"]
    numeric_columns.extend(
        column for column in ("trade_count", "bar_vwap") if column in frame
    )
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[numeric_columns].isna().any().any() or not np.isfinite(
        frame[numeric_columns].to_numpy(dtype=float)
    ).all():
        raise AcquisitionDataError("Provider bars contain null or non-numeric OHLCV values")
    if (
        frame[["open", "high", "low", "close"]].le(0).any().any()
        or frame["volume"].lt(0).any()
        or ("trade_count" in frame and frame["trade_count"].lt(0).any())
        or ("bar_vwap" in frame and frame["bar_vwap"].le(0).any())
    ):
        raise AcquisitionDataError("Provider bars contain invalid price, volume, or trade values")
    inconsistent = (
        frame["high"].lt(frame[["open", "close"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close"]].min(axis=1))
        | frame["high"].lt(frame["low"])
    )
    if inconsistent.any():
        raise AcquisitionDataError("Provider bars contain inconsistent OHLC values")
    frame["timestamp"] = _timestamps(frame)
    if "symbol" in frame and not frame["symbol"].astype(str).str.upper().eq(request.symbol).all():
        raise AcquisitionDataError("Provider bars contain a mismatched symbol")
    duplicates = int(frame["timestamp"].duplicated(keep=False).sum())
    if duplicates:
        raise AcquisitionDataError(f"Duplicate provider timestamps: {duplicates} rows")
    out_of_order = not frame["timestamp"].is_monotonic_increasing
    local_dates = frame["timestamp"].dt.date
    cross_date = int(local_dates.ne(request.trading_date).sum())
    if cross_date:
        raise AcquisitionDataError(f"Cross-date provider bars: {cross_date}")
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    clock_window = frame["timestamp"].ge(request.start_timestamp) & frame["timestamp"].lt(request.end_timestamp)
    unexpected_1600 = int(
        (
            frame["timestamp"].dt.hour.eq(16)
            & frame["timestamp"].dt.minute.eq(0)
            & (request.segment is AcquisitionSegment.REGULAR)
        ).sum()
    )
    if request.segment is AcquisitionSegment.REGULAR:
        if regular_expected_minutes is None:
            raise ValueError("regular_expected_minutes is required for regular normalization")
        expected = pd.DatetimeIndex(regular_expected_minutes).tz_convert(NY)
        authoritative = frame["timestamp"].isin(expected)
    else:
        expected = pd.date_range(
            request.start_timestamp,
            request.end_timestamp - pd.Timedelta(1, unit="min"),
            freq="min",
        )
        authoritative = pd.Series(True, index=frame.index)
    accepted = clock_window & authoritative
    outside = int((~accepted).sum())
    normalized = frame.loc[accepted].reset_index(drop=True)
    ordered = [column for column in _CANONICAL_BAR_COLUMNS if column in normalized]
    ordered.extend(sorted(set(normalized.columns).difference(ordered)))
    normalized = normalized.loc[:, ordered]
    observed = pd.DatetimeIndex(normalized["timestamp"])
    report = NormalizationReport(
        request.segment.value,
        len(frame),
        len(normalized),
        len(expected),
        len(expected.difference(observed)),
        duplicates,
        out_of_order,
        cross_date,
        outside,
        unexpected_1600,
        request.requested_feed,
        actual_feed,
        actual_feed_evidence,
    )
    normalized.attrs.update(
        data_feed=request.requested_feed,
        actual_feed=actual_feed,
        actual_feed_evidence=actual_feed_evidence,
        acquisition_segment=request.segment.value,
        selection_cutoff=str(selection_cutoff(request.trading_date)),
    )
    return normalized, report


def file_sha256(path: Path) -> str:
    """Hash finalized file bytes using SHA-256."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exclusive_publish_text(path: Path, content: str) -> None:
    """Atomically publish new text without overwriting an existing path."""
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


def _portable_path(root: Path, path: Path) -> str:
    return str(path.relative_to(Path(root)))


def persist_acquisition(
    root: Path,
    request: AcquisitionRequest,
    raw_payload: dict,
    processed: pd.DataFrame,
    report: NormalizationReport,
    provider_metadata: dict,
) -> SegmentPaths:
    """Atomically publish a write-once segment and hashes of finalized files."""
    if report.requested_feed != request.requested_feed or report.segment != request.segment.value:
        raise AcquisitionDataError("Normalization report does not match acquisition request")
    metadata_feed = provider_metadata.get("actual_feed")
    if report.actual_feed != metadata_feed:
        raise AcquisitionDataError("Normalization and provider feed metadata disagree")
    metadata_evidence = provider_metadata.get("actual_feed_evidence")
    if metadata_evidence is not None and metadata_evidence != report.actual_feed_evidence:
        raise AcquisitionDataError("Normalization and provider feed evidence disagree")
    paths = research_segment_paths(root, request)
    final_paths = (paths.raw_response, paths.processed_bars, paths.metadata)
    if existing := [path for path in final_paths if path.exists()]:
        raise FileExistsError(f"Acquisition output is write-once and already exists: {existing[0]}")
    raw_content = json.dumps(raw_payload, indent=2, sort_keys=True, default=str) + "\n"
    processed_content = processed.to_csv(index=False, lineterminator="\n")
    created: list[Path] = []
    try:
        _exclusive_publish_text(paths.raw_response, raw_content)
        created.append(paths.raw_response)
        _exclusive_publish_text(paths.processed_bars, processed_content)
        created.append(paths.processed_bars)
        metadata = {
            "status": "success",
            "provider": provider_metadata.get("provider", "unknown"),
            "requested_endpoint": provider_metadata.get("requested_endpoint"),
            "actual_endpoint": provider_metadata.get("actual_endpoint"),
            "timeframe": provider_metadata.get("timeframe"),
            "adjustment": provider_metadata.get("adjustment"),
            "sort_order": provider_metadata.get("sort_order"),
            "symbol": request.symbol,
            "trading_date": str(request.trading_date),
            "segment": request.segment.value,
            "requested_feed": request.requested_feed,
            "actual_feed": provider_metadata.get("actual_feed"),
            "actual_feed_evidence": report.actual_feed_evidence,
            "requested_start_timestamp": request.start_timestamp.isoformat(),
            "requested_end_timestamp_exclusive": request.end_timestamp.isoformat(),
            "acquisition_timestamp": provider_metadata.get("acquisition_timestamp"),
            "calendar_id": request.calendar_id,
            "timezone_assumption": "America/New_York; provider timestamps converted from timezone-aware values",
            "dataset_vintage": request.dataset_vintage,
            "pagination": {
                "page_count": provider_metadata.get("page_count"),
                "pagination_occurred": provider_metadata.get("pagination_occurred"),
                "page_tokens_followed": provider_metadata.get("page_tokens_followed", 0),
                "page_record_counts": provider_metadata.get("page_record_counts", []),
                "page_token_sha256": provider_metadata.get("page_token_sha256", []),
            },
            "retry_count": provider_metadata.get("retry_count", 0),
            "provider_response_out_of_order": provider_metadata.get(
                "provider_response_out_of_order", False
            ),
            "provider_record_count": provider_metadata.get("total_bar_count"),
            "record_count": len(processed),
            "normalization": asdict(report),
            "raw_response_file": _portable_path(root, paths.raw_response),
            "processed_file": _portable_path(root, paths.processed_bars),
            "raw_response_sha256": file_sha256(paths.raw_response),
            "processed_sha256": file_sha256(paths.processed_bars),
        }
        _exclusive_publish_text(
            paths.metadata, json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )
        created.append(paths.metadata)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return paths


def persist_acquisition_failure(
    root: Path,
    request: AcquisitionRequest,
    error: Exception,
    *,
    provider: str,
    retry_count: int = 0,
    raw_payload: dict | None = None,
) -> Path:
    """Publish a write-once failure record and any returned raw response."""
    paths = research_segment_paths(root, request)
    path = paths.metadata
    final_paths = (paths.raw_response, paths.processed_bars, paths.metadata)
    if existing := [candidate for candidate in final_paths if candidate.exists()]:
        raise FileExistsError(
            f"Acquisition output is write-once and already exists: {existing[0]}"
        )
    created: list[Path] = []
    raw_hash = raw_file = None
    try:
        if raw_payload is not None:
            _exclusive_publish_text(
                paths.raw_response,
                json.dumps(raw_payload, indent=2, sort_keys=True, default=str) + "\n",
            )
            created.append(paths.raw_response)
            raw_hash = file_sha256(paths.raw_response)
            raw_file = _portable_path(root, paths.raw_response)
        payload = {
            "status": "failed",
            "provider": provider,
            "symbol": request.symbol,
            "trading_date": str(request.trading_date),
            "segment": request.segment.value,
            "requested_feed": request.requested_feed,
            "requested_start_timestamp": request.start_timestamp.isoformat(),
            "requested_end_timestamp_exclusive": request.end_timestamp.isoformat(),
            "failure_timestamp": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "dataset_vintage": request.dataset_vintage,
            "raw_response_file": raw_file,
            "raw_response_sha256": raw_hash,
        }
        _exclusive_publish_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        created.append(path)
    except Exception:
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise
    return path


def acquire_research_session(
    client: Any,
    calendar: Any,
    root: Path,
    *,
    symbol: str,
    trading_date: date,
    dataset_vintage: str,
    feed: str = "sip",
    calendar_id: str = "XNYS",
) -> tuple[SegmentPaths, SegmentPaths]:
    """Acquire and persist the two isolated Research Cohort V001 segments."""
    schedule = calendar.schedule(trading_date, calendar_id)
    requests = requests_for_session(symbol, trading_date, schedule, dataset_vintage, feed)
    return tuple(
        acquire_research_segment(
            client, root, request,
            regular_expected_minutes=(
                schedule.expected_minutes
                if request.segment is AcquisitionSegment.REGULAR
                else None
            ),
        )
        for request in requests
    )


def acquire_research_segment(
    client: Any,
    root: Path,
    request: AcquisitionRequest,
    *,
    regular_expected_minutes: pd.DatetimeIndex | None = None,
) -> SegmentPaths:
    """Acquire one write-once segment so broad jobs can resume safely."""
    payload = None
    try:
        payload, bars = client.get_bars_range(
            request.symbol,
            request.start_timestamp,
            request.end_timestamp,
            feed=request.requested_feed,
            segment=request.segment.value,
            trading_date=request.trading_date,
            dataset_vintage=request.dataset_vintage,
            allow_empty=request.segment is AcquisitionSegment.PREMARKET,
        )
        provider_metadata = payload.get("acquisition_metadata") or {}
        processed, report = normalize_segment_bars(
            bars,
            request,
            actual_feed=provider_metadata.get("actual_feed"),
            actual_feed_evidence=provider_metadata.get("actual_feed_evidence", ""),
            regular_expected_minutes=regular_expected_minutes,
        )
        return persist_acquisition(
            root, request, payload, processed, report, provider_metadata
        )
    except Exception as exc:
        if isinstance(exc, FileExistsError):
            raise
        partial_payload = payload or getattr(exc, "partial_payload", None)
        persist_acquisition_failure(
            root, request, exc, provider="alpaca",
            retry_count=getattr(exc, "retry_count", 0),
            raw_payload=partial_payload,
        )
        raise


def deterministic_calendar_plan(
    calendar: Any,
    *,
    cohort_start: date = date(2024, 6, 3),
    cohort_session_count: int = 60,
    warmup_session_count: int = 20,
    calendar_id: str = "XNYS",
) -> pd.DataFrame:
    """Create the fixed daily plan without inspecting symbols or outcomes."""
    if cohort_session_count < 1 or warmup_session_count < 0:
        raise ValueError("Session counts must be non-negative and cohort count must be positive")

    def sessions_from(start: date, count: int, direction: int) -> list[Any]:
        values, cursor = [], pd.Timestamp(start)
        while len(values) < count:
            try:
                schedule = calendar.schedule(cursor.date(), calendar_id)
                values.append(schedule)
            except NonTradingSessionError:
                pass
            cursor += pd.Timedelta(direction, unit="day")
        return values

    cohort = sessions_from(cohort_start, cohort_session_count, 1)
    prior_start = cohort_start - pd.Timedelta(1, unit="day")
    warmup = list(reversed(sessions_from(prior_start, warmup_session_count, -1)))
    rows = []
    for role, schedules in (("warmup", warmup), ("cohort", cohort)):
        for schedule in schedules:
            day = schedule.trading_date
            rows.append({
                "plan_order": len(rows) + 1,
                "trading_date": str(day),
                "session_role": role,
                "calendar_id": calendar_id,
                "premarket_start": premarket_open(day).isoformat(),
                "selection_cutoff_exclusive": selection_cutoff(day).isoformat(),
                "regular_open": schedule.open_timestamp.isoformat(),
                "regular_close_exclusive": schedule.close_timestamp.isoformat(),
                "expected_regular_minutes": len(schedule.expected_minutes),
            })
    return pd.DataFrame(rows)
