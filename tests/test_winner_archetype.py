from dataclasses import replace
from datetime import date, datetime, timedelta
from itertools import permutations
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aml.winner_archetype import (
    CandidateEvent,
    MinuteBar,
    balance_diagnostics,
    calculate_outcome,
    plan_chronological_partitions,
    plan_matched_controls,
)
from aml.winner_archetype_contracts import (
    MATCHING_SCHEMA,
    OUTCOME_DEFINITION_SCHEMA,
    ControlMatchingSpec,
    OutcomeDefinition,
    WinnerArchetypeError,
    canonical_hash,
    load_experiment_spec,
)


ROOT = Path(__file__).parents[1]
SPEC = load_experiment_spec(ROOT / "config/winner_archetype_experiment_v001.json")
MANIFEST = canonical_hash({"synthetic": True})
ZONE = ZoneInfo("America/New_York")


def outcome_definition(**changes):
    values = {
        "schema_version": OUTCOME_DEFINITION_SCHEMA,
        "definition_version": "synthetic-outcome-v001",
        "reference_price_semantics": "bar_open",
        "reference_time": "09:30",
        "evaluation_start": "09:30",
        "evaluation_end": "09:34",
        "session_timezone": "America/New_York",
        "upside_threshold": .10,
        "downside_threshold": .05,
        "reward_to_risk_multiple": 2.0,
        "sustained_momentum_threshold": .05,
        "sustained_minutes": 2,
        "close_above_reference": "evaluation_close",
        "ambiguity_rule": "downside_first_conservative",
        "missing_minute_rule": "no_forward_fill_mark_incomplete",
        "halt_treatment": "exclude_verified_halt_minutes_and_report",
    }
    values.update(changes)
    return OutcomeDefinition(**values)


def bars(rows, *, session="2024-06-03"):
    start = datetime.combine(date.fromisoformat(session), datetime.min.time(), ZONE).replace(
        hour=9, minute=30
    )
    return [
        MinuteBar((start + timedelta(minutes=index)).isoformat(), *row)
        for index, row in enumerate(rows)
    ]


def calculate(rows, *, definition=None, session="2024-06-03", halts=()):
    return calculate_outcome(
        symbol="TEST", security_identifier="SYNTHETIC-TEST", session=session,
        definition=definition or outcome_definition(), bars=bars(rows, session=session),
        input_manifest_hash=MANIFEST, verified_halt_intervals=halts,
    )


def event(identifier, symbol, winner, shift=0, session="2024-06-03", missing=None):
    features = {
        "price": 10 + shift,
        "premarket_gap": .1 + shift / 100,
        "premarket_dollar_volume": 2_000_000 + shift * 100_000,
        "premarket_relative_volume": 8 + shift,
        "atr_percent_20": .08 + shift / 1000,
        "spread_bps": 20 + shift,
    }
    if missing:
        features[missing] = None
    return CandidateEvent(
        event_id=identifier, session=session, symbol=symbol,
        security_identifier=f"SYNTHETIC-{symbol}", winner=winner,
        pre_outcome_features=features,
    )


def test_partition_plan_is_chronological_complete_and_deterministic():
    sessions = []
    current = date(2024, 6, 3)
    while len(sessions) < 60:
        if current.weekday() < 5:
            sessions.append(current.isoformat())
        current += timedelta(days=1)
    first = plan_chronological_partitions(sessions, SPEC.partition_spec)
    second = plan_chronological_partitions(tuple(sessions), SPEC.partition_spec)
    assert first == second
    assert len(first.assignments["discovery"]) == 30
    assert len(first.assignments["validation"]) == 15
    assert len(first.assignments["holdout"]) == 15
    assert len(set().union(*(set(value) for value in first.assignments.values()))) == 60


def test_partition_plan_rejects_duplicate_overlap_unsorted_and_too_few_sessions():
    with pytest.raises(WinnerArchetypeError, match="ordered and unique"):
        plan_chronological_partitions(("2024-06-04", "2024-06-03"), SPEC.partition_spec)
    with pytest.raises(WinnerArchetypeError, match="ordered and unique"):
        plan_chronological_partitions(("2024-06-03",) * 30, SPEC.partition_spec)
    with pytest.raises(WinnerArchetypeError, match="Too few"):
        plan_chronological_partitions(
            tuple((date(2024, 6, 1) + timedelta(days=index)).isoformat() for index in range(29)),
            SPEC.partition_spec,
        )


