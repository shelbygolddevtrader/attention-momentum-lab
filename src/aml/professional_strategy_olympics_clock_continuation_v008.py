"""Design-only V008 clock continuation and nonce-authority contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from pathlib import Path
import re

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    parse_canonical_timestamp,
    strict_json_bytes,
    validate_artifact as validate_v005_artifact,
    validate_relative_path,
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
    validate_clock_exchange,
    validate_runtime_record,
)


CONTRACT_PATH = "config/professional_strategy_olympics_clock_continuation_v008.json"
SCHEMA = "aml.professional-strategy-olympics.clock-continuation.v008"
VERSION = "professional-strategy-olympics-clock-continuation-v008"
CONTRACT_DOMAIN = "aml.olympics.v008.clock-continuation"
CONTRACT_IDENTITY = "81c2d0caa1f42915acc4558585a43bb5cf0435095bfa3c3145e33e5bbbd0d0dc"
DESIGN_BASE_COMMIT = "0c0a3e60af5fa4cfefc9d0e63933fcea1ca867a3"
V005_GOVERNANCE_IDENTITY = "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0"
V005_COMMAND_IDENTITY = "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb"
V004_IMPLEMENTATION_IDENTITY = "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
MAXIMUM_BYTES = 250_000

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

SECTION_NAMES = (
    "inheritance",
    "nonce_authority",
    "packaged_history",
    "live_session",
    "continuation_storage",
    "lifecycle_binding",
    "interruption_replay_recovery",
    "determinism",
    "runtime_schemas",
    "error_status_model",
    "canonicalization",
    "capability_scope",
    "validation_manifest",
)

EXPECTED_SECTION_IDENTITIES = {
    "inheritance": "940c5e590ba1bcd471710304f85db8f9cac7fe8947017f6e4b7449a198f0098a",
    "nonce_authority": "40b41062b862810c8703fd6a85d715369fd100209580748aa7234bf8321e1d07",
    "packaged_history": "58f62c0b9f8349e37bd431885d328dcd1d930e100a43209aae473f0ae9868cbc",
    "live_session": "42e55f9c8c978a2af8e8157ea1b3df2e5a698e3f6435e8a08d1cd5e35e1e0389",
    "continuation_storage": "446edfddc5ae4d16c75ab8b1de98162cada15b6f6106fe811240ec42c9617421",
    "lifecycle_binding": "4cf588190a44d7c11b76378e92263c70778fc4a8df32603a69e4201b256dea0f",
    "interruption_replay_recovery": "3941be3e1a544e783528f7b3dc5780659b93e952a8777dbfc74dc11fcca65f92",
    "determinism": "aabc067ecd86b077f007da0fc6d979e9b08974ac062ec1fd66ca85d7450c3f41",
    "runtime_schemas": "5c29e974331d711276bc4e3a83412a458f0f975ecf1764b34845dd7b0b724269",
    "error_status_model": "578b1950ecbf0b0eaca06d1efeed1e31603b92e0422f7b912c85819daedbb57d",
    "canonicalization": "dee3f719ce2a91d8f190d8e6173be7f0ec45d3949145334155cde5af22e6fc23",
    "capability_scope": "c90c4926e680dae01b8478dd2f969e635eb5481bf909792ef282cd95c6880e1f",
    "validation_manifest": "182fd82c30dc112e21a4a0de92f14eeb214c3bfd648a2a9ec3aa130a8cd0c8fe",
}

ROOT_FIELDS = {
    "schema_version",
    "version",
    "prospective_as_of",
    "contract_identity",
    *SECTION_NAMES,
    "section_identities",
}

FAILURE_CODES = frozenset(
    {
        "V008_ENTROPY_UNAVAILABLE",
        "V008_NONCE_COLLISION",
        "V008_PACKAGED_HISTORY_REPLAY",
        "V008_SEQUENCE_CONTINUITY",
        "V008_CONTINUATION_STORAGE",
        "V008_CONTINUATION_REPLAY",
        "V008_CONTINUITY_INDETERMINATE",
        "V008_LIFECYCLE_BINDING",
        "V008_SESSION_INTERRUPTED",
        "V008_RECOVERY_PROHIBITED",
    }
)


class OlympicsClockContinuationV008Error(ValueError):
    """A frozen V008 contract or synthetic continuation record is invalid."""


def _reject(code: str, detail: str) -> None:
    raise OlympicsClockContinuationV008Error(f"{code}:{detail}")


def _exact_mapping(value: object, keys: set[str], detail: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _reject("V008_SCHEMA", detail)
    return value


def _identity(value: object, detail: str) -> str:
    if type(value) is not str or not HASH_RE.fullmatch(value):
        _reject("V008_SCHEMA", detail)
    return value


def _nullable_identity(value: object, detail: str) -> str | None:
    if value is None:
        return None
    return _identity(value, detail)


def _token(value: object, detail: str) -> str:
    if type(value) is not str or not TOKEN_RE.fullmatch(value):
        _reject("V008_SCHEMA", detail)
    return value


def _field_name(value: object, detail: str) -> str:
    if type(value) is not str or not FIELD_RE.fullmatch(value):
        _reject("V008_SCHEMA", detail)
    return value


def _uint31_min_2(value: object, detail: str) -> int:
    if type(value) is not int or not 2 <= value <= 2_147_483_647:
        _reject("V008_SCHEMA", detail)
    return value


def validate_nonce_observation(raw: object, *, observed_nonces: set[str]) -> str:
    """Validate one injected pure-test getentropy observation without fallback."""
    if type(raw) is not bytes or len(raw) != 32:
        _reject("V008_ENTROPY_UNAVAILABLE", "exact_32_bytes")
    candidate = raw.hex()
    if candidate in observed_nonces:
        _reject("V008_NONCE_COLLISION", "observed_nonce")
    return candidate


def failure_class(code: str, claim_phase: str) -> str:
    """Return the one frozen classification for a V008 failure and claim phase."""
    if code not in FAILURE_CODES or claim_phase not in {"preclaim", "postclaim"}:
        _reject("V008_SCHEMA", "failure_class_input")
    if code == "V008_CONTINUITY_INDETERMINATE":
        return "indeterminate"
    if code == "V008_PACKAGED_HISTORY_REPLAY":
        return "preclaim_rejection"
    return "preclaim_rejection" if claim_phase == "preclaim" else "postclaim_indeterminate"


def record_identity(record_type: str, record: Mapping[str, object], contract: Mapping[str, object]) -> str:
    schema = contract["runtime_schemas"][record_type]
    identity_field = str(schema["identity_field"])
    projection = {key: item for key, item in record.items() if key != identity_field}
    return domain_hash(str(schema["identity_domain"]), projection)


def _validate_rule(rule: str, value: object, detail: str) -> None:
    if rule == "literal:true":
        if value is not True:
            _reject("V008_SCHEMA", detail)
        return
    if rule == "literal:false":
        if value is not False:
            _reject("V008_SCHEMA", detail)
        return
    if rule.startswith("literal:"):
        if value != rule.removeprefix("literal:"):
            _reject("V008_SCHEMA", detail)
        return
    if rule == "identity":
        _identity(value, detail)
        return
    if rule == "nullable_identity":
        _nullable_identity(value, detail)
        return
    if rule == "uint31_min_2":
        _uint31_min_2(value, detail)
        return
    if rule == "uint31":
        if type(value) is not int or not 0 <= value <= 2_147_483_647:
            _reject("V008_SCHEMA", detail)
        return
    if rule == "uint63":
        if type(value) is not int or not 0 <= value <= 9_223_372_036_854_775_807:
            _reject("V008_SCHEMA", detail)
        return
    if rule.startswith("literal_int:"):
        if type(value) is not int or value != int(rule.removeprefix("literal_int:")):
            _reject("V008_SCHEMA", detail)
        return
    if rule == "artifact_type" or rule == "token":
        _token(value, detail)
        return
    if rule == "field_name":
        _field_name(value, detail)
        return
    if rule == "timestamp":
        try:
            parse_canonical_timestamp(value)
        except ValueError as exc:
            raise OlympicsClockContinuationV008Error(f"V008_SCHEMA:{detail}") from exc
        return
    if rule == "relative_path":
        try:
            validate_relative_path(value)
        except ValueError as exc:
            raise OlympicsClockContinuationV008Error(f"V008_SCHEMA:{detail}") from exc
        return
    if rule.startswith("enum:"):
        if value not in rule.removeprefix("enum:").split("|"):
            _reject("V008_SCHEMA", detail)
        return
    if rule == "v008_failure_code":
        if value not in FAILURE_CODES:
            _reject("V008_SCHEMA", detail)
        return
    if rule == "array_identity_0_16_sorted_unique":
        if (
            type(value) is not list
            or len(value) > 16
            or any(type(item) is not str for item in value)
        ):
            _reject("V008_SCHEMA", detail)
        if value != sorted(value, key=lambda item: item.encode("utf-8")) or len(value) != len(
            set(value)
        ):
            _reject("V008_SCHEMA", detail)
        for item in value:
            _identity(item, detail)
        return
    _reject("V008_SCHEMA", f"unsupported_rule_{detail}")


def validate_continuation_record(
    record_type: str,
    record: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Validate one exact V008 binding or documentary failure record."""
    schemas = contract["runtime_schemas"]
    if record_type not in schemas:
        _reject("V008_SCHEMA", "record_type")
    schema = schemas[record_type]
    fields = schema["fields"]
    _exact_mapping(record, set(fields), record_type)
    for field, rule in fields.items():
        _validate_rule(str(rule), record[field], f"{record_type}_{field}")
    identity_field = str(schema["identity_field"])
    if record[identity_field] != record_identity(record_type, record, contract):
        _reject("V008_SCHEMA", f"{record_type}_identity")
    if record["v008_clock_continuation_contract_identity"] != CONTRACT_IDENTITY:
        _reject("V008_SCHEMA", f"{record_type}_contract_binding")
    if (
        record_type != "continuation_write_evidence"
        and record["runtime_boundary_identity"] != V007_RUNTIME_BOUNDARY_IDENTITY
    ):
        _reject("V008_SCHEMA", f"{record_type}_runtime_binding")

    if record_type == "continuation_invocation":
        if (
            record["first_live_sequence_number"] != 2
            or record["state"] != "durably_claimed_before_entropy_or_socket"
            or record["reuse_policy"] != "single_invocation_no_restart_no_resume"
        ):
            _reject("V008_CONTINUATION_REPLAY", "invocation_claim")
    elif record_type == "continuation_binding":
        sequence = int(record["sequence_number"])
        first = sequence == 2
        if first != (record["prior_continuation_binding_identity"] is None):
            _reject("V008_SEQUENCE_CONTINUITY", "prior_binding")
        if first != (record["packaged_prior_response_identity"] is not None):
            _reject("V008_SEQUENCE_CONTINUITY", "packaged_anchor")
        if record["binding_state"] != "durable_complete":
            _reject("V008_LIFECYCLE_BINDING", "binding_state")
    elif record_type == "continuation_failure":
        expected = failure_class(str(record["failure_code"]), str(record["claim_phase"]))
        if record["failure_class"] != expected or record["reuse_prohibited"] is not True:
            _reject("V008_LIFECYCLE_BINDING", "failure_class")
        if record["response_identity"] is not None and record["request_identity"] is None:
            _reject("V008_SEQUENCE_CONTINUITY", "orphan_response")
    else:
        if (
            record["hard_link_count"] != 1
            or record["same_device"] is not True
            or record["symlink_free"] is not True
        ):
            _reject("V008_CONTINUATION_STORAGE", "write_evidence")
    return dict(record)


