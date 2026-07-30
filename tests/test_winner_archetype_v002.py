from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.winner_archetype_contracts import load_experiment_spec
from aml.winner_archetype_v002 import (
    CAPABILITY_SCHEMA,
    ENTITLEMENT_SCHEMA,
    EVIDENCE_SCHEMA,
    EXPERIMENT_BINDING_SCHEMA,
    INPUT_MANIFEST_SCHEMA,
    READINESS_EVIDENCE_SCHEMA,
    SECURITY_IDENTITY_SCHEMA,
    SESSION_SCHEMA,
    SYMBOL_LINEAGE_SCHEMA,
    UNIVERSE_SNAPSHOT_SCHEMA,
    V001_EXPERIMENT_IDENTITY,
    CompletenessState,
    CorporateActionRecord,
    DiscoveryExperimentBinding,
    EntitlementEvidence,
    EvidenceAssertion,
    ImmutableInputManifest,
    ProviderCapability,
    ReadinessEvidenceBundle,
    RequirementReadinessEvidence,
    SecurityIdentity,
    SessionContract,
    SourceRequirementsMatrix,
    SymbolLineageRecord,
    UniverseConstituent,
    UniverseSnapshot,
    V002Error,
    authorize_discovery_path,
    build_readiness_report,
    deterministic_unique_records,
    load_protocol_v002,
    load_readiness_evidence_v002,
    load_source_requirements_v002,
    validate_expected_coverage,
)


ROOT = Path(__file__).parents[1]
PROTOCOL_PATH = ROOT / "config/winner_archetype_protocol_v002.json"
MATRIX_PATH = ROOT / "config/winner_archetype_source_requirements_v002.json"
V001_PATH = ROOT / "config/winner_archetype_experiment_v001.json"
CLI = ROOT / "scripts/plan_winner_archetype_discovery_v002.py"
PROTOCOL = load_protocol_v002(PROTOCOL_PATH)
MATRIX = load_source_requirements_v002(MATRIX_PATH)
HASHES = tuple(character * 64 for character in "123456789abcdef")


def security(**changes):
    values = {
        "schema_version": SECURITY_IDENTITY_SCHEMA,
        "canonical_security_id": "security-001",
        "listing_id": "listing-001",
        "issuer_id": "issuer-001",
        "identifier_source": "synthetic-point-in-time-master",
        "identifier_source_version": "source-v001",
        "effective_from": "2024-01-01T00:00:00-05:00",
        "effective_to": None,
        "first_known_at": "2024-01-01T00:00:00-05:00",
        "revision": 1,
        "supersedes_identity": None,
    }
    values.update(changes)
    return SecurityIdentity(**values)


def lineage(**changes):
    values = {
        "schema_version": SYMBOL_LINEAGE_SCHEMA,
        "canonical_security_id": "security-001",
        "listing_id": "listing-001",
        "symbol": "TEST",
        "effective_from": "2024-01-01T00:00:00-05:00",
        "effective_to": None,
        "first_known_at": "2024-01-01T00:00:00-05:00",
        "source_manifest_hash": HASHES[0],
        "revision": 1,
        "supersedes_record_hash": None,
    }
    values.update(changes)
    return SymbolLineageRecord(**values)


def constituent(**changes):
    values = {
        "security_identity_hash": security().identity,
        "symbol_lineage_hash": lineage().identity,
        "canonical_security_id": "security-001",
        "listing_id": "listing-001",
        "symbol": "TEST",
        "primary_exchange": "XNAS",
        "security_type": "common_stock",
        "listing_status": "active",
        "selection_timestamp": "2024-06-03T09:25:00-04:00",
        "eligibility_effective_from": "2024-01-01T00:00:00-05:00",
        "eligibility_effective_to": None,
        "first_known_at": "2024-01-01T00:00:00-05:00",
        "tradable": True,
        "quoteable": True,
        "sip_covered": True,
    }
    values.update(changes)
    return UniverseConstituent(**values)


