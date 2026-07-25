"""Plan or execute a resumable Alpaca SIP backfill for a fixed universe."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import threading

from aml.alpaca_rest import AlpacaREST
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_backfill import (
    backfill_job_lock, load_universe, plan_tasks, run_task, trading_dates,
    universe_sha256,
)
from aml.settings import Settings


DEFAULT_UNIVERSE = Path("config/liquid_day_trading_universe_v001.csv")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Backfill premarket and regular one-minute bars for a fixed liquid-market universe"
    )
    value.add_argument("--start", required=True, type=date.fromisoformat)
    value.add_argument("--end", required=True, type=date.fromisoformat)
    value.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    value.add_argument("--dataset-vintage", required=True)
    value.add_argument("--feed", choices=("sip", "iex"), default="sip")
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--workers", type=int, default=6)
    value.add_argument("--max-tasks", type=int)
    value.add_argument(
        "--retry-failures", action="store_true",
        help="Archive prior failed attempt records and retry their fixed paths",
    )
    value.add_argument("--execute", action="store_true")
    return value


def execute_backfill(args, root, calendar, tasks, estimate) -> int:
    """Execute a previously printed plan while holding its dataset lock."""
    settings = Settings.from_env()
    thread_state = threading.local()

    def execute(task):
        if not hasattr(thread_state, "client"):
            thread_state.client = AlpacaREST(settings)
        return run_task(
            thread_state.client, calendar, root, task,
            dataset_vintage=args.dataset_vintage, feed=args.feed,
            retry_failures=args.retry_failures,
        )

    progress_path = root / "data" / "research" / args.dataset_vintage / "backfill_progress.jsonl"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"completed": 0, "skipped": 0, "failed": 0}
    with progress_path.open("a", encoding="utf-8", buffering=1) as progress:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(execute, task): task for task in tasks}
            for index, future in enumerate(as_completed(futures), start=1):
                task = futures[future]
                try:
                    result = future.result()
                    record = asdict(result)
                    record["trading_date"] = str(result.trading_date)
                except Exception as exc:
                    record = {
                        "symbol": task.instrument.symbol,
                        "trading_date": str(task.trading_date),
                        "downloaded_segments": 0, "skipped_segments": 0,
                        "status": "failed", "detail": f"{type(exc).__name__}: {exc}",
                    }
                counts[record["status"]] += 1
                record["recorded_at"] = datetime.now(timezone.utc).isoformat()
                progress.write(json.dumps(record, sort_keys=True) + "\n")
                if index == 1 or index % 25 == 0 or index == len(tasks):
                    print(f"Progress {index}/{len(tasks)}: {counts}", flush=True)
    summary = {**estimate, "status": "finished", "results": counts, "progress_file": str(progress_path)}
    summary_path = progress_path.with_name("backfill_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if counts["failed"] else 0


def main() -> int:
    args = parser().parse_args()
    if args.workers < 1 or args.workers > 24:
        raise ValueError("workers must be between 1 and 24")
    if args.max_tasks is not None and args.max_tasks < 1:
        raise ValueError("max-tasks must be positive")
    root = args.root.resolve()
    universe_path = (root / args.universe).resolve() if not args.universe.is_absolute() else args.universe
    instruments = load_universe(universe_path)
    calendar = ExchangeCalendarsAdapter()
    sessions = trading_dates(calendar, args.start, args.end)
    tasks = plan_tasks(instruments, sessions)
    if args.max_tasks is not None:
        tasks = tasks[:args.max_tasks]
    estimate = {
        "status": "planned" if not args.execute else "starting",
        "start": str(args.start), "end": str(args.end), "feed": args.feed,
        "dataset_vintage": args.dataset_vintage,
        "universe_file": str(universe_path.relative_to(root)),
        "universe_sha256": universe_sha256(universe_path),
        "symbols": [item.symbol for item in instruments],
        "symbol_count": len(instruments), "trading_session_count": len(sessions),
        "task_count": len(tasks), "maximum_request_count": len(tasks) * 2,
        "workers": args.workers,
    }
    print(json.dumps(estimate, indent=2))
    if not args.execute:
        print("Dry run only. Add --execute to download data; no orders are ever submitted.")
        return 0
    with backfill_job_lock(root, args.dataset_vintage):
        return execute_backfill(args, root, calendar, tasks, estimate)


if __name__ == "__main__":
    raise SystemExit(main())
