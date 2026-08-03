"""Pure validation for the design-only Olympics V007 runtime boundary.

V007 freezes schemas and relationships only.  This module performs no socket,
filesystem-arbitration, repository-attestation, authorization, or execution
operation.
"""

from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Sequence
import unicodedata

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_IDENTITY as V005_COMMAND_IDENTITY,
    CONTRACT_IDENTITY as V005_GOVERNANCE_IDENTITY,
    EVENT_PROJECTION_DOMAIN,
    OlympicsAuthorizationGovernanceV005Error,
    TIMESTAMP_FIELDS,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    parse_canonical_timestamp,
    strict_json_bytes,
    transition_spec,
    validate_artifact as validate_v005_artifact,
    validate_clock_bundle as validate_v005_clock_bundle,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    implementation_identity as v004_implementation_identity,
)
from aml.professional_strategy_olympics_operator_interface_v006 import (
    CONTRACT_IDENTITY as V006_OPERATOR_INTERFACE_IDENTITY,
    load_contract as load_v006_contract,
)


CONTRACT_PATH = "config/professional_strategy_olympics_runtime_boundary_v007.json"
SCHEMA = "aml.professional-strategy-olympics.runtime-boundary.v007"
VERSION = "professional-strategy-olympics-runtime-boundary-v007"
CONTRACT_DOMAIN = "aml.olympics.v007.runtime-boundary"
DESIGN_BASE_COMMIT = "303306b0d2eef4e6fd86ae88dc03ddea5585e210"
CONTRACT_IDENTITY = "a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45"
MAXIMUM_BYTES = 250_000

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REPOSITORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9._-]{0,99}$")
SCHEMA_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,159}$")

SECTION_NAMES = (
    "inheritance",
    "capability_scope",
    "canonicalization",
    "runtime_package",
    "runtime_schemas",
    "socket_transport",
    "peer_identity",
    "clock_session_replay",
    "repository_freshness_replay",
    "repository_trust",
    "runtime_identity_binding",
    "cross_version_binding",
    "error_status_model",
    "validation_manifest",
)
EXPECTED_SECTION_IDENTITIES = {
    "inheritance": "aa9f200c0c4fce52ab25cf566be73c03e3fc8a8334ea86a0b8c4924c34ec556a",
    "capability_scope": "1c6463c621a47b686b3f1468a5a535ff0518806b9d8e73b06e3267bf8caf2de9",
    "canonicalization": "e866c4636b955e9c1156ff2a929e31b5395f5e5b8ffba468b22d29826a2e0ddc",
    "runtime_package": "0309811ffcde9b453c75c96637ac590eb71dc42140f04c988dbd9ae326ea182e",
    "runtime_schemas": "4e82fd2b0cf99efce8c053f10eb673581c77d46aa7dde70b3675c99f7bca962a",
    "socket_transport": "2e26ee2e18b04dd2b42d42cbe1e1baddb63e403c1c5acdcdb72f406e14ac14f6",
    "peer_identity": "32400675c1a769a12b272c47ef2189c22cdff32455c8707916d35d0fb1d72823",
    "clock_session_replay": "6b91e36fa8ab327dc030cc9d479fad8c5933c8660c0daaee871b57b7a69793ed",
    "repository_freshness_replay": "b39aec2006aceed475d174af5d6693264e44d505a3e46a762664032453ede98b",
    "repository_trust": "c83aa57a1890ac9c364115d0e8129ac036daad01d18b78050cc0d0624524ce9a",
    "runtime_identity_binding": "03e1a35687b841aaddb1bf5742547f0bbf915b46e6fdbc17931cf42464b6453e",
    "cross_version_binding": "478fd9e7eab006a11b1ab259068a57ae7cd597e0941d1e80d026c20d4362e4da",
    "error_status_model": "330ff6bede7cedda5fe28fccd9324d0fef0ecd7641d0ad00d14b1e0724b40847",
    "validation_manifest": "495b81c9ad1cd3717315b472c33ddaf4775ac9a3665fa0d3b4b0ddcbc226320c",
}

ROOT_FIELDS = {
    "schema_version",
    "version",
    "prospective_as_of",
    "contract_identity",
    "section_identities",
    *SECTION_NAMES,
}
RUNTIME_RECORD_TYPES = (
    "runtime_package",
    "runtime_envelope",
    "clock_bootstrap",
    "clock_request",
    "clock_response",
    "registry_initialization",
    "replay_registry",
    "repository_request",
    "repository_response",
)
RECORD_INDEX_FIELDS = {
    "artifact_type",
    "artifact_identity",
    "relative_path",
    "canonical_bytes_sha256",
    "schema_version",
}
CLAIMS_NOT_MADE = (
    "github_account_authenticity",
    "github_repository_ownership",
    "host_kernel_integrity",
    "human_identity",
    "physical_disk_reality",
    "remote_freshness_without_separate_evidence",
    "tls_authenticity",
)


class OlympicsRuntimeBoundaryV007Error(ValueError):
    """A V007 contract or runtime record is malformed or inconsistent."""


def _reject(code: str, detail: str) -> None:
    raise OlympicsRuntimeBoundaryV007Error(f"{code}:{detail}")


def _timestamp(value: object, *, code: str = "V007_SCHEMA"):
    try:
        return parse_canonical_timestamp(value)
    except OlympicsAuthorizationGovernanceV005Error as exc:
        raise OlympicsRuntimeBoundaryV007Error(f"{code}:timestamp") from exc


