"""Deterministic V002 provider capability contract and evidence decision matrix."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Mapping

from aml.winner_archetype_contracts import canonical_hash, canonical_json
from aml.winner_archetype_v002 import (
    SourceRequirementsMatrix,
    WinnerArchetypeProtocolV002,
    load_protocol_v002,
    load_source_requirements_v002,
)


CAPABILITY_CONTRACT_SCHEMA = "aml.winner-archetype.provider-capability-contract.v002"
DECISION_MATRIX_SCHEMA = "aml.winner-archetype.provider-decision-matrix.v002"
EVIDENCE_LEVELS = (
    "provider_claim",
    "public_documentation",
    "written_provider_confirmation",
    "sample_schema_verification",
    "license_confirmation",
    "empirical_completeness_evidence",
)
EVIDENCE_STATUSES = ("proven", "claimed", "unknown", "conflicting", "insufficient")


class CapabilityContractError(ValueError):
    """Provider evidence cannot satisfy the frozen capability contract."""


REQUIRED_FIELDS = {
    "broad_market_regime_inputs": ["instrument_id", "observation_timestamp", "first_available_at", "value"],
    "catalyst_broad_news": ["source_record_id", "security_id", "publication_timestamp", "provider_receipt_timestamp", "headline", "raw_payload"],
    "catalyst_sec_filings": ["accession_number", "cik", "acceptance_timestamp", "filing_type", "document_identity", "raw_payload"],
    "catalyst_specialist_regulatory": ["source_record_id", "issuer_id", "category", "publication_timestamp", "first_available_at", "raw_payload"],
    "corporate_actions": ["action_id", "security_id", "action_type", "announcement_timestamp", "effective_timestamp", "first_known_at"],
    "exchange_calendar": ["session", "scheduled_open", "scheduled_close", "selection_cutoff", "closure_classification", "calendar_version"],
    "halt_market_status": ["security_id", "halt_timestamp", "resume_timestamp", "halt_type", "first_known_at", "source_record_id"],
    "security_master": ["security_id", "listing_id", "issuer_id", "symbol", "exchange", "security_type", "status", "effective_interval", "first_known_at"],
    "sip_minute_bars": ["security_id", "minute", "open", "high", "low", "close", "volume", "trade_count", "vwap", "tick_manifest_hash"],
    "sip_quotes": ["security_id", "participant_timestamp", "sip_timestamp", "sequence", "bid", "ask", "sizes", "exchanges", "conditions", "tape"],
    "sip_trades": ["security_id", "participant_timestamp", "sip_timestamp", "sequence", "price", "size", "exchange", "conditions", "tape", "trade_id"],
    "symbol_lineage": ["security_id", "listing_id", "symbol", "effective_from", "effective_to", "first_known_at", "revision"],
    "universe_snapshot": ["session", "snapshot_timestamp", "security_id", "listing_id", "symbol", "exchange", "security_type", "status", "expected_count"],
}


def build_capability_contract(
    protocol: WinnerArchetypeProtocolV002,
    matrix: SourceRequirementsMatrix,
) -> dict[str, object]:
    requirements = []
    for source in matrix.requirements:
        dataset = source.dataset
        sequence = (
            "complete_source_sequence_and_gap_reconciliation_required"
            if dataset in {"sip_quotes", "sip_trades"}
            else "source_revision_or_file_order_identity_required"
        )
        row = {
            "dataset": dataset,
            "required_capability": source.required_capability,
            "required_fields": REQUIRED_FIELDS[dataset],
            "timestamp_semantics": ["event_or_effective_time", "provider_receipt_or_first_available_time", "retrieval_time", "revision_time_when_applicable"],
            "timezone": protocol.calendar["timezone"],
            "coverage_interval": source.historical_range,
            "point_in_time_requirement": source.point_in_time_requirement,
            "sequence_requirement": sequence,
            "correction_cancellation_lineage": "append_only_revisions_with_original_payload_and_supersession_identity",
            "negative_coverage_requirement": source.completeness_requirement,
            "provider_and_feed_identity": "provider_source_version_feed_role_and_file_or_query_identity_required",
            "entitlement_evidence": "written_account_scope_license_and_effective_interval_required" if source.entitlement_status != "not_required" else "not_required",
            "archive_and_retention_terms": "written_local_immutable_archive_and_retention_terms_required",
            "redistribution_and_research_use_rights": "written_internal_quantitative_research_and_nonredistribution_rights_required",
            "raw_payload_availability": "immutable_original_payload_or_authoritative_file_required",
            "manifest_requirements": "V002 capability_entitlement_input_and_coverage_manifests_required",
            "hashing_requirements": "SHA-256_raw_normalized_manifest_and_partition_hashes",
            "completeness_criteria": source.completeness_requirement,
            "conflict_resolution_rules": "unresolved_authoritative_conflict_blocks_readiness",
            "acceptable_evidence_types": list(EVIDENCE_LEVELS),
            "minimum_capability_evidence": ["written_provider_confirmation", "sample_schema_verification"],
            "minimum_entitlement_evidence": ["license_confirmation"] if source.entitlement_status != "not_required" else [],
            "minimum_readiness_evidence": ["empirical_completeness_evidence"],
            "failure_conditions": ["missing_required_field", "ambiguous_or_future_timestamp", "unknown_or_incomplete_coverage", "unreconciled_sequence_or_revision", "missing_license_or_retention_right", "unresolved_source_conflict"],
        }
        requirements.append(row)
    payload = {
        "schema_version": CAPABILITY_CONTRACT_SCHEMA,
        "contract_version": "winner-archetype-provider-capability-contract-v002",
        "protocol_identity": protocol.identity,
        "source_requirements_identity": matrix.identity,
        "evidence_levels": list(EVIDENCE_LEVELS),
        "evidence_policy": {
            "provider_claim": "never_sufficient",
            "public_documentation": "never_sufficient_without_written_and_schema_evidence",
            "written_provider_confirmation": "capability_only_not_completeness",
            "sample_schema_verification": "schema_only_not_completeness",
            "license_confirmation": "entitlement_only_not_completeness",
            "empirical_completeness_evidence": "required_but_not_automatically_sufficient",
        },
        "requirements": requirements,
        "pilot_authorized": False,
    }
    return {**payload, "contract_identity": canonical_hash(payload)}


PROVIDERS = {
    "alpaca": {
        "label": "Alpaca Algo Trader Plus",
        "public_reference": "docs/WINNER_ARCHETYPE_V002_READINESS_ROADMAP.md#alpaca",
        "advertised_price": {"amount_usd": 99, "period": "month", "evidence_level": "public_documentation", "verified_for_contract": False},
        "claimed": {"broad_market_regime_inputs", "sip_minute_bars", "sip_quotes", "sip_trades"},
    },
    "massive": {
        "label": "Massive Stocks Advanced",
        "public_reference": "docs/WINNER_ARCHETYPE_V002_READINESS_ROADMAP.md#massive",
        "advertised_price": {"amount_usd": 199, "period": "month", "evidence_level": "public_documentation", "verified_for_contract": False},
        "claimed": {"broad_market_regime_inputs", "catalyst_broad_news", "corporate_actions", "security_master", "sip_minute_bars", "sip_quotes", "sip_trades", "symbol_lineage", "universe_snapshot"},
    },
    "point_in_time_security_master_tbd": {
        "label": "Prospective point-in-time security-master provider",
        "public_reference": None,
        "advertised_price": {"amount_usd": None, "period": "quote_required", "evidence_level": "provider_claim", "verified_for_contract": False},
        "claimed": set(),
    },
    "nasdaq_nyse_status_sources": {
        "label": "Nasdaq and NYSE public halt/status sources",
        "public_reference": "docs/WINNER_ARCHETYPE_V002_READINESS_ROADMAP.md#exchange-directories-calendars-and-halts",
        "advertised_price": {"amount_usd": 0, "period": "public_access", "evidence_level": "public_documentation", "verified_for_contract": False},
        "claimed": {"exchange_calendar", "halt_market_status"},
    },
    "broad_news_provider_tbd": {
        "label": "Prospective broad news and catalyst provider",
        "public_reference": "docs/WINNER_ARCHETYPE_V002_READINESS_ROADMAP.md#broad-news-and-specialist-catalysts",
        "advertised_price": {"amount_usd": None, "period": "quote_required", "evidence_level": "public_documentation", "verified_for_contract": False},
        "claimed": {"catalyst_broad_news", "catalyst_specialist_regulatory"},
    },
}


def build_decision_matrix(contract: Mapping[str, object]) -> dict[str, object]:
    datasets = [item["dataset"] for item in contract["requirements"]]
    providers = []
    for provider_id, definition in PROVIDERS.items():
        capabilities = []
        for dataset in datasets:
            claimed = dataset in definition["claimed"]
            capabilities.append(
                {
                    "dataset": dataset,
                    "status": "claimed" if claimed else "unknown",
                    "highest_evidence_level": "public_documentation" if claimed else None,
                    "evidence_levels": ["public_documentation"] if claimed else [],
                    "readiness_credit": False,
                    "evidence_reference": definition["public_reference"] if claimed else None,
                    "notes": "public_or_marketing_claim_requires_written_schema_license_and_completeness_proof" if claimed else "not_yet_assessed",
                }
            )
        providers.append(
            {
                "provider_id": provider_id,
                "label": definition["label"],
                "pricing": definition["advertised_price"],
                "one_time_acquisition_cost_usd": None,
                "recurring_cost_usd": definition["advertised_price"]["amount_usd"],
                "estimated_archive_size_bytes": None,
                "estimated_working_storage_bytes": None,
                "capabilities": capabilities,
            }
        )
    payload = {
        "schema_version": DECISION_MATRIX_SCHEMA,
        "matrix_version": "winner-archetype-provider-decision-matrix-v002",
        "protocol_identity": contract["protocol_identity"],
        "capability_contract_identity": contract["contract_identity"],
        "allowed_statuses": list(EVIDENCE_STATUSES),
        "providers": providers,
        "minimum_compliant_source_sets": [],
        "minimum_compliant_source_set_status": "blocked_no_proven_capabilities",
        "planning_estimates": {
            "full_market_sip_compressed_bytes_low": 1_500_000_000_000,
            "full_market_sip_compressed_bytes_high": 2_000_000_000_000,
            "working_storage_bytes_low": 4_000_000_000_000,
            "working_storage_bytes_high": 6_000_000_000_000,
            "pricing_lower_bound_usd": 298,
            "pricing_planning_range_usd": [1000, 10000],
            "status": "planning_assumptions_not_quotes_or_readiness_evidence",
        },
        "pilot_authorized": False,
    }
    return {**payload, "matrix_identity": canonical_hash(payload)}


def minimum_compliant_source_sets(
    contract: Mapping[str, object], decision_matrix: Mapping[str, object]
) -> list[list[str]]:
    """Return smallest provider combinations only when every proof gate is met."""
    requirements = {item["dataset"]: item for item in contract["requirements"]}
    covered: dict[str, set[str]] = {}
    for provider in decision_matrix["providers"]:
        provider_coverage = set()
        for cell in provider["capabilities"]:
            required = requirements[cell["dataset"]]
            evidence = set(cell["evidence_levels"])
            gates = set(required["minimum_capability_evidence"])
            gates.update(required["minimum_entitlement_evidence"])
            gates.update(required["minimum_readiness_evidence"])
            proven = cell["status"] == "proven" and gates <= evidence
            if cell["readiness_credit"] != proven:
                raise CapabilityContractError(
                    "Readiness credit must equal the complete evidence-gate result"
                )
            if proven:
                provider_coverage.add(cell["dataset"])
        covered[provider["provider_id"]] = provider_coverage
    target = set(requirements)
    provider_ids = sorted(covered)
    for size in range(1, len(provider_ids) + 1):
        solutions = [
            list(group)
            for group in combinations(provider_ids, size)
            if set().union(*(covered[item] for item in group)) >= target
        ]
        if solutions:
            return solutions
    return []


def validate_contract_and_matrix(
    contract: Mapping[str, object],
    decision_matrix: Mapping[str, object],
    protocol: WinnerArchetypeProtocolV002,
    source_matrix: SourceRequirementsMatrix,
) -> None:
    if dict(contract) != build_capability_contract(protocol, source_matrix):
        raise CapabilityContractError("Capability contract is stale, incomplete, or tampered")
    if dict(decision_matrix) != build_decision_matrix(contract):
        raise CapabilityContractError("Provider decision matrix is stale, incomplete, or tampered")
    if any(
        capability["readiness_credit"]
        for provider in decision_matrix["providers"]
        for capability in provider["capabilities"]
    ):
        raise CapabilityContractError("Unproven provider evidence cannot receive readiness credit")
    if minimum_compliant_source_sets(contract, decision_matrix):
        raise CapabilityContractError("Seed matrix cannot contain a compliant provider set")


def canonical_contract_files(protocol_path: Path, source_matrix_path: Path) -> tuple[bytes, bytes]:
    protocol = load_protocol_v002(protocol_path)
    source_matrix = load_source_requirements_v002(source_matrix_path)
    contract = build_capability_contract(protocol, source_matrix)
    decision_matrix = build_decision_matrix(contract)
    return canonical_json(contract), canonical_json(decision_matrix)
