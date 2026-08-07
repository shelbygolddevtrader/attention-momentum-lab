from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import shutil

import pytest

from aml.benchmark_candidate_first_half_hour_to_close_momentum_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY,
    EXECUTOR_REGISTRY,
    FROZEN_SPECIFICATION,
    NON_OPERATIVE_TARGET_SENTINEL,
    SPECIFICATION_IDENTITY,
    conformance_bars,
    conformance_inputs,
    evaluate_first_half_hour_to_close_momentum,
    evaluation_input,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
)
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json
from aml.first_half_hour_to_close_momentum_child_v001 import (
    CANDIDATE_SPECIFIC_LABELS,
    EVIDENCE_REQUIRED_ROLES,
    FirstHalfHourToCloseMilestoneError,
    build_evidence,
    default_config,
    required_inventory_contract_identity,
    validate_config,
    verify_evidence_directory,
    write_evidence,
)
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/first_half_hour_to_close_momentum_child_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
EVIDENCE = ROOT / "manifests/first_half_hour_to_close_momentum_child_v001"


def _config() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_prospective_child_identities_and_registration_reproduce() -> None:
    authority = FROZEN_SPECIFICATION["design_authority"]
    assert authority["classification"] == "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES"
    assert authority["outcome_access_before_freeze"] is False
    assert authority["optimization_count"] == 0
    assert authority["parameter_search_count"] == 0
    assert SPECIFICATION_IDENTITY == canonical_hash(
        {"domain": "aml.first-half-hour-to-close-momentum-specification.v001", "specification": FROZEN_SPECIFICATION}
    )
    assert CHILD_STRATEGY_IDENTITY == canonical_hash(
        {"domain": "aml.first-half-hour-to-close-momentum-strategy.v001", "specification_identity": SPECIFICATION_IDENTITY}
    )
    assert EXECUTOR_REGISTRY == {CHILD_HYPOTHESIS_ID: evaluate_first_half_hour_to_close_momentum}
    assert EXECUTOR_IDENTITY


@pytest.mark.parametrize(
    ("case", "status", "reason"),
    [
        ("positive", "proposal", None),
        ("threshold-absent", "no_signal", "first_half_hour_return_below_threshold"),
        ("missing-entry", "unavailable", "missing_next_bar"),
        ("duplicate-signal", "no_signal", "maximum_proposals_reached"),
    ],
)
def test_frozen_decision_paths(case: str, status: str, reason: str | None) -> None:
    result = evaluate_first_half_hour_to_close_momentum(conformance_inputs()[case])
    assert result.status == status
    assert (result.proposal is not None) is (status == "proposal")
    if reason is not None:
        assert result.reason_codes == (reason,)


def test_missing_open_is_an_integrity_failure() -> None:
    with pytest.raises(ExecutorIntegrityError, match="missing_segment_start"):
        evaluate_first_half_hour_to_close_momentum(conformance_inputs()["missing-open"])


def test_positive_proposal_uses_exact_clock_stop_and_close_exit_sentinel() -> None:
    result = evaluate_first_half_hour_to_close_momentum(conformance_inputs()["positive"])
    assert result.proposal is not None
    proposal = result.proposal
    assert proposal.intended_entry_timestamp.endswith("10:00:00-05:00")
    assert proposal.stop == 99.70
    assert proposal.target == NON_OPERATIVE_TARGET_SENTINEL
    assert proposal.timeout_complete_bars == 390


def test_wrong_symbol_and_wrong_clock_do_not_signal() -> None:
    bars = conformance_bars()
    wrong_symbol = tuple(replace(bar, symbol="QQQ") for bar in bars[:30])
    assert evaluate_first_half_hour_to_close_momentum(
        evaluation_input(wrong_symbol, next_bar=replace(bars[30], symbol="QQQ"))
    ).reason_codes == ("symbol_outside_frozen_universe",)
    shortened = bars[:29]
    assert evaluate_first_half_hour_to_close_momentum(
        evaluation_input(shortened, next_bar=bars[29])
    ).reason_codes == ("outside_exact_decision_timestamp",)


def test_malformed_and_gapped_bars_fail_closed() -> None:
    with pytest.raises(ExecutorIntegrityError):
        evaluate_first_half_hour_to_close_momentum(conformance_inputs()["integrity-failure"])
    bars = list(conformance_bars()[:30])
    bars[10] = replace(bars[10], timestamp=bars[10].timestamp + timedelta(minutes=1))
    with pytest.raises(ExecutorIntegrityError):
        evaluate_first_half_hour_to_close_momentum(
            evaluation_input(tuple(bars), next_bar=conformance_bars()[30])
        )


def test_no_lookahead_and_frozen_pipeline_conformance() -> None:
    assert no_lookahead_conformance()
    assert proposal_pipeline_conformance()


def test_config_is_exact_contaminated_and_all_spy_sessions() -> None:
    config = validate_config(_config(), ROOT)
    assert config == default_config(ROOT)
    binding = config["exploratory_dataset_binding"]
    assert binding["symbols"] == ["SPY"]
    assert binding["evaluation_session_rule"]["expected_count"] == 753
    assert config["policy"]["optimization_count"] == 0
    assert config["policy"]["empirical_execution_permitted"] is False
    assert config["required_inventory_contract_identity"] == required_inventory_contract_identity()


def test_evidence_rebuild_is_byte_identical_and_verifies(tmp_path: Path) -> None:
    config = _config()
    artifacts = build_evidence(repository_root=ROOT, config=config, library_path=LIBRARY)
    output = tmp_path / "evidence"
    manifest = write_evidence(output, artifacts)
    assert set(artifacts) == set(EVIDENCE_REQUIRED_ROLES)
    conformance = artifacts["07-conformance.json"]["payload"]
    assert conformance["stop_target_collision_precedence"] is True
    assert conformance["lifecycle_session_liquidation"] is True
    assert manifest == json.loads((EVIDENCE / "manifest.json").read_text())
    for name, artifact in artifacts.items():
        assert canonical_json(artifact) == (EVIDENCE / name).read_bytes()
    assert verify_evidence_directory(output, repository_root=ROOT, config=config)["verified"]


def test_evidence_inventory_is_closed_and_write_once(tmp_path: Path) -> None:
    target = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, target)
    (target / "09-extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FirstHalfHourToCloseMilestoneError, match="not closed"):
        verify_evidence_directory(target, repository_root=ROOT, config=_config())
    with pytest.raises(FirstHalfHourToCloseMilestoneError, match="already exists"):
        write_evidence(target, {})


def test_candidate_specific_non_evidence_label_is_frozen() -> None:
    assert CANDIDATE_SPECIFIC_LABELS == ("NOT EMPIRICAL EVIDENCE",)
