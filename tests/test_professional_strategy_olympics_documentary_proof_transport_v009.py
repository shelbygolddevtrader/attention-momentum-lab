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
    artifact_identity,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
)
from aml.professional_strategy_olympics_documentary_proof_transport_v009 import (
    CONTRACT_DOMAIN,
    CONTRACT_IDENTITY,
    ENVELOPE_SCHEMA,
    MAX_CONTRACT_BYTES,
    MAX_PACKAGE_BYTES,
    MAX_TOTAL_DECODED_BYTES,
    PACKAGE_SCHEMA,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    V005_COMMAND_IDENTITY,
    V005_GOVERNANCE_IDENTITY,
    V006_OPERATOR_INTERFACE_IDENTITY,
    V007_RUNTIME_BOUNDARY_IDENTITY,
    V008_CLOCK_CONTINUATION_IDENTITY,
    OlympicsDocumentaryProofTransportV009Error,
    encode_raw_member,
    envelope_identity,
    git_object_oid,
    load_contract,
    package_identity,
    package_relative_path,
    prohibit_fallback,
    proof_relative_path,
    validate_contract,
    validate_documentary_proof_transport,
    validate_envelope,
    validate_invocation_binding,
    validate_package,
    validate_package_inventory,
    validate_storage_observations,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/professional_strategy_olympics_documentary_proof_transport_v009.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_documentary_proof_transport_v009.py"
ZERO = "0" * 64
GIT_A = "a" * 40
V006_PACKAGE = "6" * 64
V007_PACKAGE = "7" * 64


def contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="ascii"))


