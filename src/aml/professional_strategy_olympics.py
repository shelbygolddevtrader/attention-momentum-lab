"""Design-only contracts for Professional Strategy Benchmark Olympics V001."""

from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Mapping

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


PROTOCOL_SCHEMA = "aml.professional-strategy-olympics.protocol.v001"
REGISTRY_SCHEMA = "aml.professional-strategy-olympics.strategy-registry.v001"
TOURNAMENT_SCHEMA = "aml.professional-strategy-olympics.tournament.v001"
READINESS_SCHEMA = "aml.professional-strategy-olympics.readiness.v001"
PROTOCOL_VERSION = "professional-strategy-olympics-v001"
ARTIFACT_NAMESPACE = "artifacts/professional_strategy_olympics/v001"
LEAN_PROTOCOL_IDENTITY = (
    "52b42287f6cd7ee6404a64ece074b8bca80f75967195c2c944e48d1b26f66fa5"
)
LEAN_READINESS_IDENTITY = (
    "867338c763d77c55690809d18e322b07008ce0bf3f3da2bfaf20d9979e148e12"
)
CAPITAL_GOVERNANCE_IDENTITY = (
    "6defde5b21b8aac1a4a1b15c501621163dcb9c400f629abd29b257f7a51073cf"
)
V002_PROTOCOL_IDENTITY = (
    "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
)
STRATEGY_IDS = (
    "failed_breakout_reversal_long_v001",
    "first_pullback_continuation_long_v001",
    "five_minute_orb_long_v001",
    "fifteen_minute_orb_long_v001",
    "gap_and_go_long_v001",
    "high_of_day_breakout_long_v001",
    "market_relative_momentum_long_v001",
    "rsi_exhaustion_reversion_long_v001",
    "vwap_mean_reversion_fade_long_v001",
    "vwap_reclaim_long_v001",
)
REQUIRED_STRATEGY_FIELDS = {
    "strategy_id", "strategy_identity", "name", "version", "division",
    "direction", "availability", "required_data_fields", "candidate_eligibility",
    "observation_window", "entry_window", "exact_entry_trigger",
    "entry_price_convention", "stop_rule", "target_rule",
    "maximum_holding_period", "end_of_day_liquidation_rule",
    "position_sizing_rule", "risk_unit", "slippage", "fees",
    "spread_assumption", "missing_bar_treatment", "halt_treatment",
    "corporate_action_treatment", "same_bar_stop_target_treatment",
    "duplicate_signal_handling", "cooldown", "maximum_entries_per_symbol_per_day",
    "maximum_concurrent_positions", "daily_loss_behavior",
    "market_regime_eligibility", "invalidating_conditions", "required_evidence",
    "allowed_parameter_variants", "claim_ceiling", "lookahead_prohibited",
    "short_version_status",
}
SUBJECTIVE_TERMS = {
    "approximately", "chart pattern", "discretionary", "eyeball", "looks strong",
    "optimize", "subjective", "trapped traders", "trendline", "tune later",
}
PROTECTED_PARTS = {
    "validation", "holdout", "sealed", "production", "operator", "live",
    "paper-forward", "paper_forward", "capital",
}
REQUIRED_READINESS_EVIDENCE = (
    "candidate_universe_binding",
    "cost_model_binding",
    "data_retention_evidence",
    "human_authorization",
    "ingestion_pipeline_verification",
    "missing_data_policy_verification",
    "partition_plan_binding",
    "provider_entitlement_evidence",
    "risk_model_binding",
    "strategy_contract_registry_verification",
    "tournament_rules_verification",
)
REQUIRED_EVENT_FIELDS = {
    "event_id", "name", "formula", "direction", "weight", "eligibility",
    "minimum_completed_trades", "undefined_policy", "tie_policy", "winsorization",
}


