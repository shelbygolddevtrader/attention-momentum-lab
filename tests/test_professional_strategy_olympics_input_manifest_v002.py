from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_input_manifest_v002 import (
    ADAPTER_CONTRACT_IDENTITY,
    ENTRANT_FIELDS,
    OlympicsInputManifestV002Error,
    ROOT_FIELDS,
    TRADE_FIELDS,
    derive_cost_stress,
    entrant_identity,
    load_contract,
    manifest_identity,
    trade_identity,
    validate_manifest,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v002 import (
    adapter_implementation_identity,
)
from aml.professional_strategy_olympics_orchestrator_v001 import executor_bindings
from aml.winner_archetype_contracts import canonical_json
from aml.winner_archetype_contracts import canonical_hash

from olympics_v002_test_support import ROOT, make_manifest, make_trade, reidentify


def validate(value: dict[str, object]) -> dict[str, object]:
    return validate_manifest(
        value, adapter_implementation_identity=adapter_implementation_identity(ROOT),
        bindings=executor_bindings(), canonical_mode=True,
    )


def test_contract_and_valid_test_fixture_validate_exactly() -> None:
    contract = load_contract(ROOT)
    value = validate(make_manifest())
    assert contract["contract_identity"] == "c9f6c8c3d02ba78c460c16230a6163fa0272b9464f60172c2bcae21fe0fbd3bb"
    assert contract["frozen_bindings"]["v002_adapter_contract_identity"] == ADAPTER_CONTRACT_IDENTITY
    assert value["entrant_count"] == 10
    assert all(item["trade_count"] == 1 for item in value["entrants"])


def test_contract_declares_every_required_exact_field() -> None:
    contract = load_contract(ROOT)
    assert set(contract["required_fields"]["root"]) == ROOT_FIELDS
    assert set(contract["required_fields"]["entrant"]) == ENTRANT_FIELDS
    assert set(contract["required_fields"]["trade"]) == TRADE_FIELDS
    assert contract["authorization"] == {
        "can_authorize_trial": False,
        "can_execute_trial": False,
        "can_publish_results": False,
    }


@pytest.mark.parametrize("field", ["schema_name", "schema_version"])
def test_wrong_schema_or_version_fails_closed(field: str) -> None:
    value = make_manifest()
    value[field] = "unsupported"
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV002Error, match="unsupported"):
        validate(value)


def test_missing_root_identity_fails_exact_field_validation() -> None:
    value = make_manifest()
    value.pop("manifest_identity")
    with pytest.raises(OlympicsInputManifestV002Error, match="fields"):
        validate(value)


def test_future_canonical_classification_is_representable_but_not_authorized() -> None:
    value = make_manifest()
    value["classification"] = "canonical_synthetic_trial_input_not_authorized"
    validated = validate(reidentify(value))
    assert validated["classification"].endswith("not_authorized")


def test_unknown_manifest_classification_fails_closed() -> None:
    value = make_manifest()
    value["classification"] = "performance_result"
    with pytest.raises(OlympicsInputManifestV002Error, match="classification"):
        validate(reidentify(value))


@pytest.mark.parametrize("level", ["root", "entrant", "trade", "lifecycle", "cost"])
def test_unknown_fields_fail_closed(level: str) -> None:
    value = make_manifest()
    target = {
        "root": value,
        "entrant": value["entrants"][0],
        "trade": value["entrants"][0]["trades"][0],
        "lifecycle": value["entrants"][0]["trades"][0]["lifecycle_evidence"],
        "cost": value["entrants"][0]["trades"][0]["cost_stress_source"],
    }[level]
    target["unexpected"] = 1
    with pytest.raises(OlympicsInputManifestV002Error, match="fields"):
        validate(reidentify(value))


@pytest.mark.parametrize(
    "field",
    [
        "v004_scoring_bundle_identity", "v001_orchestrator_contract_identity",
        "v001_orchestrator_implementation_identity", "v002_adapter_contract_identity",
        "v002_adapter_implementation_identity", "executor_registry_identity",
        "simulator_registry_identity", "lifecycle_identity",
    ],
)
def test_wrong_frozen_root_binding_fails_closed(field: str) -> None:
    value = make_manifest()
    value[field] = "f" * 64
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV002Error, match="binding changed"):
        validate(value)


@pytest.mark.parametrize(
    "field", ["strategy_identity", "executor_identity", "simulator_identity", "lifecycle_identity"]
)
def test_wrong_entrant_binding_fails_closed(field: str) -> None:
    value = make_manifest()
    value["entrants"][0][field] = "f" * 64
    with pytest.raises(OlympicsInputManifestV002Error, match="binding|identity"):
        validate(reidentify(value))


