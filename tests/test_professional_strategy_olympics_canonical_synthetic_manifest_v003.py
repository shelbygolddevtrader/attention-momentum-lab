from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_canonical_synthetic_manifest_v003 import (
    ENTRANT_IDS,
    FIXTURE_IDENTITY,
    MANIFEST_IDENTITY,
    MANIFEST_PATH,
    SOURCE_COMMIT,
    CanonicalSyntheticManifestV003Error,
    integrity_report,
    load_canonical_manifest,
    validate_canonical_manifest,
    validation_report,
)
from aml.professional_strategy_olympics_input_manifest_v003 import (
    OlympicsInputManifestV003Error,
    manifest_identity,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    future_run_identity,
)
from aml.winner_archetype_contracts import canonical_json

from olympics_v003_test_support import ROOT, reidentify_v003


def raw_manifest() -> dict[str, object]:
    return json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))


def root_change(field: str, value: object) -> dict[str, object]:
    result = raw_manifest()
    result[field] = value
    result["manifest_identity"] = manifest_identity(result)
    return result


def trade_change(field: str, value: object) -> dict[str, object]:
    result = raw_manifest()
    result["entrants"][0]["trades"][0][field] = value
    return reidentify_v003(result)


def test_committed_manifest_is_the_exact_canonical_v003_input() -> None:
    value = load_canonical_manifest(ROOT)
    assert value["source_commit_identity"] == SOURCE_COMMIT
    assert value["fixture_identity"] == FIXTURE_IDENTITY
    assert value["manifest_identity"] == MANIFEST_IDENTITY
    assert tuple(entrant["entrant_id"] for entrant in value["entrants"]) == ENTRANT_IDS
    assert [entrant["trade_count"] for entrant in value["entrants"]] == [1] * 10
    assert sum(len(entrant["trades"]) for entrant in value["entrants"]) == 10
    assert manifest_identity(value) == MANIFEST_IDENTITY


def test_committed_json_is_stably_sorted_and_contains_no_result_fields() -> None:
    value = raw_manifest()
    expected = json.dumps(value, indent=2, sort_keys=True) + "\n"
    assert (ROOT / MANIFEST_PATH).read_text(encoding="utf-8") == expected
    forbidden = {"ranking", "rank", "percentile", "aggregate_score", "winner"}
    assert not (forbidden & set(value))
    assert canonical_json(value) == canonical_json(dict(reversed(tuple(value.items()))))


def test_validation_only_is_non_authorizing_and_non_executing(tmp_path: Path) -> None:
    before = tuple(tmp_path.iterdir())
    report = validation_report(ROOT)
    assert report["status"] == "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
    assert report["trial_authorized"] is False
    assert report["trial_executed"] is False
    assert report["authorization_created"] is False
    assert report["artifact_published"] is False
    assert report["ranking_exists"] is False
    assert tuple(tmp_path.iterdir()) == before


def test_integrity_report_and_future_run_identity_are_deterministic() -> None:
    first = integrity_report(ROOT)
    assert first == integrity_report(ROOT)
    report = json.loads(first)
    assert report["execution_count"] == 0
    assert report["future_run_identity"] == future_run_identity(
        load_canonical_manifest(ROOT), ROOT
    )


def test_cli_is_hash_seed_and_timezone_independent() -> None:
    command = [
        sys.executable,
        "scripts/validate_professional_strategy_olympics_canonical_synthetic_manifest_v003.py",
        "--root",
        str(ROOT),
    ]
    outputs = []
    for seed, timezone in (("1", "UTC"), ("77", "America/Denver"), ("9", "Asia/Tokyo")):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "PYTHONPATH": str(ROOT / "src"),
        }
        outputs.append(subprocess.run(
            command, cwd=ROOT, env=environment, check=True, capture_output=True,
        ).stdout)
    assert len(set(outputs)) == 1


@pytest.mark.parametrize("field", ["schema_name", "schema_version"])
def test_wrong_schema_or_version_fails_closed(field: str) -> None:
    with pytest.raises(OlympicsInputManifestV003Error):
        validate_canonical_manifest(root_change(field, "unsupported"), ROOT)


@pytest.mark.parametrize(
    "field",
    [
        "v002_contract_identity",
        "v003_contract_identity",
        "v003_adapter_contract_identity",
        "v003_adapter_implementation_identity",
        "v001_orchestrator_contract_identity",
        "v001_orchestrator_implementation_identity",
        "v002_adapter_contract_identity",
        "v002_adapter_implementation_identity",
        "v004_scoring_bundle_identity",
        "executor_registry_identity",
        "simulator_registry_identity",
        "lifecycle_identity",
    ],
)
def test_wrong_lineage_identity_fails_closed(field: str) -> None:
    with pytest.raises(OlympicsInputManifestV003Error):
        validate_canonical_manifest(root_change(field, "f" * 64), ROOT)


