from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    canonical_bytes,
    domain_hash,
    strict_json_bytes,
)
from aml.professional_strategy_olympics_operator_interface_v006 import (
    COMMAND_DOMAIN,
    COMMAND_IDENTITY,
    CONTRACT_DOMAIN,
    CONTRACT_IDENTITY,
    CONTRACT_PATH,
    DESIGN_BASE_COMMIT,
    EXPECTED_SECTION_IDENTITIES,
    OlympicsOperatorInterfaceV006Error,
    SECTION_NAMES,
    authoritative_run_identity,
    canonical_contract_bytes,
    load_contract,
    validate_contract,
    validate_repository_lineage,
    validation_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_operator_interface_v006.py"
V006_DESIGN_SOURCE_COMMIT = "8350c4b30c8c9b7b040c336e456dc434b858c77b"
V006_AUDITED_MERGE_COMMIT = "303306b0d2eef4e6fd86ae88dc03ddea5585e210"


def contract() -> dict[str, object]:
    return load_contract(ROOT)


def reseal(value: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(value)
    result["contract_identity"] = domain_hash(
        CONTRACT_DOMAIN,
        {key: item for key, item in result.items() if key != "contract_identity"},
    )
    return result


def test_contract_loads_with_exact_identities_and_bytes() -> None:
    value = contract()
    assert value["contract_identity"] == CONTRACT_IDENTITY
    assert value["command"]["command_identity"] == COMMAND_IDENTITY
    assert (ROOT / CONTRACT_PATH).read_bytes() == canonical_bytes(value)
    assert canonical_contract_bytes(value) == canonical_bytes(value)
    assert len(canonical_bytes(value)) == 12_321


def test_contract_and_command_identities_reproduce_independently() -> None:
    value = contract()
    command = {key: item for key, item in value["command"].items() if key != "command_identity"}
    command_direct = hashlib.sha256(
        COMMAND_DOMAIN.encode("ascii") + b"\0" + canonical_bytes(command)
    ).hexdigest()
    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    contract_direct = hashlib.sha256(
        CONTRACT_DOMAIN.encode("ascii") + b"\0" + canonical_bytes(projection)
    ).hexdigest()
    assert command_direct == domain_hash(COMMAND_DOMAIN, command) == COMMAND_IDENTITY
    assert contract_direct == domain_hash(CONTRACT_DOMAIN, projection) == CONTRACT_IDENTITY


@pytest.mark.parametrize("name", SECTION_NAMES)
def test_every_section_identity_reproduces(name: str) -> None:
    value = contract()
    projection = value[name]
    if name == "command":
        projection = {key: item for key, item in projection.items() if key != "command_identity"}
    assert (
        domain_hash(f"aml.olympics.v006.section.{name}", projection)
        == EXPECTED_SECTION_IDENTITIES[name]
        == value["section_identities"][name]
    )


@pytest.mark.parametrize("name", SECTION_NAMES)
def test_recomputed_mutated_section_still_rejects(name: str) -> None:
    value = contract()
    changed = copy.deepcopy(value)
    section = changed[name]
    key = next(iter(section))
    original = section[key]
    if type(original) is bool:
        section[key] = not original
    elif type(original) is int:
        section[key] = original + 1
    elif type(original) is str:
        section[key] = f"{original}_changed"
    elif type(original) is list:
        section[key] = [*original, "changed"]
    else:
        section[key] = {**original, "CHANGED": "true"}
    projection = section
    if name == "command":
        projection = {field: item for field, item in section.items() if field != "command_identity"}
        section["command_identity"] = domain_hash(COMMAND_DOMAIN, projection)
        projection = {field: item for field, item in section.items() if field != "command_identity"}
    changed["section_identities"][name] = domain_hash(
        f"aml.olympics.v006.section.{name}", projection
    )
    changed = reseal(changed)
    with pytest.raises(OlympicsOperatorInterfaceV006Error):
        validate_contract(changed)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("failure_protocol"),
        lambda value: value.update({"unknown": True}),
        lambda value: value["capability_scope"].update({"execution_implemented": True}),
        lambda value: value["command"].update({"shell": True}),
        lambda value: value["command"].update({"entry_point": "scripts/other.py"}),
        lambda value: value["trusted_clock_interface"].update({"network_in_operator": "permitted"}),
        lambda value: value["trusted_clock_interface"].update({"one_request_per_event": False}),
        lambda value: value["repository_attestation_interface"].update({"network_in_operator": "permitted"}),
        lambda value: value["historical_lineage"].update({"design_base_commit": "0" * 40}),
        lambda value: value["validation_manifest"].update({"authorization_artifact_present": True}),
        lambda value: value["execution_mapping"].update({"strategy_or_scoring_changes": "permitted"}),
    ],
)
def test_governance_weakening_rejects_even_when_outer_identity_is_recomputed(mutation) -> None:
    changed = copy.deepcopy(contract())
    mutation(changed)
    changed = reseal(changed)
    with pytest.raises(OlympicsOperatorInterfaceV006Error):
        validate_contract(changed)