def _exact_mapping(value: object, keys: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _reject("V007_SCHEMA", f"{name}_field_inventory")
    return value


def _valid_relative_path(value: object) -> bool:
    if type(value) is not str or not value or len(value.encode("ascii", errors="ignore")) > 1024:
        return False
    if not value.isascii() or value != value.lower() or "\x00" in value or value.endswith("/"):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _valid_absolute_path(value: object, *, socket_path: bool = False) -> bool:
    if type(value) is not str or unicodedata.normalize("NFC", value) != value or "\x00" in value:
        return False
    maximum = 103 if socket_path else 1024
    if not (1 <= len(value.encode("utf-8")) <= maximum) or not value.startswith("/") or value == "/" or value.endswith("/"):
        return False
    return all(part not in {"", ".", ".."} for part in PurePosixPath(value).parts[1:])


def _decode_base64(value: object) -> bytes:
    if type(value) is not str or len(value) > 2_666_668:
        _reject("V007_SCHEMA", "base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise OlympicsRuntimeBoundaryV007Error("V007_SCHEMA:base64") from exc
    if base64.b64encode(decoded).decode("ascii") != value or len(decoded) > 2_000_000:
        _reject("V007_SCHEMA", "base64")
    return decoded


def encode_frame(value: Mapping[str, object], *, maximum_bytes: int = 2_000_000) -> bytes:
    """Encode one V007 canonical length-prefixed frame without I/O."""
    payload = canonical_bytes(value)
    if not 0 < len(payload) <= maximum_bytes:
        _reject("V007_REQUEST_FRAME", "frame_size")
    return len(payload).to_bytes(4, "big") + payload


def decode_frame(frame: bytes, *, maximum_bytes: int = 2_000_000) -> dict[str, object]:
    """Decode exactly one complete V007 frame; trailing frames are rejected."""
    if type(frame) is not bytes or len(frame) < 4:
        _reject("V007_RESPONSE_FRAME", "prefix")
    declared = int.from_bytes(frame[:4], "big")
    if declared == 0 or declared > maximum_bytes:
        _reject("V007_RESPONSE_FRAME", "declared_size")
    if len(frame) != 4 + declared:
        _reject("V007_RESPONSE_FRAME", "partial_or_trailing")
    try:
        return strict_json_bytes(frame[4:], maximum_bytes=maximum_bytes)
    except ValueError as exc:
        raise OlympicsRuntimeBoundaryV007Error(
            "V007_RESPONSE_FRAME:canonical_payload"
        ) from exc


def _validate_record_index(value: object) -> None:
    if type(value) is not list or not value:
        _reject("V007_RUNTIME_REACHABILITY", "record_index")
    previous: tuple[bytes, bytes, bytes, bytes] | None = None
    seen_paths: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for entry in value:
        item = _exact_mapping(entry, RECORD_INDEX_FIELDS, "record_index_entry")
        artifact_type = item["artifact_type"]
        identity = item["artifact_identity"]
        relative_path = item["relative_path"]
        digest = item["canonical_bytes_sha256"]
        schema = item["schema_version"]
        if not all(type(part) is str for part in (artifact_type, identity, relative_path, digest, schema)):
            _reject("V007_RUNTIME_REACHABILITY", "record_index_type")
        if not TOKEN_RE.fullmatch(artifact_type) or not HASH_RE.fullmatch(identity) or not HASH_RE.fullmatch(digest):
            _reject("V007_RUNTIME_REACHABILITY", "record_index_identity")
        if not _valid_relative_path(relative_path) or not SCHEMA_RE.fullmatch(schema):
            _reject("V007_RUNTIME_REACHABILITY", "record_index_path_or_schema")
        key = tuple(part.encode("utf-8") for part in (artifact_type, identity, relative_path, schema))
        if previous is not None and key <= previous:
            _reject("V007_RUNTIME_REACHABILITY", "record_index_order")
        if relative_path in seen_paths or (artifact_type, identity) in seen_pairs:
            _reject("V007_RUNTIME_REACHABILITY", "record_index_duplicate")
        previous = key
        seen_paths.add(relative_path)
        seen_pairs.add((artifact_type, identity))


def _validate_primitive(rule: str, value: object) -> None:
    if rule.startswith("literal_int:"):
        expected = int(rule.split(":", 1)[1])
        if type(value) is not int or value != expected:
            _reject("V007_SCHEMA", "literal_integer")
        return
    if rule.startswith("literal:"):
        if value != rule.split(":", 1)[1]:
            _reject("V007_SCHEMA", "literal")
        return
    if rule.startswith("enum:"):
        if type(value) is not str or value not in rule.split(":", 1)[1].split("|"):
            _reject("V007_SCHEMA", "enum")
        return
    if rule.startswith("nullable:"):
        if value is not None:
            _validate_primitive(rule.split(":", 1)[1], value)
        return
    if rule.startswith("array:"):
        parts = rule.split(":")
        if len(parts) != 5:
            _reject("V007_SCHEMA", "array_rule")
        item_rule, minimum, maximum, order = parts[1], int(parts[2]), int(parts[3]), parts[4]
        if type(value) is not list or not minimum <= len(value) <= maximum:
            _reject("V007_SCHEMA", "array_bounds")
        for item in value:
            _validate_primitive(item_rule, item)
        if order == "sorted_unique":
            if value != sorted(value, key=lambda item: canonical_bytes(item)) or len(value) != len(set(value)):
                _reject("V007_SCHEMA", "array_order")
        elif order != "ordered":
            _reject("V007_SCHEMA", "array_order_rule")
        return
    if rule == "boolean":
        valid = type(value) is bool
    elif rule == "uint31":
        valid = type(value) is int and 0 <= value <= 2_147_483_647
    elif rule == "uint63":
        valid = type(value) is int and 0 <= value <= 9_223_372_036_854_775_807
    elif rule in {"identity", "nonce"}:
        valid = type(value) is str and HASH_RE.fullmatch(value) is not None
    elif rule == "git_oid":
        valid = type(value) is str and GIT_RE.fullmatch(value) is not None
    elif rule == "timestamp":
        try:
            _timestamp(value)
            valid = True
        except OlympicsRuntimeBoundaryV007Error:
            valid = False
    elif rule == "socket_path":
        valid = _valid_absolute_path(value, socket_path=True)
    elif rule == "absolute_path":
        valid = _valid_absolute_path(value)
    elif rule == "relative_path":
        valid = _valid_relative_path(value)
    elif rule in {"token", "artifact_type", "field_name"}:
        valid = type(value) is str and FIELD_RE.fullmatch(value) is not None
    elif rule == "repository_name":
        valid = type(value) is str and REPOSITORY_RE.fullmatch(value) is not None
    elif rule == "base64":
        _decode_base64(value)
        valid = True
    elif rule == "path_blob_binding":
        valid = False
        if type(value) is str and "=" in value:
            path, oid = value.rsplit("=", 1)
            valid = _valid_relative_path(path) and GIT_RE.fullmatch(oid) is not None
    elif rule == "parent_edge":
        valid = type(value) is str and re.fullmatch(r"[0-9a-f]{40}>[0-9a-f]{40}", value) is not None
    elif rule == "record_index":
        _validate_record_index(value)
        valid = True
    else:
        _reject("V007_SCHEMA", "unknown_rule")
        return
    if not valid:
        _reject("V007_SCHEMA", rule)


def record_identity(record_type: str, record: Mapping[str, object], contract: Mapping[str, object]) -> str:
    schema = contract["runtime_schemas"][record_type]
    identity_field = str(schema["identity_field"])
    projection = {key: item for key, item in record.items() if key != identity_field}
    return domain_hash(str(schema["identity_domain"]), projection)


def operator_implementation_identity(
    manifest: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    observed_files: Mapping[str, tuple[str, bytes]],
) -> str:
    """Validate the non-circular full-tree operator inventory and identity."""
    binding = contract["runtime_identity_binding"]
    fields = set(binding["future_manifest_fields"])
    _exact_mapping(manifest, fields, "operator_implementation_manifest")
    expected = {
        "schema_version": binding["future_manifest_schema"],
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v007_runtime_boundary_identity": CONTRACT_IDENTITY,
    }
    if any(manifest[key] != item for key, item in expected.items()):
        _reject("V007_IMPLEMENTATION_IDENTITY", "manifest_binding")
    files = manifest["implementation_files"]
    if type(files) is not list or not files:
        _reject("V007_IMPLEMENTATION_IDENTITY", "file_inventory")
    entries = []
    previous_path: bytes | None = None
    seen_paths: set[str] = set()
    for entry in files:
        item = _exact_mapping(
            entry,
            set(binding["implementation_file_entry_fields"]),
            "operator_implementation_file",
        )
        path = item["relative_path"]
        mode = item["git_mode"]
        if (
            not _valid_relative_path(path)
            or path == binding["future_manifest_path"]
            or mode not in {"100644", "100755"}
            or type(item["canonical_bytes_sha256"]) is not str
            or not HASH_RE.fullmatch(item["canonical_bytes_sha256"])
        ):
            _reject("V007_IMPLEMENTATION_IDENTITY", "file_entry")
        encoded_path = str(path).encode("utf-8")
        if (
            previous_path is not None
            and encoded_path <= previous_path
            or str(path) in seen_paths
        ):
            _reject("V007_IMPLEMENTATION_IDENTITY", "file_order")
        previous_path = encoded_path
        seen_paths.add(str(path))
        entries.append(dict(item))
    if not set(binding["implementation_entrypoint_paths"]) <= seen_paths:
        _reject("V007_IMPLEMENTATION_IDENTITY", "entrypoint_inventory")
    if set(observed_files) != seen_paths:
        _reject("V007_IMPLEMENTATION_IDENTITY", "observed_inventory")
    for item in entries:
        mode, raw = observed_files[str(item["relative_path"])]
        if (
            mode != item["git_mode"]
            or type(raw) is not bytes
            or hashlib.sha256(raw).hexdigest()
            != item["canonical_bytes_sha256"]
        ):
            _reject("V007_IMPLEMENTATION_IDENTITY", "observed_file")
    projection = {name: manifest[name] for name in binding["implementation_projection"]}
    identity = domain_hash(str(binding["implementation_identity_domain"]), projection)
    if manifest["implementation_identity"] != identity:
        _reject("V007_IMPLEMENTATION_IDENTITY", "identity")
    return identity


def validate_runtime_record(record_type: str, record: Mapping[str, object], contract: Mapping[str, object]) -> dict[str, object]:
    if record_type not in RUNTIME_RECORD_TYPES:
        _reject("V007_SCHEMA", "unknown_record_type")
    schema = contract["runtime_schemas"][record_type]
    fields = schema["fields"]
    _exact_mapping(record, set(fields), record_type)
    for name, rule in fields.items():
        _validate_primitive(str(rule), record[name])
    identity_field = str(schema["identity_field"])
    if record[identity_field] != record_identity(record_type, record, contract):
        _reject("V007_BOOTSTRAP_IDENTITY" if record_type == "clock_bootstrap" else "V007_RESPONSE_IDENTITY", record_type)
    _validate_runtime_semantics(record_type, record, contract)
    return dict(record)


def _validate_runtime_semantics(record_type: str, record: Mapping[str, object], contract: Mapping[str, object]) -> None:
    if record.get("runtime_boundary_identity", CONTRACT_IDENTITY) != CONTRACT_IDENTITY:
        _reject("V007_IMPLEMENTATION_IDENTITY", "runtime_boundary")
    if record_type == "clock_bootstrap":
        if (
            record["v005_governance_identity"] != V005_GOVERNANCE_IDENTITY
            or record["v005_command_identity"] != V005_COMMAND_IDENTITY
            or record["v006_operator_interface_identity"] != V006_OPERATOR_INTERFACE_IDENTITY
            or record["system_account_identity"] != record["verifier_actor_identity"]
        ):
            _reject("V007_VERIFIER_MISMATCH", "bootstrap_binding")
        expected_session = domain_hash(
            str(contract["clock_session_replay"]["session_identity_domain"]),
            {name: record[name] for name in contract["clock_session_replay"]["session_identity_projection"]},
        )
        if record["session_identity"] != expected_session:
            _reject("V007_BOOTSTRAP_IDENTITY", "session_identity")
    elif record_type == "clock_request":
        try:
            payload = strict_json_bytes(
                _decode_base64(record["event_projection_canonical_base64"])
            )
        except OlympicsAuthorizationGovernanceV005Error as exc:
            raise OlympicsRuntimeBoundaryV007Error(
                "V007_REQUEST_IDENTITY:event_projection_bytes"
            ) from exc
        if domain_hash(EVENT_PROJECTION_DOMAIN, payload) != record["event_projection_identity"]:
            _reject("V007_REQUEST_IDENTITY", "event_projection")
        repository_mapping = {
            "repository_request": ("repository_request", "requested_at"),
            "repository_response": ("repository_response", "observation_timestamp"),
        }
        expected = repository_mapping.get(str(record["transition_id"]))
        if expected is None:
            v005_contract = load_v005_contract(Path(__file__).resolve().parents[2])
            try:
                transition = transition_spec(v005_contract, str(record["transition_id"]))
                artifact_type = str(transition["new_artifact_type"])
                expected = (artifact_type, TIMESTAMP_FIELDS[artifact_type])
            except (KeyError, ValueError) as exc:
                raise OlympicsRuntimeBoundaryV007Error(
                    "V007_REQUEST_FRAME:transition"
                ) from exc
        if (record["bound_artifact_type"], record["bound_timestamp_field"]) != expected:
            _reject("V007_REQUEST_FRAME", "purpose_binding")
    elif record_type == "clock_response":
        _validate_clock_response_status(record, contract)
    elif record_type == "repository_request":
        expected = {
            "expected_repository_identity": "shelbygolddevtrader/attention-momentum-lab",
            "expected_command_identity": V005_COMMAND_IDENTITY,
            "expected_v004_contract_identity": V004_CONTRACT_IDENTITY,
            "expected_v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
            "expected_v005_governance_identity": V005_GOVERNANCE_IDENTITY,
            "expected_v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
            "expected_v007_runtime_boundary_identity": CONTRACT_IDENTITY,
        }
        if any(record[key] != value for key, value in expected.items()):
            _reject("V007_REPOSITORY_REQUEST", "frozen_binding")
    elif record_type == "repository_response":
        _validate_repository_response_status(record, contract)


def _validate_clock_response_status(
    record: Mapping[str, object], contract: Mapping[str, object]
) -> None:
    started = _timestamp(record["verification_started_at"])
    completed = _timestamp(record["verification_completed_at"])
    if completed < started or completed - started > timedelta(seconds=5):
        _reject("V007_VERIFICATION_WINDOW", "clock_response")
    payload_fields = tuple(
        key for key in record if key.startswith("v005_clock_")
    )
    if record["status"] == "success":
        if record["failure_code"] is not None or record["registry_write_state"] != "durable_unique" or record["verified_timestamp"] is None:
            _reject("V007_RESPONSE_FRAME", "success_matrix")
        if any(record[key] is None for key in payload_fields):
            _reject("V007_RESPONSE_FRAME", "success_payload")
        verified = _timestamp(record["verified_timestamp"])
        if not started <= verified <= completed:
            _reject("V007_VERIFICATION_WINDOW", "verified_timestamp")
    else:
        if record["failure_code"] is None or record["verified_timestamp"] is not None or any(record[key] is not None for key in payload_fields):
            _reject("V007_RESPONSE_FRAME", "non_success_matrix")
        if record["failure_code"] not in contract["clock_session_replay"]["failure_codes"]:
            _reject("V007_RESPONSE_FRAME", "failure_code")
        if record["status"] == "indeterminate" and record["registry_write_state"] != "indeterminate":
            _reject("V007_REGISTRY_WRITE_INDETERMINATE", "clock")


def _validate_repository_response_status(record: Mapping[str, object], contract: Mapping[str, object]) -> None:
    observed = (
        "repository_identity",
        "observed_source_commit",
        "observed_source_tree",
        "observed_clean_state",
        "source_root_observation_identity",
    )
    if tuple(record["claims_not_made"]) != CLAIMS_NOT_MADE:
        _reject("V007_UNSUPPORTED_TRUST_CLAIM", "claims_not_made")
    observed_at = _timestamp(record["observation_timestamp"])
    valid_from = _timestamp(record["valid_from"])
    valid_until = _timestamp(record["valid_until"])
    maximum = int(contract["repository_freshness_replay"]["maximum_age_seconds"])
    if valid_from != observed_at or valid_until != valid_from + timedelta(seconds=maximum):
        _reject("V007_STALE_REPOSITORY", "validity_equation")
    if record["status"] == "success":
        if record["failure_code"] is not None or record["registry_write_state"] != "durable_unique" or any(record[key] is None for key in observed):
            _reject("V007_REPOSITORY_RESPONSE", "success_matrix")
    else:
        if record["failure_code"] is None or any(record[key] is not None for key in observed) or record["observed_path_blob_bindings"] or record["observed_parent_relationships"]:
            _reject("V007_REPOSITORY_RESPONSE", "non_success_matrix")
        if record["failure_code"] not in contract["repository_freshness_replay"]["failure_codes"]:
            _reject("V007_REPOSITORY_RESPONSE", "failure_code")
        if record["status"] == "indeterminate" and record["registry_write_state"] != "indeterminate":
            _reject("V007_REGISTRY_WRITE_INDETERMINATE", "repository")


def repository_event_projection_identity(
    record_type: str,
    record: Mapping[str, object],
    contract: Mapping[str, object],
) -> str:
    if record_type not in {"repository_request", "repository_response"}:
        _reject("V007_REPOSITORY_REQUEST", "projection_type")
    identity_field = str(contract["runtime_schemas"][record_type]["identity_field"])
    timestamp_field = (
        "requested_at" if record_type == "repository_request" else "observation_timestamp"
    )
    excluded = {
        identity_field,
        timestamp_field,
        "clock_request_envelope_identity",
        "clock_response_envelope_identity",
    }
    projection = {key: item for key, item in record.items() if key not in excluded}
    return domain_hash(
        EVENT_PROJECTION_DOMAIN,
        {"artifact_type": record_type, "projection": projection},
    )


def validate_clock_exchange(
    request: Mapping[str, object],
    response: Mapping[str, object],
    bootstrap: Mapping[str, object],
    registry: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    previous_verified_timestamp: str | None = None,
) -> None:
    request = validate_runtime_record("clock_request", request, contract)
    response = validate_runtime_record("clock_response", response, contract)
    bootstrap = validate_runtime_record("clock_bootstrap", bootstrap, contract)
    registry = validate_runtime_record("replay_registry", registry, contract)
    if registry["registry_kind"] != "clock" or registry["replay_registry_identity"] != bootstrap["clock_replay_registry_identity"]:
        _reject("V007_REGISTRY_UNAVAILABLE", "clock_registry")
    if (
        registry["owner_service_identity"] != bootstrap["verifier_service_identity"]
        or registry["owner_implementation_identity"]
        != bootstrap["verifier_implementation_identity"]
        or registry["owner_uid"] != bootstrap["expected_peer_uid"]
        or registry["owner_gid"] != bootstrap["expected_peer_gid"]
    ):
        _reject("V007_REGISTRY_CONTINUITY", "clock_registry_owner")
    pairs = (
        (response["request_identity"], request["request_identity"]),
        (response["request_nonce"], request["request_nonce"]),
        (response["session_identity"], request["session_identity"]),
        (response["sequence_number"], request["sequence_number"]),
        (request["session_identity"], bootstrap["session_identity"]),
        (request["authorization_identity"], bootstrap["authorization_identity"]),
        (request["operator_implementation_identity"], bootstrap["operator_implementation_identity"]),
        (response["verifier_actor_identity"], bootstrap["verifier_actor_identity"]),
        (response["verifier_service_identity"], bootstrap["verifier_service_identity"]),
        (response["verifier_implementation_identity"], bootstrap["verifier_implementation_identity"]),
        (response["clock_replay_registry_identity"], registry["replay_registry_identity"]),
    )
    if any(left != right for left, right in pairs):
        _reject("V007_VERIFIER_MISMATCH", "clock_exchange")
    if response["request_nonce"] == response["evidence_nonce"]:
        _reject("V007_NONCE_COLLISION", "clock")
    if previous_verified_timestamp is not None and response["status"] == "success":
        if _timestamp(response["verified_timestamp"]) < _timestamp(
            previous_verified_timestamp, code="V007_STALE_CLOCK"
        ):
            _reject("V007_CLOCK_ROLLBACK", "clock_exchange")
    if response["status"] == "success":
        v005_contract = load_v005_contract(Path(__file__).resolve().parents[2])
        artifact_specs = (
            ("clock_request", "v005_clock_request_base64", "v005_clock_request_identity"),
            ("clock_evidence", "v005_clock_evidence_base64", "v005_clock_evidence_identity"),
            ("clock_verifier_attestation", "v005_clock_verifier_attestation_base64", "v005_clock_verifier_attestation_identity"),
            ("clock_attestation", "v005_clock_attestation_base64", "v005_clock_attestation_identity"),
        )
        artifacts: dict[str, dict[str, object]] = {}
        try:
            for artifact_type, payload_field, identity_field in artifact_specs:
                artifact = strict_json_bytes(_decode_base64(response[payload_field]))
                validate_v005_artifact(artifact, artifact_type, v005_contract)
                schema = v005_contract["artifact_schemas"][artifact_type]
                if artifact[schema["identity_field"]] != response[identity_field]:
                    _reject("V007_RESPONSE_IDENTITY", artifact_type)
                artifacts[artifact_type] = artifact
            validate_v005_clock_bundle(
                artifacts["clock_request"],
                artifacts["clock_evidence"],
                artifacts["clock_verifier_attestation"],
                artifacts["clock_attestation"],
                v005_contract,
            )
        except OlympicsAuthorizationGovernanceV005Error as exc:
            raise OlympicsRuntimeBoundaryV007Error(
                "V007_RESPONSE_IDENTITY:v005_clock_bundle"
            ) from exc
        expected_v005_purpose = (
            ("activation", "activated_at")
            if request["bound_artifact_type"]
            in {"repository_request", "repository_response"}
            else (
                request["bound_artifact_type"],
                request["bound_timestamp_field"],
            )
        )
        if (
            artifacts["clock_request"]["request_nonce"]
            != response["evidence_nonce"]
            or artifacts["clock_verifier_attestation"][
                "verifier_account_identity"
            ]
            != bootstrap["system_account_identity"]
            or (
                artifacts["clock_attestation"]["bound_artifact_type"],
                artifacts["clock_attestation"]["bound_timestamp_field"],
            )
            != expected_v005_purpose
            or artifacts["clock_attestation"][
                "bound_event_projection_identity"
            ]
            != request["event_projection_identity"]
            or artifacts["clock_attestation"]["canonical_utc_timestamp"]
            != response["verified_timestamp"]
        ):
            _reject("V007_RESPONSE_IDENTITY", "v005_clock_request_binding")


def validate_repository_exchange(
    request: Mapping[str, object],
    response: Mapping[str, object],
    request_clock_request: Mapping[str, object],
    request_clock_response: Mapping[str, object],
    response_clock_request: Mapping[str, object],
    response_clock_response: Mapping[str, object],
    repository_registry: Mapping[str, object],
    clock_bootstrap: Mapping[str, object],
    clock_registry: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    trusted_use_time: str,
) -> None:
    request = validate_runtime_record("repository_request", request, contract)
    response = validate_runtime_record("repository_response", response, contract)
    request_clock_request = validate_runtime_record(
        "clock_request", request_clock_request, contract
    )
    request_clock_response = validate_runtime_record(
        "clock_response", request_clock_response, contract
    )
    response_clock_response = validate_runtime_record(
        "clock_response", response_clock_response, contract
    )
    response_clock_request = validate_runtime_record(
        "clock_request", response_clock_request, contract
    )
    repository_registry = validate_runtime_record(
        "replay_registry", repository_registry, contract
    )
    if (
        repository_registry["registry_kind"] != "repository"
        or request["repository_replay_registry_identity"]
        != repository_registry["replay_registry_identity"]
        or response["repository_replay_registry_identity"]
        != repository_registry["replay_registry_identity"]
    ):
        _reject("V007_REGISTRY_UNAVAILABLE", "repository_registry")
    if (
        repository_registry["owner_service_identity"]
        != request["expected_attestor_service_identity"]
        or repository_registry["owner_implementation_identity"]
        != request["expected_attestor_implementation_identity"]
        or repository_registry["owner_uid"] != request["expected_attestor_uid"]
        or repository_registry["owner_gid"] != request["expected_attestor_gid"]
    ):
        _reject("V007_REGISTRY_CONTINUITY", "repository_registry_owner")
    validate_clock_exchange(
        request_clock_request,
        request_clock_response,
        clock_bootstrap,
        clock_registry,
        contract,
    )
    validate_clock_exchange(
        response_clock_request,
        response_clock_response,
        clock_bootstrap,
        clock_registry,
        contract,
        previous_verified_timestamp=str(request_clock_response["verified_timestamp"]),
    )
    if response["repository_request_identity"] != request["repository_request_identity"] or response["request_nonce"] != request["request_nonce"]:
        _reject("V007_REPOSITORY_REPLAY", "request_response")
    if response["request_nonce"] == response["attestation_nonce"]:
        _reject("V007_NONCE_COLLISION", "repository")
    if (
        response["attestor_actor_identity"]
        != request["expected_attestor_actor_identity"]
        or response["attestor_service_identity"]
        != request["expected_attestor_service_identity"]
        or response["attestor_implementation_identity"]
        != request["expected_attestor_implementation_identity"]
    ):
        _reject("V007_ATTESTOR_MISMATCH", "repository")
    clock_bindings = (
        (
            request["authorization_identity"],
            request_clock_request["authorization_identity"],
        ),
        (
            request["authorization_identity"],
            response_clock_request["authorization_identity"],
        ),
        (
            request["authoritative_run_identity"],
            request_clock_request["authoritative_run_identity"],
        ),
        (
            request["authoritative_run_identity"],
            response_clock_request["authoritative_run_identity"],
        ),
        (
            request["expected_operator_implementation_identity"],
            request_clock_request["operator_implementation_identity"],
        ),
        (
            request["expected_operator_implementation_identity"],
            response_clock_request["operator_implementation_identity"],
        ),
        (
            request["clock_request_envelope_identity"],
            request_clock_request["request_identity"],
        ),
        (
            request["clock_response_envelope_identity"],
            request_clock_response["response_identity"],
        ),
        (
            response["clock_request_envelope_identity"],
            response_clock_request["request_identity"],
        ),
        (
            response["clock_response_envelope_identity"],
            response_clock_response["response_identity"],
        ),
        (request["requested_at"], request_clock_response["verified_timestamp"]),
        (
            response["observation_timestamp"],
            response_clock_response["verified_timestamp"],
        ),
    )
    if (
        any(left != right for left, right in clock_bindings)
        or request_clock_response["status"] != "success"
        or response_clock_response["status"] != "success"
    ):
        _reject("V007_STALE_REPOSITORY", "clock_binding")
    if request_clock_request["event_projection_identity"] != repository_event_projection_identity(
        "repository_request", request, contract
    ):
        _reject("V007_REPOSITORY_REQUEST", "clock_projection")
    if response_clock_request["event_projection_identity"] != repository_event_projection_identity(
        "repository_response", response, contract
    ):
        _reject("V007_REPOSITORY_RESPONSE", "clock_projection")
    use_time = _timestamp(trusted_use_time, code="V007_STALE_REPOSITORY")
    if not _timestamp(response["valid_from"]) <= use_time < _timestamp(
        response["valid_until"]
    ):
        _reject("V007_STALE_REPOSITORY", "use_time")
    if response["status"] == "success":
        expected = (
            (response["repository_identity"], request["expected_repository_identity"]),
            (response["observed_source_commit"], request["expected_source_commit"]),
            (response["observed_source_tree"], request["expected_source_tree"]),
            (response["observed_path_blob_bindings"], request["required_path_blob_bindings"]),
            (response["observed_parent_relationships"], request["required_parent_relationships"]),
            (response["observed_clean_state"], True),
        )
        if any(left != right for left, right in expected):
            _reject("V007_REPOSITORY_RESPONSE", "observed_binding")


def validate_runtime_graph(
    records: Mapping[str, Sequence[Mapping[str, object]]],
    contract: Mapping[str, object],
    *,
    trusted_use_time: str,
) -> dict[str, Mapping[str, object]]:
    required = set(RUNTIME_RECORD_TYPES)
    if set(records) != required or any(not values for values in records.values()):
        _reject("V007_RUNTIME_REACHABILITY", "record_types")
    multiple = {
        "clock_request",
        "clock_response",
        "registry_initialization",
        "replay_registry",
    }
    if any(len(values) != (2 if name in multiple else 1) for name, values in records.items()):
        _reject("V007_RUNTIME_REACHABILITY", "record_count")
    validated: dict[str, Mapping[str, object]] = {}
    all_identities: set[str] = set()
    for name, values in records.items():
        for index, value in enumerate(values):
            record = validate_runtime_record(name, value, contract)
            identity_field = contract["runtime_schemas"][name]["identity_field"]
            identity = str(record[identity_field])
            if identity in all_identities:
                _reject("V007_RUNTIME_REACHABILITY", "duplicate_identity")
            all_identities.add(identity)
            validated[f"{name}:{index}"] = record
    package = validated["runtime_package:0"]
    envelope = validated["runtime_envelope:0"]
    bootstrap = validated["clock_bootstrap:0"]
    request = validated["repository_request:0"]
    response = validated["repository_response:0"]
    clock_requests = [validated["clock_request:0"], validated["clock_request:1"]]
    clock_responses = [validated["clock_response:0"], validated["clock_response:1"]]
    initializations = [
        validated["registry_initialization:0"],
        validated["registry_initialization:1"],
    ]
    registries = [validated["replay_registry:0"], validated["replay_registry:1"]]
    initialization_by_kind = {
        str(item["registry_kind"]): item for item in initializations
    }
    registry_by_kind = {str(item["registry_kind"]): item for item in registries}
    if (
        set(registry_by_kind) != {"clock", "repository"}
        or set(initialization_by_kind) != {"clock", "repository"}
    ):
        _reject("V007_RUNTIME_REACHABILITY", "registry_kind")
    for kind, registry in registry_by_kind.items():
        initialization = initialization_by_kind[kind]
        checks = (
            (registry["initialization_marker_identity"], initialization["registry_initialization_identity"]),
            (registry["registry_epoch_identity"], initialization["registry_epoch_identity"]),
            (registry["canonical_root"], initialization["canonical_root"]),
            (registry["owner_service_identity"], initialization["owner_service_identity"]),
            (registry["owner_implementation_identity"], initialization["owner_implementation_identity"]),
            (registry["owner_uid"], initialization["owner_uid"]),
            (registry["owner_gid"], initialization["owner_gid"]),
            (registry["directory_mode"], initialization["directory_mode"]),
            (registry["file_mode"], initialization["file_mode"]),
            (registry["filesystem"], initialization["filesystem"]),
        )
        if any(left != right for left, right in checks):
            _reject("V007_REGISTRY_CONTINUITY", f"{kind}_registry_initialization")
    request_by_identity = {str(item["request_identity"]): item for item in clock_requests}
    response_by_identity = {str(item["response_identity"]): item for item in clock_responses}
    if (
        len(request_by_identity) != 2
        or len(response_by_identity) != 2
        or sorted(int(item["sequence_number"]) for item in clock_requests) != [0, 1]
        or len({str(item["request_nonce"]) for item in clock_requests}) != 2
        or len({str(item["evidence_nonce"]) for item in clock_responses}) != 2
        or {str(item["session_identity"]) for item in clock_requests}
        != {str(bootstrap["session_identity"])}
    ):
        _reject("V007_RUNTIME_REACHABILITY", "clock_sequence_or_nonce")
    all_clock_nonces = {
        str(bootstrap["session_nonce"]),
        *(str(item["request_nonce"]) for item in clock_requests),
        *(str(item["evidence_nonce"]) for item in clock_responses),
    }
    if len(all_clock_nonces) != 5:
        _reject("V007_NONCE_COLLISION", "clock_registry_scope")
    request_clock_response = response_by_identity.get(
        str(request["clock_response_envelope_identity"])
    )
    response_clock_response = response_by_identity.get(
        str(response["clock_response_envelope_identity"])
    )
    if request_clock_response is None or response_clock_response is None:
        _reject("V007_RUNTIME_REACHABILITY", "repository_clock_response")
    request_clock_request = request_by_identity.get(
        str(request_clock_response["request_identity"])
    )
    response_clock_request = request_by_identity.get(
        str(response_clock_response["request_identity"])
    )
    if request_clock_request is None or response_clock_request is None:
        _reject("V007_RUNTIME_REACHABILITY", "repository_clock_request")
    sequenced_requests = sorted(
        clock_requests, key=lambda item: int(item["sequence_number"])
    )
    response_for_first = next(
        item
        for item in clock_responses
        if item["request_identity"] == sequenced_requests[0]["request_identity"]
    )
    if (
        sequenced_requests[0]["prior_clock_attestation_identity"]
        != bootstrap["initial_clock_attestation_identity"]
        or sequenced_requests[1]["prior_clock_attestation_identity"]
        != response_for_first["v005_clock_attestation_identity"]
    ):
        _reject("V007_CLOCK_ROLLBACK", "prior_attestation_chain")
    checks = (
        (package["runtime_envelope_identity"], envelope["runtime_envelope_identity"]),
        (envelope["clock_bootstrap_identity"], bootstrap["clock_bootstrap_identity"]),
        (envelope["repository_request_identity"], request["repository_request_identity"]),
        (envelope["repository_response_identity"], response["repository_response_identity"]),
        (envelope["clock_replay_registry_identity"], registry_by_kind["clock"]["replay_registry_identity"]),
        (envelope["repository_replay_registry_identity"], registry_by_kind["repository"]["replay_registry_identity"]),
        (
            request["clock_request_envelope_identity"],
            request_clock_request["request_identity"],
        ),
        (
            response["clock_request_envelope_identity"],
            response_clock_request["request_identity"],
        ),
        (
            request_clock_request["event_projection_identity"],
            repository_event_projection_identity("repository_request", request, contract),
        ),
        (
            response_clock_request["event_projection_identity"],
            repository_event_projection_identity("repository_response", response, contract),
        ),
    )
    shared_fields = ("authorization_identity", "authorized_source_commit", "authorized_source_tree", "authoritative_run_identity", "operator_implementation_identity")
    if any(left != right for left, right in checks):
        _reject("V007_RUNTIME_REACHABILITY", "edge")
    for field in shared_fields:
        if field in envelope and package[field] != envelope[field]:
            _reject("V007_RUNTIME_REACHABILITY", f"shared_{field}")
    cross_record_checks = (
        (package["authorization_identity"], bootstrap["authorization_identity"]),
        (package["authorization_identity"], request["authorization_identity"]),
        (package["authoritative_run_identity"], request["authoritative_run_identity"]),
        (package["operator_implementation_identity"], bootstrap["operator_implementation_identity"]),
        (package["operator_implementation_identity"], request["expected_operator_implementation_identity"]),
        (package["authorized_source_commit"], request["expected_source_commit"]),
        (package["authorized_source_tree"], request["expected_source_tree"]),
        (envelope["v005_governance_identity"], V005_GOVERNANCE_IDENTITY),
        (envelope["v005_command_identity"], V005_COMMAND_IDENTITY),
        (envelope["v006_operator_interface_identity"], V006_OPERATOR_INTERFACE_IDENTITY),
        (
            package["v006_operator_package_identity"],
            envelope["v006_operator_package_identity"],
        ),
    )
    if any(left != right for left, right in cross_record_checks):
        _reject("V007_RUNTIME_REACHABILITY", "cross_record_binding")

    authorization_identity = str(package["authorization_identity"])
    expected_paths = {
        ("runtime_envelope", str(envelope["runtime_envelope_identity"])):
            f"runtime/{authorization_identity}/runtime_envelope.json",
        ("clock_bootstrap", str(bootstrap["clock_bootstrap_identity"])):
            f"runtime/{authorization_identity}/clock_bootstrap.json",
        ("repository_request", str(request["repository_request_identity"])):
            f"runtime/{authorization_identity}/repository_request.json",
        ("repository_response", str(response["repository_response_identity"])):
            f"runtime/{authorization_identity}/repository_response.json",
    }
    for registry in registries:
        expected_paths[("replay_registry", str(registry["replay_registry_identity"]))] = (
            f"runtime/{authorization_identity}/{registry['registry_kind']}_replay_registry.json"
        )
    for initialization in initializations:
        expected_paths[
            (
                "registry_initialization",
                str(initialization["registry_initialization_identity"]),
            )
        ] = (
            f"runtime/{authorization_identity}/"
            f"{initialization['registry_kind']}_registry_initialization.json"
        )
    for clock_request_record in clock_requests:
        expected_paths[("clock_request", str(clock_request_record["request_identity"]))] = (
            f"runtime/{authorization_identity}/clock_requests/"
            f"{clock_request_record['bound_artifact_type']}.json"
        )
    for clock_response_record in clock_responses:
        bound_request = request_by_identity.get(str(clock_response_record["request_identity"]))
        if bound_request is None:
            _reject("V007_RUNTIME_REACHABILITY", "orphan_clock_response")
        expected_paths[("clock_response", str(clock_response_record["response_identity"]))] = (
            f"runtime/{authorization_identity}/clock_responses/"
            f"{bound_request['bound_artifact_type']}.json"
        )

    indexed = {
        (str(item["artifact_type"]), str(item["artifact_identity"]))
        for item in package["record_index"]
    }
    if any(item[0] == "runtime_package" for item in indexed):
        _reject("V007_RUNTIME_REACHABILITY", "self_index")
    if indexed != set(expected_paths):
        _reject("V007_RUNTIME_REACHABILITY", "index_inventory")
    record_by_key = {
        (
            key.split(":", 1)[0],
            str(record[contract["runtime_schemas"][key.split(":", 1)[0]]["identity_field"]]),
        ): record
        for key, record in validated.items()
        if not key.startswith("runtime_package:")
    }
    for item in package["record_index"]:
        key = (str(item["artifact_type"]), str(item["artifact_identity"]))
        record = record_by_key[key]
        schema = contract["runtime_schemas"][key[0]]
        if (
            item["relative_path"] != expected_paths[key]
            or item["schema_version"] != schema["schema_version"]
            or item["canonical_bytes_sha256"]
            != hashlib.sha256(canonical_bytes(record)).hexdigest()
        ):
            _reject("V007_RUNTIME_REACHABILITY", "index_metadata")
    validate_repository_exchange(
        request,
        response,
        request_clock_request,
        request_clock_response,
        response_clock_request,
        response_clock_response,
        registry_by_kind["repository"],
        bootstrap,
        registry_by_kind["clock"],
        contract,
        trusted_use_time=trusted_use_time,
    )
    return validated


def _validate_schema_definitions(value: Mapping[str, object]) -> None:
    schemas = _exact_mapping(value["runtime_schemas"], set(RUNTIME_RECORD_TYPES), "runtime_schemas")
    domains: set[str] = set()
    for name, schema_value in schemas.items():
        schema = _exact_mapping(schema_value, {"schema_version", "identity_field", "identity_domain", "fields"}, f"schema_{name}")
        fields = schema["fields"]
        if not isinstance(fields, Mapping) or set(fields) != set(fields.keys()) or schema["identity_field"] not in fields:
            _reject("V007_SCHEMA", f"schema_fields_{name}")
        if fields["schema_version"] != f"literal:{schema['schema_version']}" or fields[schema["identity_field"]] != "identity":
            _reject("V007_SCHEMA", f"schema_identity_{name}")
        if schema["identity_domain"] in domains or not str(schema["identity_domain"]).startswith("aml.olympics.v007."):
            _reject("V007_SCHEMA", f"schema_domain_{name}")
        domains.add(str(schema["identity_domain"]))
        for rule in fields.values():
            if type(rule) is not str or not rule:
                _reject("V007_SCHEMA", f"schema_rule_{name}")


def validate_contract(value: Mapping[str, object], root: Path | None = None) -> dict[str, object]:
    _exact_mapping(value, ROOT_FIELDS, "root")
    if value["schema_version"] != SCHEMA or value["version"] != VERSION:
        _reject("V007_SCHEMA", "version")
    _timestamp(value["prospective_as_of"])
    inheritance = value["inheritance"]
    expected_inheritance = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "relationship": "additive_successor_clarifying_only_the_V006_runtime_boundary",
        "precedence": "V007_controls_runtime_package_bootstrap_transport_rpc_replay_repository_attestation_and_operator_implementation_binding;all_other_V006_rules_remain_normative",
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
    }
    if inheritance != expected_inheritance:
        _reject("V007_SCHEMA", "inheritance")
    scope = value["capability_scope"]
    if not isinstance(scope, Mapping) or scope.get("design_only") is not True or scope.get("runtime_contract_frozen") is not True or any(item is not False for key, item in scope.items() if key not in {"design_only", "runtime_contract_frozen"}):
        _reject("V007_SCHEMA", "capability_scope")
    if value["socket_transport"]["model"] != "path_based_AF_UNIX_SOCK_STREAM_only" or value["socket_transport"]["inherited_descriptor"] != "prohibited":
        _reject("V007_SOCKET_PATH", "ambiguous_model")
    if value["peer_identity"]["mechanism"] != "getpeereid(3)_on_connected_AF_UNIX_socket" or value["peer_identity"]["pid_binding"] != "not_available_not_claimed":
        _reject("V007_PEER_IDENTITY", "mechanism")
    if tuple(value["repository_trust"]["claims_not_made_exact"]) != CLAIMS_NOT_MADE:
        _reject("V007_UNSUPPORTED_TRUST_CLAIM", "contract")
    _validate_schema_definitions(value)
    section_identities = _exact_mapping(value["section_identities"], set(SECTION_NAMES), "section_identities")
    for name in SECTION_NAMES:
        actual = domain_hash(f"aml.olympics.v007.section.{name}", value[name])
        if section_identities[name] != EXPECTED_SECTION_IDENTITIES[name] or actual != EXPECTED_SECTION_IDENTITIES[name]:
            _reject("V007_SCHEMA", f"section_identity_{name}")
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    if value["contract_identity"] != CONTRACT_IDENTITY or domain_hash(CONTRACT_DOMAIN, projection) != CONTRACT_IDENTITY:
        _reject("V007_SCHEMA", "contract_identity")
    if root is not None:
        load_v005_contract(root)
        load_v006_contract(root)
        if v004_implementation_identity(root) != V004_IMPLEMENTATION_IDENTITY:
            _reject("V007_SCHEMA", "v004_implementation")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    try:
        raw = (root / CONTRACT_PATH).read_bytes()
    except OSError as exc:
        raise OlympicsRuntimeBoundaryV007Error("V007_SCHEMA:contract_missing") from exc
    try:
        value = strict_json_bytes(raw, maximum_bytes=MAXIMUM_BYTES)
    except ValueError as exc:
        raise OlympicsRuntimeBoundaryV007Error("V007_SCHEMA:contract_bytes") from exc
    return validate_contract(value, root)


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_bytes(validate_contract(value))


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    report = {
        "authorization_present": False,
        "clock_verifier_present": False,
        "design_contract_valid": True,
        "execution_permitted": False,
        "operator_implementation_present": False,
        "repository_attestor_present": False,
        "runtime_boundary_identity": CONTRACT_IDENTITY,
        "status": contract["validation_manifest"]["status"],
    }
    return canonical_bytes(report)
