from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    CANONICAL_CLOCK_REQUEST,
    COMMAND_DOMAIN,
    COMMAND_IDENTITY,
    CONTRACT_IDENTITY,
    DESIGN_BASE_COMMIT,
    GOVERNANCE_DOMAIN,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    VALIDITY_SECONDS,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    OlympicsAuthorizationGovernanceV005Error,
    artifact_identity,
    authorization_proposal_identity,
    authorization_is_valid_at,
    canonical_bytes,
    canonical_contract_bytes,
    clock_evidence_identity,
    clock_request_identity,
    domain_hash,
    load_contract,
    parse_canonical_timestamp,
    parse_imf_fixdate,
    strict_json_bytes,
    synthetic_archive_outcome,
    synthetic_claim_outcome,
    validate_access_evidence,
    validate_archive_bindings,
    validate_artifact,
    validate_claim_bindings,
    validate_clock_attestation,
    validate_contract,
    validate_cross_bindings,
    validate_documentary_binding,
    validate_relative_path,
    validate_role_assignment,
    validate_supersession_chain,
    validate_transition,
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
GIT_C = "c" * 40
DATE = "Wed, 31 Jul 2030 12:00:00 GMT"
STAMP = "2030-07-31T12:00:00Z"
RAW_HEADERS = b"HTTP/1.1 200 OK\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\nX-Test: synthetic\r\n\r\n"


