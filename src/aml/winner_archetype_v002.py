"""Prospective, provider-neutral contracts for Winner Archetype Protocol V002."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


PROTOCOL_SCHEMA = "aml.winner-archetype.protocol.v002"
SOURCE_MATRIX_SCHEMA = "aml.winner-archetype.source-requirements.v002"
SECURITY_IDENTITY_SCHEMA = "aml.winner-archetype.security-identity.v002"
SYMBOL_LINEAGE_SCHEMA = "aml.winner-archetype.symbol-lineage.v002"
UNIVERSE_SNAPSHOT_SCHEMA = "aml.winner-archetype.universe-snapshot.v002"
SESSION_SCHEMA = "aml.winner-archetype.session.v002"
CAPABILITY_SCHEMA = "aml.winner-archetype.provider-capability.v002"
ENTITLEMENT_SCHEMA = "aml.winner-archetype.entitlement-evidence.v002"
EVIDENCE_SCHEMA = "aml.winner-archetype.evidence-assertion.v002"
INPUT_MANIFEST_SCHEMA = "aml.winner-archetype.input-manifest.v002"
EXPERIMENT_BINDING_SCHEMA = "aml.winner-archetype.experiment-binding.v002"
READINESS_SCHEMA = "aml.winner-archetype.readiness.v002"
READINESS_EVIDENCE_SCHEMA = "aml.winner-archetype.readiness-evidence.v002"
V001_EXPERIMENT_IDENTITY = (
    "f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a"
)
PROTECTED_DISCOVERY_PARTS = {
    "validation",
    "holdout",
    "sealed",
    "sealed-holdout",
    "paper-forward",
    "paper_forward",
    "production",
    "operator",
    "forward-validation",
    "validation-extension",
    "future-empirical-artifacts",
}
SIP_DATASETS = {"sip_trades", "sip_quotes", "sip_minute_bars"}
ELIGIBLE_EXCHANGES = {"XASE", "XNAS", "XNYS"}


class V002Error(ValueError):
    """A prospective V002 research-integrity contract was violated."""


class CompletenessState(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CONFLICTING = "conflicting"
    CORRECTED = "corrected"
    SUPERSEDED = "superseded"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"
    COVERAGE_UNKNOWN = "coverage_unknown"
    ENTITLEMENT_UNVERIFIED = "entitlement_unverified"


BLOCKING_STATES = {
    CompletenessState.INCOMPLETE,
    CompletenessState.CONFLICTING,
    CompletenessState.SUPERSEDED,
    CompletenessState.UNAVAILABLE,
    CompletenessState.INVALID,
    CompletenessState.COVERAGE_UNKNOWN,
    CompletenessState.ENTITLEMENT_UNVERIFIED,
}


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise V002Error(f"{field} must be a SHA-256 digest")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V002Error(f"{field} must be a non-empty string")
    canonical_json({field: value})
    return value


def _timestamp(value: object, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V002Error(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V002Error(f"{field} must include a timezone")
    return parsed


def _state(value: CompletenessState | str, field: str) -> CompletenessState:
    try:
        return CompletenessState(value)
    except ValueError as exc:
        raise V002Error(f"{field} is unsupported") from exc


def validate_not_future(value: str, as_of: str, field: str) -> None:
    if _timestamp(value, field) > _timestamp(as_of, "as_of"):
        raise V002Error(f"{field} cannot be future-dated")


def _sorted_unique_hashes(values: Sequence[str], field: str) -> tuple[str, ...]:
    result = tuple(_hash(item, field) for item in values)
    if not result or result != tuple(sorted(set(result))):
        raise V002Error(f"{field} must be non-empty, sorted, and unique")
    return result


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise V002Error("V002 JSON path is missing or exceeds the size limit")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise V002Error("V002 JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(V002Error(item)),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, V002Error) as exc:
        raise V002Error("V002 input is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise V002Error("V002 JSON root must be an object")
    canonical_json(value)
    return value


def authorize_discovery_path(path: Path, allowed_root: Path) -> Path:
    """Reject protected names, traversal, symlinks, and escapes before any read."""
    if ".." in path.parts:
        raise V002Error("Discovery path traversal is prohibited")
    normalized = {part.casefold().replace("_", "-") for part in path.parts}
    if normalized & {item.replace("_", "-") for item in PROTECTED_DISCOVERY_PARTS}:
        raise V002Error("Discovery cannot access protected artifact paths")
    lexical = path if path.is_absolute() else allowed_root / path
    lexical = lexical.absolute()
    cursor = lexical
    while cursor != cursor.parent:
        if cursor.exists() and cursor.is_symlink():
            raise V002Error("Discovery paths cannot contain symlinks")
        cursor = cursor.parent
    root = allowed_root.resolve(strict=True)
    resolved = lexical.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise V002Error("Discovery path escapes its approved root") from exc
    return resolved


@dataclass(frozen=True)
class WinnerArchetypeProtocolV002:
    schema_version: str
    protocol_version: str
    prospective_as_of: str
    prior_protocol: Mapping[str, object]
    planning: Mapping[str, object]
    universe: Mapping[str, object]
    security_identity: Mapping[str, object]
    calendar: Mapping[str, object]
    market_data: Mapping[str, object]
    corporate_actions: Mapping[str, object]
    halts: Mapping[str, object]
    catalysts: Mapping[str, object]
    provenance: Mapping[str, object]
    completeness: Mapping[str, object]
    separation: Mapping[str, object]
    compatibility: Mapping[str, object]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "WinnerArchetypeProtocolV002":
        if not isinstance(value, Mapping) or value.get("schema_version") != PROTOCOL_SCHEMA:
            raise V002Error("V001 and other protocol schemas are not V002-compatible")
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise V002Error("V002 protocol contains missing or unexpected fields")
        if value["protocol_version"] != "winner-archetype-protocol-v002":
            raise V002Error("V002 protocol version is unsupported")
        _timestamp(value["prospective_as_of"], "prospective_as_of")
        prior = value["prior_protocol"]
        if not isinstance(prior, Mapping) or prior.get("experiment_identity") != V001_EXPERIMENT_IDENTITY:
            raise V002Error("V002 must explicitly bind the frozen V001 identity")
        required_nested = {
            "planning": {"selection_start", "initial_sessions", "extension_sessions", "maximum_sessions", "minimum_eligible_events", "partition_basis_points"},
            "universe": {"eligible_exchanges", "eligible_security_types", "excluded_security_types", "required_flags", "non_required_flags", "completeness_rule"},
            "security_identity": {"stable_identifier_rule", "symbol_lineage_rule", "future_knowledge_rule"},
            "calendar": {"provider", "provider_version", "calendar_id", "timezone", "premarket_start", "selection_cutoff", "selection_cutoff_semantics", "regular_open", "early_close_rule", "outcome_end_rule", "conflict_rule"},
            "market_data": {"required_feed", "required_datasets", "quote_max_age_seconds", "adjustment_policy", "missing_data_rule", "feed_substitution_rule"},
            "corporate_actions": {"required_types", "knowledge_time_rule", "adjustment_rule"},
            "halts": {"required_types", "absence_evidence_rule", "conflict_rule"},
            "catalysts": {"required_categories", "minimum_coverage", "unknown_rule", "duplicate_rule"},
            "provenance": {"required_fields", "hash_algorithm", "canonical_serialization"},
            "completeness": {"states", "blocking_states", "silent_drop_rule"},
            "separation": {"execution_phase", "protected_path_parts", "access_rule"},
            "compatibility": {"v001_immutable", "automatic_migration", "production_behavior"},
        }
        for field, keys in required_nested.items():
            section = value[field]
            if not isinstance(section, Mapping) or not keys.issubset(section):
                raise V002Error(f"V002 {field} section is incomplete")
        if value["market_data"]["required_feed"] != "sip":
            raise V002Error("V002 requires SIP and prohibits feed substitution")
        if value["calendar"]["timezone"] != "America/New_York":
            raise V002Error("V002 market timezone must be America/New_York")
        if value["calendar"]["early_close_rule"] != "eligible_use_scheduled_close":
            raise V002Error("V002 early-close behavior must be explicit")
        protocol = cls(**value)
        protocol.identity
        return protocol

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


def load_protocol_v002(path: Path) -> WinnerArchetypeProtocolV002:
    return WinnerArchetypeProtocolV002.from_mapping(_strict_json(path))


@dataclass(frozen=True)
class SecurityIdentity:
    schema_version: str
    canonical_security_id: str
    listing_id: str
    issuer_id: str
    identifier_source: str
    identifier_source_version: str
    effective_from: str
    effective_to: str | None
    first_known_at: str
    revision: int
    supersedes_identity: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SECURITY_IDENTITY_SCHEMA:
            raise V002Error("Security identity schema is not V002")
        for field in (
            "canonical_security_id", "listing_id", "issuer_id",
            "identifier_source", "identifier_source_version",
        ):
            _text(getattr(self, field), field)
        start = _timestamp(self.effective_from, "effective_from")
        known = _timestamp(self.first_known_at, "first_known_at")
        if self.effective_to is not None and _timestamp(self.effective_to, "effective_to") <= start:
            raise V002Error("Security identity effective interval is invalid")
        if type(self.revision) is not int or self.revision < 1:
            raise V002Error("Security identity revision must be positive")
        if self.revision == 1 and self.supersedes_identity is not None:
            raise V002Error("Initial security identity cannot supersede another identity")
        if self.revision > 1:
            _hash(self.supersedes_identity, "supersedes_identity")
        if known > start and self.revision == 1:
            raise V002Error("Initial security identity cannot be known after it becomes effective")

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class SymbolLineageRecord:
    schema_version: str
    canonical_security_id: str
    listing_id: str
    symbol: str
    effective_from: str
    effective_to: str | None
    first_known_at: str
    source_manifest_hash: str
    revision: int
    supersedes_record_hash: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SYMBOL_LINEAGE_SCHEMA:
            raise V002Error("Symbol lineage schema is not V002")
        for field in ("canonical_security_id", "listing_id", "symbol"):
            _text(getattr(self, field), field)
        if self.symbol != self.symbol.upper():
            raise V002Error("Symbol lineage symbols must be normalized")
        start = _timestamp(self.effective_from, "effective_from")
        known = _timestamp(self.first_known_at, "first_known_at")
        if self.effective_to is not None and _timestamp(self.effective_to, "effective_to") <= start:
            raise V002Error("Symbol lineage interval is invalid")
        if known > start:
            raise V002Error("Symbol changes cannot be applied before first knowledge")
        _hash(self.source_manifest_hash, "source_manifest_hash")
        if type(self.revision) is not int or self.revision < 1:
            raise V002Error("Symbol lineage revision must be positive")
        if self.revision > 1:
            _hash(self.supersedes_record_hash, "supersedes_record_hash")
        elif self.supersedes_record_hash is not None:
            raise V002Error("Initial symbol lineage cannot supersede a record")

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class UniverseConstituent:
    security_identity_hash: str
    symbol_lineage_hash: str
    canonical_security_id: str
    listing_id: str
    symbol: str
    primary_exchange: str
    security_type: str
    listing_status: str
    selection_timestamp: str
    eligibility_effective_from: str
    eligibility_effective_to: str | None
    first_known_at: str
    tradable: bool
    quoteable: bool
    sip_covered: bool

    def __post_init__(self) -> None:
        _hash(self.security_identity_hash, "security_identity_hash")
        _hash(self.symbol_lineage_hash, "symbol_lineage_hash")
        for field in (
            "canonical_security_id", "listing_id", "symbol", "primary_exchange",
            "security_type", "listing_status",
        ):
            _text(getattr(self, field), field)
        if self.symbol != self.symbol.upper():
            raise V002Error("Universe symbol must be normalized")
        if self.primary_exchange not in ELIGIBLE_EXCHANGES:
            raise V002Error("Universe exchange is not V002-eligible")
        if self.security_type != "common_stock":
            raise V002Error("Only common stock is V002-eligible")
        if any(
            type(value) is not bool
            for value in (self.tradable, self.quoteable, self.sip_covered)
        ):
            raise V002Error("Universe eligibility flags must be boolean")
        selection = _timestamp(self.selection_timestamp, "selection_timestamp")
        effective = _timestamp(self.eligibility_effective_from, "eligibility_effective_from")
        known = _timestamp(self.first_known_at, "first_known_at")
        if known > selection:
            raise V002Error("Future-known universe records cannot leak backward")
        if effective > selection:
            raise V002Error("Future eligibility cannot be applied to an earlier selection")
        if self.eligibility_effective_to is not None:
            end = _timestamp(self.eligibility_effective_to, "eligibility_effective_to")
            if end <= selection:
                raise V002Error("Delisted or inactive listings are not selection-eligible")
        if self.listing_status != "active":
            raise V002Error("Only active listings are universe constituents")
        if not (self.tradable and self.quoteable and self.sip_covered):
            raise V002Error("Eligible constituents require tradable, quoteable, SIP coverage")

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class UniverseSnapshot:
    schema_version: str
    session: str
    selection_timestamp: str
    source_manifest_hashes: tuple[str, ...]
    coverage_state: CompletenessState
    expected_constituent_count: int
    constituents: tuple[UniverseConstituent, ...]

    def __post_init__(self) -> None:
        if self.schema_version != UNIVERSE_SNAPSHOT_SCHEMA:
            raise V002Error("Universe snapshot schema is not V002")
        date.fromisoformat(self.session)
        _timestamp(self.selection_timestamp, "selection_timestamp")
        _sorted_unique_hashes(self.source_manifest_hashes, "source_manifest_hashes")
        state = _state(self.coverage_state, "coverage_state")
        if state is not CompletenessState.COMPLETE:
            raise V002Error("Universe completeness must be proven before selection")
        if type(self.expected_constituent_count) is not int or self.expected_constituent_count < 1:
            raise V002Error("Universe expected count must be positive")
        ordered = tuple(sorted(self.constituents, key=lambda item: (item.canonical_security_id, item.listing_id)))
        if ordered != self.constituents:
            raise V002Error("Universe constituents must use deterministic stable-ID ordering")
        identities = [item.identity for item in self.constituents]
        if len(identities) != self.expected_constituent_count or len(set(identities)) != len(identities):
            raise V002Error("Universe constituents are missing or duplicated")
        if any(item.selection_timestamp != self.selection_timestamp for item in self.constituents):
            raise V002Error("Universe constituent cutoff conflicts with its snapshot")

    @property
    def identity(self) -> str:
        payload = asdict(self)
        payload["coverage_state"] = self.coverage_state.value
        return canonical_hash(payload)


@dataclass(frozen=True)
class SessionContract:
    schema_version: str
    session: str
    timezone: str
    calendar_identity: str
    scheduled_open: str
    scheduled_close: str
    premarket_start: str
    selection_cutoff: str
    early_close: bool
    calendar_state: CompletenessState

    def __post_init__(self) -> None:
        if self.schema_version != SESSION_SCHEMA:
            raise V002Error("Session schema is not V002")
        session = date.fromisoformat(self.session)
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise V002Error("Session timezone is not IANA-valid") from exc
        if self.timezone != "America/New_York":
            raise V002Error("V002 session timezone must be America/New_York")
        _hash(self.calendar_identity, "calendar_identity")
        opened = _timestamp(self.scheduled_open, "scheduled_open")
        closed = _timestamp(self.scheduled_close, "scheduled_close")
        premarket = _timestamp(self.premarket_start, "premarket_start")
        cutoff = _timestamp(self.selection_cutoff, "selection_cutoff")
        zone = ZoneInfo(self.timezone)
        boundaries = (opened, closed, premarket, cutoff)
        if any(item.astimezone(zone).date() != session for item in boundaries):
            raise V002Error("Session timestamps must fall on the declared market date")
        if any(item.utcoffset() != item.astimezone(zone).utcoffset() for item in boundaries):
            raise V002Error("Session timestamp offset conflicts with market timezone")
        if not (premarket < cutoff < opened < closed):
            raise V002Error("Session boundaries are not strictly ordered")
        if (
            cutoff.astimezone(zone).strftime("%H:%M:%S") != "09:25:00"
            or premarket.astimezone(zone).strftime("%H:%M:%S") != "04:00:00"
        ):
            raise V002Error("V002 premarket and selection cutoffs are fixed")
        if _state(self.calendar_state, "calendar_state") is not CompletenessState.COMPLETE:
            raise V002Error("Conflicting or incomplete calendars block the session")
        expected_early = closed.astimezone(ZoneInfo(self.timezone)).strftime("%H:%M") != "16:00"
        if self.early_close != expected_early:
            raise V002Error("Early-close flag conflicts with scheduled close")

    @property
    def outcome_end(self) -> str:
        return (_timestamp(self.scheduled_close, "scheduled_close") - timedelta(minutes=1)).isoformat()

    @property
    def identity(self) -> str:
        payload = asdict(self)
        payload["calendar_state"] = self.calendar_state.value
        payload["outcome_end"] = self.outcome_end
        return canonical_hash(payload)


@dataclass(frozen=True)
class SourceRequirement:
    dataset: str
    required_capability: str
    authoritative_role: str
    acceptable_substitute: str
    corroborating_source: str
    point_in_time_requirement: str
    completeness_requirement: str
    historical_range: str
    security_coverage: str
    session_coverage: str
    entitlement_status: str
    provider_candidate: str
    cost_status: str
    readiness_state: str
    blocking_reason: str

    def __post_init__(self) -> None:
        for field, value in asdict(self).items():
            _text(value, field)

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class SourceRequirementsMatrix:
    schema_version: str
    matrix_version: str
    requirements: tuple[SourceRequirement, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "SourceRequirementsMatrix":
        if set(value) != {"schema_version", "matrix_version", "requirements"}:
            raise V002Error("Source matrix contains missing or unexpected fields")
        if value["schema_version"] != SOURCE_MATRIX_SCHEMA:
            raise V002Error("V001 source requirements are not V002-compatible")
        _text(value["matrix_version"], "matrix_version")
        raw = value["requirements"]
        if not isinstance(raw, list) or not raw:
            raise V002Error("Source matrix cannot be empty")
        requirements = tuple(SourceRequirement(**item) for item in raw)
        ordered = tuple(sorted(requirements, key=lambda item: (item.dataset, item.required_capability)))
        if requirements != ordered:
            raise V002Error("Source requirements must be deterministically ordered")
        keys = [(item.dataset, item.required_capability) for item in requirements]
        if len(keys) != len(set(keys)):
            raise V002Error("Source requirements cannot be duplicated")
        return cls(value["schema_version"], value["matrix_version"], requirements)

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


def load_source_requirements_v002(path: Path) -> SourceRequirementsMatrix:
    return SourceRequirementsMatrix.from_mapping(_strict_json(path))


@dataclass(frozen=True)
class ProviderCapability:
    schema_version: str
    declaration_id: str
    provider_name: str
    provider_version: str
    dataset: str
    capability: str
    coverage_start: str
    coverage_end: str
    market_coverage: str
    security_coverage: str
    session_coverage: str
    feed_type: str
    timestamp_precision: str
    point_in_time_guarantee: str
    correction_support: str
    historical_revision_support: str
    pagination_or_file_identity: str
    completeness_evidence_hash: str
    source_role: str
    licensing_status: str
    retention_status: str
    declared_at: str

    def __post_init__(self) -> None:
        if self.schema_version != CAPABILITY_SCHEMA:
            raise V002Error("Provider capability schema is not V002")
        for field, value in asdict(self).items():
            if field not in {"completeness_evidence_hash"}:
                _text(value, field)
        _hash(self.completeness_evidence_hash, "completeness_evidence_hash")
        start = date.fromisoformat(self.coverage_start)
        end = date.fromisoformat(self.coverage_end)
        if end < start:
            raise V002Error("Provider capability coverage interval is invalid")
        _timestamp(self.declared_at, "declared_at")
        if self.dataset in SIP_DATASETS and self.feed_type != "sip":
            raise V002Error("Non-SIP capability cannot satisfy a SIP dataset")

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))

    def validate_as_of(self, as_of: str) -> None:
        validate_not_future(self.declared_at, as_of, "declared_at")


@dataclass(frozen=True)
class EntitlementEvidence:
    schema_version: str
    capability_identity: str
    account_scope_hash: str
    verified_at: str
    valid_from: str
    valid_to: str
    status: CompletenessState
    evidence_hash: str
    licensing_status: str
    retention_status: str

    def __post_init__(self) -> None:
        if self.schema_version != ENTITLEMENT_SCHEMA:
            raise V002Error("Entitlement evidence schema is not V002")
        for field in ("capability_identity", "account_scope_hash", "evidence_hash"):
            _hash(getattr(self, field), field)
        verified = _timestamp(self.verified_at, "verified_at")
        valid_from = _timestamp(self.valid_from, "valid_from")
        valid_to = _timestamp(self.valid_to, "valid_to")
        if not valid_from <= verified <= valid_to:
            raise V002Error("Entitlement verification falls outside its validity interval")
        if _state(self.status, "status") is not CompletenessState.COMPLETE:
            raise V002Error("Unverified entitlement cannot authorize acquisition")
        _text(self.licensing_status, "licensing_status")
        _text(self.retention_status, "retention_status")

    @property
    def identity(self) -> str:
        payload = asdict(self)
        payload["status"] = self.status.value
        return canonical_hash(payload)

    def validate_as_of(self, as_of: str) -> None:
        validate_not_future(self.verified_at, as_of, "verified_at")


@dataclass(frozen=True)
class EvidenceAssertion:
    schema_version: str
    evidence_type: str
    subject_id: str
    interval_start: str
    interval_end: str
    assertion: str
    coverage_state: CompletenessState
    coverage_manifest_hash: str | None
    source_record_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != EVIDENCE_SCHEMA:
            raise V002Error("Evidence assertion schema is not V002")
        if self.evidence_type not in {"quote_issue", "halt", "catalyst"}:
            raise V002Error("Evidence assertion type is unsupported")
        if self.assertion not in {"present", "absent", "unknown"}:
            raise V002Error("Evidence assertion is unsupported")
        _text(self.subject_id, "subject_id")
        if _timestamp(self.interval_end, "interval_end") < _timestamp(self.interval_start, "interval_start"):
            raise V002Error("Evidence assertion interval is invalid")
        state = _state(self.coverage_state, "coverage_state")
        if self.assertion == "absent":
            if state is not CompletenessState.COMPLETE or self.coverage_manifest_hash is None:
                raise V002Error("Negative evidence requires proven complete source coverage")
            _hash(self.coverage_manifest_hash, "coverage_manifest_hash")
        if self.assertion == "unknown" and state is CompletenessState.COMPLETE:
            raise V002Error("Unknown evidence cannot claim complete classification")
        if self.assertion == "present" and not self.source_record_hashes:
            raise V002Error("Positive evidence requires source records")
        if self.source_record_hashes:
            _sorted_unique_hashes(self.source_record_hashes, "source_record_hashes")

    @property
    def identity(self) -> str:
        payload = asdict(self)
        payload["coverage_state"] = self.coverage_state.value
        return canonical_hash(payload)

@dataclass(frozen=True)
class CorporateActionRecord:
    action_id: str
    canonical_security_id: str
    action_type: str
    announcement_timestamp: str
    first_known_at: str
    effective_timestamp: str
    source_manifest_hash: str
    revision: int
    supersedes_record_hash: str | None

    def __post_init__(self) -> None:
        for field in ("action_id", "canonical_security_id", "action_type"):
            _text(getattr(self, field), field)
        _timestamp(self.announcement_timestamp, "announcement_timestamp")
        _timestamp(self.first_known_at, "first_known_at")
        _timestamp(self.effective_timestamp, "effective_timestamp")
        _hash(self.source_manifest_hash, "source_manifest_hash")
        if type(self.revision) is not int or self.revision < 1:
            raise V002Error("Corporate-action revision must be positive")
        if self.revision > 1:
            _hash(self.supersedes_record_hash, "supersedes_record_hash")
        elif self.supersedes_record_hash is not None:
            raise V002Error("Initial corporate action cannot supersede a record")

    def usable_at(self, timestamp: str, *, adjustment: bool) -> bool:
        decision = _timestamp(timestamp, "decision_timestamp")
        if _timestamp(self.first_known_at, "first_known_at") > decision:
            return False
        return not adjustment or _timestamp(self.effective_timestamp, "effective_timestamp") <= decision

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class ImmutableInputManifest:
    schema_version: str
    manifest_version: str
    dataset: str
    execution_phase: str
    feed_type: str
    source_name: str
    source_role: str
    source_version: str
    query_or_file_identity: str
    retrieval_timestamp: str
    coverage_start: str
    coverage_end: str
    raw_sha256: tuple[str, ...]
    normalized_sha256: tuple[str, ...]
    parser_version: str
    normalization_version: str
    completeness_state: CompletenessState
    revision: int
    supersedes_manifest_hash: str | None
    correction_timestamp: str | None

    def __post_init__(self) -> None:
        if self.schema_version != INPUT_MANIFEST_SCHEMA:
            raise V002Error("V001 and other input manifests are rejected by V002")
        for field in (
            "manifest_version", "dataset", "source_name", "source_role",
            "source_version", "query_or_file_identity", "parser_version",
            "normalization_version",
        ):
            _text(getattr(self, field), field)
        if self.execution_phase != "discovery":
            raise V002Error("V002 discovery manifests cannot bind another phase")
        retrieved = _timestamp(self.retrieval_timestamp, "retrieval_timestamp")
        start = _timestamp(self.coverage_start, "coverage_start")
        end = _timestamp(self.coverage_end, "coverage_end")
        if end < start or retrieved < end:
            raise V002Error("Manifest coverage or retrieval timestamps are future-dated")
        _sorted_unique_hashes(self.raw_sha256, "raw_sha256")
        _sorted_unique_hashes(self.normalized_sha256, "normalized_sha256")
        state = _state(self.completeness_state, "completeness_state")
        if state in BLOCKING_STATES:
            raise V002Error("Blocking completeness state cannot enter an experiment")
        if self.dataset in SIP_DATASETS and self.feed_type != "sip":
            raise V002Error("SIP datasets reject IEX, indicative, delayed, or substituted feeds")
        if type(self.revision) is not int or self.revision < 1:
            raise V002Error("Manifest revision must be positive")
        if state is CompletenessState.CORRECTED and self.revision == 1:
            raise V002Error("Corrected manifest requires append-only revision lineage")
        if self.revision == 1:
            if self.supersedes_manifest_hash is not None or self.correction_timestamp is not None:
                raise V002Error("Initial manifest cannot claim correction lineage")
        else:
            _hash(self.supersedes_manifest_hash, "supersedes_manifest_hash")
            corrected = _timestamp(self.correction_timestamp, "correction_timestamp")
            if corrected < retrieved:
                raise V002Error("Correction timestamp cannot precede the original retrieval")

    @property
    def identity(self) -> str:
        payload = asdict(self)
        payload["completeness_state"] = self.completeness_state.value
        return canonical_hash(payload)

    def validate_as_of(self, as_of: str) -> None:
        validate_not_future(self.retrieval_timestamp, as_of, "retrieval_timestamp")
        if self.correction_timestamp is not None:
            validate_not_future(self.correction_timestamp, as_of, "correction_timestamp")


@dataclass(frozen=True)
class RequirementReadinessEvidence:
    """Manifest-only evidence for one source requirement; never empirical rows."""

    dataset: str
    required_capability: str
    capability: ProviderCapability | None
    entitlement: EntitlementEvidence | None
    input_manifests: tuple[ImmutableInputManifest, ...]
    coverage_evidence_hashes: tuple[str, ...]
    expected_security_set_hash: str | None
    observed_security_set_hash: str | None
    expected_session_set_hash: str | None
    observed_session_set_hash: str | None
    conflict_status: str

    def __post_init__(self) -> None:
        _text(self.dataset, "dataset")
        _text(self.required_capability, "required_capability")
        if self.capability is not None:
            if (
                self.capability.dataset != self.dataset
                or self.capability.capability != self.required_capability
            ):
                raise V002Error("Capability evidence does not match its source requirement")
        if self.entitlement is not None:
            if self.capability is None:
                raise V002Error("Entitlement evidence requires a bound capability")
            if self.entitlement.capability_identity != self.capability.identity:
                raise V002Error("Entitlement evidence does not bind the declared capability")
        ordered = deterministic_unique_records(self.input_manifests)
        if ordered != self.input_manifests:
            raise V002Error("Input manifests must be deterministically ordered and unique")
        if any(item.dataset != self.dataset for item in self.input_manifests):
            raise V002Error("Input manifest dataset does not match its source requirement")
        if self.input_manifests and self.capability is None:
            raise V002Error("Acquired manifests require a bound provider capability")
        for manifest in self.input_manifests:
            if (
                manifest.source_name != self.capability.provider_name
                or manifest.source_role != self.capability.source_role
                or manifest.feed_type != self.capability.feed_type
            ):
                raise V002Error("Input manifest does not match its provider capability")
            capability_start = date.fromisoformat(self.capability.coverage_start)
            capability_end = date.fromisoformat(self.capability.coverage_end)
            manifest_start = _timestamp(manifest.coverage_start, "coverage_start").date()
            manifest_end = _timestamp(manifest.coverage_end, "coverage_end").date()
            if not capability_start <= manifest_start <= manifest_end <= capability_end:
                raise V002Error("Input manifest exceeds declared provider coverage")
            if self.entitlement is not None:
                retrieved = _timestamp(manifest.retrieval_timestamp, "retrieval_timestamp")
                valid_from = _timestamp(self.entitlement.valid_from, "valid_from")
                valid_to = _timestamp(self.entitlement.valid_to, "valid_to")
                if not valid_from <= retrieved <= valid_to:
                    raise V002Error("Input manifest was retrieved outside entitlement validity")
        if self.coverage_evidence_hashes:
            _sorted_unique_hashes(
                self.coverage_evidence_hashes,
                "coverage_evidence_hashes",
            )
        for expected_field, observed_field in (
            ("expected_security_set_hash", "observed_security_set_hash"),
            ("expected_session_set_hash", "observed_session_set_hash"),
        ):
            expected = getattr(self, expected_field)
            observed = getattr(self, observed_field)
            if (expected is None) != (observed is None):
                raise V002Error("Expected and observed coverage hashes must be supplied together")
            if expected is not None:
                _hash(expected, expected_field)
                _hash(observed, observed_field)
        if self.conflict_status not in {"clear", "conflicting", "unverified"}:
            raise V002Error("Conflict status is unsupported")

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class ReadinessEvidenceBundle:
    """Provider-neutral readiness ledger bound to the frozen V002 identities."""

    schema_version: str
    evidence_version: str
    protocol_identity: str
    source_requirements_identity: str
    as_of: str
    requirements: tuple[RequirementReadinessEvidence, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ReadinessEvidenceBundle":
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected or value.get("schema_version") != READINESS_EVIDENCE_SCHEMA:
            raise V002Error("Readiness evidence contains missing or unexpected fields")
        _text(value["evidence_version"], "evidence_version")
        _hash(value["protocol_identity"], "protocol_identity")
        _hash(value["source_requirements_identity"], "source_requirements_identity")
        _timestamp(value["as_of"], "as_of")
        raw_requirements = value["requirements"]
        if not isinstance(raw_requirements, list) or not raw_requirements:
            raise V002Error("Readiness evidence requirements cannot be empty")
        requirements = tuple(_readiness_requirement_from_mapping(item) for item in raw_requirements)
        ordered = tuple(sorted(requirements, key=lambda item: (item.dataset, item.required_capability)))
        if requirements != ordered:
            raise V002Error("Readiness evidence requirements must be deterministically ordered")
        keys = [(item.dataset, item.required_capability) for item in requirements]
        if len(keys) != len(set(keys)):
            raise V002Error("Readiness evidence requirements cannot be duplicated")
        bundle = cls(
            schema_version=value["schema_version"],
            evidence_version=value["evidence_version"],
            protocol_identity=value["protocol_identity"],
            source_requirements_identity=value["source_requirements_identity"],
            as_of=value["as_of"],
            requirements=requirements,
        )
        for requirement in bundle.requirements:
            if requirement.capability is not None:
                requirement.capability.validate_as_of(bundle.as_of)
            if requirement.entitlement is not None:
                requirement.entitlement.validate_as_of(bundle.as_of)
            for manifest in requirement.input_manifests:
                manifest.validate_as_of(bundle.as_of)
        return bundle

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


def _readiness_requirement_from_mapping(value: object) -> RequirementReadinessEvidence:
    if not isinstance(value, Mapping):
        raise V002Error("Readiness requirement evidence must be an object")
    expected = set(RequirementReadinessEvidence.__dataclass_fields__)
    if set(value) != expected:
        raise V002Error("Readiness requirement evidence contains missing or unexpected fields")
    capability_value = value["capability"]
    entitlement_value = value["entitlement"]
    manifests_value = value["input_manifests"]
    if capability_value is not None and not isinstance(capability_value, Mapping):
        raise V002Error("Capability evidence must be an object or null")
    if entitlement_value is not None and not isinstance(entitlement_value, Mapping):
        raise V002Error("Entitlement evidence must be an object or null")
    if not isinstance(manifests_value, list):
        raise V002Error("Input manifests must be a list")
    manifests = []
    for item in manifests_value:
        if not isinstance(item, Mapping):
            raise V002Error("Input manifest evidence must be an object")
        manifest_values = dict(item)
        manifest_values["completeness_state"] = _state(
            manifest_values.get("completeness_state"),
            "completeness_state",
        )
        manifest_values["raw_sha256"] = tuple(manifest_values.get("raw_sha256", ()))
        manifest_values["normalized_sha256"] = tuple(
            manifest_values.get("normalized_sha256", ())
        )
        manifests.append(ImmutableInputManifest(**manifest_values))
    entitlement = None
    if entitlement_value is not None:
        entitlement_values = dict(entitlement_value)
        entitlement_values["status"] = _state(entitlement_values.get("status"), "status")
        entitlement = EntitlementEvidence(**entitlement_values)
    return RequirementReadinessEvidence(
        dataset=value["dataset"],
        required_capability=value["required_capability"],
        capability=None if capability_value is None else ProviderCapability(**capability_value),
        entitlement=entitlement,
        input_manifests=tuple(manifests),
        coverage_evidence_hashes=tuple(value["coverage_evidence_hashes"]),
        expected_security_set_hash=value["expected_security_set_hash"],
        observed_security_set_hash=value["observed_security_set_hash"],
        expected_session_set_hash=value["expected_session_set_hash"],
        observed_session_set_hash=value["observed_session_set_hash"],
        conflict_status=value["conflict_status"],
    )


def load_readiness_evidence_v002(path: Path) -> ReadinessEvidenceBundle:
    return ReadinessEvidenceBundle.from_mapping(_strict_json(path))


def validate_expected_coverage(
    expected_security_ids: Iterable[str],
    observed_security_ids: Iterable[str],
    expected_sessions: Iterable[str],
    observed_sessions: Iterable[str],
) -> None:
    expected_securities = tuple(sorted(set(expected_security_ids)))
    observed_securities = tuple(sorted(set(observed_security_ids)))
    expected_days = tuple(sorted(set(expected_sessions)))
    observed_days = tuple(sorted(set(observed_sessions)))
    if expected_securities != observed_securities:
        raise V002Error("Required securities cannot be silently dropped")
    if expected_days != observed_days:
        raise V002Error("Required sessions cannot be silently dropped")


def deterministic_unique_records(records: Sequence[ImmutableInputManifest]) -> tuple[ImmutableInputManifest, ...]:
    ordered = tuple(sorted(records, key=lambda item: (item.dataset, item.identity)))
    seen: dict[tuple[str, str], str] = {}
    result = []
    for record in ordered:
        key = (record.dataset, record.query_or_file_identity)
        if key in seen and seen[key] != record.identity:
            raise V002Error("Conflicting duplicate source records fail closed")
        if key not in seen:
            result.append(record)
            seen[key] = record.identity
    return tuple(result)


@dataclass(frozen=True)
class DiscoveryExperimentBinding:
    schema_version: str
    protocol_identity: str
    source_requirements_identity: str
    calendar_identity: str
    session_plan_identity: str
    universe_snapshot_identities: tuple[str, ...]
    security_master_identity: str
    symbol_lineage_identity: str
    corporate_actions_identity: str
    trades_manifest_identity: str
    quotes_manifest_identity: str
    bars_manifest_identity: str
    halts_manifest_identity: str
    catalysts_manifest_identity: str
    provider_capability_identities: tuple[str, ...]
    entitlement_identities: tuple[str, ...]
    parser_identities: tuple[str, ...]
    normalization_identities: tuple[str, ...]
    execution_phase: str

    def __post_init__(self) -> None:
        if self.schema_version != EXPERIMENT_BINDING_SCHEMA:
            raise V002Error("Experiment binding schema is not V002")
        if self.execution_phase != "discovery":
            raise V002Error("V002 experiment binding is discovery-only")
        scalar_hashes = (
            self.protocol_identity, self.source_requirements_identity,
            self.calendar_identity, self.session_plan_identity,
            self.security_master_identity, self.symbol_lineage_identity,
            self.corporate_actions_identity, self.trades_manifest_identity,
            self.quotes_manifest_identity, self.bars_manifest_identity,
            self.halts_manifest_identity, self.catalysts_manifest_identity,
        )
        for item in scalar_hashes:
            _hash(item, "experiment identity component")
        for field in (
            "universe_snapshot_identities", "provider_capability_identities",
            "entitlement_identities", "parser_identities", "normalization_identities",
        ):
            _sorted_unique_hashes(getattr(self, field), field)

    @property
    def identity(self) -> str:
        return canonical_hash(asdict(self))


def build_readiness_report(
    protocol: WinnerArchetypeProtocolV002,
    matrix: SourceRequirementsMatrix,
    evidence: ReadinessEvidenceBundle | None = None,
) -> dict[str, object]:
    """Build a deterministic pre-acquisition report without reading empirical inputs."""
    if evidence is not None:
        if evidence.protocol_identity != protocol.identity:
            raise V002Error("Readiness evidence does not bind the loaded protocol")
        if evidence.source_requirements_identity != matrix.identity:
            raise V002Error("Readiness evidence does not bind the loaded source matrix")
        expected_keys = {
            (item.dataset, item.required_capability) for item in matrix.requirements
        }
        observed_keys = {
            (item.dataset, item.required_capability) for item in evidence.requirements
        }
        if expected_keys != observed_keys:
            raise V002Error("Readiness evidence must cover every source requirement exactly once")
        evidence_by_key = {
            (item.dataset, item.required_capability): item
            for item in evidence.requirements
        }
    else:
        evidence_by_key = {}
    prerequisites = []
    categories: dict[str, int] = {
        "capability": 0,
        "entitlement": 0,
        "acquisition": 0,
        "coverage": 0,
        "completeness": 0,
        "conflict": 0,
    }
    for requirement in matrix.requirements:
        failures = []
        bound = evidence_by_key.get((requirement.dataset, requirement.required_capability))
        capability_missing = (
            bound.capability is None
            if bound is not None
            else requirement.provider_candidate == "unselected"
        )
        if capability_missing:
            failures.append("capability_unverified")
            categories["capability"] += 1
        entitlement_missing = (
            requirement.entitlement_status != "not_required"
            and (
                bound is None
                or bound.entitlement is None
            )
        ) if bound is not None else requirement.entitlement_status not in {"verified", "not_required"}
        if entitlement_missing:
            failures.append("entitlement_unverified")
            categories["entitlement"] += 1
        acquisition_missing = (
            not bound.input_manifests
            if bound is not None
            else requirement.readiness_state in {"unavailable", "not_acquired"}
        )
        if acquisition_missing:
            failures.append("not_acquired")
            categories["acquisition"] += 1
        if bound is not None:
            security_coverage_required = (
                requirement.security_coverage != "market_calendar_not_security_specific"
            )
            coverage_unproven = (
                not bound.coverage_evidence_hashes
                or (
                    security_coverage_required
                    and bound.expected_security_set_hash is None
                )
                or bound.expected_session_set_hash is None
                or (
                    security_coverage_required
                    and bound.expected_security_set_hash != bound.observed_security_set_hash
                )
                or bound.expected_session_set_hash != bound.observed_session_set_hash
            )
        else:
            coverage_unproven = requirement.readiness_state in {"coverage_unknown", "unavailable"}
        if coverage_unproven:
            failures.append("coverage_unproven")
            categories["coverage"] += 1
        if bound is not None:
            completeness_unproven = (
                not bound.input_manifests
                or any(
                    item.completeness_state
                    not in {CompletenessState.COMPLETE, CompletenessState.CORRECTED}
                    for item in bound.input_manifests
                )
                or coverage_unproven
            )
        else:
            completeness_unproven = requirement.readiness_state != "complete"
        if completeness_unproven:
            failures.append("completeness_unproven")
            categories["completeness"] += 1
        conflict_failure = None
        if bound is not None and bound.conflict_status == "unverified":
            conflict_failure = "conflict_unverified"
        elif (
            bound is not None and bound.conflict_status == "conflicting"
        ) or (bound is None and requirement.readiness_state == "conflicting"):
            conflict_failure = "source_conflict"
        if conflict_failure is not None:
            failures.append(conflict_failure)
            categories["conflict"] += 1
        prerequisites.append(
            {
                "dataset": requirement.dataset,
                "required_capability": requirement.required_capability,
                "ready": not failures,
                "failures": sorted(set(failures)),
                "blocking_reason": requirement.blocking_reason,
            }
        )
    payload = {
        "schema_version": READINESS_SCHEMA,
        "protocol_identity": protocol.identity,
        "source_requirements_identity": matrix.identity,
        "execution_phase": "discovery",
        "status": "blocked" if any(not item["ready"] for item in prerequisites) else "ready",
        "pilot_authorized": False,
        "empirical_data_opened": False,
        "eligible_event_count_calculated": False,
        "prerequisites": prerequisites,
        "unresolved_by_category": categories,
    }
    if evidence is not None:
        payload["readiness_evidence_identity"] = evidence.identity
    return {**payload, "readiness_identity": canonical_hash(payload)}
