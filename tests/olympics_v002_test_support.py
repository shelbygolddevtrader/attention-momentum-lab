from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_input_manifest_v002 import (
    ADAPTER_CONTRACT_IDENTITY,
    EXECUTOR_REGISTRY_IDENTITY,
    ORDERING_VERSION,
    SCHEMA,
    SIMULATOR_REGISTRY_IDENTITY,
    SOURCE_COMMIT_IDENTITY,
    VERSION,
    V001_IMPLEMENTATION_IDENTITY,
    V001_ORCHESTRATOR_IDENTITY,
    entrant_identity,
    fraction_record,
    lifecycle_evidence_identity,
    manifest_identity,
    proposal_identity,
    trade_identity,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v002 import (
    adapter_implementation_identity,
)
from aml.professional_strategy_olympics_orchestrator_v001 import executor_bindings
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[1]


def _ns(day: int, minute: int) -> int:
    seconds = int(datetime(2024, 1, day, 15, minute, tzinfo=timezone.utc).timestamp())
    return seconds * 1_000_000_000


def make_trade(_namespace: str, day: int, *, direction: str = "long") -> dict[str, object]:
    proposal = _ns(day, 0)
    intended = _ns(day, 2)
    actual = intended
    exit_time = _ns(day, 3)
    quantity = 100 if direction == "long" else -100
    if direction == "long":
        raw_entry, adjusted_entry = 9_990_010, 10_000_000
        raw_exit, adjusted_exit = 12_532_533, 12_520_000
        stop, target = 7_500_000, 20_000_000
        gross = 252_000_000
    else:
        raw_entry, adjusted_entry = 10_010_010, 10_000_000
        raw_exit, adjusted_exit = 7_992_008, 8_000_000
        stop, target = 12_500_000, 5_000_000
        gross = 200_000_000
    net = gross - 2_000_000
    lifecycle: dict[str, object] = {
        "stop_reached": False,
        "target_reached": True,
        "timeout_reached": False,
        "invalidation_reached": False,
        "session_end_reached": False,
        "same_bar_stop_and_target": False,
        "evidence_identity": "0" * 64,
    }
    lifecycle["evidence_identity"] = lifecycle_evidence_identity(lifecycle)
    costs: dict[str, object] = {
        "entry_friction_basis_points": 10,
        "exit_friction_basis_points": 10,
        "entry_commission_microdollars": 1_000_000,
        "exit_commission_microdollars": 1_000_000,
        "other_costs_microdollars": 0,
        "borrow_cost_microdollars": 0,
        "price_impact_cost_microdollars": 0,
        "source_identity": "0" * 64,
    }
    costs["source_identity"] = canonical_hash({
        key: value for key, value in costs.items() if key != "source_identity"
    })
    trade: dict[str, object] = {
        "proposal_identity": "0" * 64,
        "proposal_timestamp_nanoseconds": proposal,
        "symbol": "SYN",
        "direction": direction,
        "confidence": fraction_record(Fraction(4, 5)),
        "intended_entry_timestamp_nanoseconds": intended,
        "actual_entry_timestamp_nanoseconds": actual,
        "entry_delay_nanoseconds": 0,
        "raw_entry_microdollars": raw_entry,
        "adjusted_entry_microdollars": adjusted_entry,
        "actual_quantity": quantity,
        "stop_microdollars": stop,
        "target_microdollars": target,
        "raw_exit_microdollars": raw_exit,
        "adjusted_exit_microdollars": adjusted_exit,
        "exit_timestamp_nanoseconds": exit_time,
        "exit_reason": "target",
        "lifecycle_evidence": lifecycle,
        "entry_commission_microdollars": 1_000_000,
        "exit_commission_microdollars": 1_000_000,
        "other_costs_microdollars": 0,
        "gross_pnl_microdollars": gross,
        "net_pnl_microdollars": net,
        "initial_risk_microdollars": 250_000_000,
        "net_R": fraction_record(Fraction(net, 250_000_000)),
        "elapsed_holding_nanoseconds": exit_time - actual,
        "capital_efficiency_numerator_microdollars": net,
        "capital_efficiency_denominator_microdollar_nanoseconds": (
            abs(quantity) * adjusted_entry * (exit_time - actual)
        ),
        "month_new_york": "2024-01",
        "regime_label": "prospective_synthetic_specification_regime",
        "validation_classification": "stage_unopened",
        "holdout_classification": "stage_unopened",
        "execution_classification": "completed_synthetic_trade",
        "sensitivity_classification": "canonical",
        "cost_stress_source": costs,
        "trade_identity": "0" * 64,
    }
    trade["proposal_identity"] = proposal_identity(trade)
    trade["trade_identity"] = trade_identity(trade)
    return trade


def make_manifest(*, with_trades: bool = True) -> dict[str, object]:
    entrants = []
    for index, binding in enumerate(executor_bindings(), start=1):
        trades = [make_trade(binding["strategy_id"], index)] if with_trades else []
        entrant: dict[str, object] = {
            "entrant_id": binding["strategy_id"],
            "strategy_identity": binding["strategy_identity"],
            "executor_identity": binding["executor_identity"],
            "simulator_identity": SIMULATOR_REGISTRY_IDENTITY,
            "lifecycle_identity": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
            "status": "active" if with_trades else "ineligible",
            "disqualification_reasons": [],
            "ineligibility_reasons": [] if with_trades else ["test_vector_zero_trades"],
            "integrity_failures": [],
            "active_dates": [f"2024-01-{index:02d}"] if with_trades else [],
            "validation_classification": "stage_unopened",
            "holdout_classification": "stage_unopened",
            "sensitivity_expectation_set": [],
            "trade_count": len(trades),
            "trades": trades,
            "entrant_identity": "0" * 64,
        }
        entrant["entrant_identity"] = entrant_identity(entrant)
        entrants.append(entrant)
    value: dict[str, object] = {
        "schema_name": SCHEMA,
        "schema_version": VERSION,
        "manifest_identity": "0" * 64,
        "synthetic_only": True,
        "fixture_identity": canonical_hash({
            "opened_stages": ["discovery"],
            "entrant_identities": [entrant["entrant_identity"] for entrant in entrants],
            "classification": "test_mathematical_specification_vector_not_trial_result",
        }),
        "opened_stages": ["discovery"],
        "v004_scoring_bundle_identity": BUNDLE_IDENTITY,
        "v001_orchestrator_contract_identity": V001_ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": adapter_implementation_identity(ROOT),
        "executor_registry_identity": EXECUTOR_REGISTRY_IDENTITY,
        "simulator_registry_identity": SIMULATOR_REGISTRY_IDENTITY,
        "lifecycle_identity": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
        "source_commit_identity": SOURCE_COMMIT_IDENTITY,
        "ordering_version": ORDERING_VERSION,
        "entrant_count": 10,
        "entrants": entrants,
        "access_prohibitions": {
            "historical": True, "live": True, "validation": True, "holdout": True,
            "extension": True, "forward": True, "provider": True, "broker": True,
            "network": True,
        },
        "classification": "test_mathematical_specification_vector_not_trial_result",
    }
    value["manifest_identity"] = manifest_identity(value)
    return value


def reidentify(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    for entrant in result["entrants"]:
        for trade in entrant["trades"]:
            trade["proposal_identity"] = proposal_identity(trade)
            evidence = trade["lifecycle_evidence"]
            evidence["evidence_identity"] = lifecycle_evidence_identity(evidence)
            costs = trade["cost_stress_source"]
            costs["source_identity"] = canonical_hash({
                key: atom for key, atom in costs.items() if key != "source_identity"
            })
            trade["trade_identity"] = trade_identity(trade)
        entrant["trade_count"] = len(entrant["trades"])
        entrant["entrant_identity"] = entrant_identity(entrant)
    result["fixture_identity"] = canonical_hash({
        "opened_stages": result["opened_stages"],
        "entrant_identities": [item["entrant_identity"] for item in result["entrants"]],
        "classification": result["classification"],
    })
    result["manifest_identity"] = manifest_identity(result)
    return result
