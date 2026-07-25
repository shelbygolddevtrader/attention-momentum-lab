"""Resumable, explicit-universe Alpaca minute-bar backfills."""

from dataclasses import dataclass
from datetime import date, timedelta
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

import pandas as pd

from aml.market_calendar import NonTradingSessionError
from aml.research_acquisition import (
    AcquisitionRequest,
    AcquisitionSegment,
    acquire_research_segment,
    file_sha256,
    requests_for_session,
    research_segment_paths,
)


UNIVERSE_COLUMNS = ("symbol", "market", "category", "notes")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


@dataclass(frozen=True)
class MarketInstrument:
    symbol: str
    market: str
    category: str
    notes: str


@dataclass(frozen=True)
class BackfillTask:
    instrument: MarketInstrument
    trading_date: date


@dataclass(frozen=True)
class BackfillResult:
    symbol: str
    trading_date: date
    downloaded_segments: int
    skipped_segments: int
    status: str
    detail: str = ""


def load_universe(path: Path) -> tuple[MarketInstrument, ...]:
    """Load an ordered, duplicate-free universe from a reviewable CSV."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(UNIVERSE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Universe is missing columns: {', '.join(sorted(missing))}")
    instruments = []
    seen = set()
    for row in frame.loc[:, UNIVERSE_COLUMNS].itertuples(index=False):
        symbol = row.symbol.strip().upper()
        if not _SYMBOL.fullmatch(symbol):
            raise ValueError(f"Invalid universe symbol: {symbol!r}")
        if symbol in seen:
            raise ValueError(f"Duplicate universe symbol: {symbol}")
        values = [row.market.strip(), row.category.strip(), row.notes.strip()]
        if any(not value for value in values):
            raise ValueError(f"Universe metadata is incomplete for {symbol}")
        seen.add(symbol)
        instruments.append(MarketInstrument(symbol, *values))
    if not instruments:
        raise ValueError("Universe must contain at least one instrument")
    return tuple(instruments)


def trading_dates(calendar: Any, start: date, end: date, calendar_id: str = "XNYS") -> tuple[date, ...]:
    """Return authoritative sessions for an inclusive date range."""
    if end < start:
        raise ValueError("Backfill end date must be on or after start date")
    sessions = []
    cursor = start
    while cursor <= end:
        try:
            calendar.schedule(cursor, calendar_id)
            sessions.append(cursor)
        except NonTradingSessionError:
            pass
        cursor += timedelta(days=1)
    if not sessions:
        raise ValueError("Backfill range contains no exchange sessions")
    return tuple(sessions)


def plan_tasks(
    instruments: tuple[MarketInstrument, ...], sessions: tuple[date, ...]
) -> tuple[BackfillTask, ...]:
    """Plan by date then configured symbol order for deterministic pilots."""
    return tuple(
        BackfillTask(instrument, trading_date)
        for trading_date in sessions
        for instrument in instruments
    )


def _metadata(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unreadable acquisition metadata: {path}") from exc


def segment_state(paths) -> str:
    """Return missing, complete, or failed; reject inconsistent file sets."""
    existence = tuple(path.exists() for path in (paths.raw_response, paths.processed_bars, paths.metadata))
    if not any(existence):
        return "missing"
    if paths.metadata.exists():
        metadata = _metadata(paths.metadata)
        if metadata.get("status") == "failed" and not paths.processed_bars.exists():
            return "failed"
    if not all(existence):
        raise RuntimeError(f"Incomplete write-once acquisition at {paths.metadata.parent}")
    metadata = _metadata(paths.metadata)
    if metadata.get("status") != "success":
        raise RuntimeError(f"Unexpected acquisition status at {paths.metadata}")
    expected = {
        paths.raw_response: metadata.get("raw_response_sha256"),
        paths.processed_bars: metadata.get("processed_sha256"),
    }
    for path, digest in expected.items():
        if not digest or file_sha256(path) != digest:
            raise RuntimeError(f"Acquisition hash mismatch: {path}")
    return "complete"


def archive_failed_segment(paths) -> tuple[Path, ...]:
    """Preserve a failed attempt before retrying its fixed write-once paths."""
    if segment_state(paths) != "failed":
        raise ValueError("Only failed acquisition records can be archived for retry")
    archive = paths.metadata.parent / "failed_attempts"
    archive.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while any((archive / f"{attempt:03d}_{path.name}").exists() for path in (paths.raw_response, paths.metadata)):
        attempt += 1
    moved = []
    for path in (paths.raw_response, paths.processed_bars, paths.metadata):
        if path.exists():
            destination = archive / f"{attempt:03d}_{path.name}"
            shutil.move(str(path), destination)
            moved.append(destination)
    return tuple(moved)


def run_task(
    client: Any,
    calendar: Any,
    root: Path,
    task: BackfillTask,
    *,
    dataset_vintage: str,
    feed: str = "sip",
    calendar_id: str = "XNYS",
    retry_failures: bool = False,
) -> BackfillResult:
    """Download only missing segments for one symbol/session."""
    schedule = calendar.schedule(task.trading_date, calendar_id)
    requests = requests_for_session(
        task.instrument.symbol, task.trading_date, schedule, dataset_vintage, feed
    )
    downloaded = skipped = 0
    for request in requests:
        paths = research_segment_paths(root, request)
        state = segment_state(paths)
        if state == "complete":
            skipped += 1
            continue
        if state == "failed":
            if retry_failures:
                archive_failed_segment(paths)
            else:
                return BackfillResult(
                    task.instrument.symbol, task.trading_date, downloaded, skipped,
                    "failed", f"Prior failure record: {paths.metadata}",
                )
        acquire_research_segment(
            client,
            root,
            request,
            regular_expected_minutes=(
                schedule.expected_minutes
                if request.segment is AcquisitionSegment.REGULAR
                else None
            ),
        )
        downloaded += 1
    status = "skipped" if downloaded == 0 else "completed"
    return BackfillResult(
        task.instrument.symbol, task.trading_date, downloaded, skipped, status
    )


def universe_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def backfill_job_lock(root: Path, dataset_vintage: str):
    """Prevent concurrent writers for one dataset vintage."""
    lock_path = Path(root) / "data" / "research" / dataset_vintage / ".backfill.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Another backfill process already holds the dataset lock: {lock_path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "dataset_vintage": dataset_vintage}) + "\n")
        handle.flush()
        try:
            yield lock_path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
