from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from aml.exploratory_research_mode_v001 import (
    LABELS,
    SOURCE_PATHS,
    ExploratoryResearchError,
    finalize_plan,
    load_plan,
    run_exploratory,
    validate_result,
    verify_bundle,
)
from aml.winner_archetype_contracts import canonical_json


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/exploratory_research_mode_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bars(symbol: str) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2023-07-24 09:30", "2023-07-24 15:59", freq="min", tz="America/New_York"
    )
    frame = pd.DataFrame(
        {
            "timestamp": timestamps.map(lambda item: item.isoformat()),
            "symbol": symbol,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 100.0,
            "trade_count": 1,
            "bar_vwap": 100.0,
        }
    )
    changes = {
        "09:51": {"volume": 200.0},
        "09:52": {"volume": 200.0},
        "09:53": {"volume": 200.0},
        "09:54": {"volume": 200.0},
        "09:55": {
            "open": 102.0,
            "high": 103.0,
            "low": 101.8,
            "close": 102.0,
            "volume": 200.0,
        },
        "09:56": {
            "open": 102.0,
            "high": 102.5,
            "low": 101.5,
            "close": 102.0,
            "volume": 50.0,
        },
        "09:57": {
            "open": 102.0,
            "high": 102.3,
            "low": 101.2,
            "close": 101.8,
            "volume": 50.0,
        },
        "09:58": {
            "open": 101.8,
            "high": 102.8,
            "low": 101.4,
            "close": 102.5,
            "volume": 50.0,
        },
        "09:59": {
            "open": 102.6,
            "high": 106.0,
            "low": 102.5,
            "close": 105.8,
            "volume": 100.0,
        },
    }
    clocks = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(
        "America/New_York"
    ).dt.strftime("%H:%M")
    for clock, values in changes.items():
        for field, value in values.items():
            frame.loc[clocks.eq(clock), field] = value
    return frame


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository = tmp_path / "repository"
    (repository / "manifests").mkdir(parents=True)
    for relative in SOURCE_PATHS:
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    dataset_root = tmp_path / "dataset-v001"
    symbols = ["AAPL", "AMD"]
    for symbol in symbols:
        base = dataset_root / "sip" / symbol / "2023-07-24"
        (base / "processed").mkdir(parents=True)
        (base / "metadata").mkdir()
        csv_path = base / "processed/regular_1min.csv"
        _bars(symbol).to_csv(csv_path, index=False)
        metadata = {
            "actual_feed": None,
            "processed_sha256": _sha(csv_path),
            "requested_feed": "sip",
            "segment": "regular",
            "status": "success",
            "symbol": symbol,
            "trading_date": "2023-07-24",
        }
        (base / "metadata/regular_acquisition.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
    fingerprint = "f" * 64
    manifest = {
        "coverage": {
            "start_date": "2023-07-24",
            "end_date": "2026-07-23",
            "symbols": symbols,
        },
        "dataset_fingerprint_sha256": fingerprint,
        "dataset_vintage": dataset_root.name,
    }
    manifest_path = repository / "manifests/source.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan = json.loads(CONFIG.read_text(encoding="utf-8"))
    plan["dataset"] = {
        **plan["dataset"],
        "dataset_fingerprint": fingerprint,
        "dataset_vintage": dataset_root.name,
        "manifest_relative_path": "manifests/source.json",
        "manifest_sha256": _sha(manifest_path),
        "selection": {
            **plan["dataset"]["selection"],
            "sessions": ["2023-07-24"],
            "symbols": symbols,
        },
    }
    plan = finalize_plan(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(canonical_json(plan))
    output = tmp_path / "exploratory_research/v001/run-test"
    return repository, dataset_root, plan_path, output


def _run(tmp_path: Path):
    repository, dataset, plan, output = _fixture(tmp_path)
    result = run_exploratory(
        repository_root=repository,
        plan_path=plan,
        library_path=LIBRARY,
        dataset_root=dataset,
        output_root=output,
    )
    return result, output


def test_frozen_plan_identity_and_claim_policy() -> None:
    plan = load_plan(CONFIG)
    assert plan["plan_identity"] == (
        "c35df6fee83318f609d84f4588203eed88289dd757a8726bcd4753eda53426df"
    )
    assert plan["labels"] == list(LABELS)
    assert plan["policy"]["empirical_conclusion_permitted"] is False
    assert plan["policy"]["profitability_metrics_published"] is False


def test_two_hypotheses_are_exercised_or_blocked_deterministically(tmp_path: Path) -> None:
    result, output = _run(tmp_path)
    assert result["verified"] is True
    assert result["hypothesis_count"] == 2
    files = sorted(output.glob("0*-*.json"))
    values = {json.loads(path.read_text())["hypothesis"]["library_entry_id"]: json.loads(path.read_text()) for path in files}
    high = values["high-of-day-breakout-continuation-v001"]
    opening = values["opening-drive-first-pullback-v001"]
    assert high["status"] == "EXPLORATORY_BLOCKED_MISSING_INPUT"
    assert high["missing_data_summary"]["missing_required_fields"] == ["spread_bps"]
    assert opening["status"] == "EXPLORATORY_EXERCISED"
    assert opening["counts"]["proposal_count"] >= 1
    assert opening["counts"]["executed_trade_count"] >= 1
    assert opening["counts"]["integrity_failure_count"] == 0
    assert opening["missing_data_summary"]["unavailable_reason_counts"]


def test_artifacts_are_unmistakable_and_contain_no_economic_metrics(tmp_path: Path) -> None:
    _, output = _run(tmp_path)
    for path in output.glob("*.json"):
        value = json.loads(path.read_text())
        text = path.read_text().lower()
        if "labels" in value:
            assert value["labels"] == list(LABELS)
        for prohibited in (
            '"net_pnl"',
            '"gross_pnl"',
            '"profit_factor"',
            '"expectancy"',
            '"win_rate"',
        ):
            assert prohibited not in text
    assert verify_bundle(output)["verified"] is True


def test_bundle_is_byte_deterministic(tmp_path: Path) -> None:
    first_result, first = _run(tmp_path / "first")
    second_result, second = _run(tmp_path / "second")
    assert first_result["run_identity"] == second_result["run_identity"]
    first_bytes = {path.name: path.read_bytes() for path in first.iterdir()}
    second_bytes = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_bytes == second_bytes


def test_write_once_and_git_namespace_boundaries(tmp_path: Path) -> None:
    repository, dataset, plan, output = _fixture(tmp_path)
    arguments = {
        "repository_root": repository,
        "plan_path": plan,
        "library_path": LIBRARY,
        "dataset_root": dataset,
        "output_root": output,
    }
    run_exploratory(**arguments)
    with pytest.raises(ExploratoryResearchError, match="already exists"):
        run_exploratory(**arguments)
    unsafe = repository / "exploratory_research/v001/run"
    (repository / ".git").mkdir()
    with pytest.raises(ExploratoryResearchError, match="inside Git"):
        run_exploratory(**{**arguments, "output_root": unsafe})


def test_tampering_and_affirmative_claims_fail_closed(tmp_path: Path) -> None:
    _, output = _run(tmp_path)
    result_path = next(output.glob("0*-*.json"))
    result = json.loads(result_path.read_text())
    result["claim_flags"]["capital_eligible"] = True
    with pytest.raises(ExploratoryResearchError, match="affirmative claim"):
        validate_result(result)
    result["claim_flags"]["capital_eligible"] = False
    result["net_pnl"] = 1.0
    with pytest.raises(ExploratoryResearchError, match="economic result key"):
        validate_result(result)


def test_validation_and_holdout_dates_are_rejected() -> None:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["dataset"]["selection"]["sessions"] = ["2025-01-02"]
    with pytest.raises(ExploratoryResearchError, match="discovery-period"):
        finalize_plan(value)


def test_partition_gap_fails_closed(tmp_path: Path) -> None:
    repository, dataset, plan, output = _fixture(tmp_path)
    csv_path = dataset / "sip/AAPL/2023-07-24/processed/regular_1min.csv"
    frame = pd.read_csv(csv_path).iloc[:-1]
    frame.to_csv(csv_path, index=False)
    metadata_path = dataset / "sip/AAPL/2023-07-24/metadata/regular_acquisition.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["processed_sha256"] = _sha(csv_path)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ExploratoryResearchError, match="regular minute gap"):
        run_exploratory(
            repository_root=repository,
            plan_path=plan,
            library_path=LIBRARY,
            dataset_root=dataset,
            output_root=output,
        )


def test_module_has_no_network_broker_or_order_capability() -> None:
    source = (ROOT / "src/aml/exploratory_research_mode_v001.py").read_text()
    forbidden = (
        "import requests",
        "import socket",
        "alpaca_rest",
        "submit_order",
        "paper trading",
        "live trading",
    )
    assert not any(item in source.lower() for item in forbidden)
