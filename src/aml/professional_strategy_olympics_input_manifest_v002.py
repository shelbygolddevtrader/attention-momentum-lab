"""Exact, prospective synthetic-input contract for Olympics V002.

This module validates supplied atoms; it never generates proposals, fills,
trades, authorization, or results.  All scoring-critical arithmetic is integer
or reduced-rational arithmetic and every nested identity is recomputed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePath
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from aml.professional_strategy_executor_registry_v001 import (
    EXECUTOR_REGISTRY_IDENTITY,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY as V004_BUNDLE_IDENTITY,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    DISQUALIFICATION_CONDITIONS,
    ORCHESTRATOR_IDENTITY as V001_ORCHESTRATOR_IDENTITY,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


SCHEMA = "aml.professional-strategy-olympics.synthetic-input-manifest.v002"
VERSION = "professional-strategy-olympics-synthetic-input-manifest-v002"
CONTRACT_SCHEMA = "aml.professional-strategy-olympics.input-manifest-contract.v002"
CONTRACT_VERSION = "professional-strategy-olympics-input-manifest-contract-v002"
V001_IMPLEMENTATION_IDENTITY = (
    "fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0"
)
SOURCE_COMMIT_IDENTITY = "43c9410670cc1c5179f43094a7fa1e2dd92e945a"
ORDERING_VERSION = "utf8-bytewise-entrant-binding-then-trade-exit-entry-symbol-proposal-v001"
VALIDATION_ONLY_STATUS = "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
SIMULATOR_FILES = (
    "src/aml/portfolio_simulator.py",
    "src/aml/trade_simulator.py",
)
SIMULATOR_SOURCE_HASHES = {
    "portfolio_simulator_sha256": (
        "4b009ef70359693b95c40110fbbddb400f286bad334867e0fc7830bae2877fad"
    ),
    "trade_simulator_sha256": (
        "8e1d539f897161c9e4414e63e2bd429a6d665a856123ef0f3b1c2455bb67d621"
    ),
}
SIMULATOR_REGISTRY_IDENTITY = canonical_hash({
    "schema": "aml.professional-strategy-olympics.simulator-source-registry.v002",
    "version": "professional-strategy-olympics-simulator-source-registry-v002",
    **SIMULATOR_SOURCE_HASHES,
    "behavior": "frozen-source-binding-only-no-redefinition",
})
ADAPTER_CONTRACT_IDENTITY = canonical_hash({
    "schema": "aml.professional-strategy-olympics.orchestrator-input-adapter.v002",
    "version": "professional-strategy-olympics-orchestrator-input-adapter-v002",
    "accepted_schema": SCHEMA,
    "target_orchestrator_identity": V001_ORCHESTRATOR_IDENTITY,
    "authorization_capability": False,
    "execution_capability": False,
})

ROOT_FIELDS = {
    "schema_name", "schema_version", "manifest_identity", "synthetic_only",
    "fixture_identity", "opened_stages", "v004_scoring_bundle_identity",
    "v001_orchestrator_contract_identity", "v001_orchestrator_implementation_identity",
    "v002_adapter_contract_identity", "v002_adapter_implementation_identity",
    "executor_registry_identity", "simulator_registry_identity", "lifecycle_identity",
    "source_commit_identity", "ordering_version", "entrant_count", "entrants",
    "access_prohibitions", "classification",
}
ENTRANT_FIELDS = {
    "entrant_id", "strategy_identity", "executor_identity", "simulator_identity",
    "lifecycle_identity", "status", "disqualification_reasons", "integrity_failures",
    "ineligibility_reasons", "active_dates", "validation_classification",
    "holdout_classification",
    "sensitivity_expectation_set", "trade_count", "trades", "entrant_identity",
}
TRADE_FIELDS = {
    "proposal_identity", "proposal_timestamp_nanoseconds", "symbol", "direction",
    "confidence", "intended_entry_timestamp_nanoseconds",
    "actual_entry_timestamp_nanoseconds", "entry_delay_nanoseconds",
    "raw_entry_microdollars", "adjusted_entry_microdollars", "actual_quantity",
    "stop_microdollars", "target_microdollars", "raw_exit_microdollars",
    "adjusted_exit_microdollars", "exit_timestamp_nanoseconds", "exit_reason",
    "lifecycle_evidence", "entry_commission_microdollars",
    "exit_commission_microdollars", "other_costs_microdollars",
    "gross_pnl_microdollars", "net_pnl_microdollars", "initial_risk_microdollars",
    "net_R", "elapsed_holding_nanoseconds", "capital_efficiency_numerator_microdollars",
    "capital_efficiency_denominator_microdollar_nanoseconds", "month_new_york",
    "regime_label", "validation_classification", "holdout_classification",
    "execution_classification", "sensitivity_classification", "cost_stress_source",
    "trade_identity",
}
LIFECYCLE_FIELDS = {
    "stop_reached", "target_reached", "timeout_reached", "invalidation_reached",
    "session_end_reached", "same_bar_stop_and_target", "evidence_identity",
}
COST_FIELDS = {
    "entry_friction_basis_points", "exit_friction_basis_points",
    "entry_commission_microdollars", "exit_commission_microdollars",
    "other_costs_microdollars", "borrow_cost_microdollars",
    "price_impact_cost_microdollars", "source_identity",
}
PROHIBITION_FIELDS = {
    "historical", "live", "validation", "holdout", "extension", "forward",
    "provider", "broker", "network",
}
STATUSES = frozenset({"active", "ineligible", "disqualified", "integrity_failure"})
EXIT_REASONS = frozenset({"stop", "target", "timeout", "invalidation", "session_end"})
STAGE_CLASSIFICATIONS = frozenset({"stage_unopened"})
EXECUTION_CLASSIFICATIONS = frozenset({"completed_synthetic_trade"})
SENSITIVITY_CLASSIFICATIONS = frozenset({"canonical", "sensitivity_variant"})
MANIFEST_CLASSIFICATIONS = frozenset({
    "test_mathematical_specification_vector_not_trial_result",
    "canonical_synthetic_trial_input_not_authorized",
})
CONTRACT_FIELDS = {
    "schema", "version", "prospective_as_of", "manifest_schema",
    "manifest_version", "frozen_bindings", "required_fields",
    "canonical_ordering", "canonical_entrant_count", "exact_arithmetic",
    "identity_policy", "enumerations", "authorization", "classification",
    "contract_identity",
}


class OlympicsInputManifestV002Error(ValueError):
    """A V002 schema, reconciliation, identity, or isolation invariant failed."""


def _strict_fields(value: object, fields: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise OlympicsInputManifestV002Error(f"{name} fields are invalid")
    return value


def _integer(value: object, name: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise OlympicsInputManifestV002Error(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise OlympicsInputManifestV002Error(f"{name} is below its minimum")
    return value


def fraction_value(value: object, name: str) -> Fraction:
    item = _strict_fields(value, {"numerator", "denominator"}, name)
    numerator = _integer(item["numerator"], f"{name}.numerator")
    denominator = _integer(item["denominator"], f"{name}.denominator", minimum=1)
    result = Fraction(numerator, denominator)
    if (result.numerator, result.denominator) != (numerator, denominator):
        raise OlympicsInputManifestV002Error(f"{name} must be reduced")
    return result


def fraction_record(value: Fraction | int) -> dict[str, int]:
    item = Fraction(value)
    return {"numerator": item.numerator, "denominator": item.denominator}


def _identity(value: Mapping[str, object], field: str) -> str:
    identity = value.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsInputManifestV002Error(f"{field} must be a SHA-256 identity")
    payload = {key: item for key, item in value.items() if key != field}
    if canonical_hash(payload) != identity:
        raise OlympicsInputManifestV002Error(f"{field} is stale or tampered")
    return identity


def _reject_floats_or_paths(value: object, location: str = "root") -> None:
    if isinstance(value, float):
        raise OlympicsInputManifestV002Error(f"floating-point value at {location}")
    if isinstance(value, str):
        lowered = value.lower()
        windows_absolute = (
            len(value) >= 3 and value[1] == ":" and value[2] in {"/", "\\"}
        )
        if value.startswith(("/", "~/")) or PurePath(value).drive or windows_absolute:
            raise OlympicsInputManifestV002Error(f"absolute machine path at {location}")
        if "://" in lowered or lowered.startswith(("www.", "alpaca", "broker:")):
            raise OlympicsInputManifestV002Error(f"external-data reference at {location}")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _reject_floats_or_paths(item, f"{location}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_floats_or_paths(item, f"{location}[{index}]")


def simulator_registry_identity(root: Path) -> str:
    """Verify and return the frozen simulator source registry identity."""
    actual = {
        key: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for key, path in zip(SIMULATOR_SOURCE_HASHES, SIMULATOR_FILES, strict=True)
    }
    if actual != SIMULATOR_SOURCE_HASHES:
        raise OlympicsInputManifestV002Error("frozen simulator source changed")
    return SIMULATOR_REGISTRY_IDENTITY


def strict_json(path: Path, *, maximum_bytes: int = 5_000_000) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > maximum_bytes:
        raise OlympicsInputManifestV002Error("JSON input is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsInputManifestV002Error("JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OlympicsInputManifestV002Error(f"invalid constant: {item}")
            ),
        )
        canonical_json(result)
    except OlympicsInputManifestV002Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsInputManifestV002Error("input must be strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise OlympicsInputManifestV002Error("JSON root must be an object")
    return result


def load_contract(root: Path) -> dict[str, object]:
    value = strict_json(root / "config/professional_strategy_olympics_input_manifest_v002.json")
    if set(value) != CONTRACT_FIELDS:
        raise OlympicsInputManifestV002Error("V002 contract fields are invalid")
    if value.get("schema") != CONTRACT_SCHEMA or value.get("version") != CONTRACT_VERSION:
        raise OlympicsInputManifestV002Error("unsupported V002 contract")
    _identity(value, "contract_identity")
    bindings = value.get("frozen_bindings")
    expected = {
        "source_commit_identity": SOURCE_COMMIT_IDENTITY,
        "v001_orchestrator_contract_identity": V001_ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v004_scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "executor_registry_identity": EXECUTOR_REGISTRY_IDENTITY,
        "simulator_registry_identity": simulator_registry_identity(root),
        "lifecycle_identity": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
        "v002_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
    }
    if bindings != expected:
        raise OlympicsInputManifestV002Error("contract frozen bindings changed")
    if value.get("manifest_schema") != SCHEMA or value.get("manifest_version") != VERSION:
        raise OlympicsInputManifestV002Error("contract manifest version changed")
    if set(value.get("required_fields", {})) != {"root", "entrant", "trade", "lifecycle", "cost"}:
        raise OlympicsInputManifestV002Error("contract field registry changed")
    field_sets = {
        "root": ROOT_FIELDS, "entrant": ENTRANT_FIELDS, "trade": TRADE_FIELDS,
        "lifecycle": LIFECYCLE_FIELDS, "cost": COST_FIELDS,
    }
    for key, expected_fields in field_sets.items():
        if set(value["required_fields"][key]) != expected_fields:
            raise OlympicsInputManifestV002Error(f"contract {key} fields changed")
    enumerations = {
        "entrant_status": sorted(STATUSES),
        "direction": ["long", "short"],
        "exit_reason": sorted(EXIT_REASONS),
        "stage_classification": sorted(STAGE_CLASSIFICATIONS),
        "execution_classification": sorted(EXECUTION_CLASSIFICATIONS),
        "sensitivity_classification": sorted(SENSITIVITY_CLASSIFICATIONS),
        "manifest_classification": sorted(MANIFEST_CLASSIFICATIONS),
        "disqualification_reason": sorted(DISQUALIFICATION_CONDITIONS),
    }
    if value["enumerations"] != enumerations:
        raise OlympicsInputManifestV002Error("contract enumerations changed")
    authorization = value.get("authorization")
    if not isinstance(authorization, Mapping) or set(authorization) != {
        "can_authorize_trial", "can_execute_trial", "can_publish_results"
    } or any(authorization.values()):
        raise OlympicsInputManifestV002Error("contract must remain unauthorized")
    return value


def lifecycle_evidence_identity(value: Mapping[str, object]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "evidence_identity"})


def proposal_identity(value: Mapping[str, object]) -> str:
    """Bind the exact proposal-stage atoms carried by one V002 trade."""
    fields = (
        "proposal_timestamp_nanoseconds", "symbol", "direction", "confidence",
        "intended_entry_timestamp_nanoseconds", "stop_microdollars",
        "target_microdollars",
    )
    return canonical_hash({field: value[field] for field in fields})


def trade_identity(value: Mapping[str, object]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "trade_identity"})


def entrant_identity(value: Mapping[str, object]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "entrant_identity"})


def manifest_identity(value: Mapping[str, object]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "manifest_identity"})


def _round_half_even(value: Fraction) -> int:
    return round(value)


def _validate_lifecycle(value: object, exit_reason: str) -> None:
    item = _strict_fields(value, LIFECYCLE_FIELDS, "lifecycle_evidence")
    for field in LIFECYCLE_FIELDS - {"evidence_identity"}:
        if type(item[field]) is not bool:
            raise OlympicsInputManifestV002Error("lifecycle flags must be boolean")
    if item["evidence_identity"] != lifecycle_evidence_identity(item):
        raise OlympicsInputManifestV002Error("lifecycle evidence identity mismatch")
    if item["same_bar_stop_and_target"] and not (item["stop_reached"] and item["target_reached"]):
        raise OlympicsInputManifestV002Error("same-bar lifecycle evidence is incomplete")
    expected_flag = {
        "stop": "stop_reached", "target": "target_reached", "timeout": "timeout_reached",
        "invalidation": "invalidation_reached", "session_end": "session_end_reached",
    }[exit_reason]
    if not item[expected_flag]:
        raise OlympicsInputManifestV002Error("exit reason lacks lifecycle evidence")
    if item["same_bar_stop_and_target"] and exit_reason != "stop":
        raise OlympicsInputManifestV002Error("same-bar stop-before-target rule violated")
    if item["stop_reached"] and exit_reason != "stop":
        raise OlympicsInputManifestV002Error("reached stop must determine the exit")
    if item["target_reached"] and not item["stop_reached"] and exit_reason != "target":
        raise OlympicsInputManifestV002Error("reached target must determine the exit")


def _validate_cost_source(value: object, trade: Mapping[str, object]) -> None:
    item = _strict_fields(value, COST_FIELDS, "cost_stress_source")
    for field in COST_FIELDS - {"source_identity"}:
        _integer(item[field], f"cost_stress_source.{field}", minimum=0)
    if item["entry_friction_basis_points"] != 10 or item["exit_friction_basis_points"] != 10:
        raise OlympicsInputManifestV002Error("baseline friction must be exactly ten bps per side")
    for field in (
        "entry_commission_microdollars", "exit_commission_microdollars",
        "other_costs_microdollars",
    ):
        if item[field] != trade[field]:
            raise OlympicsInputManifestV002Error("cost source does not reconcile with trade")
    if item["price_impact_cost_microdollars"] != 0:
        raise OlympicsInputManifestV002Error("price-impact cost remains unsupported")
    if item["borrow_cost_microdollars"] != item["other_costs_microdollars"]:
        raise OlympicsInputManifestV002Error("evidenced borrow cost does not reconcile")
    if item["source_identity"] != canonical_hash(
        {key: atom for key, atom in item.items() if key != "source_identity"}
    ):
        raise OlympicsInputManifestV002Error("cost source identity mismatch")


def derive_cost_stress(value: Mapping[str, object]) -> dict[str, Fraction]:
    """Derive exact per-trade net-R scenarios; no final score is trusted."""
    source = value["cost_stress_source"]
    baseline_costs = (
        source["entry_commission_microdollars"]
        + source["exit_commission_microdollars"]
        + source["other_costs_microdollars"]
    )
    quantity = abs(value["actual_quantity"])
    results: dict[str, Fraction] = {}
    for label, multiplier in (
        ("base_1x", Fraction(1)), ("stress_1_5x", Fraction(3, 2)),
        ("stress_2x", Fraction(2)),
    ):
        increment = multiplier - 1
        incremental_friction = (
            quantity
            * (
                value["raw_entry_microdollars"]
                + value["raw_exit_microdollars"]
            )
            * Fraction(source["entry_friction_basis_points"], 10_000)
            * increment
        )
        incremental_costs = Fraction(baseline_costs) * increment
        results[label] = (
            value["net_pnl_microdollars"]
            - incremental_friction
            - incremental_costs
        ) / value["initial_risk_microdollars"]
    return results


def _validate_trade(value: object, seen: set[str]) -> None:
    trade = _strict_fields(value, TRADE_FIELDS, "trade")
    _reject_floats_or_paths(trade, "trade")
    if trade["trade_identity"] != trade_identity(trade):
        raise OlympicsInputManifestV002Error("trade identity mismatch")
    if trade["trade_identity"] in seen:
        raise OlympicsInputManifestV002Error("duplicate trade identity")
    seen.add(trade["trade_identity"])
    proposal = trade["proposal_identity"]
    if not isinstance(proposal, str) or not HASH_PATTERN.fullmatch(proposal):
        raise OlympicsInputManifestV002Error("proposal identity is invalid")
    if proposal != proposal_identity(trade):
        raise OlympicsInputManifestV002Error("proposal identity mismatch")
    if not isinstance(trade["symbol"], str) or not trade["symbol"]:
        raise OlympicsInputManifestV002Error("symbol is invalid")
    if trade["direction"] not in {"long", "short"}:
        raise OlympicsInputManifestV002Error("direction is invalid")
    quantity = _integer(trade["actual_quantity"], "actual_quantity")
    if (trade["direction"] == "long" and quantity <= 0) or (
        trade["direction"] == "short" and quantity >= 0
    ):
        raise OlympicsInputManifestV002Error("direction and quantity do not reconcile")
    confidence = fraction_value(trade["confidence"], "confidence")
    if not 0 <= confidence <= 1:
        raise OlympicsInputManifestV002Error("confidence must be between zero and one")
    timestamps = [
        _integer(trade[field], field, minimum=0)
        for field in (
            "proposal_timestamp_nanoseconds", "intended_entry_timestamp_nanoseconds",
            "actual_entry_timestamp_nanoseconds", "exit_timestamp_nanoseconds",
        )
    ]
    if not timestamps[0] < timestamps[1] <= timestamps[2] < timestamps[3]:
        raise OlympicsInputManifestV002Error("trade timestamp ordering is invalid")
    delay = timestamps[2] - timestamps[1]
    if trade["entry_delay_nanoseconds"] != delay:
        raise OlympicsInputManifestV002Error("entry delay does not reconcile")
    duration = timestamps[3] - timestamps[2]
    if trade["elapsed_holding_nanoseconds"] != duration:
        raise OlympicsInputManifestV002Error("holding duration does not reconcile")
    integer_fields = TRADE_FIELDS - {
        "proposal_identity", "symbol", "direction", "confidence", "exit_reason",
        "lifecycle_evidence", "net_R", "month_new_york", "regime_label",
        "validation_classification", "holdout_classification",
        "execution_classification", "sensitivity_classification", "cost_stress_source",
        "trade_identity",
    }
    for field in integer_fields:
        _integer(trade[field], field)
    positive_prices = (
        "raw_entry_microdollars", "adjusted_entry_microdollars", "stop_microdollars",
        "target_microdollars", "raw_exit_microdollars", "adjusted_exit_microdollars",
        "initial_risk_microdollars",
    )
    if any(trade[field] <= 0 for field in positive_prices):
        raise OlympicsInputManifestV002Error("prices and risk must be positive")
    if any(trade[field] < 0 for field in (
        "entry_commission_microdollars", "exit_commission_microdollars",
        "other_costs_microdollars",
    )):
        raise OlympicsInputManifestV002Error("costs cannot be negative")
    basis = trade["adjusted_entry_microdollars"]
    if trade["direction"] == "long":
        if not trade["stop_microdollars"] < basis < trade["target_microdollars"]:
            raise OlympicsInputManifestV002Error("long stop or target placement is invalid")
        expected_entry = _round_half_even(Fraction(trade["raw_entry_microdollars"] * 1001, 1000))
        expected_exit = _round_half_even(Fraction(trade["raw_exit_microdollars"] * 999, 1000))
        gross = quantity * (expected_exit - expected_entry)
    else:
        if not trade["target_microdollars"] < basis < trade["stop_microdollars"]:
            raise OlympicsInputManifestV002Error("short stop or target placement is invalid")
        expected_entry = _round_half_even(Fraction(trade["raw_entry_microdollars"] * 999, 1000))
        expected_exit = _round_half_even(Fraction(trade["raw_exit_microdollars"] * 1001, 1000))
        gross = abs(quantity) * (expected_entry - expected_exit)
    if trade["adjusted_entry_microdollars"] != expected_entry or trade["adjusted_exit_microdollars"] != expected_exit:
        raise OlympicsInputManifestV002Error("adjusted price does not reconcile")
    if trade["gross_pnl_microdollars"] != gross:
        raise OlympicsInputManifestV002Error("gross P&L does not reconcile")
    costs = (
        trade["entry_commission_microdollars"]
        + trade["exit_commission_microdollars"]
        + trade["other_costs_microdollars"]
    )
    if trade["net_pnl_microdollars"] != gross - costs:
        raise OlympicsInputManifestV002Error("net P&L does not reconcile")
    if fraction_value(trade["net_R"], "net_R") != Fraction(
        trade["net_pnl_microdollars"], trade["initial_risk_microdollars"]
    ):
        raise OlympicsInputManifestV002Error("net R does not reconcile")
    expected_denominator = abs(quantity) * basis * duration
    if trade["capital_efficiency_numerator_microdollars"] != trade["net_pnl_microdollars"] or trade["capital_efficiency_denominator_microdollar_nanoseconds"] != expected_denominator:
        raise OlympicsInputManifestV002Error("capital-efficiency atoms do not reconcile")
    seconds, _ = divmod(timestamps[3], 1_000_000_000)
    month = datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(
        ZoneInfo("America/New_York")
    ).strftime("%Y-%m")
    if trade["month_new_york"] != month:
        raise OlympicsInputManifestV002Error("New York month does not reconcile")
    if trade["exit_reason"] not in EXIT_REASONS:
        raise OlympicsInputManifestV002Error("exit reason is invalid")
    _validate_lifecycle(trade["lifecycle_evidence"], trade["exit_reason"])
    _validate_cost_source(trade["cost_stress_source"], trade)
    scenarios = derive_cost_stress(trade)
    if scenarios["base_1x"] != fraction_value(trade["net_R"], "net_R"):
        raise OlympicsInputManifestV002Error("base cost-stress scenario does not reconcile")
    if trade["validation_classification"] not in STAGE_CLASSIFICATIONS or trade["holdout_classification"] != "stage_unopened":
        raise OlympicsInputManifestV002Error("validation or holdout classification is invalid")
    if trade["execution_classification"] not in EXECUTION_CLASSIFICATIONS or trade["sensitivity_classification"] not in SENSITIVITY_CLASSIFICATIONS:
        raise OlympicsInputManifestV002Error("execution or sensitivity classification is invalid")
    if not isinstance(trade["regime_label"], str) or not trade["regime_label"]:
        raise OlympicsInputManifestV002Error("regime label is missing")


def _trade_order(trade: Mapping[str, object]) -> tuple[object, ...]:
    return (
        trade.get("exit_timestamp_nanoseconds", -1),
        trade.get("actual_entry_timestamp_nanoseconds", -1),
        str(trade.get("symbol", "")).encode("utf-8"),
        str(trade.get("proposal_identity", "")).encode("utf-8"),
    )


def _validate_entrant(value: object, binding: Mapping[str, str], seen: set[str]) -> None:
    entrant = _strict_fields(value, ENTRANT_FIELDS, "entrant")
    _reject_floats_or_paths(entrant, "entrant")
    if entrant["entrant_identity"] != entrant_identity(entrant):
        raise OlympicsInputManifestV002Error("entrant identity mismatch")
    if entrant["entrant_identity"] in seen:
        raise OlympicsInputManifestV002Error("duplicate entrant identity")
    seen.add(entrant["entrant_identity"])
    for field in ("strategy_id", "strategy_identity", "executor_identity"):
        entrant_field = "entrant_id" if field == "strategy_id" else field
        if entrant[entrant_field] != binding[field]:
            raise OlympicsInputManifestV002Error("entrant binding or order changed")
    if entrant["simulator_identity"] != SIMULATOR_REGISTRY_IDENTITY or entrant["lifecycle_identity"] != SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY:
        raise OlympicsInputManifestV002Error("entrant simulator or lifecycle identity changed")
    if entrant["status"] not in STATUSES:
        raise OlympicsInputManifestV002Error("entrant status is invalid")
    reasons = entrant["disqualification_reasons"]
    ineligibility = entrant["ineligibility_reasons"]
    failures = entrant["integrity_failures"]
    reason_sets = (reasons, ineligibility, failures)
    if any(not isinstance(items, list) or items != sorted(set(items)) for items in reason_sets):
        raise OlympicsInputManifestV002Error("entrant reasons must be unique and sorted")
    if any(
        not isinstance(reason, str) or not reason
        for items in reason_sets
        for reason in items
    ):
        raise OlympicsInputManifestV002Error("entrant reasons must be nonempty strings")
    if not set(reasons).issubset(DISQUALIFICATION_CONDITIONS):
        raise OlympicsInputManifestV002Error("unknown frozen disqualification reason")
    if (
        bool(reasons) != (entrant["status"] == "disqualified")
        or bool(ineligibility) != (entrant["status"] == "ineligible")
        or bool(failures) != (entrant["status"] == "integrity_failure")
    ):
        raise OlympicsInputManifestV002Error("entrant status does not reconcile")
    dates = entrant["active_dates"]
    if not isinstance(dates, list) or dates != sorted(set(dates)):
        raise OlympicsInputManifestV002Error("active dates must be unique and sorted")
    try:
        parsed_dates = [date.fromisoformat(item) for item in dates]
    except (TypeError, ValueError) as exc:
        raise OlympicsInputManifestV002Error("active dates must be ISO calendar dates") from exc
    if [item.isoformat() for item in parsed_dates] != dates:
        raise OlympicsInputManifestV002Error("active dates must be canonical ISO dates")
    if entrant["validation_classification"] not in STAGE_CLASSIFICATIONS or entrant["holdout_classification"] != "stage_unopened":
        raise OlympicsInputManifestV002Error("entrant stage classification is invalid")
    variants = entrant["sensitivity_expectation_set"]
    if not isinstance(variants, list):
        raise OlympicsInputManifestV002Error("sensitivity expectation set must be a list")
    for index, variant in enumerate(variants):
        fraction_value(variant, f"sensitivity_expectation_set[{index}]")
    trades = entrant["trades"]
    if not isinstance(trades, list) or entrant["trade_count"] != len(trades):
        raise OlympicsInputManifestV002Error("entrant trade count does not reconcile")
    if trades != sorted(trades, key=_trade_order):
        raise OlympicsInputManifestV002Error("trade ordering is nondeterministic")
    for trade in trades:
        _validate_trade(trade, seen)


def validate_manifest(
    value: Mapping[str, object], *, adapter_implementation_identity: str,
    bindings: Sequence[Mapping[str, str]], canonical_mode: bool = True,
) -> dict[str, object]:
    root = _strict_fields(value, ROOT_FIELDS, "manifest")
    _reject_floats_or_paths(root)
    if root["schema_name"] != SCHEMA or root["schema_version"] != VERSION:
        raise OlympicsInputManifestV002Error("unsupported V002 input manifest")
    expected = {
        "synthetic_only": True,
        "opened_stages": ["discovery"],
        "v004_scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "v001_orchestrator_contract_identity": V001_ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": adapter_implementation_identity,
        "executor_registry_identity": EXECUTOR_REGISTRY_IDENTITY,
        "simulator_registry_identity": SIMULATOR_REGISTRY_IDENTITY,
        "lifecycle_identity": SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
        "ordering_version": ORDERING_VERSION,
    }
    for field, expected_value in expected.items():
        if root[field] != expected_value:
            raise OlympicsInputManifestV002Error(f"{field} binding changed")
    source = root["source_commit_identity"]
    if not isinstance(source, str) or len(source) != 40 or any(
        character not in "0123456789abcdef" for character in source
    ):
        raise OlympicsInputManifestV002Error("source commit identity is invalid")
    if root["classification"] not in MANIFEST_CLASSIFICATIONS:
        raise OlympicsInputManifestV002Error("manifest classification is invalid")
    prohibitions = _strict_fields(root["access_prohibitions"], PROHIBITION_FIELDS, "access_prohibitions")
    if any(value is not True for value in prohibitions.values()):
        raise OlympicsInputManifestV002Error("all access prohibitions must remain enabled")
    entrants = root["entrants"]
    if not isinstance(entrants, list) or root["entrant_count"] != len(entrants):
        raise OlympicsInputManifestV002Error("entrant count does not reconcile")
    if canonical_mode and len(entrants) != 10:
        raise OlympicsInputManifestV002Error("canonical mode requires exactly ten entrants")
    if len(bindings) != len(entrants):
        raise OlympicsInputManifestV002Error("executor binding count changed")
    seen: set[str] = set()
    for entrant, binding in zip(entrants, bindings, strict=True):
        _validate_entrant(entrant, binding, seen)
    fixture_expected = canonical_hash({
        "opened_stages": root["opened_stages"],
        "entrant_identities": [entrant["entrant_identity"] for entrant in entrants],
        "classification": root["classification"],
    })
    if root["fixture_identity"] != fixture_expected:
        raise OlympicsInputManifestV002Error("fixture identity mismatch")
    if root["manifest_identity"] != manifest_identity(root):
        raise OlympicsInputManifestV002Error("manifest identity mismatch")
    return dict(root)


def load_manifest(
    path: Path, *, adapter_implementation_identity: str,
    bindings: Sequence[Mapping[str, str]], canonical_mode: bool = True,
) -> dict[str, object]:
    return validate_manifest(
        strict_json(path), adapter_implementation_identity=adapter_implementation_identity,
        bindings=bindings, canonical_mode=canonical_mode,
    )
