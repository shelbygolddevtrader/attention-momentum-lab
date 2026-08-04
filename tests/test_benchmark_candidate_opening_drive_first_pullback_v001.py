from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from aml.benchmark_candidate_opening_drive_first_pullback_v001 import (
    REFERENCE_STRATEGY_ID,
    conformance_bars,
    conformance_inputs,
    evaluate_opening_drive_first_pullback,
    evaluation_input,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
    verify_reference_binding,
)
from aml.professional_strategy_executor_models_v001 import HaltInterval


def test_reference_binding_is_frozen() -> None:
    assert verify_reference_binding() is None


def test_complete_conformance_state_paths() -> None:
    inputs = conformance_inputs()
    assert evaluate_opening_drive_first_pullback(inputs["positive"]).status == "proposal"
    assert evaluate_opening_drive_first_pullback(inputs["negative"]).status == "no_signal"
    assert evaluate_opening_drive_first_pullback(inputs["unavailable"]).status == "unavailable"
    assert (
        evaluate_opening_drive_first_pullback(inputs["integrity-failure"]).status
        == "integrity_failure"
    )


def test_alias_delegates_to_reference_strategy_without_rule_changes() -> None:
    result = evaluate_opening_drive_first_pullback(conformance_inputs()["positive"])
    assert result.strategy_id == REFERENCE_STRATEGY_ID
    assert result.proposal is not None
    assert result.proposal.strategy_id == REFERENCE_STRATEGY_ID


def test_next_bar_only_exposes_open() -> None:
    assert no_lookahead_conformance() is True


def test_frozen_proposal_pipeline_accepts_positive_case() -> None:
    assert proposal_pipeline_conformance() is True


def test_missing_next_bar_is_unavailable() -> None:
    bars = conformance_bars()
    result = evaluate_opening_drive_first_pullback(
        evaluation_input(bars[:29], next_bar=None)
    )
    assert result.status == "unavailable"
    assert result.reason_codes == ("missing_next_bar",)


def test_halted_next_bar_is_no_trade() -> None:
    bars = conformance_bars()
    value = evaluation_input(bars[:29], next_bar=bars[29])
    assert value.next_bar is not None
    value = replace(
        value,
        next_bar=replace(value.next_bar, halted=True),
        halts=(
            HaltInterval(
                start=value.next_bar.timestamp,
                resume=value.next_bar.timestamp.replace(minute=0) + timedelta(hours=1),
                first_known_at=value.decision_cutoff,
            ),
        ),
    )
    result = evaluate_opening_drive_first_pullback(value)
    assert result.status == "no_trade"
    assert result.reason_codes == ("halt_before_entry",)
