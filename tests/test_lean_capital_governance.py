from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.lean_capital_governance import (
    STAGE_ORDER,
    CapitalGovernanceError,
    allocate_realized_profit,
    assess_stage_entry,
    canonical_governance_bytes,
    load_governance,
    regression_stage,
    runtime_authorization_survives,
    validate_capital_claim,
    validate_governance,
    validate_reserve_purchase_plan,
    validate_scaling_step,
)
from aml.winner_archetype_contracts import canonical_json


ROOT = Path(__file__).parents[1]
GOVERNANCE_PATH = ROOT / "config/lean_discovery_capital_governance_v001.json"
PROTOCOL_PATH = ROOT / "config/lean_discovery_protocol_v001.json"
CLI = ROOT / "scripts/validate_lean_capital_governance_v001.py"
GOVERNANCE = load_governance(GOVERNANCE_PATH)


def _tiny_live_evidence(**overrides):
    evidence = {
        "completed_stages": list(STAGE_ORDER[:4]),
        "observation_calendar_days": 180,
        "observation_trading_sessions": 0,
        "signals": 100,
        "completed_trades": 100,
        "net_expectancy_r": 0.08,
        "expectancy_interval_lower_r": 0.01,
        "maximum_drawdown_pct": 4.0,
        "maximum_drawdown_r": 7.0,
        "signal_capture_rate": 0.96,
        "median_implementation_shortfall_bps": 10.0,
        "p95_implementation_shortfall_bps": 40.0,
        "data_completeness_rate": 0.999,
        "integrity_failures": 0,
        "strategy_identity_matches": True,
        "disposable_risk_declaration": True,
        "prohibited_capital_source_present": False,
        "prohibited_sizing_or_leverage_detected": False,
        "validated_strategy_risk_limit_pct": 0.25,
        "maximum_risk_per_trade_pct": 0.25,
        "maximum_daily_loss_pct": 0.49,
        "maximum_weekly_loss_pct": 1.49,
        "human_approval_evidence_hashes": {
            field: f"{index:064x}"
            for index, field in enumerate(
                GOVERNANCE["stages"][4]["human_approval_evidence"], start=1
            )
        },
    }
    evidence.update(overrides)
    return evidence


def _allocation_request(**overrides):
    request = {
        "stage_id": "limited_self_funding",
        "source_type": "settled_realized_net_trading_profit",
        "eligible_profit_cents": 100_000,
        "ending_equity_cents": 1_100_000,
        "prior_high_water_equity_cents": 1_000_000,
        "external_deposit_cents": 0,
        "unrealized_pnl_cents": 0,
        "recovered_loss_cents": 0,
        "completed_trade_hashes": ["1" * 64, "2" * 64],
        "reconciliation_manifest_hash": "3" * 64,
        "account_statement_hash": "4" * 64,
    }
    request.update(overrides)
    return request


def test_tracked_governance_is_canonical_identity_bound_and_design_only():
    assert GOVERNANCE["governance_identity"] == (
        "6defde5b21b8aac1a4a1b15c501621163dcb9c400f629abd29b257f7a51073cf"
    )
    assert GOVERNANCE["lean_protocol_identity"] == json.loads(PROTOCOL_PATH.read_text())[
        "protocol_identity"
    ]
    assert canonical_governance_bytes(GOVERNANCE_PATH) == canonical_json(GOVERNANCE)
    assert GOVERNANCE["status"] == "design_only_all_execution_unauthorized"
    assert not any(
        GOVERNANCE["authorization"][field]
        for field in (
            "paper_authorized", "live_authorized", "reserve_transfer_authorized",
            "provider_purchase_authorized",
        )
    )


def test_all_seven_stages_define_every_required_governance_dimension():
    stages = GOVERNANCE["stages"]
    assert [stage["id"] for stage in stages] == list(STAGE_ORDER)
    required = {
        "entry_requirements", "minimum_observation_period", "minimum_signals",
        "minimum_completed_trades", "allowable_strategy_changes",
        "net_expectancy_threshold", "maximum_drawdown",
        "execution_quality_threshold", "data_quality_threshold",
        "risk_per_trade_limit", "daily_loss_limit_pct", "weekly_loss_limit_pct",
        "shutdown_conditions", "human_approval_evidence", "regression_conditions",
    }
    assert all(required <= set(stage) for stage in stages)


def test_live_gate_cannot_pass_before_every_prior_stage():
    evidence = _tiny_live_evidence(completed_stages=list(STAGE_ORDER[:3]))
    result = assess_stage_entry(GOVERNANCE, "tiny_live_capital_test", evidence)
    assert result["eligible_for_human_review"] is False
    assert "prior_stages_incomplete" in result["failures"]
    assert result["execution_authorized"] is False


def test_complete_gate_evidence_only_enables_human_review_not_execution():
    result = assess_stage_entry(
        GOVERNANCE, "tiny_live_capital_test", _tiny_live_evidence()
    )
    assert result["eligible_for_human_review"] is True
    assert result["execution_authorized"] is False
    assert result["design_only"] is True


