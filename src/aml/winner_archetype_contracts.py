"""Strict research-only contracts for Winner Archetype Discovery V0.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
import hashlib
import json
import math
import re
from typing import Any, ClassVar, Mapping
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


EXPERIMENT_SCHEMA = "aml.winner-archetype.experiment.v001"
PARTITION_SCHEMA = "aml.winner-archetype.partition.v001"
SNAPSHOT_SPEC_SCHEMA = "aml.winner-archetype.snapshot-spec.v001"
FEATURE_DEFINITION_SCHEMA = "aml.winner-archetype.feature-definition.v001"
FEATURE_SNAPSHOT_SCHEMA = "aml.winner-archetype.feature-snapshot.v001"
OUTCOME_DEFINITION_SCHEMA = "aml.winner-archetype.outcome-definition.v001"
OUTCOME_RECORD_SCHEMA = "aml.winner-archetype.outcome-record.v001"
MATCHING_SCHEMA = "aml.winner-archetype.control-matching.v001"
MATCHED_CONTROL_SCHEMA = "aml.winner-archetype.matched-control.v001"
ARCHETYPE_SCHEMA = "aml.winner-archetype.definition.v001"
ARCHETYPE_ASSIGNMENT_SCHEMA = "aml.winner-archetype.assignment.v001"
BALANCE_SCHEMA = "aml.winner-archetype.balance-diagnostic.v001"
HYPOTHESIS_SCHEMA = "aml.winner-archetype.hypothesis.v001"
HYPOTHESIS_FREEZE_SCHEMA = "aml.winner-archetype.hypothesis-freeze.v001"
MANIFEST_SCHEMA = "aml.winner-archetype.manifest.v001"

HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
MAX_TEXT = 20_000
MAX_COLLECTION = 10_000
PHASES = {"discovery", "validation", "holdout", "paper_forward"}
APPROVED_MATCHING_FIELDS = {
    "price", "premarket_gap", "premarket_dollar_volume",
    "premarket_relative_volume", "atr_percent_20", "spread_bps",
    "market_cap", "float_shares", "catalyst_category", "sector", "industry",
}
OUTCOME_DERIVED_FIELDS = {
    "winner", "outcome", "mfe", "mae", "future_return", "forward_return",
    "pnl", "profit", "loss", "target_hit", "stop_hit", "outcome_severity",
}


def is_outcome_derived_field(value: str) -> bool:
    normalized = value.strip().casefold().replace("-", "_")
    prefixes = (
        "future_", "forward_", "mfe", "mae", "pnl", "profit", "loss",
        "exit_", "target_", "stop_", "return_after_",
    )
    return (
        normalized in OUTCOME_DERIVED_FIELDS
        or normalized.startswith(prefixes)
        or "outcome" in normalized
    )


class WinnerArchetypeError(ValueError):
    """A winner-archetype research contract was violated."""


def canonical_json(value: object) -> bytes:
    """Return deterministic UTF-8 JSON, rejecting non-finite and malformed values."""
    _bounded_json(value)
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError, RecursionError) as exc:
        raise WinnerArchetypeError("Value is not canonical JSON") from exc


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _bounded_json(value: object, *, depth: int = 0) -> None:
    if depth > 40:
        raise WinnerArchetypeError("JSON nesting exceeds the contract limit")
    if value is None or type(value) is bool or type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise WinnerArchetypeError("Numeric values must be finite")
        return
    if isinstance(value, str):
        _text(value, "JSON text", allow_empty=True)
        return
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_COLLECTION:
            raise WinnerArchetypeError("JSON list exceeds the contract limit")
        for item in value:
            _bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION:
            raise WinnerArchetypeError("JSON object exceeds the contract limit")
        for key, item in value.items():
            _text(key, "JSON key")
            _bounded_json(item, depth=depth + 1)
        return
    raise WinnerArchetypeError("Unsupported JSON value type")


def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise WinnerArchetypeError(f"{field} must be a non-empty string")
    if len(value) > MAX_TEXT:
        raise WinnerArchetypeError(f"{field} exceeds the size limit")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise WinnerArchetypeError(f"{field} contains invalid Unicode")
    return value


def _identifier(value: object, field: str) -> str:
    text = _text(value, field)
    if not IDENTIFIER_PATTERN.fullmatch(text):
        raise WinnerArchetypeError(f"{field} is malformed")
    return text


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise WinnerArchetypeError(f"{field} must be a SHA-256 digest")
    return value


def _date(value: object, field: str) -> date:
    text = _text(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise WinnerArchetypeError(f"{field} is malformed") from exc


def _timestamp(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WinnerArchetypeError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WinnerArchetypeError(f"{field} must include a timezone")
    return parsed


def _clock(value: object, field: str) -> time:
    text = _text(value, field)
    try:
        parsed = time.fromisoformat(text)
    except ValueError as exc:
        raise WinnerArchetypeError(f"{field} is malformed") from exc
    if parsed.tzinfo is not None:
        raise WinnerArchetypeError(f"{field} must be a local wall-clock time")
    return parsed


def _zone(value: object, field: str) -> ZoneInfo:
    text = _text(value, field)
    try:
        return ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise WinnerArchetypeError(f"{field} is not an IANA timezone") from exc


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise WinnerArchetypeError(f"{field} must be an integer >= {minimum}")
    return value


def _number(value: object, field: str, *, minimum: float | None = None) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise WinnerArchetypeError(f"{field} must be finite numeric")
    number = float(value)
    if minimum is not None and number < minimum:
        raise WinnerArchetypeError(f"{field} must be >= {minimum}")
    return number


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or (not allow_empty and not value):
        raise WinnerArchetypeError(f"{field} must be a non-empty sequence")
    result = tuple(_text(item, field) for item in value)
    if len(set(result)) != len(result):
        raise WinnerArchetypeError(f"{field} must be unique")
    return result


def _exact_mapping(value: Mapping[str, object], fields: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise WinnerArchetypeError(f"{label} contains missing or unexpected fields")


class StrictContract:
    SCHEMA: ClassVar[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def identity(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class CohortPartitionSpec(StrictContract):
    schema_version: str
    partition_version: str
    discovery_basis_points: int
    validation_basis_points: int
    holdout_basis_points: int
    minimum_sessions_per_partition: int
    chronological: bool

    SCHEMA = PARTITION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported partition schema")
        _identifier(self.partition_version, "partition_version")
        values = (
            _integer(self.discovery_basis_points, "discovery_basis_points", minimum=1),
            _integer(self.validation_basis_points, "validation_basis_points", minimum=1),
            _integer(self.holdout_basis_points, "holdout_basis_points", minimum=1),
        )
        if sum(values) != 10_000:
            raise WinnerArchetypeError("Partition basis points must total 10000")
        _integer(self.minimum_sessions_per_partition, "minimum_sessions_per_partition", minimum=1)
        if self.chronological is not True:
            raise WinnerArchetypeError("Partitions must be chronological")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CohortPartitionSpec:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Partition spec")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class DecisionSnapshotSpec(StrictContract):
    schema_version: str
    snapshot_version: str
    local_time: str
    timezone: str
    cutoff_semantics: str
    analysis_phase: str

    SCHEMA = SNAPSHOT_SPEC_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported snapshot-spec schema")
        _identifier(self.snapshot_version, "snapshot_version")
        _clock(self.local_time, "local_time")
        _zone(self.timezone, "timezone")
        if self.cutoff_semantics not in {"exclusive", "inclusive"}:
            raise WinnerArchetypeError("cutoff_semantics is ambiguous")
        if self.analysis_phase not in {"premarket", "post_open"}:
            raise WinnerArchetypeError("analysis_phase is unsupported")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> DecisionSnapshotSpec:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Snapshot spec")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FeatureDefinition(StrictContract):
    schema_version: str
    name: str
    definition_version: str
    family: str
    units: str
    observation_window: str
    required_inputs: tuple[str, ...]
    missing_data_behavior: str
    zero_is_distinct_from_missing: bool
    point_in_time_safe: bool
    licensing_approval_required: bool
    allowed_phases: tuple[str, ...]

    SCHEMA = FEATURE_DEFINITION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported feature-definition schema")
        _identifier(self.name, "feature name")
        _identifier(self.definition_version, "definition_version")
        for field in ("family", "units", "observation_window", "missing_data_behavior"):
            _text(getattr(self, field), field)
        _strings(self.required_inputs, "required_inputs")
        if type(self.zero_is_distinct_from_missing) is not bool:
            raise WinnerArchetypeError("zero_is_distinct_from_missing must be boolean")
        if self.point_in_time_safe is not True:
            raise WinnerArchetypeError("Research features must declare point-in-time safety")
        if type(self.licensing_approval_required) is not bool:
            raise WinnerArchetypeError("licensing_approval_required must be boolean")
        phases = _strings(self.allowed_phases, "allowed_phases")
        if not set(phases).issubset(PHASES):
            raise WinnerArchetypeError("Feature allowed_phases are unsupported")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> FeatureDefinition:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Feature definition")
        payload = dict(value)
        payload["required_inputs"] = tuple(payload["required_inputs"])
        payload["allowed_phases"] = tuple(payload["allowed_phases"])
        return cls(**payload)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FeatureSnapshot(StrictContract):
    schema_version: str
    session: str
    symbol: str
    security_identifier: str
    decision_timestamp: str
    latest_input_timestamp: str
    timezone: str
    cutoff_semantics: str
    snapshot_version: str
    snapshot_spec_hash: str
    feature_definition_version: str
    source_manifest_hashes: tuple[str, ...]
    completeness_status: str
    feature_values: Mapping[str, object]
    missingness: Mapping[str, bool]
    feature_window_end_timestamps: Mapping[str, str]
    canonical_feature_hash: str

    SCHEMA = FEATURE_SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported feature-snapshot schema")
        session = _date(self.session, "session")
        if not SYMBOL_PATTERN.fullmatch(_text(self.symbol, "symbol")):
            raise WinnerArchetypeError("symbol is not normalized")
        _text(self.security_identifier, "security_identifier")
        observed = _timestamp(self.decision_timestamp, "decision_timestamp")
        latest = _timestamp(self.latest_input_timestamp, "latest_input_timestamp")
        zone = _zone(self.timezone, "timezone")
        if observed.astimezone(zone).date() != session:
            raise WinnerArchetypeError("Decision timestamp is outside its session")
        if self.cutoff_semantics not in {"exclusive", "inclusive"}:
            raise WinnerArchetypeError("cutoff_semantics is ambiguous")
        if (
            self.cutoff_semantics == "exclusive" and not latest < observed
        ) or (
            self.cutoff_semantics == "inclusive" and not latest <= observed
        ):
            raise WinnerArchetypeError("Feature input timestamp exceeds the declared cutoff")
        _identifier(self.snapshot_version, "snapshot_version")
        _hash(self.snapshot_spec_hash, "snapshot_spec_hash")
        _identifier(self.feature_definition_version, "feature_definition_version")
        if not self.source_manifest_hashes:
            raise WinnerArchetypeError("Feature snapshots require source manifests")
        for item in self.source_manifest_hashes:
            _hash(item, "source_manifest_hash")
        if tuple(sorted(set(self.source_manifest_hashes))) != self.source_manifest_hashes:
            raise WinnerArchetypeError("Source manifests must be sorted and unique")
        if self.completeness_status not in {"complete", "partial", "unavailable"}:
            raise WinnerArchetypeError("completeness_status is unsupported")
        if not self.feature_values:
            raise WinnerArchetypeError("Feature snapshots require feature values")
        _bounded_json(dict(self.feature_values))
        if set(self.feature_values) != set(self.missingness):
            raise WinnerArchetypeError("Feature values and missingness keys differ")
        if set(self.feature_values) != set(self.feature_window_end_timestamps):
            raise WinnerArchetypeError("Feature values and input-window keys differ")
        for key, missing in self.missingness.items():
            _identifier(key, "missingness feature")
            if type(missing) is not bool:
                raise WinnerArchetypeError("Missingness values must be boolean")
            if missing != (self.feature_values[key] is None):
                raise WinnerArchetypeError("Missingness does not match feature value")
            window_end = _timestamp(
                self.feature_window_end_timestamps[key], f"{key}.window_end"
            )
            if (
                self.cutoff_semantics == "exclusive" and not window_end < observed
            ) or (
                self.cutoff_semantics == "inclusive" and not window_end <= observed
            ):
                raise WinnerArchetypeError("Feature input window extends past the cutoff")
        expected = canonical_hash({key: self.feature_values[key] for key in sorted(self.feature_values)})
        if _hash(self.canonical_feature_hash, "canonical_feature_hash") != expected:
            raise WinnerArchetypeError("Feature hash does not match canonical values")


@dataclass(frozen=True)
class OutcomeDefinition(StrictContract):
    schema_version: str
    definition_version: str
    direction: str
    reference_price_semantics: str
    reference_time: str
    evaluation_start: str
    evaluation_end: str
    session_timezone: str
    upside_threshold: float
    downside_threshold: float
    reward_to_risk_multiple: float
    sustained_momentum_threshold: float
    sustained_minutes: int
    close_above_reference: str
    ambiguity_rule: str
    missing_minute_rule: str
    halt_treatment: str

    SCHEMA = OUTCOME_DEFINITION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported outcome-definition schema")
        _identifier(self.definition_version, "definition_version")
        if self.direction not in {"long", "short"}:
            raise WinnerArchetypeError("Outcome direction is unsupported")
        if self.reference_price_semantics not in {"bar_open", "bar_close", "declared_external"}:
            raise WinnerArchetypeError("reference_price_semantics is unsupported")
        reference = _clock(self.reference_time, "reference_time")
        start = _clock(self.evaluation_start, "evaluation_start")
        end = _clock(self.evaluation_end, "evaluation_end")
        if not reference <= start < end:
            raise WinnerArchetypeError("Outcome evaluation times are inconsistent")
        _zone(self.session_timezone, "session_timezone")
        for field in (
            "upside_threshold", "downside_threshold", "reward_to_risk_multiple",
            "sustained_momentum_threshold",
        ):
            if _number(getattr(self, field), field, minimum=0.0) <= 0:
                raise WinnerArchetypeError(f"{field} must be positive")
        _integer(self.sustained_minutes, "sustained_minutes", minimum=1)
        if self.close_above_reference not in {"session_close", "evaluation_close"}:
            raise WinnerArchetypeError("close_above_reference is unsupported")
        if self.ambiguity_rule != "downside_first_conservative":
            raise WinnerArchetypeError("Intrabar ambiguity must use the conservative rule")
        if self.missing_minute_rule != "no_forward_fill_mark_incomplete":
            raise WinnerArchetypeError("Missing minutes may not be forward-filled")
        if self.halt_treatment != "exclude_verified_halt_minutes_and_report":
            raise WinnerArchetypeError("halt_treatment is unsupported")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> OutcomeDefinition:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Outcome definition")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class OutcomeRecord(StrictContract):
    schema_version: str
    outcome_id: str
    symbol: str
    security_identifier: str
    session: str
    outcome_definition_version: str
    outcome_definition_hash: str
    direction: str
    reference_timestamp: str
    reference_price: float | None
    evaluation_window: tuple[str, str]
    input_manifest_hash: str
    verified_halt_evidence_hash: str
    completeness_status: str
    missing_minutes: int
    verified_halt_minutes: int
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    threshold_order: str
    reward_to_risk_achieved: bool | None
    sustained_momentum_achieved: bool | None
    closed_above_reference: bool | None
    halt_involved: bool
    canonical_result_hash: str

    SCHEMA = OUTCOME_RECORD_SCHEMA

    def result_payload(self) -> dict[str, object]:
        return {
            key: value for key, value in self.to_dict().items()
            if key not in {"outcome_id", "canonical_result_hash"}
        }

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported outcome-record schema")
        _hash(self.outcome_id, "outcome_id")
        if not SYMBOL_PATTERN.fullmatch(_text(self.symbol, "symbol")):
            raise WinnerArchetypeError("symbol is not normalized")
        _text(self.security_identifier, "security_identifier")
        _date(self.session, "session")
        _identifier(self.outcome_definition_version, "outcome_definition_version")
        _hash(self.outcome_definition_hash, "outcome_definition_hash")
        if self.direction not in {"long", "short"}:
            raise WinnerArchetypeError("Outcome direction is unsupported")
        _timestamp(self.reference_timestamp, "reference_timestamp")
        if self.reference_price is not None:
            _number(self.reference_price, "reference_price", minimum=0.0000001)
        if len(self.evaluation_window) != 2:
            raise WinnerArchetypeError("evaluation_window must contain two timestamps")
        start, end = (_timestamp(item, "evaluation_window") for item in self.evaluation_window)
        if start >= end:
            raise WinnerArchetypeError("evaluation_window is invalid")
        _hash(self.input_manifest_hash, "input_manifest_hash")
        _hash(self.verified_halt_evidence_hash, "verified_halt_evidence_hash")
        if self.completeness_status not in {"complete", "halt_adjusted_complete", "incomplete", "no_usable_bars"}:
            raise WinnerArchetypeError("completeness_status is unsupported")
        _integer(self.missing_minutes, "missing_minutes")
        _integer(self.verified_halt_minutes, "verified_halt_minutes")
        for field in ("maximum_favorable_excursion", "maximum_adverse_excursion"):
            value = getattr(self, field)
            if value is not None:
                _number(value, field)
        if self.threshold_order not in {"upside_first", "downside_first", "ambiguous_downside_first", "neither", "unavailable"}:
            raise WinnerArchetypeError("threshold_order is unsupported")
        for field in ("reward_to_risk_achieved", "sustained_momentum_achieved", "closed_above_reference"):
            if getattr(self, field) is not None and type(getattr(self, field)) is not bool:
                raise WinnerArchetypeError(f"{field} must be boolean or null")
        if type(self.halt_involved) is not bool:
            raise WinnerArchetypeError("halt_involved must be boolean")
        result_hash = canonical_hash(self.result_payload())
        if _hash(self.canonical_result_hash, "canonical_result_hash") != result_hash:
            raise WinnerArchetypeError("canonical_result_hash is invalid")
        identity_payload = {
            "symbol": self.symbol,
            "security_identifier": self.security_identifier,
            "session": self.session,
            "outcome_definition_version": self.outcome_definition_version,
            "outcome_definition_hash": self.outcome_definition_hash,
            "direction": self.direction,
            "reference_timestamp": self.reference_timestamp,
            "reference_price": self.reference_price,
            "evaluation_window": self.evaluation_window,
            "halt_treatment": self.completeness_status,
            "input_manifest_hash": self.input_manifest_hash,
            "verified_halt_evidence_hash": self.verified_halt_evidence_hash,
            "canonical_result_hash": self.canonical_result_hash,
        }
        if self.outcome_id != canonical_hash(identity_payload):
            raise WinnerArchetypeError("outcome_id is invalid")


@dataclass(frozen=True)
class ControlMatchingSpec(StrictContract):
    schema_version: str
    matching_version: str
    matching_fields: tuple[str, ...]
    field_scales: Mapping[str, float]
    field_weights: Mapping[str, float]
    maximum_controls: int
    with_replacement: bool
    same_session_required: bool
    winner_order_fields: tuple[str, ...]
    tie_break_fields: tuple[str, ...]

    SCHEMA = MATCHING_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported matching schema")
        _identifier(self.matching_version, "matching_version")
        fields = _strings(self.matching_fields, "matching_fields")
        prohibited = {item for item in fields if is_outcome_derived_field(item)}
        if prohibited:
            raise WinnerArchetypeError("Outcome-derived matching fields are prohibited")
        if not set(fields).issubset(APPROVED_MATCHING_FIELDS):
            raise WinnerArchetypeError("Matching fields are not in the approved pre-outcome set")
        if set(self.field_scales) != set(fields) or set(self.field_weights) != set(fields):
            raise WinnerArchetypeError("Matching scales and weights must cover every field exactly")
        for field in fields:
            _number(self.field_scales[field], f"scale.{field}", minimum=0.0000001)
            _number(self.field_weights[field], f"weight.{field}", minimum=0.0)
        if not any(float(value) > 0 for value in self.field_weights.values()):
            raise WinnerArchetypeError("At least one matching weight must be positive")
        if _integer(self.maximum_controls, "maximum_controls", minimum=1) > 2:
            raise WinnerArchetypeError("At most two controls are permitted")
        if type(self.with_replacement) is not bool:
            raise WinnerArchetypeError("with_replacement must be boolean")
        if self.same_session_required is not True:
            raise WinnerArchetypeError("Control matching must require the same session")
        winner_order = _strings(self.winner_order_fields, "winner_order_fields")
        if winner_order != ("session", "symbol", "event_id"):
            raise WinnerArchetypeError("Winner ordering must be session, symbol, then event_id")
        ties = _strings(self.tie_break_fields, "tie_break_fields")
        if ties != ("symbol", "event_id"):
            raise WinnerArchetypeError("Tie-breaking must be symbol then event_id")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ControlMatchingSpec:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Matching spec")
        payload = dict(value)
        payload["matching_fields"] = tuple(payload["matching_fields"])
        payload["winner_order_fields"] = tuple(payload["winner_order_fields"])
        payload["tie_break_fields"] = tuple(payload["tie_break_fields"])
        return cls(**payload)  # type: ignore[arg-type]


@dataclass(frozen=True)
class MatchedControlRecord(StrictContract):
    schema_version: str
    match_id: str
    matching_version: str
    matching_spec_hash: str
    winner_event_id: str
    control_event_id: str | None
    session: str
    rank: int
    distance: float | None
    with_replacement: bool
    reason_code: str
    fields_used: tuple[str, ...]

    SCHEMA = MATCHED_CONTROL_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported matched-control schema")
        _hash(self.match_id, "match_id")
        _identifier(self.matching_version, "matching_version")
        _hash(self.matching_spec_hash, "matching_spec_hash")
        _identifier(self.winner_event_id, "winner_event_id")
        if self.control_event_id is not None:
            _identifier(self.control_event_id, "control_event_id")
        _date(self.session, "session")
        _integer(self.rank, "rank", minimum=1)
        if self.distance is not None:
            _number(self.distance, "distance", minimum=0.0)
        if type(self.with_replacement) is not bool:
            raise WinnerArchetypeError("with_replacement must be boolean")
        if self.reason_code not in {"matched", "insufficient_controls", "missing_matching_fields"}:
            raise WinnerArchetypeError("reason_code is unsupported")
        if self.reason_code == "matched" and (
            self.control_event_id is None or self.distance is None
        ):
            raise WinnerArchetypeError("A matched record requires a control and distance")
        if self.reason_code != "matched" and (
            self.control_event_id is not None or self.distance is not None
        ):
            raise WinnerArchetypeError("An unmatched record cannot carry a control or distance")
        _strings(self.fields_used, "fields_used")
        payload = {
            key: value for key, value in self.to_dict().items()
            if key not in {"schema_version", "match_id"}
        }
        if self.match_id != canonical_hash(payload):
            raise WinnerArchetypeError("match_id is invalid")


@dataclass(frozen=True)
class ArchetypeDefinition(StrictContract):
    schema_version: str
    archetype_id: str
    version: str
    description: str
    assignment_method: str
    inclusion_rule: str
    feature_names: tuple[str, ...]
    feature_definition_hashes: tuple[str, ...]
    discovery_partition_id: str
    population_manifest_hash: str
    missing_data_policy: str
    normalization_method: str
    distance_or_clustering_method: str
    cluster_label_stabilization_method: str
    parameter_hash: str
    minimum_sample_size: int
    sample_count: int
    winner_count: int
    control_count: int
    missingness_summary: Mapping[str, float]
    balance_diagnostic_ids: tuple[str, ...]
    hypothesis_status: str
    sample_sufficiency: str
    interpretation_status: str

    SCHEMA = ARCHETYPE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported archetype schema")
        for field in ("archetype_id", "version", "discovery_partition_id"):
            _identifier(getattr(self, field), field)
        for field in ("description", "assignment_method", "inclusion_rule"):
            _text(getattr(self, field), field)
        if any(
            token in self.description.casefold()
            for token in ("profitable", "predictive", "tradable", "statistically significant")
        ):
            raise WinnerArchetypeError("Discovery archetype descriptions cannot claim performance")
        _strings(self.feature_names, "feature_names")
        if len(self.feature_definition_hashes) != len(self.feature_names):
            raise WinnerArchetypeError("Every archetype feature requires a definition hash")
        for item in self.feature_definition_hashes:
            _hash(item, "feature_definition_hash")
        _hash(self.population_manifest_hash, "population_manifest_hash")
        for field in (
            "missing_data_policy", "normalization_method",
            "distance_or_clustering_method", "cluster_label_stabilization_method",
        ):
            _text(getattr(self, field), field)
        _hash(self.parameter_hash, "parameter_hash")
        _integer(self.minimum_sample_size, "minimum_sample_size", minimum=1)
        if not self.discovery_partition_id.startswith("discovery-"):
            raise WinnerArchetypeError("Archetypes must originate in discovery")
        counts = [
            _integer(getattr(self, field), field)
            for field in ("sample_count", "winner_count", "control_count")
        ]
        if counts[1] + counts[2] > counts[0]:
            raise WinnerArchetypeError("Archetype counts are inconsistent")
        if counts[0] == 0:
            raise WinnerArchetypeError("An archetype cannot be empty")
        for feature, value in self.missingness_summary.items():
            _identifier(feature, "missingness feature")
            if not 0 <= _number(value, "missingness rate") <= 1:
                raise WinnerArchetypeError("Missingness rate must be within [0, 1]")
        for item in self.balance_diagnostic_ids:
            _hash(item, "balance_diagnostic_id")
        if self.hypothesis_status not in {"descriptive", "proposed", "frozen"}:
            raise WinnerArchetypeError("hypothesis_status is unsupported")
        if self.sample_sufficiency not in {"insufficient", "meets_minimum"}:
            raise WinnerArchetypeError("sample_sufficiency is unsupported")
        expected_sufficiency = (
            "meets_minimum" if self.sample_count >= self.minimum_sample_size
            else "insufficient"
        )
        if self.sample_sufficiency != expected_sufficiency:
            raise WinnerArchetypeError("sample_sufficiency does not match the sample count")
        if self.interpretation_status != "no_performance_claim_permitted":
            raise WinnerArchetypeError("Discovery archetypes cannot carry performance claims")


@dataclass(frozen=True)
class ArchetypeAssignment(StrictContract):
    schema_version: str
    assignment_id: str
    archetype_id: str
    event_id: str
    partition: str
    feature_snapshot_id: str
    population_manifest_hash: str
    assignment_method_hash: str

    SCHEMA = ARCHETYPE_ASSIGNMENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported archetype-assignment schema")
        _hash(self.assignment_id, "assignment_id")
        _identifier(self.archetype_id, "archetype_id")
        _identifier(self.event_id, "event_id")
        if self.partition not in {"discovery", "validation"}:
            raise WinnerArchetypeError("Archetype assignment cannot access holdout or paper data")
        _hash(self.feature_snapshot_id, "feature_snapshot_id")
        _hash(self.population_manifest_hash, "population_manifest_hash")
        _hash(self.assignment_method_hash, "assignment_method_hash")
        payload = {
            key: value for key, value in self.to_dict().items()
            if key not in {"schema_version", "assignment_id"}
        }
        if self.assignment_id != canonical_hash(payload):
            raise WinnerArchetypeError("assignment_id is invalid")


@dataclass(frozen=True)
class BalanceDiagnostic(StrictContract):
    schema_version: str
    diagnostic_id: str
    matching_version: str
    matching_spec_hash: str
    matched_set_hash: str
    feature_name: str
    stage: str
    winner_count: int
    control_count: int
    unmatched_winner_count: int
    standardized_mean_difference: float | None
    calculation_status: str
    missing_winner_count: int
    missing_control_count: int

    SCHEMA = BALANCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported balance schema")
        _hash(self.diagnostic_id, "diagnostic_id")
        _identifier(self.matching_version, "matching_version")
        _hash(self.matching_spec_hash, "matching_spec_hash")
        _hash(self.matched_set_hash, "matched_set_hash")
        _identifier(self.feature_name, "feature_name")
        if self.stage not in {"before", "after"}:
            raise WinnerArchetypeError("Balance stage is unsupported")
        for field in (
            "winner_count", "control_count", "unmatched_winner_count",
            "missing_winner_count", "missing_control_count",
        ):
            _integer(getattr(self, field), field)
        if self.calculation_status not in {
            "calculated", "balanced_zero_variance", "undefined_zero_variance",
            "insufficient_data",
        }:
            raise WinnerArchetypeError("Balance calculation_status is unsupported")
        if self.standardized_mean_difference is not None:
            _number(self.standardized_mean_difference, "standardized_mean_difference")
        payload = {
            key: value for key, value in self.to_dict().items()
            if key not in {"schema_version", "diagnostic_id"}
        }
        if self.diagnostic_id != canonical_hash(payload):
            raise WinnerArchetypeError("diagnostic_id is invalid")


@dataclass(frozen=True)
class HypothesisRecord(StrictContract):
    schema_version: str
    hypothesis_id: str
    sequence: int
    version: str
    statement: str
    source_archetype_id: str
    allowed_features: tuple[str, ...]
    proposed_direction: str
    proposed_test: str
    discovery_partition_version: str
    validation_status: str
    holdout_status: str
    rejection_status: str
    supersedes_hypothesis_id: str | None
    parameter_freeze_hash: str | None
    frozen: bool
    creation_timestamp_metadata: str | None

    SCHEMA = HYPOTHESIS_SCHEMA

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value for key, value in self.to_dict().items()
            if key != "creation_timestamp_metadata"
        }

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported hypothesis schema")
        _identifier(self.hypothesis_id, "hypothesis_id")
        _integer(self.sequence, "sequence", minimum=1)
        _identifier(self.version, "version")
        _text(self.statement, "statement")
        _identifier(self.source_archetype_id, "source_archetype_id")
        _strings(self.allowed_features, "allowed_features")
        if self.proposed_direction not in {"higher", "lower", "different", "descriptive"}:
            raise WinnerArchetypeError("proposed_direction is unsupported")
        _text(self.proposed_test, "proposed_test")
        _identifier(self.discovery_partition_version, "discovery_partition_version")
        if self.validation_status not in {"not_started", "passed", "failed", "inconclusive"}:
            raise WinnerArchetypeError("validation_status is unsupported")
        if self.holdout_status not in {"sealed", "authorized", "evaluated"}:
            raise WinnerArchetypeError("holdout_status is unsupported")
        if self.rejection_status not in {"active", "rejected", "superseded"}:
            raise WinnerArchetypeError("rejection_status is unsupported")
        if self.supersedes_hypothesis_id is not None:
            _identifier(self.supersedes_hypothesis_id, "supersedes_hypothesis_id")
            if self.supersedes_hypothesis_id == self.hypothesis_id:
                raise WinnerArchetypeError("A hypothesis cannot supersede itself")
        if type(self.frozen) is not bool:
            raise WinnerArchetypeError("frozen must be boolean")
        if self.frozen:
            _hash(self.parameter_freeze_hash, "parameter_freeze_hash")
        elif self.parameter_freeze_hash is not None:
            raise WinnerArchetypeError("Unfrozen hypotheses cannot carry a parameter hash")
        if self.creation_timestamp_metadata is not None:
            _timestamp(self.creation_timestamp_metadata, "creation_timestamp_metadata")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> HypothesisRecord:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Hypothesis record")
        payload = dict(value)
        payload["allowed_features"] = tuple(payload["allowed_features"])
        return cls(**payload)  # type: ignore[arg-type]


@dataclass(frozen=True)
class HypothesisFreezeSpec(StrictContract):
    schema_version: str
    rule_or_model_specification: Mapping[str, object]
    parameter_values: Mapping[str, object]
    outcome_definition_hash: str
    matching_spec_hash: str
    partition_plan_id: str
    feature_definition_hashes: Mapping[str, str]
    missing_data_policy: str
    statistical_test: str
    multiple_testing_family: str
    decision_threshold: Mapping[str, object]
    deterministic_seed: int

    SCHEMA = HYPOTHESIS_FREEZE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported hypothesis-freeze schema")
        for field in ("rule_or_model_specification", "parameter_values", "decision_threshold"):
            value = getattr(self, field)
            if not isinstance(value, Mapping) or not value:
                raise WinnerArchetypeError(f"{field} must be a non-empty mapping")
            _bounded_json(dict(value))
        for field in ("outcome_definition_hash", "matching_spec_hash", "partition_plan_id"):
            _hash(getattr(self, field), field)
        if not self.feature_definition_hashes:
            raise WinnerArchetypeError("A freeze requires feature-definition hashes")
        for name, item in self.feature_definition_hashes.items():
            _identifier(name, "frozen feature name")
            _hash(item, "feature_definition_hash")
        for field in ("missing_data_policy", "statistical_test", "multiple_testing_family"):
            _text(getattr(self, field), field)
        _integer(self.deterministic_seed, "deterministic_seed")


@dataclass(frozen=True)
class WinnerArchetypeExperimentSpec(StrictContract):
    schema_version: str
    experiment_version: str
    research_question: str
    selection_start: str
    initial_end: str
    initial_sessions: int
    extension_sessions: int
    minimum_eligible_events: int
    maximum_sessions: int
    hard_latest_date: str
    warmup_start: str
    warmup_end: str
    selection_cutoff_local: str
    selection_timezone: str
    selection_cutoff_semantics: str
    minimum_gap: float
    minimum_premarket_dollar_volume: float
    minimum_premarket_relative_volume: float
    selection_feed: str
    evaluation_feed: str
    partition_spec: CohortPartitionSpec
    decision_snapshots: tuple[DecisionSnapshotSpec, ...]
    feature_definitions: tuple[FeatureDefinition, ...]
    outcome_definitions: tuple[OutcomeDefinition, ...]
    control_matching_spec: ControlMatchingSpec
    deterministic_seed: int
    minimum_archetype_sample: int
    confidence_level: float
    bootstrap_iterations: int
    resampling_unit: str
    sensitivity_dimensions: tuple[str, ...]
    multiple_testing_correction: str
    holdout_access_policy: str
    feature_input_window_policy: str
    multiple_testing_family: str
    effect_size_definition: str
    missing_data_sensitivity_plan: str
    outcome_sensitivity_plan: str
    regime_stability_plan: str

    SCHEMA = EXPERIMENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported experiment schema")
        _identifier(self.experiment_version, "experiment_version")
        _text(self.research_question, "research_question")
        start = _date(self.selection_start, "selection_start")
        initial_end = _date(self.initial_end, "initial_end")
        latest = _date(self.hard_latest_date, "hard_latest_date")
        warmup_start = _date(self.warmup_start, "warmup_start")
        warmup_end = _date(self.warmup_end, "warmup_end")
        if not warmup_start <= warmup_end < start <= initial_end <= latest:
            raise WinnerArchetypeError("Research and warm-up dates are inconsistent")
        for field in ("initial_sessions", "extension_sessions", "minimum_eligible_events", "maximum_sessions"):
            _integer(getattr(self, field), field, minimum=1)
        if self.initial_sessions > self.maximum_sessions:
            raise WinnerArchetypeError("initial_sessions exceeds maximum_sessions")
        _clock(self.selection_cutoff_local, "selection_cutoff_local")
        _zone(self.selection_timezone, "selection_timezone")
        if self.selection_cutoff_semantics != "exclusive":
            raise WinnerArchetypeError("Selection cutoff must be exclusive")
        _number(self.minimum_gap, "minimum_gap", minimum=0.0)
        _number(self.minimum_premarket_dollar_volume, "minimum_premarket_dollar_volume", minimum=0.0)
        _number(self.minimum_premarket_relative_volume, "minimum_premarket_relative_volume", minimum=0.0)
        if self.selection_feed != "sip" or self.evaluation_feed != "sip":
            raise WinnerArchetypeError("Selection and evaluation require SIP")
        if len({item.snapshot_version for item in self.decision_snapshots}) != len(self.decision_snapshots):
            raise WinnerArchetypeError("Duplicate decision snapshot versions")
        if len({item.name for item in self.feature_definitions}) != len(self.feature_definitions):
            raise WinnerArchetypeError("Duplicate feature names")
        if len({item.definition_version for item in self.outcome_definitions}) != len(self.outcome_definitions):
            raise WinnerArchetypeError("Duplicate outcome definition versions")
        _integer(self.deterministic_seed, "deterministic_seed")
        _integer(self.minimum_archetype_sample, "minimum_archetype_sample", minimum=1)
        confidence = _number(self.confidence_level, "confidence_level")
        if not 0 < confidence < 1:
            raise WinnerArchetypeError("confidence_level must be within (0, 1)")
        _integer(self.bootstrap_iterations, "bootstrap_iterations", minimum=1_000)
        if self.resampling_unit != "session_cluster_primary_event_secondary":
            raise WinnerArchetypeError("resampling_unit must preserve clustered dependence")
        _strings(self.sensitivity_dimensions, "sensitivity_dimensions")
        if self.multiple_testing_correction not in {"benjamini_hochberg", "holm"}:
            raise WinnerArchetypeError("multiple_testing_correction is unsupported")
        if self.holdout_access_policy != "frozen_hypothesis_and_parameter_hash_required":
            raise WinnerArchetypeError("holdout_access_policy is unsafe")
        if self.feature_input_window_policy != "every_feature_window_ends_at_or_before_snapshot_cutoff":
            raise WinnerArchetypeError("feature_input_window_policy is unsafe")
        for field in (
            "multiple_testing_family", "effect_size_definition",
            "missing_data_sensitivity_plan", "outcome_sensitivity_plan",
            "regime_stability_plan",
        ):
            _text(getattr(self, field), field)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> WinnerArchetypeExperimentSpec:
        _exact_mapping(value, set(cls.__dataclass_fields__) - {"SCHEMA"}, "Experiment spec")
        payload = dict(value)
        payload["partition_spec"] = CohortPartitionSpec.from_mapping(payload["partition_spec"])
        payload["decision_snapshots"] = tuple(
            DecisionSnapshotSpec.from_mapping(item) for item in payload["decision_snapshots"]
        )
        payload["feature_definitions"] = tuple(
            FeatureDefinition.from_mapping(item) for item in payload["feature_definitions"]
        )
        payload["outcome_definitions"] = tuple(
            OutcomeDefinition.from_mapping(item) for item in payload["outcome_definitions"]
        )
        payload["control_matching_spec"] = ControlMatchingSpec.from_mapping(
            payload["control_matching_spec"]
        )
        payload["sensitivity_dimensions"] = tuple(payload["sensitivity_dimensions"])
        return cls(**payload)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ExperimentManifest(StrictContract):
    schema_version: str
    manifest_id: str
    experiment_spec_hash: str
    partition_plan_id: str
    ordered_sessions: tuple[str, ...]
    partition_boundaries: Mapping[str, tuple[str, str]]
    source_manifest_hashes: tuple[str, ...]
    feature_definition_hashes: tuple[str, ...]
    outcome_definition_hashes: tuple[str, ...]
    control_matching_hash: str
    hypothesis_registry_hash: str | None
    holdout_accessed: bool

    SCHEMA = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != self.SCHEMA:
            raise WinnerArchetypeError("Unsupported manifest schema")
        _hash(self.manifest_id, "manifest_id")
        for field in ("experiment_spec_hash", "partition_plan_id", "control_matching_hash"):
            _hash(getattr(self, field), field)
        if self.hypothesis_registry_hash is not None:
            _hash(self.hypothesis_registry_hash, "hypothesis_registry_hash")
        if type(self.holdout_accessed) is not bool:
            raise WinnerArchetypeError("holdout_accessed must be boolean")
        sessions = tuple(_date(item, "ordered_session").isoformat() for item in self.ordered_sessions)
        if sessions != tuple(sorted(set(sessions))):
            raise WinnerArchetypeError("Manifest sessions must be ordered and unique")
        if set(self.partition_boundaries) != {"discovery", "validation", "holdout"}:
            raise WinnerArchetypeError("Manifest partition boundaries are incomplete")
        for boundary in self.partition_boundaries.values():
            if len(boundary) != 2 or _date(boundary[0], "boundary") > _date(boundary[1], "boundary"):
                raise WinnerArchetypeError("Manifest partition boundary is invalid")
        discovery = self.partition_boundaries["discovery"]
        validation = self.partition_boundaries["validation"]
        holdout = self.partition_boundaries["holdout"]
        if not (
            discovery[0] == sessions[0]
            and discovery[1] < validation[0] <= validation[1] < holdout[0]
            and holdout[1] == sessions[-1]
            and all(item in sessions for item in (*discovery, *validation, *holdout))
        ):
            raise WinnerArchetypeError("Manifest partition boundaries overlap or omit edges")
        collections = (
            self.source_manifest_hashes,
            self.feature_definition_hashes,
            self.outcome_definition_hashes,
        )
        if any(not collection for collection in collections):
            raise WinnerArchetypeError("Manifest digest collections cannot be empty")
        for collection in collections:
            for item in collection:
                _hash(item, "manifest digest")
            if tuple(sorted(set(collection))) != collection:
                raise WinnerArchetypeError("Manifest digest collections must be sorted and unique")
        payload = {
            key: value for key, value in self.to_dict().items()
            if key not in {"schema_version", "manifest_id"}
        }
        if self.manifest_id != canonical_hash(payload):
            raise WinnerArchetypeError("manifest_id is invalid")


def load_experiment_spec(path: str | Any) -> WinnerArchetypeExperimentSpec:
    """Load a bounded strict experiment specification from a local JSON file."""
    from pathlib import Path

    source = Path(path)
    normalized_parts = {part.casefold().replace("_", "-") for part in source.parts}
    if normalized_parts & {"holdout", "sealed", "validation-extension", "forward-validation"}:
        raise WinnerArchetypeError("Research contracts cannot be loaded from protected outcome paths")
    absolute = source if source.is_absolute() else Path.cwd() / source
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise WinnerArchetypeError("Experiment specification path contains a symlink")
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 1_000_000:
        raise WinnerArchetypeError("Experiment specification path is unsafe")
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = item
        return result

    try:
        value = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise WinnerArchetypeError("Experiment specification is invalid JSON") from exc
    if not isinstance(value, dict):
        raise WinnerArchetypeError("Experiment specification must contain an object")
    return WinnerArchetypeExperimentSpec.from_mapping(value)
