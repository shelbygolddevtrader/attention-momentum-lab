"""Pure validation for design-only Olympics authorization governance V005.

The module validates the frozen contract and synthetic evidence records.  It has
no network client, authorization writer/consumer, or Olympics execution path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from typing import Mapping, Sequence

from aml.winner_archetype_contracts import canonical_json


CONTRACT_PATH = "config/professional_strategy_olympics_authorization_governance_v005.json"
SCHEMA = "aml.professional-strategy-olympics.authorization-governance.v005"
VERSION = "professional-strategy-olympics-authorization-governance-v005"
CONTRACT_IDENTITY = "fe8708b38c8966f6db42c3b59a99103aae750b8c440e7f133e2e8aaecdfb7b88"
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
REQUEST_DOMAIN = "aml.olympics.v005.clock-request"
EVIDENCE_DOMAIN = "aml.olympics.v005.clock-evidence"
PROPOSAL_DOMAIN = "aml.olympics.v005.authorization-proposal"
CANONICAL_CLOCK_REQUEST = (
    b"HEAD /rate_limit HTTP/1.1\r\n"
    b"Host: api.github.com\r\n"
    b"X-GitHub-Api-Version: 2022-11-28\r\n"
    b"Connection: close\r\n\r\n"
)

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
LOGIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class OlympicsAuthorizationGovernanceV005Error(ValueError):
    """A V005 schema, identity, or governance invariant failed."""


def _reject(message: str) -> None:
    raise OlympicsAuthorizationGovernanceV005Error(message)


def _walk_strings(value: object) -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            _reject("all strings must be Unicode NFC")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise OlympicsAuthorizationGovernanceV005Error("invalid Unicode") from exc
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _reject("JSON object keys must be strings")
            _walk_strings(key)
            _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            _walk_strings(item)


def canonical_bytes(value: object) -> bytes:
    """Canonical JSON with NFC enforcement and one final LF."""
    _walk_strings(value)
    try:
        return canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid canonical JSON") from exc


def domain_hash(domain: str, value: object) -> str:
    """Return SHA-256(UTF8(domain) || NUL || canonical JSON bytes)."""
    if not TOKEN_RE.fullmatch(domain.replace(".", "_")) or not domain.startswith("aml."):
        _reject("invalid identity domain")
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + canonical_bytes(value)).hexdigest()


def strict_json_bytes(raw: bytes, *, maximum_bytes: int = 2_000_000) -> dict[str, object]:
    """Decode strict UTF-8 JSON, rejecting duplicates, BOM, constants, and non-NFC."""
    if not raw or len(raw) > maximum_bytes or raw.startswith(b"\xef\xbb\xbf"):
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
            parse_constant=lambda item: _reject(f"non-finite number: {item}"),
        )
    except OlympicsAuthorizationGovernanceV005Error:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OlympicsAuthorizationGovernanceV005Error("invalid strict JSON") from exc
    if not isinstance(value, dict):
        _reject("JSON root must be an object")
    _walk_strings(value)
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
    expected = parsed.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    if expected != value:
        _reject("Date header is not canonical IMF-fixdate")
    return parsed.astimezone(timezone.utc)


def _validate_relative_path(value: object) -> None:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 1024:
        _reject("invalid relative path")
    if value.startswith(("/", "\\", "//")) or "\\" in value or "\x00" in value:
        _reject("path injection")
    if re.match(r"^[A-Za-z]:", value):
        _reject("drive path prohibited")
    parts = value.split("/")
    if any(not part or part in {".", ".."} or not COMPONENT_RE.fullmatch(part) for part in parts):
        _reject("invalid path component")
    if str(PurePosixPath(*parts)) != value:
        _reject("noncanonical relative path")


def validate_relative_path(value: object) -> None:
    """Validate a synthetic V005 repository/store-relative path."""
    _validate_relative_path(value)


def _validate_absolute_path(value: object) -> None:
    if type(value) is not str or not value.startswith("/") or value == "/":
        _reject("absolute path required")
    if value.endswith("/") or len(value.encode("utf-8")) > 1024 or "\x00" in value or "\\" in value:
        _reject("invalid absolute path")
    _validate_relative_path(value[1:])


def _validate_primitive(name: str, value: object) -> None:
    if name == "timestamp":
        parse_canonical_timestamp(value)
    elif name == "rfc7231_date":
        parse_imf_fixdate(value)
    elif name == "identity":
        if type(value) is not str or not HASH_RE.fullmatch(value):
            _reject("invalid identity")
    elif name == "git_oid":
        if type(value) is not str or not GIT_RE.fullmatch(value):
            _reject("invalid git object identity")
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
            _reject("invalid normalized GitHub login")
    elif name == "semver3":
        if type(value) is not str or not SEMVER_RE.fullmatch(value):
            _reject("invalid semantic version")
    elif name == "nonce":
        if type(value) is not str or not HASH_RE.fullmatch(value):
            _reject("invalid nonce")
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
        key, _ = value.split("=", 1)
        _validate_primitive("env_name", key)
    else:
        _reject(f"unknown primitive {name}")


def _validate_rule(rule: object, value: object) -> None:
    if type(rule) is not str:
        _reject("schema rule must be a string")
    if rule.startswith("identity:"):
        _validate_primitive("identity", value)
    elif rule.startswith("nullable_identity:"):
        if value is not None:
            _validate_primitive("identity", value)
    elif rule.startswith("nullable:"):
        if value is not None:
            _validate_primitive(rule.split(":", 1)[1], value)
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
    elif rule.startswith("array:"):
        parts = rule.split(":")
        if len(parts) != 5 or type(value) is not list:
            _reject("invalid array")
        primitive, minimum, maximum, order = parts[1], int(parts[2]), int(parts[3]), parts[4]
        if not minimum <= len(value) <= maximum:
            _reject("array cardinality violation")
        for item in value:
            _validate_primitive(primitive, item)
        if order == "sorted_unique" and value != sorted(set(value)):
            _reject("array must be sorted and unique")
        if order not in {"sorted_unique", "ordered"}:
            _reject("unknown array ordering")
    else:
        _validate_primitive(rule, value)


def artifact_identity(record: Mapping[str, object], schema: Mapping[str, object]) -> str:
    identity_field = schema["identity_field"]
    projection = {key: value for key, value in record.items() if key != identity_field}
    return domain_hash(str(schema["domain"]), projection)


def authorization_proposal_identity(record: Mapping[str, object]) -> str:
    """Hash the pre-approval projection, avoiding authorization/approval circularity."""
    projection = {
        key: value
        for key, value in record.items()
        if key not in {"authorization_identity", "approval_evidence_identity"}
    }
    return domain_hash(PROPOSAL_DOMAIN, projection)


def validate_artifact(
    record: Mapping[str, object],
    artifact_type: str,
    contract: Mapping[str, object],
    *,
    verify_identity: bool = True,
) -> dict[str, object]:
    schemas = contract.get("artifact_schemas")
    if not isinstance(schemas, Mapping) or artifact_type not in schemas:
        _reject("unknown artifact schema")
    schema = schemas[artifact_type]
    if not isinstance(schema, Mapping) or not isinstance(schema.get("fields"), Mapping):
        _reject("malformed artifact schema")
    fields = schema["fields"]
    if set(record) != set(fields):
        _reject("artifact fields are missing or unknown")
    for name, rule in fields.items():
        _validate_rule(rule, record[name])
    identity_field = schema["identity_field"]
    if verify_identity and record[identity_field] != artifact_identity(record, schema):
        _reject("artifact identity mismatch")
    return dict(record)


def clock_request_identity(request_bytes: bytes) -> str:
    if request_bytes != CANONICAL_CLOCK_REQUEST:
        _reject("clock request bytes changed")
    return hashlib.sha256(REQUEST_DOMAIN.encode() + b"\x00" + request_bytes).hexdigest()


def clock_evidence_identity(raw_headers: bytes) -> str:
    try:
        text = raw_headers.decode("ascii", errors="strict")
    except UnicodeError as exc:
        raise OlympicsAuthorizationGovernanceV005Error("clock headers must be ASCII") from exc
    if not text.endswith("\r\n\r\n") or "\n" in text.replace("\r\n", ""):
        _reject("clock headers require CRLF and terminal CRLFCRLF")
    lines = text[:-4].split("\r\n")
    if not lines or lines[0] != "HTTP/1.1 200 OK":
        _reject("unexpected clock response status")
    dates = [line for line in lines[1:] if line.split(":", 1)[0].lower() == "date"]
    if len(dates) != 1 or ":" not in dates[0]:
        _reject("exactly one Date header required")
    date_value = dates[0].split(":", 1)[1]
    if not date_value.startswith(" "):
        _reject("Date header requires one leading OWS space")
    parse_imf_fixdate(date_value[1:])
    evidence = {
        "raw_date_header_line": dates[0],
        "request_bytes_sha256": hashlib.sha256(CANONICAL_CLOCK_REQUEST).hexdigest(),
        "response_header_block_sha256": hashlib.sha256(raw_headers).hexdigest(),
        "response_status_line": lines[0],
    }
    return domain_hash(EVIDENCE_DOMAIN, evidence)


def validate_clock_attestation(
    record: Mapping[str, object], raw_headers: bytes, contract: Mapping[str, object]
) -> dict[str, object]:
    result = validate_artifact(record, "clock_attestation", contract)
    if result["request_identity"] != clock_request_identity(CANONICAL_CLOCK_REQUEST):
        _reject("clock request identity mismatch")
    if result["evidence_byte_identity"] != clock_evidence_identity(raw_headers):
        _reject("clock evidence identity mismatch")
    header_date = parse_imf_fixdate(result["response_date_as_received"])
    canonical = parse_canonical_timestamp(result["canonical_utc_timestamp"])
    if header_date != canonical:
        _reject("clock timestamp mismatch")
    if parse_canonical_timestamp(result["observation_timestamp"]) != canonical:
        _reject("zero-tolerance observation mismatch")
    return result


def validate_access_evidence(record: Mapping[str, object], contract: Mapping[str, object]) -> None:
    """Validate the exact bounded absence observation without overclaiming it."""
    validate_artifact(record, "access_prohibition", contract)
    inspected_names = set(record["inspected_environment_names"])
    prohibited_names = set(record["prohibited_credential_names"])
    inspected_roots = set(record["inspected_filesystem_roots"])
    prohibited_roots = set(record["prohibited_filesystem_roots"])
    if not prohibited_names <= inspected_names or not prohibited_roots <= inspected_roots:
        _reject("prohibited access scope was not fully inspected")
    if record["permitted_exceptions"]:
        _reject("V005 permits no access-prohibition exception")


def authorization_is_valid_at(record: Mapping[str, object], trusted_time: str) -> bool:
    issued = parse_canonical_timestamp(record.get("issued_at"))
    expires = parse_canonical_timestamp(record.get("expires_at"))
    now = parse_canonical_timestamp(trusted_time)
    if expires != issued + timedelta(seconds=VALIDITY_SECONDS):
        _reject("authorization expiration equation mismatch")
    return issued <= now < expires


def validate_role_assignment(
    record: Mapping[str, object],
    identities: Mapping[str, Mapping[str, object]],
    contract: Mapping[str, object],
) -> None:
    validate_artifact(record, "role_assignment", contract)
    for identity, identity_record in identities.items():
        validate_artifact(identity_record, "operator_identity", contract)
        if identity_record["operator_identity"] != identity:
            _reject("identity registry key mismatch")
    matrix = contract["role_separation"]["matrix"]
    for pair, relation in matrix.items():
        left, right = pair.split("|")
        left_key = f"{left}_identity"
        right_key = f"{right}_identity"
        left_identity = record.get(left_key)
        right_identity = record.get(right_key)
        if left_identity is None or right_identity is None:
            continue
        if left_identity not in identities or right_identity not in identities:
            _reject("unknown role identity")
        left_id = identities[left_identity].get("github_user_id")
        right_id = identities[right_identity].get("github_user_id")
        if relation == "must_differ" and left_id == right_id:
            _reject(f"role separation violation: {pair}")
        if relation == "must_match" and left_id != right_id:
            _reject(f"role matching violation: {pair}")
        if relation not in {"must_differ", "must_match", "may_match"}:
            _reject("unknown role relation")


def validate_transition(contract: Mapping[str, object], prior: str, target: str, actor: str) -> dict[str, object]:
    transitions = contract["lifecycle"]["transitions"]
    matches = [item for item in transitions if item["from"] == prior and item["to"] == target]
    if len(matches) != 1 or matches[0]["actor"] != actor:
        _reject("lifecycle transition is not permitted")
    return dict(matches[0])


def synthetic_claim_outcome(events: Mapping[str, object]) -> str:
    """Evaluate a pure fault-injection vector for the frozen claim protocol."""
    expected = {
        "root_valid", "local_apfs", "exclusive_arbitration", "arbitration_complete",
        "arbitration_file_fsync", "arbitration_close", "arbitration_directory_fsync",
        "exclusive_claim", "claim_complete", "claim_regular", "claim_link_count_one",
        "claim_mode_owner_valid", "claim_file_fsync", "claim_close", "claim_directory_fsync",
    }
    if set(events) != expected or any(type(value) is not bool for value in events.values()):
        _reject("claim fault vector schema changed")
    if not events["root_valid"] or not events["local_apfs"]:
        return "rejected"
    if not events["exclusive_arbitration"]:
        return "already_claimed"
    arbitration = (
        "arbitration_complete", "arbitration_file_fsync", "arbitration_close",
        "arbitration_directory_fsync",
    )
    claim = (
        "exclusive_claim", "claim_complete", "claim_regular", "claim_link_count_one",
        "claim_mode_owner_valid", "claim_file_fsync", "claim_close", "claim_directory_fsync",
    )
    return "consumed" if all(events[field] for field in (*arbitration, *claim)) else "indeterminate"


def synthetic_archive_outcome(events: Mapping[str, object]) -> str:
    """Evaluate a pure fault-injection vector for write-once archive publication."""
    expected = {
        "destination_exclusive", "all_files_complete", "all_file_fsyncs",
        "directory_fsync_before_marker", "marker_exclusive", "marker_complete",
        "marker_fsync", "directory_fsync_after_marker", "parent_directory_fsync",
        "manifest_matches",
    }
    if set(events) != expected or any(type(value) is not bool for value in events.values()):
        _reject("archive fault vector schema changed")
    if not events["destination_exclusive"] or not events["marker_exclusive"]:
        return "existing_destination_rejected"
    return "archived" if all(events.values()) else "indeterminate"


def validate_supersession_chain(records: Sequence[Mapping[str, object]], contract: Mapping[str, object]) -> None:
    predecessors: set[object] = set()
    successors: set[object] = set()
    edges: dict[object, object] = {}
    for record in records:
        validate_artifact(record, "supersession", contract)
        predecessor = record["predecessor_authorization_identity"]
        successor = record["successor_authorization_identity"]
        if predecessor == successor or predecessor in predecessors or successor in successors:
            _reject("supersession fork, duplicate, or self-cycle")
        predecessors.add(predecessor)
        successors.add(successor)
        edges[predecessor] = successor
    for start in edges:
        seen: set[object] = set()
        current = start
        while current in edges:
            if current in seen:
                _reject("supersession cycle")
            seen.add(current)
            current = edges[current]


def validate_documentary_binding(
    binding: Mapping[str, object],
    authorization: Mapping[str, object],
    contract: Mapping[str, object],
    *,
    authorization_bytes: bytes,
    authorization_blob_oid: str,
    documentary_commit: str,
    documentary_tree: str,
    documentary_parent: str,
) -> None:
    """Validate the non-circular synthetic commit-A/commit-B proof facts."""
    validate_artifact(binding, "documentary_binding", contract)
    validate_artifact(authorization, "authorization", contract)
    if authorization_bytes != canonical_bytes(authorization):
        _reject("documentary authorization bytes are not canonical")
    if documentary_commit == authorization["authorized_source_commit"]:
        _reject("documentary commit cannot be executable source")
    expected = (
        (binding["authorization_identity"], authorization["authorization_identity"]),
        (binding["authorization_blob_oid"], authorization_blob_oid),
        (binding["documentary_authorization_commit"], documentary_commit),
        (binding["documentary_authorization_tree"], documentary_tree),
        (binding["documentary_parent_commit"], documentary_parent),
        (documentary_parent, authorization["authorized_source_commit"]),
    )
    if any(left != right for left, right in expected):
        _reject("documentary binding mismatch")


def validate_claim_bindings(
    claim: Mapping[str, object], authorization: Mapping[str, object], contract: Mapping[str, object]
) -> None:
    validate_artifact(claim, "consumption_claim", contract)
    validate_artifact(authorization, "authorization", contract)
    expected = (
        (claim["authorization_identity"], authorization["authorization_identity"]),
        (claim["operator_identity"], authorization["operator_identity"]),
        (claim["source_commit"], authorization["authorized_source_commit"]),
        (claim["source_tree"], authorization["authorized_source_tree"]),
        (claim["store_manifest_identity"], authorization["consumption_store_manifest_identity"]),
    )
    if any(left != right for left, right in expected):
        _reject("consumption claim binding mismatch")


def validate_archive_bindings(
    archive: Mapping[str, object],
    terminal: Mapping[str, object],
    claim: Mapping[str, object],
    authorization: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    validate_artifact(archive, "archive_manifest", contract)
    validate_artifact(terminal, "lifecycle_terminal", contract)
    validate_claim_bindings(claim, authorization, contract)
    expected = (
        (archive["authorization_identity"], authorization["authorization_identity"]),
        (archive["consumption_claim_identity"], claim["claim_identity"]),
        (archive["terminal_lifecycle_identity"], terminal["lifecycle_terminal_identity"]),
        (archive["terminal_state"], terminal["terminal_state"]),
        (archive["run_identity"], terminal["run_identity"]),
        (archive["source_commit"], authorization["authorized_source_commit"]),
        (archive["source_tree"], authorization["authorized_source_tree"]),
    )
    if any(left != right for left, right in expected):
        _reject("archive binding mismatch")
    if archive["terminal_state"] == "run_succeeded" and archive["failure_identity"] is not None:
        _reject("success archive cannot contain failure identity")
    if archive["terminal_state"] == "run_failed" and archive["failure_identity"] is None:
        _reject("failed archive requires failure identity")


def validate_cross_bindings(
    authorization: Mapping[str, object],
    approval: Mapping[str, object],
    checkout: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    validate_artifact(authorization, "authorization", contract)
    validate_artifact(approval, "human_approval", contract)
    validate_artifact(checkout, "source_checkout", contract)
    equations = (
        (approval["authorization_proposal_identity"], authorization_proposal_identity(authorization)),
        (approval["author_identity"], authorization["authorization_author_identity"]),
        (approval["reviewer_identity"], authorization["reviewer_identity"]),
        (approval["reviewed_source_commit"], authorization["authorized_source_commit"]),
        (approval["reviewed_source_tree"], authorization["authorized_source_tree"]),
        (approval["reviewed_governance_identity"], authorization["v005_governance_identity"]),
        (approval["reviewed_command_identity"], authorization["execution_command_identity"]),
        (approval["clock_attestation_identity"], authorization["clock_attestation_identity"]),
        (checkout["source_commit"], authorization["authorized_source_commit"]),
        (checkout["source_tree"], authorization["authorized_source_tree"]),
        (checkout["source_checkout_manifest_identity"], authorization["source_checkout_manifest_identity"]),
    )
    if any(left != right for left, right in equations):
        _reject("cross-artifact binding mismatch")
    if authorization["v005_governance_identity"] != contract["contract_identity"]:
        _reject("wrong governance identity")
    if authorization["execution_command_identity"] != contract["execution_command"]["command_identity"]:
        _reject("wrong command identity")
    if authorization["v004_contract_identity"] != V004_CONTRACT_IDENTITY or authorization["v004_implementation_identity"] != V004_IMPLEMENTATION_IDENTITY:
        _reject("wrong V004 identity")
    if authorization["execution_argv"] != contract["execution_command"]["argv"]:
        _reject("wrong execution argv")
    if authorization["reviewer_identity"] == authorization["authorization_author_identity"]:
        _reject("self-approval prohibited")
    if not authorization_is_valid_at(authorization, authorization["issued_at"]):
        _reject("authorization not valid at issuance")


def _validate_contract_structure(value: Mapping[str, object]) -> None:
    required = {
        "artifact_schemas", "archival_protocol", "canonicalization", "clock_protocol",
        "consumption_protocol", "contract_identity", "documentary_binding_protocol",
        "execution_command", "historical_lineage", "identity_domains", "lifecycle",
        "path_security", "primitives", "prospective_as_of", "role_separation",
        "schema_language", "schema_version", "scope", "supersession_protocol",
        "validation_manifest", "version",
    }
    if set(value) != required or value.get("schema_version") != SCHEMA or value.get("version") != VERSION:
        _reject("V005 root schema is invalid")
    parse_canonical_timestamp(value.get("prospective_as_of"))
    schemas = value.get("artifact_schemas")
    domains = value.get("identity_domains")
    if not isinstance(schemas, Mapping) or not isinstance(domains, Mapping) or len(schemas) != 14:
        _reject("V005 must define exactly fourteen artifact schemas")
    for name, schema in schemas.items():
        if not isinstance(schema, Mapping) or set(schema) != {"domain", "fields", "identity_field", "immutable", "path"}:
            _reject("artifact schema metadata is incomplete")
        if schema["domain"] != domains.get(name) or schema["immutable"] is not True:
            _reject("artifact domain or immutability mismatch")
        fields = schema["fields"]
        if not isinstance(fields, Mapping) or schema["identity_field"] not in fields:
            _reject("artifact identity field missing")
        if fields[schema["identity_field"]] != "identity:self":
            _reject("artifact self identity rule missing")
        _validate_relative_path(str(schema["path"]).format(**{field: "a" * 64 for field in fields}))
    if set(domains.values()) != {
        schema["domain"] for schema in schemas.values()
    } | {GOVERNANCE_DOMAIN, COMMAND_DOMAIN, REQUEST_DOMAIN, EVIDENCE_DOMAIN, PROPOSAL_DOMAIN}:
        _reject("identity domains are incomplete or duplicated")
    if len(set(domains.values())) != len(domains):
        _reject("identity domains must be unique")
    if len(value["lifecycle"]["transitions"]) != 20:
        _reject("lifecycle transition table changed")
    if value["consumption_protocol"]["supported_filesystem"] != "single_host_local_APFS_only":
        _reject("coordination model changed")
    if value["clock_protocol"]["skew_tolerance_seconds"] != 0:
        _reject("clock tolerance changed")


def validate_contract(value: Mapping[str, object]) -> dict[str, object]:
    _validate_contract_structure(value)
    lineage = value["historical_lineage"]
    expected_lineage = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
    }
    if lineage != expected_lineage:
        _reject("historical lineage changed")
    command = value["execution_command"]
    command_projection = {key: item for key, item in command.items() if key != "command_identity"}
    if command["command_identity"] != COMMAND_IDENTITY or domain_hash(COMMAND_DOMAIN, command_projection) != COMMAND_IDENTITY:
        _reject("execution command identity changed")
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    if value["contract_identity"] != CONTRACT_IDENTITY or domain_hash(GOVERNANCE_DOMAIN, projection) != CONTRACT_IDENTITY:
        _reject("governance identity changed")
    if any(value["scope"].values()):
        _reject("design-only scope changed")
    if value["validation_manifest"] != {
        "authorization_artifact_present": False,
        "design_only": True,
        "future_implementation_required": True,
        "status": "DESIGN_ONLY_V005_CORRECTED_AUTHORIZATION_NOT_CREATED",
        "trial_artifacts_present": False,
    }:
        _reject("validation status changed")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    path = root / CONTRACT_PATH
    try:
        raw = path.read_bytes()
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
        "official_run_authorized": False,
        "official_run_executed": False,
        "status": contract["validation_manifest"]["status"],
    })
