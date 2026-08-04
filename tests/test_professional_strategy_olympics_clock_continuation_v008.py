from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import aml.professional_strategy_olympics_clock_continuation_v008 as continuation_module
from aml.professional_strategy_olympics_authorization_governance_v005 import (
    canonical_bytes,
    domain_hash,
    strict_json_bytes,
)
from aml.professional_strategy_olympics_clock_continuation_v008 import (
    CONTRACT_DOMAIN,
    CONTRACT_IDENTITY,
    CONTRACT_PATH,
    DESIGN_BASE_COMMIT,
    EXPECTED_SECTION_IDENTITIES,
    FAILURE_CODES,
    OlympicsClockContinuationV008Error,
    SECTION_NAMES,
    canonical_contract_bytes,
    continuation_relative_path,
    failure_class,
    load_contract,
    record_identity,
    validate_binding_to_invocation,
    validate_continuation_record,
    validate_contract,
    validate_failure_binding,
    validate_invocation_binding,
    validate_lifecycle_binding,
    validate_nonce_observation,
    validate_sequence_chain,
    validate_write_evidence,
    validation_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_clock_continuation_v008.py"
H = "a" * 64
H2 = "b" * 64
H3 = "c" * 64
T = "2026-08-03T12:00:00Z"
# Scope the historical design-only assertion to the audited V008 merge. Using
# the current HEAD would incorrectly prohibit unrelated future research results.
DESIGN_MILESTONE_MERGE_COMMIT = "02529b3001d090c48186607d398b73209e8deb85"


def contract() -> dict[str, object]:
    return load_contract(ROOT)


def reseal_contract(value: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(value)
    changed["contract_identity"] = domain_hash(
        CONTRACT_DOMAIN,
        {key: item for key, item in changed.items() if key != "contract_identity"},
    )
    return changed


def seal_record(record_type: str, value: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(value)
    schema = contract()["runtime_schemas"][record_type]
    field = str(schema["identity_field"])
    result[field] = record_identity(record_type, result, contract())
    return result


def binding(sequence: int = 2, prior: str | None = None) -> dict[str, object]:
    first = sequence == 2
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-continuation-binding.v008",
        "continuation_binding_identity": H,
        "continuation_invocation_identity": "e" * 64,
        "v008_clock_continuation_contract_identity": CONTRACT_IDENTITY,
        "runtime_boundary_identity": "a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45",
        "authorization_identity": "1" * 64,
        "authoritative_run_identity": "2" * 64,
        "operator_implementation_identity": "3" * 64,
        "session_identity": "4" * 64,
        "sequence_number": sequence,
        "request_identity": "5" * 64,
        "response_identity": "6" * 64,
        "packaged_prior_response_identity": "7" * 64 if first else None,
        "prior_continuation_binding_identity": None if first else prior,
        "v005_clock_attestation_identity": "8" * 64,
        "v005_root_artifact_type": "activation",
        "v005_root_artifact_identity": "9" * 64,
        "v005_transition_id": "authorization_activated",
        "v005_transition_envelope_identity": "a" * 64,
        "v005_timestamp_field": "activated_at",
        "verified_timestamp": T,
        "request_durability_identity": "b" * 64,
        "response_durability_identity": "c" * 64,
        "root_durability_identity": "d" * 64,
        "binding_state": "durable_complete",
    }
    return seal_record("continuation_binding", value)


def unique_binding(sequence: int, prior: str | None) -> dict[str, object]:
    value = binding(sequence, prior)
    for offset, field in enumerate(
        (
            "request_identity",
            "response_identity",
            "v005_clock_attestation_identity",
            "v005_root_artifact_identity",
            "v005_transition_envelope_identity",
        ),
        start=10,
    ):
        value[field] = f"{sequence * 100 + offset:064x}"
    return seal_record("continuation_binding", value)


def failure(code: str = "V008_ENTROPY_UNAVAILABLE", phase: str = "preclaim") -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-continuation-failure.v008",
        "continuation_failure_identity": H,
        "continuation_invocation_identity": "e" * 64,
        "v008_clock_continuation_contract_identity": CONTRACT_IDENTITY,
        "runtime_boundary_identity": "a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45",
        "authorization_identity": "1" * 64,
        "operator_implementation_identity": "3" * 64,
        "session_identity": "4" * 64,
        "failed_sequence_number": 2,
        "request_identity": None,
        "response_identity": None,
        "prior_clock_attestation_identity": "8" * 64,
        "prior_continuation_binding_identity": None,
        "claim_phase": phase,
        "failure_code": code,
        "failure_class": failure_class(code, phase),
        "known_durable_identity_set": [],
        "reuse_prohibited": True,
        "authority": "documentary_quarantine_only_no_V005_transition",
    }
    return seal_record("continuation_failure", value)


def write_evidence(target_type: str = "clock_request") -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-continuation-write-evidence.v008",
        "continuation_write_evidence_identity": H,
        "v008_clock_continuation_contract_identity": CONTRACT_IDENTITY,
        "authorization_identity": "1" * 64,
        "target_record_type": target_type,
        "target_identity": "5" * 64,
        "target_relative_path": "evidence/clock/v008/example.json",
        "canonical_bytes_sha256": "6" * 64,
        "continuation_invocation_identity": "e" * 64,
        "device_id": 1,
        "mount_id": 2,
        "owner_uid": 501,
        "group_gid": 20,
        "root_mode": "0700",
        "file_mode": "0600",
        "hard_link_count": 1,
        "same_device": True,
        "symlink_free": True,
        "exclusive_creation_result": "won",
        "file_fullfsync_result": "success",
        "file_close_result": "success",
        "directory_fsync_result": "success",
        "durability_trace": "open_root_no_follow|verify_mount_device_owner_mode|exclusive_create|write_complete|f_fullfsync_file|close_file|fsync_directory",
    }
    return seal_record("continuation_write_evidence", value)


