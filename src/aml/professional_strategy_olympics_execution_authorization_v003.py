"""Prospective lineage-bound, single-use Olympics authorization adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    FIXTURE_IDENTITY,
    MANIFEST_IDENTITY,
    load_canonical_manifest,
)
from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY as V003_CONTRACT_IDENTITY,
    V002_ADAPTER_IMPLEMENTATION_IDENTITY,
    V002_CONTRACT_IDENTITY,
    V003_ADAPTER_CONTRACT_IDENTITY,
    strict_json,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    adapt_manifest,
    adapter_implementation_identity as v003_adapter_implementation_identity,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    AUTHORIZATION_SCHEMA as V001_AUTHORIZATION_SCHEMA,
    ORCHESTRATOR_IDENTITY,
    _run_identity as v001_run_identity,
    implementation_identity as v001_implementation_identity,
    validate_authorization as validate_v001_authorization,
)
from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY as V004_IDENTITY,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


CONTRACT_PATH = "config/professional_strategy_olympics_execution_authorization_v003.json"
MODULE_PATH = "src/aml/professional_strategy_olympics_execution_authorization_v003.py"
CONTRACT_IDENTITY = "6ebc042a7205ef7fe51262bdf51d6d2088c12f9977708c8c822027c8407858de"
ADAPTER_CONTRACT_IDENTITY = "aed4de197ba09ac87fe41af52e299ca9f7319c613ef5182a2f442009a1013816"
SCHEMA = "aml.professional-strategy-olympics.lineage-bound-synthetic-trial-authorization.v003"
SOURCE_COMMIT = "bfc06262e48cbcb5611f205f5aea2b4d7ac34493"
PERMITTED_OPERATION = "execute_inaugural_canonical_synthetic_olympics_once"
PROHIBITIONS = frozenset({
    "historical", "live", "validation", "holdout", "extension", "forward",
    "provider", "broker", "production", "network",
})
AUTHORIZATION_FIELDS = frozenset({
    "schema_version", "authorization_identity", "trial_authorized", "trial_kind",
    "permitted_operation", "maximum_execution_count", "merged_source_commit",
    "v001_orchestrator_identity", "v001_implementation_identity",
    "v002_contract_identity", "v002_adapter_identity", "v003_contract_identity",
    "v003_adapter_contract_identity", "v003_adapter_implementation_identity",
    "v003_execution_adapter_contract_identity",
    "v003_execution_adapter_implementation_identity", "v004_scoring_identity",
    "canonical_fixture_identity", "canonical_manifest_identity",
    "projected_v001_manifest_identity", "projected_v001_run_identity",
    "lineage_run_identity", "human_approval_reference", "access_prohibitions",
})


class OlympicsExecutionAuthorizationV003Error(ValueError):
    """The authorization lineage, projection, or consumption invariant failed."""


def implementation_identity(root: Path) -> str:
    return canonical_hash({
        "contract_identity": CONTRACT_IDENTITY,
        "adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "module_sha256": hashlib.sha256((root / MODULE_PATH).read_bytes()).hexdigest(),
    })


def load_contract(root: Path) -> dict[str, object]:
    value = strict_json(root / CONTRACT_PATH)
    identity = value.get("contract_identity")
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsExecutionAuthorizationV003Error("contract identity is invalid")
    if canonical_hash({k: v for k, v in value.items() if k != "contract_identity"}) != identity:
        raise OlympicsExecutionAuthorizationV003Error("contract identity changed")
    if identity != CONTRACT_IDENTITY or value.get("adapter_contract_identity") != ADAPTER_CONTRACT_IDENTITY:
        raise OlympicsExecutionAuthorizationV003Error("frozen contract binding changed")
    if any(value.get(flag) is not False for flag in (
        "authorization_creation_permitted", "trial_execution_permitted",
        "publication_permitted",
    )):
        raise OlympicsExecutionAuthorizationV003Error("prospective boundary changed")
    return value


def projected_identities(root: Path) -> tuple[str, str]:
    manifest = load_canonical_manifest(root)
    projected = adapt_manifest(manifest, root).v001_manifest
    input_identity = projected["manifest_identity"]
    return input_identity, v001_run_identity(
        input_identity, v001_implementation_identity(root)
    )


def lineage_run_identity(root: Path) -> str:
    input_identity, inner_run = projected_identities(root)
    return canonical_hash({
        "merged_source_commit": SOURCE_COMMIT,
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": v001_implementation_identity(root),
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_contract_identity": V003_CONTRACT_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v003_adapter_implementation_identity": v003_adapter_implementation_identity(root),
        "v003_execution_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "v003_execution_adapter_implementation_identity": implementation_identity(root),
        "v004_scoring_identity": V004_IDENTITY,
        "canonical_fixture_identity": FIXTURE_IDENTITY,
        "canonical_manifest_identity": MANIFEST_IDENTITY,
        "projected_v001_manifest_identity": input_identity,
        "projected_v001_run_identity": inner_run,
        "permitted_operation": PERMITTED_OPERATION,
        "maximum_execution_count": 1,
    })


def validate_authorization(value: Mapping[str, object], root: Path) -> dict[str, object]:
    load_contract(root)
    if set(value) != AUTHORIZATION_FIELDS or value.get("schema_version") != SCHEMA:
        raise OlympicsExecutionAuthorizationV003Error("authorization schema is invalid")
    identity = value.get("authorization_identity")
    if not isinstance(identity, str) or canonical_hash(
        {k: v for k, v in value.items() if k != "authorization_identity"}
    ) != identity:
        raise OlympicsExecutionAuthorizationV003Error("authorization identity is invalid")
    input_identity, inner_run = projected_identities(root)
    required = {
        "trial_authorized": True, "trial_kind": "synthetic",
        "permitted_operation": PERMITTED_OPERATION, "maximum_execution_count": 1,
        "merged_source_commit": SOURCE_COMMIT,
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": v001_implementation_identity(root),
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_contract_identity": V003_CONTRACT_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v003_adapter_implementation_identity": v003_adapter_implementation_identity(root),
        "v003_execution_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "v003_execution_adapter_implementation_identity": implementation_identity(root),
        "v004_scoring_identity": V004_IDENTITY,
        "canonical_fixture_identity": FIXTURE_IDENTITY,
        "canonical_manifest_identity": MANIFEST_IDENTITY,
        "projected_v001_manifest_identity": input_identity,
        "projected_v001_run_identity": inner_run,
        "lineage_run_identity": lineage_run_identity(root),
        "access_prohibitions": {key: True for key in sorted(PROHIBITIONS)},
    }
    if any(value.get(field) != expected for field, expected in required.items()):
        raise OlympicsExecutionAuthorizationV003Error("authorization binding is invalid")
    if not isinstance(value.get("human_approval_reference"), str) or not value["human_approval_reference"]:
        raise OlympicsExecutionAuthorizationV003Error("human approval reference is required")
    return dict(value)


def project_v001_authorization(value: Mapping[str, object], root: Path) -> dict[str, object]:
    validated = validate_authorization(value, root)
    input_identity, inner_run = projected_identities(root)
    projected = {
        "schema_version": V001_AUTHORIZATION_SCHEMA,
        "trial_authorized": True, "trial_kind": "synthetic",
        "orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "orchestrator_implementation_identity": v001_implementation_identity(root),
        "scoring_bundle_identity": V004_IDENTITY,
        "input_manifest_identity": input_identity, "run_identity": inner_run,
        "human_approval_reference": validated["human_approval_reference"],
    }
    projected["authorization_identity"] = canonical_hash(projected)
    validate_v001_authorization(
        projected, execute_requested=True, input_identity=input_identity,
        implementation=v001_implementation_identity(root),
    )
    return projected


def consume_once(
    value: Mapping[str, object], root: Path, consumption_root: Path
) -> bytes:
    """Atomically consume before any future artifact generation can begin."""
    validated = validate_authorization(value, root)
    identity = validated["authorization_identity"]
    destination = consumption_root / identity
    try:
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise OlympicsExecutionAuthorizationV003Error("authorization already consumed") from exc
    evidence = canonical_json({
        "authorization_identity": identity,
        "consumed": True,
        "execution_count": 1,
        "lineage_run_identity": validated["lineage_run_identity"],
        "maximum_execution_count": 1,
        "state": "consumed_before_artifact_generation",
    })
    (destination / "consumption.json").write_bytes(evidence)
    return evidence
