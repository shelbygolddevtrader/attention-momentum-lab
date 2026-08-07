from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import shutil

import pytest

from aml.benchmark_candidate_volatility_expansion_breakout_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY,
    EXECUTOR_REGISTRY,
    FROZEN_SPECIFICATION,
    SPECIFICATION_IDENTITY,
    conformance_bars,
    conformance_inputs,
    evaluate_volatility_expansion_breakout,
    evaluation_input,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
)
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError
from aml.volatility_expansion_breakout_child_v001 import (
    CANDIDATE_SPECIFIC_LABELS,
    EVIDENCE_REQUIRED_ROLES,
    VolatilityExpansionMilestoneError,
    build_evidence,
    default_config,
    required_inventory_contract_identity,
    validate_config,
    verify_evidence_directory,
    write_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/volatility_expansion_breakout_child_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
EVIDENCE = ROOT / "manifests/volatility_expansion_breakout_child_v001"


def _config() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_prospective_child_identities_and_registration_reproduce() -> None:
    assert FROZEN_SPECIFICATION["design_authority"] == {
        "classification": "PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES",
        "parent_is_exact_specification": False,
        "outcome_access_before_freeze": False,
        "optimization_count": 0,
        "parameter_search_count": 0,
    }
    assert SPECIFICATION_IDENTITY == canonical_hash(
        {
            "domain": "aml.volatility-expansion-breakout-specification.v001",
            "specification": FROZEN_SPECIFICATION,
        }
    )
    assert CHILD_STRATEGY_IDENTITY == canonical_hash(
        {
            "domain": "aml.volatility-expansion-breakout-strategy.v001",
            "specification_identity": SPECIFICATION_IDENTITY,
        }
    )
    assert EXECUTOR_IDENTITY
    assert EXECUTOR_REGISTRY == {
        CHILD_HYPOTHESIS_ID: evaluate_volatility_expansion_breakout
    }


@pytest.mark.parametrize(
    ("case", "status", "reason"),
    [
        ("positive", "proposal", None),
        ("expansion-absent", "no_signal", "expansion_ratio_below_threshold"),
        ("breakout-absent", "no_signal", "expansion_close_not_above_breakout"),
        ("volume-absent", "no_signal", "same_clock_volume_below_threshold"),
        ("volume-unavailable", "unavailable", "same_clock_volume_warmup_incomplete"),
        ("warmup-unavailable", "unavailable", "atr20_warmup_incomplete"),
        ("duplicate-signal", "no_signal", "maximum_proposals_reached"),
    ],
)
def test_frozen_decision_paths(case: str, status: str, reason: str | None) -> None:
    result = evaluate_volatility_expansion_breakout(conformance_inputs()[case])
    assert result.status == status
    assert (result.proposal is not None) is (status == "proposal")
    if reason is not None:
        assert result.reason_codes == (reason,)


def test_positive_proposal_uses_next_bar_entry_structure_stop_and_two_r() -> None:
    result = evaluate_volatility_expansion_breakout(conformance_inputs()["positive"])
    assert result.proposal is not None
    proposal = result.proposal
    assert proposal.intended_entry_timestamp.endswith("09:52:00-05:00")
    assert proposal.stop == 99.80
    assert proposal.target > proposal.cost_adjusted_entry
    assert proposal.target == pytest.approx(
        proposal.cost_adjusted_entry
        + 2.0 * (proposal.cost_adjusted_entry - proposal.stop),
        abs=0.01,
    )


def test_missing_next_bar_fails_closed() -> None:
    bars = conformance_bars()
    result = evaluate_volatility_expansion_breakout(
        evaluation_input(bars[:22], next_bar=None)
    )
    assert result.status == "unavailable"


def test_malformed_and_gapped_bars_raise_integrity_failure() -> None:
    bars = list(conformance_bars()[:22])
    bars[5] = replace(bars[5], high=bars[5].low - 1.0)
    with pytest.raises(ExecutorIntegrityError):
        evaluate_volatility_expansion_breakout(
            evaluation_input(tuple(bars), next_bar=conformance_bars()[22])
        )
    bars = list(conformance_bars()[:22])
    bars[10] = replace(bars[10], timestamp=bars[10].timestamp + timedelta(minutes=1))
    with pytest.raises(ExecutorIntegrityError):
        evaluate_volatility_expansion_breakout(
            evaluation_input(tuple(bars), next_bar=conformance_bars()[22])
        )


def test_no_lookahead_and_frozen_pipeline_conformance() -> None:
    assert no_lookahead_conformance()
    assert proposal_pipeline_conformance()


def test_config_is_exact_and_contaminated_only() -> None:
    config = validate_config(_config(), ROOT)
    assert config == default_config(ROOT)
    assert config["policy"]["optimization_count"] == 0
    assert config["policy"]["parameter_search_count"] == 0
    assert config["policy"]["empirical_execution_permitted"] is False
    assert config["exploratory_dataset_binding"]["empirical_authorized"] is False
    assert config["required_inventory_contract_identity"] == (
        required_inventory_contract_identity()
    )


def test_evidence_rebuild_is_byte_identical_and_verifies(tmp_path: Path) -> None:
    config = _config()
    artifacts = build_evidence(
        repository_root=ROOT,
        config=config,
        library_path=LIBRARY,
    )
    output = tmp_path / "evidence"
    manifest = write_evidence(output, artifacts)
    assert set(artifacts) == set(EVIDENCE_REQUIRED_ROLES)
    conformance = artifacts["07-conformance.json"]["payload"]
    assert conformance["stop_target_collision_precedence"] is True
    assert conformance["lifecycle_timeout"] is True
    assert manifest == json.loads((EVIDENCE / "manifest.json").read_text())
    for name, artifact in artifacts.items():
        assert canonical_json(artifact) == (EVIDENCE / name).read_bytes()
    assert verify_evidence_directory(
        output,
        repository_root=ROOT,
        config=config,
    )["verified"]


def test_evidence_inventory_is_closed_and_write_once(tmp_path: Path) -> None:
    target = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, target)
    (target / "09-extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(VolatilityExpansionMilestoneError, match="not closed"):
        verify_evidence_directory(target, repository_root=ROOT, config=_config())
    with pytest.raises(VolatilityExpansionMilestoneError, match="already exists"):
        write_evidence(target, {})


def test_evidence_rejects_missing_required_artifact(tmp_path: Path) -> None:
    target = tmp_path / "evidence"
    shutil.copytree(EVIDENCE, target)
    (target / "07-conformance.json").unlink()
    with pytest.raises(VolatilityExpansionMilestoneError):
        verify_evidence_directory(target, repository_root=ROOT, config=_config())


def test_candidate_specific_non_evidence_label_is_frozen() -> None:
    assert CANDIDATE_SPECIFIC_LABELS == ("NOT EMPIRICAL EVIDENCE",)
