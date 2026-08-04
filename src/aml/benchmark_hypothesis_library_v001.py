"""Deterministic, hypothesis-only benchmark research library V001.

The library freezes research questions before triage, executable specification,
implementation, or discovery.  It derives Framework V001 observation and
hypothesis identities but grants no downstream execution authority.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Mapping
from urllib.parse import urlsplit

from aml.benchmark_strategy_research_v001 import (
    BenchmarkResearchError,
    canonical_hash,
    canonical_json,
    create_hypothesis,
    create_observation,
)


SCHEMA_VERSION = "aml.benchmark-hypothesis-library.v001"
LIBRARY_VERSION = "benchmark-hypothesis-library-v001"
FRAMEWORK_VERSION = "benchmark-strategy-research-v001"
FRAMEWORK_SOURCE_COMMIT = "d7651c2f31059039b8b0dc5d6baa716c53a57e4b"
SOURCE_DOMAIN = "aml.benchmark-hypothesis-library.source.v001"
REGISTRATION_DOMAIN = "aml.benchmark-hypothesis-library.registration.v001"
LIBRARY_DOMAIN = "aml.benchmark-hypothesis-library.v001"
CONCEPT_DOMAIN = "aml.benchmark-hypothesis-library.concept.v001"
HASH = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
MAX_LIBRARY_BYTES = 2_000_000
ENTRY_FIELDS = {
    "library_entry_id",
    "entry_version",
    "revision",
    "parent_registration_identity",
    "registration_status",
    "registered_at",
    "title",
    "taxonomy",
    "directional_scope",
    "market_assumption",
    "economic_mechanism",
    "entry_concept",
    "exit_concept",
    "invalidation_conditions",
    "expected_regimes",
    "required_indicators",
    "expected_trade_frequency",
    "expected_holding_period",
    "anticipated_failure_modes",
    "source_ids",
    "source_interpretation",
    "multiple_testing_family",
    "related_hypothesis_ids",
    "distinctness_rationale",
    "discovery_authorized",
    "implementation_authorized",
    "required_next_stage",
    "framework_observation_identity",
    "framework_hypothesis_identity",
    "registration_identity",
}
SOURCE_FIELDS = {
    "source_id",
    "source_type",
    "title",
    "authors_or_organization",
    "publication_year",
    "stable_locator",
    "evidence_scope",
    "interpretation_limit",
    "source_material_identity",
}
TOP_FIELDS = {
    "schema_version",
    "library_version",
    "framework_dependency",
    "policy",
    "source_count",
    "hypothesis_count",
    "sources",
    "hypotheses",
    "library_identity",
}
FREQUENCY_BUCKETS = {"very_low", "low", "medium", "high"}
SOURCE_TYPES = {"academic_research", "professional_literature", "official_market_documentation"}
REGISTRATION_STATUS = "preregistered_hypothesis_only"
REQUIRED_NEXT_STAGE = "triage_then_executable_specification_and_framework_preregistration"
PROHIBITED_POLICY_TOKENS = {
    "validation",
    "holdout",
    "forward testing",
    "paper trading",
    "live trading",
    "olympics execution",
    "optimization",
    "parameter search",
}


class HypothesisLibraryError(ValueError):
    """The library is malformed, noncanonical, or exceeds its authority."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HypothesisLibraryError(f"{field} must be a non-empty string")
    if len(value) > 20_000:
        raise HypothesisLibraryError(f"{field} exceeds the size limit")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise HypothesisLibraryError(f"{field} contains invalid Unicode") from exc
    if any(ord(character) < 32 for character in value):
        raise HypothesisLibraryError(f"{field} contains control characters")
    return value


def _identifier(value: object, field: str) -> str:
    result = _text(value, field)
    if not IDENTIFIER.fullmatch(result):
        raise HypothesisLibraryError(f"{field} is malformed")
    return result


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise HypothesisLibraryError(f"{field} must be a SHA-256 identity")
    return value


def _timestamp(value: object, field: str) -> str:
    result = _text(value, field)
    try:
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HypothesisLibraryError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HypothesisLibraryError(f"{field} must be timezone-aware")
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if parsed.utcoffset().total_seconds() != 0 or canonical != result:
        raise HypothesisLibraryError(f"{field} must use canonical UTC")
    return result