def test_trade_entrant_and_manifest_identities_recompute() -> None:
    value = make_manifest()
    assert validate(value)["manifest_identity"] == manifest_identity(value)
    value["entrants"][0]["trades"][0]["symbol"] = "ALTERED"
    value["entrants"][0]["entrant_identity"] = entrant_identity(value["entrants"][0])
    value["fixture_identity"] = canonical_hash({
        "opened_stages": value["opened_stages"],
        "entrant_identities": [item["entrant_identity"] for item in value["entrants"]],
        "classification": value["classification"],
    })
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV002Error, match="trade identity"):
        validate(value)


@pytest.mark.parametrize("direction", ["long", "short"])
def test_direction_and_quantity_reconcile_for_both_directions(direction: str) -> None:
    value = make_manifest()
    value["entrants"][0]["trades"] = [make_trade("direction-spec", 1, direction=direction)]
    assert validate(reidentify(value))["entrants"][0]["trades"][0]["direction"] == direction


def test_direction_quantity_mismatch_fails_closed() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0]["actual_quantity"] = -100
    with pytest.raises(OlympicsInputManifestV002Error, match="direction and quantity"):
        validate(reidentify(value))


def test_invalid_direction_fails_closed() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0]["direction"] = "sideways"
    with pytest.raises(OlympicsInputManifestV002Error, match="direction"):
        validate(reidentify(value))


@pytest.mark.parametrize(
    ("field", "new_value", "message"),
    [
        ("actual_entry_timestamp_nanoseconds", 0, "timestamp ordering"),
        ("entry_delay_nanoseconds", 1, "entry delay"),
        ("elapsed_holding_nanoseconds", 1, "holding duration"),
        ("stop_microdollars", 11_000_000, "stop or target"),
        ("target_microdollars", 9_000_000, "stop or target"),
    ],
)
def test_timing_and_price_placement_fail_closed(field: str, new_value: int, message: str) -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0][field] = new_value
    with pytest.raises(OlympicsInputManifestV002Error, match=message):
        validate(reidentify(value))


def test_lifecycle_exit_reason_and_same_bar_conservatism_fail_closed() -> None:
    value = make_manifest()
    evidence = value["entrants"][0]["trades"][0]["lifecycle_evidence"]
    evidence["stop_reached"] = True
    evidence["same_bar_stop_and_target"] = True
    with pytest.raises(OlympicsInputManifestV002Error, match="stop-before-target"):
        validate(reidentify(value))


def test_stale_lifecycle_evidence_identity_fails_closed() -> None:
    value = make_manifest()
    trade = value["entrants"][0]["trades"][0]
    evidence = trade["lifecycle_evidence"]
    evidence["evidence_identity"] = "f" * 64
    trade["trade_identity"] = trade_identity(trade)
    value["entrants"][0]["entrant_identity"] = entrant_identity(value["entrants"][0])
    value["fixture_identity"] = canonical_hash({
        "opened_stages": value["opened_stages"],
        "entrant_identities": [item["entrant_identity"] for item in value["entrants"]],
        "classification": value["classification"],
    })
    value["manifest_identity"] = manifest_identity(value)
    with pytest.raises(OlympicsInputManifestV002Error, match="lifecycle evidence"):
        validate(value)


@pytest.mark.parametrize(
    ("field", "delta", "message"),
    [
        ("adjusted_entry_microdollars", 1, "adjusted price"),
        ("gross_pnl_microdollars", 1, "gross P&L"),
        ("net_pnl_microdollars", 1, "net P&L"),
        ("capital_efficiency_numerator_microdollars", 1, "capital-efficiency"),
        ("capital_efficiency_denominator_microdollar_nanoseconds", 1, "capital-efficiency"),
    ],
)
def test_exact_economic_reconciliation_fails_closed(field: str, delta: int, message: str) -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0][field] += delta
    with pytest.raises(OlympicsInputManifestV002Error, match=message):
        validate(reidentify(value))


def test_net_r_reconciliation_is_exact_and_reduced() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0]["net_R"] = {"numerator": 2, "denominator": 2}
    with pytest.raises(OlympicsInputManifestV002Error, match="reduced"):
        validate(reidentify(value))


def test_cost_stress_derives_exact_one_one_and_half_and_two_x() -> None:
    trade = make_manifest()["entrants"][0]["trades"][0]
    scenarios = derive_cost_stress(trade)
    assert scenarios["base_1x"] == Fraction(1)
    assert scenarios["base_1x"] > scenarios["stress_1_5x"] > scenarios["stress_2x"]
    assert all(isinstance(value, Fraction) for value in scenarios.values())


