"""Deterministic, non-empirical V002 calendar and conditional session plans."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_calendar import NonTradingSessionError
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json
from aml.winner_archetype_v002 import WinnerArchetypeProtocolV002, load_protocol_v002


SESSION_PLAN_SCHEMA = "aml.winner-archetype.session-plan.v002"
SESSION_PLAN_VERSION = "winner-archetype-session-plan-v002"
SESSION_POLICY_VERSION = "frozen-v002-conditional-50-25-25-v001"


class SessionPlanError(ValueError):
    """The immutable session plan cannot be proven from the frozen protocol."""


def _partition(sessions: list[str], basis_points: Mapping[str, object]) -> dict[str, object]:
    discovery_count = len(sessions) * int(basis_points["discovery"]) // 10_000
    validation_count = len(sessions) * int(basis_points["validation"]) // 10_000
    holdout_start = discovery_count + validation_count
    assignments = {
        "discovery": sessions[:discovery_count],
        "validation": sessions[discovery_count:holdout_start],
        "holdout": sessions[holdout_start:],
    }
    if any(not values for values in assignments.values()):
        raise SessionPlanError("Every conditional partition must be non-empty")
    flattened = [item for name in ("discovery", "validation", "holdout") for item in assignments[name]]
    if flattened != sessions or len(flattened) != len(set(flattened)):
        raise SessionPlanError("Conditional partitions overlap or omit sessions")
    boundaries = {name: [values[0], values[-1]] for name, values in assignments.items()}
    payload = {
        "cohort_session_count": len(sessions),
        "assignments": assignments,
        "boundaries": boundaries,
        "counts": {name: len(values) for name, values in assignments.items()},
    }
    return {**payload, "partition_identity": canonical_hash(payload)}


def _horizons(initial: int, extension: int, maximum: int) -> list[int]:
    if not 0 < initial <= maximum or extension <= 0:
        raise SessionPlanError("Protocol cohort horizons are invalid")
    result = list(range(initial, maximum, extension))
    if not result or result[-1] != maximum:
        result.append(maximum)
    if result != sorted(set(result)):
        raise SessionPlanError("Protocol cohort horizons are not ordered and unique")
    return result


def build_session_plan(
    protocol: WinnerArchetypeProtocolV002,
    *,
    protocol_file_hash: str,
    calendar: ExchangeCalendarsAdapter | None = None,
    conflicting_closure_dates: tuple[str, ...] = (),
) -> dict[str, object]:
    """Build all protocol-permitted plans without choosing a final cohort."""
    if conflicting_closure_dates:
        raise SessionPlanError("Conflicting closure evidence blocks session-plan publication")
    if not HASH_PATTERN.fullmatch(protocol_file_hash):
        raise SessionPlanError("Protocol file hash must be SHA-256")
    calendar = calendar or ExchangeCalendarsAdapter()
    calendar_rule = protocol.calendar
    identity = calendar.identity({calendar_rule["calendar_id"]})
    if (
        identity.provider != calendar_rule["provider"]
        or identity.provider_version != calendar_rule["provider_version"]
        or identity.calendar_ids != (calendar_rule["calendar_id"],)
        or identity.exchange_timezones != ((calendar_rule["calendar_id"], calendar_rule["timezone"]),)
        or identity.minute_side != "left"
    ):
        raise SessionPlanError("Calendar identity conflicts with the frozen V002 protocol")

    planning = protocol.planning
    current = date.fromisoformat(planning["selection_start"])
    end = date.fromisoformat(planning["hard_latest_date"])
    zone = ZoneInfo(calendar_rule["timezone"])
    cutoff_time = time.fromisoformat(calendar_rule["selection_cutoff"])
    sessions: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    while current <= end:
        try:
            schedule = calendar.schedule(current, calendar_rule["calendar_id"])
        except NonTradingSessionError:
            excluded.append(
                {
                    "date": current.isoformat(),
                    "classification": calendar.non_session_reason(
                        current, calendar_rule["calendar_id"]
                    ),
                }
            )
        else:
            cutoff = datetime.combine(current, cutoff_time, zone)
            opened = schedule.open_timestamp.to_pydatetime()
            closed = schedule.close_timestamp.to_pydatetime()
            if not cutoff < opened < closed:
                raise SessionPlanError("Session cutoff, open, and close are not ordered")
            early_close = closed.astimezone(zone).time().replace(tzinfo=None) != time(16, 0)
            sessions.append(
                {
                    "session": current.isoformat(),
                    "selection_cutoff": cutoff.isoformat(),
                    "scheduled_open": opened.isoformat(),
                    "scheduled_close": closed.isoformat(),
                    "early_close": early_close,
                    "classification": "early_close" if early_close else "regular_session",
                }
            )
        current += timedelta(days=1)

    session_ids = [item["session"] for item in sessions]
    if session_ids != sorted(set(session_ids)):
        raise SessionPlanError("Calendar sessions are not strictly ordered and unique")
    if len(session_ids) != int(planning["maximum_sessions"]):
        raise SessionPlanError("Unexpected calendar gaps changed the frozen maximum cohort")
    if session_ids[0] != planning["selection_start"] or session_ids[-1] != planning["hard_latest_date"]:
        raise SessionPlanError("Calendar boundaries conflict with the frozen planning interval")

    candidates = [
        _partition(session_ids[:count], planning["partition_basis_points"])
        for count in _horizons(
            int(planning["initial_sessions"]),
            int(planning["extension_sessions"]),
            int(planning["maximum_sessions"]),
        )
    ]
    payload = {
        "schema_version": SESSION_PLAN_SCHEMA,
        "manifest_version": SESSION_PLAN_VERSION,
        "protocol_identity": protocol.identity,
        "protocol_file_sha256": protocol_file_hash,
        "calendar": {
            **identity.normalized_payload(),
            "calendar_identity": identity.fingerprint(),
        },
        "policy": {
            "policy_version": SESSION_POLICY_VERSION,
            "timezone": calendar_rule["timezone"],
            "selection_cutoff": calendar_rule["selection_cutoff"],
            "selection_cutoff_semantics": calendar_rule["selection_cutoff_semantics"],
            "early_close_rule": calendar_rule["early_close_rule"],
            "partition_rule": planning["partition_rule"],
            "partition_basis_points": planning["partition_basis_points"],
            "minimum_eligible_events": planning["minimum_eligible_events"],
        },
        "selection_sessions": sessions,
        "excluded_calendar_dates": excluded,
        "conditional_partition_plans": candidates,
        "final_cohort_status": "unresolved_until_selection_only_eligible_event_count",
        "final_partition_identity": None,
        "pilot_authorized": False,
        "empirical_data_opened": False,
        "validation_or_holdout_outcomes_opened": False,
        "component_hashes": {
            "selection_sessions_sha256": canonical_hash(sessions),
            "excluded_calendar_dates_sha256": canonical_hash(excluded),
            "conditional_partition_plans_sha256": canonical_hash(candidates),
        },
    }
    return {**payload, "manifest_identity": canonical_hash(payload)}


def validate_session_plan(
    manifest: Mapping[str, object], protocol: WinnerArchetypeProtocolV002, protocol_file_hash: str
) -> None:
    expected = build_session_plan(protocol, protocol_file_hash=protocol_file_hash)
    if dict(manifest) != expected:
        raise SessionPlanError("Session-plan manifest is tampered, stale, or conflicting")


def load_session_plan(path: Path, protocol_path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise SessionPlanError("Session-plan manifest is missing or oversized")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SessionPlanError("Session-plan manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise SessionPlanError("Session-plan manifest root must be an object")
    validate_session_plan(
        value,
        load_protocol_v002(protocol_path),
        protocol_file_sha256(protocol_path),
    )
    return value


def protocol_file_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not HASH_PATTERN.fullmatch(digest):  # pragma: no cover
        raise SessionPlanError("Protocol file hash failed")
    return digest


def canonical_session_plan_bytes(protocol_path: Path) -> bytes:
    protocol = load_protocol_v002(protocol_path)
    manifest = build_session_plan(
        protocol,
        protocol_file_hash=protocol_file_sha256(protocol_path),
    )
    return canonical_json(manifest)
