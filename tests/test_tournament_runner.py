import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from aml.tournament_config import FIXED_SPLITS, load_tournament_config
from aml.tournament_runner import SourceState, build_plan, run_tournament


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_root(tmp_path):
    config_payload = json.loads(
        (Path(__file__).parents[1] / "config/strategy_tournament_baseline.yaml").read_text()
    )
    config_payload["dataset_manifest"] = "manifests/test.json"
    config_payload["strategies"] = [
        item for item in config_payload["strategies"] if item["strategy_id"] == "no_trade"
    ]
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_payload))
    base = tmp_path / "data" / "research" / "test-v001" / "sip" / "AAA" / "2023-07-24"
    processed = base / "processed" / "regular_1min.csv"
    metadata = base / "metadata" / "regular_acquisition.json"
    processed.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    timestamps = pd.date_range("2023-07-24 09:30", periods=10, freq="min", tz="America/New_York")
    pd.DataFrame({
        "timestamp": timestamps, "symbol": "AAA", "open": 100.0,
        "high": 100.1, "low": 99.9, "close": 100.0, "volume": 100,
        "bar_vwap": 100.0,
    }).to_csv(processed, index=False)
    metadata.write_text(json.dumps({
        "status": "success", "requested_feed": "sip", "timeframe": "1Min",
        "dataset_vintage": "test-v001", "symbol": "AAA",
        "trading_date": "2023-07-24", "segment": "regular", "record_count": 10,
        "processed_sha256": _sha(processed),
        "normalization": {"expected_minute_count": 10, "missing_timestamp_count": 0},
    }))
    manifest = {
        "dataset_vintage": "test-v001", "dataset_fingerprint_sha256": "d" * 64,
        "coverage": {
            "feed": "sip", "timeframe": "1Min", "symbols": ["AAA"],
            "start_date": "2023-07-24", "end_date": "2023-07-24",
        },
        "partitions": [],
    }
    return load_tournament_config(config_path), manifest


def test_run_identity_resume_atomic_completeness_and_deterministic_outputs(tmp_path):
    config, manifest = fixture_root(tmp_path)
    source = SourceState("a" * 40, True, "b" * 64, ("src/example.py",))
    plan = build_plan(
        tmp_path, config, manifest, source, (FIXED_SPLITS["development"],),
        strategy_ids=["no_trade"], symbols=["AAA"],
    )
    first = run_tournament(
        tmp_path, tmp_path / "artifacts-one", config, plan, manifest, source, resume=False
    )
    second = run_tournament(
        tmp_path, tmp_path / "artifacts-two", config, plan, manifest, source, resume=False
    )
    assert first.run_id == second.run_id
    assert first.deterministic_artifact_hashes == second.deterministic_artifact_hashes
    resumed = run_tournament(
        tmp_path, tmp_path / "artifacts-one", config, plan, manifest, source, resume=True
    )
    assert resumed.resumed_units == 1
    (first.final_directory / "leaderboard.csv").write_text("corrupt\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_tournament(
            tmp_path, tmp_path / "artifacts-one", config, plan, manifest, source, resume=True
        )


def test_run_identity_changes_with_source_or_configuration(tmp_path):
    config, manifest = fixture_root(tmp_path)
    split = (FIXED_SPLITS["development"],)
    one = build_plan(tmp_path, config, manifest, SourceState("a" * 40, False, "b" * 64, ()), split)
    two = build_plan(tmp_path, config, manifest, SourceState("a" * 40, True, "c" * 64, ("src/x.py",)), split)
    assert one.run_id != two.run_id
