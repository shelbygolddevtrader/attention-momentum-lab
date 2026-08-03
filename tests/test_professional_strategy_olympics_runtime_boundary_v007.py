from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    EVENT_PROJECTION_DOMAIN,
    artifact_identity as v005_artifact_identity,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    strict_json_bytes,
)
from aml.professional_strategy_olympics_runtime_boundary_v007 import (
    CLAIMS_NOT_MADE,
    CONTRACT_DOMAIN,
    CONTRACT_IDENTITY,
    CONTRACT_PATH,
    EXPECTED_SECTION_IDENTITIES,
    OlympicsRuntimeBoundaryV007Error,
    SECTION_NAMES,
    canonical_contract_bytes,
    decode_frame,
    encode_frame,
    load_contract,
    operator_implementation_identity,
    record_identity,
    repository_event_projection_identity,
    validate_clock_exchange,
    validate_contract,
    validate_repository_exchange,
    validate_runtime_graph,
    validate_runtime_record,
    validation_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_runtime_boundary_v007.py"
H = "1" * 64
G = "2" * 40
T0 = "2026-08-03T12:00:00Z"
IMF_T0 = "Mon, 03 Aug 2026 12:00:00 GMT"


def contract() -> dict[str, object]:
    return load_contract(ROOT)


def reseal_contract(value: dict[str, object], section: str | None = None) -> dict[str, object]:
    result = copy.deepcopy(value)
    if section is not None:
        result["section_identities"][section] = domain_hash(
            f"aml.olympics.v007.section.{section}", result[section]
        )
    result["contract_identity"] = domain_hash(
        CONTRACT_DOMAIN,
        {key: item for key, item in result.items() if key != "contract_identity"},
    )
    return result


def seal(record_type: str, value: dict[str, object], value_contract: dict[str, object]) -> dict[str, object]:
    identity_field = value_contract["runtime_schemas"][record_type]["identity_field"]
    value[identity_field] = record_identity(record_type, value, value_contract)
    return value


def v005_clock_artifacts(
    *, nonce: str, artifact_type: str, timestamp_field: str, projection_identity: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    value_contract = load_v005_contract(ROOT)
    raw_request = (
        b"HEAD /rate_limit HTTP/1.1\r\n"
        b"Host: api.github.com\r\n"
        b"X-GitHub-Api-Version: 2022-11-28\r\n"
        + f"X-AML-Clock-Nonce: {nonce}\r\n".encode()
        + b"Cache-Control: no-cache, no-store\r\n"
        b"Pragma: no-cache\r\n"
        b"Connection: close\r\n\r\n"
    )
    request = {
        "clock_request_identity": H,
        "direct_origin_required": True,
        "maximum_elapsed_milliseconds": 5000,
        "method": "HEAD",
        "origin": "https://api.github.com:443",
        "raw_request_bytes_base64": base64.b64encode(raw_request).decode(),
        "request_nonce": nonce,
        "schema_version": "aml.professional-strategy-olympics.clock-request.v005",
        "target": "/rate_limit",
    }
    request["clock_request_identity"] = v005_artifact_identity(
        request, value_contract["artifact_schemas"]["clock_request"]
    )
    raw_headers = f"HTTP/1.1 200 OK\r\nDate: {IMF_T0}\r\n\r\n".encode()
    evidence = {
        "clock_evidence_identity": H,
        "http_version": "HTTP/1.1",
        "raw_response_headers_base64": base64.b64encode(raw_headers).decode(),
        "redirect_count": 0,
        "request_identity": request["clock_request_identity"],
        "response_date_as_received": IMF_T0,
        "response_elapsed_milliseconds": 100,
        "response_status": 200,
        "schema_version": "aml.professional-strategy-olympics.clock-evidence.v005",
    }
    evidence["clock_evidence_identity"] = v005_artifact_identity(
        evidence, value_contract["artifact_schemas"]["clock_evidence"]
    )
    verifier = {
        "cache_result": "absent",
        "certificate_result": "verified",
        "clock_verifier_attestation_identity": H,
        "direct_tls_result": "verified",
        "evidence_identity": evidence["clock_evidence_identity"],
        "header_policy_result": "strict_allowlist_passed",
        "proxy_result": "absent",
        "redirect_result": "absent",
        "replay_nonce": nonce,
        "request_identity": request["clock_request_identity"],
        "schema_version": "aml.professional-strategy-olympics.clock-verifier-attestation.v005",
        "transport_evidence_identity": "8" * 64,
        "trust_scope": "external_verifier_attestation_not_independently_authenticated",
        "verified_at": T0,
        "verified_date": IMF_T0,
        "verified_host": "api.github.com",
        "verifier_account_identity": "7" * 64,
        "verifier_version": "1.0.0",
    }
    verifier["clock_verifier_attestation_identity"] = v005_artifact_identity(
        verifier, value_contract["artifact_schemas"]["clock_verifier_attestation"]
    )
    attestation = {
        "bound_artifact_type": artifact_type,
        "bound_event_projection_identity": projection_identity,
        "bound_timestamp_field": timestamp_field,
        "canonical_utc_timestamp": T0,
        "clock_attestation_identity": H,
        "evidence_identity": evidence["clock_evidence_identity"],
        "request_identity": request["clock_request_identity"],
        "reuse_policy": "unique_per_lifecycle_artifact",
        "schema_version": "aml.professional-strategy-olympics.clock-attestation.v005",
        "verifier_attestation_identity": verifier[
            "clock_verifier_attestation_identity"
        ],
    }
    attestation["clock_attestation_identity"] = v005_artifact_identity(
        attestation, value_contract["artifact_schemas"]["clock_attestation"]
    )
    return request, evidence, verifier, attestation


def replay_registry(kind: str, value_contract: dict[str, object]) -> dict[str, object]:
    return seal(
        "replay_registry",
        {
            "schema_version": "aml.professional-strategy-olympics.replay-registry.v007",
            "replay_registry_identity": H,
            "registry_kind": kind,
            "owner_service_identity": "3" * 64,
            "owner_implementation_identity": "4" * 64,
            "canonical_root": f"/synthetic/{kind}-registry",
            "owner_uid": 501,
            "owner_gid": 20,
            "directory_mode": "0700",
            "file_mode": "0600",
            "filesystem": "local_APFS",
            "nonce_scope": "global_per_service_identity_and_implementation_identity",
            "atomicity": "openat_O_CREAT_O_EXCL_O_WRONLY_O_NOFOLLOW_then_F_FULLFSYNC_close_parent_fsync",
            "collision_policy": "replay_reject",
            "write_failure_policy": "indeterminate_no_success_response",
            "retention_policy": "permanent_no_delete_or_reuse",
        },
        value_contract,
    )


def bootstrap(clock_registry: dict[str, object], value_contract: dict[str, object]) -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-bootstrap.v007",
        "clock_bootstrap_identity": H,
        "runtime_boundary_identity": CONTRACT_IDENTITY,
        "authorization_identity": "5" * 64,
        "v005_governance_identity": "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0",
        "v005_command_identity": "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb",
        "v006_operator_interface_identity": "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6",
        "operator_implementation_identity": "6" * 64,
        "system_account_identity": "7" * 64,
        "verifier_actor_identity": "7" * 64,
        "verifier_service_identity": "8" * 64,
        "verifier_implementation_identity": "9" * 64,
        "protocol_version": 1,
        "session_nonce": "a" * 64,
        "session_identity": H,
        "socket_path": "/synthetic/aml-clock.sock",
        "expected_peer_uid": 501,
        "expected_peer_gid": 20,
        "maximum_request_bytes": 2_000_000,
        "maximum_response_bytes": 2_000_000,
        "connect_timeout_milliseconds": 1000,
        "read_timeout_milliseconds": 1000,
        "write_timeout_milliseconds": 1000,
        "total_verification_deadline_milliseconds": 5000,
        "session_policy": "one_connection_multiple_strictly_sequenced_requests",
        "reconnect_policy": "no_reconnect_verifier_restart_invalidates_authorization",
        "error_policy": "no_local_clock_fallback",
        "clock_replay_registry_identity": clock_registry["replay_registry_identity"],
        "initial_clock_request_identity": "b" * 64,
        "initial_clock_evidence_identity": "c" * 64,
        "initial_clock_verifier_attestation_identity": "d" * 64,
        "initial_clock_attestation_identity": "e" * 64,
    }
    projection = {
        name: value[name]
        for name in value_contract["clock_session_replay"]["session_identity_projection"]
    }
    value["session_identity"] = domain_hash(
        value_contract["clock_session_replay"]["session_identity_domain"], projection
    )
    return seal("clock_bootstrap", value, value_contract)


def clock_request(value_bootstrap: dict[str, object], value_contract: dict[str, object]) -> dict[str, object]:
    projection = {"artifact_type": "activation", "projection": {"authorization_identity": "5" * 64}}
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-request-envelope.v007",
        "request_identity": H,
        "protocol_version": 1,
        "runtime_boundary_identity": CONTRACT_IDENTITY,
        "authorization_identity": value_bootstrap["authorization_identity"],
        "authoritative_run_identity": "f" * 64,
        "operator_implementation_identity": value_bootstrap["operator_implementation_identity"],
        "verifier_service_identity": value_bootstrap["verifier_service_identity"],
        "session_identity": value_bootstrap["session_identity"],
        "sequence_number": 0,
        "request_nonce": "0" * 64,
        "transition_id": "authorization_activated",
        "bound_artifact_type": "activation",
        "bound_timestamp_field": "activated_at",
        "event_projection_identity": domain_hash(EVENT_PROJECTION_DOMAIN, projection),
        "event_projection_canonical_base64": base64.b64encode(canonical_bytes(projection)).decode(),
        "prior_clock_attestation_identity": None,
        "requested_semantics": "github_Date_second_precision_for_exact_V005_event_projection",
    }
    return seal("clock_request", value, value_contract)


