from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    FIXTURE_IDENTITY,
    MANIFEST_IDENTITY,
)
from aml.professional_strategy_olympics_execution_authorization_v003 import (
    ADAPTER_CONTRACT_IDENTITY as V003_EXECUTION_CONTRACT_IDENTITY,
    CONTRACT_IDENTITY as V003_AUTHORIZATION_CONTRACT_IDENTITY,
    implementation_identity as v003_execution_identity,
    projected_identities,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    AUTHORIZATION_SCHEMA,
    CONTRACT_IDENTITY,
    OUTER_ARTIFACT_NAMES,
    PERMITTED_OPERATION,
    PROHIBITIONS,
    OlympicsExecutionPublicationV004Error,
    consume_and_build,
    implementation_identity,
    lineage_run_identity,
    load_contract,
    publish_once,
    repository_commit,
    validate_authorization,
)
from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ORCHESTRATOR_IDENTITY,
    implementation_identity as v001_identity,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).parents[1]


def authorization() -> dict[str, object]:
    input_identity, inner_run = projected_identities(ROOT)
    value = {
        "schema_version": AUTHORIZATION_SCHEMA,
        "trial_authorized": True,
        "trial_kind": "synthetic",
        "permitted_operation": PERMITTED_OPERATION,
        "maximum_execution_count": 1,
        "merged_source_commit": repository_commit(ROOT),
        "v003_authorization_contract_identity": V003_AUTHORIZATION_CONTRACT_IDENTITY,
        "v003_execution_contract_identity": V003_EXECUTION_CONTRACT_IDENTITY,
        "v003_execution_implementation_identity": v003_execution_identity(ROOT),
        "v004_execution_publication_contract_identity": CONTRACT_IDENTITY,
        "v004_execution_publication_implementation_identity": implementation_identity(ROOT),
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": v001_identity(ROOT),
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


def test_contract_is_prospective_and_v003_remains_unchanged() -> None:
    contract = load_contract(ROOT)
    assert contract["authorization_creation_permitted"] is False
    assert contract["execution_without_external_authorization_permitted"] is False
    assert contract["publication_without_external_authorization_permitted"] is False
    assert contract["write_once_publication"] is True
    assert v003_execution_identity(ROOT) == (
        "3265cf0d35cc63317248edc9b368169f4a1950c32bb955447b6a7e6651173d14"
    )


def test_authorization_binds_execution_and_publication_implementation() -> None:
    value = validate_authorization(authorization(), ROOT)
    assert value["v004_execution_publication_contract_identity"] == CONTRACT_IDENTITY
    assert value["v004_execution_publication_implementation_identity"] == implementation_identity(ROOT)
    assert value["lineage_run_identity"] == lineage_run_identity(ROOT)


@pytest.mark.parametrize(
    "field",
    [
        "merged_source_commit",
        "v003_execution_implementation_identity",
        "v004_execution_publication_contract_identity",
        "v004_execution_publication_implementation_identity",
        "canonical_manifest_identity",
        "projected_v001_run_identity",
        "lineage_run_identity",
    ],
)
def test_modified_lineage_fails_closed(field: str) -> None:
    value = authorization()
    value[field] = "f" * len(str(value[field]))
    with pytest.raises(OlympicsExecutionPublicationV004Error, match="binding"):
        validate_authorization(reidentify(value), ROOT)


def test_test_only_pipeline_is_deterministic_and_consumes_before_build(tmp_path: Path) -> None:
    value = authorization()
    first = consume_and_build(value, ROOT, tmp_path / "claims-a")
    second = consume_and_build(value, ROOT, tmp_path / "claims-b")
    assert first == second
    assert tuple(first) == OUTER_ARTIFACT_NAMES
    consumption = json.loads(first["consumption.json"])
    lineage = json.loads(first["lineage_run_manifest.json"])
    assert consumption["state"] == "consumed_before_artifact_generation"
    assert lineage["authoritative_run_identity"] == value["lineage_run_identity"]
    assert lineage["classification"] == "canonical_synthetic_non_performance_non_economic"
    with pytest.raises(OlympicsExecutionPublicationV004Error, match="already consumed"):
        consume_and_build(value, ROOT, tmp_path / "claims-a")


def test_write_once_publication_rejects_even_identical_reuse(tmp_path: Path) -> None:
    value = authorization()
    artifacts = consume_and_build(value, ROOT, tmp_path / "claims")
    destination = publish_once(tmp_path / "published", value, ROOT, artifacts)
    assert sorted(path.name for path in destination.iterdir()) == sorted(OUTER_ARTIFACT_NAMES)
    with pytest.raises(OlympicsExecutionPublicationV004Error, match="collision"):
        publish_once(tmp_path / "published", value, ROOT, artifacts)


def test_tampered_bundle_cannot_be_published(tmp_path: Path) -> None:
    value = authorization()
    artifacts = consume_and_build(value, ROOT, tmp_path / "claims")
    artifacts["ranking_ledger.json"] += b"\n"
    with pytest.raises(OlympicsExecutionPublicationV004Error, match="index reconciliation"):
        publish_once(tmp_path / "published", value, ROOT, artifacts)


def test_bundle_is_hash_seed_and_timezone_independent() -> None:
    code = (
        "import hashlib,tempfile; from pathlib import Path; "
        "from test_professional_strategy_olympics_execution_publication_v004 "
        "import ROOT,authorization; "
        "from aml.professional_strategy_olympics_execution_publication_v004 "
        "import consume_and_build; "
        "from aml.winner_archetype_contracts import canonical_hash; "
        "a=consume_and_build(authorization(),ROOT,Path(tempfile.mkdtemp())); "
        "print(canonical_hash({k:hashlib.sha256(v).hexdigest() for k,v in a.items()}))"
    )
    outputs = []
    for seed, timezone in (("1", "UTC"), ("77", "America/Denver"), ("9", "Asia/Tokyo")):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'tests'}",
        }
        outputs.append(subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
        ).stdout)
    assert len(set(outputs)) == 1


def test_no_official_authorization_or_trial_artifact_is_committed() -> None:
    assert not tuple(ROOT.glob("config/*official*authorization*.json"))
    assert not tuple(ROOT.glob("config/*inaugural*authorization*.json"))
    assert not (ROOT / "artifacts/professional_strategy_olympics").exists()