def _primitive(name: str, index: int = 0) -> object:
    values: dict[str, object] = {
        "absolute_path": f"/synthetic/root{index}",
        "argv": f"arg{index}",
        "artifact_type": "proposal",
        "base64": "",
        "boolean": False,
        "domain_name": "aml.synthetic.domain",
        "durability_event": "open_root_no_follow",
        "env_assignment": f"A{index}=value",
        "env_name": f"A{index}",
        "field_name": "proposal_identity",
        "git_oid": f"{index % 10}" * 40,
        "github_login": f"person-{index}",
        "hostname": f"host{index}.example",
        "identity": hashlib.sha256(f"identity-{index}".encode()).hexdigest(),
        "nonce": hashlib.sha256(f"nonce-{index}".encode()).hexdigest(),
        "relative_path": f"synthetic/path{index}.json",
        "rfc7231_date": "Wed, 31 Jul 2030 12:00:00 GMT",
        "schema_identifier": "aml.synthetic.schema.v005",
        "semver3": "3.13.0",
        "state_name": "synthetic_state",
        "timestamp": "2030-07-31T12:00:00Z",
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
        return [hashlib.sha256(f"external-{i}".encode()).hexdigest() for i in range(int(minimum))]
    if rule.startswith("array:"):
        _, primitive, minimum, _, order = rule.split(":")
        items = [_primitive(primitive, i) for i in range(int(minimum))]
        return sorted(set(items)) if order == "sorted_unique" else items
    return _primitive(rule)


def _artifact(kind: str, **overrides: object) -> dict[str, object]:
    c = load_v005_contract(ROOT)
    schema = c["artifact_schemas"][kind]
    record = {name: _value(rule) for name, rule in schema["fields"].items()}
    record.update(overrides)
    record[schema["identity_field"]] = artifact_identity(record, schema)
    return record


def _tree_proof(path: str, leaf_oid: str) -> tuple[str, bytes]:
    child_oid = leaf_oid
    reverse_steps = []
    components = path.split("/")
    for index, component in reversed(list(enumerate(components))):
        mode = "100644" if index == len(components) - 1 else "40000"
        raw_tree = mode.encode() + b" " + component.encode() + b"\0" + bytes.fromhex(child_oid)
        tree_oid = git_object_oid("tree", raw_tree)
        reverse_steps.append(
            {
                "component": component,
                "mode": mode,
                "object_oid": child_oid,
                "object_type": "blob" if mode == "100644" else "tree",
                "raw_tree_base64": base64.b64encode(raw_tree).decode(),
                "tree_oid": tree_oid,
            }
        )
        child_oid = tree_oid
    return child_oid, canonical_bytes({"steps": list(reversed(reverse_steps))})


def documentary_fixture() -> tuple[
    dict[str, object], dict[str, object], dict[str, bytes], dict[str, object], dict[str, object]
]:
    authorization = _artifact("authorization", authorized_source_commit=GIT_A)
    auth_bytes = canonical_bytes(authorization)
    auth_blob = git_object_oid("blob", auth_bytes)
    auth_path = f"authorizations/{authorization['authorization_identity']}/authorization.json"
    tree_a, auth_proof = _tree_proof(auth_path, auth_blob)
    commit_a_raw = (
        f"tree {tree_a}\nparent {GIT_A}\nauthor Synthetic <s@example.com> 0 +0000\n"
        "committer Synthetic <s@example.com> 0 +0000\n\nauthorization\n"
    ).encode()
    commit_a = git_object_oid("commit", commit_a_raw)
    binding = _artifact(
        "documentary_binding",
        authorization_identity=authorization["authorization_identity"],
        authorization_relative_path=auth_path,
        authorization_blob_oid=auth_blob,
        authorization_tree_oid=tree_a,
        documentary_authorization_commit_oid=commit_a,
        authorized_source_parent_oid=GIT_A,
        repository_context_identity=authorization["repository_context_identity"],
    )
    binding_bytes = canonical_bytes(binding)
    binding_blob = git_object_oid("blob", binding_bytes)
    binding_path = f"bindings/{authorization['authorization_identity']}/documentary_binding.json"
    tree_b, binding_proof = _tree_proof(binding_path, binding_blob)
    commit_b_raw = (
        f"tree {tree_b}\nparent {commit_a}\nauthor Synthetic <s@example.com> 1 +0000\n"
        "committer Synthetic <s@example.com> 1 +0000\n\nbinding\n"
    ).encode()
    raw = {
        "authorization_bytes": auth_bytes,
        "authorization_tree_proof_bytes": auth_proof,
        "commit_a_raw_bytes": commit_a_raw,
        "documentary_binding_bytes": binding_bytes,
        "binding_tree_proof_bytes": binding_proof,
        "commit_b_raw_bytes": commit_b_raw,
    }
    envelope: dict[str, object] = {
        "schema_version": ENVELOPE_SCHEMA,
        "envelope_identity": ZERO,
        "authorization_identity": authorization["authorization_identity"],
        "documentary_binding_identity": binding["documentary_binding_identity"],
        "authorization_commit_a_oid": commit_a,
        "documentary_binding_commit_b_oid": git_object_oid("commit", commit_b_raw),
        "authorization_tree_oid": tree_a,
        "binding_tree_oid": tree_b,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v006_operator_package_identity": V006_PACKAGE,
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "v007_runtime_package_identity": V007_PACKAGE,
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "v009_contract_identity": CONTRACT_IDENTITY,
        "package_binding_identity": ZERO,
        "raw_members": {name: encode_raw_member(name, value) for name, value in raw.items()},
    }
    envelope["package_binding_identity"] = domain_hash(
        "aml.olympics.v009.documentary-proof-package-binding",
        {
            "authorization_identity": envelope["authorization_identity"],
            "documentary_binding_identity": envelope["documentary_binding_identity"],
            "v006_operator_package_identity": V006_PACKAGE,
            "v007_runtime_package_identity": V007_PACKAGE,
            "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
            "v009_contract_identity": CONTRACT_IDENTITY,
        },
    )
    envelope["envelope_identity"] = envelope_identity(envelope)
    envelope_bytes = canonical_bytes(envelope)
    path = proof_relative_path(str(authorization["authorization_identity"]))
    common = {
        "artifact_type": "documentary_git_proof",
        "artifact_identity": envelope["envelope_identity"],
        "relative_path": path,
        "canonical_bytes_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
    }
    package: dict[str, object] = {
        "schema_version": PACKAGE_SCHEMA,
        "package_identity": ZERO,
        "v009_contract_identity": CONTRACT_IDENTITY,
        "authorization_identity": authorization["authorization_identity"],
        "documentary_binding_identity": binding["documentary_binding_identity"],
        "v006_operator_package_identity": V006_PACKAGE,
        "v007_runtime_package_identity": V007_PACKAGE,
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "documentary_proof_envelope_identity": envelope["envelope_identity"],
        "documentary_proof_envelope_relative_path": path,
        "v006_record_index_extension": common,
        "v007_supplemental_manifest_entry": {**common, "schema_version": ENVELOPE_SCHEMA},
    }
    package["package_identity"] = package_identity(package)
    return authorization, binding, raw, envelope, package


def validate_fixture(
    authorization: dict[str, object],
    binding: dict[str, object],
    envelope: dict[str, object],
    package: dict[str, object],
) -> None:
    c = load_contract(ROOT)
    validate_envelope(
        envelope,
        authorization,
        binding,
        v006_operator_package_identity=V006_PACKAGE,
        v007_runtime_package_identity=V007_PACKAGE,
        contract=c,
        v005_contract=load_v005_contract(ROOT),
    )
    validate_package(package, envelope, canonical_bytes(envelope), contract=c)


def test_contract_and_cli_are_canonical_and_design_only() -> None:
    c = load_contract(ROOT)
    assert c["contract_identity"] == CONTRACT_IDENTITY
    assert CONTRACT_PATH.read_bytes() == canonical_bytes(c)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(ROOT)],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    report = json.loads(result.stdout)
    assert report["status"].startswith("DESIGN_ONLY_V009")
    assert report["operator_implemented"] is False
    assert report["official_run_executed"] is False


