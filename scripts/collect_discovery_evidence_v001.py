#!/usr/bin/env python3
"""Collect bounded discovery halt/action evidence and freeze the XNYS calendar."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile

from dotenv import load_dotenv

from aml.discovery_evidence_v001 import (
    build_calendar_artifact,
    collect_corporate_action_evidence,
    collect_halt_evidence,
    reconcile_gme_reference_halts,
)
from aml.winner_archetype_contracts import canonical_json


def _symbols(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        values = [row["symbol"] for row in csv.DictReader(handle)]
    if len(values) != 23 or len(set(values)) != 23:
        raise SystemExit("Universe must contain exactly 23 unique symbols")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--universe",
        type=Path,
        default=Path("config/liquid_day_trading_universe_v001.csv"),
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--gme-halt-reference-root",
        type=Path,
        default=Path("data/market_halts/GME"),
    )
    args = parser.parse_args()

    if args.env_file:
        load_dotenv(args.env_file, override=False)
    symbols = _symbols(args.universe)
    output = args.output_root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"Write-once output already exists: {output}")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        calendar = build_calendar_artifact()
        calendar_path = staging / "calendar_v001.json"
        descriptor = os.open(
            calendar_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json(calendar))
        halts = collect_halt_evidence(staging / "halts_v001", symbols=symbols)
        halt_reconciliation = reconcile_gme_reference_halts(
            halts["normalized_records"],
            (
                args.gme_halt_reference_root / "2024-05-13_verified_halts.csv",
                args.gme_halt_reference_root / "2024-05-14_verified_halts.csv",
            ),
        )
        actions = collect_corporate_action_evidence(
            staging / "corporate_actions_v001",
            symbols=symbols,
            api_key=os.environ.get("ALPACA_API_KEY", "")
            or os.environ.get("APCA_API_KEY_ID", ""),
            api_secret=os.environ.get("ALPACA_SECRET_KEY", "")
            or os.environ.get("APCA_API_SECRET_KEY", ""),
        )
        os.replace(staging, output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    report = {
        "calendar_identity": calendar["identity"],
        "calendar_sessions": len(calendar["sessions"]),
        "halt_identity": halts["identity"],
        "halt_raw_response_count": len(halts["daily"]),
        "halt_universe_record_count": len(halts["normalized_records"]),
        "gme_halt_reconciliation_identity": halt_reconciliation["identity"],
        "gme_halt_reconciliation_count": halt_reconciliation["record_count"],
        "corporate_action_identity": actions["identity"],
        "corporate_action_page_count": len(actions["pages"]),
        "corporate_action_record_count": len(actions["records"]),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