def raw_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def identify_contract(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    command = result["execution_command"]
    command["command_identity"] = domain_hash(
        COMMAND_DOMAIN, {key: item for key, item in command.items() if key != "command_identity"}
    )
    result["contract_identity"] = domain_hash(
        GOVERNANCE_DOMAIN,
        {key: item for key, item in result.items() if key != "contract_identity"},
    )
    return result


def _primitive(name: str, index: int = 0) -> object:
    values: dict[str, object] = {
        "absolute_path": f"/synthetic/root{index}",
        "argv": f"arg{index}",
        "env_assignment": f"A{index}=value",
        "env_name": f"A{index}",
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
    if rule.startswith("array:"):
        _, primitive, minimum, _, order = rule.split(":")
        items = [_primitive(primitive, index) for index in range(int(minimum))]
        return sorted(items) if order == "sorted_unique" else items
    return _primitive(rule)


def make_artifact(kind: str, **overrides: object) -> dict[str, object]:
    contract = raw_contract()
    schema = contract["artifact_schemas"][kind]
    record = {name: _value(rule) for name, rule in schema["fields"].items()}
    record.update(overrides)
    record[schema["identity_field"]] = artifact_identity(record, schema)
    return record


def _operator(user_id: int, login: str) -> dict[str, object]:
    return make_artifact("operator_identity", github_user_id=user_id, github_login=login)


def bound_records() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    contract = raw_contract()
    author, reviewer, operator = (hashlib.sha256(name.encode()).hexdigest() for name in ("author", "reviewer", "operator"))
    checkout = make_artifact("source_checkout", source_commit=GIT_A, source_tree=GIT_B)
    authorization = make_artifact(
        "authorization",
        authorization_author_identity=author,
        authorized_source_commit=GIT_A,
        authorized_source_tree=GIT_B,
        clock_attestation_identity=ONE,
        execution_argv=contract["execution_command"]["argv"],
        execution_command_identity=COMMAND_IDENTITY,
        expires_at="2030-08-03T12:00:00Z",
        issued_at=STAMP,
        operator_identity=operator,
        reviewer_identity=reviewer,
        source_checkout_manifest_identity=checkout["source_checkout_manifest_identity"],
        v005_governance_identity=CONTRACT_IDENTITY,
    )
    approval = make_artifact(
        "human_approval",
        approval_timestamp=STAMP,
        authorization_proposal_identity=authorization_proposal_identity(authorization),
        author_identity=author,
        clock_attestation_identity=ONE,
        reviewed_command_identity=COMMAND_IDENTITY,
        reviewed_governance_identity=CONTRACT_IDENTITY,
        reviewed_source_commit=GIT_A,
        reviewed_source_tree=GIT_B,
        reviewer_identity=reviewer,
    )
    authorization["approval_evidence_identity"] = approval["approval_evidence_identity"]
    authorization["authorization_identity"] = artifact_identity(
        authorization, contract["artifact_schemas"]["authorization"]
    )
    return authorization, approval, checkout


def test_committed_contract_and_two_domain_identities_are_exact() -> None:
    contract = load_contract(ROOT)
    assert contract["contract_identity"] == CONTRACT_IDENTITY
    assert contract["execution_command"]["command_identity"] == COMMAND_IDENTITY
    assert len(contract["artifact_schemas"]) == 14
    assert domain_hash(
        GOVERNANCE_DOMAIN, {key: item for key, item in contract.items() if key != "contract_identity"}
    ) == CONTRACT_IDENTITY
    command = contract["execution_command"]
    assert domain_hash(
        COMMAND_DOMAIN, {key: item for key, item in command.items() if key != "command_identity"}
    ) == COMMAND_IDENTITY


def test_independent_hashlib_identity_reproduction() -> None:
    contract = raw_contract()
    projection = {key: item for key, item in contract.items() if key != "contract_identity"}
    direct = hashlib.sha256(GOVERNANCE_DOMAIN.encode() + b"\x00" + canonical_bytes(projection)).hexdigest()
    assert direct == domain_hash(GOVERNANCE_DOMAIN, projection) == CONTRACT_IDENTITY
    command = contract["execution_command"]
    projection = {key: item for key, item in command.items() if key != "command_identity"}
    direct = hashlib.sha256(COMMAND_DOMAIN.encode() + b"\x00" + canonical_bytes(projection)).hexdigest()
    assert direct == domain_hash(COMMAND_DOMAIN, projection) == COMMAND_IDENTITY


def test_v004_and_immutable_tag_lineage_remain_exact() -> None:
    assert load_contract(ROOT)["historical_lineage"] == {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
    }
    assert ACTUAL_V004_CONTRACT_IDENTITY == V004_CONTRACT_IDENTITY
    assert actual_v004_implementation_identity(ROOT) == V004_IMPLEMENTATION_IDENTITY


@pytest.mark.parametrize("kind", sorted(raw_contract()["artifact_schemas"]))
def test_each_artifact_schema_accepts_one_canonical_synthetic_record(kind: str) -> None:
    record = make_artifact(kind)
    assert validate_artifact(record, kind, raw_contract()) == record


@pytest.mark.parametrize("kind", sorted(raw_contract()["artifact_schemas"]))
def test_each_artifact_schema_rejects_missing_and_unknown_fields(kind: str) -> None:
    record = make_artifact(kind)
    missing = dict(record)
    missing.pop(next(iter(missing)))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="fields"):
        validate_artifact(missing, kind, raw_contract())
    record["unknown"] = False
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="fields"):
        validate_artifact(record, kind, raw_contract())


@pytest.mark.parametrize(
    ("kind", "field", "bad"),
    [
        ("operator_identity", "github_user_id", True),
        ("operator_identity", "github_user_id", 0),
        ("operator_identity", "github_login", "UPPER"),
        ("authorization", "maximum_execution_count", True),
        ("authorization", "previous_authorization_identity", ""),
        ("clock_attestation", "response_status", 200.0),
        ("source_checkout", "detached_head", 1),
        ("environment_manifest", "architecture", "sparc"),
        ("archive_manifest", "result_identities", [ONE, ONE]),
    ],
)
def test_wrong_primitive_null_boolean_enum_and_duplicate_array_reject(
    kind: str, field: str, bad: object
) -> None:
    record = make_artifact(kind)
    record[field] = bad
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_artifact(record, kind, raw_contract(), verify_identity=False)


