"""Lifecycle and unchanged downstream execution for one Library V001 candidate."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

import pandas as pd

from aml.benchmark_candidate_high_of_day_breakout_v001 import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    HighOfDayCandidateIntegrityError,
    HighOfDayDecision,
    REQUIRED_COLUMNS,
    evaluate_high_of_day_breakout,
)
from aml.benchmark_hypothesis_library_v001 import framework_artifacts, load_library
from aml.benchmark_strategy_research_v001 import (
    canonical_hash,
    canonical_json,
    create_archive,
    create_triage,
    make_artifact,
    preregister,
    record_conformance,
    validate_artifact,
    verify_bundle,
    write_bundle,
)
from aml.discovery_screen_v001 import CompletedTrade, classify, trade_metrics
from aml.portfolio_simulator import (
    DuplicateSignalPolicy,
    PortfolioConfig,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)


PLAN_SCHEMA = "aml.executable-benchmark-candidate.v001"
PLAN_VERSION = "executable-benchmark-candidate-v001"
EVIDENCE_CLASS = "synthetic_non_empirical_executable_candidate"
EXPECTED_HYPOTHESIS_IDENTITY = (
    "3545e9db49dca14f2598541afaa3da65a66cf63e5cc9ded12b4a826f15abef86"
)
EXPECTED_REGISTRATION_IDENTITY = (
    "a58bfa6327704c4b693e99f1837a783ae9d7448b667adac304232df05646d5b7"
)
HASH = re.compile(r"^[0-9a-f]{64}$")
PLAN_FIELDS = {
    "schema_version",
    "plan_version",
    "candidate_id",
    "candidate_version",
    "selected_hypothesis",
    "selection_rationale",
    "evidence_class",
    "dataset",
    "triage",
    "specification",
    "preregistration",
    "plan_identity",
}
IMPLEMENTATION_FILES = [
    "src/aml/benchmark_candidate_high_of_day_breakout_v001.py",
    "src/aml/benchmark_executable_candidate_v001.py",
]
DOWNSTREAM_FILES = [
    "src/aml/discovery_screen_v001.py",
    "src/aml/portfolio_simulator.py",
]


class ExecutableCandidateError(ValueError):
    """Candidate plan, lifecycle, execution, or evidence is invalid."""


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ExecutableCandidateError(f"{field} must be a SHA-256 identity")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutableCandidateError(f"{field} must be a non-empty string")
    return value


def _timestamp(value: object, field: str) -> str:
    result = _text(value, field)
    try:
        parsed = datetime.fromisoformat(result)
    except ValueError as exc:
        raise ExecutableCandidateError(f"{field} is malformed") from exc
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
        or canonical != result
    ):
        raise ExecutableCandidateError(f"{field} must use canonical UTC")
    return result


def candidate_dataset_identity(frame: pd.DataFrame) -> str:
    """Bind every field used by the candidate and unchanged simulator."""

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ExecutableCandidateError("candidate dataset must be non-empty")
    required = sorted(REQUIRED_COLUMNS)
    if any(field not in frame for field in required):
        raise ExecutableCandidateError("candidate dataset fields are incomplete")
    normalized = frame.loc[:, required].copy(deep=True)
    try:
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExecutableCandidateError("candidate dataset timestamps are malformed") from exc
    if normalized["timestamp"].dt.tz is None:
        raise ExecutableCandidateError("candidate dataset timestamps must be timezone-aware")
    records: list[dict[str, object]] = []
    for record in normalized.to_dict("records"):
        record["timestamp"] = pd.Timestamp(record["timestamp"]).isoformat()
        for field in ("open", "high", "low", "close", "volume", "spread_bps"):
            value = float(record[field])
            if not math.isfinite(value):
                raise ExecutableCandidateError("candidate dataset values must be finite")
            record[field] = value
        records.append(dict(sorted(record.items())))
    return canonical_hash(
        {
            "domain": "aml.executable-benchmark-candidate.dataset.v001",
            "records": records,
        }
    )


def plan_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(PLAN_FIELDS - {"plan_identity"})}
    return canonical_hash(
        {
            "domain": "aml.executable-benchmark-candidate.plan.v001",
            "plan": projection,
        }
    )


def validate_plan(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != PLAN_FIELDS:
        raise ExecutableCandidateError("candidate plan schema is invalid")
    if value["schema_version"] != PLAN_SCHEMA or value["plan_version"] != PLAN_VERSION:
        raise ExecutableCandidateError("candidate plan version changed")
    if value["candidate_id"] != CANDIDATE_ID or value["candidate_version"] != CANDIDATE_VERSION:
        raise ExecutableCandidateError("candidate identity changed")
    selected = value["selected_hypothesis"]
    if selected != {
        "library_entry_id": CANDIDATE_ID,
        "framework_hypothesis_identity": EXPECTED_HYPOTHESIS_IDENTITY,
        "registration_identity": EXPECTED_REGISTRATION_IDENTITY,
        "revision": 1,
    }:
        raise ExecutableCandidateError("selected hypothesis identity changed")
    rationale = value["selection_rationale"]
    if not isinstance(rationale, list) or rationale != sorted(set(rationale)) or not rationale:
        raise ExecutableCandidateError("selection rationale must be unique and sorted")
    for item in rationale:
        _text(item, "selection rationale")
    if value["evidence_class"] != EVIDENCE_CLASS:
        raise ExecutableCandidateError("candidate evidence class changed")
    dataset = value["dataset"]
    if not isinstance(dataset, Mapping) or set(dataset) != {
        "relative_path",
        "file_sha256",
        "dataset_identity",
        "authorization",
        "claim_limit",
    }:
        raise ExecutableCandidateError("candidate dataset binding schema is invalid")
    path = Path(_text(dataset["relative_path"], "dataset relative path"))
    if path.is_absolute() or ".." in path.parts:
        raise ExecutableCandidateError("candidate dataset path is unsafe")
    _identity(dataset["file_sha256"], "dataset file hash")
    _identity(dataset["dataset_identity"], "dataset identity")
    if dataset["authorization"] != "candidate_v001_synthetic_discovery_only":
        raise ExecutableCandidateError("candidate dataset authorization changed")
    if dataset["claim_limit"] != "pipeline_evidence_only_no_empirical_edge_claim":
        raise ExecutableCandidateError("candidate dataset claim limit changed")
    triage = value["triage"]
    if not isinstance(triage, Mapping) or set(triage) != {
        "disposition",
        "duplicate_signature",
        "duplicate_hypothesis_identities",
        "priority_vector",
        "reasons",
    }:
        raise ExecutableCandidateError("candidate triage schema is invalid")
    if triage["disposition"] != "admit":
        raise ExecutableCandidateError("candidate must be prospectively admitted")
    _identity(triage["duplicate_signature"], "duplicate signature")
    if triage["duplicate_hypothesis_identities"] != []:
        raise ExecutableCandidateError("candidate has an unresolved duplicate")
    specification = value["specification"]
    required_specification = {
        "strategy_id",
        "strategy_version",
        "direction",
        "required_input_fields",
        "decision_window",
        "level_rule",
        "consolidation_rule",
        "trigger_rule",
        "entry_rule",
        "stop_rule",
        "target_rule",
        "timeout_minutes",
        "missing_data_rule",
        "integrity_rule",
        "maximum_entries_per_symbol_session",
        "downstream_proposal_type",
        "classification_function",
        "material_data_limitation_threshold",
        "fixed_parameters",
    }
    if not isinstance(specification, Mapping) or set(specification) != required_specification:
        raise ExecutableCandidateError("candidate specification schema is invalid")
    if (
        specification["strategy_id"] != CANDIDATE_ID
        or specification["strategy_version"] != CANDIDATE_VERSION
        or specification["direction"] != "long"
        or specification["downstream_proposal_type"]
        != "aml.portfolio_simulator.StrategyProposal"
        or specification["classification_function"]
        != "aml.discovery_screen_v001.classify"
    ):
        raise ExecutableCandidateError("candidate specification binding changed")
    if specification["fixed_parameters"] != {
        "atr_window": 20,
        "consolidation_bars": 5,
        "consolidation_width_atr_max": 0.75,
        "level_minimum_age_bars": 15,
        "maximum_prior_tests": 2,
        "price_max": 500.0,
        "price_min": 2.0,
        "relative_volume_min": 1.5,
        "reward_risk_multiple": 2.0,
        "spread_bps_max": 15.0,
        "stop_atr_offset": 0.05,
        "volume_window": 20,
    }:
        raise ExecutableCandidateError("candidate fixed parameters changed")
    if specification["timeout_minutes"] != 90:
        raise ExecutableCandidateError("candidate timeout changed")
    threshold = specification["material_data_limitation_threshold"]
    if threshold != 0.1:
        raise ExecutableCandidateError("candidate data limitation threshold changed")
    preregistration = value["preregistration"]
    if not isinstance(preregistration, Mapping) or set(preregistration) != {
        "preregistered_at",
        "prohibited_dataset_labels",
        "research_definitions_locked",
    }:
        raise ExecutableCandidateError("candidate preregistration schema is invalid")
    _timestamp(preregistration["preregistered_at"], "preregistered_at")
    prohibited = preregistration["prohibited_dataset_labels"]
    if not isinstance(prohibited, list) or prohibited != sorted(set(prohibited)):
        raise ExecutableCandidateError("candidate prohibited datasets are invalid")
    if not {"forward validation", "holdout", "validation"}.issubset(set(prohibited)):
        raise ExecutableCandidateError("candidate preregistration omits protected data")
    if preregistration["research_definitions_locked"] is not True:
        raise ExecutableCandidateError("candidate research definitions are not locked")
    if value["plan_identity"] != plan_identity(value):
        raise ExecutableCandidateError("candidate plan identity is stale or tampered")
    return dict(value)


def load_plan(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ExecutableCandidateError("candidate plan is missing, unsafe, or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ExecutableCandidateError("candidate plan has duplicate keys")
            result[key] = item
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ExecutableCandidateError(f"non-finite plan value:{item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutableCandidateError("candidate plan is malformed") from exc
    validate_plan(value)
    if path.read_bytes() != canonical_json(value):
        raise ExecutableCandidateError("candidate plan bytes are not canonical")
    return value


def finalize_plan(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    result["plan_identity"] = plan_identity(result)
    validate_plan(result)
    return result


def load_dataset(repository_root: Path, plan: Mapping[str, object]) -> pd.DataFrame:
    validate_plan(plan)
    root = Path(repository_root).resolve()
    path = root / str(plan["dataset"]["relative_path"])
    if not path.is_file() or path.is_symlink():
        raise ExecutableCandidateError("authorized candidate dataset is unavailable")
    if hashlib.sha256(path.read_bytes()).hexdigest() != plan["dataset"]["file_sha256"]:
        raise ExecutableCandidateError("authorized candidate dataset file changed")
    frame = pd.read_csv(path)
    if candidate_dataset_identity(frame) != plan["dataset"]["dataset_identity"]:
        raise ExecutableCandidateError("authorized candidate dataset identity changed")
    return frame


def _source_hashes(repository_root: Path) -> dict[str, str]:
    root = Path(repository_root).resolve()
    result: dict[str, str] = {}
    for relative in IMPLEMENTATION_FILES + DOWNSTREAM_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ExecutableCandidateError(f"candidate source is invalid:{relative}")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(result.items()))


def _binding(
    repository_root: Path,
    preregistration_artifact: Mapping[str, object],
    specification: Mapping[str, object],
) -> dict[str, object]:
    payload = {
        "preregistration_identity": preregistration_artifact["identity"],
        "specification_identity": specification["identity"],
        "implementation_callable": (
            "aml.benchmark_candidate_high_of_day_breakout_v001."
            "evaluate_high_of_day_breakout"
        ),
        "implementation_files": IMPLEMENTATION_FILES,
        "downstream_files": DOWNSTREAM_FILES,
        "no_frozen_file_modified": True,
        "source_sha256": _source_hashes(repository_root),
    }
    return make_artifact(
        "implementation_binding",
        payload,
        parent_identities=(
            preregistration_artifact["identity"],
            specification["identity"],
        ),
    )


def verify_binding(repository_root: Path, binding: Mapping[str, object]) -> None:
    binding = validate_artifact(binding, "implementation_binding")
    if binding["payload"].get("source_sha256") != _source_hashes(repository_root):
        raise ExecutableCandidateError("candidate implementation binding changed")


def _provenance(
    artifacts: Mapping[str, Mapping[str, object]], dataset_identity: str
) -> dict[str, str]:
    return {
        "hypothesis_identity": str(artifacts["hypothesis"]["identity"]),
        "specification_identity": str(artifacts["specification"]["identity"]),
        "preregistration_identity": str(artifacts["preregistration"]["identity"]),
        "implementation_binding_identity": str(
            artifacts["implementation_binding"]["identity"]
        ),
        "dataset_identity": dataset_identity,
    }


def run_conformance(
    frame: pd.DataFrame,
    *,
    artifacts: Mapping[str, Mapping[str, object]],
    dataset_identity: str,
) -> dict[str, object]:
    provenance = _provenance(artifacts, dataset_identity)
    positive_prefix = frame.iloc[:21].copy(deep=True)
    positive = evaluate_high_of_day_breakout(positive_prefix, **provenance)
    if positive.status != "proposal" or positive.proposal is None:
        raise ExecutableCandidateError("candidate positive conformance failed")
    negative_prefix = positive_prefix.copy(deep=True)
    negative_prefix.loc[negative_prefix.index[-1], ["high", "close", "volume"]] = [
        10.20,
        10.19,
        2200,
    ]
    negative = evaluate_high_of_day_breakout(negative_prefix, **provenance)
    if negative.status != "no_signal" or negative.proposal is not None:
        raise ExecutableCandidateError("candidate negative conformance failed")
    unavailable = evaluate_high_of_day_breakout(frame.iloc[:20], **provenance)
    if unavailable.status != "unavailable" or unavailable.proposal is not None:
        raise ExecutableCandidateError("candidate unavailable conformance failed")
    duplicate = pd.concat(
        [positive_prefix, positive_prefix.iloc[[-1]]], ignore_index=True
    )
    try:
        evaluate_high_of_day_breakout(duplicate, **provenance)
    except HighOfDayCandidateIntegrityError:
        integrity_passed = True
    else:
        integrity_passed = False
    if not integrity_passed:
        raise ExecutableCandidateError("candidate integrity conformance failed")
    repeated = evaluate_high_of_day_breakout(positive_prefix, **provenance)
    if (
        repeated.proposal is None
        or repeated.proposal.proposal_id != positive.proposal.proposal_id
    ):
        raise ExecutableCandidateError("candidate deterministic conformance failed")
    changed_future = frame.copy(deep=True)
    changed_future.loc[changed_future.index[21] :, ["open", "high", "low", "close"]] *= 1.5
    no_lookahead = evaluate_high_of_day_breakout(
        changed_future.iloc[:21], **provenance
    )
    if (
        no_lookahead.proposal is None
        or no_lookahead.proposal.proposal_id != positive.proposal.proposal_id
    ):
        raise ExecutableCandidateError("candidate no-lookahead conformance failed")
    downstream = simulate_portfolio(
        [positive.proposal],
        {"TEST": frame},
        _portfolio_config(0.001),
    )
    if len(downstream.proposal_audit) != 1 or downstream.proposal_audit.iloc[0][
        "status"
    ] not in {"accepted", "rejected"}:
        raise ExecutableCandidateError("candidate proposal pipeline conformance failed")
    return record_conformance(
        {
            "implementation_binding_identity": artifacts["implementation_binding"][
                "identity"
            ],
            "positive_path": True,
            "negative_path": True,
            "unavailable_path": True,
            "integrity_failure_path": True,
            "no_lookahead_path": True,
            "deterministic_path": True,
            "proposal_pipeline_path": True,
            "all_checks_passed": True,
        },
        artifacts["implementation_binding"],
    )


def build_preregistered_artifacts(
    *,
    repository_root: Path,
    plan: Mapping[str, object],
    library: Mapping[str, object],
    frame: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    validate_plan(plan)
    entries = {
        entry["library_entry_id"]: entry for entry in library["hypotheses"]
    }
    sources = {source["source_id"]: source for source in library["sources"]}
    if CANDIDATE_ID not in entries:
        raise ExecutableCandidateError("selected Library hypothesis is unavailable")
    entry = entries[CANDIDATE_ID]
    if (
        entry["framework_hypothesis_identity"] != EXPECTED_HYPOTHESIS_IDENTITY
        or entry["registration_identity"] != EXPECTED_REGISTRATION_IDENTITY
        or entry["revision"] != 1
    ):
        raise ExecutableCandidateError("selected Library hypothesis changed")
    observation, hypothesis = framework_artifacts(entry, sources)
    triage = create_triage(
        {**plan["triage"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
    )
    specification = make_artifact(
        "specification",
        {**plan["specification"], "hypothesis_identity": hypothesis["identity"]},
        parent_identities=(hypothesis["identity"], triage["identity"]),
    )
    dataset_identity = candidate_dataset_identity(frame)
    if dataset_identity != plan["dataset"]["dataset_identity"]:
        raise ExecutableCandidateError("candidate dataset binding changed")
    preregistration_artifact = preregister(
        {
            "observation_identity": observation["identity"],
            "hypothesis_identity": hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "permitted_discovery_dataset_identities": [dataset_identity],
            "prohibited_dataset_labels": plan["preregistration"][
                "prohibited_dataset_labels"
            ],
            "contaminated_dataset_identities": hypothesis["payload"][
                "contaminated_dataset_identities"
            ],
            "preregistered_at": plan["preregistration"]["preregistered_at"],
            "research_definitions_locked": True,
        },
        observation,
        hypothesis,
        triage,
        specification,
    )
    binding = _binding(
        repository_root, preregistration_artifact, specification
    )
    result = {
        "observation": observation,
        "hypothesis": hypothesis,
        "triage": triage,
        "specification": specification,
        "preregistration": preregistration_artifact,
        "implementation_binding": binding,
    }
    result["conformance"] = run_conformance(
        frame,
        artifacts=result,
        dataset_identity=dataset_identity,
    )
    return result


def _portfolio_config(slippage: float) -> PortfolioConfig:
    return PortfolioConfig(
        total_capital=100_000.0,
        strategy_allocations=(
            StrategyAllocation(CANDIDATE_ID, CANDIDATE_VERSION, 100_000.0),
        ),
        maximum_position_risk_fraction=0.0025,
        maximum_concurrent_positions=3,
        maximum_symbol_concentration_fraction=0.5,
        maximum_strategy_concentration_fraction=1.0,
        daily_loss_limit_fraction=0.01,
        slippage_fraction=slippage,
        maximum_entry_delay_minutes=0,
        duplicate_signal_policy=DuplicateSignalPolicy.REJECT_EXACT,
    )


def _completed_trades(
    trades: pd.DataFrame, *, strategy_identity: str, cost_scenario: str
) -> list[CompletedTrade]:
    result: list[CompletedTrade] = []
    for row in trades.itertuples(index=False):
        result.append(
            CompletedTrade(
                strategy_id=str(row.strategy_identifier),
                strategy_identity=strategy_identity,
                proposal_identity=str(row.proposal_id),
                symbol=str(row.symbol),
                session=pd.Timestamp(row.actual_entry_timestamp).date().isoformat(),
                signal_timestamp=pd.Timestamp(row.signal_timestamp).isoformat(),
                entry_timestamp=pd.Timestamp(row.actual_entry_timestamp).isoformat(),
                exit_timestamp=pd.Timestamp(row.exit_timestamp).isoformat(),
                raw_entry=float(row.raw_entry_price),
                raw_exit=float(row.raw_exit_price),
                stop=float(row.stop_price),
                target=float(row.target_price),
                quantity=int(row.quantity),
                exit_reason=str(row.exit_reason),
                gross_pnl=float(row.gross_pnl),
                entry_commission=0.0,
                exit_commission=0.0,
                net_pnl=float(row.net_pnl),
                net_r_multiple=float(row.net_pnl) / 250.0,
                cost_scenario=cost_scenario,
            )
        )
    return result


def _candidate_decisions(
    frame: pd.DataFrame, provenance: Mapping[str, str]
) -> tuple[list[HighOfDayDecision], list[StrategyProposal], int]:
    decisions: list[HighOfDayDecision] = []
    proposals: list[StrategyProposal] = []
    integrity_failures = 0
    for index in range(20, len(frame)):
        try:
            decision = evaluate_high_of_day_breakout(
                frame.iloc[: index + 1], **provenance
            )
        except HighOfDayCandidateIntegrityError:
            integrity_failures += 1
            break
        decisions.append(decision)
        if decision.status == "proposal":
            if decision.proposal is None:
                integrity_failures += 1
            else:
                proposals.append(decision.proposal)
            break
        if decision.proposal is not None:
            integrity_failures += 1
            break
    return decisions, proposals, integrity_failures


def execute_candidate_discovery(
    *,
    repository_root: Path,
    frame: pd.DataFrame,
    artifacts: Mapping[str, Mapping[str, object]],
    dataset_identity: str,
) -> tuple[dict[str, object], dict[str, object]]:
    verify_binding(repository_root, artifacts["implementation_binding"])
    for artifact_type in (
        "hypothesis",
        "specification",
        "preregistration",
        "implementation_binding",
        "conformance",
    ):
        validate_artifact(artifacts[artifact_type], artifact_type)
    permitted = artifacts["preregistration"]["payload"][
        "permitted_discovery_dataset_identities"
    ]
    if dataset_identity not in permitted:
        raise ExecutableCandidateError("candidate dataset is not preregistered")
    provenance = _provenance(artifacts, dataset_identity)
    try:
        evaluate_high_of_day_breakout(frame, **provenance)
    except HighOfDayCandidateIntegrityError as exc:
        raise ExecutableCandidateError("candidate discovery input integrity failure") from exc
    decisions, proposals, integrity_failures = _candidate_decisions(frame, provenance)
    if integrity_failures:
        raise ExecutableCandidateError("candidate integrity failures prevent publication")
    status_counts = {
        status: sum(decision.status == status for decision in decisions)
        for status in ("proposal", "no_signal", "unavailable")
    }
    evaluation_count = len(decisions)
    unavailable_fraction = (
        status_counts["unavailable"] / evaluation_count if evaluation_count else 1.0
    )
    scenario_metrics: dict[str, object] = {}
    scenario_trades: dict[str, list[dict[str, object]]] = {}
    scenario_counts: dict[str, int] = {}
    base_audit: list[dict[str, object]] = []
    for name, slippage in (("base", 0.001), ("cost_1_5x", 0.0015), ("cost_2x", 0.002)):
        downstream = simulate_portfolio(
            proposals, {"TEST": frame}, _portfolio_config(slippage)
        )
        completed = _completed_trades(
            downstream.trades,
            strategy_identity=str(artifacts["specification"]["identity"]),
            cost_scenario=name,
        )
        scenario_counts[name] = len(completed)
        scenario_metrics[name] = trade_metrics(completed)
        scenario_trades[name] = [asdict(item) for item in completed]
        if name == "base":
            base_audit = json.loads(
                json.dumps(
                    downstream.proposal_audit.to_dict("records"),
                    default=lambda value: (
                        value.isoformat() if isinstance(value, pd.Timestamp) else value
                    ),
                )
            )
    if len(set(scenario_counts.values())) != 1:
        raise ExecutableCandidateError("candidate cost scenario counts changed")
    accepted = scenario_counts["base"]
    rejected = sum(row["status"] == "rejected" for row in base_audit)
    if len(proposals) != accepted + rejected:
        raise ExecutableCandidateError("candidate proposal reconciliation failed")
    metrics = {"trade_count": accepted, **scenario_metrics}
    material_data_limitation = unavailable_fraction > 0.1
    classification_value = classify(
        metrics, material_data_limitation=material_data_limitation
    )
    discovery = make_artifact(
        "discovery",
        {
            **provenance,
            "conformance_identity": artifacts["conformance"]["identity"],
            "evidence_class": EVIDENCE_CLASS,
            "evaluation_count": evaluation_count,
            "decision_status_counts": status_counts,
            "proposal_count": len(proposals),
            "accepted_trade_count": accepted,
            "rejected_proposal_count": rejected,
            "executor_integrity_failure_count": 0,
            "unavailable_fraction": unavailable_fraction,
            "material_data_limitation": material_data_limitation,
            "cost_scenario_trade_counts": scenario_counts,
            "metrics": metrics,
            "proposal_audit": base_audit,
            "trades": scenario_trades,
        },
        parent_identities=(
            artifacts["hypothesis"]["identity"],
            artifacts["specification"]["identity"],
            artifacts["preregistration"]["identity"],
            artifacts["implementation_binding"]["identity"],
            artifacts["conformance"]["identity"],
        ),
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
    return discovery, classification_artifact


def build_candidate_bundle(
    *,
    repository_root: Path,
    plan_path: Path,
    library_path: Path,
    output_root: Path,
) -> dict[str, object]:
    plan = load_plan(plan_path)
    library = load_library(library_path)
    frame = load_dataset(repository_root, plan)
    artifacts = build_preregistered_artifacts(
        repository_root=repository_root,
        plan=plan,
        library=library,
        frame=frame,
    )
    dataset_identity = candidate_dataset_identity(frame)
    discovery, classification_artifact = execute_candidate_discovery(
        repository_root=repository_root,
        frame=frame,
        artifacts=artifacts,
        dataset_identity=dataset_identity,
    )
    archive = create_archive(
        hypothesis=artifacts["hypothesis"],
        archive_state=(
            "rejected"
            if classification_artifact["payload"]["classification"] == "REJECT"
            else "completed"
        ),
        reason=(
            "Frozen synthetic executable-candidate discovery completed; no empirical "
            "edge, validation, deployment, or capital claim is authorized."
        ),
        related_artifacts=(
            artifacts["observation"],
            artifacts["triage"],
            artifacts["specification"],
            artifacts["preregistration"],
            artifacts["implementation_binding"],
            artifacts["conformance"],
            discovery,
            classification_artifact,
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
        classification_artifact,
        archive,
    )
    manifest = write_bundle(output_root, ordered)
    verified = verify_bundle(output_root)
    return {
        "bundle_identity": manifest["identity"],
        "classification": classification_artifact["payload"]["classification"],
        "classification_identity": classification_artifact["identity"],
        "conformance_identity": artifacts["conformance"]["identity"],
        "dataset_identity": dataset_identity,
        "discovery_identity": discovery["identity"],
        "implementation_binding_identity": artifacts["implementation_binding"][
            "identity"
        ],
        "preregistration_identity": artifacts["preregistration"]["identity"],
        "specification_identity": artifacts["specification"]["identity"],
        "verified": verified["verified"],
    }
