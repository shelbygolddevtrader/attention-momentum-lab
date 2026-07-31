from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY,
    OlympicsInputManifestV003Error,
    ROOT_FIELDS,
    SCHEMA,
    VERSION,
    V002_CONTRACT_IDENTITY,
    load_contract,
    manifest_identity,
    validate_manifest,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    adapter_implementation_identity,
)
from aml.professional_strategy_olympics_orchestrator_v001 import executor_bindings
from aml.winner_archetype_contracts import canonical_json

from olympics_v002_test_support import make_trade
from olympics_v003_test_support import ROOT, make_v003_manifest, reidentify_v003


def validate(value: dict[str, object]) -> dict[str, object]:
    return validate_manifest(
        value,
        v003_adapter_implementation_identity=adapter_implementation_identity(ROOT),
        bindings=executor_bindings(),
        canonical_mode=True,
    )


def test_contract_and_valid_v003_specification_fixture() -> None:
    contract = load_contract(ROOT)
    value = validate(make_v003_manifest())
    assert contract["contract_identity"] == CONTRACT_IDENTITY
    assert value["schema_name"] == SCHEMA
    assert value["schema_version"] == VERSION
    assert value["v002_contract_identity"] == V002_CONTRACT_IDENTITY


def test_exact_root_adds_only_versioned_identity_edges_to_v002() -> None:
    from aml.professional_strategy_olympics_input_manifest_v002 import (
        ROOT_FIELDS as V002_ROOT_FIELDS,
    )

    assert ROOT_FIELDS - V002_ROOT_FIELDS == {
        "v002_contract_identity", "v003_contract_identity",
        "v003_adapter_contract_identity", "v003_adapter_implementation_identity",
    }


def test_missing_v002_contract_identity_fails_closed() -> None:
    value = make_v003_manifest()
    value.pop("v002_contract_identity")
    with pytest.raises(OlympicsInputManifestV003Error, match="fields"):
        validate(value)


def test_wrong_v002_contract_identity_fails_before_projection() -> None:
    value = make_v003_manifest()
    value["v002_contract_identity"] = "f" * 64
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV003Error, match="v002_contract_identity"):
        validate(value)


def test_unknown_root_field_fails_closed() -> None:
    value = make_v003_manifest()
    value["extension"] = False
    with pytest.raises(OlympicsInputManifestV003Error, match="fields"):
        validate(value)


@pytest.mark.parametrize("field", ["schema_name", "schema_version"])
def test_wrong_v003_schema_or_version_fails_closed(field: str) -> None:
    value = make_v003_manifest()
    value[field] = "unsupported"
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV003Error, match="unsupported"):
        validate(value)


@pytest.mark.parametrize(
    "field",
    [
        "v001_orchestrator_contract_identity",
        "v001_orchestrator_implementation_identity",
        "v002_adapter_implementation_identity",
        "v003_adapter_implementation_identity",
        "v004_scoring_bundle_identity",
        "executor_registry_identity",
        "simulator_registry_identity",
        "lifecycle_identity",
    ],
)
def test_wrong_inherited_or_v003_identity_fails_closed(field: str) -> None:
    value = make_v003_manifest()
    value[field] = "f" * 64
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV003Error, match="binding|inherited"):
        validate(value)


def test_v002_contract_field_participates_in_manifest_identity() -> None:
    value = make_v003_manifest()
    original = value["manifest_identity"]
    value["v002_contract_identity"] = "f" * 64
    assert manifest_identity(value) != original
    with pytest.raises(OlympicsInputManifestV003Error, match="manifest identity"):
        validate(value)


def test_map_insertion_order_does_not_change_bytes_or_identity() -> None:
    value = make_v003_manifest()
    reversed_value = dict(reversed(tuple(value.items())))
    assert canonical_json(value) == canonical_json(reversed_value)
    assert manifest_identity(value) == manifest_identity(reversed_value)
    assert validate(reversed_value) == value


def test_inherited_entrant_and_trade_ordering_remain_fail_closed() -> None:
    entrants = make_v003_manifest()
    entrants["entrants"][0], entrants["entrants"][1] = (
        entrants["entrants"][1], entrants["entrants"][0]
    )
    with pytest.raises(OlympicsInputManifestV003Error, match="order"):
        validate(reidentify_v003(entrants))

    trades = make_v003_manifest()
    trades["entrants"][0]["trades"].append(make_trade("v003-order", 20))
    trades["entrants"][0]["trades"].reverse()
    with pytest.raises(OlympicsInputManifestV003Error, match="trade ordering"):
        validate(reidentify_v003(trades))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("actual_quantity", -100, "direction and quantity"),
        ("actual_entry_timestamp_nanoseconds", 0, "timestamp ordering"),
        ("stop_microdollars", 11_000_000, "stop or target"),
        ("target_microdollars", 9_000_000, "stop or target"),
        ("gross_pnl_microdollars", 1, "gross P&L"),
        ("net_pnl_microdollars", 1, "net P&L"),
    ],
)
def test_inherited_scoring_critical_reconciliation(field: str, value: int, message: str) -> None:
    manifest = make_v003_manifest()
    manifest["entrants"][0]["trades"][0][field] = value
    with pytest.raises(OlympicsInputManifestV003Error, match=message):
        validate(reidentify_v003(manifest))


def test_hash_seed_timezone_and_repeatability_are_byte_identical(tmp_path: Path) -> None:
    fixture = tmp_path / "v003-test-vector.json"
    fixture.write_bytes(canonical_json(make_v003_manifest()))
    command = [
        sys.executable,
        "scripts/validate_professional_strategy_olympics_input_manifest_v003.py",
        "--root", str(ROOT), "--input", str(fixture), "--validation-only",
    ]
    outputs = []
    for seed, timezone in (("1", "UTC"), ("711", "America/Denver"), ("99", "Asia/Tokyo")):
        env = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "PYTHONPATH": str(ROOT / "src"),
        }
        outputs.append(subprocess.run(
            command, cwd=ROOT, env=env, check=True, capture_output=True,
        ).stdout)
    assert len(set(outputs)) == 1


def test_v001_and_v002_files_remain_byte_for_byte_frozen() -> None:
    expected = {
        "src/aml/professional_strategy_olympics_orchestrator_v001.py": "d1712360c12b0f588268660f850779ea062934d9501c76b6875327c94db51132",
        "scripts/run_professional_strategy_olympics_orchestrator_v001.py": "de03c9328719bba73b1512641515bf5eab87ee4576ef39b17013abf058761041",
        "config/professional_strategy_olympics_input_manifest_v002.json": "7aa794855ac96ea1879b43de7f86447ab6115c365217b370eba41651482ebd70",
        "src/aml/professional_strategy_olympics_input_manifest_v002.py": "30fd96df9ea8c5feccfe097cc7c305994b338e89284a38ca308b8f06b9c9638d",
        "src/aml/professional_strategy_olympics_orchestrator_input_adapter_v002.py": "d7af5b8793dc75a65b28652d70cbdf7c95d52d27d607e3df7bfa1bed0d77ebe5",
        "scripts/validate_professional_strategy_olympics_input_manifest_v002.py": "4549c813c985eea4f7e139a324a19a9c32552839795683ad2430b4c4d538757d",
    }
    assert {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in expected
    } == expected
