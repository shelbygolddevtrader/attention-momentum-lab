from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.provider_capability_v002 import (
    CapabilityContractError,
    build_capability_contract,
    canonical_contract_files,
    minimum_compliant_source_sets,
    validate_contract_and_matrix,
)
from aml.winner_archetype_v002 import load_protocol_v002, load_source_requirements_v002


ROOT = Path(__file__).parents[1]
PROTOCOL_PATH = ROOT / "config/winner_archetype_protocol_v002.json"
SOURCE_PATH = ROOT / "config/winner_archetype_source_requirements_v002.json"
CONTRACT_PATH = ROOT / "config/winner_archetype_provider_capability_contract_v002.json"
MATRIX_PATH = ROOT / "config/winner_archetype_provider_decision_matrix_v002.json"
CLI = ROOT / "scripts/build_provider_capability_package_v002.py"
PROTOCOL = load_protocol_v002(PROTOCOL_PATH)
SOURCE_MATRIX = load_source_requirements_v002(SOURCE_PATH)


def tracked():
    return json.loads(CONTRACT_PATH.read_text()), json.loads(MATRIX_PATH.read_text())


def test_tracked_contract_and_matrix_are_canonical_complete_and_identity_bound():
    contract, matrix = tracked()
    expected_contract, expected_matrix = canonical_contract_files(PROTOCOL_PATH, SOURCE_PATH)
    assert CONTRACT_PATH.read_bytes() == expected_contract
    assert MATRIX_PATH.read_bytes() == expected_matrix
    validate_contract_and_matrix(contract, matrix, PROTOCOL, SOURCE_MATRIX)
    assert contract["contract_identity"] == (
        "4a73a61d56e2b8085b02d2afdf3ffbaf45af0a54a2549b7d30e4a4eaf01afe83"
    )
    assert matrix["matrix_identity"] == (
        "8d44c588be7c0501d746a2b476ea6ca42157feae1854db7bd9e1024b7bf4a1db"
    )


def test_all_thirteen_families_define_every_required_contract_dimension():
    contract = build_capability_contract(PROTOCOL, SOURCE_MATRIX)
    required_dimensions = {
        "required_fields", "timestamp_semantics", "timezone", "coverage_interval",
        "point_in_time_requirement", "sequence_requirement",
        "correction_cancellation_lineage", "negative_coverage_requirement",
        "provider_and_feed_identity", "entitlement_evidence",
        "archive_and_retention_terms", "redistribution_and_research_use_rights",
        "raw_payload_availability", "manifest_requirements", "hashing_requirements",
        "completeness_criteria", "conflict_resolution_rules",
        "acceptable_evidence_types", "failure_conditions",
    }
    assert len(contract["requirements"]) == 13
    assert {item["dataset"] for item in contract["requirements"]} == {
        item.dataset for item in SOURCE_MATRIX.requirements
    }
    assert all(required_dimensions <= set(item) for item in contract["requirements"])


def test_marketing_and_public_documentation_never_receive_readiness_credit():
    contract, matrix = tracked()
    assert contract["evidence_policy"]["provider_claim"] == "never_sufficient"
    assert contract["evidence_policy"]["public_documentation"].startswith("never_sufficient")
    cells = [cell for provider in matrix["providers"] for cell in provider["capabilities"]]
    assert len(cells) == 65
    assert {cell["status"] for cell in cells} <= {"claimed", "unknown"}
    assert not any(cell["readiness_credit"] for cell in cells)
    assert matrix["minimum_compliant_source_sets"] == []
    assert matrix["pilot_authorized"] is False


def test_pricing_and_storage_are_explicitly_non_evidentiary_planning_fields():
    _, matrix = tracked()
    estimates = matrix["planning_estimates"]
    assert estimates["status"] == "planning_assumptions_not_quotes_or_readiness_evidence"
    assert estimates["full_market_sip_compressed_bytes_low"] == 1_500_000_000_000
    assert estimates["working_storage_bytes_high"] == 6_000_000_000_000
    assert all(provider["pricing"]["verified_for_contract"] is False for provider in matrix["providers"])


def test_tampered_contract_matrix_or_readiness_credit_fails_closed():
    contract, matrix = tracked()
    changed_contract = deepcopy(contract)
    changed_contract["requirements"][0]["required_fields"].pop()
    with pytest.raises(CapabilityContractError, match="contract"):
        validate_contract_and_matrix(changed_contract, matrix, PROTOCOL, SOURCE_MATRIX)
    changed_matrix = deepcopy(matrix)
    changed_matrix["providers"][0]["capabilities"][0]["readiness_credit"] = True
    with pytest.raises(CapabilityContractError, match="matrix"):
        validate_contract_and_matrix(contract, changed_matrix, PROTOCOL, SOURCE_MATRIX)


def test_minimum_compliant_source_set_requires_every_written_schema_license_and_coverage_gate():
    contract, matrix = tracked()
    complete = deepcopy(matrix)
    required = {item["dataset"]: item for item in contract["requirements"]}
    provider = complete["providers"][0]
    for cell in provider["capabilities"]:
        requirement = required[cell["dataset"]]
        evidence = set(requirement["minimum_capability_evidence"])
        evidence.update(requirement["minimum_entitlement_evidence"])
        evidence.update(requirement["minimum_readiness_evidence"])
        cell.update(
            status="proven",
            evidence_levels=sorted(evidence),
            highest_evidence_level="empirical_completeness_evidence",
            readiness_credit=True,
        )
    assert minimum_compliant_source_sets(contract, complete) == [["alpaca"]]
    provider["capabilities"][0]["evidence_levels"].remove("written_provider_confirmation")
    with pytest.raises(CapabilityContractError, match="Readiness credit"):
        minimum_compliant_source_sets(contract, complete)


@pytest.mark.parametrize("artifact", ("contract", "matrix"))
def test_cli_is_hashseed_and_timezone_deterministic(artifact, tmp_path):
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "America/New_York")):
        environment = os.environ.copy()
        environment.update(PYTHONHASHSEED=seed, TZ=timezone, PYTHONPATH=str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, str(CLI), "--artifact", artifact],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
