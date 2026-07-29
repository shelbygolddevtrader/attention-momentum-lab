import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import time

import pytest

import aml.historical_catalyst_ingestion as ingestion
from aml.catalyst_storage import write_once
from aml.historical_catalyst_ingestion import (
    HistoricalIngestionError, build_ingestion_plan, inspect_batch_status,
    preflight_plan, publish_plan,
)
from aml.historical_catalyst_providers import (
    HistoricalProviderError, InputLimits, LocalHistoricalFileProvider,
)


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures/historical_catalysts"
JSONL = FIXTURES / "synthetic_batch.jsonl"
ARRAY = FIXTURES / "synthetic_array.json"
AS_OF = "2024-12-31T23:59:59+00:00"


def limits(**overrides):
    values = {
        "max_total_source_bytes": 200_000,
        "max_record_bytes": 50_000,
        "max_records": 20,
        "max_nesting_depth": 10,
        "max_string_length": 10_000,
        "max_headline_length": 1_000,
        "max_summary_length": 5_000,
        "max_source_files": 10,
    }
    values.update(overrides)
    return InputLimits(**values)


def roots(tmp_path):
    repository = tmp_path / "repository"
    destination = tmp_path / "registry"
    repository.mkdir(mode=0o700, parents=True)
    destination.mkdir(mode=0o700, parents=True)
    destination.chmod(0o700)
    return repository, destination


def provider():
    return LocalHistoricalFileProvider("synthetic-local", "provider-v001")


def plan(tmp_path, source=JSONL, **kwargs):
    repository, destination = roots(tmp_path)
    result = build_ingestion_plan(
        provider(), (source.resolve(),), destination, repository, AS_OF, limits(), **kwargs,
    )
    return result, repository, destination


def first_input():
    return json.loads(JSONL.read_text(encoding="utf-8").splitlines()[0])


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def test_jsonl_preserves_exact_record_bytes_and_distinct_logical_identity():
    records = provider().read((JSONL.resolve(),), limits())
    lines = JSONL.read_bytes().splitlines(keepends=True)
    assert records[0].source_record_bytes == lines[0]
    assert records[0].source_record_byte_length == len(lines[0])
    assert records[0].source_record_byte_hash != ingestion._digest(records[0].logical_record)
    assert base64.b64decode(
        ingestion._source_record(records[0], provider().provider, provider().provider_version)[
            "source_record_bytes_base64"
        ]
    ) == lines[0]


def test_json_array_records_source_file_identity_and_byte_envelope_limitation(tmp_path):
    result, _, _ = plan(tmp_path, ARRAY)
    raw = next(item.record for item in result.artifacts if item.kind == "raw")
    source = next(item.record for item in result.artifacts if item.kind == "source")
    assert raw["source_record_byte_envelope"] == "source-file-only"
    assert raw["source_record_bytes_base64"] is None
    assert source["json_array_byte_envelope_limitation"] is True
    assert raw["source_file_hash"] == source["source_file_hash"]


def test_deterministic_plan_across_roots_source_order_timezone_and_clock(tmp_path, monkeypatch):
    source_a = tmp_path / "a" / "z.jsonl"
    source_b = tmp_path / "a" / "a.jsonl"
    source_a.parent.mkdir()
    lines = JSONL.read_bytes().splitlines(keepends=True)
    source_a.write_bytes(lines[0])
    source_b.write_bytes(lines[1])
    repo_one = tmp_path / "repo-one"
    root_one = tmp_path / "root-one"
    repo_two = tmp_path / "repo-two"
    root_two = tmp_path / "root-two"
    for path in (repo_one, root_one, repo_two, root_two):
        path.mkdir(mode=0o700)
        path.chmod(0o700)
    original_timezone = os.environ.get("TZ")
    try:
        monkeypatch.setattr(time, "time", lambda: 1.0)
        monkeypatch.setenv("TZ", "UTC")
        if hasattr(time, "tzset"):
            time.tzset()
        first = build_ingestion_plan(
            provider(), (source_a.resolve(), source_b.resolve()), root_one, repo_one,
            AS_OF, limits(),
        )
        monkeypatch.setattr(time, "time", lambda: 9_999_999_999.0)
        monkeypatch.setenv("TZ", "America/Denver")
        if hasattr(time, "tzset"):
            time.tzset()
        second = build_ingestion_plan(
            provider(), (source_b.resolve(), source_a.resolve()), root_two, repo_two,
            AS_OF, limits(),
        )
    finally:
        if original_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_timezone
        if hasattr(time, "tzset"):
            time.tzset()
    assert first.run_id == second.run_id
    assert first.summary() == second.summary()
    assert str(tmp_path) not in json.dumps(first.summary(), sort_keys=True)


