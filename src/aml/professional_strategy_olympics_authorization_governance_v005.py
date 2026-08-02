"""Pure, design-only validation for Olympics authorization governance V005.

This module parses canonical records and validates synthetic evidence bundles. It
does not contain network, filesystem mutation, authorization creation or
consumption, subprocess, dynamic execution, or Olympics runner capabilities.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Mapping, Sequence


CONTRACT_PATH = "config/professional_strategy_olympics_authorization_governance_v005.json"
SCHEMA = "aml.professional-strategy-olympics.authorization-governance.v005"
VERSION = "professional-strategy-olympics-authorization-governance-v005"
CONTRACT_IDENTITY = "9408e2b9dcb4e14534f4f7699ea26fe0846f4a2d3f2ad416ea11758a34f2223a"
COMMAND_IDENTITY = "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb"
DESIGN_BASE_COMMIT = "2f5390a844b9187b92da124a77173669f1b3f536"
V004_CONTRACT_IDENTITY = "0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053"
V004_IMPLEMENTATION_IDENTITY = "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4"
TAG_NAME = "v0.1.1-research-baseline"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
VALIDITY_SECONDS = 259_200
GOVERNANCE_DOMAIN = "aml.olympics.v005.governance"
COMMAND_DOMAIN = "aml.olympics.v005.command"
EVENT_PROJECTION_DOMAIN = "aml.olympics.v005.event-projection"
MAX_JSON_BYTES = 2_000_000
MAX_JSON_DEPTH = 40

EXPECTED_TRANSITIONS = {
    "proposal_approved": ("proposed", "approved", "authorization_author", False, "proposal", "human_approval", "not_applicable"),
    "authorization_activated": ("approved", "active_unconsumed", "operator", False, "human_approval", "activation", "issued_at<=operation<expires_at"),
    "consumption_decision_won": ("active_unconsumed", "claiming", "operator", False, "activation", "authorization_decision", "issued_at<=operation<expires_at"),
    "consumption_claim_durable": ("claiming", "consumed", "operator", False, "authorization_decision", "consumption_claim", "issued_at<=operation<expires_at"),
    "build_started": ("consumed", "build_started", "operator", False, "consumption_claim", "build_start", "issued_at<=operation<expires_at"),
    "run_started": ("build_started", "run_started", "operator", False, "build_start", "run_start", "issued_at<=operation<expires_at"),
    "run_succeeded": ("run_started", "run_succeeded", "operator", False, "run_start", "lifecycle_terminal", "issued_at<=operation<expires_at"),
    "run_failed": ("run_started", "run_failed", "operator", False, "run_start", "lifecycle_terminal", "issued_at<=operation<expires_at"),
    "build_failed": ("build_started", "run_failed", "operator", False, "build_start", "lifecycle_terminal", "issued_at<=operation<expires_at"),
    "success_archive_started": ("run_succeeded", "archive_pending", "archive_custodian", False, "lifecycle_terminal", "archive_pending", "issued_at<=operation<expires_at"),
    "failure_archive_started": ("run_failed", "archive_pending", "archive_custodian", False, "lifecycle_terminal", "archive_pending", "issued_at<=operation<expires_at"),
    "archive_completed": ("archive_pending", "archived", "archive_custodian", True, "archive_pending", "completion_marker", "issued_at<=operation<expires_at"),
    "supersession_decision_won": ("active_unconsumed", "superseding", "superseding_authorization_author", False, "activation", "authorization_decision", "issued_at<=operation<expires_at"),
    "supersession_durable": ("superseding", "superseded", "superseding_authorization_author", True, "authorization_decision", "supersession", "issued_at<=operation<expires_at"),
    "authorization_expired": ("active_unconsumed", "expired", "system", True, "activation", "expiration", "operation==expires_at"),
    "proposal_rejected": ("proposed", "rejected", "reviewer", True, "proposal", "rejection", "not_applicable"),
    "preflight_rejected": ("approved", "rejected", "operator", True, "human_approval", "rejection", "issued_at<=operation<expires_at"),
    "claim_indeterminate": ("claiming", "indeterminate", "system", False, "authorization_decision", "indeterminate", "issued_at<=operation<expires_at"),
    "build_indeterminate": ("consumed", "indeterminate", "system", False, "consumption_claim", "indeterminate", "issued_at<=operation<expires_at"),
    "run_indeterminate": ("run_started", "indeterminate", "system", False, "run_start", "indeterminate", "issued_at<=operation<expires_at"),
    "archive_indeterminate": ("archive_pending", "indeterminate", "system", False, "archive_pending", "indeterminate", "issued_at<=operation<expires_at"),
    "claim_recovered": ("indeterminate", "consumed", "operator", False, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
    "build_recovered": ("indeterminate", "build_started", "operator", False, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
    "run_success_recovered": ("indeterminate", "run_succeeded", "operator", False, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
    "run_failure_recovered": ("indeterminate", "run_failed", "operator", False, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
    "archive_recovered": ("indeterminate", "archive_pending", "archive_custodian", False, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
    "archive_completion_recovered": ("indeterminate", "archived", "archive_custodian", True, "indeterminate", "recovery", "issued_at<=operation<expires_at"),
}

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
LOGIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ARTIFACT_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
BASE64_RE = re.compile(r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")
DOMAIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,127}$")
SCHEMA_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,159}$")
STATE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class OlympicsAuthorizationGovernanceV005Error(ValueError):
    """A V005 schema, identity, or governance invariant failed."""


def _reject(message: str) -> None:
    raise OlympicsAuthorizationGovernanceV005Error(message)


def _walk_json(value: object, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        _reject("JSON nesting exceeds forty levels")
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is float:
        _reject("floats are prohibited")
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value:
            _reject("all strings must be Unicode NFC")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise OlympicsAuthorizationGovernanceV005Error("invalid Unicode") from exc
        return
    if type(value) is list:
        for item in value:
            _walk_json(item, depth=depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _reject("JSON object keys must be strings")
            _walk_json(key, depth=depth + 1)
            _walk_json(item, depth=depth + 1)
        return
    _reject("unsupported JSON value")


def canonical_bytes(value: object) -> bytes:
    """Canonical UTF-8 JSON: ASCII escapes, compact sorted keys, and one LF."""
    _walk_json(value)
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid canonical JSON") from exc


def domain_hash(domain: str, value: object) -> str:
    if type(domain) is not str or not domain.startswith("aml.") or "\x00" in domain:
        _reject("invalid identity domain")
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + canonical_bytes(value)).hexdigest()


def strict_json_bytes(raw: bytes, *, maximum_bytes: int = MAX_JSON_BYTES) -> dict[str, object]:
    """Parse only bytes already in the exact V005 canonical representation."""
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _reject("JSON is empty, oversized, or has a BOM")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _reject("duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique,
            parse_float=lambda _: _reject("floats are prohibited"),
            parse_constant=lambda _: _reject("non-finite numbers are prohibited"),
        )
    except OlympicsAuthorizationGovernanceV005Error:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid strict JSON") from exc
    if type(value) is not dict:
        _reject("JSON root must be an object")
    if raw != canonical_bytes(value):
        _reject("supplied JSON bytes are not canonical")
    return value


def parse_canonical_timestamp(value: object) -> datetime:
    if type(value) is not str or not TIMESTAMP_RE.fullmatch(value):
        _reject("timestamp is not canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise OlympicsAuthorizationGovernanceV005Error("timestamp is malformed") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        _reject("timestamp is not canonical")
    return parsed


def parse_imf_fixdate(value: object) -> datetime:
    if type(value) is not str or len(value) != 29 or not value.endswith(" GMT"):
        _reject("Date header must be exact IMF-fixdate in GMT")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid Date header") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        _reject("Date header must be UTC")
    if parsed.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT") != value:
        _reject("Date header is not canonical IMF-fixdate")
    return parsed.astimezone(timezone.utc)


def _decode_base64(value: object) -> bytes:
    if type(value) is not str or len(value) > 2_700_000 or not BASE64_RE.fullmatch(value):
        _reject("invalid canonical base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != value:
        _reject("base64 is not canonical")
    return decoded


def _validate_relative_path(value: object) -> None:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 1024:
        _reject("invalid relative path")
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value or "\x00" in value:
        _reject("path injection")
    parts = value.split("/")
    if any(not part or part in {".", ".."} or not COMPONENT_RE.fullmatch(part) for part in parts):
        _reject("invalid path component")
    if str(PurePosixPath(*parts)) != value:
        _reject("noncanonical relative path")


def validate_relative_path(value: object) -> None:
    _validate_relative_path(value)


def _validate_absolute_path(value: object) -> None:
    if type(value) is not str or not value.startswith("/") or value == "/" or value.endswith("/"):
        _reject("invalid absolute path")
    if len(value.encode("utf-8")) > 1024 or "\x00" in value or "\\" in value:
        _reject("invalid absolute path")
    _validate_relative_path(value[1:])


def _validate_primitive(name: str, value: object, contract: Mapping[str, object] | None = None) -> None:
    if name == "timestamp":
        parse_canonical_timestamp(value)
    elif name == "rfc7231_date":
        parse_imf_fixdate(value)
    elif name == "identity":
        if type(value) is not str or not HASH_RE.fullmatch(value):
            _reject("invalid identity")
    elif name == "git_oid":
        if type(value) is not str or not GIT_RE.fullmatch(value):
            _reject("invalid Git object ID")
    elif name == "uint31":
        if type(value) is not int or not 0 <= value <= 2_147_483_647:
            _reject("invalid uint31")
    elif name == "uint63":
        if type(value) is not int or not 1 <= value <= 9_223_372_036_854_775_807:
            _reject("invalid uint63")
    elif name == "env_name":
        if type(value) is not str or not ENV_RE.fullmatch(value):
            _reject("invalid environment name")
    elif name == "token":
        if type(value) is not str or not TOKEN_RE.fullmatch(value):
            _reject("invalid token")
    elif name == "hostname":
        if type(value) is not str or not HOST_RE.fullmatch(value):
            _reject("invalid hostname")
    elif name == "github_login":
        if type(value) is not str or not LOGIN_RE.fullmatch(value):
            _reject("invalid GitHub login")
    elif name == "semver3":
        if type(value) is not str or not SEMVER_RE.fullmatch(value):
            _reject("invalid semantic version")
    elif name == "nonce":
        _validate_primitive("identity", value)
    elif name == "relative_path":
        _validate_relative_path(value)
    elif name == "absolute_path":
        _validate_absolute_path(value)
    elif name == "argv":
        if type(value) is not str or not value or len(value.encode()) > 512 or any(c in value for c in "\x00\r\n"):
            _reject("invalid argv element")
    elif name == "env_assignment":
        if type(value) is not str or "=" not in value or len(value.encode()) > 256:
            _reject("invalid environment assignment")
        _validate_primitive("env_name", value.split("=", 1)[0])
    elif name == "field_name":
        if type(value) is not str or not FIELD_RE.fullmatch(value):
            _reject("invalid field name")
    elif name == "artifact_type":
        schemas = {} if contract is None else contract.get("artifact_schemas", {})
        if type(value) is not str or not ARTIFACT_RE.fullmatch(value) or value not in schemas:
            _reject("invalid artifact type")
    elif name == "base64":
        _decode_base64(value)
    elif name == "durability_event":
        allowed = {
            "open_root_no_follow", "verify_mount_device_owner_mode", "exclusive_create", "write_complete",
            "f_fullfsync_file", "close_file", "fsync_directory", "rename_exclusive", "fsync_parent_directory",
        }
        if value not in allowed:
            _reject("invalid durability event")
    elif name == "domain_name":
        if type(value) is not str or not DOMAIN_NAME_RE.fullmatch(value):
            _reject("invalid domain name")
    elif name == "schema_identifier":
        if type(value) is not str or not SCHEMA_IDENTIFIER_RE.fullmatch(value):
            _reject("invalid schema identifier")
    elif name == "state_name":
        if type(value) is not str or not STATE_NAME_RE.fullmatch(value):
            _reject("invalid state name")
    else:
        _reject(f"unknown primitive {name}")


def _validate_rule(rule: object, value: object, contract: Mapping[str, object]) -> None:
    if type(rule) is not str:
        _reject("schema rule must be a string")
    if rule.startswith("identity:"):
        target = rule.split(":", 1)[1]
        if target != "self" and target not in contract["artifact_schemas"] and target not in contract["compatibility_edges"]["external_types"] and target not in {"command", "governance", "event_projection"}:
            _reject("unregistered identity target")
        _validate_primitive("identity", value)
    elif rule.startswith("nullable_identity:"):
        if value is not None:
            _validate_rule("identity:" + rule.split(":", 1)[1], value, contract)
    elif rule.startswith("nullable:"):
        if value is not None:
            _validate_primitive(rule.split(":", 1)[1], value, contract)
    elif rule.startswith("literal:"):
        literal = rule.split(":", 1)[1]
        expected: object = {"true": True, "false": False, "null": None}.get(literal, literal)
        if literal.isdecimal():
            expected = int(literal)
        if type(value) is not type(expected) or value != expected:
            _reject(f"literal mismatch: expected {literal}")
    elif rule.startswith("enum:"):
        if type(value) is not str or value not in rule.split(":", 1)[1].split("|"):
            _reject("enum mismatch")
    elif rule.startswith("array_identity:"):
        parts = rule.split(":")
        if len(parts) != 5:
            _reject("invalid identity array schema")
        _validate_array("identity:" + parts[1], value, int(parts[2]), int(parts[3]), parts[4], contract)
    elif rule.startswith("array:"):
        parts = rule.split(":")
        if len(parts) != 5:
            _reject("invalid array schema")
        _validate_array(parts[1], value, int(parts[2]), int(parts[3]), parts[4], contract)
    else:
        _validate_primitive(rule, value, contract)


def _validate_array(rule: str, value: object, minimum: int, maximum: int, order: str, contract: Mapping[str, object]) -> None:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        _reject("array cardinality violation")
    for item in value:
        _validate_rule(rule, item, contract) if rule.startswith("identity:") else _validate_primitive(rule, item, contract)
    if order == "sorted_unique" and value != sorted(set(value)):
        _reject("array must be sorted and unique")
    if order not in {"sorted_unique", "ordered"}:
        _reject("unknown array ordering")


def artifact_identity(record: Mapping[str, object], schema: Mapping[str, object]) -> str:
    field = schema["identity_field"]
    return domain_hash(str(schema["domain"]), {key: value for key, value in record.items() if key != field})


def validate_artifact(record: Mapping[str, object], artifact_type: str, contract: Mapping[str, object], *, verify_identity: bool = True) -> dict[str, object]:
    schemas = contract.get("artifact_schemas")
    if not isinstance(schemas, Mapping) or artifact_type not in schemas:
        _reject("unknown artifact schema")
    schema = schemas[artifact_type]
    fields = schema.get("fields") if isinstance(schema, Mapping) else None
    if not isinstance(fields, Mapping) or set(record) != set(fields):
        _reject("artifact fields are missing or unknown")
    for name, rule in fields.items():
        _validate_rule(rule, record[name], contract)
    identity_field = schema["identity_field"]
    if verify_identity and record[identity_field] != artifact_identity(record, schema):
        _reject("artifact identity mismatch")
    return dict(record)


def artifact_self_identity(record: Mapping[str, object], artifact_type: str, contract: Mapping[str, object]) -> str:
    return str(record[contract["artifact_schemas"][artifact_type]["identity_field"]])


def event_projection_identity(record: Mapping[str, object], artifact_type: str, contract: Mapping[str, object], timestamp_field: str) -> str:
    identity_field = contract["artifact_schemas"][artifact_type]["identity_field"]
    projection = {key: value for key, value in record.items() if key not in {identity_field, timestamp_field, "clock_attestation_identity"}}
    return domain_hash(EVENT_PROJECTION_DOMAIN, {"artifact_type": artifact_type, "projection": projection})


def _parse_response_headers(raw: bytes) -> tuple[str, dict[str, list[str]]]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeError as exc:
        raise OlympicsAuthorizationGovernanceV005Error("headers must be ASCII") from exc
    if not text.endswith("\r\n\r\n") or "\n" in text.replace("\r\n", ""):
        _reject("headers require exact CRLF framing")
    lines = text[:-4].split("\r\n")
    headers: dict[str, list[str]] = {}
    for line in lines[1:]:
        if ":" not in line:
            _reject("malformed response header")
        name, value = line.split(":", 1)
        if not name or not value.startswith(" "):
            _reject("noncanonical response header")
        headers.setdefault(name.lower(), []).append(value[1:])
    return lines[0], headers


def validate_clock_bundle(
    request: Mapping[str, object],
    evidence: Mapping[str, object],
    verifier: Mapping[str, object],
    attestation: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    event: Mapping[str, object] | None = None,
    event_type: str | None = None,
    timestamp_field: str | None = None,
) -> None:
    validate_artifact(request, "clock_request", contract)
    validate_artifact(evidence, "clock_evidence", contract)
    validate_artifact(verifier, "clock_verifier_attestation", contract)
    validate_artifact(attestation, "clock_attestation", contract)
    expected_request = (
        b"HEAD /rate_limit HTTP/1.1\r\n"
        b"Host: api.github.com\r\n"
        b"X-GitHub-Api-Version: 2022-11-28\r\n"
        + f"X-AML-Clock-Nonce: {request['request_nonce']}\r\n".encode("ascii")
        + b"Cache-Control: no-cache, no-store\r\n"
        b"Pragma: no-cache\r\n"
        b"Connection: close\r\n\r\n"
    )
    if _decode_base64(request["raw_request_bytes_base64"]) != expected_request:
        _reject("clock raw request bytes are not canonical or nonce-bound")
    if (
        evidence["request_identity"] != request["clock_request_identity"]
        or verifier["request_identity"] != request["clock_request_identity"]
        or verifier["evidence_identity"] != evidence["clock_evidence_identity"]
        or attestation["request_identity"] != request["clock_request_identity"]
        or attestation["evidence_identity"] != evidence["clock_evidence_identity"]
        or attestation["verifier_attestation_identity"]
        != verifier["clock_verifier_attestation_identity"]
    ):
        _reject("clock request/evidence/verifier/attestation binding mismatch")
    raw = _decode_base64(evidence["raw_response_headers_base64"])
    status, headers = _parse_response_headers(raw)
    if status != "HTTP/1.1 200 OK" or set(headers.get("date", [])) != {str(evidence["response_date_as_received"])} or len(headers.get("date", [])) != 1:
        _reject("clock status or Date evidence mismatch")
    if set(headers) != {"date"}:
        _reject("clock response headers violate the strict Date-only allowlist")
    if evidence["redirect_count"] != 0 or evidence["response_elapsed_milliseconds"] > 5000:
        _reject("documentary clock response bounds failed")
    stamp = parse_imf_fixdate(evidence["response_date_as_received"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    if (
        verifier["verified_date"] != evidence["response_date_as_received"]
        or verifier["verified_at"] != stamp
        or attestation["canonical_utc_timestamp"] != stamp
    ):
        _reject("clock normalization mismatch")
    if event is not None:
        if event_type is None or timestamp_field is None:
            _reject("event clock binding arguments missing")
        if event.get("clock_attestation_identity") != attestation["clock_attestation_identity"]:
            _reject("event uses unrelated clock attestation")
        if event.get(timestamp_field) != attestation["canonical_utc_timestamp"]:
            _reject("event timestamp must textually equal attested timestamp")
        if attestation["bound_artifact_type"] != event_type or attestation["bound_timestamp_field"] != timestamp_field:
            _reject("clock artifact domain or field mismatch")
        expected_projection = event_projection_identity(event, event_type, contract, timestamp_field)
        if attestation["bound_event_projection_identity"] != expected_projection:
            _reject("clock event projection mismatch")


def authorization_is_valid_at(record: Mapping[str, object], trusted_time: str) -> bool:
    issued = parse_canonical_timestamp(record.get("issued_at"))
    expires = parse_canonical_timestamp(record.get("expires_at"))
    now = parse_canonical_timestamp(trusted_time)
    if expires != issued + timedelta(seconds=VALIDITY_SECONDS):
        _reject("authorization expiration equation mismatch")
    return issued <= now < expires


def validate_role_assignment(record: Mapping[str, object], accounts: Mapping[str, Mapping[str, object]], contract: Mapping[str, object]) -> None:
    validate_artifact(record, "role_assignment", contract)
    for identity, account in accounts.items():
        validate_artifact(account, "stable_account", contract)
        if account["stable_account_identity"] != identity:
            _reject("stable account registry key mismatch")
    for pair, relation in contract["role_separation"]["matrix"].items():
        left, right = pair.split("|")
        left_identity = record.get(f"{left}_identity")
        right_identity = record.get(f"{right}_identity")
        if left_identity is None or right_identity is None:
            continue
        if left_identity not in accounts or right_identity not in accounts:
            _reject("unresolved stable account")
        left_id = accounts[left_identity]["github_user_id"]
        right_id = accounts[right_identity]["github_user_id"]
        if relation == "must_differ" and left_id == right_id:
            _reject("role separation violation")
        if relation not in {"must_differ", "may_match"}:
            _reject("unknown role relation")


def validate_display_metadata(record: Mapping[str, object], account: Mapping[str, object], contract: Mapping[str, object]) -> None:
    validate_artifact(record, "display_metadata", contract)
    validate_artifact(account, "stable_account", contract)
    if record["stable_account_identity"] != account["stable_account_identity"]:
        _reject("display metadata account mismatch")


def validate_access_evidence(record: Mapping[str, object], contract: Mapping[str, object]) -> None:
    validate_artifact(record, "access_prohibition", contract)
    if not set(record["prohibited_resources"]) <= set(record["inspected_resources"]):
        _reject("prohibited resource scope was not inspected")
    if not set(record["prohibited_credential_names"]) <= set(record["inspected_environment_names"]):
        _reject("prohibited credential scope was not inspected")
    if not set(record["prohibited_filesystem_roots"]) <= set(record["inspected_filesystem_roots"]):
        _reject("prohibited filesystem scope was not inspected")
    if not set(record["prohibited_network_destinations"]) <= set(record["inspected_network_destinations"]):
        _reject("prohibited network scope was not inspected")
    observed_fields = (
        "observed_network_clients",
        "observed_prohibited_resources",
        "observed_prohibited_credential_names",
        "observed_prohibited_filesystem_roots",
        "observed_prohibited_network_destinations",
    )
    if any(record[field] for field in observed_fields):
        _reject("access evidence observed a prohibited item or network client")


def _index_artifacts(artifacts: Mapping[str, Sequence[Mapping[str, object]]], contract: Mapping[str, object]) -> tuple[dict[str, tuple[str, Mapping[str, object]]], set[str]]:
    registry: dict[str, tuple[str, Mapping[str, object]]] = {}
    types: set[str] = set()
    for artifact_type, records in artifacts.items():
        if artifact_type not in contract["artifact_schemas"] or type(records) not in {list, tuple}:
            _reject("unknown artifact type or non-sequence registry")
        types.add(artifact_type)
        for record in records:
            validate_artifact(record, artifact_type, contract)
            identity = artifact_self_identity(record, artifact_type, contract)
            if identity in registry:
                _reject("duplicate or cross-type artifact identity")
            registry[identity] = (artifact_type, record)
    return registry, types


def validate_typed_bundle(artifacts: Mapping[str, Sequence[Mapping[str, object]]], contract: Mapping[str, object], *, required_types: Sequence[str], forbidden_types: Sequence[str] = ()) -> dict[str, tuple[str, Mapping[str, object]]]:
    registry, supplied_types = _index_artifacts(artifacts, contract)
    if supplied_types != set(required_types) or supplied_types & set(forbidden_types):
        _reject("bundle has missing, orphaned, or forbidden artifact types")
    external = set(contract["compatibility_edges"]["external_types"])
    referenced: set[str] = set()
    for artifact_type, records in artifacts.items():
        fields = contract["artifact_schemas"][artifact_type]["fields"]
        for record in records:
            for field, rule in fields.items():
                targets: list[tuple[str, object]] = []
                if str(rule).startswith("identity:"):
                    targets = [(str(rule).split(":", 1)[1], record[field])]
                elif str(rule).startswith("nullable_identity:") and record[field] is not None:
                    targets = [(str(rule).split(":", 1)[1], record[field])]
                elif str(rule).startswith("array_identity:"):
                    target = str(rule).split(":")[1]
                    targets = [(target, item) for item in record[field]]
                for target, identity in targets:
                    if target in external or target in {"self", "command", "governance", "event_projection"}:
                        continue
                    resolved = registry.get(str(identity))
                    if resolved is None or resolved[0] != target:
                        _reject(f"unresolved or cross-type artifact reference: {artifact_type}.{field}->{target}")
                    referenced.add(str(identity))

            dynamic_target: tuple[str, str] | None = None
            if artifact_type == "typed_reference":
                dynamic_target = (str(record["target_artifact_type"]), str(record["target_identity"]))
            elif artifact_type == "canonical_payload":
                dynamic_target = (str(record["artifact_type"]), str(record["artifact_identity"]))
            elif artifact_type == "durability_evidence":
                dynamic_target = (str(record["target_artifact_type"]), str(record["target_artifact_identity"]))
            elif artifact_type == "transition_envelope":
                dynamic_target = (str(record["root_artifact_type"]), str(record["root_artifact_identity"]))
            if dynamic_target is not None:
                target_type, identity = dynamic_target
                resolved = registry.get(identity)
                if resolved is None or resolved[0] != target_type:
                    _reject(f"unresolved dynamic reference from {artifact_type} to {target_type}")
                referenced.add(identity)

    envelopes = artifacts.get("transition_envelope", ())
    roots = {
        artifact_self_identity(record, "transition_envelope", contract)
        for record in envelopes
    }
    permitted_unreferenced = roots
    all_identities = set(registry)
    orphaned = all_identities - referenced - permitted_unreferenced
    if orphaned:
        _reject("bundle contains orphaned or ambiguous records")
    return registry


def validate_typed_reference(
    reference: Mapping[str, object],
    registry: Mapping[str, tuple[str, Mapping[str, object]]],
    contract: Mapping[str, object],
    *,
    expected_type: str,
    expected_state: str | None,
) -> Mapping[str, object]:
    validate_artifact(reference, "typed_reference", contract)
    if reference["target_artifact_type"] != expected_type or reference["target_state"] != expected_state:
        _reject("typed prior reference type or state mismatch")
    schema = contract["artifact_schemas"][expected_type]
    if (
        reference["target_schema_version"] != schema["fields"]["schema_version"].split(":", 1)[1]
        or reference["target_domain"] != schema["domain"]
        or reference["target_identity_field"] != schema["identity_field"]
    ):
        _reject("typed prior reference schema metadata mismatch")
    resolved = registry.get(str(reference["target_identity"]))
    if resolved is None or resolved[0] != expected_type:
        _reject("typed prior reference is unresolved")
    return resolved[1]


def transition_spec(contract: Mapping[str, object], transition_id: str) -> Mapping[str, object]:
    matches = [item for item in contract["lifecycle"]["transitions"] if item["transition_id"] == transition_id]
    if len(matches) != 1:
        _reject("unknown or duplicate lifecycle transition")
    return matches[0]


TIMESTAMP_FIELDS = {
    "proposal": "proposal_timestamp", "human_approval": "approval_timestamp", "authorization": "issued_at",
    "activation": "activated_at", "authorization_decision": "decision_timestamp", "consumption_claim": "consumed_at",
    "build_start": "build_started_at", "run_start": "run_started_at", "lifecycle_terminal": "terminal_timestamp",
    "archive_pending": "archive_started_at", "archive_manifest": "archive_timestamp", "completion_marker": "completed_at",
    "supersession": "supersession_timestamp", "rejection": "rejected_at", "expiration": "expired_at",
    "indeterminate": "recorded_at", "recovery": "recovered_at",
}


def validate_transition_bundle(
    transition_id: str,
    actor_role: str,
    artifacts: Mapping[str, Sequence[Mapping[str, object]]],
    contract: Mapping[str, object],
    *,
    documentary_git_proof: Mapping[str, object] | None = None,
) -> None:
    spec = transition_spec(contract, transition_id)
    if actor_role != spec["actor"]:
        _reject("wrong transition actor")
    required = list(spec["required_artifact_types"])
    choices = list(spec["required_one_of_artifact_type_sets"])
    if choices:
        selected = [choice for choice in choices if set(artifacts) == set(required) | set(choice)]
        if len(selected) != 1:
            _reject("transition must supply exactly one conditional artifact set")
        required.extend(selected[0])
    registry = validate_typed_bundle(
        artifacts,
        contract,
        required_types=required,
        forbidden_types=spec["forbidden_competing_artifact_types"],
    )
    envelope = _one(artifacts, "transition_envelope")
    new_type = str(spec["new_artifact_type"])
    new_records = artifacts.get(new_type, ())
    if len(new_records) != 1:
        _reject("transition requires exactly one new artifact")
    event = new_records[0]
    event_identity = artifact_self_identity(event, new_type, contract)
    if (
        envelope["transition_id"] != transition_id
        or envelope["source_state"] != spec["from"]
        or envelope["destination_state"] != spec["to"]
        or envelope["actor_role"] != actor_role
        or envelope["root_artifact_type"] != new_type
        or envelope["root_artifact_identity"] != event_identity
    ):
        _reject("transition envelope does not match the frozen transition")

    prior_reference = registry.get(str(envelope["prior_reference_identity"]))
    if prior_reference is None or prior_reference[0] != "typed_reference":
        _reject("transition prior reference is missing or untyped")
    prior = validate_typed_reference(
        prior_reference[1],
        registry,
        contract,
        expected_type=str(spec["prior_record_type"]),
        expected_state=str(spec["from"]),
    )
    supporting_types: list[str] = []
    for reference_identity in envelope["supporting_reference_identities"]:
        resolved_reference = registry.get(str(reference_identity))
        if resolved_reference is None or resolved_reference[0] != "typed_reference":
            _reject("transition supporting reference is missing or untyped")
        reference = resolved_reference[1]
        supporting_types.append(str(reference["target_artifact_type"]))
        validate_typed_reference(
            reference,
            registry,
            contract,
            expected_type=str(reference["target_artifact_type"]),
            expected_state=None,
        )
    expected_supporting = ["documentary_binding"] if spec["documentary_binding_required"] else []
    if sorted(supporting_types) != expected_supporting:
        _reject("transition supporting evidence differs from the frozen inventory")
    if "prior_reference_identity" in event and event["prior_reference_identity"] != envelope["prior_reference_identity"]:
        _reject("event and envelope use different typed prior references")

    used_attestations: set[str] = set()
    used_verifiers: set[str] = set()
    for event_type, timestamp_field in TIMESTAMP_FIELDS.items():
        for event in artifacts.get(event_type, ()):
            attestation_identity = str(event["clock_attestation_identity"])
            if attestation_identity in used_attestations:
                _reject("clock attestation reuse is prohibited")
            used_attestations.add(attestation_identity)
            resolved = registry.get(attestation_identity)
            if resolved is None or resolved[0] != "clock_attestation":
                _reject("event clock attestation unresolved")
            attestation = resolved[1]
            request = registry[str(attestation["request_identity"])][1]
            evidence = registry[str(attestation["evidence_identity"])][1]
            verifier_identity = str(attestation["verifier_attestation_identity"])
            if verifier_identity in used_verifiers:
                _reject("clock verifier attestation reuse is prohibited")
            used_verifiers.add(verifier_identity)
            verifier = registry[verifier_identity][1]
            validate_clock_bundle(
                request,
                evidence,
                verifier,
                attestation,
                contract,
                event=event,
                event_type=event_type,
                timestamp_field=timestamp_field,
            )
    for authorization in artifacts.get("authorization", ()):
        if not authorization_is_valid_at(authorization, str(authorization["issued_at"])):
            _reject("authorization is invalid at issuance")
    _validate_transition_actor(envelope, event, artifacts, contract)
    _validate_transition_time_and_validity(spec, event, new_type, prior, artifacts)
    _validate_transition_durability(envelope, event, new_type, artifacts, contract)
    _validate_foundational_equations(transition_id, artifacts, contract)
    if spec["documentary_binding_required"]:
        if documentary_git_proof is None:
            _reject("documentary Git proof is required")
        validate_documentary_git_proof(
            _one(artifacts, "documentary_binding"),
            _one(artifacts, "authorization"),
            contract,
            documentary_git_proof,
        )
    elif documentary_git_proof is not None:
        _reject("documentary Git proof is not permitted for this transition")
    _validate_transition_semantics(transition_id, artifacts, contract)


def _one(artifacts: Mapping[str, Sequence[Mapping[str, object]]], artifact_type: str) -> Mapping[str, object]:
    records = artifacts.get(artifact_type, ())
    if len(records) != 1:
        _reject(f"exactly one {artifact_type} required")
    return records[0]


ACTOR_FIELDS = {
    "human_approval": "author_identity",
    "activation": "operator_identity",
    "authorization_decision": "actor_identity",
    "consumption_claim": "operator_identity",
    "build_start": "operator_identity",
    "run_start": "operator_identity",
    "lifecycle_terminal": "operator_identity",
    "archive_pending": "operator_identity",
    "completion_marker": "actor_identity",
    "supersession": "superseding_author_identity",
    "expiration": "actor_identity",
    "rejection": "actor_identity",
    "indeterminate": "actor_identity",
    "recovery": "recovery_actor_identity",
}


def _validate_transition_actor(
    envelope: Mapping[str, object],
    event: Mapping[str, object],
    artifacts: Mapping[str, Sequence[Mapping[str, object]]],
    contract: Mapping[str, object],
) -> None:
    role = str(envelope["actor_role"])
    assignment = _one(artifacts, "role_assignment")
    accounts = {
        str(item["stable_account_identity"]): item
        for item in artifacts.get("stable_account", ())
    }
    validate_role_assignment(assignment, accounts, contract)
    role_field = f"{role}_identity"
    if role_field not in assignment or assignment[role_field] != envelope["actor_identity"]:
        _reject("transition actor is not assigned to the declared stable account")
    root_type = str(envelope["root_artifact_type"])
    actor_field = ACTOR_FIELDS.get(root_type)
    if actor_field is None or event.get(actor_field) != envelope["actor_identity"]:
        _reject("transition event is not bound to the acting stable account")
    if envelope["actor_identity"] not in accounts:
        _reject("transition actor stable account is unresolved")


def _event_timestamp(record: Mapping[str, object], artifact_type: str) -> str:
    field = TIMESTAMP_FIELDS.get(artifact_type)
    if field is None or field not in record:
        _reject("timestamp-bearing transition artifact is missing its timestamp")
    return str(record[field])


def _validate_transition_time_and_validity(
    spec: Mapping[str, object],
    event: Mapping[str, object],
    event_type: str,
    prior: Mapping[str, object],
    artifacts: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    operation = parse_canonical_timestamp(_event_timestamp(event, event_type))
    prior_type = str(spec["prior_record_type"])
    prior_time = parse_canonical_timestamp(_event_timestamp(prior, prior_type))
    if operation < prior_time:
        _reject("lifecycle timestamp predates its typed prior record")
    validity = str(spec["authorization_validity"])
    if validity == "not_applicable":
        return
    authorization_records = artifacts.get("authorization", ())
    target_authorization_identity = event.get(
        "authorization_identity",
        event.get("predecessor_authorization_identity"),
    )
    matching_authorizations = [
        item
        for item in authorization_records
        if item["authorization_identity"] == target_authorization_identity
    ]
    if len(matching_authorizations) != 1:
        _reject("operation authorization is missing or ambiguous")
    authorization = matching_authorizations[0]
    issued = parse_canonical_timestamp(authorization["issued_at"])
    expires = parse_canonical_timestamp(authorization["expires_at"])
    if validity == "issued_at<=operation<expires_at":
        if not issued <= operation < expires:
            _reject("authorization is not valid at the dependent operation timestamp")
    elif validity == "operation==expires_at":
        if operation != expires:
            _reject("expiration must occur at the exact frozen boundary")
    else:
        _reject("unknown authorization-validity equation")


def _render_artifact_path(
    artifact_type: str,
    record: Mapping[str, object],
    contract: Mapping[str, object],
) -> str:
    path = str(contract["artifact_schemas"][artifact_type]["path"])
    for field in re.findall(r"\{([a-z][a-z0-9_]*)\}", path):
        if field not in record:
            _reject("artifact path placeholder is unresolved")
        path = path.replace("{" + field + "}", str(record[field]))
    validate_relative_path(path)
    return path


def _validate_transition_durability(
    envelope: Mapping[str, object],
    event: Mapping[str, object],
    event_type: str,
    artifacts: Mapping[str, Sequence[Mapping[str, object]]],
    contract: Mapping[str, object],
) -> None:
    durability = _one(artifacts, "durability_evidence")
    payload_matches = [
        item
        for item in artifacts.get("canonical_payload", ())
        if item["canonical_payload_identity"] == durability["canonical_payload_identity"]
    ]
    if len(payload_matches) != 1:
        _reject("durability payload is missing or ambiguous")
    payload = payload_matches[0]
    filesystem = _one(artifacts, "filesystem_evidence")
    validate_filesystem_evidence(filesystem, contract)
    raw = _decode_base64(payload["canonical_bytes_base64"])
    event_identity = artifact_self_identity(event, event_type, contract)
    expected_path = _render_artifact_path(event_type, event, contract)
    parent_path = expected_path.rsplit("/", 1)[0]
    expected_transition_identity = domain_hash(
        "aml.olympics.v005.transition-key",
        {
            "transition_id": envelope["transition_id"],
            "source_state": envelope["source_state"],
            "destination_state": envelope["destination_state"],
            "root_artifact_identity": event_identity,
        },
    )
    expected_trace = contract["durability_protocol"]["trace"]
    equations = (
        envelope["durability_evidence_identity"] == durability["durability_evidence_identity"],
        payload["artifact_type"] == event_type,
        payload["artifact_identity"] == event_identity,
        raw == canonical_bytes(event),
        payload["canonical_bytes_sha256"] == hashlib.sha256(raw).hexdigest(),
        durability["target_artifact_type"] == event_type,
        durability["target_artifact_identity"] == event_identity,
        durability["canonical_payload_identity"] == payload["canonical_payload_identity"],
        durability["target_relative_path"] == expected_path,
        durability["parent_relative_path"] == parent_path,
        durability["filesystem_evidence_identity"] == filesystem["filesystem_evidence_identity"],
        durability["transition_identity"] == expected_transition_identity,
        durability["durability_trace"] == expected_trace,
    )
    if not all(equations):
        _reject("transition durability is not bound to exact artifact, bytes, path, and trace")


def _validate_foundational_equations(
    transition_id: str,
    artifacts: Mapping[str, Sequence[Mapping[str, object]]],
    contract: Mapping[str, object],
) -> None:
    authorizations = artifacts.get("authorization", ())
    authorization_ids = {
        str(item["authorization_identity"]) for item in authorizations
    }
    supersession = transition_id.startswith("supersession")
    if (not supersession and len(authorization_ids) > 1) or (supersession and len(authorization_ids) != 2):
        _reject("authorization bundle cardinality is ambiguous")
    if not supersession and authorization_ids:
        expected = next(iter(authorization_ids))
        for records in artifacts.values():
            for record in records:
                if "authorization_identity" in record and record["authorization_identity"] != expected:
                    _reject("cross-artifact authorization identity mismatch")
    run_ids = {
        str(record["run_identity"])
        for records in artifacts.values()
        for record in records
        if "run_identity" in record
    }
    if len(run_ids) > 1:
        _reject("cross-artifact run identity mismatch")
    if authorizations:
        primary = authorizations[0]
        for claim in artifacts.get("consumption_claim", ()):
            if claim["source_commit"] != primary["authorized_source_commit"] or claim["source_tree"] != primary["authorized_source_tree"]:
                _reject("consumption source differs from authorized source")
        for proposal in artifacts.get("proposal", ()):
            if proposal["execution_command_identity"] != primary["execution_command_identity"]:
                _reject("proposal and authorization command identities differ")
        if primary["v005_governance_identity"] != contract["contract_identity"]:
            _reject("authorization governance identity mismatch")


def _validate_transition_semantics(transition_id: str, artifacts: Mapping[str, Sequence[Mapping[str, object]]], contract: Mapping[str, object]) -> None:
    if "authorization_decision" in artifacts:
        decision = _one(artifacts, "authorization_decision")
        activation = _one(artifacts, "activation")
        expected = "supersede" if transition_id.startswith("supersession") else "consume"
        if decision["activation_identity"] != activation["activation_identity"] or decision["decision_kind"] != expected or (expected == "consume" and decision["successor_authorization_identity"] is not None) or (expected == "supersede" and decision["successor_authorization_identity"] is None):
            _reject("decision kind or successor invariant failed")
    if "lifecycle_terminal" in artifacts:
        validate_terminal_bundle(
            _one(artifacts, "lifecycle_terminal"),
            _one(artifacts, "result_manifest") if "result_manifest" in artifacts else None,
            _one(artifacts, "failure") if "failure" in artifacts else None,
            contract,
        )
    if transition_id == "proposal_approved":
        proposal = _one(artifacts, "proposal")
        approval = _one(artifacts, "human_approval")
        if approval["proposal_identity"] != proposal["proposal_identity"] or approval["author_identity"] != proposal["authorization_author_identity"] or approval["author_identity"] == approval["reviewer_identity"]:
            _reject("approval binding or role separation failed")
        if parse_canonical_timestamp(approval["approval_timestamp"]) < parse_canonical_timestamp(proposal["proposal_timestamp"]):
            _reject("approval predates proposal")
    if transition_id == "authorization_activated":
        proposal = _one(artifacts, "proposal")
        approval = _one(artifacts, "human_approval")
        authorization = _one(artifacts, "authorization")
        activation = _one(artifacts, "activation")
        checkout = _one(artifacts, "source_checkout")
        equations = (
            (authorization["proposal_identity"], proposal["proposal_identity"]),
            (authorization["approval_identity"], approval["approval_identity"]),
            (authorization["authorized_source_commit"], checkout["source_commit"]),
            (authorization["authorized_source_tree"], checkout["source_tree"]),
            (authorization["v005_governance_identity"], contract["contract_identity"]),
            (authorization["execution_command_identity"], contract["execution_command"]["command_identity"]),
            (authorization["execution_argv"], contract["execution_command"]["argv"]),
        )
        if any(left != right for left, right in equations):
            _reject("authorization activation binding mismatch")
        if not (parse_canonical_timestamp(proposal["proposal_timestamp"]) <= parse_canonical_timestamp(approval["approval_timestamp"]) <= parse_canonical_timestamp(authorization["issued_at"]) <= parse_canonical_timestamp(activation["activated_at"]) < parse_canonical_timestamp(authorization["expires_at"])):
            _reject("authorization activation timestamp ordering failed")
        validate_access_evidence(_one(artifacts, "access_prohibition"), contract)
        validate_filesystem_evidence(_one(artifacts, "filesystem_evidence"), contract)
        binding = _one(artifacts, "documentary_binding")
        if binding["repository_context_identity"] != authorization["repository_context_identity"]:
            _reject("documentary and authorization repository contexts differ")
    if transition_id == "authorization_expired":
        authorization = _one(artifacts, "authorization")
        expiration = _one(artifacts, "expiration")
        if parse_canonical_timestamp(expiration["expired_at"]) < parse_canonical_timestamp(authorization["expires_at"]):
            _reject("expiration precedes authorization expiry")
    if transition_id == "proposal_rejected":
        rejection = _one(artifacts, "rejection")
        proposal = _one(artifacts, "proposal")
        if rejection["authorization_identity"] is not None:
            _reject("proposal rejection prior-state binding mismatch")
    if transition_id == "preflight_rejected":
        rejection = _one(artifacts, "rejection")
        authorization = _one(artifacts, "authorization")
        if rejection["authorization_identity"] != authorization["authorization_identity"]:
            _reject("preflight rejection prior-state binding mismatch")
    if transition_id == "archive_completed":
        pending = _one(artifacts, "archive_pending")
        archive = _one(artifacts, "archive_manifest")
        completion = _one(artifacts, "completion_marker")
        expected_destination = f"archives/{archive['run_identity']}"
        expected_staging = f"archives/staging/{pending['archive_pending_identity']}"
        if not (
            archive["archive_pending_identity"] == pending["archive_pending_identity"]
            and archive["terminal_identity"] == pending["terminal_identity"]
            and archive["destination_relative_path"] == pending["destination_relative_path"] == expected_destination
            and archive["staging_relative_path"] == expected_staging
            and parse_canonical_timestamp(pending["archive_started_at"])
            <= parse_canonical_timestamp(archive["archive_timestamp"])
            <= parse_canonical_timestamp(completion["completed_at"])
        ):
            _reject("archive pending, manifest, path, or timestamp reconciliation failed")
        validate_archive_bundle(
            archive,
            _one(artifacts, "lifecycle_terminal"),
            completion,
            _one(artifacts, "result_manifest") if "result_manifest" in artifacts else None,
            _one(artifacts, "failure") if "failure" in artifacts else None,
            contract,
        )
    if transition_id == "supersession_durable":
        decision = _one(artifacts, "authorization_decision")
        supersession = _one(artifacts, "supersession")
        if supersession["decision_identity"] != decision["decision_identity"] or supersession["predecessor_authorization_identity"] != decision["authorization_identity"] or supersession["successor_authorization_identity"] != decision["successor_authorization_identity"]:
            _reject("supersession record does not match durable decision")
        authorization_map = {
            str(item["authorization_identity"]): item
            for item in artifacts["authorization"]
        }
        activation_map = {
            str(item["authorization_identity"]): item
            for item in artifacts["activation"]
        }
        account_map = {
            str(item["stable_account_identity"]): item
            for item in artifacts["stable_account"]
        }
        validate_supersession_chain(
            [supersession],
            [decision],
            authorization_map,
            contract,
            activations=activation_map,
            competing_records={
                kind: artifacts.get(kind, ())
                for kind in (
                    "consumption_claim",
                    "expiration",
                    "rejection",
                    "lifecycle_terminal",
                    "indeterminate",
                )
            },
            role_assignment=_one(artifacts, "role_assignment"),
            accounts=account_map,
        )
    if transition_id.endswith("_recovered"):
        recovery = _one(artifacts, "recovery")
        indeterminate = _one(artifacts, "indeterminate")
        if recovery["prior_indeterminate_identity"] != indeterminate["indeterminate_identity"]:
            _reject("recovery does not reference the exact indeterminate record")
    if transition_id in {"archive_recovered", "archive_completion_recovered"}:
        pending = _one(artifacts, "archive_pending")
        archive = _one(artifacts, "archive_manifest")
        terminal = _one(artifacts, "lifecycle_terminal")
        expected_destination = f"archives/{archive['run_identity']}"
        expected_staging = f"archives/staging/{pending['archive_pending_identity']}"
        if not (
            archive["archive_pending_identity"] == pending["archive_pending_identity"]
            and archive["terminal_identity"] == terminal["terminal_identity"] == pending["terminal_identity"]
            and archive["authorization_identity"] == terminal["authorization_identity"] == pending["authorization_identity"]
            and archive["run_identity"] == terminal["run_identity"]
            and archive["destination_relative_path"] == pending["destination_relative_path"] == expected_destination
            and archive["staging_relative_path"] == expected_staging
            and parse_canonical_timestamp(pending["archive_started_at"]) <= parse_canonical_timestamp(archive["archive_timestamp"])
        ):
            _reject("archive recovery identity, path, or timestamp reconciliation failed")
        if transition_id == "archive_completion_recovered":
            validate_archive_bundle(
                archive,
                terminal,
                _one(artifacts, "completion_marker"),
                _one(artifacts, "result_manifest") if "result_manifest" in artifacts else None,
                _one(artifacts, "failure") if "failure" in artifacts else None,
                contract,
            )


def validate_terminal_bundle(terminal: Mapping[str, object], result_manifest: Mapping[str, object] | None, failure: Mapping[str, object] | None, contract: Mapping[str, object]) -> None:
    validate_artifact(terminal, "lifecycle_terminal", contract)
    success = terminal["terminal_state"] == "run_succeeded"
    if success:
        if result_manifest is None or failure is not None or terminal["result_manifest_identity"] is None or not terminal["result_identities"] or terminal["failure_identity"] is not None or terminal["failure_details"] is not None:
            _reject("successful terminal success/failure exclusivity failed")
        validate_artifact(result_manifest, "result_manifest", contract)
        if (
            terminal["result_manifest_identity"] != result_manifest["result_manifest_identity"]
            or terminal["result_identities"] != result_manifest["result_identities"]
            or terminal["authorization_identity"] != result_manifest["authorization_identity"]
            or terminal["run_identity"] != result_manifest["run_identity"]
        ):
            _reject("successful terminal result projection mismatch")
    else:
        if failure is None or result_manifest is not None or terminal["result_manifest_identity"] is not None or terminal["result_identities"] or terminal["failure_identity"] is None or terminal["failure_details"] is None:
            _reject("failed terminal success/failure exclusivity failed")
        validate_artifact(failure, "failure", contract)
        if (
            terminal["failure_identity"] != failure["failure_identity"]
            or terminal["failure_details"] != failure["failure_code"]
            or terminal["authorization_identity"] != failure["authorization_identity"]
            or terminal["run_identity"] != failure["run_identity"]
        ):
            _reject("failed terminal projection mismatch")


def validate_archive_bundle(archive: Mapping[str, object], terminal: Mapping[str, object], completion: Mapping[str, object], result_manifest: Mapping[str, object] | None, failure: Mapping[str, object] | None, contract: Mapping[str, object]) -> None:
    validate_artifact(archive, "archive_manifest", contract)
    validate_artifact(completion, "completion_marker", contract)
    validate_terminal_bundle(terminal, result_manifest, failure, contract)
    success = terminal["terminal_state"] == "run_succeeded"
    if archive["archive_state"] != ("success" if success else "failure"):
        _reject("archive state differs from terminal")
    fields = ("result_manifest_identity", "result_identities", "failure_identity", "failure_details")
    if any(archive[field] != terminal[field] for field in fields):
        _reject("archive projection differs from terminal")
    if completion["archive_identity"] != archive["archive_identity"] or completion["terminal_state"] != terminal["terminal_state"]:
        _reject("completion marker binding mismatch")
    if not (
        archive["authorization_identity"]
        == terminal["authorization_identity"]
        == completion["authorization_identity"]
        and archive["run_identity"] == terminal["run_identity"] == completion["run_identity"]
        and archive["terminal_identity"] == terminal["terminal_identity"]
        and completion["archive_identity"] == archive["archive_identity"]
    ):
        _reject("archive, terminal, and completion foundational identities differ")
    expected_files = sorted(
        [str(terminal["terminal_identity"])]
        + ([str(failure["failure_identity"])] if failure is not None else [str(result_manifest["result_manifest_identity"])])
        + ([] if result_manifest is None else [str(item) for item in result_manifest["result_identities"]])
    )
    if archive["expected_file_identities"] != expected_files:
        _reject("archive expected-file inventory differs from terminal outcome")


def validate_supersession_chain(
    records: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    authorizations: Mapping[str, Mapping[str, object]],
    contract: Mapping[str, object],
    *,
    activations: Mapping[str, Mapping[str, object]],
    competing_records: Mapping[str, Sequence[Mapping[str, object]]],
    role_assignment: Mapping[str, object],
    accounts: Mapping[str, Mapping[str, object]],
) -> None:
    validate_role_assignment(role_assignment, accounts, contract)
    decision_by_auth: dict[str, Mapping[str, object]] = {}
    for decision in decisions:
        validate_artifact(decision, "authorization_decision", contract)
        auth = str(decision["authorization_identity"])
        if auth in decision_by_auth:
            _reject("multiple decisions for one authorization")
        decision_by_auth[auth] = decision
    edges: dict[str, str] = {}
    incoming: set[str] = set()
    for record in records:
        validate_artifact(record, "supersession", contract)
        predecessor = str(record["predecessor_authorization_identity"])
        successor = str(record["successor_authorization_identity"])
        if predecessor == successor or predecessor in edges or successor in incoming:
            _reject("supersession self-cycle, fork, or duplicate incoming edge")
        decision = decision_by_auth.get(predecessor)
        if decision is None or decision["decision_kind"] != "supersede" or decision["successor_authorization_identity"] != successor or decision["decision_identity"] != record["decision_identity"]:
            _reject("supersession decision mismatch")
        if predecessor not in authorizations or successor not in authorizations:
            _reject("stale or missing authorization in supersession chain")
        predecessor_record = authorizations[predecessor]
        successor_record = authorizations[successor]
        validate_artifact(predecessor_record, "authorization", contract)
        validate_artifact(successor_record, "authorization", contract)
        activation = activations.get(predecessor)
        if activation is None:
            _reject("supersession predecessor lacks active lifecycle evidence")
        validate_artifact(activation, "activation", contract)
        if activation["authorization_identity"] != predecessor:
            _reject("supersession activation names another authorization")
        prohibited = {
            "consumption_claim",
            "expiration",
            "rejection",
            "lifecycle_terminal",
            "indeterminate",
            "supersession",
        }
        if any(competing_records.get(kind) for kind in prohibited):
            _reject("supersession predecessor is no longer active and unconsumed")
        decision_time = str(decision["decision_timestamp"])
        if not authorization_is_valid_at(predecessor_record, decision_time):
            _reject("supersession decision occurred outside authorization validity")
        if record["superseding_author_identity"] != role_assignment["superseding_authorization_author_identity"]:
            _reject("supersession actor is not the assigned stable account")
        previous_operator = role_assignment["previous_operator_identity"]
        if previous_operator is None:
            _reject("supersession previous operator is missing")
        if accounts[previous_operator]["github_user_id"] == accounts[record["superseding_author_identity"]]["github_user_id"]:
            _reject("supersession author and previous operator must differ")
        if successor_record["previous_authorization_identity"] != predecessor:
            _reject("successor predecessor link mismatch")
        preserved = ("authoritative_run_identity", "canonical_fixture_identity", "canonical_manifest_identity", "dataset_manifest_identity", "execution_command_identity", "v004_contract_identity", "v004_implementation_identity", "authorized_source_commit", "authorized_source_tree")
        if any(predecessor_record[field] != successor_record[field] for field in preserved):
            _reject("supersession changed preserved identity")
        edges[predecessor] = successor
        incoming.add(successor)
    for start in edges:
        seen: set[str] = set()
        current = start
        while current in edges:
            if current in seen:
                _reject("supersession cycle")
            seen.add(current)
            current = edges[current]


def synthetic_arbitration_outcome(*, consume_decision_durable: bool, supersede_decision_durable: bool, uncertainty: bool = False) -> str:
    if type(consume_decision_durable) is not bool or type(supersede_decision_durable) is not bool or type(uncertainty) is not bool:
        _reject("arbitration flags must be booleans")
    if uncertainty:
        return "indeterminate_recovery_only"
    if consume_decision_durable and supersede_decision_durable:
        return "integrity_failure"
    if consume_decision_durable:
        return "consumption_wins"
    if supersede_decision_durable:
        return "supersession_wins_successor_eligible_on_own_path"
    return "retry_before_atomicity"


def validate_filesystem_evidence(record: Mapping[str, object], contract: Mapping[str, object]) -> None:
    validate_artifact(record, "filesystem_evidence", contract)
    required_order = ["open_root_no_follow", "verify_mount_device_owner_mode", "exclusive_create", "write_complete", "f_fullfsync_file", "close_file", "fsync_directory"]
    trace = record["durability_trace"]
    position = -1
    for required in required_order:
        try:
            position = trace.index(required, position + 1)
        except ValueError:
            _reject("filesystem durability trace is incomplete or reordered")
    if record["fault_state"] != "none":
        _reject("indeterminate filesystem evidence cannot authorize progress")


def synthetic_archive_outcome(mode: str, evidence: Mapping[str, object]) -> str:
    fields = {
        "destination_exists",
        "manifest_exists",
        "marker_exists",
        "required_files_present",
        "all_intended_bytes_match",
        "unexpected_files",
        "recovery_authorized",
        "all_file_fullfsyncs",
        "directory_fsyncs",
        "parent_fsync",
        "marker_fullfsync",
        "marker_archive_identity_matches",
    }
    if set(evidence) != fields or any(type(value) is not bool for value in evidence.values()):
        _reject("archive fault evidence schema changed")
    if mode not in {"first_publication", "authorized_recovery", "verify_complete"}:
        _reject("unknown archive mode")
    destination = evidence["destination_exists"]
    manifest = evidence["manifest_exists"]
    marker = evidence["marker_exists"]
    files = evidence["required_files_present"]
    impossible = (
        (not destination and any((manifest, marker, files, evidence["all_intended_bytes_match"], evidence["all_file_fullfsyncs"], evidence["directory_fsyncs"], evidence["parent_fsync"], evidence["marker_fullfsync"])))
        or (marker and not manifest)
        or (marker and not files)
        or (marker and not evidence["marker_archive_identity_matches"])
    )
    if impossible or evidence["unexpected_files"] or (destination and not evidence["all_intended_bytes_match"]):
        return "invalid_conflicting"
    complete = all(
        evidence[field]
        for field in (
            "destination_exists",
            "manifest_exists",
            "marker_exists",
            "required_files_present",
            "all_intended_bytes_match",
            "all_file_fullfsyncs",
            "directory_fsyncs",
            "parent_fsync",
            "marker_fullfsync",
            "marker_archive_identity_matches",
        )
    )
    if complete:
        return "already_complete_and_valid"
    if mode == "first_publication":
        return "publication_permitted" if not destination else "invalid_conflicting"
    if mode == "authorized_recovery":
        return "recovery_permitted" if destination and evidence["recovery_authorized"] else "invalid_conflicting"
    return "indeterminate"


def _git_oid(kind: str, payload: bytes) -> str:
    if kind not in {"blob", "tree", "commit"}:
        _reject("unsupported Git object type")
    return hashlib.sha1(kind.encode() + b" " + str(len(payload)).encode() + b"\x00" + payload).hexdigest()


def _parse_commit(raw: bytes) -> tuple[str, list[str]]:
    try:
        header = raw.split(b"\n\n", 1)[0].decode("utf-8", errors="strict")
    except (UnicodeError, ValueError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid raw commit bytes") from exc
    trees = [line[5:] for line in header.splitlines() if line.startswith("tree ")]
    parents = [line[7:] for line in header.splitlines() if line.startswith("parent ")]
    if len(trees) != 1 or any(not GIT_RE.fullmatch(item) for item in trees + parents):
        _reject("invalid commit headers")
    return trees[0], parents


def _parse_tree(raw: bytes) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    cursor = 0
    while cursor < len(raw):
        space = raw.find(b" ", cursor)
        nul = raw.find(b"\x00", space + 1)
        if space < 0 or nul < 0 or nul + 21 > len(raw):
            _reject("invalid raw tree bytes")
        mode = raw[cursor:space].decode("ascii")
        name = raw[space + 1:nul].decode("utf-8", errors="strict")
        oid = raw[nul + 1:nul + 21].hex()
        if mode not in {"100644", "40000"} or "/" in name or name in {".", ".."}:
            _reject("invalid tree entry")
        entries.append((mode, name, oid))
        cursor = nul + 21
    return entries


def _verify_tree_proof(proof_bytes: bytes, root_oid: str, path: str, leaf_oid: str) -> None:
    proof = strict_json_bytes(proof_bytes)
    if set(proof) != {"steps"} or type(proof["steps"]) is not list:
        _reject("invalid tree proof schema")
    parts = path.split("/")
    if len(proof["steps"]) != len(parts):
        _reject("tree proof path length mismatch")
    expected_tree = root_oid
    for index, step in enumerate(proof["steps"]):
        if type(step) is not dict or set(step) != {"component", "mode", "object_oid", "object_type", "raw_tree_base64", "tree_oid"}:
            _reject("invalid tree proof step")
        raw_tree = _decode_base64(step["raw_tree_base64"])
        tree_oid = _git_oid("tree", raw_tree)
        expected_mode = "100644" if index == len(parts) - 1 else "40000"
        expected_type = "blob" if index == len(parts) - 1 else "tree"
        expected_object = leaf_oid if index == len(parts) - 1 else str(step["object_oid"])
        if step["component"] != parts[index] or step["mode"] != expected_mode or step["object_type"] != expected_type or step["tree_oid"] != tree_oid or tree_oid != expected_tree:
            _reject("tree proof component or object mismatch")
        if (expected_mode, parts[index], expected_object) not in _parse_tree(raw_tree):
            _reject("tree proof entry absent")
        expected_tree = str(step["object_oid"])
    if expected_tree != leaf_oid:
        _reject("tree proof leaf mismatch")


def validate_documentary_git_proof(binding: Mapping[str, object], authorization: Mapping[str, object], contract: Mapping[str, object], proof: Mapping[str, object]) -> None:
    validate_artifact(binding, "documentary_binding", contract)
    validate_artifact(authorization, "authorization", contract)
    byte_keys = {"authorization_bytes", "authorization_tree_proof_bytes", "commit_a_raw_bytes", "binding_bytes", "binding_tree_proof_bytes", "commit_b_raw_bytes"}
    expected_keys = byte_keys | {"commit_b_oid"}
    if set(proof) != expected_keys or any(type(proof[key]) is not bytes for key in byte_keys) or type(proof["commit_b_oid"]) is not str or not GIT_RE.fullmatch(str(proof["commit_b_oid"])):
        _reject("documentary Git proof is incomplete")
    if proof["authorization_bytes"] != canonical_bytes(authorization) or proof["binding_bytes"] != canonical_bytes(binding):
        _reject("documentary bytes are not exact canonical artifacts")
    expected_authorization_path = f"authorizations/{authorization['authorization_identity']}/authorization.json"
    if (
        binding["authorization_identity"] != authorization["authorization_identity"]
        or binding["authorization_relative_path"] != expected_authorization_path
        or binding["repository_context_identity"] != authorization["repository_context_identity"]
    ):
        _reject("documentary binding authorization, canonical path, or repository context mismatch")
    auth_blob = _git_oid("blob", proof["authorization_bytes"])
    binding_blob = _git_oid("blob", proof["binding_bytes"])
    tree_a, parents_a = _parse_commit(proof["commit_a_raw_bytes"])
    tree_b, parents_b = _parse_commit(proof["commit_b_raw_bytes"])
    commit_a = _git_oid("commit", proof["commit_a_raw_bytes"])
    commit_b = _git_oid("commit", proof["commit_b_raw_bytes"])
    equations = (
        (binding["authorization_blob_oid"], auth_blob), (binding["authorization_tree_oid"], tree_a),
        (binding["documentary_authorization_commit_oid"], commit_a),
        (binding["authorized_source_parent_oid"], authorization["authorized_source_commit"]),
    )
    if any(left != right for left, right in equations) or proof["commit_b_oid"] != commit_b or parents_a != [authorization["authorized_source_commit"]] or parents_b != [commit_a]:
        _reject("Git object identity or direct-parent equation failed")
    _verify_tree_proof(proof["authorization_tree_proof_bytes"], tree_a, str(binding["authorization_relative_path"]), auth_blob)
    _verify_tree_proof(proof["binding_tree_proof_bytes"], tree_b, f"bindings/{authorization['authorization_identity']}/documentary_binding.json", binding_blob)


def _validate_contract_structure(value: Mapping[str, object]) -> None:
    required = {"archive_truth_table","artifact_schemas","archive_protocol","canonicalization","clock_protocol","compatibility_edges","consumption_protocol","contract_identity","documentary_binding_protocol","durability_protocol","execution_command","historical_lineage","identity_domains","lifecycle","path_security","primitives","prospective_as_of","repository_context_protocol","role_separation","schema_language","schema_version","scope","supersession_protocol","validation_manifest","version"}
    if set(value) != required or value.get("schema_version") != SCHEMA or value.get("version") != VERSION:
        _reject("V005 root schema is invalid")
    parse_canonical_timestamp(value.get("prospective_as_of"))
    schemas = value.get("artifact_schemas")
    domains = value.get("identity_domains")
    if not isinstance(schemas, Mapping) or not isinstance(domains, Mapping) or len(schemas) != 37:
        _reject("V005 must define exactly thirty-seven artifact schemas")
    for name, schema in schemas.items():
        if not isinstance(schema, Mapping) or set(schema) != {"domain","fields","identity_field","immutable","path"}:
            _reject("artifact schema metadata is incomplete")
        if schema["domain"] != domains.get(name) or schema["immutable"] is not True or schema["fields"].get(schema["identity_field"]) != "identity:self":
            _reject("artifact domain, immutability, or identity rule mismatch")
        if len(schema["fields"]) != len(set(schema["fields"])):
            _reject("duplicate schema field")
    if len(set(domains.values())) != len(domains) or set(domains) != set(schemas) | {"governance","command","event_projection"}:
        _reject("identity domains are incomplete or duplicated")
    transitions = value["lifecycle"]["transitions"]
    if len(transitions) != len(EXPECTED_TRANSITIONS) or value["lifecycle"]["transition_count"] != len(EXPECTED_TRANSITIONS) or len({item["transition_id"] for item in transitions}) != len(EXPECTED_TRANSITIONS):
        _reject("lifecycle transition inventory changed")
    required_transition_keys = {"transition_id","from","to","actor","required_artifact_types","required_one_of_artifact_type_sets","new_artifact_type","forbidden_competing_artifact_types","prior_state_identity_required","clock_binding","documentary_binding_required","atomicity_point","durability","crash_before_atomicity","crash_after_atomicity_before_durability","retry","idempotency","recovery","terminal","prior_record_type","required_event_record_type","required_timestamp_equation","authorization_validity","required_identity_equations","durability_trace_type","allowed_retry_mode","allowed_recovery_route"}
    for item in transitions:
        conditional_types = {name for group in item["required_one_of_artifact_type_sets"] for name in group}
        if set(item) != required_transition_keys or item["new_artifact_type"] not in schemas or set(item["required_artifact_types"]) - set(schemas) or set(item["forbidden_competing_artifact_types"]) - set(schemas) or conditional_types - set(schemas):
            _reject("transition bundle schema is incomplete")
        expected = EXPECTED_TRANSITIONS.get(item["transition_id"])
        actual = (
            item["from"], item["to"], item["actor"], item["terminal"],
            item["prior_record_type"], item["new_artifact_type"], item["authorization_validity"],
        )
        if expected is None or actual != expected or item["required_event_record_type"] != item["new_artifact_type"]:
            _reject("machine lifecycle differs from the independently frozen transition matrix")
    if value["lifecycle"]["terminal_states"] != ["archived", "expired", "rejected", "superseded"]:
        _reject("terminal state inventory changed")
    if value["supersession_protocol"]["eligible_predecessor_states"] != ["active_unconsumed"]:
        _reject("supersession predecessor state policy changed")


def validate_contract(value: Mapping[str, object]) -> dict[str, object]:
    try:
        _validate_contract_structure(value)
    except (AttributeError, KeyError, TypeError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract structure is malformed") from exc
    if value["historical_lineage"] != {"design_base_commit":DESIGN_BASE_COMMIT,"immutable_tag_name":TAG_NAME,"immutable_tag_object":TAG_OBJECT,"immutable_tagged_commit":TAGGED_COMMIT,"v004_contract_identity":V004_CONTRACT_IDENTITY,"v004_implementation_identity":V004_IMPLEMENTATION_IDENTITY}:
        _reject("historical lineage changed")
    command = value["execution_command"]
    if not isinstance(command, Mapping):
        _reject("execution command is malformed")
    projection = {key:item for key,item in command.items() if key != "command_identity"}
    if command["command_identity"] != COMMAND_IDENTITY or domain_hash(COMMAND_DOMAIN, projection) != COMMAND_IDENTITY:
        _reject("execution command identity changed")
    projection = {key:item for key,item in value.items() if key != "contract_identity"}
    if value["contract_identity"] != CONTRACT_IDENTITY or domain_hash(GOVERNANCE_DOMAIN, projection) != CONTRACT_IDENTITY:
        _reject("governance identity changed")
    if any(value["scope"].values()):
        _reject("design-only scope changed")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    try:
        raw = (root / CONTRACT_PATH).read_bytes()
    except OSError as exc:
        raise OlympicsAuthorizationGovernanceV005Error("V005 contract is missing") from exc
    return validate_contract(strict_json_bytes(raw))


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_bytes(validate_contract(value))


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    return canonical_bytes({
        "artifact_schema_count": len(contract["artifact_schemas"]),
        "authorization_created": False,
        "authorization_governance_identity": contract["contract_identity"],
        "execution_capability_implemented": False,
        "execution_command_identity": contract["execution_command"]["command_identity"],
        "lifecycle_transition_count": len(contract["lifecycle"]["transitions"]),
        "official_run_authorized": False,
        "official_run_executed": False,
        "status": contract["validation_manifest"]["status"],
    })
