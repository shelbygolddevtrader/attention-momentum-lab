"""Fail-closed operations for the preregistered V0.1.1 validation extension."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
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
_PROTECTED_PATH_TOKENS = {"final", "finalized", "holdout", "tournament", "tournaments"}
_AUDIT_FIELDS = {
    "acquisition_started": {"source_commit", "start_date", "end_date"},
    "partition_processed": {"symbol", "trading_date", "status"},
    "acquisition_failed": {"symbol", "trading_date", "error_type"},
    "acquisition_finished": set(),
}
_AUDIT_COMMON_FIELDS = {
    "schema_version", "request_id", "sequence", "previous_record_sha256",
    "recorded_at", "event", "record_sha256",
}


class ForwardValidationError(RuntimeError):
    """Raised before an unsafe or non-preregistered operation can begin."""


class RedactedProviderError(RuntimeError):
    """Provider failure whose message and retained payload contain no credentials."""


def _redact_text(value: str, secrets: Sequence[str]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _redact_value(value: object, secrets: Sequence[str]) -> object:
    if isinstance(value, dict):
        return {
            _redact_text(str(key), secrets): _redact_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), secrets)


class RedactedProviderClient:
    """Delegate provider calls while removing secrets from failure evidence."""

    def __init__(self, delegate: object, secret_values: Sequence[str]) -> None:
        self._delegate = delegate
        self._secrets = tuple(value for value in secret_values if value)

    def get_bars_range(self, *args: object, **kwargs: object):
        try:
            return self._delegate.get_bars_range(*args, **kwargs)
        except Exception as exc:
            safe = RedactedProviderError(
                f"Provider request failed ({type(exc).__name__})"
            )
            safe.retry_count = getattr(exc, "retry_count", 0)
            partial = getattr(exc, "partial_payload", None)
            if partial is not None:
                safe.partial_payload = _redact_value(partial, self._secrets)
            raise safe from None


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


def _path_tokens(path: Path) -> set[str]:
    return {
        token
        for part in path.parts
        for token in re.split(r"[^a-z0-9]+", part.casefold())
        if token
    }


def _repository_path(root: Path, value: Path, label: str) -> Path:
    raw = Path(value)
    if ".." in raw.parts:
        raise ForwardValidationError(f"{label} path traversal is prohibited")
    candidate = raw if raw.is_absolute() else root / raw
    absolute = validate_extension_input_path(candidate)
    try:
        absolute.relative_to(root)
    except ValueError as exc:
        raise ForwardValidationError(f"{label} path must remain inside the repository") from exc
    return absolute


def _reject_finalized_collision(path: Path) -> None:
    if _path_tokens(path).intersection(_PROTECTED_PATH_TOKENS):
        raise ForwardValidationError(
            "Output cannot collide with holdout, tournament, or finalized artifacts"
        )


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
    for path in (plan.manifest_path, plan.audit_path):
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise ForwardValidationError("Sealed control files must be regular, non-symlink files")
        if path.exists() and path.stat().st_nlink != 1:
            raise ForwardValidationError("Hard-linked sealed control files are prohibited")
    if plan.audit_path.exists() and not plan.manifest_path.exists():
        raise ForwardValidationError("An audit log cannot exist without its request manifest")
    if plan.manifest_path.exists():
        if plan.manifest_path.read_bytes() != _canonical_json(plan.identity):
            raise ForwardValidationError("Existing acquisition manifest has a different identity")
        if plan.audit_path.exists():
            _validate_audit_text(plan, plan.audit_path.read_text(encoding="utf-8"))


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
    universe_path = _repository_path(root, universe, "Universe")
    control_path = _repository_path(root, control_root, "Control output")
    verify_writable_destination(control_path)
    if universe_path != root / DEFAULT_UNIVERSE:
        raise ForwardValidationError("Universe must use the preregistered repository path")
    if control_path != root / DEFAULT_CONTROL_ROOT:
        raise ForwardValidationError("Control output must use the deterministic sealed path")
    dataset_root = _repository_path(
        root, Path("data") / "research" / DATASET_VINTAGE, "Dataset output"
    )
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
    validate_extension_input_path(plan.sealed_directory)
    if plan.sealed_directory.is_symlink() or not plan.sealed_directory.is_dir():
        raise ForwardValidationError("Sealed control destination is unsafe")
    _verify_existing_control_files(plan)
    content = _canonical_json(plan.identity)
    if plan.manifest_path.exists():
        if plan.manifest_path.is_symlink() or not plan.manifest_path.is_file():
            raise ForwardValidationError("Acquisition manifest must be a regular file")
        if plan.manifest_path.stat().st_nlink != 1:
            raise ForwardValidationError("Hard-linked acquisition manifests are prohibited")
        if plan.manifest_path.read_bytes() != content:
            raise ForwardValidationError("Existing acquisition manifest has a different identity")
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(plan.manifest_path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _validate_audit_text(plan: ForwardValidationPlan, text: str) -> tuple[int, str]:
    previous = hashlib.sha256(_canonical_json(plan.identity)).hexdigest()
    if not text:
        return 0, previous
    if not text.endswith("\n"):
        raise ForwardValidationError("Existing audit log is truncated")
    for expected_sequence, line in enumerate(text.splitlines(keepends=True), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ForwardValidationError("Existing audit log is malformed") from exc
        if not isinstance(record, dict) or _canonical_json(record).decode() != line:
            raise ForwardValidationError("Existing audit log is not canonical")
        event = record.get("event")
        expected_fields = _AUDIT_FIELDS.get(event)
        if expected_fields is None or set(record) != _AUDIT_COMMON_FIELDS | expected_fields:
            raise ForwardValidationError("Existing audit record schema is invalid")
        if (
            record.get("schema_version") != FORWARD_VALIDATION_SCHEMA
            or record.get("request_id") != plan.request_id
            or record.get("sequence") != expected_sequence
            or record.get("previous_record_sha256") != previous
        ):
            raise ForwardValidationError("Existing audit record identity or chain is invalid")
        try:
            recorded_at = datetime.fromisoformat(str(record["recorded_at"]))
        except ValueError as exc:
            raise ForwardValidationError("Existing audit timestamp is malformed") from exc
        if recorded_at.tzinfo is None:
            raise ForwardValidationError("Existing audit timestamp must be timezone-aware")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        actual_hash = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
        if record.get("record_sha256") != actual_hash:
            raise ForwardValidationError("Existing audit record hash is invalid")
        previous = actual_hash
    return expected_sequence, previous


def _audit(
    plan: ForwardValidationPlan,
    event: str,
    *,
    recorded_at: datetime,
    **fields: object,
) -> None:
    if recorded_at.tzinfo is None:
        raise ForwardValidationError("Audit timestamps must be timezone-aware")
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(plan.audit_path, flags, 0o600)
    except OSError as exc:
        raise ForwardValidationError("Audit log cannot be opened safely") from exc
    with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
        audit_stat = os.fstat(handle.fileno())
        if not stat.S_ISREG(audit_stat.st_mode):
            raise ForwardValidationError("Audit log must be a regular file")
        if audit_stat.st_nlink != 1:
            raise ForwardValidationError("Hard-linked audit logs are prohibited")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        sequence, previous = _validate_audit_text(plan, handle.read())
        unsigned = {
            "schema_version": FORWARD_VALIDATION_SCHEMA,
            "request_id": plan.request_id,
            "sequence": sequence + 1,
            "previous_record_sha256": previous,
            "recorded_at": recorded_at.astimezone(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        record = {
            **unsigned,
            "record_sha256": hashlib.sha256(_canonical_json(unsigned)).hexdigest(),
        }
        expected_fields = _AUDIT_FIELDS.get(event)
        if expected_fields is None or set(fields) != expected_fields:
            raise ForwardValidationError("Audit record fields do not match the event schema")
        handle.write(_canonical_json(record).decode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


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
                error_type = type(exc).__name__
                _audit(
                    plan, "acquisition_failed", recorded_at=clock(),
                    symbol=task.instrument.symbol,
                    trading_date=task.trading_date.isoformat(),
                    error_type=error_type,
                )
                raise ForwardValidationError(
                    f"Acquisition failed for {task.instrument.symbol} "
                    f"on {task.trading_date} ({error_type})"
                ) from None
            if result.status not in {"completed", "skipped"}:
                _audit(
                    plan, "acquisition_failed", recorded_at=clock(), symbol=result.symbol,
                    trading_date=result.trading_date.isoformat(),
                    error_type="PriorAcquisitionFailure",
                )
                raise ForwardValidationError(
                    f"Acquisition remains failed for {result.symbol} on {result.trading_date}"
                )
            _audit(
                plan, "partition_processed", recorded_at=clock(), symbol=result.symbol,
                trading_date=result.trading_date.isoformat(), status=result.status,
            )
    _audit(plan, "acquisition_finished", recorded_at=clock())