def invocation() -> dict[str, object]:
    value = {
        "schema_version": "aml.professional-strategy-olympics.clock-continuation-invocation.v008",
        "continuation_invocation_identity": H,
        "v008_clock_continuation_contract_identity": CONTRACT_IDENTITY,
        "runtime_boundary_identity": "a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45",
        "authorization_identity": "1" * 64,
        "authoritative_run_identity": "2" * 64,
        "operator_implementation_identity": "3" * 64,
        "session_identity": "4" * 64,
        "packaged_sequence_1_response_identity": "5" * 64,
        "packaged_sequence_1_v005_clock_attestation_identity": "6" * 64,
        "first_live_sequence_number": 2,
        "state": "durably_claimed_before_entropy_or_socket",
        "reuse_policy": "single_invocation_no_restart_no_resume",
    }
    return seal_record("continuation_invocation", value)


def bound_write_evidence(
    target_type: str, target: dict[str, object], sequence: int | None
) -> dict[str, object]:
    identity_field = {
        "clock_request": "request_identity",
        "clock_response": "response_identity",
        "continuation_binding": "continuation_binding_identity",
        "continuation_failure": "continuation_failure_identity",
        "continuation_invocation": "continuation_invocation_identity",
    }[target_type]
    result = write_evidence(target_type)
    result["target_identity"] = target[identity_field]
    result["continuation_invocation_identity"] = (
        target["continuation_invocation_identity"]
        if "continuation_invocation_identity" in target
        else "e" * 64
    )
    result["target_relative_path"] = continuation_relative_path(
        target_type,
        authorization_identity="1" * 64,
        record_identity_value=str(target[identity_field]),
        sequence_number=sequence,
    )
    result["canonical_bytes_sha256"] = hashlib.sha256(canonical_bytes(target)).hexdigest()
    return seal_record("continuation_write_evidence", result)


def mutate_leaf(value: object) -> object:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return f"{value}_changed"
    if type(value) is list:
        return [*value, "changed"]
    if type(value) is dict:
        changed = copy.deepcopy(value)
        key = next(iter(changed))
        changed[key] = mutate_leaf(changed[key])
        return changed
    raise AssertionError(type(value))


def test_contract_loads_with_exact_identity_size_and_canonical_bytes() -> None:
    value = contract()
    raw = (ROOT / CONTRACT_PATH).read_bytes()
    assert len(raw) == 24_335
    assert raw == canonical_bytes(value) == canonical_contract_bytes(value)
    assert value["contract_identity"] == CONTRACT_IDENTITY
    assert value["schema_version"] == "aml.professional-strategy-olympics.clock-continuation.v008"
    assert value["capability_scope"]["design_only"] is True
    assert value["validation_manifest"]["execution_permitted"] is False


def test_outer_identity_reproduces_independently() -> None:
    value = contract()
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    direct = hashlib.sha256(
        CONTRACT_DOMAIN.encode("ascii") + b"\0" + canonical_bytes(projection)
    ).hexdigest()
    assert direct == CONTRACT_IDENTITY


@pytest.mark.parametrize("name", SECTION_NAMES)
def test_every_section_identity_reproduces(name: str) -> None:
    value = contract()
    assert (
        domain_hash(f"aml.olympics.v008.section.{name}", value[name])
        == value["section_identities"][name]
        == EXPECTED_SECTION_IDENTITIES[name]
    )


@pytest.mark.parametrize("name", SECTION_NAMES)
def test_every_normative_section_mutation_rejects_even_when_resealed(name: str) -> None:
    changed = copy.deepcopy(contract())
    changed[name] = mutate_leaf(changed[name])
    changed["section_identities"][name] = domain_hash(
        f"aml.olympics.v008.section.{name}", changed[name]
    )
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_contract(reseal_contract(changed))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("nonce_authority"),
        lambda value: value.update({"unknown": True}),
        lambda value: value["nonce_authority"].update({"generation_model": "deterministic"}),
        lambda value: value["nonce_authority"].update({"sole_generator": "clock_verifier"}),
        lambda value: value["nonce_authority"].update({"retry_policy": "retry"}),
        lambda value: value["packaged_history"].update({"wire_behavior": "replay"}),
        lambda value: value["live_session"].update({"first_live_sequence": 1}),
        lambda value: value["live_session"].update({"reconnect": "permitted"}),
        lambda value: value["continuation_storage"].update({"ephemeral_records": "responses"}),
        lambda value: value["interruption_replay_recovery"].update({"same_authorization_restart": "permitted"}),
        lambda value: value["capability_scope"].update({"operator_implemented": True}),
        lambda value: value["validation_manifest"].update({"execution_permitted": True}),
    ],
)
def test_security_weakening_rejects_after_outer_reseal(mutation) -> None:
    changed = copy.deepcopy(contract())
    mutation(changed)
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_contract(reseal_contract(changed))