def test_dry_plan_creates_no_directories_or_files(tmp_path):
    result, _, destination = plan(tmp_path)
    assert result.artifacts
    assert list(destination.iterdir()) == []


def test_protected_forward_outcome_storage_is_inaccessible(tmp_path):
    repository = tmp_path / "repository"
    destination = tmp_path / "sealed" / "validation-extension"
    repository.mkdir(mode=0o700)
    destination.mkdir(mode=0o700, parents=True)
    destination.chmod(0o700)
    with pytest.raises(HistoricalIngestionError, match="protected outcome"):
        build_ingestion_plan(
            provider(), (JSONL.resolve(),), destination, repository, AS_OF, limits(),
        )


def test_publication_is_ordered_and_manifest_is_only_publication_boundary(tmp_path, monkeypatch):
    result, _, destination = plan(tmp_path)
    events = []
    original = ingestion.write_once

    def recording_write(root, relative, record, validator):
        events.append(relative.parts[-2] if relative.name != "manifest.json" else "manifest")
        return original(root, relative, record, validator)

    monkeypatch.setattr(ingestion, "write_once", recording_write)
    manifest = publish_plan(destination, result)
    assert events[0] == "raw"
    assert events[-1] == "manifest"
    assert manifest == destination / result.manifest_path
    assert inspect_batch_status(destination, result.run_id)["status"] == "published"


def test_partial_matching_files_require_explicit_recovery_and_are_never_deleted(tmp_path):
    result, repository, destination = plan(tmp_path)
    first = result.artifacts[0]
    preserved = write_once(
        destination, first.relative_path, first.record, ingestion.VALIDATORS[first.kind],
    )
    original = preserved.read_bytes()
    assert inspect_batch_status(destination, result.run_id)["status"] == "unpublished-incomplete"
    with pytest.raises(HistoricalIngestionError, match="explicit recovery"):
        preflight_plan(destination, result, recovery=False)
    recovered = build_ingestion_plan(
        provider(), (JSONL.resolve(),), destination, repository, AS_OF, limits(), recovery=True,
    )
    assert preflight_plan(destination, recovered, recovery=True)["matching"] == 1
    publish_plan(destination, recovered, recovery=True)
    assert preserved.read_bytes() == original
    assert inspect_batch_status(destination, result.run_id)["status"] == "published"


def test_partial_mismatch_fails_closed_and_recovery_never_deletes(tmp_path):
    result, repository, destination = plan(tmp_path)
    target = destination / result.artifacts[0].relative_path
    current = destination
    for part in result.artifacts[0].relative_path.parent.parts:
        current = current / part
        current.mkdir(mode=0o700)
    target.write_bytes(b"mismatch\n")
    target.chmod(0o600)
    with pytest.raises(HistoricalIngestionError, match="differs"):
        build_ingestion_plan(
            provider(), (JSONL.resolve(),), destination, repository, AS_OF,
            limits(), recovery=True,
        )
    assert target.read_bytes() == b"mismatch\n"
    assert not (destination / result.manifest_path).exists()


