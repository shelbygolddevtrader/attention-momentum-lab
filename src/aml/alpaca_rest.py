"""Minimal Alpaca REST client with pagination-safe historical bar access."""

from copy import deepcopy
from datetime import date, datetime, time, timezone
import hashlib
import time as time_module
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from aml.settings import Settings

NY = ZoneInfo("America/New_York")


class AlpacaDataPermissionError(RuntimeError):
    """The requested Alpaca market-data feed is not enabled for the account."""


class AlpacaREST:
    """Alpaca REST adapter; credentials are used only in request headers."""

    def __init__(
        self,
        settings: Settings,
        timeout: int = 30,
        max_retries: int = 4,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.settings = settings
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url, headers=self.settings.headers, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    error = RuntimeError(
                        f"Network request failed after {attempt + 1} attempts: {exc}"
                    )
                    error.retry_count = attempt
                    raise error from exc
                time_module.sleep(self.retry_backoff_seconds * (2 ** attempt))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after is not None else None
                    except ValueError:
                        delay = None
                    time_module.sleep(
                        delay if delay is not None else self.retry_backoff_seconds * (2 ** attempt)
                    )
                    continue
            break
        if response is None:  # pragma: no cover - loop invariants guarantee a response or exception
            raise RuntimeError("Network request did not return a response")
        if response.status_code >= 400:
            requested_feed = str((params or {}).get("feed", "")).lower()
            if response.status_code == 403 and requested_feed in {"sip", "iex"}:
                raise AlpacaDataPermissionError(
                    f"Alpaca denied access to the requested {requested_feed.upper()} "
                    "market-data feed (HTTP 403). Confirm that these credentials "
                    "belong to an account with the required historical data plan; "
                    "the request was not retried with another feed."
                )
            raise RuntimeError(f"Alpaca HTTP {response.status_code}: {response.text[:800]}")
        return response.json()

    def get_paper_account(self) -> dict[str, Any]:
        return self._get(f"{self.settings.paper_base_url}/v2/account")

    def get_bars_range(
        self,
        symbol: str,
        start_timestamp: pd.Timestamp | datetime | str,
        end_timestamp: pd.Timestamp | datetime | str,
        *,
        feed: str,
        segment: str,
        trading_date: date,
        dataset_vintage: str,
        allow_empty: bool = False,
    ) -> tuple[dict, pd.DataFrame]:
        """Fetch every page for an explicit, timezone-aware research window."""
        symbol = symbol.upper().strip()
        requested_feed = feed.lower()
        if requested_feed not in {"sip", "iex"}:
            raise ValueError("Alpaca research feed must be sip or iex")
        start = pd.Timestamp(start_timestamp)
        end = pd.Timestamp(end_timestamp)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Alpaca range timestamps must be timezone-aware")
        if end <= start:
            raise ValueError("Alpaca range end must be after start")
        start = start.tz_convert(timezone.utc)
        end = end.tz_convert(timezone.utc)
        endpoint = f"{self.settings.data_base_url}/v2/stocks/{symbol}/bars"
        base_params = {
            "timeframe": "1Min", "start": start.isoformat(), "end": end.isoformat(),
            "adjustment": "all", "feed": requested_feed, "sort": "asc", "limit": 10000,
        }
        rows, pages, seen_tokens, token_hashes, page_counts = [], [], set(), [], []
        echoed_feeds: set[str] = set()
        page_count, token, final_payload = 0, None, {}
        while True:
            params = dict(base_params)
            if token is not None:
                params["page_token"] = token
            payload = None
            recorded = False
            try:
                payload = self._get(endpoint, params)
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"Malformed Alpaca page {page_count + 1}: response must be an object"
                    )
                if "bars" not in payload or "next_page_token" not in payload:
                    raise ValueError(
                        f"Malformed Alpaca page {page_count + 1}: "
                        "bars and next_page_token are required"
                    )
                if payload["bars"] is not None and not isinstance(payload["bars"], list):
                    raise ValueError(
                        f"Malformed Alpaca page {page_count + 1}: bars must be a list or null"
                    )
                returned_symbol = payload.get("symbol")
                if returned_symbol is not None and str(returned_symbol).upper() != symbol:
                    raise ValueError(
                        f"Alpaca response symbol mismatch: requested {symbol}, "
                        f"received {returned_symbol}"
                    )
                if payload.get("feed") is not None:
                    echoed_feeds.add(str(payload["feed"]).lower())
                    if echoed_feeds != {requested_feed}:
                        raise ValueError(
                            f"Alpaca response feed mismatch: requested {requested_feed}, "
                            f"received {sorted(echoed_feeds)}"
                        )
                page_count += 1
                page_rows = payload.get("bars") or []
                page_counts.append(len(page_rows))
                rows.extend(page_rows)
                pages.append(deepcopy(payload))
                recorded = True
                final_payload = deepcopy(payload)
                next_token = payload.get("next_page_token")
                if next_token is None:
                    break
                if next_token in seen_tokens:
                    raise ValueError(
                        f"Repeated Alpaca next_page_token on page {page_count}: {next_token}"
                    )
                seen_tokens.add(next_token)
                token_hashes.append(hashlib.sha256(str(next_token).encode()).hexdigest())
                token = next_token
            except Exception as exc:
                partial_pages = list(pages)
                if payload is not None and not recorded:
                    partial_pages.append(deepcopy(payload))
                exc.partial_payload = {
                    "status": "partial_failure",
                    "provider_pages": partial_pages,
                    "completed_page_count": page_count,
                    "failed_page_number": page_count + (0 if recorded else 1),
                    "requested_feed": requested_feed,
                    "requested_endpoint": endpoint,
                }
                raise
        if not rows and not allow_empty:
            raise RuntimeError(f"No bars returned for {symbol} on {trading_date}")
        frame = pd.DataFrame(rows, columns=None if rows else ["t", "o", "h", "l", "c", "v", "n", "vw"]).rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume", "n": "trade_count", "vw": "bar_vwap"
        })
        if not frame.empty:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(NY)
        else:
            frame["timestamp"] = pd.Series(dtype="datetime64[ns, America/New_York]")
        provider_out_of_order = not frame["timestamp"].is_monotonic_increasing
        if frame["timestamp"].duplicated().any():
            duplicates = frame.loc[frame["timestamp"].duplicated(keep=False), "timestamp"]
            raise ValueError(f"Duplicate timestamps across Alpaca pages: {duplicates.iloc[0]}")
        frame["symbol"] = symbol
        frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
        fetched_at = datetime.now(timezone.utc).isoformat()
        actual_feed = requested_feed if echoed_feeds == {requested_feed} else None
        feed_evidence = (
            "provider_response_field"
            if actual_feed is not None
            else "explicit_request_parameter_provider_did_not_echo_feed"
        )
        metadata = {
            "provider": "alpaca", "status": "success", "symbol": symbol,
            "trading_date": str(trading_date), "segment": segment,
            "requested_feed": requested_feed, "actual_feed": actual_feed,
            "actual_feed_evidence": feed_evidence,
            "requested_endpoint": endpoint, "actual_endpoint": endpoint,
            "timeframe": base_params["timeframe"],
            "adjustment": base_params["adjustment"], "start_timestamp": base_params["start"],
            "end_timestamp": base_params["end"], "sort_order": base_params["sort"],
            "page_count": page_count, "total_bar_count": len(frame),
            "fetch_timestamp": fetched_at, "acquisition_timestamp": fetched_at,
            "pagination_occurred": page_count > 1,
            "page_tokens_followed": len(seen_tokens), "retry_count": 0,
            "page_record_counts": page_counts,
            "page_token_sha256": token_hashes,
            "provider_response_out_of_order": provider_out_of_order,
            "timezone_assumption": "request converted to UTC; response converted to America/New_York",
            "dataset_vintage": dataset_vintage,
        }
        combined_payload = {
            "bars": rows, "symbol": final_payload.get("symbol", symbol),
            "next_page_token": final_payload.get("next_page_token"),
            "provider_pages": pages,
            "final_response_metadata": {
                key: value for key, value in final_payload.items()
                if key not in {"bars", "next_page_token"}
            },
            "acquisition_metadata": metadata,
        }
        return combined_payload, frame

    def get_minute_bars(
        self, symbol: str, trading_date: date, feed: str | None = None
    ) -> tuple[dict, pd.DataFrame]:
        """Fetch regular-session bars while preserving the legacy feed default.

        Research callers use :meth:`get_bars_range` with explicit windows.
        Omitting ``feed`` here continues to use ``Settings.data_feed``.
        """
        requested_feed = (feed or self.settings.data_feed).lower()
        start = datetime.combine(trading_date, time(9, 30), NY)
        end = datetime.combine(trading_date, time(16, 0), NY)
        return self.get_bars_range(
            symbol, start, end, feed=requested_feed, segment="regular",
            trading_date=trading_date, dataset_vintage="legacy-single-session",
        )
