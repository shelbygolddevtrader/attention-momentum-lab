from dataclasses import dataclass
import os
from dotenv import load_dotenv
from aml.data_paths import HISTORICAL_DATA_FEED


HISTORICAL_FEEDS = {"iex", "sip"}


def historical_feed_from_env() -> str:
    """Return the explicit historical feed without loading credentials."""
    feed = os.getenv(
        "ALPACA_HISTORICAL_DATA_FEED", HISTORICAL_DATA_FEED
    ).strip().lower()
    if feed not in HISTORICAL_FEEDS:
        raise RuntimeError(
            "Unsupported ALPACA_HISTORICAL_DATA_FEED: "
            f"{feed!r}; expected one of: iex, sip"
        )
    return feed

@dataclass(frozen=True)
class Settings:
    api_key: str
    secret_key: str
    # Legacy/live callers may continue to use ALPACA_DATA_FEED (default IEX).
    data_feed: str = "iex"
    paper_base_url: str = "https://paper-api.alpaca.markets"
    data_base_url: str = "https://data.alpaca.markets"
    # Historical research commands pass this role explicitly and default to SIP.
    historical_data_feed: str = HISTORICAL_DATA_FEED

    @classmethod
    def from_env(cls):
        load_dotenv()
        key = os.getenv("ALPACA_API_KEY", "").strip()
        secret = os.getenv("ALPACA_SECRET_KEY", "").strip()
        feed = os.getenv("ALPACA_DATA_FEED", "iex").strip().lower()
        historical_feed = historical_feed_from_env()
        if not key or key == "replace_with_paper_key":
            raise RuntimeError("Missing ALPACA_API_KEY in .env")
        if not secret or secret == "replace_with_paper_secret":
            raise RuntimeError("Missing ALPACA_SECRET_KEY in .env")
        if feed not in {"iex", "sip", "otc", "boats"}:
            raise RuntimeError(f"Unsupported data feed: {feed}")
        return cls(
            api_key=key,
            secret_key=secret,
            data_feed=feed,
            historical_data_feed=historical_feed,
        )

    @property
    def headers(self):
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
        }
