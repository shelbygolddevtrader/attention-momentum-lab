from dataclasses import asdict, replace
from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from aml.winner_archetype import (
    authorize_phase_access,
    build_experiment_manifest,
    build_feature_snapshot,
    freeze_hypothesis,
    plan_chronological_partitions,
    validate_append_only_result,
    validate_hypothesis_registry,
)
from aml.winner_archetype_contracts import (
    ARCHETYPE_ASSIGNMENT_SCHEMA,
    ARCHETYPE_SCHEMA,
    HYPOTHESIS_SCHEMA,
    ArchetypeAssignment,
    ArchetypeDefinition,
    HypothesisRecord,
    WinnerArchetypeError,
    WinnerArchetypeExperimentSpec,
    canonical_hash,
    canonical_json,
    load_experiment_spec,
)


ROOT = Path(__file__).parents[1]
SPEC_PATH = ROOT / "config/winner_archetype_experiment_v001.json"


def spec_mapping():
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def hypothesis(
    identifier="hypothesis-001", sequence=1, *, supersedes=None,
    rejection_status="active", frozen=False, parameter_hash=None,
    validation_status="not_started",
):
    return HypothesisRecord(
        schema_version=HYPOTHESIS_SCHEMA,
        hypothesis_id=identifier,
        sequence=sequence,
        version="hypothesis-v001",
        statement="Synthetic point-in-time feature differs between groups.",
        source_archetype_id="archetype-001",
        allowed_features=("premarket_gap",),
        proposed_direction="different",
        proposed_test="Predeclared synthetic matched comparison.",
        discovery_partition_version="chronological-50-25-25-v001",
        validation_status=validation_status,
        holdout_status="sealed",
        rejection_status=rejection_status,
        supersedes_hypothesis_id=supersedes,
        parameter_freeze_hash=parameter_hash,
        frozen=frozen,
        creation_timestamp_metadata="2026-07-29T12:00:00+00:00",
    )


def test_repository_experiment_spec_is_strict_versioned_and_deterministic():
    first = load_experiment_spec(SPEC_PATH)
    second = WinnerArchetypeExperimentSpec.from_mapping(spec_mapping())
    assert first == second
    assert first.identity == second.identity
    assert first.selection_start == "2024-06-03"
    assert first.hard_latest_date == "2025-06-04"
    assert first.selection_cutoff_local == "09:25"
    assert first.minimum_gap == .08
    assert first.minimum_premarket_dollar_volume == 1_000_000
    assert first.minimum_premarket_relative_volume == 5
    assert first.selection_feed == first.evaluation_feed == "sip"


@pytest.mark.parametrize("mutation", ("missing", "unexpected"))
def test_experiment_schema_rejects_missing_and_unexpected_fields(mutation):
    value = spec_mapping()
    if mutation == "missing":
        value.pop("research_question")
    else:
        value["surprise"] = True
    with pytest.raises(WinnerArchetypeError, match="missing or unexpected"):
        WinnerArchetypeExperimentSpec.from_mapping(value)


def test_experiment_loader_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"one","schema_version":"two"}', encoding="utf-8")
    with pytest.raises(WinnerArchetypeError, match="invalid JSON"):
        load_experiment_spec(path)


def test_boolean_as_integer_nonfinite_duplicate_features_and_bad_timezone_fail():
    value = spec_mapping()
    value["initial_sessions"] = True
    with pytest.raises(WinnerArchetypeError, match="integer"):
        WinnerArchetypeExperimentSpec.from_mapping(value)
    value = spec_mapping()
    value["minimum_gap"] = float("nan")
    with pytest.raises(WinnerArchetypeError, match="finite"):
        WinnerArchetypeExperimentSpec.from_mapping(value)
    value = spec_mapping()
    value["feature_definitions"].append(value["feature_definitions"][0])
    with pytest.raises(WinnerArchetypeError, match="Duplicate feature"):
        WinnerArchetypeExperimentSpec.from_mapping(value)
    value = spec_mapping()
    value["decision_snapshots"][0]["timezone"] = "Not/AZone"
    with pytest.raises(WinnerArchetypeError, match="IANA"):
        WinnerArchetypeExperimentSpec.from_mapping(value)


