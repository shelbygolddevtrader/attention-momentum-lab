"""Deterministic upstream lifecycle for one benchmark-research candidate.

The module adds no execution semantics.  Candidate proposals are evaluated by
the existing shared portfolio simulator, and classifications are delegated to
the existing discovery classifier.  All lifecycle entities are immutable,
content-addressed artifacts; lifecycle changes create new artifacts rather than
mutating earlier records.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable, Mapping, Sequence
import unicodedata

import pandas as pd

from aml.benchmark_research_candidate_v001 import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    CandidateDecision,
    CandidateIntegrityError,
    evaluate_opening_range_midpoint_reclaim,
)
from aml.discovery_screen_v001 import CompletedTrade, classify, trade_metrics
from aml.portfolio_simulator import (
    DuplicateSignalPolicy,
    PortfolioConfig,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)


FRAMEWORK_SCHEMA = "aml.benchmark-strategy-research.v001"
FRAMEWORK_VERSION = "benchmark-strategy-research-v001"
HASH = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
MAX_ARTIFACT_BYTES = 2_000_000
MAX_TEXT_LENGTH = 20_000
ARTIFACT_TYPES = frozenset(
    {
        "observation",
        "hypothesis",
        "triage",
        "specification",
        "preregistration",
        "implementation_binding",
        "conformance",
        "discovery",
        "classification",
        "archive",
    }
)
TERMINAL_ARCHIVE_STATES = frozenset(
    {"completed", "rejected", "abandoned", "superseded"}
)


class BenchmarkResearchError(ValueError):
    """Research entity, lifecycle, or immutable-publication violation."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise BenchmarkResearchError("non-finite values are prohibited")
    return value


