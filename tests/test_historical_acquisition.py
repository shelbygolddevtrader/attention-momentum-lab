from datetime import date
import json

import pandas as pd
import pytest

from aml.alpaca_rest import AlpacaREST
from aml.cli import fetch, parser
from aml.data_paths import (
    HISTORICAL_DATA_FEED, artifact_directory, feed_paths, load_bars,
    validate_replay_feed,
)
from aml.settings import Settings


DAY = date(2024, 1, 2)


def raw_bar(minute, close=100.0):
    return {
        "t": f"2024-01-02T14:{minute:02d}:00Z", "o": close, "h": close + 1,
        "l": close - 1, "c": close, "v": 1000, "n": 10, "vw": close,
    }


def client_with_pages(pages):
    client = AlpacaREST(Settings("key", "secret", "iex"))
    calls = []

    def get(url, params):
        calls.append((url, dict(params)))
        return pages[len(calls) - 1]

    client._get = get
    return client, calls


def test_historical_cli_defaults_to_sip_and_accepts_explicit_iex(monkeypatch):
    monkeypatch.delenv("ALPACA_HISTORICAL_DATA_FEED", raising=False)
    default = parser().parse_args(["fetch", "--symbol", "AAPL", "--date", "2024-01-02"])
    explicit = parser().parse_args(["fetch", "--symbol", "AAPL", "--date", "2024-01-02", "--feed", "iex"])
    assert default.feed == HISTORICAL_DATA_FEED == "sip"
    assert explicit.feed == "iex"
    with pytest.raises(SystemExit):
        parser().parse_args(["fetch", "--symbol", "AAPL", "--date", "2024-01-02", "--feed", "bad"])


def test_historical_cli_uses_configured_feed_default(monkeypatch):
    monkeypatch.setenv("ALPACA_HISTORICAL_DATA_FEED", "iex")
    configured = parser().parse_args(
        ["fetch", "--symbol", "AAPL", "--date", "2024-01-02"]
    )
    assert configured.feed == "iex"


def test_null_token_uses_one_request_and_sends_feed():
    client, calls = client_with_pages([{"bars": [raw_bar(30)], "symbol": "AAPL", "next_page_token": None}])
    payload, frame = client.get_minute_bars("AAPL", DAY, feed="sip")
    assert len(calls) == 1
    assert calls[0][1]["feed"] == "sip"
    assert "page_token" not in calls[0][1]
    assert len(frame) == 1
    assert payload["acquisition_metadata"]["page_count"] == 1
    assert not payload["acquisition_metadata"]["pagination_occurred"]


def test_omitted_fetch_feed_preserves_configured_live_feed():
    client, calls = client_with_pages([{"bars": [raw_bar(30)], "next_page_token": None}])
    client.get_minute_bars("AAPL", DAY)
    assert calls[0][1]["feed"] == "iex"


def test_multiple_pages_are_combined_and_token_and_feed_are_sent():
    pages = [
        {"bars": [raw_bar(30)], "symbol": "AAPL", "next_page_token": "next"},
        {"bars": [raw_bar(31)], "symbol": "AAPL", "next_page_token": None},
    ]
    client, calls = client_with_pages(pages)
    payload, frame = client.get_minute_bars("AAPL", DAY, feed="iex")
    assert frame["timestamp"].dt.minute.tolist() == [30, 31]
    assert [call[1]["feed"] for call in calls] == ["iex", "iex"]
    assert calls[1][1]["page_token"] == "next"
    assert payload["acquisition_metadata"]["page_count"] == 2
    assert payload["acquisition_metadata"]["pagination_occurred"]


def test_repeated_page_token_fails_clearly():
    pages = [
        {"bars": [raw_bar(30)], "next_page_token": "same"},
        {"bars": [raw_bar(31)], "next_page_token": "same"},
    ]
    client, _ = client_with_pages(pages)
    with pytest.raises(ValueError, match="Repeated Alpaca next_page_token"):
        client.get_minute_bars("AAPL", DAY, feed="sip")


def test_duplicate_timestamps_across_pages_fail_clearly():
    pages = [
        {"bars": [raw_bar(30)], "next_page_token": "next"},
        {"bars": [raw_bar(30)], "next_page_token": None},
    ]
    client, _ = client_with_pages(pages)
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        client.get_minute_bars("AAPL", DAY, feed="sip")


def test_feed_paths_coexist_and_fetch_metadata_has_no_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    sip = feed_paths("AAPL", DAY, "sip")
    iex = feed_paths("AAPL", DAY, "iex")
    assert sip[0] != iex[0] and sip[1] != iex[1] and sip[3] != iex[3]
    client, _ = client_with_pages([{"bars": [raw_bar(30)], "symbol": "AAPL", "next_page_token": None}])
    fetch(client, "AAPL", DAY, "sip")
    assert "Requested feed: sip" in capsys.readouterr().out
    metadata = json.loads(sip[2].read_text())
    assert metadata["requested_feed"] == "sip"
    assert metadata["page_count"] == 1
    assert metadata["source_raw_file"] == str(sip[0])
    serialized = sip[0].read_text() + sip[2].read_text()
    assert "secret" not in serialized and '"key"' not in serialized


def test_replay_defaults_to_sip_and_allows_iex_and_legacy():
    default = parser().parse_args(["replay", "--symbol", "AAPL", "--date", "2024-01-02"])
    assert default.feed == "sip"
    assert parser().parse_args(["replay", "--symbol", "AAPL", "--date", "2024-01-02", "--feed", "iex"]).feed == "iex"
    assert parser().parse_args(["replay", "--symbol", "AAPL", "--date", "2024-01-02", "--feed", "legacy"]).feed == "legacy"


def test_loads_explicit_feeds_and_legacy_signature_warns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for feed, close in (("sip", 101.0), ("iex", 99.0)):
        path = feed_paths("AAPL", DAY, feed)[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"timestamp": ["2024-01-02 09:30:00-05:00"], "close": [close]}).to_csv(path, index=False)
    assert load_bars("AAPL", DAY, "sip").iloc[0]["close"] == 101.0
    assert load_bars("AAPL", DAY, "iex").iloc[0]["close"] == 99.0
    legacy = tmp_path / "data/processed/AAPL/2024-01-02_1min.csv"
    pd.DataFrame({"timestamp": ["2024-01-02 09:30:00-05:00"], "close": [98.0]}).to_csv(legacy, index=False)
    with pytest.deprecated_call(match="legacy unsuffixed.*IEX"):
        bars = load_bars("AAPL", DAY)
    assert bars.attrs["data_feed"] == "legacy_iex"


def test_downstream_feed_validation_prevents_mixing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sip_root = artifact_directory("AAPL", DAY, "sip")
    sip_root.mkdir(parents=True)
    (sip_root / "summary.json").write_text(json.dumps({"data_feed": "iex"}))
    with pytest.raises(RuntimeError, match="Replay feed mismatch"):
        validate_replay_feed(sip_root, "sip")


def test_mocked_http_response_never_serializes_headers(monkeypatch):
    class Response:
        status_code = 200
        def json(self): return {"bars": [raw_bar(30)], "symbol": "AAPL", "next_page_token": None}
        text = ""
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response())
    client = AlpacaREST(Settings("credential-key", "credential-secret", "iex"))
    payload, _ = client.get_minute_bars("AAPL", DAY, feed="sip")
    serialized = json.dumps(payload)
    assert "credential-key" not in serialized
    assert "credential-secret" not in serialized
