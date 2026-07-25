import json
from pathlib import Path

import pytest

from aml.catalyst_collectors import MockCatalystCollector, SyntheticCatalystNormalizer
from aml.catalyst_observations import (
    CLUSTER_SCHEMA_VERSION, MANIFEST_SCHEMA_VERSION, PARSER_AUDIT_SCHEMA_VERSION,
    SOURCE_SCHEMA_VERSION, CatalystSchemaError, cluster_id, validate_cluster,
    manifest_id, parser_audit_id, validate_manifest, validate_observation,
    validate_parser_audit, validate_raw_record, validate_source_metadata,
)


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/catalysts/synthetic_story_v001.json"


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def raw_and_observation():
    raw = MockCatalystCollector(
        (payload(),), "2024-01-03T14:00:10+00:00",
    ).collect()[0]
    return raw, SyntheticCatalystNormalizer().normalize(raw)


def test_synthetic_collector_preserves_raw_before_normalization():
    raw, observation = raw_and_observation()
    validate_raw_record(raw)
    validate_observation(observation)
    assert raw["payload"]["headline"].startswith("SYNTHETIC:")
    assert observation["raw_record_hash"] == raw["raw_record_hash"]
    assert observation["publication_timestamp"] != observation["first_seen_timestamp"]
    assert observation["first_seen_timestamp"] != observation["acquisition_timestamp"]


def test_raw_record_rejects_unknown_fields_and_unsupported_schema():
    raw, _ = raw_and_observation()
    raw["unknown"] = "synthetic"
    with pytest.raises(CatalystSchemaError, match="missing or unknown"):
        validate_raw_record(raw)
    raw, _ = raw_and_observation()
    raw["schema_version"] = "aml.catalyst.raw.v999"
    with pytest.raises(CatalystSchemaError, match="Unsupported"):
        validate_raw_record(raw)


@pytest.mark.parametrize("field", ("headline", "direction"))
def test_missing_and_unknown_observation_fields_fail(field):
    _, observation = raw_and_observation()
    observation.pop(field)
    with pytest.raises(CatalystSchemaError, match="missing or unknown"):
        validate_observation(observation)
    _, observation = raw_and_observation()
    observation["unexpected"] = 1
    with pytest.raises(CatalystSchemaError, match="missing or unknown"):
        validate_observation(observation)


def test_invalid_and_naive_timestamps_fail():
    raw, _ = raw_and_observation()
    raw["acquisition_timestamp"] = "2024-01-03T14:00:10"
    with pytest.raises(CatalystSchemaError, match="timezone"):
        validate_raw_record(raw)
    _, observation = raw_and_observation()
    observation["first_seen_timestamp"] = "not-a-time"
    with pytest.raises(CatalystSchemaError, match="malformed"):
        validate_observation(observation)


def test_boolean_does_not_satisfy_ordinal_score():
    _, observation = raw_and_observation()
    observation["materiality"] = True
    with pytest.raises(CatalystSchemaError, match="integer"):
        validate_observation(observation)


def test_observation_identity_detects_any_normalized_change():
    _, observation = raw_and_observation()
    observation["normalized_summary"] = "Changed after identity creation"
    with pytest.raises(CatalystSchemaError, match="identity"):
        validate_observation(observation)


def test_raw_hash_detects_payload_mutation():
    raw, _ = raw_and_observation()
    raw["payload"]["headline"] = "Changed"
    with pytest.raises(CatalystSchemaError, match="hash"):
        validate_raw_record(raw)


def test_secrets_and_forward_outcomes_are_rejected_without_echoing_values():
    secret = "never-echo-this-secret"
    bad = payload()
    bad["api_key"] = secret
    with pytest.raises(CatalystSchemaError) as denied:
        MockCatalystCollector((bad,), "2024-01-03T14:00:10+00:00").collect()
    assert secret not in str(denied.value)
    bad = payload()
    bad["future_return"] = 0.5
    with pytest.raises(CatalystSchemaError, match="forward outcomes"):
        MockCatalystCollector((bad,), "2024-01-03T14:00:10+00:00").collect()


def test_mock_collector_rejects_non_synthetic_input():
    bad = payload()
    bad["synthetic"] = False
    with pytest.raises(ValueError, match="non-synthetic"):
        MockCatalystCollector((bad,), "2024-01-03T14:00:10+00:00").collect()


def test_duplicate_cluster_has_stable_identity():
    _, observation = raw_and_observation()
    cluster = {
        "schema_version": CLUSTER_SCHEMA_VERSION,
        "cluster_id": "pending",
        "member_observation_ids": [observation["observation_id"]],
        "cluster_basis": "Synthetic exact-story fixture",
        "created_at": "2024-01-03T14:00:11+00:00",
        "parser_version": "synthetic-parser-v001",
        "synthetic": True,
    }
    cluster["cluster_id"] = cluster_id(cluster)
    validate_cluster(cluster)
    assert cluster_id(cluster) == cluster["cluster_id"]


def test_source_metadata_requires_explicit_licensing():
    source = {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_id": "synthetic-ir", "source_name": "Synthetic IR",
        "source_type": "investor_relations", "license_name": "Synthetic fixture only",
        "license_url": "synthetic://license", "redistribution_permitted": False,
        "retention_policy": "Repository fixture only",
        "terms_reviewed_at": "2024-01-01T00:00:00+00:00",
        "metadata_version": "v001", "synthetic": True,
    }
    validate_source_metadata(source)
    source["redistribution_permitted"] = 1
    with pytest.raises(CatalystSchemaError, match="boolean"):
        validate_source_metadata(source)


def test_manifest_and_parser_audit_reconcile():
    raw, observation = raw_and_observation()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION, "manifest_id": "pending",
        "vendor": "synthetic-mock", "vendor_release": "synthetic-release-v001",
        "parser_version": "synthetic-parser-v001",
        "acquisition_started_at": "2024-01-03T14:00:09+00:00",
        "acquisition_finished_at": "2024-01-03T14:00:12+00:00",
        "raw_record_hashes": [raw["raw_record_hash"]], "record_count": 1,
        "synthetic": True,
    }
    manifest["manifest_id"] = manifest_id(manifest)
    validate_manifest(manifest)
    manifest["record_count"] = True
    manifest["manifest_id"] = manifest_id(manifest)
    with pytest.raises(CatalystSchemaError, match="count"):
        validate_manifest(manifest)
    audit = {
        "schema_version": PARSER_AUDIT_SCHEMA_VERSION, "audit_id": "pending",
        "raw_record_hash": raw["raw_record_hash"],
        "observation_id": observation["observation_id"],
        "parser_version": "synthetic-parser-v001",
        "parsed_at": "2024-01-03T14:00:12+00:00", "status": "normalized",
        "warning_codes": [], "synthetic": True,
    }
    audit["audit_id"] = parser_audit_id(audit)
    validate_parser_audit(audit)
