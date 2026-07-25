import json
from pathlib import Path

import pytest

from aml.experiment_registry import (
    ExperimentError, append_operational_note, load_registry, preregister, specification_hash,
    transition, validate_experiment, validate_registry_root, write_spec,
)


ROOT = Path(__file__).parents[1]
SPEC = ROOT / "experiments/v012/v012-catalyst-presence.json"


def draft():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def resolved():
    spec = draft()
    spec["observation_window"] = "Synthetic fixed window"
    spec["primary_metric"] = {
        "name": "Synthetic fixed metric", "unit": "count", "direction": "descriptive",
    }
    spec["multiple_testing_family"] = "Synthetic fixed family"
    spec["feature_definitions"][0]["definition"] = (
        "Whether one qualifying catalyst was first seen within a fixed synthetic interval."
    )
    spec["minimum_sample_size"] = {
        "status": "resolved", "value": 100,
        "rationale": "Synthetic test resolution only.",
    }
    for field in (
        "decision_thresholds", "promotion_criteria", "rejection_criteria",
        "stop_conditions",
    ):
        spec[field] = {
            "status": "resolved", "rule": "Synthetic fixed rule",
            "rationale": "Synthetic test resolution only.",
        }
    return spec


def test_repository_drafts_validate_and_are_not_preregistered():
    specs = load_registry((ROOT / "experiments/v012").resolve())
    assert [item["experiment_id"] for item in specs] == [
        "v012-catalyst-category", "v012-catalyst-presence", "v012-catalyst-timing",
    ]
    assert {item["status"] for item in specs} == {"draft"}
    assert all(item["preregistration_hash"] is None for item in specs)


@pytest.mark.parametrize("mutation", ("missing", "unknown"))
def test_missing_and_unknown_fields_fail(mutation):
    spec = draft()
    if mutation == "missing":
        spec.pop("hypothesis")
    else:
        spec["surprise"] = True
    with pytest.raises(ExperimentError, match="fields differ"):
        validate_experiment(spec)


def test_timezone_and_baseline_fail_closed():
    spec = draft()
    spec["registration_timestamp"] = "2026-07-25T20:00:00"
    with pytest.raises(ExperimentError, match="timezone"):
        validate_experiment(spec)
    spec = draft()
    spec["strategy_baseline"]["strategy_version"] = "0.1.2"
    with pytest.raises(ExperimentError, match="baseline"):
        validate_experiment(spec)


def test_boolean_does_not_satisfy_numeric_minimum_sample():
    spec = draft()
    spec["minimum_sample_size"] = {
        "status": "resolved", "value": True, "rationale": "Synthetic test.",
    }
    with pytest.raises(ExperimentError, match="positive integer"):
        validate_experiment(spec)


def test_unresolved_draft_cannot_be_preregistered():
    with pytest.raises(ExperimentError, match="resolved"):
        preregister(draft())


def test_preregistration_hash_is_canonical_and_research_fields_are_immutable():
    registered = preregister(resolved())
    assert registered["preregistration_hash"] == specification_hash(registered)
    reordered = json.loads(json.dumps(registered, sort_keys=False))
    assert specification_hash(reordered) == specification_hash(registered)
    changed = dict(registered)
    changed["hypothesis"] = "Retrospectively changed"
    with pytest.raises(ExperimentError, match="modified"):
        validate_experiment(changed)


def test_status_transitions_are_explicit_and_do_not_change_preregistration_hash():
    registered = preregister(resolved())
    collecting = transition(registered, "collecting")
    assert collecting["preregistration_hash"] == registered["preregistration_hash"]
    with pytest.raises(ExperimentError, match="Invalid status transition"):
        transition(collecting, "promoted")


def test_operational_notes_append_separately_without_changing_specification(tmp_path):
    registry = tmp_path / "registry"
    registered = preregister(resolved())
    write_spec(registry / f"{registered['experiment_id']}.json", registered)
    original = specification_hash(registered)
    path = append_operational_note(
        registry.resolve(), registered["experiment_id"],
        "2026-07-25T21:00:00+00:00", "synthetic-author", "Synthetic note one",
    )
    append_operational_note(
        registry.resolve(), registered["experiment_id"],
        "2026-07-25T21:01:00+00:00", "synthetic-author", "Synthetic note two",
    )
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert specification_hash(load_registry(registry.resolve())[0]) == original


def test_duplicate_ids_fail(tmp_path):
    registry = tmp_path / "registry"
    write_spec(registry / "one.json", draft())
    write_spec(registry / "two.json", draft())
    with pytest.raises(ExperimentError, match="Duplicate"):
        load_registry(registry.resolve())


def test_registry_rejects_traversal_protected_paths_and_symlinks(tmp_path):
    with pytest.raises(ExperimentError, match="traversal"):
        validate_registry_root(tmp_path / ".." / "registry")
    with pytest.raises(ExperimentError, match="protected"):
        validate_registry_root((tmp_path / "sealed" / "registry").resolve())
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ExperimentError, match="symlink"):
        validate_registry_root(linked)


def test_forward_outcomes_cannot_be_permitted():
    spec = draft()
    spec["permitted_datasets"].append("forward-validation outcomes")
    with pytest.raises(ExperimentError, match="leakage"):
        validate_experiment(spec)


def test_cli_intentionally_has_no_evaluation_command():
    source = (ROOT / "scripts/manage_experiments.py").read_text(encoding="utf-8")
    assert "add_parser(\"evaluate\")" not in source
    assert "sealed" not in source.casefold()
