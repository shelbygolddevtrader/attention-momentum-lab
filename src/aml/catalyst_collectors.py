"""Passive collector contracts and deterministic synthetic implementations only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from aml.catalyst_observations import (
    CATALYST_SCHEMA_VERSION, RAW_SCHEMA_VERSION, normalized_record_hash,
    observation_id, sha256, validate_observation, validate_raw_record,
)


class Collector(Protocol):
    """Future adapters preserve vendor records and never return strategy features."""

    @property
    def source_name(self) -> str: ...

    def collect(self) -> Sequence[Mapping[str, object]]: ...


class Normalizer(Protocol):
    def normalize(self, raw: Mapping[str, object]) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class MockCatalystCollector:
    """Deterministic repository-safe collector; accepts synthetic payloads only."""

    payloads: tuple[Mapping[str, object], ...]
    acquisition_timestamp: str
    vendor_release: str = "synthetic-release-v001"
    source_name: str = "synthetic-mock"

    def collect(self) -> tuple[dict[str, object], ...]:
        records = []
        for payload in self.payloads:
            if payload.get("synthetic") is not True:
                raise ValueError("Mock collector rejects non-synthetic payloads")
            raw_payload = dict(payload)
            record = {
                "schema_version": RAW_SCHEMA_VERSION,
                "vendor": self.source_name,
                "vendor_release": self.vendor_release,
                "source_record_id": str(payload["source_record_id"]),
                "acquisition_timestamp": self.acquisition_timestamp,
                "payload": raw_payload,
                "raw_record_hash": sha256(raw_payload),
                "synthetic": True,
            }
            validate_raw_record(record)
            records.append(record)
        return tuple(records)


@dataclass(frozen=True)
class SyntheticCatalystNormalizer:
    parser_version: str = "synthetic-parser-v001"

    def normalize(self, raw: Mapping[str, object]) -> dict[str, object]:
        validate_raw_record(raw)
        payload = raw["payload"]
        fields = {
            "symbol", "security_identifier", "publication_timestamp",
            "first_seen_timestamp", "effective_event_timestamp", "source_name",
            "source_type", "source_locator", "headline", "normalized_summary",
            "catalyst_category", "direction", "novelty", "materiality",
            "company_specificity", "source_credibility", "is_primary_source",
            "duplicate_story_cluster_id", "language",
        }
        if set(payload) != fields | {"source_record_id", "synthetic"}:
            raise ValueError("Synthetic normalizer payload fields differ")
        record = {
            "schema_version": CATALYST_SCHEMA_VERSION,
            **{field: payload[field] for field in fields},
            "acquisition_timestamp": raw["acquisition_timestamp"],
            "vendor_release": raw["vendor_release"],
            "raw_record_hash": raw["raw_record_hash"],
            "parser_version": self.parser_version,
            "synthetic": True,
        }
        record["observation_id"] = observation_id(record)
        record["normalized_record_hash"] = normalized_record_hash(record)
        validate_observation(record)
        return record


def run_passive_collection(
    collector: Collector,
    normalizer: Normalizer,
    preserve_raw: Callable[[Mapping[str, object]], Path],
) -> tuple[tuple[Path, Mapping[str, object]], ...]:
    """Require durable raw preservation before any normalization is attempted."""
    completed = []
    for raw in collector.collect():
        location = preserve_raw(raw)
        if not isinstance(location, Path) or not location.is_file():
            raise RuntimeError("Raw preservation did not produce a durable file")
        completed.append((location, normalizer.normalize(raw)))
    return tuple(completed)