@pytest.mark.parametrize(
    "transform",
    [
        lambda raw: b" " + raw,
        lambda raw: raw[:-1],
        lambda raw: raw + b"\n",
        lambda raw: raw[:-1] + b"\r\n",
        lambda raw: b"\xef\xbb\xbf" + raw,
        lambda raw: json.dumps(json.loads(raw), indent=2).encode("ascii") + b"\n",
        lambda raw: raw.replace(b'"version":', b'"version":"duplicate","version":', 1),
    ],
)
def test_noncanonical_duplicate_and_framing_contract_bytes_reject(transform) -> None:
    raw = (ROOT / CONTRACT_PATH).read_bytes()
    with pytest.raises(ValueError):
        strict_json_bytes(transform(raw), maximum_bytes=250_000)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1.0}\n',
        b'{"a":NaN}\n',
        b'{"a":-0.0}\n',
        b'{"a":"\xff"}\n',
        '{"a":"e\u0301"}\n'.encode(),
    ],
)
def test_float_nonfinite_invalid_utf8_and_non_nfc_reject(raw: bytes) -> None:
    with pytest.raises(ValueError):
        strict_json_bytes(raw)


def test_nonce_observation_is_exact_lowercase_hex_and_does_not_mutate_seen_set() -> None:
    seen = {"01" * 32}
    assert validate_nonce_observation(bytes(range(32)), observed_nonces=seen) == bytes(range(32)).hex()
    assert seen == {"01" * 32}


@pytest.mark.parametrize("raw", [None, "00" * 32, b"", b"x" * 31, b"x" * 33])
def test_nonce_unavailable_paths_fail_closed(raw: object) -> None:
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_ENTROPY_UNAVAILABLE"):
        validate_nonce_observation(raw, observed_nonces=set())


def test_nonce_collision_has_no_retry_result() -> None:
    raw = b"x" * 32
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_NONCE_COLLISION"):
        validate_nonce_observation(raw, observed_nonces={raw.hex()})


@pytest.mark.parametrize("code", sorted(FAILURE_CODES))
@pytest.mark.parametrize("phase", ["preclaim", "postclaim"])
def test_every_failure_has_one_closed_classification(code: str, phase: str) -> None:
    result = failure_class(code, phase)
    if code == "V008_CONTINUITY_INDETERMINATE":
        assert result == "indeterminate"
    elif code == "V008_PACKAGED_HISTORY_REPLAY":
        assert result == "preclaim_rejection"
    else:
        assert result == ("preclaim_rejection" if phase == "preclaim" else "postclaim_indeterminate")


def test_unknown_failure_or_phase_rejects() -> None:
    with pytest.raises(OlympicsClockContinuationV008Error):
        failure_class("V008_UNKNOWN", "preclaim")
    with pytest.raises(OlympicsClockContinuationV008Error):
        failure_class("V008_ENTROPY_UNAVAILABLE", "unknown")


def test_canonical_binding_and_failure_records_validate() -> None:
    assert validate_continuation_record("continuation_binding", binding(), contract())["sequence_number"] == 2
    assert validate_continuation_record("continuation_write_evidence", write_evidence(), contract())[
        "target_record_type"
    ] == "clock_request"
    assert validate_continuation_record("continuation_invocation", invocation(), contract())[
        "first_live_sequence_number"
    ] == 2
    for code in FAILURE_CODES:
        for phase in ("preclaim", "postclaim"):
            assert validate_continuation_record("continuation_failure", failure(code, phase), contract())[
                "failure_code"
            ] == code


@pytest.mark.parametrize(
    "record_type,factory",
    [
        ("continuation_binding", binding),
        ("continuation_failure", failure),
        ("continuation_write_evidence", write_evidence),
        ("continuation_invocation", invocation),
    ],
)
def test_every_record_field_is_required_and_unknown_fields_reject(record_type: str, factory) -> None:
    value = factory()
    for field in tuple(value):
        changed = copy.deepcopy(value)
        changed.pop(field)
        with pytest.raises(OlympicsClockContinuationV008Error):
            validate_continuation_record(record_type, changed, contract())
    changed = copy.deepcopy(value)
    changed["unknown"] = True
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_continuation_record(record_type, changed, contract())


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence_number", 1),
        ("sequence_number", True),
        ("verified_timestamp", "2026-08-03T12:00:00-06:00"),
        ("v005_transition_id", "UPPER"),
        ("binding_state", "partial"),
        ("v008_clock_continuation_contract_identity", H),
        ("runtime_boundary_identity", H),
    ],
)
def test_binding_wrong_types_values_and_contract_substitution_reject(field: str, value: object) -> None:
    changed = binding()
    changed[field] = value
    changed = seal_record("continuation_binding", changed)
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_continuation_record("continuation_binding", changed, contract())


