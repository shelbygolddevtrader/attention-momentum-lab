"""Pure validation for the design-only Olympics V009 proof transport.

V009 transports the exact byte values consumed by the frozen V005
``validate_documentary_git_proof`` function.  It performs no Git lookup,
network access, filesystem discovery, authorization, or execution.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Any

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_IDENTITY as V005_COMMAND_IDENTITY,
    CONTRACT_IDENTITY as V005_GOVERNANCE_IDENTITY,
    OlympicsAuthorizationGovernanceV005Error,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    strict_json_bytes,
    validate_contract as validate_v005_contract,
    validate_documentary_git_proof,
)
from aml.professional_strategy_olympics_clock_continuation_v008 import (
    CONTRACT_IDENTITY as V008_CLOCK_CONTINUATION_IDENTITY,
    load_contract as load_v008_contract,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    CONTRACT_IDENTITY as V004_CONTRACT_IDENTITY,
    implementation_identity as v004_implementation_identity,
)
from aml.professional_strategy_olympics_operator_interface_v006 import (
    CONTRACT_IDENTITY as V006_OPERATOR_INTERFACE_IDENTITY,
    load_contract as load_v006_contract,
)
from aml.professional_strategy_olympics_runtime_boundary_v007 import (
    CONTRACT_IDENTITY as V007_RUNTIME_BOUNDARY_IDENTITY,
    load_contract as load_v007_contract,
)


CONTRACT_PATH = "config/professional_strategy_olympics_documentary_proof_transport_v009.json"
SCHEMA = "aml.professional-strategy-olympics.documentary-proof-transport.v009"
VERSION = "professional-strategy-olympics-documentary-proof-transport-v009"
CONTRACT_DOMAIN = "aml.olympics.v009.documentary-proof-transport"
ENVELOPE_SCHEMA = "aml.professional-strategy-olympics.documentary-proof-envelope.v009"
ENVELOPE_DOMAIN = "aml.olympics.v009.documentary-proof-envelope"
PACKAGE_SCHEMA = "aml.professional-strategy-olympics.documentary-proof-package.v009"
PACKAGE_DOMAIN = "aml.olympics.v009.documentary-proof-package"
PACKAGE_BINDING_DOMAIN = "aml.olympics.v009.documentary-proof-package-binding"
MEMBER_DOMAIN = "aml.olympics.v009.documentary-proof-member"
VALIDATION_DOMAIN = "aml.olympics.v009.documentary-proof-validation"

CONTRACT_IDENTITY = "0d9cba96035cec3c21bef24597ac32b308d71fc83c3ac07ea81e126ea4d12794"
DESIGN_BASE_COMMIT = "02529b3001d090c48186607d398b73209e8deb85"
V004_IMPLEMENTATION_IDENTITY = "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"

MAX_CONTRACT_BYTES = 250_000
MAX_ENVELOPE_BYTES = 800_000
MAX_PACKAGE_BYTES = 32_768
MAX_TOTAL_DECODED_BYTES = 500_000
MAX_TOTAL_PACKAGE_BYTES = MAX_ENVELOPE_BYTES + MAX_PACKAGE_BYTES
MAX_PATH_BYTES = 1024
MAX_TREE_PROOF_ENTRIES = 32
MAX_COMMIT_PARENTS = 1

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
SCHEMA_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,159}$")
BASE64_RE = re.compile(
    r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"
)

RAW_MEMBER_LIMITS = {
    "authorization_bytes": 2_000_000,
    "authorization_tree_proof_bytes": 200_000,
    "commit_a_raw_bytes": 32_768,
    "documentary_binding_bytes": 2_000_000,
    "binding_tree_proof_bytes": 200_000,
    "commit_b_raw_bytes": 32_768,
}
RAW_MEMBER_NAMES = tuple(RAW_MEMBER_LIMITS)

SECTION_NAMES = (
    "inheritance",
    "transport_model",
    "envelope_schema",
    "raw_byte_representation",
    "git_object_validation",
    "package_integration",
    "detached_source_relationship",
    "canonicalization",
    "resource_limits",
    "error_status_model",
    "authority_boundary",
    "capability_scope",
    "validation_manifest",
)
EXPECTED_SECTION_IDENTITIES = {
    "inheritance": "c44a61ec97a52dc656c5ed37821ab14639dcff4ae83718343604b7aa7ac93a0c",
    "transport_model": "d0c7ff1aaaa36b520544728d4af0a0248d2841418cb48fbb05aa5e8225b88ad2",
    "envelope_schema": "0728276c03d78f652d23fb6a848b407915bb3bae9eef2ed22d29ee4099d09605",
    "raw_byte_representation": "1c3b7b9d197236a71b861817b1ed98932314cd28f6beddc5c04fb2c521ace17a",
    "git_object_validation": "53a2bdb3b7fe705e7f0cbd889d440f89d099db442eb574cee9f3149da06a690a",
    "package_integration": "0eee723d429b225202cac41c95663dd8ce35eee7c538ac8e6ac97b799b081964",
    "detached_source_relationship": "490d7dcc8247f2cc478ca61ec7c67b1e3cf8d361ec99488348ed427d3d6d49ef",
    "canonicalization": "7c2beeb6b39a4d32d141c20304d4fb85d2578ba5b94ddf6fdb0be431cb49e310",
    "resource_limits": "260f7795d452b19f8176a4ad6e8bc4b45a1501b7aa3d7ab565d034b5bd774bb7",
    "error_status_model": "63497e131ab028fadf80f410621bf9e4f61ac67e09a128f38f5c88a9dd3d3cce",
    "authority_boundary": "cdcd38bbca9e997f1d72b9dad103477082b4af262b0bda9accb65eb7a0f17f04",
    "capability_scope": "46f0c6ba3815ff359ac457a52bd46ec8b76d25a474d39104da321a494508512a",
    "validation_manifest": "0f9f9f5f69b68451a598a6caf72d81d48afca5bb318e5e7d3aa707b665890bd7",
}

ROOT_FIELDS = {
    "schema_version",
    "version",
    "prospective_as_of",
    "contract_identity",
    "section_identities",
    *SECTION_NAMES,
}

ENVELOPE_FIELDS = {
    "schema_version",
    "envelope_identity",
    "authorization_identity",
    "documentary_binding_identity",
    "authorization_commit_a_oid",
    "documentary_binding_commit_b_oid",
    "authorization_tree_oid",
    "binding_tree_oid",
    "v004_contract_identity",
    "v004_implementation_identity",
    "v005_governance_identity",
    "v005_command_identity",
    "v006_operator_interface_identity",
    "v006_operator_package_identity",
    "v007_runtime_boundary_identity",
    "v007_runtime_package_identity",
    "v008_clock_continuation_identity",
    "v009_contract_identity",
    "package_binding_identity",
    "raw_members",
}

RAW_MEMBER_FIELDS = {
    "encoding",
    "encoded_length",
    "decoded_length",
    "sha256",
    "member_identity",
    "value",
}

INDEX_FIELDS_V006 = {
    "artifact_type",
    "artifact_identity",
    "relative_path",
    "canonical_bytes_sha256",
}
INDEX_FIELDS_V007 = INDEX_FIELDS_V006 | {"schema_version"}

PACKAGE_FIELD_ORDER = (
    "schema_version",
    "package_identity",
    "v009_contract_identity",
    "authorization_identity",
    "documentary_binding_identity",
    "v006_operator_package_identity",
    "v007_runtime_package_identity",
    "v008_clock_continuation_identity",
    "documentary_proof_envelope_identity",
    "documentary_proof_envelope_relative_path",
    "v006_record_index_extension",
    "v007_supplemental_manifest_entry",
)
PACKAGE_FIELDS = set(PACKAGE_FIELD_ORDER)

PACKAGE_BINDING_FIELD_ORDER = (
    "authorization_identity",
    "documentary_binding_identity",
    "v006_operator_package_identity",
    "v007_runtime_package_identity",
    "v008_clock_continuation_identity",
    "v009_contract_identity",
)

VALIDATION_ORDER = (
    "validate_frozen_contract_and_lineage",
    "validate_closed_world_inventory_and_canonical_bytes",
    "validate_storage_observations",
    "validate_envelope_and_recover_exact_v005_proof",
    "validate_successor_package_binding",
    "validate_v008_invocation_binding",
)

STORAGE_OBSERVATION_FIELDS = {
    "relative_path",
    "object_type",
    "filesystem_mode",
    "git_mode",
    "hard_link_count",
    "symlink_free",
    "same_device",
    "durable",
    "byte_length",
    "bytes_sha256",
}

FAILURE_CODES = frozenset(
    {
        "V009_PROOF_ABSENT",
        "V009_PROOF_DUPLICATED",
        "V009_PROOF_UNREADABLE",
        "V009_PROOF_IDENTITY_MISMATCH",
        "V009_PROOF_PACKAGE_MISMATCH",
        "V009_RAW_MEMBER_MISSING",
        "V009_RAW_MEMBER_EXTRA",
        "V009_RAW_MEMBER_SIZE_MISMATCH",
        "V009_RAW_MEMBER_HASH_MISMATCH",
        "V009_MALFORMED_GIT_OBJECT",
        "V009_DECLARED_OID_MISMATCH",
        "V009_TREE_PROOF_MISMATCH",
        "V009_ARTIFACT_PATH_MISMATCH",
        "V009_ARTIFACT_MODE_MISMATCH",
        "V009_ARTIFACT_BYTES_MISMATCH",
        "V009_COMMIT_PARENT_MISMATCH",
        "V009_AUTHORIZATION_MISMATCH",
        "V009_DOCUMENTARY_BINDING_MISMATCH",
        "V009_CROSS_VERSION_SUBSTITUTION",
        "V009_PACKAGE_REACHABILITY_UNCERTAIN",
        "V009_DURABILITY_UNCERTAIN",
        "V009_UNSUPPORTED_GIT_OBJECT_FORMAT",
        "V009_FALLBACK_PROHIBITED",
        "V009_SCHEMA",
    }
)


class OlympicsDocumentaryProofTransportV009Error(ValueError):
    """A V009 contract, proof envelope, or package binding is invalid."""


def _reject(code: str, detail: str) -> None:
    if code not in FAILURE_CODES:
        code = "V009_SCHEMA"
    raise OlympicsDocumentaryProofTransportV009Error(f"{code}:{detail}")


def _canonical_json_bytes(value: object, detail: str) -> bytes:
    try:
        return canonical_bytes(value)
    except OlympicsAuthorizationGovernanceV005Error as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            f"V009_SCHEMA:{detail}"
        ) from exc


def _domain_identity(domain: str, value: object, detail: str) -> str:
    try:
        return domain_hash(domain, value)
    except OlympicsAuthorizationGovernanceV005Error as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            f"V009_SCHEMA:{detail}"
        ) from exc


def _exact_mapping(value: object, fields: set[str], detail: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _reject("V009_SCHEMA", detail)
    return value


def _identity(value: object, detail: str) -> str:
    if type(value) is not str or not HASH_RE.fullmatch(value):
        _reject("V009_SCHEMA", detail)
    return value


def _git_oid(value: object, detail: str) -> str:
    if type(value) is not str or not GIT_RE.fullmatch(value):
        _reject("V009_UNSUPPORTED_GIT_OBJECT_FORMAT", detail)
    return value


def _relative_path(value: object, detail: str) -> str:
    if type(value) is not str or not value.isascii() or value != value.lower():
        _reject("V009_ARTIFACT_PATH_MISMATCH", detail)
    if (
        not 1 <= len(value.encode("ascii")) <= MAX_PATH_BYTES
        or value.endswith("/")
        or "\x00" in value
    ):
        _reject("V009_ARTIFACT_PATH_MISMATCH", detail)
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        _reject("V009_ARTIFACT_PATH_MISMATCH", detail)
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        _reject("V009_ARTIFACT_PATH_MISMATCH", detail)
    return value


def git_object_oid(kind: str, payload: bytes) -> str:
    """Reproduce the SHA-1 OID of one exact loose-object payload."""
    if kind not in {"blob", "tree", "commit"} or type(payload) is not bytes:
        _reject("V009_UNSUPPORTED_GIT_OBJECT_FORMAT", "sha1_only")
    header = f"{kind} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _preflight_member(name: str, value: object) -> int:
    member = _exact_mapping(value, RAW_MEMBER_FIELDS, f"raw_member_{name}")
    if member["encoding"] != "base64_rfc4648_padded":
        _reject("V009_SCHEMA", f"raw_member_encoding_{name}")
    encoded = member["value"]
    if (
        type(encoded) is not str
        or not encoded.isascii()
        or not BASE64_RE.fullmatch(encoded)
    ):
        _reject("V009_SCHEMA", f"raw_member_base64_{name}")
    if type(member["encoded_length"]) is not int or member["encoded_length"] != len(encoded):
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", f"encoded_{name}")
    encoded_limit = 4 * ((RAW_MEMBER_LIMITS[name] + 2) // 3)
    if len(encoded) > encoded_limit:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", f"encoded_limit_{name}")
    padding = 2 if encoded.endswith("==") else 1 if encoded.endswith("=") else 0
    decoded_length = (len(encoded) // 4) * 3 - padding
    if (
        type(member["decoded_length"]) is not int
        or member["decoded_length"] != decoded_length
        or decoded_length > RAW_MEMBER_LIMITS[name]
    ):
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", f"decoded_{name}")
    _identity(member["sha256"], f"raw_member_sha256_{name}")
    _identity(member["member_identity"], f"raw_member_identity_{name}")
    return decoded_length


def _decode_member(name: str, value: object) -> bytes:
    member = _exact_mapping(value, RAW_MEMBER_FIELDS, f"raw_member_{name}")
    _preflight_member(name, member)
    encoded = member["value"]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            f"V009_SCHEMA:raw_member_base64_{name}"
        ) from exc
    if base64.b64encode(raw).decode("ascii") != encoded:
        _reject("V009_SCHEMA", f"raw_member_noncanonical_base64_{name}")
    if (
        type(member["decoded_length"]) is not int
        or member["decoded_length"] != len(raw)
        or len(raw) > RAW_MEMBER_LIMITS[name]
    ):
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", f"decoded_{name}")
    digest = hashlib.sha256(raw).hexdigest()
    if member["sha256"] != digest:
        _reject("V009_RAW_MEMBER_HASH_MISMATCH", name)
    expected_member_identity = _domain_identity(
        MEMBER_DOMAIN,
        {"member_name": name, "decoded_length": len(raw), "sha256": digest},
        f"raw_member_identity_{name}",
    )
    if member["member_identity"] != expected_member_identity:
        _reject("V009_PROOF_IDENTITY_MISMATCH", f"member_{name}")
    return raw


def encode_raw_member(name: str, raw: bytes) -> dict[str, object]:
    """Build the canonical in-envelope representation for tests and tooling."""
    if name not in RAW_MEMBER_LIMITS or type(raw) is not bytes:
        _reject("V009_SCHEMA", "raw_member")
    if len(raw) > RAW_MEMBER_LIMITS[name]:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", name)
    digest = hashlib.sha256(raw).hexdigest()
    encoded = base64.b64encode(raw).decode("ascii")
    return {
        "encoding": "base64_rfc4648_padded",
        "encoded_length": len(encoded),
        "decoded_length": len(raw),
        "sha256": digest,
        "member_identity": _domain_identity(
            MEMBER_DOMAIN,
            {"member_name": name, "decoded_length": len(raw), "sha256": digest},
            f"raw_member_identity_{name}",
        ),
        "value": encoded,
    }


def envelope_identity(value: Mapping[str, object]) -> str:
    projection = {key: item for key, item in value.items() if key != "envelope_identity"}
    return _domain_identity(ENVELOPE_DOMAIN, projection, "envelope_identity")


def package_identity(value: Mapping[str, object]) -> str:
    projection = {key: item for key, item in value.items() if key != "package_identity"}
    return _domain_identity(PACKAGE_DOMAIN, projection, "package_identity")


def _commit_headers(raw: bytes) -> tuple[str, list[str]]:
    if not raw or len(raw) > 32_768 or b"\n\n" not in raw or b"\r" in raw or b"\x00" in raw:
        _reject("V009_MALFORMED_GIT_OBJECT", "commit_framing")
    try:
        header = raw.split(b"\n\n", 1)[0].decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            "V009_MALFORMED_GIT_OBJECT:commit_encoding"
        ) from exc
    lines = header.splitlines()
    trees = [line[5:] for line in lines if line.startswith("tree ")]
    parents = [line[7:] for line in lines if line.startswith("parent ")]
    if len(trees) != 1 or len(parents) > MAX_COMMIT_PARENTS:
        _reject("V009_MALFORMED_GIT_OBJECT", "commit_headers")
    _git_oid(trees[0], "commit_tree")
    for parent in parents:
        _git_oid(parent, "commit_parent")
    return trees[0], parents


def _tree_proof_entry_count(raw: bytes) -> int:
    try:
        proof = strict_json_bytes(raw, maximum_bytes=200_000)
    except ValueError as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            "V009_TREE_PROOF_MISMATCH:canonical_json"
        ) from exc
    if set(proof) != {"steps"} or type(proof["steps"]) is not list:
        _reject("V009_TREE_PROOF_MISMATCH", "schema")
    count = len(proof["steps"])
    if not 1 <= count <= MAX_TREE_PROOF_ENTRIES:
        _reject("V009_TREE_PROOF_MISMATCH", "entry_count")
    return count


def _tree_entries(raw: bytes) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    cursor = 0
    while cursor < len(raw):
        space = raw.find(b" ", cursor)
        nul = raw.find(b"\0", space + 1)
        if space < cursor or nul < space or nul + 21 > len(raw):
            _reject("V009_TREE_PROOF_MISMATCH", "tree_framing")
        try:
            mode = raw[cursor:space].decode("ascii")
            name = raw[space + 1 : nul].decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise OlympicsDocumentaryProofTransportV009Error(
                "V009_TREE_PROOF_MISMATCH:tree_encoding"
            ) from exc
        entries.append((mode, name, raw[nul + 1 : nul + 21].hex()))
        cursor = nul + 21
    return entries


def _inspect_tree_proof(
    raw: bytes,
    *,
    root_oid: str,
    path: str,
    leaf_oid: str,
) -> None:
    _tree_proof_entry_count(raw)
    proof = strict_json_bytes(raw, maximum_bytes=200_000)
    parts = path.split("/")
    if len(proof["steps"]) != len(parts):
        _reject("V009_ARTIFACT_PATH_MISMATCH", "tree_proof_depth")
    expected_tree = root_oid
    for index, raw_step in enumerate(proof["steps"]):
        step = _exact_mapping(
            raw_step,
            {
                "component",
                "mode",
                "object_oid",
                "object_type",
                "raw_tree_base64",
                "tree_oid",
            },
            "tree_proof_step",
        )
        expected_mode = "100644" if index == len(parts) - 1 else "40000"
        expected_type = "blob" if index == len(parts) - 1 else "tree"
        if step["component"] != parts[index]:
            _reject("V009_ARTIFACT_PATH_MISMATCH", "tree_component")
        if step["mode"] != expected_mode:
            _reject("V009_ARTIFACT_MODE_MISMATCH", "tree_mode")
        if step["object_type"] != expected_type:
            _reject("V009_TREE_PROOF_MISMATCH", "object_type")
        object_oid = _git_oid(step["object_oid"], "tree_object_oid")
        tree_oid = _git_oid(step["tree_oid"], "tree_oid")
        encoded = step["raw_tree_base64"]
        if type(encoded) is not str or any(ch.isspace() for ch in encoded):
            _reject("V009_TREE_PROOF_MISMATCH", "tree_base64")
        try:
            tree_raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise OlympicsDocumentaryProofTransportV009Error(
                "V009_TREE_PROOF_MISMATCH:tree_base64"
            ) from exc
        if base64.b64encode(tree_raw).decode("ascii") != encoded:
            _reject("V009_TREE_PROOF_MISMATCH", "tree_base64_canonical")
        if git_object_oid("tree", tree_raw) != tree_oid or tree_oid != expected_tree:
            _reject("V009_TREE_PROOF_MISMATCH", "tree_oid_chain")
        expected_object = leaf_oid if index == len(parts) - 1 else object_oid
        if (expected_mode, parts[index], expected_object) not in _tree_entries(tree_raw):
            _reject("V009_TREE_PROOF_MISMATCH", "tree_entry")
        expected_tree = object_oid
    if expected_tree != leaf_oid:
        _reject("V009_TREE_PROOF_MISMATCH", "leaf_oid")


def _package_binding_identity(envelope: Mapping[str, object]) -> str:
    return _domain_identity(
        PACKAGE_BINDING_DOMAIN,
        {
            "authorization_identity": envelope["authorization_identity"],
            "documentary_binding_identity": envelope["documentary_binding_identity"],
            "v006_operator_package_identity": envelope["v006_operator_package_identity"],
            "v007_runtime_package_identity": envelope["v007_runtime_package_identity"],
            "v008_clock_continuation_identity": envelope["v008_clock_continuation_identity"],
            "v009_contract_identity": envelope["v009_contract_identity"],
        },
        "package_binding_identity",
    )


def validate_envelope(
    envelope: Mapping[str, object],
    authorization: Mapping[str, object],
    documentary_binding: Mapping[str, object],
    *,
    v006_operator_package_identity: str,
    v007_runtime_package_identity: str,
    contract: Mapping[str, object],
    v005_contract: Mapping[str, object],
) -> dict[str, bytes]:
    """Validate and recover the exact seven-value V005 proof input offline."""
    validate_contract(contract)
    if not isinstance(authorization, Mapping) or not isinstance(
        documentary_binding, Mapping
    ):
        _reject("V009_SCHEMA", "documentary_artifacts")
    try:
        validate_v005_contract(v005_contract)
    except OlympicsAuthorizationGovernanceV005Error as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            "V009_CROSS_VERSION_SUBSTITUTION:v005_contract"
        ) from exc
    _exact_mapping(envelope, ENVELOPE_FIELDS, "envelope_fields")
    if envelope["schema_version"] != ENVELOPE_SCHEMA:
        _reject("V009_SCHEMA", "envelope_schema")
    envelope_bytes = _canonical_json_bytes(envelope, "envelope_canonical_json")
    if len(envelope_bytes) > MAX_ENVELOPE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "envelope_limit")
    raw_value = envelope["raw_members"]
    if not isinstance(raw_value, Mapping):
        _reject("V009_RAW_MEMBER_MISSING", "raw_members")
    missing_members = set(RAW_MEMBER_NAMES) - set(raw_value)
    extra_members = set(raw_value) - set(RAW_MEMBER_NAMES)
    if missing_members:
        _reject("V009_RAW_MEMBER_MISSING", "raw_members")
    if extra_members:
        _reject("V009_RAW_MEMBER_EXTRA", "raw_members")
    raw_members = _exact_mapping(raw_value, set(RAW_MEMBER_NAMES), "raw_members")
    declared_total = sum(
        _preflight_member(name, raw_members[name]) for name in RAW_MEMBER_NAMES
    )
    if declared_total > MAX_TOTAL_DECODED_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "total")
    identities = {
        "authorization_identity": authorization.get("authorization_identity"),
        "documentary_binding_identity": documentary_binding.get(
            "documentary_binding_identity"
        ),
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v006_operator_package_identity": _identity(
            v006_operator_package_identity, "v006_package"
        ),
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "v007_runtime_package_identity": _identity(
            v007_runtime_package_identity, "v007_package"
        ),
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "v009_contract_identity": CONTRACT_IDENTITY,
    }
    static_version_fields = {
        "v004_contract_identity",
        "v004_implementation_identity",
        "v005_governance_identity",
        "v005_command_identity",
        "v006_operator_interface_identity",
        "v007_runtime_boundary_identity",
        "v008_clock_continuation_identity",
        "v009_contract_identity",
    }
    for field, expected in identities.items():
        if envelope[field] != expected:
            if field == "authorization_identity":
                code = "V009_AUTHORIZATION_MISMATCH"
            elif field == "documentary_binding_identity":
                code = "V009_DOCUMENTARY_BINDING_MISMATCH"
            elif field in static_version_fields:
                code = "V009_CROSS_VERSION_SUBSTITUTION"
            else:
                code = "V009_PROOF_PACKAGE_MISMATCH"
            _reject(code, field)
    if envelope["package_binding_identity"] != _package_binding_identity(envelope):
        _reject("V009_PROOF_PACKAGE_MISMATCH", "package_binding_identity")
    if envelope["envelope_identity"] != envelope_identity(envelope):
        _reject("V009_PROOF_IDENTITY_MISMATCH", "envelope")
    decoded = {name: _decode_member(name, raw_members[name]) for name in RAW_MEMBER_NAMES}
    if sum(map(len, decoded.values())) != declared_total:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "total")
    if decoded["authorization_bytes"] != _canonical_json_bytes(
        authorization, "authorization_canonical_json"
    ):
        _reject("V009_ARTIFACT_BYTES_MISMATCH", "authorization")
    if decoded["documentary_binding_bytes"] != _canonical_json_bytes(
        documentary_binding, "documentary_binding_canonical_json"
    ):
        _reject("V009_ARTIFACT_BYTES_MISMATCH", "documentary_binding")

    tree_a, parents_a = _commit_headers(decoded["commit_a_raw_bytes"])
    tree_b, parents_b = _commit_headers(decoded["commit_b_raw_bytes"])
    commit_a = git_object_oid("commit", decoded["commit_a_raw_bytes"])
    commit_b = git_object_oid("commit", decoded["commit_b_raw_bytes"])
    declared = (
        (envelope["authorization_commit_a_oid"], commit_a),
        (envelope["documentary_binding_commit_b_oid"], commit_b),
        (envelope["authorization_tree_oid"], tree_a),
        (envelope["binding_tree_oid"], tree_b),
    )
    if any(_git_oid(left, "declared_oid") != right for left, right in declared):
        _reject("V009_DECLARED_OID_MISMATCH", "commit_or_tree")
    if parents_a != [authorization.get("authorized_source_commit")] or parents_b != [commit_a]:
        _reject("V009_COMMIT_PARENT_MISMATCH", "direct_parent")
    auth_blob = git_object_oid("blob", decoded["authorization_bytes"])
    binding_blob = git_object_oid("blob", decoded["documentary_binding_bytes"])
    _inspect_tree_proof(
        decoded["authorization_tree_proof_bytes"],
        root_oid=tree_a,
        path=f"authorizations/{authorization['authorization_identity']}/authorization.json",
        leaf_oid=auth_blob,
    )
    _inspect_tree_proof(
        decoded["binding_tree_proof_bytes"],
        root_oid=tree_b,
        path=f"bindings/{authorization['authorization_identity']}/documentary_binding.json",
        leaf_oid=binding_blob,
    )

    proof = {
        "authorization_bytes": decoded["authorization_bytes"],
        "authorization_tree_proof_bytes": decoded["authorization_tree_proof_bytes"],
        "commit_a_raw_bytes": decoded["commit_a_raw_bytes"],
        "binding_bytes": decoded["documentary_binding_bytes"],
        "binding_tree_proof_bytes": decoded["binding_tree_proof_bytes"],
        "commit_b_raw_bytes": decoded["commit_b_raw_bytes"],
        "commit_b_oid": str(envelope["documentary_binding_commit_b_oid"]),
    }
    try:
        validate_documentary_git_proof(documentary_binding, authorization, v005_contract, proof)
    except OlympicsAuthorizationGovernanceV005Error as exc:
        detail = str(exc).lower()
        if "tree proof" in detail or "tree entry" in detail:
            code = "V009_TREE_PROOF_MISMATCH"
        elif "parent" in detail:
            code = "V009_COMMIT_PARENT_MISMATCH"
        elif "canonical artifacts" in detail:
            code = "V009_ARTIFACT_BYTES_MISMATCH"
        else:
            code = "V009_DOCUMENTARY_BINDING_MISMATCH"
        raise OlympicsDocumentaryProofTransportV009Error(f"{code}:v005") from exc
    return proof


def proof_relative_path(authorization_identity: str) -> str:
    _identity(authorization_identity, "authorization_identity")
    return f"proofs/{authorization_identity}/documentary_git_proof_v009.json"


def package_relative_path(authorization_identity: str) -> str:
    _identity(authorization_identity, "authorization_identity")
    return f"authorizations/{authorization_identity}/documentary_proof_package_v009.json"


def validate_package(
    package: Mapping[str, object],
    envelope: Mapping[str, object],
    envelope_bytes: bytes,
    *,
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Validate V009 reachability from exact sealed V006/V007 roots."""
    validate_contract(contract)
    _exact_mapping(package, PACKAGE_FIELDS, "package_fields")
    _exact_mapping(envelope, ENVELOPE_FIELDS, "package_envelope_fields")
    if package["schema_version"] != PACKAGE_SCHEMA:
        _reject("V009_SCHEMA", "package_schema")
    package_bytes = _canonical_json_bytes(package, "package_canonical_json")
    if len(package_bytes) > MAX_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "package_manifest_limit")
    if type(envelope_bytes) is not bytes or len(envelope_bytes) > MAX_ENVELOPE_BYTES:
        _reject("V009_PROOF_UNREADABLE", "envelope_bytes")
    if envelope_bytes != _canonical_json_bytes(envelope, "envelope_canonical_json"):
        _reject("V009_PROOF_UNREADABLE", "noncanonical_envelope")
    auth = _identity(package["authorization_identity"], "package_authorization")
    path = proof_relative_path(auth)
    digest = hashlib.sha256(envelope_bytes).hexdigest()
    expected_common = {
        "artifact_type": "documentary_git_proof",
        "artifact_identity": envelope["envelope_identity"],
        "relative_path": path,
        "canonical_bytes_sha256": digest,
    }
    v006_entry = _exact_mapping(
        package["v006_record_index_extension"], INDEX_FIELDS_V006, "v006_index_extension"
    )
    v007_entry = _exact_mapping(
        package["v007_supplemental_manifest_entry"],
        INDEX_FIELDS_V007,
        "v007_supplemental_entry",
    )
    if dict(v006_entry) != expected_common or dict(v007_entry) != {
        **expected_common,
        "schema_version": ENVELOPE_SCHEMA,
    }:
        _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "index_entry")
    checks = (
        (package["v009_contract_identity"], CONTRACT_IDENTITY),
        (package["authorization_identity"], envelope["authorization_identity"]),
        (package["documentary_binding_identity"], envelope["documentary_binding_identity"]),
        (package["v006_operator_package_identity"], envelope["v006_operator_package_identity"]),
        (package["v007_runtime_package_identity"], envelope["v007_runtime_package_identity"]),
        (package["v008_clock_continuation_identity"], V008_CLOCK_CONTINUATION_IDENTITY),
        (package["documentary_proof_envelope_identity"], envelope["envelope_identity"]),
        (package["documentary_proof_envelope_relative_path"], path),
    )
    if any(left != right for left, right in checks):
        _reject("V009_PROOF_PACKAGE_MISMATCH", "package_binding")
    if package["package_identity"] != package_identity(package):
        _reject("V009_PROOF_IDENTITY_MISMATCH", "package")
    return dict(package)


