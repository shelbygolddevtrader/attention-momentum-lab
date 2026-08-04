"""Coverage, fail-closed, immutability, and determinism tests for Campaign V001."""

from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.benchmark_hypothesis_library_v001 import load_library
from aml.benchmark_implementation_campaign_v001 import (
    ARCHITECTURE_FIT_BY_CAPABILITY,
    CLASSIFICATION_BY_CAPABILITY,
    BenchmarkImplementationCampaignError,
    assessment_identity,
    finalize_config,
    load_config,
    run_campaign,
    validate_config,
    verify_campaign,
)
from aml.benchmark_strategy_research_v001 import canonical_json, verify_bundle


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/benchmark_implementation_campaign_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
CANDIDATE_BUNDLE = ROOT / "manifests/executable_benchmark_candidate_v001"
CANONICAL_OUTPUT = ROOT / "manifests/benchmark_implementation_campaign_v001"
CLI = ROOT / "scripts/run_benchmark_implementation_campaign_v001.py"
EXCLUDED = "high-of-day-breakout-continuation-v001"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _campaign(tmp_path: Path) -> Path:
    output = tmp_path / "implementation-campaign"
    run_campaign(
        config_path=CONFIG,
        library_path=LIBRARY,
        output_root=output,
        repository_root=ROOT,
    )
    return output


def test_config_is_canonical_and_covers_every_remaining_hypothesis_once() -> None:
    library = load_library(LIBRARY)
    config = load_config(CONFIG, library)
    assert CONFIG.read_bytes() == canonical_json(config)
    expected = sorted(
        item["library_entry_id"]
        for item in library["hypotheses"]
        if item["library_entry_id"] != EXCLUDED
    )
    actual = [item["library_entry_id"] for item in config["assessments"]]
    assert actual == expected
    assert len(actual) == len(set(actual)) == 39
    assert config["existing_executable_candidate"]["library_entry_id"] == EXCLUDED
    assert config["library_dependency"]["library_identity"] == library[
        "library_identity"
    ]
    assert config["library_dependency"]["file_sha256"] == hashlib.sha256(
        LIBRARY.read_bytes()
    ).hexdigest()


def test_every_assessment_is_identity_bound_and_fail_closed() -> None:
    library = load_library(LIBRARY)
    config = load_config(CONFIG, library)
    entries = {item["library_entry_id"]: item for item in library["hypotheses"]}
    for assessment in config["assessments"]:
        entry = entries[assessment["library_entry_id"]]
        assert assessment["registration_identity"] == entry["registration_identity"]
        assert assessment["framework_hypothesis_identity"] == entry[
            "framework_hypothesis_identity"
        ]
        assert assessment["library_revision"] == entry["revision"] == 1
        assert assessment["required_indicators"] == entry["required_indicators"]
        assert assessment["expected_holding_period"] == entry[
            "expected_holding_period"
        ]
        capability = assessment["minimal_missing_capability"]["capability_class"]
        assert assessment["canonical_classification"] == (
            CLASSIFICATION_BY_CAPABILITY[capability]
        )
        assert assessment["architecture_fit"] == (
            ARCHITECTURE_FIT_BY_CAPABILITY[capability]
        )
        assert not any(assessment["complete_chain"].values())
        assert assessment["assessment_identity"] == assessment_identity(assessment)


def test_minimal_capability_counts_and_representative_decisions_are_exact() -> None:
    config = load_config(CONFIG, load_library(LIBRARY))
    assessments = {item["library_entry_id"]: item for item in config["assessments"]}
    assert Counter(
        item["minimal_missing_capability"]["capability_class"]
        for item in assessments.values()
    ) == {"data": 24, "governance": 11, "execution_model": 3, "indicator": 1}
    expected = {
        "failed-volume-breakout-reversal-v001": (
            "governance",
            "prospective-numeric-executable-specification",
        ),
        "late-day-rebalance-continuation-v001": (
            "indicator",
            "synchronized-breadth-volume-profile-indicator",
        ),
        "spread-normalization-reversal-v001": (
            "execution_model",
            "subminute-quote-execution-model",
        ),
        "analyst-revision-continuation-v001": (
            "data",
            "point-in-time-analyst-revision-history",
        ),
    }
    for entry_id, (capability_class, capability_code) in expected.items():
        missing = assessments[entry_id]["minimal_missing_capability"]
        assert missing["capability_class"] == capability_class
        assert missing["capability_code"] == capability_code


