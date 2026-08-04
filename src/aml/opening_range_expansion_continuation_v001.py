"""Opening Range Expansion Continuation V001 research milestone.

This module owns a prospectively frozen child specification, exact reference
binding, conformance evidence, executor registration, and a claim-limited
exploratory adapter.  Frozen evaluators, lifecycle, publication, discovery,
Olympics, and governance code remain unchanged.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from zoneinfo import ZoneInfo

from aml.benchmark_candidate_opening_range_expansion_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_REVISION,
    CHILD_VERSION,
    EXECUTOR_REGISTRY,
    PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    PARENT_LIBRARY_ENTRY_ID,
    PARENT_REGISTRATION_IDENTITY,
    REFERENCE_EXECUTOR_IDENTITY,
    REFERENCE_LIFECYCLE_IDENTITY,
    REFERENCE_STRATEGY_ID,
    REFERENCE_STRATEGY_IDENTITY,
    conformance_inputs,
    evaluate_opening_range_expansion,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
    verify_reference_binding,
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
    verify_bundle,
)
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HistoricalClockVolume,
)
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError


ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
SCHEMA = "aml.opening-range-expansion-continuation.v001"
MILESTONE_VERSION = "opening-range-expansion-continuation-v001"
EVIDENCE_MANIFEST_SCHEMA = "aml.opening-range-expansion-evidence-manifest.v001"
EXPLORATORY_SUMMARY_SCHEMA = "aml.exploratory-research-summary.v001"
HASH = re.compile(r"^[0-9a-f]{64}$")
LIBRARY_IDENTITY = "6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003"
DATASET_FINGERPRINT = "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d"
DATASET_MANIFEST_SHA256 = (
    "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b"
)
DATASET_VINTAGE = "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001"
SYNTHETIC_RELATIVE_PATH = (
    "tests/fixtures/opening_range_expansion_continuation_v001/orb_synthetic.csv"
)
SOURCE_PATHS = (
    "scripts/run_opening_range_expansion_continuation_v001.py",
    "src/aml/benchmark_candidate_opening_range_expansion_v001.py",
    "src/aml/opening_range_expansion_continuation_v001.py",
)
FROZEN_DOWNSTREAM_PATHS = (
    "src/aml/discovery_screen_v001.py",
    "src/aml/exploratory_research_mode_v001.py",
    "src/aml/professional_strategy_executor_models_v001.py",
    "src/aml/professional_strategy_executors_v001.py",
    "src/aml/professional_strategy_indicators_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
)
WARMUP_SESSIONS = (
    "2023-07-24",
    "2023-07-25",
    "2023-07-26",
    "2023-07-27",
    "2023-07-28",
    "2023-07-31",
    "2023-08-01",
    "2023-08-02",
    "2023-08-03",
    "2023-08-04",
    "2023-08-07",
    "2023-08-08",
    "2023-08-09",
    "2023-08-10",
    "2023-08-11",
    "2023-08-14",
    "2023-08-15",
    "2023-08-16",
    "2023-08-17",
    "2023-08-18",
)
EVALUATION_SESSIONS = (
    "2023-08-21",
    "2023-08-22",
    "2023-08-23",
    "2023-08-24",
    "2023-08-25",
)
SYMBOLS = ("AAPL", "AMD", "NVDA", "PLTR", "TSLA")


class OpeningRangeExpansionError(ValueError):
    """A specification, binding, conformance, or exploratory invariant failed."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.opening-range-expansion-executable-specification.v001",
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_version": CHILD_VERSION,
    "parent_library_entry_id": PARENT_LIBRARY_ENTRY_ID,
    "parent_framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    "revision": CHILD_REVISION,
    "ambiguity_resolution": {
        "action": "new_child_hypothesis",
        "reason": (
            "The immutable parent leaves direction, range duration, thresholds, and "
            "lifecycle values unresolved; the child adopts one already-frozen contract "
            "without modifying the parent."
        ),
        "source_supported_interpretation": (
            "Exact semantic alias of five_minute_orb_long_v002; no alternative rule."
        ),
    },
    "market_assumption": (
        "A completed five-minute opening range summarizes early price discovery; a "
        "participation-confirmed upside close beyond that frozen range can continue."
    ),
    "economic_mechanism": (
        "The range break may trigger stops and attract directional participation."
    ),
    "direction": "long_only",
    "session": {
        "calendar": "XNYS",
        "segment": "regular",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "scheduled_open": "09:30 America/New_York",
        "normal_scheduled_close": "16:00 America/New_York",
    },
    "opening_range": {
        "duration_complete_bars": 5,
        "bar_labels": ["09:30", "09:31", "09:32", "09:33", "09:34"],
        "complete_at": "09:35",
        "high": "maximum unrounded high of the exact five bars",
        "low": "minimum unrounded low of the exact five bars",
        "equal_extreme_tie": "earliest timestamp",
        "realized_volatility_proxy": (
            "unrounded range high minus unrounded range low; recorded through the "
            "bound high/low snapshots and not used as an additional eligibility gate"
        ),
    },
    "eligibility": {
        "decision_close_minimum": 2.0,
        "decision_close_maximum": 500.0,
        "post_halt_signal_blocked": True,
        "maximum_entries_per_symbol_session": 2,
        "cooldown_complete_bars": 15,
    },
    "expansion": {
        "definition": "completed decision-bar close strictly above unrounded range high",
        "observation_window": "09:35 through 10:59 inclusive",
        "range_invalidation": (
            "any post-range completed close below unrounded range low before trigger"
        ),
    },
    "volume_confirmation": {
        "indicator": "same_clock_volume_median20_sessions_v002",
        "history": (
            "twenty most recent prior eligible complete non-early-close non-halt sessions"
        ),
        "baseline": "median volume at the identical minute label",
        "ratio": "decision-bar volume divided by baseline",
        "minimum_ratio_inclusive": 1.5,
        "point_in_time_rule": "only sessions strictly before the decision session",
    },
    "trigger": {
        "rule": (
            "first completed eligible post-range bar satisfying expansion and volume"
        ),
        "signal_timestamp": "decision bar end",
        "tie_breaking": "earliest signal timestamp then immutable strategy identity",
    },
    "entry": {
        "rule": "exact next complete bar raw open",
        "entry_window": "09:36 through 11:00 inclusive",
        "adverse_friction_basis_points": 10,
        "pre_entry_invalidation": "raw or cost-adjusted entry at or below rounded stop",
    },
    "stop": {
        "rule": "fixed opening range low",
        "rounding": "floor to one cent",
    },
    "target": {
        "rule": "cost-adjusted entry plus two times initial per-share risk",
        "rounding": "ceil to one cent",
    },
    "lifecycle": {
        "maximum_complete_bars": 120,
        "session_liquidation": (
            "close of 120th held bar or 15:55 bar close, with early-close fifth-bar-before-close, "
            "whichever occurs first"
        ),
        "event_precedence": (
            "gap stop, intrabar stop, gap target, intrabar target, timeout, session liquidation"
        ),
        "gap_through": (
            "long stop exits at min(open,stop); long target exits at max(open,target)"
        ),
        "commission": "$0.005 per share per order with $1 minimum per order",
    },
    "missing_data": {
        "missing_range_bar": "unavailable:required_range_bar_missing",
        "fewer_than_20_eligible_same_clock_observations": (
            "unavailable:unavailable_same_clock_history"
        ),
        "missing_next_bar": "unavailable:missing_next_bar",
        "no_fabrication_or_forward_fill": True,
    },
    "integrity": {
        "nonfinite_or_invalid_ohlcv": "raise ExecutorIntegrityError",
        "duplicate_or_nonmonotonic_timestamp": "raise ExecutorIntegrityError",
        "opening_range_timestamp_mismatch": (
            "raise ExecutorIntegrityError:orb:range_timestamp_integrity"
        ),
        "lookahead": "only bars ending at or before decision cutoff plus next raw open",
    },
    "decision_states": ["integrity_failure", "no_signal", "no_trade", "proposal", "unavailable"],
    "expected_failure_modes": [
        "modeled costs and adverse selection exceed any gross effect",
        "range break is a liquidity sweep",
        "same-clock volume history is incomplete",
        "volume confirmation arrives after price exhaustion",
    ],
    "claim_boundary": (
        "exploratory diagnostics only; no empirical, profitability, validation, holdout, "
        "production, or capital conclusion"
    ),
    "reference_contract": {
        "strategy_id": REFERENCE_STRATEGY_ID,
        "strategy_identity": REFERENCE_STRATEGY_IDENTITY,
        "executor_identity": REFERENCE_EXECUTOR_IDENTITY,
        "lifecycle_identity": REFERENCE_LIFECYCLE_IDENTITY,
    },
}


