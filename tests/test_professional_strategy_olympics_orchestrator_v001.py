from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_final_scoring_v004 import EVENT_IDS
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ARTIFACT_NAMES,
    ORCHESTRATOR_IDENTITY,
    OlympicsOrchestratorV001Error,
    V004_BUNDLE_IDENTITY,
    compute_raw_events,
    cost_stress_expectancies,
    executor_bindings,
    fraction_record,
    implementation_identity,
    load_orchestrator_contract,
    publish_artifacts,
    rank_events,
    validate_authorization,
    validate_input_manifest,
    validate_only,
    validate_specification_vectors,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[1]


def fraction(value: Fraction | int) -> dict[str, int]:
    item = Fraction(value)
    return {"numerator": item.numerator, "denominator": item.denominator}


def timestamp(year: int, month: int, day: int, minute: int) -> int:
    return int(
        datetime(year, month, day, 15, minute, tzinfo=timezone.utc).timestamp()
        * 1_000_000_000
    )


def trades(
    count: int = 40, *, return_scale: int = 1, namespace: str = "default"
) -> list[dict[str, object]]:
    result = []
    for index in range(count):
        month = index // 10 + 1
        entry = timestamp(2024, month, index % 10 + 1, 0)
        positive = index % 2 == 0 or (return_scale == 2 and index % 4 == 1)
        net_r = Fraction(1) if positive else Fraction(-1, 2)
        net_pnl = net_r * 250_000_000
        raw_exit = 12_532_533 if positive else 8_778_779
        result.append({
            "proposal_identity": canonical_hash({"namespace": namespace, "proposal": index}),
            "symbol": "SYN",
            "entry_nanoseconds": entry,
            "exit_nanoseconds": entry + 60_000_000_000,
            "quantity": 100,
            "raw_entry_microdollars": 9_990_010,
            "raw_exit_microdollars": raw_exit,
            "entry_price_microdollars": 10_000_000,
            "target_microdollars": 20_000_000,
            "entry_commission_microdollars": 1_000_000,
            "exit_commission_microdollars": 1_000_000,
            "risk_budget_microdollars": 250_000_000,
            "net_pnl_microdollars": net_pnl.numerator,
            "net_R": fraction(net_r),
            "exit_month_new_york": f"2024-{month:02d}",
            "regime_label": "pre_outcome_low" if index < count / 2 else "pre_outcome_high",
        })
    return result


def entrant(binding: dict[str, str], *, trade_count: int = 40) -> dict[str, object]:
    return {
        **binding,
        "disqualified": False,
        "disqualification_reasons": [],
        "active_dates": [f"2024-01-{day:02d}" for day in range(1, 11)],
        "trades": trades(trade_count, namespace=binding["strategy_id"]),
        "sensitivity_variant_expectancies": [],
    }


def manifest() -> dict[str, object]:
    entrants = [entrant(binding) for binding in executor_bindings()]
    value: dict[str, object] = {
        "schema_version": "aml.professional-strategy-olympics.synthetic-input-manifest.v001",
        "manifest_identity": "0" * 64,
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "synthetic": True,
        "fixture_identity": canonical_hash({
            "opened_stages": ["discovery"], "entrants": entrants,
        }),
        "opened_stages": ["discovery"],
        "entrants": entrants,
    }
    value["manifest_identity"] = canonical_hash({
        key: item for key, item in value.items() if key != "manifest_identity"
    })
    return value


def event_contracts() -> list[dict[str, object]]:
    return load_orchestrator_contract(ROOT) and json.loads(
        (ROOT / "config/professional_strategy_olympics_final_scoring_v004.json").read_text()
    )["raw_event_registry"]["events"]


def test_contract_identity_and_authorization_remain_frozen_closed() -> None:
    contract = load_orchestrator_contract(ROOT)
    assert contract["orchestrator_identity"] == ORCHESTRATOR_IDENTITY
    assert not any(contract["authorization"].values())
    assert contract["readiness"]["trial_authorized"] is False
    assert contract["readiness"]["synthetic_trial_executed"] is False


