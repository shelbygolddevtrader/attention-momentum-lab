from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_DOMAIN,
    COMMAND_IDENTITY,
    CONTRACT_IDENTITY,
    DESIGN_BASE_COMMIT,
    GOVERNANCE_DOMAIN,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    OlympicsAuthorizationGovernanceV005Error,
    artifact_identity,
    authorization_is_valid_at,
    canonical_bytes,
    event_projection_identity,
    load_contract,
    parse_canonical_timestamp,
    strict_json_bytes,
    synthetic_archive_outcome,
    synthetic_arbitration_outcome,
    transition_spec,
    validate_archive_bundle,
    validate_artifact,
    validate_clock_bundle,
    validate_contract,
    validate_display_metadata,
    validate_documentary_git_proof,
    validate_filesystem_evidence,
    validate_role_assignment,
    validate_supersession_chain,
    validate_terminal_bundle,
    validate_transition_bundle,
    validate_typed_bundle,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    CONTRACT_IDENTITY as ACTUAL_V004_CONTRACT_IDENTITY,
    implementation_identity as actual_v004_implementation_identity,
)


ROOT = Path(__file__).parents[1]
CONTRACT_PATH = ROOT / "config/professional_strategy_olympics_authorization_governance_v005.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_authorization_governance_v005.py"
ZERO = "0" * 64
ONE = "1" * 64
GIT_A = "a" * 40
GIT_B = "b" * 40
STAMP = "2030-07-31T12:00:00Z"
DATE = "Wed, 31 Jul 2030 12:00:00 GMT"
RAW_HEADERS = b"HTTP/1.1 200 OK\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\nX-Origin: synthetic\r\n\r\n"


def contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="ascii"))


def _primitive(name: str, index: int = 0) -> object:
    values: dict[str, object] = {
        "absolute_path": f"/synthetic/root{index}",
        "argv": f"arg{index}",
        "artifact_type": "proposal",
        "base64": "",
        "durability_event": "open_root_no_follow",
        "env_assignment": f"A{index}=value",
        "env_name": f"A{index}",
        "field_name": "proposal_timestamp",
        "git_oid": f"{index % 10}" * 40,
        "github_login": f"person-{index}",
        "hostname": f"host{index}.example",
        "identity": hashlib.sha256(f"identity-{index}".encode()).hexdigest(),
        "nonce": hashlib.sha256(f"nonce-{index}".encode()).hexdigest(),
        "relative_path": f"synthetic/path{index}.json",
        "rfc7231_date": DATE,
        "semver3": "3.12.7",
        "timestamp": STAMP,
        "token": f"token{index}",
        "uint31": index,
        "uint63": index + 1,
    }
    return values[name]


def _value(rule: str) -> object:
    if rule.startswith("identity:"):
        return ZERO
    if rule.startswith("nullable"):
        return None
    if rule.startswith("literal:"):
        literal = rule.split(":", 1)[1]
        if literal == "true":
            return True
        if literal == "false":
            return False
        if literal == "null":
            return None
        if literal.isdecimal():
            return int(literal)
        return literal
    if rule.startswith("enum:"):
        return rule.split(":", 1)[1].split("|")[0]
    if rule.startswith("array_identity:"):
        _, _, minimum, _, _ = rule.split(":")
        return [hashlib.sha256(f"external-{index}".encode()).hexdigest() for index in range(int(minimum))]
    if rule.startswith("array:"):
        _, primitive, minimum, _, order = rule.split(":")
        items = [_primitive(primitive, index) for index in range(int(minimum))]
        return sorted(set(items)) if order == "sorted_unique" else items
    return _primitive(rule)


def make_artifact(kind: str, **overrides: object) -> dict[str, object]:
    c = contract()
    schema = c["artifact_schemas"][kind]
    record = {name: _value(rule) for name, rule in schema["fields"].items()}
    record.update(overrides)
    record[schema["identity_field"]] = artifact_identity(record, schema)
    return record


def _account(user_id: int) -> dict[str, object]:
    return make_artifact("stable_account", github_user_id=user_id)


def _event(kind: str, serial: int, base: dict[str, object], timestamp_field: str, *, stamp: str = STAMP, date: str = DATE, **overrides: object) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    c = contract()
    event = make_artifact(kind, **base, **overrides, **{timestamp_field: stamp}, clock_attestation_identity=ZERO)
    nonce = hashlib.sha256(f"request-{serial}".encode()).hexdigest()
    raw_request = (
        b"HEAD /rate_limit HTTP/1.1\r\n"
        b"Host: api.github.com\r\n"
        b"X-GitHub-Api-Version: 2022-11-28\r\n"
        + f"X-AML-Clock-Nonce: {nonce}\r\n".encode()
        + b"Cache-Control: no-cache, no-store\r\n"
        b"Pragma: no-cache\r\n"
        b"Connection: close\r\n\r\n"
    )
    request = make_artifact(
        "clock_request",
        request_nonce=nonce,
        raw_request_bytes_base64=base64.b64encode(raw_request).decode(),
    )
    evidence = make_artifact(
        "clock_evidence",
        request_identity=request["clock_request_identity"],
        raw_response_headers_base64=base64.b64encode(b"HTTP/1.1 200 OK\r\nDate: " + date.encode() + b"\r\nX-Origin: synthetic\r\n\r\n").decode(),
        response_date_as_received=date,
        response_elapsed_milliseconds=100,
    )
    projection = event_projection_identity(event, kind, c, timestamp_field)
    attestation = make_artifact(
        "clock_attestation",
        request_identity=request["clock_request_identity"],
        evidence_identity=evidence["clock_evidence_identity"],
        canonical_utc_timestamp=stamp,
        bound_artifact_type=kind,
        bound_event_projection_identity=projection,
        bound_timestamp_field=timestamp_field,
    )
    event["clock_attestation_identity"] = attestation["clock_attestation_identity"]
    event[c["artifact_schemas"][kind]["identity_field"]] = artifact_identity(event, c["artifact_schemas"][kind])
    return event, request, evidence, attestation


