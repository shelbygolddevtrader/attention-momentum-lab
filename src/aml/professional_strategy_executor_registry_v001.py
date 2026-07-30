"""Identity-bound registry for synthetic Olympics V002 executors."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from aml.professional_strategy_executor_models_v001 import (
    EXECUTOR_PROTOCOL_IDENTITY,
    EvaluationInput,
    EvaluationResult,
)
from aml.professional_strategy_executors_v001 import (
    EXECUTOR_FUNCTIONS,
    EXECUTOR_IDENTITIES,
    STRATEGIES,
    evaluate,
)
from aml.professional_strategy_indicators_v001 import (
    SHARED_INDICATOR_IMPLEMENTATION_IDENTITY,
)
from aml.professional_strategy_lifecycle_v001 import (
    SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY,
    V002_PROTOCOL_IDENTITY,
)
from aml.professional_strategy_olympics_v002 import STRATEGY_IDS
from aml.winner_archetype_contracts import canonical_hash, canonical_json


REGISTRY_VERSION = "professional-strategy-executor-registry-v001"


def _module_identity() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _registry_payload() -> dict[str, object]:
    return {
        "schema": "aml.professional-strategy-executor-registry.v001",
        "version": REGISTRY_VERSION,
        "v002_protocol_identity": V002_PROTOCOL_IDENTITY,
        "strategy_ids": list(STRATEGY_IDS),
        "strategy_identities": [
            STRATEGIES[strategy_id]["strategy_identity"] for strategy_id in STRATEGY_IDS
        ],
        "executor_identities": [EXECUTOR_IDENTITIES[item] for item in STRATEGY_IDS],
        "executor_protocol_identity": EXECUTOR_PROTOCOL_IDENTITY,
        "shared_indicator_implementation_identity": (
            SHARED_INDICATOR_IMPLEMENTATION_IDENTITY
        ),
        "shared_lifecycle_implementation_identity": (
            SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY
        ),
        "authorization": "synthetic_only_empirical_blocked",
    }


EXECUTOR_REGISTRY_IDENTITY = canonical_hash(_registry_payload())


def implementation_bundle() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "aml.professional-strategy-executors.bundle.v001",
        "version": "professional-strategy-executors-bundle-v001",
        "v002_protocol_identity": V002_PROTOCOL_IDENTITY,
        "executor_protocol_identity": EXECUTOR_PROTOCOL_IDENTITY,
        "shared_indicator_implementation_identity": (
            SHARED_INDICATOR_IMPLEMENTATION_IDENTITY
        ),
        "shared_lifecycle_implementation_identity": (
            SHARED_LIFECYCLE_IMPLEMENTATION_IDENTITY
        ),
        "executor_registry_identity": EXECUTOR_REGISTRY_IDENTITY,
        "registry_module_identity": _module_identity(),
        "executors": [
            {
                "strategy_id": strategy_id,
                "strategy_identity": STRATEGIES[strategy_id]["strategy_identity"],
                "executor_identity": EXECUTOR_IDENTITIES[strategy_id],
            }
            for strategy_id in STRATEGY_IDS
        ],
        "empirical_readiness": {
            "status": "blocked_synthetic_implementation_only",
            "empirical_data_accessed": False,
            "discovery_authorized": False,
            "tournament_authorized": False,
            "validation_authorized": False,
            "holdout_authorized": False,
            "paper_authorized": False,
            "live_authorized": False,
        },
    }
    payload["implementation_bundle_identity"] = canonical_hash(payload)
    readiness = {
        "implementation_bundle_identity": payload["implementation_bundle_identity"],
        **payload["empirical_readiness"],
    }
    payload["blocked_empirical_readiness_identity"] = canonical_hash(readiness)
    return payload


def canonical_bundle_bytes() -> bytes:
    return canonical_json(implementation_bundle())


def executor_registry() -> Mapping[str, object]:
    if tuple(EXECUTOR_FUNCTIONS) != STRATEGY_IDS:
        raise RuntimeError("executor registry order no longer matches frozen V002")
    if len(set(EXECUTOR_IDENTITIES.values())) != 10:
        raise RuntimeError("executor identities must be unique")
    return MappingProxyType(dict(EXECUTOR_FUNCTIONS))


def execute(strategy_id: str, value: EvaluationInput) -> EvaluationResult:
    executor_registry()
    return evaluate(strategy_id, value)
