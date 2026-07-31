"""Prospective V003 Olympics input contract with direct V002 lineage.

V003 is additive.  It preserves the complete frozen V002 representation and
validation behavior while requiring the previously omitted V002 contract
identity in every manifest's own canonical identity graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from aml.professional_strategy_executor_registry_v001 import (
    EXECUTOR_REGISTRY_IDENTITY,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY as V004_BUNDLE_IDENTITY,
)
from aml.professional_strategy_olympics_input_manifest_v002 import (
    ADAPTER_CONTRACT_IDENTITY as V002_ADAPTER_CONTRACT_IDENTITY,
    ROOT_FIELDS as V002_ROOT_FIELDS,
    SCHEMA as V002_SCHEMA,
    VERSION as V002_VERSION,
    V001_IMPLEMENTATION_IDENTITY,
    V001_ORCHESTRATOR_IDENTITY,
    manifest_identity as v002_manifest_identity,
    strict_json,
    validate_manifest as validate_v002_manifest,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash


SCHEMA = "aml.professional-strategy-olympics.synthetic-input-manifest.v003"
VERSION = "professional-strategy-olympics-synthetic-input-manifest-v003"
CONTRACT_SCHEMA = "aml.professional-strategy-olympics.input-manifest-contract.v003"
CONTRACT_VERSION = "professional-strategy-olympics-input-manifest-contract-v003"
V002_CONTRACT_IDENTITY = (
    "c9f6c8c3d02ba78c460c16230a6163fa0272b9464f60172c2bcae21fe0fbd3bb"
)
V002_ADAPTER_IMPLEMENTATION_IDENTITY = (
    "b656c07e0208479b85227b1d0b0e06f0e8f4ba5637bbb276ed045faf1bfce6d1"
)
V003_ADAPTER_CONTRACT_IDENTITY = (
    "baeb58120f458299b2d81e8381836d3c2ea00c21f28b47da703cb07a5e536261"
)
CONTRACT_IDENTITY = (
    "4b33f5a806f4fb71e65dfe571b230c32e0fea7efbad5698b4f57af9e4276371f"
)
LINEAGE_SOURCE_COMMIT = "c33efb55109361dcc6f37d87143cf655a56318d5"
ROOT_FIELDS = V002_ROOT_FIELDS | {
    "v002_contract_identity",
    "v003_contract_identity",
    "v003_adapter_contract_identity",
    "v003_adapter_implementation_identity",
}
V003_ONLY_FIELDS = ROOT_FIELDS - V002_ROOT_FIELDS
CONTRACT_FIELDS = {
    "schema", "version", "prospective_as_of", "manifest_schema",
    "manifest_version", "correction", "frozen_bindings", "root_fields",
    "inheritance", "identity_policy", "authorization", "classification",
    "contract_identity",
}


class OlympicsInputManifestV003Error(ValueError):
    """A V003 schema, lineage, identity, or inherited invariant failed."""


def _strict_fields(value: object, fields: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise OlympicsInputManifestV003Error(f"{name} fields are invalid")
    return value


def _identity(value: Mapping[str, object], field: str) -> str:
    identity = value.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsInputManifestV003Error(f"{field} must be a SHA-256 identity")
    payload = {key: item for key, item in value.items() if key != field}
    if canonical_hash(payload) != identity:
        raise OlympicsInputManifestV003Error(f"{field} is stale or tampered")
    return identity


def manifest_identity(value: Mapping[str, object]) -> str:
    """Bind every V003 root and nested atom except the identity field itself."""
    return canonical_hash({
        key: item for key, item in value.items() if key != "manifest_identity"
    })


def project_to_v002(value: Mapping[str, object]) -> dict[str, object]:
    """Create the exact inherited V002 validation view without upgrading input."""
    projected = {
        key: item for key, item in value.items() if key not in V003_ONLY_FIELDS
    }
    projected["schema_name"] = V002_SCHEMA
    projected["schema_version"] = V002_VERSION
    projected["manifest_identity"] = v002_manifest_identity(projected)
    return projected


def load_contract(root: Path) -> dict[str, object]:
    value = strict_json(
        root / "config/professional_strategy_olympics_input_manifest_v003.json"
    )
    if set(value) != CONTRACT_FIELDS:
        raise OlympicsInputManifestV003Error("V003 contract fields are invalid")
    if value.get("schema") != CONTRACT_SCHEMA or value.get("version") != CONTRACT_VERSION:
        raise OlympicsInputManifestV003Error("unsupported V003 contract")
    if _identity(value, "contract_identity") != CONTRACT_IDENTITY:
        raise OlympicsInputManifestV003Error("V003 contract identity changed")
    if value.get("manifest_schema") != SCHEMA or value.get("manifest_version") != VERSION:
        raise OlympicsInputManifestV003Error("V003 manifest version changed")
    if set(value.get("root_fields", ())) != ROOT_FIELDS:
        raise OlympicsInputManifestV003Error("V003 root field registry changed")
    correction = value.get("correction")
    if correction != {
        "field": "v002_contract_identity",
        "required": True,
        "exact_value": V002_CONTRACT_IDENTITY,
        "included_in_manifest_identity": True,
        "included_in_future_run_identity": True,
        "inference_or_external_registration_permitted": False,
    }:
        raise OlympicsInputManifestV003Error("V003 correction semantics changed")
    expected_bindings = {
        "lineage_source_commit": LINEAGE_SOURCE_COMMIT,
        "v001_orchestrator_contract_identity": V001_ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_input_manifest_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v004_scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "executor_registry_identity": EXECUTOR_REGISTRY_IDENTITY,
        "simulator_registry_identity": (
            "732fc6d982b031f0e6f428bb9e52e7c53e90a374fc883ec376504044fe7fea00"
        ),
        "lifecycle_identity": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    }
    if value.get("frozen_bindings") != expected_bindings:
        raise OlympicsInputManifestV003Error("V003 frozen bindings changed")
    authorization = value.get("authorization")
    if not isinstance(authorization, Mapping) or set(authorization) != {
        "can_authorize_trial", "can_execute_trial", "can_publish_results"
    } or any(authorization.values()):
        raise OlympicsInputManifestV003Error("V003 must remain unauthorized")
    return value


def validate_manifest(
    value: Mapping[str, object], *, v003_adapter_implementation_identity: str,
    bindings: Sequence[Mapping[str, str]], canonical_mode: bool = True,
) -> dict[str, object]:
    root = _strict_fields(value, ROOT_FIELDS, "V003 manifest")
    if root.get("schema_name") != SCHEMA or root.get("schema_version") != VERSION:
        raise OlympicsInputManifestV003Error("unsupported V003 input manifest")
    if root.get("manifest_identity") != manifest_identity(root):
        raise OlympicsInputManifestV003Error("V003 manifest identity mismatch")
    expected = {
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v003_contract_identity": CONTRACT_IDENTITY,
        "v002_adapter_contract_identity": V002_ADAPTER_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v003_adapter_implementation_identity": v003_adapter_implementation_identity,
    }
    for field, expected_value in expected.items():
        if root.get(field) != expected_value:
            raise OlympicsInputManifestV003Error(f"{field} binding changed")
    projected = project_to_v002(root)
    try:
        validate_v002_manifest(
            projected,
            adapter_implementation_identity=V002_ADAPTER_IMPLEMENTATION_IDENTITY,
            bindings=bindings,
            canonical_mode=canonical_mode,
        )
    except ValueError as exc:
        raise OlympicsInputManifestV003Error(
            f"inherited V002 validation failed: {exc}"
        ) from exc
    return dict(root)


def load_manifest(
    path: Path, *, v003_adapter_implementation_identity: str,
    bindings: Sequence[Mapping[str, str]], canonical_mode: bool = True,
) -> dict[str, object]:
    return validate_manifest(
        strict_json(path),
        v003_adapter_implementation_identity=v003_adapter_implementation_identity,
        bindings=bindings,
        canonical_mode=canonical_mode,
    )


def canonical_contract_bytes(root: Path) -> bytes:
    """Return canonical bytes for deterministic contract verification."""
    from aml.winner_archetype_contracts import canonical_json

    return canonical_json(load_contract(root))