def test_partition_boolean_is_not_integer_and_ratios_must_total_10000():
    with pytest.raises(WinnerArchetypeError, match="integer"):
        replace(SPEC.partition_spec, discovery_basis_points=True)
    with pytest.raises(WinnerArchetypeError, match="10000"):
        replace(SPEC.partition_spec, holdout_basis_points=2499)


def test_outcome_clear_winner_and_clear_nonwinner():
    winner = calculate([
        (100, 101, 99, 100), (100, 106, 100, 105), (105, 111, 104, 110),
        (110, 112, 109, 111), (111, 113, 110, 112),
    ])
    assert winner.threshold_order == "upside_first"
    assert winner.reward_to_risk_achieved is True
    assert winner.sustained_momentum_achieved is True
    assert winner.closed_above_reference is True
    loser = calculate([
        (100, 101, 99, 100), (100, 100, 94, 95), (95, 96, 93, 94),
        (94, 95, 93, 94), (94, 95, 93, 94),
    ])
    assert loser.threshold_order == "downside_first"
    assert loser.reward_to_risk_achieved is False
    assert loser.closed_above_reference is False


def test_outcome_threshold_order_and_exact_touch_are_deterministic():
    upside = calculate([(100, 110, 96, 105)] + [(105, 106, 104, 105)] * 4)
    assert upside.threshold_order == "upside_first"
    downside = calculate([(100, 109, 95, 99)] + [(99, 100, 98, 99)] * 4)
    assert downside.threshold_order == "downside_first"
    ambiguous = calculate([(100, 110, 95, 100)] + [(100, 101, 99, 100)] * 4)
    assert ambiguous.threshold_order == "ambiguous_downside_first"


def test_missing_minutes_are_not_forward_filled_and_halts_are_explicit():
    source = bars([
        (100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100),
        (100, 101, 99, 100), (100, 101, 99, 100),
    ])
    incomplete = calculate_outcome(
        symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
        definition=outcome_definition(), bars=source[:2] + source[3:],
        input_manifest_hash=MANIFEST,
    )
    assert incomplete.completeness_status == "incomplete"
    assert incomplete.missing_minutes == 1
    halt = source[2].timestamp
    adjusted = calculate_outcome(
        symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
        definition=outcome_definition(), bars=source[:2] + source[3:],
        input_manifest_hash=MANIFEST, verified_halt_intervals=((halt, halt),),
    )
    assert adjusted.completeness_status == "halt_adjusted_complete"
    assert adjusted.verified_halt_minutes == 1
    assert adjusted.halt_involved is True


def test_no_usable_bars_is_explicit_and_does_not_invent_reference_price():
    result = calculate_outcome(
        symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
        definition=outcome_definition(), bars=(), input_manifest_hash=MANIFEST,
    )
    assert result.completeness_status == "no_usable_bars"
    assert result.reference_price is None
    assert result.maximum_favorable_excursion is None
    assert result.threshold_order == "unavailable"


@pytest.mark.parametrize("session,offset", (("2024-03-11", "-04:00"), ("2024-11-04", "-05:00")))
def test_outcomes_bind_new_york_dst_offsets(session, offset):
    result = calculate([(100, 101, 99, 100)] * 5, session=session)
    assert result.reference_timestamp.endswith(offset)


def test_outcome_identity_changes_with_definition_and_manifest():
    rows = [(100, 111, 99, 110)] * 5
    first = calculate(rows)
    changed = calculate(rows, definition=outcome_definition(upside_threshold=.2))
    assert first.outcome_id != changed.outcome_id
    other_manifest = calculate_outcome(
        symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
        definition=outcome_definition(), bars=bars(rows),
        input_manifest_hash="f" * 64,
    )
    assert first.outcome_id != other_manifest.outcome_id


def test_outcome_rejects_out_of_order_duplicate_and_invalid_bars():
    source = bars([(100, 101, 99, 100)] * 5)
    with pytest.raises(WinnerArchetypeError, match="chronological"):
        calculate_outcome(
            symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
            definition=outcome_definition(), bars=tuple(reversed(source)),
            input_manifest_hash=MANIFEST,
        )
    with pytest.raises(WinnerArchetypeError, match="unique"):
        calculate_outcome(
            symbol="TEST", security_identifier="SYNTHETIC-TEST", session="2024-06-03",
            definition=outcome_definition(), bars=(source[0], source[0]),
            input_manifest_hash=MANIFEST,
        )
    with pytest.raises(WinnerArchetypeError, match="OHLC"):
        MinuteBar(source[0].timestamp, 100, 90, 99, 100).validate()