def failed_clock_response(
    request: dict[str, object],
    value_bootstrap: dict[str, object],
    clock_registry: dict[str, object],
    value_contract: dict[str, object],
) -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-response-envelope.v007",
        "response_identity": H,
        "protocol_version": 1,
        "request_identity": request["request_identity"],
        "request_nonce": request["request_nonce"],
        "evidence_nonce": "1" * 64,
        "verifier_actor_identity": value_bootstrap["verifier_actor_identity"],
        "verifier_service_identity": value_bootstrap["verifier_service_identity"],
        "verifier_implementation_identity": value_bootstrap["verifier_implementation_identity"],
        "session_identity": request["session_identity"],
        "sequence_number": request["sequence_number"],
        "status": "failure",
        "failure_code": "tls_failure",
        "verified_timestamp": None,
        "verification_started_at": T0,
        "verification_completed_at": "2026-08-03T12:00:01Z",
        "v005_clock_request_identity": None,
        "v005_clock_request_base64": None,
        "v005_clock_evidence_identity": None,
        "v005_clock_evidence_base64": None,
        "v005_clock_verifier_attestation_identity": None,
        "v005_clock_verifier_attestation_base64": None,
        "v005_clock_attestation_identity": None,
        "v005_clock_attestation_base64": None,
        "clock_replay_registry_identity": clock_registry["replay_registry_identity"],
        "registry_write_state": "collision",
    }
    return seal("clock_response", value, value_contract)