def test_positive_envelope_package_and_all_six_raw_members() -> None:
    authorization, binding, raw, envelope, package = documentary_fixture()
    validate_fixture(authorization, binding, envelope, package)
    assert set(envelope["raw_members"]) == set(raw)
    assert envelope["documentary_binding_commit_b_oid"] == git_object_oid(
        "commit", raw["commit_b_raw_bytes"]
    )


def test_closed_world_inventory_and_detached_source_without_commit_b() -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    validate_fixture(authorization, binding, envelope, package)
    auth = str(authorization["authorization_identity"])
    members = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    validate_package_inventory(
        members,
        authorization_identity=auth,
        package=package,
        envelope=envelope,
        contract=load_contract(ROOT),
    )
    # No repository path or object database is supplied to any proof validator.


def _storage_observations(members: dict[str, bytes]) -> list[dict[str, object]]:
    return [
        {
            "relative_path": path,
            "object_type": "regular_file",
            "filesystem_mode": "0600",
            "git_mode": "100644",
            "hard_link_count": 1,
            "symlink_free": True,
            "same_device": True,
            "durable": True,
            "byte_length": len(payload),
            "bytes_sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in sorted(members.items())
    ]


def test_storage_observations_bind_regular_files_modes_links_and_durability() -> None:
    authorization, _, _, envelope, package = documentary_fixture()
    auth = str(authorization["authorization_identity"])
    members = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    validate_storage_observations(
        _storage_observations(members), members, authorization_identity=auth
    )


def test_composite_validator_recovers_v005_proof_and_preflights_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    auth = str(authorization["authorization_identity"])
    members = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    invocation = {"authorization_identity": auth}
    runtime = {
        "authorization_identity": auth,
        "runtime_package_identity": V007_PACKAGE,
        "v006_operator_package_identity": V006_PACKAGE,
    }
    proof = validate_documentary_proof_transport(
        authorization,
        binding,
        envelope,
        package,
        members,
        _storage_observations(members),
        invocation,
        runtime,
        v006_operator_package_identity=V006_PACKAGE,
        v007_runtime_package_identity=V007_PACKAGE,
        contract=load_contract(ROOT),
        v005_contract=load_v005_contract(ROOT),
    )
    assert proof["commit_b_oid"] == envelope["documentary_binding_commit_b_oid"]

    def forbidden_decode(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Base64 decode occurred before inventory rejection")

    monkeypatch.setattr(base64, "b64decode", forbidden_decode)
    attacked_members = {**members, "proofs/extra.json": b"{}\n"}
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_PACKAGE_REACHABILITY_UNCERTAIN",
    ):
        validate_documentary_proof_transport(
            authorization,
            binding,
            envelope,
            package,
            attacked_members,
            _storage_observations(members),
            invocation,
            runtime,
            v006_operator_package_identity=V006_PACKAGE,
            v007_runtime_package_identity=V007_PACKAGE,
            contract=load_contract(ROOT),
            v005_contract=load_v005_contract(ROOT),
        )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("object_type", "symlink", "V009_ARTIFACT_MODE_MISMATCH"),
        ("filesystem_mode", "0644", "V009_ARTIFACT_MODE_MISMATCH"),
        ("git_mode", "100755", "V009_ARTIFACT_MODE_MISMATCH"),
        ("hard_link_count", 2, "V009_PACKAGE_REACHABILITY_UNCERTAIN"),
        ("symlink_free", False, "V009_PACKAGE_REACHABILITY_UNCERTAIN"),
        ("same_device", False, "V009_DURABILITY_UNCERTAIN"),
        ("durable", False, "V009_DURABILITY_UNCERTAIN"),
        ("byte_length", 0, "V009_RAW_MEMBER_SIZE_MISMATCH"),
        ("bytes_sha256", "8" * 64, "V009_RAW_MEMBER_HASH_MISMATCH"),
    ],
)
def test_storage_observation_mutations_fail(field: str, value: object, code: str) -> None:
    authorization, _, _, envelope, package = documentary_fixture()
    auth = str(authorization["authorization_identity"])
    members = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    observations = _storage_observations(members)
    observations[0][field] = value
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match=code):
        validate_storage_observations(observations, members, authorization_identity=auth)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("authorization_identity", "8" * 64, "V009_AUTHORIZATION_MISMATCH"),
        ("documentary_binding_identity", "8" * 64, "V009_DOCUMENTARY_BINDING_MISMATCH"),
        ("v004_contract_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v004_implementation_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v005_governance_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v005_command_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v006_operator_interface_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v006_operator_package_identity", "8" * 64, "V009_PROOF_PACKAGE_MISMATCH"),
        ("v007_runtime_boundary_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v007_runtime_package_identity", "8" * 64, "V009_PROOF_PACKAGE_MISMATCH"),
        ("v008_clock_continuation_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("v009_contract_identity", "8" * 64, "V009_CROSS_VERSION_SUBSTITUTION"),
        ("authorization_commit_a_oid", "a" * 39, "V009_UNSUPPORTED_GIT_OBJECT_FORMAT"),
        ("documentary_binding_commit_b_oid", "B" * 40, "V009_UNSUPPORTED_GIT_OBJECT_FORMAT"),
    ],
)
def test_security_relevant_envelope_field_mutations_fail(
    field: str, value: object, code: str
) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    envelope[field] = value
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match=code):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize("name", list((
    "authorization_bytes",
    "authorization_tree_proof_bytes",
    "commit_a_raw_bytes",
    "documentary_binding_bytes",
    "binding_tree_proof_bytes",
    "commit_b_raw_bytes",
)))
def test_every_raw_member_hash_substitution_fails(name: str) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    envelope["raw_members"][name]["sha256"] = "8" * 64
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_RAW_MEMBER_HASH_MISMATCH",
    ):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing", "V009_RAW_MEMBER_MISSING"),
        ("extra", "V009_RAW_MEMBER_EXTRA"),
        ("unknown_envelope", "V009_SCHEMA"),
        ("unknown_package", "V009_SCHEMA"),
    ],
)
def test_closed_world_field_inventories_fail(mutation: str, code: str) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    if mutation == "missing":
        del envelope["raw_members"]["commit_b_raw_bytes"]
    elif mutation == "extra":
        envelope["raw_members"]["extra"] = encode_raw_member("commit_b_raw_bytes", b"")
    elif mutation == "unknown_envelope":
        envelope["unknown"] = True
    else:
        package["unknown"] = True
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match=code):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize(
    "mutation",
    ["whitespace", "unpadded", "url_alphabet", "wrong_encoded_length", "wrong_decoded_length"],
)
def test_alternate_or_malformed_base64_fails(mutation: str) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    member = envelope["raw_members"]["commit_a_raw_bytes"]
    if mutation == "whitespace":
        member["value"] += "\n"
        member["encoded_length"] += 1
    elif mutation == "unpadded":
        member["value"] = member["value"].rstrip("=")
        member["encoded_length"] = len(member["value"])
    elif mutation == "url_alphabet":
        member["value"] = "_" + member["value"][1:]
    elif mutation == "wrong_encoded_length":
        member["encoded_length"] += 1
    else:
        member["decoded_length"] += 1
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize("part", ["commit_a_raw_bytes", "commit_b_raw_bytes"])
def test_commit_object_mutation_and_parent_substitution_fail(part: str) -> None:
    authorization, binding, raw, envelope, package = documentary_fixture()
    altered = raw[part].replace(b"parent ", b"parent b", 1)
    envelope["raw_members"][part] = encode_raw_member(part, altered)
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize("part", ["authorization_tree_proof_bytes", "binding_tree_proof_bytes"])
def test_tree_proof_path_mode_oid_and_substitution_fail(part: str) -> None:
    authorization, binding, raw, envelope, package = documentary_fixture()
    proof = json.loads(raw[part])
    proof["steps"][-1]["mode"] = "100755"
    envelope["raw_members"][part] = encode_raw_member(part, canonical_bytes(proof))
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_ARTIFACT_MODE_MISMATCH"):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize("part", ["authorization_tree_proof_bytes", "binding_tree_proof_bytes"])
def test_tree_proof_path_substitution_has_exact_failure_class(part: str) -> None:
    authorization, binding, raw, envelope, package = documentary_fixture()
    proof = json.loads(raw[part])
    proof["steps"][-1]["component"] = "substituted.json"
    envelope["raw_members"][part] = encode_raw_member(part, canonical_bytes(proof))
    envelope["envelope_identity"] = envelope_identity(envelope)
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_ARTIFACT_PATH_MISMATCH"):
        validate_fixture(authorization, binding, envelope, package)