@pytest.mark.parametrize(
    "raw_transform",
    [
        lambda raw: b" " + raw,
        lambda raw: raw[:-1],
        lambda raw: raw + b"\n",
        lambda raw: raw[:-1] + b"\r\n",
        lambda raw: b"\xef\xbb\xbf" + raw,
        lambda raw: json.dumps(json.loads(raw), indent=2).encode("ascii") + b"\n",
    ],
)
def test_noncanonical_contract_bytes_reject(raw_transform) -> None:
    raw = (ROOT / CONTRACT_PATH).read_bytes()
    with pytest.raises(ValueError):
        strict_json_bytes(raw_transform(raw), maximum_bytes=250_000)


def test_duplicate_key_float_nonfinite_invalid_utf8_and_non_nfc_reject() -> None:
    attacks = [
        b'{"a":{"x":1,"x":2}}\n',
        b'{"a":1.0}\n',
        b'{"a":NaN}\n',
        b'{"a":"\xff"}\n',
        '{"a":"e\u0301"}\n'.encode(),
    ]
    for raw in attacks:
        with pytest.raises(ValueError):
            strict_json_bytes(raw)


def test_report_is_deterministic_and_explicitly_nonexecuting() -> None:
    first = validation_report(ROOT)
    assert first == validation_report(ROOT)
    value = json.loads(first)
    assert value["authorization_created"] is False
    assert value["execution_implemented"] is False
    assert value["official_run_executed"] is False
    assert value["remaining_external_prerequisites"] == sorted(
        value["remaining_external_prerequisites"], key=lambda item: item.encode()
    )


def test_cli_is_deterministic_across_hash_seeds_and_timezones() -> None:
    outputs: set[bytes] = set()
    for seed in ("0", "1", "8675309", "4294967295", "123456789", "999999999"):
        for timezone in ("UTC", "America/Denver", "Asia/Tokyo"):
            environment = {**os.environ, "PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONPATH": str(ROOT / "src")}
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(ROOT)],
                check=True,
                capture_output=True,
                env=environment,
            )
            outputs.add(completed.stdout)
            assert completed.stderr == b""
    assert outputs == {validation_report(ROOT)}


def test_repository_lineage_and_tag_are_preserved() -> None:
    result = validate_repository_lineage(ROOT)
    assert result["design_base_is_ancestor"] is True
    assert result["tag_object"] == "746e147efd9bb09dedfdd4d2850f461e36d9f046"
    assert result["tagged_commit"] == "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
    assert DESIGN_BASE_COMMIT == "763e7aa241cdbf8febe0191ee5f01a8156869931"


def test_authoritative_run_identity_is_source_bound_and_deterministic() -> None:
    first = authoritative_run_identity(ROOT, DESIGN_BASE_COMMIT)
    assert first == authoritative_run_identity(ROOT, DESIGN_BASE_COMMIT)
    assert first != authoritative_run_identity(ROOT, "0" * 40)
    with pytest.raises(OlympicsOperatorInterfaceV006Error):
        authoritative_run_identity(ROOT, "not-a-commit")


def test_v004_and_v005_bytes_are_unchanged() -> None:
    expected = {
        "config/professional_strategy_olympics_authorization_governance_v005.json": "afe13c93d8671600946a025040c2b45f9a1415fe9c4a8422f60d3b8c00c16075",
        "src/aml/professional_strategy_olympics_authorization_governance_v005.py": "9d2a75882e28217fb7165523afdb6d09ccabde6809ac248569e893cedb24054f",
        "config/professional_strategy_olympics_execution_publication_v004.json": "fe178d6ae2131b96101fe71fa8adce64f1ca5fb61794db8b0a5104e4308c363e",
        "src/aml/professional_strategy_olympics_execution_publication_v004.py": "4edb69625e85b831eeea4bb4107b4b6fb97c101dc69a3bfe7db385efd61180a0",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_design_milestone_contains_no_runner_or_authorization() -> None:
    assert not (ROOT / "scripts/run_professional_strategy_olympics_v005.py").exists()
    parents = subprocess.run(
        ["git", "show", "-s", "--format=%P", V006_AUDITED_MERGE_COMMIT],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert parents == f"{DESIGN_BASE_COMMIT} {V006_DESIGN_SOURCE_COMMIT}"
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", V006_AUDITED_MERGE_COMMIT, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            DESIGN_BASE_COMMIT,
            V006_AUDITED_MERGE_COMMIT,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any("authorization.json" in path or path.startswith("artifacts/") for path in changed)


def test_validator_and_cli_have_no_execution_or_network_capability() -> None:
    combined = (
        (ROOT / "src/aml/professional_strategy_olympics_operator_interface_v006.py").read_text()
        + SCRIPT.read_text()
    )
    forbidden = (
        "import requests",
        "import socket",
        "urllib",
        "httpx",
        "aiohttp",
        "consume_and_build(",
        "build_artifact_bundle(",
        "publish_once(",
    )
    for token in forbidden:
        assert token not in combined
