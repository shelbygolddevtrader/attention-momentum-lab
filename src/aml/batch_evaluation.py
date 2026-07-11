"""Deterministic, session-isolated batch evaluation infrastructure."""

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.market_calendar import (
    CalendarIdentity, MarketCalendar, NonTradingSessionError, SessionSchedule,
)
from aml.market_halts import (
    CompletenessMode, HaltSchedule, completeness_metadata, load_verified_halts,
)
from aml.replay import replay_to_frame
from aml.trade_simulator import SimulationConfig, simulate_trades

SESSION_CLASSES = {"attention_event", "ordinary_control"}
QUALITY_BANDS = {"complete_or_minor", "moderate_gaps", "missing_heavy", "unknown"}
MANIFEST_COLUMNS = [
    "symbol", "trading_date", "calendar_id", "session_class", "cohort_id", "selection_rule",
    "data_source", "data_feed", "inclusion_timestamp", "dataset_vintage",
    "matched_group_id",
]


@dataclass(frozen=True)
class QualityPolicy:
    configuration_version: str
    complete_session_maximum_missing_percentage: float
    usable_session_maximum_missing_percentage: float
    excluded_quality_bands: tuple[str, ...]
    exclude_quality_flagged_sessions: bool
    require_clean_git_worktree: bool

    def __post_init__(self):
        if not isinstance(self.configuration_version, str) or not self.configuration_version.strip():
            raise ValueError("Quality configuration version is required")
        lower = self.complete_session_maximum_missing_percentage
        upper = self.usable_session_maximum_missing_percentage
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (lower, upper)):
            raise ValueError("Quality percentages must be numeric")
        if not 0 <= lower <= 1 or not 0 <= upper <= 1:
            raise ValueError("Quality percentages must be between 0 and 1")
        if lower > upper:
            raise ValueError("Complete-session threshold cannot exceed usable-session threshold")
        if any(not isinstance(value, str) for value in self.excluded_quality_bands):
            raise ValueError("Excluded quality bands must be strings")
        unknown = set(self.excluded_quality_bands).difference(QUALITY_BANDS)
        if unknown:
            raise ValueError(f"Unknown excluded quality bands: {', '.join(sorted(unknown))}")
        if not isinstance(self.exclude_quality_flagged_sessions, bool):
            raise ValueError("exclude_quality_flagged_sessions must be boolean")
        if self.require_clean_git_worktree is not True:
            raise ValueError("Real batch evaluation must require a clean Git worktree")

    def normalized_payload(self):
        payload = asdict(self)
        payload["excluded_quality_bands"] = sorted(self.excluded_quality_bands)
        return payload

    def fingerprint(self):
        encoded = json.dumps(self.normalized_payload(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def load_quality_policy(path: Path) -> QualityPolicy:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed quality configuration: {exc}") from exc
    expected = {
        "configuration_version", "complete_session_maximum_missing_percentage",
        "usable_session_maximum_missing_percentage", "excluded_quality_bands",
        "exclude_quality_flagged_sessions", "require_clean_git_worktree",
    }
    if set(payload) != expected:
        unknown = set(payload).difference(expected)
        missing = expected.difference(payload)
        detail = f"unknown={sorted(unknown)}, missing={sorted(missing)}"
        raise ValueError(f"Unknown or missing quality configuration fields: {detail}")
    if not isinstance(payload["excluded_quality_bands"], list):
        raise ValueError("excluded_quality_bands must be a list")
    for field in ("exclude_quality_flagged_sessions", "require_clean_git_worktree"):
        if not isinstance(payload[field], bool):
            raise ValueError(f"{field} must be boolean")
    payload["excluded_quality_bands"] = tuple(payload["excluded_quality_bands"])
    return QualityPolicy(**payload)


@dataclass
class BatchResult:
    run_id: str
    normalized_manifest: pd.DataFrame
    session_results: pd.DataFrame
    trades: pd.DataFrame
    candidates: pd.DataFrame
    input_hashes: dict[str, str]
    calendar_identity: CalendarIdentity


def normalize_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    missing = set(MANIFEST_COLUMNS).difference(manifest.columns)
    if missing:
        raise ValueError(f"Missing manifest fields: {', '.join(sorted(missing))}")
    frame = manifest[MANIFEST_COLUMNS].copy()
    for column in MANIFEST_COLUMNS:
        frame[column] = frame[column].astype("string").str.strip()
        if frame[column].isna().any() or frame[column].eq("").any():
            raise ValueError(f"Missing required provenance: {column}")
    frame["symbol"] = frame["symbol"].str.upper()
    frame["calendar_id"] = frame["calendar_id"].str.upper()
    parsed_dates = pd.to_datetime(frame["trading_date"], format="%Y-%m-%d", errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("Malformed trading_date")
    frame["trading_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    if not frame["session_class"].isin(SESSION_CLASSES).all():
        raise ValueError("Unsupported session_class")
    inclusion = pd.to_datetime(frame["inclusion_timestamp"], utc=True, errors="coerce")
    if inclusion.isna().any():
        raise ValueError("Malformed inclusion_timestamp")
    frame["inclusion_timestamp"] = inclusion.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    grouped = frame.groupby(["symbol", "trading_date"])["session_class"].nunique()
    if (grouped > 1).any():
        raise ValueError("Conflicting session classifications")
    if frame.duplicated(["symbol", "trading_date"]).any():
        raise ValueError("Duplicate symbol/trading_date session")
    return frame.sort_values(["symbol", "trading_date"], kind="stable").reset_index(drop=True)


def normalized_manifest_bytes(manifest: pd.DataFrame) -> bytes:
    normalized = normalize_manifest(manifest)
    return normalized.to_csv(index=False, lineterminator="\n").encode()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_run_id(
    manifest: pd.DataFrame,
    strategy_fingerprint: str,
    simulator_config: SimulationConfig,
    source_commit: str,
    input_hashes: dict[str, str],
    quality_policy_fingerprint: str,
    calendar_fingerprint: str,
    completeness_mode=CompletenessMode.STRICT,
) -> str:
    payload = {
        "manifest_sha256": hashlib.sha256(normalized_manifest_bytes(manifest)).hexdigest(),
        "strategy_fingerprint": strategy_fingerprint,
        "simulator_config": asdict(simulator_config),
        "source_commit": source_commit,
        "input_hashes": dict(sorted(input_hashes.items())),
        "quality_policy_fingerprint": quality_policy_fingerprint,
        "calendar_fingerprint": calendar_fingerprint,
        "completeness_mode": CompletenessMode(completeness_mode).value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def _quality(observed: pd.DatetimeIndex, expected: pd.DatetimeIndex, policy: QualityPolicy):
    observed_regular = observed.intersection(expected)
    missing = expected.difference(observed_regular)
    missing_pct = len(missing) / len(expected) if len(expected) else None
    largest_gap = 0
    current_gap = 0
    observed_set = set(observed_regular)
    for timestamp in expected:
        if timestamp not in observed_set:
            current_gap += 1
            largest_gap = max(largest_gap, current_gap)
        else:
            current_gap = 0
    if missing_pct is None:
        band = "unknown"
    elif missing_pct <= policy.complete_session_maximum_missing_percentage:
        band = "complete_or_minor"
    elif missing_pct <= policy.usable_session_maximum_missing_percentage:
        band = "moderate_gaps"
    else:
        band = "missing_heavy"
    return len(observed_regular), len(missing), missing_pct, largest_gap, band


def _base_result(row, schedule=None, completeness_mode=CompletenessMode.STRICT, halts=None):
    expected_count = len(schedule.expected_minutes) if schedule is not None else None
    return {
        **row.to_dict(), "status": None, "status_detail": "", "exclusion_reason": "",
        "included_in_aggregate": False, "expected_minute_count": expected_count,
        "observed_minute_count": None, "missing_minute_count": None,
        "missing_percentage": None, "largest_consecutive_gap": None,
        "first_observed_timestamp": None, "last_observed_timestamp": None,
        "candidate_count": None, "trade_count": None, "wins": None, "losses": None,
        "session_pnl": None, "session_return": None, "session_maximum_drawdown": None,
        "exit_reason_counts": None, "data_quality_band": "missing_heavy",
        **completeness_metadata(completeness_mode, halts),
    }


def evaluate_batch(
    manifest: pd.DataFrame,
    loader: Callable[[pd.Series], pd.DataFrame],
    calendar: MarketCalendar,
    strategy_fingerprint: str,
    source_commit: str,
    input_hashes: dict[str, str],
    quality_policy: QualityPolicy,
    simulator_config: SimulationConfig | None = None,
    completeness_mode=CompletenessMode.STRICT,
    halt_loader: Callable[[pd.Series], HaltSchedule] | None = None,
) -> BatchResult:
    normalized = normalize_manifest(manifest)
    config = simulator_config or SimulationConfig()
    completeness_mode = CompletenessMode(completeness_mode)
    policy = quality_policy
    calendar_identity = calendar.identity(set(normalized["calendar_id"]))
    run_id = deterministic_run_id(
        normalized, strategy_fingerprint, config, source_commit, input_hashes,
        policy.fingerprint(),
        calendar_identity.fingerprint(),
        completeness_mode,
    )
    session_rows, all_trades, all_candidates = [], [], []
    for _, row in normalized.iterrows():
        trading_day = date.fromisoformat(row["trading_date"])
        halts = None
        result = _base_result(row, completeness_mode=completeness_mode)
        try:
            schedule = calendar.schedule(trading_day, row["calendar_id"])
            halts = (
                halt_loader(row) if halt_loader is not None
                else load_verified_halts(row["symbol"], row["trading_date"])
            )
            result = _base_result(row, schedule, completeness_mode, halts)
            bars = loader(row).copy()
            if bars.empty:
                raise FileNotFoundError("No bars available")
            bars["timestamp"] = pd.to_datetime(bars["timestamp"])
            symbols = set(bars["symbol"].astype(str).str.upper()) if "symbol" in bars else set()
            if symbols != {row["symbol"]}:
                raise ValueError("Mixed or mismatched symbols in session bars")
            if set(bars["timestamp"].dt.date) != {trading_day}:
                raise ValueError("Cross-date bars in session input")
            observed = pd.DatetimeIndex(bars["timestamp"])
            observed_count, missing_count, missing_pct, largest_gap, band = _quality(
                observed, schedule.expected_minutes, policy
            )
            result.update({
                "observed_minute_count": observed_count,
                "missing_minute_count": missing_count,
                "missing_percentage": missing_pct,
                "largest_consecutive_gap": largest_gap,
                "first_observed_timestamp": observed.min(),
                "last_observed_timestamp": observed.max(),
                "data_quality_band": band,
            })
            replay = replay_to_frame(bars)
            enriched = replay.merge(
                bars[["timestamp", "high", "low"]], on="timestamp", how="left", validate="one_to_one"
            )
            candidates = analyze_candidate_outcomes(
                enriched,
                candidate_score_threshold=config.candidate_score_threshold,
                completeness_mode=completeness_mode,
                halt_schedule=halts,
            )
            trades, summary = simulate_trades(
                replay, bars, config, completeness_mode, halts
            )
            result.update({
                "candidate_count": len(candidates), "trade_count": len(trades),
                "wins": summary["wins"], "losses": summary["losses"],
                "session_pnl": summary["ending_equity"] - config.starting_equity,
                "session_return": summary["total_return"],
                "session_maximum_drawdown": summary["maximum_drawdown"],
                "exit_reason_counts": json.dumps(trades["exit_reason"].value_counts().to_dict(), sort_keys=True),
            })
            quality_flagged = (
                missing_pct is None
                or missing_pct > policy.usable_session_maximum_missing_percentage
                or band in policy.excluded_quality_bands
            )
            excluded_by_policy = band in policy.excluded_quality_bands or (
                quality_flagged and policy.exclude_quality_flagged_sessions
            )
            if quality_flagged:
                result.update(
                    status="quality_flagged",
                    status_detail="Coverage gaps exceed configured usable-session threshold",
                    exclusion_reason="missing_data_quality" if excluded_by_policy else "",
                    included_in_aggregate=not excluded_by_policy,
                )
            elif candidates.empty:
                result.update(status="zero_candidates", status_detail="No score-55+ candidates", included_in_aggregate=True)
            elif trades.empty:
                result.update(status="zero_trades", status_detail="Candidates produced no accepted trades", included_in_aggregate=True)
            else:
                result.update(status="completed", included_in_aggregate=True)
            if not candidates.empty:
                candidates = candidates.assign(trading_date=row["trading_date"], session_class=row["session_class"], cohort_id=row["cohort_id"])
                all_candidates.append(candidates)
            if not trades.empty:
                trades = trades.assign(trading_date=row["trading_date"], session_class=row["session_class"], cohort_id=row["cohort_id"], data_quality_band=band)
                all_trades.append(trades)
        except NonTradingSessionError as exc:
            result.update(
                status="non_trading_session", status_detail=str(exc),
                exclusion_reason="not_scheduled_by_exchange_calendar",
                included_in_aggregate=False,
            )
        except FileNotFoundError as exc:
            result.update(status="no_data", status_detail=str(exc), exclusion_reason="no_data")
        except ValueError as exc:
            result.update(status="invalid_data", status_detail=str(exc), exclusion_reason="invalid_data")
        except Exception as exc:
            result.update(status="processing_error", status_detail=f"{type(exc).__name__}: {exc}", exclusion_reason="processing_error")
        session_rows.append(result)
    return BatchResult(
        run_id, normalized, pd.DataFrame(session_rows),
        pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(),
        pd.concat(all_candidates, ignore_index=True) if all_candidates else pd.DataFrame(),
        dict(sorted(input_hashes.items())),
        calendar_identity,
    )


def batch_artifact_directory(root: Path, run_id: str) -> Path:
    if not run_id or any(character not in "0123456789abcdef" for character in run_id):
        raise ValueError("Invalid deterministic run ID")
    base = (root / "artifacts" / "batch").resolve()
    destination = (base / run_id).resolve()
    if destination.parent != base:
        raise ValueError("Artifact path escapes batch root")
    return destination


def dirty_source_paths(porcelain_output: str):
    relevant_roots = ("src/", "scripts/", "config/", "tests/")
    relevant_files = {"pyproject.toml", "Dockerfile", "Makefile"}
    paths = []
    records = porcelain_output.split("\0") if "\0" in porcelain_output else porcelain_output.splitlines()
    for line in records:
        if not line:
            continue
        path = line[3:].split(" -> ")[-1]
        if path.startswith(relevant_roots) or path in relevant_files:
            paths.append(path)
    return paths


def require_reproducible_source(porcelain_output: str, required: bool):
    dirty = dirty_source_paths(porcelain_output)
    if required and dirty:
        raise RuntimeError(
            "Reproducible batch runs require committed source/config/test files; "
            f"dirty paths: {', '.join(dirty)}"
        )
    return not dirty
