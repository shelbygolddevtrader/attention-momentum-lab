"""Strict design-only validation for executable Olympics V002 contracts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_olympics import (
    CAPITAL_GOVERNANCE_IDENTITY,
    LEAN_PROTOCOL_IDENTITY,
    LEAN_READINESS_IDENTITY,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


SCHEMA = "aml.professional-strategy-olympics.protocol.v002"
VERSION = "professional-strategy-olympics-v002"
V001_PROTOCOL_IDENTITY = "8a7f4c2ca1c6b133e769992ef8315186de87b0f7f1baedf6d549536db6f72f3e"
V001_REGISTRY_IDENTITY = "af1e44069fd5e226ad702469fdf10c7e0b1c49c803065e20c83588b22e17bbc0"
V001_TOURNAMENT_IDENTITY = "10d41bf657759b5db5b5524a18158a480797ab9dcfcca59e7921672d31bb70aa"
V001_READINESS_IDENTITY = "ebe1179fea526e4bad0c808609ff68320840d57d2172355227edfeccaf054602"
V002_WINNER_ARCHETYPE_IDENTITY = "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
STRATEGY_IDS = (
    "failed_downside_breakdown_reclaim_long_v002",
    "first_pullback_continuation_long_v002",
    "five_minute_orb_long_v002",
    "fifteen_minute_orb_long_v002",
    "gap_and_go_long_v002",
    "high_of_day_breakout_long_v002",
    "market_relative_momentum_long_v002",
    "rsi_exhaustion_reversion_long_v002",
    "vwap_mean_reversion_fade_long_v002",
    "vwap_reclaim_long_v002",
)
SECTION_IDENTITIES = {
    "shared_indicators": "indicators_identity",
    "input_schema": "input_schema_identity",
    "lifecycle": "lifecycle_identity",
    "costs": "cost_model_identity",
    "registry": "registry_identity",
    "tournament": "tournament_identity",
    "evidence_classification": "evidence_identity",
    "unresolved_register": "unresolved_identity",
    "readiness": "readiness_identity",
}
REQUIRED_STRATEGY_FIELDS = {
    "strategy_id", "strategy_identity", "name", "version", "direction",
    "v001_lineage", "required_inputs", "required_indicators", "eligibility",
    "observation_window", "entry_window", "setup", "trigger", "entry",
    "stop", "target", "timeout", "invalidation", "tie_breaking",
    "maximum_entries_per_symbol_day", "cooldown_complete_bars",
    "allowed_parameter_variants", "claim_ceiling", "synthetic_fixture_contract",
}
FORBIDDEN_UNRESOLVED_VALUES = {"", "any", "discretionary", "later", "tbd", "undefined"}


class OlympicsV002Error(ValueError):
    """A V002 completeness, identity, or authorization invariant failed."""


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise OlympicsV002Error("V002 specification is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsV002Error("V002 JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(OlympicsV002Error(item)),
        )
        canonical_json(value)
    except OlympicsV002Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsV002Error("V002 specification must be strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OlympicsV002Error("V002 specification root must be an object")
    return value


def _identity(value: Mapping[str, object], field: str) -> str:
    identity = value.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsV002Error(f"{field} must be a SHA-256 identity")
    payload = {key: item for key, item in value.items() if key != field}
    if canonical_hash(payload) != identity:
        raise OlympicsV002Error(f"{field} is stale or tampered")
    return identity


def _defined(value: object, path: str = "root") -> None:
    if value is None:
        raise OlympicsV002Error(f"{path} cannot be null")
    if isinstance(value, str) and value.strip().casefold() in FORBIDDEN_UNRESOLVED_VALUES:
        raise OlympicsV002Error(f"{path} is unresolved")
    if isinstance(value, Mapping):
        if not value:
            raise OlympicsV002Error(f"{path} cannot be an empty object")
        for key, item in value.items():
            _defined(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _defined(item, f"{path}[{index}]")


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise OlympicsV002Error("prospective_as_of must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OlympicsV002Error("prospective_as_of is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OlympicsV002Error("prospective_as_of must include a timezone")


def validate_bundle(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version", "protocol_version", "prospective_as_of", "protocol_identity",
        "artifact_namespace", "historical_lineage", "shared_indicators", "input_schema",
        "lifecycle", "costs", "strategies", "registry", "tournament",
        "evidence_classification", "unresolved_register", "readiness", "authorization",
    }
    if set(value) != expected:
        raise OlympicsV002Error("V002 root contains missing or unexpected fields")
    if value["schema_version"] != SCHEMA or value["protocol_version"] != VERSION:
        raise OlympicsV002Error("Unsupported Olympics V002 specification")
    _validate_timestamp(value["prospective_as_of"])
    lineage = value["historical_lineage"]
    if lineage != {
        "v001_protocol_identity": V001_PROTOCOL_IDENTITY,
        "v001_registry_identity": V001_REGISTRY_IDENTITY,
        "v001_tournament_identity": V001_TOURNAMENT_IDENTITY,
        "v001_readiness_identity": V001_READINESS_IDENTITY,
        "lean_protocol_identity": LEAN_PROTOCOL_IDENTITY,
        "lean_readiness_identity": LEAN_READINESS_IDENTITY,
        "capital_governance_identity": CAPITAL_GOVERNANCE_IDENTITY,
        "winner_archetype_v002_identity": V002_WINNER_ARCHETYPE_IDENTITY,
        "lineage_policy": "v001_preserved_v002_prospective_completion_no_empirical_input",
    }:
        raise OlympicsV002Error("V001 or independent-governance lineage changed")
    for section, field in SECTION_IDENTITIES.items():
        if not isinstance(value[section], Mapping):
            raise OlympicsV002Error(f"{section} must be an object")
        _identity(value[section], field)
    strategies = value["strategies"]
    if not isinstance(strategies, list) or len(strategies) != 10:
        raise OlympicsV002Error("Exactly ten V002 strategies are required")
    if [item.get("strategy_id") for item in strategies] != list(STRATEGY_IDS):
        raise OlympicsV002Error("V002 strategies must use the exact stable order")
    for strategy in strategies:
        if set(strategy) != REQUIRED_STRATEGY_FIELDS:
            raise OlympicsV002Error("V002 strategy contract schema is incomplete")
        _identity(strategy, "strategy_identity")
        if strategy["direction"] != "long_only":
            raise OlympicsV002Error("V002 contains an unauthorized short strategy")
        if strategy["allowed_parameter_variants"] != []:
            raise OlympicsV002Error("V002 permits no parameter alternatives")
        fixture = strategy["synthetic_fixture_contract"]
        if set(fixture) != {"positive_path", "negative_path", "unavailable_path", "integrity_failure_path"}:
            raise OlympicsV002Error("Every strategy needs four synthetic fixture blueprints")
        _defined(strategy, strategy["strategy_id"])
    indicator_ids = {
        item["indicator_id"] for item in value["shared_indicators"]["definitions"]
    }
    if len(indicator_ids) != len(value["shared_indicators"]["definitions"]):
        raise OlympicsV002Error("Indicator IDs must be unique")
    input_ids = {item["input_id"] for item in value["input_schema"]["datasets"]}
    if len(input_ids) != len(value["input_schema"]["datasets"]):
        raise OlympicsV002Error("Input IDs must be unique")
    for strategy in strategies:
        if not set(strategy["required_indicators"]).issubset(indicator_ids):
            raise OlympicsV002Error("Strategy references an undefined indicator")
        if not set(strategy["required_inputs"]).issubset(input_ids):
            raise OlympicsV002Error("Strategy references an undefined input")
    registry = value["registry"]
    if registry["strategy_identities"] != [item["strategy_identity"] for item in strategies]:
        raise OlympicsV002Error("Registry does not bind every strategy identity")
    if registry["strategy_ids"] != list(STRATEGY_IDS):
        raise OlympicsV002Error("Registry strategy IDs changed")
    tournament = value["tournament"]
    bindings = {
        "registry_identity": registry["registry_identity"],
        "indicators_identity": value["shared_indicators"]["indicators_identity"],
        "input_schema_identity": value["input_schema"]["input_schema_identity"],
        "lifecycle_identity": value["lifecycle"]["lifecycle_identity"],
        "cost_model_identity": value["costs"]["cost_model_identity"],
    }
    if any(tournament.get(key) != expected for key, expected in bindings.items()):
        raise OlympicsV002Error("Tournament component binding changed")
    readiness_bindings = {
        **bindings,
        "tournament_identity": tournament["tournament_identity"],
        "evidence_identity": value["evidence_classification"]["evidence_identity"],
        "unresolved_identity": value["unresolved_register"]["unresolved_identity"],
    }
    if any(value["readiness"].get(key) != expected for key, expected in readiness_bindings.items()):
        raise OlympicsV002Error("Readiness component binding changed")
    unresolved = value["unresolved_register"]
    if unresolved["material_item_count"] != 0 or unresolved["items"] != []:
        raise OlympicsV002Error("Material unresolved items remain")
    readiness = value["readiness"]
    if readiness["status"] != "design_complete_implementation_not_authorized":
        raise OlympicsV002Error("V002 readiness must remain implementation-blocked")
    if readiness["unresolved_material_item_count"] != 0:
        raise OlympicsV002Error("Readiness reports unresolved material items")
    authorization = value["authorization"]
    if authorization != {
        "empirical_runner_authorized": False,
        "discovery_authorized": False,
        "tournament_scoring_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "capital_release_authorized": False,
        "production_authorized": False,
    }:
        raise OlympicsV002Error("V002 design cannot authorize execution or capital")
    if any(value["readiness"].get(key) is not False for key in authorization):
        raise OlympicsV002Error("Readiness authorization flags must all remain false")
    for section in ("shared_indicators", "input_schema", "lifecycle", "costs", "tournament", "evidence_classification"):
        _defined(value[section], section)
    _identity(value, "protocol_identity")
    return dict(value)


def load_bundle(path: Path) -> dict[str, object]:
    return validate_bundle(_strict_json(path))


def canonical_bundle_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_json(validate_bundle(value))