def test_strict_json_rejects_duplicates_nonfinite_bom_invalid_unicode_and_oversize() -> None:
    invalid = (
        b'{"a":1,"a":2}', b'{"x":NaN}', b"\xef\xbb\xbf{}", b"\xff", b"[]",
    )
    for raw in invalid:
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            strict_json_bytes(raw)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="oversized"):
        strict_json_bytes(b'{}', maximum_bytes=1)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="NFC"):
        strict_json_bytes(json.dumps({"x": "e\u0301"}).encode())


@pytest.mark.parametrize(
    "value",
    [
        "2030-01-02T03:04:05+00:00", "2030-01-01T22:04:05-05:00",
        "2030-01-02T03:04:05.000Z", "2030-01-02 03:04:05Z",
        "2030-01-02T03:04:60Z", "2030-02-30T03:04:05Z",
    ],
)
def test_timestamp_rejects_offsets_subseconds_leap_seconds_and_malformed(value: str) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        parse_canonical_timestamp(value)


@pytest.mark.parametrize(
    "value",
    [
        "Thu, 31 Jul 2030 12:00:00 UTC", "Thu, 31 Jul 2030 12:00:00 +0000",
        "Thursday, 31 Jul 2030 12:00:00 GMT", "Thu, 31 Jul 2030 12:00:00.0 GMT",
        "Fri, 31 Jul 2030 12:00:00 GMT",
    ],
)
def test_imf_fixdate_rejects_non_gmt_subseconds_and_noncanonical(value: str) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        parse_imf_fixdate(value)


def valid_attestation(**overrides: object) -> dict[str, object]:
    values = {
        "canonical_utc_timestamp": STAMP,
        "evidence_byte_identity": clock_evidence_identity(RAW_HEADERS),
        "observation_timestamp": STAMP,
        "request_identity": clock_request_identity(CANONICAL_CLOCK_REQUEST),
        "response_date_as_received": DATE,
        **overrides,
    }
    record = make_artifact("clock_attestation", **values)
    return record


def test_valid_trusted_clock_attestation_is_fully_bound() -> None:
    record = valid_attestation()
    assert validate_clock_attestation(record, RAW_HEADERS, raw_contract()) == record


@pytest.mark.parametrize(
    "raw",
    [
        b"HTTP/1.1 302 Found\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\n\r\n",
        b"HTTP/1.1 200 OK\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\n\r\n",
        b"HTTP/1.1 200 OK\nDate: Wed, 31 Jul 2030 12:00:00 GMT\n\n",
        b"HTTP/1.1 200 OK\r\nDate: Wed, 31 Jul 2030 12:00:00 UTC\r\n\r\n",
    ],
)
def test_clock_evidence_rejects_redirect_missing_duplicate_date_bad_lines_and_non_gmt(raw: bytes) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        clock_evidence_identity(raw)


def test_clock_attestation_rejects_altered_request_evidence_and_timestamp() -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="request bytes"):
        clock_request_identity(CANONICAL_CLOCK_REQUEST.replace(b"HEAD", b"GET "))
    for field, bad in (
        ("request_identity", ZERO),
        ("evidence_byte_identity", ZERO),
        ("canonical_utc_timestamp", "2030-07-31T12:00:01Z"),
        ("observation_timestamp", "2030-07-31T12:00:01Z"),
        ("github_api_origin", "http://api.github.com:80"),
        ("https_authority", "evil.example"),
        ("request_target", "/user"),
    ):
        record = valid_attestation(**{field: bad})
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_clock_attestation(record, RAW_HEADERS, raw_contract())


def test_authorization_validity_is_exact_72_hours_and_half_open() -> None:
    authorization = make_artifact("authorization", issued_at=STAMP, expires_at="2030-08-03T12:00:00Z")
    assert VALIDITY_SECONDS == 259_200
    assert authorization_is_valid_at(authorization, STAMP)
    assert authorization_is_valid_at(authorization, "2030-08-03T11:59:59Z")
    assert not authorization_is_valid_at(authorization, "2030-08-03T12:00:00Z")
    bad = dict(authorization, expires_at="2030-08-03T11:59:59Z")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="equation"):
        authorization_is_valid_at(bad, STAMP)


