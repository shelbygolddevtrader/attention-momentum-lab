"""Prospective, lineage-bound, single-use Olympics execution publication."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping

from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    FIXTURE_IDENTITY,
    MANIFEST_IDENTITY,
    load_canonical_manifest,
)
from aml.professional_strategy_olympics_execution_authorization_v003 import (
    ADAPTER_CONTRACT_IDENTITY as V003_EXECUTION_CONTRACT_IDENTITY,
    CONTRACT_IDENTITY as V003_AUTHORIZATION_CONTRACT_IDENTITY,
    implementation_identity as v003_execution_implementation_identity,
    projected_identities,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import adapt_manifest
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ARTIFACT_NAMES as V001_ARTIFACT_NAMES,
    AUTHORIZATION_SCHEMA as V001_AUTHORIZATION_SCHEMA,
    ORCHESTRATOR_IDENTITY,
    build_artifact_bundle,
    implementation_identity as v001_implementation_identity,
)
from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_input_manifest_v003 import strict_json
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


CONTRACT_PATH = "config/professional_strategy_olympics_execution_publication_v004.json"
MODULE_PATH = "src/aml/professional_strategy_olympics_execution_publication_v004.py"
CONTRACT_IDENTITY = "0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053"
AUTHORIZATION_SCHEMA = (
    "aml.professional-strategy-olympics.lineage-bound-synthetic-trial-authorization.v004"
)
PERMITTED_OPERATION = "execute_and_publish_inaugural_canonical_synthetic_olympics_once"
PROHIBITIONS = frozenset({
    "broker", "extension", "forward", "historical", "holdout", "live",
    "network", "production", "provider", "validation",
})
OUTER_ARTIFACT_NAMES = (
    *V001_ARTIFACT_NAMES,
    "authorization_ledger.json",
    "consumption.json",
    "lineage_run_manifest.json",
    "artifact_index.json",
)
AUTHORIZATION_FIELDS = frozenset({
    "schema_version", "authorization_identity", "trial_authorized", "trial_kind",
    "permitted_operation", "maximum_execution_count", "merged_source_commit",
    "v003_authorization_contract_identity", "v003_execution_contract_identity",
    "v003_execution_implementation_identity", "v004_execution_publication_contract_identity",
    "v004_execution_publication_implementation_identity", "v001_orchestrator_identity",
    "v001_implementation_identity", "v004_scoring_identity", "canonical_fixture_identity",
    "canonical_manifest_identity", "projected_v001_manifest_identity",
    "projected_v001_run_identity", "lineage_run_identity", "human_approval_reference",
    "access_prohibitions",
})


class OlympicsExecutionPublicationV004Error(ValueError):
    """An authorization, execution, consumption, or publication invariant failed."""


def implementation_identity(root: Path) -> str:
    return canonical_hash({
        "contract_identity": CONTRACT_IDENTITY,
        "module_sha256": hashlib.sha256((root / MODULE_PATH).read_bytes()).hexdigest(),
    })


def load_contract(root: Path) -> dict[str, object]:
    value = strict_json(root / CONTRACT_PATH)
    identity = value.get("contract_identity")
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsExecutionPublicationV004Error("contract identity is invalid")
    if canonical_hash({k: v for k, v in value.items() if k != "contract_identity"}) != identity:
        raise OlympicsExecutionPublicationV004Error("contract identity changed")
    if (
        identity != CONTRACT_IDENTITY
        or value.get("source_commit_binding") != "exact_checked_out_commit"
    ):
        raise OlympicsExecutionPublicationV004Error("frozen contract binding changed")
    if any(value.get(flag) is not False for flag in (
        "authorization_creation_permitted",
        "execution_without_external_authorization_permitted",
        "publication_without_external_authorization_permitted",
    )):
        raise OlympicsExecutionPublicationV004Error("prospective boundary changed")
    if value.get("maximum_execution_count") != 1 or value.get("write_once_publication") is not True:
        raise OlympicsExecutionPublicationV004Error("single-use policy changed")
    return value


def repository_commit(root: Path) -> str:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise OlympicsExecutionPublicationV004Error("repository commit is invalid")
    return commit


def lineage_run_identity(root: Path, merged_source_commit: str | None = None) -> str:
    input_identity, inner_run = projected_identities(root)
    source_commit = merged_source_commit or repository_commit(root)
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise OlympicsExecutionPublicationV004Error("merged source commit is invalid")
    return canonical_hash({
        "merged_source_commit": source_commit,
        "v003_authorization_contract_identity": V003_AUTHORIZATION_CONTRACT_IDENTITY,
        "v003_execution_contract_identity": V003_EXECUTION_CONTRACT_IDENTITY,
        "v003_execution_implementation_identity": v003_execution_implementation_identity(root),
        "v004_execution_publication_contract_identity": CONTRACT_IDENTITY,
        "v004_execution_publication_implementation_identity": implementation_identity(root),
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": v001_implementation_identity(root),
        "v004_scoring_identity": BUNDLE_IDENTITY,
        "canonical_fixture_identity": FIXTURE_IDENTITY,
        "canonical_manifest_identity": MANIFEST_IDENTITY,
        "projected_v001_manifest_identity": input_identity,
        "projected_v001_run_identity": inner_run,
        "permitted_operation": PERMITTED_OPERATION,
        "maximum_execution_count": 1,
    })


def validate_authorization(value: Mapping[str, object], root: Path) -> dict[str, object]:
    load_contract(root)
    if set(value) != AUTHORIZATION_FIELDS or value.get("schema_version") != AUTHORIZATION_SCHEMA:
        raise OlympicsExecutionPublicationV004Error("authorization schema is invalid")
    identity = value.get("authorization_identity")
    if not isinstance(identity, str) or canonical_hash(
        {k: v for k, v in value.items() if k != "authorization_identity"}
    ) != identity:
        raise OlympicsExecutionPublicationV004Error("authorization identity is invalid")
    input_identity, inner_run = projected_identities(root)
    required = {
        "trial_authorized": True,
        "trial_kind": "synthetic",
        "permitted_operation": PERMITTED_OPERATION,
        "maximum_execution_count": 1,
        "merged_source_commit": repository_commit(root),
        "v003_authorization_contract_identity": V003_AUTHORIZATION_CONTRACT_IDENTITY,
        "v003_execution_contract_identity": V003_EXECUTION_CONTRACT_IDENTITY,
        "v003_execution_implementation_identity": v003_execution_implementation_identity(root),
        "v004_execution_publication_contract_identity": CONTRACT_IDENTITY,
        "v004_execution_publication_implementation_identity": implementation_identity(root),
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_implementation_identity": v001_implementation_identity(root),
        "v004_scoring_identity": BUNDLE_IDENTITY,
        "canonical_fixture_identity": FIXTURE_IDENTITY,
        "canonical_manifest_identity": MANIFEST_IDENTITY,
        "projected_v001_manifest_identity": input_identity,
        "projected_v001_run_identity": inner_run,
        "lineage_run_identity": lineage_run_identity(root, repository_commit(root)),
        "access_prohibitions": {key: True for key in sorted(PROHIBITIONS)},
    }
    if any(value.get(field) != expected for field, expected in required.items()):
        raise OlympicsExecutionPublicationV004Error("authorization binding is invalid")
    approval = value.get("human_approval_reference")
    if not isinstance(approval, str) or not approval:
        raise OlympicsExecutionPublicationV004Error("human approval reference is required")
    return dict(value)


def _project_v001(value: Mapping[str, object], root: Path) -> dict[str, object]:
    validated = validate_authorization(value, root)
    input_identity, inner_run = projected_identities(root)
    projected = {
        "schema_version": V001_AUTHORIZATION_SCHEMA,
        "trial_authorized": True,
        "trial_kind": "synthetic",
        "orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "orchestrator_implementation_identity": v001_implementation_identity(root),
        "scoring_bundle_identity": BUNDLE_IDENTITY,
        "input_manifest_identity": input_identity,
        "run_identity": inner_run,
        "human_approval_reference": validated["human_approval_reference"],
    }
    projected["authorization_identity"] = canonical_hash(projected)
    return projected


def consume_and_build(
    value: Mapping[str, object], root: Path, consumption_root: Path
) -> dict[str, bytes]:
    """Consume first, then invoke the unchanged V001 orchestrator and wrap its output."""
    validated = validate_authorization(value, root)
    identity = str(validated["authorization_identity"])
    claim = consumption_root / identity
    try:
        claim.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise OlympicsExecutionPublicationV004Error("authorization already consumed") from exc
    consumption = canonical_json({
        "authorization_identity": identity,
        "consumed": True,
        "execution_count": 1,
        "lineage_run_identity": validated["lineage_run_identity"],
        "state": "consumed_before_artifact_generation",
    })
    (claim / "consumption.json").write_bytes(consumption)
    manifest = adapt_manifest(load_canonical_manifest(root), root).v001_manifest
    inner = build_artifact_bundle(
        root, manifest, _project_v001(validated, root), execute_requested=True
    )
    artifacts = dict(inner)
    artifacts["authorization_ledger.json"] = canonical_json(validated)
    artifacts["consumption.json"] = consumption
    artifacts["lineage_run_manifest.json"] = canonical_json({
        "authorization_identity": identity,
        "authoritative_run_identity": validated["lineage_run_identity"],
        "classification": "canonical_synthetic_non_performance_non_economic",
        "inner_v001_run_identity": validated["projected_v001_run_identity"],
        "status": "complete",
    })
    index_records = [
        {"name": name, "sha256": hashlib.sha256(artifacts[name]).hexdigest()}
        for name in artifacts
    ]
    artifacts["artifact_index.json"] = canonical_json({
        "artifacts": index_records,
        "authoritative_run_identity": validated["lineage_run_identity"],
    })
    if tuple(artifacts) != OUTER_ARTIFACT_NAMES:
        raise OlympicsExecutionPublicationV004Error("artifact assembly is incomplete")
    return artifacts


def _validate_bundle(
    value: Mapping[str, object], root: Path, artifacts: Mapping[str, bytes]
) -> str:
    validated = validate_authorization(value, root)
    run_identity = str(validated["lineage_run_identity"])
    if tuple(artifacts) != OUTER_ARTIFACT_NAMES:
        raise OlympicsExecutionPublicationV004Error("publication input is invalid")
    expected_index = [
        {"name": name, "sha256": hashlib.sha256(artifacts[name]).hexdigest()}
        for name in OUTER_ARTIFACT_NAMES
        if name != "artifact_index.json"
    ]
    try:
        index = strict_json_bytes(artifacts["artifact_index.json"])
        lineage = strict_json_bytes(artifacts["lineage_run_manifest.json"])
    except (KeyError, ValueError) as exc:
        raise OlympicsExecutionPublicationV004Error("artifact bundle is malformed") from exc
    if index != {"artifacts": expected_index, "authoritative_run_identity": run_identity}:
        raise OlympicsExecutionPublicationV004Error("artifact index reconciliation failed")
    if artifacts["authorization_ledger.json"] != canonical_json(validated):
        raise OlympicsExecutionPublicationV004Error("authorization ledger reconciliation failed")
    if lineage.get("authoritative_run_identity") != run_identity:
        raise OlympicsExecutionPublicationV004Error("lineage reconciliation failed")
    return run_identity


def strict_json_bytes(payload: bytes) -> dict[str, object]:
    import json

    value = json.loads(payload)
    if not isinstance(value, dict) or canonical_json(value) != payload:
        raise ValueError("artifact JSON is not canonical")
    return value


def publish_once(
    destination_root: Path,
    value: Mapping[str, object],
    root: Path,
    artifacts: Mapping[str, bytes],
) -> Path:
    """Atomically publish the authoritative outer bundle; every reuse fails."""
    run_identity = _validate_bundle(value, root, artifacts)
    destination_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    final = destination_root / run_identity
    if final.exists():
        raise OlympicsExecutionPublicationV004Error("write-once output collision")
    temporary = destination_root / f".{run_identity}.incomplete"
    try:
        temporary.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise OlympicsExecutionPublicationV004Error("incomplete publication already exists") from exc
    for name in OUTER_ARTIFACT_NAMES:
        with (temporary / name).open("xb") as stream:
            stream.write(artifacts[name])
            stream.flush()
            os.fsync(stream.fileno())
    os.replace(temporary, final)
    return final
