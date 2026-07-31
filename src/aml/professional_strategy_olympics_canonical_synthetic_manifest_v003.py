"""Immutable loader and reconciler for the canonical V003 synthetic input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from aml.professional_strategy_olympics_input_manifest_v003 import (
    SCHEMA,
    VERSION,
    manifest_identity,
    strict_json,
    validate_manifest,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    adapter_implementation_identity,
    future_run_identity,
    validation_only,
)
from aml.professional_strategy_olympics_orchestrator_v001 import executor_bindings
from aml.winner_archetype_contracts import canonical_json


MANIFEST_PATH = (
    "config/professional_strategy_olympics_canonical_synthetic_manifest_v003.json"
)
SOURCE_COMMIT = "4ec2e1e38c716351d9d592e6dc8ca0d99ee805b8"
FIXTURE_IDENTITY = (
    "7093c039bb2bb06ed63fad08238e6ac6594db2747f9b975822c1f7dc9d30ddb7"
)
MANIFEST_IDENTITY = (
    "fc16aed963b8c6aac0b0e01affea29148cb4d396d8dfa3e5398d68671e4788b0"
)
VALIDATION_ONLY_STATUS = "VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED"
ENTRANT_IDS = (
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


class CanonicalSyntheticManifestV003Error(ValueError):
    """The committed canonical input or its validation boundary changed."""


def validate_canonical_manifest(
    value: Mapping[str, object], root: Path
) -> dict[str, object]:
    """Reconcile a candidate against V003 and the frozen canonical identity."""
    manifest = validate_manifest(
        value,
        v003_adapter_implementation_identity=adapter_implementation_identity(root),
        bindings=executor_bindings(),
        canonical_mode=True,
    )
    expected = {
        "schema_name": SCHEMA,
        "schema_version": VERSION,
        "classification": "canonical_synthetic_trial_input_not_authorized",
        "source_commit_identity": SOURCE_COMMIT,
        "fixture_identity": FIXTURE_IDENTITY,
        "manifest_identity": MANIFEST_IDENTITY,
        "entrant_count": 10,
        "synthetic_only": True,
        "opened_stages": ["discovery"],
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise CanonicalSyntheticManifestV003Error(
                f"canonical {field} binding changed"
            )
    entrants = manifest["entrants"]
    if not isinstance(entrants, list) or tuple(
        entrant.get("entrant_id") for entrant in entrants
        if isinstance(entrant, Mapping)
    ) != ENTRANT_IDS:
        raise CanonicalSyntheticManifestV003Error("canonical entrant order changed")
    if any(
        not isinstance(entrant, Mapping)
        or entrant.get("trade_count") != 1
        or len(entrant.get("trades", ())) != 1
        for entrant in entrants
    ):
        raise CanonicalSyntheticManifestV003Error("canonical trade counts changed")
    if manifest_identity(manifest) != MANIFEST_IDENTITY:
        raise CanonicalSyntheticManifestV003Error("manifest identity changed")
    return manifest


def load_canonical_manifest(root: Path) -> dict[str, object]:
    """Load and independently bind the sole canonical V003 synthetic input."""
    return validate_canonical_manifest(strict_json(root / MANIFEST_PATH), root)


def validation_report(root: Path) -> dict[str, object]:
    """Validate without authorization, artifact publication, or execution."""
    manifest = load_canonical_manifest(root)
    report = json.loads(validation_only(manifest, root))
    if report.get("status") != VALIDATION_ONLY_STATUS:
        raise CanonicalSyntheticManifestV003Error("authorization boundary changed")
    return report


def integrity_report(root: Path) -> bytes:
    """Return a deterministic non-performance integrity report."""
    manifest = load_canonical_manifest(root)
    report = validation_report(root)
    return canonical_json({
        "classification": "canonical_synthetic_input_integrity_not_result",
        "entrant_count": manifest["entrant_count"],
        "entrant_ids": list(ENTRANT_IDS),
        "execution_count": 0,
        "fixture_identity": FIXTURE_IDENTITY,
        "future_run_identity": future_run_identity(manifest, root),
        "manifest_identity": MANIFEST_IDENTITY,
        "source_commit_identity": SOURCE_COMMIT,
        "status": report["status"],
        "total_trade_count": sum(
            entrant["trade_count"] for entrant in manifest["entrants"]
        ),
        "trial_authorized": False,
        "trial_executed": False,
    })
