"""Fail-closed Historical PIT Dataset Authorization V001.

This module assesses one already-acquired dataset slice.  It never downloads
data, runs a strategy, or converts a failed assessment into permission.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re

from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json


SCHEMA_VERSION = "aml.historical-pit-dataset-authorization.v001"
ASSESSMENT_ID = "historical-pit-dataset-authorization-v001"
VERIFICATION_SCHEMA = "aml.historical-pit-dataset-authorization-verification.v001"
HASH = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_GATES = (
    "completeness",
    "contamination",
    "deterministic_identity",
    "discovery_period_eligibility",
    "feed_identity",
    "licensing_and_retention",
    "point_in_time_correctness",
    "provenance",
    "reproducibility",
)
PROTECTED_BOUNDARIES = (
    "forward validation",
    "holdout",
    "live trading",
    "olympics execution",
    "paper trading",
    "validation",
)
EXPECTED_GATE_OUTCOMES = {
    "completeness": ("passed", None),
    "contamination": (
        "failed",
        "candidate-descends-from-previously-evaluated-dataset",
    ),
    "deterministic_identity": ("passed", None),
    "discovery_period_eligibility": ("passed", None),
    "feed_identity": ("failed", "provider-feed-identity-not-echoed"),
    "licensing_and_retention": (
        "failed",
        "written-license-retention-evidence-missing",
    ),
    "point_in_time_correctness": (
        "failed",
        "point-in-time-corporate-action-lineage-unproven",
    ),
    "provenance": ("passed", None),
    "reproducibility": ("passed", None),
}


class HistoricalPITAuthorizationError(ValueError):
    """The assessment or its local evidence is malformed or contradictory."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise HistoricalPITAuthorizationError(f"{field} must be lowercase SHA-256")
    return value