@pytest.mark.parametrize(
    "field,value,reason",
    (
        ("integrity_failures", 1, "integrity_failure"),
        ("strategy_identity_matches", False, "strategy_identity_drift"),
        ("data_completeness_rate", 0.998, "data_quality_below_threshold"),
        ("net_expectancy_r", 0.01, "net_expectancy_below_threshold"),
        ("maximum_drawdown_pct", 5.1, "maximum_drawdown_breached"),
        ("signal_capture_rate", 0.94, "execution_capture_below_threshold"),
        ("disposable_risk_declaration", False, "disposable_risk_not_declared"),
        ("prohibited_capital_source_present", True, "prohibited_capital_source"),
        ("prohibited_sizing_or_leverage_detected", True, "prohibited_sizing_or_leverage"),
        ("maximum_risk_per_trade_pct", 0.251, "risk_per_trade_limit_breached"),
        ("maximum_daily_loss_pct", 0.5, "daily_loss_limit_breached"),
        ("maximum_weekly_loss_pct", 1.5, "weekly_loss_limit_breached"),
    ),
)
def test_live_gate_fails_closed_on_threshold_or_integrity_breach(field, value, reason):
    result = assess_stage_entry(
        GOVERNANCE, "tiny_live_capital_test", _tiny_live_evidence(**{field: value})
    )
    assert result["eligible_for_human_review"] is False
    assert reason in result["failures"]


def test_initial_live_risk_and_loss_caps_are_frozen():
    stage = GOVERNANCE["stages"][4]
    assert stage["risk_per_trade_limit"] == {
        "rule": "lower_of_account_equity_pct_or_frozen_validated_strategy_limit",
        "maximum_equity_pct": 0.25,
        "validated_strategy_limit_required": True,
    }
    assert stage["daily_loss_limit_pct"] == 0.5
    assert stage["weekly_loss_limit_pct"] == 1.5


def test_discovery_minimum_trading_sessions_are_enforced():
    evidence = {
        "completed_stages": [],
        "observation_calendar_days": 0,
        "observation_trading_sessions": 29,
        "signals": 60,
        "completed_trades": 0,
        "data_completeness_rate": 0.999,
        "integrity_failures": 0,
        "strategy_identity_matches": True,
        "human_approval_evidence_hashes": {
            field: f"{index:064x}"
            for index, field in enumerate(
                GOVERNANCE["stages"][0]["human_approval_evidence"], start=1
            )
        },
    }
    result = assess_stage_entry(GOVERNANCE, "discovery_research", evidence)
    assert "minimum_observation_sessions_not_met" in result["failures"]


@pytest.mark.parametrize(
    "daily,weekly,integrity,identity,drift,execution",
    (
        (0.5, 0.0, 0, True, False, False),
        (0.0, 1.5, 0, True, False, False),
        (0.0, 0.0, 1, True, False, False),
        (0.0, 0.0, 0, False, False, False),
        (0.0, 0.0, 0, True, True, False),
        (0.0, 0.0, 0, True, False, True),
    ),
)
def test_loss_integrity_identity_strategy_or_execution_breach_revokes_authorization(
    daily, weekly, integrity, identity, drift, execution
):
    assert runtime_authorization_survives(
        authorization_active=True,
        daily_loss_pct=daily,
        weekly_loss_pct=weekly,
        stage_daily_limit_pct=0.5,
        stage_weekly_limit_pct=1.5,
        integrity_failures=integrity,
        identity_matches=identity,
        strategy_drift=drift,
        execution_threshold_breached=execution,
    ) is False


def test_runtime_guardrail_cannot_create_authorization():
    assert runtime_authorization_survives(
        authorization_active=False,
        daily_loss_pct=0.0,
        weekly_loss_pct=0.0,
        stage_daily_limit_pct=0.5,
        stage_weekly_limit_pct=1.5,
        integrity_failures=0,
        identity_matches=True,
        strategy_drift=False,
        execution_threshold_breached=False,
    ) is False


@pytest.mark.parametrize(
    "change,expected",
    (
        ("strategy_logic", "discovery_research"),
        ("signal_threshold", "discovery_research"),
        ("sizing_or_risk", "discovery_research"),
        ("market_data_semantics", "discovery_research"),
        ("execution_adapter_material", "prospective_paper_forward"),
        ("documentation_only", "controlled_scaling"),
    ),
)
def test_strategy_and_execution_changes_reset_applicable_evidence_stage(change, expected):
    assert regression_stage(change) == expected


def test_unknown_change_type_fails_closed():
    with pytest.raises(CapitalGovernanceError, match="fails closed"):
        regression_stage("unclassified_change")


def test_scaling_is_limited_to_25_percent_and_review_gates():
    result = validate_scaling_step(
        GOVERNANCE,
        previous_risk_units=100,
        proposed_risk_units=125,
        new_completed_trades=100,
        observation_days=90,
        human_approved=True,
    )
    assert result["increase_basis_points"] == 2500
    assert result["execution_authorized"] is False
    with pytest.raises(CapitalGovernanceError, match="25 percent"):
        validate_scaling_step(
            GOVERNANCE,
            previous_risk_units=100,
            proposed_risk_units=126,
            new_completed_trades=100,
            observation_days=90,
            human_approved=True,
        )