def test_ambiguous_cutoff_and_outcome_derived_matching_field_fail():
    value = spec_mapping()
    value["selection_cutoff_semantics"] = "approximately"
    with pytest.raises(WinnerArchetypeError, match="exclusive"):
        WinnerArchetypeExperimentSpec.from_mapping(value)
    value = spec_mapping()
    matching = value["control_matching_spec"]
    matching["matching_fields"].append("mfe")
    matching["field_scales"]["mfe"] = 1
    matching["field_weights"]["mfe"] = 1
    with pytest.raises(WinnerArchetypeError, match="Outcome-derived"):
        WinnerArchetypeExperimentSpec.from_mapping(value)


def test_canonical_json_rejects_nan_infinity_invalid_unicode_and_is_order_independent():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(WinnerArchetypeError, match="finite"):
            canonical_json({"value": value})
    with pytest.raises(WinnerArchetypeError, match="Unicode"):
        canonical_json({"value": "bad\ud800"})


def test_feature_snapshot_binds_cutoff_missingness_and_source_manifests():
    spec = load_experiment_spec(SPEC_PATH)
    snapshot = build_feature_snapshot(
        session="2024-06-03",
        symbol="TEST",
        security_identifier="SYNTHETIC-TEST",
        snapshot_spec=spec.decision_snapshots[2],
        latest_input_timestamp="2024-06-03T09:24:59-04:00",
        feature_definition_version="feature-set-v001",
        source_manifest_hashes=("b" * 64, "a" * 64),
        completeness_status="partial",
        feature_values={"premarket_gap": .1, "spread_bps": None},
    )
    assert snapshot.missingness == {"premarket_gap": False, "spread_bps": True}
    assert snapshot.source_manifest_hashes == ("a" * 64, "b" * 64)
    assert snapshot.snapshot_version == "premarket-0925-v001"
    assert snapshot.snapshot_spec_hash == spec.decision_snapshots[2].identity
    assert snapshot.canonical_feature_hash == canonical_hash(snapshot.feature_values)


def test_feature_snapshot_rejects_post_cutoff_information():
    spec = load_experiment_spec(SPEC_PATH)
    with pytest.raises(WinnerArchetypeError, match="exceeds"):
        build_feature_snapshot(
            session="2024-06-03",
            symbol="TEST",
            security_identifier="SYNTHETIC-TEST",
            snapshot_spec=spec.decision_snapshots[2],
            latest_input_timestamp="2024-06-03T09:25:00-04:00",
            feature_definition_version="feature-set-v001",
            source_manifest_hashes=("a" * 64,),
            completeness_status="complete",
            feature_values={"premarket_gap": .1},
        )


def test_hypothesis_freeze_identity_excludes_human_timestamp_metadata():
    draft = hypothesis()
    changed_timestamp = replace(
        draft, creation_timestamp_metadata="2027-01-01T00:00:00+00:00"
    )
    assert canonical_hash(draft.identity_payload()) == canonical_hash(
        changed_timestamp.identity_payload()
    )
    frozen = freeze_hypothesis(draft, {"threshold": .1})
    assert frozen.frozen is True
    assert frozen.parameter_freeze_hash == canonical_hash({"threshold": .1})
    with pytest.raises(WinnerArchetypeError, match="parameter_freeze_hash"):
        hypothesis(frozen=True, parameter_hash=None)


def test_hypothesis_mapping_rejects_unexpected_fields():
    value = asdict(hypothesis())
    value["unexpected"] = "no"
    with pytest.raises(WinnerArchetypeError, match="unexpected"):
        HypothesisRecord.from_mapping(value)


def test_hypothesis_registry_rejects_duplicates_bad_order_and_forward_supersession():
    with pytest.raises(WinnerArchetypeError, match="Duplicate"):
        validate_hypothesis_registry((hypothesis(), hypothesis()))
    with pytest.raises(WinnerArchetypeError, match="sequence"):
        validate_hypothesis_registry((hypothesis(sequence=2),))
    with pytest.raises(WinnerArchetypeError, match="point backward"):
        validate_hypothesis_registry((
            hypothesis("hypothesis-002", supersedes="hypothesis-001"),
        ))


