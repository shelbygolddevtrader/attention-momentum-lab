"""Write-once, project-external storage contracts for catalyst observations."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable, Mapping

from aml.catalyst_observations import canonical_json


class CatalystStorageError(RuntimeError):
    """Protected catalyst storage violation."""


FINALIZATION_IDENTITY_FIELDS = {
    "partition", "record_count", "content_hash", "finalized_at",
}


def validate_storage_root(root: Path, repository_root: Path) -> Path:
    raw = Path(root)
    repository = Path(repository_root).resolve()
    if not raw.is_absolute() or ".." in raw.parts:
        raise CatalystStorageError("Storage root must be absolute without traversal")
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise CatalystStorageError("Storage root contains a symlink component")
    if not raw.is_dir() or raw.is_symlink() or raw.resolve() != raw:
        raise CatalystStorageError("Storage root must be an existing resolved directory")
    try:
        raw.relative_to(repository)
    except ValueError:
        pass
    else:
        raise CatalystStorageError("Catalyst data must remain outside the repository")
    info = raw.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise CatalystStorageError("Storage ownership or permissions are unsafe")
    if not os.access(raw, os.W_OK | os.X_OK):
        raise CatalystStorageError("Storage root is not writable")
    return raw


def _component(value: str, field: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise CatalystStorageError(f"Unsafe partition component: {field}")
    return value


def _validate_private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise CatalystStorageError("Protected storage component is not a resolved directory")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise CatalystStorageError("Protected storage component permissions are unsafe")


def _prepare_destination_components(root: Path, parent: Path) -> None:
    _validate_private_directory(root)
    current = root
    for part in parent.relative_to(root).parts:
        current = current / part
        if not current.exists():
            current.mkdir(mode=0o700)
            _fsync_directory(current.parent)
        _validate_private_directory(current)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reject_finalized(path: Path, root: Path) -> None:
    current = path.parent
    while current != root.parent:
        if (current / ".finalized.json").exists():
            raise CatalystStorageError("Finalized catalyst partition is immutable")
        if current == root:
            break
        current = current.parent


def write_once(
    root: Path, relative: Path, record: Mapping[str, object],
    validator: Callable[[Mapping[str, object]], None],
) -> Path:
    validator(record)
    if relative.is_absolute() or ".." in relative.parts:
        raise CatalystStorageError("Relative storage path is unsafe")
    destination = root / relative
    _reject_finalized(destination, root)
    _prepare_destination_components(root, destination.parent)
    if destination.is_symlink():
        raise CatalystStorageError("Destination is a symlink")
    payload = canonical_json(dict(record))
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as exc:
            raise CatalystStorageError("Write-once catalyst record already exists") from exc
        _fsync_directory(destination.parent)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def finalize_partition(partition: Path, identity: Mapping[str, object]) -> Path:
    _validate_private_directory(partition)
    if set(identity) != FINALIZATION_IDENTITY_FIELDS:
        raise CatalystStorageError("Finalization identity fields differ")
    _component(str(identity["partition"]), "partition")
    if type(identity["record_count"]) is not int or identity["record_count"] < 0:
        raise CatalystStorageError("Finalization record_count is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(identity["content_hash"])):
        raise CatalystStorageError("Finalization content_hash is invalid")
    try:
        finalized_at = datetime.fromisoformat(
            str(identity["finalized_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CatalystStorageError("Finalization timestamp is malformed") from exc
    if finalized_at.tzinfo is None or finalized_at.utcoffset() is None:
        raise CatalystStorageError("Finalization timestamp must include a timezone")
    marker = partition / ".finalized.json"
    payload = canonical_json({
        "schema_version": "aml.catalyst.partition-finalization.v001", **identity,
    })
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".finalized.", suffix=".tmp", dir=partition,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, marker, follow_symlinks=False)
        except FileExistsError as exc:
            raise CatalystStorageError("Partition is already finalized") from exc
        _fsync_directory(partition)
    finally:
        if temporary.exists():
            temporary.unlink()
    return marker


def raw_path(record: Mapping[str, object]) -> Path:
    day = str(record["acquisition_timestamp"])[:10]
    return Path("raw") / _component(str(record["vendor"]), "vendor") / day / f"{record['raw_record_hash']}.json"


def observation_path(record: Mapping[str, object]) -> Path:
    day = str(record["publication_timestamp"])[:10]
    return Path("normalized") / day / _component(str(record["symbol"]), "symbol") / f"{record['observation_id']}.json"


def cluster_path(record: Mapping[str, object]) -> Path:
    day = str(record["created_at"])[:10]
    return Path("clusters") / day / f"{record['cluster_id']}.json"


def source_path(record: Mapping[str, object]) -> Path:
    version = _component(str(record["metadata_version"]), "metadata_version")
    return Path("sources") / _component(str(record["source_id"]), "source_id") / f"{version}.json"


def manifest_path(record: Mapping[str, object]) -> Path:
    day = str(record["acquisition_started_at"])[:10]
    return Path("manifests") / _component(str(record["vendor"]), "vendor") / day / f"{record['manifest_id']}.json"


def parser_audit_path(record: Mapping[str, object]) -> Path:
    day = str(record["parsed_at"])[:10]
    return Path("parser-audit") / _component(str(record["parser_version"]), "parser_version") / day / f"{record['audit_id']}.json"


def read_canonical(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if payload != canonical_json(value):
        raise CatalystStorageError("Stored record is not canonical JSON")
    return value
