"""Opening Range Expansion Continuation V001 research milestone.

This module owns a prospectively frozen child specification, exact reference
binding, conformance evidence, executor registration, and a claim-limited
exploratory adapter.  Frozen evaluators, lifecycle, publication, discovery,
Olympics, and governance code remain unchanged.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
from zoneinfo import ZoneInfo

from aml.benchmark_candidate_opening_range_expansion_v001 import (
    CHILD_HYPOTHESIS_ID,
    CHILD_REVISION,
    CHILD_VERSION,
    EXECUTOR_REGISTRY,
    PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    PARENT_LIBRARY_ENTRY_ID,
    PARENT_REGISTRATION_IDENTITY,
    REFERENCE_EXECUTOR_IDENTITY,
    REFERENCE_LIFECYCLE_IDENTITY,
    REFERENCE_STRATEGY_ID,
    REFERENCE_STRATEGY_IDENTITY,
    conformance_inputs,
    evaluate_opening_range_expansion,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
    verify_reference_binding,
)
from aml.benchmark_executable_specification_runtime_v001 import (
    ConformanceCase,
    dataset_authorization_identity,
    file_hashes,
    implementation_binding_artifact,
    run_conformance,
    validate_dataset_authorization,
    verify_implementation_binding,
)
from aml.benchmark_hypothesis_library_v001 import framework_artifacts, load_library
from aml.benchmark_strategy_research_v001 import (
    canonical_hash,
    canonical_json,
    create_observation,
    create_triage,
    make_artifact,
    validate_artifact,
)
from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.exploratory_research_mode_v001 import (
    CLAIM_CEILING,
    EVIDENCE_CLASS,
    LABELS,
    MANIFEST_SCHEMA,
    LoadedPartition,
    _next_open,
    _output_path,
    _partition,
    _reject_prohibited_keys,
    _result_payload,
    _sha256,
    _strict_json,
    verify_bundle,
)
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HistoricalClockVolume,
)
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError


ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
SCHEMA = "aml.opening-range-expansion-continuation.v001"
MILESTONE_VERSION = "opening-range-expansion-continuation-v001"
EVIDENCE_MANIFEST_SCHEMA = "aml.opening-range-expansion-evidence-manifest.v001"
EXPLORATORY_SUMMARY_SCHEMA = "aml.exploratory-research-summary.v001"
CANDIDATE_SPECIFIC_LABEL = "NOT EMPIRICAL EVIDENCE"
CANDIDATE_SPECIFIC_LABELS = (CANDIDATE_SPECIFIC_LABEL,)
CANDIDATE_PROHIBITED_CLAIM_SCHEMA = (
    "aml.opening-range-expansion-prohibited-claims.v001"
)
CANDIDATE_REQUIRED_INVENTORY_SCHEMA = (
    "aml.opening-range-expansion-required-inventory.v001"
)
CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA = (
    "aml.opening-range-expansion-structured-observation.v001"
)
CANDIDATE_FREE_TEXT_DOMAIN_SCHEMA = (
    "aml.opening-range-expansion-free-text-domain.v001"
)
CANDIDATE_PROHIBITED_FIELDS = frozenset(
    {
        "alpha",
        "annualized_return",
        "authorized_empirical_evidence",
        "average_loss",
        "average_win",
        "beta",
        "broker_ready",
        "buy_recommendation",
        "cagr",
        "calmar",
        "capital_allocation",
        "capital_allocation_recommended",
        "capital_efficiency",
        "capital_eligible",
        "confidence_interval",
        "deployment_ready",
        "drawdown",
        "edge",
        "empirical_edge",
        "empirical_evidence",
        "evidence_of_edge",
        "expectancy",
        "expected_value",
        "gross_pnl",
        "holdout_passed",
        "information_ratio",
        "invest",
        "live_trading_ready",
        "loss",
        "loss_rate",
        "max_drawdown",
        "maximum_drawdown",
        "net_pnl",
        "out_of_sample_passed",
        "paper_trading_ready",
        "payoff_ratio",
        "pnl",
        "p_value",
        "position_size_recommendation",
        "production_ready",
        "profit",
        "profit_factor",
        "profitability",
        "profitable",
        "ready_for_production",
        "realized_pnl",
        "recommended_capital",
        "recommendation",
        "repeatable_edge",
        "return",
        "returns",
        "risk_adjusted_return",
        "robust",
        "robustness",
        "sell_recommendation",
        "sharpe",
        "sharpe_ratio",
        "sortino",
        "sortino_ratio",
        "statistical_significance",
        "statistically_significant",
        "total_return",
        "trade_recommendation",
        "t_stat",
        "unrealized_pnl",
        "validated",
        "validation_passed",
        "volatility",
        "win_rate",
    }
)
CANDIDATE_PROHIBITED_KEY_TOKENS = frozenset(
    {
        "alpha",
        "beta",
        "calmar",
        "capital",
        "cagr",
        "deployment",
        "drawdown",
        "economic",
        "edge",
        "empirical",
        "expectancy",
        "holdout",
        "invest",
        "live",
        "loss",
        "paper",
        "payoff",
        "pnl",
        "production",
        "profit",
        "profitability",
        "profitable",
        "recommendation",
        "return",
        "robust",
        "robustness",
        "sharpe",
        "sortino",
        "statistical",
        "statistically",
        "validated",
        "validation",
        "volatility",
        "win",
    }
)
CANDIDATE_CLAIM_CONTEXT_KEYS = frozenset(
    {
        "assessment",
        "claim",
        "claims",
        "classification",
        "conclusion",
        "decision",
        "evidence",
        "metrics",
        "performance",
        "recommendation",
        "readiness",
        "result",
        "status",
    }
)
CANDIDATE_PROHIBITED_AFFIRMATIVE_PHRASES = frozenset(
    {
        "allocate capital",
        "broker ready",
        "capital allocation is recommended",
        "capital allocation recommended",
        "capital efficient",
        "capital eligible",
        "deployment ready",
        "empirical edge",
        "evidence of edge",
        "evidence of profitability",
        "has an empirical edge",
        "holdout passed",
        "live trading ready",
        "paper trading ready",
        "production ready",
        "profitability confirmed",
        "profitable",
        "ready for production",
        "statistically significant",
        "is robust",
        "is validated",
        "positive expectancy",
        "repeatable edge",
        "validation passed",
        "validated edge",
    }
)
CANDIDATE_NEGATIVE_CLAIM_ALLOWANCES = {
    ("claim_flags", "capital_eligible"): False,
    ("claim_flags", "empirical_evidence"): False,
    ("claim_flags", "holdout"): False,
    ("claim_flags", "production"): False,
    ("claim_flags", "validation"): False,
    ("economic_metrics_published",): False,
    ("empirical_conclusion_authorized",): False,
    ("policy", "profitability_metrics_published"): False,
}
CANDIDATE_PROSPECTIVE_DESIGN_ALLOWANCES = frozenset(
    {
        ("02-child-hypothesis.json", "payload.expected_edge"),
        ("04-specification.json", "payload.rules.opening_range.realized_volatility_proxy"),
    }
)
CANDIDATE_PERMITTED_NEGATIVE_CLAIM_STRINGS = frozenset(
    (*LABELS, CANDIDATE_SPECIFIC_LABEL, EVIDENCE_CLASS)
)
CANDIDATE_OBSERVATION_TYPES = frozenset(
    {
        "ARTIFACT_VERIFICATION",
        "DATA_AVAILABILITY",
        "DATA_QUALITY",
        "DETERMINISM",
        "EVALUATOR_PATH",
        "IMPLEMENTATION_BEHAVIOR",
        "INTEGRITY_BEHAVIOR",
        "LIFECYCLE_BEHAVIOR",
        "MISSING_INPUT",
        "NO_SIGNAL_REASON",
        "PARSER_PATH",
        "RECONCILIATION",
        "UNAVAILABLE_REASON",
    }
)
CANDIDATE_OBSERVATION_OUTCOMES = frozenset(
    {
        "ABSENT",
        "ACCEPTED_AS_DIAGNOSTIC",
        "BYTE_IDENTICAL",
        "EXERCISED",
        "INTEGRITY_FAILURE",
        "MALFORMED",
        "MATCHED",
        "MISSING",
        "NOT_EXERCISED",
        "NO_SIGNAL",
        "PRESENT",
        "RECONCILED",
        "REJECTED",
        "UNAVAILABLE",
    }
)
CANDIDATE_OBSERVATION_SUBJECTS = frozenset(
    {
        "breakout_condition",
        "candidate_result",
        "edge_case_parser_branch",
        "frozen_evaluator",
        "frozen_evaluator_and_lifecycle",
        "historical_spread_input",
        "proposal_lifecycle",
        "range_invalidation",
        "relative_volume_threshold",
        "required_source_field",
        "same_clock_volume_warmup",
        "validation_input_field",
        "validation_outcome_access",
        "empirical_edge_claim",
        "production_flag",
    }
)
CANDIDATE_OBSERVATION_REASON_CODES = frozenset(
    {
        "BRANCH_COVERAGE",
        "CONDITION_NOT_MET",
        "COUNTS_RECONCILED",
        "DETERMINISM_CONFIRMED",
        "FIELD_NOT_PRESENT",
        "FROZEN_COMPONENT_REUSED",
        "INPUT_UNAVAILABLE",
        "INSUFFICIENT_WARMUP",
        "INTEGRITY_REJECTED",
        "NO_EMPIRICAL_CLAIM",
        "NO_PROPOSAL_EMITTED",
        "NO_VALIDATION_ACCESS",
        "PROPOSAL_EMITTED",
    }
)
CANDIDATE_OBSERVATION_ASSERTION_SCOPE = "ENGINEERING_ONLY"
CANDIDATE_OBSERVATION_DETAILS = {
    (
        "IMPLEMENTATION_BEHAVIOR",
        "validation_input_field",
        "ABSENT",
        "FIELD_NOT_PRESENT",
    ): "The validation field was absent from the input.",
    (
        "PARSER_PATH",
        "edge_case_parser_branch",
        "EXERCISED",
        "BRANCH_COVERAGE",
    ): "The edge-case parser branch was exercised.",
    (
        "IMPLEMENTATION_BEHAVIOR",
        "validation_outcome_access",
        "ABSENT",
        "NO_VALIDATION_ACCESS",
    ): "No validation outcome was accessed.",
    (
        "IMPLEMENTATION_BEHAVIOR",
        "empirical_edge_claim",
        "ABSENT",
        "NO_EMPIRICAL_CLAIM",
    ): "No empirical edge claim was made.",
    (
        "IMPLEMENTATION_BEHAVIOR",
        "production_flag",
        "ABSENT",
        "FIELD_NOT_PRESENT",
    ): "The production flag was not present.",
    (
        "EVALUATOR_PATH",
        "frozen_evaluator",
        "NOT_EXERCISED",
        "NO_PROPOSAL_EMITTED",
    ): "The frozen evaluator emitted no proposal in the bounded exercise.",
    (
        "EVALUATOR_PATH",
        "frozen_evaluator",
        "EXERCISED",
        "PROPOSAL_EMITTED",
    ): "The frozen evaluator emitted at least one proposal in the bounded exercise.",
    (
        "IMPLEMENTATION_BEHAVIOR",
        "frozen_evaluator_and_lifecycle",
        "MATCHED",
        "FROZEN_COMPONENT_REUSED",
    ): "Frozen downstream evaluator and lifecycle code were reused unchanged.",
    (
        "DATA_AVAILABILITY",
        "same_clock_volume_warmup",
        "UNAVAILABLE",
        "INSUFFICIENT_WARMUP",
    ): "Same-clock volume warm-up was incomplete.",
    (
        "NO_SIGNAL_REASON",
        "breakout_condition",
        "NO_SIGNAL",
        "CONDITION_NOT_MET",
    ): "The breakout condition was not met.",
    (
        "RECONCILIATION",
        "candidate_result",
        "RECONCILED",
        "COUNTS_RECONCILED",
    ): "The candidate result reconciled with the run summary.",
    (
        "MISSING_INPUT",
        "required_source_field",
        "ABSENT",
        "FIELD_NOT_PRESENT",
    ): "A required source field was absent from the input.",
    (
        "INTEGRITY_BEHAVIOR",
        "proposal_lifecycle",
        "INTEGRITY_FAILURE",
        "INTEGRITY_REJECTED",
    ): "The integrity path rejected one or more diagnostic evaluations.",
}
CANDIDATE_IMPLEMENTATION_NOTE_CODES = frozenset(
    {
        "EVALUATOR_BINDING_VERIFIED",
        "EVALUATOR_INVOCATION_REFUSED",
        "FROZEN_COMPONENTS_REUSED",
        "MISSING_INPUT_NOT_SUBSTITUTED",
    }
)
CANDIDATE_WARNING_CODES = frozenset(
    {
        "CONTAMINATED_PARENT_DATASET",
        "POINT_IN_TIME_CORPORATE_ACTION_LINEAGE_UNPROVEN",
        "PROVIDER_FEED_IDENTITY_NOT_ECHOED",
        "WRITTEN_LICENSE_RETENTION_EVIDENCE_MISSING",
    }
)
CANDIDATE_DECISION_STATUSES = frozenset(
    {"integrity_failure", "no_signal", "no_trade", "proposal", "unavailable"}
)
CANDIDATE_DECISION_REASON_KEYS = frozenset(
    {
        "integrity_failure:executor_integrity_rejected",
        "no_signal:breakout_close_not_above_range",
        "no_signal:cooldown_active",
        "no_signal:maximum_entries_reached",
        "no_signal:outside_observation_window",
        "no_signal:post_halt_signal_block",
        "no_signal:price_above_maximum",
        "no_signal:price_below_minimum",
        "no_signal:range_invalidated",
        "no_signal:relative_volume_below_threshold",
        "no_trade:entry_outside_window",
        "no_trade:halt_before_entry",
        "no_trade:nonpositive_risk",
        "no_trade:target_not_above_entry",
        "proposal:none",
        "unavailable:missing_next_bar",
        "unavailable:required_range_bar_missing",
        "unavailable:unavailable_same_clock_history",
    }
)
CANDIDATE_MISSING_FIELD_CODES = frozenset(
    {"next_bar", "opening_range_bar", "same_clock_volume_history"}
)
_CAMEL_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_WORD_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALPHANUMERIC = re.compile(r"[^0-9A-Za-z]+")
_TOKEN_ALIASES = {
    "drawdowns": "drawdown",
    "edges": "edge",
    "efficiencies": "efficiency",
    "intervals": "interval",
    "losses": "loss",
    "profits": "profit",
    "ratios": "ratio",
    "recommendations": "recommendation",
    "returns": "return",
    "wins": "win",
}
HASH = re.compile(r"^[0-9a-f]{64}$")
LIBRARY_IDENTITY = "6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003"
DATASET_FINGERPRINT = "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d"
DATASET_MANIFEST_SHA256 = (
    "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b"
)
DATASET_VINTAGE = "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001"
SYNTHETIC_RELATIVE_PATH = (
    "tests/fixtures/opening_range_expansion_continuation_v001/orb_synthetic.csv"
)
SOURCE_PATHS = (
    "scripts/run_opening_range_expansion_continuation_v001.py",
    "src/aml/benchmark_candidate_opening_range_expansion_v001.py",
    "src/aml/opening_range_expansion_continuation_v001.py",
)
FROZEN_DOWNSTREAM_PATHS = (
    "src/aml/discovery_screen_v001.py",
    "src/aml/exploratory_research_mode_v001.py",
    "src/aml/professional_strategy_executor_models_v001.py",
    "src/aml/professional_strategy_executors_v001.py",
    "src/aml/professional_strategy_indicators_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
)
WARMUP_SESSIONS = (
    "2023-07-24",
    "2023-07-25",
    "2023-07-26",
    "2023-07-27",
    "2023-07-28",
    "2023-07-31",
    "2023-08-01",
    "2023-08-02",
    "2023-08-03",
    "2023-08-04",
    "2023-08-07",
    "2023-08-08",
    "2023-08-09",
    "2023-08-10",
    "2023-08-11",
    "2023-08-14",
    "2023-08-15",
    "2023-08-16",
    "2023-08-17",
    "2023-08-18",
)
EVALUATION_SESSIONS = (
    "2023-08-21",
    "2023-08-22",
    "2023-08-23",
    "2023-08-24",
    "2023-08-25",
)
SYMBOLS = ("AAPL", "AMD", "NVDA", "PLTR", "TSLA")

EVIDENCE_REQUIRED_ROLES = {
    "01-observation.json": "observation",
    "02-child-hypothesis.json": "child_hypothesis",
    "03-triage.json": "triage",
    "04-specification.json": "specification",
    "05-preregistration.json": "preregistration",
    "06-implementation-binding.json": "implementation_binding",
    "07-conformance.json": "conformance_evidence",
    "08-executor-registration.json": "executor_registration",
}
EVIDENCE_ARTIFACT_TYPES = {
    "01-observation.json": "observation",
    "02-child-hypothesis.json": "hypothesis",
    "03-triage.json": "triage",
    "04-specification.json": "specification",
    "05-preregistration.json": "preregistration",
    "06-implementation-binding.json": "implementation_binding",
    "07-conformance.json": "conformance",
    "08-executor-registration.json": "implementation_binding",
}
EXPLORATORY_RESULT_PATH = f"01-{CHILD_HYPOTHESIS_ID}.json"
EXPLORATORY_REQUIRED_ROLES = {
    EXPLORATORY_RESULT_PATH: "candidate_result",
    "run.json": "exploratory_run",
    "summary.json": "candidate_summary",
}
RESULT_REQUIRED_FIELDS = frozenset(
    {
        "candidate_artifact_role",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_specific_labels",
        "candidate_structured_observation_contract_identity",
        "claim_ceiling",
        "claim_flags",
        "confidence_warnings",
        "config_identity",
        "counts",
        "dataset_binding_identity",
        "decision_reason_counts",
        "decision_status_counts",
        "evidence_class",
        "evidence_manifest_identity",
        "hypothesis",
        "identity",
        "implementation_binding_identity",
        "implementation_notes",
        "integrity_diagnostic_count",
        "labels",
        "missing_data_summary",
        "obvious_anomalies",
        "observation_count",
        "observation_identities",
        "partition_count",
        "partition_inspection",
        "qualitative_observations",
        "run_identity",
        "schema_version",
        "status",
    }
)
SUMMARY_REQUIRED_FIELDS = frozenset(
    {
        "candidate_artifact_role",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_specific_labels",
        "candidate_structured_observation_contract_identity",
        "claim_ceiling",
        "config_identity",
        "counts",
        "dataset_binding_identity",
        "decision_reason_counts",
        "decision_status_counts",
        "economic_metrics_published",
        "empirical_conclusion_authorized",
        "evidence_binding",
        "evidence_class",
        "identity",
        "labels",
        "observation_count",
        "observation_identities",
        "partition_bindings",
        "result_identity",
        "result_path",
        "run_identity",
        "schema_version",
        "source_sha256",
    }
)
RUN_REQUIRED_FIELDS = frozenset(
    {
        "candidate_artifact_role",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_specific_labels",
        "candidate_structured_observation_contract_identity",
        "claim_ceiling",
        "config_identity",
        "counts",
        "dataset_binding_identity",
        "economic_metrics_published",
        "empirical_conclusion_authorized",
        "evidence_class",
        "evidence_manifest_identity",
        "identity",
        "labels",
        "observation_count",
        "observation_identities",
        "result_references",
        "run_identity",
        "schema_version",
        "summary_reference",
    }
)


class OpeningRangeExpansionError(ValueError):
    """A specification, binding, conformance, or exploratory invariant failed."""


FROZEN_SPECIFICATION: dict[str, object] = {
    "schema_version": "aml.opening-range-expansion-executable-specification.v001",
    "strategy_id": CHILD_HYPOTHESIS_ID,
    "strategy_version": CHILD_VERSION,
    "parent_library_entry_id": PARENT_LIBRARY_ENTRY_ID,
    "parent_framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
    "revision": CHILD_REVISION,
    "ambiguity_resolution": {
        "action": "new_child_hypothesis",
        "reason": (
            "The immutable parent leaves direction, range duration, thresholds, and "
            "lifecycle values unresolved; the child adopts one already-frozen contract "
            "without modifying the parent."
        ),
        "source_supported_interpretation": (
            "Exact semantic alias of five_minute_orb_long_v002; no alternative rule."
        ),
    },
    "market_assumption": (
        "A completed five-minute opening range summarizes early price discovery; a "
        "participation-confirmed upside close beyond that frozen range can continue."
    ),
    "economic_mechanism": (
        "The range break may trigger stops and attract directional participation."
    ),
    "direction": "long_only",
    "session": {
        "calendar": "XNYS",
        "segment": "regular",
        "bar_interval": "left_labeled_[t,t+1_minute)",
        "scheduled_open": "09:30 America/New_York",
        "normal_scheduled_close": "16:00 America/New_York",
    },
    "opening_range": {
        "duration_complete_bars": 5,
        "bar_labels": ["09:30", "09:31", "09:32", "09:33", "09:34"],
        "complete_at": "09:35",
        "high": "maximum unrounded high of the exact five bars",
        "low": "minimum unrounded low of the exact five bars",
        "equal_extreme_tie": "earliest timestamp",
        "realized_volatility_proxy": (
            "unrounded range high minus unrounded range low; recorded through the "
            "bound high/low snapshots and not used as an additional eligibility gate"
        ),
    },
    "eligibility": {
        "decision_close_minimum": 2.0,
        "decision_close_maximum": 500.0,
        "post_halt_signal_blocked": True,
        "maximum_entries_per_symbol_session": 2,
        "cooldown_complete_bars": 15,
    },
    "expansion": {
        "definition": "completed decision-bar close strictly above unrounded range high",
        "observation_window": "09:35 through 10:59 inclusive",
        "range_invalidation": (
            "any post-range completed close below unrounded range low before trigger"
        ),
    },
    "volume_confirmation": {
        "indicator": "same_clock_volume_median20_sessions_v002",
        "history": (
            "twenty most recent prior eligible complete non-early-close non-halt sessions"
        ),
        "baseline": "median volume at the identical minute label",
        "ratio": "decision-bar volume divided by baseline",
        "minimum_ratio_inclusive": 1.5,
        "point_in_time_rule": "only sessions strictly before the decision session",
    },
    "trigger": {
        "rule": (
            "first completed eligible post-range bar satisfying expansion and volume"
        ),
        "signal_timestamp": "decision bar end",
        "tie_breaking": "earliest signal timestamp then immutable strategy identity",
    },
    "entry": {
        "rule": "exact next complete bar raw open",
        "entry_window": "09:36 through 11:00 inclusive",
        "adverse_friction_basis_points": 10,
        "pre_entry_invalidation": "raw or cost-adjusted entry at or below rounded stop",
    },
    "stop": {
        "rule": "fixed opening range low",
        "rounding": "floor to one cent",
    },
    "target": {
        "rule": "cost-adjusted entry plus two times initial per-share risk",
        "rounding": "ceil to one cent",
    },
    "lifecycle": {
        "maximum_complete_bars": 120,
        "session_liquidation": (
            "close of 120th held bar or 15:55 bar close, with early-close fifth-bar-before-close, "
            "whichever occurs first"
        ),
        "event_precedence": (
            "gap stop, intrabar stop, gap target, intrabar target, timeout, session liquidation"
        ),
        "gap_through": (
            "long stop exits at min(open,stop); long target exits at max(open,target)"
        ),
        "commission": "$0.005 per share per order with $1 minimum per order",
    },
    "missing_data": {
        "missing_range_bar": "unavailable:required_range_bar_missing",
        "fewer_than_20_eligible_same_clock_observations": (
            "unavailable:unavailable_same_clock_history"
        ),
        "missing_next_bar": "unavailable:missing_next_bar",
        "no_fabrication_or_forward_fill": True,
    },
    "integrity": {
        "nonfinite_or_invalid_ohlcv": "raise ExecutorIntegrityError",
        "duplicate_or_nonmonotonic_timestamp": "raise ExecutorIntegrityError",
        "opening_range_timestamp_mismatch": (
            "raise ExecutorIntegrityError:orb:range_timestamp_integrity"
        ),
        "lookahead": "only bars ending at or before decision cutoff plus next raw open",
    },
    "decision_states": ["integrity_failure", "no_signal", "no_trade", "proposal", "unavailable"],
    "expected_failure_modes": [
        "modeled costs and adverse selection exceed any gross effect",
        "range break is a liquidity sweep",
        "same-clock volume history is incomplete",
        "volume confirmation arrives after price exhaustion",
    ],
    "claim_boundary": (
        "exploratory diagnostics only; no empirical, profitability, validation, holdout, "
        "production, or capital conclusion"
    ),
    "reference_contract": {
        "strategy_id": REFERENCE_STRATEGY_ID,
        "strategy_identity": REFERENCE_STRATEGY_IDENTITY,
        "executor_identity": REFERENCE_EXECUTOR_IDENTITY,
        "lifecycle_identity": REFERENCE_LIFECYCLE_IDENTITY,
    },
}


def specification_identity() -> str:
    return canonical_hash(
        {
            "domain": "aml.opening-range-expansion-specification.v001",
            "specification": FROZEN_SPECIFICATION,
        }
    )


def candidate_structured_observation_contract() -> dict[str, object]:
    """Return the closed engineering-observation schema."""

    detail_templates = [
        {
            "observation_type": signature[0],
            "subject": signature[1],
            "outcome": signature[2],
            "reason_code": signature[3],
            "details": details,
        }
        for signature, details in sorted(CANDIDATE_OBSERVATION_DETAILS.items())
    ]
    return {
        "schema_version": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
        "required_fields": [
            "assertion_scope",
            "details",
            "identity",
            "observation_type",
            "outcome",
            "reason_code",
            "subject",
        ],
        "assertion_scopes": [CANDIDATE_OBSERVATION_ASSERTION_SCOPE],
        "observation_types": sorted(CANDIDATE_OBSERVATION_TYPES),
        "outcomes": sorted(CANDIDATE_OBSERVATION_OUTCOMES),
        "subjects": sorted(CANDIDATE_OBSERVATION_SUBJECTS),
        "reason_codes": sorted(CANDIDATE_OBSERVATION_REASON_CODES),
        "detail_templates": detail_templates,
        "details_policy": {
            "maximum_utf8_bytes": 160,
            "maximum_sentences": 1,
            "rendering": "exact_template_for_structured_signature",
            "acceptance_authority": "structured_fields_only",
            "arbitrary_prose_permitted": False,
        },
        "prohibited_assertion_domains": [
            "benchmark outperformance",
            "capital eligibility or recommendation",
            "deployment or production readiness",
            "empirical edge",
            "holdout or out-of-sample success",
            "paper live or broker readiness",
            "profitability pnl or returns",
            "risk-adjusted performance",
            "statistical significance",
            "validation success",
        ],
    }


def candidate_structured_observation_contract_identity() -> str:
    return canonical_hash(
        {
            "domain": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
            "contract": candidate_structured_observation_contract(),
        }
    )


def _observation_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(set(value) - {"identity"})}
    return canonical_hash(
        {
            "domain": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
            "observation": projection,
        }
    )


def create_structured_observation(
    observation_type: str,
    subject: str,
    outcome: str,
    reason_code: str,
) -> dict[str, object]:
    """Create one exact, identity-bound engineering observation."""

    signature = (observation_type, subject, outcome, reason_code)
    details = CANDIDATE_OBSERVATION_DETAILS.get(signature)
    if details is None:
        raise OpeningRangeExpansionError("unknown structured observation signature")
    base = {
        "observation_type": observation_type,
        "subject": subject,
        "outcome": outcome,
        "reason_code": reason_code,
        "details": details,
        "assertion_scope": CANDIDATE_OBSERVATION_ASSERTION_SCOPE,
    }
    value = {**base, "identity": _observation_identity(base)}
    validate_structured_observation(value)
    return value


def validate_structured_observation(value: Mapping[str, object]) -> dict[str, object]:
    """Validate one observation without accepting arbitrary prose."""

    required = {
        "assertion_scope",
        "details",
        "identity",
        "observation_type",
        "outcome",
        "reason_code",
        "subject",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise OpeningRangeExpansionError("structured observation schema changed")
    observation_type = value.get("observation_type")
    subject = value.get("subject")
    outcome = value.get("outcome")
    reason_code = value.get("reason_code")
    if (
        observation_type not in CANDIDATE_OBSERVATION_TYPES
        or subject not in CANDIDATE_OBSERVATION_SUBJECTS
        or outcome not in CANDIDATE_OBSERVATION_OUTCOMES
        or reason_code not in CANDIDATE_OBSERVATION_REASON_CODES
        or value.get("assertion_scope") != CANDIDATE_OBSERVATION_ASSERTION_SCOPE
    ):
        raise OpeningRangeExpansionError("structured observation vocabulary changed")
    signature = (observation_type, subject, outcome, reason_code)
    expected_details = CANDIDATE_OBSERVATION_DETAILS.get(signature)
    details = value.get("details")
    if (
        not isinstance(details, str)
        or details != expected_details
        or len(details.encode("utf-8")) > 160
        or details.count(".") != 1
        or not details.endswith(".")
    ):
        raise OpeningRangeExpansionError("structured observation details changed")
    if value.get("identity") != _observation_identity(value):
        raise OpeningRangeExpansionError("structured observation identity changed")
    return dict(value)


def candidate_free_text_domain_contract() -> dict[str, object]:
    """Classify every accepted candidate string channel."""

    return {
        "schema_version": CANDIDATE_FREE_TEXT_DOMAIN_SCHEMA,
        "arbitrary_prose_permitted": False,
        "prohibited_claim_contract_identity": (
            candidate_prohibited_claim_contract_identity()
        ),
        "classes": {
            "bounded_engineering_details": {
                "paths": ["candidate_result.qualitative_observations[].details"],
                "contract_identity": candidate_structured_observation_contract_identity(),
            },
            "controlled_enum": {
                "paths": [
                    "*.candidate_artifact_role",
                    "candidate_result.implementation_notes[]",
                    "candidate_result.obvious_anomalies[]",
                    "candidate_result.status",
                    "structured_observation.assertion_scope",
                    "structured_observation.observation_type",
                    "structured_observation.outcome",
                    "structured_observation.reason_code",
                ]
            },
            "controlled_identifier": {
                "paths": [
                    "*.schema_version",
                    "candidate_result.decision_reason_counts.*",
                    "candidate_result.decision_status_counts.*",
                    "candidate_result.hypothesis.*",
                    "structured_observation.subject",
                ]
            },
            "exact_frozen_label": {
                "paths": ["*.candidate_specific_labels[]", "*.labels[]"]
            },
            "exact_frozen_text": {
                "paths": [
                    "configuration.*",
                    "evidence.01-observation.json.*",
                    "evidence.02-child-hypothesis.json.*",
                    "evidence.03-triage.json.*",
                    "evidence.04-specification.json.*",
                    "evidence.05-preregistration.json.*",
                ],
                "enforcement": "exact canonical reconstruction",
            },
            "hash_or_identity": {"pattern": "^[0-9a-f]{64}$"},
            "path": {
                "enforcement": "relative closed-inventory path without traversal or symlink"
            },
            "warning_or_reason_code": {
                "warning_codes": sorted(CANDIDATE_WARNING_CODES),
                "decision_statuses": sorted(CANDIDATE_DECISION_STATUSES),
                "decision_reason_keys": sorted(CANDIDATE_DECISION_REASON_KEYS),
                "missing_field_codes": sorted(CANDIDATE_MISSING_FIELD_CODES),
                "closed_registry": True,
            },
        },
        "publication_channels": [
            "configuration",
            "observation",
            "child hypothesis metadata",
            "triage",
            "specification metadata",
            "implementation binding",
            "conformance evidence",
            "executor registration",
            "evidence manifest",
            "candidate result",
            "candidate summary",
            "exploratory run",
            "exploratory manifest",
        ],
        "unrestricted_string_channels": [],
        "invariant": (
            "Human-readable engineering details are subordinate exact renderings of "
            "a closed structured observation and never control acceptance."
        ),
    }


def candidate_free_text_domain_contract_identity() -> str:
    return canonical_hash(
        {
            "domain": CANDIDATE_FREE_TEXT_DOMAIN_SCHEMA,
            "contract": candidate_free_text_domain_contract(),
        }
    )


def candidate_required_inventory_contract() -> dict[str, object]:
    """Return the closed, candidate-specific artifact-role contract."""

    return {
        "schema_version": CANDIDATE_REQUIRED_INVENTORY_SCHEMA,
        "closed_inventory": True,
        "optional_roles": [],
        "file_type": "canonical_json_only",
        "evidence": [
            {"path": path, "role": role, "cardinality": 1}
            for path, role in sorted(EVIDENCE_REQUIRED_ROLES.items())
        ],
        "exploratory_publication": [
            {"path": path, "role": role, "cardinality": 1}
            for path, role in sorted(EXPLORATORY_REQUIRED_ROLES.items())
        ],
        "manifest_roles": {
            "evidence": "evidence_manifest",
            "exploratory_publication": "exploratory_manifest",
        },
        "semantic_contracts": {
            "free_text_domain": candidate_free_text_domain_contract_identity(),
            "prohibited_claims": candidate_prohibited_claim_contract_identity(),
            "structured_observations": (
                candidate_structured_observation_contract_identity()
            ),
        },
        "exploratory_artifact_fields": {
            "candidate_result": sorted(RESULT_REQUIRED_FIELDS),
            "candidate_summary": sorted(SUMMARY_REQUIRED_FIELDS),
            "exploratory_run": sorted(RUN_REQUIRED_FIELDS),
        },
        "identity_and_hash_rules": [
            "every non-manifest artifact carries a canonical content identity",
            "every inventory record binds exact role path identity and sha256",
            "each required role and path occurs exactly once",
            "manifest identity binds the complete canonically ordered inventory",
        ],
        "lineage_graph": [
            "specification -> implementation_binding",
            "implementation_binding -> conformance_evidence",
            "conformance_evidence -> executor_registration",
            "evidence_manifest -> every evidence role",
            "exploratory_run -> candidate_result + candidate_summary",
            "candidate_summary -> candidate_result",
            "exploratory_manifest -> exploratory_run + candidate_result + candidate_summary",
        ],
        "invariant": (
            "A hash-consistent bundle is incomplete unless every required canonical "
            "role is present exactly once."
        ),
    }


def candidate_required_inventory_contract_identity() -> str:
    return canonical_hash(
        {
            "domain": CANDIDATE_REQUIRED_INVENTORY_SCHEMA,
            "contract": candidate_required_inventory_contract(),
        }
    )


def _config_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(set(value) - {"config_identity"})}
    return canonical_hash({"domain": SCHEMA, "config": projection})


def _historical_binding_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key] for key in sorted(set(value) - {"binding_identity"})
    }
    return canonical_hash(
        {"domain": "aml.exploratory-contaminated-dataset-binding.v001", "binding": projection}
    )


def finalize_config(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    synthetic = result["synthetic_dataset_authorization"]
    projection = {
        key: synthetic[key]
        for key in sorted(set(synthetic) - {"authorization_identity"})
    }
    synthetic["authorization_identity"] = dataset_authorization_identity(projection)
    historical = result["exploratory_dataset_binding"]
    historical["binding_identity"] = _historical_binding_identity(historical)
    result["config_identity"] = _config_identity(result)
    return result


def validate_config(value: Mapping[str, object], repository_root: Path) -> dict[str, object]:
    _reject_candidate_prohibited_claims(value, artifact_name="configuration.json")
    required = {
        "schema_version",
        "milestone_version",
        "parent",
        "child",
        "reference_contract",
        "specification_identity",
        "synthetic_dataset_authorization",
        "exploratory_dataset_binding",
        "source_paths",
        "frozen_downstream_paths",
        "policy",
        "config_identity",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_structured_observation_contract_identity",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise OpeningRangeExpansionError("campaign config schema is invalid")
    if (
        value["schema_version"] != SCHEMA
        or value["milestone_version"] != MILESTONE_VERSION
        or value["specification_identity"] != specification_identity()
        or value["candidate_prohibited_claim_contract_identity"]
        != candidate_prohibited_claim_contract_identity()
        or value["candidate_structured_observation_contract_identity"]
        != candidate_structured_observation_contract_identity()
        or value["candidate_free_text_domain_contract_identity"]
        != candidate_free_text_domain_contract_identity()
        or value["candidate_required_inventory_contract_identity"]
        != candidate_required_inventory_contract_identity()
    ):
        raise OpeningRangeExpansionError("campaign version or specification changed")
    if value["parent"] != {
        "library_entry_id": PARENT_LIBRARY_ENTRY_ID,
        "framework_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
        "registration_identity": PARENT_REGISTRATION_IDENTITY,
        "library_identity": LIBRARY_IDENTITY,
        "revision": 1,
    }:
        raise OpeningRangeExpansionError("parent identity changed")
    if value["child"] != {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": CHILD_REVISION,
        "version": CHILD_VERSION,
    }:
        raise OpeningRangeExpansionError("child identity changed")
    if value["reference_contract"] != FROZEN_SPECIFICATION["reference_contract"]:
        raise OpeningRangeExpansionError("reference contract changed")
    if value["source_paths"] != list(SOURCE_PATHS):
        raise OpeningRangeExpansionError("source inventory changed")
    if value["frozen_downstream_paths"] != list(FROZEN_DOWNSTREAM_PATHS):
        raise OpeningRangeExpansionError("frozen downstream inventory changed")
    if value["policy"] != {
        "empirical_execution_permitted": False,
        "exploratory_execution_permitted": True,
        "frozen_downstream_modified": False,
        "holdout_access_permitted": False,
        "optimization_count": 0,
        "paper_or_live_trading_permitted": False,
        "profitability_metrics_published": False,
        "validation_access_permitted": False,
    }:
        raise OpeningRangeExpansionError("claim policy changed")
    validate_dataset_authorization(
        value["synthetic_dataset_authorization"], repository_root=repository_root
    )
    historical = value["exploratory_dataset_binding"]
    required_historical = {
        "binding_kind",
        "dataset_fingerprint",
        "dataset_vintage",
        "manifest_relative_path",
        "manifest_sha256",
        "contamination_labels",
        "symbols",
        "warmup_sessions",
        "evaluation_sessions",
        "selection_rule",
        "empirical_authorized",
        "binding_identity",
    }
    if not isinstance(historical, Mapping) or set(historical) != required_historical:
        raise OpeningRangeExpansionError("exploratory dataset binding schema is invalid")
    if historical != {
        "binding_kind": "contaminated_exploratory_only_not_empirical_authorization",
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "dataset_vintage": DATASET_VINTAGE,
        "manifest_relative_path": (
            "manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json"
        ),
        "manifest_sha256": DATASET_MANIFEST_SHA256,
        "contamination_labels": list(LABELS),
        "symbols": list(SYMBOLS),
        "warmup_sessions": list(WARMUP_SESSIONS),
        "evaluation_sessions": list(EVALUATION_SESSIONS),
        "selection_rule": (
            "Five lexicographically fixed liquid symbols; first five XNYS sessions after "
            "the first twenty dataset sessions, selected before candidate outcomes."
        ),
        "empirical_authorized": False,
        "binding_identity": historical["binding_identity"],
    }:
        raise OpeningRangeExpansionError("exploratory dataset binding changed")
    if historical["binding_identity"] != _historical_binding_identity(historical):
        raise OpeningRangeExpansionError("exploratory dataset binding identity changed")
    if value["config_identity"] != _config_identity(value):
        raise OpeningRangeExpansionError("config identity is stale or tampered")
    verify_reference_binding()
    return dict(value)


def load_config(path: Path, repository_root: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_config(value, repository_root)
    if path.read_bytes() != canonical_json(value):
        raise OpeningRangeExpansionError("campaign config is not canonical JSON")
    return value


def _parent_entry(config: Mapping[str, object], library_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    library = load_library(library_path)
    if library["library_identity"] != config["parent"]["library_identity"]:
        raise OpeningRangeExpansionError("library identity changed")
    entry = next(
        (item for item in library["hypotheses"] if item["library_entry_id"] == PARENT_LIBRARY_ENTRY_ID),
        None,
    )
    if entry is None or any(
        entry[field] != config["parent"][field]
        for field in ("framework_hypothesis_identity", "registration_identity", "revision")
    ):
        raise OpeningRangeExpansionError("parent library entry changed")
    sources = {item["source_id"]: item for item in library["sources"]}
    observation, parent_hypothesis = framework_artifacts(entry, sources)
    if parent_hypothesis["identity"] != PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY:
        raise OpeningRangeExpansionError("parent framework identity does not reproduce")
    return observation, parent_hypothesis


def _child_payload() -> dict[str, object]:
    return {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": CHILD_REVISION,
        "parent_hypothesis_identity": PARENT_FRAMEWORK_HYPOTHESIS_IDENTITY,
        "title": "Five-minute long opening-range expansion continuation",
        "market_assumption": FROZEN_SPECIFICATION["market_assumption"],
        "mechanism": FROZEN_SPECIFICATION["economic_mechanism"],
        "required_evidence": [
            "exact five-minute opening range",
            "twenty-session point-in-time same-clock volume history",
            "next-bar lifecycle reconciliation",
        ],
        "expected_edge": (
            "A participation-confirmed upside range expansion may continue; exploratory "
            "exercise cannot determine whether this expectation is true."
        ),
        "invalidation_conditions": [
            "any post-range close below range low before trigger",
            "frozen reference identity changes",
            "point-in-time same-clock history is unavailable",
        ],
        "known_risks": [
            "adverse selection",
            "false breakout liquidity sweep",
            "modeled costs exceed any gross effect",
        ],
        "required_indicators": [
            "opening range high and low",
            "opening-range width realized-volatility proxy",
            "same-clock volume median over twenty prior eligible sessions",
        ],
        "expected_holding_period": "one to 120 complete one-minute bars",
        "expected_market_regime": "directional opening or expanding intraday volatility",
        "expected_failure_modes": list(FROZEN_SPECIFICATION["expected_failure_modes"]),
        "taxonomy": ["breakout", "opening", "volatility"],
        "contaminated_dataset_identities": [DATASET_FINGERPRINT],
        "multiple_testing_family": "opening-range-v001",
    }


def build_evidence(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    library_path: Path,
) -> dict[str, dict[str, object]]:
    validate_config(config, repository_root)
    _, parent_hypothesis = _parent_entry(config, library_path)
    observation = create_observation(
        {
            "observation_id": "opening-range-expansion-contract-derivation-v001",
            "title": "Prospective exact-contract derivation",
            "source_kind": "repository_contract_derivation_without_outcome_access",
            "source_references": [
                "config/benchmark_hypothesis_library_v001.json",
                "config/professional_strategy_olympics_v002.json",
            ],
            "source_dataset_identities": [],
            "observed_behavior": (
                "The parent is intentionally underspecified and the repository already "
                "contains one exact five-minute long ORB contract suitable for a child."
            ),
            "recorded_at": "2026-08-04T21:22:00Z",
        }
    )
    child_hypothesis = make_artifact(
        "hypothesis",
        _child_payload(),
        parent_identities=(parent_hypothesis["identity"], observation["identity"]),
    )
    triage = create_triage(
        {
            "hypothesis_identity": child_hypothesis["identity"],
            "disposition": "admit",
            "duplicate_signature": canonical_hash(
                {"domain": "aml.opening-range-expansion-triage.v001", "child": CHILD_HYPOTHESIS_ID}
            ),
            "duplicate_hypothesis_identities": [],
            "priority_vector": {
                "mechanism_plausibility": 2,
                "supporting_evidence": 1,
                "expected_frequency": 2,
                "data_readiness": 3,
                "distinctness": 1,
                "falsification_value": 3,
                "engineering_cost": 3,
                "contamination_risk": 1,
            },
            "reasons": [
                "Every executable rule is an exact alias of a frozen reference contract.",
                "The child resolves parent ambiguity before inspecting candidate outcomes.",
            ],
        },
        child_hypothesis,
    )
    specification = make_artifact(
        "specification",
        {
            "hypothesis_identity": child_hypothesis["identity"],
            "canonical_specification_identity": specification_identity(),
            "rules": FROZEN_SPECIFICATION,
        },
        parent_identities=(child_hypothesis["identity"], triage["identity"]),
    )
    preregistration = make_artifact(
        "preregistration",
        {
            "observation_identity": observation["identity"],
            "hypothesis_identity": child_hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "canonical_specification_identity": specification_identity(),
            "preregistered_at": "2026-08-04T21:22:00Z",
            "research_definitions_locked": True,
            "permitted_empirical_dataset_identities": [],
            "contaminated_exploratory_dataset_identities": [DATASET_FINGERPRINT],
            "claim_ceiling": "exploratory_engineering_diagnostics_only",
            "prohibited_boundaries": [
                "capital allocation",
                "forward validation",
                "holdout",
                "live trading",
                "paper trading",
                "profitability conclusions",
                "validation",
            ],
        },
        parent_identities=(
            observation["identity"],
            child_hypothesis["identity"],
            triage["identity"],
            specification["identity"],
        ),
    )
    binding = implementation_binding_artifact(
        repository_root=repository_root,
        preregistration=preregistration,
        specification=specification,
        implementation_callable=(
            "aml.benchmark_candidate_opening_range_expansion_v001."
            "evaluate_opening_range_expansion"
        ),
        reference_contract=config["reference_contract"],
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    binding_payload = dict(binding["payload"])
    binding_payload.update(
        {
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
        }
    )
    binding = make_artifact(
        "implementation_binding",
        binding_payload,
        parent_identities=tuple(binding["parent_identities"]),
    )
    inputs = conformance_inputs()
    conformance = run_conformance(
        implementation_binding=binding,
        cases=(
            ConformanceCase(
                "integrity-failure",
                "integrity_failure",
                lambda: evaluate_opening_range_expansion(inputs["integrity-failure"]),
                (ExecutorIntegrityError,),
            ),
            ConformanceCase(
                "negative",
                "no_signal",
                lambda: evaluate_opening_range_expansion(inputs["negative"]),
            ),
            ConformanceCase(
                "positive",
                "proposal",
                lambda: evaluate_opening_range_expansion(inputs["positive"]),
            ),
            ConformanceCase(
                "unavailable",
                "unavailable",
                lambda: evaluate_opening_range_expansion(inputs["unavailable"]),
            ),
        ),
        repeat_case_id="positive",
        no_lookahead_check=no_lookahead_conformance,
        proposal_pipeline_check=proposal_pipeline_conformance,
    )
    conformance_payload = dict(conformance["payload"])
    conformance_payload.update(
        {
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
        }
    )
    conformance = make_artifact(
        "conformance",
        conformance_payload,
        parent_identities=(binding["identity"],),
    )
    registration = make_artifact(
        "implementation_binding",
        {
            "binding_kind": "executor_registration",
            "child_hypothesis_id": CHILD_HYPOTHESIS_ID,
            "implementation_binding_identity": binding["identity"],
            "implementation_callable": (
                "aml.benchmark_candidate_opening_range_expansion_v001."
                "evaluate_opening_range_expansion"
            ),
            "registry_keys": sorted(EXECUTOR_REGISTRY),
            "reference_strategy_id": REFERENCE_STRATEGY_ID,
            "reference_executor_identity": REFERENCE_EXECUTOR_IDENTITY,
            "empirical_execution_permitted": False,
            "exploratory_execution_permitted": True,
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
        },
        parent_identities=(binding["identity"], conformance["identity"]),
    )
    artifacts = {
        "01-observation.json": observation,
        "02-child-hypothesis.json": child_hypothesis,
        "03-triage.json": triage,
        "04-specification.json": specification,
        "05-preregistration.json": preregistration,
        "06-implementation-binding.json": binding,
        "07-conformance.json": conformance,
        "08-executor-registration.json": registration,
    }
    verify_evidence_objects(artifacts, repository_root, config)
    return artifacts


def verify_evidence_objects(
    artifacts: Mapping[str, Mapping[str, object]],
    repository_root: Path,
    config: Mapping[str, object],
) -> None:
    if set(artifacts) != set(EVIDENCE_REQUIRED_ROLES):
        raise OpeningRangeExpansionError("evidence file inventory changed")
    _reject_candidate_prohibited_claims(
        config, artifact_name="configuration.json"
    )
    for name, artifact_type in EVIDENCE_ARTIFACT_TYPES.items():
        validate_artifact(artifacts[name], artifact_type)
        _reject_candidate_prohibited_claims(artifacts[name], artifact_name=name)
    binding = artifacts["06-implementation-binding.json"]
    verify_implementation_binding(
        binding,
        repository_root=repository_root,
        source_paths=config["source_paths"],
        dataset_authorization=config["synthetic_dataset_authorization"],
    )
    for artifact_name in (
        "06-implementation-binding.json",
        "07-conformance.json",
        "08-executor-registration.json",
    ):
        payload = artifacts[artifact_name]["payload"]
        if (
            payload.get("candidate_prohibited_claim_contract_identity")
            != candidate_prohibited_claim_contract_identity()
            or payload.get("candidate_required_inventory_contract_identity")
            != candidate_required_inventory_contract_identity()
            or payload.get("candidate_structured_observation_contract_identity")
            != candidate_structured_observation_contract_identity()
            or payload.get("candidate_free_text_domain_contract_identity")
            != candidate_free_text_domain_contract_identity()
        ):
            raise OpeningRangeExpansionError(
                f"candidate verification contract changed:{artifact_name}"
            )
    conformance = artifacts["07-conformance.json"]
    if (
        conformance["payload"].get("all_checks_passed") is not True
        or conformance["payload"].get("no_lookahead") is not True
        or conformance["payload"].get("proposal_pipeline") is not True
    ):
        raise OpeningRangeExpansionError("conformance evidence is incomplete")
    registration = artifacts["08-executor-registration.json"]["payload"]
    if (
        registration.get("registry_keys") != [CHILD_HYPOTHESIS_ID]
        or set(EXECUTOR_REGISTRY) != {CHILD_HYPOTHESIS_ID}
        or EXECUTOR_REGISTRY[CHILD_HYPOTHESIS_ID]
        is not evaluate_opening_range_expansion
    ):
        raise OpeningRangeExpansionError("executor registration changed")
    if artifacts["07-conformance.json"]["parent_identities"] != [binding["identity"]]:
        raise OpeningRangeExpansionError("conformance lineage changed")
    if set(artifacts["08-executor-registration.json"]["parent_identities"]) != {
        binding["identity"],
        artifacts["07-conformance.json"]["identity"],
    }:
        raise OpeningRangeExpansionError("executor registration lineage changed")


def _evidence_manifest(artifacts: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    if set(artifacts) != set(EVIDENCE_REQUIRED_ROLES):
        raise OpeningRangeExpansionError("evidence file inventory changed")
    files = [
        {
            "path": name,
            "role": EVIDENCE_REQUIRED_ROLES[name],
            "sha256": hashlib.sha256(canonical_json(value)).hexdigest(),
            "identity": value["identity"],
        }
        for name, value in sorted(artifacts.items())
    ]
    base = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA,
        "milestone_version": MILESTONE_VERSION,
        "specification_identity": specification_identity(),
        "candidate_prohibited_claim_contract_identity": (
            candidate_prohibited_claim_contract_identity()
        ),
        "candidate_structured_observation_contract_identity": (
            candidate_structured_observation_contract_identity()
        ),
        "candidate_free_text_domain_contract_identity": (
            candidate_free_text_domain_contract_identity()
        ),
        "candidate_required_inventory_contract_identity": (
            candidate_required_inventory_contract_identity()
        ),
        "candidate_artifact_role": "evidence_manifest",
        "files": files,
        "immutable": True,
        "empirical_result_count": 0,
    }
    manifest = {**base, "identity": canonical_hash(base)}
    _reject_candidate_prohibited_claims(
        manifest, artifact_name="evidence-manifest.json"
    )
    return manifest


def write_evidence(
    output_root: Path,
    artifacts: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    target = Path(output_root)
    if target.exists():
        expected = {name: canonical_json(value) for name, value in artifacts.items()}
        manifest = _evidence_manifest(artifacts)
        expected["manifest.json"] = canonical_json(manifest)
        actual = {item.name: item.read_bytes() for item in target.iterdir() if item.is_file()}
        if actual != expected:
            raise OpeningRangeExpansionError("existing evidence differs from canonical bytes")
        return manifest
    target.mkdir(parents=True, exist_ok=False)
    for name, value in sorted(artifacts.items()):
        (target / name).write_bytes(canonical_json(value))
    manifest = _evidence_manifest(artifacts)
    (target / "manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def verify_evidence_directory(
    output_root: Path,
    *,
    repository_root: Path,
    config: Mapping[str, object],
) -> dict[str, object]:
    root = Path(output_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise OpeningRangeExpansionError("evidence manifest is missing or unsafe")
    manifest = _strict_json(manifest_path)
    if not isinstance(manifest, Mapping):
        raise OpeningRangeExpansionError("evidence manifest schema is invalid")
    _reject_candidate_prohibited_claims(manifest, artifact_name="evidence-manifest.json")
    if set(manifest) != {
        "candidate_artifact_role",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_structured_observation_contract_identity",
        "empirical_result_count",
        "files",
        "identity",
        "immutable",
        "milestone_version",
        "schema_version",
        "specification_identity",
    }:
        raise OpeningRangeExpansionError("evidence manifest schema changed")
    identity = manifest.get("identity")
    base = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest.get("schema_version") != EVIDENCE_MANIFEST_SCHEMA
        or identity != canonical_hash(base)
        or manifest.get("empirical_result_count") != 0
        or manifest.get("candidate_artifact_role") != "evidence_manifest"
        or manifest.get("candidate_prohibited_claim_contract_identity")
        != candidate_prohibited_claim_contract_identity()
        or manifest.get("candidate_required_inventory_contract_identity")
        != candidate_required_inventory_contract_identity()
        or manifest.get("candidate_structured_observation_contract_identity")
        != candidate_structured_observation_contract_identity()
        or manifest.get("candidate_free_text_domain_contract_identity")
        != candidate_free_text_domain_contract_identity()
    ):
        raise OpeningRangeExpansionError("evidence manifest changed")
    records = manifest.get("files")
    if not isinstance(records, list) or not all(
        isinstance(record, Mapping) for record in records
    ):
        raise OpeningRangeExpansionError("evidence manifest inventory is invalid")
    if not all(
        set(record) == {"identity", "path", "role", "sha256"}
        for record in records
    ):
        raise OpeningRangeExpansionError("evidence manifest record schema is invalid")
    expected_pairs = sorted(EVIDENCE_REQUIRED_ROLES.items())
    actual_pairs = [(record.get("path"), record.get("role")) for record in records]
    if actual_pairs != expected_pairs:
        raise OpeningRangeExpansionError("evidence required role inventory changed")
    artifacts: dict[str, dict[str, object]] = {}
    expected = {"manifest.json"}
    for record in records:
        relative = Path(str(record.get("path", "")))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix != ".json"
            or relative.as_posix() not in EVIDENCE_REQUIRED_ROLES
        ):
            raise OpeningRangeExpansionError("unsafe evidence path")
        path = root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise OpeningRangeExpansionError("evidence file is missing or unsafe")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256"):
            raise OpeningRangeExpansionError("evidence hash changed")
        value = _strict_json(path)
        if not isinstance(value, Mapping):
            raise OpeningRangeExpansionError("evidence artifact schema is invalid")
        if value.get("identity") != record.get("identity"):
            raise OpeningRangeExpansionError("evidence identity changed")
        _reject_candidate_prohibited_claims(
            value, artifact_name=relative.as_posix()
        )
        artifacts[relative.as_posix()] = value
        expected.add(relative.as_posix())
    actual = {item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()}
    if actual != expected:
        raise OpeningRangeExpansionError("evidence directory contains extra files")
    verify_evidence_objects(artifacts, repository_root, config)
    canonical_artifacts = build_evidence(
        repository_root=repository_root,
        config=config,
        library_path=repository_root / "config/benchmark_hypothesis_library_v001.json",
    )
    if artifacts != canonical_artifacts:
        raise OpeningRangeExpansionError("evidence artifacts differ from canonical graph")
    if manifest != _evidence_manifest(artifacts):
        raise OpeningRangeExpansionError("evidence manifest does not bind exact role graph")
    return {
        "artifact_identities": {
            EVIDENCE_REQUIRED_ROLES[path]: artifact["identity"]
            for path, artifact in sorted(artifacts.items())
        },
        "manifest_identity": identity,
        "verified": True,
    }


def _load_partitions(
    dataset_root: Path,
    binding: Mapping[str, object],
) -> tuple[dict[tuple[str, str], LoadedPartition], list[dict[str, object]]]:
    partitions: dict[tuple[str, str], LoadedPartition] = {}
    records: list[dict[str, object]] = []
    all_sessions = [*binding["warmup_sessions"], *binding["evaluation_sessions"]]
    for session in all_sessions:
        for symbol in binding["symbols"]:
            item = _partition(
                dataset_root,
                symbol=symbol,
                session=session,
                dataset_fingerprint=binding["dataset_fingerprint"],
            )
            partitions[(symbol, session)] = item
            records.append(
                {
                    "metadata_sha256": item.metadata_sha256,
                    "processed_sha256": item.processed_sha256,
                    "role": "warmup" if session in binding["warmup_sessions"] else "evaluated",
                    "session": session,
                    "symbol": symbol,
                    "warning_codes": list(item.warning_codes),
                }
            )
    return partitions, records


def _historical_volume(
    session: date,
    minute: str,
    histories: Sequence[tuple[date, dict[str, float], str]],
) -> tuple[HistoricalClockVolume, ...]:
    return tuple(
        HistoricalClockVolume(
            prior_session,
            minute,
            volumes[minute],
            True,
            DATASET_FINGERPRINT,
            source_identity,
        )
        for prior_session, volumes, source_identity in histories[-20:]
        if prior_session < session and minute in volumes
    )


def _evaluate_exploratory(
    partitions: Mapping[tuple[str, str], LoadedPartition],
    binding: Mapping[str, object],
) -> tuple[dict[str, int], Counter[str], Counter[str], list[object], list[dict[str, object]]]:
    histories: dict[str, list[tuple[date, dict[str, float], str]]] = defaultdict(list)
    for session in binding["warmup_sessions"]:
        for symbol in binding["symbols"]:
            item = partitions[(symbol, session)]
            histories[symbol].append(
                (
                    item.session,
                    {bar.timestamp.strftime("%H:%M"): bar.volume for bar in item.bars},
                    item.processed_sha256,
                )
            )
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposals: list[object] = []
    integrity: list[dict[str, object]] = []
    for session in binding["evaluation_sessions"]:
        for symbol in binding["symbols"]:
            partition = partitions[(symbol, session)]
            opened = datetime.combine(partition.session, time(9, 30), NY)
            closed = datetime.combine(partition.session, time(16, 0), NY)
            for index, bar in enumerate(partition.bars):
                clock = bar.timestamp.strftime("%H:%M")
                if not "09:35" <= clock <= "10:59":
                    continue
                history = _historical_volume(partition.session, clock, histories[symbol])
                try:
                    result = evaluate_opening_range_expansion(
                        EvaluationInput(
                            symbol_bars=partition.bars[: index + 1],
                            next_bar=_next_open(partition.bars, index),
                            scheduled_open=opened,
                            scheduled_close=closed,
                            decision_cutoff=bar.timestamp + timedelta(minutes=1),
                            same_clock_history=history,
                            halt_coverage_complete=True,
                            corporate_action_coverage_complete=True,
                            corporate_action_lineage_valid=True,
                            halt_manifest_identity="exploratory-no-halt-intervals-observed",
                            corporate_action_manifest_identity=(
                                "exploratory-retrospective-coverage-contaminated"
                            ),
                            calendar_identity="exploratory-fixed-normal-xnys-session",
                        )
                    )
                except ExecutorIntegrityError as exc:
                    statuses["integrity_failure"] += 1
                    reasons["integrity_failure:executor_integrity_rejected"] += 1
                    integrity.append(
                        {
                            "session": session,
                            "symbol": symbol,
                            "timestamp": bar.timestamp.isoformat(),
                            "reason": str(exc),
                        }
                    )
                    continue
                statuses[result.status] += 1
                for reason in result.reason_codes or ("none",):
                    reasons[f"{result.status}:{reason}"] += 1
                if result.proposal is not None:
                    proposals.append(result.proposal)
            histories[symbol].append(
                (
                    partition.session,
                    {bar.timestamp.strftime("%H:%M"): bar.volume for bar in partition.bars},
                    partition.processed_sha256,
                )
            )
    bars_by_key = {
        (partitions[(symbol, session)].symbol, partitions[(symbol, session)].session): (
            partitions[(symbol, session)].bars
        )
        for session in binding["evaluation_sessions"]
        for symbol in binding["symbols"]
    }
    calendar_by_date = {
        date.fromisoformat(session): CalendarSession(
            date.fromisoformat(session),
            datetime.combine(date.fromisoformat(session), time(9, 30), NY),
            datetime.combine(date.fromisoformat(session), time(16, 0), NY),
            False,
        )
        for session in binding["evaluation_sessions"]
    }
    trades, rejections = simulate_strategy(
        REFERENCE_STRATEGY_ID, proposals, bars_by_key, calendar_by_date
    )
    if len(proposals) != len(trades) + len(rejections):
        raise OpeningRangeExpansionError("exploratory proposal reconciliation failed")
    counts = {
        "executed_trade_count": len(trades),
        "integrity_failure_count": statuses["integrity_failure"],
        "proposal_count": len(proposals),
        "rejected_proposal_count": len(rejections),
        "trigger_count": len(proposals) + statuses["no_trade"],
        "unavailable_event_count": statuses["unavailable"],
    }
    return counts, statuses, reasons, proposals, integrity


def _source_hashes(repository_root: Path) -> dict[str, str]:
    return file_hashes(
        repository_root, sorted([*SOURCE_PATHS, *FROZEN_DOWNSTREAM_PATHS])
    )


def normalize_candidate_claim_name(value: str) -> str:
    """Normalize reviewable key variants without fuzzy or substring matching."""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = _CAMEL_ACRONYM_BOUNDARY.sub(r"\1_\2", normalized)
    normalized = _CAMEL_WORD_BOUNDARY.sub(r"\1_\2", normalized)
    tokens = [
        _TOKEN_ALIASES.get(token, token)
        for token in _NON_ALPHANUMERIC.sub("_", normalized).casefold().split("_")
        if token
    ]
    return "_".join(tokens)


def candidate_prohibited_claim_contract() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_PROHIBITED_CLAIM_SCHEMA,
        "normalization": [
            "Unicode NFKC normalization",
            "camelCase and PascalCase boundary splitting",
            "spaces, hyphens, underscores, and punctuation collapse to underscores",
            "Unicode-independent ASCII case folding",
            "explicit relevant plural-token aliases",
            "exact normalized-field and contiguous token-sequence matching; no fuzzy matching",
        ],
        "prohibited_fields": sorted(CANDIDATE_PROHIBITED_FIELDS),
        "claim_context_keys": sorted(CANDIDATE_CLAIM_CONTEXT_KEYS),
        "prohibited_affirmative_phrases": sorted(
            CANDIDATE_PROHIBITED_AFFIRMATIVE_PHRASES
        ),
        "structured_observation_contract_identity": (
            candidate_structured_observation_contract_identity()
        ),
        "unrestricted_observation_prose_permitted": False,
        "negative_claim_allowances": [
            {"path": ".".join(path), "required_value": required}
            for path, required in sorted(CANDIDATE_NEGATIVE_CLAIM_ALLOWANCES.items())
        ],
        "recursive_scope": [
            "complete manifest object",
            "every manifest file record",
            "every manifested artifact",
            "all nested mappings and sequences",
            "all string values for exact affirmative phrases",
            "claim-bearing values for prohibited normalized claim terms",
            "structured engineering details after exact observation validation",
        ],
        "vocabulary_is_not_a_claim": (
            "isolated technical vocabulary is allowed only in frozen or structured "
            "channels; arbitrary publication prose is prohibited"
        ),
        "fully_rehashed_prohibited_claims_remain_prohibited": True,
    }


def candidate_prohibited_claim_contract_identity() -> str:
    return canonical_hash(
        {
            "domain": CANDIDATE_PROHIBITED_CLAIM_SCHEMA,
            "contract": candidate_prohibited_claim_contract(),
        }
    )


def _candidate_key_is_prohibited(normalized: str) -> bool:
    tokens = normalized.split("_")
    for field in CANDIDATE_PROHIBITED_FIELDS:
        field_tokens = field.split("_")
        if any(
            tokens[index : index + len(field_tokens)] == field_tokens
            for index in range(len(tokens) - len(field_tokens) + 1)
        ):
            return True
    return False


def _contains_prohibited_affirmative_phrase(value: str) -> bool:
    normalized = normalize_candidate_claim_name(value)
    tokens = normalized.split("_")
    for phrase in CANDIDATE_PROHIBITED_AFFIRMATIVE_PHRASES:
        phrase_tokens = normalize_candidate_claim_name(phrase).split("_")
        if any(
            tokens[index : index + len(phrase_tokens)] == phrase_tokens
            for index in range(len(tokens) - len(phrase_tokens) + 1)
        ):
            return True
    return False


def _claim_context(path: tuple[str, ...]) -> bool:
    return any(part in CANDIDATE_CLAIM_CONTEXT_KEYS for part in path if not part.startswith("["))


def _reject_candidate_prohibited_claims(
    value: object,
    *,
    artifact_name: str,
    path: tuple[str, ...] = (),
) -> None:
    """Reject prohibited claim semantics regardless of hash consistency."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = normalize_candidate_claim_name(str(key))
            child_path = (*path, normalized)
            dotted = ".".join(child_path)
            if (artifact_name, dotted) in CANDIDATE_PROSPECTIVE_DESIGN_ALLOWANCES:
                _reject_candidate_prohibited_claims(
                    item,
                    artifact_name=artifact_name,
                    path=child_path,
                )
                continue
            if child_path in CANDIDATE_NEGATIVE_CLAIM_ALLOWANCES:
                if item is not CANDIDATE_NEGATIVE_CLAIM_ALLOWANCES[child_path]:
                    raise OpeningRangeExpansionError(
                        "candidate negative claim allowance became affirmative:"
                        f"{artifact_name}:{'.'.join(child_path)}"
                    )
                continue
            if _candidate_key_is_prohibited(normalized):
                raise OpeningRangeExpansionError(
                    "prohibited candidate claim field:"
                    f"{artifact_name}:{'.'.join(child_path)}"
                )
            _reject_candidate_prohibited_claims(
                item,
                artifact_name=artifact_name,
                path=child_path,
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _reject_candidate_prohibited_claims(
                item,
                artifact_name=artifact_name,
                path=(*path, f"[{index}]"),
            )
    elif isinstance(value, str):
        if value in CANDIDATE_PERMITTED_NEGATIVE_CLAIM_STRINGS or value in set(
            CANDIDATE_OBSERVATION_DETAILS.values()
        ):
            return
        normalized = normalize_candidate_claim_name(value)
        if _contains_prohibited_affirmative_phrase(value) or (
            _claim_context(path) and _candidate_key_is_prohibited(normalized)
        ):
            raise OpeningRangeExpansionError(
                "prohibited candidate claim value:"
                f"{artifact_name}:{'.'.join(path)}"
            )


def _require_candidate_specific_label(
    value: Mapping[str, object], *, artifact_name: str
) -> None:
    """Require the exact additive candidate label without changing V001 labels."""

    if value.get("candidate_specific_labels") != list(CANDIDATE_SPECIFIC_LABELS):
        raise OpeningRangeExpansionError(
            f"candidate-specific exploratory label changed:{artifact_name}"
        )


def _structured_observations_for_result(
    counts: Mapping[str, int], missing_fields: Sequence[str]
) -> list[dict[str, object]]:
    observations = [
        create_structured_observation(
            "IMPLEMENTATION_BEHAVIOR",
            "frozen_evaluator_and_lifecycle",
            "MATCHED",
            "FROZEN_COMPONENT_REUSED",
        ),
        create_structured_observation(
            "RECONCILIATION",
            "candidate_result",
            "RECONCILED",
            "COUNTS_RECONCILED",
        ),
    ]
    if missing_fields:
        observations.append(
            create_structured_observation(
                "MISSING_INPUT",
                "required_source_field",
                "ABSENT",
                "FIELD_NOT_PRESENT",
            )
        )
    elif counts["proposal_count"]:
        observations.append(
            create_structured_observation(
                "EVALUATOR_PATH",
                "frozen_evaluator",
                "EXERCISED",
                "PROPOSAL_EMITTED",
            )
        )
    else:
        observations.append(
            create_structured_observation(
                "EVALUATOR_PATH",
                "frozen_evaluator",
                "NOT_EXERCISED",
                "NO_PROPOSAL_EMITTED",
            )
        )
    if counts["integrity_failure_count"]:
        observations.append(
            create_structured_observation(
                "INTEGRITY_BEHAVIOR",
                "proposal_lifecycle",
                "INTEGRITY_FAILURE",
                "INTEGRITY_REJECTED",
            )
        )
    return sorted(observations, key=lambda item: str(item["identity"]))


def _validate_candidate_result_string_domain(value: Mapping[str, object]) -> None:
    observations = value.get("qualitative_observations")
    if not isinstance(observations, list) or not observations:
        raise OpeningRangeExpansionError("structured observations are missing")
    if not all(isinstance(item, Mapping) for item in observations):
        raise OpeningRangeExpansionError("unstructured observation prose is prohibited")
    validated = [validate_structured_observation(item) for item in observations]
    identities = [item["identity"] for item in validated]
    if (
        identities != sorted(identities)
        or value.get("observation_count") != len(validated)
        or value.get("observation_identities") != identities
    ):
        raise OpeningRangeExpansionError("structured observation reconciliation changed")
    notes = value.get("implementation_notes")
    if (
        not isinstance(notes, list)
        or notes != sorted(notes)
        or not notes
        or not all(item in CANDIDATE_IMPLEMENTATION_NOTE_CODES for item in notes)
    ):
        raise OpeningRangeExpansionError("implementation-note vocabulary changed")
    if value.get("status") not in {
        "EXPLORATORY_DIAGNOSTIC_ONLY",
        "EXPLORATORY_EXERCISED",
    }:
        raise OpeningRangeExpansionError("candidate result status changed")
    anomalies = value.get("obvious_anomalies")
    if not isinstance(anomalies, list) or not set(anomalies).issubset(
        {
            "NONZERO_EXECUTOR_INTEGRITY_FAILURES",
            "NO_TRIGGER_OBSERVED_IN_BOUNDED_EXERCISE",
        }
    ):
        raise OpeningRangeExpansionError("candidate anomaly vocabulary changed")
    warnings = value.get("confidence_warnings")
    if (
        not isinstance(warnings, list)
        or warnings != sorted(warnings)
        or not set(warnings).issubset(set(LABELS) | set(CANDIDATE_WARNING_CODES))
    ):
        raise OpeningRangeExpansionError("candidate warning vocabulary changed")
    reasons = value.get("decision_reason_counts")
    if (
        not isinstance(reasons, Mapping)
        or not set(reasons).issubset(CANDIDATE_DECISION_REASON_KEYS)
        or not all(isinstance(item, int) and item >= 0 for item in reasons.values())
    ):
        raise OpeningRangeExpansionError("candidate decision-reason vocabulary changed")
    statuses = value.get("decision_status_counts")
    if (
        not isinstance(statuses, Mapping)
        or not set(statuses).issubset(CANDIDATE_DECISION_STATUSES)
        or not all(isinstance(item, int) and item >= 0 for item in statuses.values())
    ):
        raise OpeningRangeExpansionError("candidate decision-status vocabulary changed")
    missing = value.get("missing_data_summary")
    if not isinstance(missing, Mapping):
        raise OpeningRangeExpansionError("candidate missing-data schema changed")
    missing_fields = missing.get("missing_required_fields")
    if not isinstance(missing_fields, list) or not all(
        isinstance(item, str) and item in CANDIDATE_MISSING_FIELD_CODES
        for item in missing_fields
    ):
        raise OpeningRangeExpansionError("candidate missing-field vocabulary changed")


def run_bounded_exploratory(
    *,
    repository_root: Path,
    config: Mapping[str, object],
    evidence_artifacts: Mapping[str, Mapping[str, object]],
    dataset_root: Path,
    output_root: Path,
) -> dict[str, object]:
    """Run one write-once, non-economic, contaminated diagnostic exercise."""

    validate_config(config, repository_root)
    verify_evidence_objects(evidence_artifacts, repository_root, config)
    evidence_manifest = _evidence_manifest(evidence_artifacts)
    child_identity = evidence_artifacts["02-child-hypothesis.json"]["identity"]
    preregistration_identity = evidence_artifacts["05-preregistration.json"][
        "identity"
    ]
    implementation_binding_identity = evidence_artifacts[
        "06-implementation-binding.json"
    ]["identity"]
    conformance_identity = evidence_artifacts["07-conformance.json"]["identity"]
    registration_identity = evidence_artifacts["08-executor-registration.json"][
        "identity"
    ]
    binding = config["exploratory_dataset_binding"]
    dataset = Path(dataset_root).resolve()
    if dataset.name != binding["dataset_vintage"]:
        raise OpeningRangeExpansionError("dataset vintage changed")
    manifest_path = repository_root / str(binding["manifest_relative_path"])
    if _sha256(manifest_path) != binding["manifest_sha256"]:
        raise OpeningRangeExpansionError("dataset manifest hash changed")
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("dataset_fingerprint_sha256") != binding["dataset_fingerprint"]:
        raise OpeningRangeExpansionError("dataset fingerprint changed")
    partitions, partition_records = _load_partitions(dataset, binding)
    counts, statuses, reasons, _, integrity = _evaluate_exploratory(partitions, binding)
    warning_codes = sorted(
        {
            warning
            for item in partitions.values()
            for warning in item.warning_codes
        }
    )
    source_sha256 = _source_hashes(repository_root)
    run_identity = canonical_hash(
        {
            "domain": "aml.opening-range-expansion-exploratory-run.v001",
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "partitions": partition_records,
            "source_sha256": source_sha256,
        }
    )
    base_result = _result_payload(
        binding={
            "evaluator_binding": (
                "aml.benchmark_candidate_opening_range_expansion_v001."
                "evaluate_opening_range_expansion"
            ),
            "framework_hypothesis_identity": child_identity,
            "library_entry_id": CHILD_HYPOTHESIS_ID,
            "registration_identity": registration_identity,
        },
        counts=counts,
        decision_counts=statuses,
        decision_reason_counts=reasons,
        partition_count=len(EVALUATION_SESSIONS) * len(SYMBOLS),
        warning_codes=warning_codes,
        missing_fields=(),
        status=(
            "EXPLORATORY_DIAGNOSTIC_ONLY"
            if counts["integrity_failure_count"]
            else "EXPLORATORY_EXERCISED"
        ),
    )
    result_base = {key: value for key, value in base_result.items() if key != "identity"}
    observations = _structured_observations_for_result(counts, ())
    result_base["qualitative_observations"] = observations
    result_base["observation_count"] = len(observations)
    result_base["observation_identities"] = [item["identity"] for item in observations]
    result_base["implementation_notes"] = [
        "EVALUATOR_BINDING_VERIFIED",
        "FROZEN_COMPONENTS_REUSED",
    ]
    result_base["candidate_specific_labels"] = list(CANDIDATE_SPECIFIC_LABELS)
    result_base["candidate_prohibited_claim_contract_identity"] = (
        candidate_prohibited_claim_contract_identity()
    )
    result_base["candidate_required_inventory_contract_identity"] = (
        candidate_required_inventory_contract_identity()
    )
    result_base["candidate_structured_observation_contract_identity"] = (
        candidate_structured_observation_contract_identity()
    )
    result_base["candidate_free_text_domain_contract_identity"] = (
        candidate_free_text_domain_contract_identity()
    )
    result_base["candidate_artifact_role"] = "candidate_result"
    result_base["run_identity"] = run_identity
    result_base["config_identity"] = config["config_identity"]
    result_base["dataset_binding_identity"] = binding["binding_identity"]
    result_base["evidence_manifest_identity"] = evidence_manifest["identity"]
    result_base["implementation_binding_identity"] = implementation_binding_identity
    result_base["partition_inspection"] = {
        "warmup_partition_count": len(WARMUP_SESSIONS) * len(SYMBOLS),
        "evaluated_partition_count": len(EVALUATION_SESSIONS) * len(SYMBOLS),
        "total_partition_count": len(partition_records),
        "warmup_session_count": len(WARMUP_SESSIONS),
        "evaluated_session_count": len(EVALUATION_SESSIONS),
        "symbol_count": len(SYMBOLS),
    }
    result_base["integrity_diagnostic_count"] = len(integrity)
    result = {**result_base, "identity": canonical_hash(result_base)}
    from aml.exploratory_research_mode_v001 import validate_result

    validate_result(result)
    _validate_candidate_result_string_domain(result)
    target = _output_path(output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".opening-range-v001-", dir=target.parent))
    try:
        result_path = staging / f"01-{CHILD_HYPOTHESIS_ID}.json"
        result_path.write_bytes(canonical_json(result))
        summary_base = {
            "schema_version": EXPLORATORY_SUMMARY_SCHEMA,
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
            "candidate_artifact_role": "candidate_summary",
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "result_identity": result["identity"],
            "result_path": result_path.name,
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_binding": {
                "child_hypothesis_identity": child_identity,
                "conformance_identity": conformance_identity,
                "evidence_manifest_identity": evidence_manifest["identity"],
                "implementation_binding_identity": implementation_binding_identity,
                "preregistration_identity": preregistration_identity,
                "registration_identity": registration_identity,
                "specification_identity": specification_identity(),
            },
            "partition_bindings": partition_records,
            "counts": counts,
            "decision_status_counts": dict(sorted(statuses.items())),
            "decision_reason_counts": dict(sorted(reasons.items())),
            "source_sha256": source_sha256,
            "observation_count": result["observation_count"],
            "observation_identities": result["observation_identities"],
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        _reject_prohibited_keys(summary_base)
        summary = {**summary_base, "identity": canonical_hash(summary_base)}
        summary_path = staging / "summary.json"
        summary_path.write_bytes(canonical_json(summary))
        run_base = {
            "schema_version": EXPLORATORY_SUMMARY_SCHEMA,
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
            "candidate_artifact_role": "exploratory_run",
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "config_identity": config["config_identity"],
            "dataset_binding_identity": binding["binding_identity"],
            "evidence_manifest_identity": evidence_manifest["identity"],
            "result_references": [
                {"path": result_path.name, "identity": result["identity"]}
            ],
            "summary_reference": {
                "path": summary_path.name,
                "identity": summary["identity"],
            },
            "counts": counts,
            "observation_count": result["observation_count"],
            "observation_identities": result["observation_identities"],
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        _reject_prohibited_keys(run_base)
        run = {**run_base, "identity": canonical_hash(run_base)}
        run_path = staging / "run.json"
        run_path.write_bytes(canonical_json(run))
        files = [
            {
                "path": result_path.name,
                "role": "candidate_result",
                "identity": result["identity"],
                "sha256": _sha256(result_path),
            },
            {
                "path": run_path.name,
                "role": "exploratory_run",
                "identity": run["identity"],
                "sha256": _sha256(run_path),
            },
            {
                "path": summary_path.name,
                "role": "candidate_summary",
                "identity": summary["identity"],
                "sha256": _sha256(summary_path),
            },
        ]
        manifest_base = {
            "schema_version": MANIFEST_SCHEMA,
            "labels": list(LABELS),
            "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
            "candidate_prohibited_claim_contract_identity": (
                candidate_prohibited_claim_contract_identity()
            ),
            "candidate_required_inventory_contract_identity": (
                candidate_required_inventory_contract_identity()
            ),
            "candidate_structured_observation_contract_identity": (
                candidate_structured_observation_contract_identity()
            ),
            "candidate_free_text_domain_contract_identity": (
                candidate_free_text_domain_contract_identity()
            ),
            "candidate_artifact_role": "exploratory_manifest",
            "run_identity": run_identity,
            "plan_identity": config["config_identity"],
            "write_once": True,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        manifest = {**manifest_base, "identity": canonical_hash(manifest_base)}
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verified = verify_opening_range_exploratory_bundle(target)
    return {
        "run_identity": run_identity,
        "manifest_identity": verified["manifest_identity"],
        "candidate_specific_labels": list(CANDIDATE_SPECIFIC_LABELS),
        "candidate_prohibited_claim_contract_identity": (
            candidate_prohibited_claim_contract_identity()
        ),
        "candidate_structured_observation_contract_identity": (
            candidate_structured_observation_contract_identity()
        ),
        "candidate_free_text_domain_contract_identity": (
            candidate_free_text_domain_contract_identity()
        ),
        "evidence_manifest_identity": evidence_manifest["identity"],
        "counts": counts,
        "partition_count": len(partition_records),
        "output_root": str(target),
        "verified": True,
    }


def verify_opening_range_exploratory_bundle(
    path: Path,
    *,
    repository_root: Path = ROOT,
    config: Mapping[str, object] | None = None,
    evidence_root: Path | None = None,
) -> dict[str, object]:
    root = Path(path).resolve()
    repository = Path(repository_root).resolve()
    active_config = (
        dict(config)
        if config is not None
        else load_config(
            repository / "config/opening_range_expansion_continuation_v001.json",
            repository,
        )
    )
    validate_config(active_config, repository)
    evidence_verification = verify_evidence_directory(
        evidence_root
        or repository / "manifests/opening_range_expansion_continuation_v001",
        repository_root=repository,
        config=active_config,
    )
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise OpeningRangeExpansionError("candidate manifest is missing or unsafe")
    manifest = _strict_json(manifest_path)
    if not isinstance(manifest, Mapping):
        raise OpeningRangeExpansionError("candidate manifest schema is invalid")
    _require_candidate_specific_label(manifest, artifact_name="manifest.json")
    if (
        manifest.get("candidate_prohibited_claim_contract_identity")
        != candidate_prohibited_claim_contract_identity()
        or manifest.get("candidate_required_inventory_contract_identity")
        != candidate_required_inventory_contract_identity()
        or manifest.get("candidate_structured_observation_contract_identity")
        != candidate_structured_observation_contract_identity()
        or manifest.get("candidate_free_text_domain_contract_identity")
        != candidate_free_text_domain_contract_identity()
        or manifest.get("candidate_artifact_role") != "exploratory_manifest"
    ):
        raise OpeningRangeExpansionError(
            "candidate verification contract changed:manifest.json"
        )
    _reject_candidate_prohibited_claims(manifest, artifact_name="manifest.json")
    if set(manifest) != {
        "candidate_artifact_role",
        "candidate_free_text_domain_contract_identity",
        "candidate_prohibited_claim_contract_identity",
        "candidate_required_inventory_contract_identity",
        "candidate_specific_labels",
        "candidate_structured_observation_contract_identity",
        "files",
        "identity",
        "labels",
        "plan_identity",
        "run_identity",
        "schema_version",
        "write_once",
    }:
        raise OpeningRangeExpansionError("candidate manifest schema changed")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise OpeningRangeExpansionError("candidate manifest file inventory is invalid")
    if not all(isinstance(record, Mapping) for record in records):
        raise OpeningRangeExpansionError("candidate manifest file record is invalid")
    if not all(
        set(record) == {"identity", "path", "role", "sha256"}
        for record in records
    ):
        raise OpeningRangeExpansionError("candidate manifest file record schema is invalid")
    record_pairs = [(record.get("path"), record.get("role")) for record in records]
    if record_pairs != sorted(EXPLORATORY_REQUIRED_ROLES.items()):
        raise OpeningRangeExpansionError(
            "candidate required role inventory changed"
        )
    artifacts_by_role: dict[str, Mapping[str, object]] = {}
    expected_files = {"manifest.json"}
    for record in records:
        relative = Path(str(record.get("path", "")))
        role = str(record.get("role", ""))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix != ".json"
            or relative.as_posix() not in EXPLORATORY_REQUIRED_ROLES
            or EXPLORATORY_REQUIRED_ROLES[relative.as_posix()] != role
        ):
            raise OpeningRangeExpansionError("unsafe candidate artifact path")
        artifact_path = (root / relative).resolve()
        if (
            not artifact_path.is_relative_to(root)
            or not artifact_path.is_file()
            or artifact_path.is_symlink()
        ):
            raise OpeningRangeExpansionError("unsafe candidate artifact path")
        value = _strict_json(artifact_path)
        if not isinstance(value, Mapping):
            raise OpeningRangeExpansionError("candidate artifact schema is invalid")
        _require_candidate_specific_label(value, artifact_name=relative.as_posix())
        if (
            value.get("candidate_prohibited_claim_contract_identity")
            != candidate_prohibited_claim_contract_identity()
            or value.get("candidate_required_inventory_contract_identity")
            != candidate_required_inventory_contract_identity()
            or value.get("candidate_structured_observation_contract_identity")
            != candidate_structured_observation_contract_identity()
            or value.get("candidate_free_text_domain_contract_identity")
            != candidate_free_text_domain_contract_identity()
            or value.get("candidate_artifact_role") != role
        ):
            raise OpeningRangeExpansionError(
                "candidate verification contract changed:"
                f"{relative.as_posix()}"
            )
        _reject_candidate_prohibited_claims(
            value, artifact_name=relative.as_posix()
        )
        if _sha256(artifact_path) != record.get("sha256"):
            raise OpeningRangeExpansionError("candidate artifact hash changed")
        if value.get("identity") != record.get("identity"):
            raise OpeningRangeExpansionError("candidate artifact identity changed")
        if role in artifacts_by_role:
            raise OpeningRangeExpansionError("candidate required role is duplicated")
        artifacts_by_role[role] = value
        expected_files.add(relative.as_posix())
    actual_files = {
        item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()
    }
    if actual_files != expected_files:
        raise OpeningRangeExpansionError("candidate closed inventory contains extra files")
    result = artifacts_by_role["candidate_result"]
    summary = artifacts_by_role["candidate_summary"]
    run = artifacts_by_role["exploratory_run"]
    for artifact_name, value, required_fields in (
        (EXPLORATORY_RESULT_PATH, result, RESULT_REQUIRED_FIELDS),
        ("summary.json", summary, SUMMARY_REQUIRED_FIELDS),
        ("run.json", run, RUN_REQUIRED_FIELDS),
    ):
        if set(value) != required_fields:
            raise OpeningRangeExpansionError(
                f"candidate artifact schema changed:{artifact_name}"
            )
    _validate_candidate_result_string_domain(result)
    if (
        summary.get("schema_version") != EXPLORATORY_SUMMARY_SCHEMA
        or summary.get("labels") != list(LABELS)
        or summary.get("economic_metrics_published") is not False
        or summary.get("empirical_conclusion_authorized") is not False
    ):
        raise OpeningRangeExpansionError("exploratory summary boundary changed")
    expected_run_identity = canonical_hash(
        {
            "domain": "aml.opening-range-expansion-exploratory-run.v001",
            "config_identity": active_config["config_identity"],
            "dataset_binding_identity": active_config["exploratory_dataset_binding"][
                "binding_identity"
            ],
            "evidence_manifest_identity": evidence_verification["manifest_identity"],
            "partitions": summary.get("partition_bindings"),
            "source_sha256": summary.get("source_sha256"),
        }
    )
    if not all(
        item.get("run_identity") == expected_run_identity
        for item in (manifest, result, summary, run)
    ):
        raise OpeningRangeExpansionError("candidate run lineage changed")
    if (
        manifest.get("plan_identity") != active_config["config_identity"]
        or result.get("config_identity") != active_config["config_identity"]
        or summary.get("config_identity") != active_config["config_identity"]
        or run.get("config_identity") != active_config["config_identity"]
        or result.get("dataset_binding_identity")
        != active_config["exploratory_dataset_binding"]["binding_identity"]
        or summary.get("dataset_binding_identity")
        != result.get("dataset_binding_identity")
        or run.get("dataset_binding_identity") != result.get("dataset_binding_identity")
        or result.get("evidence_manifest_identity")
        != evidence_verification["manifest_identity"]
        or summary.get("evidence_binding", {}).get("evidence_manifest_identity")
        != evidence_verification["manifest_identity"]
        or run.get("evidence_manifest_identity")
        != evidence_verification["manifest_identity"]
    ):
        raise OpeningRangeExpansionError("candidate authority lineage changed")
    evidence_identities = evidence_verification["artifact_identities"]
    expected_evidence_binding = {
        "child_hypothesis_identity": evidence_identities["child_hypothesis"],
        "conformance_identity": evidence_identities["conformance_evidence"],
        "evidence_manifest_identity": evidence_verification["manifest_identity"],
        "implementation_binding_identity": evidence_identities[
            "implementation_binding"
        ],
        "preregistration_identity": evidence_identities["preregistration"],
        "registration_identity": evidence_identities["executor_registration"],
        "specification_identity": specification_identity(),
    }
    if (
        result.get("hypothesis")
        != {
            "evaluator_binding": (
                "aml.benchmark_candidate_opening_range_expansion_v001."
                "evaluate_opening_range_expansion"
            ),
            "framework_hypothesis_identity": evidence_identities["child_hypothesis"],
            "library_entry_id": CHILD_HYPOTHESIS_ID,
            "registration_identity": evidence_identities["executor_registration"],
        }
        or result.get("implementation_binding_identity")
        != evidence_identities["implementation_binding"]
        or summary.get("evidence_binding") != expected_evidence_binding
    ):
        raise OpeningRangeExpansionError("candidate evidence lineage changed")
    if (
        summary.get("result_identity") != result.get("identity")
        or summary.get("result_path") != EXPLORATORY_RESULT_PATH
        or run.get("result_references")
        != [{"path": EXPLORATORY_RESULT_PATH, "identity": result.get("identity")}]
        or run.get("summary_reference")
        != {"path": "summary.json", "identity": summary.get("identity")}
        or run.get("counts") != result.get("counts")
        or summary.get("counts") != result.get("counts")
        or summary.get("observation_count") != result.get("observation_count")
        or run.get("observation_count") != result.get("observation_count")
        or summary.get("observation_identities")
        != result.get("observation_identities")
        or run.get("observation_identities") != result.get("observation_identities")
    ):
        raise OpeningRangeExpansionError("candidate result-summary-run graph changed")
    verified = verify_bundle(root)
    _reject_prohibited_keys(summary)
    return verified