@pytest.mark.parametrize(
    "field",
    [
        "artifact_type",
        "artifact_identity",
        "relative_path",
        "canonical_bytes_sha256",
    ],
)
def test_v006_and_v007_index_substitution_fails(field: str) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    package["v006_record_index_extension"][field] = "8" * 64
    package["package_identity"] = package_identity(package)
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_PACKAGE_REACHABILITY_UNCERTAIN",
    ):
        validate_fixture(authorization, binding, envelope, package)


def test_inventory_absent_duplicate_extra_alternate_and_traversal_fail() -> None:
    authorization, _, _, envelope, package = documentary_fixture()
    auth = str(authorization["authorization_identity"])
    valid = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    cases = [
        {package_relative_path(auth): canonical_bytes(package)},
        {**valid, f"proofs/{auth}/copy/documentary_git_proof_v009.json": canonical_bytes(envelope)},
        {**valid, f"proofs/{auth}/extra.json": b"{}\n"},
        {**valid, f"proofs/{auth}/../escape.json": b"{}\n"},
        {**valid, f"proofs/{auth}/./documentary_git_proof_v009.json": b"{}\n"},
        {**valid, f"proofs/{auth}//documentary_git_proof_v009.json": b"{}\n"},
        {**valid, f"proofs/{auth}/bad\x00path.json": b"{}\n"},
    ]
    for members in cases:
        with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
            validate_package_inventory(
                members,
                authorization_identity=auth,
                package=package,
                envelope=envelope,
                contract=load_contract(ROOT),
            )