def fixture_records(transition_id: str) -> dict[str, list[dict[str, object]]]:
    c = contract()
    accounts = [_account(index + 1) for index in range(5)]
    author, reviewer, operator, previous, superseder = [item["stable_account_identity"] for item in accounts]
    records: dict[str, list[dict[str, object]]] = {"stable_account": accounts}
    filesystem = make_artifact(
        "filesystem_evidence",
        device_id=1,
        mount_id=1,
        durability_trace=[
            "open_root_no_follow", "verify_mount_device_owner_mode", "exclusive_create", "write_complete",
            "f_fullfsync_file", "close_file", "fsync_directory",
        ],
    )
    source = make_artifact("source_checkout", source_commit=GIT_A, source_tree=GIT_B)
    environment = make_artifact("environment_manifest")
    access = make_artifact(
        "access_prohibition",
        operator_identity=operator,
        prohibited_resources=["holdout"],
        prohibited_credential_names=["ALPACA_API_KEY"],
        prohibited_filesystem_roots=["/synthetic/protected"],
        prohibited_network_destinations=["api.alpaca.markets"],
        inspected_resources=["holdout"],
        inspected_environment_names=["ALPACA_API_KEY"],
        inspected_filesystem_roots=["/synthetic/protected"],
        inspected_network_destinations=["api.alpaca.markets"],
    )
    store = make_artifact("consumption_store", filesystem_evidence_identity=filesystem["filesystem_evidence_identity"])
    role = make_artifact(
        "role_assignment",
        governance_author_identity=author,
        source_author_identity=author,
        authorization_author_identity=author,
        reviewer_identity=reviewer,
        operator_identity=operator,
        archive_custodian_identity=reviewer,
        previous_operator_identity=previous,
        superseding_authorization_author_identity=superseder,
    )
    for kind, item in (("filesystem_evidence", filesystem), ("source_checkout", source), ("environment_manifest", environment), ("access_prohibition", access), ("consumption_store", store), ("role_assignment", role)):
        records[kind] = [item]
    serial = 0

    def add_event(kind: str, base: dict[str, object], timestamp_field: str, *, stamp: str = STAMP, date: str = DATE, **overrides: object) -> dict[str, object]:
        nonlocal serial
        serial += 1
        item, request, evidence, attestation = _event(kind, serial, base, timestamp_field, stamp=stamp, date=date, **overrides)
        records.setdefault(kind, []).append(item)
        records.setdefault("clock_request", []).append(request)
        records.setdefault("clock_evidence", []).append(evidence)
        records.setdefault("clock_attestation", []).append(attestation)
        return item

    proposal = add_event(
        "proposal",
        {"authorization_author_identity": author},
        "proposal_timestamp",
        authorized_source_commit=GIT_A,
        authorized_source_tree=GIT_B,
        execution_command_identity=COMMAND_IDENTITY,
    )
    approval = add_event(
        "human_approval",
        {"proposal_identity": proposal["proposal_identity"], "author_identity": author, "reviewer_identity": reviewer},
        "approval_timestamp",
    )
    authorization = add_event(
        "authorization",
        {
            "proposal_identity": proposal["proposal_identity"],
            "approval_identity": approval["approval_identity"],
            "authorization_author_identity": author,
            "reviewer_identity": reviewer,
            "operator_identity": operator,
            "environment_manifest_identity": environment["environment_manifest_identity"],
            "source_checkout_identity": source["source_checkout_identity"],
            "consumption_store_identity": store["consumption_store_identity"],
            "access_prohibition_identity": access["access_prohibition_identity"],
            "role_assignment_identity": role["role_assignment_identity"],
        },
        "issued_at",
        authorized_source_commit=GIT_A,
        authorized_source_tree=GIT_B,
        v005_governance_identity=CONTRACT_IDENTITY,
        execution_command_identity=COMMAND_IDENTITY,
        execution_argv=c["execution_command"]["argv"],
        expires_at="2030-08-03T12:00:00Z",
    )
    auth = authorization["authorization_identity"]
    _, documentary_binding, _ = _documentary_fixture(authorization)
    records["documentary_binding"] = [documentary_binding]
    activation = add_event("activation", {"authorization_identity": auth, "prior_record_identity": auth, "operator_identity": operator}, "activated_at")
    superseding = transition_id.startswith("supersession")
    successor = None
    if superseding:
        successor = add_event(
            "authorization",
            {
                "proposal_identity": proposal["proposal_identity"], "approval_identity": approval["approval_identity"],
                "authorization_author_identity": superseder, "reviewer_identity": reviewer, "operator_identity": operator,
                "environment_manifest_identity": environment["environment_manifest_identity"],
                "source_checkout_identity": source["source_checkout_identity"], "consumption_store_identity": store["consumption_store_identity"],
                "access_prohibition_identity": access["access_prohibition_identity"], "role_assignment_identity": role["role_assignment_identity"],
            },
            "issued_at",
            authorized_source_commit=GIT_A, authorized_source_tree=GIT_B,
            v005_governance_identity=CONTRACT_IDENTITY, execution_command_identity=COMMAND_IDENTITY,
            execution_argv=c["execution_command"]["argv"], expires_at="2030-08-03T12:00:00Z",
            previous_authorization_identity=auth,
        )
    decision = add_event(
        "authorization_decision",
        {},
        "decision_timestamp",
        authorization_identity=auth,
        activation_identity=activation["activation_identity"],
        decision_kind="supersede" if superseding else "consume",
        successor_authorization_identity=successor["authorization_identity"] if successor else None,
        actor_identity=superseder if superseding else operator,
    )
    claim = add_event(
        "consumption_claim",
        {"authorization_identity": auth, "prior_record_identity": decision["decision_identity"], "operator_identity": operator},
        "consumed_at",
        decision_identity=decision["decision_identity"],
        source_commit=GIT_A,
        source_tree=GIT_B,
        consumption_store_identity=store["consumption_store_identity"],
    )
    build = add_event("build_start", {"authorization_identity": auth, "prior_record_identity": claim["claim_identity"], "operator_identity": operator}, "build_started_at", claim_identity=claim["claim_identity"])
    run = add_event("run_start", {"authorization_identity": auth, "prior_record_identity": build["build_start_identity"], "operator_identity": operator}, "run_started_at", build_start_identity=build["build_start_identity"])
    result = make_artifact("result_manifest", authorization_identity=auth)
    failure = make_artifact("failure", authorization_identity=auth)
    records["result_manifest"] = [result]
    records["failure"] = [failure]
    wants_failure = transition_id in {"run_failed", "build_failed", "failure_archive_started"}
    terminal = add_event(
        "lifecycle_terminal",
        {"authorization_identity": auth, "prior_record_identity": run["run_start_identity"] if transition_id != "build_failed" else build["build_start_identity"], "operator_identity": operator},
        "terminal_timestamp",
        terminal_state="run_failed" if wants_failure else "run_succeeded",
        result_manifest_identity=None if wants_failure else result["result_manifest_identity"],
        result_identities=[] if wants_failure else result["result_identities"],
        failure_identity=failure["failure_identity"] if wants_failure else None,
        failure_details=failure["failure_code"] if wants_failure else None,
    )
    pending = add_event("archive_pending", {"authorization_identity": auth, "prior_record_identity": terminal["terminal_identity"], "operator_identity": reviewer}, "archive_started_at", terminal_identity=terminal["terminal_identity"])
    archive = add_event(
        "archive_manifest",
        {},
        "archive_timestamp",
        authorization_identity=auth,
        archive_pending_identity=pending["archive_pending_identity"],
        terminal_identity=terminal["terminal_identity"],
        archive_state="failure" if wants_failure else "success",
        result_manifest_identity=None if wants_failure else result["result_manifest_identity"],
        result_identities=[] if wants_failure else result["result_identities"],
        failure_identity=failure["failure_identity"] if wants_failure else None,
        failure_details=failure["failure_code"] if wants_failure else None,
    )
    add_event(
        "completion_marker",
        {},
        "completed_at",
        authorization_identity=auth,
        archive_identity=archive["archive_identity"],
        terminal_state=terminal["terminal_state"],
    )
    add_event(
        "supersession",
        {},
        "supersession_timestamp",
        predecessor_authorization_identity=auth,
        successor_authorization_identity=successor["authorization_identity"] if successor else ONE,
        decision_identity=decision["decision_identity"],
        superseding_author_identity=superseder,
        approval_identity=approval["approval_identity"],
    )
    rejected_auth = None if transition_id == "proposal_rejected" else auth
    add_event(
        "rejection",
        {},
        "rejected_at",
        authorization_identity=rejected_auth,
        proposal_identity=proposal["proposal_identity"],
        prior_record_identity=proposal["proposal_identity"] if rejected_auth is None else approval["approval_identity"],
        actor_identity=reviewer if rejected_auth is None else operator,
    )
    add_event(
        "expiration",
        {},
        "expired_at",
        authorization_identity=auth,
        prior_record_identity=activation["activation_identity"],
        stamp="2030-08-03T12:00:00Z",
        date="Sat, 03 Aug 2030 12:00:00 GMT",
    )
    uncertain = "claim" if transition_id == "claim_indeterminate" else "archive" if transition_id == "archive_indeterminate" else "terminal"
    add_event(
        "indeterminate",
        {},
        "recorded_at",
        authorization_identity=auth,
        prior_record_identity=decision["decision_identity"] if uncertain == "claim" else pending["archive_pending_identity"] if uncertain == "archive" else run["run_start_identity"],
        uncertain_operation=uncertain,
    )
    spec = transition_spec(c, transition_id)
    required = list(spec["required_artifact_types"])
    if spec["required_one_of_artifact_type_sets"]:
        required.extend(spec["required_one_of_artifact_type_sets"][1 if wants_failure else 0])
    if wants_failure:
        records.pop("result_manifest", None)
    else:
        records.pop("failure", None)
    bundle = {kind: records[kind] for kind in required}
    used_attestations = {
        str(item["clock_attestation_identity"])
        for kind, items in bundle.items()
        if kind not in {"clock_request", "clock_evidence", "clock_attestation"}
        for item in items
        if "clock_attestation_identity" in item
    }
    bundle["clock_attestation"] = [
        item for item in records["clock_attestation"]
        if item["clock_attestation_identity"] in used_attestations
    ]
    used_requests = {str(item["request_identity"]) for item in bundle["clock_attestation"]}
    used_evidence = {str(item["evidence_identity"]) for item in bundle["clock_attestation"]}
    bundle["clock_request"] = [item for item in records["clock_request"] if item["clock_request_identity"] in used_requests]
    bundle["clock_evidence"] = [item for item in records["clock_evidence"] if item["clock_evidence_identity"] in used_evidence]
    return bundle