def _sorted_strings(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise HypothesisLibraryError(f"{field} must be a string list")
    result = [_text(item, f"{field} item") for item in value]
    if result != sorted(set(result)):
        raise HypothesisLibraryError(f"{field} must be unique and sorted")
    return result


def _source_projection(source: Mapping[str, object]) -> dict[str, object]:
    return {key: source[key] for key in sorted(SOURCE_FIELDS - {"source_material_identity"})}


def source_material_identity(source: Mapping[str, object]) -> str:
    return canonical_hash({"domain": SOURCE_DOMAIN, "source": _source_projection(source)})


def _observation_payload(
    entry: Mapping[str, object], source_identities: list[str]
) -> dict[str, object]:
    return {
        "observation_id": f"{entry['library_entry_id']}-obs",
        "title": entry["title"],
        "source_kind": "preregistered_literature_and_documented_behavior",
        "source_references": entry["source_ids"],
        "source_dataset_identities": source_identities,
        "observed_behavior": entry["source_interpretation"],
        "recorded_at": entry["registered_at"],
    }


def _hypothesis_payload(
    entry: Mapping[str, object], source_identities: list[str]
) -> dict[str, object]:
    evidence = sorted(
        {
            "complete point-in-time inputs for every required indicator",
            "net-of-cost discovery metrics from the unchanged downstream pipeline",
            "reconciliation, integrity, and concentration evidence",
        }
    )
    return {
        "hypothesis_id": entry["library_entry_id"],
        "revision": entry["revision"],
        "parent_hypothesis_identity": None,
        "title": entry["title"],
        "market_assumption": entry["market_assumption"],
        "mechanism": entry["economic_mechanism"],
        "required_evidence": evidence,
        "expected_edge": (
            "Positive net expectancy after unchanged modeled costs only in the stated "
            "regime; absence of that evidence invalidates the hypothesis."
        ),
        "invalidation_conditions": entry["invalidation_conditions"],
        "known_risks": entry["anticipated_failure_modes"],
        "required_indicators": entry["required_indicators"],
        "expected_holding_period": entry["expected_holding_period"],
        "expected_market_regime": "; ".join(entry["expected_regimes"]),
        "expected_failure_modes": entry["anticipated_failure_modes"],
        "taxonomy": entry["taxonomy"],
        "contaminated_dataset_identities": source_identities,
        "multiple_testing_family": entry["multiple_testing_family"],
    }


def framework_artifacts(
    entry: Mapping[str, object], sources: Mapping[str, Mapping[str, object]]
) -> tuple[dict[str, object], dict[str, object]]:
    """Materialize one registration as native Framework V001 artifacts."""

    identities = sorted(
        _identity(sources[source_id]["source_material_identity"], "source material identity")
        for source_id in entry["source_ids"]
    )
    try:
        observation = create_observation(_observation_payload(entry, identities))
        hypothesis = create_hypothesis(_hypothesis_payload(entry, identities), observation)
    except BenchmarkResearchError as exc:
        raise HypothesisLibraryError("entry is not Framework V001 compatible") from exc
    return observation, hypothesis


def derive_framework_identities(
    entry: Mapping[str, object], sources: Mapping[str, Mapping[str, object]]
) -> tuple[str, str]:
    observation, hypothesis = framework_artifacts(entry, sources)
    return observation["identity"], hypothesis["identity"]


def _entry_projection(entry: Mapping[str, object]) -> dict[str, object]:
    return {key: entry[key] for key in sorted(ENTRY_FIELDS - {"registration_identity"})}


def registration_identity(entry: Mapping[str, object]) -> str:
    return canonical_hash({"domain": REGISTRATION_DOMAIN, "entry": _entry_projection(entry)})


def concept_identity(entry: Mapping[str, object]) -> str:
    fields = (
        "economic_mechanism",
        "entry_concept",
        "exit_concept",
        "invalidation_conditions",
        "expected_regimes",
        "required_indicators",
        "expected_holding_period",
    )
    return canonical_hash(
        {"domain": CONCEPT_DOMAIN, "concept": {field: entry[field] for field in fields}}
    )


def library_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(TOP_FIELDS - {"library_identity"})}
    return canonical_hash({"domain": LIBRARY_DOMAIN, "library": projection})