def continuation_relative_path(
    record_type: str,
    *,
    authorization_identity: str,
    record_identity_value: str,
    sequence_number: int | None,
) -> str:
    """Render the one frozen relative path for a later continuation record."""
    _identity(authorization_identity, "authorization_identity")
    _identity(record_identity_value, "record_identity")
    if record_type == "continuation_failure":
        if sequence_number is not None:
            _reject("V008_CONTINUATION_STORAGE", "failure_sequence_path")
        return f"evidence/clock/v008/{authorization_identity}/continuation_failure.json"
    if record_type == "continuation_invocation":
        if sequence_number is not None:
            _reject("V008_CONTINUATION_STORAGE", "invocation_sequence_path")
        return f"evidence/clock/v008/{authorization_identity}/invocation.json"
    if record_type not in {"clock_request", "clock_response", "continuation_binding"}:
        _reject("V008_CONTINUATION_STORAGE", "record_type")
    sequence = _uint31_min_2(sequence_number, "sequence_path")
    directory = {
        "clock_request": "requests",
        "clock_response": "responses",
        "continuation_binding": "bindings",
    }[record_type]
    return (
        f"evidence/clock/v008/{authorization_identity}/{directory}/"
        f"{sequence:010d}-{record_identity_value}.json"
    )


def validate_write_evidence(
    evidence: Mapping[str, object],
    target_record_type: str,
    target_record: Mapping[str, object],
    *,
    authorization_identity: str,
    continuation_invocation_identity: str,
    sequence_number: int | None,
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Bind one V008 durability record to exact canonical target bytes and path."""
    if not isinstance(target_record, Mapping):
        _reject("V008_CONTINUATION_STORAGE", "target_record")
    evidence = validate_continuation_record("continuation_write_evidence", evidence, contract)
    identity_fields = {
        "clock_request": "request_identity",
        "clock_response": "response_identity",
        "continuation_binding": "continuation_binding_identity",
        "continuation_failure": "continuation_failure_identity",
        "continuation_invocation": "continuation_invocation_identity",
    }
    identity_field = identity_fields.get(target_record_type)
    if identity_field is None:
        _reject("V008_CONTINUATION_STORAGE", "target_record_type")
    target_identity = _identity(target_record.get(identity_field), "target_identity")
    expected_path = continuation_relative_path(
        target_record_type,
        authorization_identity=authorization_identity,
        record_identity_value=target_identity,
        sequence_number=sequence_number,
    )
    checks = (
        (evidence["authorization_identity"], authorization_identity),
        (evidence["continuation_invocation_identity"], continuation_invocation_identity),
        (evidence["target_record_type"], target_record_type),
        (evidence["target_identity"], target_identity),
        (evidence["target_relative_path"], expected_path),
        (evidence["canonical_bytes_sha256"], hashlib.sha256(canonical_bytes(target_record)).hexdigest()),
    )
    if any(left != right for left, right in checks):
        _reject("V008_CONTINUATION_STORAGE", "write_evidence_binding")
    return evidence


def validate_invocation_binding(
    invocation: Mapping[str, object],
    *,
    authorization_identity: str,
    authoritative_run_identity: str,
    operator_implementation_identity: str,
    session_identity: str,
    packaged_sequence_1_response_identity: str,
    packaged_sequence_1_v005_clock_attestation_identity: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Bind the one invocation claim to exact resolved package/session facts."""
    invocation = validate_continuation_record("continuation_invocation", invocation, contract)
    expected = (
        (invocation["authorization_identity"], _identity(authorization_identity, "authorization")),
        (invocation["authoritative_run_identity"], _identity(authoritative_run_identity, "run")),
        (
            invocation["operator_implementation_identity"],
            _identity(operator_implementation_identity, "operator"),
        ),
        (invocation["session_identity"], _identity(session_identity, "session")),
        (
            invocation["packaged_sequence_1_response_identity"],
            _identity(packaged_sequence_1_response_identity, "packaged_response"),
        ),
        (
            invocation["packaged_sequence_1_v005_clock_attestation_identity"],
            _identity(
                packaged_sequence_1_v005_clock_attestation_identity,
                "packaged_attestation",
            ),
        ),
    )
    if any(actual != resolved for actual, resolved in expected):
        _reject("V008_SEQUENCE_CONTINUITY", "invocation_binding")
    return invocation


def validate_binding_to_invocation(
    binding: Mapping[str, object],
    invocation: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Prove a later lifecycle binding belongs to the single invocation claim."""
    binding = validate_continuation_record("continuation_binding", binding, contract)
    invocation = validate_continuation_record("continuation_invocation", invocation, contract)
    checks = (
        (binding["continuation_invocation_identity"], invocation["continuation_invocation_identity"]),
        (binding["authorization_identity"], invocation["authorization_identity"]),
        (binding["authoritative_run_identity"], invocation["authoritative_run_identity"]),
        (binding["operator_implementation_identity"], invocation["operator_implementation_identity"]),
        (binding["session_identity"], invocation["session_identity"]),
    )
    if any(left != right for left, right in checks):
        _reject("V008_LIFECYCLE_BINDING", "invocation_binding")
    if int(binding["sequence_number"]) == 2 and (
        binding["packaged_prior_response_identity"]
        != invocation["packaged_sequence_1_response_identity"]
    ):
        _reject("V008_SEQUENCE_CONTINUITY", "invocation_packaged_anchor")
    return binding


def validate_failure_binding(
    failure: Mapping[str, object],
    invocation: Mapping[str, object],
    *,
    prior_clock_attestation_identity: str,
    prior_continuation_binding_identity: str | None,
    known_durable_identity_set: Sequence[str],
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Bind a documentary failure marker to exact invocation and durable history."""
    failure = validate_continuation_record("continuation_failure", failure, contract)
    invocation = validate_continuation_record("continuation_invocation", invocation, contract)
    expected_known = list(known_durable_identity_set)
    if (
        len(expected_known) > 16
        or any(type(item) is not str for item in expected_known)
        or expected_known != sorted(expected_known, key=lambda item: item.encode("utf-8"))
        or len(expected_known) != len(set(expected_known))
    ):
        _reject("V008_SCHEMA", "known_durable_identity_set")
    for item in expected_known:
        _identity(item, "known_durable_identity_set")
    prior_attestation = _identity(prior_clock_attestation_identity, "prior_attestation")
    prior_binding = _nullable_identity(prior_continuation_binding_identity, "prior_binding")
    checks = (
        (failure["continuation_invocation_identity"], invocation["continuation_invocation_identity"]),
        (failure["authorization_identity"], invocation["authorization_identity"]),
        (failure["operator_implementation_identity"], invocation["operator_implementation_identity"]),
        (failure["session_identity"], invocation["session_identity"]),
        (failure["prior_clock_attestation_identity"], prior_attestation),
        (failure["prior_continuation_binding_identity"], prior_binding),
        (failure["known_durable_identity_set"], expected_known),
    )
    if any(left != right for left, right in checks):
        _reject("V008_LIFECYCLE_BINDING", "failure_binding")
    if int(failure["failed_sequence_number"]) == 2 and (
        prior_binding is not None
        or prior_attestation
        != invocation["packaged_sequence_1_v005_clock_attestation_identity"]
    ):
        _reject("V008_SEQUENCE_CONTINUITY", "failure_packaged_anchor")
    if int(failure["failed_sequence_number"]) > 2 and prior_binding is None:
        _reject("V008_SEQUENCE_CONTINUITY", "failure_prior_binding")
    return failure


def validate_lifecycle_binding(
    binding: Mapping[str, object],
    invocation: Mapping[str, object],
    request: Mapping[str, object],
    response: Mapping[str, object],
    root_artifact: Mapping[str, object],
    transition_envelope: Mapping[str, object],
    request_write_evidence: Mapping[str, object],
    response_write_evidence: Mapping[str, object],
    *,
    root_artifact_type: str,
    contract: Mapping[str, object],
    v005_contract: Mapping[str, object],
    v007_contract: Mapping[str, object],
    bootstrap: Mapping[str, object],
    previous_verified_timestamp: str,
) -> dict[str, object]:
    """Validate the exact additive edge from a V007 exchange to one V005 transition."""
    binding = validate_binding_to_invocation(binding, invocation, contract)
    request = validate_runtime_record("clock_request", request, v007_contract)
    response = validate_runtime_record("clock_response", response, v007_contract)
    validate_clock_exchange(
        request,
        response,
        bootstrap,
        v007_contract,
        v005_contract,
        previous_verified_timestamp=previous_verified_timestamp,
    )
    root_artifact = validate_v005_artifact(root_artifact, root_artifact_type, v005_contract)
    transition_envelope = validate_v005_artifact(
        transition_envelope, "transition_envelope", v005_contract
    )
    request_write_evidence = validate_write_evidence(
        request_write_evidence,
        "clock_request",
        request,
        authorization_identity=str(binding["authorization_identity"]),
        continuation_invocation_identity=str(binding["continuation_invocation_identity"]),
        sequence_number=int(binding["sequence_number"]),
        contract=contract,
    )
    response_write_evidence = validate_write_evidence(
        response_write_evidence,
        "clock_response",
        response,
        authorization_identity=str(binding["authorization_identity"]),
        continuation_invocation_identity=str(binding["continuation_invocation_identity"]),
        sequence_number=int(binding["sequence_number"]),
        contract=contract,
    )
    timestamp_field = str(binding["v005_timestamp_field"])
    root_schema = v005_contract["artifact_schemas"][root_artifact_type]
    frozen_timestamp_field = v005_contract["lifecycle"]["timestamp_fields"].get(
        root_artifact_type
    )
    checks = (
        (binding["runtime_boundary_identity"], V007_RUNTIME_BOUNDARY_IDENTITY),
        (binding["authorization_identity"], request["authorization_identity"]),
        (binding["authoritative_run_identity"], request["authoritative_run_identity"]),
        (binding["operator_implementation_identity"], request["operator_implementation_identity"]),
        (binding["session_identity"], request["session_identity"]),
        (binding["sequence_number"], request["sequence_number"]),
        (binding["request_identity"], request["request_identity"]),
        (binding["response_identity"], response["response_identity"]),
        (
            binding["request_durability_identity"],
            request_write_evidence["continuation_write_evidence_identity"],
        ),
        (
            binding["response_durability_identity"],
            response_write_evidence["continuation_write_evidence_identity"],
        ),
        (binding["v005_clock_attestation_identity"], response["v005_clock_attestation_identity"]),
        (binding["v005_root_artifact_type"], root_artifact_type),
        (binding["v005_root_artifact_identity"], root_artifact[str(root_schema["identity_field"])]),
        (binding["v005_transition_id"], request["transition_id"]),
        (binding["v005_transition_id"], transition_envelope["transition_id"]),
        (binding["v005_transition_envelope_identity"], transition_envelope["transition_envelope_identity"]),
        (binding["v005_timestamp_field"], request["bound_timestamp_field"]),
        (binding["verified_timestamp"], response["verified_timestamp"]),
        (timestamp_field, frozen_timestamp_field),
        (root_artifact.get(timestamp_field), response["verified_timestamp"]),
        (transition_envelope.get("root_artifact_type"), root_artifact_type),
        (transition_envelope.get("root_artifact_identity"), binding["v005_root_artifact_identity"]),
        (
            transition_envelope.get("durability_evidence_identity"),
            binding["root_durability_identity"],
        ),
    )
    if any(left != right for left, right in checks):
        _reject("V008_LIFECYCLE_BINDING", "resolved_equation")
    return binding


def validate_sequence_chain(
    bindings: Sequence[Mapping[str, object]],
    *,
    packaged_sequence_1_response_identity: str,
    contract: Mapping[str, object],
) -> list[dict[str, object]]:
    """Validate contiguous sequence-2-and-later binding order and ancestry."""
    _identity(packaged_sequence_1_response_identity, "packaged_response")
    validated = [validate_continuation_record("continuation_binding", item, contract) for item in bindings]
    if not validated:
        return []
    if [int(item["sequence_number"]) for item in validated] != list(range(2, 2 + len(validated))):
        _reject("V008_SEQUENCE_CONTINUITY", "sequence")
    identities: set[str] = set()
    invocation_identities = {str(item["continuation_invocation_identity"]) for item in validated}
    if len(invocation_identities) != 1:
        _reject("V008_SEQUENCE_CONTINUITY", "invocation_identity")
    for index, item in enumerate(validated):
        identity = str(item["continuation_binding_identity"])
        if identity in identities:
            _reject("V008_CONTINUATION_REPLAY", "binding_identity")
        identities.add(identity)
        if index == 0:
            if item["packaged_prior_response_identity"] != packaged_sequence_1_response_identity:
                _reject("V008_SEQUENCE_CONTINUITY", "first_anchor")
        elif item["prior_continuation_binding_identity"] != validated[index - 1]["continuation_binding_identity"]:
            _reject("V008_SEQUENCE_CONTINUITY", "binding_chain")
    return validated


def validate_contract(value: Mapping[str, object], root: Path | None = None) -> dict[str, object]:
    """Validate the frozen design-only V008 contract and predecessor identities."""
    _exact_mapping(value, ROOT_FIELDS, "root")
    if value["schema_version"] != SCHEMA or value["version"] != VERSION:
        _reject("V008_SCHEMA", "version")
    for name in SECTION_NAMES:
        if not isinstance(value[name], Mapping):
            _reject("V008_SCHEMA", f"section_{name}")
    section_identities = _exact_mapping(
        value["section_identities"], set(SECTION_NAMES), "section_identities"
    )
    for name in SECTION_NAMES:
        expected = EXPECTED_SECTION_IDENTITIES[name]
        if section_identities[name] != expected or domain_hash(
            f"aml.olympics.v008.section.{name}", value[name]
        ) != expected:
            _reject("V008_SCHEMA", f"section_identity_{name}")
    try:
        parse_canonical_timestamp(value["prospective_as_of"])
    except ValueError as exc:
        raise OlympicsClockContinuationV008Error("V008_SCHEMA:prospective_as_of") from exc

    inheritance = value["inheritance"]
    expected_lineage = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "immutable_tag_name": "v0.1.1-research-baseline",
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
    }
    if any(inheritance.get(key) != expected for key, expected in expected_lineage.items()):
        _reject("V008_SCHEMA", "inheritance")
    if inheritance.get("relationship") != "additive_successor_resolving_only_post_package_clock_session_continuation_and_nonce_authority":
        _reject("V008_SCHEMA", "scope")

    if value["packaged_history"]["packaged_sequences"] != [0, 1]:
        _reject("V008_SEQUENCE_CONTINUITY", "packaged_sequences")
    if value["live_session"]["first_live_sequence"] != 2:
        _reject("V008_SEQUENCE_CONTINUITY", "first_live_sequence")
    if value["nonce_authority"]["sole_generator"] != "the_exact_authorized_V005_operator_process_after_operator_identity_package_source_repository_and_prior_clock_history_validation":
        _reject("V008_SCHEMA", "nonce_authority")
    if value["nonce_authority"]["entropy_source"] != "macOS_getentropy(2)_one_successful_call_for_exactly_32_bytes_per_request_nonce":
        _reject("V008_SCHEMA", "entropy_source")
    if value["continuation_storage"]["ephemeral_records"] != "none":
        _reject("V008_SCHEMA", "storage")
    if value["live_session"]["reconnect"] != "prohibited":
        _reject("V008_SCHEMA", "reconnect")
    if value["interruption_replay_recovery"]["same_authorization_restart"] != "prohibited_even_if_no_V005_mutation_was_published":
        _reject("V008_SCHEMA", "restart")

    scope = value["capability_scope"]
    if (
        not isinstance(scope, Mapping)
        or scope.get("design_only") is not True
        or scope.get("clock_continuation_contract_frozen") is not True
        or any(item is not False for key, item in scope.items() if key not in {"design_only", "clock_continuation_contract_frozen"})
    ):
        _reject("V008_SCHEMA", "capability_scope")
    if value["validation_manifest"]["execution_permitted"] is not False:
        _reject("V008_SCHEMA", "execution_permitted")
    if not isinstance(value["error_status_model"].get("errors"), Mapping) or set(
        value["error_status_model"]["errors"]
    ) != FAILURE_CODES:
        _reject("V008_SCHEMA", "failure_codes")

    schemas = value["runtime_schemas"]
    if set(schemas) != {
        "continuation_binding",
        "continuation_failure",
        "continuation_write_evidence",
        "continuation_invocation",
    }:
        _reject("V008_SCHEMA", "runtime_schemas")
    for name, schema in schemas.items():
        if set(schema) != {"schema_version", "identity_domain", "identity_field", "fields"}:
            _reject("V008_SCHEMA", f"schema_{name}")
        fields = schema["fields"]
        if not isinstance(fields, Mapping) or schema["identity_field"] not in fields:
            _reject("V008_SCHEMA", f"schema_fields_{name}")

    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    if value["contract_identity"] != CONTRACT_IDENTITY or domain_hash(CONTRACT_DOMAIN, projection) != CONTRACT_IDENTITY:
        _reject("V008_SCHEMA", "contract_identity")

    if root is not None:
        load_v005_contract(root)
        load_v006_contract(root)
        load_v007_contract(root)
        if v004_implementation_identity(root) != V004_IMPLEMENTATION_IDENTITY:
            _reject("V008_SCHEMA", "v004_implementation")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    try:
        raw = (root / CONTRACT_PATH).read_bytes()
    except OSError as exc:
        raise OlympicsClockContinuationV008Error("V008_SCHEMA:contract_missing") from exc
    try:
        value = strict_json_bytes(raw, maximum_bytes=MAXIMUM_BYTES)
    except ValueError as exc:
        raise OlympicsClockContinuationV008Error("V008_SCHEMA:contract_bytes") from exc
    return validate_contract(value, root)


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_bytes(validate_contract(value))


def validation_report(root: Path) -> bytes:
    value = load_contract(root)
    report = {
        "authorization_present": False,
        "clock_continuation_identity": value["contract_identity"],
        "clock_verifier_present": False,
        "design_contract_valid": True,
        "execution_permitted": False,
        "operator_present": False,
        "repository_attestor_present": False,
        "status": value["validation_manifest"]["status"],
    }
    return canonical_bytes(report)


def contract_file_sha256(root: Path) -> str:
    return hashlib.sha256((root / CONTRACT_PATH).read_bytes()).hexdigest()
