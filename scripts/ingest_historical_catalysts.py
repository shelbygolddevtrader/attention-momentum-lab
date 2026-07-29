#!/usr/bin/env python3
"""Validate, plan, publish, or recover bounded synthetic historical catalysts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aml.historical_catalyst_ingestion import (
    ExactObservationalContentDeduplicator, StrictSyntheticHistoricalNormalizer,
    build_ingestion_plan, inspect_batch_status, publish_plan,
    validate_historical_root,
)
from aml.historical_catalyst_providers import InputLimits, LocalHistoricalFileProvider


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _ingestion_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--provider", required=True)
    command.add_argument("--provider-version", required=True)
    command.add_argument("--source", action="append", required=True, type=Path)
    command.add_argument("--destination-root", required=True, type=Path)
    command.add_argument("--as-of", required=True)
    command.add_argument("--normalizer-version", required=True)
    command.add_argument("--deduplicator-version", required=True)
    command.add_argument("--max-total-source-bytes", required=True, type=int)
    command.add_argument("--max-record-bytes", required=True, type=int)
    command.add_argument("--max-records", required=True, type=int)
    command.add_argument("--max-nesting-depth", required=True, type=int)
    command.add_argument("--max-string-length", required=True, type=int)
    command.add_argument("--max-headline-length", required=True, type=int)
    command.add_argument("--max-summary-length", required=True, type=int)
    command.add_argument("--max-source-files", required=True, type=int)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    for name in ("validate", "dry-run", "plan", "publish", "recover"):
        _ingestion_arguments(commands.add_parser(name))
    status = commands.add_parser("status")
    status.add_argument("--destination-root", required=True, type=Path)
    status.add_argument("--run-id", required=True)
    return value


def _limits(args: argparse.Namespace) -> InputLimits:
    return InputLimits(
        max_total_source_bytes=args.max_total_source_bytes,
        max_record_bytes=args.max_record_bytes,
        max_records=args.max_records,
        max_nesting_depth=args.max_nesting_depth,
        max_string_length=args.max_string_length,
        max_headline_length=args.max_headline_length,
        max_summary_length=args.max_summary_length,
        max_source_files=args.max_source_files,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status":
        root = validate_historical_root(args.destination_root, REPOSITORY_ROOT)
        print(json.dumps(inspect_batch_status(root, args.run_id), sort_keys=True))
        return 0
    provider = LocalHistoricalFileProvider(args.provider, args.provider_version)
    normalizer = StrictSyntheticHistoricalNormalizer(args.normalizer_version)
    deduplicator = ExactObservationalContentDeduplicator(args.deduplicator_version)
    plan = build_ingestion_plan(
        provider,
        tuple(args.source),
        args.destination_root,
        REPOSITORY_ROOT,
        args.as_of,
        _limits(args),
        normalizer=normalizer,
        deduplicator=deduplicator,
        recovery=args.command == "recover",
    )
    root = validate_historical_root(args.destination_root, REPOSITORY_ROOT)
    if args.command in {"validate", "dry-run", "plan"}:
        result = plan.summary()
        result["mode"] = args.command
        result["writes_performed"] = 0
        print(json.dumps(result, sort_keys=True))
        return 0
    manifest_path = publish_plan(root, plan, recovery=args.command == "recover")
    print(json.dumps({
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "mode": args.command,
        "run_id": plan.run_id,
        "status": "published",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