def _safe_relative(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise HistoricalPITAuthorizationError(f"{field} must be a relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise HistoricalPITAuthorizationError(f"{field} is unsafe")
    return path


def _regular_local_file(root: Path, relative: Path, field: str) -> Path:
    """Resolve a contained regular file while rejecting every symlink component."""

    resolved_root = Path(root).resolve()
    current = resolved_root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise HistoricalPITAuthorizationError(f"{field} traverses a symlink")
    resolved = current.resolve()
    if not resolved.is_file() or resolved_root not in resolved.parents:
        raise HistoricalPITAuthorizationError(f"{field} is unavailable or unsafe")
    return resolved


def dataset_identity(candidate: Mapping[str, object]) -> str:
    """Content identity of the exact candidate slice and its source lineage."""

    projection = {
        key: candidate[key]
        for key in sorted(set(candidate) - {"dataset_identity"})
    }
    return canonical_hash(
        {"domain": "aml.historical-pit-dataset.v001", "candidate": projection}
    )


def authorization_decision(gates: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return the sole permitted decision implied by exact gate states."""

    observed = [gate.get("gate_id") for gate in gates]
    if observed != list(REQUIRED_GATES):
        raise HistoricalPITAuthorizationError(
            "authorization gates must be complete and deterministically ordered"
        )
    failed: list[str] = []
    for gate in gates:
        if set(gate) != {"evidence", "failure_code", "gate_id", "status"}:
            raise HistoricalPITAuthorizationError("authorization gate schema is invalid")
        status = gate["status"]
        code = gate["failure_code"]
        evidence = gate["evidence"]
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item for item in evidence
        ):
            raise HistoricalPITAuthorizationError("gate evidence must be non-empty text")
        if status == "passed":
            if code is not None:
                raise HistoricalPITAuthorizationError("passed gate cannot have failure code")
        elif status == "failed":
            if not isinstance(code, str) or not code:
                raise HistoricalPITAuthorizationError("failed gate requires failure code")
            failed.append(code)
        else:
            raise HistoricalPITAuthorizationError("gate status must be passed or failed")
    authorized = not failed
    return {
        "authorized": authorized,
        "discovery_execution_permitted": authorized,
        "reason_codes": sorted(failed),
        "scope": "discovery_only" if authorized else "none",
        "status": "AUTHORIZED" if authorized else "BLOCKED_NOT_AUTHORIZED",
    }


def assessment_identity(value: Mapping[str, object]) -> str:
    """Identity of all assessment facts except the self-authenticating field."""

    projection = {
        key: value[key]
        for key in sorted(set(value) - {"assessment_identity"})
    }
    return canonical_hash(
        {"domain": "aml.historical-pit-dataset-authorization.v001", "assessment": projection}
    )


def finalize_assessment(value: Mapping[str, object]) -> dict[str, object]:
    """Canonicalize and calculate candidate, decision, and assessment identities."""

    result = json.loads(canonical_json(value))
    candidate = result["candidate"]
    candidate["dataset_identity"] = dataset_identity(candidate)
    result["authorization"] = authorization_decision(result["gates"])
    result["assessment_identity"] = assessment_identity(result)
    return result


def validate_assessment(
    value: Mapping[str, object], *, repository_root: Path
) -> dict[str, object]:
    """Validate structure, dependency hashes, identities, and fail-closed decision."""

    required = {
        "assessment_id",
        "assessment_identity",
        "authorization",
        "candidate",
        "created_at",
        "dependencies",
        "gates",
        "policy",
        "schema_version",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise HistoricalPITAuthorizationError("assessment schema is invalid")
    if value["schema_version"] != SCHEMA_VERSION or value["assessment_id"] != ASSESSMENT_ID:
        raise HistoricalPITAuthorizationError("assessment version changed")
    if value["created_at"] != "2026-08-04T22:00:00Z":
        raise HistoricalPITAuthorizationError("assessment timestamp changed")

    dependencies = value["dependencies"]
    dependency_fields = {
        "assessment_source_sha256",
        "calendar_identity",
        "corporate_action_manifest_identity",
        "executable_specification_identity",
        "framework_hypothesis_identity",
        "halt_manifest_identity",
        "implementation_identity",
        "registration_identity",
        "source_manifest_path",
        "source_manifest_sha256",
    }
    if not isinstance(dependencies, Mapping) or set(dependencies) != dependency_fields:
        raise HistoricalPITAuthorizationError("dependency schema is invalid")
    for field in dependency_fields - {
        "assessment_source_sha256",
        "source_manifest_path",
    }:
        _require_hash(dependencies[field], field)
    source_hashes = dependencies["assessment_source_sha256"]
    required_source_paths = [
        "scripts/run_historical_pit_dataset_authorization_v001.py",
        "src/aml/historical_pit_dataset_authorization_v001.py",
    ]
    if (
        not isinstance(source_hashes, Mapping)
        or list(source_hashes) != required_source_paths
    ):
        raise HistoricalPITAuthorizationError("assessment source inventory changed")
    for relative, expected_hash in source_hashes.items():
        _require_hash(expected_hash, f"assessment_source_sha256.{relative}")
        source_path = _regular_local_file(
            Path(repository_root),
            _safe_relative(relative, "assessment source path"),
            "assessment source",
        )
        if _sha256(source_path) != expected_hash:
            raise HistoricalPITAuthorizationError("assessment source bytes changed")
    manifest_relative = _safe_relative(
        dependencies["source_manifest_path"], "source_manifest_path"
    )
    manifest_path = _regular_local_file(
        Path(repository_root), manifest_relative, "source manifest"
    )
    if _sha256(manifest_path) != dependencies["source_manifest_sha256"]:
        raise HistoricalPITAuthorizationError("source manifest bytes changed")
    try:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalPITAuthorizationError("source manifest is malformed") from exc
    if not isinstance(source_manifest, Mapping):
        raise HistoricalPITAuthorizationError("source manifest must be an object")

    expected_dependencies = {
        "calendar_identity": "8b9ea9f8edfd4a43b4b3c886496c1d14b1a81285b88cc42aab217a7896a8a4e1",
        "corporate_action_manifest_identity": "d7436e94f6d15749a96ba2d5f474b2220337e67b7a2509cabf17fc609c07424d",
        "executable_specification_identity": "ad9eda50f8542eacf66867b309802021b0d7c81d6cf54404fdf5d10f96d283a0",
        "framework_hypothesis_identity": "f00ebf1e2d873e816998ed02fc0b9eea39b08c9761de0e7d0263efeebb752fec",
        "halt_manifest_identity": "57b84efe0be071bb5be03e7b18d083a9b4972fd4091f2ed93604d218032c781a",
        "implementation_identity": "896148c2197b519b3eb9b11fa9082b3215d7494322829ea9b3a826f7055e7c26",
        "registration_identity": "7b15827b59b021bc7dec7a11122ce8f7f0a5f0e3e5fb98af085b04ddeda3f2cb",
        "source_manifest_path": "manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json",
        "source_manifest_sha256": "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b",
    }
    for field, expected in expected_dependencies.items():
        if dependencies[field] != expected:
            raise HistoricalPITAuthorizationError(f"frozen dependency changed:{field}")

    candidate = value["candidate"]
    candidate_fields = {
        "acquired_at",
        "actual_feed",
        "actual_feed_evidence",
        "adjustment",
        "dataset_identity",
        "dataset_vintage",
        "expected_regular_minute_count",
        "files",
        "provider",
        "regular_end_exclusive",
        "regular_start_inclusive",
        "requested_feed",
        "selection_rule",
        "segment",
        "source_dataset_fingerprint",
        "symbol",
        "timeframe",
        "trading_date",
    }
    if not isinstance(candidate, Mapping) or set(candidate) != candidate_fields:
        raise HistoricalPITAuthorizationError("candidate schema is invalid")
    _require_hash(candidate["dataset_identity"], "dataset_identity")
    _require_hash(candidate["source_dataset_fingerprint"], "source_dataset_fingerprint")
    if candidate["dataset_identity"] != dataset_identity(candidate):
        raise HistoricalPITAuthorizationError("candidate dataset identity changed")
    files = candidate["files"]
    if not isinstance(files, Mapping) or set(files) != {"metadata", "processed", "raw"}:
        raise HistoricalPITAuthorizationError("candidate file inventory is invalid")
    for label, record in files.items():
        if not isinstance(record, Mapping) or set(record) != {"relative_path", "sha256"}:
            raise HistoricalPITAuthorizationError(f"candidate {label} file is invalid")
        _safe_relative(record["relative_path"], f"{label}.relative_path")
        _require_hash(record["sha256"], f"{label}.sha256")
    expected_candidate_values = {
        "acquired_at": "2026-07-25T02:19:28.017353+00:00",
        "actual_feed": None,
        "actual_feed_evidence": "explicit_request_parameter_provider_did_not_echo_feed",
        "adjustment": "all",
        "dataset_vintage": "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001",
        "expected_regular_minute_count": 390,
        "provider": "Alpaca Markets",
        "regular_end_exclusive": "2023-07-24T16:00:00-04:00",
        "regular_start_inclusive": "2023-07-24T09:30:00-04:00",
        "requested_feed": "sip",
        "selection_rule": "earliest frozen discovery date then lexicographically smallest symbol with exactly 390 regular one-minute rows; no outcome field inspected",
        "segment": "regular",
        "source_dataset_fingerprint": "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d",
        "symbol": "AAPL",
        "timeframe": "1Min",
        "trading_date": "2023-07-24",
    }
    if any(candidate[field] != expected for field, expected in expected_candidate_values.items()):
        raise HistoricalPITAuthorizationError("frozen smallest-candidate selection changed")
    if (
        source_manifest.get("dataset_fingerprint_sha256")
        != candidate["source_dataset_fingerprint"]
        or source_manifest.get("dataset_vintage") != candidate["dataset_vintage"]
    ):
        raise HistoricalPITAuthorizationError("source manifest lineage changed")

    if not isinstance(value["gates"], list):
        raise HistoricalPITAuthorizationError("gates must be a list")
    decision = authorization_decision(value["gates"])
    for gate in value["gates"]:
        if (gate["status"], gate["failure_code"]) != EXPECTED_GATE_OUTCOMES[
            gate["gate_id"]
        ]:
            raise HistoricalPITAuthorizationError(
                f"frozen gate outcome changed:{gate['gate_id']}"
            )
    if value["authorization"] != decision:
        raise HistoricalPITAuthorizationError("authorization contradicts gate evidence")
    if value["policy"] != {
        "acquisition_performed": False,
        "discovery_executed": False,
        "empirical_outcome_access_count": 0,
        "immutable_revision_required_for_change": True,
        "protected_boundaries": list(PROTECTED_BOUNDARIES),
        "strategy_or_downstream_change_count": 0,
    }:
        raise HistoricalPITAuthorizationError("authorization policy changed")
    if value["assessment_identity"] != assessment_identity(value):
        raise HistoricalPITAuthorizationError("assessment identity changed")
    return dict(value)


def load_assessment(path: Path, *, repository_root: Path) -> dict[str, object]:
    """Load an exact canonical assessment."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalPITAuthorizationError("assessment is unreadable") from exc
    validate_assessment(value, repository_root=repository_root)
    if path.read_bytes() != canonical_json(value):
        raise HistoricalPITAuthorizationError("assessment JSON is not canonical")
    return value


def verify_local_candidate(
    assessment: Mapping[str, object], *, dataset_root: Path
) -> dict[str, object]:
    """Verify only candidate bytes and bounded regular-session completeness."""

    candidate = assessment["candidate"]
    root = Path(dataset_root).resolve()
    observed_hashes: dict[str, str] = {}
    resolved: dict[str, Path] = {}
    for label, record in candidate["files"].items():
        relative = _safe_relative(record["relative_path"], f"{label}.relative_path")
        path = _regular_local_file(root, relative, f"{label} evidence")
        observed_hashes[label] = _sha256(path)
        if observed_hashes[label] != record["sha256"]:
            raise HistoricalPITAuthorizationError(f"{label} evidence bytes changed")
        resolved[label] = path

    try:
        metadata = json.loads(resolved["metadata"].read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalPITAuthorizationError("candidate metadata is malformed") from exc
    expected_metadata = {
        "provider": "alpaca",
        "symbol": candidate["symbol"],
        "segment": candidate["segment"],
        "timeframe": candidate["timeframe"],
        "requested_feed": candidate["requested_feed"],
        "actual_feed": candidate["actual_feed"],
        "actual_feed_evidence": candidate["actual_feed_evidence"],
        "adjustment": candidate["adjustment"],
        "record_count": candidate["expected_regular_minute_count"],
        "requested_start_timestamp": candidate["regular_start_inclusive"],
        "requested_end_timestamp_exclusive": candidate["regular_end_exclusive"],
        "acquisition_timestamp": candidate["acquired_at"],
        "raw_response_sha256": candidate["files"]["raw"]["sha256"],
        "processed_sha256": candidate["files"]["processed"]["sha256"],
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            raise HistoricalPITAuthorizationError(f"metadata mismatch:{field}")
    normalization = metadata.get("normalization")
    if not isinstance(normalization, Mapping) or any(
        normalization.get(field) != expected
        for field, expected in {
            "cross_date_bar_count": 0,
            "duplicate_timestamp_count": 0,
            "expected_minute_count": 390,
            "missing_timestamp_count": 0,
            "out_of_order": False,
            "output_record_count": 390,
            "requested_feed": "sip",
            "segment": "regular",
        }.items()
    ):
        raise HistoricalPITAuthorizationError("metadata normalization is incomplete")
    pagination = metadata.get("pagination")
    if not isinstance(pagination, Mapping) or (
        pagination.get("page_count") != 1
        or pagination.get("page_record_counts") != [391]
        or pagination.get("page_tokens_followed") != 0
        or pagination.get("pagination_occurred") is not False
    ):
        raise HistoricalPITAuthorizationError("metadata pagination is incomplete")

    try:
        raw_payload = json.loads(resolved["raw"].read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalPITAuthorizationError("raw candidate is malformed") from exc
    raw_bars = raw_payload.get("bars") if isinstance(raw_payload, Mapping) else None
    if (
        not isinstance(raw_bars, list)
        or len(raw_bars) != 391
        or raw_payload.get("symbol") != candidate["symbol"]
        or raw_payload.get("next_page_token") is not None
    ):
        raise HistoricalPITAuthorizationError("raw candidate delivery is incomplete")
    try:
        raw_timestamps = [datetime.fromisoformat(bar["t"]) for bar in raw_bars]
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoricalPITAuthorizationError("raw candidate timestamps are malformed") from exc
    expected_start = datetime.fromisoformat(candidate["regular_start_inclusive"])
    expected_end = datetime.fromisoformat(candidate["regular_end_exclusive"])
    in_window = [
        timestamp
        for timestamp in raw_timestamps
        if expected_start <= timestamp < expected_end
    ]
    if (
        raw_timestamps != sorted(raw_timestamps)
        or len(set(raw_timestamps)) != len(raw_timestamps)
        or len(in_window) != 390
        or in_window[0] != expected_start
        or in_window[-1] + timedelta(minutes=1) != expected_end
    ):
        raise HistoricalPITAuthorizationError("raw candidate interval is incomplete")

    try:
        with resolved["processed"].open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise HistoricalPITAuthorizationError("processed candidate is unreadable") from exc
    expected_columns = [
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trade_count",
        "bar_vwap",
    ]
    if not rows or list(rows[0]) != expected_columns:
        raise HistoricalPITAuthorizationError("processed candidate schema changed")
    if len(rows) != candidate["expected_regular_minute_count"]:
        raise HistoricalPITAuthorizationError("processed candidate is incomplete")
    try:
        timestamps = [datetime.fromisoformat(row["timestamp"]) for row in rows]
        expected_start = datetime.fromisoformat(candidate["regular_start_inclusive"])
        expected_end = datetime.fromisoformat(candidate["regular_end_exclusive"])
    except (TypeError, ValueError) as exc:
        raise HistoricalPITAuthorizationError(
            "processed candidate timestamps are malformed"
        ) from exc
    if (
        timestamps[0] != expected_start
        or timestamps[-1] + timedelta(minutes=1) != expected_end
        or any(
            later - earlier != timedelta(minutes=1)
            for earlier, later in zip(timestamps, timestamps[1:])
        )
        or any(row["symbol"] != candidate["symbol"] for row in rows)
    ):
        raise HistoricalPITAuthorizationError("processed candidate boundary changed")
    return {
        "candidate_bytes_verified": True,
        "observed_file_sha256": dict(sorted(observed_hashes.items())),
        "regular_minute_count": len(rows),
        "timestamp_boundary_verified": True,
    }


def verification_artifact(
    assessment: Mapping[str, object], *, local_verification: Mapping[str, object]
) -> dict[str, object]:
    """Create immutable verification evidence without creating authorization."""

    payload = {
        "assessment_identity": assessment["assessment_identity"],
        "authorization": assessment["authorization"],
        "dataset_identity": assessment["candidate"]["dataset_identity"],
        "gate_results": [
            {
                "failure_code": gate["failure_code"],
                "gate_id": gate["gate_id"],
                "status": gate["status"],
            }
            for gate in assessment["gates"]
        ],
        "local_candidate_verification": dict(local_verification),
        "no_discovery_execution": True,
        "no_protected_boundary_access": True,
        "schema_version": VERIFICATION_SCHEMA,
    }
    payload["verification_identity"] = canonical_hash(
        {"domain": VERIFICATION_SCHEMA, "verification": payload}
    )
    return payload
