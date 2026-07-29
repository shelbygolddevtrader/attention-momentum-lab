from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

import pytest

from aml.historical_catalyst_ingestion import (
    HistoricalIngestionError, _digest, build_ingestion_plan, raw_identity,
)
from aml.historical_catalyst_providers import (
    HistoricalProviderError, InputLimits, LocalHistoricalFileProvider,
)


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/historical_catalysts/synthetic_batch.jsonl"
AS_OF = "2024-12-31T23:59:59+00:00"


def limits(**changes):
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
    values.update(changes)
    return InputLimits(**values)


def roots(tmp_path):
    repository = tmp_path / "repository"
    destination = tmp_path / "destination"
    repository.mkdir(mode=0o700, parents=True)
    destination.mkdir(mode=0o700, parents=True)
    destination.chmod(0o700)
    return repository, destination


def cli_command(mode, destination, source=FIXTURE):
    return [
        sys.executable,
        str(ROOT / "scripts/ingest_historical_catalysts.py"),
        mode,
        "--provider", "synthetic-local",
        "--provider-version", "provider-v001",
        "--source", str(source.resolve()),
        "--destination-root", str(destination),
        "--as-of", AS_OF,
        "--normalizer-version", "historical-synthetic-normalizer-v001",
        "--deduplicator-version", "exact-observational-content-v001",
        "--max-total-source-bytes", "200000",
        "--max-record-bytes", "50000",
        "--max-records", "20",
        "--max-nesting-depth", "10",
        "--max-string-length", "10000",
        "--max-headline-length", "1000",
        "--max-summary-length", "5000",
        "--max-source-files", "10",
    ]


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        0,
        -10,
        1.25,
        "synthetic",
        ["a", 1, False],
        {"nested": {"value": [1, 2, 3]}},
    ],
)
def test_canonical_identity_is_stable_for_supported_finite_values(value):
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert _digest(value) == _digest(json.loads(serialized))


def test_raw_identity_is_independent_of_mapping_insertion_order():
    fields = {
        "schema_version": "aml.catalyst.raw.v002",
        "provider": "synthetic-local",
        "provider_version": "v001",
        "provider_release": "release-v001",
        "source_identifier": "story-001",
        "retrieval_timestamp": "2024-01-01T00:00:00+00:00",
        "source_file_hash": "a" * 64,
        "source_record_index": 0,
        "source_record_byte_hash": "b" * 64,
        "logical_payload_hash": "c" * 64,
        "normalization_version": "normalizer-v001",
        "revision_of_raw_id": None,
    }
    assert raw_identity(fields) == raw_identity(dict(reversed(list(fields.items()))))


@pytest.mark.parametrize(
    "identifier",
    ["../escape", "/absolute", "nested/path", "back\\slash", "space value", ""],
)
def test_path_like_provider_identifiers_fail(tmp_path, identifier):
    repository, destination = roots(tmp_path)
    provider = LocalHistoricalFileProvider(identifier, "provider-v001")
    with pytest.raises(HistoricalIngestionError, match="partition identifier|non-empty"):
        build_ingestion_plan(
            provider, (FIXTURE.resolve(),), destination, repository, AS_OF, limits(),
        )


@pytest.mark.parametrize("depth_limit", [1, 2, 3])
def test_nesting_limit_fails_without_truncation(tmp_path, depth_limit):
    source = tmp_path / "nested.json"
    value = json.loads(FIXTURE.read_text(encoding="utf-8").splitlines()[0])
    value["payload"]["extra"] = {"a": {"b": {"c": "value"}}}
    source.write_text(json.dumps(value), encoding="utf-8")
    provider = LocalHistoricalFileProvider("synthetic-local", "provider-v001")
    with pytest.raises(HistoricalProviderError, match="nesting"):
        provider.read((source.resolve(),), limits(max_nesting_depth=depth_limit))


def test_duplicate_immutable_identifier_from_provider_fails(tmp_path):
    base = LocalHistoricalFileProvider("synthetic-local", "provider-v001")
    record = base.read((FIXTURE.resolve(),), limits())[0]

    @dataclass(frozen=True)
    class DuplicateProvider:
        provider: str = "synthetic-local"
        provider_version: str = "provider-v001"

        def read(self, paths, configured_limits):
            return (record, record)

    repository, destination = roots(tmp_path)
    with pytest.raises(HistoricalIngestionError, match="Duplicate immutable raw identifier"):
        build_ingestion_plan(
            DuplicateProvider(), (FIXTURE.resolve(),), destination, repository,
            AS_OF, limits(),
        )


def test_source_file_count_and_record_count_bounds(tmp_path):
    first = tmp_path / "one.jsonl"
    second = tmp_path / "two.jsonl"
    first.write_bytes(FIXTURE.read_bytes())
    second.write_bytes(FIXTURE.read_bytes())
    provider = LocalHistoricalFileProvider("synthetic-local", "provider-v001")
    with pytest.raises(HistoricalProviderError, match="Source-file count"):
        provider.read((first.resolve(), second.resolve()), limits(max_source_files=1))
    with pytest.raises(HistoricalProviderError, match="Record count"):
        provider.read((first.resolve(),), limits(max_records=1))


def test_configurable_limits_cannot_exceed_absolute_safety_ceilings():
    with pytest.raises(HistoricalProviderError, match="absolute safety ceiling"):
        limits(max_record_bytes=2_000_001).validate()


def test_cli_dry_run_is_deterministic_and_writes_nothing(tmp_path):
    repository, destination = roots(tmp_path)
    command = cli_command("dry-run", destination)
    first = subprocess.run(command, cwd=repository, capture_output=True, text=True, check=True)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["writes_performed"] == 0
    assert list(destination.iterdir()) == []


def test_cli_publish_and_status_use_manifest_boundary(tmp_path):
    repository, destination = roots(tmp_path)
    published = subprocess.run(
        cli_command("publish", destination),
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(published.stdout)
    status = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ingest_historical_catalysts.py"),
            "status",
            "--destination-root", str(destination),
            "--run-id", result["run_id"],
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(status.stdout)["status"] == "published"


def test_source_filename_and_absolute_root_do_not_change_plan_identity(tmp_path):
    first_source = tmp_path / "one" / "first-name.jsonl"
    second_source = tmp_path / "two" / "renamed.jsonl"
    first_source.parent.mkdir()
    second_source.parent.mkdir()
    first_source.write_bytes(FIXTURE.read_bytes())
    second_source.write_bytes(FIXTURE.read_bytes())
    first_repository, first_destination = roots(tmp_path / "first-roots")
    second_repository, second_destination = roots(tmp_path / "second-roots")
    first = build_ingestion_plan(
        LocalHistoricalFileProvider("synthetic-local", "provider-v001"),
        (first_source.resolve(),), first_destination, first_repository, AS_OF, limits(),
    )
    second = build_ingestion_plan(
        LocalHistoricalFileProvider("synthetic-local", "provider-v001"),
        (second_source.resolve(),), second_destination, second_repository, AS_OF, limits(),
    )
    assert first.run_id == second.run_id
    assert first.summary() == second.summary()
