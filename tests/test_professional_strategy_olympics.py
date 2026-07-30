from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics import (
    ARTIFACT_NAMESPACE,
    CAPITAL_GOVERNANCE_IDENTITY,
    LEAN_PROTOCOL_IDENTITY,
    LEAN_READINESS_IDENTITY,
    OlympicsError,
    REQUIRED_STRATEGY_FIELDS,
    STRATEGY_IDS,
    V002_PROTOCOL_IDENTITY,
    assess_advancement,
    authorize_discovery_path,
    build_readiness,
    evidence_reset_stage,
    load_protocol,
    load_readiness_artifact,
    load_registry,
    load_tournament,
    score_competitor,
    validate_claim,
    validate_protocol,
    validate_registry,
    validate_tournament,
)
from aml.winner_archetype_contracts import canonical_hash, canonical_json


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config/professional_strategy_olympics_protocol_v001.json"
REGISTRY_PATH = ROOT / "config/professional_strategy_olympics_strategy_registry_v001.json"
TOURNAMENT_PATH = ROOT / "config/professional_strategy_olympics_tournament_v001.json"
READINESS_PATH = ROOT / "config/professional_strategy_olympics_readiness_v001.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_v001.py"


@pytest.fixture(scope="module")
def artifacts():
    protocol = load_protocol(PROTOCOL_PATH)
    registry = load_registry(REGISTRY_PATH, protocol)
    tournament = load_tournament(TOURNAMENT_PATH, protocol, registry)
    readiness = load_readiness_artifact(
        READINESS_PATH, protocol, registry, tournament
    )
    return protocol, registry, tournament, readiness


def reidentify(value, field):
    value[field] = canonical_hash({key: item for key, item in value.items() if key != field})
    return value


def test_frozen_identity_chain(artifacts):
    protocol, registry, tournament, readiness = artifacts
    assert protocol["protocol_identity"] == "8a7f4c2ca1c6b133e769992ef8315186de87b0f7f1baedf6d549536db6f72f3e"
    assert registry["registry_identity"] == "af1e44069fd5e226ad702469fdf10c7e0b1c49c803065e20c83588b22e17bbc0"
    assert tournament["tournament_identity"] == "10d41bf657759b5db5b5524a18158a480797ab9dcfcca59e7921672d31bb70aa"
    assert readiness["readiness_identity"] == "ebe1179fea526e4bad0c808609ff68320840d57d2172355227edfeccaf054602"


def test_independence_bindings_are_frozen(artifacts):
    independence = artifacts[0]["independence"]
    assert independence["lean_protocol_identity"] == LEAN_PROTOCOL_IDENTITY
    assert independence["lean_readiness_identity"] == LEAN_READINESS_IDENTITY
    assert independence["capital_governance_identity"] == CAPITAL_GOVERNANCE_IDENTITY
    assert independence["v002_protocol_identity"] == V002_PROTOCOL_IDENTITY
    assert independence["readiness_credit_inheritance"] == "none"


def test_exactly_ten_canonical_benchmark_families(artifacts):
    strategies = artifacts[1]["strategies"]
    assert tuple(item["strategy_id"] for item in strategies) == STRATEGY_IDS
    assert len(strategies) == 10
    assert len({item["strategy_identity"] for item in strategies}) == 10
    assert all(item["division"] == "benchmark" for item in strategies)
    assert all(item["direction"] == "long_only" for item in strategies)
    assert all(item["allowed_parameter_variants"] == [] for item in strategies)


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_every_strategy_contract_is_complete_and_mechanical(artifacts, strategy_id):
    strategy = next(
        item for item in artifacts[1]["strategies"] if item["strategy_id"] == strategy_id
    )
    assert set(strategy) == REQUIRED_STRATEGY_FIELDS
    assert strategy["lookahead_prohibited"] is True
    assert strategy["entry_price_convention"] == "next_complete_bar_open_after_trigger_plus_shared_adverse_costs"
    assert strategy["same_bar_stop_target_treatment"] == "stop_first_conservative"
    assert "completed" in strategy["exact_entry_trigger"].casefold()
    assert "point-in-time" in canonical_json(strategy).decode("utf-8").casefold() or strategy_id in {
        "failed_breakout_reversal_long_v001",
        "first_pullback_continuation_long_v001",
        "high_of_day_breakout_long_v001",
        "vwap_mean_reversion_fade_long_v001",
        "vwap_reclaim_long_v001",
    }


