from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path

import pytest

from aml.discovery_evidence_v001 import (
    DISCOVERY_END,
    DISCOVERY_START,
    EvidenceError,
    FetchResponse,
    build_calendar_artifact,
    collect_corporate_action_evidence,
    normalize_corporate_actions,
    parse_nasdaq_halts,
    reconcile_gme_reference_halts,
    verify_raw_bundle,
)


UNIVERSE = frozenset({"GME"} | {f"S{index:02d}" for index in range(22)})


def _rss(items: str, count: int) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:ndaq="http://www.nasdaqtrader.com/"><channel>
<ndaq:numItems>{count}</ndaq:numItems>{items}</channel></rss>""".encode()


def _halt_item(symbol: str = "GME") -> str:
    return f"""<item><ndaq:IssueSymbol>{symbol}</ndaq:IssueSymbol>
<ndaq:Market>N</ndaq:Market><ndaq:ReasonCode>M</ndaq:ReasonCode>
<ndaq:HaltDate>05/13/2024</ndaq:HaltDate><ndaq:HaltTime>09:35:46</ndaq:HaltTime>
<ndaq:ResumptionDate>05/13/2024</ndaq:ResumptionDate>
<ndaq:ResumptionQuoteTime>09:40:46</ndaq:ResumptionQuoteTime>
<ndaq:ResumptionTradeTime>09:40:46</ndaq:ResumptionTradeTime></item>"""


def test_positive_and_negative_halt_evidence() -> None:
    records, count = parse_nasdaq_halts(
        _rss(_halt_item(), 1), date(2024, 5, 13), UNIVERSE
    )
    assert count == 1
    assert records[0]["symbol"] == "GME"
    assert records[0]["resumption_status"] == "complete"
    empty, count = parse_nasdaq_halts(_rss("", 0), date(2024, 5, 13), UNIVERSE)
    assert empty == [] and count == 0


@pytest.mark.parametrize(
    "payload,error",
    [
        (b"<broken>", "malformed_halt_response"),
        (_rss(_halt_item(), 2), "halt_response_item_count_mismatch"),
        (_rss(_halt_item().replace("09:35:46", "bad"), 1), "malformed_halt_start"),
    ],
)
def test_halt_parser_fails_closed(payload: bytes, error: str) -> None:
    with pytest.raises(EvidenceError, match=error):
        parse_nasdaq_halts(payload, date(2024, 5, 13), UNIVERSE)


def test_irrelevant_provider_time_defect_does_not_change_universe_ledger() -> None:
    malformed_other = _halt_item("OTHER").replace("09:40:46", "08:00:00")
    records, count = parse_nasdaq_halts(
        _rss(malformed_other, 1), date(2024, 5, 13), UNIVERSE
    )
    assert records == []
    assert count == 1


def test_existing_gme_halts_reconcile_exactly_and_fail_on_change() -> None:
    paths = (
        Path("data/market_halts/GME/2024-05-13_verified_halts.csv"),
        Path("data/market_halts/GME/2024-05-14_verified_halts.csv"),
    )
    records = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                resume = row["resume_trade_timestamp"]
                records.append({
                    "symbol": "GME",
                    "halt_date": row["trading_date"],
                    "halt_time": row["halt_timestamp"].replace(" ", "T"),
                    "reported_resumption_date": date.fromisoformat(
                        row["trading_date"]
                    ).strftime("%m/%d/%Y"),
                    "reported_quote_resumption_time": row[
                        "resume_quote_timestamp"
                    ][11:19],
                    "reported_trade_resumption_time": resume[11:19],
                    "reason_code": row["halt_code"],
                    "source": row["source"],
                })
    result = reconcile_gme_reference_halts(records, paths)
    assert result["record_count"] == 25
    with pytest.raises(EvidenceError, match="gme_halt_reference_mismatch"):
        reconcile_gme_reference_halts(records[:-1], paths)


def test_calendar_identity_and_early_closes_are_frozen() -> None:
    first = build_calendar_artifact()
    second = build_calendar_artifact()
    assert first == second
    assert len(first["sessions"]) == 364
    assert [
        item["session"] for item in first["sessions"] if item["early_close"]
    ] == ["2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24"]


def test_corporate_action_multi_symbol_shapes_and_negative_coverage(tmp_path: Path) -> None:
    pages = [{
        "corporate_actions": {
            "spin_offs": [{
                "id": "spin-1", "source_symbol": "GME", "new_symbol": "NEW",
                "process_date": "2024-01-02", "ex_date": "2024-01-02",
            }],
            "stock_mergers": [{
                "id": "merge-1", "acquiree_symbol": "OLD",
                "acquirer_symbol": "S00", "effective_date": "2024-02-01",
            }],
        },
        "next_page_token": None,
    }]
    normalized = normalize_corporate_actions(pages, UNIVERSE)
    assert [item["symbol"] for item in normalized] == ["GME", "S00"]

    payload = json.dumps(pages[0], sort_keys=True).encode()

    def fetch(url, params, headers):
        assert params["start"] == DISCOVERY_START.isoformat()
        assert params["end"] == DISCOVERY_END.isoformat()
        assert "APCA-API-SECRET-KEY" in headers
        return FetchResponse(200, payload, {"x-request-id": "request-1"})

    destination = tmp_path / "actions"
    result = collect_corporate_action_evidence(
        destination,
        symbols=sorted(UNIVERSE),
        api_key="key",
        api_secret="secret",
        fetch=fetch,
        retrieved_at=lambda: "2026-08-03T00:00:00.000000+00:00",
    )
    assert result["pagination_complete"] is True
    assert "S01" in result["negative_coverage_symbols"]
    verify_raw_bundle(destination, result)


def test_corporate_action_duplicate_conflict_rejected() -> None:
    record = {"id": "same", "symbol": "GME", "ex_date": "2024-01-02"}
    pages = [
        {"corporate_actions": {"forward_splits": [record]}},
        {"corporate_actions": {"forward_splits": [{**record, "new_rate": 2}]}},
    ]
    with pytest.raises(EvidenceError, match="duplicate_conflict"):
        normalize_corporate_actions(pages, UNIVERSE)


def test_corporate_action_write_once(tmp_path: Path) -> None:
    destination = tmp_path / "actions"
    destination.mkdir()
    with pytest.raises(EvidenceError, match="missing_credentials_or_universe"):
        collect_corporate_action_evidence(
            destination,
            symbols=sorted(UNIVERSE),
            api_key="",
            api_secret="",
        )