def snapshot(*constituents):
    members = tuple(constituents or (constituent(),))
    return UniverseSnapshot(
        schema_version=UNIVERSE_SNAPSHOT_SCHEMA,
        session="2024-06-03",
        selection_timestamp="2024-06-03T09:25:00-04:00",
        source_manifest_hashes=(HASHES[0],),
        coverage_state=CompletenessState.COMPLETE,
        expected_constituent_count=len(members),
        constituents=members,
    )


def session(**changes):
    values = {
        "schema_version": SESSION_SCHEMA,
        "session": "2024-06-03",
        "timezone": "America/New_York",
        "calendar_identity": HASHES[0],
        "scheduled_open": "2024-06-03T09:30:00-04:00",
        "scheduled_close": "2024-06-03T16:00:00-04:00",
        "premarket_start": "2024-06-03T04:00:00-04:00",
        "selection_cutoff": "2024-06-03T09:25:00-04:00",
        "early_close": False,
        "calendar_state": CompletenessState.COMPLETE,
    }
    values.update(changes)
    return SessionContract(**values)


def capability(**changes):
    values = {
        "schema_version": CAPABILITY_SCHEMA,
        "declaration_id": "synthetic-capability-001",
        "provider_name": "synthetic-provider",
        "provider_version": "provider-v001",
        "dataset": "sip_quotes",
        "capability": "historical-sip-quotes",
        "coverage_start": "2024-01-01",
        "coverage_end": "2025-01-01",
        "market_coverage": "all-US-exchanges",
        "security_coverage": "all-listed-common-stock",
        "session_coverage": "04:00-20:00-America/New_York",
        "feed_type": "sip",
        "timestamp_precision": "nanosecond",
        "point_in_time_guarantee": "provider-receipt-timestamp",
        "correction_support": "append-only",
        "historical_revision_support": "versioned",
        "pagination_or_file_identity": "file-001",
        "completeness_evidence_hash": HASHES[0],
        "source_role": "authoritative",
        "licensing_status": "approved-synthetic",
        "retention_status": "approved-synthetic",
        "declared_at": "2026-07-29T12:00:00+00:00",
    }
    values.update(changes)
    return ProviderCapability(**values)


def entitlement(**changes):
    values = {
        "schema_version": ENTITLEMENT_SCHEMA,
        "capability_identity": capability().identity,
        "account_scope_hash": HASHES[1],
        "verified_at": "2026-07-29T12:00:00+00:00",
        "valid_from": "2026-07-29T00:00:00+00:00",
        "valid_to": "2026-07-30T00:00:00+00:00",
        "status": CompletenessState.COMPLETE,
        "evidence_hash": HASHES[2],
        "licensing_status": "approved-synthetic",
        "retention_status": "approved-synthetic",
    }
    values.update(changes)
    return EntitlementEvidence(**values)


def manifest(**changes):
    values = {
        "schema_version": INPUT_MANIFEST_SCHEMA,
        "manifest_version": "manifest-v002",
        "dataset": "sip_quotes",
        "execution_phase": "discovery",
        "feed_type": "sip",
        "source_name": "synthetic-provider",
        "source_role": "authoritative",
        "source_version": "source-v001",
        "query_or_file_identity": "query-001",
        "retrieval_timestamp": "2026-07-29T12:00:00+00:00",
        "coverage_start": "2024-06-03T08:00:00+00:00",
        "coverage_end": "2024-06-03T20:00:00+00:00",
        "raw_sha256": (HASHES[0],),
        "normalized_sha256": (HASHES[1],),
        "parser_version": "parser-v002",
        "normalization_version": "normalizer-v002",
        "completeness_state": CompletenessState.COMPLETE,
        "revision": 1,
        "supersedes_manifest_hash": None,
        "correction_timestamp": None,
    }
    values.update(changes)
    return ImmutableInputManifest(**values)