def test_committed_contract_identity_inventory_and_lineage_are_exact() -> None:
    c = load_contract(ROOT)
    assert c["contract_identity"] == CONTRACT_IDENTITY
    assert c["execution_command"]["command_identity"] == COMMAND_IDENTITY
    assert len(c["artifact_schemas"]) == 31
    assert len(c["lifecycle"]["transitions"]) == 20
    assert c["historical_lineage"] == {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
    }
    assert ACTUAL_V004_CONTRACT_IDENTITY == V004_CONTRACT_IDENTITY
    assert actual_v004_implementation_identity(ROOT) == V004_IMPLEMENTATION_IDENTITY


def test_independent_identity_reproduction_and_byte_counts() -> None:
    c = contract()
    projection = {key: value for key, value in c.items() if key != "contract_identity"}
    assert len(canonical_bytes(projection)) == 62455
    assert hashlib.sha256(GOVERNANCE_DOMAIN.encode() + b"\0" + canonical_bytes(projection)).hexdigest() == CONTRACT_IDENTITY
    command = c["execution_command"]
    projection = {key: value for key, value in command.items() if key != "command_identity"}
    assert len(canonical_bytes(projection)) == 535
    assert hashlib.sha256(COMMAND_DOMAIN.encode() + b"\0" + canonical_bytes(projection)).hexdigest() == COMMAND_IDENTITY


