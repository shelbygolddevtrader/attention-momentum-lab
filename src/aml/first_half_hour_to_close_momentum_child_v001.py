"""Evidence and exploratory runner for First Half-Hour To Close Momentum Child V001."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from zoneinfo import ZoneInfo

from aml.benchmark_candidate_first_half_hour_to_close_momentum_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_REVISION,
    CHILD_STRATEGY_IDENTITY,
    CHILD_VERSION,
    EXECUTOR_IDENTITY,
    EXECUTOR_REGISTRY,
    FROZEN_SPECIFICATION,
    PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    PARENT_LIBRARY_ENTRY_ID,
    PARENT_REGISTRATION_IDENTITY,
    SPECIFICATION_IDENTITY,
    conformance_bars,
    conformance_inputs,
    evaluate_first_half_hour_to_close_momentum,
    evaluation_input,
    frozen_dependency_identities,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
)
from aml.benchmark_executable_specification_runtime_v001 import (
    ConformanceCase,
    dataset_authorization_identity,
    file_hashes,
    implementation_binding_artifact,
    run_conformance,
    validate_dataset_authorization,
    verify_implementation_binding,
)
from aml.benchmark_hypothesis_library_v001 import framework_artifacts, load_library
from aml.benchmark_strategy_research_v001 import (
    canonical_hash,
    canonical_json,
    create_observation,
    create_triage,
    make_artifact,
    validate_artifact,
)
from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.exploratory_research_mode_v001 import (
    CLAIM_CEILING,
    EVIDENCE_CLASS,
    LABELS,
    MANIFEST_SCHEMA,
    LoadedPartition,
    _next_open,
    _output_path,
    _partition,
    _reject_prohibited_keys,
    _result_payload,
    _sha256,
    _strict_json,
    validate_result,
)
from aml.opening_range_expansion_continuation_v001 import (
    CANDIDATE_SPECIFIC_LABELS,
    _reject_candidate_prohibited_claims,
    candidate_prohibited_claim_contract_identity,
    candidate_structured_observation_contract_identity,
    create_structured_observation,
    validate_structured_observation,
)
from aml.professional_strategy_executor_models_v001 import EvaluationInput
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError


ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
SCHEMA = "aml.first-half-hour-to-close-momentum-child.v001"
MILESTONE_VERSION = "first-half-hour-to-close-momentum-prospective-child-v001"
EVIDENCE_MANIFEST_SCHEMA = "aml.first-half-hour-to-close-momentum-evidence-manifest.v001"
DATASET_FINGERPRINT = "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d"
DATASET_VINTAGE = "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001"
DATASET_MANIFEST_SHA256 = (
    "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b"
)
LIBRARY_IDENTITY = "6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003"
SYNTHETIC_RELATIVE_PATH = (
    "tests/fixtures/first_half_hour_to_close_momentum_child_v001/"
    "first_half_hour_to_close_momentum_synthetic.csv"
)
SOURCE_PATHS = (
    "scripts/run_first_half_hour_to_close_momentum_child_v001.py",
    "src/aml/benchmark_candidate_first_half_hour_to_close_momentum_v001.py",
    "src/aml/first_half_hour_to_close_momentum_child_v001.py",
)
FROZEN_DOWNSTREAM_PATHS = (
    "src/aml/discovery_screen_v001.py",
    "src/aml/exploratory_research_mode_v001.py",
    "src/aml/opening_range_expansion_continuation_v001.py",
    "src/aml/professional_strategy_executor_models_v001.py",
    "src/aml/professional_strategy_indicators_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
)
FROZEN_SYMBOL = "SPY"
FROZEN_SESSION_COUNT = 753
FROZEN_START_DATE = "2023-07-24"
FROZEN_END_DATE = "2026-07-23"
EVIDENCE_REQUIRED_ROLES = {
    "01-observation.json": "observation",
    "02-child-hypothesis.json": "child_hypothesis",
    "03-triage.json": "triage",
    "04-specification.json": "specification",
    "05-preregistration.json": "preregistration",
    "06-implementation-binding.json": "implementation_binding",
    "07-conformance.json": "conformance_evidence",
    "08-executor-registration.json": "executor_registration",
}
EVIDENCE_ARTIFACT_TYPES = {
    "01-observation.json": "observation",
    "02-child-hypothesis.json": "hypothesis",
    "03-triage.json": "triage",
    "04-specification.json": "specification",
    "05-preregistration.json": "preregistration",
    "06-implementation-binding.json": "implementation_binding",
    "07-conformance.json": "conformance",
    "08-executor-registration.json": "implementation_binding",
}
EXPLORATORY_RESULT_PATH = f"01-{CHILD_HYPOTHESIS_ID}.json"
EXPLORATORY_REQUIRED_ROLES = {
    EXPLORATORY_RESULT_PATH: "candidate_result",
    "run.json": "exploratory_run",
    "summary.json": "candidate_summary",
}


class FirstHalfHourToCloseMilestoneError(ValueError):
    """A candidate identity, evidence, or exploratory invariant failed."""


def required_inventory_contract() -> dict[str, object]:
    return {
        "schema_version": "aml.first-half-hour-to-close-momentum-required-inventory.v001",
        "closed_inventory": True,
        "optional_roles": [],
        "evidence": [
            {"path": path, "role": role, "cardinality": 1}
            for path, role in sorted(EVIDENCE_REQUIRED_ROLES.items())
        ],
        "exploratory": [
            {"path": path, "role": role, "cardinality": 1}
            for path, role in sorted(EXPLORATORY_REQUIRED_ROLES.items())
        ],
        "candidate_label": list(CANDIDATE_SPECIFIC_LABELS),
        "prohibited_claim_contract_identity": (
            candidate_prohibited_claim_contract_identity()
        ),
        "structured_observation_contract_identity": (
            candidate_structured_observation_contract_identity()
        ),
        "invariant": (
            "Every required canonical role must be present exactly once even when "
            "a reduced bundle is internally hash-consistent."
        ),
    }


def required_inventory_contract_identity() -> str:
    return canonical_hash(
        {
            "domain": "aml.first-half-hour-to-close-momentum-required-inventory.v001",
            "contract": required_inventory_contract(),
        }
    )


def _config_identity(value: Mapping[str, object]) -> str:
    base = {key: value[key] for key in sorted(set(value) - {"config_identity"})}
    return canonical_hash({"domain": SCHEMA, "config": base})


def _dataset_binding_identity(value: Mapping[str, object]) -> str:
    base = {key: value[key] for key in sorted(set(value) - {"binding_identity"})}
    return canonical_hash(
        {"domain": "aml.exploratory-contaminated-dataset-binding.v001", "binding": base}
    )


def finalize_config(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    synthetic = result["synthetic_dataset_authorization"]
    synthetic_base = {
        key: synthetic[key]
        for key in sorted(set(synthetic) - {"authorization_identity"})
    }
    synthetic["authorization_identity"] = dataset_authorization_identity(
        synthetic_base
    )
    exploratory = result["exploratory_dataset_binding"]
    exploratory["binding_identity"] = _dataset_binding_identity(exploratory)
    result["config_identity"] = _config_identity(result)
    return result


def default_config(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root).resolve()
    fixture = root / SYNTHETIC_RELATIVE_PATH
    value = {
        "schema_version": SCHEMA,
        "milestone_version": MILESTONE_VERSION,
        "config_identity": "0" * 64,
        "parent": {
            "library_entry_id": PARENT_LIBRARY_ENTRY_ID,
            "framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
            "registration_identity": PARENT_REGISTRATION_IDENTITY,
            "revision": 1,
            "library_identity": LIBRARY_IDENTITY,
        },
        "child": {
            "hypothesis_id": CHILD_HYPOTHESIS_ID,
            "revision": CHILD_REVISION,
            "version": CHILD_VERSION,
            "strategy_identity": CHILD_STRATEGY_IDENTITY,
        },
        "specification_identity": SPECIFICATION_IDENTITY,
        "executor_identity": EXECUTOR_IDENTITY,
        "required_inventory_contract_identity": (
            required_inventory_contract_identity()
        ),
        "source_paths": list(SOURCE_PATHS),
        "frozen_downstream_paths": list(FROZEN_DOWNSTREAM_PATHS),
        "synthetic_dataset_authorization": {
            "authorization_id": "first-half-hour-to-close-momentum-conformance-only-v001",
            "authorization_identity": "0" * 64,
            "dataset_identity": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "evidence_class": "synthetic_non_empirical",
            "file_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "prohibited_boundaries": [
                "forward validation",
                "holdout",
                "live trading",
                "olympics execution",
                "paper trading",
                "validation",
            ],
            "relative_path": SYNTHETIC_RELATIVE_PATH,
            "scope": "discovery_pipeline_conformance_only",
        },
        "exploratory_dataset_binding": {
            "binding_identity": "0" * 64,
            "binding_kind": "contaminated_exploratory_only_not_empirical_authorization",
            "dataset_fingerprint": DATASET_FINGERPRINT,
            "dataset_vintage": DATASET_VINTAGE,
            "manifest_relative_path": (
                "manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json"
            ),
            "manifest_sha256": DATASET_MANIFEST_SHA256,
            "symbols": [FROZEN_SYMBOL],
            "warmup_sessions": [],
            "evaluation_session_rule": {
                "selection": "all regular SPY sessions in the exact bound dataset",
                "start_date": FROZEN_START_DATE,
                "end_date": FROZEN_END_DATE,
                "expected_count": FROZEN_SESSION_COUNT,
            },
            "selection_rule": (
                "Every one of the 753 SPY regular sessions present in the exact "
                "content-addressed dataset, 2023-07-24 through 2026-07-23 inclusive; "
                "no outcome-based session selection and no indicator warm-up partition."
            ),
            "empirical_authorized": False,
            "contamination_labels": list(LABELS),
        },
        "policy": {
            "prospective_human_authorized_design": True,
            "parent_exact_alias_claimed": False,
            "exploratory_execution_permitted": True,
            "empirical_execution_permitted": False,
            "profitability_metrics_published": False,
            "optimization_count": 0,
            "parameter_search_count": 0,
            "validation_access_permitted": False,
            "holdout_access_permitted": False,
            "paper_or_live_trading_permitted": False,
            "frozen_downstream_modified": False,
        },
    }
    return finalize_config(value)


def validate_config(value: Mapping[str, object], repository_root: Path) -> dict[str, object]:
    expected = default_config(repository_root)
    if json.loads(canonical_json(value)) != expected:
        raise FirstHalfHourToCloseMilestoneError("candidate configuration changed")
    if value.get("config_identity") != _config_identity(value):
        raise FirstHalfHourToCloseMilestoneError("configuration identity changed")
    validate_dataset_authorization(
        value["synthetic_dataset_authorization"],
        repository_root=repository_root,
    )
    _reject_candidate_prohibited_claims(value, artifact_name="configuration.json")
    return dict(value)


def load_config(path: Path, repository_root: Path) -> dict[str, object]:
    value = _strict_json(path)
    return validate_config(value, repository_root)


def _parent_entry(
    config: Mapping[str, object], library_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    library = load_library(library_path)
    if library["library_identity"] != config["parent"]["library_identity"]:
        raise FirstHalfHourToCloseMilestoneError("library identity changed")
    entry = next(
        (
            item
            for item in library["hypotheses"]
            if item["library_entry_id"] == PARENT_LIBRARY_ENTRY_ID
        ),
        None,
    )
    if entry is None or any(
        entry[field] != config["parent"][field]
        for field in (
            "framework_hypothesis_identity",
            "registration_identity",
            "revision",
        )
    ):
        raise FirstHalfHourToCloseMilestoneError("immutable parent changed")
    sources = {item["source_id"]: item for item in library["sources"]}
    observation, hypothesis = framework_artifacts(entry, sources)
    if hypothesis["identity"] != PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY:
        raise FirstHalfHourToCloseMilestoneError("parent identity does not reproduce")
    return observation, hypothesis


def _child_payload() -> dict[str, object]:
    return {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": CHILD_REVISION,
        "parent_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
        "title": "Positive first-half-hour momentum held toward the close on SPY",
        "market_assumption": (
            "A sufficiently strong positive market move during the first regular "
            "half-hour can persist through the remainder of the session."
        ),
        "mechanism": (
            "One SPY position entered at 10:00 after a positive 0.50 percent first-"
            "half-hour return tests lower-turnover intraday directional persistence."
        ),
        "required_evidence": [
            "exact consecutive 09:30 through 09:59 SPY minute OHLCV",
            "exact 10:00 entry bar open",
            "complete regular-session lifecycle through frozen liquidation",
        ],
        "expected_edge": (
            "The prospectively defined mechanism may continue; exploratory exercise "
            "cannot establish whether that expectation is correct."
        ),
        "invalidation_conditions": [
            "first-half-hour return below positive 0.50 percent",
            "signal window or 10:00 entry bar incomplete",
            "cost-adjusted entry not strictly above the first-half-hour low stop",
            "required input or provenance unavailable",
        ],
        "known_risks": [
            "adverse selection",
            "morning direction reverses over the remaining session",
            "wide first-half-hour range constrains position size",
            "modeled costs exceed any gross effect",
        ],
        "required_indicators": [
            "first-half-hour SPY return",
            "first-half-hour SPY low",
            "XNYS regular-session clock",
        ],
        "expected_holding_period": "10:00 entry through the frozen session liquidation unless stopped",
        "expected_market_regime": "persistent market-direction session",
        "expected_failure_modes": list(FROZEN_SPECIFICATION["expected_failure_modes"]),
        "taxonomy": ["momentum", "persistence", "time-of-day"],
        "contaminated_dataset_identities": [DATASET_FINGERPRINT],
        "multiple_testing_family": "intraday-market-persistence-v001",
    }


def _lifecycle_conformance() -> dict[str, bool]:
    bars = conformance_bars()
    result = evaluate_first_half_hour_to_close_momentum(
        evaluation_input(bars[:30], next_bar=bars[30])
    )
    if result.proposal is None:
        return {
            "lifecycle_session_liquidation": False,
            "stop_target_collision_precedence": False,
        }
    calendar = {
        bars[0].session: CalendarSession(
            bars[0].session,
            datetime.combine(bars[0].session, time(9, 30), NY),
            datetime.combine(bars[0].session, time(16, 0), NY),
            False,
        )
    }
    collision = list(bars)
    collision[30] = replace(collision[30], low=90.0)
    collision_trades, collision_rejections = simulate_strategy(
        "five_minute_orb_long_v002",
        [result.proposal],
        {("SPY", bars[0].session): tuple(collision)},
        calendar,
    )
    session_trades, session_rejections = simulate_strategy(
        "five_minute_orb_long_v002",
        [result.proposal],
        {("SPY", bars[0].session): bars},
        calendar,
    )
    return {
        "lifecycle_session_liquidation": (
            not session_rejections
            and len(session_trades) == 1
            and session_trades[0].exit_reason == "session_liquidation"
        ),
        "stop_target_collision_precedence": (
            not collision_rejections
            and len(collision_trades) == 1
            and collision_trades[0].exit_reason == "intrabar_stop"
        ),
    }


def build_evidence(
    *, repository_root: Path, config: Mapping[str, object], library_path: Path
) -> dict[str, dict[str, object]]:
    validate_config(config, repository_root)
    _, parent = _parent_entry(config, library_path)
    observation = create_observation(
        {
            "observation_id": "first-half-hour-to-close-momentum-prospective-design-v001",
            "title": "Prospective human-authorized first-half-hour-to-close-momentum design",
            "source_kind": "human_authorized_design_without_outcome_access",
            "source_references": [
                "config/benchmark_hypothesis_library_v001.json",
                "src/aml/professional_strategy_indicators_v001.py",
                "src/aml/professional_strategy_lifecycle_v001.py",
            ],
            "source_dataset_identities": [],
            "observed_behavior": (
                "The broad parent leaves executable rules open; the human-authorized "
                "child freezes one simple OHLCV-only experiment prospectively."
            ),
            "recorded_at": "2026-08-07T18:00:00Z",
        }
    )
    child = make_artifact(
        "hypothesis",
        _child_payload(),
        parent_identities=(parent["identity"], observation["identity"]),
    )
    triage = create_triage(
        {
            "hypothesis_identity": child["identity"],
            "disposition": "admit",
            "duplicate_signature": canonical_hash(
                {
                    "domain": "aml.first-half-hour-to-close-momentum-triage.v001",
                    "child": CHILD_HYPOTHESIS_ID,
                }
            ),
            "duplicate_hypothesis_identities": [],
            "priority_vector": {
                "mechanism_plausibility": 2,
                "supporting_evidence": 1,
                "expected_frequency": 2,
                "data_readiness": 3,
                "distinctness": 3,
                "falsification_value": 3,
                "engineering_cost": 2,
                "contamination_risk": 1,
            },
            "reasons": [
                "Every rule was fixed before candidate outcome access.",
                "Only frozen OHLCV indicators and lifecycle primitives are reused.",
                "The child adds a lower-turnover market-persistence mechanism.",
            ],
        },
        child,
    )
    specification = make_artifact(
        "specification",
        {
            "hypothesis_identity": child["identity"],
            "canonical_specification_identity": SPECIFICATION_IDENTITY,
            "rules": FROZEN_SPECIFICATION,
        },
        parent_identities=(child["identity"], triage["identity"]),
    )
    preregistration = make_artifact(
        "preregistration",
        {
            "observation_identity": observation["identity"],
            "hypothesis_identity": child["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "canonical_specification_identity": SPECIFICATION_IDENTITY,
            "preregistered_at": "2026-08-07T18:00:00Z",
            "research_definitions_locked": True,
            "permitted_empirical_dataset_identities": [],
            "contaminated_exploratory_dataset_identities": [DATASET_FINGERPRINT],
            "claim_ceiling": "exploratory_engineering_diagnostics_only",
            "labels": [*LABELS, *CANDIDATE_SPECIFIC_LABELS],
            "prohibited_boundaries": [
                "capital allocation",
                "forward validation",
                "holdout",
                "live trading",
                "paper trading",
                "profitability conclusions",
                "validation",
            ],
        },
        parent_identities=(
            observation["identity"],
            child["identity"],
            triage["identity"],
            specification["identity"],
        ),
    )
    reference = {
        "binding_kind": "candidate_specific_evaluator_reusing_frozen_primitives",
        "strategy_identity": CHILD_STRATEGY_IDENTITY,
        "executor_identity": EXECUTOR_IDENTITY,
        "specification_identity": SPECIFICATION_IDENTITY,
        "dependency_identities": frozen_dependency_identities(),
    }
    binding = implementation_binding_artifact(
        repository_root=repository_root,
        preregistration=preregistration,
        specification=specification,
        implementation_callable=(
            "aml.benchmark_candidate_first_half_hour_to_close_momentum_v001."
            "evaluate_first_half_hour_to_close_momentum"
        ),
        reference_contract=reference,
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    inputs = conformance_inputs()
    conformance = run_conformance(
        implementation_binding=binding,
        cases=(
            ConformanceCase(
                "duplicate-signal",
                "no_signal",
                lambda: evaluate_first_half_hour_to_close_momentum(
                    inputs["duplicate-signal"]
                ),
            ),
            ConformanceCase(
                "integrity-failure",
                "integrity_failure",
                lambda: evaluate_first_half_hour_to_close_momentum(
                    inputs["integrity-failure"]
                ),
                (ExecutorIntegrityError,),
            ),
            ConformanceCase(
                "missing-entry",
                "unavailable",
                lambda: evaluate_first_half_hour_to_close_momentum(
                    inputs["missing-entry"]
                ),
            ),
            ConformanceCase(
                "missing-open",
                "integrity_failure",
                lambda: evaluate_first_half_hour_to_close_momentum(
                    inputs["missing-open"]
                ),
                (ExecutorIntegrityError,),
            ),
            ConformanceCase(
                "positive",
                "proposal",
                lambda: evaluate_first_half_hour_to_close_momentum(inputs["positive"]),
            ),
            ConformanceCase(
                "threshold-absent",
                "no_signal",
                lambda: evaluate_first_half_hour_to_close_momentum(
                    inputs["threshold-absent"]
                ),
            ),
        ),
        repeat_case_id="positive",
        no_lookahead_check=no_lookahead_conformance,
        proposal_pipeline_check=proposal_pipeline_conformance,
    )
    lifecycle_checks = _lifecycle_conformance()
    conformance = make_artifact(
        "conformance",
        {**conformance["payload"], **lifecycle_checks},
        parent_identities=conformance["parent_identities"],
    )
    registration = make_artifact(
        "implementation_binding",
        {
            "binding_kind": "executor_registration",
            "child_hypothesis_id": CHILD_HYPOTHESIS_ID,
            "implementation_binding_identity": binding["identity"],
            "conformance_identity": conformance["identity"],
            "implementation_callable": (
                "aml.benchmark_candidate_first_half_hour_to_close_momentum_v001."
                "evaluate_first_half_hour_to_close_momentum"
            ),
            "registry_keys": sorted(EXECUTOR_REGISTRY),
            "strategy_identity": CHILD_STRATEGY_IDENTITY,
            "executor_identity": EXECUTOR_IDENTITY,
            "empirical_execution_permitted": False,
            "exploratory_execution_permitted": True,
        },
        parent_identities=(binding["identity"], conformance["identity"]),
    )
    artifacts = {
        "01-observation.json": observation,
        "02-child-hypothesis.json": child,
        "03-triage.json": triage,
        "04-specification.json": specification,
        "05-preregistration.json": preregistration,
        "06-implementation-binding.json": binding,
        "07-conformance.json": conformance,
        "08-executor-registration.json": registration,
    }
    verify_evidence_objects(artifacts, repository_root, config)
    return artifacts


def verify_evidence_objects(
    artifacts: Mapping[str, Mapping[str, object]],
    repository_root: Path,
    config: Mapping[str, object],
) -> None:
    if set(artifacts) != set(EVIDENCE_REQUIRED_ROLES):
        raise FirstHalfHourToCloseMilestoneError("evidence inventory changed")
    validate_config(config, repository_root)
    for name, artifact_type in EVIDENCE_ARTIFACT_TYPES.items():
        validate_artifact(artifacts[name], artifact_type)
        _reject_prohibited_keys(artifacts[name])
    verify_implementation_binding(
        artifacts["06-implementation-binding.json"],
        repository_root=repository_root,
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    conformance = artifacts["07-conformance.json"]
    if (
        conformance["payload"].get("all_checks_passed") is not True
        or conformance["payload"].get("no_lookahead") is not True
        or conformance["payload"].get("proposal_pipeline") is not True
        or conformance["payload"].get("stop_target_collision_precedence") is not True
        or conformance["payload"].get("lifecycle_session_liquidation") is not True
    ):
        raise FirstHalfHourToCloseMilestoneError("conformance is incomplete")
    registration = artifacts["08-executor-registration.json"]
    if registration["payload"].get("registry_keys") != [CHILD_HYPOTHESIS_ID]:
        raise FirstHalfHourToCloseMilestoneError("executor registration changed")
    if registration["payload"].get("implementation_binding_identity") != artifacts[
        "06-implementation-binding.json"
    ]["identity"] or registration["payload"].get("conformance_identity") != conformance[
        "identity"
    ]:
        raise FirstHalfHourToCloseMilestoneError("executor lineage changed")


def _evidence_manifest(
    artifacts: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    files = [
        {
            "path": name,
            "role": EVIDENCE_REQUIRED_ROLES[name],
            "identity": value["identity"],
            "sha256": hashlib.sha256(canonical_json(value)).hexdigest(),
        }
        for name, value in sorted(artifacts.items())
    ]
    base = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA,
        "milestone_version": MILESTONE_VERSION,
        "specification_identity": SPECIFICATION_IDENTITY,
        "required_inventory_contract_identity": (
            required_inventory_contract_identity()
        ),
        "candidate_prohibited_claim_contract_identity": (
            candidate_prohibited_claim_contract_identity()
        ),
        "candidate_structured_observation_contract_identity": (
            candidate_structured_observation_contract_identity()
        ),
        "candidate_artifact_role": "evidence_manifest",
        "files": files,
        "immutable": True,
        "empirical_result_count": 0,
    }
    return {**base, "identity": canonical_hash(base)}


def write_evidence(
    output_root: Path, artifacts: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    root = Path(output_root)
    if root.exists():
        raise FirstHalfHourToCloseMilestoneError("evidence output already exists")
    root.mkdir(parents=True)
    for name, artifact in sorted(artifacts.items()):
        (root / name).write_bytes(canonical_json(artifact))
    manifest = _evidence_manifest(artifacts)
    (root / "manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def verify_evidence_directory(
    output_root: Path,
    *, repository_root: Path,
    config: Mapping[str, object],
) -> dict[str, object]:
    root = Path(output_root)
    manifest = _strict_json(root / "manifest.json")
    identity = manifest.get("identity")
    base = {key: value for key, value in manifest.items() if key != "identity"}
    if identity != canonical_hash(base) or not manifest.get("files"):
        raise FirstHalfHourToCloseMilestoneError("evidence manifest changed")
    pairs = [
        (item.get("path"), item.get("role")) for item in manifest.get("files", [])
    ]
    if pairs != sorted(EVIDENCE_REQUIRED_ROLES.items()):
        raise FirstHalfHourToCloseMilestoneError("evidence role inventory changed")
    artifacts: dict[str, Mapping[str, object]] = {}
    expected = {"manifest.json"}
    for item in manifest["files"]:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise FirstHalfHourToCloseMilestoneError("unsafe evidence path")
        path = root / relative
        if not path.is_file() or path.is_symlink() or _sha256(path) != item["sha256"]:
            raise FirstHalfHourToCloseMilestoneError("evidence file hash changed")
        artifact = _strict_json(path)
        if artifact.get("identity") != item["identity"]:
            raise FirstHalfHourToCloseMilestoneError("evidence identity changed")
        artifacts[relative.as_posix()] = artifact
        expected.add(relative.as_posix())
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise FirstHalfHourToCloseMilestoneError("evidence directory is not closed")
    verify_evidence_objects(artifacts, repository_root, config)
    return {
        "evidence_manifest_identity": identity,
        "specification_identity": SPECIFICATION_IDENTITY,
        "verified": True,
    }


def _load_partitions(
    dataset_root: Path, binding: Mapping[str, object]
) -> tuple[dict[tuple[str, str], LoadedPartition], list[dict[str, object]]]:
    partitions: dict[tuple[str, str], LoadedPartition] = {}
    records: list[dict[str, object]] = []
    rule = binding["evaluation_session_rule"]
    session_dirs = sorted(
        item.parent.parent.name
        for item in (dataset_root / "sip" / FROZEN_SYMBOL).glob(
            "*/processed/regular_1min.csv"
        )
    )
    if (
        len(session_dirs) != rule["expected_count"]
        or session_dirs[0] != rule["start_date"]
        or session_dirs[-1] != rule["end_date"]
        or len(set(session_dirs)) != len(session_dirs)
    ):
        raise FirstHalfHourToCloseMilestoneError("frozen SPY session universe changed")
    for session in session_dirs:
        item = _partition(
            dataset_root,
            symbol=FROZEN_SYMBOL,
            session=session,
            dataset_fingerprint=binding["dataset_fingerprint"],
        )
        partitions[(FROZEN_SYMBOL, session)] = item
        records.append(
            {
                "metadata_sha256": item.metadata_sha256,
                "processed_sha256": item.processed_sha256,
                "session": item.session.isoformat(),
                "symbol": item.symbol,
                "warning_codes": list(item.warning_codes),
            }
        )
    return partitions, records


def _evaluate_exploratory(
    partitions: Mapping[tuple[str, str], LoadedPartition],
    binding: Mapping[str, object],
) -> tuple[dict[str, int], Counter[str], Counter[str], list[object], list[dict[str, object]]]:
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposals: list[object] = []
    integrity: list[dict[str, object]] = []
    eligible_decisions = 0
    for _, partition in sorted(partitions.items()):
        opened = datetime.combine(partition.session, time(9, 30), NY)
        closed = partition.bars[-1].timestamp + timedelta(minutes=1)
        if len(partition.bars) < 31:
            statuses["unavailable"] += 1
            reasons["unavailable:first_half_hour_or_entry_bar_missing"] += 1
            continue
        decision_bar = partition.bars[29]
        try:
            result = evaluate_first_half_hour_to_close_momentum(
                EvaluationInput(
                    symbol_bars=partition.bars[:30],
                    next_bar=_next_open(partition.bars, 29),
                    scheduled_open=opened,
                    scheduled_close=closed,
                    decision_cutoff=decision_bar.timestamp + timedelta(minutes=1),
                    halt_coverage_complete=True,
                    corporate_action_coverage_complete=True,
                    corporate_action_lineage_valid=True,
                    halt_manifest_identity="exploratory-retrospective-halt-coverage",
                    corporate_action_manifest_identity=(
                        "exploratory-retrospective-coverage-contaminated"
                    ),
                    calendar_identity="exploratory-source-session-boundary",
                )
            )
        except ExecutorIntegrityError as exc:
            statuses["integrity_failure"] += 1
            reasons["integrity_failure:executor_integrity_rejected"] += 1
            integrity.append(
                (
                    {
                        "session": partition.session.isoformat(),
                        "symbol": partition.symbol,
                        "timestamp": decision_bar.timestamp.isoformat(),
                        "reason": str(exc),
                    }
                )
            )
            continue
        statuses[result.status] += 1
        for reason in result.reason_codes or ("none",):
            reasons[f"{result.status}:{reason}"] += 1
        if result.status not in {"integrity_failure", "unavailable"}:
            eligible_decisions += 1
        if result.proposal is not None:
            proposals.append(result.proposal)
    bars_by_key = {
        (partition.symbol, partition.session): partition.bars
        for partition in partitions.values()
    }
    calendar = {
        partition.session: CalendarSession(
            partition.session,
            datetime.combine(partition.session, time(9, 30), NY),
            partition.bars[-1].timestamp + timedelta(minutes=1),
            len(partition.bars) < 390,
        )
        for partition in partitions.values()
    }
    completed, rejections = simulate_strategy(
        "five_minute_orb_long_v002", proposals, bars_by_key, calendar
    )
    if len(proposals) != len(completed) + len(rejections):
        raise FirstHalfHourToCloseMilestoneError("proposal reconciliation failed")
    counts = {
        "causal_decision_count": sum(statuses.values()),
        "eligible_decision_count": eligible_decisions,
        "evaluated_partition_count": len(partitions),
        "executed_trade_count": len(completed),
        "integrity_failure_count": statuses["integrity_failure"],
        "no_signal_count": statuses["no_signal"],
        "partition_inspected_count": len(partitions),
        "proposal_count": len(proposals),
        "rejected_proposal_count": len(rejections),
        "trigger_count": len(proposals) + statuses["no_trade"],
        "unavailable_event_count": statuses["unavailable"],
        "warmup_partition_count": 0,
    }
    return counts, statuses, reasons, proposals, integrity


def _observations(counts: Mapping[str, int]) -> list[dict[str, object]]:
    values = [
        create_structured_observation(
            "RECONCILIATION",
            "candidate_result",
            "RECONCILED",
            "COUNTS_RECONCILED",
        ),
        create_structured_observation(
            "NO_SIGNAL_REASON",
            "candidate_result",
            "NO_SIGNAL",
            "CONDITION_NOT_MET",
        ),
    ]
    if counts["proposal_count"]:
        values.append(
            create_structured_observation(
                "EVALUATOR_PATH",
                "frozen_evaluator",
                "EXERCISED",
                "PROPOSAL_EMITTED",
            )
        )
    else:
        values.append(
            create_structured_observation(
                "EVALUATOR_PATH",
                "frozen_evaluator",
                "NOT_EXERCISED",
                "NO_PROPOSAL_EMITTED",
            )
        )
    if counts["integrity_failure_count"]:
        values.append(
            create_structured_observation(
                "INTEGRITY_BEHAVIOR",
                "proposal_lifecycle",
                "INTEGRITY_FAILURE",
                "INTEGRITY_REJECTED",
            )
        )
    return sorted(values, key=lambda item: str(item["identity"]))


def _source_hashes(repository_root: Path) -> dict[str, str]:
    return file_hashes(
        repository_root, sorted([*SOURCE_PATHS, *FROZEN_DOWNSTREAM_PATHS])
    )


def run_bounded_exploratory(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    evidence_artifacts: Mapping[str, Mapping[str, object]],
    dataset_root: Path,
    output_root: Path,
) -> dict[str, object]:
    validate_config(config, repository_root)
    verify_evidence_objects(evidence_artifacts, repository_root, config)
    evidence_manifest = _evidence_manifest(evidence_artifacts)
    binding = config["exploratory_dataset_binding"]
    dataset = Path(dataset_root).resolve()
    if dataset.name != binding["dataset_vintage"]:
        raise FirstHalfHourToCloseMilestoneError("dataset vintage changed")
    manifest_path = repository_root / str(binding["manifest_relative_path"])
    if _sha256(manifest_path) != binding["manifest_sha256"]:
        raise FirstHalfHourToCloseMilestoneError("dataset manifest hash changed")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("dataset_fingerprint_sha256") != DATASET_FINGERPRINT:
        raise FirstHalfHourToCloseMilestoneError("dataset fingerprint changed")
    partitions, partition_records = _load_partitions(dataset, binding)
    counts, statuses, reasons, _, integrity = _evaluate_exploratory(
        partitions, binding
    )
    source_sha256 = _source_hashes(repository_root)
    run_identity = canonical_hash(
        {
            "domain": "aml.first-half-hour-to-close-momentum-exploratory-run.v001",
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "partitions": partition_records,
            "source_tree_identity": canonical_hash(
                {
                    "domain": "aml.first-half-hour-to-close-momentum-source-tree.v001",
                    "source_sha256": source_sha256,
                }
            ),
        }
    )
    child_identity = evidence_artifacts["02-child-hypothesis.json"]["identity"]
    registration_identity = evidence_artifacts["08-executor-registration.json"][
        "identity"
    ]
    base = _result_payload(
        binding={
            "evaluator_binding": (
                "aml.benchmark_candidate_first_half_hour_to_close_momentum_v001."
                "evaluate_first_half_hour_to_close_momentum"
            ),
            "framework_hypothesis_identity": child_identity,
            "library_entry_id": CHILD_HYPOTHESIS_ID,
            "registration_identity": registration_identity,
        },
        counts=counts,
        decision_counts=statuses,
        decision_reason_counts=reasons,
        partition_count=counts["evaluated_partition_count"],
        warning_codes=[
            "CONTAMINATED_PARENT_DATASET",
            "POINT_IN_TIME_CORPORATE_ACTION_LINEAGE_UNPROVEN",
            "PROVIDER_FEED_IDENTITY_NOT_ECHOED",
            "WRITTEN_LICENSE_RETENTION_EVIDENCE_MISSING",
        ],
        missing_fields=(),
        status=(
            "EXPLORATORY_DIAGNOSTIC_ONLY"
            if counts["integrity_failure_count"]
            else "EXPLORATORY_EXERCISED"
        ),
    )
    result_base = {key: value for key, value in base.items() if key != "identity"}
    observations = _observations(counts)
    result_base["qualitative_observations"] = observations
    result_base["observation_count"] = len(observations)
    result_base["observation_identities"] = [item["identity"] for item in observations]
    result_base["implementation_notes"] = [
        "CANDIDATE_EVALUATOR_BOUND",
        "FROZEN_COMPONENTS_REUSED",
    ]
    result_base["candidate_specific_labels"] = list(CANDIDATE_SPECIFIC_LABELS)
    result_base["candidate_prohibited_claim_contract_identity"] = (
        candidate_prohibited_claim_contract_identity()
    )
    result_base["candidate_structured_observation_contract_identity"] = (
        candidate_structured_observation_contract_identity()
    )
    result_base["required_inventory_contract_identity"] = (
        required_inventory_contract_identity()
    )
    result_base["candidate_artifact_role"] = "candidate_result"
    result_base["run_identity"] = run_identity
    result_base["config_identity"] = config["config_identity"]
    result_base["dataset_binding_identity"] = binding["binding_identity"]
    result_base["evidence_manifest_identity"] = evidence_manifest["identity"]
    result_base["integrity_diagnostic_count"] = len(integrity)
    result = {**result_base, "identity": canonical_hash(result_base)}
    validate_result(result)
    for observation in observations:
        validate_structured_observation(observation)
    _reject_candidate_prohibited_claims(result, artifact_name="candidate-result.json")
    target = _output_path(output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".first-half-hour-to-close-momentum-v001-", dir=target.parent))
    try:
        result_path = staging / EXPLORATORY_RESULT_PATH
        result_path.write_bytes(canonical_json(result))
        summary_base = {
            "schema_version": "aml.exploratory-research-summary.v001",
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_artifact_role": "candidate_summary",
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "required_inventory_contract_identity": (
                required_inventory_contract_identity()
            ),
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "result_identity": result["identity"],
            "result_path": result_path.name,
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "counts": counts,
            "decision_status_counts": dict(sorted(statuses.items())),
            "decision_reason_counts": dict(sorted(reasons.items())),
            "observation_count": len(observations),
            "observation_identities": [item["identity"] for item in observations],
            "source_tree_identity": canonical_hash(
                {
                    "domain": "aml.first-half-hour-to-close-momentum-source-tree.v001",
                    "source_sha256": source_sha256,
                }
            ),
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        _reject_prohibited_keys(summary_base)
        summary = {**summary_base, "identity": canonical_hash(summary_base)}
        summary_path = staging / "summary.json"
        summary_path.write_bytes(canonical_json(summary))
        run_base = {
            "schema_version": "aml.exploratory-research-summary.v001",
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_artifact_role": "exploratory_run",
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "required_inventory_contract_identity": (
                required_inventory_contract_identity()
            ),
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "result_references": [
                {"path": result_path.name, "identity": result["identity"]}
            ],
            "summary_reference": {
                "path": summary_path.name,
                "identity": summary["identity"],
            },
            "counts": counts,
            "observation_count": len(observations),
            "observation_identities": [item["identity"] for item in observations],
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        _reject_prohibited_keys(run_base)
        run = {**run_base, "identity": canonical_hash(run_base)}
        run_path = staging / "run.json"
        run_path.write_bytes(canonical_json(run))
        files = [
            {
                "path": result_path.name,
                "role": "candidate_result",
                "identity": result["identity"],
                "sha256": _sha256(result_path),
            },
            {
                "path": run_path.name,
                "role": "exploratory_run",
                "identity": run["identity"],
                "sha256": _sha256(run_path),
            },
            {
                "path": summary_path.name,
                "role": "candidate_summary",
                "identity": summary["identity"],
                "sha256": _sha256(summary_path),
            },
        ]
        manifest_base = {
            "schema_version": MANIFEST_SCHEMA,
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_artifact_role": "exploratory_manifest",
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "required_inventory_contract_identity": (
                required_inventory_contract_identity()
            ),
            "run_identity": run_identity,
            "plan_identity": config["config_identity"],
            "write_once": True,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        manifest = {**manifest_base, "identity": canonical_hash(manifest_base)}
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verified = verify_exploratory_bundle(
        target,
        repository_root=repository_root,
        config=config,
        evidence_root=repository_root / "manifests/first_half_hour_to_close_momentum_child_v001",
    )
    return {
        "run_identity": run_identity,
        "manifest_identity": verified["manifest_identity"],
        "evidence_manifest_identity": evidence_manifest["identity"],
        "counts": counts,
        "partition_count": len(partition_records),
        "output_root": str(target),
        "verified": True,
    }


def verify_exploratory_bundle(
    path: Path,
    *,
    repository_root: Path,
    config: Mapping[str, object],
    evidence_root: Path,
) -> dict[str, object]:
    verify_evidence_directory(
        evidence_root, repository_root=repository_root, config=config
    )
    root = Path(path).resolve()
    manifest = _strict_json(root / "manifest.json")
    identity = manifest.get("identity")
    base = {key: value for key, value in manifest.items() if key != "identity"}
    if identity != canonical_hash(base):
        raise FirstHalfHourToCloseMilestoneError("exploratory manifest identity changed")
    if manifest.get("labels") != list(LABELS) or manifest.get(
        "candidate_specific_labels"
    ) != list(CANDIDATE_SPECIFIC_LABELS):
        raise FirstHalfHourToCloseMilestoneError("exploratory labels changed")
    if manifest.get("required_inventory_contract_identity") != (
        required_inventory_contract_identity()
    ):
        raise FirstHalfHourToCloseMilestoneError("inventory contract changed")
    pairs = [(item.get("path"), item.get("role")) for item in manifest.get("files", [])]
    if pairs != sorted(EXPLORATORY_REQUIRED_ROLES.items()):
        raise FirstHalfHourToCloseMilestoneError("exploratory inventory changed")
    artifacts: dict[str, Mapping[str, object]] = {}
    expected = {"manifest.json"}
    for item in manifest["files"]:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise FirstHalfHourToCloseMilestoneError("unsafe exploratory path")
        artifact_path = root / relative
        if (
            not artifact_path.is_file()
            or artifact_path.is_symlink()
            or _sha256(artifact_path) != item.get("sha256")
        ):
            raise FirstHalfHourToCloseMilestoneError("exploratory artifact changed")
        artifact = _strict_json(artifact_path)
        if artifact.get("identity") != item.get("identity"):
            raise FirstHalfHourToCloseMilestoneError("exploratory identity changed")
        if artifact.get("labels") != list(LABELS) or artifact.get(
            "candidate_specific_labels"
        ) != list(CANDIDATE_SPECIFIC_LABELS):
            raise FirstHalfHourToCloseMilestoneError("artifact labels changed")
        _reject_candidate_prohibited_claims(
            artifact, artifact_name=relative.as_posix()
        )
        artifacts[str(item["role"])] = artifact
        expected.add(relative.as_posix())
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file()
    }
    if actual != expected:
        raise FirstHalfHourToCloseMilestoneError("exploratory directory is not closed")
    result = artifacts["candidate_result"]
    validate_result(result)
    observations = result.get("qualitative_observations")
    if not isinstance(observations, list) or not observations:
        raise FirstHalfHourToCloseMilestoneError("structured observations missing")
    validated = [validate_structured_observation(item) for item in observations]
    observation_ids = [item["identity"] for item in validated]
    if (
        result.get("observation_count") != len(validated)
        or result.get("observation_identities") != observation_ids
    ):
        raise FirstHalfHourToCloseMilestoneError("observation reconciliation changed")
    summary = artifacts["candidate_summary"]
    run = artifacts["exploratory_run"]
    if (
        summary.get("result_identity") != result["identity"]
        or run.get("result_references")
        != [{"path": EXPLORATORY_RESULT_PATH, "identity": result["identity"]}]
        or run.get("summary_reference")
        != {"path": "summary.json", "identity": summary["identity"]}
        or result.get("counts") != summary.get("counts")
        or result.get("counts") != run.get("counts")
        or result.get("run_identity") != manifest.get("run_identity")
    ):
        raise FirstHalfHourToCloseMilestoneError("exploratory lineage changed")
    counts = result["counts"]
    if counts["proposal_count"] != (
        counts["executed_trade_count"] + counts["rejected_proposal_count"]
    ):
        raise FirstHalfHourToCloseMilestoneError("proposal counts do not reconcile")
    return {"manifest_identity": identity, "verified": True}