def test_existing_executable_candidate_remains_separate_and_unchanged() -> None:
    config = load_config(CONFIG, load_library(LIBRARY))
    existing = config["existing_executable_candidate"]
    bundle = verify_bundle(CANDIDATE_BUNDLE)
    assert bundle["identity"] == existing["bundle_identity"]
    assert existing["campaign_identity"] == (
        "f31e0148844b7912b3408d17559e90b3c7d3266ed177286823a875c646cfcca3"
    )
    assert existing["classification"] == "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    assert EXCLUDED not in {
        item["library_entry_id"] for item in config["assessments"]
    }


def test_campaign_publishes_complete_immutable_readiness_evidence(
    tmp_path: Path,
) -> None:
    output = _campaign(tmp_path)
    manifest = verify_campaign(
        output,
        config_path=CONFIG,
        library_path=LIBRARY,
        repository_root=ROOT,
    )
    assert manifest["verified"] is True
    assert manifest["library_hypothesis_count"] == 40
    assert manifest["existing_executable_count"] == 1
    assert manifest["assessment_count"] == manifest["blocked_count"] == 39
    assert manifest["complete_chain_count"] == 0
    assert manifest["capability_class_counts"] == {
        "data": 24,
        "execution_model": 3,
        "governance": 11,
        "indicator": 1,
    }
    assert manifest["classification_counts"] == {
        "BLOCKED_MISSING_AUTHORIZED_DATA": 24,
        "BLOCKED_MISSING_EXECUTABLE_SPECIFICATION": 11,
        "BLOCKED_MISSING_EXECUTION_MODEL": 3,
        "BLOCKED_MISSING_INDICATOR": 1,
    }
    assert manifest["reconciliation"]["empirical_outcome_access_count"] == 0
    assert manifest["reconciliation"]["strategy_execution_count"] == 0
    assert len(list(output.glob("assessments/*/readiness.json"))) == 39


def test_committed_campaign_is_canonical_and_verified() -> None:
    manifest = verify_campaign(
        CANONICAL_OUTPUT,
        config_path=CONFIG,
        library_path=LIBRARY,
        repository_root=ROOT,
    )
    assert manifest["verified"] is True
    assert manifest["campaign_identity"] == (
        "56e9326744b5b593a2d2a60ebd51f6c848ed4b6e2180ad6a03e0a7b023dd18c1"
    )
    assert manifest["manifest_identity"] == (
        "f1af6b11aa8092a08db62e04a80259c5e31508c0b5d51aeb99c8cf6ecef9a961"
    )