@pytest.mark.parametrize("kind", sorted(contract()["artifact_schemas"]))
def test_every_artifact_schema_accepts_exact_record_and_rejects_unknown_or_missing(kind: str) -> None:
    record = make_artifact(kind)
    assert validate_artifact(record, kind, contract()) == record
    unknown = dict(record, unknown=False)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="fields"):
        validate_artifact(unknown, kind, contract())
    missing = dict(record)
    missing.pop(next(iter(missing)))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="fields"):
        validate_artifact(missing, kind, contract())


@pytest.mark.parametrize("kind", sorted(contract()["artifact_schemas"]))
def test_every_artifact_governed_field_mutation_invalidates_identity(kind: str) -> None:
    c = contract()
    record = make_artifact(kind)
    identity_field = c["artifact_schemas"][kind]["identity_field"]
    for field, value in record.items():
        if field == identity_field:
            continue
        changed = dict(record)
        if value is None:
            changed[field] = ONE
        elif type(value) is bool:
            changed[field] = not value
        elif type(value) is int:
            changed[field] = value + 1
        elif type(value) is str:
            changed[field] = value + "x"
        else:
            changed[field] = [*value, ONE]
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_artifact(changed, kind, c)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda raw: b" " + raw,
        lambda raw: raw[:-1],
        lambda raw: raw + b"\n",
        lambda raw: raw.replace(b"\n", b"\r\n"),
        lambda raw: b"\xef\xbb\xbf" + raw,
        lambda raw: raw.replace(b":", b": ", 1),
        lambda raw: raw.replace(b"{", b"{\n", 1),
    ],
)
def test_canonical_json_byte_mutations_reject(mutator) -> None:
    raw = canonical_bytes({"a": "caf\u00e9", "b": 1})
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        strict_json_bytes(mutator(raw))


def test_canonical_json_unicode_duplicates_depth_numbers_and_size_reject() -> None:
    canonical = canonical_bytes({"a": "caf\u00e9", "astral": "\U0001f600", "line": "\u2028\u2029"})
    assert b"caf\\u00e9" in canonical and b"\\ud83d\\ude00" in canonical and b"\\u2028\\u2029" in canonical
    assert strict_json_bytes(canonical)["a"] == "caf\u00e9"
    attacks = [
        b'{"a":1,"a":1}\n', b'{"a":1.0}\n', b'{"a":NaN}\n',
        '{"a":"cafe\u0301"}\n'.encode(), b'{"a":"\\u00E9"}\n',
        b'{"a":"\\ud800"}\n', b'{"a":1}\xff\n',
    ]
    for raw in attacks:
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            strict_json_bytes(raw)
    nested: object = 0
    for _ in range(42):
        nested = {"a": nested}
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="nesting"):
        canonical_bytes(nested)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="oversized"):
        strict_json_bytes(b"{" + b" " * 100 + b"}\n", maximum_bytes=10)