def test_v008_invocation_binding_is_transitive_and_exact() -> None:
    authorization, _, _, _, package = documentary_fixture()
    invocation = {"authorization_identity": authorization["authorization_identity"]}
    runtime = {
        "authorization_identity": authorization["authorization_identity"],
        "runtime_package_identity": V007_PACKAGE,
        "v006_operator_package_identity": V006_PACKAGE,
    }
    validate_invocation_binding(package, invocation, runtime)
    runtime["runtime_package_identity"] = "8" * 64
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
        validate_invocation_binding(package, invocation, runtime)


@pytest.mark.parametrize(
    "kind",
    [
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
    ],
)
def test_every_fallback_is_explicitly_prohibited(kind: str) -> None:
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error, match="V009_FALLBACK_PROHIBITED"
    ):
        prohibit_fallback(kind)


def test_contract_unknown_missing_and_identity_mutations_fail() -> None:
    c = contract()
    cases = []
    extra = deepcopy(c)
    extra["unknown"] = True
    cases.append(extra)
    missing = deepcopy(c)
    del missing["transport_model"]
    cases.append(missing)
    section = deepcopy(c)
    section["section_identities"]["inheritance"] = ZERO
    cases.append(section)
    outer = deepcopy(c)
    outer["contract_identity"] = ZERO
    cases.append(outer)
    for candidate in cases:
        with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
            validate_contract(candidate)


