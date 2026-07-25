"""Fail-closed, research-only experiment specifications and lifecycle controls."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping
import unicodedata


EXPERIMENT_SCHEMA_VERSION = "aml.experiment.v001"
BASELINE_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
BASELINE_REFERENCE = {
    "strategy_id": "attention_momentum",
    "strategy_version": "0.1.1",
    "baseline_commit": BASELINE_COMMIT,
}
STATUSES = {
    "draft", "preregistered", "collecting", "sealed", "evaluated",
    "promoted", "rejected", "abandoned",
}
TRANSITIONS = {
    "draft": {"preregistered", "abandoned"},
    "preregistered": {"collecting", "abandoned"},
    "collecting": {"sealed", "abandoned"},
    "sealed": {"evaluated"},
    "evaluated": {"promoted", "rejected"},
    "promoted": set(), "rejected": set(), "abandoned": set(),
}
FIELDS = {
    "schema_version", "experiment_id", "human_name", "status", "hypothesis",
    "rationale", "strategy_baseline", "code_version", "registration_timestamp",
    "registration_author", "permitted_datasets", "prohibited_datasets",
    "feature_definitions", "target_population", "observation_window",
    "comparison_group", "primary_metric", "secondary_metrics",
    "minimum_sample_size", "decision_thresholds", "promotion_criteria",
    "rejection_criteria", "stop_conditions", "multiple_testing_family",
    "leakage_risks", "known_limitations", "notes", "preregistration_hash",
}
IMMUTABLE_FIELDS = FIELDS - {"status", "preregistration_hash"}
PROHIBITED_DATA_TOKENS = {
    "forward-validation outcome", "validation-extension outcome", "sealed outcome",
    "holdout", "profit and loss", "p&l", "future return", "realized outcome",
}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
MAX_SPEC_BYTES = 1_000_000
MAX_TEXT_LENGTH = 20_000


class ExperimentError(ValueError):
    """Specification or lifecycle violation."""


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ExperimentError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExperimentError(f"{field} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExperimentError(f"{field} must include a timezone")
    return parsed


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentError(f"{field} must be a non-empty string")
    if len(value) > MAX_TEXT_LENGTH:
        raise ExperimentError(f"{field} exceeds the size limit")
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise ExperimentError(f"{field} contains control or malformed Unicode")
    return value


def _string_list(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ExperimentError(f"{field} must be a string list")
    for item in value:
        _string(item, f"{field} item")
    if len(set(value)) != len(value):
        raise ExperimentError(f"{field} contains duplicates")
    return value


def _metric(value: object, field: str) -> None:
    required = {"name", "unit", "direction"}
    if not isinstance(value, dict) or set(value) != required:
        raise ExperimentError(f"{field} metric schema is malformed")
    _string(value["name"], f"{field}.name")
    _string(value["unit"], f"{field}.unit")
    if value["direction"] not in {"higher", "lower", "two-sided", "descriptive"}:
        raise ExperimentError(f"{field}.direction is unsupported")


def _criterion(value: object, field: str) -> None:
    required = {"status", "rule", "rationale"}
    if not isinstance(value, dict) or set(value) != required:
        raise ExperimentError(f"{field} schema is malformed")
    if value["status"] not in {"resolved", "unresolved"}:
        raise ExperimentError(f"{field}.status is invalid")
    _string(value["rule"], f"{field}.rule")
    _string(value["rationale"], f"{field}.rationale")


def _minimum_sample(value: object) -> None:
    required = {"status", "value", "rationale"}
    if not isinstance(value, dict) or set(value) != required:
        raise ExperimentError("minimum_sample_size schema is malformed")
    if value["status"] == "unresolved":
        if value["value"] is not None:
            raise ExperimentError("Unresolved minimum sample must have a null value")
    elif value["status"] == "resolved":
        if type(value["value"]) is not int or value["value"] < 1:
            raise ExperimentError("Resolved minimum sample must be a positive integer")
    else:
        raise ExperimentError("minimum_sample_size.status is invalid")
    _string(value["rationale"], "minimum_sample_size.rationale")


def validate_experiment(spec: Mapping[str, object]) -> None:
    if set(spec) != FIELDS:
        missing, unknown = FIELDS - set(spec), set(spec) - FIELDS
        raise ExperimentError(f"Experiment fields differ; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if spec["schema_version"] != EXPERIMENT_SCHEMA_VERSION:
        raise ExperimentError("Unsupported experiment schema version")
    experiment_id = _string(spec["experiment_id"], "experiment_id")
    if not IDENTIFIER.fullmatch(experiment_id):
        raise ExperimentError("experiment_id is malformed")
    for field in (
        "human_name", "hypothesis", "rationale", "registration_author",
        "target_population", "observation_window", "comparison_group",
        "multiple_testing_family", "notes",
    ):
        _string(spec[field], field)
    if spec["status"] not in STATUSES:
        raise ExperimentError("Unknown experiment status")
    if spec["strategy_baseline"] != BASELINE_REFERENCE:
        raise ExperimentError("Invalid frozen baseline reference")
    code_version = _string(spec["code_version"], "code_version")
    if not re.fullmatch(r"[0-9a-f]{40}", code_version):
        raise ExperimentError("code_version must be a full Git commit")
    _timestamp(spec["registration_timestamp"], "registration_timestamp")
    permitted = _string_list(spec["permitted_datasets"], "permitted_datasets")
    prohibited = _string_list(spec["prohibited_datasets"], "prohibited_datasets")
    combined = " ".join(permitted).casefold()
    if any(token in combined for token in PROHIBITED_DATA_TOKENS):
        raise ExperimentError("Experiment permits forward-validation outcome leakage")
    prohibited_text = " ".join(prohibited).casefold()
    if "forward-validation outcome" not in prohibited_text or "holdout" not in prohibited_text:
        raise ExperimentError("Prohibited datasets must explicitly seal forward outcomes and holdout")
    features = spec["feature_definitions"]
    if not isinstance(features, list) or not features:
        raise ExperimentError("feature_definitions must be non-empty")
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != {"name", "definition", "availability_time"}:
            raise ExperimentError("Feature definition schema is malformed")
        for field in feature:
            _string(feature[field], f"feature.{field}")
    _metric(spec["primary_metric"], "primary_metric")
    secondary = spec["secondary_metrics"]
    if not isinstance(secondary, list):
        raise ExperimentError("secondary_metrics must be a list")
    for index, metric in enumerate(secondary):
        _metric(metric, f"secondary_metrics[{index}]")
    _minimum_sample(spec["minimum_sample_size"])
    for field in (
        "decision_thresholds", "promotion_criteria", "rejection_criteria",
        "stop_conditions",
    ):
        _criterion(spec[field], field)
    for field in ("leakage_risks", "known_limitations"):
        _string_list(spec[field], field)
    preregistration_hash = spec["preregistration_hash"]
    if preregistration_hash is not None and (
        not isinstance(preregistration_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", preregistration_hash)
    ):
        raise ExperimentError("preregistration_hash is malformed")
    if spec["status"] == "draft" and preregistration_hash is not None:
        raise ExperimentError("Draft experiments cannot carry a preregistration hash")
    if spec["status"] not in {"draft", "abandoned"} and preregistration_hash is None:
        raise ExperimentError("Post-preregistration status requires a preregistration hash")
    if preregistration_hash is not None:
        if preregistration_hash != specification_hash(spec):
            raise ExperimentError("Preregistered research fields were modified")


def specification_payload(spec: Mapping[str, object]) -> dict[str, object]:
    return {field: spec[field] for field in sorted(IMMUTABLE_FIELDS)}


def specification_hash(spec: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(specification_payload(spec))).hexdigest()


def preregister(spec: Mapping[str, object]) -> dict[str, object]:
    validate_experiment(spec)
    if spec["status"] != "draft":
        raise ExperimentError("Only a draft can be preregistered")
    if "unresolved" in json.dumps(specification_payload(spec)).casefold():
        raise ExperimentError("All research-defining decisions must be resolved")
    if spec["minimum_sample_size"]["status"] != "resolved":
        raise ExperimentError("minimum_sample_size must be resolved before preregistration")
    for field in (
        "decision_thresholds", "promotion_criteria", "rejection_criteria",
        "stop_conditions",
    ):
        if spec[field]["status"] != "resolved":
            raise ExperimentError(f"{field} must be resolved before preregistration")
    updated = dict(spec)
    updated["status"] = "preregistered"
    updated["preregistration_hash"] = specification_hash(updated)
    validate_experiment(updated)
    return updated


def transition(spec: Mapping[str, object], new_status: str) -> dict[str, object]:
    validate_experiment(spec)
    current = str(spec["status"])
    if new_status not in TRANSITIONS[current]:
        raise ExperimentError(f"Invalid status transition: {current} -> {new_status}")
    if new_status == "preregistered":
        return preregister(spec)
    updated = dict(spec)
    updated["status"] = new_status
    validate_experiment(updated)
    return updated


def validate_registry_root(root: Path) -> Path:
    raw = Path(root)
    if not raw.is_absolute() or ".." in raw.parts:
        raise ExperimentError("Registry root must be absolute without traversal")
    protected = {"holdout", "sealed", "forward-validation", "validation-extension"}
    if any(part.casefold().replace("_", "-") in protected for part in raw.parts):
        raise ExperimentError("Registry commands cannot access protected outcome paths")
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ExperimentError("Registry root contains a symlink")
    return raw


def _validated_spec_path(path: Path) -> Path:
    raw = Path(path)
    if ".." in raw.parts:
        raise ExperimentError("Experiment specification path contains traversal")
    absolute = raw if raw.is_absolute() else Path.cwd() / raw
    validate_registry_root(absolute.parent)
    return absolute


def load_spec(path: Path) -> dict[str, object]:
    path = _validated_spec_path(path)
    if path.is_symlink():
        raise ExperimentError("Experiment specification cannot be a symlink")
    info = path.stat()
    if info.st_nlink != 1:
        raise ExperimentError("Experiment specification cannot be hard-linked")
    if info.st_size > MAX_SPEC_BYTES:
        raise ExperimentError("Experiment specification exceeds the size limit")
    with path.open(encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict):
        raise ExperimentError("Experiment file must contain an object")
    validate_experiment(spec)
    return spec


def load_registry(root: Path) -> list[dict[str, object]]:
    root = validate_registry_root(root)
    specs = [load_spec(path) for path in sorted(root.glob("*.json"))]
    identifiers = [spec["experiment_id"] for spec in specs]
    if len(set(identifiers)) != len(identifiers):
        raise ExperimentError("Duplicate experiment IDs")
    return specs


def write_spec(path: Path, spec: Mapping[str, object], *, replace: bool = False) -> None:
    validate_experiment(spec)
    path = _validated_spec_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ExperimentError("Experiment specification cannot be a symlink")
    if replace:
        if not path.is_file():
            raise ExperimentError("Existing experiment specification is required")
        current = load_spec(path)
        if current["experiment_id"] != spec["experiment_id"]:
            raise ExperimentError("Experiment identity cannot change")
        if spec["status"] not in TRANSITIONS[str(current["status"])]:
            raise ExperimentError("Replacement bypasses the lifecycle transition table")
        if current["status"] != "draft" and specification_hash(spec) != current["preregistration_hash"]:
            raise ExperimentError("Replacement modifies preregistered research fields")
    payload = canonical_json(dict(spec))
    if len(payload) > MAX_SPEC_BYTES:
        raise ExperimentError("Experiment specification exceeds the size limit")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError as exc:
                raise ExperimentError("Experiment specification already exists") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def draft_template(experiment_id: str, name: str, author: str, code_version: str) -> dict[str, object]:
    unresolved = {
        "status": "unresolved", "rule": "UNRESOLVED",
        "rationale": "Evidence is insufficient before data collection.",
    }
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_id": experiment_id, "human_name": name, "status": "draft",
        "hypothesis": "UNRESOLVED", "rationale": "UNRESOLVED",
        "strategy_baseline": dict(BASELINE_REFERENCE), "code_version": code_version,
        "registration_timestamp": datetime.now(timezone.utc).isoformat(),
        "registration_author": author,
        "permitted_datasets": ["synthetic catalyst fixtures"],
        "prohibited_datasets": ["forward-validation outcomes", "sealed holdout"],
        "feature_definitions": [{
            "name": "UNRESOLVED", "definition": "UNRESOLVED",
            "availability_time": "Must be point-in-time available before the signal timestamp.",
        }],
        "target_population": "UNRESOLVED", "observation_window": "UNRESOLVED",
        "comparison_group": "UNRESOLVED",
        "primary_metric": {"name": "UNRESOLVED", "unit": "UNRESOLVED", "direction": "descriptive"},
        "secondary_metrics": [], "minimum_sample_size": {
            "status": "unresolved", "value": None,
            "rationale": "Evidence is insufficient before data collection.",
        },
        "decision_thresholds": dict(unresolved), "promotion_criteria": dict(unresolved),
        "rejection_criteria": dict(unresolved), "stop_conditions": dict(unresolved),
        "multiple_testing_family": "UNRESOLVED",
        "leakage_risks": ["Forward outcomes must remain sealed."],
        "known_limitations": ["Draft specification is incomplete."],
        "notes": "Operational notes must be appended separately after preregistration.",
        "preregistration_hash": None,
    }


def append_operational_note(
    registry_root: Path, experiment_id: str, recorded_at: str, author: str, note: str,
) -> Path:
    specs = {item["experiment_id"]: item for item in load_registry(registry_root)}
    if experiment_id not in specs:
        raise ExperimentError("Experiment ID does not exist")
    spec = specs[experiment_id]
    if spec["preregistration_hash"] is None:
        raise ExperimentError("Operational notes begin after preregistration")
    _timestamp(recorded_at, "recorded_at")
    _string(author, "author")
    _string(note, "note")
    path = registry_root / f"{experiment_id}.notes.jsonl"
    if path.is_symlink():
        raise ExperimentError("Operational note log cannot be a symlink")
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        previous = spec["preregistration_hash"]
        for line in handle:
            existing = json.loads(line)
            unsigned = {key: value for key, value in existing.items() if key != "note_hash"}
            if existing.get("previous_note_hash") != previous:
                raise ExperimentError("Operational note chain is invalid")
            if existing.get("note_hash") != hashlib.sha256(canonical_json(unsigned)).hexdigest():
                raise ExperimentError("Operational note hash is invalid")
            previous = existing["note_hash"]
        payload = {
            "schema_version": "aml.experiment-note.v001",
            "experiment_id": experiment_id,
            "recorded_at": recorded_at,
            "author": author,
            "note": note,
            "preregistration_hash": spec["preregistration_hash"],
            "previous_note_hash": previous,
        }
        payload["note_hash"] = hashlib.sha256(canonical_json(payload)).hexdigest()
        handle.seek(0, os.SEEK_END)
        handle.write(canonical_json(payload).decode())
        handle.flush()
        os.fsync(handle.fileno())
    return path
