"""Tests for the bounded, non-validation Alpaca SIP engineering rehearsal."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
import pytest

from aml.engineering_rehearsal import (
    ENGINEERING_EVIDENCE_CLASS,
    EngineeringRehearsalScope,
    acquire_or_resume_rehearsal,
    persist_rehearsal_scope_manifest,
    rehearsal_scope_manifest,
    run_engineering_rehearsal,
)
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.portfolio_artifacts import discover_completed_runs
from aml.research_acquisition import (
    AcquisitionDataError,
    requests_for_session,
    research_segment_paths,
)


class FixedClient:
    """Return fixed provider-shaped frames without network access."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_bars_range(
        self,
        symbol,
        start,
        end,
        *,
        feed,
        segment,
        trading_date,
        dataset_vintage,
        allow_empty,
    ):
        self.calls.append({
            "symbol": symbol,
            "start": start,
            "end": end,
            "feed": feed,
            "segment": segment,
            "allow_empty": allow_empty,
        })
        if segment == "premarket":
            timestamps = pd.DatetimeIndex([
                pd.Timestamp("2026-07-15 04:00", tz="America/New_York"),
                pd.Timestamp("2026-07-15 09:24", tz="America/New_York"),
            ])
        else:
            timestamps = pd.date_range(
                "2026-07-15 09:30", periods=40, freq="min",
                tz="America/New_York",
            )
        bars = pd.DataFrame({
            "timestamp": timestamps,
            "symbol": symbol,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000,
            "trade_count": 10,
            "bar_vwap": 100.0,
        })
        fetched = "2026-07-16T00:00:00+00:00"
        metadata = {
            "provider": "alpaca",
            "status": "success",
            "symbol": symbol,
            "trading_date": str(trading_date),
            "segment": segment,
            "requested_feed": feed,
            "actual_feed": None,
            "actual_feed_evidence": (
                "explicit_request_parameter_provider_did_not_echo_feed"
            ),
            "requested_endpoint": "https://data.alpaca.markets/v2/stocks/AAPL/bars",
            "actual_endpoint": "https://data.alpaca.markets/v2/stocks/AAPL/bars",
            "timeframe": "1Min",
            "adjustment": "all",
            "sort_order": "asc",
            "page_count": 1,
            "total_bar_count": len(bars),
            "acquisition_timestamp": fetched,
            "pagination_occurred": False,
            "page_tokens_followed": 0,
            "page_record_counts": [len(bars)],
            "page_token_sha256": [],
            "retry_count": 0,
            "provider_response_out_of_order": False,
            "dataset_vintage": dataset_vintage,
        }
        raw_bars = [{"t": timestamp.isoformat()} for timestamp in timestamps]
        payload = {
            "bars": raw_bars,
            "next_page_token": None,
            "provider_pages": [{"bars": raw_bars, "next_page_token": None}],
            "acquisition_metadata": metadata,
        }
        return payload, bars


def test_scope_is_fixed_outcome_free_and_separate_from_production() -> None:
    scope = EngineeringRehearsalScope()
    manifest = rehearsal_scope_manifest(scope)
    assert scope.symbol == "AAPL"
    assert str(scope.trading_date) == "2026-07-15"
    assert manifest["evidence_class"] == ENGINEERING_EVIDENCE_CLASS
    assert manifest["production_cohort_member"] is False
    assert manifest["production_cohort_rules_modified"] is False
    assert manifest["point_in_time_universe"].startswith("unavailable_")
    assert manifest["negative_corporate_action_evidence"].startswith("unavailable_")
    assert manifest["commercial_retention_rights"].startswith("unverified_")
    assert "pnl" not in json.dumps(manifest).lower()
    with pytest.raises(ValueError, match="fixed"):
        EngineeringRehearsalScope(symbol="GME")


def test_scope_manifest_is_deterministic_and_write_once(tmp_path: Path) -> None:
    first = persist_rehearsal_scope_manifest(tmp_path)
    original = first.read_bytes()
    second = persist_rehearsal_scope_manifest(tmp_path)
    assert first == second
    assert second.read_bytes() == original
    first.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="conflicts"):
        persist_rehearsal_scope_manifest(tmp_path)


def test_acquisition_is_bounded_atomic_and_resumable(tmp_path: Path) -> None:
    client = FixedClient()
    calendar = ExchangeCalendarsAdapter()
    first = acquire_or_resume_rehearsal(client, calendar, tmp_path)
    assert len(client.calls) == 2
    assert {call["segment"] for call in client.calls} == {"premarket", "regular"}
    assert {call["feed"] for call in client.calls} == {"sip"}
    assert first[-1] is False
    second = acquire_or_resume_rehearsal(client, calendar, tmp_path)
    assert second[-1] is True
    assert len(client.calls) == 2


def test_partial_or_tampered_cache_fails_closed(tmp_path: Path) -> None:
    scope = EngineeringRehearsalScope()
    calendar = ExchangeCalendarsAdapter()
    schedule = calendar.schedule(scope.trading_date, scope.calendar_id)
    premarket, _ = requests_for_session(
        scope.symbol,
        scope.trading_date,
        schedule,
        scope.dataset_vintage,
        scope.feed,
    )
    paths = research_segment_paths(tmp_path, premarket)
    paths.raw_response.parent.mkdir(parents=True)
    paths.raw_response.write_text("{}\n", encoding="utf-8")
    with pytest.raises(AcquisitionDataError, match="partial"):
        acquire_or_resume_rehearsal(FixedClient(), calendar, tmp_path)

    other = tmp_path / "other"
    acquire_or_resume_rehearsal(FixedClient(), calendar, other)
    other_paths = research_segment_paths(other, premarket)
    other_paths.processed_bars.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(AcquisitionDataError, match="hash mismatch"):
        acquire_or_resume_rehearsal(FixedClient(), calendar, other)


def test_end_to_end_run_preserves_provenance_and_resumes(tmp_path: Path) -> None:
    client = FixedClient()
    calendar = ExchangeCalendarsAdapter()
    artifact_root = tmp_path / "artifacts" / "portfolio"
    strategy = tmp_path / "config" / "strategy_v001.yaml"
    strategy.parent.mkdir(parents=True)
    strategy.write_bytes(Path("config/strategy_v001.yaml").read_bytes())
    first = run_engineering_rehearsal(
        client,
        calendar,
        tmp_path,
        artifact_root,
        source_commit="a" * 40,
        source_worktree_dirty=False,
        execution_timestamp=pd.Timestamp(datetime(2026, 7, 16, tzinfo=timezone.utc)),
    )
    second = run_engineering_rehearsal(
        client,
        calendar,
        tmp_path,
        artifact_root,
        source_commit="a" * 40,
        source_worktree_dirty=False,
        execution_timestamp=pd.Timestamp(datetime(2026, 7, 17, tzinfo=timezone.utc)),
    )
    assert first.run_id == second.run_id
    assert not first.acquisition_cache_reused
    assert second.acquisition_cache_reused
    assert first.premarket_bar_count == 2
    assert first.regular_bar_count == 40
    metadata = json.loads(
        (first.artifact_directory / "run_metadata.json").read_text(encoding="utf-8")
    )
    provenance = metadata["provenance"]
    assert metadata["run_label"] == "development"
    assert provenance["evidence_class"] == ENGINEERING_EVIDENCE_CLASS
    assert provenance["not_validation_evidence"] is True
    assert provenance["requested_feed"] == "sip"
    assert provenance["strategy_employee"]["strategy_version"] == "0.1.1"
    assert len(metadata["input_hashes"]) == 8
    assert discover_completed_runs(artifact_root) == [first.artifact_directory]