def repository_request(
    value_bootstrap: dict[str, object],
    repository_registry: dict[str, object],
    value_contract: dict[str, object],
) -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.repository-attestation-request.v007",
        "repository_request_identity": H,
        "runtime_boundary_identity": CONTRACT_IDENTITY,
        "authorization_identity": value_bootstrap["authorization_identity"],
        "authoritative_run_identity": "f" * 64,
        "source_root_canonical_path": "/synthetic/authorized-source",
        "expected_repository_identity": "shelbygolddevtrader/attention-momentum-lab",
        "expected_source_commit": G,
        "expected_source_tree": "3" * 40,
        "required_path_blob_bindings": [f"config/example.json={'4' * 40}"],
        "required_parent_relationships": [f"{G}>{'5' * 40}"],
        "expected_operator_implementation_identity": value_bootstrap["operator_implementation_identity"],
        "expected_command_identity": "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb",
        "expected_v004_contract_identity": "0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053",
        "expected_v004_implementation_identity": "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4",
        "expected_v005_governance_identity": "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0",
        "expected_v006_operator_interface_identity": "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6",
        "expected_v007_runtime_boundary_identity": CONTRACT_IDENTITY,
        "expected_manifest_identity": "6" * 64,
        "expected_orchestrator_identity": "9e1af13518bc4c6588ce4faaf302e15182f9d42e5dd8c453fc6d27dd257b8d3e",
        "request_nonce": "2" * 64,
        "requester_actor_identity": "3" * 64,
        "clock_request_envelope_identity": H,
        "clock_response_envelope_identity": H,
        "expected_attestor_actor_identity": "6" * 64,
        "expected_attestor_implementation_identity": "8" * 64,
        "expected_attestor_service_identity": "7" * 64,
        "requested_at": T0,
        "maximum_age_seconds": 300,
        "repository_replay_registry_identity": repository_registry["replay_registry_identity"],
    }
    return seal("repository_request", value, value_contract)


def repository_response(
    request: dict[str, object],
    repository_registry: dict[str, object],
    value_contract: dict[str, object],
) -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.repository-attestation-response.v007",
        "repository_response_identity": H,
        "repository_request_identity": request["repository_request_identity"],
        "request_nonce": request["request_nonce"],
        "attestation_nonce": "5" * 64,
        "attestor_actor_identity": "6" * 64,
        "attestor_service_identity": "7" * 64,
        "attestor_implementation_identity": "8" * 64,
        "repository_replay_registry_identity": repository_registry["replay_registry_identity"],
        "registry_write_state": "durable_unique",
        "status": "success",
        "failure_code": None,
        "repository_identity": request["expected_repository_identity"],
        "observed_source_commit": request["expected_source_commit"],
        "observed_source_tree": request["expected_source_tree"],
        "observed_path_blob_bindings": request["required_path_blob_bindings"],
        "observed_parent_relationships": request["required_parent_relationships"],
        "observed_clean_state": True,
        "source_root_observation_identity": "9" * 64,
        "observation_timestamp": T0,
        "valid_from": T0,
        "valid_until": "2026-08-03T12:05:00Z",
        "clock_request_envelope_identity": H,
        "clock_response_envelope_identity": H,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }
    return seal("repository_response", value, value_contract)


def repository_clock_pair(
    record_type: str,
    record: dict[str, object],
    value_bootstrap: dict[str, object],
    clock_registry: dict[str, object],
    value_contract: dict[str, object],
    *,
    sequence: int,
    prior_clock_attestation_identity: str,
) -> tuple[dict[str, object], dict[str, object]]:
    request = clock_request(value_bootstrap, value_contract)
    timestamp_field = "requested_at" if record_type == "repository_request" else "observation_timestamp"
    identity_field = value_contract["runtime_schemas"][record_type]["identity_field"]
    excluded = {
        identity_field,
        timestamp_field,
        "clock_request_envelope_identity",
        "clock_response_envelope_identity",
    }
    projection = {key: item for key, item in record.items() if key not in excluded}
    wrapper = {"artifact_type": record_type, "projection": projection}
    request.update(
        {
            "sequence_number": sequence,
            "request_nonce": f"{sequence + 10:064x}",
            "transition_id": record_type,
            "bound_artifact_type": record_type,
            "bound_timestamp_field": timestamp_field,
            "event_projection_identity": repository_event_projection_identity(
                record_type, record, value_contract
            ),
            "event_projection_canonical_base64": base64.b64encode(
                canonical_bytes(wrapper)
            ).decode(),
            "prior_clock_attestation_identity": prior_clock_attestation_identity,
        }
    )
    seal("clock_request", request, value_contract)
    v005_request, v005_evidence, v005_verifier, v005_attestation = (
        v005_clock_artifacts(
            nonce=f"{sequence + 30:064x}",
            artifact_type="activation",
            timestamp_field="activated_at",
            projection_identity=request["event_projection_identity"],
        )
    )
    response = {
        "schema_version": "aml.professional-strategy-olympics.clock-response-envelope.v007",
        "response_identity": H,
        "protocol_version": 1,
        "request_identity": request["request_identity"],
        "request_nonce": request["request_nonce"],
        "evidence_nonce": f"{sequence + 20:064x}",
        "verifier_actor_identity": value_bootstrap["verifier_actor_identity"],
        "verifier_service_identity": value_bootstrap["verifier_service_identity"],
        "verifier_implementation_identity": value_bootstrap["verifier_implementation_identity"],
        "session_identity": request["session_identity"],
        "sequence_number": sequence,
        "status": "success",
        "failure_code": None,
        "verified_timestamp": record[timestamp_field],
        "verification_started_at": record[timestamp_field],
        "verification_completed_at": record[timestamp_field],
        "v005_clock_request_identity": v005_request["clock_request_identity"],
        "v005_clock_request_base64": base64.b64encode(
            canonical_bytes(v005_request)
        ).decode(),
        "v005_clock_evidence_identity": v005_evidence["clock_evidence_identity"],
        "v005_clock_evidence_base64": base64.b64encode(
            canonical_bytes(v005_evidence)
        ).decode(),
        "v005_clock_verifier_attestation_identity": v005_verifier[
            "clock_verifier_attestation_identity"
        ],
        "v005_clock_verifier_attestation_base64": base64.b64encode(
            canonical_bytes(v005_verifier)
        ).decode(),
        "v005_clock_attestation_identity": v005_attestation[
            "clock_attestation_identity"
        ],
        "v005_clock_attestation_base64": base64.b64encode(
            canonical_bytes(v005_attestation)
        ).decode(),
        "clock_replay_registry_identity": clock_registry["replay_registry_identity"],
        "registry_write_state": "durable_unique",
    }
    seal("clock_response", response, value_contract)
    return request, response


