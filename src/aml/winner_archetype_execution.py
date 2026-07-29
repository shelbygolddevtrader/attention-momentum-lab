"""Fail-closed, discovery-only execution readiness for Winner Archetype V001."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_calendar import NonTradingSessionError
from aml.winner_archetype import plan_chronological_partitions
from aml.winner_archetype_contracts import (
    HASH_PATTERN,
    WinnerArchetypeError,
    canonical_hash,
    load_experiment_spec,
)


DISCOVERY_INPUT_SCHEMA = "aml.winner-archetype.discovery-input.v001"
DISCOVERY_PLAN_SCHEMA = "aml.winner-archetype.discovery-plan.v001"
PROTECTED_PATH_PARTS = {"validation", "holdout", "sealed", "paper_forward"}
INPUT_HASH_FIELDS = (
    "universe_manifest_sha256",
    "security_master_manifest_sha256",
    "calendar_manifest_sha256",
    "market_bars_manifest_sha256",
    "quotes_manifest_sha256",
    "catalyst_registry_manifest_sha256",
    "halt_registry_manifest_sha256",
    "corporate_actions_manifest_sha256",
)


def _sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise WinnerArchetypeError(f"{field} must be a SHA-256 digest")
    return value


def _safe_read_path(path: Path) -> Path:
    lexical = path.absolute()
    if any(part.casefold() in PROTECTED_PATH_PARTS for part in lexical.parts):
        raise WinnerArchetypeError("Discovery execution cannot read protected partition paths")
    cursor = lexical
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise WinnerArchetypeError("Discovery input paths cannot contain symlinks")
        cursor = cursor.parent
    resolved = path.resolve(strict=True)
    if any(part.casefold() in PROTECTED_PATH_PARTS for part in resolved.parts):
        raise WinnerArchetypeError("Discovery execution cannot read protected partition paths")
    return resolved


@dataclass(frozen=True)
class DiscoveryInputBinding:
    """Identity-bound, provider-neutral declaration of discovery inputs."""

    schema_version: str
    experiment_identity: str
    phase: str
    provider: str
    feed: str
    entitlement_plan: str
    retrieval_timestamp: str
    normalization_version: str
    timezone: str
    universe_definition_id: str
    universe_manifest_sha256: str
    security_master_manifest_sha256: str
    calendar_manifest_sha256: str
    market_bars_manifest_sha256: str
    quotes_manifest_sha256: str
    catalyst_registry_manifest_sha256: str
    halt_registry_manifest_sha256: str
    corporate_actions_manifest_sha256: str
    raw_payload_sha256: tuple[str, ...]
    normalized_record_sha256: tuple[str, ...]

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object],
        *,
        expected_experiment_identity: str,
        as_of: datetime,
    ) -> "DiscoveryInputBinding":
        expected = set(cls.__dataclass_fields__)
        if not isinstance(value, Mapping) or set(value) != expected:
            raise WinnerArchetypeError(
                "Discovery input binding contains missing or unexpected fields"
            )
        if value["schema_version"] != DISCOVERY_INPUT_SCHEMA:
            raise WinnerArchetypeError("Discovery input schema is unsupported")
        if value["experiment_identity"] != expected_experiment_identity:
            raise WinnerArchetypeError("Discovery input binding targets another experiment")
        if value["phase"] != "discovery":
            raise WinnerArchetypeError("Only discovery inputs may be bound")
        if value["feed"] != "sip":
            raise WinnerArchetypeError("Frozen V001 requires the SIP feed")
        for field in (
            "provider",
            "entitlement_plan",
            "normalization_version",
            "timezone",
            "universe_definition_id",
        ):
            item = value[field]
            if not isinstance(item, str) or not item.strip():
                raise WinnerArchetypeError(f"{field} is required")
        try:
            ZoneInfo(str(value["timezone"]))
        except ZoneInfoNotFoundError as exc:
            raise WinnerArchetypeError("timezone must be an IANA timezone") from exc
        if not isinstance(value["retrieval_timestamp"], str):
            raise WinnerArchetypeError("retrieval_timestamp is malformed")
        try:
            retrieved = datetime.fromisoformat(
                str(value["retrieval_timestamp"]).replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise WinnerArchetypeError("retrieval_timestamp is malformed") from exc
        if retrieved.tzinfo is None or retrieved.utcoffset() is None:
            raise WinnerArchetypeError("retrieval_timestamp must include a timezone")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise WinnerArchetypeError("as_of must include a timezone")
        if retrieved > as_of:
            raise WinnerArchetypeError("Discovery inputs cannot be future-dated")
        for field in INPUT_HASH_FIELDS:
            _sha256(value[field], field)
        sequences: dict[str, tuple[str, ...]] = {}
        for field in ("raw_payload_sha256", "normalized_record_sha256"):
            items = value[field]
            if not isinstance(items, list) or not items or len(items) > 10_000:
                raise WinnerArchetypeError(f"{field} must be a non-empty list")
            normalized = tuple(_sha256(item, field) for item in items)
            if tuple(sorted(set(normalized))) != normalized:
                raise WinnerArchetypeError(f"{field} must be sorted and unique")
            sequences[field] = normalized
        payload = dict(value)
        payload.update(sequences)
        binding = cls(**payload)
        binding.identity
        return binding

    @property
    def identity(self) -> str:
        return canonical_hash(
            {
                field: list(value) if isinstance(value, tuple) else value
                for field, value in self.__dict__.items()
            }
        )


def load_discovery_input_binding(
    path: Path,
    *,
    expected_experiment_identity: str,
    as_of: datetime,
) -> DiscoveryInputBinding:
    safe = _safe_read_path(path)
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise WinnerArchetypeError("Discovery input binding has duplicate JSON keys")
            result[key] = item
        return result

    try:
        value = json.loads(
            safe.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WinnerArchetypeError("Discovery input binding is not valid UTF-8 JSON") from exc
    return DiscoveryInputBinding.from_mapping(
        value, expected_experiment_identity=expected_experiment_identity, as_of=as_of
    )


def _sessions(start: date, end: date) -> tuple[str, ...]:
    calendar = ExchangeCalendarsAdapter()
    result: list[str] = []
    current = start
    while current <= end:
        try:
            calendar.schedule(current, "XNYS")
        except NonTradingSessionError:
            pass
        else:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return tuple(result)


def build_discovery_readiness_plan(
    experiment_path: Path,
    *,
    input_binding: DiscoveryInputBinding | None = None,
) -> dict[str, object]:
    """Return a deterministic plan; never opens market or outcome records."""
    spec = load_experiment_spec(experiment_path)
    all_sessions = _sessions(
        date.fromisoformat(spec.selection_start), date.fromisoformat(spec.hard_latest_date)
    )
    if len(all_sessions) != spec.maximum_sessions:
        raise WinnerArchetypeError(
            "Authoritative calendar does not match the frozen maximum session count"
        )
    horizons = list(range(spec.initial_sessions, spec.maximum_sessions, spec.extension_sessions))
    if horizons[-1] != spec.maximum_sessions:
        horizons.append(spec.maximum_sessions)
    conditional_partitions = []
    for count in horizons:
        partition = plan_chronological_partitions(all_sessions[:count], spec.partition_spec)
        conditional_partitions.append(
            {
                "cohort_session_count": count,
                "discovery_session_count": len(partition.assignments["discovery"]),
                "discovery_start": partition.boundaries["discovery"][0],
                "discovery_end": partition.boundaries["discovery"][1],
                "partition_plan_id": partition.plan_id,
            }
        )
    blockers = []
    if input_binding is None:
        blockers.append("identity_bound_discovery_input_manifest_missing")
    else:
        if input_binding.experiment_identity != spec.identity:
            raise WinnerArchetypeError("Bound inputs target another experiment")
    blockers.append("eligible_universe_definition_not_bound_by_frozen_v001")
    plan = {
        "schema_version": DISCOVERY_PLAN_SCHEMA,
        "experiment_identity": spec.identity,
        "execution_phase": "discovery",
        "status": "blocked_protocol_revision_required",
        "pilot_authorized": False,
        "input_binding_identity": input_binding.identity if input_binding else None,
        "selection_session_count": len(all_sessions),
        "selection_start": all_sessions[0],
        "selection_end": all_sessions[-1],
        "warmup_start": spec.warmup_start,
        "warmup_end": spec.warmup_end,
        "discovery_partition_resolution": (
            "conditional_until_the_frozen_extension_rule_observes_at_least_100_eligible_events"
        ),
        "conditional_discovery_partitions": conditional_partitions,
        "required_feed": spec.selection_feed,
        "required_input_manifests": list(INPUT_HASH_FIELDS),
        "required_provenance": [
            "provider",
            "entitlement_plan",
            "retrieval_timestamp",
            "raw_payload_sha256",
            "normalized_record_sha256",
            "normalization_version",
            "timezone",
        ],
        "complete_event_rules": [
            "point_in_time_security_identity_and_universe_membership_resolved",
            "all_selection_features_complete_before_09_25_America_New_York",
            "all_six_matching_fields_complete",
            "session_calendar_and_early_close_semantics_resolved",
            "verified_halt_coverage_complete",
            "minute_outcome_window_complete_or_only_verified_halt_minutes_missing",
            "all_raw_and_normalized_records_hash_verified",
        ],
        "fail_closed_reasons": [
            "missing_or_conflicting_source_record",
            "future_dated_or_post_cutoff_input",
            "incomplete_20_session_lookback",
            "unresolved_corporate_action_or_symbol_identity",
            "unverified_missing_minute_or_halt",
            "missing_mandatory_matching_feature",
            "partition_or_experiment_identity_mismatch",
        ],
        "blockers": sorted(blockers),
        "outcome_access_performed": False,
    }
    return {**plan, "plan_identity": canonical_hash(plan)}
