import hashlib
import json

import pandas as pd
import pytest

from aml.dataset_manifest import build_dataset_manifest


COMMIT = "a" * 40


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(tmp_path, *, corrupt=False):
    universe = tmp_path / "config" / "universe.csv"
    universe.parent.mkdir()
    universe.write_text("symbol,market,category,notes\nSPY,S&P,index,proxy\n")
    for segment, rows in (("premarket", 2), ("regular", 3)):
        base = tmp_path / "data" / "research" / "v001" / "sip" / "SPY" / "2024-01-02"
        raw = base / "raw" / f"{segment}_provider_response.json"
        processed = base / "processed" / f"{segment}_1min.csv"
        metadata = base / "metadata" / f"{segment}_acquisition.json"
        for path in (raw, processed, metadata):
            path.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(json.dumps({"bars": []}) + "\n")
        pd.DataFrame({"timestamp": range(rows), "close": range(rows)}).to_csv(processed, index=False)
        record = {
            "status": "success", "provider": "alpaca", "requested_feed": "sip",
            "actual_feed": None,
            "actual_feed_evidence": "explicit_request_parameter_provider_did_not_echo_feed",
            "timeframe": "1Min", "dataset_vintage": "v001", "symbol": "SPY",
            "trading_date": "2024-01-02", "segment": segment,
            "record_count": rows, "raw_response_sha256": _sha(raw),
            "processed_sha256": _sha(processed),
            "acquisition_timestamp": "2024-01-03T00:00:00+00:00",
            "normalization": {
                "output_record_count": rows, "missing_timestamp_count": 0,
                "duplicate_timestamp_count": 0, "out_of_order": False,
                "cross_date_bar_count": 0, "outside_requested_window_count": 0,
                "unexpected_1600_bar_count": 0,
            },
        }
        metadata.write_text(json.dumps(record) + "\n")
    if corrupt:
        raw.write_text("changed\n")
    return universe


def test_manifest_is_path_independent_and_contains_required_identity(tmp_path):
    universe = _dataset(tmp_path)
    manifest = build_dataset_manifest(
        tmp_path, dataset_vintage="v001", universe_path=universe,
        source_commit=COMMIT, repository="https://github.com/example/repo",
        start="2024-01-02", end="2024-01-02", subscription_plan="Plan",
        subscription_price_usd_per_month=99, generated_at="2024-01-04T00:00:00+00:00",
    )
    assert manifest["coverage"]["symbol_day_count"] == 1
    assert manifest["partitions"][0]["rows"] == {"premarket": 2, "regular": 3, "total": 5}
    assert manifest["software"]["downloader_commit"] == COMMIT
    assert manifest["validation"]["successful_segments"] == 2
    assert manifest["coverage"]["processed_row_count"] == 5
    assert manifest["validation"]["verified_file_count"] == 6
    assert manifest["validation"]["by_segment"]["regular"]["processed_row_count"] == 3
    assert str(tmp_path) not in json.dumps(manifest)


def test_manifest_fails_closed_on_hash_change(tmp_path):
    universe = _dataset(tmp_path, corrupt=True)
    with pytest.raises(RuntimeError, match="Raw file hash mismatch"):
        build_dataset_manifest(
            tmp_path, dataset_vintage="v001", universe_path=universe,
            source_commit=COMMIT, repository="https://github.com/example/repo",
            start="2024-01-02", end="2024-01-02", subscription_plan="Plan",
            subscription_price_usd_per_month=99,
        )