def validate_package_inventory(
    members: Mapping[str, bytes],
    *,
    authorization_identity: str,
    package: Mapping[str, object],
    envelope: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    """Reject absent, duplicate/alternate, unindexed, or unreachable proof files."""
    validate_contract(contract)
    _exact_mapping(package, PACKAGE_FIELDS, "inventory_package_fields")
    _exact_mapping(envelope, ENVELOPE_FIELDS, "inventory_envelope_fields")
    proof_path = proof_relative_path(authorization_identity)
    package_path = package_relative_path(authorization_identity)
    expected = {
        proof_path: _canonical_json_bytes(
            envelope, "envelope_canonical_json"
        ),
        package_path: _canonical_json_bytes(
            package, "package_canonical_json"
        ),
    }
    if len(expected[proof_path]) > MAX_ENVELOPE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "envelope_limit")
    if len(expected[package_path]) > MAX_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "package_manifest_limit")
    if sum(len(item) for item in expected.values()) > MAX_TOTAL_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "total_package")
    if not isinstance(members, Mapping):
        _reject("V009_PROOF_UNREADABLE", "inventory")
    for path in members:
        _relative_path(path, "inventory_path")
    proof_paths = [path for path in members if path.endswith("documentary_git_proof_v009.json")]
    if not proof_paths:
        _reject("V009_PROOF_ABSENT", "inventory")
    if len(proof_paths) != 1:
        _reject("V009_PROOF_DUPLICATED", "inventory")
    if set(members) != set(expected):
        _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "closed_world_inventory")
    if any(type(members[path]) is not bytes or members[path] != raw for path, raw in expected.items()):
        _reject("V009_PROOF_IDENTITY_MISMATCH", "inventory_bytes")
    if sum(len(item) for item in members.values()) > MAX_TOTAL_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "total_package")