def experiment(**changes):
    values = {
        "schema_version": EXPERIMENT_BINDING_SCHEMA,
        "protocol_identity": PROTOCOL.identity,
        "source_requirements_identity": MATRIX.identity,
        "calendar_identity": HASHES[0],
        "session_plan_identity": HASHES[1],
        "universe_snapshot_identities": (HASHES[2],),
        "security_master_identity": HASHES[3],
        "symbol_lineage_identity": HASHES[4],
        "corporate_actions_identity": HASHES[5],
        "trades_manifest_identity": HASHES[6],
        "quotes_manifest_identity": HASHES[7],
        "bars_manifest_identity": HASHES[8],
        "halts_manifest_identity": HASHES[9],
        "catalysts_manifest_identity": HASHES[10],
        "provider_capability_identities": (HASHES[11],),
        "entitlement_identities": (HASHES[12],),
        "parser_identities": (HASHES[13],),
        "normalization_identities": (HASHES[14],),
        "execution_phase": "discovery",
    }
    values.update(changes)
    return DiscoveryExperimentBinding(**values)


def readiness_evidence(*, conflict_dataset=None):
    requirements = []
    for index, requirement in enumerate(MATRIX.requirements):
        declared = capability(
            declaration_id=f"synthetic-{requirement.dataset}",
            dataset=requirement.dataset,
            capability=requirement.required_capability,
            feed_type="sip" if requirement.dataset in {"sip_trades", "sip_quotes", "sip_minute_bars"} else "not_applicable",
            pagination_or_file_identity=f"file-{requirement.dataset}",
        )
        authorized = None
        if requirement.entitlement_status != "not_required":
            authorized = entitlement(
                capability_identity=declared.identity,
                valid_to="2026-08-01T00:00:00+00:00",
            )
        acquired = manifest(
            dataset=requirement.dataset,
            feed_type=declared.feed_type,
            query_or_file_identity=f"query-{index:02d}-{requirement.dataset}",
        )
        requirements.append(
            RequirementReadinessEvidence(
                dataset=requirement.dataset,
                required_capability=requirement.required_capability,
                capability=declared,
                entitlement=authorized,
                input_manifests=(acquired,),
                coverage_evidence_hashes=(HASHES[3],),
                expected_security_set_hash=HASHES[4],
                observed_security_set_hash=HASHES[4],
                expected_session_set_hash=HASHES[5],
                observed_session_set_hash=HASHES[5],
                conflict_status="conflicting" if requirement.dataset == conflict_dataset else "clear",
            )
        )
    return ReadinessEvidenceBundle(
        schema_version=READINESS_EVIDENCE_SCHEMA,
        evidence_version="synthetic-readiness-v001",
        protocol_identity=PROTOCOL.identity,
        source_requirements_identity=MATRIX.identity,
        as_of="2026-07-30T00:00:00+00:00",
        requirements=tuple(requirements),
    )


def test_repository_protocol_and_source_matrix_are_strict_and_deterministic():
    assert PROTOCOL.identity == load_protocol_v002(PROTOCOL_PATH).identity
    assert MATRIX.identity == load_source_requirements_v002(MATRIX_PATH).identity
    assert PROTOCOL.schema_version.endswith("v002")
    assert MATRIX.schema_version.endswith("v002")
    assert len(MATRIX.requirements) == 13
    assert PROTOCOL.identity == "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
    assert MATRIX.identity == "4a0f350cd24ae2ef5509cbfc72a6994a1bb9df9d3e2dedcfe3354b2cfe4a168c"


def test_universe_identity_changes_for_constituent_identifier_and_eligibility_time():
    base = constituent()
    changed_identifier = constituent(canonical_security_id="security-002")
    changed_time = constituent(first_known_at="2024-05-01T00:00:00-04:00")
    assert len({snapshot(base).identity, snapshot(changed_identifier).identity, snapshot(changed_time).identity}) == 3


