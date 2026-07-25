"""Vendor-neutral, observational catalyst schemas with point-in-time semantics."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Mapping


RAW_SCHEMA_VERSION = "aml.catalyst.raw.v001"
CATALYST_SCHEMA_VERSION = "aml.catalyst.observation.v001"
CLUSTER_SCHEMA_VERSION = "aml.catalyst.cluster.v001"
SOURCE_SCHEMA_VERSION = "aml.catalyst.source.v001"
MANIFEST_SCHEMA_VERSION = "aml.catalyst.manifest.v001"
PARSER_AUDIT_SCHEMA_VERSION = "aml.catalyst.parser-audit.v001"
CATEGORIES = {
    "earnings", "guidance", "sec_filing", "analyst_action",
    "merger_or_acquisition", "financing", "regulatory_action", "legal_event",
    "product_announcement", "partnership", "management_change",
    "clinical_or_scientific_result", "contract_or_customer_win", "macroeconomic",
    "sector_wide", "rumor", "correction_or_retraction", "other",
}
DIRECTIONS = {"positive", "negative", "mixed", "neutral", "unknown"}
SOURCE_TYPES = {
    "news_vendor", "regulatory_filing", "investor_relations", "wire_service",
    "licensed_dataset", "other",
}
FORWARD_OUTCOME_FIELDS = {
    "pnl", "profit", "loss", "future_return", "trade_return", "exit_price",
    "win", "outcome", "target_hit", "stop_hit", "forward_maximum_return",
}
SECRET_TOKENS = {"api_key", "secret", "password", "authorization", "credential", "token"}
HASH = re.compile(r"^[0-9a-f]{64}$")


class CatalystSchemaError(ValueError):
    """Strict catalyst contract violation."""


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _exact(record: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(record) != fields:
        raise CatalystSchemaError(f"{label} contains missing or unknown fields")


def _text(value: object, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CatalystSchemaError(f"{field} must be a non-empty string")
    return value


def _time(value: object, field: str, *, nullable: bool = False) -> datetime | None:
    text = _text(value, field, nullable=nullable)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalystSchemaError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CatalystSchemaError(f"{field} must include a timezone")
    return parsed


def _score(value: object, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 5:
        raise CatalystSchemaError(f"{field} must be an integer from 0 through 5")
    return value


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise CatalystSchemaError(f"{field} must be a SHA-256 digest")
    return value


def _reject_sensitive_or_outcome_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in SECRET_TOKENS or normalized in FORWARD_OUTCOME_FIELDS:
                raise CatalystSchemaError("Credentials and forward outcomes are prohibited")
            _reject_sensitive_or_outcome_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_or_outcome_keys(nested)


RAW_FIELDS = {
    "schema_version", "vendor", "vendor_release", "source_record_id",
    "acquisition_timestamp", "payload", "raw_record_hash", "synthetic",
}


def validate_raw_record(record: Mapping[str, object]) -> None:
    _exact(record, RAW_FIELDS, "Raw record")
    if record["schema_version"] != RAW_SCHEMA_VERSION:
        raise CatalystSchemaError("Unsupported raw schema version")
    for field in ("vendor", "vendor_release", "source_record_id"):
        _text(record[field], field)
    _time(record["acquisition_timestamp"], "acquisition_timestamp")
    if record["synthetic"] is not True:
        raise CatalystSchemaError("Repository collector fixtures must be explicitly synthetic")
    payload = record["payload"]
    if not isinstance(payload, dict):
        raise CatalystSchemaError("Raw payload must be an object")
    _reject_sensitive_or_outcome_keys(payload)
    if _hash(record["raw_record_hash"], "raw_record_hash") != sha256(payload):
        raise CatalystSchemaError("Raw record hash does not match canonical payload")


OBSERVATION_FIELDS = {
    "schema_version", "observation_id", "symbol", "security_identifier",
    "publication_timestamp", "first_seen_timestamp", "effective_event_timestamp",
    "source_name", "source_type", "source_locator", "headline", "normalized_summary",
    "catalyst_category", "direction", "novelty", "materiality", "company_specificity",
    "source_credibility", "is_primary_source", "duplicate_story_cluster_id", "language",
    "acquisition_timestamp", "vendor_release", "raw_record_hash", "parser_version",
    "synthetic",
}
OBSERVATION_IDENTITY_FIELDS = OBSERVATION_FIELDS - {"observation_id"}


def observation_id(record: Mapping[str, object]) -> str:
    return sha256({field: record[field] for field in sorted(OBSERVATION_IDENTITY_FIELDS)})


def validate_observation(record: Mapping[str, object]) -> None:
    _exact(record, OBSERVATION_FIELDS, "Catalyst observation")
    if record["schema_version"] != CATALYST_SCHEMA_VERSION:
        raise CatalystSchemaError("Unsupported catalyst schema version")
    symbol = _text(record["symbol"], "symbol")
    if symbol != symbol.upper() or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
        raise CatalystSchemaError("symbol is not normalized")
    _text(record["security_identifier"], "security_identifier", nullable=True)
    publication = _time(record["publication_timestamp"], "publication_timestamp")
    first_seen = _time(record["first_seen_timestamp"], "first_seen_timestamp")
    _time(record["effective_event_timestamp"], "effective_event_timestamp", nullable=True)
    acquisition = _time(record["acquisition_timestamp"], "acquisition_timestamp")
    if first_seen < publication or acquisition < first_seen:
        raise CatalystSchemaError("Timestamp ordering violates point-in-time semantics")
    for field in (
        "source_name", "source_locator", "headline", "normalized_summary", "language",
        "vendor_release", "parser_version", "duplicate_story_cluster_id",
    ):
        _text(record[field], field)
    if record["source_type"] not in SOURCE_TYPES:
        raise CatalystSchemaError("source_type is unsupported")
    if record["catalyst_category"] not in CATEGORIES:
        raise CatalystSchemaError("catalyst_category is unsupported")
    if record["direction"] not in DIRECTIONS:
        raise CatalystSchemaError("direction is unsupported")
    for field in ("novelty", "materiality", "company_specificity", "source_credibility"):
        _score(record[field], field)
    if type(record["is_primary_source"]) is not bool or record["synthetic"] is not True:
        raise CatalystSchemaError("Boolean provenance fields are malformed")
    _hash(record["raw_record_hash"], "raw_record_hash")
    _hash(record["duplicate_story_cluster_id"], "duplicate_story_cluster_id")
    if _hash(record["observation_id"], "observation_id") != observation_id(record):
        raise CatalystSchemaError("Observation identity does not match canonical content")
    _reject_sensitive_or_outcome_keys(record)


CLUSTER_FIELDS = {
    "schema_version", "cluster_id", "member_observation_ids", "cluster_basis",
    "created_at", "parser_version", "synthetic",
}


def cluster_id(record: Mapping[str, object]) -> str:
    payload = {key: record[key] for key in sorted(CLUSTER_FIELDS - {"cluster_id"})}
    return sha256(payload)


def validate_cluster(record: Mapping[str, object]) -> None:
    _exact(record, CLUSTER_FIELDS, "Duplicate cluster")
    if record["schema_version"] != CLUSTER_SCHEMA_VERSION or record["synthetic"] is not True:
        raise CatalystSchemaError("Cluster schema or provenance is invalid")
    members = record["member_observation_ids"]
    if not isinstance(members, list) or not members or members != sorted(set(members)):
        raise CatalystSchemaError("Cluster members must be a sorted unique list")
    for member in members:
        _hash(member, "member_observation_id")
    _text(record["cluster_basis"], "cluster_basis")
    _time(record["created_at"], "created_at")
    _text(record["parser_version"], "parser_version")
    if _hash(record["cluster_id"], "cluster_id") != cluster_id(record):
        raise CatalystSchemaError("Cluster identity does not match canonical content")


SOURCE_FIELDS = {
    "schema_version", "source_id", "source_name", "source_type", "license_name",
    "license_url", "redistribution_permitted", "retention_policy", "terms_reviewed_at",
    "metadata_version", "synthetic",
}


def validate_source_metadata(record: Mapping[str, object]) -> None:
    _exact(record, SOURCE_FIELDS, "Source metadata")
    if record["schema_version"] != SOURCE_SCHEMA_VERSION or record["synthetic"] is not True:
        raise CatalystSchemaError("Source schema or provenance is invalid")
    for field in (
        "source_id", "source_name", "license_name", "license_url", "retention_policy",
        "metadata_version",
    ):
        _text(record[field], field)
    if record["source_type"] not in SOURCE_TYPES:
        raise CatalystSchemaError("Source type is unsupported")
    if type(record["redistribution_permitted"]) is not bool:
        raise CatalystSchemaError("redistribution_permitted must be boolean")
    _time(record["terms_reviewed_at"], "terms_reviewed_at")


MANIFEST_FIELDS = {
    "schema_version", "manifest_id", "vendor", "vendor_release", "parser_version",
    "acquisition_started_at", "acquisition_finished_at", "raw_record_hashes",
    "record_count", "synthetic",
}


def manifest_id(record: Mapping[str, object]) -> str:
    return sha256({key: record[key] for key in sorted(MANIFEST_FIELDS - {"manifest_id"})})


def validate_manifest(record: Mapping[str, object]) -> None:
    _exact(record, MANIFEST_FIELDS, "Acquisition manifest")
    if record["schema_version"] != MANIFEST_SCHEMA_VERSION or record["synthetic"] is not True:
        raise CatalystSchemaError("Manifest schema or provenance is invalid")
    for field in ("vendor", "vendor_release", "parser_version"):
        _text(record[field], field)
    if _hash(record["manifest_id"], "manifest_id") != manifest_id(record):
        raise CatalystSchemaError("Manifest identity does not match canonical content")
    started = _time(record["acquisition_started_at"], "acquisition_started_at")
    finished = _time(record["acquisition_finished_at"], "acquisition_finished_at")
    if finished < started:
        raise CatalystSchemaError("Manifest timestamps are reversed")
    hashes = record["raw_record_hashes"]
    if not isinstance(hashes, list) or hashes != sorted(set(hashes)):
        raise CatalystSchemaError("Manifest hashes must be sorted and unique")
    for value in hashes:
        _hash(value, "raw_record_hash")
    if type(record["record_count"]) is not int or record["record_count"] != len(hashes):
        raise CatalystSchemaError("Manifest count does not reconcile")


AUDIT_FIELDS = {
    "schema_version", "audit_id", "raw_record_hash", "observation_id",
    "parser_version", "parsed_at", "status", "warning_codes", "synthetic",
}


def parser_audit_id(record: Mapping[str, object]) -> str:
    return sha256({key: record[key] for key in sorted(AUDIT_FIELDS - {"audit_id"})})


def validate_parser_audit(record: Mapping[str, object]) -> None:
    _exact(record, AUDIT_FIELDS, "Parser audit")
    if record["schema_version"] != PARSER_AUDIT_SCHEMA_VERSION or record["synthetic"] is not True:
        raise CatalystSchemaError("Parser audit schema or provenance is invalid")
    _text(record["parser_version"], "parser_version")
    if _hash(record["audit_id"], "audit_id") != parser_audit_id(record):
        raise CatalystSchemaError("Parser audit identity does not match canonical content")
    _hash(record["raw_record_hash"], "raw_record_hash")
    _hash(record["observation_id"], "observation_id")
    _time(record["parsed_at"], "parsed_at")
    if record["status"] not in {"normalized", "rejected"}:
        raise CatalystSchemaError("Parser audit status is invalid")
    warnings = record["warning_codes"]
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        raise CatalystSchemaError("warning_codes must be a string list")
