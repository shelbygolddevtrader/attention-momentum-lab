"""Research-lifecycle, isolation, and determinism tests for V001."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from aml.benchmark_research_candidate_v001 import (
    CandidateIntegrityError,
    evaluate_opening_range_midpoint_reclaim,
)
from aml.benchmark_strategy_research_v001 import (
    BenchmarkResearchError,
    bind_implementation,
    canonical_hash,
    canonical_json,
    create_archive,
    create_child_hypothesis,
    create_hypothesis,
    create_observation,
    create_specification,
    create_triage,
    execute_discovery,
    make_artifact,
    market_data_identity,
    preregister,
    run_candidate_conformance,
    validate_artifact,
    verify_bundle,
    write_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "config/benchmark_strategy_research_v001_example.json"
BARS_PATH = (
    ROOT
    / "tests/fixtures/benchmark_research_v001/opening_reclaim_synthetic.csv"
)
SOURCE_DATASET = "c" * 64


def plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def bars() -> pd.DataFrame:
    return pd.read_csv(BARS_PATH)


def entities() -> dict[str, dict[str, object]]:
    value = plan()
    observation = create_observation(value["observation"])
    hypothesis = create_hypothesis(value["hypothesis"], observation)
    triage = create_triage(
        {**value["triage"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
    )
    specification = create_specification(
        {**value["specification"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
        triage,
    )
    registration = preregister(
        {
            **value["preregistration"],
            "observation_identity": observation["identity"],
            "hypothesis_identity": hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
        },
        observation,
        hypothesis,
        triage,
        specification,
    )
    binding = bind_implementation(
        ROOT,
        {
            "preregistration_identity": registration["identity"],
            "specification_identity": specification["identity"],
            "implementation_callable": (
                "aml.benchmark_research_candidate_v001."
                "evaluate_opening_range_midpoint_reclaim"
            ),
            "implementation_files": [
                "src/aml/benchmark_research_candidate_v001.py",
                "src/aml/benchmark_strategy_research_v001.py",
            ],
            "downstream_files": [
                "src/aml/discovery_screen_v001.py",
                "src/aml/portfolio_simulator.py",
            ],
            "no_frozen_file_modified": True,
        },
        registration,
        specification,
    )
    fixture = bars()
    dataset = market_data_identity({"TEST": fixture})
    conformance = run_candidate_conformance(
        fixture,
        dataset_identity=dataset,
        hypothesis=hypothesis,
        specification=specification,
        preregistration=registration,
        binding=binding,
    )
    return {
        "observation": observation,
        "hypothesis": hypothesis,
        "triage": triage,
        "specification": specification,
        "preregistration": registration,
        "implementation_binding": binding,
        "conformance": conformance,
    }


def run_discovery(
    values: dict[str, dict[str, object]] | None = None,
    frame: pd.DataFrame | None = None,
):
    values = values or entities()
    frame = bars() if frame is None else frame
    dataset = market_data_identity({"TEST": frame})
    return execute_discovery(
        {"TEST": frame},
        repository_root=ROOT,
        dataset_identity=dataset,
        hypothesis=values["hypothesis"],
        specification=values["specification"],
        preregistration=values["preregistration"],
        binding=values["implementation_binding"],
        conformance=values["conformance"],
    )


def test_canonical_entities_are_deterministic_and_identity_bound() -> None:
    first, second = entities(), entities()
    assert first == second
    assert canonical_json(first) == canonical_json(second)
    for artifact in first.values():
        assert validate_artifact(artifact) == artifact
    tampered = json.loads(canonical_json(first["hypothesis"]))
    tampered["payload"]["expected_edge"] = "changed after preregistration"
    with pytest.raises(BenchmarkResearchError, match="stale or tampered"):
        validate_artifact(tampered)


def test_observation_data_is_permanently_contaminated() -> None:
    value = plan()
    observation = create_observation(value["observation"])
    invalid = {**value["hypothesis"], "contaminated_dataset_identities": []}
    with pytest.raises(BenchmarkResearchError, match="permanently contaminated"):
        create_hypothesis(invalid, observation)


def test_preregistration_rejects_contaminated_evaluation_data() -> None:
    value = plan()
    observation = create_observation(value["observation"])
    hypothesis = create_hypothesis(value["hypothesis"], observation)
    triage = create_triage(
        {**value["triage"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
    )
    specification = create_specification(
        {**value["specification"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
        triage,
    )
    invalid = {
        **value["preregistration"],
        "observation_identity": observation["identity"],
        "hypothesis_identity": hypothesis["identity"],
        "triage_identity": triage["identity"],
        "specification_identity": specification["identity"],
        "permitted_discovery_dataset_identities": [SOURCE_DATASET],
    }
    with pytest.raises(BenchmarkResearchError, match="contaminated data"):
        preregister(
            invalid, observation, hypothesis, triage, specification
        )


def test_post_preregistration_change_requires_new_child_and_contamination() -> None:
    value = entities()
    parent = value["hypothesis"]
    observation = value["observation"]
    discovery_dataset = market_data_identity({"TEST": bars()})
    child_payload = {
        **parent["payload"],
        "revision": 2,
        "parent_hypothesis_identity": parent["identity"],
        "expected_edge": "Prospective child definition, not inherited evidence.",
        "contaminated_dataset_identities": sorted(
            [SOURCE_DATASET, discovery_dataset]
        ),
    }
    with pytest.raises(BenchmarkResearchError, match="create_child_hypothesis"):
        create_hypothesis(child_payload, observation)
    child = create_child_hypothesis(
        parent,
        value["preregistration"],
        child_payload,
        datasets_used_after_preregistration=(discovery_dataset,),
        observation=observation,
    )
    assert child["identity"] != parent["identity"]
    assert child["payload"]["revision"] == 2
    assert parent["identity"] in child["parent_identities"]
    assert discovery_dataset in child["payload"]["contaminated_dataset_identities"]
    missing_contamination = {
        **child_payload,
        "contaminated_dataset_identities": [SOURCE_DATASET],
    }
    with pytest.raises(BenchmarkResearchError, match="inherit all contaminated"):
        create_child_hypothesis(
            parent,
            value["preregistration"],
            missing_contamination,
            datasets_used_after_preregistration=(discovery_dataset,),
            observation=observation,
        )


def test_candidate_positive_negative_unavailable_and_integrity_paths() -> None:
    value = entities()
    frame = bars()
    kwargs = {
        "hypothesis_identity": value["hypothesis"]["identity"],
        "specification_identity": value["specification"]["identity"],
        "preregistration_identity": value["preregistration"]["identity"],
        "implementation_binding_identity": value["implementation_binding"]["identity"],
        "dataset_identity": market_data_identity({"TEST": frame}),
    }
    positive = evaluate_opening_range_midpoint_reclaim(frame.iloc[:7], **kwargs)
    assert positive.status == "proposal"
    assert positive.proposal is not None
    negative = frame.iloc[:7].copy()
    negative.loc[negative.index[-1], ["open", "high", "close"]] = [10.1, 10.2, 10.1]
    assert evaluate_opening_range_midpoint_reclaim(negative, **kwargs).status == "no_signal"
    incomplete = frame.iloc[:7].drop(index=2).reset_index(drop=True)
    assert evaluate_opening_range_midpoint_reclaim(incomplete, **kwargs).status == "unavailable"
    duplicate = pd.concat([frame.iloc[:7], frame.iloc[[6]]], ignore_index=True)
    with pytest.raises(CandidateIntegrityError, match="unique"):
        evaluate_opening_range_midpoint_reclaim(duplicate, **kwargs)


def test_candidate_has_no_lookahead_and_does_not_mutate_inputs() -> None:
    value = entities()
    frame = bars()
    original = frame.copy(deep=True)
    kwargs = {
        "hypothesis_identity": value["hypothesis"]["identity"],
        "specification_identity": value["specification"]["identity"],
        "preregistration_identity": value["preregistration"]["identity"],
        "implementation_binding_identity": value["implementation_binding"]["identity"],
        "dataset_identity": market_data_identity({"TEST": frame}),
    }
    first = evaluate_opening_range_midpoint_reclaim(frame.iloc[:7], **kwargs)
    changed = frame.copy(deep=True)
    changed.loc[7:, ["open", "high", "low", "close"]] *= 3
    second = evaluate_opening_range_midpoint_reclaim(changed.iloc[:7], **kwargs)
    assert first.proposal is not None and second.proposal is not None
    assert first.proposal.proposal_id == second.proposal.proposal_id
    pd.testing.assert_frame_equal(frame, original)


def test_discovery_uses_existing_pipeline_classifier_and_reconciles() -> None:
    discovery, classification = run_discovery()
    payload = discovery["payload"]
    assert payload["executor_integrity_failure_count"] == 0
    assert payload["proposal_count"] == (
        payload["accepted_trade_count"] + payload["rejected_proposal_count"]
    )
    assert len(set(payload["cost_scenario_trade_counts"].values())) == 1
    assert classification["payload"]["classification"] == (
        "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    )
    assert classification["payload"]["classification_function"] == (
        "aml.discovery_screen_v001.classify"
    )
    assert classification["payload"]["validation_eligible"] is False
    assert classification["payload"]["evidence_class"] == (
        "synthetic_non_empirical_vertical_slice"
    )


def test_discovery_rejects_unregistered_or_contaminated_data() -> None:
    value = entities()
    frame = bars()
    with pytest.raises(BenchmarkResearchError, match="not permitted"):
        execute_discovery(
            {"TEST": frame},
            repository_root=ROOT,
            dataset_identity="d" * 64,
            hypothesis=value["hypothesis"],
            specification=value["specification"],
            preregistration=value["preregistration"],
            binding=value["implementation_binding"],
            conformance=value["conformance"],
        )


def test_implementation_substitution_prevents_classification() -> None:
    value = entities()
    frame = bars()
    binding_payload = json.loads(canonical_json(value["implementation_binding"]))[
        "payload"
    ]
    candidate_path = "src/aml/benchmark_research_candidate_v001.py"
    binding_payload["source_sha256"][candidate_path] = "d" * 64
    substituted = make_artifact(
        "implementation_binding",
        binding_payload,
        parent_identities=value["implementation_binding"]["parent_identities"],
    )
    with pytest.raises(BenchmarkResearchError, match="bound implementation changed"):
        execute_discovery(
            {"TEST": frame},
            repository_root=ROOT,
            dataset_identity=market_data_identity({"TEST": frame}),
            hypothesis=value["hypothesis"],
            specification=value["specification"],
            preregistration=value["preregistration"],
            binding=substituted,
            conformance=value["conformance"],
        )


def test_archive_supports_completed_rejected_abandoned_and_superseded() -> None:
    value = entities()
    discovery, classification = run_discovery(value)
    completed = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="completed",
        reason="Synthetic lifecycle completed.",
        related_artifacts=(discovery, classification),
        empirical_outcomes_accessed=False,
    )
    with pytest.raises(BenchmarkResearchError, match="requires its discovery"):
        create_archive(
            hypothesis=value["hypothesis"],
            archive_state="completed",
            reason="Missing discovery lineage.",
            related_artifacts=(classification,),
            empirical_outcomes_accessed=False,
        )
    rejected_classification = make_artifact(
        "classification",
        {
            "discovery_identity": discovery["identity"],
            "classification": "REJECT",
            "evidence_class": "synthetic_non_empirical_vertical_slice",
        },
        parent_identities=(discovery["identity"],),
    )
    rejected = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="rejected",
        reason="Frozen rejection rule applied.",
        related_artifacts=(discovery, rejected_classification),
        empirical_outcomes_accessed=False,
    )
    abandoned = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="abandoned",
        reason="Abandoned before empirical outcome access.",
        related_artifacts=(),
        empirical_outcomes_accessed=False,
    )
    dataset = market_data_identity({"TEST": bars()})
    child_payload = {
        **value["hypothesis"]["payload"],
        "revision": 2,
        "parent_hypothesis_identity": value["hypothesis"]["identity"],
        "expected_edge": "Prospective superseding child.",
        "contaminated_dataset_identities": sorted([SOURCE_DATASET, dataset]),
    }
    child = create_child_hypothesis(
        value["hypothesis"],
        value["preregistration"],
        child_payload,
        datasets_used_after_preregistration=(dataset,),
        observation=value["observation"],
    )
    superseded = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="superseded",
        reason="Prospective child created after preregistration.",
        related_artifacts=(value["preregistration"], child),
        empirical_outcomes_accessed=False,
    )
    assert {
        completed["payload"]["archive_state"],
        rejected["payload"]["archive_state"],
        abandoned["payload"]["archive_state"],
        superseded["payload"]["archive_state"],
    } == {"completed", "rejected", "abandoned", "superseded"}
    with pytest.raises(BenchmarkResearchError, match="cannot be abandoned"):
        create_archive(
            hypothesis=value["hypothesis"],
            archive_state="abandoned",
            reason="Improper file-drawer attempt.",
            related_artifacts=(),
            empirical_outcomes_accessed=True,
        )


def test_write_once_bundle_verifies_and_rejects_tampering(tmp_path: Path) -> None:
    value = entities()
    discovery, classification = run_discovery(value)
    related = (
        value["observation"],
        value["triage"],
        value["specification"],
        value["preregistration"],
        value["implementation_binding"],
        value["conformance"],
        discovery,
        classification,
    )
    archive = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="completed",
        reason="Synthetic vertical slice completed.",
        related_artifacts=related,
        empirical_outcomes_accessed=False,
    )
    ordered = (
        value["observation"],
        value["hypothesis"],
        value["triage"],
        value["specification"],
        value["preregistration"],
        value["implementation_binding"],
        value["conformance"],
        discovery,
        classification,
        archive,
    )
    root = tmp_path / "bundle"
    manifest = write_bundle(root, ordered)
    assert verify_bundle(root)["identity"] == manifest["identity"]
    with pytest.raises(BenchmarkResearchError, match="already exists"):
        write_bundle(root, ordered)
    manifest_path = root / "manifest.json"
    original_manifest = manifest_path.read_bytes()
    unknown = json.loads(original_manifest)
    unknown["unexpected"] = True
    unknown["identity"] = canonical_hash(
        {key: item for key, item in unknown.items() if key != "identity"}
    )
    manifest_path.write_bytes(canonical_json(unknown))
    with pytest.raises(BenchmarkResearchError, match="manifest schema"):
        verify_bundle(root)
    manifest_path.write_bytes(original_manifest)
    unsafe = json.loads(original_manifest)
    unsafe["files"][0]["path"] = "../outside.json"
    unsafe["identity"] = canonical_hash(
        {key: item for key, item in unsafe.items() if key != "identity"}
    )
    manifest_path.write_bytes(canonical_json(unsafe))
    with pytest.raises(BenchmarkResearchError, match="path is unsafe"):
        verify_bundle(root)
    manifest_path.write_bytes(original_manifest)
    path = root / "09-classification.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(BenchmarkResearchError, match="file hash mismatch"):
        verify_bundle(root)


def test_publication_rejects_protected_output_boundaries(tmp_path: Path) -> None:
    value = entities()
    discovery, classification = run_discovery(value)
    related = (
        value["observation"],
        value["triage"],
        value["specification"],
        value["preregistration"],
        value["implementation_binding"],
        value["conformance"],
        discovery,
        classification,
    )
    archive = create_archive(
        hypothesis=value["hypothesis"],
        archive_state="completed",
        reason="Synthetic vertical slice completed.",
        related_artifacts=related,
        empirical_outcomes_accessed=False,
    )
    ordered = (
        value["observation"],
        value["hypothesis"],
        value["triage"],
        value["specification"],
        value["preregistration"],
        value["implementation_binding"],
        value["conformance"],
        discovery,
        classification,
        archive,
    )
    with pytest.raises(BenchmarkResearchError, match="protected boundary"):
        write_bundle(tmp_path / "holdout" / "run", ordered)


def test_full_cli_is_byte_deterministic_across_hash_seeds_and_timezones(
    tmp_path: Path,
) -> None:
    outputs = []
    for index, (seed, timezone) in enumerate((("1", "UTC"), ("777", "Asia/Tokyo"))):
        output = tmp_path / f"run-{index}"
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
        }
        command = [
            sys.executable,
            str(ROOT / "scripts/run_benchmark_strategy_research_v001.py"),
            "--repository-root",
            str(ROOT),
            "--plan",
            str(PLAN_PATH),
            "--bars",
            str(BARS_PATH),
            "--output-root",
            str(output),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(completed.stdout)
        assert result["verified"] is True
        assert result["classification"] == "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
        outputs.append(output)
    first = {
        path.name: path.read_bytes()
        for path in sorted(outputs[0].iterdir())
        if path.is_file()
    }
    second = {
        path.name: path.read_bytes()
        for path in sorted(outputs[1].iterdir())
        if path.is_file()
    }
    assert first == second


def test_new_research_layer_has_no_prohibited_capability_or_reverse_import() -> None:
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "src/aml/benchmark_research_candidate_v001.py",
            "src/aml/benchmark_strategy_research_v001.py",
            "scripts/run_benchmark_strategy_research_v001.py",
        )
    )
    prohibited = (
        "submit_order",
        "TradingClient",
        "paper_trading",
        "live_trading",
        "holdout_artifact",
        "validation_extension",
        "professional_strategy_olympics_orchestrator",
    )
    assert not any(token in sources for token in prohibited)
    for frozen in (
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
        "src/aml/professional_strategy_executors_v001.py",
        "src/aml/professional_strategy_lifecycle_v001.py",
    ):
        assert "benchmark_strategy_research_v001" not in (
            ROOT / frozen
        ).read_text(encoding="utf-8")