def repository_fixture(value_contract: dict[str, object]) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    clock_registry = replay_registry("clock", value_contract)
    repository_registry = replay_registry("repository", value_contract)
    value_bootstrap = bootstrap(clock_registry, value_contract)
    request = repository_request(value_bootstrap, repository_registry, value_contract)
    request_clock_request, request_clock_response = repository_clock_pair(
        "repository_request",
        request,
        value_bootstrap,
        clock_registry,
        value_contract,
        sequence=0,
        prior_clock_attestation_identity=value_bootstrap[
            "initial_clock_attestation_identity"
        ],
    )
    request["clock_request_envelope_identity"] = request_clock_request["request_identity"]
    request["clock_response_envelope_identity"] = request_clock_response["response_identity"]
    seal("repository_request", request, value_contract)
    response = repository_response(request, repository_registry, value_contract)
    response_clock_request, response_clock_response = repository_clock_pair(
        "repository_response",
        response,
        value_bootstrap,
        clock_registry,
        value_contract,
        sequence=1,
        prior_clock_attestation_identity=request_clock_response[
            "v005_clock_attestation_identity"
        ],
    )
    response["clock_request_envelope_identity"] = response_clock_request["request_identity"]
    response["clock_response_envelope_identity"] = response_clock_response["response_identity"]
    seal("repository_response", response, value_contract)
    return (
        value_bootstrap,
        clock_registry,
        repository_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    )