@pytest.mark.parametrize("value", ["2030-01-01T00:00:00+00:00", "2030-01-01T00:00:00.1Z", "2030-01-01T00:00:60Z", "2030-1-01T00:00:00Z"])
def test_noncanonical_timestamps_reject(value: str) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        parse_canonical_timestamp(value)


def test_clock_bundle_accepts_direct_origin_and_rejects_attacks() -> None:
    event, request, evidence, attestation = _event("proposal", 1, {"authorization_author_identity": ZERO}, "proposal_timestamp")
    validate_clock_bundle(request, evidence, attestation, contract(), event=event, event_type="proposal", timestamp_field="proposal_timestamp")
    for field, value in [
        ("proxy_used", True), ("age_header_present", True), ("via_header_present", True),
        ("cache_indicator_present", True), ("redirect_count", 1), ("response_elapsed_milliseconds", 5001),
        ("tls_peer_host", "example.com"), ("tls_certificate_verified", False),
    ]:
        altered = make_artifact("clock_evidence", **{**evidence, field: value, "clock_evidence_identity": ZERO})
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_clock_bundle(request, altered, attestation, contract(), event=event, event_type="proposal", timestamp_field="proposal_timestamp")
    hostile_headers = [
        RAW_HEADERS.replace(b"X-Origin: synthetic", b"Age: 1"),
        RAW_HEADERS.replace(b"X-Origin: synthetic", b"Via: proxy"),
        RAW_HEADERS.replace(b"X-Origin: synthetic", b"X-Cache: HIT"),
        RAW_HEADERS.replace(b"Date:", b"Date: Wed, 31 Jul 2030 12:00:00 GMT\r\nDate:"),
        RAW_HEADERS.replace(b"HTTP/1.1 200 OK", b"HTTP/1.1 302 Found"),
    ]
    for raw in hostile_headers:
        altered = make_artifact("clock_evidence", **{**evidence, "raw_response_headers_base64": base64.b64encode(raw).decode(), "clock_evidence_identity": ZERO})
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_clock_bundle(request, altered, attestation, contract(), event=event, event_type="proposal", timestamp_field="proposal_timestamp")
    wrong_event = dict(event, proposal_timestamp="2030-07-31T12:00:01Z")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="textually"):
        validate_clock_bundle(request, evidence, attestation, contract(), event=wrong_event, event_type="proposal", timestamp_field="proposal_timestamp")


def test_transition_rejects_reused_clock_attestation() -> None:
    c = contract()
    bundle = fixture_records("authorization_activated")
    proposal = bundle["proposal"][0]
    approval = bundle["human_approval"][0]
    approval["clock_attestation_identity"] = proposal["clock_attestation_identity"]
    approval[c["artifact_schemas"]["human_approval"]["identity_field"]] = artifact_identity(approval, c["artifact_schemas"]["human_approval"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_transition_bundle(
            "authorization_activated",
            "operator",
            bundle,
            c,
            documentary_git_proof=_documentary_fixture(bundle["authorization"][0])[2],
        )


def test_stable_account_identity_ignores_display_login_and_roles_never_compare_login() -> None:
    account = _account(42)
    renamed_a = make_artifact("display_metadata", stable_account_identity=account["stable_account_identity"], github_login="old-name")
    renamed_b = make_artifact("display_metadata", stable_account_identity=account["stable_account_identity"], github_login="new-name")
    validate_display_metadata(renamed_a, account, contract())
    validate_display_metadata(renamed_b, account, contract())
    assert renamed_a["display_metadata_identity"] != renamed_b["display_metadata_identity"]
    assert account["stable_account_identity"] == _account(42)["stable_account_identity"]
    assert account["stable_account_identity"] != _account(43)["stable_account_identity"]
    for login in [None, "", "UPPER", "-bad", "bad-"]:
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_artifact(make_artifact("display_metadata", github_login=login), "display_metadata", contract())


def test_role_separation_resolves_stable_accounts_only() -> None:
    accounts = [_account(index) for index in range(1, 6)]
    ids = [item["stable_account_identity"] for item in accounts]
    role = make_artifact(
        "role_assignment", governance_author_identity=ids[0], source_author_identity=ids[0],
        authorization_author_identity=ids[0], reviewer_identity=ids[1], operator_identity=ids[2],
        archive_custodian_identity=ids[1], previous_operator_identity=ids[3],
        superseding_authorization_author_identity=ids[4],
    )
    registry = {item["stable_account_identity"]: item for item in accounts}
    validate_role_assignment(role, registry, contract())
    bad = make_artifact("role_assignment", **{**role, "reviewer_identity": ids[2], "role_assignment_identity": ZERO})
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="separation"):
        validate_role_assignment(bad, registry, contract())


@pytest.mark.parametrize("transition_id", [item["transition_id"] for item in contract()["lifecycle"]["transitions"]])
def test_every_transition_executes_complete_typed_synthetic_bundle(transition_id: str) -> None:
    c = contract()
    spec = transition_spec(c, transition_id)
    bundle = fixture_records(transition_id)
    proof = _documentary_fixture(bundle["authorization"][0])[2] if spec["documentary_binding_required"] else None
    validate_transition_bundle(transition_id, spec["actor"], bundle, c, documentary_git_proof=proof)


@pytest.mark.parametrize("transition_id", [item["transition_id"] for item in contract()["lifecycle"]["transitions"]])
def test_every_transition_rejects_each_missing_required_type_and_wrong_actor(transition_id: str) -> None:
    c = contract()
    spec = transition_spec(c, transition_id)
    bundle = fixture_records(transition_id)
    proof = _documentary_fixture(bundle["authorization"][0])[2] if spec["documentary_binding_required"] else None
    for missing in spec["required_artifact_types"]:
        incomplete = dict(bundle)
        incomplete.pop(missing)
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_transition_bundle(transition_id, spec["actor"], incomplete, c, documentary_git_proof=proof)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="actor"):
        validate_transition_bundle(transition_id, "wrong_actor", bundle, c, documentary_git_proof=proof)