def test_matching_exact_ties_and_input_order_are_deterministic():
    candidates = [
        event("winner-001", "AAA", True),
        event("control-002", "CCC", False, 1),
        event("control-001", "BBB", False, 1),
    ]
    expected = plan_matched_controls(candidates, SPEC.control_matching_spec)
    assert [item.control_event_id for item in expected] == ["control-001", "control-002"]
    for ordering in permutations(candidates):
        assert plan_matched_controls(ordering, SPEC.control_matching_spec) == expected


def test_matching_shortage_missing_fields_same_day_and_no_reuse():
    candidates = [
        event("winner-001", "AAA", True),
        event("winner-002", "BBB", True, .1),
        event("control-001", "CCC", False, 1),
        event("other-day-001", "DDD", False, 0, session="2024-06-04"),
    ]
    matches = plan_matched_controls(candidates, SPEC.control_matching_spec)
    assert sum(item.control_event_id == "control-001" for item in matches) == 1
    assert any(item.reason_code == "insufficient_controls" for item in matches)
    missing = plan_matched_controls(
        [event("winner-001", "AAA", True), event("control-001", "BBB", False, missing="price")],
        SPEC.control_matching_spec,
    )
    assert {item.reason_code for item in missing} == {"missing_matching_fields"}


def test_matching_with_replacement_is_explicit():
    reusable = replace(SPEC.control_matching_spec, with_replacement=True)
    candidates = [
        event("winner-001", "AAA", True),
        event("winner-002", "BBB", True),
        event("control-001", "CCC", False),
    ]
    matches = plan_matched_controls(candidates, reusable)
    assert sum(item.control_event_id == "control-001" for item in matches) == 2
    assert all(item.with_replacement for item in matches)


def test_matching_supports_pre_outcome_categorical_fields_deterministically():
    categorical = ControlMatchingSpec(
        schema_version=MATCHING_SCHEMA,
        matching_version="categorical-v001",
        matching_fields=("sector",), field_scales={"sector": 1},
        field_weights={"sector": 1}, maximum_controls=2,
        with_replacement=False, same_session_required=True,
        tie_break_fields=("symbol", "event_id"),
    )
    winner = replace(
        event("winner-001", "AAA", True),
        pre_outcome_features={"sector": "technology"},
    )
    same = replace(
        event("control-001", "BBB", False),
        pre_outcome_features={"sector": "technology"},
    )
    different = replace(
        event("control-002", "CCC", False),
        pre_outcome_features={"sector": "healthcare"},
    )
    matches = plan_matched_controls((different, winner, same), categorical)
    assert [item.control_event_id for item in matches] == ["control-001", "control-002"]
    assert [item.distance for item in matches] == [0.0, 1.0]
    diagnostics = balance_diagnostics((winner, same, different), matches, categorical)
    assert len(diagnostics) == 4
    assert all(item.feature_name.startswith("sector.category-") for item in diagnostics)


def test_matching_spec_rejects_prohibited_future_fields():
    with pytest.raises(WinnerArchetypeError, match="Outcome-derived"):
        ControlMatchingSpec(
            schema_version=MATCHING_SCHEMA,
            matching_version="unsafe-v001",
            matching_fields=("mfe",), field_scales={"mfe": 1},
            field_weights={"mfe": 1}, maximum_controls=2,
            with_replacement=False, same_session_required=True,
            tie_break_fields=("symbol", "event_id"),
        )
    with pytest.raises(WinnerArchetypeError, match="Outcome-derived"):
        replace(
            SPEC.control_matching_spec,
            matching_fields=("forward_5m_return",),
            field_scales={"forward_5m_return": 1},
            field_weights={"forward_5m_return": 1},
        )


def test_balance_diagnostics_report_before_and_after_matching():
    candidates = [
        event("winner-001", "AAA", True),
        event("control-001", "BBB", False, 1),
        event("control-002", "CCC", False, 2),
    ]
    matches = plan_matched_controls(candidates, SPEC.control_matching_spec)
    diagnostics = balance_diagnostics(candidates, matches, SPEC.control_matching_spec)
    assert len(diagnostics) == len(SPEC.control_matching_spec.matching_fields) * 2
    assert {item.stage for item in diagnostics} == {"before", "after"}
    assert all(len(item.diagnostic_id) == 64 for item in diagnostics)
