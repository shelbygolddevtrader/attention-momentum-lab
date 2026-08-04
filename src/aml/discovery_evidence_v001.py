"""Bounded evidence acquisition for the V002 discovery-only screen.

The module deliberately contains no strategy evaluation.  It turns provider
responses into immutable, canonical evidence bundles and exposes pure parsers
that can be tested without network access.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable, Iterable, Mapping, Sequence
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_calendar import NonTradingSessionError
from aml.winner_archetype_contracts import canonical_hash, canonical_json


SCHEMA = "aml.discovery-evidence.v001"
DISCOVERY_START = date(2023, 7, 24)
DISCOVERY_END = date(2024, 12, 31)
NY = ZoneInfo("America/New_York")
NASDAQ_URL = "https://www.nasdaqtrader.com/rss.aspx"
ALPACA_URL = "https://data.alpaca.markets/v1/corporate-actions"
ACTION_TYPES = (
    "reverse_split", "forward_split", "unit_split", "cash_dividend",
    "stock_dividend", "spin_off", "cash_merger", "stock_merger",
    "stock_and_cash_merger", "redemption", "name_change",
    "worthless_removal", "rights_distribution", "partial_call",
    "reorganization",
)


class EvidenceError(RuntimeError):
    """Evidence is incomplete, malformed, mutable, or outside the boundary."""


@dataclass(frozen=True, slots=True)
class FetchResponse:
    status_code: int
    content: bytes
    headers: Mapping[str, str]


Fetcher = Callable[[str, Mapping[str, str], Mapping[str, str]], FetchResponse]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_interval(start: date, end: date) -> None:
    if start != DISCOVERY_START or end != DISCOVERY_END:
        raise EvidenceError("discovery_boundary_mismatch")


def _default_fetch(
    url: str, params: Mapping[str, str], headers: Mapping[str, str]
) -> FetchResponse:
    response = requests.get(url, params=params, headers=headers, timeout=45)
    return FetchResponse(response.status_code, response.content, dict(response.headers))


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise EvidenceError(f"immutable_path_exists:{path.name}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _publish_directory(staging: Path, destination: Path) -> None:
    if destination.exists():
        raise EvidenceError(f"immutable_bundle_exists:{destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, destination)


def _parse_halt_datetime(day_text: str, clock_text: str, field: str) -> datetime:
    day_text = day_text.strip()
    clock_text = clock_text.strip()
    formats = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M")
    for pattern in formats:
        try:
            value = datetime.strptime(f"{day_text} {clock_text}", pattern)
        except ValueError:
            continue
        return value.replace(tzinfo=NY)
    raise EvidenceError(f"malformed_halt_{field}")


def parse_nasdaq_halts(
    payload: bytes, requested_date: date, universe: frozenset[str]
) -> tuple[list[dict[str, Any]], int]:
    """Parse one official RSS payload and return universe records and total count."""

    try:
        root = ET.fromstring(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise EvidenceError("malformed_halt_response") from exc
    namespace = {"ndaq": "http://www.nasdaqtrader.com/"}
    item_count_node = root.find("./channel/ndaq:numItems", namespace)
    if item_count_node is None or not (item_count_node.text or "").strip().isdigit():
        raise EvidenceError("halt_response_missing_item_count")
    declared_count = int((item_count_node.text or "").strip())
    items = root.findall("./channel/item")
    if declared_count != len(items):
        raise EvidenceError("halt_response_item_count_mismatch")
    records: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in items:
        def text(name: str) -> str:
            node = item.find(f"ndaq:{name}", namespace)
            return "" if node is None or node.text is None else node.text.strip()

        symbol = text("IssueSymbol").upper()
        halt_date = text("HaltDate")
        halt_time = text("HaltTime")
        if not symbol or not halt_date or not halt_time:
            raise EvidenceError("halt_response_missing_required_field")
        # The complete provider payload is retained for negative coverage.  Exact
        # time semantics are validated only for records that can affect the
        # declared universe; unrelated provider defects cannot alter its ledger.
        if symbol not in universe:
            continue
        start = _parse_halt_datetime(halt_date, halt_time, "start")
        if start.date() != requested_date:
            raise EvidenceError("halt_response_wrong_date")
        resume_date = text("ResumptionDate")
        quote_resume_time = text("ResumptionQuoteTime")
        trade_resume_time = text("ResumptionTradeTime")
        resume_time = trade_resume_time or quote_resume_time
        resume = None
        if resume_date and resume_time:
            resume = _parse_halt_datetime(resume_date, resume_time, "resume")
            if resume <= start:
                raise EvidenceError("halt_response_invalid_resume")
        elif resume_time:
            raise EvidenceError("halt_response_time_without_resume_date")
        record = {
            "symbol": symbol,
            "halt_date": start.date().isoformat(),
            "halt_time": start.isoformat(),
            "resumption_date": None if resume is None else resume.date().isoformat(),
            "resumption_time": None if resume is None else resume.isoformat(),
            "reported_resumption_date": resume_date or None,
            "reported_quote_resumption_time": quote_resume_time or None,
            "reported_trade_resumption_time": trade_resume_time or None,
            "resumption_status": "complete" if resume is not None else "unresolved",
            "reason_code": text("ReasonCode"),
            "market": text("Market"),
            "source": f"{NASDAQ_URL}?feed=tradehalts&haltdate={requested_date:%m%d%Y}",
        }
        key = (symbol, record["halt_time"], record["reason_code"])
        prior = seen.get(key)
        if prior is not None and prior != record:
            raise EvidenceError("halt_duplicate_conflict")
        seen[key] = record
        if prior is None:
            records.append(record)
    records.sort(key=lambda item: (item["halt_time"], item["symbol"], item["reason_code"]))
    return records, declared_count


def collect_halt_evidence(
    destination: Path,
    *,
    symbols: Sequence[str],
    start: date = DISCOVERY_START,
    end: date = DISCOVERY_END,
    fetch: Fetcher = _default_fetch,
    retrieved_at: Callable[[], str] = _utc_now,
    workers: int = 6,
) -> dict[str, Any]:
    """Retrieve every calendar date and atomically publish a write-once bundle."""

    _validate_interval(start, end)
    universe = frozenset(symbols)
    if len(universe) != 23 or any(not re.fullmatch(r"[A-Z.]{1,10}", item) for item in universe):
        raise EvidenceError("invalid_discovery_universe")
    staging = Path(tempfile.mkdtemp(prefix="halt-evidence-", dir=destination.parent))
    daily: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    try:
        dates = list(date_range(start, end))

        def retrieve(cursor: date) -> tuple[date, FetchResponse, str]:
            params = {"feed": "tradehalts", "haltdate": cursor.strftime("%m%d%Y")}
            response = fetch(NASDAQ_URL, params, {})
            if response.status_code != 200:
                raise EvidenceError(f"halt_retrieval_failed:{cursor}:{response.status_code}")
            return cursor, response, retrieved_at()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            responses = list(pool.map(retrieve, dates))
        for cursor, response, timestamp in responses:
            params = {"feed": "tradehalts", "haltdate": cursor.strftime("%m%d%Y")}
            last_error: EvidenceError | None = None
            for attempt in range(3):
                try:
                    records, source_count = parse_nasdaq_halts(
                        response.content, cursor, universe
                    )
                    break
                except EvidenceError as exc:
                    last_error = exc
                    if attempt == 2:
                        raise EvidenceError(f"{exc}:{cursor.isoformat()}") from exc
                    response = fetch(NASDAQ_URL, params, {})
                    timestamp = retrieved_at()
                    if response.status_code != 200:
                        raise EvidenceError(
                            f"halt_retrieval_failed:{cursor}:{response.status_code}"
                        )
            else:  # pragma: no cover - loop either breaks or raises
                assert last_error is not None
                raise last_error
            relative = f"raw/{cursor.isoformat()}.xml"
            _write_exclusive(staging / relative, response.content)
            raw_sha = sha256_bytes(response.content)
            daily.append({
                "date": cursor.isoformat(),
                "retrieved_at": timestamp,
                "request_identity": canonical_hash({"url": NASDAQ_URL, "params": params}),
                "raw_path": relative,
                "raw_sha256": raw_sha,
                "source_record_count": source_count,
                "universe_record_count": len(records),
                "coverage_status": "positive" if records else "negative_complete",
            })
            for record in records:
                ledger.append({**record, "raw_sha256": raw_sha})
        manifest = {
            "schema": f"{SCHEMA}.halts",
            "source": "Nasdaq Trader Trade Halts RSS",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbols": sorted(universe),
            "daily": daily,
            "normalized_records": ledger,
        }
        identity = canonical_hash(manifest)
        manifest["identity"] = identity
        _write_exclusive(staging / "manifest.json", canonical_json(manifest))
        _publish_directory(staging, destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def reconcile_gme_reference_halts(
    records: Sequence[Mapping[str, Any]], reference_paths: Sequence[Path]
) -> dict[str, Any]:
    """Require exact agreement with the 25 pre-existing May 2024 GME halts."""

    if len(reference_paths) != 2 or any(not path.is_file() for path in reference_paths):
        raise EvidenceError("gme_halt_reference_missing")
    expected: set[tuple[str, str, str, str, str]] = set()
    reference_hashes: dict[str, str] = {}
    for path in sorted(reference_paths, key=lambda item: item.name):
        reference_hashes[path.name] = sha256_bytes(path.read_bytes())
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                expected.add((
                    datetime.fromisoformat(row["halt_timestamp"]).isoformat(),
                    datetime.fromisoformat(row["resume_quote_timestamp"]).isoformat(),
                    datetime.fromisoformat(row["resume_trade_timestamp"]).isoformat(),
                    row["halt_code"],
                    row["source"],
                ))
    observed: set[tuple[str, str, str, str, str]] = set()
    for record in records:
        if record.get("symbol") != "GME" or record.get("halt_date") not in {
            "2024-05-13", "2024-05-14",
        }:
            continue
        resume_date = str(record.get("reported_resumption_date") or "")
        quote_time = str(record.get("reported_quote_resumption_time") or "")
        trade_time = str(record.get("reported_trade_resumption_time") or "")
        if not resume_date or not quote_time or not trade_time:
            raise EvidenceError("gme_halt_reference_incomplete_resumption")
        observed.add((
            datetime.fromisoformat(str(record["halt_time"])).isoformat(),
            _parse_halt_datetime(resume_date, quote_time, "resume").isoformat(),
            _parse_halt_datetime(resume_date, trade_time, "resume").isoformat(),
            str(record.get("reason_code", "")),
            str(record.get("source", "")),
        ))
    if len(expected) != 25 or expected != observed:
        raise EvidenceError(
            f"gme_halt_reference_mismatch:expected={len(expected)}:observed={len(observed)}"
        )
    result = {
        "schema": f"{SCHEMA}.gme-halt-reconciliation",
        "record_count": len(observed),
        "reference_hashes": dict(sorted(reference_hashes.items())),
    }
    result["identity"] = canonical_hash(result)
    return result


def normalize_corporate_actions(
    pages: Sequence[Mapping[str, Any]], symbols: frozenset[str]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for page_number, page in enumerate(pages, start=1):
        groups = page.get("corporate_actions")
        if not isinstance(groups, Mapping):
            raise EvidenceError("corporate_actions_invalid_groups")
        for provider_type, values in groups.items():
            if not isinstance(provider_type, str) or not isinstance(values, list):
                raise EvidenceError("corporate_actions_invalid_group")
            normalized_type = provider_type.removesuffix("s")
            for raw in values:
                if not isinstance(raw, Mapping):
                    raise EvidenceError("corporate_actions_invalid_record")
                candidate_symbols = sorted({
                    str(raw.get(key, "")).upper()
                    for key in (
                        "symbol", "source_symbol", "new_symbol",
                        "acquiree_symbol", "acquirer_symbol",
                    )
                    if raw.get(key) and str(raw.get(key, "")).upper() in symbols
                })
                symbol = candidate_symbols[0] if candidate_symbols else ""
                action_id = str(raw.get("id", ""))
                if not symbol or not action_id:
                    raise EvidenceError("corporate_actions_missing_identity")
                for key, value in raw.items():
                    if isinstance(value, float) and not math.isfinite(value):
                        raise EvidenceError("corporate_actions_nonfinite_number")
                    if isinstance(value, str):
                        value.encode("utf-8", "strict")
                dates: dict[str, str] = {}
                for key, value in raw.items():
                    if key.endswith("_date") and value is not None:
                        try:
                            dates[key] = date.fromisoformat(str(value)).isoformat()
                        except ValueError as exc:
                            raise EvidenceError("corporate_actions_malformed_date") from exc
                record = {
                    "provider_type": provider_type,
                    "action_type": normalized_type,
                    "provider_action_id": action_id,
                    "symbol": symbol,
                    "universe_symbols": candidate_symbols,
                    "process_date": dates.get("process_date"),
                    "effective_dates": dict(sorted(dates.items())),
                    "revision_information_available": any(
                        key in raw for key in ("revision", "updated_at", "created_at")
                    ),
                    "raw_fields": dict(sorted(raw.items())),
                    "source_page": page_number,
                }
                key = (provider_type, action_id)
                prior = seen.get(key)
                if prior is not None and {
                    key: value for key, value in prior.items() if key != "source_page"
                } != {
                    key: value for key, value in record.items() if key != "source_page"
                }:
                    raise EvidenceError("corporate_action_duplicate_conflict")
                if prior is None:
                    seen[key] = record
                    records.append(record)
    records.sort(key=lambda item: (item["symbol"], item["action_type"], item["provider_action_id"]))
    return records


def collect_corporate_action_evidence(
    destination: Path,
    *,
    symbols: Sequence[str],
    api_key: str,
    api_secret: str,
    start: date = DISCOVERY_START,
    end: date = DISCOVERY_END,
    fetch: Fetcher = _default_fetch,
    retrieved_at: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    _validate_interval(start, end)
    universe = frozenset(symbols)
    if len(universe) != 23 or not api_key or not api_secret:
        raise EvidenceError("corporate_actions_missing_credentials_or_universe")
    staging = Path(tempfile.mkdtemp(prefix="action-evidence-", dir=destination.parent))
    pages: list[Mapping[str, Any]] = []
    page_meta: list[dict[str, Any]] = []
    token: str | None = None
    try:
        for page_number in range(1, 1001):
            params = {
                "symbols": ",".join(sorted(universe)),
                "types": ",".join(ACTION_TYPES),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": "1000",
                "sort": "asc",
            }
            if token is not None:
                params["page_token"] = token
            response = fetch(
                ALPACA_URL,
                params,
                {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret},
            )
            if response.status_code != 200:
                raise EvidenceError(f"corporate_action_retrieval_failed:{response.status_code}")
            try:
                page = json.loads(response.content)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EvidenceError("corporate_actions_malformed_json") from exc
            if not isinstance(page, Mapping):
                raise EvidenceError("corporate_actions_nonobject_page")
            raw_path = f"raw/page-{page_number:04d}.json"
            _write_exclusive(staging / raw_path, response.content)
            pages.append(page)
            page_meta.append({
                "page": page_number,
                "retrieved_at": retrieved_at(),
                "request_identity": canonical_hash({"url": ALPACA_URL, "params": params}),
                "provider_request_id": response.headers.get("x-request-id")
                or response.headers.get("X-Request-ID"),
                "page_token_supplied": token,
                "raw_path": raw_path,
                "raw_sha256": sha256_bytes(response.content),
            })
            next_token = page.get("next_page_token")
            if next_token is None:
                break
            if not isinstance(next_token, str) or not next_token or next_token == token:
                raise EvidenceError("corporate_actions_invalid_pagination")
            token = next_token
        else:
            raise EvidenceError("corporate_actions_pagination_limit")
        records = normalize_corporate_actions(pages, universe)
        positive = {
            symbol for item in records for symbol in item["universe_symbols"]
        }
        manifest = {
            "schema": f"{SCHEMA}.corporate-actions",
            "source": "Alpaca Market Data GET /v1/corporate-actions",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbols": sorted(universe),
            "action_types_requested": list(ACTION_TYPES),
            "pages": page_meta,
            "pagination_complete": True,
            "records": records,
            "negative_coverage_symbols": sorted(universe - positive),
            "point_in_time_revision_limitation": (
                "Provider response does not guarantee historical first-known timestamps; "
                "positive action observations require conservative downstream exclusion."
            ),
        }
        identity = canonical_hash(manifest)
        manifest["identity"] = identity
        _write_exclusive(staging / "manifest.json", canonical_json(manifest))
        _publish_directory(staging, destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_calendar_artifact(
    *, start: date = DISCOVERY_START, end: date = DISCOVERY_END
) -> dict[str, Any]:
    _validate_interval(start, end)
    calendar = ExchangeCalendarsAdapter()
    calendar_identity = calendar.identity({"XNYS"})
    values: list[dict[str, str]] = []
    for label in date_range(start, end):
        try:
            schedule = calendar.schedule(label, "XNYS")
        except NonTradingSessionError:
            continue
        opened = schedule.open_timestamp
        closed = schedule.close_timestamp
        values.append({
            "session": label.isoformat(),
            "regular_open": opened.isoformat(),
            "regular_close": closed.isoformat(),
            "early_close": closed.strftime("%H:%M") != "16:00",
        })
    artifact = {
        "schema": f"{SCHEMA}.calendar",
        "calendar_package": calendar_identity.provider,
        "calendar_package_version": calendar_identity.provider_version,
        "calendar": "XNYS",
        "timezone": "America/New_York",
        "discovery_start": start.isoformat(),
        "discovery_end": end.isoformat(),
        "warmup_policy": "first_20_eligible_sessions_per_required_baseline_are_warmup_only",
        "regular_session_boundary": "[XNYS_open,XNYS_close)",
        "sessions": values,
    }
    if len(values) != 364:
        raise EvidenceError(f"calendar_session_count_mismatch:{len(values)}")
    early = [item["session"] for item in values if item["early_close"]]
    expected = ["2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24"]
    if early != expected:
        raise EvidenceError(f"calendar_early_close_mismatch:{early}")
    artifact["identity"] = canonical_hash(artifact)
    return artifact


def verify_raw_bundle(root: Path, manifest: Mapping[str, Any]) -> None:
    """Rehash every raw payload referenced by a halt or action manifest."""

    records = manifest.get("daily", manifest.get("pages", []))
    if not isinstance(records, list) or not records:
        raise EvidenceError("raw_bundle_missing_records")
    for item in records:
        path = root / str(item["raw_path"])
        if not path.is_file() or sha256_bytes(path.read_bytes()) != item["raw_sha256"]:
            raise EvidenceError(f"raw_bundle_hash_mismatch:{path.name}")


def date_range(start: date, end: date) -> Iterable[date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)