def test_all_nineteen_v004_vectors_are_identity_bound_non_results() -> None:
    vectors = validate_specification_vectors(ROOT)
    assert len(vectors) == 19
    assert len({item["id"] for item in vectors}) == 19
    assert all(item["classification"].endswith("not_trial_result") for item in vectors)
    assert all(len(item["vector_identity"]) == 64 for item in vectors)


def test_validation_only_is_byte_identical_and_executes_nothing() -> None:
    first = validate_only(ROOT, manifest())
    second = validate_only(ROOT, manifest())
    assert first == second
    report = json.loads(first)
    assert report["status"] == "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
    assert report["trial_executed"] is False
    assert report["performance_result"] is False
    assert report["entrant_count"] == 10


def test_manifest_binds_all_ten_strategy_and_executor_identities() -> None:
    value = validate_input_manifest(manifest())
    assert len(value["entrants"]) == 10
    assert [item["strategy_identity"] for item in value["entrants"]] == [
        item["strategy_identity"] for item in executor_bindings()
    ]


@pytest.mark.parametrize("mutation", ["scoring", "order", "fraction", "month", "duplicate"])
def test_manifest_integrity_failures_never_silently_default(mutation: str) -> None:
    value = manifest()
    if mutation == "scoring":
        value["scoring_bundle_identity"] = "f" * 64
    elif mutation == "order":
        value["entrants"][0], value["entrants"][1] = value["entrants"][1], value["entrants"][0]
    elif mutation == "fraction":
        value["entrants"][0]["trades"][0]["net_R"] = {"numerator": 2, "denominator": 2}
    elif mutation == "month":
        value["entrants"][0]["trades"][0]["exit_month_new_york"] = "2099-01"
    else:
        value["entrants"][1]["trades"][0]["proposal_identity"] = (
            value["entrants"][0]["trades"][0]["proposal_identity"]
        )
    value["fixture_identity"] = canonical_hash({
        "opened_stages": value["opened_stages"], "entrants": value["entrants"],
    })
    value["manifest_identity"] = canonical_hash({
        key: item for key, item in value.items() if key != "manifest_identity"
    })
    with pytest.raises(OlympicsOrchestratorV001Error):
        validate_input_manifest(value)


def test_all_fifteen_raw_events_have_exact_expected_status_and_core_values() -> None:
    values = {item.event_id: item for item in compute_raw_events(entrant(executor_bindings()[0]))}
    assert tuple(values) == EVENT_IDS
    assert values["net_expectancy"].raw == Fraction(1, 4)
    assert values["downside_adjusted_return"].raw == (Fraction(1, 4), Fraction(1, 8))
    assert values["maximum_drawdown"].raw == Fraction(1, 2)
    assert values["profit_factor"].raw == Fraction(2)
    assert values["payoff_ratio"].raw == Fraction(2)
    assert values["hit_rate"].raw == Fraction(1, 2)
    assert values["tail_loss"].raw == Fraction(1, 2)
    assert values["monthly_stability"].raw == Fraction(1, 4)
    assert values["regime_stability"].raw == Fraction(1, 4)
    assert values["validation_consistency"].reason == "validation_stage_unopened"
    assert values["holdout_consistency"].reason == "holdout_stage_unopened"
    assert values["capital_efficiency"].eligible
    assert values["trade_sufficiency"].raw == Fraction(40)
    assert values["execution_robustness"].raw == cost_stress_expectancies(
        entrant(executor_bindings()[0])["trades"]
    )[-1]
    assert values["sensitivity_robustness"].raw == Fraction(1, 4)


def test_cost_stress_uses_fixed_atoms_and_fails_infeasible_entry_closed() -> None:
    values = trades()
    expectancies = cost_stress_expectancies(values)
    assert expectancies is not None
    assert expectancies[0] == Fraction(1, 4)
    assert expectancies[0] > expectancies[1] > expectancies[2]
    values[0]["target_microdollars"] = 9_999_000
    assert cost_stress_expectancies(values) is None