def runtime_records(value_contract: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    (
        value_bootstrap,
        clock_registry,
        repository_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    ) = repository_fixture(value_contract)
    envelope = seal(
        "runtime_envelope",
        {
            "schema_version": "aml.professional-strategy-olympics.runtime-envelope.v007",
            "runtime_envelope_identity": H,
            "runtime_boundary_identity": CONTRACT_IDENTITY,
            "authorization_identity": value_bootstrap["authorization_identity"],
            "authorized_source_commit": request["expected_source_commit"],
            "authorized_source_tree": request["expected_source_tree"],
            "authoritative_run_identity": request["authoritative_run_identity"],
            "operator_implementation_identity": value_bootstrap["operator_implementation_identity"],
            "clock_bootstrap_identity": value_bootstrap["clock_bootstrap_identity"],
            "repository_request_identity": request["repository_request_identity"],
            "repository_response_identity": response["repository_response_identity"],
            "clock_replay_registry_identity": clock_registry["replay_registry_identity"],
            "repository_replay_registry_identity": repository_registry["replay_registry_identity"],
            "v005_transition_envelope_identity": "b" * 64,
            "v005_governance_identity": "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0",
            "v005_command_identity": "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb",
            "v006_operator_interface_identity": "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6",
        },
        value_contract,
    )
    runtime_root = f"runtime/{value_bootstrap['authorization_identity']}"
    indexed = [
        ("clock_bootstrap", value_bootstrap, f"{runtime_root}/clock_bootstrap.json"),
        ("clock_request", request_clock_request, f"{runtime_root}/clock_requests/repository_request.json"),
        ("clock_request", response_clock_request, f"{runtime_root}/clock_requests/repository_response.json"),
        ("clock_response", request_clock_response, f"{runtime_root}/clock_responses/repository_request.json"),
        ("clock_response", response_clock_response, f"{runtime_root}/clock_responses/repository_response.json"),
        ("replay_registry", clock_registry, f"{runtime_root}/clock_replay_registry.json"),
        ("replay_registry", repository_registry, f"{runtime_root}/repository_replay_registry.json"),
        ("repository_request", request, f"{runtime_root}/repository_request.json"),
        ("repository_response", response, f"{runtime_root}/repository_response.json"),
        ("runtime_envelope", envelope, f"{runtime_root}/runtime_envelope.json"),
    ]
    entries = []
    for record_type, record, relative_path in indexed:
        schema = value_contract["runtime_schemas"][record_type]
        entries.append(
            {
                "artifact_type": record_type,
                "artifact_identity": record[schema["identity_field"]],
                "relative_path": relative_path,
                "canonical_bytes_sha256": hashlib.sha256(canonical_bytes(record)).hexdigest(),
                "schema_version": schema["schema_version"],
            }
        )
    entries.sort(
        key=lambda item: tuple(
            str(item[name]).encode()
            for name in ("artifact_type", "artifact_identity", "relative_path", "schema_version")
        )
    )
    package = seal(
        "runtime_package",
        {
            "schema_version": "aml.professional-strategy-olympics.runtime-package.v007",
            "runtime_package_identity": H,
            "runtime_boundary_identity": CONTRACT_IDENTITY,
            "operator_implementation_identity": value_bootstrap["operator_implementation_identity"],
            "authorization_identity": value_bootstrap["authorization_identity"],
            "authorized_source_commit": request["expected_source_commit"],
            "authorized_source_tree": request["expected_source_tree"],
            "authoritative_run_identity": request["authoritative_run_identity"],
            "runtime_envelope_identity": envelope["runtime_envelope_identity"],
            "record_index": entries,
        },
        value_contract,
    )
    return {
        "runtime_package": [package],
        "runtime_envelope": [envelope],
        "clock_bootstrap": [value_bootstrap],
        "clock_request": [request_clock_request, response_clock_request],
        "clock_response": [request_clock_response, response_clock_response],
        "repository_request": [request],
        "repository_response": [response],
        "replay_registry": [clock_registry, repository_registry],
    }


def test_contract_loads_as_canonical_bytes_with_exact_identities() -> None:
    value = contract()
    assert value["contract_identity"] == CONTRACT_IDENTITY
    assert (ROOT / CONTRACT_PATH).read_bytes() == canonical_bytes(value)
    assert canonical_contract_bytes(value) == canonical_bytes(value)
    assert len(canonical_bytes(value)) == 30_076


def test_outer_and_every_section_identity_reproduce_independently() -> None:
    value = contract()
    for name in SECTION_NAMES:
        expected = hashlib.sha256(
            f"aml.olympics.v007.section.{name}".encode() + b"\0" + canonical_bytes(value[name])
        ).hexdigest()
        assert expected == EXPECTED_SECTION_IDENTITIES[name] == value["section_identities"][name]
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    assert hashlib.sha256(CONTRACT_DOMAIN.encode() + b"\0" + canonical_bytes(projection)).hexdigest() == CONTRACT_IDENTITY


def _leaf_paths(value: object, prefix: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [path for key, item in value.items() for path in _leaf_paths(item, (*prefix, key))]
    if isinstance(value, list):
        return [path for index, item in enumerate(value) for path in _leaf_paths(item, (*prefix, index))]
    return [prefix]


def _mutate_leaf(value: object) -> object:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if value is None:
        return "changed"
    return f"{value}_changed"


@pytest.mark.parametrize(
    ("section", "path"),
    [
        (section, path)
        for section in SECTION_NAMES
        for path in _leaf_paths(json.loads((ROOT / CONTRACT_PATH).read_text())[section])
    ],
)
def test_every_normative_section_leaf_is_identity_covered(section: str, path: tuple[object, ...]) -> None:
    changed = copy.deepcopy(contract())
    target = changed[section]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = _mutate_leaf(target[path[-1]])
    changed = reseal_contract(changed, section)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error):
        validate_contract(changed)


@pytest.mark.parametrize(
    "transform",
    [
        lambda raw: b" " + raw,
        lambda raw: raw[:-1],
        lambda raw: raw + b"\n",
        lambda raw: raw[:-1] + b"\r\n",
        lambda raw: b"\xef\xbb\xbf" + raw,
        lambda raw: json.dumps(json.loads(raw), indent=2).encode() + b"\n",
    ],
)
def test_noncanonical_contract_bytes_reject(transform) -> None:
    with pytest.raises(ValueError):
        strict_json_bytes(transform((ROOT / CONTRACT_PATH).read_bytes()))


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}\n',
        b'{"a":1.0}\n',
        b'{"a":NaN}\n',
        b'{"a":"\xff"}\n',
        '{"a":"e\u0301"}\n'.encode(),
    ],
)
def test_hostile_json_rejects(raw: bytes) -> None:
    with pytest.raises(ValueError):
        strict_json_bytes(raw)


def test_frame_round_trip_is_exactly_one_canonical_message() -> None:
    value = {"alpha": 1, "beta": ["x"]}
    frame = encode_frame(value)
    assert frame[:4] == len(canonical_bytes(value)).to_bytes(4, "big")
    assert decode_frame(frame) == value


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"\x00\x00\x00",
        b"\x00\x00\x00\x00",
        (2_000_001).to_bytes(4, "big"),
        b"\x00\x00\x00\x05{}\n",
        b"\x00\x00\x00\x03{}\ntrailing",
        b"\x00\x00\x00\x04{ }\n",
        b"\x00\x00\x00\x0e{\"a\":1,\"a\":2}\n",
    ],
)
def test_hostile_frames_reject(frame: bytes) -> None:
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RESPONSE_FRAME"):
        decode_frame(frame)


def operator_manifest(value_contract: dict[str, object]) -> dict[str, object]:
    binding = value_contract["runtime_identity_binding"]
    value = {
        "schema_version": binding["future_manifest_schema"],
        "implementation_identity": H,
        "v005_governance_identity": "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0",
        "v005_command_identity": "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb",
        "v006_operator_interface_identity": "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6",
        "v007_runtime_boundary_identity": CONTRACT_IDENTITY,
        "implementation_files": [
            {"relative_path": path, "canonical_bytes_sha256": str(index + 1) * 64}
            for index, path in enumerate(binding["implementation_source_paths"])
        ],
    }
    projection = {
        name: value[name] for name in binding["implementation_projection"]
    }
    value["implementation_identity"] = domain_hash(
        binding["implementation_identity_domain"], projection
    )
    return value