def test_report_is_deterministic_and_contains_no_performance_claim(
    tmp_path: Path,
) -> None:
    output = _campaign(tmp_path)
    report = (output / "IMPLEMENTATION_READINESS_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "Remaining hypotheses assessed: 39" in report
    assert "Complete executable chains found: 0" in report
    assert "`data`: 24" in report
    assert "does not\nexecute a strategy" in report
    prohibited_claims = (
        "validated edge",
        "profitable strategy",
        "paper ready",
        "live ready",
    )
    assert not any(claim in report.casefold() for claim in prohibited_claims)


def test_publication_is_write_once_and_rejects_protected_boundaries(
    tmp_path: Path,
) -> None:
    output = _campaign(tmp_path)
    with pytest.raises(BenchmarkImplementationCampaignError, match="already exists"):
        run_campaign(
            config_path=CONFIG,
            library_path=LIBRARY,
            output_root=output,
            repository_root=ROOT,
        )
    with pytest.raises(BenchmarkImplementationCampaignError, match="protected boundary"):
        run_campaign(
            config_path=CONFIG,
            library_path=LIBRARY,
            output_root=tmp_path / "holdout" / "campaign",
            repository_root=ROOT,
        )


def test_tampered_artifact_and_report_are_rejected(tmp_path: Path) -> None:
    output = _campaign(tmp_path)
    artifact = min(output.glob("assessments/*/readiness.json"))
    original = artifact.read_bytes()
    artifact.write_bytes(original + b" ")
    with pytest.raises(BenchmarkImplementationCampaignError, match="file hash"):
        verify_campaign(
            output,
            config_path=CONFIG,
            library_path=LIBRARY,
            repository_root=ROOT,
        )
    artifact.write_bytes(original)
    report = output / "IMPLEMENTATION_READINESS_REPORT.md"
    report.write_bytes(report.read_bytes() + b"changed\n")
    with pytest.raises(BenchmarkImplementationCampaignError, match="file hash"):
        verify_campaign(
            output,
            config_path=CONFIG,
            library_path=LIBRARY,
            repository_root=ROOT,
        )


def test_unexpected_file_is_rejected(tmp_path: Path) -> None:
    output = _campaign(tmp_path)
    (output / "unexpected.txt").write_text("not canonical\n", encoding="utf-8")
    with pytest.raises(BenchmarkImplementationCampaignError, match="unexpected"):
        verify_campaign(
            output,
            config_path=CONFIG,
            library_path=LIBRARY,
            repository_root=ROOT,
        )


def test_missing_duplicate_or_completed_assessment_is_rejected() -> None:
    library = load_library(LIBRARY)
    original = _json(CONFIG)
    missing = copy.deepcopy(original)
    missing["assessments"].pop()
    missing["campaign_identity"] = "0" * 64
    with pytest.raises(BenchmarkImplementationCampaignError, match="exactly cover"):
        finalize_config(missing, library)
    duplicate = copy.deepcopy(original)
    duplicate["assessments"][-1] = copy.deepcopy(duplicate["assessments"][-2])
    duplicate["campaign_identity"] = "0" * 64
    with pytest.raises(BenchmarkImplementationCampaignError, match="exactly cover"):
        finalize_config(duplicate, library)
    completed = copy.deepcopy(original)
    completed["assessments"][0]["complete_chain"] = {
        key: True for key in completed["assessments"][0]["complete_chain"]
    }
    completed["campaign_identity"] = "0" * 64
    with pytest.raises(
        BenchmarkImplementationCampaignError, match="complete executable chain"
    ):
        finalize_config(completed, library)


def test_identity_or_classification_substitution_is_rejected() -> None:
    library = load_library(LIBRARY)
    changed = _json(CONFIG)
    changed["assessments"][0]["framework_hypothesis_identity"] = "d" * 64
    changed["campaign_identity"] = "0" * 64
    with pytest.raises(BenchmarkImplementationCampaignError, match="hypothesis binding"):
        finalize_config(changed, library)
    changed = _json(CONFIG)
    changed["assessments"][0]["canonical_classification"] = (
        "BLOCKED_MISSING_INDICATOR"
    )
    changed["campaign_identity"] = "0" * 64
    with pytest.raises(BenchmarkImplementationCampaignError, match="classification"):
        finalize_config(changed, library)


def test_bound_source_substitution_fails_before_publication(tmp_path: Path) -> None:
    library = load_library(LIBRARY)
    changed = _json(CONFIG)
    changed["campaign_source_sha256"][
        "src/aml/benchmark_implementation_campaign_v001.py"
    ] = "d" * 64
    changed["campaign_identity"] = "0" * 64
    changed = finalize_config(changed, library)
    changed_path = tmp_path / "changed.json"
    changed_path.write_bytes(canonical_json(changed))
    output = tmp_path / "changed-output"
    with pytest.raises(BenchmarkImplementationCampaignError, match="source changed"):
        run_campaign(
            config_path=changed_path,
            library_path=LIBRARY,
            output_root=output,
            repository_root=ROOT,
        )
    assert not output.exists()


def test_cli_output_is_byte_deterministic_across_hash_seeds_and_timezones(
    tmp_path: Path,
) -> None:
    roots: list[Path] = []
    summaries: list[str] = []
    for index, (seed, timezone) in enumerate((("1", "UTC"), ("777", "Asia/Tokyo"))):
        output = tmp_path / f"campaign-{index}"
        completed = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--config",
                str(CONFIG),
                "--library",
                str(LIBRARY),
                "--output-root",
                str(output),
                "--repository-root",
                str(ROOT),
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(ROOT / "src"),
                "TZ": timezone,
            },
            check=True,
            capture_output=True,
            text=True,
        )
        roots.append(output)
        summaries.append(completed.stdout)
    snapshots = [
        {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        for root in roots
    ]
    assert snapshots[0] == snapshots[1]
    assert summaries[0] == summaries[1]


def test_layer_has_no_execution_network_or_protected_data_capability() -> None:
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "src/aml/benchmark_implementation_campaign_v001.py",
            "scripts/run_benchmark_implementation_campaign_v001.py",
        )
    )
    prohibited = (
        "simulate_portfolio(",
        "evaluate_high_of_day_breakout(",
        "TradingClient",
        "submit_order",
        "requests.get",
        "urllib.request",
        "socket.socket",
        "run_professional_strategy_olympics",
    )
    assert not any(token in sources for token in prohibited)
    for frozen in (
        "src/aml/benchmark_strategy_research_v001.py",
        "src/aml/benchmark_discovery_campaign_v001.py",
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
        "src/aml/professional_strategy_olympics_orchestrator_v001.py",
    ):
        assert "benchmark_implementation_campaign_v001" not in (
            ROOT / frozen
        ).read_text(encoding="utf-8")


def test_config_validation_is_pure_and_does_not_create_artifacts(tmp_path: Path) -> None:
    config = _json(CONFIG)
    library = load_library(LIBRARY)
    before = set(tmp_path.rglob("*"))
    assert validate_config(config, library)["campaign_identity"] == config[
        "campaign_identity"
    ]
    assert set(tmp_path.rglob("*")) == before