def test_first_and_later_binding_anchors_are_mutually_exclusive() -> None:
    first = binding()
    first["prior_continuation_binding_identity"] = H2
    first = seal_record("continuation_binding", first)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_continuation_record("continuation_binding", first, contract())
    later = binding(3, H2)
    later["packaged_prior_response_identity"] = H3
    later = seal_record("continuation_binding", later)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_continuation_record("continuation_binding", later, contract())


def test_response_without_request_is_rejected_in_failure_record() -> None:
    changed = failure()
    changed["response_identity"] = H2
    changed = seal_record("continuation_failure", changed)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_continuation_record("continuation_failure", changed, contract())


def test_write_evidence_binds_exact_target_bytes_identity_and_path() -> None:
    target = binding()
    evidence = bound_write_evidence("continuation_binding", target, 2)
    assert validate_write_evidence(
        evidence,
        "continuation_binding",
        target,
        authorization_identity="1" * 64,
        continuation_invocation_identity=str(target["continuation_invocation_identity"]),
        sequence_number=2,
        contract=contract(),
    )["target_identity"] == target["continuation_binding_identity"]
    invocation_record = invocation()
    invocation_evidence = bound_write_evidence("continuation_invocation", invocation_record, None)
    assert validate_write_evidence(
        invocation_evidence,
        "continuation_invocation",
        invocation_record,
        authorization_identity="1" * 64,
        continuation_invocation_identity=str(invocation_record["continuation_invocation_identity"]),
        sequence_number=None,
        contract=contract(),
    )["target_identity"] == invocation_record["continuation_invocation_identity"]


@pytest.mark.parametrize("mutation", ["path", "hash", "identity", "type", "authorization"])
def test_write_evidence_target_substitution_rejects(mutation: str) -> None:
    target = binding()
    evidence = bound_write_evidence("continuation_binding", target, 2)
    if mutation == "path":
        evidence["target_relative_path"] = "evidence/clock/v008/wrong.json"
    elif mutation == "hash":
        evidence["canonical_bytes_sha256"] = H2
    elif mutation == "identity":
        evidence["target_identity"] = H2
    elif mutation == "type":
        evidence["target_record_type"] = "clock_request"
    else:
        evidence["authorization_identity"] = H2
    evidence = seal_record("continuation_write_evidence", evidence)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_STORAGE"):
        validate_write_evidence(
            evidence,
            "continuation_binding",
            target,
            authorization_identity="1" * 64,
            continuation_invocation_identity=str(target["continuation_invocation_identity"]),
            sequence_number=2,
            contract=contract(),
        )


def test_failure_path_has_no_sequence_alias() -> None:
    target = failure()
    assert continuation_relative_path(
        "continuation_failure",
        authorization_identity="1" * 64,
        record_identity_value=str(target["continuation_failure_identity"]),
        sequence_number=None,
    ).endswith("/continuation_failure.json")
    with pytest.raises(OlympicsClockContinuationV008Error):
        continuation_relative_path(
            "continuation_failure",
            authorization_identity="1" * 64,
            record_identity_value=str(target["continuation_failure_identity"]),
            sequence_number=2,
        )


def test_invocation_claim_path_state_and_no_sequence_alias_are_exact() -> None:
    value = invocation()
    assert continuation_relative_path(
        "continuation_invocation",
        authorization_identity="1" * 64,
        record_identity_value=str(value["continuation_invocation_identity"]),
        sequence_number=None,
    ).endswith("/invocation.json")
    for field, replacement in (
        ("first_live_sequence_number", 3),
        ("state", "partial"),
        ("reuse_policy", "resume"),
    ):
        changed = copy.deepcopy(value)
        changed[field] = replacement
        changed = seal_record("continuation_invocation", changed)
        with pytest.raises(OlympicsClockContinuationV008Error):
            validate_continuation_record("continuation_invocation", changed, contract())


def test_invocation_claim_binds_every_resolved_package_and_session_identity() -> None:
    value = invocation()
    evidence = bound_write_evidence("continuation_invocation", value, None)
    assert validate_invocation_binding(
        value,
        evidence,
        authorization_identity="1" * 64,
        authoritative_run_identity="2" * 64,
        operator_implementation_identity="3" * 64,
        session_identity="4" * 64,
        packaged_sequence_1_response_identity="5" * 64,
        packaged_sequence_1_v005_clock_attestation_identity="6" * 64,
        contract=contract(),
    )["continuation_invocation_identity"] == value["continuation_invocation_identity"]
    for field in (
        "authorization_identity",
        "authoritative_run_identity",
        "operator_implementation_identity",
        "session_identity",
        "packaged_sequence_1_response_identity",
        "packaged_sequence_1_v005_clock_attestation_identity",
    ):
        kwargs = {
            "authorization_identity": "1" * 64,
            "authoritative_run_identity": "2" * 64,
            "operator_implementation_identity": "3" * 64,
            "session_identity": "4" * 64,
            "packaged_sequence_1_response_identity": "5" * 64,
            "packaged_sequence_1_v005_clock_attestation_identity": "6" * 64,
        }
        kwargs[field] = "f" * 64
        with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
            validate_invocation_binding(value, evidence, contract=contract(), **kwargs)

    altered_evidence = copy.deepcopy(evidence)
    altered_evidence["canonical_bytes_sha256"] = H2
    altered_evidence = seal_record("continuation_write_evidence", altered_evidence)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_STORAGE"):
        validate_invocation_binding(
            value,
            altered_evidence,
            authorization_identity="1" * 64,
            authoritative_run_identity="2" * 64,
            operator_implementation_identity="3" * 64,
            session_identity="4" * 64,
            packaged_sequence_1_response_identity="5" * 64,
            packaged_sequence_1_v005_clock_attestation_identity="6" * 64,
            contract=contract(),
        )