def test_future_operator_identity_is_non_circular_and_reproducible() -> None:
    value_contract = contract()
    manifest = operator_manifest(value_contract)
    assert operator_implementation_identity(manifest, value_contract) == manifest[
        "implementation_identity"
    ]
    assert "implementation_identity" not in value_contract[
        "runtime_identity_binding"
    ]["implementation_projection"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"v007_runtime_boundary_identity": "0" * 64}),
        lambda value: value["implementation_files"].reverse(),
        lambda value: value["implementation_files"].pop(),
        lambda value: value["implementation_files"][0].update(
            {"relative_path": "src/aml/alternate.py"}
        ),
        lambda value: value["implementation_files"][0].update(
            {"canonical_bytes_sha256": "0" * 64}
        ),
        lambda value: value.update({"implementation_identity": "0" * 64}),
    ],
)
def test_future_operator_identity_rejects_substitution(mutation) -> None:
    value_contract = contract()
    manifest = operator_manifest(value_contract)
    mutation(manifest)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_IMPLEMENTATION_IDENTITY"):
        operator_implementation_identity(manifest, value_contract)


def test_runtime_graph_is_closed_and_deterministic() -> None:
    value_contract = contract()
    records = runtime_records(value_contract)
    first = validate_runtime_graph(records, value_contract)
    second = validate_runtime_graph(copy.deepcopy(records), value_contract)
    assert first == second


@pytest.mark.parametrize(
    "mutation",
    [
        lambda records: records.update({"unknown": records["clock_bootstrap"]}),
        lambda records: records.pop("repository_response"),
        lambda records: records["runtime_envelope"].append(records["runtime_envelope"][0]),
        lambda records: records["replay_registry"].append(records["replay_registry"][0]),
    ],
)
def test_runtime_graph_rejects_unknown_missing_and_duplicate_records(mutation) -> None:
    value_contract = contract()
    records = runtime_records(value_contract)
    mutation(records)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RUNTIME_REACHABILITY"):
        validate_runtime_graph(records, value_contract)


def test_runtime_graph_rejects_wrong_edge_and_mixed_authorization() -> None:
    value_contract = contract()
    records = runtime_records(value_contract)
    envelope = records["runtime_envelope"][0]
    envelope["clock_bootstrap_identity"] = "0" * 64
    seal("runtime_envelope", envelope, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RUNTIME_REACHABILITY"):
        validate_runtime_graph(records, value_contract)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("relative_path", "runtime/5/alternate.json"),
        ("schema_version", "aml.alternate.v007"),
        ("canonical_bytes_sha256", "0" * 64),
    ],
)
def test_runtime_graph_rejects_index_metadata_substitution(
    field: str, replacement: object
) -> None:
    value_contract = contract()
    records = runtime_records(value_contract)
    package = records["runtime_package"][0]
    package["record_index"][0][field] = replacement
    package["record_index"].sort(
        key=lambda item: tuple(
            str(item[name]).encode()
            for name in (
                "artifact_type",
                "artifact_identity",
                "relative_path",
                "schema_version",
            )
        )
    )
    seal("runtime_package", package, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RUNTIME_REACHABILITY"):
        validate_runtime_graph(records, value_contract)


def test_runtime_graph_rejects_extra_index_record_and_package_self_index() -> None:
    value_contract = contract()
    for self_index in (False, True):
        records = runtime_records(value_contract)
        package = records["runtime_package"][0]
        package["record_index"].append(
            {
                "artifact_type": "runtime_package" if self_index else "clock_request",
                "artifact_identity": package["runtime_package_identity"]
                if self_index
                else "0" * 64,
                "relative_path": "runtime/extra.json",
                "canonical_bytes_sha256": "0" * 64,
                "schema_version": "aml.extra.v007",
            }
        )
        package["record_index"].sort(
            key=lambda item: tuple(
                str(item[name]).encode()
                for name in (
                    "artifact_type",
                    "artifact_identity",
                    "relative_path",
                    "schema_version",
                )
            )
        )
        seal("runtime_package", package, value_contract)
        with pytest.raises(
            OlympicsRuntimeBoundaryV007Error, match="V007_RUNTIME_REACHABILITY"
        ):
            validate_runtime_graph(records, value_contract)


@pytest.mark.parametrize("attack", ["prior_chain", "cross_type_nonce"])
def test_runtime_graph_rejects_clock_chain_and_global_nonce_replay(attack: str) -> None:
    value_contract = contract()
    records = runtime_records(value_contract)
    if attack == "prior_chain":
        records["clock_request"][1]["prior_clock_attestation_identity"] = "0" * 64
        seal("clock_request", records["clock_request"][1], value_contract)
    else:
        records["clock_response"][1]["evidence_nonce"] = records["clock_request"][0][
            "request_nonce"
        ]
        seal("clock_response", records["clock_response"][1], value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error):
        validate_runtime_graph(records, value_contract)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("schema_version", "wrong"),
        ("socket_path", "relative.sock"),
        ("expected_peer_uid", -1),
        ("protocol_version", 2),
        ("reconnect_policy", "reconnect"),
        ("verifier_actor_identity", "0" * 64),
    ],
)
def test_clock_bootstrap_schema_and_binding_attacks_reject(field: str, replacement: object) -> None:
    value_contract = contract()
    registry = replay_registry("clock", value_contract)
    value = bootstrap(registry, value_contract)
    value[field] = replacement
    seal("clock_bootstrap", value, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error):
        validate_runtime_record("clock_bootstrap", value, value_contract)


