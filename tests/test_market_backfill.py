from datetime import date
import hashlib
import json

import pandas as pd
import pytest

from aml.market_backfill import (
    MarketInstrument, archive_failed_segment, backfill_job_lock, load_universe, plan_tasks,
    segment_state, trading_dates,
)
from aml.market_calendar import NonTradingSessionError
from aml.research_acquisition import SegmentPaths


def write_universe(path, rows):
    pd.DataFrame(rows, columns=["symbol", "market", "category", "notes"]).to_csv(path, index=False)


def test_universe_is_ordered_and_rejects_duplicates(tmp_path):
    path = tmp_path / "universe.csv"
    write_universe(path, [("spy", "S&P 500", "index", "proxy"), ("QQQ", "Nasdaq", "index", "proxy")])
    assert [item.symbol for item in load_universe(path)] == ["SPY", "QQQ"]
    write_universe(path, [("SPY", "one", "index", "proxy"), ("spy", "two", "index", "proxy")])
    with pytest.raises(ValueError, match="Duplicate universe symbol"):
        load_universe(path)


class WeekdayCalendar:
    def schedule(self, day, calendar_id):
        if day.weekday() >= 5:
            raise NonTradingSessionError("closed")
        return object()


def test_session_and_task_plans_are_deterministic():
    sessions = trading_dates(WeekdayCalendar(), date(2024, 1, 5), date(2024, 1, 8))
    assert sessions == (date(2024, 1, 5), date(2024, 1, 8))
    instruments = (
        MarketInstrument("SPY", "S&P", "index", "proxy"),
        MarketInstrument("QQQ", "Nasdaq", "index", "proxy"),
    )
    tasks = plan_tasks(instruments, sessions)
    assert [(task.trading_date, task.instrument.symbol) for task in tasks] == [
        (date(2024, 1, 5), "SPY"), (date(2024, 1, 5), "QQQ"),
        (date(2024, 1, 8), "SPY"), (date(2024, 1, 8), "QQQ"),
    ]


def test_segment_state_verifies_success_hashes_and_recognizes_failures(tmp_path):
    paths = SegmentPaths(tmp_path / "raw.json", tmp_path / "bars.csv", tmp_path / "metadata.json")
    assert segment_state(paths) == "missing"
    paths.raw_response.write_text("raw")
    paths.processed_bars.write_text("bars")
    paths.metadata.write_text(json.dumps({
        "status": "success",
        "raw_response_sha256": hashlib.sha256(b"raw").hexdigest(),
        "processed_sha256": hashlib.sha256(b"bars").hexdigest(),
    }))
    assert segment_state(paths) == "complete"
    paths.processed_bars.unlink()
    paths.raw_response.unlink()
    paths.metadata.write_text(json.dumps({"status": "failed"}))
    assert segment_state(paths) == "failed"


def test_segment_state_rejects_partial_output(tmp_path):
    paths = SegmentPaths(tmp_path / "raw.json", tmp_path / "bars.csv", tmp_path / "metadata.json")
    paths.raw_response.write_text("partial")
    with pytest.raises(RuntimeError, match="Incomplete write-once acquisition"):
        segment_state(paths)


def test_failed_attempt_is_archived_without_deletion(tmp_path):
    paths = SegmentPaths(tmp_path / "raw.json", tmp_path / "bars.csv", tmp_path / "metadata.json")
    paths.raw_response.write_text("partial provider response")
    paths.metadata.write_text(json.dumps({"status": "failed"}))
    archived = archive_failed_segment(paths)
    assert len(archived) == 2
    assert all(path.exists() for path in archived)
    assert not paths.raw_response.exists() and not paths.metadata.exists()
    assert segment_state(paths) == "missing"


def test_dataset_lock_rejects_concurrent_writer(tmp_path):
    with backfill_job_lock(tmp_path, "v001") as lock_path:
        assert lock_path.exists()
        with pytest.raises(RuntimeError, match="Another backfill process"):
            with backfill_job_lock(tmp_path, "v001"):
                pass
    with backfill_job_lock(tmp_path, "v001"):
        pass
