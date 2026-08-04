"""Immutable specification campaign for one preregistered benchmark hypothesis.

This module is intentionally specification-only.  It validates and publishes
the exact prospective rules needed by a later implementation milestone, but it
cannot evaluate bars, create proposals, execute a strategy, or inspect outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from aml.benchmark_hypothesis_library_v001 import load_library
from aml.benchmark_implementation_campaign_v001 import load_config as load_readiness
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json


SCHEMA_VERSION = "aml.benchmark-specification-campaign.v001"
CAMPAIGN_VERSION = "benchmark-specification-campaign-v001"
MANIFEST_SCHEMA = "aml.benchmark-specification-campaign.manifest.v001"
SELECTED_ID = "opening-drive-first-pullback-v001"
CAMPAIGN_ID = "benchmark-specification-campaign-v001"
SOURCE_COMMIT = "a63eab2ea149ff547e6e60f68d9b9b7317ed0680"
CREATED_AT = "2026-08-04T18:00:00Z"
CAMPAIGN_SOURCE_PATHS = {
    "scripts/validate_benchmark_specification_campaign_v001.py",
    "src/aml/benchmark_specification_campaign_v001.py",
}
MAX_JSON_BYTES = 4_000_000
HASH = re.compile(r"^[0-9a-f]{64}$")
GIT_OID = re.compile(r"^[0-9a-f]{40}$")

CONFIG_FIELDS = {
    "schema_version",
    "campaign_version",
    "campaign_id",
    "created_at",
    "source_commit",
    "dependencies",
    "selected_hypothesis",
    "selection_policy",
    "selection_review",
    "specification",
    "policy",
    "campaign_source_sha256",
    "selection_identity",
    "specification_identity",
    "campaign_identity",
}


class BenchmarkSpecificationCampaignError(ValueError):
    """The specification campaign or its immutable evidence is invalid."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.benchmark-executable-specification.v001",
    "specification_version": "opening-drive-first-pullback-long-v001",
    "strategy_id": SELECTED_ID,
    "direction": "long",
    "direction_scope_rule": (
        "This specification exercises the long arm explicitly permitted by the "
        "revision-1 hypothesis. The short arm remains unspecified and unauthorized."
    ),
    "market_assumption": (
        "A directional opening drive with broad participation can reveal informed "
        "demand before slower traders complete their orders."
    ),
    "economic_mechanism": (
        "The first controlled retracement may supply liquidity for continuation "
        "while preserving the drive's information content."
    ),
    "bar_and_session": {
        "calendar": "XNYS point-in-time session calendar",
        "timezone": "America/New_York",
        "bar_interval": "one minute",
        "bar_semantics": "left-labeled complete interval [t,t+1 minute)",
        "regular_session_start": "09:30",
        "scheduled_close": "calendar supplied; no implicit 16:00 default",
        "setup_source_bar_first": "09:35",
        "setup_source_bar_last": "11:30",
        "intended_entry_first": "09:36",
        "intended_entry_last": "11:31",
        "early_close_liquidation": "fifth completed bar before scheduled close",
        "normal_liquidation": "15:55 completed-bar close",
    },
    "data_dependencies": {
        "required_fields": [
            "adjustment_identity",
            "close",
            "corporate_action_manifest_identity",
            "feed",
            "halt_manifest_identity",
            "high",
            "low",
            "open",
            "security_id",
            "session",
            "source_manifest_identity",
            "symbol",
            "timestamp",
            "volume",
        ],
        "feed": "sip",
        "calendar": "point-in-time XNYS",
        "corporate_actions": "complete point-in-time split-adjustment lineage",
        "halts": "complete point-in-time halt intervals [start,resume)",
        "allowed_history": "current symbol-session prefix only",
        "future_data": "prohibited except the next exact bar open exposed after signal",
    },
    "numeric_semantics": {
        "representation": "IEEE-754 binary64",
        "operation_rounding": "round to nearest, ties to even",
        "comparison_tolerance": "none; apply the stated strict or inclusive operator directly",
        "median_20": (
            "sort ascending and take the arithmetic mean of the values at zero-based "
            "indices 9 and 10"
        ),
        "cent_rounding_input": (
            "convert binary64 to its shortest round-trip decimal string before decimal "
            "floor or ceiling quantization to 0.01"
        ),
    },
    "indicators": {
        "atr20": (
            "Wilder ATR20 over completed regular-session bars; first true range is "
            "high-low and each later true range is max(high-low, abs(high-prior close), "
            "abs(low-prior close)); seed is the arithmetic mean of the first 20 true "
            "ranges, then ATR=(19*prior_ATR+TR)/20; reset after every timestamp gap and "
            "session boundary; current trigger bar included"
        ),
        "local_five_bar_volume_ratio": (
            "For candidate impulse-end index i, require 25 consecutive completed bars "
            "i-24 through i; divide mean volume of i-4 through i by median volume of "
            "i-24 through i-5; baseline must be positive"
        ),
        "opening_drive_return": "impulse_end_high / impulse_anchor_low - 1",
        "pullback_depth": (
            "(impulse_end_high - pullback_low) / "
            "(impulse_end_high - impulse_anchor_low)"
        ),
        "impulse_volume_mean": "arithmetic mean of impulse-end bar and prior four bars",
        "pullback_volume_mean": (
            "arithmetic mean from pullback-start bar through trigger bar inclusive"
        ),
    },
    "eligibility": {
        "session": "regular",
        "current_close_minimum_inclusive": 2.0,
        "current_close_maximum_inclusive": 500.0,
        "impulse_return_minimum_inclusive": 0.03,
        "impulse_volume_ratio_minimum_inclusive": 2.0,
        "pullback_depth_minimum_inclusive": 0.20,
        "pullback_depth_maximum_inclusive": 0.50,
        "pullback_duration_bars_minimum_inclusive": 2,
        "pullback_duration_bars_maximum_inclusive": 10,
        "maximum_entries_per_symbol_session": 1,
        "post_halt_signal_block_complete_bars": 5,
    },
    "setup": {
        "impulse_anchor": (
            "Scan completed bars from 09:31. Maintain the earliest running minimum low "
            "beginning at 09:30; replace the anchor only on a strictly lower low."
        ),
        "impulse_end": (
            "The earliest completed bar no later than 10:00 whose high is at least 3% "
            "above the then-current anchor low and whose local five-bar volume ratio "
            "is at least 2.0. The trigger bar is never an impulse candidate."
        ),
        "first_pullback_start": (
            "The earliest completed bar after impulse end whose low is strictly below "
            "the immediately preceding completed bar low."
        ),
        "pullback_membership": (
            "All completed bars from first-pullback start through the candidate trigger "
            "bar inclusive."
        ),
        "pullback_structure": (
            "Duration is 2 through 10 bars inclusive; depth is 0.20 through 0.50 "
            "inclusive; every pullback close is at or above the 50% retracement; every "
            "post-impulse low is at or above the impulse-anchor low; and pullback mean "
            "volume is strictly less than impulse mean volume."
        ),
        "trigger": (
            "The earliest eligible completed pullback bar that closes strictly above "
            "the immediately preceding completed bar high."
        ),
        "signal_timestamp": "exclusive end of the completed trigger bar",
    },
    "entry": {
        "intended_timestamp": "exactly the signal timestamp (next left-labeled minute)",
        "raw_price": "next exact completed-bar open",
        "cost_adjusted_price": "raw next-bar open multiplied by 1.001",
        "allowed_delay_bars": 0,
        "pre_entry_invalidation": [
            "entry timestamp outside the frozen entry window",
            "next bar halted",
            "next exact bar missing",
            "raw or cost-adjusted entry at or below rounded stop",
        ],
    },
    "stop_target_and_lifecycle": {
        "unrounded_stop": "pullback low minus 0.05 times ATR20 at trigger",
        "stop_rounding": "floor to the nearest cent",
        "target": "cost-adjusted entry plus 2 times initial per-share risk",
        "target_rounding": "ceiling to the nearest cent",
        "maximum_holding_complete_bars": 90,
        "same_bar_precedence": "gap stop, intrabar stop, gap target, intrabar target",
        "gap_through_stop": "exit at minimum of bar open and stop",
        "gap_through_target": "exit at maximum of bar open and target",
        "session_exit": (
            "Exit on the earlier of timeout or the 15:55 completed-bar close; on an "
            "early close use the fifth completed bar before scheduled close."
        ),
        "halt_exit": (
            "No entry while halted; an open position exits at the first executable "
            "post-halt bar under the same conservative precedence."
        ),
        "reentry": (
            "maximum one accepted entry per symbol-session; once prior-entry state "
            "contains this strategy, every later evaluation is no-signal"
        ),
        "post_rejection_evaluation": (
            "Only an accepted entry is recorded in prior-entry state. A no-signal, "
            "unavailable, or no-trade decision does not itself prohibit evaluation of a "
            "later bar against the same first pullback while all duration and time gates "
            "still pass."
        ),
        "shared_cost_model": {
            "adverse_friction_basis_points_per_side": 10,
            "commission_usd_per_share_per_order": 0.005,
            "minimum_commission_usd_per_order": 1.0,
        },
        "shared_risk_model": {
            "risk_budget_usd": 250.0,
            "requested_shares": (
                "floor(risk_budget_usd / (cost-adjusted entry - rounded stop)); "
                "whole shares only and zero shares is no-trade"
            ),
            "initial_capital_usd": 100000.0,
            "maximum_gross_exposure_fraction": 0.5,
            "maximum_concurrent_positions": 3,
            "daily_new_entry_loss_stop_fraction": 0.01,
            "portfolio_admission": (
                "apply the unchanged shared exposure, concurrency, and daily-loss gates; "
                "this specification may not override or reorder them"
            ),
        },
    },
    "event_ordering": [
        "validate all identities, provenance, calendar, halt, corporate-action, and bar integrity",
        "apply post-halt, price, and one-entry state gates",
        "calculate causal ATR and local-volume series from completed bars only",
        "select earliest eligible impulse and its earliest running-low anchor",
        "select first pullback and evaluate structural invalidations",
        "evaluate the earliest eligible trigger",
        "resolve the next exact bar and pre-entry invalidations",
        "round stop, apply entry friction, and calculate rounded fixed 2R target",
        "emit one immutable proposal or one terminal non-proposal decision",
    ],
    "rule_precedence": [
        "integrity_failure",
        "state_or_common_no_signal",
        "indicator_or_required_input_unavailable",
        "setup_absent_or_invalid_no_signal",
        "trigger_absent_no_signal",
        "pre_entry_no_trade_or_unavailable",
        "proposal",
    ],
    "tie_breaking": [
        "earliest eligible impulse-end timestamp",
        "earliest timestamp for equal running-minimum anchor lows",
        "earliest first-pullback start",
        "earliest eligible trigger timestamp",
    ],
    "missing_data_behavior": {
        "interpolation": "prohibited",
        "forward_fill": "prohibited",
        "unclassified_minute_gap": "integrity_failure",
        "halt_covered_gap": "ATR and consecutive indicators reset; unavailable until rewarmed",
        "missing_local_volume_window": "unavailable if a price-qualified impulse has no ratio and no later eligible impulse exists",
        "missing_atr20_at_trigger": "unavailable",
        "missing_next_exact_bar": "unavailable",
        "incomplete_provenance": "integrity_failure",
    },
    "integrity_expectations": [
        "timezone-aware America/New_York canonical minute timestamps",
        "strictly increasing unique bars from scheduled open",
        "finite positive OHLC with valid ranges and nonnegative volume",
        "one security identity, symbol, and session per evaluation",
        "no bar ending after the decision cutoff",
        "complete halt coverage and immutable halt provenance",
        "complete corporate-action coverage and valid adjustment lineage",
        "exact next-bar security, symbol, session, timestamp, feed, and provenance binding",
        "zero look-ahead beyond the explicitly isolated next-bar open",
    ],
    "decision_states": {
        "proposal": ["all gates pass and positive initial risk exists"],
        "no_signal": [
            "common eligibility or state gate fails",
            "impulse or pullback absent",
            "pullback duration, depth, structure, anchor, or volume contraction fails",
            "continuation trigger absent",
        ],
        "unavailable": [
            "ATR20 unavailable",
            "required local-volume ratio unavailable",
            "next exact bar missing",
        ],
        "no_trade": [
            "next bar halted",
            "entry outside window",
            "nonpositive entry risk",
            "target not above entry",
        ],
        "integrity_failure": ["any integrity expectation is violated"],
    },
    "invalidation_conditions": [
        "pullback depth below 0.20 or above 0.50",
        "pullback duration below 2 or above 10 completed bars",
        "any pullback close strictly below the 50% retracement",
        "any post-impulse low strictly below the impulse-anchor low",
        "pullback mean volume greater than or equal to impulse mean volume",
        "next raw or cost-adjusted entry at or below rounded stop",
        "required input unavailable",
    ],
    "expected_failure_modes": [
        "modeled costs and adverse selection exceed the gross effect",
        "opening drive is temporary auction pressure",
        "pullback structure is definition-sensitive",
        "qualifying events are too infrequent for a defensible conclusion",
        "halt or corporate-action exclusions materially limit coverage",
    ],
    "implementation_boundary": {
        "status": "ready_for_separate_implementation_milestone",
        "implementation_authorized": False,
        "discovery_authorized": False,
        "dataset_authorized": False,
        "reference_strategy_id": "first_pullback_continuation_long_v002",
        "reference_strategy_identity": "1013ee3c7c57ae6cb5326aa22e09ba980dfbe4bc2815fb40c0596db4f09b7c82",
        "reference_executor_identity": "9affc9b5496498c3c1371674af8b7b0e83a4a5d68672e869827cbf35a2babacd",
        "required_next_evidence": [
            "authorized dataset binding",
            "conformance evidence",
            "implementation binding",
            "registered executor",
        ],
    },
    "claim_boundary": (
        "Prospective design evidence only. This specification contains no market "
        "outcomes and supports no claim of edge, profitability, validation eligibility, "
        "Olympics eligibility, deployment readiness, or capital eligibility."
    ),
}


