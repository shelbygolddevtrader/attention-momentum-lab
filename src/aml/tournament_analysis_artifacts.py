"""Write-once, hash-verified artifacts derived from finalized tournaments."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import MappingProxyType
from typing import Mapping


ANALYSIS_SCHEMA_VERSION = "aml.tournament-analysis.v1"
_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_component(value: str, label: str) -> str:
    if not isinstance(value, str) or not _COMPONENT.fullmatch(value):
        raise ValueError(f"Unsafe {label} component")
    if value in {".", ".."} or "holdout" in value.casefold():
        raise ValueError(f"Protected or unsafe {label} component")
    return value


def _reject_symlinks(path: Path, stop: Path) -> None:
    """Reject existing symlinks from ``stop`` through ``path`` inclusive."""
    stop = stop.resolve()
    candidate = Path(os.path.abspath(path))
    try:
        candidate.relative_to(stop)
    except ValueError as exc:
        raise ValueError("Analysis path escapes artifact root") from exc
    current = stop
    for component in candidate.relative_to(stop).parts:
        current = current / component
        if current.exists() and current.is_symlink():
            raise ValueError(f"Symlinked artifact path is prohibited: {current}")


def _safe_artifact_name(name: str) -> str:
    _safe_component(name, "artifact name")
    if Path(name).suffix not in {".csv", ".json", ".md", ".txt"}:
        raise ValueError(f"Unsupported analysis artifact extension: {name}")
    return name


@dataclass(frozen=True)
class AnalysisProvenance:
    analysis_name: str
    analysis_version: str
    source_commit: str
    source_worktree_dirty: bool
    source_worktree_fingerprint: str
    deterministic_configuration: Mapping[str, object]

    def __post_init__(self) -> None:
        _safe_component(self.analysis_name, "analysis name")
        _safe_component(self.analysis_version, "analysis version")
        if not isinstance(self.source_commit, str) or not self.source_commit:
            raise ValueError("source_commit is required")
        if not isinstance(self.source_worktree_dirty, bool):
            raise ValueError("source_worktree_dirty must be boolean")
        if (
            not isinstance(self.source_worktree_fingerprint, str)
            or len(self.source_worktree_fingerprint) != 64
        ):
            raise ValueError("source_worktree_fingerprint must be SHA-256")
        try:
            frozen = json.loads(_canonical_json(dict(self.deterministic_configuration)))
        except (TypeError, ValueError) as exc:
            raise ValueError("deterministic_configuration must be canonical JSON") from exc
        object.__setattr__(self, "deterministic_configuration", MappingProxyType(frozen))


@dataclass(frozen=True)
class FinalizedTournamentSource:
    run_id: str
    final_directory: Path
    manifest: Mapping[str, object]
    manifest_sha256: str
    artifact_hashes: Mapping[str, str]


@dataclass(frozen=True)
class PublishedAnalysis:
    analysis_id: str
    directory: Path
    manifest: Mapping[str, object]


def verify_finalized_tournament(
    artifacts_root: Path, run_id: str
) -> FinalizedTournamentSource:
    """Load a finalized run and fail closed on any manifest-covered mutation."""
    run_id = _safe_component(run_id, "run ID")
    root = Path(os.path.abspath(artifacts_root))
    _reject_symlinks(root, root)
    final = root / run_id / "final"
    _reject_symlinks(final, root)
    if not final.is_dir() or final.is_symlink():
        raise ValueError("Finalized tournament directory is missing or unsafe")
    manifest_path = final / "run_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Finalized run manifest is missing or unsafe")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("Finalized run manifest is malformed") from exc
    if manifest.get("run_id") != run_id or manifest.get("status") != "completed":
        raise ValueError("Tournament source is not the requested completed run")
    artifact_hashes = manifest.get("artifact_hashes")
    if not isinstance(artifact_hashes, dict) or not artifact_hashes:
        raise ValueError("Finalized run manifest lacks artifact hashes")
    verified: dict[str, str] = {}
    for raw_name, expected in sorted(artifact_hashes.items()):
        name = _safe_artifact_name(raw_name)
        path = final / name
        _reject_symlinks(path, root)
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Finalized source artifact is missing or unsafe: {name}")
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(f"Finalized source artifact hash mismatch: {name}")
        verified[name] = actual
    return FinalizedTournamentSource(
        run_id=run_id,
        final_directory=final,
        manifest=MappingProxyType(manifest),
        manifest_sha256=_sha256_bytes(manifest_bytes),
        artifact_hashes=MappingProxyType(verified),
    )


def _analysis_identity(
    source: FinalizedTournamentSource, provenance: AnalysisProvenance
) -> tuple[str, dict[str, object]]:
    identity = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "source_tournament_run_id": source.run_id,
        "source_manifest_sha256": source.manifest_sha256,
        "source_artifact_hashes": dict(source.artifact_hashes),
        "analysis_name": provenance.analysis_name,
        "analysis_version": provenance.analysis_version,
        "source_commit": provenance.source_commit,
        "source_worktree_dirty": provenance.source_worktree_dirty,
        "source_worktree_fingerprint": provenance.source_worktree_fingerprint,
        "deterministic_configuration": dict(provenance.deterministic_configuration),
    }
    return _sha256_bytes(_canonical_json(identity))[:24], identity


def _validate_existing(directory: Path, expected_manifest: bytes) -> dict[str, object]:
    manifest_path = directory / "analysis_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Existing analysis is incomplete or unsafe")
    if manifest_path.read_bytes() != expected_manifest:
        raise ValueError("Existing deterministic analysis manifest differs")
    manifest = json.loads(expected_manifest)
    for name, expected in manifest["generated_artifact_hashes"].items():
        path = directory / name
        if not path.is_file() or path.is_symlink() or _sha256_file(path) != expected:
            raise ValueError(f"Existing analysis artifact hash mismatch: {name}")
    return manifest


def publish_tournament_analysis(
    artifacts_root: Path,
    run_id: str,
    provenance: AnalysisProvenance,
    generated_artifacts: Mapping[str, bytes],
) -> PublishedAnalysis:
    """Publish deterministic derived bytes outside ``final/`` without overwrite."""
    source = verify_finalized_tournament(artifacts_root, run_id)
    if not generated_artifacts:
        raise ValueError("At least one generated analysis artifact is required")
    artifacts: dict[str, bytes] = {}
    for raw_name, value in sorted(generated_artifacts.items()):
        name = _safe_artifact_name(raw_name)
        if name == "analysis_manifest.json":
            raise ValueError("analysis_manifest.json is reserved")
        if not isinstance(value, bytes):
            raise ValueError("Generated analysis artifacts must be bytes")
        artifacts[name] = value
    analysis_id, identity = _analysis_identity(source, provenance)
    root = Path(os.path.abspath(artifacts_root))
    analysis_root = root / source.run_id / "analysis"
    destination = analysis_root / analysis_id
    _reject_symlinks(analysis_root, root)
    _reject_symlinks(destination, root)
    generated_hashes = {
        name: _sha256_bytes(value) for name, value in sorted(artifacts.items())
    }
    manifest = {
        **identity,
        "analysis_id": analysis_id,
        "generated_artifact_hashes": generated_hashes,
    }
    manifest_bytes = _canonical_json(manifest)
    if destination.exists():
        existing = _validate_existing(destination, manifest_bytes)
        return PublishedAnalysis(analysis_id, destination, MappingProxyType(existing))
    analysis_root.mkdir(parents=True, exist_ok=True)
    _reject_symlinks(analysis_root, root)
    temporary = Path(tempfile.mkdtemp(prefix=f".{analysis_id}.", dir=analysis_root))
    try:
        for name, value in artifacts.items():
            (temporary / name).write_bytes(value)
        (temporary / "analysis_manifest.json").write_bytes(manifest_bytes)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return PublishedAnalysis(analysis_id, destination, MappingProxyType(manifest))


def load_tournament_analysis(directory: Path) -> Mapping[str, bytes]:
    """Load already-generated analysis bytes without recalculation."""
    directory = Path(os.path.abspath(directory))
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Analysis directory is missing or unsafe")
    manifest_path = directory / "analysis_manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Analysis manifest is missing or unsafe")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != ANALYSIS_SCHEMA_VERSION:
        raise ValueError("Unsupported analysis schema")
    loaded: dict[str, bytes] = {}
    for name, expected in sorted(manifest.get("generated_artifact_hashes", {}).items()):
        _safe_artifact_name(name)
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Analysis artifact is missing or unsafe: {name}")
        value = path.read_bytes()
        if _sha256_bytes(value) != expected:
            raise ValueError(f"Analysis artifact hash mismatch: {name}")
        loaded[name] = value
    return MappingProxyType(loaded)