def canonical_json(value: object) -> bytes:
    """Canonical UTF-8 JSON shared by every V001 research artifact."""

    try:
        return (
            json.dumps(
                _jsonable(value),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BenchmarkResearchError("value is not canonically serializable") from exc


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def market_data_identity(bars_by_symbol: Mapping[str, pd.DataFrame]) -> str:
    """Bind deterministic bar contents without mutating caller-owned frames."""

    if not isinstance(bars_by_symbol, Mapping) or not bars_by_symbol:
        raise BenchmarkResearchError("market data must be a non-empty symbol mapping")
    payload: list[dict[str, object]] = []
    for symbol, frame in sorted(bars_by_symbol.items()):
        if not isinstance(symbol, str) or not symbol.strip() or not isinstance(frame, pd.DataFrame):
            raise BenchmarkResearchError("market data symbols and frames are invalid")
        required = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        if any(field not in frame for field in required):
            raise BenchmarkResearchError("market data fields are incomplete")
        normalized = frame.loc[:, required].copy(deep=True)
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"])
        if normalized["timestamp"].dt.tz is None:
            raise BenchmarkResearchError("market data timestamps must be timezone-aware")
        for record in normalized.to_dict("records"):
            record["timestamp"] = pd.Timestamp(record["timestamp"]).isoformat()
            payload.append({key: _jsonable(value) for key, value in record.items()})
    return canonical_hash({"schema": "aml.benchmark-research.market-data.v001", "bars": payload})


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkResearchError(f"{field} must be a non-empty string")
    if len(value) > MAX_TEXT_LENGTH:
        raise BenchmarkResearchError(f"{field} exceeds the size limit")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise BenchmarkResearchError(f"{field} contains invalid Unicode")
    return value


def _identifier(value: object, field: str) -> str:
    result = _text(value, field)
    if not IDENTIFIER.fullmatch(result):
        raise BenchmarkResearchError(f"{field} is malformed")
    return result


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise BenchmarkResearchError(f"{field} must be a SHA-256 identity")
    return value


def _identities(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise BenchmarkResearchError(f"{field} must be an identity list")
    result = [_identity(item, f"{field} item") for item in value]
    if result != sorted(set(result)):
        raise BenchmarkResearchError(f"{field} must be unique and sorted")
    return result


def _strings(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise BenchmarkResearchError(f"{field} must be a string list")
    result = [_text(item, f"{field} item") for item in value]
    if result != sorted(set(result)):
        raise BenchmarkResearchError(f"{field} must be unique and sorted")
    return result


def _timestamp(value: object, field: str) -> str:
    result = _text(value, field)
    try:
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkResearchError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BenchmarkResearchError(f"{field} must be timezone-aware")
    if parsed.utcoffset().total_seconds() != 0:
        raise BenchmarkResearchError(f"{field} must use UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def make_artifact(
    artifact_type: str,
    payload: Mapping[str, object],
    *,
    parent_identities: Sequence[str] = (),
) -> dict[str, object]:
    """Create one immutable content-addressed artifact."""

    if artifact_type not in ARTIFACT_TYPES:
        raise BenchmarkResearchError("unsupported research artifact type")
    parents = sorted(set(parent_identities))
    for parent in parents:
        _identity(parent, "parent identity")
    base: dict[str, object] = {
        "schema_version": FRAMEWORK_SCHEMA,
        "framework_version": FRAMEWORK_VERSION,
        "artifact_type": artifact_type,
        "parent_identities": parents,
        "payload": dict(payload),
    }
    if len(canonical_json(base)) > MAX_ARTIFACT_BYTES:
        raise BenchmarkResearchError("research artifact exceeds the size limit")
    return {**base, "identity": canonical_hash(base)}


def validate_artifact(
    value: Mapping[str, object], expected_type: str | None = None
) -> dict[str, object]:
    required = {
        "schema_version",
        "framework_version",
        "artifact_type",
        "parent_identities",
        "payload",
        "identity",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise BenchmarkResearchError("research artifact schema is invalid")
    if value["schema_version"] != FRAMEWORK_SCHEMA:
        raise BenchmarkResearchError("research artifact schema version changed")
    if value["framework_version"] != FRAMEWORK_VERSION:
        raise BenchmarkResearchError("research framework version changed")
    artifact_type = value["artifact_type"]
    if artifact_type not in ARTIFACT_TYPES or (
        expected_type is not None and artifact_type != expected_type
    ):
        raise BenchmarkResearchError("research artifact type is invalid")
    _identities(value["parent_identities"], "parent_identities", allow_empty=True)
    if not isinstance(value["payload"], Mapping):
        raise BenchmarkResearchError("research artifact payload must be an object")
    identity = _identity(value["identity"], "identity")
    base = {key: value[key] for key in required if key != "identity"}
    if canonical_hash(base) != identity:
        raise BenchmarkResearchError("research artifact identity is stale or tampered")
    return dict(value)


def create_observation(payload: Mapping[str, object]) -> dict[str, object]:
    required = {
        "observation_id",
        "title",
        "source_kind",
        "source_references",
        "source_dataset_identities",
        "observed_behavior",
        "recorded_at",
    }
    if set(payload) != required:
        raise BenchmarkResearchError("observation fields are invalid")
    _identifier(payload["observation_id"], "observation_id")
    for field in ("title", "source_kind", "observed_behavior"):
        _text(payload[field], field)
    _strings(payload["source_references"], "source_references", allow_empty=True)
    _identities(
        payload["source_dataset_identities"],
        "source_dataset_identities",
        allow_empty=True,
    )
    normalized = dict(payload)
    normalized["recorded_at"] = _timestamp(payload["recorded_at"], "recorded_at")
    return make_artifact("observation", normalized)


def _create_hypothesis(
    payload: Mapping[str, object],
    observation: Mapping[str, object],
    *,
    child_authorized: bool,
) -> dict[str, object]:
    observation = validate_artifact(observation, "observation")
    required = {
        "hypothesis_id",
        "revision",
        "parent_hypothesis_identity",
        "title",
        "market_assumption",
        "mechanism",
        "required_evidence",
        "expected_edge",
        "invalidation_conditions",
        "known_risks",
        "required_indicators",
        "expected_holding_period",
        "expected_market_regime",
        "expected_failure_modes",
        "taxonomy",
        "contaminated_dataset_identities",
        "multiple_testing_family",
    }
    if set(payload) != required:
        raise BenchmarkResearchError("hypothesis fields are invalid")
    _identifier(payload["hypothesis_id"], "hypothesis_id")
    if type(payload["revision"]) is not int or payload["revision"] < 1:
        raise BenchmarkResearchError("hypothesis revision must be positive")
    parent = payload["parent_hypothesis_identity"]
    if parent is not None:
        _identity(parent, "parent_hypothesis_identity")
    for field in (
        "title",
        "market_assumption",
        "mechanism",
        "expected_edge",
        "expected_holding_period",
        "expected_market_regime",
        "multiple_testing_family",
    ):
        _text(payload[field], field)
    for field in (
        "required_evidence",
        "invalidation_conditions",
        "known_risks",
        "required_indicators",
        "expected_failure_modes",
        "taxonomy",
    ):
        _strings(payload[field], field)
    contaminated = _identities(
        payload["contaminated_dataset_identities"],
        "contaminated_dataset_identities",
        allow_empty=True,
    )
    observed_datasets = observation["payload"]["source_dataset_identities"]
    if not set(observed_datasets).issubset(contaminated):
        raise BenchmarkResearchError(
            "observation datasets must remain permanently contaminated"
        )
    if (parent is None) != (payload["revision"] == 1):
        raise BenchmarkResearchError("hypothesis parent and revision disagree")
    if parent is not None and not child_authorized:
        raise BenchmarkResearchError(
            "post-preregistration revisions require create_child_hypothesis"
        )
    parents = [observation["identity"]]
    if parent is not None:
        parents.append(parent)
    return make_artifact("hypothesis", payload, parent_identities=parents)


def create_hypothesis(
    payload: Mapping[str, object], observation: Mapping[str, object]
) -> dict[str, object]:
    """Create a root hypothesis; frozen revisions use the child-only API."""

    return _create_hypothesis(payload, observation, child_authorized=False)


def create_triage(
    payload: Mapping[str, object], hypothesis: Mapping[str, object]
) -> dict[str, object]:
    hypothesis = validate_artifact(hypothesis, "hypothesis")
    required = {
        "hypothesis_identity",
        "disposition",
        "duplicate_signature",
        "duplicate_hypothesis_identities",
        "priority_vector",
        "reasons",
    }
    if set(payload) != required or payload["hypothesis_identity"] != hypothesis["identity"]:
        raise BenchmarkResearchError("triage fields or hypothesis binding are invalid")
    if payload["disposition"] not in {"admit", "reject_duplicate", "reject_scope"}:
        raise BenchmarkResearchError("triage disposition is invalid")
    _identity(payload["duplicate_signature"], "duplicate_signature")
    duplicates = _identities(
        payload["duplicate_hypothesis_identities"],
        "duplicate_hypothesis_identities",
        allow_empty=True,
    )
    if payload["disposition"] == "admit" and duplicates:
        raise BenchmarkResearchError("admitted hypothesis cannot have exact duplicates")
    priority = payload["priority_vector"]
    fields = (
        "mechanism_plausibility",
        "supporting_evidence",
        "expected_frequency",
        "data_readiness",
        "distinctness",
        "falsification_value",
        "engineering_cost",
        "contamination_risk",
    )
    if not isinstance(priority, Mapping) or set(priority) != set(fields):
        raise BenchmarkResearchError("priority vector fields or order are invalid")
    if any(type(priority[field]) is not int or not 0 <= priority[field] <= 3 for field in fields):
        raise BenchmarkResearchError("priority vector values must be integers from 0 to 3")
    _strings(payload["reasons"], "reasons")
    return make_artifact(
        "triage", payload, parent_identities=(hypothesis["identity"],)
    )


def create_specification(
    payload: Mapping[str, object],
    hypothesis: Mapping[str, object],
    triage: Mapping[str, object],
) -> dict[str, object]:
    hypothesis = validate_artifact(hypothesis, "hypothesis")
    triage = validate_artifact(triage, "triage")
    required = {
        "hypothesis_identity",
        "strategy_id",
        "strategy_version",
        "direction",
        "required_input_fields",
        "decision_window",
        "signal_rule",
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
    }
    if set(payload) != required or payload["hypothesis_identity"] != hypothesis["identity"]:
        raise BenchmarkResearchError("specification fields or hypothesis binding are invalid")
    if triage["payload"]["disposition"] != "admit":
        raise BenchmarkResearchError("only an admitted hypothesis may be specified")
    _identifier(payload["strategy_id"], "strategy_id")
    for field in (
        "strategy_version",
        "direction",
        "decision_window",
        "signal_rule",
        "entry_rule",
        "stop_rule",
        "target_rule",
        "missing_data_rule",
        "integrity_rule",
        "downstream_proposal_type",
        "classification_function",
    ):
        _text(payload[field], field)
    _strings(payload["required_input_fields"], "required_input_fields")
    if type(payload["timeout_minutes"]) is not int or payload["timeout_minutes"] < 1:
        raise BenchmarkResearchError("timeout_minutes must be positive")
    if (
        type(payload["maximum_entries_per_symbol_session"]) is not int
        or payload["maximum_entries_per_symbol_session"] < 1
    ):
        raise BenchmarkResearchError("maximum entries must be positive")
    threshold = payload["material_data_limitation_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise BenchmarkResearchError("material data limitation threshold is invalid")
    if not 0 <= float(threshold) <= 1:
        raise BenchmarkResearchError("material data limitation threshold is outside [0,1]")
    if payload["strategy_id"] != CANDIDATE_ID or payload["strategy_version"] != CANDIDATE_VERSION:
        raise BenchmarkResearchError("vertical-slice candidate identity changed")
    if payload["downstream_proposal_type"] != "aml.portfolio_simulator.StrategyProposal":
        raise BenchmarkResearchError("downstream proposal binding changed")
    if payload["classification_function"] != "aml.discovery_screen_v001.classify":
        raise BenchmarkResearchError("discovery classification binding changed")
    return make_artifact(
        "specification",
        payload,
        parent_identities=(hypothesis["identity"], triage["identity"]),
    )


def preregister(
    payload: Mapping[str, object],
    observation: Mapping[str, object],
    hypothesis: Mapping[str, object],
    triage: Mapping[str, object],
    specification: Mapping[str, object],
) -> dict[str, object]:
    artifacts = (
        validate_artifact(observation, "observation"),
        validate_artifact(hypothesis, "hypothesis"),
        validate_artifact(triage, "triage"),
        validate_artifact(specification, "specification"),
    )
    required = {
        "observation_identity",
        "hypothesis_identity",
        "triage_identity",
        "specification_identity",
        "permitted_discovery_dataset_identities",
        "prohibited_dataset_labels",
        "contaminated_dataset_identities",
        "preregistered_at",
        "research_definitions_locked",
    }
    expected = [artifact["identity"] for artifact in artifacts]
    if set(payload) != required or [
        payload["observation_identity"],
        payload["hypothesis_identity"],
        payload["triage_identity"],
        payload["specification_identity"],
    ] != expected:
        raise BenchmarkResearchError("preregistration lineage is invalid")
    permitted = _identities(
        payload["permitted_discovery_dataset_identities"],
        "permitted_discovery_dataset_identities",
    )
    contaminated = _identities(
        payload["contaminated_dataset_identities"],
        "contaminated_dataset_identities",
        allow_empty=True,
    )
    if contaminated != hypothesis["payload"]["contaminated_dataset_identities"]:
        raise BenchmarkResearchError("preregistration contamination set changed")
    if set(permitted).intersection(contaminated):
        raise BenchmarkResearchError("contaminated data cannot be permitted for evaluation")
    prohibited = _strings(
        payload["prohibited_dataset_labels"], "prohibited_dataset_labels"
    )
    prohibited_text = " ".join(prohibited).casefold()
    if "forward validation" not in prohibited_text or "holdout" not in prohibited_text:
        raise BenchmarkResearchError(
            "preregistration must explicitly prohibit forward validation and holdout"
        )
    if payload["research_definitions_locked"] is not True:
        raise BenchmarkResearchError("preregistration must lock research definitions")
    normalized = dict(payload)
    normalized["preregistered_at"] = _timestamp(
        payload["preregistered_at"], "preregistered_at"
    )
    return make_artifact(
        "preregistration", normalized, parent_identities=tuple(expected)
    )


def bind_implementation(
    repository_root: Path,
    payload: Mapping[str, object],
    preregistration: Mapping[str, object],
    specification: Mapping[str, object],
) -> dict[str, object]:
    preregistration = validate_artifact(preregistration, "preregistration")
    specification = validate_artifact(specification, "specification")
    required = {
        "preregistration_identity",
        "specification_identity",
        "implementation_callable",
        "implementation_files",
        "downstream_files",
        "no_frozen_file_modified",
    }
    if set(payload) != required:
        raise BenchmarkResearchError("implementation binding fields are invalid")
    if payload["preregistration_identity"] != preregistration["identity"] or payload[
        "specification_identity"
    ] != specification["identity"]:
        raise BenchmarkResearchError("implementation binding lineage is invalid")
    if payload["implementation_callable"] != (
        "aml.benchmark_research_candidate_v001."
        "evaluate_opening_range_midpoint_reclaim"
    ):
        raise BenchmarkResearchError("implementation callable changed")
    expected_implementation = [
        "src/aml/benchmark_research_candidate_v001.py",
        "src/aml/benchmark_strategy_research_v001.py",
    ]
    expected_downstream = [
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
    ]
    if payload["implementation_files"] != expected_implementation:
        raise BenchmarkResearchError("implementation file binding changed")
    if payload["downstream_files"] != expected_downstream:
        raise BenchmarkResearchError("downstream file binding changed")
    if payload["no_frozen_file_modified"] is not True:
        raise BenchmarkResearchError("implementation must preserve frozen files")
    root = Path(repository_root).resolve()
    source_hashes: dict[str, str] = {}
    for relative in expected_implementation + expected_downstream:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise BenchmarkResearchError(f"bound source file is invalid: {relative}")
        source_hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    normalized = {**payload, "source_sha256": source_hashes}
    return make_artifact(
        "implementation_binding",
        normalized,
        parent_identities=(preregistration["identity"], specification["identity"]),
    )


def verify_implementation_binding(
    repository_root: Path, binding: Mapping[str, object]
) -> dict[str, object]:
    """Recalculate all source bindings immediately before candidate execution."""

    binding = validate_artifact(binding, "implementation_binding")
    root = Path(repository_root).resolve()
    recorded = binding["payload"].get("source_sha256")
    if not isinstance(recorded, Mapping) or not recorded:
        raise BenchmarkResearchError("implementation source bindings are missing")
    expected_paths = (
        binding["payload"]["implementation_files"]
        + binding["payload"]["downstream_files"]
    )
    if sorted(recorded) != sorted(expected_paths):
        raise BenchmarkResearchError("implementation source binding paths changed")
    for relative in expected_paths:
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != recorded[relative]
        ):
            raise BenchmarkResearchError(f"bound implementation changed:{relative}")
    return binding


def record_conformance(
    payload: Mapping[str, object],
    binding: Mapping[str, object],
) -> dict[str, object]:
    binding = validate_artifact(binding, "implementation_binding")
    required = {
        "implementation_binding_identity",
        "positive_path",
        "negative_path",
        "unavailable_path",
        "integrity_failure_path",
        "no_lookahead_path",
        "deterministic_path",
        "proposal_pipeline_path",
        "all_checks_passed",
    }
    if set(payload) != required or payload["implementation_binding_identity"] != binding["identity"]:
        raise BenchmarkResearchError("conformance fields or binding are invalid")
    check_fields = sorted(required - {"implementation_binding_identity", "all_checks_passed"})
    if any(payload[field] is not True for field in check_fields):
        raise BenchmarkResearchError("every conformance path must pass")
    if payload["all_checks_passed"] is not True:
        raise BenchmarkResearchError("conformance did not pass")
    return make_artifact(
        "conformance", payload, parent_identities=(binding["identity"],)
    )


def run_candidate_conformance(
    fixture: pd.DataFrame,
    *,
    dataset_identity: str,
    hypothesis: Mapping[str, object],
    specification: Mapping[str, object],
    preregistration: Mapping[str, object],
    binding: Mapping[str, object],
) -> dict[str, object]:
    """Exercise every required candidate path without creating research evidence."""

    hypothesis = validate_artifact(hypothesis, "hypothesis")
    specification = validate_artifact(specification, "specification")
    preregistration = validate_artifact(preregistration, "preregistration")
    binding = validate_artifact(binding, "implementation_binding")
    dataset_identity = _identity(dataset_identity, "dataset_identity")
    frame = fixture.copy(deep=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if len(frame) < 8:
        raise BenchmarkResearchError("conformance fixture is too short")
    kwargs = {
        "hypothesis_identity": hypothesis["identity"],
        "specification_identity": specification["identity"],
        "preregistration_identity": preregistration["identity"],
        "implementation_binding_identity": binding["identity"],
        "dataset_identity": dataset_identity,
    }
    positive_prefix = frame.iloc[:7].copy(deep=True)
    positive = evaluate_opening_range_midpoint_reclaim(positive_prefix, **kwargs)
    if positive.status != "proposal" or positive.proposal is None:
        raise BenchmarkResearchError("candidate positive conformance path failed")
    negative_prefix = positive_prefix.copy(deep=True)
    negative_prefix.loc[negative_prefix.index[-1], ["open", "close", "high"]] = [
        10.1,
        10.1,
        10.2,
    ]
    negative = evaluate_opening_range_midpoint_reclaim(negative_prefix, **kwargs)
    if negative.status != "no_signal" or negative.proposal is not None:
        raise BenchmarkResearchError("candidate negative conformance path failed")
    unavailable_prefix = positive_prefix.drop(index=positive_prefix.index[2]).reset_index(drop=True)
    unavailable = evaluate_opening_range_midpoint_reclaim(unavailable_prefix, **kwargs)
    if unavailable.status != "unavailable" or unavailable.proposal is not None:
        raise BenchmarkResearchError("candidate unavailable conformance path failed")
    duplicate_prefix = pd.concat(
        [positive_prefix, positive_prefix.iloc[[-1]]], ignore_index=True
    )
    try:
        evaluate_opening_range_midpoint_reclaim(duplicate_prefix, **kwargs)
    except CandidateIntegrityError:
        integrity_passed = True
    else:
        integrity_passed = False
    if not integrity_passed:
        raise BenchmarkResearchError("candidate integrity conformance path failed")
    repeated = evaluate_opening_range_midpoint_reclaim(positive_prefix, **kwargs)
    if repeated.proposal is None or repeated.proposal.proposal_id != positive.proposal.proposal_id:
        raise BenchmarkResearchError("candidate deterministic conformance path failed")
    changed_future = frame.copy(deep=True)
    changed_future.loc[changed_future.index[7]:, ["open", "high", "low", "close"]] *= 1.5
    unchanged_prefix = changed_future.iloc[:7]
    no_lookahead = evaluate_opening_range_midpoint_reclaim(unchanged_prefix, **kwargs)
    if no_lookahead.proposal is None or no_lookahead.proposal.proposal_id != positive.proposal.proposal_id:
        raise BenchmarkResearchError("candidate no-lookahead conformance path failed")
    settings = PortfolioConfig(
        total_capital=100_000.0,
        strategy_allocations=(
            StrategyAllocation(CANDIDATE_ID, CANDIDATE_VERSION, 100_000.0),
        ),
        maximum_position_risk_fraction=0.0025,
        maximum_concurrent_positions=3,
        maximum_symbol_concentration_fraction=0.5,
        maximum_strategy_concentration_fraction=1.0,
        daily_loss_limit_fraction=0.01,
        slippage_fraction=0.001,
        maximum_entry_delay_minutes=0,
    )
    downstream = simulate_portfolio(
        [positive.proposal],
        {str(frame.iloc[0]["symbol"]): frame},
        settings,
    )
    if len(downstream.proposal_audit) != 1 or downstream.proposal_audit.iloc[0]["status"] not in {
        "accepted",
        "rejected",
    }:
        raise BenchmarkResearchError("existing proposal pipeline conformance path failed")
    return record_conformance(
        {
            "implementation_binding_identity": binding["identity"],
            "positive_path": True,
            "negative_path": True,
            "unavailable_path": True,
            "integrity_failure_path": True,
            "no_lookahead_path": True,
            "deterministic_path": True,
            "proposal_pipeline_path": True,
            "all_checks_passed": True,
        },
        binding,
    )


def _decision_prefixes(frame: pd.DataFrame) -> Sequence[pd.DataFrame]:
    prepared = frame.copy(deep=True)
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"])
    local = prepared["timestamp"].dt.tz_convert("America/New_York")
    indices = [
        index
        for index, clock in enumerate(local.dt.strftime("%H:%M"))
        if "09:36" <= clock <= "10:30"
    ]
    return tuple(prepared.iloc[: index + 1].copy(deep=True) for index in indices)


def _candidate_decisions(
    bars_by_symbol: Mapping[str, pd.DataFrame],
    *,
    hypothesis_identity: str,
    specification_identity: str,
    preregistration_identity: str,
    implementation_binding_identity: str,
    dataset_identity: str,
    evaluator: Callable[..., CandidateDecision],
) -> tuple[list[CandidateDecision], list[StrategyProposal], int]:
    decisions: list[CandidateDecision] = []
    proposals: list[StrategyProposal] = []
    integrity_failure_count = 0
    for symbol, frame in sorted(bars_by_symbol.items()):
        emitted = False
        for prefix in _decision_prefixes(frame):
            try:
                decision = evaluator(
                    prefix,
                    hypothesis_identity=hypothesis_identity,
                    specification_identity=specification_identity,
                    preregistration_identity=preregistration_identity,
                    implementation_binding_identity=implementation_binding_identity,
                    dataset_identity=dataset_identity,
                )
            except CandidateIntegrityError:
                integrity_failure_count += 1
                break
            decisions.append(decision)
            if decision.status == "proposal":
                if decision.proposal is None or decision.proposal.symbol != symbol.upper():
                    integrity_failure_count += 1
                    break
                proposals.append(decision.proposal)
                emitted = True
                break
            if decision.proposal is not None:
                integrity_failure_count += 1
                break
        if emitted:
            continue
    return decisions, proposals, integrity_failure_count


def _completed_trades(
    trades: pd.DataFrame,
    *,
    strategy_identity: str,
    cost_scenario: str,
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


def execute_discovery(
    bars_by_symbol: Mapping[str, pd.DataFrame],
    *,
    repository_root: Path,
    dataset_identity: str,
    hypothesis: Mapping[str, object],
    specification: Mapping[str, object],
    preregistration: Mapping[str, object],
    binding: Mapping[str, object],
    conformance: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Execute one identity-bound candidate through unchanged downstream code."""

    hypothesis = validate_artifact(hypothesis, "hypothesis")
    specification = validate_artifact(specification, "specification")
    preregistration = validate_artifact(preregistration, "preregistration")
    binding = verify_implementation_binding(repository_root, binding)
    conformance = validate_artifact(conformance, "conformance")
    dataset_identity = _identity(dataset_identity, "dataset_identity")
    prereg = preregistration["payload"]
    if dataset_identity not in prereg["permitted_discovery_dataset_identities"]:
        raise BenchmarkResearchError("dataset is not permitted by preregistration")
    if dataset_identity in prereg["contaminated_dataset_identities"]:
        raise BenchmarkResearchError("contaminated data cannot evaluate the hypothesis")
    if binding["identity"] != conformance["payload"]["implementation_binding_identity"]:
        raise BenchmarkResearchError("conformance does not bind the implementation")
    provenance = {
        "hypothesis_identity": hypothesis["identity"],
        "specification_identity": specification["identity"],
        "preregistration_identity": preregistration["identity"],
        "implementation_binding_identity": binding["identity"],
        "dataset_identity": dataset_identity,
    }
    for symbol, frame in sorted(bars_by_symbol.items()):
        try:
            complete = evaluate_opening_range_midpoint_reclaim(frame, **provenance)
        except CandidateIntegrityError as exc:
            raise BenchmarkResearchError(
                f"candidate discovery input integrity failure:{symbol}"
            ) from exc
        if complete.status == "unavailable":
            raise BenchmarkResearchError(
                f"candidate discovery input incomplete:{symbol}:{complete.reason_codes[0]}"
            )
    decisions, proposals, integrity_failure_count = _candidate_decisions(
        bars_by_symbol,
        **provenance,
        evaluator=evaluate_opening_range_midpoint_reclaim,
    )
    if integrity_failure_count:
        raise BenchmarkResearchError(
            f"candidate integrity failures prevent discovery:{integrity_failure_count}"
        )
    status_counts = {
        status: sum(decision.status == status for decision in decisions)
        for status in ("proposal", "no_signal", "unavailable")
    }
    evaluation_count = len(decisions)
    unavailable_fraction = (
        status_counts["unavailable"] / evaluation_count if evaluation_count else 1.0
    )
    threshold = float(
        specification["payload"]["material_data_limitation_threshold"]
    )
    material_data_limitation = unavailable_fraction > threshold
    scenario_metrics: dict[str, object] = {}
    scenario_trades: dict[str, list[dict[str, object]]] = {}
    base_audit: list[dict[str, object]] = []
    scenario_counts: dict[str, int] = {}
    for name, slippage in (("base", 0.001), ("cost_1_5x", 0.0015), ("cost_2x", 0.002)):
        settings = PortfolioConfig(
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
        downstream = simulate_portfolio(proposals, bars_by_symbol, settings)
        completed = _completed_trades(
            downstream.trades,
            strategy_identity=specification["identity"],
            cost_scenario=name,
        )
        scenario_metrics[name] = trade_metrics(completed)
        scenario_counts[name] = len(completed)
        scenario_trades[name] = [asdict(item) for item in completed]
        if name == "base":
            base_audit = _jsonable(downstream.proposal_audit.to_dict("records"))
    if len(set(scenario_counts.values())) != 1:
        raise BenchmarkResearchError("cost scenario trade counts do not reconcile")
    metrics = {
        "trade_count": scenario_counts["base"],
        **scenario_metrics,
    }
    classification = classify(
        metrics, material_data_limitation=material_data_limitation
    )
    accepted = scenario_counts["base"]
    rejected = sum(row["status"] == "rejected" for row in base_audit)
    if len(proposals) != accepted + rejected:
        raise BenchmarkResearchError("proposal acceptance reconciliation failed")
    discovery_payload: dict[str, object] = {
        "hypothesis_identity": hypothesis["identity"],
        "specification_identity": specification["identity"],
        "preregistration_identity": preregistration["identity"],
        "implementation_binding_identity": binding["identity"],
        "conformance_identity": conformance["identity"],
        "dataset_identity": dataset_identity,
        "evidence_class": "synthetic_non_empirical_vertical_slice",
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
    }
    discovery = make_artifact(
        "discovery",
        discovery_payload,
        parent_identities=(
            hypothesis["identity"],
            specification["identity"],
            preregistration["identity"],
            binding["identity"],
            conformance["identity"],
        ),
    )
    classification_artifact = make_artifact(
        "classification",
        {
            "discovery_identity": discovery["identity"],
            "classification": classification,
            "classification_function": "aml.discovery_screen_v001.classify",
            "evidence_class": "synthetic_non_empirical_vertical_slice",
            "validation_eligible": False,
            "claim_ceiling": "pipeline_execution_only_no_empirical_edge_claim",
        },
        parent_identities=(discovery["identity"],),
    )
    return discovery, classification_artifact


def create_archive(
    *,
    hypothesis: Mapping[str, object],
    archive_state: str,
    reason: str,
    related_artifacts: Sequence[Mapping[str, object]],
    empirical_outcomes_accessed: bool,
) -> dict[str, object]:
    hypothesis = validate_artifact(hypothesis, "hypothesis")
    if archive_state not in TERMINAL_ARCHIVE_STATES:
        raise BenchmarkResearchError("archive state is invalid")
    reason = _text(reason, "archive reason")
    related = [validate_artifact(item) for item in related_artifacts]
    related_identities = sorted({item["identity"] for item in related})
    classifications = [
        item for item in related if item["artifact_type"] == "classification"
    ]
    if archive_state in {"completed", "rejected"} and not classifications:
        raise BenchmarkResearchError("completed or rejected archive requires classification")
    if archive_state == "rejected" and any(
        item["payload"].get("classification") != "REJECT"
        for item in classifications
    ):
        raise BenchmarkResearchError("rejected archive requires a REJECT classification")
    if archive_state == "completed" and any(
        item["payload"].get("classification") == "REJECT"
        for item in classifications
    ):
        raise BenchmarkResearchError("REJECT classification requires rejected archive")
    related_by_identity = {item["identity"]: item for item in related}
    for classification in classifications:
        discovery_identity = classification["payload"].get("discovery_identity")
        discovery = related_by_identity.get(discovery_identity)
        if discovery is None or discovery["artifact_type"] != "discovery":
            raise BenchmarkResearchError(
                "archived classification requires its discovery artifact"
            )
        if discovery["payload"].get("hypothesis_identity") != hypothesis["identity"]:
            raise BenchmarkResearchError(
                "archived classification belongs to another hypothesis"
            )
    if archive_state == "abandoned" and empirical_outcomes_accessed:
        raise BenchmarkResearchError(
            "post-outcome work cannot be abandoned without classification"
        )
    if archive_state == "superseded" and not any(
        item["artifact_type"] == "preregistration" for item in related
    ):
        raise BenchmarkResearchError("post-freeze supersession requires preregistration")
    if archive_state == "superseded" and not any(
        item["artifact_type"] == "hypothesis"
        and item["payload"].get("parent_hypothesis_identity") == hypothesis["identity"]
        for item in related
    ):
        raise BenchmarkResearchError("supersession archive requires its child hypothesis")
    return make_artifact(
        "archive",
        {
            "hypothesis_identity": hypothesis["identity"],
            "archive_state": archive_state,
            "reason": reason,
            "related_artifact_identities": related_identities,
            "empirical_outcomes_accessed": empirical_outcomes_accessed,
        },
        parent_identities=(hypothesis["identity"], *related_identities),
    )


def create_child_hypothesis(
    parent_hypothesis: Mapping[str, object],
    parent_preregistration: Mapping[str, object],
    child_payload: Mapping[str, object],
    *,
    datasets_used_after_preregistration: Sequence[str],
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Create the only permitted representation of a post-freeze modification."""

    parent = validate_artifact(parent_hypothesis, "hypothesis")
    preregistration = validate_artifact(parent_preregistration, "preregistration")
    if preregistration["payload"]["hypothesis_identity"] != parent["identity"]:
        raise BenchmarkResearchError("parent preregistration does not bind hypothesis")
    used = sorted({_identity(item, "used dataset identity") for item in datasets_used_after_preregistration})
    expected_contaminated = sorted(
        set(parent["payload"]["contaminated_dataset_identities"]).union(used)
    )
    if child_payload.get("parent_hypothesis_identity") != parent["identity"]:
        raise BenchmarkResearchError("child must name the frozen parent identity")
    if child_payload.get("revision") != parent["payload"]["revision"] + 1:
        raise BenchmarkResearchError("child revision must increment exactly once")
    if child_payload.get("contaminated_dataset_identities") != expected_contaminated:
        raise BenchmarkResearchError("child must inherit all contaminated data")
    child = _create_hypothesis(child_payload, observation, child_authorized=True)
    if child["identity"] == parent["identity"]:
        raise BenchmarkResearchError("post-freeze change must create a new identity")
    return child


def _validate_complete_lifecycle(
    artifacts: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    validated = [validate_artifact(item) for item in artifacts]
    required_types = [
        "observation",
        "hypothesis",
        "triage",
        "specification",
        "preregistration",
        "implementation_binding",
        "conformance",
        "discovery",
        "classification",
        "archive",
    ]
    if [item["artifact_type"] for item in validated] != required_types:
        raise BenchmarkResearchError("complete lifecycle bundle order is invalid")
    by_type = {item["artifact_type"]: item for item in validated}
    observation = by_type["observation"]
    hypothesis = by_type["hypothesis"]
    triage = by_type["triage"]
    specification = by_type["specification"]
    registration = by_type["preregistration"]
    binding = by_type["implementation_binding"]
    conformance = by_type["conformance"]
    discovery = by_type["discovery"]
    classification = by_type["classification"]
    archive = by_type["archive"]
    if hypothesis["parent_identities"] != [observation["identity"]]:
        raise BenchmarkResearchError("bundle must contain one root hypothesis")
    if triage["payload"].get("hypothesis_identity") != hypothesis["identity"]:
        raise BenchmarkResearchError("bundle triage lineage is invalid")
    if specification["payload"].get("hypothesis_identity") != hypothesis["identity"]:
        raise BenchmarkResearchError("bundle specification lineage is invalid")
    expected_registration = {
        "observation_identity": observation["identity"],
        "hypothesis_identity": hypothesis["identity"],
        "triage_identity": triage["identity"],
        "specification_identity": specification["identity"],
    }
    if any(
        registration["payload"].get(field) != identity
        for field, identity in expected_registration.items()
    ):
        raise BenchmarkResearchError("bundle preregistration lineage is invalid")
    if binding["payload"].get("preregistration_identity") != registration["identity"]:
        raise BenchmarkResearchError("bundle implementation lineage is invalid")
    if binding["payload"].get("specification_identity") != specification["identity"]:
        raise BenchmarkResearchError("bundle implementation lineage is invalid")
    if conformance["payload"].get("implementation_binding_identity") != binding["identity"]:
        raise BenchmarkResearchError("bundle conformance lineage is invalid")
    expected_discovery = {
        "hypothesis_identity": hypothesis["identity"],
        "specification_identity": specification["identity"],
        "preregistration_identity": registration["identity"],
        "implementation_binding_identity": binding["identity"],
        "conformance_identity": conformance["identity"],
    }
    if any(
        discovery["payload"].get(field) != identity
        for field, identity in expected_discovery.items()
    ):
        raise BenchmarkResearchError("bundle discovery lineage is invalid")
    if classification["payload"].get("discovery_identity") != discovery["identity"]:
        raise BenchmarkResearchError("bundle classification lineage is invalid")
    expected_related = sorted(item["identity"] for item in validated[0:9] if item is not hypothesis)
    if archive["payload"].get("hypothesis_identity") != hypothesis["identity"] or archive[
        "payload"
    ].get("related_artifact_identities") != expected_related:
        raise BenchmarkResearchError("bundle archive lineage is incomplete")
    return validated


def write_bundle(output_root: Path, artifacts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Publish one complete lifecycle bundle atomically and write-once."""

    raw_root = Path(output_root)
    if ".." in raw_root.parts:
        raise BenchmarkResearchError("research output cannot contain traversal")
    root = raw_root.resolve()
    protected = {"validation", "holdout", "forward-validation", "olympics"}
    if any(part.casefold().replace("_", "-") in protected for part in root.parts):
        raise BenchmarkResearchError("research output crosses a protected boundary")
    if root.exists():
        raise BenchmarkResearchError("research output already exists")
    validated = _validate_complete_lifecycle(artifacts)
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    try:
        files: list[dict[str, object]] = []
        for index, artifact in enumerate(validated, start=1):
            name = f"{index:02d}-{artifact['artifact_type']}.json"
            data = canonical_json(artifact)
            path = staging / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            files.append(
                {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            )
        manifest_base: dict[str, object] = {
            "schema_version": "aml.benchmark-strategy-research.bundle.v001",
            "framework_version": FRAMEWORK_VERSION,
            "artifact_identities": [item["identity"] for item in validated],
            "files": files,
            "immutable": True,
        }
        manifest = {**manifest_base, "identity": canonical_hash(manifest_base)}
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging, root)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_bundle(output_root: Path) -> dict[str, object]:
    raw_root = Path(output_root)
    if ".." in raw_root.parts:
        raise BenchmarkResearchError("research bundle path cannot contain traversal")
    root = raw_root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BenchmarkResearchError("research bundle manifest is missing")
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkResearchError("research bundle manifest is malformed") from exc
    required = {
        "schema_version",
        "framework_version",
        "artifact_identities",
        "files",
        "immutable",
        "identity",
    }
    if not isinstance(raw_manifest, dict) or set(raw_manifest) != required:
        raise BenchmarkResearchError("research bundle manifest schema is invalid")
    if raw_manifest["schema_version"] != "aml.benchmark-strategy-research.bundle.v001":
        raise BenchmarkResearchError("research bundle manifest schema changed")
    if raw_manifest["framework_version"] != FRAMEWORK_VERSION:
        raise BenchmarkResearchError("research bundle framework changed")
    if raw_manifest["immutable"] is not True:
        raise BenchmarkResearchError("research bundle must be immutable")
    identity = _identity(raw_manifest["identity"], "bundle identity")
    manifest = {key: value for key, value in raw_manifest.items() if key != "identity"}
    if canonical_hash(manifest) != identity:
        raise BenchmarkResearchError("research bundle identity is stale or tampered")
    if not isinstance(manifest["files"], list) or len(manifest["files"]) != 10:
        raise BenchmarkResearchError("research bundle file inventory is invalid")
    artifact_manifest_identities = manifest["artifact_identities"]
    if not isinstance(artifact_manifest_identities, list) or len(
        artifact_manifest_identities
    ) != 10:
        raise BenchmarkResearchError("research bundle artifact inventory is invalid")
    for artifact_identity in artifact_manifest_identities:
        _identity(artifact_identity, "artifact identity")
    if len(set(artifact_manifest_identities)) != len(artifact_manifest_identities):
        raise BenchmarkResearchError("research bundle artifact identities repeat")
    artifact_identities: list[str] = []
    artifacts: list[dict[str, object]] = []
    expected_names = [
        "01-observation.json",
        "02-hypothesis.json",
        "03-triage.json",
        "04-specification.json",
        "05-preregistration.json",
        "06-implementation_binding.json",
        "07-conformance.json",
        "08-discovery.json",
        "09-classification.json",
        "10-archive.json",
    ]
    for index, record in enumerate(manifest["files"], start=1):
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "bytes"}:
            raise BenchmarkResearchError("research bundle file record is invalid")
        _identity(record["sha256"], "research bundle file hash")
        if type(record["bytes"]) is not int or not 0 < record["bytes"] <= MAX_ARTIFACT_BYTES:
            raise BenchmarkResearchError("research bundle file size is invalid")
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise BenchmarkResearchError("research bundle file path is unsafe")
        if relative.name != expected_names[index - 1]:
            raise BenchmarkResearchError("research bundle file order is invalid")
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != record["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise BenchmarkResearchError("research bundle file hash mismatch")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BenchmarkResearchError("research bundle artifact is malformed") from exc
        artifact = validate_artifact(value)
        artifacts.append(artifact)
        artifact_identities.append(artifact["identity"])
    if artifact_identities != manifest["artifact_identities"]:
        raise BenchmarkResearchError("research bundle artifact order changed")
    _validate_complete_lifecycle(artifacts)
    return {**manifest, "identity": identity, "verified": True}
