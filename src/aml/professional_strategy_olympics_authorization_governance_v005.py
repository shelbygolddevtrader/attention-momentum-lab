"""Design-only validation for Olympics authorization governance V005.

This module validates the frozen governance document and synthetic timestamp
vectors.  It cannot create, approve, consume, execute, or publish anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Mapping

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


CONTRACT_PATH = "config/professional_strategy_olympics_authorization_governance_v005.json"
SCHEMA = "aml.professional-strategy-olympics.authorization-governance.v005"
VERSION = "professional-strategy-olympics-authorization-governance-v005"
CONTRACT_IDENTITY = "e2df2d9405f5f4dbc4f5f17ac3712368f1894caa56e79f36c0eb67d06c0709ed"
COMMAND_IDENTITY = "278f812e47cb0d290e9188fcdaf93c7eb4b01e60f70b503471e67b7d31f54a1a"
DESIGN_BASE_COMMIT = "2f5390a844b9187b92da124a77173669f1b3f536"
V004_CONTRACT_IDENTITY = "0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053"
V004_IMPLEMENTATION_IDENTITY = "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4"
TAG_NAME = "v0.1.1-research-baseline"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
AUTHORIZATION_SCHEMA = "aml.professional-strategy-olympics.single-use-authorization.v005"
VALIDITY_SECONDS = 259_200
TIMESTAMP_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ROOT_FIELDS = frozenset({
    "authorization_schema", "authorization_storage", "authorization_validity",
    "contract_identity", "cryptographic_binding", "execution_command",
    "execution_source_policy", "historical_lineage", "post_execution_archival",
    "prospective_as_of", "replay_prevention", "review_procedure", "schema_version", "scope",
    "supersession_policy", "validation_manifest", "version",
})
AUTHORIZATION_FIELDS = (
    "schema_version", "authorization_identity", "authorization_created_at",
    "not_before", "expires_at", "authorization_status", "authorized_source_commit",
    "authorized_source_tree", "v004_execution_publication_contract_identity",
    "v004_execution_publication_implementation_identity", "v005_governance_identity",
    "authoritative_run_identity", "canonical_fixture_identity",
    "canonical_manifest_identity", "projected_v001_manifest_identity",
    "projected_v001_run_identity", "execution_entry_point",
    "execution_command_identity", "execution_environment_manifest_identity",
    "operator_instance_identity", "consumption_store_identity",
    "maximum_execution_count", "human_approval_reference",
    "independent_reviewer_identity", "supersedes_authorization_identity",
    "access_prohibitions",
)
SCOPE = {
    "authorization_created": False,
    "authorization_creation_capability_implemented": False,
    "capital_activated": False,
    "empirical_data_accessed": False,
    "execution_capability_implemented": False,
    "holdout_opened": False,
    "official_results_created": False,
    "official_run_authorized": False,
    "official_run_executed": False,
    "production_or_live_access": False,
    "publication_capability_implemented": False,
    "rankings_or_scores_created": False,
    "validation_opened": False,
}


class OlympicsAuthorizationGovernanceV005Error(ValueError):
    """A frozen V005 design or research boundary invariant failed."""


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsAuthorizationGovernanceV005Error("V005 JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OlympicsAuthorizationGovernanceV005Error(item)
            ),
        )
        canonical_json(value)
    except OlympicsAuthorizationGovernanceV005Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error(
            "V005 contract must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract root must be an object")
    return value


def parse_canonical_timestamp(value: object) -> datetime:
    """Parse the exact V005 UTC-second format for synthetic design vectors."""
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise OlympicsAuthorizationGovernanceV005Error("timestamp is not canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise OlympicsAuthorizationGovernanceV005Error("timestamp is malformed") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise OlympicsAuthorizationGovernanceV005Error("timestamp is not canonical")
    return parsed


def synthetic_validity_vector(
    created_at: str, not_before: str, expires_at: str, trusted_time: str
) -> bool:
    """Evaluate only the frozen clock equation with synthetic timestamps."""
    created = parse_canonical_timestamp(created_at)
    start = parse_canonical_timestamp(not_before)
    expiry = parse_canonical_timestamp(expires_at)
    now = parse_canonical_timestamp(trusted_time)
    if start != created or expiry != created + timedelta(seconds=VALIDITY_SECONDS):
        raise OlympicsAuthorizationGovernanceV005Error("validity equation changed")
    return start <= now < expiry


def validate_contract(value: Mapping[str, object]) -> dict[str, object]:
    if (
        set(value) != ROOT_FIELDS
        or value.get("schema_version") != SCHEMA
        or value.get("version") != VERSION
    ):
        raise OlympicsAuthorizationGovernanceV005Error("V005 root schema is invalid")
    parse_canonical_timestamp(value.get("prospective_as_of"))
    identity = value.get("contract_identity")
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract identity is invalid")
    if canonical_hash({key: item for key, item in value.items() if key != "contract_identity"}) != identity:
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract identity changed")
    lineage = value.get("historical_lineage")
    if lineage != {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_execution_publication_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_execution_publication_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
    }:
        raise OlympicsAuthorizationGovernanceV005Error("V005 lineage changed")

    schema = value.get("authorization_schema")
    if not isinstance(schema, Mapping) or schema.get("schema_version") != AUTHORIZATION_SCHEMA:
        raise OlympicsAuthorizationGovernanceV005Error("authorization schema changed")
    if tuple(schema.get("required_fields", ())) != AUTHORIZATION_FIELDS:
        raise OlympicsAuthorizationGovernanceV005Error("authorization fields changed")
    if schema.get("unknown_fields") != "reject" or schema.get("status_at_publication") != "authorized_unused":
        raise OlympicsAuthorizationGovernanceV005Error("authorization strictness changed")

    validity = value.get("authorization_validity")
    if not isinstance(validity, Mapping) or validity.get("duration_seconds") != VALIDITY_SECONDS:
        raise OlympicsAuthorizationGovernanceV005Error("authorization validity changed")
    if validity.get("timestamp_format") != "YYYY-MM-DDTHH:MM:SSZ":
        raise OlympicsAuthorizationGovernanceV005Error("timestamp format changed")
    if validity.get("creation_time_source") != "github_pull_request_createdAt_for_authorization_review_pr":
        raise OlympicsAuthorizationGovernanceV005Error("issuance clock changed")

    command = value.get("execution_command")
    if not isinstance(command, Mapping):
        raise OlympicsAuthorizationGovernanceV005Error("execution command is missing")
    command_payload = {key: item for key, item in command.items() if key != "command_identity"}
    if command.get("command_identity") != COMMAND_IDENTITY or canonical_hash(command_payload) != COMMAND_IDENTITY:
        raise OlympicsAuthorizationGovernanceV005Error("execution command identity changed")
    if command.get("entry_point") != "scripts/run_professional_strategy_olympics_v005.py":
        raise OlympicsAuthorizationGovernanceV005Error("execution entry point changed")

    source = value.get("execution_source_policy")
    if not isinstance(source, Mapping) or source.get("checkout_mode") != "detached_HEAD":
        raise OlympicsAuthorizationGovernanceV005Error("detached source policy changed")
    if source.get("commit_rule") != "HEAD_equals_authorized_source_commit":
        raise OlympicsAuthorizationGovernanceV005Error("authorized source rule changed")

    replay = value.get("replay_prevention")
    if not isinstance(replay, Mapping) or replay.get("maximum_execution_count") != 1:
        raise OlympicsAuthorizationGovernanceV005Error("single-use policy changed")
    if replay.get("consumption_order") != "validate_then_atomically_claim_before_any_artifact_generation":
        raise OlympicsAuthorizationGovernanceV005Error("consumption order changed")
    if value.get("scope") != SCOPE:
        raise OlympicsAuthorizationGovernanceV005Error("design-only scope changed")
    validation = value.get("validation_manifest")
    if not isinstance(validation, Mapping) or validation.get("status") != (
        "DESIGN_ONLY_V005_GOVERNANCE_FROZEN_AUTHORIZATION_NOT_CREATED"
    ):
        raise OlympicsAuthorizationGovernanceV005Error("validation status changed")
    if identity != CONTRACT_IDENTITY:
        raise OlympicsAuthorizationGovernanceV005Error("unexpected V005 contract identity")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    return validate_contract(_strict_json(root / CONTRACT_PATH))


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_json(validate_contract(value))


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    return canonical_json({
        "authorization_created": False,
        "authorization_governance_identity": contract["contract_identity"],
        "execution_capability_implemented": False,
        "official_run_authorized": False,
        "official_run_executed": False,
        "status": contract["validation_manifest"]["status"],
    })
