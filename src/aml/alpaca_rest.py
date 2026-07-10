from datetime import date, datetime, time, timezone
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

    def get_minute_bars(self, symbol: str, trading_date: date):
        symbol = symbol.upper().strip()
        start = datetime.combine(trading_date, time(9, 30), NY).astimezone(timezone.utc)
        end = datetime.combine(trading_date, time(16, 0), NY).astimezone(timezone.utc)
        payload = self._get(
            f"{self.settings.data_base_url}/v2/stocks/{symbol}/bars",
            {
                "timeframe": "1Min",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "adjustment": "all",
                "feed": self.settings.data_feed,
                "sort": "asc",
                "limit": 10000,
            },
        )
        rows = payload.get("bars") or []
        if not rows:
            raise RuntimeError(f"No bars returned for {symbol} on {trading_date}")
        frame = pd.DataFrame(rows).rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume", "n": "trade_count", "vw": "bar_vwap"
        })
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(NY)
        frame["symbol"] = symbol
        return payload, frame.sort_values("timestamp").reset_index(drop=True)