SELECTION_REVIEW: list[dict[str, object]] = [
    {
        "library_entry_id": "failed-volume-breakout-reversal-v001",
        "semantic_fit": "partial",
        "new_assumption_codes": ["breakout-side", "balance-target", "level-definition"],
        "reused_capability_count": 2,
        "selected": False,
        "reason": "Existing reuse covers only a downside reclaim and does not freeze the hypothesis's two-sided breakout level or balance target.",
    },
    {
        "library_entry_id": "first-half-hour-to-close-momentum-v001",
        "semantic_fit": "indicator_only",
        "new_assumption_codes": ["entry-clock", "market-volume-state", "return-threshold", "stop-and-exit"],
        "reused_capability_count": 1,
        "selected": False,
        "reason": "Only elapsed return is reusable; clock, eligibility, risk, and exit semantics remain open.",
    },
    {
        "library_entry_id": "high-relative-volume-price-continuation-v001",
        "semantic_fit": "indicator_only",
        "new_assumption_codes": ["cumulative-volume-baseline", "directional-move", "liquidity-threshold", "persistence-exit"],
        "reused_capability_count": 1,
        "selected": False,
        "reason": "A relative-volume primitive exists, but cumulative baseline, move, liquidity, and persistence rules remain unspecified.",
    },
    {
        "library_entry_id": SELECTED_ID,
        "semantic_fit": "exact_existing_contract_analogue",
        "new_assumption_codes": [],
        "reused_capability_count": 1,
        "selected": True,
        "reason": "The frozen long first-pullback contract resolves every numeric, timing, tie, missing-data, and lifecycle rule while staying inside an explicitly permitted direction.",
    },
    {
        "library_entry_id": "opening-range-expansion-continuation-v001",
        "semantic_fit": "multiple_contract_choices",
        "new_assumption_codes": ["opening-range-duration", "range-invalidation-reference"],
        "reused_capability_count": 2,
        "selected": False,
        "reason": "Two reusable ORB durations and two allowed invalidation references create unresolved experiment choices.",
    },
    {
        "library_entry_id": "opening-range-failed-breakout-reversal-v001",
        "semantic_fit": "none",
        "new_assumption_codes": ["breakout-excursion", "internal-target", "opening-range-duration", "renewed-failure-rule"],
        "reused_capability_count": 0,
        "selected": False,
        "reason": "No existing evaluator freezes its range, excursion, internal target, or renewed-failure semantics.",
    },
    {
        "library_entry_id": "overnight-gap-continuation-with-volume-v001",
        "semantic_fit": "partial",
        "new_assumption_codes": ["gap-fill-invalidation", "opening-hold", "relative-volume-definition"],
        "reused_capability_count": 1,
        "selected": False,
        "reason": "Gap-and-go reuse adds premarket-high and consolidation rules while the library hypothesis leaves opening hold and gap-fill invalidation open.",
    },
    {
        "library_entry_id": "overnight-gap-exhaustion-reversal-v001",
        "semantic_fit": "none",
        "new_assumption_codes": ["countertrend-reference", "exhaustion-test", "gap-closure-target", "opening-extreme"],
        "reused_capability_count": 0,
        "selected": False,
        "reason": "No existing evaluator freezes the exhaustion test, early reference, opening extreme, or gap-closure target.",
    },
    {
        "library_entry_id": "overnight-inventory-reversal-to-vwap-v001",
        "semantic_fit": "partial",
        "new_assumption_codes": ["failure-to-extend", "overnight-return", "target-precedence"],
        "reused_capability_count": 2,
        "selected": False,
        "reason": "VWAP reuse does not resolve overnight return, failure-to-extend, or prior-close-versus-VWAP target precedence.",
    },
    {
        "library_entry_id": "volatility-expansion-breakout-v001",
        "semantic_fit": "indicator_only",
        "new_assumption_codes": ["compression-window", "expansion-definition", "range-boundary", "relative-volume-threshold"],
        "reused_capability_count": 1,
        "selected": False,
        "reason": "ATR exists, but compression, expansion, boundary, and confirmation definitions remain open.",
    },
    {
        "library_entry_id": "vwap-deviation-mean-reversion-v001",
        "semantic_fit": "partial",
        "new_assumption_codes": ["deviation-normalizer", "failure-to-extend", "liquidity-threshold", "partial-convergence-target"],
        "reused_capability_count": 2,
        "selected": False,
        "reason": "VWAP reuse does not resolve normalized deviation, failure-to-extend, liquidity, or convergence semantics.",
    },
]


