"""Integrity tests for segmented Research Cohort V001 acquisition."""

from datetime import date
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from aml.alpaca_rest import AlpacaREST
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.research_acquisition import (
    AcquisitionDataError, acquire_research_session,
    deterministic_calendar_plan, normalize_segment_bars, persist_acquisition,
    persist_acquisition_failure, requests_for_session, research_segment_paths,
)
from aml.settings import Settings


DAY = date(2024, 6, 3)


def bar(timestamp, symbol="TEST"):
    return {
        "timestamp": pd.Timestamp(timestamp), "symbol": symbol,
        "open": 10.0, "high": 10.1, "low": 9.9, "close": 10.0,
        "volume": 100, "trade_count": 2, "bar_vwap": 10.0,
    }


def requests(vintage="v1"):
    schedule = ExchangeCalendarsAdapter().schedule(DAY, "XNYS")
    return schedule, requests_for_session("TEST", DAY, schedule, vintage)


def test_premarket_boundaries_are_0400_inclusive_and_0925_exclusive():
    _, (request, _) = requests()
    bars = pd.DataFrame([
        bar("2024-06-03 04:00:00-04:00"),
        bar("2024-06-03 09:24:00-04:00"),
        bar("2024-06-03 09:25:00-04:00"),
    ])
    normalized, report = normalize_segment_bars(bars, request, actual_feed="sip")
    assert normalized["timestamp"].dt.strftime("%H:%M").tolist() == ["04:00", "09:24"]
    assert report.outside_requested_window_count == 1
    assert report.expected_minute_count == 325


def test_regular_normalization_uses_authoritative_left_labeled_index():
    schedule, (_, request) = requests()
    bars = pd.DataFrame([
        bar("2024-06-03 15:59:00-04:00"),
        bar("2024-06-03 09:30:00-04:00"),
        bar("2024-06-03 16:00:00-04:00"),
    ])
    normalized, report = normalize_segment_bars(
        bars, request, actual_feed="sip",
        regular_expected_minutes=schedule.expected_minutes,
    )
    assert normalized["timestamp"].dt.strftime("%H:%M").tolist() == ["09:30", "15:59"]
    assert report.out_of_order
    assert report.unexpected_1600_bar_count == 1
    assert report.outside_requested_window_count == 1
    assert report.missing_timestamp_count == 388


def test_duplicate_cross_date_and_feed_mismatch_fail_closed():
    _, (request, _) = requests()
    duplicate = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")] * 2)
    with pytest.raises(AcquisitionDataError, match="Duplicate"):
        normalize_segment_bars(duplicate, request, actual_feed="sip")
    crossed = pd.DataFrame([bar("2024-06-04 04:00:00-04:00")])
    with pytest.raises(AcquisitionDataError, match="Cross-date"):
        normalize_segment_bars(crossed, request, actual_feed="sip")
    with pytest.raises(AcquisitionDataError, match="Feed mismatch"):
        normalize_segment_bars(pd.DataFrame([bar("2024-06-03 04:00:00-04:00")]), request, actual_feed="iex")


def test_null_or_inconsistent_ohlcv_fails_closed():
    _, (request, _) = requests()
    missing_close = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    missing_close.loc[0, "close"] = None
    with pytest.raises(AcquisitionDataError, match="null or non-numeric"):
        normalize_segment_bars(missing_close, request, actual_feed="sip")
    inconsistent = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    inconsistent.loc[0, "high"] = 9.0
    with pytest.raises(AcquisitionDataError, match="inconsistent OHLC"):
        normalize_segment_bars(inconsistent, request, actual_feed="sip")


def test_processed_column_order_is_canonical():
    _, (request, _) = requests()
    original = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    shuffled = original.loc[:, reversed(original.columns)]
    first, _ = normalize_segment_bars(original, request, actual_feed="sip")
    second, _ = normalize_segment_bars(shuffled, request, actual_feed="sip")
    pd.testing.assert_frame_equal(first, second)


def test_calendar_plan_is_deterministic_and_contains_warmup_and_early_close():
    calendar = ExchangeCalendarsAdapter()
    first = deterministic_calendar_plan(calendar)
    second = deterministic_calendar_plan(calendar)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 80
    assert first.iloc[0]["trading_date"] == "2024-05-03"
    assert first.iloc[19]["trading_date"] == "2024-05-31"
    assert first.iloc[20]["trading_date"] == "2024-06-03"
    assert first.iloc[-1]["trading_date"] == "2024-08-27"
    july_third = first.loc[first["trading_date"].eq("2024-07-03")].iloc[0]
    assert july_third["expected_regular_minutes"] == 210
    assert "13:00:00-04:00" in july_third["regular_close_exclusive"]