def test_binding_and_failure_records_resolve_to_the_single_invocation_claim() -> None:
    invocation_record = invocation()
    invocation_record["packaged_sequence_1_response_identity"] = "7" * 64
    invocation_record["packaged_sequence_1_v005_clock_attestation_identity"] = "8" * 64
    invocation_record = seal_record("continuation_invocation", invocation_record)
    lifecycle = binding()
    lifecycle["continuation_invocation_identity"] = invocation_record[
        "continuation_invocation_identity"
    ]
    lifecycle = seal_record("continuation_binding", lifecycle)
    assert validate_binding_to_invocation(lifecycle, invocation_record, contract()) == lifecycle

    marker = failure()
    marker["continuation_invocation_identity"] = invocation_record[
        "continuation_invocation_identity"
    ]
    marker = seal_record("continuation_failure", marker)
    marker_evidence = bound_write_evidence("continuation_failure", marker, None)
    assert validate_failure_binding(
        marker,
        invocation_record,
        marker_evidence,
        prior_clock_attestation_identity="8" * 64,
        prior_continuation_binding_identity=None,
        known_durable_identity_set=[],
        contract=contract(),
    ) == marker

    altered_evidence = copy.deepcopy(marker_evidence)
    altered_evidence["canonical_bytes_sha256"] = H2
    altered_evidence = seal_record("continuation_write_evidence", altered_evidence)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_STORAGE"):
        validate_failure_binding(
            marker,
            invocation_record,
            altered_evidence,
            prior_clock_attestation_identity="8" * 64,
            prior_continuation_binding_identity=None,
            known_durable_identity_set=[],
            contract=contract(),
        )

    substituted = copy.deepcopy(marker)
    substituted["continuation_invocation_identity"] = H2
    substituted = seal_record("continuation_failure", substituted)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_LIFECYCLE_BINDING"):
        validate_failure_binding(
            substituted,
            invocation_record,
            marker_evidence,
            prior_clock_attestation_identity="8" * 64,
            prior_continuation_binding_identity=None,
            known_durable_identity_set=[],
            contract=contract(),
        )


def test_later_failure_requires_exact_prior_binding_and_sorted_durable_history() -> None:
    invocation_record = invocation()
    marker = failure()
    marker["failed_sequence_number"] = 3
    marker["prior_continuation_binding_identity"] = H2
    marker["prior_clock_attestation_identity"] = H3
    marker["continuation_invocation_identity"] = invocation_record[
        "continuation_invocation_identity"
    ]
    marker["known_durable_identity_set"] = ["1" * 64, "2" * 64]
    marker = seal_record("continuation_failure", marker)
    marker_evidence = bound_write_evidence("continuation_failure", marker, None)
    assert validate_failure_binding(
        marker,
        invocation_record,
        marker_evidence,
        prior_clock_attestation_identity=H3,
        prior_continuation_binding_identity=H2,
        known_durable_identity_set=["1" * 64, "2" * 64],
        contract=contract(),
    ) == marker
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_failure_binding(
            marker,
            invocation_record,
            marker_evidence,
            prior_clock_attestation_identity=H3,
            prior_continuation_binding_identity=None,
            known_durable_identity_set=["2" * 64, "1" * 64],
            contract=contract(),
        )


def test_non_mapping_write_target_fails_with_stable_storage_code() -> None:
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_STORAGE"):
        validate_write_evidence(
            write_evidence(),
            "clock_request",
            [],  # type: ignore[arg-type]
            authorization_identity="1" * 64,
            continuation_invocation_identity="e" * 64,
            sequence_number=2,
            contract=contract(),
        )


def test_malformed_known_durable_array_fails_with_stable_code() -> None:
    changed = failure()
    changed["known_durable_identity_set"] = [{}]
    changed = seal_record("continuation_failure", changed)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SCHEMA"):
        validate_continuation_record("continuation_failure", changed, contract())


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_record_type", "unknown"),
        ("target_relative_path", "../escape.json"),
        ("device_id", -1),
        ("mount_id", True),
        ("owner_uid", 2_147_483_648),
        ("hard_link_count", 2),
        ("same_device", False),
        ("symlink_free", False),
        ("file_fullfsync_result", "failed"),
    ],
)
def test_write_evidence_wrong_path_type_durability_or_filesystem_rejects(
    field: str, value: object
) -> None:
    changed = write_evidence()
    changed[field] = value
    changed = seal_record("continuation_write_evidence", changed)
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_continuation_record("continuation_write_evidence", changed, contract())