class OlympicsError(ValueError):
    """A benchmark-integrity, isolation, scoring, or claim boundary failed."""


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 3_000_000:
        raise OlympicsError("Olympics JSON is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsError("Olympics JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(OlympicsError(item)),
        )
        canonical_json(result)
    except OlympicsError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsError("Olympics input is not strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise OlympicsError("Olympics JSON root must be an object")
    return result


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise OlympicsError(f"{field} must be a SHA-256 digest")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise OlympicsError(f"{field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OlympicsError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OlympicsError(f"{field} must include a timezone")
    return parsed


def _validate_identity(value: Mapping[str, object], identity_field: str) -> None:
    identity = _hash(value[identity_field], identity_field)
    payload = {key: item for key, item in value.items() if key != identity_field}
    if canonical_hash(payload) != identity:
        raise OlympicsError(f"{identity_field} is stale or tampered")


def validate_protocol(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version", "protocol_version", "prospective_as_of", "protocol_identity",
        "purpose", "independence", "dataset_binding", "divisions",
        "artifact_namespace", "claim_ladder", "provenance", "authorization",
    }
    if set(value) != expected:
        raise OlympicsError("Olympics protocol contains missing or unexpected fields")
    if value["schema_version"] != PROTOCOL_SCHEMA or value["protocol_version"] != PROTOCOL_VERSION:
        raise OlympicsError("Unsupported Olympics protocol version")
    _timestamp(value["prospective_as_of"], "prospective_as_of")
    _validate_identity(value, "protocol_identity")
    independence = value["independence"]
    if independence != {
        "lean_protocol_identity": LEAN_PROTOCOL_IDENTITY,
        "lean_readiness_identity": LEAN_READINESS_IDENTITY,
        "capital_governance_identity": CAPITAL_GOVERNANCE_IDENTITY,
        "v002_protocol_identity": V002_PROTOCOL_IDENTITY,
        "identity_mutation": "prohibited",
        "readiness_credit_inheritance": "none",
    }:
        raise OlympicsError("Frozen Lean, capital, or V002 identity binding changed")
    if value["artifact_namespace"] != ARTIFACT_NAMESPACE:
        raise OlympicsError("Olympics artifacts must use the dedicated namespace")
    if value["authorization"] != {
        "human_authorization_required": True,
        "pilot_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "capital_release_authorized": False,
    }:
        raise OlympicsError("Olympics design cannot authorize execution or capital")
    divisions = value["divisions"]
    if divisions["benchmark_division"] != "exactly_ten_preregistered_strategy_families":
        raise OlympicsError("Benchmark Division definition changed")
    if divisions["research_division_entries"] != []:
        raise OlympicsError("Research Division must remain empty during design")
    return dict(value)


def load_protocol(path: Path) -> dict[str, object]:
    return validate_protocol(_strict_json(path))


def _validate_strategy(contract: Mapping[str, object]) -> None:
    if set(contract) != REQUIRED_STRATEGY_FIELDS:
        raise OlympicsError("Strategy contract contains missing or unexpected fields")
    if contract["strategy_id"] not in STRATEGY_IDS or contract["division"] != "benchmark":
        raise OlympicsError("Strategy is not a registered Benchmark Division competitor")
    identity = _hash(contract["strategy_identity"], "strategy_identity")
    payload = {key: item for key, item in contract.items() if key != "strategy_identity"}
    if canonical_hash(payload) != identity:
        raise OlympicsError("Strategy identity is stale or tampered")
    if contract["direction"] not in {"long_only", "short_only"}:
        raise OlympicsError("Strategy direction is invalid")
    if contract["direction"] == "short_only":
        if contract["availability"] != "exhibition_only" or contract["short_version_status"] != "unavailable_without_point_in_time_borrow_evidence":
            raise OlympicsError("Short strategy without borrow evidence must be exhibition-only")
    if contract["entry_price_convention"] != "next_complete_bar_open_after_trigger_plus_shared_adverse_costs":
        raise OlympicsError("Entries must occur after the completed trigger bar")
    if contract["same_bar_stop_target_treatment"] != "stop_first_conservative":
        raise OlympicsError("Same-bar stop/target treatment must be deterministic")
    if contract["lookahead_prohibited"] is not True:
        raise OlympicsError("Strategy must explicitly prohibit lookahead")
    variants = contract["allowed_parameter_variants"]
    if not isinstance(variants, list) or len(variants) > 3:
        raise OlympicsError("A strategy may contain no more than three frozen variants")
    text = canonical_json(payload).decode("utf-8").casefold()
    if any(term in text for term in SUBJECTIVE_TERMS):
        raise OlympicsError("Subjective or optimization language is prohibited")
    if any(token in text for token in ("continuous_range", "unbounded", "tbd")):
        raise OlympicsError("Unbounded or unfinished strategy rules are prohibited")


def validate_registry(value: Mapping[str, object], protocol: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version", "registry_version", "registry_identity", "protocol_identity",
        "selection_description", "shared_contract_bindings", "strategies",
        "research_division", "exhibition_policy", "authorization",
    }
    if set(value) != expected or value["schema_version"] != REGISTRY_SCHEMA:
        raise OlympicsError("Strategy registry contains missing or unexpected fields")
    if value["protocol_identity"] != protocol["protocol_identity"]:
        raise OlympicsError("Strategy registry is bound to the wrong protocol")
    _validate_identity(value, "registry_identity")
    strategies = value["strategies"]
    if not isinstance(strategies, list) or len(strategies) != 10:
        raise OlympicsError("Exactly ten benchmark strategy families are required")
    if [item["strategy_id"] for item in strategies] != list(STRATEGY_IDS):
        raise OlympicsError("Strategy contracts must be sorted and exactly registered")
    for strategy in strategies:
        _validate_strategy(strategy)
    if len({item["strategy_identity"] for item in strategies}) != 10:
        raise OlympicsError("Every strategy identity must be unique")
    if value["research_division"] != {"status": "reserved_empty", "entries": []}:
        raise OlympicsError("Empirical Research Division entries are prohibited")
    if value["authorization"] != {"benchmark_execution_authorized": False}:
        raise OlympicsError("Strategy registry cannot authorize execution")
    shared_fields = (
        "entry_price_convention", "position_sizing_rule", "risk_unit", "slippage",
        "fees", "spread_assumption", "same_bar_stop_target_treatment",
        "maximum_concurrent_positions", "daily_loss_behavior",
    )
    for field in shared_fields:
        if len({canonical_json(strategy[field]) for strategy in strategies}) != 1:
            raise OlympicsError(f"Strategy contracts disagree on shared {field}")
    return dict(value)


def load_registry(path: Path, protocol: Mapping[str, object]) -> dict[str, object]:
    return validate_registry(_strict_json(path), protocol)


def validate_tournament(
    value: Mapping[str, object], protocol: Mapping[str, object], registry: Mapping[str, object]
) -> dict[str, object]:
    expected = {
        "schema_version", "tournament_version", "tournament_identity",
        "protocol_identity", "registry_identity", "shared_environment",
        "ranking_divisions", "scoring_events", "overall_scoring", "advancement_gates",
        "multiple_testing", "disqualification_rules", "authorization",
    }
    if set(value) != expected or value["schema_version"] != TOURNAMENT_SCHEMA:
        raise OlympicsError("Tournament specification contains missing or unexpected fields")
    if value["protocol_identity"] != protocol["protocol_identity"] or value["registry_identity"] != registry["registry_identity"]:
        raise OlympicsError("Tournament identity dependencies do not match")
    _validate_identity(value, "tournament_identity")
    events = value["scoring_events"]
    if not isinstance(events, list) or len(events) != 15:
        raise OlympicsError("Exactly fifteen medal events are required")
    if len({event["event_id"] for event in events}) != 15:
        raise OlympicsError("Medal event identities must be unique")
    if any(set(event) != REQUIRED_EVENT_FIELDS for event in events):
        raise OlympicsError("Medal event definitions must use the frozen schema")
    if any(event["direction"] not in {"higher_is_better", "lower_is_better"} for event in events):
        raise OlympicsError("Medal event direction is invalid")
    if any(type(event["minimum_completed_trades"]) is not int or event["minimum_completed_trades"] < 1 for event in events):
        raise OlympicsError("Medal event minimum trade count is invalid")
    if sum(event["weight"] for event in events) != 100:
        raise OlympicsError("Medal event weights must total 100")
    if any(event["event_id"] == "raw_return" for event in events):
        raise OlympicsError("Raw-return-only ranking is prohibited")
    environment = value["shared_environment"]
    required_environment = {
        "initial_capital_usd": 100000,
        "risk_per_trade_fraction": 0.0025,
        "risk_per_trade_usd": 250,
        "maximum_concurrent_positions": 3,
        "maximum_gross_exposure_fraction": 0.5,
        "daily_loss_new_entry_stop_fraction": 0.01,
        "entry_semantics": "next_complete_bar_open_after_trigger",
        "same_bar_ordering": "stop_before_target",
    }
    if any(environment.get(key) != expected for key, expected in required_environment.items()):
        raise OlympicsError("Shared risk or execution environment changed")
    if set(value["overall_scoring"]["rankings"]) != {"equal_risk", "capital_constrained"}:
        raise OlympicsError("Both frozen tournament rankings are required")
    if value["overall_scoring"]["tie_breaking"] != [
        "validation_net_expectancy", "holdout_net_expectancy",
        "lower_maximum_drawdown", "lexicographic_strategy_identity",
    ]:
        raise OlympicsError("Tournament tie-breaking changed")
    if value["authorization"] != {
        "medal_grants_advancement": False,
        "pilot_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "capital_release_authorized": False,
    }:
        raise OlympicsError("Tournament cannot authorize advancement or execution")
    return dict(value)


def load_tournament(
    path: Path, protocol: Mapping[str, object], registry: Mapping[str, object]
) -> dict[str, object]:
    return validate_tournament(_strict_json(path), protocol, registry)


def validate_readiness_artifact(
    value: Mapping[str, object], protocol: Mapping[str, object],
    registry: Mapping[str, object], tournament: Mapping[str, object],
) -> dict[str, object]:
    expected = build_readiness(protocol, registry, tournament)
    if dict(value) != expected:
        raise OlympicsError("Tracked readiness artifact is stale or tampered")
    return dict(value)


def load_readiness_artifact(
    path: Path, protocol: Mapping[str, object], registry: Mapping[str, object],
    tournament: Mapping[str, object],
) -> dict[str, object]:
    return validate_readiness_artifact(
        _strict_json(path), protocol, registry, tournament
    )


def build_readiness(
    protocol: Mapping[str, object], registry: Mapping[str, object],
    tournament: Mapping[str, object], evidence: Mapping[str, str] | None = None,
) -> dict[str, object]:
    validated_protocol = validate_protocol(protocol)
    validated_registry = validate_registry(registry, validated_protocol)
    validated_tournament = validate_tournament(
        tournament, validated_protocol, validated_registry
    )
    supplied = dict(evidence or {})
    if set(supplied) - set(REQUIRED_READINESS_EVIDENCE):
        raise OlympicsError("Readiness evidence contains unexpected fields")
    for key, digest in supplied.items():
        _hash(digest, key)
    missing = [key for key in REQUIRED_READINESS_EVIDENCE if key not in supplied]
    payload = {
        "schema_version": READINESS_SCHEMA,
        "readiness_version": "professional-strategy-olympics-readiness-v001",
        "protocol_identity": validated_protocol["protocol_identity"],
        "registry_identity": validated_registry["registry_identity"],
        "tournament_identity": validated_tournament["tournament_identity"],
        "status": "blocked" if missing else "evidence_complete_execution_not_implemented",
        "required_evidence": list(REQUIRED_READINESS_EVIDENCE),
        "satisfied_evidence": sorted(supplied),
        "unresolved_evidence": missing,
        "pilot_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "capital_release_authorized": False,
        "empirical_data_opened": False,
        "validation_outcomes_opened": False,
        "holdout_outcomes_opened": False,
        "maximum_claim_level": 0,
    }
    return {**payload, "readiness_identity": canonical_hash(payload)}


def score_competitor(tournament: Mapping[str, object], event_scores: Mapping[str, float]) -> float:
    events = tournament["scoring_events"]
    expected = {event["event_id"] for event in events}
    if set(event_scores) != expected:
        raise OlympicsError("Every medal event requires one defined score")
    total = 0.0
    for event in events:
        score = event_scores[event["event_id"]]
        if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise OlympicsError("Undefined medal metrics fail closed")
        if not 0.0 <= float(score) <= 100.0:
            raise OlympicsError("Medal event scores must be between 0 and 100")
        total += float(score) * event["weight"] / 100.0
    return round(total, 10)


def assess_advancement(
    tournament: Mapping[str, object], stage: str, metrics: Mapping[str, object]
) -> dict[str, object]:
    if stage not in {"discovery", "validation", "holdout"}:
        raise OlympicsError("Unknown advancement stage")
    gate = tournament["advancement_gates"][stage]
    failures = []
    comparisons = (
        ("completed_trades", "minimum_completed_trades", "insufficient_trade_count", "minimum"),
        ("net_expectancy_r", "minimum_net_expectancy_r", "expectancy_below_threshold", "minimum"),
        ("maximum_drawdown_r", "maximum_drawdown_r", "drawdown_breached", "maximum"),
        ("active_months", "minimum_active_months", "month_coverage_inadequate", "minimum"),
        ("regime_count", "minimum_regime_count", "regime_coverage_inadequate", "minimum"),
    )
    for metric, threshold, reason, direction in comparisons:
        observed = float(metrics.get(metric, float("-inf") if direction == "minimum" else float("inf")))
        if (direction == "minimum" and observed < gate[threshold]) or (
            direction == "maximum" and observed > gate[threshold]
        ):
            failures.append(reason)
    if stage != "discovery" and float(metrics.get("expectancy_interval_lower_r", float("-inf"))) < gate["minimum_expectancy_interval_lower_r"]:
        failures.append("expectancy_interval_below_threshold")
    if float(metrics.get("top_symbol_pnl_fraction", float("inf"))) > gate["maximum_top_symbol_pnl_fraction"]:
        failures.append("symbol_concentration_breached")
    if float(metrics.get("top_day_pnl_fraction", float("inf"))) > gate["maximum_top_day_pnl_fraction"]:
        failures.append("day_concentration_breached")
    if float(metrics.get("variant_expectancy_range_r", float("inf"))) > gate["maximum_variant_expectancy_range_r"]:
        failures.append("parameter_sensitivity_breached")
    if int(metrics.get("critical_integrity_failures", 1)) != 0:
        failures.append("critical_integrity_failure")
    if metrics.get("strategy_identity_unchanged") is not True:
        failures.append("strategy_changed")
    if metrics.get("claim_compliant") is not True:
        failures.append("claim_noncompliance")
    payload = {
        "stage": stage,
        "eligible_to_freeze_for_next_stage": not failures,
        "failures": sorted(set(failures)),
        "paper_authorized": False,
        "live_authorized": False,
        "capital_release_authorized": False,
    }
    return {**payload, "assessment_identity": canonical_hash(payload)}


def authorize_discovery_path(path: Path, root: Path) -> Path:
    if ".." in path.parts:
        raise OlympicsError("Path traversal is prohibited")
    normalized = {part.casefold().replace("_", "-") for part in path.parts}
    if normalized & {part.replace("_", "-") for part in PROTECTED_PARTS}:
        raise OlympicsError("Discovery cannot access protected outcomes or execution paths")
    candidate = (path if path.is_absolute() else root / path).absolute()
    cursor = candidate
    while cursor != cursor.parent:
        if cursor.exists() and cursor.is_symlink():
            raise OlympicsError("Olympics paths cannot contain symlinks")
        cursor = cursor.parent
    try:
        relative = candidate.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise OlympicsError("Olympics path escapes its approved root") from exc
    if relative.parts[: len(Path(ARTIFACT_NAMESPACE).parts)] != Path(ARTIFACT_NAMESPACE).parts:
        raise OlympicsError("Olympics path is outside its artifact namespace")
    return candidate


def validate_claim(level: int, text: str) -> None:
    if type(level) is not int or not 0 <= level <= 9:
        raise OlympicsError("Claim level must be between zero and nine")
    normalized = " ".join(text.casefold().split())
    requirements = {
        "pipeline operational": 1,
        "discovery result": 2,
        "discovery advancement": 3,
        "validated": 4,
        "holdout passed": 5,
        "paper-forward candidate": 6,
        "tiny-live candidate": 7,
        "self-funding candidate": 8,
        "controlled-scaling candidate": 9,
    }
    for phrase, minimum in requirements.items():
        if phrase in normalized and level < minimum:
            raise OlympicsError("Claim language exceeds the achieved evidence level")
    for prohibited in (
        "best strategy", "professional winner", "production ready", "proven edge",
        "revenue generating",
    ):
        if prohibited in normalized:
            raise OlympicsError("Olympics ranking cannot support this claim")
    if "profitable" in normalized and level < 5:
        raise OlympicsError("Profitability language requires at least one-time holdout evidence")


def evidence_reset_stage(change_type: str) -> str:
    if change_type in {
        "candidate_eligibility", "entry_trigger", "exit_rule", "risk_rule",
        "cost_model", "parameter_variant", "market_regime_rule",
    }:
        return "discovery"
    if change_type in {"documentation_only", "formatting_only"}:
        return "unchanged"
    raise OlympicsError("Unknown strategy change fails closed")