def test_manifest_cannot_publish_before_every_artifact_verifies(tmp_path, monkeypatch):
    result, _, destination = plan(tmp_path)
    original = ingestion.write_once

    def corrupting_write(root, relative, record, validator):
        path = original(root, relative, record, validator)
        if relative == result.artifacts[-1].relative_path:
            path.write_bytes(b"changed\n")
        return path

    monkeypatch.setattr(ingestion, "write_once", corrupting_write)
    with pytest.raises(HistoricalIngestionError, match="verify"):
        publish_plan(destination, result)
    assert not (destination / result.manifest_path).exists()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'{"a":1,"a":2}\n', "duplicate keys"),
        (b"\xef\xbb\xbf{}", "BOM"),
        (b'"\xff"', "UTF-8"),
        (b'{"value":NaN}', "not finite"),
        (b'{"value":Infinity}', "not finite"),
        (b'{"value":-Infinity}', "not finite"),
    ],
)
def test_strict_parser_rejects_unsafe_json(tmp_path, payload, message):
    source = tmp_path / "bad.jsonl"
    source.write_bytes(payload)
    with pytest.raises(HistoricalProviderError, match=message):
        provider().read((source.resolve(),), limits())


def test_bounds_unknown_fields_and_missing_provenance_fail(tmp_path):
    source = tmp_path / "input.json"
    value = first_input()
    value["unknown"] = True
    write_json(source, value)
    with pytest.raises(HistoricalProviderError, match="missing or unknown"):
        provider().read((source.resolve(),), limits())
    value = first_input()
    value.pop("source_identifier")
    write_json(source, value)
    with pytest.raises(HistoricalProviderError, match="missing or unknown"):
        provider().read((source.resolve(),), limits())
    write_json(source, first_input())
    with pytest.raises(HistoricalProviderError, match="byte limit"):
        provider().read((source.resolve(),), limits(max_record_bytes=20))


def test_secret_like_provenance_and_forward_outcomes_fail_without_value_echo(tmp_path):
    source = tmp_path / "secret.json"
    secret = "do-not-echo-this-value"
    value = first_input()
    value["source_identifier"] = f"api_key={secret}"
    write_json(source, value)
    repository, destination = roots(tmp_path / "roots-one")
    with pytest.raises(HistoricalIngestionError, match="Secret-like") as denied:
        build_ingestion_plan(provider(), (source.resolve(),), destination, repository, AS_OF, limits())
    assert secret not in str(denied.value)
    value = first_input()
    value["payload"]["future_return"] = 1.0
    write_json(source, value)
    repository, destination = roots(tmp_path / "roots-two")
    with pytest.raises(HistoricalIngestionError, match="forward outcomes"):
        build_ingestion_plan(provider(), (source.resolve(),), destination, repository, AS_OF, limits())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("retrieval_timestamp", "not-a-time", "malformed"),
        ("retrieval_timestamp", "2024-01-03T14:00:10", "timezone"),
        ("retrieval_timestamp", "2025-01-01T00:00:00+00:00", "exceeds as_of"),
    ],
)
def test_retrieval_timestamp_validation(tmp_path, field, value, message):
    source = tmp_path / "input.json"
    record = first_input()
    record[field] = value
    write_json(source, record)
    repository, destination = roots(tmp_path / "roots")
    with pytest.raises(HistoricalIngestionError, match=message):
        build_ingestion_plan(
            provider(), (source.resolve(),), destination, repository, AS_OF, limits(),
        )


def test_future_publication_and_first_seen_order_fail(tmp_path):
    source = tmp_path / "input.json"
    record = first_input()
    record["payload"]["publication_timestamp"] = "2024-01-03T14:00:11+00:00"
    write_json(source, record)
    repository, destination = roots(tmp_path / "roots-one")
    with pytest.raises(HistoricalIngestionError, match="point-in-time"):
        build_ingestion_plan(provider(), (source.resolve(),), destination, repository, AS_OF, limits())
    record = first_input()
    record["payload"]["first_seen_timestamp"] = "2024-01-03T13:59:59+00:00"
    write_json(source, record)
    repository, destination = roots(tmp_path / "roots-two")
    with pytest.raises(HistoricalIngestionError, match="point-in-time"):
        build_ingestion_plan(provider(), (source.resolve(),), destination, repository, AS_OF, limits())


def test_ambiguous_correction_predecessor_fails(tmp_path):
    source = tmp_path / "ambiguous.jsonl"
    first = first_input()
    second = deepcopy(first)
    second["retrieval_timestamp"] = "2024-01-03T14:01:00+00:00"
    second["payload"]["headline"] = "SYNTHETIC: corrected content"
    source.write_text(
        "\n".join(json.dumps(item, separators=(",", ":")) for item in (first, second)) + "\n",
        encoding="utf-8",
    )
    repository, destination = roots(tmp_path / "roots")
    with pytest.raises(HistoricalIngestionError, match="unresolved or ambiguous"):
        build_ingestion_plan(provider(), (source.resolve(),), destination, repository, AS_OF, limits())


