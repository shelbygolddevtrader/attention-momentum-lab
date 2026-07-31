"""Validation-only V003 input adapter over the frozen V002/V001 path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_olympics_final_scoring_v004 import (
    BUNDLE_IDENTITY as V004_BUNDLE_IDENTITY,
)
from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY,
    SCHEMA,
    V002_ADAPTER_IMPLEMENTATION_IDENTITY,
    V002_CONTRACT_IDENTITY,
    V003_ADAPTER_CONTRACT_IDENTITY,
    manifest_identity,
    project_to_v002,
    validate_manifest,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v002 import (
    AdaptedInput,
    adapt_manifest as adapt_v002_manifest,
    validation_only as validate_v002_only,
)
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ORCHESTRATOR_IDENTITY,
    executor_bindings,
)
from aml.professional_strategy_olympics_input_manifest_v002 import (
    V001_IMPLEMENTATION_IDENTITY,
)
from aml.winner_archetype_contracts import canonical_hash, canonical_json


VERSION = "professional-strategy-olympics-orchestrator-input-adapter-v003"
MODULE_PATH = "src/aml/professional_strategy_olympics_orchestrator_input_adapter_v003.py"
VALIDATOR_PATH = "src/aml/professional_strategy_olympics_input_manifest_v003.py"
CLI_PATH = "scripts/validate_professional_strategy_olympics_input_manifest_v003.py"
VALIDATION_ONLY_STATUS = "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"


class OlympicsOrchestratorInputAdapterV003Error(ValueError):
    """A V003 validation, lineage, projection, or authorization boundary failed."""


def adapter_implementation_identity(root: Path) -> str:
    """Bind V003 lineage and exact validator, adapter, and CLI bytes."""
    paths = (root / VALIDATOR_PATH, root / MODULE_PATH, root / CLI_PATH)
    if any(not path.is_file() for path in paths):
        raise OlympicsOrchestratorInputAdapterV003Error(
            "V003 adapter implementation file missing"
        )
    return canonical_hash({
        "v003_contract_identity": CONTRACT_IDENTITY,
        "v003_adapter_contract_identity": V003_ADAPTER_CONTRACT_IDENTITY,
        "v002_contract_identity": V002_CONTRACT_IDENTITY,
        "v002_adapter_implementation_identity": V002_ADAPTER_IMPLEMENTATION_IDENTITY,
        "validator_sha256": hashlib.sha256(paths[0].read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(paths[1].read_bytes()).hexdigest(),
        "cli_sha256": hashlib.sha256(paths[2].read_bytes()).hexdigest(),
    })


def adapt_manifest(value: Mapping[str, object], root: Path) -> AdaptedInput:
    """Validate V003 and project through unchanged V002 into unchanged V001."""
    if value.get("schema_name") != SCHEMA:
        raise OlympicsOrchestratorInputAdapterV003Error(
            "V003 mode rejects V001, V002, and other non-V003 input"
        )
    validated = validate_manifest(
        value,
        v003_adapter_implementation_identity=adapter_implementation_identity(root),
        bindings=executor_bindings(),
        canonical_mode=True,
    )
    return adapt_v002_manifest(project_to_v002(validated), root)


def future_run_identity(value: Mapping[str, object], root: Path) -> str:
    """Compute the future one-use binding without creating authorization."""
    implementation = adapter_implementation_identity(root)
    validated = validate_manifest(
        value,
        v003_adapter_implementation_identity=implementation,
        bindings=executor_bindings(),
        canonical_mode=True,
    )
    return canonical_hash({
        "source_commit_identity": validated["source_commit_identity"],
        "v001_orchestrator_contract_identity": ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": V001_IMPLEMENTATION_IDENTITY,
        "v002_contract_identity": validated["v002_contract_identity"],
        "v002_adapter_implementation_identity": (
            V002_ADAPTER_IMPLEMENTATION_IDENTITY
        ),
        "v003_contract_identity": validated["v003_contract_identity"],
        "v003_adapter_implementation_identity": implementation,
        "v004_scoring_bundle_identity": V004_BUNDLE_IDENTITY,
        "v003_manifest_identity": validated["manifest_identity"],
    })


def validation_only(value: Mapping[str, object], root: Path) -> bytes:
    """Return an identity report while preserving the frozen closed gate."""
    adapted = adapt_manifest(value, root)
    inherited_report = json.loads(
        validate_v002_only(project_to_v002(value), root)
    )
    if inherited_report.get("status") != VALIDATION_ONLY_STATUS:
        raise OlympicsOrchestratorInputAdapterV003Error(
            "inherited V001 authorization boundary changed"
        )
    report = {
        "schema": "aml.professional-strategy-olympics.v003-validation-only-report",
        "status": VALIDATION_ONLY_STATUS,
        "v002_contract_identity": value["v002_contract_identity"],
        "v003_contract_identity": CONTRACT_IDENTITY,
        "v003_manifest_identity": manifest_identity(value),
        "v003_adapter_identity": adapter_implementation_identity(root),
        "v001_projected_manifest_identity": adapted.v001_manifest[
            "manifest_identity"
        ],
        "future_run_identity": future_run_identity(value, root),
        "entrant_count": len(value["entrants"]),
        "trial_authorized": False,
        "trial_executed": False,
        "authorization_created": False,
        "artifact_published": False,
        "ranking_exists": False,
        "aggregate_score_exists": False,
        "performance_result_exists": False,
    }
    return canonical_json(report)
