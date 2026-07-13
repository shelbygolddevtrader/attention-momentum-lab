"""Acquire one explicitly identified Research Cohort V001 SIP session."""

import argparse
from datetime import date
from pathlib import Path

from aml.alpaca_rest import AlpacaREST
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.research_acquisition import acquire_research_session
from aml.settings import Settings


def parser() -> argparse.ArgumentParser:
    """Build the single-session acquisition CLI parser."""
    value = argparse.ArgumentParser(description="Acquire one segmented Research Cohort V001 SIP session")
    value.add_argument("symbol")
    value.add_argument("trading_date", type=date.fromisoformat)
    value.add_argument("--dataset-vintage", required=True)
    value.add_argument("--feed", choices=("sip",), default="sip")
    value.add_argument("--root", type=Path, default=Path.cwd())
    return value


def main() -> int:
    """Acquire one symbol/date; broad or implicit downloads are unsupported."""
    args = parser().parse_args()
    paths = acquire_research_session(
        AlpacaREST(Settings.from_env()), ExchangeCalendarsAdapter(), args.root,
        symbol=args.symbol, trading_date=args.trading_date,
        dataset_vintage=args.dataset_vintage, feed=args.feed,
    )
    for path in paths:
        print(f"Saved {path.processed_bars} with metadata {path.metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
