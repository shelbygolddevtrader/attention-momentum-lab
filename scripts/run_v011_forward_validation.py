"""Preflight or explicitly acquire the sealed V0.1.1 validation extension."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

from aml.forward_validation import (
    DEFAULT_CONTROL_ROOT,
    DEFAULT_UNIVERSE,
    build_preflight_plan,
    execute_acquisition,
    preflight_report,
    validate_acquisition_only_tokens,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--start", required=True, type=date.fromisoformat)
    value.add_argument("--end", required=True, type=date.fromisoformat)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    value.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    value.add_argument("--retry-failures", action="store_true")
    value.add_argument(
        "--execute-acquisition", action="store_true",
        help="Make authenticated SIP requests; absent this flag, preflight is network-free",
    )
    return value


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    validate_acquisition_only_tokens(arguments)
    args = parser().parse_args(arguments)
    root = args.root.resolve()

    from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter

    calendar = ExchangeCalendarsAdapter()
    plan = build_preflight_plan(
        root, start=args.start, end=args.end, environment=os.environ,
        calendar=calendar, universe=args.universe, control_root=args.control_root,
    )
    print(json.dumps(preflight_report(plan), indent=2, sort_keys=True))
    if not args.execute_acquisition:
        print("Dry run only: no network requests, market data, replay, or analysis were performed.")
        return 0

    from aml.alpaca_rest import AlpacaREST
    from aml.settings import Settings

    execute_acquisition(
        plan, client=AlpacaREST(Settings.from_env()), calendar=calendar,
        retry_failures=args.retry_failures,
    )
    print("Acquisition finished. Sealed operational audit retained; no strategy results generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