def test_strategy_identity_tampering_fails(artifacts):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    changed["strategies"][0]["stop_rule"] = "changed"
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="Strategy identity"):
        validate_registry(changed, protocol)


def test_protocol_identity_tampering_fails(artifacts):
    changed = deepcopy(artifacts[0])
    changed["purpose"] += " changed"
    with pytest.raises(OlympicsError, match="protocol_identity"):
        validate_protocol(changed)


def test_protocol_cannot_authorize_execution(artifacts):
    changed = deepcopy(artifacts[0])
    changed["authorization"]["pilot_authorized"] = True
    reidentify(changed, "protocol_identity")
    with pytest.raises(OlympicsError, match="cannot authorize"):
        validate_protocol(changed)


def test_research_division_must_remain_empty(artifacts):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    changed["research_division"]["entries"] = ["candidate"]
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="Research Division"):
        validate_registry(changed, protocol)


def test_more_than_three_variants_fails(artifacts):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    strategy = changed["strategies"][0]
    strategy["allowed_parameter_variants"] = ["a", "b", "c", "d"]
    reidentify(strategy, "strategy_identity")
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="no more than three"):
        validate_registry(changed, protocol)


@pytest.mark.parametrize("bad_text", ["subjective", "optimize", "tbd", "continuous_range"])
def test_subjective_or_unbounded_contract_language_fails(artifacts, bad_text):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    strategy = changed["strategies"][0]
    strategy["candidate_eligibility"] = bad_text
    reidentify(strategy, "strategy_identity")
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="prohibited"):
        validate_registry(changed, protocol)


def test_unavailable_short_contract_cannot_be_scored(artifacts):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    strategy = changed["strategies"][0]
    strategy["direction"] = "short_only"
    reidentify(strategy, "strategy_identity")
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="exhibition-only"):
        validate_registry(changed, protocol)


def test_exactly_fifteen_weighted_events(artifacts):
    events = artifacts[2]["scoring_events"]
    assert len(events) == 15
    assert sum(event["weight"] for event in events) == 100
    assert all(event["minimum_completed_trades"] >= 1 for event in events)
    assert all(event["undefined_policy"] for event in events)
    assert all(event["tie_policy"] for event in events)


def test_raw_return_only_event_fails(artifacts):
    protocol, registry, tournament, _ = artifacts
    changed = deepcopy(tournament)
    changed["scoring_events"][0]["event_id"] = "raw_return"
    reidentify(changed, "tournament_identity")
    with pytest.raises(OlympicsError, match="Raw-return"):
        validate_tournament(changed, protocol, registry)


def test_scoring_requires_every_finite_event(artifacts):
    tournament = artifacts[2]
    scores = {item["event_id"]: 50.0 for item in tournament["scoring_events"]}
    assert score_competitor(tournament, scores) == 50.0
    scores.pop("net_expectancy")
    with pytest.raises(OlympicsError, match="Every medal"):
        score_competitor(tournament, scores)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 100.1])
def test_invalid_event_scores_fail_closed(artifacts, bad):
    tournament = artifacts[2]
    scores = {item["event_id"]: 50.0 for item in tournament["scoring_events"]}
    scores["net_expectancy"] = bad
    with pytest.raises(OlympicsError):
        score_competitor(tournament, scores)