def validate_storage_observations(
    observations: object,
    members: Mapping[str, bytes],
    *,
    authorization_identity: str,
) -> None:
    """Validate pure, typed storage evidence without performing filesystem I/O."""
    expected_paths = {
        proof_relative_path(authorization_identity),
        package_relative_path(authorization_identity),
    }
    if not isinstance(members, Mapping) or set(members) != expected_paths:
        _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "storage_member_inventory")
    if any(type(members[path]) is not bytes for path in expected_paths):
        _reject("V009_PROOF_UNREADABLE", "storage_member_bytes")
    proof_path = proof_relative_path(authorization_identity)
    package_path = package_relative_path(authorization_identity)
    if len(members[proof_path]) > MAX_ENVELOPE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "envelope_limit")
    if len(members[package_path]) > MAX_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "package_manifest_limit")
    if sum(len(members[path]) for path in expected_paths) > MAX_TOTAL_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "total_package")
    if type(observations) is not list or len(observations) != 2:
        _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "storage_observation_count")
    seen: set[str] = set()
    for raw in observations:
        item = _exact_mapping(raw, STORAGE_OBSERVATION_FIELDS, "storage_observation")
        path = _relative_path(item["relative_path"], "storage_observation_path")
        if path in seen or path not in expected_paths or path not in members:
            _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "storage_observation_path")
        seen.add(path)
        if item["object_type"] != "regular_file" or item["filesystem_mode"] != "0600":
            _reject("V009_ARTIFACT_MODE_MISMATCH", path)
        if item["git_mode"] != "100644":
            _reject("V009_ARTIFACT_MODE_MISMATCH", path)
        if type(item["hard_link_count"]) is not int or item["hard_link_count"] != 1:
            _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "link_state")
        if item["symlink_free"] is not True:
            _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "link_state")
        if item["same_device"] is not True or item["durable"] is not True:
            _reject("V009_DURABILITY_UNCERTAIN", path)
        payload = members[path]
        if type(item["byte_length"]) is not int or item["byte_length"] != len(payload):
            _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "stored_member")
        if item["bytes_sha256"] != hashlib.sha256(payload).hexdigest():
            _reject("V009_RAW_MEMBER_HASH_MISMATCH", "stored_member")
    if seen != expected_paths:
        _reject("V009_PACKAGE_REACHABILITY_UNCERTAIN", "storage_reachability")


