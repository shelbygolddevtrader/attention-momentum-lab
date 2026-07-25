import json
from pathlib import Path

import pytest

from aml.catalyst_collectors import MockCatalystCollector, SyntheticCatalystNormalizer
from aml.catalyst_observations import validate_observation, validate_raw_record
from aml.catalyst_storage import (
    CatalystStorageError, finalize_partition, observation_path, raw_path,
    read_canonical, validate_storage_root, write_once,
)


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/catalysts/synthetic_story_v001.json"


def records():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = MockCatalystCollector(
        (payload,), "2024-01-03T14:00:10+00:00",
    ).collect()[0]
    return raw, SyntheticCatalystNormalizer().normalize(raw)


def roots(tmp_path):
    repository = tmp_path / "repository"
    storage = tmp_path / "storage"
    repository.mkdir(mode=0o700)
    storage.mkdir(mode=0o700)
    storage.chmod(0o700)
    return repository, validate_storage_root(storage, repository)


def test_storage_root_rejects_repository_traversal_permissions_and_symlinks(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir(mode=0o700)
    inside = repository / "data"
    inside.mkdir(mode=0o700)
    with pytest.raises(CatalystStorageError, match="outside"):
        validate_storage_root(inside, repository)
    with pytest.raises(CatalystStorageError, match="traversal"):
        validate_storage_root(tmp_path / ".." / "storage", repository)
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o755)
    unsafe.chmod(0o755)
    with pytest.raises(CatalystStorageError, match="permissions"):
        validate_storage_root(unsafe, repository)
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(CatalystStorageError, match="symlink"):
        validate_storage_root(linked, repository)


def test_raw_and_normalized_records_use_deterministic_canonical_paths(tmp_path):
    repository, storage = roots(tmp_path)
    raw, observation = records()
    raw_file = write_once(storage, raw_path(raw), raw, validate_raw_record)
    normalized_file = write_once(
        storage, observation_path(observation), observation, validate_observation,
    )
    assert raw_file.relative_to(storage).parts[:2] == ("raw", "synthetic-mock")
    assert normalized_file.relative_to(storage).parts[:2] == ("normalized", "2024-01-03")
    assert read_canonical(raw_file) == raw
    assert read_canonical(normalized_file) == observation
    assert validate_storage_root(storage, repository) == storage


def test_write_once_and_finalized_partition_are_immutable(tmp_path):
    _, storage = roots(tmp_path)
    raw, _ = records()
    relative = raw_path(raw)
    written = write_once(storage, relative, raw, validate_raw_record)
    with pytest.raises(CatalystStorageError, match="already exists"):
        write_once(storage, relative, raw, validate_raw_record)
    marker = finalize_partition(written.parent, {"partition": "synthetic-2024-01-03"})
    assert marker.is_file()
    alternate = dict(raw)
    alternate["source_record_id"] = "synthetic-example-002"
    with pytest.raises(CatalystStorageError, match="Finalized"):
        write_once(
            storage, written.parent.relative_to(storage) / "alternate.json",
            alternate, validate_raw_record,
        )
    with pytest.raises(CatalystStorageError, match="already finalized"):
        finalize_partition(written.parent, {"partition": "synthetic-2024-01-03"})


def test_relative_path_traversal_and_destination_symlink_fail(tmp_path):
    _, storage = roots(tmp_path)
    raw, _ = records()
    with pytest.raises(CatalystStorageError, match="unsafe"):
        write_once(storage, Path("..") / "escape.json", raw, validate_raw_record)
    target = storage / "target.json"
    target.write_text("synthetic", encoding="utf-8")
    destination = storage / "linked.json"
    destination.symlink_to(target)
    with pytest.raises(CatalystStorageError, match="symlink"):
        write_once(storage, Path("linked.json"), raw, validate_raw_record)
