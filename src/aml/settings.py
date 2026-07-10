from dataclasses import dataclass
import os
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    api_key: str
    secret_key: str
    data_feed: str = "iex"
    paper_base_url: str = "https://paper-api.alpaca.markets"
    data_base_url: str = "https://data.alpaca.markets"

    @classmethod
    def from_env(cls):
        load_dotenv()
        key = os.getenv("ALPACA_API_KEY", "").strip()
        secret = os.getenv("ALPACA_SECRET_KEY", "").strip()
        feed = os.getenv("ALPACA_DATA_FEED", "iex").strip().lower()
        if not key or key == "replace_with_paper_key":
            raise RuntimeError("Missing ALPACA_API_KEY in .env")
        if not secret or secret == "replace_with_paper_secret":
            raise RuntimeError("Missing ALPACA_SECRET_KEY in .env")
        if feed not in {"iex", "sip", "otc", "boats"}:
            raise RuntimeError(f"Unsupported data feed: {feed}")
        return cls(key, secret, feed)

    @property
    def headers(self):
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
        }
