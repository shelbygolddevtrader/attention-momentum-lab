"""Claim-limited exploratory execution over contaminated historical inputs.

This module is deliberately parallel to empirical publication.  It reuses
frozen evaluators and lifecycle simulation, but its artifacts are structurally
incapable of becoming discovery, validation, Olympics, production, or capital
evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from aml.benchmark_candidate_opening_drive_first_pullback_v001 import (
    REFERENCE_STRATEGY_ID,
    evaluate_opening_drive_first_pullback,
    verify_reference_binding,
)
from aml.benchmark_hypothesis_library_v001 import load_library
from aml.discovery_screen_v001 import CalendarSession, simulate_strategy
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_executors_v001 import ExecutorIntegrityError
from aml.winner_archetype_contracts import canonical_hash, canonical_json


SCHEMA = "aml.exploratory-research-mode.v001"
MODE_VERSION = "exploratory-research-mode-v001"
RESULT_SCHEMA = "aml.exploratory-hypothesis-result.v001"
MANIFEST_SCHEMA = "aml.exploratory-research-manifest.v001"
EVIDENCE_CLASS = "exploratory_non_empirical_contaminated"
NY = ZoneInfo("America/New_York")
HASH = re.compile(r"^[0-9a-f]{64}$")
LABELS = (
    "CONTAMINATED DATA",
    "EXPLORATORY ONLY",
    "NOT AUTHORIZED FOR EMPIRICAL CONCLUSIONS",
    "NOT CAPITAL ELIGIBLE",
    "NOT HOLDOUT",
    "NOT PRODUCTION",
    "NOT VALIDATION",
)
CLAIM_CEILING = "engineering_behavior_and_research_prioritization_only"
PROHIBITED_RESULT_KEYS = frozenset(
    {
        "alpha",
        "annualized_return",
        "edge",
        "expectancy",
        "gross_pnl",
        "net_pnl",
        "profit_factor",
        "return",
        "sharpe",
        "sortino",
        "win_rate",
    }
)
SOURCE_PATHS = (
    "scripts/run_exploratory_research_mode_v001.py",
    "src/aml/benchmark_candidate_opening_drive_first_pullback_v001.py",
    "src/aml/discovery_screen_v001.py",
    "src/aml/exploratory_research_mode_v001.py",
    "src/aml/professional_strategy_executor_models_v001.py",
    "src/aml/professional_strategy_executors_v001.py",
    "src/aml/professional_strategy_indicators_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
)
PLAN_FIELDS = {
    "schema_version",
    "mode_version",
    "dataset",
    "hypotheses",
    "labels",
    "policy",
    "plan_identity",
}


class ExploratoryResearchError(ValueError):
    """Exploratory input, boundary, reconciliation, or artifact is invalid."""


@dataclass(frozen=True, slots=True)
class LoadedPartition:
    symbol: str
    session: date
    bars: tuple[MinuteBar, ...]
    processed_sha256: str
    metadata_sha256: str
    warning_codes: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 5_000_000:
        raise ExploratoryResearchError(f"JSON input is missing, unsafe, or oversized:{path.name}")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ExploratoryResearchError(f"duplicate JSON key:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ExploratoryResearchError(f"non-finite JSON value:{token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExploratoryResearchError(f"malformed JSON input:{path.name}") from exc
    if not isinstance(value, dict):
        raise ExploratoryResearchError(f"JSON input must be an object:{path.name}")
    return value


def plan_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(PLAN_FIELDS - {"plan_identity"})}
    return canonical_hash({"domain": SCHEMA, "plan": projection})


def validate_plan(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != PLAN_FIELDS:
        raise ExploratoryResearchError("exploratory plan schema is invalid")
    if value["schema_version"] != SCHEMA or value["mode_version"] != MODE_VERSION:
        raise ExploratoryResearchError("exploratory plan version changed")
    if value["labels"] != list(LABELS):
        raise ExploratoryResearchError("mandatory exploratory labels changed")
    dataset = value["dataset"]
    required_dataset = {
        "dataset_fingerprint",
        "dataset_vintage",
        "manifest_relative_path",
        "manifest_sha256",
        "selection",
    }
    if not isinstance(dataset, Mapping) or set(dataset) != required_dataset:
        raise ExploratoryResearchError("exploratory dataset schema is invalid")
    for field in ("dataset_fingerprint", "manifest_sha256"):
        if not isinstance(dataset[field], str) or not HASH.fullmatch(dataset[field]):
            raise ExploratoryResearchError(f"dataset identity is malformed:{field}")
    path = Path(str(dataset["manifest_relative_path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ExploratoryResearchError("dataset manifest path is unsafe")
    selection = dataset["selection"]
    if not isinstance(selection, Mapping) or set(selection) != {
        "sessions",
        "symbols",
        "selection_rule",
    }:
        raise ExploratoryResearchError("dataset selection schema is invalid")
    sessions = selection["sessions"]
    symbols = selection["symbols"]
    if (
        not isinstance(sessions, list)
        or sessions != sorted(set(sessions))
        or not sessions
        or any(date.fromisoformat(item) > date(2024, 12, 31) for item in sessions)
    ):
        raise ExploratoryResearchError("sessions must be unique discovery-period dates")
    if (
        not isinstance(symbols, list)
        or symbols != sorted(set(symbols))
        or not symbols
        or any(not isinstance(item, str) or not item for item in symbols)
    ):
        raise ExploratoryResearchError("symbols must be unique and sorted")
    hypotheses = value["hypotheses"]
    if not isinstance(hypotheses, list) or len(hypotheses) < 2:
        raise ExploratoryResearchError("exploratory mode requires multiple hypotheses")
    ids = [item.get("library_entry_id") for item in hypotheses if isinstance(item, Mapping)]
    if ids != sorted(set(ids)) or len(ids) != len(hypotheses):
        raise ExploratoryResearchError("hypothesis entries must be unique and sorted")
    required_hypothesis = {
        "evaluator_binding",
        "framework_hypothesis_identity",
        "library_entry_id",
        "registration_identity",
        "required_input_fields",
    }
    for item in hypotheses:
        if not isinstance(item, Mapping) or set(item) != required_hypothesis:
            raise ExploratoryResearchError("hypothesis binding schema is invalid")
        for field in ("framework_hypothesis_identity", "registration_identity"):
            if not isinstance(item[field], str) or not HASH.fullmatch(item[field]):
                raise ExploratoryResearchError(f"hypothesis identity is malformed:{field}")
        fields = item["required_input_fields"]
        if not isinstance(fields, list) or fields != sorted(set(fields)) or not fields:
            raise ExploratoryResearchError("required input fields must be unique and sorted")
    if value["policy"] != {
        "accepted_research_publication_permitted": False,
        "capital_eligible": False,
        "claim_ceiling": CLAIM_CEILING,
        "contaminated_data_required": True,
        "empirical_conclusion_permitted": False,
        "holdout_access_permitted": False,
        "optimization_permitted": False,
        "parallel_artifact_namespace": "exploratory_research/v001",
        "profitability_metrics_published": False,
        "validation_access_permitted": False,
        "write_once": True,
    }:
        raise ExploratoryResearchError("exploratory claim policy changed")
    if value["plan_identity"] != plan_identity(value):
        raise ExploratoryResearchError("exploratory plan identity is stale or tampered")
    return dict(value)


def load_plan(path: Path) -> dict[str, object]:
    value = _strict_json(path)
    validate_plan(value)
    if path.read_bytes() != canonical_json(value):
        raise ExploratoryResearchError("exploratory plan is not canonical JSON")
    return value


def finalize_plan(value: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(canonical_json(value))
    result["plan_identity"] = plan_identity(result)
    validate_plan(result)
    return result


def _validate_library(plan: Mapping[str, object], library_path: Path) -> None:
    library = load_library(library_path)
    entries = {item["library_entry_id"]: item for item in library["hypotheses"]}
    for binding in plan["hypotheses"]:
        entry = entries.get(binding["library_entry_id"])
        if entry is None or any(
            entry[field] != binding[field]
            for field in ("framework_hypothesis_identity", "registration_identity")
        ):
            raise ExploratoryResearchError(
                f"hypothesis library binding changed:{binding['library_entry_id']}"
            )


def _source_hashes(repository_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        path = repository_root / relative
        if not path.is_file() or path.is_symlink():
            raise ExploratoryResearchError(f"exploratory source is invalid:{relative}")
        result[relative] = _sha256(path)
    return dict(sorted(result.items()))


def _verify_manifest(
    repository_root: Path, plan: Mapping[str, object]
) -> dict[str, object]:
    dataset = plan["dataset"]
    path = repository_root / str(dataset["manifest_relative_path"])
    if _sha256(path) != dataset["manifest_sha256"]:
        raise ExploratoryResearchError("source dataset manifest hash changed")
    manifest = _strict_json(path)
    if (
        manifest.get("dataset_fingerprint_sha256") != dataset["dataset_fingerprint"]
        or manifest.get("dataset_vintage") != dataset["dataset_vintage"]
    ):
        raise ExploratoryResearchError("source dataset identity changed")
    coverage = manifest.get("coverage", {})
    selected = plan["dataset"]["selection"]
    if not set(selected["symbols"]).issubset(set(coverage.get("symbols", []))):
        raise ExploratoryResearchError("selected symbol is outside source manifest")
    if any(
        not coverage.get("start_date") <= item <= coverage.get("end_date")
        for item in selected["sessions"]
    ):
        raise ExploratoryResearchError("selected session is outside source manifest")
    return manifest


def _partition(
    dataset_root: Path,
    *,
    symbol: str,
    session: str,
    dataset_fingerprint: str,
) -> LoadedPartition:
    base = dataset_root / "sip" / symbol / session
    csv_path = base / "processed" / "regular_1min.csv"
    metadata_path = base / "metadata" / "regular_acquisition.json"
    if not csv_path.is_file() or not metadata_path.is_file():
        raise ExploratoryResearchError(f"partition missing:{symbol}:{session}")
    metadata = _strict_json(metadata_path)
    if (
        metadata.get("symbol") != symbol
        or metadata.get("trading_date") != session
        or metadata.get("segment") != "regular"
        or metadata.get("requested_feed") != "sip"
        or metadata.get("status") != "success"
    ):
        raise ExploratoryResearchError(f"partition metadata mismatch:{symbol}:{session}")
    processed_hash = _sha256(csv_path)
    if metadata.get("processed_sha256") != processed_hash:
        raise ExploratoryResearchError(f"partition hash mismatch:{symbol}:{session}")
    frame = pd.read_csv(csv_path)
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ExploratoryResearchError(f"partition columns incomplete:{symbol}:{session}")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(NY)
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ExploratoryResearchError(f"partition timestamp integrity:{symbol}:{session}")
    numeric = frame[["open", "high", "low", "close", "volume"]].astype(float)
    if not all(math.isfinite(value) for value in numeric.to_numpy().ravel()):
        raise ExploratoryResearchError(f"partition non-finite value:{symbol}:{session}")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise ExploratoryResearchError(f"partition nonpositive price:{symbol}:{session}")
    if (numeric["volume"] < 0).any():
        raise ExploratoryResearchError(f"partition negative volume:{symbol}:{session}")
    if frame["symbol"].astype(str).ne(symbol).any():
        raise ExploratoryResearchError(f"partition symbol mismatch:{symbol}:{session}")
    expected = pd.date_range(
        f"{session} 09:30", f"{session} 15:59", freq="min", tz=NY
    )
    if not pd.DatetimeIndex(timestamps).equals(expected):
        raise ExploratoryResearchError(f"partition regular minute gap:{symbol}:{session}")
    warnings = [
        "CONTAMINATED_PARENT_DATASET",
        "POINT_IN_TIME_CORPORATE_ACTION_LINEAGE_UNPROVEN",
        "WRITTEN_LICENSE_RETENTION_EVIDENCE_MISSING",
    ]
    if metadata.get("actual_feed") != "sip":
        warnings.append("PROVIDER_FEED_IDENTITY_NOT_ECHOED")
    bars = tuple(
        MinuteBar(
            security_id=symbol,
            symbol=symbol,
            session=date.fromisoformat(session),
            timestamp=timestamp.to_pydatetime(),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
            feed="sip",
            adjustment_identity=dataset_fingerprint,
            source_manifest_identity=processed_hash,
        )
        for timestamp, row in zip(timestamps, frame.itertuples(index=False), strict=True)
    )
    return LoadedPartition(
        symbol,
        date.fromisoformat(session),
        bars,
        processed_hash,
        _sha256(metadata_path),
        tuple(sorted(warnings)),
    )


def _next_open(bars: tuple[MinuteBar, ...], index: int) -> NextBarOpen | None:
    if index + 1 >= len(bars):
        return None
    current = bars[index]
    following = bars[index + 1]
    if following.timestamp != current.timestamp + timedelta(minutes=1):
        return None
    return NextBarOpen(
        security_id=following.security_id,
        symbol=following.symbol,
        session=following.session,
        timestamp=following.timestamp,
        open=following.open,
        feed=following.feed,
        adjustment_identity=following.adjustment_identity,
        source_manifest_identity=following.source_manifest_identity,
    )


def _opening_drive_result(
    partitions: Sequence[LoadedPartition],
) -> tuple[
    dict[str, int],
    Counter[str],
    Counter[str],
    list[object],
    list[dict[str, object]],
]:
    verify_reference_binding()
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposals: list[object] = []
    integrity: list[dict[str, object]] = []
    for partition in partitions:
        opened = datetime.combine(partition.session, time(9, 30), NY)
        closed = datetime.combine(partition.session, time(16, 0), NY)
        for index, bar in enumerate(partition.bars):
            clock = bar.timestamp.strftime("%H:%M")
            if not "09:35" <= clock <= "11:30":
                continue
            try:
                result = evaluate_opening_drive_first_pullback(
                    EvaluationInput(
                        symbol_bars=partition.bars[: index + 1],
                        next_bar=_next_open(partition.bars, index),
                        scheduled_open=opened,
                        scheduled_close=closed,
                        decision_cutoff=bar.timestamp + timedelta(minutes=1),
                        halt_coverage_complete=True,
                        corporate_action_coverage_complete=True,
                        corporate_action_lineage_valid=True,
                        halt_manifest_identity="exploratory-no-halt-intervals-observed",
                        corporate_action_manifest_identity=(
                            "exploratory-retrospective-coverage-contaminated"
                        ),
                        calendar_identity="exploratory-fixed-normal-xnys-session",
                    )
                )
            except ExecutorIntegrityError as exc:
                statuses["integrity_failure"] += 1
                reasons[f"integrity_failure:{exc}"] += 1
                integrity.append(
                    {
                        "session": partition.session.isoformat(),
                        "symbol": partition.symbol,
                        "timestamp": bar.timestamp.isoformat(),
                        "reason": str(exc),
                    }
                )
                continue
            statuses[result.status] += 1
            for reason in result.reason_codes or ("none",):
                reasons[f"{result.status}:{reason}"] += 1
            if result.proposal is not None:
                proposals.append(result.proposal)
    bars_by_key = {
        (item.symbol, item.session): item.bars for item in partitions
    }
    calendar_by_date = {
        item.session: CalendarSession(
            item.session,
            datetime.combine(item.session, time(9, 30), NY),
            datetime.combine(item.session, time(16, 0), NY),
            False,
        )
        for item in partitions
    }
    trades, rejections = simulate_strategy(
        REFERENCE_STRATEGY_ID, proposals, bars_by_key, calendar_by_date
    )
    if len(proposals) != len(trades) + len(rejections):
        raise ExploratoryResearchError("proposal lifecycle reconciliation failed")
    counts = {
        "executed_trade_count": len(trades),
        "integrity_failure_count": statuses["integrity_failure"],
        "proposal_count": len(proposals),
        "rejected_proposal_count": len(rejections),
        "trigger_count": len(proposals) + statuses["no_trade"],
        "unavailable_event_count": statuses["unavailable"],
    }
    return counts, statuses, reasons, proposals, integrity


def _result_payload(
    *,
    binding: Mapping[str, object],
    counts: Mapping[str, int],
    decision_counts: Mapping[str, int],
    decision_reason_counts: Mapping[str, int],
    partition_count: int,
    warning_codes: Sequence[str],
    missing_fields: Sequence[str],
    status: str,
) -> dict[str, object]:
    proposal_count = counts["proposal_count"]
    integrity_count = counts["integrity_failure_count"]
    observations = []
    if missing_fields:
        observations.append(
            "Evaluation was unavailable because a required source field was absent."
        )
    elif proposal_count:
        observations.append(
            "The frozen evaluator emitted at least one proposal in the bounded exercise."
        )
    else:
        observations.append(
            "The frozen evaluator emitted no proposal in the bounded exercise."
        )
    if integrity_count:
        observations.append("Integrity failures require engineering investigation.")
    anomalies = []
    if integrity_count:
        anomalies.append("NONZERO_EXECUTOR_INTEGRITY_FAILURES")
    if counts["trigger_count"] == 0 and not missing_fields:
        anomalies.append("NO_TRIGGER_OBSERVED_IN_BOUNDED_EXERCISE")
    payload = {
        "schema_version": RESULT_SCHEMA,
        "labels": list(LABELS),
        "evidence_class": EVIDENCE_CLASS,
        "claim_ceiling": CLAIM_CEILING,
        "hypothesis": {
            "evaluator_binding": binding["evaluator_binding"],
            "framework_hypothesis_identity": binding["framework_hypothesis_identity"],
            "library_entry_id": binding["library_entry_id"],
            "registration_identity": binding["registration_identity"],
        },
        "status": status,
        "counts": dict(sorted(counts.items())),
        "decision_status_counts": dict(sorted(decision_counts.items())),
        "decision_reason_counts": dict(sorted(decision_reason_counts.items())),
        "partition_count": partition_count,
        "qualitative_observations": sorted(observations),
        "implementation_notes": sorted(
            [
                f"Evaluator binding: {binding['evaluator_binding']}",
                (
                    "Evaluator invocation was refused; no missing input was substituted."
                    if missing_fields
                    else "Frozen downstream evaluator and lifecycle code were reused unchanged."
                ),
            ]
        ),
        "obvious_anomalies": sorted(anomalies),
        "missing_data_summary": {
            "missing_required_fields": sorted(missing_fields),
            "unavailable_event_count": counts["unavailable_event_count"],
            "unavailable_reason_counts": {
                key: value
                for key, value in sorted(decision_reason_counts.items())
                if key.startswith("unavailable:")
            },
        },
        "confidence_warnings": sorted(set(warning_codes) | set(LABELS)),
        "claim_flags": {
            "accepted_research_publication": False,
            "capital_eligible": False,
            "empirical_evidence": False,
            "holdout": False,
            "production": False,
            "validation": False,
        },
    }
    return {**payload, "identity": canonical_hash(payload)}


def _reject_prohibited_keys(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in PROHIBITED_RESULT_KEYS:
                raise ExploratoryResearchError(
                    f"economic result key prohibited in exploratory artifact:{path}.{key}"
                )
            _reject_prohibited_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_prohibited_keys(item, f"{path}[{index}]")


def validate_result(value: Mapping[str, object]) -> dict[str, object]:
    _reject_prohibited_keys(value)
    if value.get("schema_version") != RESULT_SCHEMA or value.get("labels") != list(LABELS):
        raise ExploratoryResearchError("exploratory result labels or schema changed")
    if (
        value.get("evidence_class") != EVIDENCE_CLASS
        or value.get("claim_ceiling") != CLAIM_CEILING
    ):
        raise ExploratoryResearchError("exploratory result claim boundary changed")
    flags = value.get("claim_flags")
    required_flags = {
        "accepted_research_publication",
        "capital_eligible",
        "empirical_evidence",
        "holdout",
        "production",
        "validation",
    }
    if (
        not isinstance(flags, Mapping)
        or set(flags) != required_flags
        or any(item is not False for item in flags.values())
    ):
        raise ExploratoryResearchError("exploratory result contains an affirmative claim")
    identity = value.get("identity")
    base = {key: item for key, item in value.items() if key != "identity"}
    if identity != canonical_hash(base):
        raise ExploratoryResearchError("exploratory result identity mismatch")
    counts = value.get("counts", {})
    if not isinstance(counts, Mapping) or any(
        not isinstance(item, int) or item < 0 for item in counts.values()
    ):
        raise ExploratoryResearchError("exploratory result counts are invalid")
    if counts.get("proposal_count") != (
        counts.get("executed_trade_count", 0) + counts.get("rejected_proposal_count", 0)
    ):
        raise ExploratoryResearchError("exploratory proposal counts do not reconcile")
    return dict(value)


def _output_path(path: Path) -> Path:
    resolved = path.resolve()
    parts = resolved.parts
    try:
        marker = parts.index("exploratory_research")
    except ValueError as exc:
        raise ExploratoryResearchError("output is outside exploratory namespace") from exc
    if parts[marker + 1 : marker + 2] != ("v001",):
        raise ExploratoryResearchError("output is outside exploratory V001 namespace")
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / ".git").exists():
            raise ExploratoryResearchError("exploratory output cannot be inside Git")
    if resolved.exists():
        raise ExploratoryResearchError("exploratory output already exists")
    return resolved


def run_exploratory(
    *,
    repository_root: Path,
    plan_path: Path,
    library_path: Path,
    dataset_root: Path,
    output_root: Path,
) -> dict[str, object]:
    """Execute a write-once, non-economic, contaminated engineering exercise."""

    root = Path(repository_root).resolve()
    plan = load_plan(plan_path)
    _validate_library(plan, library_path)
    _verify_manifest(root, plan)
    if Path(dataset_root).resolve().name != plan["dataset"]["dataset_vintage"]:
        raise ExploratoryResearchError("dataset root vintage changed")
    selected = plan["dataset"]["selection"]
    partitions = tuple(
        _partition(
            Path(dataset_root).resolve(),
            symbol=symbol,
            session=session,
            dataset_fingerprint=plan["dataset"]["dataset_fingerprint"],
        )
        for session in selected["sessions"]
        for symbol in selected["symbols"]
    )
    partition_records = [
        {
            "metadata_sha256": item.metadata_sha256,
            "processed_sha256": item.processed_sha256,
            "session": item.session.isoformat(),
            "symbol": item.symbol,
            "warning_codes": list(item.warning_codes),
        }
        for item in partitions
    ]
    source_sha256 = _source_hashes(root)
    run_identity = canonical_hash(
        {
            "domain": "aml.exploratory-research-run.v001",
            "plan_identity": plan["plan_identity"],
            "partitions": partition_records,
            "source_sha256": source_sha256,
        }
    )
    common_warnings = sorted(
        {warning for item in partitions for warning in item.warning_codes}
    )
    results: list[dict[str, object]] = []
    for binding in plan["hypotheses"]:
        hypothesis_id = binding["library_entry_id"]
        if hypothesis_id == "opening-drive-first-pullback-v001":
            counts, statuses, reasons, _, _ = _opening_drive_result(partitions)
            result = _result_payload(
                binding=binding,
                counts=counts,
                decision_counts=statuses,
                decision_reason_counts=reasons,
                partition_count=len(partitions),
                warning_codes=common_warnings,
                missing_fields=(),
                status=(
                    "EXPLORATORY_DIAGNOSTIC_ONLY"
                    if counts["integrity_failure_count"]
                    else "EXPLORATORY_EXERCISED"
                ),
            )
        elif hypothesis_id == "high-of-day-breakout-continuation-v001":
            unavailable = len(partitions)
            result = _result_payload(
                binding=binding,
                counts={
                    "executed_trade_count": 0,
                    "integrity_failure_count": 0,
                    "proposal_count": 0,
                    "rejected_proposal_count": 0,
                    "trigger_count": 0,
                    "unavailable_event_count": unavailable,
                },
                decision_counts={"unavailable": unavailable},
                decision_reason_counts={
                    "unavailable:required_input_missing:spread_bps": unavailable
                },
                partition_count=len(partitions),
                warning_codes=common_warnings + ["REQUIRED_SPREAD_INPUT_UNAVAILABLE"],
                missing_fields=("spread_bps",),
                status="EXPLORATORY_BLOCKED_MISSING_INPUT",
            )
        else:
            raise ExploratoryResearchError(
                f"unregistered exploratory evaluator:{hypothesis_id}"
            )
        validate_result(result)
        results.append(result)
    target = _output_path(output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".exploratory-v001-", dir=target.parent))
    try:
        files: list[dict[str, object]] = []
        for index, result in enumerate(results, start=1):
            name = f"{index:02d}-{result['hypothesis']['library_entry_id']}.json"
            path = staging / name
            path.write_bytes(canonical_json(result))
            files.append({"path": name, "sha256": _sha256(path)})
        summary_base = {
            "schema_version": "aml.exploratory-research-summary.v001",
            "labels": list(LABELS),
            "evidence_class": EVIDENCE_CLASS,
            "claim_ceiling": CLAIM_CEILING,
            "run_identity": run_identity,
            "plan_identity": plan["plan_identity"],
            "dataset_fingerprint": plan["dataset"]["dataset_fingerprint"],
            "partition_count": len(partitions),
            "hypothesis_count": len(results),
            "hypothesis_status_counts": dict(
                sorted(Counter(item["status"] for item in results).items())
            ),
            "partition_bindings": partition_records,
            "source_sha256": source_sha256,
            "economic_metrics_published": False,
            "empirical_conclusion_authorized": False,
        }
        summary = {**summary_base, "identity": canonical_hash(summary_base)}
        _reject_prohibited_keys(summary)
        summary_path = staging / "summary.json"
        summary_path.write_bytes(canonical_json(summary))
        files.append({"path": "summary.json", "sha256": _sha256(summary_path)})
        manifest_base = {
            "schema_version": MANIFEST_SCHEMA,
            "labels": list(LABELS),
            "run_identity": run_identity,
            "plan_identity": plan["plan_identity"],
            "write_once": True,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        manifest = {**manifest_base, "identity": canonical_hash(manifest_base)}
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verified = verify_bundle(target)
    return {
        "run_identity": run_identity,
        "manifest_identity": verified["manifest_identity"],
        "hypothesis_count": len(results),
        "partition_count": len(partitions),
        "verified": True,
        "output_root": str(target),
    }


def verify_bundle(path: Path) -> dict[str, object]:
    root = Path(path).resolve()
    manifest = _strict_json(root / "manifest.json")
    identity = manifest.pop("identity", None)
    if manifest.get("schema_version") != MANIFEST_SCHEMA or identity != canonical_hash(manifest):
        raise ExploratoryResearchError("exploratory manifest identity mismatch")
    if manifest.get("labels") != list(LABELS) or manifest.get("write_once") is not True:
        raise ExploratoryResearchError("exploratory manifest boundary changed")
    expected_files = {"manifest.json"}
    for item in manifest.get("files", []):
        relative = Path(str(item.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ExploratoryResearchError("unsafe exploratory artifact path")
        artifact = root / relative
        if not artifact.is_file() or artifact.is_symlink() or _sha256(artifact) != item.get("sha256"):
            raise ExploratoryResearchError(f"exploratory artifact hash mismatch:{relative}")
        value = _strict_json(artifact)
        _reject_prohibited_keys(value)
        if value.get("labels") != list(LABELS):
            raise ExploratoryResearchError(f"exploratory artifact labels missing:{relative}")
        if value.get("schema_version") == RESULT_SCHEMA:
            validate_result(value)
        elif value.get("schema_version") == "aml.exploratory-research-summary.v001":
            summary_identity = value.get("identity")
            summary_base = {key: item for key, item in value.items() if key != "identity"}
            if (
                summary_identity != canonical_hash(summary_base)
                or value.get("evidence_class") != EVIDENCE_CLASS
                or value.get("claim_ceiling") != CLAIM_CEILING
                or value.get("economic_metrics_published") is not False
                or value.get("empirical_conclusion_authorized") is not False
            ):
                raise ExploratoryResearchError("exploratory summary boundary changed")
        else:
            raise ExploratoryResearchError(f"unknown exploratory artifact schema:{relative}")
        expected_files.add(relative.as_posix())
    actual_files = {
        item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()
    }
    if actual_files != expected_files:
        raise ExploratoryResearchError("exploratory bundle contains unmanifested files")
    return {"manifest_identity": identity, "verified": True}