def test_ticker_change_preserves_security_identity_but_changes_symbol_lineage_identity():
    stable = security()
    old = lineage()
    new = lineage(
        symbol="TWO",
        effective_from="2024-05-01T00:00:00-04:00",
        first_known_at="2024-05-01T00:00:00-04:00",
    )
    assert stable.canonical_security_id == "security-001"
    assert old.canonical_security_id == new.canonical_security_id
    assert old.identity != new.identity


@pytest.mark.parametrize(
    "change,message",
    [
        ({"first_known_at": "2024-06-04T00:00:00-04:00"}, "Future-known"),
        ({"eligibility_effective_from": "2024-06-04T00:00:00-04:00"}, "Future eligibility"),
        ({"eligibility_effective_to": "2024-06-03T09:00:00-04:00"}, "Delisted"),
        ({"listing_status": "suspended"}, "Only active"),
    ],
)
def test_future_delisting_suspension_and_eligibility_cannot_leak_backward(change, message):
    with pytest.raises(V002Error, match=message):
        constituent(**change)


@pytest.mark.parametrize(
    "change,message",
    [
        ({"security_type": "etf"}, "common stock"),
        ({"primary_exchange": "OTCM"}, "exchange"),
        ({"tradable": False}, "tradable"),
        ({"quoteable": 1}, "boolean"),
    ],
)
def test_excluded_types_exchanges_and_unproven_flags_cannot_enter_universe(change, message):
    with pytest.raises(V002Error, match=message):
        constituent(**change)


def test_future_known_and_not_yet_effective_actions_cannot_adjust_history():
    action = CorporateActionRecord(
        action_id="action-001",
        canonical_security_id="security-001",
        action_type="split",
        announcement_timestamp="2024-06-03T12:00:00-04:00",
        first_known_at="2024-06-03T12:01:00-04:00",
        effective_timestamp="2024-06-10T09:30:00-04:00",
        source_manifest_hash=HASHES[0],
        revision=1,
        supersedes_record_hash=None,
    )
    assert not action.usable_at("2024-06-03T09:25:00-04:00", adjustment=False)
    assert not action.usable_at("2024-06-04T09:25:00-04:00", adjustment=True)
    assert action.usable_at("2024-06-10T09:30:00-04:00", adjustment=True)


def test_missing_security_and_session_coverage_fail_closed():
    with pytest.raises(V002Error, match="securities"):
        validate_expected_coverage(("one", "two"), ("one",), ("2024-06-03",), ("2024-06-03",))
    with pytest.raises(V002Error, match="sessions"):
        validate_expected_coverage(("one",), ("one",), ("2024-06-03", "2024-06-04"), ("2024-06-03",))


def test_early_close_is_eligible_explicit_and_uses_scheduled_last_minute():
    early = session(
        session="2024-07-03",
        scheduled_open="2024-07-03T09:30:00-04:00",
        scheduled_close="2024-07-03T13:00:00-04:00",
        premarket_start="2024-07-03T04:00:00-04:00",
        selection_cutoff="2024-07-03T09:25:00-04:00",
        early_close=True,
    )
    assert early.outcome_end == "2024-07-03T12:59:00-04:00"
    assert early.identity == replace(early).identity


@pytest.mark.parametrize(
    "day,offset",
    (("2024-03-11", "-04:00"), ("2024-11-04", "-05:00")),
)
def test_session_contract_is_dst_explicit(day, offset):
    winter_or_summer = session(
        session=day,
        scheduled_open=f"{day}T09:30:00{offset}",
        scheduled_close=f"{day}T16:00:00{offset}",
        premarket_start=f"{day}T04:00:00{offset}",
        selection_cutoff=f"{day}T09:25:00{offset}",
    )
    assert datetime.fromisoformat(winter_or_summer.selection_cutoff).astimezone(timezone.utc).tzinfo == timezone.utc


