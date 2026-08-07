from __future__ import annotations

from copy import deepcopy

import pytest

from aml.contaminated_economic_poc_v001 import (
    FROZEN_POC_CONTRACT,
    LABELS,
    frozen_poc_contract,
    poc_contract_identity,
    validate_poc_contract,
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