def _leaf_paths(value: object, prefix: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [
            path
            for key, item in value.items()
            for path in _leaf_paths(item, (*prefix, key))
        ]
    if isinstance(value, list):
        return [
            path
            for index, item in enumerate(value)
            for path in _leaf_paths(item, (*prefix, index))
        ]
    return [prefix]


def test_recursive_mutation_of_every_contract_leaf_fails() -> None:
    original = contract()
    for path in _leaf_paths(original):
        candidate = deepcopy(original)
        parent: object = candidate
        for component in path[:-1]:
            parent = parent[component]
        leaf = parent[path[-1]]
        replacement: object
        if type(leaf) is bool:
            replacement = not leaf
        elif type(leaf) is int:
            replacement = leaf + 1
        elif type(leaf) is str:
            replacement = leaf + "x"
        else:  # pragma: no cover - the frozen contract has only scalar leaf types
            raise AssertionError(f"unsupported leaf type at {path}")
        parent[path[-1]] = replacement
        with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
            validate_contract(candidate)


def test_duplicate_json_keys_invalid_utf8_and_noncanonical_bytes_fail(tmp_path: Path) -> None:
    canonical = CONTRACT_PATH.read_bytes()
    replacements = [
        canonical.replace(b'{"authority_boundary":', b'{"authority_boundary":{},"authority_boundary":', 1),
        b"\xff",
        canonical.replace(b"{", b"{ ", 1),
    ]
    for index, raw in enumerate(replacements):
        root = tmp_path / str(index)
        path = root / "config"
        path.mkdir(parents=True)
        (path / CONTRACT_PATH.name).write_bytes(raw)
        with pytest.raises(OlympicsDocumentaryProofTransportV009Error):
            load_contract(root)


def test_validator_output_is_identical_across_hash_seeds_and_timezones() -> None:
    outputs = set()
    for seed in ("0", "1", "2", "3", "42", "4294967295"):
        for timezone in ("UTC", "America/Denver", "Asia/Tokyo"):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(ROOT)],
                check=True,
                capture_output=True,
                env={
                    **os.environ,
                    "PYTHONPATH": str(ROOT / "src"),
                    "PYTHONHASHSEED": seed,
                    "TZ": timezone,
                },
            )
            outputs.add(result.stdout)
    assert len(outputs) == 1


def test_outer_and_section_identities_reproduce_independently() -> None:
    c = contract()
    for name, identity in c["section_identities"].items():
        assert identity == domain_hash(f"{CONTRACT_DOMAIN}.section.{name}", c[name])
    projection = {key: value for key, value in c.items() if key != "contract_identity"}
    assert c["contract_identity"] == domain_hash(CONTRACT_DOMAIN, projection)


def test_proof_validator_imports_no_network_or_git_process_capability() -> None:
    module = (
        ROOT
        / "src/aml/professional_strategy_olympics_documentary_proof_transport_v009.py"
    ).read_text(encoding="utf-8")
    prohibited = ("requests", "urllib", "httpx", "socket", "subprocess", "git fetch", "GitHub")
    assert not any(f"import {name}" in module for name in prohibited)
    assert "subprocess." not in module
    assert "socket." not in module


