#!/usr/bin/env python3
"""Acquire or compare one bounded Alpaca IEX/SIP historical session."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import pandas as pd

from aml.alpaca_rest import AlpacaREST
from aml.batch_evaluation import load_quality_policy
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.feed_comparison import compare_historical_feeds, write_feed_comparison
from aml.market_halts import CompletenessMode, load_verified_halts
from aml.research_acquisition import (
    AcquisitionSegment,
    acquire_research_session,
    file_sha256,
    requests_for_session,
    research_segment_paths,
)
from aml.settings import Settings


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Deterministically compare Alpaca IEX and SIP regular-session bars"
    )
    value.add_argument("symbol")
    value.add_argument("trading_date", type=date.fromisoformat)
    value.add_argument("--dataset-vintage", required=True)
    value.add_argument(
        "--download",
        action="store_true",
        help="Acquire both feed-qualified datasets before comparing them",
    )
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--completeness-mode",
        choices=[mode.value for mode in CompletenessMode],
        default=CompletenessMode.HALT_AWARE.value,
    )
    return value


def _load_regular(root: Path, request) -> tuple[pd.DataFrame, str]:
    paths = research_segment_paths(root, request)
    if not paths.processed_bars.is_file() or not paths.metadata.is_file():
        raise FileNotFoundError(
            f"Missing {request.requested_feed.upper()} research data for "
            f"{request.symbol} {request.trading_date}; rerun with --download"
        )
    metadata = json.loads(paths.metadata.read_text(encoding="utf-8"))
    if metadata.get("status") != "success":
        raise RuntimeError(
            f"{request.requested_feed.upper()} acquisition is not successful: "
            f"{metadata.get('error_message', 'unknown failure')}"
        )
    if metadata.get("requested_feed") != request.requested_feed:
        raise RuntimeError("Acquisition metadata feed does not match its path")
    digest = file_sha256(paths.processed_bars)
    if digest != metadata.get("processed_sha256"):
        raise RuntimeError(
            f"{request.requested_feed.upper()} processed-data hash mismatch"
        )
    bars = pd.read_csv(paths.processed_bars)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    return bars, digest


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    calendar = ExchangeCalendarsAdapter()
    schedule = calendar.schedule(args.trading_date, "XNYS")
    if args.download:
        client = AlpacaREST(Settings.from_env())
        # SIP first makes entitlement failure immediate. There is no fallback.
        for feed in ("sip", "iex"):
            acquire_research_session(
                client,
                calendar,
                root,
                symbol=args.symbol,
                trading_date=args.trading_date,
                dataset_vintage=args.dataset_vintage,
                feed=feed,
            )
    requests = {
        feed: next(
            request
            for request in requests_for_session(
                args.symbol,
                args.trading_date,
                schedule,
                args.dataset_vintage,
                feed,
            )
            if request.segment is AcquisitionSegment.REGULAR
        )
        for feed in ("iex", "sip")
    }
    loaded = {feed: _load_regular(root, request) for feed, request in requests.items()}
    summary, differences = compare_historical_feeds(
        loaded["iex"][0],
        loaded["sip"][0],
        symbol=args.symbol,
        trading_date=str(args.trading_date),
        expected_minutes=schedule.expected_minutes,
        quality_policy=load_quality_policy(root / "config/batch_evaluation_v001.yaml"),
        halt_schedule=load_verified_halts(
            args.symbol, args.trading_date, root / "data/market_halts"
        ),
        completeness_mode=args.completeness_mode,
        input_hashes={
            f"regular_bars:{feed}": loaded[feed][1] for feed in ("iex", "sip")
        },
    )
    output = write_feed_comparison(
        root
        / "artifacts/feed_comparisons"
        / args.dataset_vintage
        / args.symbol.upper()
        / str(args.trading_date),
        summary,
        differences,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Completed comparison artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