def test_hypothesis_supersession_is_append_only_and_deterministic():
    original = hypothesis(rejection_status="superseded")
    revised = hypothesis(
        "hypothesis-002", sequence=2, supersedes="hypothesis-001"
    )
    assert validate_hypothesis_registry((original, revised)) == validate_hypothesis_registry(
        (original, revised)
    )


def test_phase_guards_reject_holdout_in_discovery_and_unfrozen_holdout_access():
    with pytest.raises(WinnerArchetypeError, match="contamination"):
        authorize_phase_access(
            execution_phase="discovery", requested_partition="holdout"
        )
    with pytest.raises(WinnerArchetypeError, match="frozen"):
        authorize_phase_access(
            execution_phase="holdout", requested_partition="holdout",
            hypothesis=hypothesis(),
        )
    frozen = freeze_hypothesis(
        hypothesis(validation_status="passed"), {"threshold": .1}
    )
    with pytest.raises(WinnerArchetypeError, match="does not match"):
        authorize_phase_access(
            execution_phase="holdout", requested_partition="holdout",
            hypothesis=frozen, supplied_parameter_hash="0" * 64,
        )
    authorize_phase_access(
        execution_phase="holdout", requested_partition="holdout",
        hypothesis=frozen, supplied_parameter_hash=frozen.parameter_freeze_hash,
    )


def test_append_only_result_guard_allows_idempotence_but_rejects_replacement():
    identity = "a" * 64
    content = "b" * 64
    validate_append_only_result({}, identity, content)
    validate_append_only_result({identity: content}, identity, content)
    with pytest.raises(WinnerArchetypeError, match="cannot be overwritten"):
        validate_append_only_result({identity: content}, identity, "c" * 64)


def test_experiment_manifest_binds_definitions_partitions_and_holdout_state():
    experiment = load_experiment_spec(SPEC_PATH)
    sessions = [
        (date(2024, 6, 1) + timedelta(days=offset)).isoformat()
        for offset in range(60)
    ]
    plan = plan_chronological_partitions(sessions, experiment.partition_spec)
    manifest = build_experiment_manifest(
        experiment_spec_hash=experiment.identity,
        partition_plan=plan,
        source_manifest_hashes=("a" * 64,),
        feature_definition_hashes=("b" * 64,),
        outcome_definition_hashes=("c" * 64,),
        control_matching_hash=experiment.control_matching_spec.identity,
        hypothesis_registry_hash=None,
        holdout_accessed=False,
    )
    assert manifest.ordered_sessions == tuple(sessions)
    assert manifest.holdout_accessed is False
    assert manifest.manifest_id == canonical_hash({
        key: value for key, value in asdict(manifest).items()
        if key not in {"schema_version", "manifest_id"}
    })


def test_archetype_contract_prohibits_performance_interpretation():
    values = {
        "schema_version": ARCHETYPE_SCHEMA,
        "archetype_id": "archetype-001",
        "version": "archetype-v001",
        "description": "Synthetic high-gap and high-volume grouping.",
        "assignment_method": "Predeclared exact synthetic rule.",
        "inclusion_rule": "premarket_gap >= 0.1",
        "feature_names": ("premarket_gap",),
        "discovery_partition_id": "discovery-v001",
        "sample_count": 30,
        "winner_count": 10,
        "control_count": 20,
        "missingness_summary": {"premarket_gap": 0.0},
        "balance_diagnostic_ids": ("a" * 64,),
        "hypothesis_status": "descriptive",
        "interpretation_status": "no_performance_claim_permitted",
    }
    assert ArchetypeDefinition(**values).sample_count == 30
    values["interpretation_status"] = "profitable"
    with pytest.raises(WinnerArchetypeError, match="performance claims"):
        ArchetypeDefinition(**values)


def test_archetype_assignment_identity_binds_method_event_and_partition():
    payload = {
        "archetype_id": "archetype-001",
        "event_id": "event-001",
        "partition": "discovery",
        "assignment_method_hash": "a" * 64,
    }
    assignment = ArchetypeAssignment(
        schema_version=ARCHETYPE_ASSIGNMENT_SCHEMA,
        assignment_id=canonical_hash(payload),
        **payload,
    )
    assert assignment.assignment_id == canonical_hash(payload)
    with pytest.raises(WinnerArchetypeError, match="assignment_id"):
        replace(assignment, partition="validation")
