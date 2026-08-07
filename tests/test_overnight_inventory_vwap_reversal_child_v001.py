from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import shutil

import pytest

from aml.benchmark_candidate_overnight_inventory_vwap_reversal_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY,
    EXECUTOR_REGISTRY,
    FROZEN_SPECIFICATION,
    SPECIFICATION_IDENTITY,
    conformance_bars,
    conformance_inputs,
    evaluate_overnight_inventory_vwap_reversal,
    evaluation_input,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
)
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json
from aml.overnight_inventory_vwap_reversal_child_v001 import (
    CANDIDATE_SPECIFIC_LABELS,
    EVIDENCE_REQUIRED_ROLES,
    MINIMUM_ECONOMIC_POC_COMPLETED_TRADES,
    OvernightInventoryVwapReversalMilestoneError,
    build_evidence,
    candidate_economic_poc_contract,
    candidate_economic_poc_contract_identity,
    default_config,
    required_inventory_contract_identity,
    validate_config,
    verify_evidence_directory,
    write_evidence,
)
from aml.professional_strategy_executor_models_v001 import PriorClose
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/overnight_inventory_vwap_reversal_child_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
EVIDENCE = ROOT / "manifests/overnight_inventory_vwap_reversal_child_v001"


def _config() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_prospective_child_identities_and_registration_reproduce() -> None:
    authority = FROZEN_SPECIFICATION["design_authority"]
    assert authority["classification"] == "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES"
    assert authority["outcome_access_before_freeze"] is False
    assert authority["optimization_count"] == 0
    assert authority["parameter_search_count"] == 0
    assert SPECIFICATION_IDENTITY == canonical_hash(
        {
            "domain": "aml.overnight-inventory-vwap-reversal-specification.v001",
            "specification": FROZEN_SPECIFICATION,
        }
    )
    assert CHILD_STRATEGY_IDENTITY == canonical_hash(
        {
            "domain": "aml.overnight-inventory-vwap-reversal-strategy.v001",
            "specification_identity": SPECIFICATION_IDENTITY,
        }
    )
    assert EXECUTOR_REGISTRY == {
        CHILD_HYPOTHESIS_ID: evaluate_overnight_inventory_vwap_reversal
    }
    assert EXECUTOR_IDENTITY


@pytest.mark.parametrize(
    ("case", "status", "reason"),
    [
        ("positive", "proposal", None),
        ("gap-threshold-absent", "no_signal", "gap_down_threshold_absent"),
        ("reversal-absent", "no_signal", "adjacent_upside_reversal_absent"),
        ("vwap-unavailable", "unavailable", "regular_vwap_unavailable"),
        ("prior-close-missing", "unavailable", "prior_close_missing"),
        ("missing-entry", "unavailable", "missing_next_bar"),
        ("duplicate-signal", "no_signal", "maximum_proposals_reached"),
    ],
)
def test_frozen_decision_paths(case: str, status: str, reason: str | None) -> None:
    result = evaluate_overnight_inventory_vwap_reversal(conformance_inputs()[case])
    assert result.status == status
    assert (result.proposal is not None) is (status == "proposal")
    if reason is not None:
        assert result.reason_codes == (reason,)


def test_positive_proposal_uses_exact_vwap_stop_and_timeout() -> None:
    result = evaluate_overnight_inventory_vwap_reversal(
        conformance_inputs()["positive"]
    )
    assert result.proposal is not None
    proposal = result.proposal
    assert proposal.intended_entry_timestamp.endswith("09:45:00-05:00")
    assert proposal.stop == 98.50
    assert proposal.target == 99.71
    assert proposal.timeout_complete_bars == 120


def test_wrong_symbol_wrong_clock_and_missing_open_fail_closed() -> None:
    bars = conformance_bars()
    wrong_symbol = tuple(replace(bar, symbol="AAPL") for bar in bars[:15])
    result = evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(wrong_symbol, next_bar=replace(bars[15], symbol="AAPL"))
    )
    assert result.reason_codes == ("symbol_outside_frozen_universe",)
    shortened = bars[:14]
    assert evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(shortened, next_bar=bars[14])
    ).reason_codes == ("outside_exact_decision_timestamp",)
    with pytest.raises(ExecutorIntegrityError, match="missing_segment_start"):
        evaluate_overnight_inventory_vwap_reversal(
            evaluation_input(bars[1:15], next_bar=bars[15])
        )