@pytest.mark.parametrize("transition_id", [item["transition_id"] for item in contract()["lifecycle"]["transitions"] if item["forbidden_competing_artifact_types"]])
def test_every_declared_competing_artifact_rejects_transition(transition_id: str) -> None:
    c = contract()
    spec = transition_spec(c, transition_id)
    bundle = fixture_records(transition_id)
    proof = _documentary_fixture(bundle["authorization"][0])[2] if spec["documentary_binding_required"] else None
    for forbidden in spec["forbidden_competing_artifact_types"]:
        attack = dict(bundle)
        attack[forbidden] = [make_artifact(forbidden)]
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_transition_bundle(transition_id, spec["actor"], attack, c, documentary_git_proof=proof)


def test_cross_type_unresolved_duplicate_and_orphan_types_reject() -> None:
    c = contract()
    account = _account(1)
    display = make_artifact("display_metadata", stable_account_identity=account["stable_account_identity"])
    validate_typed_bundle({"stable_account": [account], "display_metadata": [display]}, c, required_types=["stable_account", "display_metadata"])
    unresolved = make_artifact("display_metadata", stable_account_identity=ONE)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="unresolved"):
        validate_typed_bundle({"stable_account": [account], "display_metadata": [unresolved]}, c, required_types=["stable_account", "display_metadata"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="orphaned"):
        validate_typed_bundle({"stable_account": [account]}, c, required_types=["stable_account", "display_metadata"])


@pytest.mark.parametrize("success", [True, False])
def test_terminal_archive_success_failure_exclusivity(success: bool) -> None:
    auth = ZERO
    result = make_artifact("result_manifest", authorization_identity=auth)
    failure = make_artifact("failure", authorization_identity=auth)
    terminal = make_artifact(
        "lifecycle_terminal", authorization_identity=auth,
        terminal_state="run_succeeded" if success else "run_failed",
        result_manifest_identity=result["result_manifest_identity"] if success else None,
        result_identities=result["result_identities"] if success else [],
        failure_identity=None if success else failure["failure_identity"],
        failure_details=None if success else failure["failure_code"],
    )
    validate_terminal_bundle(terminal, result if success else None, None if success else failure, contract())
    archive = make_artifact(
        "archive_manifest", authorization_identity=auth, terminal_identity=terminal["terminal_identity"],
        archive_state="success" if success else "failure",
        result_manifest_identity=result["result_manifest_identity"] if success else None,
        result_identities=result["result_identities"] if success else [],
        failure_identity=None if success else failure["failure_identity"],
        failure_details=None if success else failure["failure_code"],
    )
    completion = make_artifact("completion_marker", authorization_identity=auth, archive_identity=archive["archive_identity"], terminal_state=terminal["terminal_state"])
    validate_archive_bundle(archive, terminal, completion, result if success else None, None if success else failure, contract())
    for field, bad_value in [("result_manifest_identity", None if success else ONE), ("result_identities", [] if success else [ONE]), ("failure_identity", ONE if success else None), ("failure_details", "failure" if success else None)]:
        bad = dict(terminal, **{field: bad_value})
        bad["terminal_identity"] = artifact_identity(bad, contract()["artifact_schemas"]["lifecycle_terminal"])
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_terminal_bundle(bad, result if success else None, None if success else failure, contract())


def test_consumption_supersession_race_matrix_and_successor_path() -> None:
    assert synthetic_arbitration_outcome(consume_decision_durable=False, supersede_decision_durable=False) == "retry_before_atomicity"
    assert synthetic_arbitration_outcome(consume_decision_durable=True, supersede_decision_durable=False) == "consumption_wins"
    assert synthetic_arbitration_outcome(consume_decision_durable=False, supersede_decision_durable=True) == "supersession_wins_successor_eligible_on_own_path"
    assert synthetic_arbitration_outcome(consume_decision_durable=True, supersede_decision_durable=True) == "integrity_failure"
    assert synthetic_arbitration_outcome(consume_decision_durable=False, supersede_decision_durable=False, uncertainty=True) == "indeterminate_recovery_only"
    protocol = contract()["consumption_protocol"]
    assert protocol["decision_path"] == "authorization-decisions/{authorization_identity}.json"
    assert "successor" in protocol["successor_rule"]


def test_supersession_chain_rejects_fork_cycle_stale_and_changed_binding() -> None:
    predecessor = make_artifact("authorization", previous_authorization_identity=None)
    successor = make_artifact("authorization", previous_authorization_identity=predecessor["authorization_identity"])
    decision = make_artifact("authorization_decision", authorization_identity=predecessor["authorization_identity"], decision_kind="supersede", successor_authorization_identity=successor["authorization_identity"])
    record = make_artifact("supersession", predecessor_authorization_identity=predecessor["authorization_identity"], successor_authorization_identity=successor["authorization_identity"], decision_identity=decision["decision_identity"])
    auths = {item["authorization_identity"]: item for item in (predecessor, successor)}
    validate_supersession_chain([record], [decision], auths, contract())
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_supersession_chain([record, record], [decision], auths, contract())
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="missing"):
        validate_supersession_chain([record], [decision], {predecessor["authorization_identity"]: predecessor}, contract())
    changed = make_artifact("authorization", **{**successor, "canonical_fixture_identity": ONE, "authorization_identity": ZERO})
    changed_record = make_artifact("supersession", predecessor_authorization_identity=predecessor["authorization_identity"], successor_authorization_identity=changed["authorization_identity"], decision_identity=decision["decision_identity"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_supersession_chain([changed_record], [decision], {predecessor["authorization_identity"]: predecessor, changed["authorization_identity"]: changed}, contract())


def test_filesystem_evidence_requires_apfs_security_and_ordered_durability() -> None:
    good = make_artifact("filesystem_evidence", durability_trace=["open_root_no_follow","verify_mount_device_owner_mode","exclusive_create","write_complete","f_fullfsync_file","close_file","fsync_directory"])
    validate_filesystem_evidence(good, contract())
    for field, value in [("filesystem_type", "nfs"), ("local_mount", False), ("removable", True), ("root_symlink", True), ("hard_link_count", 2), ("acl_present", True), ("xattrs_present", True), ("cross_device_traversal", True)]:
        bad = make_artifact("filesystem_evidence", **{**good, field: value, "filesystem_evidence_identity": ZERO})
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_filesystem_evidence(bad, contract())
    reordered = make_artifact("filesystem_evidence", durability_trace=["open_root_no_follow","verify_mount_device_owner_mode","exclusive_create","write_complete","close_file","f_fullfsync_file","fsync_directory"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="reordered"):
        validate_filesystem_evidence(reordered, contract())


def test_archive_first_publication_recovery_and_complete_verification_matrix() -> None:
    base = {"destination_exists":False,"marker_exists":True,"all_intended_bytes_match":True,"unexpected_files":False,"recovery_authorized":False,"all_file_fullfsyncs":True,"directory_fsyncs":True,"parent_fsync":True,"marker_fullfsync":True}
    assert synthetic_archive_outcome("first_publication", base) == "archived"
    existing = dict(base, destination_exists=True)
    assert synthetic_archive_outcome("first_publication", existing) == "rejected_existing_destination"
    assert synthetic_archive_outcome("authorized_recovery", dict(existing, recovery_authorized=True)) == "archived"
    assert synthetic_archive_outcome("verify_complete", existing) == "verified_complete"
    assert synthetic_archive_outcome("verify_complete", dict(existing, marker_exists=False)) == "indeterminate"
    assert synthetic_archive_outcome("authorized_recovery", dict(existing, recovery_authorized=True, unexpected_files=True)) == "rejected_conflict"


def test_authorization_validity_is_half_open_and_exactly_72_hours() -> None:
    record = {"issued_at": STAMP, "expires_at": "2030-08-03T12:00:00Z"}
    assert authorization_is_valid_at(record, STAMP)
    assert authorization_is_valid_at(record, "2030-08-03T11:59:59Z")
    assert not authorization_is_valid_at(record, "2030-08-03T12:00:00Z")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        authorization_is_valid_at({**record, "expires_at": "2030-08-03T12:00:01Z"}, STAMP)


def _git_oid(kind: str, payload: bytes) -> str:
    return hashlib.sha1(kind.encode() + b" " + str(len(payload)).encode() + b"\0" + payload).hexdigest()


def _tree_proof(path: str, leaf_oid: str) -> tuple[str, bytes]:
    components = path.split("/")
    child_oid = leaf_oid
    reverse_steps = []
    for index, component in reversed(list(enumerate(components))):
        mode = "100644" if index == len(components) - 1 else "40000"
        object_type = "blob" if mode == "100644" else "tree"
        raw_tree = mode.encode() + b" " + component.encode() + b"\0" + bytes.fromhex(child_oid)
        tree_oid = _git_oid("tree", raw_tree)
        reverse_steps.append({
            "component": component,
            "mode": mode,
            "object_oid": child_oid,
            "object_type": object_type,
            "raw_tree_base64": base64.b64encode(raw_tree).decode(),
            "tree_oid": tree_oid,
        })
        child_oid = tree_oid
    return child_oid, canonical_bytes({"steps": list(reversed(reverse_steps))})


def _documentary_fixture(authorization: dict[str, object] | None = None) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    authorization = authorization or make_artifact("authorization", authorized_source_commit=GIT_A)
    auth_bytes = canonical_bytes(authorization)
    auth_blob = _git_oid("blob", auth_bytes)
    auth_path = f"authorizations/{authorization['authorization_identity']}/authorization.json"
    tree_a, auth_tree_proof = _tree_proof(auth_path, auth_blob)
    commit_a_raw = f"tree {tree_a}\nparent {GIT_A}\nauthor Synthetic <s@example.com> 0 +0000\ncommitter Synthetic <s@example.com> 0 +0000\n\nauthorization\n".encode()
    commit_a = _git_oid("commit", commit_a_raw)
    binding = make_artifact(
        "documentary_binding",
        authorization_identity=authorization["authorization_identity"],
        authorization_relative_path=auth_path,
        authorization_blob_oid=auth_blob,
        authorization_tree_oid=tree_a,
        documentary_authorization_commit_oid=commit_a,
        authorized_source_parent_oid=GIT_A,
    )
    binding_bytes = canonical_bytes(binding)
    binding_blob = _git_oid("blob", binding_bytes)
    binding_path = f"bindings/{authorization['authorization_identity']}/documentary_binding.json"
    tree_b, binding_tree_proof = _tree_proof(binding_path, binding_blob)
    commit_b_raw = f"tree {tree_b}\nparent {commit_a}\nauthor Synthetic <s@example.com> 1 +0000\ncommitter Synthetic <s@example.com> 1 +0000\n\nbinding\n".encode()
    proof = {
        "authorization_bytes": auth_bytes,
        "authorization_tree_proof_bytes": auth_tree_proof,
        "commit_a_raw_bytes": commit_a_raw,
        "binding_bytes": binding_bytes,
        "binding_tree_proof_bytes": binding_tree_proof,
        "commit_b_raw_bytes": commit_b_raw,
        "commit_b_oid": _git_oid("commit", commit_b_raw),
    }
    return authorization, binding, proof


def test_documentary_git_proof_recomputes_raw_objects_and_direct_parents() -> None:
    authorization, binding, proof = _documentary_fixture()
    validate_documentary_git_proof(binding, authorization, contract(), proof)
    attacks = []
    for key in [key for key in proof if key != "commit_b_oid"]:
        altered = dict(proof)
        altered[key] = proof[key] + b"x"
        attacks.append(altered)
    attacks.append({**proof, "commit_b_oid": GIT_B})
    attacks.append({**proof, "commit_a_raw_bytes": proof["commit_a_raw_bytes"].replace(f"parent {GIT_A}".encode(), f"parent {GIT_B}".encode())})
    attacks.append({**proof, "commit_b_raw_bytes": proof["commit_b_raw_bytes"].replace(b"\nauthor ", f"\nparent {GIT_B}\nauthor ".encode())})
    for altered in attacks:
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_documentary_git_proof(binding, authorization, contract(), altered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorization_blob_oid", GIT_B),
        ("authorization_tree_oid", GIT_B),
        ("documentary_authorization_commit_oid", GIT_B),
        ("authorized_source_parent_oid", GIT_B),
        ("authorization_relative_path", "wrong/authorization.json"),
        ("repository_identity", "other/repository"),
        ("repository_object_format", "sha256"),
    ],
)
def test_documentary_git_proof_rejects_forged_ids_path_mode_format_and_repository(field: str, value: str) -> None:
    authorization, binding, proof = _documentary_fixture()
    forged = make_artifact("documentary_binding", **{**binding, field: value, "documentary_binding_identity": ZERO})
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_documentary_git_proof(forged, authorization, contract(), proof)


def test_every_governed_contract_field_mutation_breaks_identity() -> None:
    original = contract()
    for key in original:
        if key == "contract_identity":
            continue
        changed = deepcopy(original)
        value = changed[key]
        changed[key] = False if value is not False else True
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_contract(changed)


def test_cli_is_pure_deterministic_and_reports_design_only(tmp_path: Path) -> None:
    outputs = []
    for timezone_name, seed in [("UTC", "0"), ("America/Denver", "1"), ("Asia/Tokyo", "8675309")]:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TZ": timezone_name, "PYTHONHASHSEED": seed, "LC_ALL": "C", "LANG": "C"}
        completed = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT)], check=True, capture_output=True, env=env)
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]
    report = strict_json_bytes(outputs[0])
    assert report["artifact_schema_count"] == 31
    assert report["lifecycle_transition_count"] == 20
    assert not report["authorization_created"]
    assert not report["execution_capability_implemented"]
    assert not report["official_run_authorized"]
    assert not report["official_run_executed"]


def test_contract_file_is_exact_canonical_bytes_and_no_execution_scope() -> None:
    raw = CONTRACT_PATH.read_bytes()
    assert raw == canonical_bytes(contract())
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    text = (ROOT / "src/aml/professional_strategy_olympics_authorization_governance_v005.py").read_text()
    for forbidden in ["requests", "urllib", "socket", "import subprocess", "eval(", "exec(", "run_professional_strategy_olympics_v005.py\""]:
        assert forbidden not in text