def test_sequence_chain_starts_at_two_is_contiguous_and_ancestry_bound() -> None:
    first = unique_binding(2, None)
    second = unique_binding(3, first["continuation_binding_identity"])
    third = unique_binding(4, second["continuation_binding_identity"])
    assert [item["sequence_number"] for item in validate_sequence_chain(
        [first, second, third],
        packaged_sequence_1_response_identity="7" * 64,
        contract=contract(),
    )] == [2, 3, 4]


@pytest.mark.parametrize("mode", ["gap", "wrong_anchor", "wrong_prior", "duplicate"])
def test_sequence_gap_anchor_substitution_and_replay_reject(mode: str) -> None:
    first = binding()
    second = binding(3, first["continuation_binding_identity"])
    items = [first, second]
    anchor = "7" * 64
    if mode == "gap":
        items[1] = binding(4, first["continuation_binding_identity"])
    elif mode == "wrong_anchor":
        anchor = "8" * 64
    elif mode == "wrong_prior":
        items[1] = binding(3, H2)
    else:
        items = [first, first]
    with pytest.raises(OlympicsClockContinuationV008Error):
        validate_sequence_chain(items, packaged_sequence_1_response_identity=anchor, contract=contract())


def test_sequence_chain_cannot_mix_invocation_claims() -> None:
    first = binding()
    second = binding(3, first["continuation_binding_identity"])
    second["continuation_invocation_identity"] = H2
    second = seal_record("continuation_binding", second)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_sequence_chain(
            [first, second],
            packaged_sequence_1_response_identity="7" * 64,
            contract=contract(),
        )


@pytest.mark.parametrize(
    "field",
    [
        "request_identity",
        "response_identity",
        "v005_clock_attestation_identity",
        "v005_root_artifact_identity",
        "v005_transition_envelope_identity",
    ],
)
def test_sequence_chain_rejects_every_cross_sequence_identity_reuse(field: str) -> None:
    first = unique_binding(2, None)
    second = unique_binding(3, first["continuation_binding_identity"])
    second[field] = first[field]
    second = seal_record("continuation_binding", second)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_REPLAY"):
        validate_sequence_chain(
            [first, second],
            packaged_sequence_1_response_identity="7" * 64,
            contract=contract(),
        )


def test_sequence_chain_rejects_cross_type_identity_reuse() -> None:
    first = unique_binding(2, None)
    second = unique_binding(3, first["continuation_binding_identity"])
    second["response_identity"] = first["request_identity"]
    second = seal_record("continuation_binding", second)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_REPLAY"):
        validate_sequence_chain(
            [first, second],
            packaged_sequence_1_response_identity="7" * 64,
            contract=contract(),
        )


