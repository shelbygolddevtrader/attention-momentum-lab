"""Deterministic, research-only historical catalyst ingestion."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Callable, Mapping, Protocol, Sequence
import unicodedata

from aml.catalyst_observations import CATEGORIES, DIRECTIONS, SOURCE_TYPES, canonical_json
from aml.catalyst_storage import read_canonical, validate_storage_root, write_once
from aml.historical_catalyst_providers import (
    HistoricalCatalystProvider, HistoricalProviderError, HistoricalSourceRecord,
    InputLimits,
)


RAW_SCHEMA_VERSION = "aml.catalyst.raw.v002"
OBSERVATION_SCHEMA_VERSION = "aml.catalyst.observation.v002"
CLUSTER_SCHEMA_VERSION = "aml.catalyst.cluster.v002"
SOURCE_BATCH_SCHEMA_VERSION = "aml.catalyst.source-batch.v001"
AUDIT_SCHEMA_VERSION = "aml.catalyst.ingestion-audit.v001"
MANIFEST_SCHEMA_VERSION = "aml.catalyst.ingestion-manifest.v001"
SUPPORTED_NORMALIZER_VERSION = "historical-synthetic-normalizer-v001"
SUPPORTED_DEDUPLICATOR_VERSION = "exact-observational-content-v001"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PROTECTED_PATH_TOKENS = {
    "holdout", "sealed", "forward-validation", "validation-extension",
}
MAX_STORED_ARTIFACT_BYTES = 32_000_000
PROHIBITED_KEYS = {
    "pnl", "profit", "loss", "future_return", "trade_return", "exit_price",
    "win", "outcome", "target_hit", "stop_hit", "forward_maximum_return",
    "api_key", "secret", "password", "authorization", "credential", "token",
}
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|password|authorization|access[_-]?token)\s*[=:]"
)
PAYLOAD_FIELDS = {
    "symbol", "security_identifier", "publication_timestamp",
    "first_seen_timestamp", "effective_event_timestamp",
    "effective_event_timestamp_origin", "source_name", "source_type",
    "source_locator", "headline", "normalized_summary", "catalyst_category",
    "direction", "novelty", "materiality", "company_specificity",
    "source_credibility", "is_primary_source", "language",
}


class HistoricalIngestionError(ValueError):
    """A historical ingestion integrity boundary failed closed."""


class HistoricalNormalizer(Protocol):
    @property
    def version(self) -> str: ...

    def normalize(self, raw: Mapping[str, object], as_of: str) -> Mapping[str, object]: ...


class CatalystDeduplicator(Protocol):
    @property
    def version(self) -> str: ...

    def cluster_key(self, observation: Mapping[str, object]) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class PlannedArtifact:
    kind: str
    identity: str
    relative_path: Path
    record: Mapping[str, object]
    content_hash: str


@dataclass(frozen=True)
class IngestionPlan:
    run_id: str
    provider: str
    provider_version: str
    normalizer_version: str
    deduplicator_version: str
    as_of: str
    limits: InputLimits
    artifacts: tuple[PlannedArtifact, ...]
    manifest: Mapping[str, object]
    manifest_path: Path

    def summary(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for artifact in self.artifacts:
            counts[artifact.kind] = counts.get(artifact.kind, 0) + 1
        return {
            "run_id": self.run_id,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "normalizer_version": self.normalizer_version,
            "deduplicator_version": self.deduplicator_version,
            "as_of": self.as_of,
            "limits": self.limits.as_dict(),
            "artifact_counts": dict(sorted(counts.items())),
            "artifacts": [
                {
                    "kind": artifact.kind,
                    "identity": artifact.identity,
                    "relative_path": artifact.relative_path.as_posix(),
                    "content_hash": artifact.content_hash,
                }
                for artifact in self.artifacts
            ],
            "manifest_path": self.manifest_path.as_posix(),
            "manifest": self.manifest,
        }


def _digest(value: object) -> str:
    try:
        return hashlib.sha256(canonical_json(value)).hexdigest()
    except (ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise HistoricalIngestionError("Value is not canonical finite JSON") from exc


def _timestamp(value: object, field: str) -> datetime:
    _text(value, field)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistoricalIngestionError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalIngestionError(f"{field} must include a timezone")
    return parsed


def _text(value: object, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise HistoricalIngestionError(f"{field} must be a non-empty string")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise HistoricalIngestionError(f"{field} contains control or malformed Unicode")
    return value


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise HistoricalIngestionError(f"{field} must be a SHA-256 digest")
    return value


def _safe_component(value: object, field: str) -> str:
    text = _text(value, field)
    if not SAFE_COMPONENT.fullmatch(text):
        raise HistoricalIngestionError(f"{field} is not a safe partition identifier")
    return text


def _validate_existing_artifact_path(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise HistoricalIngestionError("Artifact path escapes the registry root") from exc
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir() or current.resolve() != current:
            raise HistoricalIngestionError("Artifact path contains an unsafe directory")
        info = current.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise HistoricalIngestionError("Artifact directory permissions are unsafe")
    if path.is_symlink() or not path.is_file():
        raise HistoricalIngestionError("Artifact is not a regular non-symlink file")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise HistoricalIngestionError("Artifact file permissions are unsafe")
    if info.st_nlink != 1:
        raise HistoricalIngestionError("Artifact cannot be hard-linked")
    if info.st_size < 1 or info.st_size > MAX_STORED_ARTIFACT_BYTES:
        raise HistoricalIngestionError("Artifact size violates the safety boundary")


def _reject_prohibited(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            collapsed = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if any(collapsed == re.sub(r"[^a-z0-9]", "", item) for item in PROHIBITED_KEYS):
                raise HistoricalIngestionError("Credentials and forward outcomes are prohibited")
            _reject_prohibited(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_prohibited(nested)
    elif isinstance(value, str) and SECRET_VALUE_PATTERN.search(value):
        raise HistoricalIngestionError("Secret-like values are prohibited")
    elif isinstance(value, float) and not (-float("inf") < value < float("inf")):
        raise HistoricalIngestionError("Non-finite numbers are prohibited")


def _exact(record: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(record) != fields:
        raise HistoricalIngestionError(f"{label} contains missing or unknown fields")


RAW_FIELDS = {
    "schema_version", "raw_id", "provider", "provider_version",
    "provider_release", "source_identifier", "retrieval_timestamp",
    "source_label", "source_format", "source_file_byte_length",
    "source_file_hash", "source_record_index", "source_record_byte_envelope",
    "source_record_byte_length", "source_record_byte_hash",
    "source_record_bytes_base64", "logical_payload", "logical_payload_hash",
    "normalization_version", "validation_status", "revision_of_raw_id",
    "lineage_status", "synthetic",
}


def raw_identity(record: Mapping[str, object]) -> str:
    identity = {
        "schema_version": record["schema_version"],
        "provider": record["provider"],
        "provider_version": record["provider_version"],
        "provider_release": record["provider_release"],
        "source_identifier": record["source_identifier"],
        "retrieval_timestamp": record["retrieval_timestamp"],
        "source_file_hash": record["source_file_hash"],
        "source_record_index": record["source_record_index"],
        "source_record_byte_hash": record["source_record_byte_hash"],
        "logical_payload_hash": record["logical_payload_hash"],
        "normalization_version": record["normalization_version"],
        "revision_of_raw_id": record["revision_of_raw_id"],
    }
    return _digest(identity)


def validate_raw_v2(record: Mapping[str, object]) -> None:
    _exact(record, RAW_FIELDS, "Historical raw record")
    if record["schema_version"] != RAW_SCHEMA_VERSION:
        raise HistoricalIngestionError("Historical raw schema is unsupported")
    for field in (
        "provider", "provider_version", "provider_release", "source_identifier",
        "source_label", "source_format", "normalization_version",
    ):
        _text(record[field], field)
    _safe_component(record["provider"], "provider")
    _safe_component(record["provider_version"], "provider_version")
    _timestamp(record["retrieval_timestamp"], "retrieval_timestamp")
    if type(record["source_file_byte_length"]) is not int or record["source_file_byte_length"] < 1:
        raise HistoricalIngestionError("source_file_byte_length is invalid")
    if type(record["source_record_index"]) is not int or record["source_record_index"] < 0:
        raise HistoricalIngestionError("source_record_index is invalid")
    _hash(record["source_file_hash"], "source_file_hash")
    if record["source_record_byte_envelope"] == "exact":
        if type(record["source_record_byte_length"]) is not int:
            raise HistoricalIngestionError("Exact source bytes require a byte length")
        _hash(record["source_record_byte_hash"], "source_record_byte_hash")
        encoded = _text(record["source_record_bytes_base64"], "source_record_bytes_base64")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise HistoricalIngestionError("Exact source-byte envelope is malformed") from exc
        if len(decoded) != record["source_record_byte_length"]:
            raise HistoricalIngestionError("Exact source-byte length does not reconcile")
        if hashlib.sha256(decoded).hexdigest() != record["source_record_byte_hash"]:
            raise HistoricalIngestionError("Exact source-byte hash does not reconcile")
    elif record["source_record_byte_envelope"] == "source-file-only":
        if any(record[field] is not None for field in (
            "source_record_byte_length", "source_record_byte_hash",
            "source_record_bytes_base64",
        )):
            raise HistoricalIngestionError("JSON-array records cannot claim exact byte envelopes")
    else:
        raise HistoricalIngestionError("source_record_byte_envelope is unsupported")
    if not isinstance(record["logical_payload"], dict):
        raise HistoricalIngestionError("logical_payload must be an object")
    if _hash(record["logical_payload_hash"], "logical_payload_hash") != _digest(record["logical_payload"]):
        raise HistoricalIngestionError("Logical-payload hash does not reconcile")
    if record["validation_status"] != "validated" or record["synthetic"] is not True:
        raise HistoricalIngestionError("Raw validation or synthetic provenance is invalid")
    revision = record["revision_of_raw_id"]
    if revision is not None:
        _hash(revision, "revision_of_raw_id")
    expected_lineage = "revision" if revision else "original"
    if record["lineage_status"] != expected_lineage:
        raise HistoricalIngestionError("Raw lineage status is inconsistent")
    if _hash(record["raw_id"], "raw_id") != raw_identity(record):
        raise HistoricalIngestionError("Raw identity does not match canonical provenance")
    _reject_prohibited(record)


OBSERVATION_FIELDS = {
    "schema_version", "observation_id", "normalized_record_hash", "raw_id",
    "provider", "retrieval_timestamp", "source_identifier",
    "normalization_version", "validation_status", "revision_of_observation_id",
    "symbol", "security_identifier", "publication_timestamp",
    "first_seen_timestamp", "effective_event_timestamp",
    "effective_event_timestamp_origin", "source_name", "source_type",
    "source_locator", "headline", "normalized_summary", "catalyst_category",
    "direction", "novelty", "materiality", "company_specificity",
    "source_credibility", "is_primary_source", "language",
    "duplicate_story_cluster_id", "synthetic",
}


def observation_identity(record: Mapping[str, object]) -> str:
    return _digest({
        "raw_id": record["raw_id"],
        "normalization_version": record["normalization_version"],
        "symbol": record["symbol"],
    })


def normalized_hash(record: Mapping[str, object]) -> str:
    return _digest({key: record[key] for key in sorted(OBSERVATION_FIELDS - {"normalized_record_hash"})})


def validate_observation_v2(record: Mapping[str, object], *, as_of: str | None = None) -> None:
    _exact(record, OBSERVATION_FIELDS, "Historical observation")
    if record["schema_version"] != OBSERVATION_SCHEMA_VERSION:
        raise HistoricalIngestionError("Historical observation schema is unsupported")
    for field in (
        "provider", "source_identifier", "normalization_version", "headline",
        "normalized_summary", "source_name", "source_locator", "language",
    ):
        _text(record[field], field)
    symbol = _text(record["symbol"], "symbol")
    if symbol != symbol.upper() or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
        raise HistoricalIngestionError("Observation symbol is not normalized")
    _text(record["security_identifier"], "security_identifier")
    retrieval = _timestamp(record["retrieval_timestamp"], "retrieval_timestamp")
    publication = _timestamp(record["publication_timestamp"], "publication_timestamp")
    first_seen = _timestamp(record["first_seen_timestamp"], "first_seen_timestamp")
    effective = record["effective_event_timestamp"]
    if effective is not None:
        _timestamp(effective, "effective_event_timestamp")
    if record["effective_event_timestamp_origin"] not in {
        "provider-reported", "source-derived", "unknown",
    }:
        raise HistoricalIngestionError("Effective-event timestamp origin is invalid")
    if (effective is None) != (record["effective_event_timestamp_origin"] == "unknown"):
        raise HistoricalIngestionError("Effective-event timestamp and origin are inconsistent")
    if publication > retrieval or first_seen < publication or first_seen > retrieval:
        raise HistoricalIngestionError("Observation timestamps violate point-in-time ordering")
    if as_of is not None and retrieval > _timestamp(as_of, "as_of"):
        raise HistoricalIngestionError("Retrieval timestamp exceeds as_of")
    if record["source_type"] not in SOURCE_TYPES:
        raise HistoricalIngestionError("Observation source type is unsupported")
    if record["catalyst_category"] not in CATEGORIES or record["direction"] not in DIRECTIONS:
        raise HistoricalIngestionError("Observation category or direction is unsupported")
    for field in ("novelty", "materiality", "company_specificity", "source_credibility"):
        value = record[field]
        if type(value) is not int or not 0 <= value <= 5:
            raise HistoricalIngestionError(f"{field} must be an integer from 0 through 5")
    if type(record["is_primary_source"]) is not bool or record["synthetic"] is not True:
        raise HistoricalIngestionError("Observation boolean provenance is invalid")
    if record["validation_status"] != "validated":
        raise HistoricalIngestionError("Observation validation status is invalid")
    _hash(record["raw_id"], "raw_id")
    revision = record["revision_of_observation_id"]
    if revision is not None:
        _hash(revision, "revision_of_observation_id")
    cluster = record["duplicate_story_cluster_id"]
    if cluster is not None:
        _hash(cluster, "duplicate_story_cluster_id")
    if _hash(record["observation_id"], "observation_id") != observation_identity(record):
        raise HistoricalIngestionError("Observation identity does not reconcile")
    if _hash(record["normalized_record_hash"], "normalized_record_hash") != normalized_hash(record):
        raise HistoricalIngestionError("Normalized observation hash does not reconcile")
    _reject_prohibited(record)


@dataclass(frozen=True)
class StrictSyntheticHistoricalNormalizer:
    version: str = SUPPORTED_NORMALIZER_VERSION

    def normalize(self, raw: Mapping[str, object], as_of: str) -> dict[str, object]:
        validate_raw_v2(raw)
        payload = raw["logical_payload"]
        if set(payload) != PAYLOAD_FIELDS:
            raise HistoricalIngestionError("Normalizer payload contains missing or unknown fields")
        record = {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "observation_id": "pending",
            "normalized_record_hash": "pending",
            "raw_id": raw["raw_id"],
            "provider": raw["provider"],
            "retrieval_timestamp": raw["retrieval_timestamp"],
            "source_identifier": raw["source_identifier"],
            "normalization_version": self.version,
            "validation_status": "validated",
            "revision_of_observation_id": None,
            **payload,
            "duplicate_story_cluster_id": None,
            "synthetic": True,
        }
        record["observation_id"] = observation_identity(record)
        record["normalized_record_hash"] = normalized_hash(record)
        validate_observation_v2(record, as_of=as_of)
        return record


@dataclass(frozen=True)
class ExactObservationalContentDeduplicator:
    version: str = SUPPORTED_DEDUPLICATOR_VERSION

    def cluster_key(self, observation: Mapping[str, object]) -> tuple[str, ...]:
        event_timestamp = observation["effective_event_timestamp"] or observation["publication_timestamp"]
        event_date = _timestamp(event_timestamp, "cluster event timestamp").date().isoformat()
        return (
            str(observation["security_identifier"]),
            event_date,
            str(observation["headline"]),
            str(observation["normalized_summary"]),
        )


CLUSTER_FIELDS = {
    "schema_version", "cluster_id", "security_identifier", "event_date",
    "member_observation_ids", "member_providers", "source_identifiers",
    "retrieval_timestamps", "deduplicator_version", "normalization_versions", "validation_status",
    "cluster_basis", "synthetic",
}


def cluster_identity(record: Mapping[str, object]) -> str:
    return _digest({key: record[key] for key in sorted(CLUSTER_FIELDS - {"cluster_id"})})


def validate_cluster_v2(record: Mapping[str, object]) -> None:
    _exact(record, CLUSTER_FIELDS, "Historical duplicate cluster")
    if record["schema_version"] != CLUSTER_SCHEMA_VERSION or record["synthetic"] is not True:
        raise HistoricalIngestionError("Historical cluster schema or provenance is invalid")
    _text(record["security_identifier"], "security_identifier")
    try:
        date.fromisoformat(str(record["event_date"]))
    except ValueError as exc:
        raise HistoricalIngestionError("Cluster event date is malformed") from exc
    for field in (
        "member_observation_ids", "member_providers", "source_identifiers",
        "retrieval_timestamps", "normalization_versions",
    ):
        values = record[field]
        if not isinstance(values, list) or not values or values != sorted(set(values)):
            raise HistoricalIngestionError(f"{field} must be a sorted unique list")
    for member in record["member_observation_ids"]:
        _hash(member, "member_observation_id")
    for timestamp in record["retrieval_timestamps"]:
        _timestamp(timestamp, "cluster retrieval timestamp")
    _text(record["deduplicator_version"], "deduplicator_version")
    _text(record["cluster_basis"], "cluster_basis")
    if record["validation_status"] != "validated":
        raise HistoricalIngestionError("Cluster validation status is invalid")
    if _hash(record["cluster_id"], "cluster_id") != cluster_identity(record):
        raise HistoricalIngestionError("Cluster identity does not reconcile")
    _reject_prohibited(record)


def _source_record(source: HistoricalSourceRecord, provider: str, provider_version: str) -> dict[str, object]:
    logical = source.logical_record
    payload = logical["payload"]
    record = {
        "schema_version": RAW_SCHEMA_VERSION,
        "raw_id": "pending",
        "provider": provider,
        "provider_version": provider_version,
        "provider_release": logical["provider_release"],
        "source_identifier": logical["source_identifier"],
        "retrieval_timestamp": logical["retrieval_timestamp"],
        "source_label": source.source_label,
        "source_format": source.source_format,
        "source_file_byte_length": source.source_file_byte_length,
        "source_file_hash": source.source_file_hash,
        "source_record_index": source.source_record_index,
        "source_record_byte_envelope": (
            "exact" if source.source_record_bytes is not None else "source-file-only"
        ),
        "source_record_byte_length": source.source_record_byte_length,
        "source_record_byte_hash": source.source_record_byte_hash,
        "source_record_bytes_base64": (
            base64.b64encode(source.source_record_bytes).decode("ascii")
            if source.source_record_bytes is not None else None
        ),
        "logical_payload": payload,
        "logical_payload_hash": _digest(payload),
        "normalization_version": "pending",
        "validation_status": "validated",
        "revision_of_raw_id": logical["revision_of_raw_id"],
        "lineage_status": "revision" if logical["revision_of_raw_id"] else "original",
        "synthetic": True,
    }
    return record


def _validate_configuration(
    provider: HistoricalCatalystProvider,
    normalizer: HistoricalNormalizer,
    deduplicator: CatalystDeduplicator,
    as_of: str,
) -> datetime:
    _safe_component(provider.provider, "provider")
    _safe_component(provider.provider_version, "provider_version")
    _safe_component(normalizer.version, "normalizer_version")
    _safe_component(deduplicator.version, "deduplicator_version")
    if normalizer.version != SUPPORTED_NORMALIZER_VERSION:
        raise HistoricalIngestionError("Normalizer version is unsupported")
    if deduplicator.version != SUPPORTED_DEDUPLICATOR_VERSION:
        raise HistoricalIngestionError("Deduplicator version is unsupported")
    return _timestamp(as_of, "as_of")


def _published_records(root: Path) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    raws: dict[str, dict[str, object]] = {}
    observations: dict[str, str] = {}
    ingestion_root = root / "ingestions"
    if not ingestion_root.exists():
        return raws, observations
    if ingestion_root.is_symlink():
        raise HistoricalIngestionError("Ingestion registry cannot be a symlink")
    for manifest_path in sorted(ingestion_root.glob("*/manifest.json")):
        _validate_existing_artifact_path(root, manifest_path)
        manifest = read_canonical(manifest_path)
        validate_manifest(manifest)
        for artifact in manifest["artifacts"]:
            path = root / artifact["relative_path"]
            _validate_existing_artifact_path(root, path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["content_hash"]:
                raise HistoricalIngestionError("Published artifact differs from its manifest")
            if artifact["kind"] == "raw":
                raw = read_canonical(path)
                validate_raw_v2(raw)
                if str(raw["raw_id"]) in raws:
                    raise HistoricalIngestionError("Published registry contains duplicate raw identity")
                raws[str(raw["raw_id"])] = raw
            elif artifact["kind"] == "observation":
                observation = read_canonical(path)
                validate_observation_v2(observation)
                if str(observation["raw_id"]) in observations:
                    raise HistoricalIngestionError(
                        "Published registry contains duplicate observation lineage"
                    )
                observations[str(observation["raw_id"])] = str(observation["observation_id"])
    return raws, observations


def _validate_lineage(new_records: Sequence[dict[str, object]], existing: Mapping[str, dict[str, object]]) -> None:
    all_records = {**existing, **{str(record["raw_id"]): record for record in new_records}}
    if len(all_records) != len(existing) + len(new_records):
        raise HistoricalIngestionError("Duplicate immutable raw identifier")
    logical_keys: set[tuple[str, str, str]] = set()
    children: dict[str, list[str]] = {}
    for raw_id, record in all_records.items():
        key = (str(record["provider"]), str(record["source_identifier"]), str(record["logical_payload_hash"]))
        if key in logical_keys:
            raise HistoricalIngestionError("Duplicate logical payload for stable provider source identifier")
        logical_keys.add(key)
        parent = record["revision_of_raw_id"]
        if parent is not None:
            children.setdefault(str(parent), []).append(raw_id)
    for start in all_records:
        seen: set[str] = set()
        current: str | None = start
        while current is not None:
            if current in seen:
                raise HistoricalIngestionError("Correction lineage contains a cycle")
            seen.add(current)
            if current not in all_records:
                break
            parent = all_records[current]["revision_of_raw_id"]
            current = str(parent) if parent is not None else None
    for record in new_records:
        raw_id = str(record["raw_id"])
        parent_id = record["revision_of_raw_id"]
        same_source = [
            item for other_id, item in all_records.items()
            if other_id != raw_id
            and item["provider"] == record["provider"]
            and item["source_identifier"] == record["source_identifier"]
        ]
        if parent_id is None:
            roots = [
                item for item in [record, *same_source]
                if item["revision_of_raw_id"] is None
            ]
            if len(roots) != 1 or roots[0]["raw_id"] != raw_id:
                raise HistoricalIngestionError("Correction predecessor is unresolved or ambiguous")
            continue
        if parent_id not in all_records:
            raise HistoricalIngestionError("Correction predecessor does not exist")
        parent = all_records[str(parent_id)]
        if parent["provider"] != record["provider"] or parent["source_identifier"] != record["source_identifier"]:
            raise HistoricalIngestionError("Correction predecessor provenance differs")
        if parent["logical_payload_hash"] == record["logical_payload_hash"]:
            raise HistoricalIngestionError("Correction payload identity must differ")
        if _timestamp(parent["retrieval_timestamp"], "predecessor retrieval") >= _timestamp(record["retrieval_timestamp"], "retrieval"):
            raise HistoricalIngestionError("Correction cannot precede or equal its predecessor")
        if len(children.get(str(parent_id), [])) != 1:
            raise HistoricalIngestionError("Correction predecessor has ambiguous competing revisions")


def _apply_revision_observations(
    observations: list[dict[str, object]],
    raws: Sequence[dict[str, object]],
    existing_observations: Mapping[str, str],
) -> None:
    raw_to_observation = {
        str(raw["raw_id"]): str(observation["observation_id"])
        for raw, observation in zip(raws, observations, strict=True)
    }
    raw_to_observation.update(existing_observations)
    for raw, observation in zip(raws, observations, strict=True):
        predecessor = raw["revision_of_raw_id"]
        if predecessor is not None:
            if str(predecessor) not in raw_to_observation:
                raise HistoricalIngestionError("Correction predecessor lacks a published observation")
            observation["revision_of_observation_id"] = raw_to_observation[str(predecessor)]
            observation["normalized_record_hash"] = normalized_hash(observation)


def _clusters(
    observations: list[dict[str, object]], deduplicator: CatalystDeduplicator,
) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, object]]] = {}
    for observation in observations:
        groups.setdefault(deduplicator.cluster_key(observation), []).append(observation)
    clusters: list[dict[str, object]] = []
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        security_identifier, event_date, _, _ = key
        record = {
            "schema_version": CLUSTER_SCHEMA_VERSION,
            "cluster_id": "pending",
            "security_identifier": security_identifier,
            "event_date": event_date,
            "member_observation_ids": sorted(str(item["observation_id"]) for item in members),
            "member_providers": sorted({str(item["provider"]) for item in members}),
            "source_identifiers": sorted({str(item["source_identifier"]) for item in members}),
            "retrieval_timestamps": sorted({str(item["retrieval_timestamp"]) for item in members}),
            "deduplicator_version": deduplicator.version,
            "normalization_versions": sorted({str(item["normalization_version"]) for item in members}),
            "validation_status": "validated",
            "cluster_basis": "Exact security, event date, headline, and normalized summary",
            "synthetic": True,
        }
        record["cluster_id"] = cluster_identity(record)
        validate_cluster_v2(record)
        for member in members:
            member["duplicate_story_cluster_id"] = record["cluster_id"]
            member["normalized_record_hash"] = normalized_hash(member)
        clusters.append(record)
    return clusters


def _source_batches(
    sources: Sequence[HistoricalSourceRecord], provider: str, provider_version: str,
    normalization_version: str,
) -> list[dict[str, object]]:
    grouped: dict[str, list[HistoricalSourceRecord]] = {}
    for source in sources:
        grouped.setdefault(source.source_label, []).append(source)
    result = []
    for label, members in sorted(grouped.items()):
        source_ids = sorted({str(item.logical_record["source_identifier"]) for item in members})
        record = {
            "schema_version": SOURCE_BATCH_SCHEMA_VERSION,
            "source_batch_id": "pending",
            "provider": provider,
            "provider_version": provider_version,
            "source_label": label,
            "source_format": members[0].source_format,
            "source_file_byte_length": members[0].source_file_byte_length,
            "source_file_hash": members[0].source_file_hash,
            "source_identifiers": source_ids,
            "retrieval_timestamps": sorted({
                str(item.logical_record["retrieval_timestamp"]) for item in members
            }),
            "normalization_version": normalization_version,
            "record_count": len(members),
            "validation_status": "validated",
            "json_array_byte_envelope_limitation": members[0].source_format == "json-array",
            "synthetic": True,
        }
        record["source_batch_id"] = _digest({key: record[key] for key in sorted(record) if key != "source_batch_id"})
        validate_source_batch(record)
        result.append(record)
    return result


SOURCE_BATCH_FIELDS = {
    "schema_version", "source_batch_id", "provider", "provider_version",
    "source_label", "source_format", "source_file_byte_length",
    "source_file_hash", "source_identifiers", "record_count",
    "retrieval_timestamps", "normalization_version", "validation_status",
    "json_array_byte_envelope_limitation", "synthetic",
}


def validate_source_batch(record: Mapping[str, object]) -> None:
    _exact(record, SOURCE_BATCH_FIELDS, "Historical source batch")
    if record["schema_version"] != SOURCE_BATCH_SCHEMA_VERSION or record["synthetic"] is not True:
        raise HistoricalIngestionError("Source-batch schema or provenance is invalid")
    for field in ("provider", "provider_version", "source_label", "source_format"):
        _text(record[field], field)
    _hash(record["source_file_hash"], "source_file_hash")
    if type(record["source_file_byte_length"]) is not int or record["source_file_byte_length"] < 1:
        raise HistoricalIngestionError("Source-batch byte length is invalid")
    identifiers = record["source_identifiers"]
    if not isinstance(identifiers, list) or not identifiers or identifiers != sorted(set(identifiers)):
        raise HistoricalIngestionError("Source identifiers must be sorted and unique")
    timestamps = record["retrieval_timestamps"]
    if not isinstance(timestamps, list) or not timestamps or timestamps != sorted(set(timestamps)):
        raise HistoricalIngestionError("Source retrieval timestamps must be sorted and unique")
    for timestamp in timestamps:
        _timestamp(timestamp, "source retrieval timestamp")
    _text(record["normalization_version"], "normalization_version")
    if type(record["record_count"]) is not int or record["record_count"] < 1:
        raise HistoricalIngestionError("Source-batch record count is invalid")
    if type(record["json_array_byte_envelope_limitation"]) is not bool:
        raise HistoricalIngestionError("Source byte-envelope limitation flag is invalid")
    if record["validation_status"] != "validated":
        raise HistoricalIngestionError("Source-batch validation status is invalid")
    expected = _digest({key: record[key] for key in sorted(record) if key != "source_batch_id"})
    if _hash(record["source_batch_id"], "source_batch_id") != expected:
        raise HistoricalIngestionError("Source-batch identity does not reconcile")
    _reject_prohibited(record)


AUDIT_FIELDS = {
    "schema_version", "audit_id", "raw_id", "observation_id", "provider",
    "retrieval_timestamp", "source_identifier", "normalization_version",
    "validation_status", "validated_as_of", "warning_codes", "synthetic",
}


def _audit(raw: Mapping[str, object], observation: Mapping[str, object], as_of: str) -> dict[str, object]:
    record = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_id": "pending",
        "raw_id": raw["raw_id"],
        "observation_id": observation["observation_id"],
        "provider": raw["provider"],
        "retrieval_timestamp": raw["retrieval_timestamp"],
        "source_identifier": raw["source_identifier"],
        "normalization_version": raw["normalization_version"],
        "validation_status": "validated",
        "validated_as_of": as_of,
        "warning_codes": [],
        "synthetic": True,
    }
    record["audit_id"] = _digest({key: record[key] for key in sorted(record) if key != "audit_id"})
    validate_audit(record)
    return record


def validate_audit(record: Mapping[str, object]) -> None:
    _exact(record, AUDIT_FIELDS, "Historical ingestion audit")
    if record["schema_version"] != AUDIT_SCHEMA_VERSION or record["synthetic"] is not True:
        raise HistoricalIngestionError("Ingestion-audit schema or provenance is invalid")
    for field in ("provider", "source_identifier", "normalization_version"):
        _text(record[field], field)
    _timestamp(record["retrieval_timestamp"], "retrieval_timestamp")
    _timestamp(record["validated_as_of"], "validated_as_of")
    _hash(record["raw_id"], "raw_id")
    _hash(record["observation_id"], "observation_id")
    if record["validation_status"] != "validated" or record["warning_codes"] != []:
        raise HistoricalIngestionError("Ingestion-audit status is invalid")
    expected = _digest({key: record[key] for key in sorted(record) if key != "audit_id"})
    if _hash(record["audit_id"], "audit_id") != expected:
        raise HistoricalIngestionError("Ingestion-audit identity does not reconcile")
    _reject_prohibited(record)


VALIDATORS: dict[str, Callable[[Mapping[str, object]], None]] = {
    "raw": validate_raw_v2,
    "observation": validate_observation_v2,
    "cluster": validate_cluster_v2,
    "source": validate_source_batch,
    "audit": validate_audit,
}


def _artifact(kind: str, identity: str, suffix: Path, record: Mapping[str, object]) -> tuple[str, str, Path, Mapping[str, object], str]:
    VALIDATORS[kind](record)
    return kind, identity, suffix, record, hashlib.sha256(canonical_json(record)).hexdigest()


def build_ingestion_plan(
    provider: HistoricalCatalystProvider,
    source_paths: Sequence[Path],
    destination_root: Path,
    repository_root: Path,
    as_of: str,
    limits: InputLimits,
    *,
    normalizer: HistoricalNormalizer | None = None,
    deduplicator: CatalystDeduplicator | None = None,
    recovery: bool = False,
) -> IngestionPlan:
    normalizer = normalizer or StrictSyntheticHistoricalNormalizer()
    deduplicator = deduplicator or ExactObservationalContentDeduplicator()
    cutoff = _validate_configuration(provider, normalizer, deduplicator, as_of)
    root = validate_historical_root(destination_root, repository_root)
    try:
        sources = tuple(provider.read(source_paths, limits))
    except HistoricalProviderError as exc:
        raise HistoricalIngestionError(str(exc)) from exc
    raws = []
    for source in sources:
        raw = _source_record(source, provider.provider, provider.provider_version)
        raw["normalization_version"] = normalizer.version
        retrieval = _timestamp(raw["retrieval_timestamp"], "retrieval_timestamp")
        if retrieval > cutoff:
            raise HistoricalIngestionError("Retrieval timestamp exceeds as_of")
        raw["raw_id"] = raw_identity(raw)
        validate_raw_v2(raw)
        raws.append(raw)
    if len({str(record["raw_id"]) for record in raws}) != len(raws):
        raise HistoricalIngestionError("Duplicate immutable raw identifier")
    existing_raws, existing_observations = _published_records(root)
    _validate_lineage(raws, existing_raws)
    observations = [dict(normalizer.normalize(raw, as_of)) for raw in raws]
    _apply_revision_observations(observations, raws, existing_observations)
    clusters = _clusters(observations, deduplicator)
    for observation in observations:
        validate_observation_v2(observation, as_of=as_of)
    source_batches = _source_batches(
        sources, provider.provider, provider.provider_version, normalizer.version,
    )
    audits = [_audit(raw, observation, as_of) for raw, observation in zip(raws, observations, strict=True)]

    provisional: list[tuple[str, str, Path, Mapping[str, object], str]] = []
    for raw in sorted(raws, key=lambda item: str(item["raw_id"])):
        provisional.append(_artifact("raw", str(raw["raw_id"]), Path("raw") / f"{raw['raw_id']}.json", raw))
    for observation in sorted(observations, key=lambda item: str(item["observation_id"])):
        provisional.append(_artifact("observation", str(observation["observation_id"]), Path("normalized") / f"{observation['observation_id']}.json", observation))
    for cluster in sorted(clusters, key=lambda item: str(item["cluster_id"])):
        provisional.append(_artifact("cluster", str(cluster["cluster_id"]), Path("clusters") / f"{cluster['cluster_id']}.json", cluster))
    for source in sorted(source_batches, key=lambda item: str(item["source_batch_id"])):
        provisional.append(_artifact("source", str(source["source_batch_id"]), Path("sources") / f"{source['source_batch_id']}.json", source))
    for audit in sorted(audits, key=lambda item: str(item["audit_id"])):
        provisional.append(_artifact("audit", str(audit["audit_id"]), Path("parser-audit") / f"{audit['audit_id']}.json", audit))
    identity_payload = {
        "provider": provider.provider,
        "provider_version": provider.provider_version,
        "normalizer_version": normalizer.version,
        "deduplicator_version": deduplicator.version,
        "as_of": as_of,
        "limits": limits.as_dict(),
        "sources": [
            {
                "source_label": source.source_label,
                "source_file_hash": source.source_file_hash,
                "source_record_index": source.source_record_index,
                "source_record_byte_hash": source.source_record_byte_hash,
            }
            for source in sources
        ],
        "artifacts": [
            {"kind": kind, "identity": identity, "suffix": suffix.as_posix(), "content_hash": content_hash}
            for kind, identity, suffix, _, content_hash in provisional
        ],
    }
    run_id = _digest(identity_payload)
    artifacts = tuple(
        PlannedArtifact(
            kind=kind,
            identity=identity,
            relative_path=Path("ingestions") / run_id / suffix,
            record=record,
            content_hash=content_hash,
        )
        for kind, identity, suffix, record, content_hash in provisional
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": "pending",
        "run_id": run_id,
        "provider": provider.provider,
        "provider_version": provider.provider_version,
        "normalizer_version": normalizer.version,
        "deduplicator_version": deduplicator.version,
        "as_of": as_of,
        "limits": limits.as_dict(),
        "source_file_hashes": sorted({source.source_file_hash for source in sources}),
        "source_identifiers": sorted({
            str(source.logical_record["source_identifier"]) for source in sources
        }),
        "retrieval_timestamps": sorted({
            str(source.logical_record["retrieval_timestamp"]) for source in sources
        }),
        "record_count": len(raws),
        "artifacts": [
            {
                "kind": artifact.kind,
                "identity": artifact.identity,
                "relative_path": artifact.relative_path.as_posix(),
                "content_hash": artifact.content_hash,
            }
            for artifact in artifacts
        ],
        "publication_status": "published",
        "validation_status": "validated",
        "synthetic": True,
    }
    manifest["manifest_id"] = _digest({key: manifest[key] for key in sorted(manifest) if key != "manifest_id"})
    validate_manifest(manifest)
    plan = IngestionPlan(
        run_id=run_id,
        provider=provider.provider,
        provider_version=provider.provider_version,
        normalizer_version=normalizer.version,
        deduplicator_version=deduplicator.version,
        as_of=as_of,
        limits=limits,
        artifacts=artifacts,
        manifest=manifest,
        manifest_path=Path("ingestions") / run_id / "manifest.json",
    )
    preflight_plan(root, plan, recovery=recovery)
    return plan


MANIFEST_FIELDS = {
    "schema_version", "manifest_id", "run_id", "provider", "provider_version",
    "normalizer_version", "deduplicator_version", "as_of", "limits",
    "source_file_hashes", "record_count", "artifacts", "publication_status",
    "source_identifiers", "retrieval_timestamps", "validation_status", "synthetic",
}


def validate_manifest(record: Mapping[str, object]) -> None:
    _exact(record, MANIFEST_FIELDS, "Historical ingestion manifest")
    if record["schema_version"] != MANIFEST_SCHEMA_VERSION or record["synthetic"] is not True:
        raise HistoricalIngestionError("Historical manifest schema or provenance is invalid")
    _hash(record["run_id"], "run_id")
    for field in ("provider", "provider_version", "normalizer_version", "deduplicator_version"):
        _text(record[field], field)
    _timestamp(record["as_of"], "as_of")
    if not isinstance(record["limits"], dict):
        raise HistoricalIngestionError("Manifest limits are malformed")
    InputLimits(**record["limits"]).validate()
    hashes = record["source_file_hashes"]
    if not isinstance(hashes, list) or not hashes or hashes != sorted(set(hashes)):
        raise HistoricalIngestionError("Manifest source hashes are malformed")
    for value in hashes:
        _hash(value, "source_file_hash")
    identifiers = record["source_identifiers"]
    if not isinstance(identifiers, list) or not identifiers or identifiers != sorted(set(identifiers)):
        raise HistoricalIngestionError("Manifest source identifiers are malformed")
    timestamps = record["retrieval_timestamps"]
    if not isinstance(timestamps, list) or not timestamps or timestamps != sorted(set(timestamps)):
        raise HistoricalIngestionError("Manifest retrieval timestamps are malformed")
    for timestamp in timestamps:
        _timestamp(timestamp, "manifest retrieval timestamp")
    if type(record["record_count"]) is not int or record["record_count"] < 1:
        raise HistoricalIngestionError("Manifest record count is invalid")
    artifacts = record["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise HistoricalIngestionError("Manifest artifacts are missing")
    paths = []
    identities = []
    raw_count = 0
    kind_order = {"raw": 0, "observation": 1, "cluster": 2, "source": 3, "audit": 4}
    order_keys = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"kind", "identity", "relative_path", "content_hash"}:
            raise HistoricalIngestionError("Manifest artifact schema is malformed")
        if artifact["kind"] not in VALIDATORS:
            raise HistoricalIngestionError("Manifest artifact kind is unsupported")
        if artifact["kind"] == "raw":
            raw_count += 1
        _hash(artifact["identity"], "artifact identity")
        _hash(artifact["content_hash"], "artifact content hash")
        relative = Path(str(artifact["relative_path"]))
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("ingestions", record["run_id"]):
            raise HistoricalIngestionError("Manifest artifact path is unsafe")
        paths.append(relative.as_posix())
        identities.append((artifact["kind"], artifact["identity"]))
        order_keys.append((kind_order[artifact["kind"]], artifact["identity"]))
    if len(paths) != len(set(paths)):
        raise HistoricalIngestionError("Manifest artifact paths are duplicated")
    if len(identities) != len(set(identities)):
        raise HistoricalIngestionError("Manifest artifact identities are duplicated")
    if order_keys != sorted(order_keys):
        raise HistoricalIngestionError("Manifest artifacts are not deterministically ordered")
    if raw_count != record["record_count"]:
        raise HistoricalIngestionError("Manifest raw-record count does not reconcile")
    if record["publication_status"] != "published":
        raise HistoricalIngestionError("Manifest publication status is invalid")
    if record["validation_status"] != "validated":
        raise HistoricalIngestionError("Manifest validation status is invalid")
    expected = _digest({key: record[key] for key in sorted(record) if key != "manifest_id"})
    if _hash(record["manifest_id"], "manifest_id") != expected:
        raise HistoricalIngestionError("Manifest identity does not reconcile")
    _reject_prohibited(record)


def validate_historical_root(destination_root: Path, repository_root: Path) -> Path:
    root = validate_storage_root(destination_root, repository_root)
    normalized_parts = {part.casefold().replace("_", "-") for part in root.parts}
    if normalized_parts & PROTECTED_PATH_TOKENS:
        raise HistoricalIngestionError("Historical ingestion cannot access protected outcome storage")
    return root


def preflight_plan(root: Path, plan: IngestionPlan, *, recovery: bool) -> dict[str, int]:
    matching = 0
    missing = 0
    manifest = root / plan.manifest_path
    if manifest.exists():
        raise HistoricalIngestionError("A valid or conflicting manifest already occupies this run ID")
    for artifact in plan.artifacts:
        destination = root / artifact.relative_path
        if destination.exists():
            _validate_existing_artifact_path(root, destination)
            actual = destination.read_bytes()
            expected = canonical_json(artifact.record)
            if actual != expected:
                raise HistoricalIngestionError("Partial artifact differs from deterministic write plan")
            if not recovery:
                raise HistoricalIngestionError("Incomplete publication exists; explicit recovery is required")
            matching += 1
        else:
            missing += 1
    return {"matching": matching, "missing": missing}


def publish_plan(root: Path, plan: IngestionPlan, *, recovery: bool = False) -> Path:
    preflight_plan(root, plan, recovery=recovery)
    for artifact in plan.artifacts:
        destination = root / artifact.relative_path
        if destination.exists():
            continue
        write_once(root, artifact.relative_path, artifact.record, VALIDATORS[artifact.kind])
    for artifact in plan.artifacts:
        destination = root / artifact.relative_path
        if not destination.is_file() or destination.read_bytes() != canonical_json(artifact.record):
            raise HistoricalIngestionError("All artifacts must verify before manifest publication")
    return write_once(root, plan.manifest_path, plan.manifest, validate_manifest)


def inspect_batch_status(root: Path, run_id: str) -> dict[str, object]:
    _hash(run_id, "run_id")
    batch = root / "ingestions" / run_id
    manifest_path = batch / "manifest.json"
    if manifest_path.exists():
        manifest = read_canonical(manifest_path)
        validate_manifest(manifest)
        verified = 0
        for artifact in manifest["artifacts"]:
            path = root / artifact["relative_path"]
            _validate_existing_artifact_path(root, path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["content_hash"]:
                raise HistoricalIngestionError("Published batch contains a missing or changed artifact")
            verified += 1
        return {"run_id": run_id, "status": "published", "verified_artifacts": verified}
    if not batch.exists():
        return {"run_id": run_id, "status": "absent", "unpublished_artifacts": 0}
    if batch.is_symlink() or not batch.is_dir():
        raise HistoricalIngestionError("Incomplete batch path is unsafe")
    artifacts = [path for path in batch.rglob("*") if path.is_file()]
    for artifact in artifacts:
        _validate_existing_artifact_path(root, artifact)
    return {
        "run_id": run_id,
        "status": "unpublished-incomplete",
        "unpublished_artifacts": len(artifacts),
    }