def test_segment_paths_and_metadata_preserve_feed_vintage_and_hashes(tmp_path):
    _, (request, _) = requests("dataset-2024-06")
    frame = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    normalized, report = normalize_segment_bars(frame, request, actual_feed="sip")
    raw = {"bars": [{"t": "2024-06-03T08:00:00Z"}], "next_page_token": None}
    paths = persist_acquisition(
        tmp_path, request, raw, normalized, report,
        {
            "provider": "alpaca", "actual_feed": "sip", "page_count": 1,
            "pagination_occurred": False, "page_tokens_followed": 0,
            "acquisition_timestamp": "2024-06-03T13:26:00Z", "retry_count": 0,
        },
    )
    metadata = json.loads(paths.metadata.read_text())
    assert metadata["requested_feed"] == metadata["actual_feed"] == "sip"
    assert metadata["dataset_vintage"] == "dataset-2024-06"
    assert metadata["record_count"] == 1
    assert len(metadata["raw_response_sha256"]) == len(metadata["processed_sha256"]) == 64
    assert "dataset-2024-06/sip/TEST/2024-06-03" in str(paths.processed_bars)
    assert "secret" not in paths.metadata.read_text().lower()


def test_alpaca_explicit_range_preserves_feed_window_and_pagination_provenance():
    pages = [
        {"bars": [{"t": "2024-06-03T08:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}], "next_page_token": "next"},
        {"bars": [{"t": "2024-06-03T08:01:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}], "next_page_token": None},
    ]
    client = AlpacaREST(Settings("key", "secret", "iex"))
    calls = []
    def get(url, params):
        calls.append(dict(params))
        return pages[len(calls) - 1]
    client._get = get
    payload, frame = client.get_bars_range(
        "TEST", "2024-06-03 04:00:00-04:00", "2024-06-03 09:25:00-04:00",
        feed="sip", segment="premarket", trading_date=DAY,
        dataset_vintage="v1", allow_empty=True,
    )
    metadata = payload["acquisition_metadata"]
    assert [call["feed"] for call in calls] == ["sip", "sip"]
    assert calls[1]["page_token"] == "next"
    assert calls[0]["start"].startswith("2024-06-03T08:00:00")
    assert calls[0]["end"].startswith("2024-06-03T13:25:00")
    assert metadata["page_record_counts"] == [1, 1]
    assert len(metadata["page_token_sha256"]) == 1
    assert metadata["actual_feed"] is None
    assert metadata["actual_feed_evidence"] == (
        "explicit_request_parameter_provider_did_not_echo_feed"
    )
    assert payload["provider_pages"] == pages
    assert len(frame) == 2


def test_alpaca_rejects_malformed_or_feed_mismatched_pages():
    client = AlpacaREST(Settings("key", "secret", "iex"))
    client._get = lambda _url, _params: {"bars": []}
    with pytest.raises(ValueError, match="bars and next_page_token"):
        client.get_bars_range(
            "TEST", "2024-06-03 04:00:00-04:00", "2024-06-03 09:25:00-04:00",
            feed="sip", segment="premarket", trading_date=DAY,
            dataset_vintage="v1", allow_empty=True,
        )
    client._get = lambda _url, _params: {
        "bars": [], "next_page_token": None, "feed": "iex",
    }
    with pytest.raises(ValueError, match="feed mismatch"):
        client.get_bars_range(
            "TEST", "2024-06-03 04:00:00-04:00", "2024-06-03 09:25:00-04:00",
            feed="sip", segment="premarket", trading_date=DAY,
            dataset_vintage="v1", allow_empty=True,
        )


def test_pagination_failure_retains_completed_provider_pages():
    pages = [{
        "bars": [{"t": "2024-06-03T08:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}],
        "next_page_token": "next",
    }]
    client = AlpacaREST(Settings("key", "secret", "iex"))
    calls = 0

    def get(_url, _params):
        nonlocal calls
        calls += 1
        if calls == 1:
            return pages[0]
        raise RuntimeError("second page unavailable")

    client._get = get
    with pytest.raises(RuntimeError, match="second page unavailable") as caught:
        client.get_bars_range(
            "TEST", "2024-06-03 04:00:00-04:00", "2024-06-03 09:25:00-04:00",
            feed="sip", segment="premarket", trading_date=DAY,
            dataset_vintage="v1", allow_empty=True,
        )
    assert caught.value.partial_payload["status"] == "partial_failure"
    assert caught.value.partial_payload["provider_pages"] == pages
    assert caught.value.partial_payload["completed_page_count"] == 1


def test_unconfirmed_feed_requires_explicit_request_provenance():
    _, (request, _) = requests()
    bars = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    with pytest.raises(AcquisitionDataError, match="feed identity"):
        normalize_segment_bars(bars, request, actual_feed=None)
    normalized, report = normalize_segment_bars(
        bars,
        request,
        actual_feed=None,
        actual_feed_evidence="explicit_request_parameter_provider_did_not_echo_feed",
    )
    assert len(normalized) == 1
    assert report.actual_feed is None


def test_acquisition_outputs_are_write_once_and_hash_finalized_bytes(tmp_path):
    _, (request, _) = requests("immutable-v1")
    frame = pd.DataFrame([bar("2024-06-03 04:00:00-04:00")])
    normalized, report = normalize_segment_bars(frame, request, actual_feed="sip")
    raw = {"bars": [], "next_page_token": None}
    metadata = {
        "provider": "alpaca", "actual_feed": "sip", "page_count": 1,
        "pagination_occurred": False, "acquisition_timestamp": "2024-06-03T13:26:00Z",
    }
    paths = persist_acquisition(
        tmp_path, request, raw, normalized, report, metadata
    )
    original = paths.raw_response.read_bytes(), paths.processed_bars.read_bytes()
    saved = json.loads(paths.metadata.read_text())
    assert saved["raw_response_sha256"] == hashlib.sha256(original[0]).hexdigest()
    assert saved["processed_sha256"] == hashlib.sha256(original[1]).hexdigest()
    assert not Path(saved["raw_response_file"]).is_absolute()
    with pytest.raises(FileExistsError, match="write-once"):
        persist_acquisition(tmp_path, request, raw, normalized, report, metadata)
    assert original == (
        paths.raw_response.read_bytes(), paths.processed_bars.read_bytes()
    )


def test_normalization_failure_preserves_returned_raw_response(tmp_path):
    _, (request, _) = requests("failure-raw-v1")
    raw = {"bars": [{"t": "malformed"}], "next_page_token": None}
    metadata_path = persist_acquisition_failure(
        tmp_path,
        request,
        AcquisitionDataError("invalid timestamp"),
        provider="alpaca",
        raw_payload=raw,
    )
    saved = json.loads(metadata_path.read_text())
    raw_path = tmp_path / saved["raw_response_file"]
    assert json.loads(raw_path.read_text()) == raw
    assert saved["raw_response_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert not research_segment_paths(tmp_path, request).processed_bars.exists()


def test_session_requests_follow_dst_offsets():
    calendar = ExchangeCalendarsAdapter()
    winter = date(2024, 2, 5)
    summer = date(2024, 6, 3)
    winter_request = requests_for_session(
        "TEST", winter, calendar.schedule(winter, "XNYS"), "v1"
    )[0]
    summer_request = requests_for_session(
        "TEST", summer, calendar.schedule(summer, "XNYS"), "v1"
    )[0]
    assert winter_request.start_timestamp.isoformat().endswith("-05:00")
    assert summer_request.start_timestamp.isoformat().endswith("-04:00")


def test_failure_metadata_is_auditable_and_contains_no_credentials(tmp_path):
    _, (request, _) = requests("failed-v1")
    path = persist_acquisition_failure(
        tmp_path, request, RuntimeError("HTTP 503 unavailable"),
        provider="alpaca", retry_count=2,
    )
    payload = json.loads(path.read_text())
    assert payload["status"] == "failed"
    assert payload["retry_count"] == 2
    assert payload["error_type"] == "RuntimeError"
    assert "key" not in payload and "headers" not in payload


def test_acquire_session_requests_isolated_segments_and_allows_empty_premarket(tmp_path):
    class Client:
        def __init__(self): self.calls = []
        def get_bars_range(self, symbol, start, end, **kwargs):
            self.calls.append((start, end, kwargs))
            rows = [] if kwargs["segment"] == "premarket" else [bar("2024-06-03 09:30:00-04:00")]
            metadata = {
                "provider": "alpaca", "actual_feed": kwargs["feed"],
                "actual_feed_evidence": "provider_response_field",
                "page_count": 1, "pagination_occurred": False,
                "page_tokens_followed": 0, "acquisition_timestamp": "2024-06-03T14:00:00Z",
            }
            return {"bars": [], "acquisition_metadata": metadata}, pd.DataFrame(rows, columns=list(bar("2024-06-03 09:30:00-04:00")))
    client = Client()
    saved = acquire_research_session(
        client, ExchangeCalendarsAdapter(), tmp_path, symbol="TEST",
        trading_date=DAY, dataset_vintage="dry-run-v1",
    )
    assert [call[2]["segment"] for call in client.calls] == ["premarket", "regular"]
    assert client.calls[0][2]["allow_empty"] is True
    assert client.calls[1][2]["allow_empty"] is False
    assert client.calls[0][1].strftime("%H:%M") == "09:25"
    assert client.calls[1][1].strftime("%H:%M") == "16:00"
    assert saved[0].processed_bars != saved[1].processed_bars
    assert research_segment_paths(tmp_path, requests("dry-run-v1")[1][0]) == saved[0]
