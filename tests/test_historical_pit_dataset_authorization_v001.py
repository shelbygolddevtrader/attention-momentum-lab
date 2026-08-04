from __future__ import annotations

import ast
import copy
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from aml.benchmark_strategy_research_v001 import canonical_json
from aml.historical_pit_dataset_authorization_v001 import (
    HistoricalPITAuthorizationError,
    REQUIRED_GATES,
    assessment_identity,
    authorization_decision,
    dataset_identity,
    finalize_assessment,
    load_assessment,
    validate_assessment,
    verification_artifact,
    verify_local_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/historical_pit_dataset_authorization_v001.json"
EXPECTED_ASSESSMENT = "75917f2859e132d3633cd3f26acb28798719e6a60e83e44311302ec2467544ce"
EXPECTED_DATASET = "a481a52db719a8441b9edee1b79a3831ff2c1591c54f58d446e5c4503dc06f18"
EXPECTED_VERIFICATION = "fb15120e00958d88676bad9c1df95d9338d88d57276bc8b2178565edd3314be0"


def _load() -> dict[str, object]:
    return load_assessment(CONFIG, repository_root=ROOT)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_fixture(tmp_path: Path, assessment: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy(assessment)
    candidate = value["candidate"]
    files = candidate["files"]
    for record in files.values():
        (tmp_path / Path(record["relative_path"])).parent.mkdir(
            parents=True, exist_ok=True
        )
    raw = tmp_path / files["raw"]["relative_path"]
    processed = tmp_path / files["processed"]["relative_path"]
    metadata = tmp_path / files["metadata"]["relative_path"]
    columns = [
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trade_count",
        "bar_vwap",
    ]
    start = datetime(2023, 7, 24, 9, 30, tzinfo=timezone(timedelta(hours=-4)))
    raw.write_text(
        json.dumps(
            {
                "bars": [
                    {
                        "c": 100.5,
                        "h": 101.0,
                        "l": 99.0,
                        "n": 10,
                        "o": 100.0,
                        "t": (start + timedelta(minutes=offset)).astimezone(
                            timezone.utc
                        ).isoformat(),
                        "v": 1000,
                        "vw": 100.25,
                    }
                    for offset in range(391)
                ],
                "next_page_token": None,
                "symbol": "AAPL",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    with processed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for offset in range(390):
            writer.writerow(
                {
                    "timestamp": (start + timedelta(minutes=offset)).isoformat(
                        sep=" "
                    ),
                    "symbol": "AAPL",
                    "open": "100.0",
                    "high": "101.0",
                    "low": "99.0",
                    "close": "100.5",
                    "volume": "1000",
                    "trade_count": "10",
                    "bar_vwap": "100.25",
                }
            )
    raw_hash = _hash(raw)
    processed_hash = _hash(processed)
    metadata.write_text(
        json.dumps(
            {
                "acquisition_timestamp": candidate["acquired_at"],
                "actual_feed": candidate["actual_feed"],
                "actual_feed_evidence": candidate["actual_feed_evidence"],
                "adjustment": candidate["adjustment"],
                "processed_sha256": processed_hash,
                "provider": "alpaca",
                "normalization": {
                    "cross_date_bar_count": 0,
                    "duplicate_timestamp_count": 0,
                    "expected_minute_count": 390,
                    "missing_timestamp_count": 0,
                    "out_of_order": False,
                    "output_record_count": 390,
                    "requested_feed": "sip",
                    "segment": "regular",
                },
                "pagination": {
                    "page_count": 1,
                    "page_record_counts": [391],
                    "page_tokens_followed": 0,
                    "pagination_occurred": False,
                },
                "raw_response_sha256": raw_hash,
                "record_count": 390,
                "requested_end_timestamp_exclusive": candidate[
                    "regular_end_exclusive"
                ],
                "requested_feed": candidate["requested_feed"],
                "requested_start_timestamp": candidate["regular_start_inclusive"],
                "segment": candidate["segment"],
                "symbol": candidate["symbol"],
                "timeframe": candidate["timeframe"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    files["raw"]["sha256"] = raw_hash
    files["processed"]["sha256"] = processed_hash
    files["metadata"]["sha256"] = _hash(metadata)
    candidate["dataset_identity"] = dataset_identity(candidate)
    return value


def test_committed_assessment_is_canonical_blocked_and_identity_bound() -> None:
    value = _load()
    assert value["assessment_identity"] == EXPECTED_ASSESSMENT
    assert value["candidate"]["dataset_identity"] == EXPECTED_DATASET
    assert value["authorization"] == {
        "authorized": False,
        "discovery_execution_permitted": False,
        "reason_codes": [
            "candidate-descends-from-previously-evaluated-dataset",
            "point-in-time-corporate-action-lineage-unproven",
            "provider-feed-identity-not-echoed",
            "written-license-retention-evidence-missing",
        ],
        "scope": "none",
        "status": "BLOCKED_NOT_AUTHORIZED",
    }
    assert CONFIG.read_bytes() == canonical_json(value)


def test_all_required_gates_are_exactly_ordered() -> None:
    value = _load()
    assert tuple(gate["gate_id"] for gate in value["gates"]) == REQUIRED_GATES


def test_failed_gate_cannot_be_presented_as_authorized() -> None:
    value = copy.deepcopy(_load())
    value["authorization"] = {
        "authorized": True,
        "discovery_execution_permitted": True,
        "reason_codes": [],
        "scope": "discovery_only",
        "status": "AUTHORIZED",
    }
    value["assessment_identity"] = assessment_identity(value)
    with pytest.raises(
        HistoricalPITAuthorizationError, match="authorization contradicts"
    ):
        validate_assessment(value, repository_root=ROOT)


def test_only_all_passing_gates_can_authorize() -> None:
    gates = copy.deepcopy(_load()["gates"])
    for gate in gates:
        gate["status"] = "passed"
        gate["failure_code"] = None
    assert authorization_decision(gates) == {
        "authorized": True,
        "discovery_execution_permitted": True,
        "reason_codes": [],
        "scope": "discovery_only",
        "status": "AUTHORIZED",
    }


def test_v001_cannot_be_mutated_into_a_successful_authorization() -> None:
    value = copy.deepcopy(_load())
    for gate in value["gates"]:
        gate["status"] = "passed"
        gate["failure_code"] = None
    value = finalize_assessment(value)
    with pytest.raises(HistoricalPITAuthorizationError, match="frozen gate outcome"):
        validate_assessment(value, repository_root=ROOT)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda value: value["gates"].pop(), "complete and deterministically ordered"),
        (
            lambda value: value["gates"][0].update(
                {"failure_code": "contradiction"}
            ),
            "passed gate cannot have failure code",
        ),
        (
            lambda value: value["candidate"].update({"symbol": "MSFT"}),
            "candidate dataset identity changed",
        ),
    ],
)
def test_tampering_fails_closed(mutation, match: str) -> None:
    value = copy.deepcopy(_load())
    mutation(value)
    with pytest.raises(HistoricalPITAuthorizationError, match=match):
        validate_assessment(value, repository_root=ROOT)


def test_finalize_is_deterministic() -> None:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["assessment_identity"] = "0" * 64
    value["candidate"]["dataset_identity"] = "0" * 64
    value["authorization"] = {}
    assert finalize_assessment(value) == _load()


def test_local_candidate_verification_checks_bytes_and_every_minute(
    tmp_path: Path,
) -> None:
    value = _local_fixture(tmp_path, _load())
    result = verify_local_candidate(value, dataset_root=tmp_path)
    assert result["candidate_bytes_verified"] is True
    assert result["regular_minute_count"] == 390
    assert result["timestamp_boundary_verified"] is True


def test_local_candidate_hash_tampering_fails_closed(tmp_path: Path) -> None:
    value = _local_fixture(tmp_path, _load())
    processed = tmp_path / value["candidate"]["files"]["processed"]["relative_path"]
    processed.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(HistoricalPITAuthorizationError, match="bytes changed"):
        verify_local_candidate(value, dataset_root=tmp_path)


def test_local_candidate_gap_fails_closed_even_with_updated_hash(tmp_path: Path) -> None:
    value = _local_fixture(tmp_path, _load())
    processed = tmp_path / value["candidate"]["files"]["processed"]["relative_path"]
    lines = processed.read_text(encoding="utf-8").splitlines()
    processed.write_text("\n".join(lines[:2] + lines[3:]) + "\n", encoding="utf-8")
    value["candidate"]["files"]["processed"]["sha256"] = _hash(processed)
    metadata = tmp_path / value["candidate"]["files"]["metadata"]["relative_path"]
    metadata_value = json.loads(metadata.read_text(encoding="utf-8"))
    metadata_value["processed_sha256"] = _hash(processed)
    metadata.write_text(
        json.dumps(metadata_value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    value["candidate"]["files"]["metadata"]["sha256"] = _hash(metadata)
    with pytest.raises(HistoricalPITAuthorizationError, match="incomplete"):
        verify_local_candidate(value, dataset_root=tmp_path)


def test_unsafe_candidate_path_is_rejected(tmp_path: Path) -> None:
    value = copy.deepcopy(_load())
    value["candidate"]["files"]["raw"]["relative_path"] = "../raw.json"
    with pytest.raises(HistoricalPITAuthorizationError, match="unsafe"):
        verify_local_candidate(value, dataset_root=tmp_path)


def test_symlinked_candidate_evidence_is_rejected(tmp_path: Path) -> None:
    value = _local_fixture(tmp_path, _load())
    raw_record = value["candidate"]["files"]["raw"]
    raw = tmp_path / raw_record["relative_path"]
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(raw.read_bytes())
    raw.unlink()
    raw.symlink_to(replacement)
    with pytest.raises(HistoricalPITAuthorizationError, match="symlink"):
        verify_local_candidate(value, dataset_root=tmp_path)


def test_committed_verification_artifact_reproduces() -> None:
    assessment = _load()
    local = {
        "candidate_bytes_verified": True,
        "observed_file_sha256": {
            label: record["sha256"]
            for label, record in assessment["candidate"]["files"].items()
        },
        "regular_minute_count": 390,
        "timestamp_boundary_verified": True,
    }
    expected = verification_artifact(assessment, local_verification=local)
    assert expected["verification_identity"] == EXPECTED_VERIFICATION
    path = ROOT / "manifests/historical_pit_dataset_authorization_v001/verification.json"
    assert path.read_bytes() == canonical_json(expected)


def test_milestone_does_not_import_execution_or_network_clients() -> None:
    source = (
        ROOT / "src/aml/historical_pit_dataset_authorization_v001.py"
    ).read_text(encoding="utf-8")
    script = (
        ROOT / "scripts/run_historical_pit_dataset_authorization_v001.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for text in (source, script):
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
    assert imported.isdisjoint({"alpaca", "httpx", "requests"})
    assert "run_discovery" not in source + script
    assert "evaluate_authorized_bars" not in source + script