def validate_invocation_binding(
    package: Mapping[str, object],
    invocation: Mapping[str, object],
    runtime_package: Mapping[str, object],
) -> None:
    """Bind V009 transitively to V008 without changing the V008 schema."""
    if not isinstance(invocation, Mapping) or not isinstance(runtime_package, Mapping):
        _reject("V009_SCHEMA", "invocation_inputs")
    _exact_mapping(package, PACKAGE_FIELDS, "invocation_package_fields")
    if package["schema_version"] != PACKAGE_SCHEMA:
        _reject("V009_SCHEMA", "invocation_package_schema")
    if len(_canonical_json_bytes(package, "invocation_package_canonical_json")) > MAX_PACKAGE_BYTES:
        _reject("V009_RAW_MEMBER_SIZE_MISMATCH", "package_manifest_limit")
    if package["v009_contract_identity"] != CONTRACT_IDENTITY:
        _reject("V009_CROSS_VERSION_SUBSTITUTION", "invocation_v009_contract")
    if package["v008_clock_continuation_identity"] != V008_CLOCK_CONTINUATION_IDENTITY:
        _reject("V009_CROSS_VERSION_SUBSTITUTION", "invocation_v008_contract")
    if package["package_identity"] != package_identity(package):
        _reject("V009_PROOF_IDENTITY_MISMATCH", "invocation_package")
    package_authorization = _identity(
        package["authorization_identity"], "invocation_package_authorization"
    )
    invocation_authorization = _identity(
        invocation.get("authorization_identity"), "invocation_authorization"
    )
    runtime_authorization = _identity(
        runtime_package.get("authorization_identity"), "runtime_authorization"
    )
    package_v007 = _identity(
        package["v007_runtime_package_identity"], "invocation_package_v007"
    )
    runtime_v007 = _identity(
        runtime_package.get("runtime_package_identity"), "runtime_package_identity"
    )
    package_v006 = _identity(
        package["v006_operator_package_identity"], "invocation_package_v006"
    )
    runtime_v006 = _identity(
        runtime_package.get("v006_operator_package_identity"),
        "runtime_v006_package_identity",
    )
    checks = (
        (package_authorization, invocation_authorization),
        (package_authorization, runtime_authorization),
        (package_v007, runtime_v007),
        (package_v006, runtime_v006),
    )
    if any(left != right for left, right in checks):
        _reject("V009_PROOF_PACKAGE_MISMATCH", "v008_invocation_binding")