def test_zero_trade_is_ineligibility_while_disqualification_is_distinct() -> None:
    empty = entrant(executor_bindings()[0], trade_count=0)
    empty["active_dates"] = []
    events = compute_raw_events(empty)
    assert all(not event.eligible for event in events)
    assert {event.reason for event in events} != {"strategy_disqualified"}
    empty["disqualified"] = True
    empty["disqualification_reasons"] = ["nondeterministic_executor_output"]
    assert {event.reason for event in compute_raw_events(empty)} == {"strategy_disqualified"}


def test_event_scores_use_exact_v003_percentiles_and_identity_ties() -> None:
    bindings = executor_bindings()
    left = entrant(bindings[0])
    right = entrant(bindings[1])
    right["trades"] = trades(40, return_scale=2, namespace=right["strategy_id"])
    values = {
        left["strategy_identity"]: compute_raw_events(left),
        right["strategy_identity"]: compute_raw_events(right),
    }
    scores = rank_events(values, event_contracts())
    expectancy = [record for record in scores if record["event_id"] == "net_expectancy"]
    by_identity = {record["strategy_identity"]: record for record in expectancy}
    assert by_identity[left["strategy_identity"]]["ordinal_rank"] == 1
    assert by_identity[left["strategy_identity"]]["event_score"] == fraction_record(Fraction())
    assert by_identity[right["strategy_identity"]]["ordinal_rank"] == 2
    assert by_identity[right["strategy_identity"]]["event_score"] == fraction_record(Fraction(100))
    validation = [record for record in scores if record["event_id"] == "validation_consistency"]
    assert all(record["event_score"] == fraction_record(Fraction()) for record in validation)
    reversed_values = dict(reversed(tuple(values.items())))
    assert rank_events(reversed_values, event_contracts()) == scores


def test_trial_execution_requires_both_gate_and_bound_artifact() -> None:
    input_identity = manifest()["manifest_identity"]
    with pytest.raises(OlympicsOrchestratorV001Error, match="execute flag"):
        validate_authorization(
            None, execute_requested=False, input_identity=input_identity,
            implementation=implementation_identity(ROOT),
        )
    with pytest.raises(OlympicsOrchestratorV001Error, match="artifact"):
        validate_authorization(
            None, execute_requested=True, input_identity=input_identity,
            implementation=implementation_identity(ROOT),
        )


def test_artifact_publication_is_write_once_and_collision_safe(tmp_path: Path) -> None:
    run_identity = canonical_hash({"run": "publication-specification-test"})
    artifacts = {name: f"{name}\n".encode() for name in ARTIFACT_NAMES}
    destination = publish_artifacts(tmp_path, run_identity, artifacts)
    assert publish_artifacts(tmp_path, run_identity, artifacts) == destination
    changed = dict(artifacts)
    changed["run_manifest.json"] = b"changed\n"
    with pytest.raises(OlympicsOrchestratorV001Error, match="collision"):
        publish_artifacts(tmp_path, run_identity, changed)


def test_cli_preflight_is_deterministic_across_hash_seed_and_timezone() -> None:
    script = ROOT / "scripts/run_professional_strategy_olympics_orchestrator_v001.py"
    outputs = []
    for seed, tz in (("1", "UTC"), ("987", "Pacific/Honolulu")):
        environment = os.environ.copy()
        environment.update({"PYTHONHASHSEED": seed, "TZ": tz, "PYTHONPATH": str(ROOT / "src")})
        outputs.append(subprocess.run(
            [sys.executable, str(script), "--repository-root", str(ROOT)],
            check=True, capture_output=True, env=environment,
        ).stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["trial_executed"] is False


def test_module_has_no_network_broker_forward_or_holdout_imports() -> None:
    source = (ROOT / "src/aml/professional_strategy_olympics_orchestrator_v001.py").read_text()
    import_lines = "\n".join(
        line for line in source.splitlines() if line.startswith(("import ", "from "))
    )
    prohibited = ("requests", "httpx", "urllib", "socket", "alpaca", "broker", "forward_validation", "holdout")
    assert all(item not in import_lines for item in prohibited)
