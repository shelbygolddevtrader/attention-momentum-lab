from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from aml.professional_strategy_olympics_execution_authorization_v003 import (
    ADAPTER_CONTRACT_IDENTITY,
    CONTRACT_IDENTITY,
    PERMITTED_OPERATION,
    PROHIBITIONS,
    SCHEMA,
    SOURCE_COMMIT,
    OlympicsExecutionAuthorizationV003Error,
    consume_once,
    implementation_identity,
    lineage_run_identity,
    load_contract,
    project_v001_authorization,
    projected_identities,
    validate_authorization,
)
from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY as V003_CONTRACT_IDENTITY,
    V002_ADAPTER_IMPLEMENTATION_IDENTITY,
    V002_CONTRACT_IDENTITY,
    V003_ADAPTER_CONTRACT_IDENTITY,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    adapter_implementation_identity as v003_adapter_identity,
)
from aml.professional_strategy_olympics_orchestrator_v001 import ORCHESTRATOR_IDENTITY
from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    FIXTURE_IDENTITY,
    MANIFEST_IDENTITY,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).parents[1]


def authorization() -> dict[str, object]:
    input_identity, inner_run = projected_identities(ROOT)
    value = {
        "schema_version": SCHEMA,
        "trial_authorized": True,
        "trial_kind": "synthetic",
        "permitted_operation": PERMITTED_OPERATION,
        "maximum_execution_count": 1,
        "merged_source_commit": SOURCE_COMMIT,
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": load_contract(ROOT)["frozen_bindings"]["v001_implementation_identity"],
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_contract_identity": V003_CONTRACT_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v003_adapter_implementation_identity": v003_adapter_identity(ROOT),
        "v003_execution_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "v003_execution_adapter_implementation_identity": implementation_identity(ROOT),
        "v004_scoring_identity": BUNDLE_IDENTITY,
        "canonical_fixture_identity": FIXTURE_IDENTITY,
        "canonical_manifest_identity": MANIFEST_IDENTITY,
        "projected_v001_manifest_identity": input_identity,
        "projected_v001_run_identity": inner_run,
        "lineage_run_identity": lineage_run_identity(ROOT),
        "human_approval_reference": "test-only-not-official-authorization",
        "access_prohibitions": {key: True for key in sorted(PROHIBITIONS)},
    }
    value["authorization_identity"] = canonical_hash(value)
    return value


def reidentify(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    result["authorization_identity"] = canonical_hash({
        key: item for key, item in result.items() if key != "authorization_identity"
    })
    return result


def test_contract_is_prospective_and_creates_no_authorization() -> None:
    contract = load_contract(ROOT)
    assert contract["contract_identity"] == CONTRACT_IDENTITY
    assert contract["adapter_contract_identity"] == ADAPTER_CONTRACT_IDENTITY
    assert contract["authorization_creation_permitted"] is False
    assert contract["trial_execution_permitted"] is False
    assert contract["publication_permitted"] is False


def test_authorization_binds_lineage_and_projects_exactly_into_v001() -> None:
    value = validate_authorization(authorization(), ROOT)
    projected = project_v001_authorization(value, ROOT)
    assert value["merged_source_commit"] == SOURCE_COMMIT
    assert value["canonical_manifest_identity"] == MANIFEST_IDENTITY
    assert value["canonical_fixture_identity"] == FIXTURE_IDENTITY
    assert value["maximum_execution_count"] == 1
    assert projected["input_manifest_identity"] == value["projected_v001_manifest_identity"]
    assert projected["run_identity"] == value["projected_v001_run_identity"]


@pytest.mark.parametrize(
    "field",
    [
        "merged_source_commit", "v001_orchestrator_identity",
        "v001_implementation_identity", "v002_contract_identity",
        "v002_adapter_identity", "v003_contract_identity",
        "v003_adapter_contract_identity", "v003_adapter_implementation_identity",
        "v003_execution_adapter_contract_identity",
        "v003_execution_adapter_implementation_identity", "v004_scoring_identity",
        "canonical_fixture_identity", "canonical_manifest_identity",
        "projected_v001_manifest_identity", "projected_v001_run_identity",
        "lineage_run_identity",
    ],
)
def test_modified_identity_or_source_fails_closed(field: str) -> None:
    value = authorization()
    value[field] = "f" * len(str(value[field]))
    with pytest.raises(OlympicsExecutionAuthorizationV003Error, match="binding"):
        validate_authorization(reidentify(value), ROOT)


def test_wrong_operation_count_and_access_flags_fail_closed() -> None:
    operation = authorization()
    operation["permitted_operation"] = "execute_twice"
    count = authorization()
    count["maximum_execution_count"] = 2
    access = authorization()
    access["access_prohibitions"]["network"] = False
    for value in (operation, count, access):
        with pytest.raises(OlympicsExecutionAuthorizationV003Error, match="binding"):
            validate_authorization(reidentify(value), ROOT)


def test_atomic_consumption_rejects_reuse_before_future_generation(tmp_path: Path) -> None:
    value = authorization()
    evidence = json.loads(consume_once(value, ROOT, tmp_path))
    assert evidence["consumed"] is True
    assert evidence["execution_count"] == 1
    assert evidence["state"] == "consumed_before_artifact_generation"
    with pytest.raises(OlympicsExecutionAuthorizationV003Error, match="already consumed"):
        consume_once(value, ROOT, tmp_path)
    assert len(tuple(tmp_path.iterdir())) == 1


def test_missing_extra_stale_and_empty_approval_fail_closed() -> None:
    missing = authorization()
    missing.pop("v002_contract_identity")
    extra = authorization()
    extra["extra"] = False
    stale = authorization()
    stale["canonical_manifest_identity"] = "f" * 64
    empty = authorization()
    empty["human_approval_reference"] = ""
    empty = reidentify(empty)
    for value in (missing, extra, stale, empty):
        with pytest.raises(OlympicsExecutionAuthorizationV003Error):
            validate_authorization(value, ROOT)


def test_no_official_authorization_or_execution_surface_exists() -> None:
    assert not (ROOT / "config/professional_strategy_olympics_inaugural_trial_authorization_v001.json").exists()
    import aml.professional_strategy_olympics_execution_authorization_v003 as module
    assert not ({"execute", "run_trial", "publish_artifacts", "create_authorization"} & set(dir(module)))
