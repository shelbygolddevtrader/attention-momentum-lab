from __future__ import annotations

from copy import deepcopy

import pytest

from aml.contaminated_economic_poc_v001 import (
    FROZEN_POC_CONTRACT,
    LABELS,
    _required_inventory_paths,
    exploratory_interpretation,
    frozen_poc_contract,
    poc_contract_identity,
    summarize_trade_records,
    validate_poc_contract,
    verify_frozen_mechanism_identities,
)


def test_prospective_contract_is_exact_and_content_addressed() -> None:
    assert validate_poc_contract(FROZEN_POC_CONTRACT) == FROZEN_POC_CONTRACT
    assert frozen_poc_contract() == FROZEN_POC_CONTRACT
    assert len(poc_contract_identity()) == 64
    assert FROZEN_POC_CONTRACT["frozen_before_economic_outcome_access"] is True
    assert tuple(FROZEN_POC_CONTRACT["labels"]) == LABELS


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["inclusion_policy"]["mechanisms"].pop(),
        lambda value: value["dataset"]["symbols"].pop(),
        lambda value: value["dataset"]["evaluation_sessions"].pop(),
        lambda value: value["costs"]["scenarios"][0].update(
            {"friction_basis_points_per_side": "9"}
        ),
        lambda value: value["interpretation"].update(
            {"minimum_completed_trades": 29}
        ),
        lambda value: value["labels"].pop(),
    ],
)
def test_contract_mutation_fails_closed(mutation) -> None:
    changed = deepcopy(FROZEN_POC_CONTRACT)
    mutation(changed)
    with pytest.raises(ValueError, match="contract changed"):
        validate_poc_contract(changed)


def test_contract_contains_no_outcome_or_mechanism_selection() -> None:
    assert len(FROZEN_POC_CONTRACT["inclusion_policy"]["mechanisms"]) == 5
    assert FROZEN_POC_CONTRACT["prohibited_actions"] == [
        "strategy_or_threshold_change",
        "optimization",
        "parameter_search",
        "outcome_based_subset_selection",
        "post_result_exclusion",
        "validation_access",
        "holdout_access",
        "forward_testing",
        "paper_trading",
        "live_trading",
        "broker_interaction",
        "olympics_execution",
        "capital_allocation",
    ]


def _record(
    *,
    proposal: str,
    symbol: str,
    net: str,
    gross: str,
    net_r: str,
    exit_reason: str,
) -> dict[str, object]:
    scenarios = {}
    for name, extra_cost in (("base", "0"), ("cost_1_5x", "20"), ("cost_2x", "40")):
        scenario_net = float(net) - float(extra_cost)
        scenarios[name] = {
            "gross_pnl": gross,
            "modeled_transaction_costs": str(float(gross) - scenario_net),
            "net_pnl": str(scenario_net),
            "gross_r": str(float(gross) / 100),
            "net_r": str(scenario_net / 100),
        }
    return {
        "candidate_id": "synthetic-candidate",
        "proposal_identity": proposal,
        "symbol": symbol,
        "exit_timestamp": f"2025-01-02T10:0{proposal[-1]}:00-05:00",
        "exit_reason": exit_reason,
        "scenarios": scenarios,
    }


def test_frozen_mechanism_identities_and_closed_inventory_reproduce() -> None:
    verify_frozen_mechanism_identities()
    paths = _required_inventory_paths()
    assert paths == sorted(paths)
    assert len(paths) == 14
    assert len(paths) == len(set(paths))
    assert "contract.json" in paths
    assert "report.md" in paths
    assert sum(path.startswith("results/") for path in paths) == 5
    assert sum(path.startswith("trades/") for path in paths) == 5


def test_metric_calculation_reconciles_and_uses_frozen_ordering() -> None:
    records = [
        _record(
            proposal="p1",
            symbol="AAA",
            net="100",
            gross="110",
            net_r="1",
            exit_reason="intrabar_target",
        ),
        _record(
            proposal="p2",
            symbol="BBB",
            net="-50",
            gross="-40",
            net_r="-0.5",
            exit_reason="intrabar_stop",
        ),
        _record(
            proposal="p3",
            symbol="CCC",
            net="0",
            gross="10",
            net_r="0",
            exit_reason="timeout",
        ),
    ]
    metrics = summarize_trade_records(
        list(reversed(records)),
        "base",
        proposal_count=5,
        rejected_proposal_count=2,
    )
    assert metrics["completed_trade_count"] == 3
    assert metrics["winner_count"] == 1
    assert metrics["loser_count"] == 1
    assert metrics["flat_trade_count"] == 1
    assert metrics["gross_pnl"] == "80.00"
    assert metrics["modeled_transaction_costs"] == "30.00"
    assert metrics["net_pnl"] == "50.00"
    assert metrics["profit_factor"] == "2.000000"
    assert metrics["total_r"] == "0.500000"
    assert metrics["median_r"] == "0.000000"
    assert metrics["maximum_drawdown"] == "50.00"
    assert metrics["longest_losing_streak"] == 1
    assert metrics["r_distribution"] == {
        "r_le_minus_1": 0,
        "minus_1_lt_r_lt_0": 1,
        "r_eq_0": 1,
        "0_lt_r_lt_1": 0,
        "1_le_r_lt_2": 1,
        "r_ge_2": 0,
    }


def test_interpretation_thresholds_are_coarse_and_prospective() -> None:
    records = [
        _record(
            proposal=f"p{index % 10}",
            symbol="AAA",
            net="-10",
            gross="0",
            net_r="-0.1",
            exit_reason="intrabar_stop",
        )
        for index in range(30)
    ]
    scenarios = {
        name: summarize_trade_records(
            records,
            name,
            proposal_count=30,
            rejected_proposal_count=0,
        )
        for name in ("base", "cost_1_5x", "cost_2x")
    }
    assert exploratory_interpretation(scenarios) == (
        "EXPLORATORY_ECONOMICALLY_UNATTRACTIVE"
    )
    too_few = {name: dict(value) for name, value in scenarios.items()}
    for value in too_few.values():
        value["completed_trade_count"] = 29
    assert exploratory_interpretation(too_few) == "EXPLORATORY_TOO_FEW_TRADES"
