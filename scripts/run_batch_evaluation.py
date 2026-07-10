import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pandas as pd

from aml.batch_evaluation import (
    batch_artifact_directory, evaluate_batch, file_sha256,
    load_quality_policy, normalize_manifest, require_reproducible_source,
)
from aml.batch_reporting import build_reports
from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.trade_simulator import SimulationConfig


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if pd.isna(value):
        return None
    return value


def main():
    parser = argparse.ArgumentParser(description="Run session-isolated batch research")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = normalize_manifest(pd.read_csv(args.manifest))
    config = SimulationConfig()
    strategy_path = root / "config" / "strategy_v001.yaml"
    quality_policy = load_quality_policy(root / "config" / "batch_evaluation_v001.yaml")
    calendar = ExchangeCalendarsAdapter()
    source_status = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    ).stdout
    source_clean = require_reproducible_source(
        source_status, quality_policy.require_clean_git_worktree
    )
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    input_paths = {
        f"{row.symbol}:{row.trading_date}": root / "data" / "processed" / row.symbol.upper() / f"{row.trading_date}_1min.csv"
        for row in manifest.itertuples()
    }
    input_hashes = {
        key: file_sha256(path) if path.exists() else "missing" for key, path in input_paths.items()
    }

    def loader(row):
        path = input_paths[f"{row['symbol']}:{row['trading_date']}"]
        if not path.exists():
            raise FileNotFoundError(f"Missing local session input for {row['symbol']} {row['trading_date']}")
        return pd.read_csv(path)

    result = evaluate_batch(
        manifest, loader, calendar, file_sha256(strategy_path),
        source_commit, input_hashes, quality_policy, config,
    )
    reports = build_reports(result.session_results, result.trades)
    output = batch_artifact_directory(root, result.run_id)
    output.mkdir(parents=True, exist_ok=True)
    result.normalized_manifest.to_csv(output / "manifest_snapshot.csv", index=False)
    result.session_results.to_csv(output / "session_results.csv", index=False)
    result.trades.to_csv(output / "trades.csv", index=False)
    result.candidates.to_csv(output / "candidates.csv", index=False)
    result.session_results.loc[result.session_results["trade_count"] == 0].to_csv(output / "zero_trade_sessions.csv", index=False)
    result.session_results[["symbol", "trading_date", "expected_minute_count", "observed_minute_count", "missing_minute_count", "missing_percentage", "largest_consecutive_gap", "data_quality_band"]].to_csv(output / "data_quality.csv", index=False)
    (output / "aggregate_overall.json").write_text(json.dumps(_json_ready(reports["overall"]), indent=2), encoding="utf-8")
    for filename, key in (
        ("aggregate_by_session_class.csv", "by_session_class"),
        ("aggregate_by_symbol.csv", "by_symbol"), ("aggregate_by_date.csv", "by_date"),
        ("aggregate_by_time_bucket.csv", "by_time_bucket"),
        ("aggregate_by_score_band.csv", "by_score_band"),
        ("aggregate_by_exit_reason.csv", "by_exit_reason"),
        ("aggregate_by_data_quality.csv", "by_data_quality"),
    ):
        reports[key].to_csv(output / filename, index=False)
    metadata = {
        "run_id": result.run_id, "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "session_level_not_portfolio", "source_commit": source_commit,
        "source_clean": source_clean,
        "strategy_fingerprint": file_sha256(strategy_path),
        "quality_policy_fingerprint": quality_policy.fingerprint(),
        "quality_policy": quality_policy.normalized_payload(),
        "calendar": result.calendar_identity.normalized_payload(),
        "calendar_fingerprint": result.calendar_identity.fingerprint(),
        "simulator_config": asdict(config), "input_hashes": result.input_hashes,
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved batch artifacts: {output}")


if __name__ == "__main__":
    main()