def _strict_json(path: Path) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise BenchmarkSpecificationCampaignError("JSON contains duplicate keys")
            result[key] = item
        return result

    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
        raise BenchmarkSpecificationCampaignError("JSON is missing, unsafe, or oversized")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                BenchmarkSpecificationCampaignError(f"non-finite JSON value:{item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkSpecificationCampaignError("JSON is malformed") from exc
    if not isinstance(value, dict):
        raise BenchmarkSpecificationCampaignError("JSON root must be an object")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 30_000:
        raise BenchmarkSpecificationCampaignError(f"{field} is invalid")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BenchmarkSpecificationCampaignError(f"{field} has invalid Unicode") from exc
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
        raise BenchmarkSpecificationCampaignError(f"{field} has prohibited Unicode")
    return value


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise BenchmarkSpecificationCampaignError(f"{field} is not a SHA-256 identity")
    return value


def specification_identity(specification: Mapping[str, object]) -> str:
    return canonical_hash(
        {
            "domain": "aml.benchmark-executable-specification.v001",
            "specification": dict(specification),
        }
    )


def selection_identity(review: list[dict[str, object]]) -> str:
    return canonical_hash(
        {"domain": "aml.benchmark-specification-selection.v001", "review": review}
    )


def campaign_identity(config: Mapping[str, object]) -> str:
    projection = {key: config[key] for key in sorted(config) if key != "campaign_identity"}
    return canonical_hash(
        {"domain": "aml.benchmark-specification-campaign.config.v001", "campaign": projection}
    )


def manifest_identity(manifest: Mapping[str, object]) -> str:
    projection = {key: manifest[key] for key in sorted(manifest) if key not in {"manifest_identity", "verified"}}
    return canonical_hash(
        {"domain": "aml.benchmark-specification-campaign.manifest.v001", "manifest": projection}
    )


def _verify_dependency_file(root: Path, value: Mapping[str, object], name: str) -> Path:
    if set(value) != {"identity", "path", "sha256"}:
        raise BenchmarkSpecificationCampaignError(f"{name} dependency schema changed")
    relative = Path(_text(value["path"], f"{name} path"))
    if relative.is_absolute() or ".." in relative.parts:
        raise BenchmarkSpecificationCampaignError(f"{name} path is unsafe")
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise BenchmarkSpecificationCampaignError(f"{name} dependency is unavailable")
    if hashlib.sha256(path.read_bytes()).hexdigest() != _identity(value["sha256"], f"{name} sha256"):
        raise BenchmarkSpecificationCampaignError(f"{name} dependency hash changed")
    _identity(value["identity"], f"{name} identity")
    return path


def validate_config(
    config: Mapping[str, object],
    *,
    library_path: Path,
    readiness_path: Path,
    repository_root: Path,
) -> dict[str, object]:
    if not isinstance(config, Mapping) or set(config) != CONFIG_FIELDS:
        raise BenchmarkSpecificationCampaignError("campaign config schema changed")
    if config["schema_version"] != SCHEMA_VERSION or config["campaign_version"] != CAMPAIGN_VERSION:
        raise BenchmarkSpecificationCampaignError("campaign version changed")
    if config["campaign_id"] != CAMPAIGN_ID:
        raise BenchmarkSpecificationCampaignError("campaign_id changed")
    if (
        not isinstance(config["source_commit"], str)
        or not GIT_OID.fullmatch(config["source_commit"])
        or config["source_commit"] != SOURCE_COMMIT
    ):
        raise BenchmarkSpecificationCampaignError("source_commit changed")
    try:
        created = datetime.fromisoformat(_text(config["created_at"], "created_at"))
    except ValueError as exc:
        raise BenchmarkSpecificationCampaignError("created_at is malformed") from exc
    if (
        created.tzinfo is None
        or created.utcoffset() is None
        or created.utcoffset().total_seconds() != 0
        or created.isoformat().replace("+00:00", "Z") != config["created_at"]
        or config["created_at"] != CREATED_AT
    ):
        raise BenchmarkSpecificationCampaignError("created_at must be canonical UTC")
    dependencies = config["dependencies"]
    if not isinstance(dependencies, Mapping) or set(dependencies) != {"implementation_campaign", "hypothesis_library"}:
        raise BenchmarkSpecificationCampaignError("dependency set changed")
    library_dependency = dependencies["hypothesis_library"]
    readiness_dependency = dependencies["implementation_campaign"]
    if not isinstance(library_dependency, Mapping) or not isinstance(readiness_dependency, Mapping):
        raise BenchmarkSpecificationCampaignError("dependency is malformed")
    if _verify_dependency_file(repository_root, library_dependency, "library").resolve() != library_path.resolve():
        raise BenchmarkSpecificationCampaignError("library path substitution")
    if _verify_dependency_file(repository_root, readiness_dependency, "readiness").resolve() != readiness_path.resolve():
        raise BenchmarkSpecificationCampaignError("readiness path substitution")
    library = load_library(library_path)
    readiness = load_readiness(readiness_path, library)
    if library_dependency["identity"] != library["library_identity"]:
        raise BenchmarkSpecificationCampaignError("library identity changed")
    if readiness_dependency["identity"] != readiness["campaign_identity"]:
        raise BenchmarkSpecificationCampaignError("readiness identity changed")
    entries = {item["library_entry_id"]: item for item in library["hypotheses"]}
    assessments = {item["library_entry_id"]: item for item in readiness["assessments"]}
    specification_ready = sorted(
        entry_id for entry_id, item in assessments.items()
        if item["canonical_classification"] == "BLOCKED_MISSING_EXECUTABLE_SPECIFICATION"
    )
    if specification_ready != sorted(item["library_entry_id"] for item in SELECTION_REVIEW):
        raise BenchmarkSpecificationCampaignError("specification-ready cohort changed")
    if config["selection_review"] != SELECTION_REVIEW:
        raise BenchmarkSpecificationCampaignError("selection review changed")
    if sum(bool(item["selected"]) for item in SELECTION_REVIEW) != 1:
        raise BenchmarkSpecificationCampaignError("selection must contain exactly one winner")
    selected = config["selected_hypothesis"]
    if not isinstance(selected, Mapping) or set(selected) != {
        "assessment_identity", "directional_arm", "framework_hypothesis_identity",
        "library_entry_id", "registration_identity", "revision",
    }:
        raise BenchmarkSpecificationCampaignError("selected hypothesis schema changed")
    entry = entries[SELECTED_ID]
    assessment = assessments[SELECTED_ID]
    expected_selected = {
        "assessment_identity": assessment["assessment_identity"],
        "directional_arm": "long",
        "framework_hypothesis_identity": entry["framework_hypothesis_identity"],
        "library_entry_id": SELECTED_ID,
        "registration_identity": entry["registration_identity"],
        "revision": entry["revision"],
    }
    if dict(selected) != expected_selected or "long" not in entry["directional_scope"]:
        raise BenchmarkSpecificationCampaignError("selected hypothesis binding changed")
    if config["specification"] != FROZEN_SPECIFICATION:
        raise BenchmarkSpecificationCampaignError("executable specification changed")
    expected_policy = {
        "classification": "SPECIFIED_READY_FOR_IMPLEMENTATION",
        "empirical_outcome_access_count": 0,
        "implementation_count": 0,
        "optimization_count": 0,
        "protected_boundary_access_count": 0,
        "semantic_change_requires_child_identity": True,
        "short_arm_authorized": False,
        "strategy_execution_count": 0,
        "write_once_artifacts": True,
    }
    if config["policy"] != expected_policy:
        raise BenchmarkSpecificationCampaignError("campaign policy changed")
    expected_selection_policy = {
        "ordered_criteria": [
            "fewest new assumptions",
            "closest semantic fit to an existing frozen contract",
            "greatest reuse of existing data, indicators, execution, and lifecycle",
            "fewest unresolved tie or missing-data semantics",
            "lexicographically smallest library entry id as final tie-break",
        ],
        "outcome_information_permitted": False,
        "performance_ranking_permitted": False,
    }
    if config["selection_policy"] != expected_selection_policy:
        raise BenchmarkSpecificationCampaignError("selection policy changed")
    source_hashes = config["campaign_source_sha256"]
    if (
        not isinstance(source_hashes, Mapping)
        or set(source_hashes) != CAMPAIGN_SOURCE_PATHS
    ):
        raise BenchmarkSpecificationCampaignError("campaign source hashes missing")
    for raw_path, digest in source_hashes.items():
        relative = Path(_text(raw_path, "campaign source path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise BenchmarkSpecificationCampaignError("campaign source path is unsafe")
        source = repository_root / relative
        if not source.is_file() or source.is_symlink():
            raise BenchmarkSpecificationCampaignError("campaign source is unavailable")
        if hashlib.sha256(source.read_bytes()).hexdigest() != _identity(digest, "campaign source digest"):
            raise BenchmarkSpecificationCampaignError("campaign source hash changed")
    if config["selection_identity"] != selection_identity(SELECTION_REVIEW):
        raise BenchmarkSpecificationCampaignError("selection identity changed")
    if config["specification_identity"] != specification_identity(FROZEN_SPECIFICATION):
        raise BenchmarkSpecificationCampaignError("specification identity changed")
    if config["campaign_identity"] != campaign_identity(config):
        raise BenchmarkSpecificationCampaignError("campaign identity changed")
    return dict(config)


def load_config(
    path: Path, *, library_path: Path, readiness_path: Path, repository_root: Path
) -> dict[str, object]:
    return validate_config(
        _strict_json(path),
        library_path=library_path,
        readiness_path=readiness_path,
        repository_root=repository_root,
    )


def build_config(
    *,
    repository_root: Path,
    source_commit: str,
    created_at: str,
) -> dict[str, object]:
    """Build the one canonical config from already-frozen repository inputs."""

    if source_commit != SOURCE_COMMIT or created_at != CREATED_AT:
        raise BenchmarkSpecificationCampaignError(
            "bootstrap lineage or timestamp differs from the frozen campaign"
        )

    library_path = repository_root / "config/benchmark_hypothesis_library_v001.json"
    readiness_path = repository_root / "config/benchmark_implementation_campaign_v001.json"
    library = load_library(library_path)
    readiness = load_readiness(readiness_path, library)
    entry = next(
        item for item in library["hypotheses"]
        if item["library_entry_id"] == SELECTED_ID
    )
    assessment = next(
        item for item in readiness["assessments"]
        if item["library_entry_id"] == SELECTED_ID
    )
    config: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "campaign_version": CAMPAIGN_VERSION,
        "campaign_id": CAMPAIGN_ID,
        "created_at": created_at,
        "source_commit": source_commit,
        "dependencies": {
            "hypothesis_library": {
                "identity": library["library_identity"],
                "path": "config/benchmark_hypothesis_library_v001.json",
                "sha256": hashlib.sha256(library_path.read_bytes()).hexdigest(),
            },
            "implementation_campaign": {
                "identity": readiness["campaign_identity"],
                "path": "config/benchmark_implementation_campaign_v001.json",
                "sha256": hashlib.sha256(readiness_path.read_bytes()).hexdigest(),
            },
        },
        "selected_hypothesis": {
            "assessment_identity": assessment["assessment_identity"],
            "directional_arm": "long",
            "framework_hypothesis_identity": entry["framework_hypothesis_identity"],
            "library_entry_id": SELECTED_ID,
            "registration_identity": entry["registration_identity"],
            "revision": entry["revision"],
        },
        "selection_policy": {
            "ordered_criteria": [
                "fewest new assumptions",
                "closest semantic fit to an existing frozen contract",
                "greatest reuse of existing data, indicators, execution, and lifecycle",
                "fewest unresolved tie or missing-data semantics",
                "lexicographically smallest library entry id as final tie-break",
            ],
            "outcome_information_permitted": False,
            "performance_ranking_permitted": False,
        },
        "selection_review": SELECTION_REVIEW,
        "specification": FROZEN_SPECIFICATION,
        "policy": {
            "classification": "SPECIFIED_READY_FOR_IMPLEMENTATION",
            "empirical_outcome_access_count": 0,
            "implementation_count": 0,
            "optimization_count": 0,
            "protected_boundary_access_count": 0,
            "semantic_change_requires_child_identity": True,
            "short_arm_authorized": False,
            "strategy_execution_count": 0,
            "write_once_artifacts": True,
        },
        "campaign_source_sha256": {
            path: hashlib.sha256((repository_root / path).read_bytes()).hexdigest()
            for path in sorted(CAMPAIGN_SOURCE_PATHS)
        },
        "selection_identity": selection_identity(SELECTION_REVIEW),
        "specification_identity": specification_identity(FROZEN_SPECIFICATION),
        "campaign_identity": "",
    }
    config["campaign_identity"] = campaign_identity(config)
    return config


def _report(config: Mapping[str, object]) -> bytes:
    spec_id = config["specification_identity"]
    campaign_id = config["campaign_identity"]
    lines = [
        "# Benchmark Specification Campaign V001 verification",
        "",
        "- Selected hypothesis: `opening-drive-first-pullback-v001`",
        "- Selected directional arm: `long` (already permitted by Library V001)",
        "- Classification: `SPECIFIED_READY_FOR_IMPLEMENTATION`",
        f"- Specification identity: `{spec_id}`",
        f"- Campaign identity: `{campaign_id}`",
        "- Specification-ready hypotheses reviewed: 11",
        "- Implementations created: 0",
        "- Strategy executions: 0",
        "- Empirical outcomes accessed: 0",
        "",
        "The selected hypothesis has a complete prospective executable specification.",
        "It has no implementation, dataset authorization, conformance evidence, or",
        "registered executor in this milestone and therefore cannot execute discovery.",
        "The short arm is not specified and may not be inferred.",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def _artifact_payloads(config: Mapping[str, object]) -> dict[str, bytes]:
    return {
        "selection_review.json": canonical_json(
            {
                "schema_version": "aml.benchmark-specification-selection.v001",
                "selection_identity": config["selection_identity"],
                "selected_library_entry_id": SELECTED_ID,
                "review": config["selection_review"],
            }
        ),
        "specification.json": canonical_json(
            {
                "schema_version": "aml.benchmark-executable-specification-artifact.v001",
                "specification": config["specification"],
                "specification_identity": config["specification_identity"],
            }
        ),
        "VERIFICATION_REPORT.md": _report(config),
    }


def _build_manifest(config: Mapping[str, object], payloads: Mapping[str, bytes]) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "campaign_version": CAMPAIGN_VERSION,
        "campaign_identity": config["campaign_identity"],
        "selection_identity": config["selection_identity"],
        "specification_identity": config["specification_identity"],
        "selected_library_entry_id": SELECTED_ID,
        "classification": "SPECIFIED_READY_FOR_IMPLEMENTATION",
        "specification_ready_cohort_count": 11,
        "selected_count": 1,
        "implementation_count": 0,
        "strategy_execution_count": 0,
        "empirical_outcome_access_count": 0,
        "protected_boundary_access_count": 0,
        "files": [
            {"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for name, payload in sorted(payloads.items())
        ],
        "manifest_identity": "",
        "verified": True,
    }
    manifest["manifest_identity"] = manifest_identity(manifest)
    return manifest


def publish_campaign(
    *, config_path: Path, library_path: Path, readiness_path: Path,
    output_root: Path, repository_root: Path,
) -> dict[str, object]:
    if output_root.exists() or output_root.is_symlink():
        raise BenchmarkSpecificationCampaignError("output already exists; publication is write-once")
    lowered = output_root.as_posix().casefold()
    if any(token in lowered for token in ("holdout", "validation", "extension", "forward")):
        raise BenchmarkSpecificationCampaignError("protected boundary in output path")
    config = load_config(
        config_path, library_path=library_path, readiness_path=readiness_path,
        repository_root=repository_root,
    )
    payloads = _artifact_payloads(config)
    manifest = _build_manifest(config, payloads)
    parent = output_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=parent))
    try:
        for name, payload in payloads.items():
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        (temporary / "manifest.json").write_bytes(canonical_json(manifest))
        os.rename(temporary, output_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return verify_campaign(
        output_root=output_root, config_path=config_path, library_path=library_path,
        readiness_path=readiness_path, repository_root=repository_root,
    )


def verify_campaign(
    *, output_root: Path, config_path: Path, library_path: Path,
    readiness_path: Path, repository_root: Path,
) -> dict[str, object]:
    config = load_config(
        config_path, library_path=library_path, readiness_path=readiness_path,
        repository_root=repository_root,
    )
    if not output_root.is_dir() or output_root.is_symlink():
        raise BenchmarkSpecificationCampaignError("campaign evidence is unavailable")
    expected_payloads = _artifact_payloads(config)
    expected_manifest = _build_manifest(config, expected_payloads)
    manifest = _strict_json(output_root / "manifest.json")
    if manifest != expected_manifest:
        raise BenchmarkSpecificationCampaignError("manifest content changed")
    expected_names = set(expected_payloads) | {"manifest.json"}
    actual_names = {path.name for path in output_root.iterdir() if path.is_file()}
    if actual_names != expected_names or any(path.is_dir() or path.is_symlink() for path in output_root.iterdir()):
        raise BenchmarkSpecificationCampaignError("campaign file set changed")
    for name, payload in expected_payloads.items():
        if (output_root / name).read_bytes() != payload:
            raise BenchmarkSpecificationCampaignError(f"artifact changed:{name}")
    if (output_root / "manifest.json").read_bytes() != canonical_json(expected_manifest):
        raise BenchmarkSpecificationCampaignError("manifest is not canonical")
    return dict(manifest)
