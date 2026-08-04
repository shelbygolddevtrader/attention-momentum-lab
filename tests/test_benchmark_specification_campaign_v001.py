"""Determinism and fail-closed tests for Specification Campaign V001."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.benchmark_hypothesis_library_v001 import load_library
from aml.benchmark_implementation_campaign_v001 import load_config as load_readiness
from aml.benchmark_specification_campaign_v001 import (
    BenchmarkSpecificationCampaignError,
    FROZEN_SPECIFICATION,
    SELECTION_REVIEW,
    campaign_identity,
    load_config,
    publish_campaign,
    selection_identity,
    specification_identity,
    validate_config,
    verify_campaign,
)
from aml.benchmark_strategy_research_v001 import canonical_json


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/benchmark_specification_campaign_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
READINESS = ROOT / "config/benchmark_implementation_campaign_v001.json"
EVIDENCE = ROOT / "manifests/benchmark_specification_campaign_v001"
CLI = ROOT / "scripts/validate_benchmark_specification_campaign_v001.py"


def _config() -> dict[str, object]:
    return load_config(
        CONFIG,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )


def _validate(value: dict[str, object]) -> None:
    validate_config(
        value,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )


def test_config_is_canonical_identity_bound_and_selects_exactly_one() -> None:
    config = _config()
    assert CONFIG.read_bytes() == canonical_json(config)
    assert config["specification_identity"] == specification_identity(
        FROZEN_SPECIFICATION
    )
    assert config["selection_identity"] == selection_identity(SELECTION_REVIEW)
    assert config["campaign_identity"] == campaign_identity(config)
    assert len(config["selection_review"]) == 11
    selected = [item for item in config["selection_review"] if item["selected"]]
    assert [item["library_entry_id"] for item in selected] == [
        "opening-drive-first-pullback-v001"
    ]


def test_selection_cohort_and_bindings_reproduce_frozen_inputs() -> None:
    library = load_library(LIBRARY)
    readiness = load_readiness(READINESS, library)
    config = _config()
    ready = sorted(
        item["library_entry_id"]
        for item in readiness["assessments"]
        if item["canonical_classification"]
        == "BLOCKED_MISSING_EXECUTABLE_SPECIFICATION"
    )
    assert ready == sorted(item["library_entry_id"] for item in SELECTION_REVIEW)
    assert len(ready) == 11
    entry = next(
        item for item in library["hypotheses"]
        if item["library_entry_id"] == "opening-drive-first-pullback-v001"
    )
    selected = config["selected_hypothesis"]
    assert selected["registration_identity"] == entry["registration_identity"]
    assert selected["framework_hypothesis_identity"] == entry[
        "framework_hypothesis_identity"
    ]
    assert selected["revision"] == entry["revision"] == 1
    assert selected["directional_arm"] == "long"
    assert "long" in entry["directional_scope"]


def test_selection_uses_no_outcomes_and_documents_all_alternatives() -> None:
    config = _config()
    assert config["selection_policy"]["outcome_information_permitted"] is False
    assert config["selection_policy"]["performance_ranking_permitted"] is False
    for item in config["selection_review"]:
        assert item["reason"]
        assert item["semantic_fit"]
        assert item["reused_capability_count"] >= 0
        assert len(item["new_assumption_codes"]) == len(
            set(item["new_assumption_codes"])
        )
    selected = next(item for item in config["selection_review"] if item["selected"])
    assert selected["semantic_fit"] == "exact_existing_contract_analogue"
    assert selected["new_assumption_codes"] == []


def test_specification_covers_every_required_semantic_domain() -> None:
    specification = _config()["specification"]
    required = {
        "market_assumption",
        "economic_mechanism",
        "bar_and_session",
        "data_dependencies",
        "numeric_semantics",
        "indicators",
        "eligibility",
        "setup",
        "entry",
        "stop_target_and_lifecycle",
        "event_ordering",
        "rule_precedence",
        "tie_breaking",
        "missing_data_behavior",
        "integrity_expectations",
        "decision_states",
        "invalidation_conditions",
        "expected_failure_modes",
        "implementation_boundary",
    }
    assert required.issubset(specification)
    assert specification["bar_and_session"]["bar_semantics"] == (
        "left-labeled complete interval [t,t+1 minute)"
    )
    assert specification["event_ordering"]
    assert specification["rule_precedence"][0] == "integrity_failure"
    assert specification["numeric_semantics"]["comparison_tolerance"] == (
        "none; apply the stated strict or inclusive operator directly"
    )
    assert set(specification["decision_states"]) == {
        "integrity_failure",
        "no_signal",
        "no_trade",
        "proposal",
        "unavailable",
    }


def test_exact_boundaries_indicators_entry_stop_target_and_ties_are_frozen() -> None:
    specification = _config()["specification"]
    eligibility = specification["eligibility"]
    assert eligibility["impulse_return_minimum_inclusive"] == 0.03
    assert eligibility["impulse_volume_ratio_minimum_inclusive"] == 2.0
    assert eligibility["pullback_depth_minimum_inclusive"] == 0.20
    assert eligibility["pullback_depth_maximum_inclusive"] == 0.50
    assert eligibility["pullback_duration_bars_minimum_inclusive"] == 2
    assert eligibility["pullback_duration_bars_maximum_inclusive"] == 10
    assert specification["entry"]["allowed_delay_bars"] == 0
    lifecycle = specification["stop_target_and_lifecycle"]
    assert lifecycle["maximum_holding_complete_bars"] == 90
    assert "0.05 times ATR20" in lifecycle["unrounded_stop"]
    assert "2 times initial per-share risk" in lifecycle["target"]
    assert "floor(risk_budget_usd" in lifecycle["shared_risk_model"][
        "requested_shares"
    ]
    assert specification["tie_breaking"] == FROZEN_SPECIFICATION["tie_breaking"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["specification"]["eligibility"].__setitem__("impulse_return_minimum_inclusive", 0.02), "specification changed"),
        (lambda value: value["selected_hypothesis"].__setitem__("directional_arm", "short"), "selected hypothesis binding changed"),
        (lambda value: value["selection_review"][0].__setitem__("selected", True), "selection review changed"),
        (lambda value: value["policy"].__setitem__("implementation_count", 1), "campaign policy changed"),
        (lambda value: value["selection_policy"].__setitem__("outcome_information_permitted", True), "selection policy changed"),
    ],
)
def test_semantic_substitution_fails_even_if_all_identities_are_recomputed(
    mutation, message: str,
) -> None:
    value = copy.deepcopy(_config())
    mutation(value)
    value["selection_identity"] = selection_identity(value["selection_review"])
    value["specification_identity"] = specification_identity(value["specification"])
    value["campaign_identity"] = campaign_identity(value)
    with pytest.raises(BenchmarkSpecificationCampaignError, match=message):
        _validate(value)


def test_source_and_dependency_substitution_fail_closed(tmp_path: Path) -> None:
    value = copy.deepcopy(_config())
    value["dependencies"]["hypothesis_library"]["sha256"] = "0" * 64
    value["campaign_identity"] = campaign_identity(value)
    with pytest.raises(BenchmarkSpecificationCampaignError, match="dependency hash"):
        _validate(value)
    value = copy.deepcopy(_config())
    source_path = next(iter(value["campaign_source_sha256"]))
    value["campaign_source_sha256"][source_path] = "0" * 64
    value["campaign_identity"] = campaign_identity(value)
    with pytest.raises(BenchmarkSpecificationCampaignError, match="source hash"):
        _validate(value)
    malformed = tmp_path / "duplicate.json"
    malformed.write_text('{"x":1,"x":2}', encoding="utf-8")
    with pytest.raises(BenchmarkSpecificationCampaignError, match="duplicate keys"):
        from aml.benchmark_specification_campaign_v001 import _strict_json

        _strict_json(malformed)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("campaign_id", "benchmark-specification-campaign-v999", "campaign_id changed"),
        ("source_commit", "0" * 40, "source_commit changed"),
        ("created_at", "2026-08-04T18:00:00+00:00", "canonical UTC"),
    ],
)
def test_campaign_lineage_and_canonical_timestamp_cannot_be_substituted(
    field: str, replacement: str, message: str
) -> None:
    value = copy.deepcopy(_config())
    value[field] = replacement
    value["campaign_identity"] = campaign_identity(value)
    with pytest.raises(BenchmarkSpecificationCampaignError, match=message):
        _validate(value)


def test_committed_artifacts_verify_and_reproduce_byte_for_byte(tmp_path: Path) -> None:
    committed = verify_campaign(
        output_root=EVIDENCE,
        config_path=CONFIG,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )
    generated = tmp_path / "campaign"
    reproduced = publish_campaign(
        output_root=generated,
        config_path=CONFIG,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )
    assert committed == reproduced
    committed_files = sorted(path.name for path in EVIDENCE.iterdir())
    assert committed_files == sorted(path.name for path in generated.iterdir())
    for name in committed_files:
        assert (EVIDENCE / name).read_bytes() == (generated / name).read_bytes()


def test_publication_is_write_once_and_protected_paths_are_rejected(tmp_path: Path) -> None:
    output = tmp_path / "campaign"
    publish_campaign(
        output_root=output,
        config_path=CONFIG,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )
    with pytest.raises(BenchmarkSpecificationCampaignError, match="already exists"):
        publish_campaign(
            output_root=output,
            config_path=CONFIG,
            library_path=LIBRARY,
            readiness_path=READINESS,
            repository_root=ROOT,
        )
    with pytest.raises(BenchmarkSpecificationCampaignError, match="protected boundary"):
        publish_campaign(
            output_root=tmp_path / "holdout" / "campaign",
            config_path=CONFIG,
            library_path=LIBRARY,
            readiness_path=READINESS,
            repository_root=ROOT,
        )


def test_tampered_or_extra_artifacts_are_rejected(tmp_path: Path) -> None:
    output = tmp_path / "campaign"
    publish_campaign(
        output_root=output,
        config_path=CONFIG,
        library_path=LIBRARY,
        readiness_path=READINESS,
        repository_root=ROOT,
    )
    (output / "specification.json").write_bytes(
        (output / "specification.json").read_bytes() + b" "
    )
    with pytest.raises(BenchmarkSpecificationCampaignError, match="artifact changed"):
        verify_campaign(
            output_root=output,
            config_path=CONFIG,
            library_path=LIBRARY,
            readiness_path=READINESS,
            repository_root=ROOT,
        )
    (output / "specification.json").write_bytes(
        (EVIDENCE / "specification.json").read_bytes()
    )
    (output / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(BenchmarkSpecificationCampaignError, match="file set"):
        verify_campaign(
            output_root=output,
            config_path=CONFIG,
            library_path=LIBRARY,
            readiness_path=READINESS,
            repository_root=ROOT,
        )


def test_cli_is_deterministic_across_hash_seed_and_timezone(tmp_path: Path) -> None:
    hashes: list[str] = []
    for index, (seed, timezone) in enumerate((("1", "UTC"), ("777", "Asia/Tokyo"))):
        output = tmp_path / f"run-{index}"
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONHASHSEED=seed, TZ=timezone)
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--repository-root",
                str(ROOT),
                "--output-root",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert json.loads(result.stdout)["verified"] is True
        digest = hashlib.sha256()
        for path in sorted(output.iterdir()):
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        hashes.append(digest.hexdigest())
    assert len(set(hashes)) == 1


def test_milestone_cannot_execute_or_authorize_a_strategy() -> None:
    config = _config()
    policy = config["policy"]
    boundary = config["specification"]["implementation_boundary"]
    assert policy["implementation_count"] == 0
    assert policy["strategy_execution_count"] == 0
    assert policy["empirical_outcome_access_count"] == 0
    assert policy["protected_boundary_access_count"] == 0
    assert boundary["implementation_authorized"] is False
    assert boundary["discovery_authorized"] is False
    assert boundary["dataset_authorized"] is False
    source = (ROOT / "src/aml/benchmark_specification_campaign_v001.py").read_text()
    assert "portfolio_simulator" not in source
    assert "def evaluate_" not in source
    assert "def execute" not in source