def test_missing_unknown_and_stale_manifest_identity_fail_closed() -> None:
    missing = raw_manifest()
    missing.pop("v002_contract_identity")
    unknown = raw_manifest()
    unknown["unknown"] = False
    stale = raw_manifest()
    stale["source_commit_identity"] = "f" * 40
    for value in (missing, unknown, stale):
        with pytest.raises(OlympicsInputManifestV003Error):
            validate_canonical_manifest(value, ROOT)


def test_wrong_but_valid_source_commit_fails_canonical_binding() -> None:
    with pytest.raises(CanonicalSyntheticManifestV003Error, match="source_commit"):
        validate_canonical_manifest(
            root_change("source_commit_identity", "f" * 40), ROOT
        )


def test_entrant_count_substitution_duplication_and_order_fail_closed() -> None:
    values = []
    count = raw_manifest()
    count["entrant_count"] = 9
    values.append(reidentify_v003(count))
    substitution = raw_manifest()
    substitution["entrants"][0]["entrant_id"] = "substitute"
    values.append(reidentify_v003(substitution))
    duplicate = raw_manifest()
    duplicate["entrants"][1] = deepcopy(duplicate["entrants"][0])
    values.append(reidentify_v003(duplicate))
    order = raw_manifest()
    order["entrants"][0], order["entrants"][1] = (
        order["entrants"][1], order["entrants"][0]
    )
    values.append(reidentify_v003(order))
    for value in values:
        with pytest.raises((OlympicsInputManifestV003Error, CanonicalSyntheticManifestV003Error)):
            validate_canonical_manifest(value, ROOT)


def test_duplicate_and_reordered_trades_fail_closed() -> None:
    duplicate = raw_manifest()
    duplicate["entrants"][0]["trades"].append(
        deepcopy(duplicate["entrants"][0]["trades"][0])
    )
    duplicate["entrants"][0]["trade_count"] = 2
    duplicate = reidentify_v003(duplicate)
    reordered = raw_manifest()
    second = deepcopy(reordered["entrants"][0]["trades"][0])
    second["proposal_timestamp_nanoseconds"] += 1
    reordered["entrants"][0]["trades"].append(second)
    reordered["entrants"][0]["trade_count"] = 2
    reordered = reidentify_v003(reordered)
    reordered["entrants"][0]["trades"].reverse()
    reordered = reidentify_v003(reordered)
    for value in (duplicate, reordered):
        with pytest.raises(OlympicsInputManifestV003Error):
            validate_canonical_manifest(value, ROOT)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("direction", "short"),
        ("actual_quantity", -100),
        ("actual_entry_timestamp_nanoseconds", 0),
        ("stop_microdollars", 11_000_000),
        ("target_microdollars", 9_000_000),
        ("exit_reason", "stop"),
        ("gross_pnl_microdollars", 1),
        ("net_pnl_microdollars", 1),
        ("initial_risk_microdollars", 1),
        ("elapsed_holding_nanoseconds", 1),
        ("capital_efficiency_numerator_microdollars", 1),
        ("validation_classification", "opened"),
        ("other_costs_microdollars", 1),
    ],
)
def test_trade_reconciliation_failures_are_never_repaired(field: str, value: object) -> None:
    with pytest.raises(OlympicsInputManifestV003Error):
        validate_canonical_manifest(trade_change(field, value), ROOT)


def test_lifecycle_net_r_cost_stress_float_path_and_network_fail_closed() -> None:
    values = []
    lifecycle = raw_manifest()
    lifecycle["entrants"][0]["trades"][0]["lifecycle_evidence"]["target_reached"] = False
    values.append(reidentify_v003(lifecycle))
    net_r = raw_manifest()
    net_r["entrants"][0]["trades"][0]["net_R"]["numerator"] = 2
    values.append(reidentify_v003(net_r))
    stress = raw_manifest()
    stress["entrants"][0]["trades"][0]["cost_stress_source"]["entry_commission_microdollars"] = 2
    values.append(reidentify_v003(stress))
    floating = raw_manifest()
    floating["entrants"][0]["trades"][0]["confidence"]["numerator"] = 0.8
    floating["manifest_identity"] = manifest_identity(floating)
    values.append(floating)
    path = raw_manifest()
    path["entrants"][0]["trades"][0]["regime_label"] = "/" + "Users/local/data"
    path["manifest_identity"] = manifest_identity(path)
    values.append(path)
    network = raw_manifest()
    network["entrants"][0]["trades"][0]["regime_label"] = (
        "https:" + "//provider.test"
    )
    network["manifest_identity"] = manifest_identity(network)
    values.append(network)
    for value in values:
        with pytest.raises(OlympicsInputManifestV003Error):
            validate_canonical_manifest(value, ROOT)