def passing_metrics(stage):
    return {
        "completed_trades": 60 if stage == "discovery" else 30,
        "net_expectancy_r": 0.05,
        "expectancy_interval_lower_r": 0,
        "maximum_drawdown_r": 8,
        "active_months": 3,
        "regime_count": 2,
        "top_symbol_pnl_fraction": 0.35,
        "top_day_pnl_fraction": 0.35,
        "variant_expectancy_range_r": 0.1,
        "critical_integrity_failures": 0,
        "strategy_identity_unchanged": True,
        "claim_compliant": True,
    }


@pytest.mark.parametrize("stage", ["discovery", "validation", "holdout"])
def test_advancement_gates_are_independent_of_execution_authority(artifacts, stage):
    result = assess_advancement(artifacts[2], stage, passing_metrics(stage))
    assert result["eligible_to_freeze_for_next_stage"] is True
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
    assert result["capital_release_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("completed_trades", 59, "insufficient_trade_count"),
        ("net_expectancy_r", 0.049, "expectancy_below_threshold"),
        ("maximum_drawdown_r", 10.01, "drawdown_breached"),
        ("top_symbol_pnl_fraction", 0.351, "symbol_concentration_breached"),
        ("top_day_pnl_fraction", 0.351, "day_concentration_breached"),
        ("variant_expectancy_range_r", 0.101, "parameter_sensitivity_breached"),
        ("critical_integrity_failures", 1, "critical_integrity_failure"),
        ("strategy_identity_unchanged", False, "strategy_changed"),
        ("claim_compliant", False, "claim_noncompliance"),
    ],
)
def test_discovery_gate_failures_are_explicit(artifacts, field, value, reason):
    metrics = passing_metrics("discovery")
    metrics[field] = value
    result = assess_advancement(artifacts[2], "discovery", metrics)
    assert result["eligible_to_freeze_for_next_stage"] is False
    assert reason in result["failures"]


def test_readiness_is_blocked_and_opens_no_data(artifacts):
    readiness = artifacts[3]
    assert readiness["status"] == "blocked"
    assert readiness["pilot_authorized"] is False
    assert readiness["empirical_data_opened"] is False
    assert readiness["validation_outcomes_opened"] is False
    assert readiness["holdout_outcomes_opened"] is False
    assert readiness["maximum_claim_level"] == 0


def test_even_complete_evidence_does_not_authorize_pilot(artifacts):
    protocol, registry, tournament, readiness = artifacts
    evidence = {key: "1" * 64 for key in readiness["required_evidence"]}
    complete = build_readiness(protocol, registry, tournament, evidence)
    assert complete["status"] == "evidence_complete_execution_not_implemented"
    assert complete["pilot_authorized"] is False
    assert complete["paper_authorized"] is False
    assert complete["live_authorized"] is False


@pytest.mark.parametrize(
    "path",
    [
        "artifacts/professional_strategy_olympics/v001/validation/result.json",
        "artifacts/professional_strategy_olympics/v001/holdout/result.json",
        "artifacts/professional_strategy_olympics/v001/live/order.json",
        "../outside.json",
    ],
)
def test_protected_or_escaping_paths_fail(tmp_path, path):
    root = tmp_path.resolve()
    with pytest.raises(OlympicsError):
        authorize_discovery_path(Path(path), root)


def test_design_namespace_path_is_allowed(tmp_path):
    root = tmp_path.resolve()
    path = Path(ARTIFACT_NAMESPACE) / "design" / "manifest.json"
    assert authorize_discovery_path(path, root) == (root / path).absolute()


@pytest.mark.parametrize(
    ("level", "claim"),
    [(0, "pipeline operational"), (2, "validated"), (4, "profitable")],
)
def test_claims_cannot_outrun_evidence(level, claim):
    with pytest.raises(OlympicsError):
        validate_claim(level, claim)


@pytest.mark.parametrize(
    "claim",
    ["best strategy", "professional winner", "proven edge", "production ready", "revenue generating"],
)
def test_absolute_olympics_claims_are_prohibited(claim):
    with pytest.raises(OlympicsError):
        validate_claim(9, claim)