def _validate_source(source: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(source, Mapping) or set(source) != SOURCE_FIELDS:
        raise HypothesisLibraryError("source schema is invalid")
    _identifier(source["source_id"], "source_id")
    if source["source_type"] not in SOURCE_TYPES:
        raise HypothesisLibraryError("source_type is invalid")
    for field in (
        "title",
        "authors_or_organization",
        "stable_locator",
        "evidence_scope",
        "interpretation_limit",
    ):
        _text(source[field], field)
    locator = urlsplit(source["stable_locator"])
    if locator.scheme != "https" or not locator.netloc or locator.username is not None:
        raise HypothesisLibraryError("source stable locator must be an HTTPS URL")
    if type(source["publication_year"]) is not int or not 1900 <= source["publication_year"] <= 2026:
        raise HypothesisLibraryError("publication_year is invalid")
    expected = source_material_identity(source)
    if source["source_material_identity"] != expected:
        raise HypothesisLibraryError("source material identity is stale or tampered")
    return dict(source)


def _validate_entry(
    entry: Mapping[str, object], sources: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS:
        raise HypothesisLibraryError("hypothesis entry schema is invalid")
    _identifier(entry["library_entry_id"], "library_entry_id")
    if entry["entry_version"] != "1.0.0":
        raise HypothesisLibraryError("entry_version changed")
    if entry["revision"] != 1 or entry["parent_registration_identity"] is not None:
        raise HypothesisLibraryError("V001 entries must be root revision one records")
    if entry["registration_status"] != REGISTRATION_STATUS:
        raise HypothesisLibraryError("registration status changed")
    _timestamp(entry["registered_at"], "registered_at")
    for field in (
        "title",
        "market_assumption",
        "economic_mechanism",
        "entry_concept",
        "exit_concept",
        "expected_holding_period",
        "source_interpretation",
        "multiple_testing_family",
        "distinctness_rationale",
    ):
        _text(entry[field], field)
    for field in (
        "taxonomy",
        "directional_scope",
        "invalidation_conditions",
        "expected_regimes",
        "required_indicators",
        "anticipated_failure_modes",
        "source_ids",
        "related_hypothesis_ids",
    ):
        _sorted_strings(
            entry[field], field, allow_empty=field == "related_hypothesis_ids"
        )
    if not set(entry["directional_scope"]).issubset({"long", "short"}):
        raise HypothesisLibraryError("directional_scope is invalid")
    _identifier(entry["multiple_testing_family"], "multiple_testing_family")
    if any(source_id not in sources for source_id in entry["source_ids"]):
        raise HypothesisLibraryError("hypothesis references an unknown source")
    frequency = entry["expected_trade_frequency"]
    if not isinstance(frequency, Mapping) or set(frequency) != {"bucket", "description"}:
        raise HypothesisLibraryError("expected trade frequency schema is invalid")
    if frequency["bucket"] not in FREQUENCY_BUCKETS:
        raise HypothesisLibraryError("expected trade frequency bucket is invalid")
    _text(frequency["description"], "expected trade frequency description")
    if entry["discovery_authorized"] is not False or entry["implementation_authorized"] is not False:
        raise HypothesisLibraryError("hypothesis library cannot authorize implementation or discovery")
    if entry["required_next_stage"] != REQUIRED_NEXT_STAGE:
        raise HypothesisLibraryError("required next stage changed")
    observation_identity, hypothesis_identity = derive_framework_identities(entry, sources)
    if entry["framework_observation_identity"] != observation_identity:
        raise HypothesisLibraryError("framework observation identity is stale or tampered")
    if entry["framework_hypothesis_identity"] != hypothesis_identity:
        raise HypothesisLibraryError("framework hypothesis identity is stale or tampered")
    expected_registration = registration_identity(entry)
    if entry["registration_identity"] != expected_registration:
        raise HypothesisLibraryError("registration identity is stale or tampered")
    return dict(entry)


def validate_library(value: Mapping[str, object]) -> dict[str, object]:
    """Validate every source, registration, Framework identity, and policy."""

    if not isinstance(value, Mapping) or set(value) != TOP_FIELDS:
        raise HypothesisLibraryError("library schema is invalid")
    if value["schema_version"] != SCHEMA_VERSION or value["library_version"] != LIBRARY_VERSION:
        raise HypothesisLibraryError("library version changed")
    dependency = value["framework_dependency"]
    expected_dependency = {
        "framework_version": FRAMEWORK_VERSION,
        "source_commit": FRAMEWORK_SOURCE_COMMIT,
        "integration": "derive_native_observation_and_hypothesis_identities_only",
    }
    if dependency != expected_dependency:
        raise HypothesisLibraryError("Framework V001 dependency changed")
    policy = value["policy"]
    required_policy = {
        "registration_scope",
        "evidence_claim",
        "mutation_rule",
        "contamination_rule",
        "downstream_boundary",
        "prohibited_actions",
    }
    if not isinstance(policy, Mapping) or set(policy) != required_policy:
        raise HypothesisLibraryError("library policy schema is invalid")
    if policy["registration_scope"] != REGISTRATION_STATUS:
        raise HypothesisLibraryError("library registration scope changed")
    for field in required_policy - {"prohibited_actions"}:
        _text(policy[field], f"policy.{field}")
    prohibited = _sorted_strings(policy["prohibited_actions"], "prohibited_actions")
    if not PROHIBITED_POLICY_TOKENS.issubset({item.casefold() for item in prohibited}):
        raise HypothesisLibraryError("library policy does not prohibit every protected action")
    raw_sources = value["sources"]
    raw_entries = value["hypotheses"]
    if not isinstance(raw_sources, list) or not isinstance(raw_entries, list):
        raise HypothesisLibraryError("sources and hypotheses must be lists")
    if not 30 <= len(raw_entries) <= 50:
        raise HypothesisLibraryError("library must contain 30 to 50 hypotheses")
    if value["source_count"] != len(raw_sources) or value["hypothesis_count"] != len(raw_entries):
        raise HypothesisLibraryError("declared library counts do not reconcile")
    sources = [_validate_source(source) for source in raw_sources]
    if [source["source_id"] for source in sources] != sorted(
        source["source_id"] for source in sources
    ):
        raise HypothesisLibraryError("sources must be deterministically sorted")
    source_by_id = {source["source_id"]: source for source in sources}
    if len(source_by_id) != len(sources) or len(
        {source["source_material_identity"] for source in sources}
    ) != len(sources):
        raise HypothesisLibraryError("source identifiers or identities repeat")
    if {source["source_type"] for source in sources} != SOURCE_TYPES:
        raise HypothesisLibraryError("library must cover every required source type")
    entries = [_validate_entry(entry, source_by_id) for entry in raw_entries]
    entry_ids = [entry["library_entry_id"] for entry in entries]
    if entry_ids != sorted(entry_ids):
        raise HypothesisLibraryError("hypotheses must be deterministically sorted")
    if len(set(entry_ids)) != len(entries):
        raise HypothesisLibraryError("hypothesis identifiers repeat")
    for identity_field in (
        "framework_observation_identity",
        "framework_hypothesis_identity",
        "registration_identity",
    ):
        if len({entry[identity_field] for entry in entries}) != len(entries):
            raise HypothesisLibraryError(f"{identity_field} repeats")
    if len({concept_identity(entry) for entry in entries}) != len(entries):
        raise HypothesisLibraryError("semantic hypothesis concepts repeat")
    used_sources = {
        source_id for entry in entries for source_id in entry["source_ids"]
    }
    if used_sources != set(source_by_id):
        raise HypothesisLibraryError("every registered source must support a hypothesis")
    known_ids = set(entry_ids)
    for entry in entries:
        if any(item not in known_ids or item == entry["library_entry_id"] for item in entry["related_hypothesis_ids"]):
            raise HypothesisLibraryError("related hypothesis reference is invalid")
        for related in entry["related_hypothesis_ids"]:
            peer = entries[entry_ids.index(related)]
            if entry["library_entry_id"] not in peer["related_hypothesis_ids"]:
                raise HypothesisLibraryError("related hypothesis links must be symmetric")
    if value["library_identity"] != library_identity(value):
        raise HypothesisLibraryError("library identity is stale or tampered")
    return dict(value)


def _strict_json(path: Path) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise HypothesisLibraryError("library JSON contains duplicate keys")
            result[key] = item
        return result

    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_LIBRARY_BYTES:
        raise HypothesisLibraryError("library path is missing, unsafe, or oversized")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                HypothesisLibraryError(f"non-finite library value: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HypothesisLibraryError("library JSON is malformed") from exc
    if not isinstance(value, dict):
        raise HypothesisLibraryError("library root must be an object")
    return value


def load_library(path: Path) -> dict[str, object]:
    value = _strict_json(path)
    validate_library(value)
    if path.read_bytes() != canonical_json(value):
        raise HypothesisLibraryError("library bytes are not canonical")
    return value


def finalize_identities(value: Mapping[str, object]) -> dict[str, object]:
    """Pure authoring helper used to freeze a complete semantic library."""

    result = json.loads(canonical_json(value))
    for source in result["sources"]:
        source["source_material_identity"] = source_material_identity(source)
    source_by_id = {source["source_id"]: source for source in result["sources"]}
    for entry in result["hypotheses"]:
        observation_identity, hypothesis_identity = derive_framework_identities(
            entry, source_by_id
        )
        entry["framework_observation_identity"] = observation_identity
        entry["framework_hypothesis_identity"] = hypothesis_identity
        entry["registration_identity"] = registration_identity(entry)
    result["source_count"] = len(result["sources"])
    result["hypothesis_count"] = len(result["hypotheses"])
    result["library_identity"] = library_identity(result)
    validate_library(result)
    return result