def validate_documentary_proof_transport(
    authorization: Mapping[str, object],
    documentary_binding: Mapping[str, object],
    envelope: Mapping[str, object],
    package: Mapping[str, object],
    members: Mapping[str, bytes],
    storage_observations: object,
    invocation: Mapping[str, object],
    runtime_package: Mapping[str, object],
    *,
    v006_operator_package_identity: str,
    v007_runtime_package_identity: str,
    contract: Mapping[str, object],
    v005_contract: Mapping[str, object],
) -> dict[str, bytes]:
    """Run the one frozen, pure V009 validation sequence without path choice."""
    validate_contract(contract)
    if not isinstance(authorization, Mapping):
        _reject("V009_SCHEMA", "authorization")
    authorization_identity = _identity(
        authorization.get("authorization_identity"), "authorization_identity"
    )
    validate_package_inventory(
        members,
        authorization_identity=authorization_identity,
        package=package,
        envelope=envelope,
        contract=contract,
    )
    validate_storage_observations(
        storage_observations,
        members,
        authorization_identity=authorization_identity,
    )
    proof = validate_envelope(
        envelope,
        authorization,
        documentary_binding,
        v006_operator_package_identity=v006_operator_package_identity,
        v007_runtime_package_identity=v007_runtime_package_identity,
        contract=contract,
        v005_contract=v005_contract,
    )
    validate_package(
        package,
        envelope,
        members[proof_relative_path(authorization_identity)],
        contract=contract,
    )
    validate_invocation_binding(package, invocation, runtime_package)
    return proof