def test_access_evidence_is_bounded_to_every_declared_prohibited_scope() -> None:
    record = make_artifact(
        "access_prohibition",
        inspected_environment_names=["API_KEY"],
        inspected_filesystem_roots=["/synthetic/sealed"],
        permitted_exceptions=[],
        prohibited_credential_names=["API_KEY"],
        prohibited_filesystem_roots=["/synthetic/sealed"],
    )
    validate_access_evidence(record, raw_contract())
    for field in ("inspected_environment_names", "inspected_filesystem_roots"):
        changed = dict(record, **{field: []})
        changed["access_prohibition_identity"] = artifact_identity(
            changed, raw_contract()["artifact_schemas"]["access_prohibition"]
        )
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="not fully inspected"):
            validate_access_evidence(changed, raw_contract())
    changed = dict(record, permitted_exceptions=["exception"])
    changed["access_prohibition_identity"] = artifact_identity(
        changed, raw_contract()["artifact_schemas"]["access_prohibition"]
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="no access"):
        validate_access_evidence(changed, raw_contract())


@pytest.mark.parametrize(
    "path",
    ["../escape", "/absolute", "a//b", "a/./b", "a/../b", "a\\b", "C:/x", "//server/x", "a\x00b", "UPPER/file", ".", ""],
)
def test_path_traversal_absolute_alternate_separator_and_invalid_components_reject(path: str) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_relative_path(path)


def test_role_matrix_uses_stable_account_id_not_login() -> None:
    contract = raw_contract()
    author = _operator(1, "author-old")
    reviewer = _operator(2, "reviewer")
    operator = _operator(3, "operator")
    archive = _operator(4, "archive")
    records = {item["operator_identity"]: item for item in (author, reviewer, operator, archive)}
    role = make_artifact(
        "role_assignment",
        archive_custodian_identity=archive["operator_identity"],
        authorization_author_identity=author["operator_identity"],
        governance_author_identity=author["operator_identity"],
        operator_identity=operator["operator_identity"],
        reviewer_identity=reviewer["operator_identity"],
        source_author_identity=author["operator_identity"],
    )
    validate_role_assignment(role, records, contract)
    renamed = make_artifact("operator_identity", github_user_id=1, github_login="author-new")
    records[reviewer["operator_identity"]] = renamed
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="registry key"):
        validate_role_assignment(role, records, contract)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("authorization_author_identity", "reviewer_identity"),
        ("authorization_author_identity", "operator_identity"),
        ("reviewer_identity", "operator_identity"),
        ("source_author_identity", "reviewer_identity"),
        ("source_author_identity", "operator_identity"),
        ("archive_custodian_identity", "operator_identity"),
    ],
)
def test_required_role_separation_pairs_reject_same_stable_user(left: str, right: str) -> None:
    person = _operator(10, "person")
    identities = {person["operator_identity"]: person}
    role = make_artifact(
        "role_assignment",
        archive_custodian_identity=person["operator_identity"],
        authorization_author_identity=person["operator_identity"],
        governance_author_identity=person["operator_identity"],
        operator_identity=person["operator_identity"],
        reviewer_identity=person["operator_identity"],
        source_author_identity=person["operator_identity"],
    )
    role[left] = person["operator_identity"]
    role[right] = person["operator_identity"]
    role["role_assignment_identity"] = artifact_identity(role, raw_contract()["artifact_schemas"]["role_assignment"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="role separation"):
        validate_role_assignment(role, identities, raw_contract())


@pytest.mark.parametrize(
    ("prior", "target", "actor"),
    [
        (item["from"], item["to"], item["actor"])
        for item in raw_contract()["lifecycle"]["transitions"]
    ],
)
def test_every_frozen_lifecycle_transition_is_machine_validated(prior: str, target: str, actor: str) -> None:
    assert validate_transition(raw_contract(), prior, target, actor)["rollback"] is False


@pytest.mark.parametrize(
    ("prior", "target", "actor"),
    [
        ("consumed", "active_unconsumed", "operator"),
        ("active_unconsumed", "consumed", "operator"),
        ("run_failed", "run_started", "operator"),
        ("archived", "active_unconsumed", "operator"),
        ("proposed", "approved", "operator"),
    ],
)
def test_unlisted_or_wrong_actor_lifecycle_transitions_reject(prior: str, target: str, actor: str) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="not permitted"):
        validate_transition(raw_contract(), prior, target, actor)


