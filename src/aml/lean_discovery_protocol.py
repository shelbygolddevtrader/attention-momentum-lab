"""Fail-closed contracts for the provider-bounded lean discovery protocol."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Mapping, Sequence

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


PROTOCOL_SCHEMA = "aml.lean-discovery.protocol.v001"
READINESS_SCHEMA = "aml.lean-discovery.readiness.v001"
PROTOCOL_VERSION = "lean-discovery-protocol-v001"
ARTIFACT_NAMESPACE = "artifacts/lean_discovery/v001"
V002_PROTOCOL_IDENTITY = (
    "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
)
V002_READINESS_IDENTITY = (
    "01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6"
)
PROTECTED_PARTS = {
    "validation",
    "holdout",
    "sealed",
    "production",
    "operator",
    "paper-forward",
    "paper_forward",
    "validation-extension",
    "validation_extension",
}
REQUIRED_EVIDENCE = (
    "code_identity",
    "corporate_action_manifest",
    "discovery_input_manifest",
    "entitlement_evidence",
    "final_partition_manifest",
    "human_authorization",
    "provider_capability_evidence",
    "retrieval_time_asset_snapshot_manifest",
    "sealed_partition_evidence",
    "selection_only_count_manifest",
)


class LeanProtocolError(ValueError):
    """A lean-protocol integrity boundary was violated."""


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise LeanProtocolError("Lean protocol input is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise LeanProtocolError("Lean protocol JSON contains duplicate keys")
            value[key] = item
        return value

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(LeanProtocolError(item)),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, LeanProtocolError) as exc:
        raise LeanProtocolError("Lean protocol input is not strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise LeanProtocolError("Lean protocol root must be an object")
    try:
        canonical_json(result)
    except ValueError as exc:
        raise LeanProtocolError("Lean protocol input contains invalid values") from exc
    return result


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise LeanProtocolError(f"{field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LeanProtocolError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LeanProtocolError(f"{field} must include a timezone")
    return parsed


def _require_mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise LeanProtocolError(f"{label} contains missing or unexpected fields")
    return value


def _validate_registry(items: object, label: str, required: set[str]) -> None:
    if not isinstance(items, list) or not items:
        raise LeanProtocolError(f"{label} must be a non-empty list")
    identifiers: list[str] = []
    for item in items:
        if not isinstance(item, Mapping) or not required <= set(item):
            raise LeanProtocolError(f"{label} entry is incomplete")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise LeanProtocolError(f"{label} identifier is malformed")
        identifiers.append(identifier)
    if identifiers != sorted(set(identifiers)):
        raise LeanProtocolError(f"{label} identifiers must be sorted and unique")


def validate_protocol(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version", "protocol_version", "prospective_as_of",
        "protocol_identity", "independence", "scientific_question",
        "claim_ladder", "calendar_and_cohort", "universe", "provider_scope",
        "candidate_selection", "feature_registry", "outcome_registry",
        "statistical_plan", "missing_data", "isolation", "cost_plan",
        "authorization",
    }
    if set(value) != expected:
        raise LeanProtocolError("Lean protocol contains missing or unexpected fields")
    if value["schema_version"] != PROTOCOL_SCHEMA or value["protocol_version"] != PROTOCOL_VERSION:
        raise LeanProtocolError("Unsupported lean protocol version")
    _timestamp(value["prospective_as_of"], "prospective_as_of")
    identity = value["protocol_identity"]
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise LeanProtocolError("protocol_identity must be a SHA-256 digest")
    payload = {key: item for key, item in value.items() if key != "protocol_identity"}
    if canonical_hash(payload) != identity:
        raise LeanProtocolError("Lean protocol identity is stale or tampered")

    independence = _require_mapping(
        value["independence"],
        {"v002_protocol_identity", "v002_readiness_identity", "v002_readiness_credit", "v002_mutation", "result_scope"},
        "independence",
    )
    if independence["v002_protocol_identity"] != V002_PROTOCOL_IDENTITY:
        raise LeanProtocolError("Frozen V002 protocol identity changed")
    if independence["v002_readiness_identity"] != V002_READINESS_IDENTITY:
        raise LeanProtocolError("Frozen V002 readiness identity changed")
    if independence["v002_readiness_credit"] != "none" or independence["v002_mutation"] != "prohibited":
        raise LeanProtocolError("Lean protocol cannot inherit or alter V002")

    cohort = _require_mapping(
        value["calendar_and_cohort"],
        {
            "session_plan_identity", "selection_sessions_sha256", "candidate_session_count",
            "candidate_start", "candidate_end", "warmup_start", "warmup_sessions",
            "initial_sessions", "extension_sessions",
            "maximum_sessions", "partition_basis_points", "selection_only_stop_rule",
            "minimum_candidate_counts", "outcome_access_before_freeze",
        },
        "calendar_and_cohort",
    )
    if cohort["initial_sessions"] != 60 or cohort["extension_sessions"] != 20:
        raise LeanProtocolError("Lean cohort must begin at 60 sessions and extend by 20")
    if cohort["warmup_sessions"] != 20 or cohort["warmup_start"] != "2024-05-03":
        raise LeanProtocolError("Lean cohort must retain the bound 20-session warmup")
    if cohort["maximum_sessions"] != 252 or cohort["candidate_session_count"] != 252:
        raise LeanProtocolError("Lean cohort must remain within the frozen candidates")
    if cohort["outcome_access_before_freeze"] != "prohibited":
        raise LeanProtocolError("Outcome access before partition freeze is prohibited")
    partition = cohort["partition_basis_points"]
    if not isinstance(partition, Mapping) or partition != {
        "discovery": 5000, "validation": 2500, "holdout": 2500
    }:
        raise LeanProtocolError("Lean partitions must remain chronological 50/25/25")

    _validate_registry(
        value["feature_registry"],
        "feature_registry",
        {"id", "observation_window", "cutoff", "definition", "missing_rule"},
    )
    _validate_registry(
        value["outcome_registry"],
        "outcome_registry",
        {"id", "observation_window", "definition", "missing_rule"},
    )
    isolation = value["isolation"]
    if not isinstance(isolation, Mapping) or isolation.get("artifact_namespace") != ARTIFACT_NAMESPACE:
        raise LeanProtocolError("Lean artifacts must use the dedicated namespace")
    if isolation.get("validation_outcome_access") != "prohibited_during_discovery":
        raise LeanProtocolError("Validation outcomes must remain sealed during discovery")
    if isolation.get("holdout_outcome_access") != "one_time_after_validation_freeze":
        raise LeanProtocolError("Holdout access rule is incomplete")
    if value["authorization"] != {
        "human_authorization_required": True,
        "live_or_paper_orders": "prohibited",
        "pilot_authorized": False,
    }:
        raise LeanProtocolError("Tracked lean protocol must remain unauthorized")
    return dict(value)


def load_protocol(path: Path) -> dict[str, object]:
    return validate_protocol(_strict_json(path))


def canonical_protocol_bytes(path: Path) -> bytes:
    return canonical_json(load_protocol(path))


def build_readiness(
    protocol: Mapping[str, object], evidence: Mapping[str, str] | None = None
) -> dict[str, object]:
    validated = validate_protocol(protocol)
    supplied = dict(evidence or {})
    unexpected = set(supplied) - set(REQUIRED_EVIDENCE)
    if unexpected:
        raise LeanProtocolError("Readiness evidence contains unexpected fields")
    for key, digest in supplied.items():
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise LeanProtocolError(f"{key} must be a SHA-256 evidence identity")
    missing = [key for key in REQUIRED_EVIDENCE if key not in supplied]
    evidence_complete = not missing
    payload: dict[str, object] = {
        "schema_version": READINESS_SCHEMA,
        "readiness_version": "lean-discovery-readiness-v001",
        "protocol_identity": validated["protocol_identity"],
        "status": "evidence_complete_execution_not_implemented" if evidence_complete else "blocked",
        "required_evidence": list(REQUIRED_EVIDENCE),
        "satisfied_evidence": sorted(supplied),
        "unresolved_evidence": missing,
        "pilot_authorized": False,
        "empirical_data_opened": False,
        "validation_outcomes_opened": False,
        "holdout_outcomes_opened": False,
        "maximum_claim_level": 0,
    }
    return {**payload, "readiness_identity": canonical_hash(payload)}


def resolve_selection_only_horizon(
    protocol: Mapping[str, object], sessions: Sequence[str], candidate_counts: Sequence[int]
) -> dict[str, object]:
    """Resolve the first qualifying horizon using counts, never outcome records."""
    validated = validate_protocol(protocol)
    cohort = validated["calendar_and_cohort"]
    if len(sessions) != cohort["candidate_session_count"] or len(candidate_counts) != len(sessions):
        raise LeanProtocolError("Selection counts must cover every bound candidate session")
    if list(sessions) != sorted(set(sessions)):
        raise LeanProtocolError("Sessions must be sorted and unique")
    if any(type(count) is not int or count < 0 for count in candidate_counts):
        raise LeanProtocolError("Candidate counts must be non-negative integers")
    horizons = list(range(cohort["initial_sessions"], cohort["maximum_sessions"] + 1, cohort["extension_sessions"]))
    if horizons[-1] != cohort["maximum_sessions"]:
        horizons.append(cohort["maximum_sessions"])
    minimums = cohort["minimum_candidate_counts"]
    for horizon in horizons:
        discovery_end = horizon // 2
        validation_end = discovery_end + horizon // 4
        counts = {
            "discovery": sum(candidate_counts[:discovery_end]),
            "validation": sum(candidate_counts[discovery_end:validation_end]),
            "holdout": sum(candidate_counts[validation_end:horizon]),
        }
        counts["total"] = sum(counts.values())
        if all(counts[key] >= minimums[key] for key in ("total", "discovery", "validation", "holdout")):
            payload = {
                "cohort_session_count": horizon,
                "partition_counts": counts,
                "boundaries": {
                    "discovery": [sessions[0], sessions[discovery_end - 1]],
                    "validation": [sessions[discovery_end], sessions[validation_end - 1]],
                    "holdout": [sessions[validation_end], sessions[horizon - 1]],
                },
                "selection_only": True,
                "outcomes_opened": False,
            }
            return {**payload, "partition_identity": canonical_hash(payload)}
    raise LeanProtocolError("Maximum horizon does not satisfy frozen sample requirements")


def authorize_discovery_path(path: Path, root: Path) -> Path:
    """Authorize only non-symlink paths inside the lean discovery namespace."""
    if ".." in path.parts:
        raise LeanProtocolError("Path traversal is prohibited")
    normalized = {part.casefold().replace("_", "-") for part in path.parts}
    if normalized & {item.replace("_", "-") for item in PROTECTED_PARTS}:
        raise LeanProtocolError("Discovery cannot access protected partitions")
    candidate = (path if path.is_absolute() else root / path).absolute()
    cursor = candidate
    while cursor != cursor.parent:
        if cursor.exists() and cursor.is_symlink():
            raise LeanProtocolError("Research paths cannot contain symlinks")
        cursor = cursor.parent
    try:
        relative = candidate.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise LeanProtocolError("Research path escapes its approved root") from exc
    namespace = Path(ARTIFACT_NAMESPACE).parts
    if relative.parts[: len(namespace)] != namespace:
        raise LeanProtocolError("Research path is outside the lean artifact namespace")
    return candidate


def validate_claim_text(achieved_level: int, text: str) -> None:
    if type(achieved_level) is not int or not 0 <= achieved_level <= 8:
        raise LeanProtocolError("Claim level must be between 0 and 8")
    normalized = " ".join(text.casefold().split())
    always_prohibited = ("proven edge", "production ready", "profitable strategy")
    if any(phrase in normalized for phrase in always_prohibited):
        raise LeanProtocolError("Claim language exceeds every lean-protocol level")
    if "validated" in normalized and achieved_level < 5:
        raise LeanProtocolError("Validation language requires untouched validation")
    if "predictive" in normalized and achieved_level < 5:
        raise LeanProtocolError("Predictive language requires untouched validation")
    if "holdout" in normalized and achieved_level < 6:
        raise LeanProtocolError("Holdout language requires one-time holdout completion")


def cost_plan(protocol: Mapping[str, object]) -> dict[str, object]:
    validated = validate_protocol(protocol)
    return dict(validated["cost_plan"])