@pytest.mark.parametrize("target", ["envelope", "package", "inventory"])
def test_identity_only_v009_contract_spoof_fails(target: str) -> None:
    authorization, binding, _, envelope, package = documentary_fixture()
    fake_contract = {"contract_identity": CONTRACT_IDENTITY}
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        if target == "envelope":
            validate_envelope(
                envelope,
                authorization,
                binding,
                v006_operator_package_identity=V006_PACKAGE,
                v007_runtime_package_identity=V007_PACKAGE,
                contract=fake_contract,
                v005_contract=load_v005_contract(ROOT),
            )
        elif target == "package":
            validate_package(
                package,
                envelope,
                canonical_bytes(envelope),
                contract=fake_contract,
            )
        else:
            auth = str(authorization["authorization_identity"])
            validate_package_inventory(
                {
                    proof_relative_path(auth): canonical_bytes(envelope),
                    package_relative_path(auth): canonical_bytes(package),
                },
                authorization_identity=auth,
                package=package,
                envelope=envelope,
                contract=fake_contract,
            )


def test_total_decoded_limit_fails_before_base64_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization, binding, _, envelope, _ = documentary_fixture()
    envelope["raw_members"]["authorization_bytes"]["decoded_length"] = (
        MAX_TOTAL_DECODED_BYTES + 1
    )
    envelope["envelope_identity"] = envelope_identity(envelope)

    def forbidden_decode(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Base64 decode occurred before size rejection")

    monkeypatch.setattr(base64, "b64decode", forbidden_decode)
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_RAW_MEMBER_SIZE_MISMATCH",
    ):
        validate_envelope(
            envelope,
            authorization,
            binding,
            v006_operator_package_identity=V006_PACKAGE,
            v007_runtime_package_identity=V007_PACKAGE,
            contract=load_contract(ROOT),
            v005_contract=load_v005_contract(ROOT),
        )


def test_storage_evidence_rejects_extra_member_and_boolean_link_count() -> None:
    authorization, _, _, envelope, package = documentary_fixture()
    auth = str(authorization["authorization_identity"])
    members = {
        proof_relative_path(auth): canonical_bytes(envelope),
        package_relative_path(auth): canonical_bytes(package),
    }
    observations = _storage_observations(members)
    extra_members = {**members, "proofs/extra.json": b"{}\n"}
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_PACKAGE_REACHABILITY_UNCERTAIN",
    ):
        validate_storage_observations(
            observations, extra_members, authorization_identity=auth
        )
    observations[0]["hard_link_count"] = True
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="V009_PACKAGE_REACHABILITY_UNCERTAIN",
    ):
        validate_storage_observations(observations, members, authorization_identity=auth)


def test_invocation_binding_rejects_missing_required_identities() -> None:
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        validate_invocation_binding(
            {"v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY},
            {},
            {},
        )


def test_noncanonical_envelope_value_uses_v009_failure_class() -> None:
    authorization, binding, _, envelope, _ = documentary_fixture()
    envelope["raw_members"]["authorization_bytes"]["decoded_length"] = 1.5
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        validate_envelope(
            envelope,
            authorization,
            binding,
            v006_operator_package_identity=V006_PACKAGE,
            v007_runtime_package_identity=V007_PACKAGE,
            contract=load_contract(ROOT),
            v005_contract=load_v005_contract(ROOT),
        )


def test_direct_contract_and_package_size_limits_fail_closed() -> None:
    oversized_contract = contract()
    oversized_contract["transport_model"]["reason"] = "x" * MAX_CONTRACT_BYTES
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="contract_size"):
        validate_contract(oversized_contract)

    _, _, _, envelope, package = documentary_fixture()
    package["v006_operator_package_identity"] = "x" * MAX_PACKAGE_BYTES
    with pytest.raises(
        OlympicsDocumentaryProofTransportV009Error,
        match="package_manifest_limit",
    ):
        validate_package(
            package,
            envelope,
            canonical_bytes(envelope),
            contract=load_contract(ROOT),
        )


def test_public_validators_reject_malformed_mapping_inputs() -> None:
    _, binding, _, envelope, package = documentary_fixture()
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        validate_envelope(
            envelope,
            [],
            binding,
            v006_operator_package_identity=V006_PACKAGE,
            v007_runtime_package_identity=V007_PACKAGE,
            contract=load_contract(ROOT),
            v005_contract=load_v005_contract(ROOT),
        )
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        validate_package(
            package,
            {},
            canonical_bytes(envelope),
            contract=load_contract(ROOT),
        )
    with pytest.raises(OlympicsDocumentaryProofTransportV009Error, match="V009_SCHEMA"):
        validate_invocation_binding(package, [], {})