def _supersession(predecessor: str, successor: str) -> dict[str, object]:
    return make_artifact(
        "supersession",
        predecessor_authorization_identity=predecessor,
        successor_authorization_identity=successor,
    )


def test_linear_supersession_chain_is_valid() -> None:
    validate_supersession_chain([_supersession(ZERO, ONE), _supersession(ONE, "2" * 64)], raw_contract())


@pytest.mark.parametrize(
    "records",
    [
        [_supersession(ZERO, ZERO)],
        [_supersession(ZERO, ONE), _supersession(ZERO, "2" * 64)],
        [_supersession(ZERO, ONE), _supersession("2" * 64, ONE)],
        [_supersession(ZERO, ONE), _supersession(ONE, ZERO)],
    ],
)
def test_supersession_self_cycle_fork_and_concurrent_successor_reject(
    records: list[dict[str, object]],
) -> None:
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_supersession_chain(records, raw_contract())


def test_cross_artifact_bindings_reject_wrong_source_governance_command_or_approval() -> None:
    authorization, approval, checkout = bound_records()
    contract = raw_contract()
    validate_cross_bindings(authorization, approval, checkout, contract)
    for target, field, bad in (
        (approval, "reviewed_source_commit", GIT_C),
        (approval, "reviewed_source_tree", GIT_C),
        (approval, "reviewed_governance_identity", ZERO),
        (approval, "reviewed_command_identity", ZERO),
        (checkout, "source_commit", GIT_C),
        (checkout, "detached_head", False),
    ):
        changed_authorization = deepcopy(authorization)
        changed_approval = deepcopy(approval)
        changed_checkout = deepcopy(checkout)
        changed_target = changed_approval if target is approval else changed_checkout
        changed_target[field] = bad
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_cross_bindings(changed_authorization, changed_approval, changed_checkout, contract)


def test_documentary_binding_is_non_circular_and_never_executable_source() -> None:
    authorization = make_artifact("authorization", authorized_source_commit=GIT_A)
    binding = make_artifact(
        "documentary_binding",
        authorization_blob_oid=GIT_C,
        authorization_identity=authorization["authorization_identity"],
        documentary_authorization_commit=GIT_B,
        documentary_authorization_tree=GIT_C,
        documentary_parent_commit=GIT_A,
    )
    validate_documentary_binding(
        binding, authorization, raw_contract(),
        authorization_bytes=canonical_bytes(authorization), authorization_blob_oid=GIT_C,
        documentary_commit=GIT_B, documentary_tree=GIT_C, documentary_parent=GIT_A,
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="cannot be executable"):
        validate_documentary_binding(
            binding, authorization, raw_contract(),
            authorization_bytes=canonical_bytes(authorization), authorization_blob_oid=GIT_C,
            documentary_commit=GIT_A, documentary_tree=GIT_C, documentary_parent=GIT_A,
        )


