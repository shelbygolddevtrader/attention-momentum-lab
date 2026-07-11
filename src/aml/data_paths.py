"""Feed-qualified paths and compatibility loading for historical market data."""

from datetime import date
from pathlib import Path
import json
import warnings

import pandas as pd

HISTORICAL_DATA_FEED = "sip"
RESEARCH_FEEDS = ("sip", "iex")
LEGACY_FEED = "legacy"


def feed_paths(symbol: str, day: date | str, feed: str = HISTORICAL_DATA_FEED):
    """Return raw, processed, metadata, and artifact paths for one feed."""
    feed = feed.lower()
    if feed not in RESEARCH_FEEDS:
        raise ValueError(f"Unsupported historical feed: {feed}")
    symbol = symbol.upper()
    raw = Path("data/raw") / symbol / f"{day}_{feed}_alpaca_response.json"
    processed = Path("data/processed") / symbol / f"{day}_{feed}_1min.csv"
    metadata = Path("data/processed") / symbol / f"{day}_{feed}_metadata.json"
    artifacts = Path("artifacts") / symbol / str(day) / feed
    return raw, processed, metadata, artifacts


def legacy_paths(symbol: str, day: date | str):
    """Return pre-feed-qualification paths, known historically to be IEX."""
    symbol = symbol.upper()
    return (
        Path("data/raw") / symbol / f"{day}_alpaca_response.json",
        Path("data/processed") / symbol / f"{day}_1min.csv",
        Path("artifacts") / symbol / str(day),
    )


def artifact_directory(symbol: str, day: date | str, feed: str):
    if feed == LEGACY_FEED:
        return legacy_paths(symbol, day)[2]
    return feed_paths(symbol, day, feed)[3]


def validate_replay_feed(directory: Path, feed: str):
    """Prevent downstream analysis from combining artifacts from another feed."""
    summary_path = directory / "summary.json"
    if feed == LEGACY_FEED:
        return
    if not summary_path.exists():
        raise RuntimeError(f"Missing replay metadata: {summary_path}; run replay for feed={feed}")
    summary = json.loads(summary_path.read_text())
    recorded = summary.get("data_feed")
    if recorded != feed:
        raise RuntimeError(
            f"Replay feed mismatch: requested {feed}, metadata records {recorded!r}"
        )


def load_bars(symbol: str, day: date | str, feed: str | None = None):
    """Load feed-qualified bars; omitted ``feed`` preserves the legacy signature.

    Unsuffixed files are historical IEX data. They are never used as a SIP
    fallback. Callers should migrate to an explicit ``sip`` or ``iex`` feed.
    """
    if feed is None or feed == LEGACY_FEED:
        warnings.warn(
            "Loading legacy unsuffixed market data as IEX; pass feed='sip' or "
            "feed='iex' and use feed-qualified files",
            DeprecationWarning,
            stacklevel=2,
        )
        path = legacy_paths(symbol, day)[1]
        actual_feed = "legacy_iex"
    else:
        path = feed_paths(symbol, day, feed)[1]
        actual_feed = feed
    if not path.exists():
        raise RuntimeError(f"Missing {path}; fetch the selected feed first")
    bars = pd.read_csv(path)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    bars.attrs.update(data_feed=actual_feed, source_path=str(path))
    metadata_path = path.with_name(path.name.replace("_1min.csv", "_metadata.json"))
    if metadata_path.exists():
        bars.attrs["acquisition_metadata"] = json.loads(metadata_path.read_text())
    return bars