def test_clock_exchange_rejects_mismatch_nonce_collision_and_rollback() -> None:
    value_contract = contract()
    registry = replay_registry("clock", value_contract)
    value_bootstrap = bootstrap(registry, value_contract)
    request = clock_request(value_bootstrap, value_contract)
    response = failed_clock_response(request, value_bootstrap, registry, value_contract)
    validate_clock_exchange(request, response, value_bootstrap, registry, value_contract)
    changed = copy.deepcopy(response)
    changed["request_identity"] = "f" * 64
    seal("clock_response", changed, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_VERIFIER_MISMATCH"):
        validate_clock_exchange(request, changed, value_bootstrap, registry, value_contract)
    changed = copy.deepcopy(response)
    changed["evidence_nonce"] = request["request_nonce"]
    seal("clock_response", changed, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_NONCE_COLLISION"):
        validate_clock_exchange(request, changed, value_bootstrap, registry, value_contract)


def test_clock_response_rejects_window_and_status_contradictions() -> None:
    value_contract = contract()
    registry = replay_registry("clock", value_contract)
    value_bootstrap = bootstrap(registry, value_contract)
    request = clock_request(value_bootstrap, value_contract)
    response = failed_clock_response(request, value_bootstrap, registry, value_contract)
    response["verification_completed_at"] = "2026-08-03T12:00:06Z"
    seal("clock_response", response, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_VERIFICATION_WINDOW"):
        validate_runtime_record("clock_response", response, value_contract)
    response = failed_clock_response(request, value_bootstrap, registry, value_contract)
    response["failure_code"] = None
    seal("clock_response", response, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RESPONSE_FRAME"):
        validate_runtime_record("clock_response", response, value_contract)
    response = failed_clock_response(request, value_bootstrap, registry, value_contract)
    response["failure_code"] = "unregistered_failure"
    seal("clock_response", response, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_RESPONSE_FRAME"):
        validate_runtime_record("clock_response", response, value_contract)


def test_clock_exchange_rejects_tampered_embedded_v005_bundle() -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        _,
        _,
        request,
        response,
        _,
        _,
        _,
    ) = repository_fixture(value_contract)
    response["v005_clock_request_base64"] = response[
        "v005_clock_evidence_base64"
    ]
    seal("clock_response", response, value_contract)
    with pytest.raises(
        OlympicsRuntimeBoundaryV007Error, match="V007_RESPONSE_IDENTITY"
    ):
        validate_clock_exchange(
            request,
            response,
            value_bootstrap,
            clock_registry,
            value_contract,
        )


def test_successful_clock_exchange_rejects_rollback_and_verifier_substitution() -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        _,
        _,
        request,
        response,
        _,
        _,
        _,
    ) = repository_fixture(value_contract)
    validate_clock_exchange(
        request, response, value_bootstrap, clock_registry, value_contract
    )
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_CLOCK_ROLLBACK"):
        validate_clock_exchange(
            request,
            response,
            value_bootstrap,
            clock_registry,
            value_contract,
            previous_verified_timestamp="2026-08-03T12:00:01Z",
        )
    substituted = copy.deepcopy(response)
    substituted["verifier_implementation_identity"] = "0" * 64
    seal("clock_response", substituted, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_VERIFIER_MISMATCH"):
        validate_clock_exchange(
            request,
            substituted,
            value_bootstrap,
            clock_registry,
            value_contract,
        )


def test_repository_exchange_accepts_exact_fresh_binding() -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        repo_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    ) = repository_fixture(value_contract)
    validate_repository_exchange(
        request,
        response,
        request_clock_request,
        request_clock_response,
        response_clock_request,
        response_clock_response,
        repo_registry,
        value_bootstrap,
        clock_registry,
        value_contract,
        trusted_use_time="2026-08-03T12:04:59Z",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("claims_not_made", [*CLAIMS_NOT_MADE[:-1], "tls_verified"], "V007_UNSUPPORTED_TRUST_CLAIM"),
        ("valid_until", "2026-08-03T12:05:01Z", "V007_STALE_REPOSITORY"),
        ("observed_source_commit", "0" * 40, "V007_REPOSITORY_RESPONSE"),
        ("attestation_nonce", "2" * 64, "V007_NONCE_COLLISION"),
    ],
)
def test_repository_attestation_attacks_reject(field: str, value: object, message: str) -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        repo_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    ) = repository_fixture(value_contract)
    response[field] = value
    seal("repository_response", response, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match=message):
        validate_repository_exchange(
            request,
            response,
            request_clock_request,
            request_clock_response,
            response_clock_request,
            response_clock_response,
            repo_registry,
            value_bootstrap,
            clock_registry,
            value_contract,
            trusted_use_time=T0,
        )


def test_repository_exchange_rejects_attestor_substitution_and_unknown_failure() -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        repo_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    ) = repository_fixture(value_contract)
    response["attestor_implementation_identity"] = "0" * 64
    seal("repository_response", response, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_ATTESTOR_MISMATCH"):
        validate_repository_exchange(
            request,
            response,
            request_clock_request,
            request_clock_response,
            response_clock_request,
            response_clock_response,
            repo_registry,
            value_bootstrap,
            clock_registry,
            value_contract,
            trusted_use_time=T0,
        )

    failed = repository_response(request, repo_registry, value_contract)
    for field in (
        "repository_identity",
        "observed_source_commit",
        "observed_source_tree",
        "observed_clean_state",
        "source_root_observation_identity",
    ):
        failed[field] = None
    failed["observed_path_blob_bindings"] = []
    failed["observed_parent_relationships"] = []
    failed["status"] = "failure"
    failed["failure_code"] = "unregistered_failure"
    failed["registry_write_state"] = "collision"
    seal("repository_response", failed, value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_REPOSITORY_RESPONSE"):
        validate_runtime_record("repository_response", failed, value_contract)


def test_repository_expiration_boundary_is_half_open() -> None:
    value_contract = contract()
    (
        value_bootstrap,
        clock_registry,
        repo_registry,
        request,
        request_clock_request,
        request_clock_response,
        response,
        response_clock_request,
        response_clock_response,
    ) = repository_fixture(value_contract)
    with pytest.raises(OlympicsRuntimeBoundaryV007Error, match="V007_STALE_REPOSITORY"):
        validate_repository_exchange(
            request,
            response,
            request_clock_request,
            request_clock_response,
            response_clock_request,
            response_clock_response,
            repo_registry,
            value_bootstrap,
            clock_registry,
            value_contract,
            trusted_use_time=response["valid_until"],
        )


def test_record_schema_rejects_extra_missing_wrong_type_and_identity() -> None:
    value_contract = contract()
    value = replay_registry("clock", value_contract)
    attacks = []
    changed = copy.deepcopy(value)
    changed["extra"] = True
    attacks.append(changed)
    changed = copy.deepcopy(value)
    changed.pop("owner_uid")
    attacks.append(changed)
    changed = copy.deepcopy(value)
    changed["owner_uid"] = True
    seal("replay_registry", changed, value_contract)
    attacks.append(changed)
    changed = copy.deepcopy(value)
    changed["replay_registry_identity"] = "0" * 64
    attacks.append(changed)
    for attack in attacks:
        with pytest.raises(OlympicsRuntimeBoundaryV007Error):
            validate_runtime_record("replay_registry", attack, value_contract)


def test_socket_model_peer_mechanism_and_operator_binding_are_unambiguous() -> None:
    value = contract()
    assert value["socket_transport"]["model"] == "path_based_AF_UNIX_SOCK_STREAM_only"
    assert value["socket_transport"]["inherited_descriptor"] == "prohibited"
    assert value["peer_identity"]["mechanism"] == "getpeereid(3)_on_connected_AF_UNIX_socket"
    assert value["peer_identity"]["pid_binding"] == "not_available_not_claimed"
    assert value["runtime_identity_binding"]["implementation_source_paths"] == [
        "scripts/run_professional_strategy_olympics_v005.py",
        "src/aml/professional_strategy_olympics_operator_v001.py",
    ]
    assert "commit_and_tree_are_excluded" in value["runtime_identity_binding"]["self_reference_avoidance"]


def test_error_inventory_has_stable_unique_codes() -> None:
    errors = contract()["error_status_model"]["errors"]
    assert all(code.startswith("V007_") for code in errors)
    assert len(errors) == len(set(errors)) == 25


def test_cli_report_is_deterministic_across_hash_seeds_and_timezones() -> None:
    outputs: set[bytes] = set()
    for seed in ("0", "1", "8675309", "4294967295", "123456789", "999999999"):
        for timezone_name in ("UTC", "America/Denver", "Asia/Tokyo"):
            environment = {
                **os.environ,
                "PYTHONHASHSEED": seed,
                "TZ": timezone_name,
                "PYTHONPATH": str(ROOT / "src"),
            }
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(ROOT)],
                check=True,
                capture_output=True,
                env=environment,
            )
            assert completed.stderr == b""
            outputs.add(completed.stdout)
    assert outputs == {validation_report(ROOT)}