def test_claim_and_archive_bindings_reconcile_and_fail_closed() -> None:
    authorization = make_artifact(
        "authorization", authorized_source_commit=GIT_A, authorized_source_tree=GIT_B,
        operator_identity=ONE, consumption_store_manifest_identity="2" * 64,
    )
    claim = make_artifact(
        "consumption_claim", authorization_identity=authorization["authorization_identity"],
        operator_identity=ONE, source_commit=GIT_A, source_tree=GIT_B,
        store_manifest_identity="2" * 64,
    )
    validate_claim_bindings(claim, authorization, raw_contract())
    terminal = make_artifact(
        "lifecycle_terminal", authorization_identity=authorization["authorization_identity"],
        run_identity="3" * 64, terminal_state="run_succeeded", failure_identity=None,
        result_manifest_identity="4" * 64,
    )
    archive = make_artifact(
        "archive_manifest", authorization_identity=authorization["authorization_identity"],
        consumption_claim_identity=claim["claim_identity"], failure_identity=None,
        run_identity="3" * 64, source_commit=GIT_A, source_tree=GIT_B,
        terminal_lifecycle_identity=terminal["lifecycle_terminal_identity"],
        terminal_state="run_succeeded",
    )
    validate_archive_bindings(archive, terminal, claim, authorization, raw_contract())
    failed = dict(archive, failure_identity="5" * 64)
    failed["archive_identity"] = artifact_identity(failed, raw_contract()["artifact_schemas"]["archive_manifest"])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="success archive"):
        validate_archive_bindings(failed, terminal, claim, authorization, raw_contract())


def _exclusive_create_worker(path: str, gate: multiprocessing.synchronize.Event, queue: multiprocessing.Queue) -> None:  # type: ignore[name-defined]
    gate.wait()
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"synthetic\n")
        os.fsync(descriptor)
        os.close(descriptor)
        queue.put("winner")
    except FileExistsError:
        queue.put("loser")


def test_temporary_local_exclusive_creation_has_exactly_one_process_winner(tmp_path: Path) -> None:
    path = tmp_path / "claim"
    gate = multiprocessing.Event()
    queue: multiprocessing.Queue = multiprocessing.Queue()
    processes = [multiprocessing.Process(target=_exclusive_create_worker, args=(str(path), gate, queue)) for _ in range(4)]
    for process in processes:
        process.start()
    gate.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    results = [queue.get(timeout=2) for _ in processes]
    assert results.count("winner") == 1
    assert results.count("loser") == 3


def test_temporary_symlink_claim_and_existing_claim_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("synthetic", encoding="utf-8")
    claim = tmp_path / "claim"
    claim.symlink_to(target)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    with pytest.raises(FileExistsError):
        os.open(claim, flags, 0o600)
    claim.unlink()
    claim.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        os.open(claim, flags, 0o600)


def test_temporary_hard_link_is_detectable_and_rejected_by_contract_rule(tmp_path: Path) -> None:
    original = tmp_path / "original"
    linked = tmp_path / "linked"
    original.write_text("synthetic", encoding="utf-8")
    os.link(original, linked)
    assert original.stat().st_nlink == linked.stat().st_nlink == 2
    assert load_contract(ROOT)["consumption_protocol"]["hard_links"].startswith(
        "require_regular_file_st_nlink_equals_1"
    )


def _successful_claim_vector() -> dict[str, bool]:
    return {
        "root_valid": True,
        "local_apfs": True,
        "exclusive_arbitration": True,
        "arbitration_complete": True,
        "arbitration_file_fsync": True,
        "arbitration_close": True,
        "arbitration_directory_fsync": True,
        "exclusive_claim": True,
        "claim_complete": True,
        "claim_regular": True,
        "claim_link_count_one": True,
        "claim_mode_owner_valid": True,
        "claim_file_fsync": True,
        "claim_close": True,
        "claim_directory_fsync": True,
    }


def test_claim_fault_model_requires_every_durability_boundary() -> None:
    good = _successful_claim_vector()
    assert synthetic_claim_outcome(good) == "consumed"
    for field in (
        "arbitration_complete", "arbitration_file_fsync", "arbitration_close",
        "arbitration_directory_fsync", "exclusive_claim", "claim_complete",
        "claim_regular", "claim_link_count_one", "claim_mode_owner_valid",
        "claim_file_fsync", "claim_close", "claim_directory_fsync",
    ):
        assert synthetic_claim_outcome({**good, field: False}) == "indeterminate"
    assert synthetic_claim_outcome({**good, "exclusive_arbitration": False}) == "already_claimed"
    assert synthetic_claim_outcome({**good, "local_apfs": False}) == "rejected"
    assert synthetic_claim_outcome({**good, "root_valid": False}) == "rejected"