def test_calendar_conflicts_and_incomplete_calendar_block_session():
    with pytest.raises(V002Error, match="calendar"):
        session(calendar_state=CompletenessState.CONFLICTING)
    with pytest.raises(V002Error, match="Early-close"):
        session(early_close=True)
    with pytest.raises(V002Error, match="offset"):
        session(
            scheduled_open="2024-06-03T09:30:00-05:00",
            scheduled_close="2024-06-03T16:00:00-05:00",
            premarket_start="2024-06-03T04:00:00-05:00",
            selection_cutoff="2024-06-03T09:25:00-05:00",
        )


@pytest.mark.parametrize("evidence_type", ("quote_issue", "halt", "catalyst"))
def test_missing_evidence_cannot_be_represented_as_negative(evidence_type):
    with pytest.raises(V002Error, match="Negative evidence"):
        EvidenceAssertion(
            schema_version=EVIDENCE_SCHEMA,
            evidence_type=evidence_type,
            subject_id="security-001",
            interval_start="2024-06-03T04:00:00-04:00",
            interval_end="2024-06-03T09:25:00-04:00",
            assertion="absent",
            coverage_state=CompletenessState.COVERAGE_UNKNOWN,
            coverage_manifest_hash=None,
            source_record_hashes=(),
        )


def test_proven_absence_requires_and_binds_complete_coverage():
    evidence = EvidenceAssertion(
        schema_version=EVIDENCE_SCHEMA,
        evidence_type="halt",
        subject_id="security-001",
        interval_start="2024-06-03T09:30:00-04:00",
        interval_end="2024-06-03T16:00:00-04:00",
        assertion="absent",
        coverage_state=CompletenessState.COMPLETE,
        coverage_manifest_hash=HASHES[0],
        source_record_hashes=(),
    )
    assert evidence.identity


def test_conflicting_duplicate_records_fail_and_identical_duplicates_deduplicate():
    first = manifest()
    same = manifest()
    assert deterministic_unique_records((same, first)) == (first,)
    conflicting = manifest(normalized_sha256=(HASHES[2],))
    with pytest.raises(V002Error, match="Conflicting duplicate"):
        deterministic_unique_records((first, conflicting))


@pytest.mark.parametrize("feed", ("iex", "delayed", "indicative", "consolidated-derived"))
def test_non_sip_and_feed_substitution_are_rejected(feed):
    with pytest.raises(V002Error, match="SIP"):
        manifest(feed_type=feed)
    with pytest.raises(V002Error, match="Non-SIP"):
        capability(feed_type=feed)


def test_future_dated_capability_entitlement_and_manifest_are_rejected_as_of():
    with pytest.raises(V002Error, match="future-dated"):
        capability().validate_as_of("2026-07-29T11:59:59+00:00")
    with pytest.raises(V002Error, match="future-dated"):
        entitlement().validate_as_of("2026-07-29T11:59:59+00:00")
    with pytest.raises(V002Error, match="future-dated"):
        manifest().validate_as_of("2026-07-29T11:59:59+00:00")


def test_corrected_and_revised_manifests_require_append_only_lineage():
    with pytest.raises(V002Error, match="append-only"):
        manifest(completeness_state=CompletenessState.CORRECTED)
    with pytest.raises(V002Error, match="supersedes"):
        manifest(revision=2, correction_timestamp="2026-07-29T13:00:00+00:00")
    corrected = manifest(
        revision=2,
        supersedes_manifest_hash=manifest().identity,
        correction_timestamp="2026-07-29T13:00:00+00:00",
        normalized_sha256=(HASHES[2],),
        completeness_state=CompletenessState.CORRECTED,
    )
    assert corrected.identity != manifest().identity


@pytest.mark.parametrize(
    "state",
    (
        CompletenessState.INCOMPLETE,
        CompletenessState.CONFLICTING,
        CompletenessState.UNAVAILABLE,
        CompletenessState.COVERAGE_UNKNOWN,
        CompletenessState.ENTITLEMENT_UNVERIFIED,
    ),
)
def test_blocking_manifest_states_cannot_enter_experiment(state):
    with pytest.raises(V002Error, match="Blocking"):
        manifest(completeness_state=state)


