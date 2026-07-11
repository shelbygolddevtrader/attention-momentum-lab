from datetime import date, datetime, time, timezone
from copy import deepcopy
from zoneinfo import ZoneInfo
import pandas as pd
import requests
from aml.settings import Settings

NY = ZoneInfo("America/New_York")

class AlpacaREST:
    def __init__(self, settings: Settings, timeout=30):
        self.settings = settings
        self.timeout = timeout

    def _get(self, url, params=None):
        try:
            response = requests.get(url, headers=self.settings.headers, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"Network request failed: {exc}") from exc
        if response.status_code >= 400:
            raise RuntimeError(f"Alpaca HTTP {response.status_code}: {response.text[:800]}")
        return response.json()

    def get_paper_account(self):
        return self._get(f"{self.settings.paper_base_url}/v2/account")

    def get_minute_bars(self, symbol: str, trading_date: date, feed: str | None = None):
        """Fetch all minute-bar pages for one session.

        ``feed`` is explicit for research callers. Omitting it preserves the
        legacy/live behavior of using ``Settings.data_feed``.
        """
        symbol = symbol.upper().strip()
        requested_feed = (feed or self.settings.data_feed).lower()
        start = datetime.combine(trading_date, time(9, 30), NY).astimezone(timezone.utc)
        end = datetime.combine(trading_date, time(16, 0), NY).astimezone(timezone.utc)
        endpoint = f"{self.settings.data_base_url}/v2/stocks/{symbol}/bars"
        base_params = {
            "timeframe": "1Min", "start": start.isoformat(), "end": end.isoformat(),
            "adjustment": "all", "feed": requested_feed, "sort": "asc", "limit": 10000,
        }
        rows, seen_tokens, page_count, token, final_payload = [], set(), 0, None, {}
        while True:
            params = dict(base_params)
            if token is not None:
                params["page_token"] = token
            payload = self._get(endpoint, params)
            page_count += 1
            rows.extend(payload.get("bars") or [])
            final_payload = deepcopy(payload)
            next_token = payload.get("next_page_token")
            if next_token is None:
                break
            if next_token in seen_tokens:
                raise ValueError(f"Repeated Alpaca next_page_token on page {page_count}: {next_token}")
            seen_tokens.add(next_token)
            token = next_token
        if not rows:
            raise RuntimeError(f"No bars returned for {symbol} on {trading_date}")
        frame = pd.DataFrame(rows).rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume", "n": "trade_count", "vw": "bar_vwap"
        })
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(NY)
        if frame["timestamp"].duplicated().any():
            duplicates = frame.loc[frame["timestamp"].duplicated(keep=False), "timestamp"]
            raise ValueError(f"Duplicate timestamps across Alpaca pages: {duplicates.iloc[0]}")
        frame["symbol"] = symbol
        frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
        metadata = {
            "symbol": symbol, "trading_date": str(trading_date), "requested_feed": requested_feed,
            "requested_endpoint": endpoint, "actual_endpoint": endpoint,
            "timeframe": base_params["timeframe"],
            "adjustment": base_params["adjustment"], "start_timestamp": base_params["start"],
            "end_timestamp": base_params["end"], "sort_order": base_params["sort"],
            "page_count": page_count, "total_bar_count": len(frame),
            "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            "pagination_occurred": page_count > 1,
        }
        combined_payload = {
            "bars": rows, "symbol": final_payload.get("symbol", symbol),
            "next_page_token": final_payload.get("next_page_token"),
            "final_response_metadata": {
                key: value for key, value in final_payload.items()
                if key not in {"bars", "next_page_token"}
            },
            "acquisition_metadata": metadata,
        }
        return combined_payload, frame