def test_lifecycle_validator_uses_exact_registry_contract_chain_and_binding_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocation_record = invocation()
    invocation_record["packaged_sequence_1_response_identity"] = "7" * 64
    invocation_record["packaged_sequence_1_v005_clock_attestation_identity"] = "8" * 64
    invocation_record = seal_record("continuation_invocation", invocation_record)
    lifecycle = binding()
    lifecycle["continuation_invocation_identity"] = invocation_record[
        "continuation_invocation_identity"
    ]
    lifecycle = seal_record("continuation_binding", lifecycle)
    request = {
        "authorization_identity": "1" * 64,
        "authoritative_run_identity": "2" * 64,
        "operator_implementation_identity": "3" * 64,
        "session_identity": "4" * 64,
        "sequence_number": 2,
        "request_identity": "5" * 64,
        "prior_clock_attestation_identity": "8" * 64,
        "transition_id": "authorization_activated",
        "bound_artifact_type": "activation",
        "bound_timestamp_field": "activated_at",
    }
    response = {
        "response_identity": "6" * 64,
        "v005_clock_attestation_identity": "8" * 64,
        "verified_timestamp": T,
    }
    packaged_response = {
        "response_identity": "7" * 64,
        "sequence_number": 1,
        "status": "success",
        "session_identity": "4" * 64,
        "v005_clock_attestation_identity": "8" * 64,
        "verified_timestamp": T,
    }
    root = {"activation_identity": "9" * 64, "activated_at": T}
    transition = {
        "transition_id": "authorization_activated",
        "transition_envelope_identity": "a" * 64,
        "root_artifact_type": "activation",
        "root_artifact_identity": "9" * 64,
        "durability_evidence_identity": "d" * 64,
    }
    request_evidence = bound_write_evidence("clock_request", request, 2)
    response_evidence = bound_write_evidence("clock_response", response, 2)
    invocation_evidence = bound_write_evidence(
        "continuation_invocation", invocation_record, None
    )
    for evidence in (request_evidence, response_evidence, invocation_evidence):
        evidence["continuation_invocation_identity"] = invocation_record[
            "continuation_invocation_identity"
        ]
    request_evidence = seal_record("continuation_write_evidence", request_evidence)
    response_evidence = seal_record("continuation_write_evidence", response_evidence)
    invocation_evidence = seal_record(
        "continuation_write_evidence", invocation_evidence
    )
    lifecycle["request_durability_identity"] = request_evidence[
        "continuation_write_evidence_identity"
    ]
    lifecycle["response_durability_identity"] = response_evidence[
        "continuation_write_evidence_identity"
    ]
    lifecycle = seal_record("continuation_binding", lifecycle)
    binding_evidence = bound_write_evidence("continuation_binding", lifecycle, 2)
    binding_evidence["continuation_invocation_identity"] = invocation_record[
        "continuation_invocation_identity"
    ]
    binding_evidence = seal_record("continuation_write_evidence", binding_evidence)
    v005_contract = {
        "artifact_schemas": {"activation": {"identity_field": "activation_identity"}},
        "lifecycle": {"timestamp_fields": {"activation": "activated_at"}},
    }
    v007_contract = {"identity": "v007"}
    clock_registry = {"identity": "clock-registry"}
    bootstrap = {"identity": "bootstrap"}
    observed: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        continuation_module,
        "validate_runtime_record",
        lambda _record_type, record, _contract: dict(record),
    )
    monkeypatch.setattr(
        continuation_module,
        "validate_v005_artifact",
        lambda record, _record_type, _contract: dict(record),
    )
    monkeypatch.setattr(
        continuation_module,
        "v005_transition_spec",
        lambda _contract, _transition_id: {"actor": "operator"},
    )
    transition_calls: list[tuple[object, ...]] = []

    def transition_bundle_spy(*args, **kwargs) -> None:
        transition_calls.append((*args, kwargs))

    monkeypatch.setattr(
        continuation_module,
        "validate_v005_transition_bundle",
        transition_bundle_spy,
    )

    def clock_exchange_spy(*args, **kwargs) -> None:
        observed.append((*args, kwargs))

    monkeypatch.setattr(continuation_module, "validate_clock_exchange", clock_exchange_spy)
    assert validate_lifecycle_binding(
        lifecycle,
        invocation_record,
        invocation_evidence,
        request,
        response,
        root,
        transition,
        request_evidence,
        response_evidence,
        binding_evidence,
        root_artifact_type="activation",
        contract=contract(),
        v005_contract=v005_contract,
        v007_contract=v007_contract,
        bootstrap=bootstrap,
        clock_registry=clock_registry,
        packaged_sequence_1_response=packaged_response,
        previous_binding=None,
        previous_binding_write_evidence=None,
        v005_transition_artifacts={
            "activation": [root],
            "transition_envelope": [transition],
        },
    ) == lifecycle
    assert observed == [
        (
            request,
            response,
            bootstrap,
            clock_registry,
            v007_contract,
            {"previous_verified_timestamp": T},
        )
    ]
    assert transition_calls == [
        (
            "authorization_activated",
            "operator",
            {"activation": [root], "transition_envelope": [transition]},
            v005_contract,
            {"documentary_git_proof": None},
        )
    ]

    later = copy.deepcopy(lifecycle)
    later["sequence_number"] = 3
    later["packaged_prior_response_identity"] = None
    later["prior_continuation_binding_identity"] = lifecycle[
        "continuation_binding_identity"
    ]
    later = seal_record("continuation_binding", later)
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_lifecycle_binding(
            later,
            invocation_record,
            invocation_evidence,
            request,
            response,
            root,
            transition,
            request_evidence,
            response_evidence,
            binding_evidence,
            root_artifact_type="activation",
            contract=contract(),
            v005_contract=v005_contract,
            v007_contract=v007_contract,
            bootstrap=bootstrap,
            clock_registry=clock_registry,
            packaged_sequence_1_response=packaged_response,
            previous_binding=lifecycle,
            previous_binding_write_evidence=None,
            v005_transition_artifacts={
                "activation": [root],
                "transition_envelope": [transition],
            },
        )

    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_LIFECYCLE_BINDING"):
        validate_lifecycle_binding(
            lifecycle,
            invocation_record,
            invocation_evidence,
            request,
            response,
            root,
            transition,
            request_evidence,
            response_evidence,
            binding_evidence,
            root_artifact_type="activation",
            contract=contract(),
            v005_contract=v005_contract,
            v007_contract=v007_contract,
            bootstrap=bootstrap,
            clock_registry=clock_registry,
            packaged_sequence_1_response=packaged_response,
            previous_binding=None,
            previous_binding_write_evidence=None,
            v005_transition_artifacts={"transition_envelope": [transition]},
        )

    wrong_prior = {**request, "prior_clock_attestation_identity": H2}
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_SEQUENCE_CONTINUITY"):
        validate_lifecycle_binding(
            lifecycle,
            invocation_record,
            invocation_evidence,
            wrong_prior,
            response,
            root,
            transition,
            request_evidence,
            response_evidence,
            binding_evidence,
            root_artifact_type="activation",
            contract=contract(),
            v005_contract=v005_contract,
            v007_contract=v007_contract,
            bootstrap=bootstrap,
            clock_registry=clock_registry,
            packaged_sequence_1_response=packaged_response,
            previous_binding=None,
            previous_binding_write_evidence=None,
            v005_transition_artifacts={
                "activation": [root],
                "transition_envelope": [transition],
            },
        )

    wrong_binding_evidence = copy.deepcopy(binding_evidence)
    wrong_binding_evidence["target_identity"] = H2
    wrong_binding_evidence = seal_record(
        "continuation_write_evidence", wrong_binding_evidence
    )
    with pytest.raises(OlympicsClockContinuationV008Error, match="V008_CONTINUATION_STORAGE"):
        validate_lifecycle_binding(
            lifecycle,
            invocation_record,
            invocation_evidence,
            request,
            response,
            root,
            transition,
            request_evidence,
            response_evidence,
            wrong_binding_evidence,
            root_artifact_type="activation",
            contract=contract(),
            v005_contract=v005_contract,
            v007_contract=v007_contract,
            bootstrap=bootstrap,
            clock_registry=clock_registry,
            packaged_sequence_1_response=packaged_response,
            previous_binding=None,
            previous_binding_write_evidence=None,
            v005_transition_artifacts={
                "activation": [root],
                "transition_envelope": [transition],
            },
        )