def test_provider_capability_and_account_entitlement_are_separate_identities():
    declaration = capability()
    evidence = entitlement(capability_identity=declaration.identity)
    assert declaration.identity != evidence.identity
    assert evidence.capability_identity == declaration.identity


def test_experiment_identity_binds_every_input_family():
    first = experiment()
    second = experiment(quotes_manifest_identity="0" * 64)
    assert first.identity != second.identity


def test_source_matrix_identity_changes_when_requirement_changes():
    requirements = list(MATRIX.requirements)
    requirements[0] = replace(requirements[0], cost_status="quoted")
    changed = SourceRequirementsMatrix(MATRIX.schema_version, MATRIX.matrix_version, tuple(requirements))
    assert changed.identity != MATRIX.identity


def test_discovery_paths_reject_protected_traversal_escape_and_symlink(tmp_path):
    allowed = tmp_path / "approved"
    allowed.mkdir()
    safe = allowed / "input.json"
    safe.write_text("{}", encoding="utf-8")
    assert authorize_discovery_path(safe, allowed) == safe.resolve()
    for protected in ("validation", "holdout", "sealed", "paper-forward", "production", "operator"):
        path = allowed / protected / "input.json"
        path.parent.mkdir()
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(V002Error, match="protected"):
            authorize_discovery_path(path, allowed)
    with pytest.raises(V002Error, match="traversal"):
        authorize_discovery_path(Path("folder/../input.json"), allowed)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(V002Error, match="escapes"):
        authorize_discovery_path(outside, allowed)
    real = allowed / "real"
    real.mkdir()
    (real / "input.json").write_text("{}", encoding="utf-8")
    link = allowed / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(V002Error, match="symlink"):
        authorize_discovery_path(link / "input.json", allowed)


def test_v001_protocol_and_manifests_are_explicitly_rejected_by_v002():
    with pytest.raises(V002Error, match="not V002-compatible"):
        load_protocol_v002(V001_PATH)
    with pytest.raises(V002Error, match="rejected by V002"):
        manifest(schema_version="aml.winner-archetype.input-manifest.v001")


def test_v001_experiment_identity_remains_frozen():
    assert load_experiment_spec(V001_PATH).identity == V001_EXPERIMENT_IDENTITY


def test_readiness_enumerates_layered_failures_and_never_authorizes_pilot():
    report = build_readiness_report(PROTOCOL, MATRIX)
    assert report["status"] == "blocked"
    assert report["pilot_authorized"] is False
    assert report["empirical_data_opened"] is False
    assert report["eligible_event_count_calculated"] is False
    assert report["unresolved_by_category"] == {
        "capability": 12,
        "entitlement": 12,
        "acquisition": 13,
        "coverage": 7,
        "completeness": 13,
        "conflict": 0,
    }
    assert report["readiness_identity"] == (
        "01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6"
    )
    assert report == build_readiness_report(PROTOCOL, MATRIX)


def test_readiness_evidence_can_reconcile_every_requirement_without_authorizing_pilot():
    evidence = readiness_evidence()
    report = build_readiness_report(PROTOCOL, MATRIX, evidence)
    assert report["status"] == "ready"
    assert report["pilot_authorized"] is False
    assert report["empirical_data_opened"] is False
    assert report["readiness_evidence_identity"] == evidence.identity
    assert all(value == 0 for value in report["unresolved_by_category"].values())
    assert all(item["ready"] for item in report["prerequisites"])
    assert report == build_readiness_report(PROTOCOL, MATRIX, evidence)


