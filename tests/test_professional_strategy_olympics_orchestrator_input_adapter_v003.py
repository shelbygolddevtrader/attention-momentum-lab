from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_input_manifest_v002 import (
    V001_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY,
    V002_ADAPTER_IMPLEMENTATION_IDENTITY,
    V002_CONTRACT_IDENTITY,
    manifest_identity,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    OlympicsOrchestratorInputAdapterV003Error,
    adapt_manifest,
    adapter_implementation_identity,
    future_run_identity,
    validation_only,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ORCHESTRATOR_IDENTITY,
    validate_input_manifest,
)
from aml.winner_archetype_contracts import canonical_hash

from olympics_v003_test_support import ROOT, make_v003_manifest


def test_adapter_accepts_v003_and_projects_through_unchanged_v001() -> None:
    adapted = adapt_manifest(make_v003_manifest(), ROOT)
    validated = validate_input_manifest(adapted.v001_manifest)
    assert len(validated["entrants"]) == 10
    assert validated["entrants"][0]["trades"][0]["quantity"] == 100
    assert adapted.status_ledger[0]["status"] == "active"


@pytest.mark.parametrize(
    "schema",
    [
        "aml.professional-strategy-olympics.synthetic-input-manifest.v001",
        "aml.professional-strategy-olympics.synthetic-input-manifest.v002",
    ],
)
def test_adapter_rejects_prior_manifest_schemas(schema: str) -> None:
    value = make_v003_manifest()
    value["schema_name"] = schema
    with pytest.raises(OlympicsOrchestratorInputAdapterV003Error, match="rejects"):
        adapt_manifest(value, ROOT)


def test_validation_only_is_exact_non_authorizing_and_writes_nothing(tmp_path: Path) -> None:
    before = tuple(tmp_path.iterdir())
    first = validation_only(make_v003_manifest(), ROOT)
    second = validation_only(make_v003_manifest(), ROOT)
    assert first == second
    report = json.loads(first)
    assert report["status"] == "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
    assert report["v002_contract_identity"] == V002_CONTRACT_IDENTITY
    assert report["v003_contract_identity"] == CONTRACT_IDENTITY
    assert report["trial_authorized"] is False
    assert report["trial_executed"] is False
    assert report["authorization_created"] is False
    assert report["artifact_published"] is False
    assert report["ranking_exists"] is False
    assert report["aggregate_score_exists"] is False
    assert report["performance_result_exists"] is False
    assert tuple(tmp_path.iterdir()) == before


def test_future_run_identity_directly_binds_v002_contract_identity() -> None:
    value = make_v003_manifest()
    implementation = adapter_implementation_identity(ROOT)
    expected_payload = {
        "source_commit_identity": value["source_commit_identity"],
        "v001_orchestrator_contract_identity": ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_contract_identity": CONTRACT_IDENTITY,
        "v003_adapter_implementation_identity": implementation,
        "v004_scoring_bundle_identity": BUNDLE_IDENTITY,
        "v003_manifest_identity": value["manifest_identity"],
    }
    identity = future_run_identity(value, ROOT)
    assert identity == canonical_hash(expected_payload)
    changed_payload = {**expected_payload, "v002_contract_identity": "f" * 64}
    assert canonical_hash(changed_payload) != identity

    invalid = deepcopy(value)
    invalid["v002_contract_identity"] = "f" * 64
    invalid["manifest_identity"] = manifest_identity(invalid)
    with pytest.raises(ValueError, match="v002_contract_identity"):
        future_run_identity(invalid, ROOT)


def test_adapter_has_no_execution_authorization_publication_or_network_surface() -> None:
    import aml.professional_strategy_olympics_orchestrator_input_adapter_v003 as module

    names = set(dir(module))
    assert not ({"execute", "authorize", "publish", "run_trial"} & names)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "import broker" not in source.lower()