def test_v004_v005_v006_files_and_immutable_tag_are_unchanged() -> None:
    expected = {
        "config/professional_strategy_olympics_authorization_governance_v005.json": "afe13c93d8671600946a025040c2b45f9a1415fe9c4a8422f60d3b8c00c16075",
        "src/aml/professional_strategy_olympics_authorization_governance_v005.py": "9d2a75882e28217fb7165523afdb6d09ccabde6809ac248569e893cedb24054f",
        "config/professional_strategy_olympics_operator_interface_v006.json": "1123cb0b503f71fd0d6841dec82cb74bfa9e35712db1f5d8b1bd527219360630",
        "src/aml/professional_strategy_olympics_operator_interface_v006.py": "a712848db59814b84533f065418993f0b8273c0249e287f9b1efe5f1751aa558",
        "config/professional_strategy_olympics_execution_publication_v004.json": "fe178d6ae2131b96101fe71fa8adce64f1ca5fb61794db8b0a5104e4308c363e",
        "src/aml/professional_strategy_olympics_execution_publication_v004.py": "4edb69625e85b831eeea4bb4107b4b6fb97c101dc69a3bfe7db385efd61180a0",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    tag_object = subprocess.run(
        ["git", "rev-parse", "v0.1.1-research-baseline"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    tagged_commit = subprocess.run(
        ["git", "rev-parse", "v0.1.1-research-baseline^{}"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert tag_object == "746e147efd9bb09dedfdd4d2850f461e36d9f046"
    assert tagged_commit == "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"


def test_design_only_module_has_no_runtime_capability() -> None:
    paths = [
        ROOT / "src/aml/professional_strategy_olympics_runtime_boundary_v007.py",
        SCRIPT,
    ]
    combined = "\n".join(path.read_text() for path in paths)
    forbidden = (
        "import socket",
        "import requests",
        "urllib",
        "httpx",
        "aiohttp",
        "import subprocess",
        "consume_and_build(",
        "publish_once(",
        "run_professional_strategy_olympics_v005.py\"",
        "alpaca",
        "broker",
    )
    for token in forbidden:
        assert token not in combined
    assert not (ROOT / "scripts/run_professional_strategy_olympics_v005.py").exists()