def test_validation_report_is_design_only_and_deterministic() -> None:
    first = validation_report(ROOT)
    assert first == validation_report(ROOT)
    value = json.loads(first)
    assert value == {
        "authorization_present": False,
        "clock_continuation_identity": CONTRACT_IDENTITY,
        "clock_verifier_present": False,
        "design_contract_valid": True,
        "execution_permitted": False,
        "operator_present": False,
        "repository_attestor_present": False,
        "status": "DESIGN_ONLY_V008_CLOCK_CONTINUATION_VALID_NO_RUNTIME_CAPABILITY",
    }


def test_cli_is_deterministic_across_required_hash_seeds_and_timezones() -> None:
    outputs: set[bytes] = set()
    for seed in ("0", "1", "2", "3", "42", "4294967295"):
        for timezone in ("UTC", "America/Denver", "Asia/Tokyo"):
            environment = {
                **os.environ,
                "LANG": "C",
                "LC_ALL": "C",
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(ROOT / "src"),
                "TZ": timezone,
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


def test_v004_v005_v006_v007_sources_are_unchanged() -> None:
    expected = {
        "config/professional_strategy_olympics_execution_publication_v004.json": "fe178d6ae2131b96101fe71fa8adce64f1ca5fb61794db8b0a5104e4308c363e",
        "src/aml/professional_strategy_olympics_execution_publication_v004.py": "4edb69625e85b831eeea4bb4107b4b6fb97c101dc69a3bfe7db385efd61180a0",
        "config/professional_strategy_olympics_authorization_governance_v005.json": "afe13c93d8671600946a025040c2b45f9a1415fe9c4a8422f60d3b8c00c16075",
        "src/aml/professional_strategy_olympics_authorization_governance_v005.py": "9d2a75882e28217fb7165523afdb6d09ccabde6809ac248569e893cedb24054f",
        "config/professional_strategy_olympics_operator_interface_v006.json": "1123cb0b503f71fd0d6841dec82cb74bfa9e35712db1f5d8b1bd527219360630",
        "src/aml/professional_strategy_olympics_operator_interface_v006.py": "a712848db59814b84533f065418993f0b8273c0249e287f9b1efe5f1751aa558",
        "config/professional_strategy_olympics_runtime_boundary_v007.json": "17b452b34777a44c150e20d5f580738858aa92e3fe0db08fea8c45de6e6439c8",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    assert DESIGN_BASE_COMMIT == "0c0a3e60af5fa4cfefc9d0e63933fcea1ca867a3"


def test_design_milestone_has_no_operator_authorization_or_results() -> None:
    assert not (ROOT / "scripts/run_professional_strategy_olympics_v005.py").exists()
    assert not (ROOT / "src/aml/professional_strategy_olympics_operator_v001.py").exists()
    assert not (ROOT / "config/professional_strategy_olympics_operator_implementation_v001.json").exists()
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            DESIGN_BASE_COMMIT,
            DESIGN_MILESTONE_MERGE_COMMIT,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any(
        path.startswith("artifacts/")
        or "authorization.json" in path
        or "result" in Path(path).name.lower()
        for path in changed
    )


def test_validator_has_no_entropy_socket_network_or_execution_capability() -> None:
    combined = (
        (ROOT / "src/aml/professional_strategy_olympics_clock_continuation_v008.py").read_text()
        + SCRIPT.read_text()
    )
    forbidden = (
        "import socket",
        "import secrets",
        "import ctypes",
        "libc.getentropy(",
        "os.getentropy(",
        "os.urandom",
        "import requests",
        "urllib",
        "httpx",
        "aiohttp",
        "build_artifact_bundle(",
        "consume_and_build(",
        "publish_once(",
        "subprocess",
    )
    for token in forbidden:
        assert token not in combined
