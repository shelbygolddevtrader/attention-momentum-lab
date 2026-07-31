"""Narrow V002-to-V001 Olympics input adapter.

The adapter validates and projects already-fixed atoms.  It has no proposal,
execution, authorization, publication, network, provider, or broker capability.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_olympics_input_manifest_v002 import (
    ADAPTER_CONTRACT_IDENTITY,
    SCHEMA,
    VALIDATION_ONLY_STATUS,
    V001_IMPLEMENTATION_IDENTITY,
    manifest_identity,
    validate_manifest,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ORCHESTRATOR_IDENTITY,
    V004_BUNDLE_IDENTITY,
    executor_bindings,
    validate_input_manifest,
    validate_only as validate_v001_only,
)
from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


VERSION = "professional-strategy-olympics-orchestrator-input-adapter-v002"
MODULE_PATH = "src/aml/professional_strategy_olympics_orchestrator_input_adapter_v002.py"
VALIDATOR_PATH = "src/aml/professional_strategy_olympics_input_manifest_v002.py"
CLI_PATH = "scripts/validate_professional_strategy_olympics_input_manifest_v002.py"


class OlympicsOrchestratorInputAdapterV002Error(ValueError):
    """A V002 validation, projection, or authorization boundary failed."""


@dataclass(frozen=True)
class AdaptedInput:
    v001_manifest: dict[str, object]
    status_ledger: tuple[dict[str, object], ...]


def adapter_implementation_identity(root: Path) -> str:
    """Bind the adapter contract and exact validator, adapter, and CLI bytes."""
    paths = (root / VALIDATOR_PATH, root / MODULE_PATH, root / CLI_PATH)
    if any(not path.is_file() for path in paths):
        raise OlympicsOrchestratorInputAdapterV002Error("V002 adapter implementation file missing")
    return canonical_hash({
        "adapter_contract_identity": ADAPTER_CONTRACT_IDENTITY,
        "validator_sha256": hashlib.sha256(paths[0].read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(paths[1].read_bytes()).hexdigest(),
        "cli_sha256": hashlib.sha256(paths[2].read_bytes()).hexdigest(),
    })


def future_run_identity(value: Mapping[str, object], root: Path) -> str:
    """Compute the future authorization binding without authorizing a run."""
    if value.get("schema_name") != SCHEMA:
        raise OlympicsOrchestratorInputAdapterV002Error("future identity requires V002 input")
    implementation = adapter_implementation_identity(root)
    validated = validate_manifest(
        value, adapter_implementation_identity=implementation,
        bindings=executor_bindings(), canonical_mode=True,
    )
    source = validated.get("source_commit_identity")
    if not isinstance(source, str) or len(source) != 40 or any(
        character not in "0123456789abcdef" for character in source
    ):
        raise OlympicsOrchestratorInputAdapterV002Error("source commit identity is invalid")
    return canonical_hash({
        "source_commit_identity": source,
        "v001_orchestrator_contract_identity": ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_adapter_identity": implementation,
        "v004_scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "v002_manifest_identity": validated["manifest_identity"],
    })


def _project_trade(trade: Mapping[str, object]) -> dict[str, object]:
    if trade["direction"] != "long" or trade["actual_quantity"] <= 0:
        raise OlympicsOrchestratorInputAdapterV002Error(
            "V001 frozen internal structure is long-only; short projection is prohibited"
        )
    if trade["other_costs_microdollars"] != 0:
        raise OlympicsOrchestratorInputAdapterV002Error(
            "V001 internal structure cannot represent non-commission other costs"
        )
    return {
        "proposal_identity": trade["proposal_identity"],
        "symbol": trade["symbol"],
        "entry_nanoseconds": trade["actual_entry_timestamp_nanoseconds"],
        "exit_nanoseconds": trade["exit_timestamp_nanoseconds"],
        "quantity": trade["actual_quantity"],
        "raw_entry_microdollars": trade["raw_entry_microdollars"],
        "raw_exit_microdollars": trade["raw_exit_microdollars"],
        "entry_price_microdollars": trade["adjusted_entry_microdollars"],
        "target_microdollars": trade["target_microdollars"],
        "entry_commission_microdollars": trade["entry_commission_microdollars"],
        "exit_commission_microdollars": trade["exit_commission_microdollars"],
        "risk_budget_microdollars": trade["initial_risk_microdollars"],
        "net_pnl_microdollars": trade["net_pnl_microdollars"],
        "net_R": trade["net_R"],
        "exit_month_new_york": trade["month_new_york"],
        "regime_label": trade["regime_label"],
    }


def _project_entrant(value: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    status = value["status"]
    disqualified = status in {"disqualified", "integrity_failure"}
    reasons = []
    if disqualified:
        reasons = ["manifest_mismatch_or_unreconciled_entrant_ledger"]
    projected = {
        "strategy_id": value["entrant_id"],
        "strategy_identity": value["strategy_identity"],
        "executor_identity": value["executor_identity"],
        "disqualified": disqualified,
        "disqualification_reasons": reasons,
        "active_dates": value["active_dates"],
        "trades": [_project_trade(trade) for trade in value["trades"]],
        "sensitivity_variant_expectancies": value["sensitivity_expectation_set"],
    }
    ledger = {
        "entrant_id": value["entrant_id"],
        "entrant_identity": value["entrant_identity"],
        "status": status,
        "disqualification_reasons": value["disqualification_reasons"],
        "ineligibility_reasons": value["ineligibility_reasons"],
        "integrity_failures": value["integrity_failures"],
    }
    return projected, ledger


def adapt_manifest(value: Mapping[str, object], root: Path) -> AdaptedInput:
    """Validate V002 and losslessly project supported frozen V001 trade atoms."""
    if value.get("schema_name") != SCHEMA:
        raise OlympicsOrchestratorInputAdapterV002Error("V002 mode rejects non-V002 input")
    adapter_identity = adapter_implementation_identity(root)
    validated = validate_manifest(
        value, adapter_implementation_identity=adapter_identity,
        bindings=executor_bindings(), canonical_mode=True,
    )
    projected: list[dict[str, object]] = []
    ledger: list[dict[str, object]] = []
    for entrant in validated["entrants"]:
        item, status = _project_entrant(entrant)
        projected.append(item)
        ledger.append(status)
    v001: dict[str, object] = {
        "schema_version": "aml.professional-strategy-olympics.synthetic-input-manifest.v001",
        "manifest_identity": "0" * 64,
        "scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "synthetic": True,
        "fixture_identity": canonical_hash({
            "opened_stages": ["discovery"], "entrants": projected,
        }),
        "opened_stages": ["discovery"],
        "entrants": projected,
    }
    v001["manifest_identity"] = canonical_hash({
        key: item for key, item in v001.items() if key != "manifest_identity"
    })
    validate_input_manifest(v001)
    return AdaptedInput(v001, tuple(ledger))


def validation_only(value: Mapping[str, object], root: Path) -> bytes:
    """Validate through V001 and return a non-authorizing, non-result report."""
    adapted = adapt_manifest(value, root)
    v001_report = json_loads_bytes(validate_v001_only(root, adapted.v001_manifest))
    if v001_report.get("status") != VALIDATION_ONLY_STATUS:
        raise OlympicsOrchestratorInputAdapterV002Error("V001 authorization boundary changed")
    report = {
        "schema": "aml.professional-strategy-olympics.v002-validation-only-report",
        "status": VALIDATION_ONLY_STATUS,
        "v002_manifest_identity": manifest_identity(value),
        "v001_projected_manifest_identity": adapted.v001_manifest["manifest_identity"],
        "adapter_identity": adapter_implementation_identity(root),
        "future_run_identity": future_run_identity(value, root),
        "entrant_count": len(value["entrants"]),
        "trial_authorized": False,
        "trial_executed": False,
        "artifact_published": False,
        "ranking_exists": False,
        "aggregate_score_exists": False,
        "performance_result_exists": False,
    }
    return canonical_json(report)


def json_loads_bytes(value: bytes) -> dict[str, object]:
    result = __import__("json").loads(value)
    if not isinstance(result, dict):
        raise OlympicsOrchestratorInputAdapterV002Error("V001 validation report is invalid")
    return result


def assert_identity(value: str) -> str:
    """Small public guard useful to future authorization callers."""
    if not HASH_PATTERN.fullmatch(value):
        raise OlympicsOrchestratorInputAdapterV002Error("identity is invalid")
    return value