@pytest.mark.parametrize(
    "change",
    ["candidate_eligibility", "entry_trigger", "exit_rule", "risk_rule", "cost_model", "parameter_variant", "market_regime_rule"],
)
def test_material_strategy_changes_reset_to_discovery(change):
    assert evidence_reset_stage(change) == "discovery"


def test_documentation_change_preserves_evidence_stage():
    assert evidence_reset_stage("documentation_only") == "unchanged"


def test_no_network_broker_or_execution_interface_in_module():
    source = (ROOT / "src/aml/professional_strategy_olympics.py").read_text()
    forbidden = ["import requests", "import httpx", "submit_order", "TradingClient", "alpaca_trade_api", "socket"]
    assert all(item not in source for item in forbidden)


def test_all_competitors_share_bound_risk_and_execution_assumptions(artifacts):
    strategies = artifacts[1]["strategies"]
    for field in (
        "entry_price_convention",
        "position_sizing_rule",
        "risk_unit",
        "slippage",
        "fees",
        "spread_assumption",
        "same_bar_stop_target_treatment",
        "maximum_concurrent_positions",
        "daily_loss_behavior",
    ):
        assert len({canonical_json(item[field]) for item in strategies}) == 1


def test_registry_rejects_competitor_specific_risk(artifacts):
    protocol, registry, _, _ = artifacts
    changed = deepcopy(registry)
    strategy = changed["strategies"][0]
    strategy["risk_unit"] = "500_USD"
    reidentify(strategy, "strategy_identity")
    reidentify(changed, "registry_identity")
    with pytest.raises(OlympicsError, match="shared risk_unit"):
        validate_registry(changed, protocol)


def test_tournament_cannot_bypass_frozen_capital_risk(artifacts):
    protocol, registry, tournament, _ = artifacts
    changed = deepcopy(tournament)
    changed["shared_environment"]["risk_per_trade_fraction"] = 0.01
    reidentify(changed, "tournament_identity")
    with pytest.raises(OlympicsError, match="risk or execution"):
        validate_tournament(changed, protocol, registry)


def test_completed_trigger_and_next_bar_rules_prohibit_future_bar_entry(artifacts):
    for strategy in artifacts[1]["strategies"]:
        assert "completed" in strategy["exact_entry_trigger"].casefold()
        assert strategy["entry_price_convention"].startswith("next_complete_bar_open")
        assert strategy["lookahead_prohibited"] is True


def run_cli(artifact, hash_seed, timezone):
    environment = os.environ.copy()
    environment.update({"PYTHONHASHSEED": hash_seed, "TZ": timezone, "PYTHONPATH": str(ROOT / "src")})
    return subprocess.run(
        [sys.executable, str(SCRIPT), artifact],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
    )


@pytest.mark.parametrize("artifact", ["protocol", "registry", "tournament", "readiness"])
def test_cli_is_byte_deterministic_across_hash_seed_and_timezone(artifact):
    first = run_cli(artifact, "1", "UTC")
    second = run_cli(artifact, "987654", "Pacific/Honolulu")
    expected_code = 2 if artifact == "readiness" else 0
    assert first.returncode == second.returncode == expected_code
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == b""


def test_tracked_readiness_matches_rebuilt_artifact(artifacts):
    protocol, registry, tournament, readiness = artifacts
    assert canonical_json(readiness) == canonical_json(
        build_readiness(protocol, registry, tournament)
    )


def test_invalid_utf8_and_duplicate_json_keys_fail(tmp_path):
    bad_utf8 = tmp_path / "bad.json"
    bad_utf8.write_bytes(b"\xff")
    with pytest.raises(OlympicsError):
        load_protocol(bad_utf8)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(OlympicsError, match="duplicate"):
        load_protocol(duplicate)


def test_nonfinite_json_is_rejected(tmp_path):
    path = tmp_path / "nan.json"
    path.write_text('{"value":NaN}')
    with pytest.raises(OlympicsError):
        load_protocol(path)