def specification_identity() -> str:
    return canonical_hash(
        {
            "domain": "aml.opening-range-expansion-specification.v001",
            "specification": FROZEN_SPECIFICATION,
        }
    )


def _config_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(set(value) - {"config_identity"})}
    return canonical_hash({"domain": SCHEMA, "config": projection})


def _historical_binding_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key] for key in sorted(set(value) - {"binding_identity"})
    }
    return canonical_hash(
        {"domain": "aml.exploratory-contaminated-dataset-binding.v001", "binding": projection}
    )


def finalize_config(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    synthetic = result["synthetic_dataset_authorization"]
    projection = {
        key: synthetic[key]
        for key in sorted(set(synthetic) - {"authorization_identity"})
    }
    synthetic["authorization_identity"] = dataset_authorization_identity(projection)
    historical = result["exploratory_dataset_binding"]
    historical["binding_identity"] = _historical_binding_identity(historical)
    result["config_identity"] = _config_identity(result)
    return result


def validate_config(value: Mapping[str, object], repository_root: Path) -> dict[str, object]:
    required = {
        "schema_version",
        "milestone_version",
        "parent",
        "child",
        "reference_contract",
        "specification_identity",
        "synthetic_dataset_authorization",
        "exploratory_dataset_binding",
        "source_paths",
        "frozen_downstream_paths",
        "policy",
        "config_identity",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise OpeningRangeExpansionError("campaign config schema is invalid")
    if (
        value["schema_version"] != SCHEMA
        or value["milestone_version"] != MILESTONE_VERSION
        or value["specification_identity"] != specification_identity()
    ):
        raise OpeningRangeExpansionError("campaign version or specification changed")
    if value["parent"] != {
        "library_entry_id": PARENT_LIBRARY_ENTRY_ID,
        "framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
        "registration_identity": PARENT_REGISTRATION_IDENTITY,
        "library_identity": LIBRARY_IDENTITY,
        "revision": 1,
    }:
        raise OpeningRangeExpansionError("parent identity changed")
    if value["child"] != {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": CHILD_REVISION,
        "version": CHILD_VERSION,
    }:
        raise OpeningRangeExpansionError("child identity changed")
    if value["reference_contract"] != FROZEN_SPECIFICATION["reference_contract"]:
        raise OpeningRangeExpansionError("reference contract changed")
    if value["source_paths"] != list(SOURCE_PATHS):
        raise OpeningRangeExpansionError("source inventory changed")
    if value["frozen_downstream_paths"] != list(FROZEN_DOWNSTREAM_PATHS):
        raise OpeningRangeExpansionError("frozen downstream inventory changed")
    if value["policy"] != {
        "empirical_execution_permitted": False,
        "exploratory_execution_permitted": True,
        "frozen_downstream_modified": False,
        "holdout_access_permitted": False,
        "optimization_count": 0,
        "paper_or_live_trading_permitted": False,
        "profitability_metrics_published": False,
        "validation_access_permitted": False,
    }:
        raise OpeningRangeExpansionError("claim policy changed")
    validate_dataset_authorization(
        value["synthetic_dataset_authorization"], repository_root=repository_root
    )
    historical = value["exploratory_dataset_binding"]
    required_historical = {
        "binding_kind",
        "dataset_fingerprint",
        "dataset_vintage",
        "manifest_relative_path",
        "manifest_sha256",
        "contamination_labels",
        "symbols",
        "warmup_sessions",
        "evaluation_sessions",
        "selection_rule",
        "empirical_authorized",
        "binding_identity",
    }
    if not isinstance(historical, Mapping) or set(historical) != required_historical:
        raise OpeningRangeExpansionError("exploratory dataset binding schema is invalid")
    if historical != {
        "binding_kind": "contaminated_exploratory_only_not_empirical_authorization",
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "dataset_vintage": DATASET_VINTAGE,
        "manifest_relative_path": (
            "manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json"
        ),
        "manifest_sha256": DATASET_MANIFEST_SHA256,
        "contamination_labels": list(LABELS),
        "symbols": list(SYMBOLS),
        "warmup_sessions": list(WARMUP_SESSIONS),
        "evaluation_sessions": list(EVALUATION_SESSIONS),
        "selection_rule": (
            "Five lexicographically fixed liquid symbols; first five XNYS sessions after "
            "the first twenty dataset sessions, selected before candidate outcomes."
        ),
        "empirical_authorized": False,
        "binding_identity": historical["binding_identity"],
    }:
        raise OpeningRangeExpansionError("exploratory dataset binding changed")
    if historical["binding_identity"] != _historical_binding_identity(historical):
        raise OpeningRangeExpansionError("exploratory dataset binding identity changed")
    if value["config_identity"] != _config_identity(value):
        raise OpeningRangeExpansionError("config identity is stale or tampered")
    verify_reference_binding()
    return dict(value)


def load_config(path: Path, repository_root: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_config(value, repository_root)
    if path.read_bytes() != canonical_json(value):
        raise OpeningRangeExpansionError("campaign config is not canonical JSON")
    return value


def _parent_entry(config: Mapping[str, object], library_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    library = load_library(library_path)
    if library["library_identity"] != config["parent"]["library_identity"]:
        raise OpeningRangeExpansionError("library identity changed")
    entry = next(
        (item for item in library["hypotheses"] if item["library_entry_id"] == PARENT_LIBRARY_ENTRY_ID),
        None,
    )
    if entry is None or any(
        entry[field] != config["parent"][field]
        for field in ("framework_hypothesis_identity", "registration_identity", "revision")
    ):
        raise OpeningRangeExpansionError("parent library entry changed")
    sources = {item["source_id"]: item for item in library["sources"]}
    observation, parent_hypothesis = framework_artifacts(entry, sources)
    if parent_hypothesis["identity"] != PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY:
        raise OpeningRangeExpansionError("parent framework identity does not reproduce")
    return observation, parent_hypothesis


def _child_payload() -> dict[str, object]:
    return {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": CHILD_REVISION,
        "parent_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
        "title": "Five-minute long opening-range expansion continuation",
        "market_assumption": FROZEN_SPECIFICATION["market_assumption"],
        "mechanism": FROZEN_SPECIFICATION["economic_mechanism"],
        "required_evidence": [
            "exact five-minute opening range",
            "twenty-session point-in-time same-clock volume history",
            "next-bar lifecycle reconciliation",
        ],
        "expected_edge": (
            "A participation-confirmed upside range expansion may continue; exploratory "
            "exercise cannot determine whether this expectation is true."
        ),
        "invalidation_conditions": [
            "any post-range close below range low before trigger",
            "frozen reference identity changes",
            "point-in-time same-clock history is unavailable",
        ],
        "known_risks": [
            "adverse selection",
            "false breakout liquidity sweep",
            "modeled costs exceed any gross effect",
        ],
        "required_indicators": [
            "opening range high and low",
            "opening-range width realized-volatility proxy",
            "same-clock volume median over twenty prior eligible sessions",
        ],
        "expected_holding_period": "one to 120 complete one-minute bars",
        "expected_market_regime": "directional opening or expanding intraday volatility",
        "expected_failure_modes": list(FROZEN_SPECIFICATION["expected_failure_modes"]),
        "taxonomy": ["breakout", "opening", "volatility"],
        "contaminated_dataset_identities": [DATASET_FINGERPRINT],
        "multiple_testing_family": "opening-range-v001",
    }


def build_evidence(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    library_path: Path,
) -> dict[str, dict[str, object]]:
    validate_config(config, repository_root)
    _, parent_hypothesis = _parent_entry(config, library_path)
    observation = create_observation(
        {
            "observation_id": "opening-range-expansion-contract-derivation-v001",
            "title": "Prospective exact-contract derivation",
            "source_kind": "repository_contract_derivation_without_outcome_access",
            "source_references": [
                "config/benchmark_hypothesis_library_v001.json",
                "config/professional_strategy_olympics_v002.json",
            ],
            "source_dataset_identities": [],
            "observed_behavior": (
                "The parent is intentionally underspecified and the repository already "
                "contains one exact five-minute long ORB contract suitable for a child."
            ),
            "recorded_at": "2026-08-04T21:22:00Z",
        }
    )
    child_hypothesis = make_artifact(
        "hypothesis",
        _child_payload(),
        parent_identities=(parent_hypothesis["identity"], observation["identity"]),
    )
    triage = create_triage(
        {
            "hypothesis_identity": child_hypothesis["identity"],
            "disposition": "admit",
            "duplicate_signature": canonical_hash(
                {"domain": "aml.opening-range-expansion-triage.v001", "child": CHILD_HYPOTHESIS_ID}
            ),
            "duplicate_hypothesis_identities": [],
            "priority_vector": {
                "mechanism_plausibility": 2,
                "supporting_evidence": 1,
                "expected_frequency": 2,
                "data_readiness": 3,
                "distinctness": 1,
                "falsification_value": 3,
                "engineering_cost": 3,
                "contamination_risk": 1,
            },
            "reasons": [
                "Every executable rule is an exact alias of a frozen reference contract.",
                "The child resolves parent ambiguity before inspecting candidate outcomes.",
            ],
        },
        child_hypothesis,
    )
    specification = make_artifact(
        "specification",
        {
            "hypothesis_identity": child_hypothesis["identity"],
            "canonical_specification_identity": specification_identity(),
            "rules": FROZEN_SPECIFICATION,
        },
        parent_identities=(child_hypothesis["identity"], triage["identity"]),
    )
    preregistration = make_artifact(
        "preregistration",
        {
            "observation_identity": observation["identity"],
            "hypothesis_identity": child_hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "canonical_specification_identity": specification_identity(),
            "preregistered_at": "2026-08-04T21:22:00Z",
            "research_definitions_locked": True,
            "permitted_empirical_dataset_identities": [],
            "contaminated_exploratory_dataset_identities": [DATASET_FINGERPRINT],
            "claim_ceiling": "exploratory_engineering_diagnostics_only",
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
            child_hypothesis["identity"],
            triage["identity"],
            specification["identity"],
        ),
    )
    binding = implementation_binding_artifact(
        repository_root=repository_root,
        preregistration=preregistration,
        specification=specification,
        implementation_callable=(
            "aml.benchmark_candidate_opening_range_expansion_v001."
            "evaluate_opening_range_expansion"
        ),
        reference_contract=config["reference_contract"],
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    inputs = conformance_inputs()
    conformance = run_conformance(
        implementation_binding=binding,
        cases=(
            ConformanceCase(
                "integrity-failure",
                "integrity_failure",
                lambda: evaluate_opening_range_expansion(inputs["integrity-failure"]),
                (ExecutorIntegrityError,),
            ),
            ConformanceCase(
                "negative",
                "no_signal",
                lambda: evaluate_opening_range_expansion(inputs["negative"]),
            ),
            ConformanceCase(
                "positive",
                "proposal",
                lambda: evaluate_opening_range_expansion(inputs["positive"]),
            ),
            ConformanceCase(
                "unavailable",
                "unavailable",
                lambda: evaluate_opening_range_expansion(inputs["unavailable"]),
            ),
        ),
        repeat_case_id="positive",
        no_lookahead_check=no_lookahead_conformance,
        proposal_pipeline_check=proposal_pipeline_conformance,
    )
    registration = make_artifact(
        "implementation_binding",
        {
            "binding_kind": "executor_registration",
            "child_hypothesis_id": CHILD_HYPOTHESIS_ID,
            "implementation_binding_identity": binding["identity"],
            "implementation_callable": (
                "aml.benchmark_candidate_opening_range_expansion_v001."
                "evaluate_opening_range_expansion"
            ),
            "registry_keys": sorted(EXECUTOR_REGISTRY),
            "reference_strategy_id": REFERENCE_STRATEGY_ID,
            "reference_executor_identity": REFERENCE_EXECUTOR_IDENTITY,
            "empirical_execution_permitted": False,
            "exploratory_execution_permitted": True,
        },
        parent_identities=(binding["identity"], conformance["identity"]),
    )
    artifacts = {
        "01-observation.json": observation,
        "02-child-hypothesis.json": child_hypothesis,
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
    expected = {
        "01-observation.json": "observation",
        "02-child-hypothesis.json": "hypothesis",
        "03-triage.json": "triage",
        "04-specification.json": "specification",
        "05-preregistration.json": "preregistration",
        "06-implementation-binding.json": "implementation_binding",
        "07-conformance.json": "conformance",
        "08-executor-registration.json": "implementation_binding",
    }
    if set(artifacts) != set(expected):
        raise OpeningRangeExpansionError("evidence file inventory changed")
    for name, artifact_type in expected.items():
        validate_artifact(artifacts[name], artifact_type)
    binding = artifacts["06-implementation-binding.json"]
    verify_implementation_binding(
        binding,
        repository_root=repository_root,
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    conformance = artifacts["07-conformance.json"]
    if (
        conformance["payload"].get("all_checks_passed") is not True
        or conformance["payload"].get("no_lookahead") is not True
        or conformance["payload"].get("proposal_pipeline") is not True
    ):
        raise OpeningRangeExpansionError("conformance evidence is incomplete")
    registration = artifacts["08-executor-registration.json"]["payload"]
    if (
        registration.get("registry_keys") != [CHILD_HYPOTHESIS_ID]
        or set(EXECUTOR_REGISTRY) != {CHILD_HYPOTHESIS_ID}
        or EXECUTOR_REGISTRY[CHILD_HYPOTHESIS_ID]
        is not evaluate_opening_range_expansion
    ):
        raise OpeningRangeExpansionError("executor registration changed")


def _evidence_manifest(artifacts: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    files = [
        {
            "path": name,
            "sha256": hashlib.sha256(canonical_json(value)).hexdigest(),
            "identity": value["identity"],
        }
        for name, value in sorted(artifacts.items())
    ]
    base = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA,
        "milestone_version": MILESTONE_VERSION,
        "specification_identity": specification_identity(),
        "files": files,
        "immutable": True,
        "empirical_result_count": 0,
    }
    return {**base, "identity": canonical_hash(base)}


def write_evidence(
    output_root: Path,
    artifacts: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    target = Path(output_root)
    if target.exists():
        expected = {name: canonical_json(value) for name, value in artifacts.items()}
        manifest = _evidence_manifest(artifacts)
        expected["manifest.json"] = canonical_json(manifest)
        actual = {item.name: item.read_bytes() for item in target.iterdir() if item.is_file()}
        if actual != expected:
            raise OpeningRangeExpansionError("existing evidence differs from canonical bytes")
        return manifest
    target.mkdir(parents=True, exist_ok=False)
    for name, value in sorted(artifacts.items()):
        (target / name).write_bytes(canonical_json(value))
    manifest = _evidence_manifest(artifacts)
    (target / "manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def verify_evidence_directory(
    output_root: Path,
    *,
    repository_root: Path,
    config: Mapping[str, object],
) -> dict[str, object]:
    root = Path(output_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    identity = manifest.get("identity")
    base = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest.get("schema_version") != EVIDENCE_MANIFEST_SCHEMA
        or identity != canonical_hash(base)
        or manifest.get("empirical_result_count") != 0
    ):
        raise OpeningRangeExpansionError("evidence manifest changed")
    artifacts: dict[str, dict[str, object]] = {}
    expected = {"manifest.json"}
    for record in manifest.get("files", []):
        relative = Path(str(record.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise OpeningRangeExpansionError("unsafe evidence path")
        path = root / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256"):
            raise OpeningRangeExpansionError("evidence hash changed")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("identity") != record.get("identity"):
            raise OpeningRangeExpansionError("evidence identity changed")
        artifacts[relative.as_posix()] = value
        expected.add(relative.as_posix())
    actual = {item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()}
    if actual != expected:
        raise OpeningRangeExpansionError("evidence directory contains extra files")
    verify_evidence_objects(artifacts, repository_root, config)
    return {"manifest_identity": identity, "verified": True}


def _load_partitions(
    dataset_root: Path,
    binding: Mapping[str, object],
) -> tuple[dict[tuple[str, str], LoadedPartition], list[dict[str, object]]]:
    partitions: dict[tuple[str, str], LoadedPartition] = {}
    records: list[dict[str, object]] = []
    all_sessions = [*binding["warmup_sessions"], *binding["evaluation_sessions"]]
    for session in all_sessions:
        for symbol in binding["symbols"]:
            item = _partition(
                dataset_root,
                symbol=symbol,
                session=session,
                dataset_fingerprint=binding["dataset_fingerprint"],
            )
            partitions[(symbol, session)] = item
            records.append(
                {
                    "metadata_sha256": item.metadata_sha256,
                    "processed_sha256": item.processed_sha256,
                    "role": "warmup" if session in binding["warmup_sessions"] else "evaluated",
                    "session": session,
                    "symbol": symbol,
                    "warning_codes": list(item.warning_codes),
                }
            )
    return partitions, records


def _historical_volume(
    session: date,
    minute: str,
    histories: Sequence[tuple[date, dict[str, float], str]],
) -> tuple[HistoricalClockVolume, ...]:
    return tuple(
        HistoricalClockVolume(
            prior_session,
            minute,
            volumes[minute],
            True,
            DATASET_FINGERPRINT,
            source_identity,
        )
        for prior_session, volumes, source_identity in histories[-20:]
        if prior_session < session and minute in volumes
    )


def _evaluate_exploratory(
    partitions: Mapping[tuple[str, str], LoadedPartition],
    binding: Mapping[str, object],
) -> tuple[dict[str, int], Counter[str], Counter[str], list[object], list[dict[str, object]]]:
    histories: dict[str, list[tuple[date, dict[str, float], str]]] = defaultdict(list)
    for session in binding["warmup_sessions"]:
        for symbol in binding["symbols"]:
            item = partitions[(symbol, session)]
            histories[symbol].append(
                (
                    item.session,
                    {bar.timestamp.strftime("%H:%M"): bar.volume for bar in item.bars},
                    item.processed_sha256,
                )
            )
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposals: list[object] = []
    integrity: list[dict[str, object]] = []
    for session in binding["evaluation_sessions"]:
        for symbol in binding["symbols"]:
            partition = partitions[(symbol, session)]
            opened = datetime.combine(partition.session, time(9, 30), NY)
            closed = datetime.combine(partition.session, time(16, 0), NY)
            for index, bar in enumerate(partition.bars):
                clock = bar.timestamp.strftime("%H:%M")
                if not "09:35" <= clock <= "10:59":
                    continue
                history = _historical_volume(partition.session, clock, histories[symbol])
                try:
                    result = evaluate_opening_range_expansion(
                        EvaluationInput(
                            symbol_bars=partition.bars[: index + 1],
                            next_bar=_next_open(partition.bars, index),
                            scheduled_open=opened,
                            scheduled_close=closed,
                            decision_cutoff=bar.timestamp + timedelta(minutes=1),
                            same_clock_history=history,
                            halt_coverage_complete=True,
                            corporate_action_coverage_complete=True,
                            corporate_action_lineage_valid=True,
                            halt_manifest_identity="exploratory-no-halt-intervals-observed",
                            corporate_action_manifest_identity=(
                                "exploratory-retrospective-coverage-contaminated"
                            ),
                            calendar_identity="exploratory-fixed-normal-xnys-session",
                        )
                    )
                except ExecutorIntegrityError as exc:
                    statuses["integrity_failure"] += 1
                    reasons[f"integrity_failure:{exc}"] += 1
                    integrity.append(
                        {
                            "session": session,
                            "symbol": symbol,
                            "timestamp": bar.timestamp.isoformat(),
                            "reason": str(exc),
                        }
                    )
                    continue
                statuses[result.status] += 1
                for reason in result.reason_codes or ("none",):
                    reasons[f"{result.status}:{reason}"] += 1
                if result.proposal is not None:
                    proposals.append(result.proposal)
            histories[symbol].append(
                (
                    partition.session,
                    {bar.timestamp.strftime("%H:%M"): bar.volume for bar in partition.bars},
                    partition.processed_sha256,
                )
            )
    bars_by_key = {
        (partitions[(symbol, session)].symbol, partitions[(symbol, session)].session): (
            partitions[(symbol, session)].bars
        )
        for session in binding["evaluation_sessions"]
        for symbol in binding["symbols"]
    }
    calendar_by_date = {
        date.fromisoformat(session): CalendarSession(
            date.fromisoformat(session),
            datetime.combine(date.fromisoformat(session), time(9, 30), NY),
            datetime.combine(date.fromisoformat(session), time(16, 0), NY),
            False,
        )
        for session in binding["evaluation_sessions"]
    }
    trades, rejections = simulate_strategy(
        REFERENCE_STRATEGY_ID, proposals, bars_by_key, calendar_by_date
    )
    if len(proposals) != len(trades) + len(rejections):
        raise OpeningRangeExpansionError("exploratory proposal reconciliation failed")
    counts = {
        "executed_trade_count": len(trades),
        "integrity_failure_count": statuses["integrity_failure"],
        "proposal_count": len(proposals),
        "rejected_proposal_count": len(rejections),
        "trigger_count": len(proposals) + statuses["no_trade"],
        "unavailable_event_count": statuses["unavailable"],
    }
    return counts, statuses, reasons, proposals, integrity


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
    """Run one write-once, non-economic, contaminated diagnostic exercise."""

    validate_config(config, repository_root)
    verify_evidence_objects(evidence_artifacts, repository_root, config)
    evidence_manifest = _evidence_manifest(evidence_artifacts)
    child_identity = evidence_artifacts["02-child-hypothesis.json"]["identity"]
    preregistration_identity = evidence_artifacts["05-preregistration.json"][
        "identity"
    ]
    implementation_binding_identity = evidence_artifacts[
        "06-implementation-binding.json"
    ]["identity"]
    conformance_identity = evidence_artifacts["07-conformance.json"]["identity"]
    registration_identity = evidence_artifacts["08-executor-registration.json"][
        "identity"
    ]
    binding = config["exploratory_dataset_binding"]
    dataset = Path(dataset_root).resolve()
    if dataset.name != binding["dataset_vintage"]:
        raise OpeningRangeExpansionError("dataset vintage changed")
    manifest_path = repository_root / str(binding["manifest_relative_path"])
    if _sha256(manifest_path) != binding["manifest_sha256"]:
        raise OpeningRangeExpansionError("dataset manifest hash changed")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("dataset_fingerprint_sha256") != binding["dataset_fingerprint"]:
        raise OpeningRangeExpansionError("dataset fingerprint changed")
    partitions, partition_records = _load_partitions(dataset, binding)
    counts, statuses, reasons, _, integrity = _evaluate_exploratory(partitions, binding)
    warning_codes = sorted(
        {
            warning
            for item in partitions.values()
            for warning in item.warning_codes
        }
    )
    base_result = _result_payload(
        binding={
            "evaluator_binding": (
                "aml.benchmark_candidate_opening_range_expansion_v001."
                "evaluate_opening_range_expansion"
            ),
            "framework_hypothesis_identity": child_identity,
            "library_entry_id": CHILD_HYPOTHESIS_ID,
            "registration_identity": registration_identity,
        },
        counts=counts,
        decision_counts=statuses,
        decision_reason_counts=reasons,
        partition_count=len(EVALUATION_SESSIONS) * len(SYMBOLS),
        warning_codes=warning_codes,
        missing_fields=(),
        status=(
            "EXPLORATORY_DIAGNOSTIC_ONLY"
            if counts["integrity_failure_count"]
            else "EXPLORATORY_EXERCISED"
        ),
    )
    result_base = {key: value for key, value in base_result.items() if key != "identity"}
    result_base["partition_inspection"] = {
        "warmup_partition_count": len(WARMUP_SESSIONS) * len(SYMBOLS),
        "evaluated_partition_count": len(EVALUATION_SESSIONS) * len(SYMBOLS),
        "total_partition_count": len(partition_records),
        "warmup_session_count": len(WARMUP_SESSIONS),
        "evaluated_session_count": len(EVALUATION_SESSIONS),
        "symbol_count": len(SYMBOLS),
    }
    result_base["integrity_diagnostic_count"] = len(integrity)
    result = {**result_base, "identity": canonical_hash(result_base)}
    from aml.exploratory_research_mode_v001 import validate_result

    validate_result(result)
    source_sha256 = _source_hashes(repository_root)
    run_identity = canonical_hash(
        {
            "domain": "aml.opening-range-expansion-exploratory-run.v001",
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "partitions": partition_records,
            "source_sha256": source_sha256,
        }
    )
    target = _output_path(output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".opening-range-v001-", dir=target.parent))
    try:
        result_path = staging / f"01-{CHILD_HYPOTHESIS_ID}.json"
        result_path.write_bytes(canonical_json(result))
        summary_base = {
            "schema_version": EXPLORATORY_SUMMARY_SCHEMA,
            "labels": list(LABELS),
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_binding": {
                "child_hypothesis_identity": child_identity,
                "conformance_identity": conformance_identity,
                "evidence_manifest_identity": evidence_manifest["identity"],
                "implementation_binding_identity": implementation_binding_identity,
                "preregistration_identity": preregistration_identity,
                "registration_identity": registration_identity,
                "specification_identity": specification_identity(),
            },
            "partition_bindings": partition_records,
            "counts": counts,
            "decision_status_counts": dict(sorted(statuses.items())),
            "decision_reason_counts": dict(sorted(reasons.items())),
            "source_sha256": source_sha256,
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        _reject_prohibited_keys(summary_base)
        summary = {**summary_base, "identity": canonical_hash(summary_base)}
        summary_path = staging / "summary.json"
        summary_path.write_bytes(canonical_json(summary))
        files = [
            {"path": result_path.name, "sha256": _sha256(result_path)},
            {"path": summary_path.name, "sha256": _sha256(summary_path)},
        ]
        manifest_base = {
            "schema_version": MANIFEST_SCHEMA,
            "labels": list(LABELS),
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
    verified = verify_opening_range_exploratory_bundle(target)
    return {
        "run_identity": run_identity,
        "manifest_identity": verified["manifest_identity"],
        "evidence_manifest_identity": evidence_manifest["identity"],
        "counts": counts,
        "partition_count": len(partition_records),
        "output_root": str(target),
        "verified": True,
    }


def verify_opening_range_exploratory_bundle(path: Path) -> dict[str, object]:
    verified = verify_bundle(path)
    summary = json.loads((Path(path) / "summary.json").read_text(encoding="utf-8"))
    if (
        summary.get("schema_version") != EXPLORATORY_SUMMARY_SCHEMA
        or summary.get("labels") != list(LABELS)
        or summary.get("economic_metrics_published") is not False
        or summary.get("empirical_conclusion_authorized") is not False
    ):
        raise OpeningRangeExpansionError("exploratory summary boundary changed")
    _reject_prohibited_keys(summary)
    return verified