def test_readiness_evidence_fails_closed_on_conflict_and_coverage_mismatch():
    conflicted = readiness_evidence(conflict_dataset="sip_quotes")
    report = build_readiness_report(PROTOCOL, MATRIX, conflicted)
    quote = next(item for item in report["prerequisites"] if item["dataset"] == "sip_quotes")
    assert quote["failures"] == ["source_conflict"]

    requirements = list(readiness_evidence().requirements)
    requirements[0] = replace(requirements[0], observed_session_set_hash=HASHES[6])
    mismatched = replace(readiness_evidence(), requirements=tuple(requirements))
    report = build_readiness_report(PROTOCOL, MATRIX, mismatched)
    first = report["prerequisites"][0]
    assert first["failures"] == ["completeness_unproven", "coverage_unproven"]


def test_readiness_evidence_binds_acquisition_to_capability_and_entitlement():
    evidence = readiness_evidence()
    requirement = evidence.requirements[0]
    with pytest.raises(V002Error, match="provider capability"):
        replace(
            requirement,
            input_manifests=(
                replace(requirement.input_manifests[0], source_name="another-provider"),
            ),
        )
    with pytest.raises(V002Error, match="entitlement validity"):
        replace(
            requirement,
            entitlement=replace(
                requirement.entitlement,
                valid_from="2026-07-30T00:00:00+00:00",
                verified_at="2026-07-30T00:00:00+00:00",
            ),
        )


def test_readiness_evidence_rejects_missing_rows_wrong_identity_and_future_evidence():
    evidence = readiness_evidence()
    with pytest.raises(V002Error, match="every source requirement"):
        build_readiness_report(PROTOCOL, MATRIX, replace(evidence, requirements=evidence.requirements[1:]))
    with pytest.raises(V002Error, match="loaded protocol"):
        build_readiness_report(PROTOCOL, MATRIX, replace(evidence, protocol_identity="0" * 64))
    calendar_index = next(
        index
        for index, item in enumerate(evidence.requirements)
        if item.dataset == "exchange_calendar"
    )
    future = replace(
        evidence.requirements[calendar_index].capability,
        declared_at="2026-07-31T00:00:00+00:00",
    )
    with pytest.raises(V002Error, match="future-dated"):
        ReadinessEvidenceBundle.from_mapping(
            _readiness_bundle_mapping(
                replace(
                    evidence,
                    requirements=(
                        *evidence.requirements[:calendar_index],
                        replace(evidence.requirements[calendar_index], capability=future),
                        *evidence.requirements[calendar_index + 1:],
                    ),
                )
            )
        )


def _readiness_bundle_mapping(bundle):
    value = {
        "schema_version": bundle.schema_version,
        "evidence_version": bundle.evidence_version,
        "protocol_identity": bundle.protocol_identity,
        "source_requirements_identity": bundle.source_requirements_identity,
        "as_of": bundle.as_of,
        "requirements": [],
    }
    for requirement in bundle.requirements:
        item = {
            "dataset": requirement.dataset,
            "required_capability": requirement.required_capability,
            "capability": None if requirement.capability is None else vars(requirement.capability),
            "entitlement": None if requirement.entitlement is None else vars(requirement.entitlement),
            "input_manifests": [vars(manifest) for manifest in requirement.input_manifests],
            "coverage_evidence_hashes": list(requirement.coverage_evidence_hashes),
            "expected_security_set_hash": requirement.expected_security_set_hash,
            "observed_security_set_hash": requirement.observed_security_set_hash,
            "expected_session_set_hash": requirement.expected_session_set_hash,
            "observed_session_set_hash": requirement.observed_session_set_hash,
            "conflict_status": requirement.conflict_status,
        }
        if item["entitlement"] is not None:
            item["entitlement"] = {**item["entitlement"], "status": requirement.entitlement.status.value}
        item["input_manifests"] = [
            {**manifest, "completeness_state": requirement.input_manifests[index].completeness_state.value}
            for index, manifest in enumerate(item["input_manifests"])
        ]
        value["requirements"].append(item)
    return value