@pytest.mark.parametrize(
    "changes,message",
    (
        ({"source_type": "deposit"}, "Only settled"),
        ({"external_deposit_cents": 1}, "external_deposit"),
        ({"unrealized_pnl_cents": 1}, "unrealized"),
        ({"recovered_loss_cents": 1}, "recovered_loss"),
        ({"ending_equity_cents": 1_050_000}, "Recovered losses"),
        ({"stage_id": "tiny_live_capital_test"}, "unavailable"),
    ),
)
def test_deposits_unrealized_pnl_and_recovered_losses_cannot_fund_reserve(changes, message):
    with pytest.raises(CapitalGovernanceError, match=message):
        allocate_realized_profit(GOVERNANCE, _allocation_request(**changes))


def test_realized_profit_allocation_is_auditable_and_50_30_20():
    result = allocate_realized_profit(GOVERNANCE, _allocation_request())
    assert result["retained_trading_capital_cents"] == 50_000
    assert result["data_platform_reserve_cents"] == 30_000
    assert result["tax_and_operational_uncertainty_cents"] == 20_000
    assert result["completed_trade_hashes"] == ["1" * 64, "2" * 64]
    assert result["transfer_authorized"] is False
    assert result["human_review_required"] is True


def test_provider_purchase_plan_cannot_use_forecast_profit_or_exceed_reserve():
    with pytest.raises(CapitalGovernanceError, match="forecast"):
        validate_reserve_purchase_plan(
            available_reserve_cents=100_000,
            proposed_cost_cents=50_000,
            forecast_profit_cents=1,
            human_approved=True,
        )
    with pytest.raises(CapitalGovernanceError, match="exceeds"):
        validate_reserve_purchase_plan(
            available_reserve_cents=40_000,
            proposed_cost_cents=50_000,
            forecast_profit_cents=0,
            human_approved=True,
        )


@pytest.mark.parametrize("source", ("backtest_gain", "paper_gain", "unrealized_gain", "deposit"))
def test_non_realized_sources_cannot_be_described_as_revenue(source):
    with pytest.raises(CapitalGovernanceError, match="not revenue"):
        validate_capital_claim(
            achieved_stage="controlled_scaling",
            source_type=source,
            text="This is scalable business revenue.",
            separate_business_evidence=True,
        )


def test_claim_ladder_requires_stage_source_and_separate_business_evidence():
    with pytest.raises(CapitalGovernanceError, match="Self-funding"):
        validate_capital_claim(
            achieved_stage="tiny_live_capital_test",
            source_type="settled_realized_net_trading_profit",
            text="The platform has self-funding capability.",
        )
    validate_capital_claim(
        achieved_stage="limited_self_funding",
        source_type="settled_realized_net_trading_profit",
        text="Limited self-funding evidence was observed.",
    )
    with pytest.raises(CapitalGovernanceError, match="separate evidence"):
        validate_capital_claim(
            achieved_stage="controlled_scaling",
            source_type="settled_realized_net_trading_profit",
            text="This is scalable business revenue.",
        )


def test_tampering_governance_identity_stage_order_or_authorization_fails():
    mutations = []
    changed = deepcopy(GOVERNANCE)
    changed["funding_reserve"]["allocation_defaults_pct"]["data_platform_reserve"] = 31
    mutations.append(changed)
    changed = deepcopy(GOVERNANCE)
    changed["stage_order"] = list(reversed(changed["stage_order"]))
    mutations.append(changed)
    changed = deepcopy(GOVERNANCE)
    changed["authorization"]["live_authorized"] = True
    mutations.append(changed)
    for mutation in mutations:
        with pytest.raises(CapitalGovernanceError):
            validate_governance(mutation)


def test_cli_is_hashseed_and_timezone_deterministic(tmp_path):
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "America/New_York")):
        environment = os.environ.copy()
        environment.update(PYTHONHASHSEED=seed, TZ=timezone, PYTHONPATH=str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, str(CLI)], cwd=tmp_path, env=environment,
            capture_output=True, text=True, check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["governance_identity"] == GOVERNANCE["governance_identity"]


def test_v002_files_and_identities_remain_unchanged():
    protocol = json.loads((ROOT / "config/winner_archetype_protocol_v002.json").read_text())
    readiness = subprocess.run(
        [sys.executable, str(ROOT / "scripts/plan_winner_archetype_discovery_v002.py")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert protocol["schema_version"] == "aml.winner-archetype.protocol.v002"
    assert json.loads(readiness.stdout)["protocol_identity"] == (
        "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
    )
    assert json.loads(readiness.stdout)["readiness_identity"] == (
        "01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6"
    )


def test_no_broker_order_interface_is_callable_from_this_milestone():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/aml/lean_capital_governance.py", CLI)
    ).casefold()
    for prohibited in (
        "import requests", "import httpx", "import socket", "alpaca_trade_api",
        "submit_order", "place_order", "cancel_order", "brokerclient",
    ):
        assert prohibited not in sources
    import aml.lean_capital_governance as module

    assert not any("order" in name for name in dir(module) if callable(getattr(module, name)))
