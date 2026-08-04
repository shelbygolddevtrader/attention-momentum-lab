"""Executable Specification Implementation V001.

The milestone binds one immutable Library hypothesis to a frozen evaluator,
proves conformance, and routes claim-limited synthetic evidence through the
unchanged Framework and Discovery Campaign contracts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re

import pandas as pd

from aml.benchmark_candidate_opening_drive_first_pullback_v001 import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    REFERENCE_EXECUTOR_IDENTITY,
    REFERENCE_STRATEGY_ID,
    REFERENCE_STRATEGY_IDENTITY,
    conformance_inputs,
    evaluate_authorized_bars,
    evaluate_opening_drive_first_pullback,
    frame_to_bars,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
    verify_reference_binding,
)
from aml.benchmark_executable_candidate_v001 import candidate_dataset_identity
from aml.benchmark_executable_specification_runtime_v001 import (
    ConformanceCase,
    dataset_authorization_identity,
    implementation_binding_artifact,
    run_conformance,
    validate_dataset_authorization,
    verify_implementation_binding,
)
from aml.benchmark_hypothesis_library_v001 import framework_artifacts, load_library
from aml.benchmark_specification_campaign_v001 import load_config as load_specification_campaign
from aml.benchmark_strategy_research_v001 import (
    canonical_hash,
    canonical_json,
    create_archive,
    create_triage,
    make_artifact,
    preregister,
    verify_bundle,
    write_bundle,
)
from aml.discovery_screen_v001 import classify, trade_metrics


CONFIG_SCHEMA = "aml.executable-specification-implementation.v001"
CONFIG_VERSION = "executable-specification-implementation-v001"
EVIDENCE_CLASS = "synthetic_non_empirical_executable_specification"
HASH = re.compile(r"^[0-9a-f]{64}$")
CONFIG_FIELDS = {
    "schema_version",
    "implementation_version",
    "candidate",
    "dependencies",
    "dataset_authorization",
    "source_paths",
    "policy",
    "implementation_identity",
}
SOURCE_PATHS = [
    "scripts/run_executable_specification_implementation_v001.py",
    "src/aml/benchmark_candidate_opening_drive_first_pullback_v001.py",
    "src/aml/benchmark_executable_specification_runtime_v001.py",
    "src/aml/benchmark_executable_specification_v001.py",
    "src/aml/discovery_screen_v001.py",
    "src/aml/professional_strategy_executor_models_v001.py",
    "src/aml/professional_strategy_executors_v001.py",
    "src/aml/professional_strategy_indicators_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
]


class ExecutableSpecificationError(ValueError):
    """Executable specification configuration or evidence is invalid."""


def implementation_identity(config: Mapping[str, object]) -> str:
    projection = {
        key: config[key]
        for key in sorted(CONFIG_FIELDS - {"implementation_identity"})
    }
    return canonical_hash(
        {
            "domain": "aml.executable-specification-implementation.v001",
            "implementation": projection,
        }
    )


def validate_config(
    config: Mapping[str, object], *, repository_root: Path
) -> dict[str, object]:
    if not isinstance(config, Mapping) or set(config) != CONFIG_FIELDS:
        raise ExecutableSpecificationError("implementation config schema is invalid")
    if (
        config["schema_version"] != CONFIG_SCHEMA
        or config["implementation_version"] != CONFIG_VERSION
    ):
        raise ExecutableSpecificationError("implementation config version changed")
    if config["candidate"] != {
        "library_entry_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "reference_strategy_id": REFERENCE_STRATEGY_ID,
        "reference_strategy_identity": REFERENCE_STRATEGY_IDENTITY,
        "reference_executor_identity": REFERENCE_EXECUTOR_IDENTITY,
    }:
        raise ExecutableSpecificationError("candidate reference binding changed")
    dependencies = config["dependencies"]
    required_dependencies = {
        "library_identity",
        "specification_campaign_identity",
        "specification_identity",
        "framework_hypothesis_identity",
        "registration_identity",
    }
    if not isinstance(dependencies, Mapping) or set(dependencies) != required_dependencies:
        raise ExecutableSpecificationError("implementation dependencies are invalid")
    for field, value in dependencies.items():
        if not isinstance(value, str) or not HASH.fullmatch(value):
            raise ExecutableSpecificationError(f"dependency is malformed:{field}")
    if config["source_paths"] != SOURCE_PATHS:
        raise ExecutableSpecificationError("implementation source inventory changed")
    policy = config["policy"]
    if policy != {
        "claim_ceiling": "pipeline_execution_only_no_empirical_edge_claim",
        "empirical_outcome_access_count": 0,
        "frozen_downstream_modified": False,
        "optimization_count": 0,
        "protected_boundary_access_count": 0,
        "short_arm_authorized": False,
    }:
        raise ExecutableSpecificationError("implementation policy changed")
    validate_dataset_authorization(
        config["dataset_authorization"], repository_root=repository_root
    )
    if config["implementation_identity"] != implementation_identity(config):
        raise ExecutableSpecificationError("implementation identity is stale or tampered")
    verify_reference_binding()
    return dict(config)


def load_config(path: Path, *, repository_root: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_config(value, repository_root=repository_root)
    if path.read_bytes() != canonical_json(value):
        raise ExecutableSpecificationError("implementation config is not canonical")
    return value


def finalize_config(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    dataset = result["dataset_authorization"]
    projection = {
        key: dataset[key]
        for key in sorted(set(dataset) - {"authorization_identity"})
    }
    dataset["authorization_identity"] = dataset_authorization_identity(projection)
    result["implementation_identity"] = implementation_identity(result)
    return result


def _load_dataset(repository_root: Path, authorization: Mapping[str, object]) -> pd.DataFrame:
    validate_dataset_authorization(authorization, repository_root=repository_root)
    path = repository_root / str(authorization["relative_path"])
    frame = pd.read_csv(path)
    if candidate_dataset_identity(frame) != authorization["dataset_identity"]:
        raise ExecutableSpecificationError("authorized dataset identity changed")
    return frame


def _artifacts(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    library_path: Path,
    specification_campaign_path: Path,
) -> tuple[dict[str, dict[str, object]], pd.DataFrame]:
    validate_config(config, repository_root=repository_root)
    library = load_library(library_path)
    specification_campaign = load_specification_campaign(
        specification_campaign_path,
        library_path=library_path,
        readiness_path=repository_root
        / "config/benchmark_implementation_campaign_v001.json",
        repository_root=repository_root,
    )
    dependencies = config["dependencies"]
    if (
        library["library_identity"] != dependencies["library_identity"]
        or specification_campaign["campaign_identity"]
        != dependencies["specification_campaign_identity"]
        or specification_campaign["specification_identity"]
        != dependencies["specification_identity"]
    ):
        raise ExecutableSpecificationError("frozen dependency identity changed")
    entries = {item["library_entry_id"]: item for item in library["hypotheses"]}
    entry = entries.get(CANDIDATE_ID)
    if (
        entry is None
        or entry["framework_hypothesis_identity"]
        != dependencies["framework_hypothesis_identity"]
        or entry["registration_identity"] != dependencies["registration_identity"]
    ):
        raise ExecutableSpecificationError("selected hypothesis identity changed")
    sources = {item["source_id"]: item for item in library["sources"]}
    observation, hypothesis = framework_artifacts(entry, sources)
    triage = create_triage(
        {
            "hypothesis_identity": hypothesis["identity"],
            "disposition": "admit",
            "priority_vector": {
                "mechanism_plausibility": 2,
                "supporting_evidence": 1,
                "expected_frequency": 2,
                "data_readiness": 3,
                "distinctness": 1,
                "falsification_value": 3,
                "engineering_cost": 3,
                "contamination_risk": 2,
            },
            "duplicate_signature": canonical_hash(
                {"domain": "aml.executable-specification.triage.v001", "id": CANDIDATE_ID}
            ),
            "duplicate_hypothesis_identities": [],
            "reasons": [
                "Specification Campaign V001 selected this hypothesis prospectively.",
                "The long arm is an exact semantic alias of a frozen evaluator.",
            ],
        },
        hypothesis,
    )
    specification = make_artifact(
        "specification",
        {
            **specification_campaign["specification"],
            "hypothesis_identity": hypothesis["identity"],
            "specification_campaign_identity": specification_campaign["campaign_identity"],
            "canonical_specification_identity": specification_campaign[
                "specification_identity"
            ],
        },
        parent_identities=(hypothesis["identity"], triage["identity"]),
    )
    dataset = config["dataset_authorization"]
    preregistration_artifact = preregister(
        {
            "observation_identity": observation["identity"],
            "hypothesis_identity": hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "permitted_discovery_dataset_identities": [dataset["dataset_identity"]],
            "prohibited_dataset_labels": dataset["prohibited_boundaries"],
            "contaminated_dataset_identities": hypothesis["payload"][
                "contaminated_dataset_identities"
            ],
            "preregistered_at": "2026-08-04T20:00:00Z",
            "research_definitions_locked": True,
        },
        observation,
        hypothesis,
        triage,
        specification,
    )
    binding = implementation_binding_artifact(
        repository_root=repository_root,
        preregistration=preregistration_artifact,
        specification=specification,
        implementation_callable=(
            "aml.benchmark_candidate_opening_drive_first_pullback_v001."
            "evaluate_opening_drive_first_pullback"
        ),
        reference_contract={
            "alias_strategy_id": CANDIDATE_ID,
            "reference_strategy_id": REFERENCE_STRATEGY_ID,
            "reference_strategy_identity": REFERENCE_STRATEGY_IDENTITY,
            "reference_executor_identity": REFERENCE_EXECUTOR_IDENTITY,
            "semantic_rule": "exact_long_arm_alias_no_strategy_rule_added",
        },
        source_paths=config["source_paths"],
        dataset_authorization=dataset,
    )
    inputs = conformance_inputs()
    cases = tuple(
        ConformanceCase(
            case_id=case_id,
            expected_status={
                "integrity-failure": "integrity_failure",
                "negative": "no_signal",
                "positive": "proposal",
                "unavailable": "unavailable",
            }[case_id],
            evaluate=lambda item=value: evaluate_opening_drive_first_pullback(item),
        )
        for case_id, value in sorted(inputs.items())
    )
    conformance = run_conformance(
        implementation_binding=binding,
        cases=cases,
        repeat_case_id="positive",
        no_lookahead_check=no_lookahead_conformance,
        proposal_pipeline_check=proposal_pipeline_conformance,
    )
    artifacts = {
        "observation": observation,
        "hypothesis": hypothesis,
        "triage": triage,
        "specification": specification,
        "preregistration": preregistration_artifact,
        "implementation_binding": binding,
        "conformance": conformance,
    }
    frame = _load_dataset(repository_root, dataset)
    return artifacts, frame


def execute_pipeline(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    library_path: Path,
    specification_campaign_path: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, object], dict[str, object]]:
    """Run claim-limited synthetic routing; publish no empirical conclusion."""

    artifacts, frame = _artifacts(
        repository_root=repository_root,
        config=config,
        library_path=library_path,
        specification_campaign_path=specification_campaign_path,
    )
    verify_implementation_binding(
        artifacts["implementation_binding"],
        repository_root=repository_root,
        source_paths=config["source_paths"],
        dataset_authorization=config["dataset_authorization"],
    )
    decisions = evaluate_authorized_bars(frame_to_bars(frame))
    integrity_failures = 0
    statuses = {
        status: sum(item.status == status for item in decisions)
        for status in ("no_signal", "no_trade", "proposal", "unavailable")
    }
    proposals = [item.proposal for item in decisions if item.proposal is not None]
    # The authorized fixture is pipeline-only.  Proposals, if any, are rejected
    # before economic simulation; lifecycle conformance is proven separately.
    rejected = len(proposals)
    metrics = {
        "trade_count": 0,
        "base": trade_metrics([]),
        "cost_1_5x": trade_metrics([]),
        "cost_2x": trade_metrics([]),
    }
    classification_value = classify(metrics, material_data_limitation=True)
    lineage = {
        "hypothesis_identity": artifacts["hypothesis"]["identity"],
        "specification_identity": artifacts["specification"]["identity"],
        "preregistration_identity": artifacts["preregistration"]["identity"],
        "implementation_binding_identity": artifacts["implementation_binding"]["identity"],
        "conformance_identity": artifacts["conformance"]["identity"],
        "dataset_identity": config["dataset_authorization"]["dataset_identity"],
    }
    discovery = make_artifact(
        "discovery",
        {
            **lineage,
            "evidence_class": EVIDENCE_CLASS,
            "evaluation_count": len(decisions),
            "decision_status_counts": statuses,
            "proposal_count": len(proposals),
            "accepted_trade_count": 0,
            "rejected_proposal_count": rejected,
            "rejection_reason": "synthetic_fixture_not_authorized_for_performance",
            "executor_integrity_failure_count": integrity_failures,
            "unavailable_fraction": (
                statuses["unavailable"] / len(decisions) if decisions else 1.0
            ),
            "material_data_limitation": True,
            "cost_scenario_trade_counts": {
                "base": 0,
                "cost_1_5x": 0,
                "cost_2x": 0,
            },
            "metrics": metrics,
            "proposal_audit": [
                {
                    "proposal_identity": item.proposal_identity,
                    "status": "rejected",
                    "reason": "synthetic_fixture_not_authorized_for_performance",
                }
                for item in proposals
            ],
            "trades": {"base": [], "cost_1_5x": [], "cost_2x": []},
        },
        parent_identities=tuple(lineage[key] for key in (
            "hypothesis_identity",
            "specification_identity",
            "preregistration_identity",
            "implementation_binding_identity",
            "conformance_identity",
        )),
    )
    classification_artifact = make_artifact(
        "classification",
        {
            "discovery_identity": discovery["identity"],
            "classification": classification_value,
            "classification_function": "aml.discovery_screen_v001.classify",
            "evidence_class": EVIDENCE_CLASS,
            "validation_eligible": False,
            "claim_ceiling": "pipeline_execution_only_no_empirical_edge_claim",
        },
        parent_identities=(discovery["identity"],),
    )
    return artifacts, discovery, classification_artifact


def build_bundle(
    *,
    repository_root: Path,
    config_path: Path,
    library_path: Path,
    specification_campaign_path: Path,
    output_root: Path,
) -> dict[str, object]:
    config = load_config(config_path, repository_root=repository_root)
    artifacts, discovery, classification = execute_pipeline(
        repository_root=repository_root,
        config=config,
        library_path=library_path,
        specification_campaign_path=specification_campaign_path,
    )
    archive = create_archive(
        hypothesis=artifacts["hypothesis"],
        archive_state="completed",
        reason=(
            "Executable specification pipeline verification completed with synthetic "
            "non-empirical evidence; no edge or validation claim is authorized."
        ),
        related_artifacts=(
            artifacts["observation"],
            artifacts["triage"],
            artifacts["specification"],
            artifacts["preregistration"],
            artifacts["implementation_binding"],
            artifacts["conformance"],
            discovery,
            classification,
        ),
        empirical_outcomes_accessed=False,
    )
    ordered: Sequence[Mapping[str, object]] = (
        artifacts["observation"],
        artifacts["hypothesis"],
        artifacts["triage"],
        artifacts["specification"],
        artifacts["preregistration"],
        artifacts["implementation_binding"],
        artifacts["conformance"],
        discovery,
        classification,
        archive,
    )
    manifest = write_bundle(output_root, ordered)
    verified = verify_bundle(output_root)
    return {
        "bundle_identity": manifest["identity"],
        "classification": classification["payload"]["classification"],
        "classification_identity": classification["identity"],
        "conformance_identity": artifacts["conformance"]["identity"],
        "dataset_identity": config["dataset_authorization"]["dataset_identity"],
        "discovery_identity": discovery["identity"],
        "implementation_binding_identity": artifacts["implementation_binding"]["identity"],
        "preregistration_identity": artifacts["preregistration"]["identity"],
        "specification_identity": artifacts["specification"]["identity"],
        "verified": verified["verified"],
    }
