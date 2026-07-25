"""Write-once, project-external storage contracts for catalyst observations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Callable, Mapping

from aml.catalyst_observations import canonical_json


class CatalystStorageError(RuntimeError):
    """Protected catalyst storage violation."""


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
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise CatalystStorageError(f"Unsafe partition component: {field}")
    return value


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
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.is_symlink():
        raise CatalystStorageError("Destination is a symlink")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise CatalystStorageError("Write-once catalyst record already exists") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_json(dict(record)))
        handle.flush()
        os.fsync(handle.fileno())
    return destination


def finalize_partition(partition: Path, identity: Mapping[str, object]) -> Path:
    if not partition.is_dir() or partition.is_symlink():
        raise CatalystStorageError("Partition must be an existing directory")
    marker = partition / ".finalized.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(marker, flags, 0o600)
    except FileExistsError as exc:
        raise CatalystStorageError("Partition is already finalized") from exc
    payload = {"schema_version": "aml.catalyst.partition-finalization.v001", **identity}
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_json(payload))
        handle.flush()
        os.fsync(handle.fileno())
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
