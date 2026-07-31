from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from aml.professional_strategy_olympics_orchestrator_input_adapter_v002 import (
    OlympicsOrchestratorInputAdapterV002Error,
    adapt_manifest,
    adapter_implementation_identity,
    future_run_identity,
    validation_only,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    cost_stress_expectancies,
    validate_input_manifest,
)
from aml.professional_strategy_olympics_input_manifest_v002 import derive_cost_stress

from olympics_v002_test_support import ROOT, make_manifest, reidentify


def test_adapter_accepts_v002_and_produces_exact_v001_internal_structure() -> None:
    value = make_manifest()
    adapted = adapt_manifest(value, ROOT)
    validated = validate_input_manifest(adapted.v001_manifest)
    source = value["entrants"][0]["trades"][0]
    projected = validated["entrants"][0]["trades"][0]
    assert projected == {
        "proposal_identity": source["proposal_identity"],
        "symbol": source["symbol"],
        "entry_nanoseconds": source["actual_entry_timestamp_nanoseconds"],
        "exit_nanoseconds": source["exit_timestamp_nanoseconds"],
        "quantity": source["actual_quantity"],
        "raw_entry_microdollars": source["raw_entry_microdollars"],
        "raw_exit_microdollars": source["raw_exit_microdollars"],
        "entry_price_microdollars": source["adjusted_entry_microdollars"],
        "target_microdollars": source["target_microdollars"],
        "entry_commission_microdollars": source["entry_commission_microdollars"],
        "exit_commission_microdollars": source["exit_commission_microdollars"],
        "risk_budget_microdollars": source["initial_risk_microdollars"],
        "net_pnl_microdollars": source["net_pnl_microdollars"],
        "net_R": source["net_R"],
        "exit_month_new_york": source["month_new_york"],
        "regime_label": source["regime_label"],
    }
    assert adapted.status_ledger[0]["status"] == "active"


def test_adapter_rejects_v001_input_in_v002_mode() -> None:
    with pytest.raises(OlympicsOrchestratorInputAdapterV002Error, match="rejects non-V002"):
        adapt_manifest({"schema_name": "aml.professional-strategy-olympics.synthetic-input-manifest.v001"}, ROOT)


def test_v002_cost_stress_is_exactly_the_frozen_v001_long_trade_semantics() -> None:
    value = make_manifest()
    adapted = adapt_manifest(value, ROOT)
    source = value["entrants"][0]["trades"][0]
    expected = cost_stress_expectancies(adapted.v001_manifest["entrants"][0]["trades"])
    scenarios = derive_cost_stress(source)
    assert expected == (
        scenarios["base_1x"], scenarios["stress_1_5x"], scenarios["stress_2x"]
    )


def test_adapter_does_not_regenerate_or_repair_trade_atoms() -> None:
    value = make_manifest()
    value["entrants"][0]["trades"][0]["net_pnl_microdollars"] += 1
    with pytest.raises(ValueError, match="net P&L"):
        adapt_manifest(reidentify(value), ROOT)


def test_validation_only_returns_exact_status_and_no_results_or_authorization(tmp_path: Path) -> None:
    before = tuple(tmp_path.iterdir())
    first = validation_only(make_manifest(), ROOT)
    second = validation_only(make_manifest(), ROOT)
    assert first == second
    report = json.loads(first)
    assert report["status"] == "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
    assert report["trial_authorized"] is False
    assert report["trial_executed"] is False
    assert report["artifact_published"] is False
    assert report["ranking_exists"] is False
    assert report["aggregate_score_exists"] is False
    assert report["performance_result_exists"] is False
    assert tuple(tmp_path.iterdir()) == before


def test_future_run_identity_binds_every_required_identity() -> None:
    value = make_manifest()
    identity = future_run_identity(value, ROOT)
    assert len(identity) == 64
    changed = deepcopy(value)
    changed["source_commit_identity"] = "f" * 40
    changed = reidentify(changed)
    assert future_run_identity(changed, ROOT) != identity
    changed = deepcopy(value)
    changed["manifest_identity"] = "f" * 64
    with pytest.raises(ValueError, match="manifest identity"):
        future_run_identity(changed, ROOT)


def test_adapter_cannot_project_short_or_unrepresented_other_costs() -> None:
    value = make_manifest()
    trade = value["entrants"][0]["trades"][0]
    trade["other_costs_microdollars"] = 1
    trade["net_pnl_microdollars"] -= 1
    trade["capital_efficiency_numerator_microdollars"] -= 1
    trade["net_R"] = {
        "numerator": trade["net_pnl_microdollars"], "denominator": 250_000_000,
    }
    with pytest.raises(ValueError):
        adapt_manifest(reidentify(value), ROOT)


def test_failure_distinctions_survive_in_adapter_status_ledger() -> None:
    value = make_manifest(with_trades=False)
    value["entrants"][0]["status"] = "integrity_failure"
    value["entrants"][0]["ineligibility_reasons"] = []
    value["entrants"][0]["integrity_failures"] = ["deterministic_test_integrity_failure"]
    adapted = adapt_manifest(reidentify(value), ROOT)
    assert adapted.status_ledger[0] == {
        "entrant_id": value["entrants"][0]["entrant_id"],
        "entrant_identity": reidentify(value)["entrants"][0]["entrant_identity"],
        "status": "integrity_failure",
        "disqualification_reasons": [],
        "ineligibility_reasons": [],
        "integrity_failures": ["deterministic_test_integrity_failure"],
    }
    assert adapted.v001_manifest["entrants"][0]["disqualified"] is True


def test_adapter_identity_is_deterministic_and_content_bound() -> None:
    first = adapter_implementation_identity(ROOT)
    second = adapter_implementation_identity(ROOT)
    assert first == second
    assert len(first) == 64


def test_adapter_surface_exposes_no_execute_authorize_or_publish_callable() -> None:
    import aml.professional_strategy_olympics_orchestrator_input_adapter_v002 as module

    names = set(dir(module))
    assert not ({"execute", "authorize", "publish", "run_trial"} & names)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "import broker" not in source.lower()