def test_stale_or_invalid_prior_close_fails_closed() -> None:
    bars = conformance_bars()
    stale = PriorClose(
        date(2025, 12, 1), 100.5, 100.5, "adjustment", "source"
    )
    result = evaluate_overnight_inventory_vwap_reversal(
        evaluation_input(bars[:15], next_bar=bars[15], prior_close=stale)
    )
    assert result.status == "unavailable"
    assert result.reason_codes == ("prior_close_stale",)
    invalid = PriorClose(date(2026, 1, 5), 100.5, 0.0, "", "source")
    with pytest.raises(ExecutorIntegrityError, match="prior_close:invalid"):
        evaluate_overnight_inventory_vwap_reversal(
            evaluation_input(bars[:15], next_bar=bars[15], prior_close=invalid)
        )


def test_malformed_and_gapped_bars_fail_closed() -> None:
    with pytest.raises(ExecutorIntegrityError):
        evaluate_overnight_inventory_vwap_reversal(
            conformance_inputs()["integrity-failure"]
        )
    bars = list(conformance_bars()[:15])
    bars[10] = replace(bars[10], timestamp=bars[10].timestamp + timedelta(minutes=1))
    with pytest.raises(ExecutorIntegrityError):
        evaluate_overnight_inventory_vwap_reversal(
            evaluation_input(tuple(bars), next_bar=conformance_bars()[15])
        )


def test_no_lookahead_and_frozen_pipeline_conformance() -> None:
    assert no_lookahead_conformance()
    assert proposal_pipeline_conformance()


def test_config_is_exact_contaminated_and_fixed_liquid_etf_universe() -> None:
    config = validate_config(_config(), ROOT)
    assert config == default_config(ROOT)
    binding = config["exploratory_dataset_binding"]
    assert binding["symbols"] == ["DIA", "IWM", "QQQ", "SPY"]
    assert binding["evaluation_session_rule"]["expected_count_per_symbol"] == 752
    assert config["policy"]["optimization_count"] == 0
    assert config["policy"]["empirical_execution_permitted"] is False
    assert config["required_inventory_contract_identity"] == (
        required_inventory_contract_identity()
    )


def test_evidence_rebuild_is_byte_identical_and_verifies(tmp_path: Path) -> None:
    config = _config()
    artifacts = build_evidence(
        repository_root=ROOT, config=config, library_path=LIBRARY
    )
    output = tmp_path / "evidence"
    manifest = write_evidence(output, artifacts)
    assert set(artifacts) == set(EVIDENCE_REQUIRED_ROLES)
    conformance = artifacts["07-conformance.json"]["payload"]
    assert conformance["stop_target_collision_precedence"] is True
    assert conformance["lifecycle_completion"] is True
    assert manifest == json.loads((EVIDENCE / "manifest.json").read_text())
    for name, artifact in artifacts.items():
        assert canonical_json(artifact) == (EVIDENCE / name).read_bytes()
    assert verify_evidence_directory(
        output, repository_root=ROOT, config=config
    )["verified"]


def test_evidence_inventory_is_closed_and_write_once(tmp_path: Path) -> None:
    target = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, target)
    (target / "09-extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OvernightInventoryVwapReversalMilestoneError, match="not closed"):
        verify_evidence_directory(target, repository_root=ROOT, config=_config())
    with pytest.raises(OvernightInventoryVwapReversalMilestoneError, match="already exists"):
        write_evidence(target, {})


def test_candidate_economic_contract_is_frozen_and_requires_thirty() -> None:
    config = _config()
    evidence_identity = json.loads((EVIDENCE / "manifest.json").read_text())["identity"]
    contract = candidate_economic_poc_contract(config, evidence_identity)
    assert contract["minimum_completed_trades"] == 30
    assert MINIMUM_ECONOMIC_POC_COMPLETED_TRADES == 30
    assert candidate_economic_poc_contract_identity(config, evidence_identity) == (
        canonical_hash(contract)
    )


def test_candidate_specific_non_evidence_label_is_frozen() -> None:
    assert CANDIDATE_SPECIFIC_LABELS == ("NOT EMPIRICAL EVIDENCE",)