def test_malformed_cost_stress_fails_closed() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0]["cost_stress_source"]["entry_friction_basis_points"] = 9
    with pytest.raises(OlympicsInputManifestV002Error, match="ten bps"):
        validate(reidentify(value))


def test_floating_point_machine_path_and_external_reference_fail_closed() -> None:
    for mutation in ("float", "path", "network"):
        value = make_manifest()
        if mutation == "float":
            value["entrants"][0]["trades"][0]["confidence"] = 0.8
        elif mutation == "path":
            value["entrants"][0]["trades"][0]["regime_label"] = (
                chr(47) + "Users/example/data"
            )
        else:
            value["entrants"][0]["trades"][0]["regime_label"] = "https://example.invalid"
        with pytest.raises(OlympicsInputManifestV002Error):
            validate(reidentify(value))


def test_canonical_bytes_ignore_map_insertion_order() -> None:
    value = make_manifest()
    reversed_value = dict(reversed(tuple(value.items())))
    assert canonical_json(value) == canonical_json(reversed_value)
    assert manifest_identity(value) == manifest_identity(reversed_value)
    assert validate(reversed_value) == value


def test_entrant_order_is_frozen_and_not_silently_sorted() -> None:
    value = make_manifest()
    value["entrants"][0], value["entrants"][1] = value["entrants"][1], value["entrants"][0]
    with pytest.raises(OlympicsInputManifestV002Error, match="binding or order"):
        validate(reidentify(value))


def test_trade_order_is_frozen_and_not_silently_sorted() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"].append(make_trade("ordering", 20))
    value["entrants"][0]["trades"].reverse()
    with pytest.raises(OlympicsInputManifestV002Error, match="trade ordering"):
        validate(reidentify(value))


@pytest.mark.parametrize("field", ["validation_classification", "holdout_classification"])
def test_invalid_population_classification_fails_closed(field: str) -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0][field] = "opened_without_authorization"
    with pytest.raises(OlympicsInputManifestV002Error, match="classification"):
        validate(reidentify(value))


def test_canonical_mode_requires_exactly_ten_entrants() -> None:
    value = make_manifest()
    value["entrants"].pop()
    value["entrant_count"] = 9
    with pytest.raises(OlympicsInputManifestV002Error, match="exactly ten"):
        validate(reidentify(value))


def test_duplicate_trade_identity_fails_closed() -> None:
    value = make_manifest()
    duplicate = deepcopy(value["entrants"][0]["trades"][0])
    value["entrants"][1]["trades"] = [duplicate]
    with pytest.raises(OlympicsInputManifestV002Error, match="duplicate trade identity"):
        validate(reidentify(value))


def test_duplicate_entrant_identity_is_rejected_as_tampering() -> None:
    value = make_manifest()
    value["entrants"][1]["entrant_identity"] = value["entrants"][0]["entrant_identity"]
    with pytest.raises(OlympicsInputManifestV002Error, match="entrant identity"):
        validate(value)


def test_manifest_identity_mismatch_fails_closed() -> None:
    value = make_manifest()
    value["manifest_identity"] = "f" * 64
    with pytest.raises(OlympicsInputManifestV002Error, match="manifest identity"):
        validate(value)


def test_hash_seed_and_timezone_do_not_change_cli_bytes(tmp_path: Path) -> None:
    fixture = tmp_path / "test-vector.json"
    fixture.write_bytes(canonical_json(make_manifest()))
    command = [
        sys.executable,
        "scripts/validate_professional_strategy_olympics_input_manifest_v002.py",
        "--root", str(ROOT), "--input", str(fixture), "--validation-only",
    ]
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "America/Denver"), ("99", "Asia/Tokyo")):
        env = {**os.environ, "PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONPATH": "src"}
        outputs.append(subprocess.run(
            command, cwd=ROOT, env=env, check=True, capture_output=True,
        ).stdout)
    assert len(set(outputs)) == 1
    assert len(hashlib.sha256(outputs[0]).hexdigest()) == 64


def test_v001_contract_module_cli_bytes_and_identity_remain_frozen() -> None:
    expected = {
        "src/aml/professional_strategy_olympics_orchestrator_v001.py": (
            "d1712360c12b0f588268660f850779ea062934d9501c76b6875327c94db51132"
        ),
        "scripts/run_professional_strategy_olympics_orchestrator_v001.py": (
            "de03c9328719bba73b1512641515bf5eab87ee4576ef39b17013abf058761041"
        ),
    }
    assert {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in expected
    } == expected
    assert adapter_implementation_identity(ROOT) != "fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0"
