from datetime import date
import json

import pandas as pd
import pytest

from aml.alpaca_rest import AlpacaDataPermissionError, AlpacaREST
from aml.batch_evaluation import QualityPolicy
from aml.feed_comparison import (
    compare_historical_feeds,
    load_feed_comparison,
    write_feed_comparison,
)
from aml.market_halts import HaltSchedule
from aml.settings import Settings, historical_feed_from_env


DAY = date(2024, 1, 2)


def policy():
    return QualityPolicy(
        configuration_version="test-v1",
        complete_session_maximum_missing_percentage=0.01,
        usable_session_maximum_missing_percentage=0.50,
        excluded_quality_bands=("missing_heavy",),
        exclude_quality_flagged_sessions=True,
        require_clean_git_worktree=True,
    )


def bars(minutes, *, changed=False):
    timestamps = pd.DatetimeIndex(
        [f"2024-01-02 09:{minute:02d}:00-05:00" for minute in minutes]
    )
    close = [101.0 if changed and index == 0 else 100.0 for index in range(len(minutes))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": close,
            "volume": 1000,
        }
    )


def comparison():
    expected = pd.date_range(
        "2024-01-02 09:30:00-05:00", periods=3, freq="min"
    )
    return compare_historical_feeds(
        bars([30, 31]),
        bars([30, 32], changed=True),
        symbol="aapl",
        trading_date=str(DAY),
        expected_minutes=expected,
        quality_policy=policy(),
        halt_schedule=HaltSchedule("AAPL", DAY),
        input_hashes={"regular_bars:sip": "b", "regular_bars:iex": "a"},
    )


def test_comparison_metrics_and_output_are_deterministic(tmp_path):
    first_summary, first_rows = comparison()
    second_summary, second_rows = comparison()
    assert first_summary == second_summary
    pd.testing.assert_frame_equal(first_rows, second_rows)
    assert first_summary["feeds"]["iex"]["row_count"] == 2
    assert first_summary["feeds"]["sip"]["missing_minute_count"] == 1
    assert first_summary["feeds"]["iex"]["duplicate_timestamp_count"] == 0
    assert first_summary["feeds"]["sip"]["total_volume"] == 2000
    assert first_summary["rows_where_ohlcv_values_differ"] == 3
    assert first_summary["requested_feeds"] == ["iex", "sip"]
    directory = write_feed_comparison(tmp_path, first_summary, first_rows)
    assert write_feed_comparison(tmp_path, second_summary, second_rows) == directory
    metadata, loaded = load_feed_comparison(directory)
    assert metadata["comparison_id"] == first_summary["comparison_id"]
    assert loaded.columns.tolist() == first_rows.columns.tolist()
    assert (directory / "comparison.json").read_bytes().endswith(b"\n")


def test_comparison_completion_validation_detects_tampering(tmp_path):
    summary, rows = comparison()
    directory = write_feed_comparison(tmp_path, summary, rows)
    (directory / "ohlcv_differences.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_feed_comparison(directory)


def test_historical_feed_environment_parsing(monkeypatch):
    monkeypatch.setenv("ALPACA_HISTORICAL_DATA_FEED", " IEX ")
    assert historical_feed_from_env() == "iex"
    monkeypatch.setenv("ALPACA_HISTORICAL_DATA_FEED", "free")
    with pytest.raises(RuntimeError, match="expected one of: iex, sip"):
        historical_feed_from_env()


def test_settings_store_explicit_historical_feed(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_DATA_FEED", "iex")
    monkeypatch.setenv("ALPACA_HISTORICAL_DATA_FEED", "sip")
    settings = Settings.from_env()
    assert settings.data_feed == "iex"
    assert settings.historical_data_feed == "sip"


def test_sip_permission_error_is_actionable_and_never_falls_back(monkeypatch):
    calls = []

    class Response:
        status_code = 403
        text = json.dumps({"message": "subscription does not permit SIP"})

    def get(*args, **kwargs):
        calls.append(kwargs["params"].copy())
        return Response()

    monkeypatch.setattr("requests.get", get)
    client = AlpacaREST(Settings("key", "secret", "iex"))
    with pytest.raises(
        AlpacaDataPermissionError,
        match="SIP.*required historical data plan.*not retried",
    ):
        client.get_minute_bars("AAPL", DAY, feed="sip")
    assert [call["feed"] for call in calls] == ["sip"]
