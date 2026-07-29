"""Bounded, provider-neutral historical catalyst input contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Mapping, Protocol, Sequence
import unicodedata


HISTORICAL_INPUT_SCHEMA_VERSION = "aml.catalyst.historical-input.v001"
INPUT_FIELDS = {
    "schema_version", "source_identifier", "retrieval_timestamp",
    "provider_release", "revision_of_raw_id", "payload", "synthetic",
}
LIMIT_CEILINGS = {
    "max_total_source_bytes": 100_000_000,
    "max_record_bytes": 2_000_000,
    "max_records": 10_000,
    "max_nesting_depth": 64,
    "max_string_length": 20_000,
    "max_headline_length": 5_000,
    "max_summary_length": 20_000,
    "max_source_files": 1_000,
}


class HistoricalProviderError(ValueError):
    """A bounded local historical source cannot be accepted safely."""


@dataclass(frozen=True)
class InputLimits:
    max_total_source_bytes: int
    max_record_bytes: int
    max_records: int
    max_nesting_depth: int
    max_string_length: int
    max_headline_length: int
    max_summary_length: int
    max_source_files: int

    def validate(self) -> None:
        for field, value in self.as_dict().items():
            if type(value) is not int or value < 1:
                raise HistoricalProviderError(f"{field} must be a positive integer")
            if value > LIMIT_CEILINGS[field]:
                raise HistoricalProviderError(f"{field} exceeds the absolute safety ceiling")
        if self.max_headline_length > self.max_string_length:
            raise HistoricalProviderError("headline limit exceeds generic string limit")
        if self.max_summary_length > self.max_string_length:
            raise HistoricalProviderError("summary limit exceeds generic string limit")

    def as_dict(self) -> dict[str, int]:
        return {
            "max_total_source_bytes": self.max_total_source_bytes,
            "max_record_bytes": self.max_record_bytes,
            "max_records": self.max_records,
            "max_nesting_depth": self.max_nesting_depth,
            "max_string_length": self.max_string_length,
            "max_headline_length": self.max_headline_length,
            "max_summary_length": self.max_summary_length,
            "max_source_files": self.max_source_files,
        }


@dataclass(frozen=True)
class HistoricalSourceRecord:
    source_label: str
    source_format: str
    source_file_byte_length: int
    source_file_hash: str
    source_record_index: int
    source_record_byte_length: int | None
    source_record_byte_hash: str | None
    source_record_bytes: bytes | None
    logical_record: Mapping[str, object]


class HistoricalCatalystProvider(Protocol):
    """Provider plug-in contract; implementations perform no normalization."""

    @property
    def provider(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def read(self, paths: Sequence[Path], limits: InputLimits) -> Sequence[HistoricalSourceRecord]: ...


def _duplicate_rejecting_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HistoricalProviderError("JSON object contains duplicate keys")
        result[key] = value
    return result


def _constant_rejected(value: str) -> None:
    raise HistoricalProviderError(f"JSON constant {value} is not finite")


def _strict_json(payload: bytes) -> object:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise HistoricalProviderError("UTF-8 BOM is prohibited")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HistoricalProviderError("Source is not strict UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_constant_rejected,
        )
    except HistoricalProviderError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise HistoricalProviderError("Source contains malformed JSON") from exc


def _validate_tree(value: object, limits: InputLimits, *, depth: int = 0) -> None:
    if depth > limits.max_nesting_depth:
        raise HistoricalProviderError("JSON nesting exceeds the configured limit")
    if isinstance(value, dict):
        for key, nested in value.items():
            _validate_string(key, limits.max_string_length, "JSON key")
            _validate_tree(nested, limits, depth=depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _validate_tree(nested, limits, depth=depth + 1)
    elif isinstance(value, str):
        _validate_string(value, limits.max_string_length, "JSON string")
    elif value is not None and type(value) not in {bool, int, float}:
        raise HistoricalProviderError("JSON contains an unsupported value type")
    elif isinstance(value, float) and not (-float("inf") < value < float("inf")):
        raise HistoricalProviderError("JSON contains a non-finite number")


def _validate_string(value: str, limit: int, label: str) -> None:
    if len(value) > limit:
        raise HistoricalProviderError(f"{label} exceeds the configured length limit")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise HistoricalProviderError(f"{label} contains control or malformed Unicode")


def _canonical_size(value: object) -> int:
    return len(
        (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        .encode("utf-8")
    )


def _bounded_read(path: Path, maximum: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise HistoricalProviderError("Source could not be opened without following links") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise HistoricalProviderError("Source path is not a regular file")
        if info.st_size < 1 or info.st_size > maximum:
            raise HistoricalProviderError("Source bytes violate the configured batch limit")
        chunks = []
        remaining = info.st_size + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1_048_576))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) != info.st_size:
            raise HistoricalProviderError("Source changed while it was being read")
        return payload
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class LocalHistoricalFileProvider:
    """Read bounded synthetic JSON or JSONL records without network access."""

    provider: str
    provider_version: str

    def read(
        self, paths: Sequence[Path], limits: InputLimits,
    ) -> tuple[HistoricalSourceRecord, ...]:
        limits.validate()
        if not paths or len(paths) > limits.max_source_files:
            raise HistoricalProviderError("Source-file count violates the configured limit")
        resolved: list[Path] = []
        for original in paths:
            path = Path(original)
            if not path.is_absolute() or ".." in path.parts:
                raise HistoricalProviderError("Source paths must be absolute without traversal")
            if path.is_symlink() or not path.is_file():
                raise HistoricalProviderError("Source path must be a regular non-symlink file")
            mode = path.stat().st_mode
            if not stat.S_ISREG(mode):
                raise HistoricalProviderError("Source path is not a regular file")
            if path.suffix.casefold() not in {".json", ".jsonl"}:
                raise HistoricalProviderError("Only JSON and JSONL sources are supported")
            resolved.append(path)

        total_bytes = 0
        records: list[HistoricalSourceRecord] = []
        for path in sorted(resolved, key=lambda item: item.as_posix()):
            size = path.stat().st_size
            total_bytes += size
            if size < 1 or total_bytes > limits.max_total_source_bytes:
                raise HistoricalProviderError("Source bytes violate the configured batch limit")
            source_bytes = _bounded_read(path, limits.max_total_source_bytes)
            if len(source_bytes) != size:
                raise HistoricalProviderError("Source changed while it was being read")
            source_hash = hashlib.sha256(source_bytes).hexdigest()
            source_format = "jsonl" if path.suffix.casefold() == ".jsonl" else "json"
            label = f"source-{source_hash}.{source_format}"
            if path.suffix.casefold() == ".jsonl":
                lines = source_bytes.splitlines(keepends=True)
                if not lines or any(not line.strip() for line in lines):
                    raise HistoricalProviderError("JSONL must contain only non-empty records")
                for index, line in enumerate(lines):
                    records.append(self._record(label, "jsonl", source_bytes, source_hash, index, line, limits))
            else:
                parsed = _strict_json(source_bytes)
                if isinstance(parsed, dict):
                    records.append(self._record(label, "json-object", source_bytes, source_hash, 0, source_bytes, limits, parsed=parsed))
                elif isinstance(parsed, list):
                    for index, item in enumerate(parsed):
                        records.append(self._record(label, "json-array", source_bytes, source_hash, index, None, limits, parsed=item))
                else:
                    raise HistoricalProviderError("JSON source must contain an object or object array")
            if len(records) > limits.max_records:
                raise HistoricalProviderError("Record count exceeds the configured limit")
        return tuple(sorted(
            records,
            key=lambda item: (
                item.source_label, item.source_record_index,
                item.source_record_byte_hash or "",
            ),
        ))

    @staticmethod
    def _record(
        label: str,
        source_format: str,
        source_bytes: bytes,
        source_hash: str,
        index: int,
        record_bytes: bytes | None,
        limits: InputLimits,
        *,
        parsed: object | None = None,
    ) -> HistoricalSourceRecord:
        logical = _strict_json(record_bytes) if parsed is None and record_bytes is not None else parsed
        if not isinstance(logical, dict):
            raise HistoricalProviderError("Every historical source record must be an object")
        _validate_tree(logical, limits)
        canonical_size = _canonical_size(logical)
        bounded_size = len(record_bytes) if record_bytes is not None else canonical_size
        if bounded_size > limits.max_record_bytes or canonical_size > limits.max_record_bytes:
            raise HistoricalProviderError("Record exceeds the configured byte limit")
        if set(logical) != INPUT_FIELDS:
            raise HistoricalProviderError("Historical input contains missing or unknown fields")
        if logical["schema_version"] != HISTORICAL_INPUT_SCHEMA_VERSION:
            raise HistoricalProviderError("Historical input schema version is unsupported")
        if logical["synthetic"] is not True:
            raise HistoricalProviderError("Only explicitly synthetic historical inputs are supported")
        payload = logical["payload"]
        if not isinstance(payload, dict):
            raise HistoricalProviderError("Historical logical payload must be an object")
        headline = payload.get("headline")
        summary = payload.get("normalized_summary")
        if not isinstance(headline, str) or not isinstance(summary, str):
            raise HistoricalProviderError("Historical payload requires headline and normalized_summary")
        _validate_string(headline, limits.max_headline_length, "headline")
        _validate_string(summary, limits.max_summary_length, "normalized_summary")
        return HistoricalSourceRecord(
            source_label=label,
            source_format=source_format,
            source_file_byte_length=len(source_bytes),
            source_file_hash=source_hash,
            source_record_index=index,
            source_record_byte_length=len(record_bytes) if record_bytes is not None else None,
            source_record_byte_hash=(
                hashlib.sha256(record_bytes).hexdigest() if record_bytes is not None else None
            ),
            source_record_bytes=record_bytes,
            logical_record=logical,
        )
