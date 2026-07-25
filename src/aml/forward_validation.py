"""Fail-closed operations for the preregistered V0.1.1 validation extension."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Mapping, Sequence

from aml.market_backfill import (
    BackfillTask,
    backfill_job_lock,
    load_universe,
    plan_tasks,
    run_task,
    segment_state,
    trading_dates,
    universe_sha256,
)
from aml.research_acquisition import requests_for_session, research_segment_paths
from aml.validation_extension import (
    EXTENSION_END,
    EXTENSION_START,
    FROZEN_STRATEGY_ID,
    FROZEN_STRATEGY_VERSION,
    FROZEN_UNIVERSE,
    VALIDATION_EXTENSION_VERSION,
    validate_extension_input_path,
)


FORWARD_VALIDATION_SCHEMA = "aml.v011-forward-validation-operations.v001"
BASELINE_TAG = "v0.1.1-research-baseline"
BASELINE_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
DATASET_VINTAGE = "alpaca-sip-v011-forward-validation-2026-07-27_to_2028-07-26-v001"
DEFAULT_UNIVERSE = Path("config/liquid_day_trading_universe_v001.csv")
DEFAULT_CONTROL_ROOT = Path("artifacts/forward_validation/sealed")
REQUIRED_DEPENDENCIES = (
    "requests",
    "dotenv",
    "pandas",
    "numpy",
    "exchange_calendars",
)
_CREDENTIAL_NAMES = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
_PLACEHOLDERS = {"", "replace_with_paper_key", "replace_with_paper_secret"}
_FORBIDDEN_OPERATION_TOKENS = {
    "analysis", "analyze", "holdout", "pnl", "replay", "results", "tournament",
}
_FORBIDDEN_DATASET_FILE_TOKENS = {
    "analysis", "final", "manifest", "report", "results", "signals", "summary",
    "tournament", "trades",
}


class ForwardValidationError(RuntimeError):
    """Raised before an unsafe or non-preregistered operation can begin."""


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def validate_date_range(start: date, end: date) -> None:
    """Allow only chronological subranges inside the frozen extension window."""
    if end < start:
        raise ForwardValidationError("End date must be on or after start date")
    if start < EXTENSION_START or end > EXTENSION_END:
        raise ForwardValidationError(
            f"Dates must remain within {EXTENSION_START} through {EXTENSION_END}"
        )


def validate_acquisition_only_tokens(tokens: Sequence[str]) -> None:
    """Reject attempts to smuggle replay, analysis, or result work into acquisition."""
    for token in tokens:
        normalized = token.casefold().replace("_", "-").replace(".", "-")
        words = set(normalized.replace("=", "-").split("-"))
        if words.intersection(_FORBIDDEN_OPERATION_TOKENS):
            raise ForwardValidationError(
                "Acquisition cannot invoke replay, analysis, holdout, or result operations"
            )


def credential_presence(environment: Mapping[str, str]) -> dict[str, bool]:
    """Return presence flags only; credential values never leave the environment."""
    return {
        name: environment.get(name, "").strip() not in _PLACEHOLDERS
        for name in _CREDENTIAL_NAMES
    }


def verify_credentials(environment: Mapping[str, str]) -> dict[str, bool]:
    status = credential_presence(environment)
    if missing := [name for name, present in status.items() if not present]:
        raise ForwardValidationError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )
    feed = environment.get("ALPACA_HISTORICAL_DATA_FEED", "sip").strip().lower()
    if feed != "sip":
        raise ForwardValidationError("The frozen validation extension requires the SIP feed")
    return status


def verify_dependencies(names: Sequence[str] = REQUIRED_DEPENDENCIES) -> tuple[str, ...]:
    missing = tuple(name for name in names if importlib.util.find_spec(name) is None)
    if missing:
        raise ForwardValidationError("Missing Python dependencies: " + ", ".join(missing))
    return tuple(names)


def verify_repository(root: Path, *, baseline_commit: str = BASELINE_COMMIT) -> str:
    """Require a clean descendant of the immutable, correctly resolved baseline tag."""
    root = Path(root).resolve()
    if _git(root, "rev-parse", "--show-toplevel") != str(root):
        raise ForwardValidationError("Command must run from the repository root")
    if _git(root, "status", "--porcelain"):
        raise ForwardValidationError("Repository working tree must be clean")
    if _git(root, "rev-parse", f"{BASELINE_TAG}^{{}}") != baseline_commit:
        raise ForwardValidationError("Immutable baseline tag does not resolve as expected")
    try:
        _git(root, "merge-base", "--is-ancestor", baseline_commit, "HEAD")
    except subprocess.CalledProcessError as exc:
        raise ForwardValidationError("HEAD is not descended from the research baseline") from exc
    return _git(root, "rev-parse", "HEAD")


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _reject_finalized_collision(path: Path) -> None:
    absolute = validate_extension_input_path(path)
    normalized = tuple(part.casefold().replace("_", "-") for part in absolute.parts)
    if "final" in normalized or "finalized" in normalized:
        raise ForwardValidationError("Output cannot collide with a finalized artifact directory")
    for index, part in enumerate(normalized[:-1]):
        if part == "tournaments" and normalized[index + 1] != "":
            raise ForwardValidationError("Forward-validation output cannot enter tournament artifacts")


def verify_writable_destination(path: Path) -> None:
    _reject_finalized_collision(path)
    parent = _nearest_existing_parent(path)
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        raise ForwardValidationError(f"Output parent is not writable: {parent}")


@dataclass(frozen=True)
class ForwardValidationPlan:
    root: Path
    start: date
    end: date
    source_commit: str
    universe_path: Path
    control_root: Path
    sessions: tuple[date, ...]
    tasks: tuple[BackfillTask, ...]

    @property
    def identity(self) -> dict[str, object]:
        return {
            "schema_version": FORWARD_VALIDATION_SCHEMA,
            "preregistration_version": VALIDATION_EXTENSION_VERSION,
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_COMMIT,
            "source_commit": self.source_commit,
            "strategy_id": FROZEN_STRATEGY_ID,
            "strategy_version": FROZEN_STRATEGY_VERSION,
            "start_date": self.start.isoformat(),
            "end_date": self.end.isoformat(),
            "feed": "sip",
            "timeframe": "1Min",
            "calendar": "XNYS",
            "dataset_vintage": DATASET_VINTAGE,
            "universe_file": self.universe_path.relative_to(self.root).as_posix(),
            "universe_sha256": universe_sha256(self.universe_path),
            "symbols": list(FROZEN_UNIVERSE),
            "operation": "acquisition_only",
            "replay_authorized": False,
            "analysis_authorized": False,
            "holdout_access_authorized": False,
        }

    @property
    def request_id(self) -> str:
        return hashlib.sha256(_canonical_json(self.identity)).hexdigest()[:24]

    @property
    def sealed_directory(self) -> Path:
        return self.control_root / self.request_id

    @property
    def manifest_path(self) -> Path:
        return self.sealed_directory / "acquisition_request.json"

    @property
    def audit_path(self) -> Path:
        return self.sealed_directory / "acquisition_audit.jsonl"


def _verify_existing_control_files(plan: ForwardValidationPlan) -> None:
    directory = plan.sealed_directory
    if not directory.exists():
        return
    if directory.is_symlink() or not directory.is_dir():
        raise ForwardValidationError("Sealed control destination is unsafe")
    allowed = {plan.manifest_path.name, plan.audit_path.name}
    unexpected = sorted(path.name for path in directory.iterdir() if path.name not in allowed)
    if unexpected:
        raise ForwardValidationError(
            "Sealed destination contains unexpected or result-like artifacts: "
            + ", ".join(unexpected)
        )
    if plan.manifest_path.exists() and plan.manifest_path.read_bytes() != _canonical_json(plan.identity):
        raise ForwardValidationError("Existing acquisition manifest has a different identity")


def _verify_partition_states(plan: ForwardValidationPlan, calendar: object) -> None:
    dataset_root = plan.root / "data" / "research" / DATASET_VINTAGE
    if dataset_root.exists():
        for path in dataset_root.rglob("*"):
            if path.is_symlink():
                raise ForwardValidationError("Symlinked acquisition output is prohibited")
            words = set(
                path.name.casefold().replace("_", "-").replace(".", "-").split("-")
            )
            if path.is_file() and words.intersection(_FORBIDDEN_DATASET_FILE_TOKENS):
                raise ForwardValidationError(
                    f"Dataset destination contains a report, manifest, or result file: {path.name}"
                )
    for task in plan.tasks:
        schedule = calendar.schedule(task.trading_date, "XNYS")
        for request in requests_for_session(
            task.instrument.symbol, task.trading_date, schedule, DATASET_VINTAGE, "sip"
        ):
            paths = research_segment_paths(plan.root, request)
            try:
                segment_state(paths)
            except RuntimeError as exc:
                raise ForwardValidationError(str(exc)) from exc


def build_preflight_plan(
    root: Path,
    *,
    start: date,
    end: date,
    environment: Mapping[str, str],
    calendar: object,
    universe: Path = DEFAULT_UNIVERSE,
    control_root: Path = DEFAULT_CONTROL_ROOT,
    require_clean_repository: bool = True,
    source_commit: str | None = None,
) -> ForwardValidationPlan:
    """Perform a network-free preflight and return a deterministic acquisition plan."""
    validate_date_range(start, end)
    verify_credentials(environment)
    verify_dependencies()
    root = Path(root).resolve()
    source_commit = verify_repository(root) if require_clean_repository else source_commit
    if (
        not source_commit
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ForwardValidationError("A full lowercase hexadecimal source commit is required")
    universe_path = universe if universe.is_absolute() else root / universe
    control_path = control_root if control_root.is_absolute() else root / control_root
    validate_extension_input_path(universe_path)
    verify_writable_destination(control_path)
    dataset_root = root / "data" / "research" / DATASET_VINTAGE
    verify_writable_destination(dataset_root)
    instruments = load_universe(universe_path)
    if tuple(item.symbol for item in instruments) != FROZEN_UNIVERSE:
        raise ForwardValidationError("Configured universe differs from the frozen extension universe")
    sessions = trading_dates(calendar, start, end)
    plan = ForwardValidationPlan(
        root, start, end, source_commit, universe_path, control_path,
        sessions, plan_tasks(instruments, sessions),
    )
    _verify_existing_control_files(plan)
    _verify_partition_states(plan, calendar)
    return plan


def preflight_report(plan: ForwardValidationPlan) -> dict[str, object]:
    """Return structural plan facts only—never credentials or strategy outcomes."""
    return {
        "status": "preflight_passed",
        "request_id": plan.request_id,
        "identity_sha256": hashlib.sha256(_canonical_json(plan.identity)).hexdigest(),
        "source_commit": plan.source_commit,
        "start_date": plan.start.isoformat(),
        "end_date": plan.end.isoformat(),
        "dataset_vintage": DATASET_VINTAGE,
        "session_count": len(plan.sessions),
        "symbol_count": len(FROZEN_UNIVERSE),
        "task_count": len(plan.tasks),
        "network_requests_performed": 0,
        "market_data_fetched": False,
        "strategy_replay_performed": False,
        "strategy_results_generated": False,
    }


def _publish_manifest_once(plan: ForwardValidationPlan) -> None:
    plan.sealed_directory.mkdir(parents=True, exist_ok=True)
    content = _canonical_json(plan.identity)
    if plan.manifest_path.exists():
        if plan.manifest_path.read_bytes() != content:
            raise ForwardValidationError("Existing acquisition manifest has a different identity")
        return
    descriptor = os.open(plan.manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _audit(
    plan: ForwardValidationPlan,
    event: str,
    *,
    recorded_at: datetime,
    **fields: object,
) -> None:
    record = {
        "schema_version": FORWARD_VALIDATION_SCHEMA,
        "request_id": plan.request_id,
        "recorded_at": recorded_at.astimezone(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with plan.audit_path.open("a", encoding="utf-8", buffering=1) as handle:
        handle.write(_canonical_json(record).decode("utf-8"))


def execute_acquisition(
    plan: ForwardValidationPlan,
    *,
    client: object,
    calendar: object,
    retry_failures: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Acquire only immutable partitions; never replay or summarize outcomes."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    observed_at = clock()
    if observed_at.tzinfo is None:
        raise ForwardValidationError("Acquisition clock must be timezone-aware")
    for session in plan.sessions:
        close = calendar.schedule(session, "XNYS").close_timestamp
        if observed_at < close.to_pydatetime().astimezone(observed_at.tzinfo):
            raise ForwardValidationError(
                f"Cannot acquire an incomplete or future XNYS session: {session}"
            )
    _verify_existing_control_files(plan)
    _publish_manifest_once(plan)
    _audit(
        plan, "acquisition_started", recorded_at=observed_at,
        source_commit=plan.source_commit,
        start_date=plan.start.isoformat(), end_date=plan.end.isoformat(),
    )
    with backfill_job_lock(plan.root, DATASET_VINTAGE):
        for task in plan.tasks:
            try:
                result = run_task(
                    client, calendar, plan.root, task, dataset_vintage=DATASET_VINTAGE,
                    feed="sip", retry_failures=retry_failures,
                )
            except Exception as exc:
                _audit(
                    plan, "acquisition_failed", recorded_at=clock(),
                    symbol=task.instrument.symbol,
                    trading_date=task.trading_date.isoformat(),
                    error_type=type(exc).__name__,
                )
                raise
            _audit(
                plan, "partition_processed", recorded_at=clock(), symbol=result.symbol,
                trading_date=result.trading_date.isoformat(), status=result.status,
            )
    _audit(plan, "acquisition_finished", recorded_at=clock())
