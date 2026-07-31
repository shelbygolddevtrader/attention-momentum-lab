from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    AUTHORIZATION_FIELDS,
    AUTHORIZATION_SCHEMA,
    COMMAND_IDENTITY,
    CONTRACT_IDENTITY,
    DESIGN_BASE_COMMIT,
    SCOPE,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    VALIDITY_SECONDS,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    OlympicsAuthorizationGovernanceV005Error,
    canonical_contract_bytes,
    load_contract,
    parse_canonical_timestamp,
    synthetic_validity_vector,
    validate_contract,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    CONTRACT_IDENTITY as ACTUAL_V004_CONTRACT_IDENTITY,
    implementation_identity as actual_v004_implementation_identity,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).parents[1]
CONTRACT_PATH = ROOT / "config/professional_strategy_olympics_authorization_governance_v005.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_authorization_governance_v005.py"


def raw_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def reidentify(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    result["contract_identity"] = canonical_hash({
        key: item for key, item in result.items() if key != "contract_identity"
    })
    return result


def test_committed_design_contract_and_identity_are_exact() -> None:
    contract = load_contract(ROOT)
    assert contract["contract_identity"] == CONTRACT_IDENTITY
    assert canonical_hash({
        key: item for key, item in contract.items() if key != "contract_identity"
    }) == CONTRACT_IDENTITY
    assert contract["authorization_schema"]["schema_version"] == AUTHORIZATION_SCHEMA
    assert tuple(contract["authorization_schema"]["required_fields"]) == AUTHORIZATION_FIELDS


def test_v004_and_immutable_tag_lineage_remain_exact() -> None:
    lineage = load_contract(ROOT)["historical_lineage"]
    assert lineage == {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_execution_publication_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_execution_publication_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
    }
    assert ACTUAL_V004_CONTRACT_IDENTITY == V004_CONTRACT_IDENTITY
    assert actual_v004_implementation_identity(ROOT) == V004_IMPLEMENTATION_IDENTITY


def test_command_identity_and_detached_source_policy_are_frozen() -> None:
    contract = load_contract(ROOT)
    command = dict(contract["execution_command"])
    assert command.pop("command_identity") == COMMAND_IDENTITY
    assert canonical_hash(command) == COMMAND_IDENTITY
    source = contract["execution_source_policy"]
    assert source["checkout_mode"] == "detached_HEAD"
    assert source["commit_rule"] == "HEAD_equals_authorized_source_commit"
    assert source["authorization_location"] == "outside_detached_source_root"
    assert source["working_tree_rule"] == "git_status_porcelain_v1_untracked_files_all_is_empty"


def test_canonical_timestamp_accepts_only_exact_utc_seconds() -> None:
    assert parse_canonical_timestamp("2030-01-02T03:04:05Z").isoformat() == (
        "2030-01-02T03:04:05+00:00"
    )
    for value in (
        "2030-01-02T03:04:05+00:00",
        "2030-01-01T22:04:05-05:00",
        "2030-01-02T03:04:05.000Z",
        "2030-01-02 03:04:05Z",
        "2030-01-02T03:04:60Z",
        "2030-02-30T03:04:05Z",
    ):
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            parse_canonical_timestamp(value)


def test_validity_is_exactly_72_hours_and_half_open() -> None:
    created = "2030-01-01T12:00:00Z"
    expiry = "2030-01-04T12:00:00Z"
    assert VALIDITY_SECONDS == 259_200
    assert synthetic_validity_vector(created, created, expiry, created) is True
    assert synthetic_validity_vector(created, created, expiry, "2030-01-04T11:59:59Z") is True
    assert synthetic_validity_vector(created, created, expiry, expiry) is False
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="equation"):
        synthetic_validity_vector(created, created, "2030-01-04T11:59:59Z", created)


@pytest.mark.parametrize(
    ("section", "field", "replacement", "message"),
    [
        ("authorization_schema", "unknown_fields", "allow", "strictness"),
        ("authorization_validity", "duration_seconds", 86_400, "validity"),
        ("authorization_validity", "creation_time_source", "local_clock", "issuance clock"),
        ("execution_source_policy", "checkout_mode", "branch", "detached source"),
        ("execution_source_policy", "commit_rule", "HEAD", "authorized source"),
        ("replay_prevention", "maximum_execution_count", 2, "single-use"),
        ("replay_prevention", "consumption_order", "build_then_claim", "consumption order"),
    ],
)
def test_governance_mutations_fail_closed(
    section: str, field: str, replacement: object, message: str
) -> None:
    changed = raw_contract()
    changed[section][field] = replacement
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match=message):
        validate_contract(reidentify(changed))


def test_command_or_lineage_mutation_fails_after_outer_reidentification() -> None:
    command = raw_contract()
    command["execution_command"]["argv_template"][0] = "python"
    lineage = raw_contract()
    lineage["historical_lineage"]["design_base_commit"] = "f" * 40
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="command identity"):
        validate_contract(reidentify(command))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="lineage"):
        validate_contract(reidentify(lineage))


def test_design_scope_has_no_authority_or_result_capability() -> None:
    contract = load_contract(ROOT)
    assert contract["scope"] == SCOPE
    assert all(value is False for value in SCOPE.values())
    assert contract["validation_manifest"] == {
        "authorization_artifact_present": False,
        "implementation_milestone": "required_after_design_merge",
        "status": "DESIGN_ONLY_V005_GOVERNANCE_FROZEN_AUTHORIZATION_NOT_CREATED",
        "trial_artifacts_present": False,
    }
    assert not (ROOT / "scripts/run_professional_strategy_olympics_v005.py").exists()
    assert not (ROOT / "governance/authorizations/professional_strategy_olympics").exists()
    assert not (ROOT / "artifacts/professional_strategy_olympics").exists()


def test_canonical_report_is_hashseed_timezone_and_locale_independent() -> None:
    expected = None
    for seed, timezone in (("1", "UTC"), ("77", "America/Denver"), ("9", "Asia/Tokyo")):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "LANG": "C",
            "LC_ALL": "C",
            "PYTHONPATH": str(ROOT / "src"),
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT)],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
        )
        expected = result.stdout if expected is None else expected
        assert result.stdout == expected
        assert result.stderr == b""


def test_contract_round_trip_is_canonical_and_deterministic() -> None:
    value = raw_contract()
    assert canonical_contract_bytes(value) == canonical_contract_bytes(
        dict(reversed(tuple(value.items())))
    )