def prohibit_fallback(kind: str) -> None:
    """Make all non-package proof acquisition paths explicitly fail closed."""
    prohibited = {
        "network",
        "github_api",
        "remote_fetch",
        "object_database",
        "refs",
        "reflogs",
        "alternates",
        "global_git_config",
        "incidental_clone",
        "external_path",
        "environment_override",
        "descendant_scan",
    }
    if kind not in prohibited:
        _reject("V009_SCHEMA", "fallback_kind")
    _reject("V009_FALLBACK_PROHIBITED", kind)


def _section_projection(name: str, contract: Mapping[str, object]) -> object:
    return contract[name]


def validate_contract(value: Mapping[str, object], root: Path | None = None) -> dict[str, object]:
    """Validate the exact design-only V009 contract and frozen lineage."""
    _exact_mapping(value, ROOT_FIELDS, "contract_fields")
    if len(_canonical_json_bytes(value, "contract_canonical_json")) > MAX_CONTRACT_BYTES:
        _reject("V009_SCHEMA", "contract_size")
    if value["schema_version"] != SCHEMA or value["version"] != VERSION:
        _reject("V009_SCHEMA", "contract_version")
    if value["prospective_as_of"] != "2026-08-03T00:00:00Z":
        _reject("V009_SCHEMA", "prospective_as_of")
    section_identities = _exact_mapping(
        value["section_identities"], set(SECTION_NAMES), "section_identity_inventory"
    )
    for name in SECTION_NAMES:
        expected = _domain_identity(
            f"{CONTRACT_DOMAIN}.section.{name}",
            _section_projection(name, value),
            f"section_{name}",
        )
        if section_identities[name] != expected:
            _reject("V009_PROOF_IDENTITY_MISMATCH", f"section_{name}")
        if EXPECTED_SECTION_IDENTITIES and EXPECTED_SECTION_IDENTITIES.get(name) != expected:
            _reject("V009_PROOF_IDENTITY_MISMATCH", f"frozen_section_{name}")
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    if value["contract_identity"] != _domain_identity(
        CONTRACT_DOMAIN, projection, "contract_identity"
    ):
        _reject("V009_PROOF_IDENTITY_MISMATCH", "contract")
    if CONTRACT_IDENTITY != "0" * 64 and value["contract_identity"] != CONTRACT_IDENTITY:
        _reject("V009_PROOF_IDENTITY_MISMATCH", "frozen_contract")
    inheritance = value["inheritance"]
    expected_lineage = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
    }
    if not isinstance(inheritance, Mapping) or any(inheritance.get(k) != v for k, v in expected_lineage.items()):
        _reject("V009_CROSS_VERSION_SUBSTITUTION", "inheritance")
    model = value["transport_model"]
    if not isinstance(model, Mapping) or model.get("selected_model") != "single_canonical_envelope_all_six_raw_byte_sequences_embedded":
        _reject("V009_SCHEMA", "transport_model")
    if model.get("separate_raw_members_permitted") is not False:
        _reject("V009_SCHEMA", "dual_transport_model")
    envelope_schema = value["envelope_schema"]
    if not isinstance(envelope_schema, Mapping) or envelope_schema.get(
        "package_binding_identity_projection"
    ) != list(PACKAGE_BINDING_FIELD_ORDER):
        _reject("V009_SCHEMA", "package_binding_projection")
    package_integration = value["package_integration"]
    if not isinstance(package_integration, Mapping) or package_integration.get(
        "package_manifest_fields"
    ) != list(PACKAGE_FIELD_ORDER):
        _reject("V009_SCHEMA", "package_manifest_fields")
    validation_manifest = value["validation_manifest"]
    if (
        not isinstance(validation_manifest, Mapping)
        or validation_manifest.get("composite_validator")
        != "validate_documentary_proof_transport"
        or validation_manifest.get("validation_order") != list(VALIDATION_ORDER)
    ):
        _reject("V009_SCHEMA", "validation_order")
    scope = value["capability_scope"]
    if not isinstance(scope, Mapping) or scope.get("design_only") is not True:
        _reject("V009_SCHEMA", "capability_scope")
    if any(scope.get(key) is not False for key in scope if key != "design_only"):
        _reject("V009_SCHEMA", "capability_enabled")
    errors = value["error_status_model"]
    if not isinstance(errors, Mapping) or set(errors.get("failure_codes", [])) != FAILURE_CODES:
        _reject("V009_SCHEMA", "failure_codes")
    limits = value["resource_limits"]
    required_limits = {
        "maximum_contract_bytes": MAX_CONTRACT_BYTES,
        "maximum_envelope_bytes": MAX_ENVELOPE_BYTES,
        "maximum_package_manifest_bytes": MAX_PACKAGE_BYTES,
        "maximum_total_decoded_proof_bytes": MAX_TOTAL_DECODED_BYTES,
        "maximum_total_proof_package_bytes": MAX_TOTAL_PACKAGE_BYTES,
        "maximum_path_bytes": MAX_PATH_BYTES,
        "maximum_tree_proof_entry_count": MAX_TREE_PROOF_ENTRIES,
        "maximum_commit_parent_count": MAX_COMMIT_PARENTS,
    }
    if not isinstance(limits, Mapping) or any(limits.get(k) != v for k, v in required_limits.items()):
        _reject("V009_SCHEMA", "resource_limits")
    if root is not None:
        if v004_implementation_identity(root) != V004_IMPLEMENTATION_IDENTITY:
            _reject("V009_CROSS_VERSION_SUBSTITUTION", "v004_implementation")
        load_v005_contract(root)
        load_v006_contract(root)
        load_v007_contract(root)
        load_v008_contract(root)
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    raw = (root / CONTRACT_PATH).read_bytes()
    if len(raw) > MAX_CONTRACT_BYTES:
        _reject("V009_SCHEMA", "contract_size")
    try:
        value = strict_json_bytes(raw, maximum_bytes=MAX_CONTRACT_BYTES)
    except ValueError as exc:
        raise OlympicsDocumentaryProofTransportV009Error(
            "V009_SCHEMA:contract_canonical_json"
        ) from exc
    return validate_contract(value, root)


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    report = {
        "authorization_created": False,
        "documentary_proof_created": False,
        "execution_permitted": False,
        "operator_implemented": False,
        "official_run_executed": False,
        "proof_transport_model": contract["transport_model"]["selected_model"],
        "status": contract["validation_manifest"]["status"],
        "v009_documentary_proof_transport_identity": contract["contract_identity"],
    }
    return _canonical_json_bytes(report, "validation_report")