def test_readiness_evidence_loader_is_strict_and_deterministic(tmp_path):
    evidence = readiness_evidence()
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(_readiness_bundle_mapping(evidence)), encoding="utf-8")
    loaded = load_readiness_evidence_v002(path)
    assert loaded == evidence
    assert loaded.identity == evidence.identity


def test_cli_json_and_text_are_deterministic_blocked_and_write_nothing(tmp_path):
    before = tuple(sorted(path.relative_to(ROOT) for path in ROOT.rglob("*") if ".git" not in path.parts))
    outputs = []
    for seed in ("1", "777"):
        for tz in ("UTC", "America/New_York"):
            environment = os.environ.copy()
            environment.update(PYTHONHASHSEED=seed, TZ=tz, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(
                [sys.executable, str(CLI), "--format", "json"],
                cwd=tmp_path,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 2
            assert result.stderr == ""
            outputs.append(result.stdout)
    assert len(set(outputs)) == 1
    assert json.loads(outputs[0])["status"] == "blocked"
    text = subprocess.run(
        [sys.executable, str(CLI), "--format", "text"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert text.returncode == 2
    assert "eligible_event_count_calculated: false" in text.stdout
    after = tuple(sorted(path.relative_to(ROOT) for path in ROOT.rglob("*") if ".git" not in path.parts))
    assert before == after


def test_manifest_and_experiment_identities_are_hashseed_and_timezone_independent(tmp_path):
    probe = f"""
from aml.winner_archetype_v002 import CompletenessState, DiscoveryExperimentBinding, ImmutableInputManifest
m = ImmutableInputManifest(
    schema_version={INPUT_MANIFEST_SCHEMA!r}, manifest_version='v002', dataset='sip_quotes',
    execution_phase='discovery', feed_type='sip', source_name='synthetic',
    source_role='authoritative', source_version='v1', query_or_file_identity='q1',
    retrieval_timestamp='2026-07-29T12:00:00+00:00',
    coverage_start='2024-06-03T08:00:00+00:00', coverage_end='2024-06-03T20:00:00+00:00',
    raw_sha256=('1'*64,), normalized_sha256=('2'*64,), parser_version='p1',
    normalization_version='n1', completeness_state=CompletenessState.COMPLETE,
    revision=1, supersedes_manifest_hash=None, correction_timestamp=None,
)
e = DiscoveryExperimentBinding(
    schema_version={EXPERIMENT_BINDING_SCHEMA!r}, protocol_identity='1'*64,
    source_requirements_identity='2'*64, calendar_identity='3'*64,
    session_plan_identity='4'*64, universe_snapshot_identities=('5'*64,),
    security_master_identity='6'*64, symbol_lineage_identity='7'*64,
    corporate_actions_identity='8'*64, trades_manifest_identity='9'*64,
    quotes_manifest_identity='a'*64, bars_manifest_identity='b'*64,
    halts_manifest_identity='c'*64, catalysts_manifest_identity='d'*64,
    provider_capability_identities=('e'*64,), entitlement_identities=('f'*64,),
    parser_identities=('0'*64,), normalization_identities=('1'*64,),
    execution_phase='discovery',
)
print(m.identity, e.identity)
"""
    outputs = []
    for seed in ("3", "991"):
        for tz in ("UTC", "America/New_York"):
            environment = os.environ.copy()
            environment.update(PYTHONHASHSEED=seed, TZ=tz, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=tmp_path,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs.append(result.stdout)
    assert len(set(outputs)) == 1


def test_v002_module_has_no_production_or_empirical_imports():
    source = (ROOT / "src/aml/winner_archetype_v002.py").read_text(encoding="utf-8")
    prohibited = (
        "from aml.forward_validation",
        "from aml.portfolio_simulator",
        "from aml.tournament_runner",
        "from aml.trade_simulator",
        "from aml.operator",
    )
    assert not any(item in source for item in prohibited)
