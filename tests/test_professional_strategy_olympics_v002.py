from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_v002 import (
    OlympicsV002Error,
    SECTION_IDENTITIES,
    STRATEGY_IDS,
    V001_PROTOCOL_IDENTITY,
    V001_READINESS_IDENTITY,
    V001_REGISTRY_IDENTITY,
    V001_TOURNAMENT_IDENTITY,
    canonical_bundle_bytes,
    load_bundle,
    validate_bundle,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config/professional_strategy_olympics_v002.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_v002.py"
BUNDLE = load_bundle(PATH)


def identify(value, field):
    value[field] = canonical_hash({key: item for key, item in value.items() if key != field})


def identify_root(value):
    identify(value, "protocol_identity")
    return value


def test_v002_protocol_identity_is_frozen():
    assert BUNDLE["protocol_identity"] == "fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583"


def test_v001_identity_lineage_is_exact_and_immutable():
    lineage = BUNDLE["historical_lineage"]
    assert lineage["v001_protocol_identity"] == V001_PROTOCOL_IDENTITY
    assert lineage["v001_registry_identity"] == V001_REGISTRY_IDENTITY
    assert lineage["v001_tournament_identity"] == V001_TOURNAMENT_IDENTITY
    assert lineage["v001_readiness_identity"] == V001_READINESS_IDENTITY
    v001 = json.loads(
        (ROOT / "config/professional_strategy_olympics_protocol_v001.json").read_text()
    )
    assert v001["protocol_identity"] == V001_PROTOCOL_IDENTITY


@pytest.mark.parametrize(
    ("section", "identity"),
    [
        ("shared_indicators", "3d1427872fc8d55e3cacc321f710a6a2b260d0a1d01259147b6ff3a422a6f852"),
        ("input_schema", "a3fc7f17fb30eaf69ec00f2955f68f1b54dc3247edc54590706abee719ba3fac"),
        ("lifecycle", "b61fa2557718cdf1dbebc0e91990bb27be3d880111bea424d967dd96253dfe12"),
        ("costs", "ba239ed1b835d91be06a674433559c2b679c07fd37b9820f0c4fe7cf7ada4570"),
        ("registry", "5a43302ca893bcb9323b0a0b473282abd36d0b4d0917322dfb5c817ca3bfd43a"),
        ("tournament", "f011b03b6d4b4249e4c4d77b029cbb74145c7f7f53486e0af89d0433da395308"),
        ("evidence_classification", "36eb12d994052735aa084f56951db088e5b1ef46d4bde856e5eba4e355d43172"),
        ("unresolved_register", "1c7e480fdf5a69a7ad4b7af6f78131181b140dbe30ef402c5bd5e5cdeb1bc0bf"),
        ("readiness", "fb9799d8cda9a671a58408f0d540d7a6ab39fe868163a2ce105eb6f1218de03b"),
    ],
)
def test_section_identity_is_frozen(section, identity):
    assert BUNDLE[section][SECTION_IDENTITIES[section]] == identity


def test_exact_ten_v002_contracts_exist_in_stable_order():
    assert tuple(item["strategy_id"] for item in BUNDLE["strategies"]) == STRATEGY_IDS
    assert len({item["strategy_identity"] for item in BUNDLE["strategies"]}) == 10


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_each_strategy_is_canonical_long_only_and_fixture_ready(strategy_id):
    strategy = next(item for item in BUNDLE["strategies"] if item["strategy_id"] == strategy_id)
    assert strategy["direction"] == "long_only"
    assert strategy["allowed_parameter_variants"] == []
    assert strategy["claim_ceiling"] == "design_only"
    assert set(strategy["synthetic_fixture_contract"]) == {
        "positive_path", "negative_path", "unavailable_path", "integrity_failure_path"
    }
    assert all(strategy["synthetic_fixture_contract"].values())
    assert strategy["entry"]["rule"] == "shared_next_exact_bar_open"
    assert strategy["stop"]["rule"]
    assert strategy["target"]["rule"]
    assert strategy["timeout"]["complete_bars"] > 0
    assert strategy["tie_breaking"]


def test_failed_breakout_lineage_is_renamed_coherently():
    strategy = BUNDLE["strategies"][0]
    assert strategy["strategy_id"] == "failed_downside_breakdown_reclaim_long_v002"
    assert "bullish" in strategy["name"].casefold()
    assert "renamed" in strategy["v001_lineage"]


def test_opening_ranges_remain_distinct_contracts():
    five = next(item for item in BUNDLE["strategies"] if item["strategy_id"].startswith("five_minute"))
    fifteen = next(item for item in BUNDLE["strategies"] if item["strategy_id"].startswith("fifteen_minute"))
    assert five["strategy_identity"] != fifteen["strategy_identity"]
    assert five["observation_window"] != fifteen["observation_window"]
    assert five["allowed_parameter_variants"] == fifteen["allowed_parameter_variants"] == []


def test_all_indicator_definitions_are_complete_and_unique():
    definitions = BUNDLE["shared_indicators"]["definitions"]
    required = {
        "indicator_id", "formula", "inputs", "lookback", "minimum_observations",
        "session_policy", "missing_policy", "halt_policy", "corporate_action_policy",
        "availability", "precision",
    }
    assert len({item["indicator_id"] for item in definitions}) == len(definitions) == 9
    assert all(set(item) == required for item in definitions)
    assert all(item["minimum_observations"] >= 1 for item in definitions)


def test_all_input_definitions_are_complete_and_unique():
    datasets = BUNDLE["input_schema"]["datasets"]
    required = {
        "input_id", "required_fields", "timestamp_rule", "completeness_rule",
        "point_in_time_rule", "failure_rule",
    }
    assert len({item["input_id"] for item in datasets}) == len(datasets) == 7
    assert all(set(item) == required for item in datasets)
    assert all(item["required_fields"] for item in datasets)


def test_every_strategy_reference_resolves():
    indicator_ids = {item["indicator_id"] for item in BUNDLE["shared_indicators"]["definitions"]}
    input_ids = {item["input_id"] for item in BUNDLE["input_schema"]["datasets"]}
    for strategy in BUNDLE["strategies"]:
        assert set(strategy["required_indicators"]) <= indicator_ids
        assert set(strategy["required_inputs"]) <= input_ids


def test_shared_lifecycle_defines_every_path():
    lifecycle = BUNDLE["lifecycle"]
    assert {"bar_semantics", "entry", "stop", "target", "timeout", "invalidation", "halts"} <= set(lifecycle)
    assert lifecycle["entry"]["maximum_delay_minutes"] == 0
    assert lifecycle["stop"]["same_bar"] == "after_open_check_stop_before_target"
    assert lifecycle["target"]["indicator_target"].endswith("never_dynamic_after_entry")
    assert lifecycle["timeout"]["missing_liquidation_bar"].startswith("integrity_failure")
    assert lifecycle["halts"]["unavailable_evidence"] == "entire_symbol_session_unavailable"


def test_cost_model_is_exact_and_net_of_commissions():
    costs = BUNDLE["costs"]
    assert costs["market_friction_basis_points_per_side"] == 10
    assert costs["long_entry_fill"] == "raw_open*(1+0.001)"
    assert costs["long_exit_fill"] == "raw_exit*(1-0.001)"
    assert costs["commission_usd_per_share_per_order"] == 0.005
    assert costs["minimum_commission_usd_per_order"] == 1
    assert costs["risk_budget_usd"] == 250


def test_market_regime_filter_was_prospectively_removed():
    strategy = next(item for item in BUNDLE["strategies"] if item["strategy_id"].startswith("market_relative"))
    assert strategy["eligibility"]["market_regime_rule"].startswith("prospectively_removed")


def test_unresolved_register_has_zero_material_items():
    unresolved = BUNDLE["unresolved_register"]
    assert unresolved["material_item_count"] == 0
    assert unresolved["items"] == []


def test_contract_presence_never_receives_score_credit():
    assert BUNDLE["registry"]["implementation_credit"].startswith("contract_presence_never")
    assert BUNDLE["tournament"]["no_contract_credit"] is True
    assert "complete_contract_aware_evaluator" in BUNDLE["tournament"]["score_eligibility"]


def test_synthetic_evidence_is_non_empirical_and_cannot_advance():
    evidence = BUNDLE["evidence_classification"]
    synthetic = next(item for item in evidence["classes"] if item["class"] == "synthetic_fixture")
    assert synthetic["counts_as_empirical"] is False
    assert "cannot_satisfy_empirical" in evidence["synthetic_prohibition"]


def test_every_authorization_remains_false():
    assert BUNDLE["authorization"]
    assert all(value is False for value in BUNDLE["authorization"].values())
    assert all(BUNDLE["readiness"][key] is False for key in BUNDLE["authorization"])
    assert BUNDLE["readiness"]["status"] == "design_complete_implementation_not_authorized"


def test_identity_tampering_fails():
    changed = deepcopy(BUNDLE)
    changed["costs"]["market_friction_basis_points_per_side"] = 9
    identify_root(changed)
    with pytest.raises(OlympicsV002Error, match="cost_model_identity"):
        validate_bundle(changed)


def test_undefined_indicator_reference_fails_even_when_reidentified():
    changed = deepcopy(BUNDLE)
    strategy = changed["strategies"][0]
    strategy["required_indicators"] = ["missing_indicator"]
    identify(strategy, "strategy_identity")
    changed["registry"]["strategy_identities"][0] = strategy["strategy_identity"]
    identify(changed["registry"], "registry_identity")
    changed["tournament"]["registry_identity"] = changed["registry"]["registry_identity"]
    identify(changed["tournament"], "tournament_identity")
    changed["readiness"]["registry_identity"] = changed["registry"]["registry_identity"]
    changed["readiness"]["tournament_identity"] = changed["tournament"]["tournament_identity"]
    identify(changed["readiness"], "readiness_identity")
    identify_root(changed)
    with pytest.raises(OlympicsV002Error, match="undefined indicator"):
        validate_bundle(changed)


@pytest.mark.parametrize("field", ["setup", "trigger", "entry", "stop", "target", "timeout", "tie_breaking"])
def test_undefined_strategy_rule_fails(field):
    changed = deepcopy(BUNDLE)
    strategy = changed["strategies"][0]
    strategy[field] = "undefined"
    identify(strategy, "strategy_identity")
    changed["registry"]["strategy_identities"][0] = strategy["strategy_identity"]
    identify(changed["registry"], "registry_identity")
    changed["tournament"]["registry_identity"] = changed["registry"]["registry_identity"]
    identify(changed["tournament"], "tournament_identity")
    changed["readiness"]["registry_identity"] = changed["registry"]["registry_identity"]
    changed["readiness"]["tournament_identity"] = changed["tournament"]["tournament_identity"]
    identify(changed["readiness"], "readiness_identity")
    identify_root(changed)
    with pytest.raises(OlympicsV002Error, match="unresolved"):
        validate_bundle(changed)


def test_material_unresolved_item_fails_even_when_reidentified():
    changed = deepcopy(BUNDLE)
    changed["unresolved_register"]["material_item_count"] = 1
    changed["unresolved_register"]["items"] = ["target_formula"]
    identify(changed["unresolved_register"], "unresolved_identity")
    changed["readiness"]["unresolved_identity"] = changed["unresolved_register"]["unresolved_identity"]
    identify(changed["readiness"], "readiness_identity")
    identify_root(changed)
    with pytest.raises(OlympicsV002Error, match="unresolved"):
        validate_bundle(changed)


def test_authorization_cannot_be_enabled_even_when_reidentified():
    changed = deepcopy(BUNDLE)
    changed["authorization"]["empirical_runner_authorized"] = True
    identify_root(changed)
    with pytest.raises(OlympicsV002Error, match="cannot authorize"):
        validate_bundle(changed)


def test_canonical_bundle_is_stable():
    assert canonical_bundle_bytes(BUNDLE) == canonical_bundle_bytes(load_bundle(PATH))


def run_cli(seed, timezone):
    environment = os.environ.copy()
    environment.update({"PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONPATH": str(ROOT / "src")})
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, env=environment,
        check=False, capture_output=True,
    )


def test_serialization_is_deterministic_across_hash_seed_and_timezone():
    outputs = [
        run_cli("1", "UTC"),
        run_cli("987654", "UTC"),
        run_cli("1", "America/New_York"),
        run_cli("987654", "America/New_York"),
    ]
    assert {item.returncode for item in outputs} == {2}
    assert len({item.stdout for item in outputs}) == 1
    assert all(item.stderr == b"" for item in outputs)


def test_no_empirical_runner_network_provider_broker_or_production_import():
    files = [
        ROOT / "src/aml/professional_strategy_olympics_v002.py",
        ROOT / "scripts/validate_professional_strategy_olympics_v002.py",
    ]
    text = "\n".join(path.read_text() for path in files)
    forbidden = (
        "import requests", "import httpx", "urllib.request", "TradingClient",
        "submit_order", "place_order", "get_account", "alpaca", "simulate_trades",
        "portfolio_simulator", "tournament_runner",
    )
    assert all(token not in text for token in forbidden)


def test_new_files_contain_no_empirical_or_generated_data_extensions():
    paths = [PATH, SCRIPT, ROOT / "src/aml/professional_strategy_olympics_v002.py"]
    assert all(path.suffix in {".json", ".py"} for path in paths)
