"""Create a deterministic, network-free Research Cohort V001 calendar plan."""

import argparse
from datetime import date
from pathlib import Path

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.research_acquisition import deterministic_calendar_plan


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def parser() -> argparse.ArgumentParser:
    """Build the dry-run planning CLI parser."""
    value = argparse.ArgumentParser(description="Create a network-free Research Cohort V001 acquisition plan")
    value.add_argument("--cohort-start", type=date.fromisoformat, default=date(2024, 6, 3))
    value.add_argument("--cohort-sessions", type=_positive_int, default=60)
    value.add_argument("--warmup-sessions", type=_nonnegative_int, default=20)
    value.add_argument("--output", type=Path)
    return value


def main() -> int:
    """Render or save the fixed calendar plan without provider access."""
    args = parser().parse_args()
    plan = deterministic_calendar_plan(
        ExchangeCalendarsAdapter(),
        cohort_start=args.cohort_start,
        cohort_session_count=args.cohort_sessions,
        warmup_session_count=args.warmup_sessions,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        plan.to_csv(args.output, index=False)
        print(f"Saved deterministic acquisition plan: {args.output}")
    print(plan.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
