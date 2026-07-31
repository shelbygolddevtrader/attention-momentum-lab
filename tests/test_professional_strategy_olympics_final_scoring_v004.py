from __future__ import annotations

import ast
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import os
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY,
    EVENT_FIELDS,
    EVENT_IDS,
    OlympicsFinalScoringV004Error,
    SECTION_IDENTITIES,
    SyntheticCapitalTrade,
    capital_efficiency,
    compare_downside_adjusted,
    exact_median,
    load_bundle,
    validate_bundle,
    validate_repository_lineage,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/professional_strategy_olympics_final_scoring_v004.json"


def test_frozen_bundle_and_all_section_identities() -> None:
    bundle = load_bundle(CONFIG)
    assert bundle["bundle_identity"] == BUNDLE_IDENTITY
    for section, (field, identity) in SECTION_IDENTITIES.items():
        assert bundle[section][field] == identity


def test_repository_lineage_and_immutable_tag() -> None:
    assert validate_repository_lineage(ROOT)["bundle_identity"] == BUNDLE_IDENTITY


def test_exactly_fifteen_complete_raw_events_and_one_hundred_weight() -> None:
    events = load_bundle(CONFIG)["raw_event_registry"]["events"]
    assert tuple(event["event_id"] for event in events) == EVENT_IDS
    assert all(set(event) == EVENT_FIELDS for event in events)
    assert sum(event["weight"] for event in events) == 100


def test_design_only_authorizations_and_readiness_are_closed() -> None:
    bundle = load_bundle(CONFIG)
    assert bundle["authorization"]
    assert not any(bundle["authorization"].values())
    assert bundle["readiness"]["tournament_runner_implemented"] is False
    assert bundle["readiness"]["tournament_scoring_executed"] is False
    assert bundle["readiness"]["empirical_data_accessed"] is False


def test_tampered_section_and_bundle_fail_closed() -> None:
    bundle = load_bundle(CONFIG)
    changed = deepcopy(bundle)
    changed["precision_policy"]["comparison_tolerance"] = "epsilon"
    with pytest.raises(OlympicsFinalScoringV004Error, match="precision_identity"):
        validate_bundle(changed)
    changed = deepcopy(bundle)
    changed["bundle_identity"] = "0" * 64
    with pytest.raises(OlympicsFinalScoringV004Error, match="bundle identity"):
        validate_bundle(changed)


def test_capital_efficiency_fully_deployed_and_zero_pnl() -> None:
    trade = SyntheticCapitalTrade("a", 1_000_000, 100, 10_000_000, 0, 60_000_000_000)
    assert capital_efficiency([trade]) == Fraction(1, 60_000_000_000_000)
    assert capital_efficiency([SyntheticCapitalTrade("z", 0, 1, 1, 0, 1)]) == 0


def test_capital_efficiency_sequential_overlap_partial_and_rejections() -> None:
    trades = [
        SyntheticCapitalTrade("a", 100, 10, 20, 0, 10),
        SyntheticCapitalTrade("b", 50, 5, 20, 5, 15),
        SyntheticCapitalTrade("rejected", 999, 99, 99, 0, 99, accepted=False),
    ]
    assert capital_efficiency(trades) == Fraction(150, 3_000)
    partial = SyntheticCapitalTrade("partial", 40, 40, 10, 0, 2)
    assert capital_efficiency([partial]) == Fraction(1, 20)


def test_capital_efficiency_negative_no_trade_and_integrity_failures() -> None:
    assert capital_efficiency([]) is None
    assert capital_efficiency([SyntheticCapitalTrade("x", -2, 1, 2, 0, 2)]) == Fraction(-1, 2)
    with pytest.raises(OlympicsFinalScoringV004Error, match="duplicate"):
        capital_efficiency([
            SyntheticCapitalTrade("x", 1, 1, 1, 0, 1),
            SyntheticCapitalTrade("x", 1, 1, 1, 0, 1),
        ])
    with pytest.raises(OlympicsFinalScoringV004Error, match="half-open"):
        capital_efficiency([SyntheticCapitalTrade("x", 1, 1, 1, 1, 1)])


def test_exact_median_and_downside_comparator_have_no_float_tolerance() -> None:
    assert exact_median([Fraction(0), Fraction(1), Fraction(2), Fraction(3)]) == Fraction(3, 2)
    assert compare_downside_adjusted(Fraction(1), Fraction(4), Fraction(1), Fraction(1)) == -1
    assert compare_downside_adjusted(Fraction(-1), Fraction(4), Fraction(-1), Fraction(1)) == 1
    assert compare_downside_adjusted(Fraction(0), Fraction(1), Fraction(0), Fraction(2)) == 0


def test_worked_examples_are_complete_deterministic_design_vectors() -> None:
    examples = load_bundle(CONFIG)["worked_examples"]
    assert examples["claim"] == "synthetic_design_vectors_only_not_results"
    assert len(examples["examples"]) == 19
    assert len({example["id"] for example in examples["examples"]}) == 19


def test_lifecycle_portfolio_cost_and_disqualification_contracts_are_explicit() -> None:
    bundle = load_bundle(CONFIG)
    assert "stop is evaluated before target" in bundle["lifecycle_outcome_semantics"]["same_bar"]
    assert "exits first" in bundle["portfolio_capital_semantics"]["same_timestamp"]
    assert bundle["cost_stress_semantics"]["raw_formula"].startswith("minimum(")
    assert len(bundle["cost_stress_semantics"]["scenarios"]) == 3
    actions = {rule["action"] for rule in bundle["disqualification_matrix"]["rules"]}
    assert actions == {"tournament_abort", "entrant_disqualification", "event_failure", "trade_rejection", "proposal_rejection"}


def test_canonical_output_is_identical_across_hash_seed_and_timezone() -> None:
    script = ROOT / "scripts/validate_professional_strategy_olympics_final_scoring_v004.py"
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "America/New_York")):
        env = os.environ.copy()
        env.update({"PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONPATH": str(ROOT / "src")})
        outputs.append(subprocess.run(
            [sys.executable, str(script), "--repository-root", str(ROOT), "--skip-tag-check"],
            check=True, capture_output=True, env=env,
        ).stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["bundle_identity"] == BUNDLE_IDENTITY


def test_design_module_has_no_runner_network_or_production_boundary_imports() -> None:
    module_path = ROOT / "src/aml/professional_strategy_olympics_final_scoring_v004.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint({"requests", "httpx", "urllib", "socket", "alpaca", "aiohttp"})
    source = module_path.read_text(encoding="utf-8")
    assert "forward_validation" not in source
    assert "holdout" not in "\n".join(
        line for line in source.splitlines() if line.lstrip().startswith(("import ", "from "))
    )
    assert "run_tournament" not in source