def _successful_archive_vector() -> dict[str, bool]:
    return {
        "destination_exclusive": True,
        "all_files_complete": True,
        "all_file_fsyncs": True,
        "directory_fsync_before_marker": True,
        "marker_exclusive": True,
        "marker_complete": True,
        "marker_fsync": True,
        "directory_fsync_after_marker": True,
        "parent_directory_fsync": True,
        "manifest_matches": True,
    }


def test_archive_fault_model_is_write_once_and_fail_closed() -> None:
    good = _successful_archive_vector()
    assert synthetic_archive_outcome(good) == "archived"
    for field in set(good) - {"destination_exclusive", "marker_exclusive"}:
        assert synthetic_archive_outcome({**good, field: False}) == "indeterminate"
    assert synthetic_archive_outcome({**good, "destination_exclusive": False}) == (
        "existing_destination_rejected"
    )
    assert synthetic_archive_outcome({**good, "marker_exclusive": False}) == (
        "existing_destination_rejected"
    )


def test_contract_freezes_partial_write_fsync_network_fs_and_archive_fail_closed_rules() -> None:
    contract = load_contract(ROOT)
    consumption = contract["consumption_protocol"]
    assert consumption["partial_write"] == "never_permits_retry_with_new_claim"
    assert consumption["supported_filesystem"] == "single_host_local_APFS_only"
    assert "fsync" in consumption["errors"]
    assert consumption["supersession_race"].startswith("consumption_and_supersession_compete")
    archive = contract["archival_protocol"]
    assert archive["existing_destination"] == "reject"
    assert archive["write_once"] is True
    assert "indeterminate" in archive["recovery"]


def test_contract_mutations_fail_after_reidentification() -> None:
    mutations = (
        ("clock_protocol", "skew_tolerance_seconds", 1),
        ("consumption_protocol", "supported_filesystem", "nfs"),
        ("validation_manifest", "authorization_artifact_present", True),
    )
    for section, field, bad in mutations:
        changed = raw_contract()
        changed[section][field] = bad
        changed = identify_contract(changed)
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            validate_contract(changed)


def test_design_scope_and_repository_have_no_authorization_runner_or_results() -> None:
    contract = load_contract(ROOT)
    assert all(value is False for value in contract["scope"].values())
    assert contract["validation_manifest"]["authorization_artifact_present"] is False
    assert not (ROOT / "scripts/run_professional_strategy_olympics_v005.py").exists()
    assert not (ROOT / "governance/authorizations/professional_strategy_olympics/v005").exists()
    assert not (ROOT / "artifacts/professional_strategy_olympics/v005").exists()


def test_canonical_report_is_hashseed_timezone_locale_and_temp_root_independent(tmp_path: Path) -> None:
    expected = None
    for seed, zone, locale in (("1", "UTC", "C"), ("77", "America/Denver", "C"), ("9", "Asia/Tokyo", "C")):
        environment = {
            **os.environ, "PYTHONHASHSEED": seed, "TZ": zone, "LANG": locale, "LC_ALL": locale,
            "PYTHONPATH": str(ROOT / "src"), "TMPDIR": str(tmp_path / f"root-{seed}"),
        }
        Path(environment["TMPDIR"]).mkdir()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT)], cwd=ROOT, env=environment,
            check=True, capture_output=True,
        )
        expected = result.stdout if expected is None else expected
        assert result.stdout == expected
        assert result.stderr == b""


def test_contract_round_trip_is_canonical_and_has_one_final_lf() -> None:
    value = raw_contract()
    data = canonical_contract_bytes(value)
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
    assert data == canonical_contract_bytes(dict(reversed(tuple(value.items()))))