def test_explicit_unambiguous_correction_publishes_new_revision(tmp_path):
    repository, destination = roots(tmp_path / "roots")
    original_source = tmp_path / "original.json"
    original_input = first_input()
    write_json(original_source, original_input)
    original_plan = build_ingestion_plan(
        provider(), (original_source.resolve(),), destination, repository, AS_OF, limits(),
    )
    original_raw = next(item for item in original_plan.artifacts if item.kind == "raw")
    original_bytes = ingestion.canonical_json(original_raw.record)
    publish_plan(destination, original_plan)

    correction_source = tmp_path / "correction.json"
    correction = deepcopy(original_input)
    correction["revision_of_raw_id"] = original_raw.identity
    correction["retrieval_timestamp"] = "2024-01-03T14:01:00+00:00"
    correction["payload"]["headline"] = "SYNTHETIC: corrected fictional announcement"
    write_json(correction_source, correction)
    correction_plan = build_ingestion_plan(
        provider(), (correction_source.resolve(),), destination, repository, AS_OF, limits(),
    )
    correction_raw = next(item.record for item in correction_plan.artifacts if item.kind == "raw")
    correction_observation = next(
        item.record for item in correction_plan.artifacts if item.kind == "observation"
    )
    assert correction_raw["revision_of_raw_id"] == original_raw.identity
    assert correction_observation["revision_of_observation_id"] is not None
    assert correction_raw["raw_id"] != original_raw.identity
    publish_plan(destination, correction_plan)
    assert (destination / original_raw.relative_path).read_bytes() == original_bytes
    assert len(list((destination / "ingestions").glob("*/manifest.json"))) == 2


def test_correction_order_and_cycles_fail_closed():
    first = {
        "raw_id": "a" * 64, "provider": "p", "source_identifier": "s",
        "logical_payload_hash": "1" * 64,
        "retrieval_timestamp": "2024-01-02T00:00:00+00:00",
        "revision_of_raw_id": "b" * 64,
    }
    second = {
        "raw_id": "b" * 64, "provider": "p", "source_identifier": "s",
        "logical_payload_hash": "2" * 64,
        "retrieval_timestamp": "2024-01-01T00:00:00+00:00",
        "revision_of_raw_id": "a" * 64,
    }
    with pytest.raises(HistoricalIngestionError, match="cycle"):
        ingestion._validate_lineage([first, second], {})
    ordered_parent = {**first, "revision_of_raw_id": None}
    ordered_child = {
        **second,
        "revision_of_raw_id": ordered_parent["raw_id"],
        "retrieval_timestamp": ordered_parent["retrieval_timestamp"],
    }
    with pytest.raises(HistoricalIngestionError, match="cannot precede or equal"):
        ingestion._validate_lineage([ordered_parent, ordered_child], {})
    competing_one = {
        **second,
        "revision_of_raw_id": ordered_parent["raw_id"],
        "retrieval_timestamp": "2024-01-03T00:00:00+00:00",
    }
    competing_two = {
        **second,
        "raw_id": "c" * 64,
        "logical_payload_hash": "3" * 64,
        "revision_of_raw_id": ordered_parent["raw_id"],
        "retrieval_timestamp": "2024-01-04T00:00:00+00:00",
    }
    with pytest.raises(HistoricalIngestionError, match="ambiguous competing revisions"):
        ingestion._validate_lineage([ordered_parent, competing_one, competing_two], {})


def test_conservative_dedup_preserves_every_record_and_observation(tmp_path):
    result, _, _ = plan(tmp_path)
    kinds = [artifact.kind for artifact in result.artifacts]
    assert kinds.count("raw") == 2
    assert kinds.count("observation") == 2
    assert kinds.count("cluster") == 1
    cluster = next(item.record for item in result.artifacts if item.kind == "cluster")
    assert len(cluster["member_observation_ids"]) == 2
