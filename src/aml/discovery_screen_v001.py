"""Deterministic discovery-only adapter for nine frozen V002 strategies.

This module is intentionally non-authoritative: it cannot access dates after
2024-12-31, cannot execute gap-and-go, and writes only to an explicit external
artifact root.  Frozen executors remain the final proposal authority.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import tempfile
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from aml.discovery_evidence_v001 import DISCOVERY_END, DISCOVERY_START
from aml.professional_strategy_executor_models_v001 import (
    EvaluationInput,
    HaltInterval,
    HistoricalClockVolume,
    LiquidityHistory,
    MinuteBar,
    NextBarOpen,
)
from aml.professional_strategy_executors_v001 import STRATEGIES, evaluate
from aml.professional_strategy_indicators_v001 import (
    atr20_series,
    exact_elapsed_return,
    local_five_volume_ratio,
    prior_volume_ratio,
    regular_vwap_series,
)
from aml.winner_archetype_contracts import canonical_hash, canonical_json


NY = ZoneInfo("America/New_York")
DATASET_MANIFEST_SHA256 = "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b"
DATASET_FINGERPRINT = "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d"
V002_PROTOCOL_IDENTITY = "fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583"
DEFERRED_STRATEGY = "gap_and_go_long_v002"
INCLUDED_STRATEGIES = tuple(
    item for item in STRATEGIES if item != DEFERRED_STRATEGY
)
BASE_BPS = 10
COMMISSION_PER_SHARE = 0.005
MINIMUM_COMMISSION = 1.0
RISK_BUDGET = 250.0
INITIAL_CAPITAL = 100_000.0
MAXIMUM_GROSS_FRACTION = 0.5
MAXIMUM_CONCURRENT = 3
DAILY_LOSS_LIMIT = 0.01
EXCLUSION_REASONS = (
    "WARMUP_INCOMPLETE",
    "REGULAR_PARTITION_MISSING",
    "UNEXPLAINED_REGULAR_GAP",
    "HALT_COVERAGE_MISSING",
    "POST_HALT_BLOCKED",
    "HALT_INTERVAL_VALIDATOR_INCOMPATIBLE",
    "CORPORATE_ACTION_COVERAGE_MISSING",
    "CORPORATE_ACTION_UNRESOLVED",
    "SPY_PARTITION_MISSING",
    "HISTORICAL_VOLUME_BASELINE_INCOMPLETE",
    "LIQUIDITY_BASELINE_INCOMPLETE",
    "STRATEGY_INPUT_UNAVAILABLE",
)


class DiscoveryIntegrityError(RuntimeError):
    """A discovery boundary or reconciliation invariant failed closed."""


@dataclass(frozen=True, slots=True)
class CalendarSession:
    session: date
    opened: datetime
    closed: datetime
    early_close: bool


@dataclass(frozen=True, slots=True)
class PartitionState:
    symbol: str
    session: date
    csv_path: Path
    csv_sha256: str
    row_count: int
    expected_count: int
    missing_count: int
    complete_or_halt_explained: bool
    unexplained_missing: tuple[str, ...]
    starts_at_scheduled_open: bool
    halts: tuple[HaltInterval, ...]
    incompatible_halt_minutes: tuple[str, ...]
    action_unresolved: bool


@dataclass(frozen=True, slots=True)
class CompletedTrade:
    strategy_id: str
    strategy_identity: str
    proposal_identity: str
    symbol: str
    session: str
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    raw_entry: float
    raw_exit: float
    stop: float
    target: float
    quantity: int
    exit_reason: str
    gross_pnl: float
    entry_commission: float
    exit_commission: float
    net_pnl: float
    net_r_multiple: float
    cost_scenario: str = "base"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiscoveryIntegrityError(f"nonobject_json:{path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_external_discovery_path(path: Path) -> Path:
    resolved = path.resolve()
    parts = resolved.parts
    try:
        marker = parts.index("discovery_screening")
    except ValueError as exc:
        raise DiscoveryIntegrityError("non_discovery_output_namespace") from exc
    if parts[marker + 1:marker + 2] != ("nine_strategy_v001",):
        raise DiscoveryIntegrityError("non_discovery_output_namespace")
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / ".git").exists():
            raise DiscoveryIntegrityError("discovery_output_inside_git_repository")
    return resolved


def verify_dataset_root(dataset_root: Path, manifest_path: Path) -> dict[str, Any]:
    root = dataset_root.resolve()
    manifest = manifest_path.resolve()
    if _sha256(manifest) != DATASET_MANIFEST_SHA256:
        raise DiscoveryIntegrityError("dataset_manifest_sha256_mismatch")
    value = _load_json(manifest)
    if value.get("dataset_fingerprint_sha256") != DATASET_FINGERPRINT:
        raise DiscoveryIntegrityError("dataset_fingerprint_mismatch")
    coverage = value.get("coverage", {})
    if (
        coverage.get("start_date") != DISCOVERY_START.isoformat()
        or date.fromisoformat(str(coverage.get("end_date"))) < DISCOVERY_END
        or coverage.get("symbol_count") != 23
    ):
        raise DiscoveryIntegrityError("dataset_coverage_mismatch")
    if not (root / "sip").is_dir():
        raise DiscoveryIntegrityError("dataset_root_missing_sip")
    return value


def load_calendar(path: Path) -> tuple[str, tuple[CalendarSession, ...]]:
    value = _load_json(path)
    identity = value.pop("identity", None)
    if identity != canonical_hash(value):
        raise DiscoveryIntegrityError("calendar_identity_mismatch")
    sessions = tuple(
        CalendarSession(
            date.fromisoformat(item["session"]),
            datetime.fromisoformat(item["regular_open"]).astimezone(NY),
            datetime.fromisoformat(item["regular_close"]).astimezone(NY),
            bool(item["early_close"]),
        )
        for item in value["sessions"]
    )
    if len(sessions) != 364 or sessions[0].session != DISCOVERY_START or sessions[-1].session != DISCOVERY_END:
        raise DiscoveryIntegrityError("calendar_boundary_mismatch")
    return str(identity), sessions


def load_halts(path: Path) -> tuple[str, dict[tuple[str, date], tuple[HaltInterval, ...]]]:
    value = _load_json(path)
    identity = value.pop("identity", None)
    if identity != canonical_hash(value) or len(value.get("daily", [])) != 527:
        raise DiscoveryIntegrityError("halt_manifest_identity_or_coverage_mismatch")
    by_key: dict[tuple[str, date], list[HaltInterval]] = defaultdict(list)
    for record in value["normalized_records"]:
        if record.get("resumption_status") != "complete":
            raise DiscoveryIntegrityError("halt_unresolved_resumption")
        start = datetime.fromisoformat(record["halt_time"]).astimezone(NY)
        resume = datetime.fromisoformat(record["resumption_time"]).astimezone(NY)
        by_key[(record["symbol"], start.date())].append(
            HaltInterval(
                start=start,
                resume=resume,
                first_known_at=start,
                source_record_identity=canonical_hash(record),
            )
        )
    return str(identity), {
        key: tuple(sorted(items, key=lambda item: (item.start, item.resume)))
        for key, items in by_key.items()
    }


def _action_date(record: Mapping[str, Any]) -> date | None:
    dates = record.get("effective_dates", {})
    for key in ("effective_date", "ex_date", "process_date", "payable_date"):
        if dates.get(key):
            return date.fromisoformat(dates[key])
    return None


def load_action_exclusions(path: Path) -> tuple[str, dict[str, tuple[date, ...]], Counter[str]]:
    value = _load_json(path)
    identity = value.pop("identity", None)
    if identity != canonical_hash(value) or not value.get("pagination_complete"):
        raise DiscoveryIntegrityError("corporate_action_identity_or_coverage_mismatch")
    affected: dict[str, set[date]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for record in value["records"]:
        counts[record["action_type"]] += 1
        if record["action_type"] == "cash_dividend":
            continue
        effective = _action_date(record)
        if effective is None:
            raise DiscoveryIntegrityError("corporate_action_effective_date_missing")
        for symbol in record["universe_symbols"]:
            affected[symbol].add(effective)
    return str(identity), {
        symbol: tuple(sorted(values)) for symbol, values in affected.items()
    }, counts


def _minute_overlaps_halt(timestamp: datetime, halt: HaltInterval) -> bool:
    """Return whether left-labeled ``[t,t+1m)`` overlaps ``[start,resume)``."""

    return timestamp < halt.resume and timestamp + timedelta(minutes=1) > halt.start


def _incompatible_halt_minutes(
    opened: datetime,
    closed: datetime,
    halts: tuple[HaltInterval, ...],
) -> tuple[str, ...]:
    """Find halt-overlap minutes the unchanged frozen validator cannot represent.

    The frozen executor validator classifies a missing minute by its left label.
    The discovery adapter conservatively removes the whole one-minute interval
    when any part overlaps an official halt.  A minute is incompatible exactly
    when interval overlap is true but no official halt contains its left label.
    Excluding that symbol-session preserves both semantics without rewriting an
    official timestamp or changing the frozen validator identity.
    """

    incompatible: list[str] = []
    cursor = opened
    while cursor < closed:
        interval_covered = any(
            _minute_overlaps_halt(cursor, halt) for halt in halts
        )
        point_covered = any(
            halt.start <= cursor < halt.resume for halt in halts
        )
        if interval_covered and not point_covered:
            incompatible.append(cursor.isoformat())
        cursor += timedelta(minutes=1)
    return tuple(incompatible)


def _read_timestamps(path: Path) -> tuple[datetime, ...]:
    frame = pd.read_csv(path, usecols=["timestamp"])
    values = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("America/New_York")
    result = tuple(item.to_pydatetime().astimezone(NY) for item in values)
    if tuple(sorted(result)) != result or len(set(result)) != len(result):
        raise DiscoveryIntegrityError(f"partition_timestamp_integrity:{path.parent.parent.name}")
    if any(item.date() > DISCOVERY_END for item in result):
        raise DiscoveryIntegrityError("later_session_access_detected")
    return result


def inspect_partition(
    dataset_root: Path,
    symbol: str,
    calendar: CalendarSession,
    halts: tuple[HaltInterval, ...],
    action_dates: tuple[date, ...],
) -> PartitionState:
    base = dataset_root / "sip" / symbol / calendar.session.isoformat()
    csv_path = base / "processed" / "regular_1min.csv"
    metadata_path = base / "metadata" / "regular_acquisition.json"
    expected = int((calendar.closed - calendar.opened).total_seconds() // 60)
    if not csv_path.is_file() or not metadata_path.is_file():
        return PartitionState(
            symbol, calendar.session, csv_path, "", 0, expected, expected,
            False, (), False, halts,
            _incompatible_halt_minutes(calendar.opened, calendar.closed, halts),
            False,
        )
    metadata = _load_json(metadata_path)
    if (
        metadata.get("trading_date") != calendar.session.isoformat()
        or metadata.get("symbol") != symbol
        or metadata.get("requested_feed") != "sip"
        or metadata.get("adjustment") != "all"
    ):
        raise DiscoveryIntegrityError("partition_metadata_binding_mismatch")
    csv_sha = str(metadata.get("processed_sha256", ""))
    if _sha256(csv_path) != csv_sha:
        raise DiscoveryIntegrityError("partition_hash_mismatch")
    timestamps = _read_timestamps(csv_path)
    expected_values = tuple(
        calendar.opened + timedelta(minutes=offset) for offset in range(expected)
    )
    actual = set(timestamps)
    missing = tuple(item for item in expected_values if item not in actual)
    unexpected = tuple(item for item in timestamps if item not in set(expected_values))
    if unexpected:
        raise DiscoveryIntegrityError("partition_outside_regular_session")
    unexplained = tuple(
        item.isoformat()
        for item in missing
        if not any(_minute_overlaps_halt(item, halt) for halt in halts)
    )
    # A retroactively adjusted partition before/on a non-cash action cannot be
    # reconstructed point-in-time without historical revision timestamps.
    action_unresolved = any(calendar.session <= action_date for action_date in action_dates)
    incompatible_halt_minutes = _incompatible_halt_minutes(
        calendar.opened, calendar.closed, halts
    )
    return PartitionState(
        symbol,
        calendar.session,
        csv_path,
        csv_sha,
        len(timestamps),
        expected,
        len(missing),
        not unexplained,
        unexplained,
        bool(
            timestamps
            and timestamps[0] == calendar.opened
            and not any(
                halt.start <= calendar.opened < halt.resume for halt in halts
            )
        ),
        halts,
        incompatible_halt_minutes,
        action_unresolved,
    )


def _needs_same_clock(strategy_id: str) -> bool:
    return strategy_id in {"five_minute_orb_long_v002", "fifteen_minute_orb_long_v002"}


def _needs_liquidity(strategy_id: str) -> bool:
    return strategy_id in {
        "market_relative_momentum_long_v002",
        "rsi_exhaustion_reversion_long_v002",
    }


def _needs_spy(strategy_id: str) -> bool:
    return _needs_liquidity(strategy_id)


def _preflight_exclusion_reason(
    state: PartitionState,
    strategy_id: str,
    spy: PartitionState | None,
    history_count: int,
) -> str:
    if not state.csv_path.is_file():
        return "REGULAR_PARTITION_MISSING"
    if state.unexplained_missing:
        return "UNEXPLAINED_REGULAR_GAP"
    if state.incompatible_halt_minutes:
        return "HALT_INTERVAL_VALIDATOR_INCOMPATIBLE"
    if not state.starts_at_scheduled_open:
        return "STRATEGY_INPUT_UNAVAILABLE"
    if state.action_unresolved:
        return "CORPORATE_ACTION_UNRESOLVED"
    if _needs_spy(strategy_id) and (
        spy is None
        or not spy.csv_path.is_file()
        or not spy.complete_or_halt_explained
        or bool(spy.incompatible_halt_minutes)
        or not spy.starts_at_scheduled_open
        or spy.action_unresolved
    ):
        return "SPY_PARTITION_MISSING"
    if (_needs_same_clock(strategy_id) or _needs_liquidity(strategy_id)) and (
        history_count < 20
    ):
        return "WARMUP_INCOMPLETE"
    return ""


def build_preflight(
    *,
    dataset_root: Path,
    manifest_path: Path,
    evidence_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    _require_external_discovery_path(output_path)
    manifest = verify_dataset_root(dataset_root, manifest_path)
    calendar_identity, sessions = load_calendar(evidence_root / "calendar_v001.json")
    halt_identity, halt_map = load_halts(evidence_root / "halts_v001/manifest.json")
    action_identity, actions, action_counts = load_action_exclusions(
        evidence_root / "corporate_actions_v001/manifest.json"
    )
    symbols = tuple(manifest["coverage"]["symbols"])
    states: dict[tuple[str, date], PartitionState] = {}
    for calendar in sessions:
        for symbol in symbols:
            states[(symbol, calendar.session)] = inspect_partition(
                dataset_root,
                symbol,
                calendar,
                halt_map.get((symbol, calendar.session), ()),
                actions.get(symbol, ()),
            )
    rows: list[dict[str, Any]] = []
    eligible_history: dict[str, list[date]] = defaultdict(list)
    for calendar in sessions:
        spy = states.get(("SPY", calendar.session))
        for symbol in symbols:
            state = states[(symbol, calendar.session)]
            for strategy_id in INCLUDED_STRATEGIES:
                history = eligible_history[symbol][-40:]
                reason = _preflight_exclusion_reason(
                    state, strategy_id, spy, len(history)
                )
                rows.append({
                    "strategy_id": strategy_id,
                    "strategy_identity": STRATEGIES[strategy_id]["strategy_identity"],
                    "symbol": symbol,
                    "session": calendar.session.isoformat(),
                    "partition_sha256": state.csv_sha256,
                    "regular_complete": state.complete_or_halt_explained,
                    "missing_minute_count": state.missing_count,
                    "halt_status": "positive" if state.halts else "negative_complete",
                    "halt_interval_validation_status": (
                        "incompatible"
                        if state.incompatible_halt_minutes
                        else "compatible"
                    ),
                    "incompatible_halt_minutes": ";".join(
                        state.incompatible_halt_minutes
                    ),
                    "halt_intervals": ";".join(
                        f"{item.start.isoformat()}/{item.resume.isoformat()}" for item in state.halts
                    ),
                    "corporate_action_status": "unresolved" if state.action_unresolved else "covered",
                    "warmup_status": "complete" if len(history) >= 20 else "incomplete",
                    "spy_status": "not_required" if not _needs_spy(strategy_id) else (
                        "complete" if spy and spy.complete_or_halt_explained else "missing"
                    ),
                    "same_clock_volume_history_status": "not_required" if not _needs_same_clock(strategy_id) else (
                        "complete" if len(history) >= 20 else "incomplete"
                    ),
                    "liquidity_history_status": "not_required" if not _needs_liquidity(strategy_id) else (
                        "complete" if len(history) >= 20 else "incomplete"
                    ),
                    "included": not reason,
                    "exclusion_reason": reason,
                })
            if (
                state.csv_path.is_file()
                and state.complete_or_halt_explained
                and not state.incompatible_halt_minutes
                and not state.action_unresolved
                and not calendar.early_close
                and not state.halts
            ):
                eligible_history[symbol].append(calendar.session)
    rows.sort(key=lambda item: (item["strategy_id"], item["symbol"], item["session"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise DiscoveryIntegrityError("preflight_output_exists")
    with output_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema": "aml.discovery-preflight.v001",
        "dataset_manifest_sha256": DATASET_MANIFEST_SHA256,
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "calendar_identity": calendar_identity,
        "halt_identity": halt_identity,
        "corporate_action_identity": action_identity,
        "corporate_action_counts": dict(sorted(action_counts.items())),
        "row_count": len(rows),
        "included_by_strategy": dict(sorted(Counter(
            item["strategy_id"] for item in rows if item["included"]
        ).items())),
        "excluded_by_strategy_reason": {
            f"{key[0]}|{key[1]}": count for key, count in sorted(Counter(
                (item["strategy_id"], item["exclusion_reason"])
                for item in rows if not item["included"]
            ).items())
        },
        "ledger_sha256": _sha256(output_path),
    }
    summary["identity"] = canonical_hash(summary)
    return summary


def load_minute_bars(state: PartitionState) -> tuple[MinuteBar, ...]:
    frame = pd.read_csv(state.csv_path)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("America/New_York")
    bars = tuple(
        MinuteBar(
            security_id=state.symbol,
            symbol=state.symbol,
            session=state.session,
            timestamp=timestamp.to_pydatetime().astimezone(NY),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
            feed="sip",
            adjustment_identity=DATASET_FINGERPRINT,
            source_manifest_identity=state.csv_sha256,
        )
        for timestamp, row in zip(timestamps, frame.itertuples(index=False), strict=True)
        if not any(
            _minute_overlaps_halt(
                timestamp.to_pydatetime().astimezone(NY), halt
            )
            for halt in state.halts
        )
    )
    return bars


def _window(strategy_id: str, current: str) -> bool:
    windows = {
        "failed_downside_breakdown_reclaim_long_v002": ("09:46", "15:00"),
        "first_pullback_continuation_long_v002": ("09:35", "11:30"),
        "five_minute_orb_long_v002": ("09:35", "10:59"),
        "fifteen_minute_orb_long_v002": ("09:45", "11:29"),
        "high_of_day_breakout_long_v002": ("09:45", "15:00"),
        "market_relative_momentum_long_v002": ("09:45", "15:00"),
        "rsi_exhaustion_reversion_long_v002": ("09:50", "15:00"),
        "vwap_mean_reversion_fade_long_v002": ("09:50", "15:00"),
        "vwap_reclaim_long_v002": ("09:50", "15:00"),
    }
    start, end = windows[strategy_id]
    return start <= current <= end


def _candidate(
    strategy_id: str,
    bars: tuple[MinuteBar, ...],
    index: int,
    spy_bars: tuple[MinuteBar, ...],
    features: Mapping[str, Any],
) -> bool:
    if index < 1:
        return False
    current = bars[index]
    if strategy_id == "first_pullback_continuation_long_v002":
        if current.close <= bars[index - 1].high or features["atr20"][index] is None:
            return False
        anchor_index = 0
        impulse: tuple[int, int] | None = None
        for cursor in range(1, index):
            if features["minutes"][cursor] > "10:00":
                break
            if bars[cursor].low < bars[anchor_index].low:
                anchor_index = cursor
            ratio = local_five_volume_ratio(bars, cursor)
            if (
                bars[cursor].high / bars[anchor_index].low - 1 >= 0.03
                and ratio is not None and ratio >= 2
            ):
                impulse = (anchor_index, cursor)
                break
        if impulse is None or impulse[1] < 4:
            return False
        anchor_index, impulse_end = impulse
        pullback_start = next((
            cursor for cursor in range(impulse_end + 1, index + 1)
            if bars[cursor].low < bars[cursor - 1].low
        ), None)
        if pullback_start is None:
            return False
        duration = index - pullback_start + 1
        if not 2 <= duration <= 10:
            return False
        impulse_low = bars[anchor_index].low
        impulse_high = bars[impulse_end].high
        pullback = bars[pullback_start:index + 1]
        pullback_low = min(bar.low for bar in pullback)
        depth = (impulse_high - pullback_low) / (impulse_high - impulse_low)
        midpoint = impulse_high - 0.5 * (impulse_high - impulse_low)
        impulse_volume = sum(
            bar.volume for bar in bars[impulse_end - 4:impulse_end + 1]
        ) / 5
        return (
            0.20 <= depth <= 0.50
            and not any(bar.close < midpoint for bar in pullback)
            and not any(
                bar.low < impulse_low for bar in bars[impulse_end + 1:index + 1]
            )
            and sum(bar.volume for bar in pullback) / len(pullback) < impulse_volume
        )
    if strategy_id in {"five_minute_orb_long_v002", "fifteen_minute_orb_long_v002"}:
        minutes = 5 if strategy_id.startswith("five") else 15
        if index < minutes:
            return False
        range_high = max(item.high for item in bars[:minutes])
        range_low = min(item.low for item in bars[:minutes])
        return (
            current.close > range_high
            and not any(item.close < range_low for item in bars[minutes:index])
        )
    if strategy_id == "high_of_day_breakout_long_v002":
        mature_hod = features["mature_hod"][index]
        if mature_hod is None or current.close <= mature_hod or index < 5:
            return False
        consolidation = bars[index - 5:index]
        atr = features["atr20"][index]
        ratio = prior_volume_ratio(bars, index)
        if atr is None or ratio is None:
            return False
        mature_index = next(
            cursor for cursor, bar in enumerate(bars[:index])
            if bar.timestamp <= current.timestamp - timedelta(minutes=15)
            and bar.high == mature_hod
        )
        failures = sum(
            bar.high > mature_hod and bar.close <= mature_hod
            for bar in bars[mature_index + 1:index]
        )
        return (
            not any(bar.high > mature_hod for bar in consolidation)
            and max(bar.high for bar in consolidation)
            - min(bar.low for bar in consolidation) <= 0.75 * atr
            and failures <= 2
            and ratio >= 1.5
        )
    if strategy_id == "market_relative_momentum_long_v002":
        symbol_return = features["return15"][index]
        spy_return = (
            exact_elapsed_return(spy_bars, len(spy_bars) - 1, 15)
            if spy_bars else None
        )
        return symbol_return is not None and spy_return is not None and symbol_return > 0 and symbol_return - spy_return >= 0.02
    if strategy_id == "rsi_exhaustion_reversion_long_v002":
        value = features["return20"][index]
        return value is not None and value <= -0.02 and current.close > bars[index - 1].high
    if strategy_id == "vwap_mean_reversion_fade_long_v002":
        if index < 4 or current.close <= bars[index - 1].close:
            return False
        declines = [
            bars[cursor - 1].close - bars[cursor].close
            for cursor in range(index - 3, index)
        ]
        atr = features["atr20"][index]
        vwap = features["vwap"][index]
        return (
            atr is not None
            and vwap is not None
            and all(item > 0 for item in declines)
            and declines[0] > declines[1] > declines[2]
            and (vwap - current.close) / atr >= 1.5
        )
    if strategy_id == "vwap_reclaim_long_v002":
        vwaps = features["vwap"]
        if not (
            index >= 4 and vwaps[index] is not None and vwaps[index - 1] is not None
            and current.close > vwaps[index] and bars[index - 1].close > vwaps[index - 1]
        ):
            return False
        sequence_end = index - 2
        sequence_start = sequence_end
        while (
            sequence_start >= 0 and vwaps[sequence_start] is not None
            and bars[sequence_start].close < vwaps[sequence_start]
        ):
            sequence_start -= 1
        return (
            sequence_end - sequence_start >= 3
            and (prior_volume_ratio(bars, index) or 0) >= 1.2
        )
    if strategy_id == "failed_downside_breakdown_reclaim_long_v002":
        atr = features["atr20"]
        reclaim_index = index - 1
        for breach_index in range(max(0, reclaim_index - 3), reclaim_index):
            prior_low = features["mature_low"][breach_index]
            breach_atr = atr[breach_index]
            if prior_low is not None and breach_atr is not None:
                if (
                    bars[breach_index].low <= prior_low - 0.25 * breach_atr
                    and bars[breach_index].close < prior_low
                    and bars[reclaim_index].close > prior_low
                    and current.close > prior_low
                ):
                    return True
        return False
    return True


def _session_features(bars: tuple[MinuteBar, ...]) -> dict[str, Any]:
    lookup = {bar.timestamp: index for index, bar in enumerate(bars)}
    return15: list[float | None] = []
    return20: list[float | None] = []
    mature_hod: list[float | None] = []
    mature_low: list[float | None] = []
    mature_cursor = 0
    running_mature_hod: float | None = None
    running_mature_low: float | None = None
    for index, bar in enumerate(bars):
        for minutes, target in ((15, return15), (20, return20)):
            start = lookup.get(bar.timestamp - timedelta(minutes=minutes))
            if start is None or index - start != minutes:
                target.append(None)
            else:
                target.append(bar.close / bars[start].close - 1)
        cutoff = bar.timestamp - timedelta(minutes=15)
        while mature_cursor < index and bars[mature_cursor].timestamp <= cutoff:
            value = bars[mature_cursor].high
            running_mature_hod = (
                value if running_mature_hod is None else max(running_mature_hod, value)
            )
            low = bars[mature_cursor].low
            running_mature_low = (
                low if running_mature_low is None else min(running_mature_low, low)
            )
            mature_cursor += 1
        mature_hod.append(running_mature_hod)
        mature_low.append(running_mature_low)
    return {
        "atr20": atr20_series(bars),
        "vwap": regular_vwap_series(bars),
        "return15": tuple(return15),
        "return20": tuple(return20),
        "mature_hod": tuple(mature_hod),
        "mature_low": tuple(mature_low),
        "minutes": tuple(
            f"{item.timestamp.hour:02d}:{item.timestamp.minute:02d}" for item in bars
        ),
    }


def _commission(quantity: int) -> float:
    return max(MINIMUM_COMMISSION, quantity * COMMISSION_PER_SHARE)


def _raw_exit(
    proposal: Any,
    bars: tuple[MinuteBar, ...],
    scheduled_close: datetime,
) -> tuple[datetime, float, str]:
    index_by_time = {item.timestamp: index for index, item in enumerate(bars)}
    entry_index = index_by_time.get(datetime.fromisoformat(proposal.intended_entry_timestamp))
    if entry_index is None:
        raise DiscoveryIntegrityError("accepted_proposal_missing_entry_bar")
    liquidation = min(
        scheduled_close.replace(hour=15, minute=55),
        scheduled_close - timedelta(minutes=5),
    )
    held = 0
    for bar in bars[entry_index:]:
        held += 1
        if bar.open <= proposal.stop:
            return bar.timestamp + timedelta(minutes=1), bar.open, "gap_stop"
        if bar.low <= proposal.stop:
            return bar.timestamp + timedelta(minutes=1), proposal.stop, "intrabar_stop"
        if bar.open >= proposal.target:
            return bar.timestamp + timedelta(minutes=1), bar.open, "gap_target"
        if bar.high >= proposal.target:
            return bar.timestamp + timedelta(minutes=1), proposal.target, "intrabar_target"
        if held >= proposal.timeout_complete_bars:
            return bar.timestamp + timedelta(minutes=1), bar.close, "timeout"
        if bar.timestamp >= liquidation:
            return bar.timestamp + timedelta(minutes=1), bar.close, "session_liquidation"
    raise DiscoveryIntegrityError("open_position_missing_exit_bar")


def _project_trade(trade: CompletedTrade, multiplier: float, name: str) -> CompletedTrade:
    entry = trade.raw_entry * (1 + BASE_BPS / 10_000 * multiplier)
    exit_value = trade.raw_exit * (1 - BASE_BPS / 10_000 * multiplier)
    gross = trade.quantity * (exit_value - entry)
    net = gross - trade.entry_commission - trade.exit_commission
    return CompletedTrade(
        **{
            **asdict(trade),
            "gross_pnl": gross,
            "net_pnl": net,
            "net_r_multiple": net / RISK_BUDGET,
            "cost_scenario": name,
        }
    )


def simulate_strategy(
    strategy_id: str,
    proposals: Sequence[Any],
    bars_by_key: Mapping[tuple[str, date], tuple[MinuteBar, ...]],
    calendar_by_date: Mapping[date, CalendarSession],
) -> tuple[list[CompletedTrade], list[dict[str, Any]]]:
    accepted: list[CompletedTrade] = []
    rejections: list[dict[str, Any]] = []
    open_positions: list[CompletedTrade] = []
    equity = INITIAL_CAPITAL
    cash = INITIAL_CAPITAL
    entries: dict[tuple[str, date], list[datetime]] = defaultdict(list)
    daily_realized: Counter[date] = Counter()
    for proposal in sorted(
        proposals,
        key=lambda item: (item.signal_timestamp, item.strategy_identity, item.symbol),
    ):
        entry_time = datetime.fromisoformat(proposal.intended_entry_timestamp)
        session = date.fromisoformat(proposal.session)
        still_open: list[CompletedTrade] = []
        for position in open_positions:
            if datetime.fromisoformat(position.exit_timestamp) <= entry_time:
                equity += position.net_pnl
                cash += (
                    position.quantity * position.raw_exit * 0.999
                    - position.exit_commission
                )
                daily_realized[date.fromisoformat(position.session)] += position.net_pnl
            else:
                still_open.append(position)
        open_positions = still_open
        prior = entries[(proposal.symbol, session)]
        max_entries = int(STRATEGIES[strategy_id]["maximum_entries_per_symbol_day"])
        cooldown = int(STRATEGIES[strategy_id]["cooldown_complete_bars"])
        reason = ""
        if len(prior) >= max_entries:
            reason = "maximum_entries_reached"
        elif prior and entry_time < prior[-1] + timedelta(minutes=cooldown):
            reason = "cooldown_active"
        elif daily_realized[session] <= -INITIAL_CAPITAL * DAILY_LOSS_LIMIT:
            reason = "daily_loss_block"
        elif len(open_positions) >= MAXIMUM_CONCURRENT:
            reason = "concurrency_block"
        raw_risk = proposal.cost_adjusted_entry - proposal.stop
        base_quantity = math.floor(RISK_BUDGET / raw_risk) if raw_risk > 0 else 0
        gross_open = sum(item.quantity * item.raw_entry for item in open_positions)
        quantity = min(
            base_quantity,
            math.floor(max(0.0, MAXIMUM_GROSS_FRACTION * equity - gross_open) / proposal.cost_adjusted_entry),
            math.floor(max(0.0, cash) / proposal.cost_adjusted_entry),
        )
        if not reason and quantity <= 0:
            reason = "exposure_block"
        if reason:
            rejections.append({
                "strategy_id": strategy_id,
                "proposal_identity": proposal.proposal_identity,
                "symbol": proposal.symbol,
                "session": proposal.session,
                "signal_timestamp": proposal.signal_timestamp,
                "reason": reason,
            })
            continue
        bars = bars_by_key[(proposal.symbol, session)]
        exit_time, raw_exit, exit_reason = _raw_exit(
            proposal, bars, calendar_by_date[session].closed
        )
        entry_commission = _commission(quantity)
        exit_commission = _commission(quantity)
        adjusted_exit = raw_exit * 0.999
        gross = quantity * (adjusted_exit - proposal.cost_adjusted_entry)
        net = gross - entry_commission - exit_commission
        trade = CompletedTrade(
            strategy_id=strategy_id,
            strategy_identity=proposal.strategy_identity,
            proposal_identity=proposal.proposal_identity,
            symbol=proposal.symbol,
            session=proposal.session,
            signal_timestamp=proposal.signal_timestamp,
            entry_timestamp=proposal.intended_entry_timestamp,
            exit_timestamp=exit_time.isoformat(),
            raw_entry=proposal.raw_entry_open,
            raw_exit=raw_exit,
            stop=proposal.stop,
            target=proposal.target,
            quantity=quantity,
            exit_reason=exit_reason,
            gross_pnl=gross,
            entry_commission=entry_commission,
            exit_commission=exit_commission,
            net_pnl=net,
            net_r_multiple=net / RISK_BUDGET,
        )
        cash -= quantity * proposal.cost_adjusted_entry + entry_commission
        entries[(proposal.symbol, session)].append(entry_time)
        open_positions.append(trade)
        accepted.append(trade)
    for position in open_positions:
        equity += position.net_pnl
    return accepted, rejections


def trade_metrics(trades: Sequence[CompletedTrade]) -> dict[str, Any]:
    ordered = sorted(
        trades, key=lambda item: (item.exit_timestamp, item.proposal_identity)
    )
    pnl = [item.net_pnl for item in ordered]
    wins = [item for item in pnl if item > 0]
    losses = [item for item in pnl if item < 0]
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for item in pnl:
        cumulative += item
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    net = sum(pnl)
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    symbol_pnl: Counter[str] = Counter()
    month_pnl: Counter[str] = Counter()
    for trade in trades:
        symbol_pnl[trade.symbol] += trade.net_pnl
        month_pnl[trade.session[:7]] += trade.net_pnl
    positive_total = sum(max(0.0, value) for value in symbol_pnl.values())
    return {
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) if trades else None,
        "gross_pnl": sum(item.gross_pnl for item in trades),
        "net_pnl": net,
        "net_expectancy": net / len(trades) if trades else None,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "profit_factor_infinite": bool(gross_profit and not gross_loss),
        "payoff_ratio": statistics.mean(wins) / -statistics.mean(losses) if wins and losses else None,
        "maximum_drawdown": drawdown,
        "tail_loss": min(pnl) if pnl else None,
        "largest_trade_profit_share": max(wins) / net if wins and net > 0 else None,
        "largest_symbol_profit_share": max(symbol_pnl.values()) / net if symbol_pnl and net > 0 else None,
        "positive_month_count": sum(value > 0 for value in month_pnl.values()),
        "active_symbols": sum(bool(value) for value in symbol_pnl.values()),
        "positive_symbol_pnl_total": positive_total,
        "symbol_pnl": dict(sorted(symbol_pnl.items())),
        "month_pnl": dict(sorted(month_pnl.items())),
    }


def classify(metrics: Mapping[str, Any], *, material_data_limitation: bool) -> str:
    count = int(metrics["trade_count"])
    if material_data_limitation:
        return "INCONCLUSIVE_DATA_LIMITATION"
    if count < 30:
        return "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    base_expectancy = float(metrics["base"]["net_expectancy"])
    stress_expectancy = float(metrics["cost_1_5x"]["net_expectancy"])
    if base_expectancy <= 0 and stress_expectancy <= 0:
        return "REJECT"
    base = metrics["base"]
    if (
        base_expectancy > 0
        and stress_expectancy > 0
        and (
            bool(base["profit_factor_infinite"])
            or float(base["profit_factor"] or 0) > 1.10
        )
        and float(base["largest_trade_profit_share"] or math.inf) <= 0.25
        and float(base["largest_symbol_profit_share"] or math.inf) <= 0.50
        and int(base["positive_month_count"]) > 1
        and float(base["maximum_drawdown"]) <= float(base["net_pnl"])
    ):
        return "PROMISING_FOR_BROADER_DISCOVERY"
    raise DiscoveryIntegrityError("screening_classification_rules_do_not_cover_result")


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_json(dict(value)))


def write_csv_exclusive(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise DiscoveryIntegrityError(f"immutable_output_exists:{path.name}")
    fieldnames = list(rows[0]) if rows else ["empty"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def artifact_manifest(root: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "manifest.json"):
        files.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        })
    value = {"schema": "aml.discovery-screen-artifacts.v001", **metadata, "files": files}
    value["identity"] = canonical_hash(value)
    return value


def evaluation_accounting(
    failure_rows: Sequence[Mapping[str, Any]],
    evaluation_totals: Mapping[str, int],
    proposal_counts: Mapping[str, int],
) -> dict[str, Any]:
    """Reconcile every post-preflight evaluation to one explicit status."""

    allowed_statuses = {
        "integrity_failure",
        "no_signal",
        "no_trade",
        "proposal",
        "unavailable",
    }
    by_strategy_status: Counter[tuple[str, str]] = Counter()
    preflight_exclusions: Counter[str] = Counter()
    for row in failure_rows:
        strategy_id = str(row["strategy_id"])
        if strategy_id not in INCLUDED_STRATEGIES:
            raise DiscoveryIntegrityError(
                f"unknown_evaluation_accounting_strategy:{strategy_id}"
            )
        count = int(row["count"])
        if count < 0:
            raise DiscoveryIntegrityError("negative_evaluation_accounting_count")
        if row["stage"] == "evaluation":
            status = str(row["status"])
            if status not in allowed_statuses:
                raise DiscoveryIntegrityError(
                    f"unknown_evaluation_accounting_status:{status}"
                )
            by_strategy_status[(strategy_id, status)] += count
        elif row["stage"] == "preflight":
            if row["status"] != "excluded" or row["reason"] not in EXCLUSION_REASONS:
                raise DiscoveryIntegrityError("invalid_preflight_accounting_row")
            preflight_exclusions[strategy_id] += count
        else:
            raise DiscoveryIntegrityError("unknown_evaluation_accounting_stage")
    for strategy_id in INCLUDED_STRATEGIES:
        accounted = sum(
            count
            for (item_strategy, _), count in by_strategy_status.items()
            if item_strategy == strategy_id
        )
        if accounted != int(evaluation_totals.get(strategy_id, 0)):
            raise DiscoveryIntegrityError(
                f"evaluation_accounting_mismatch:{strategy_id}:"
                f"expected={evaluation_totals.get(strategy_id, 0)}:actual={accounted}"
            )
        proposal_status_count = by_strategy_status.get((strategy_id, "proposal"), 0)
        if proposal_status_count != int(proposal_counts.get(strategy_id, 0)):
            raise DiscoveryIntegrityError(
                f"proposal_status_accounting_mismatch:{strategy_id}"
            )
    integrity_count = sum(
        count
        for (_, status), count in by_strategy_status.items()
        if status == "integrity_failure"
    )
    return {
        "evaluation_totals": dict(sorted(
            (key, int(value)) for key, value in evaluation_totals.items()
        )),
        "preflight_exclusion_counts": dict(sorted(preflight_exclusions.items())),
        "status_counts": {
            f"{strategy_id}|{status}": count
            for (strategy_id, status), count in sorted(by_strategy_status.items())
        },
        "executor_integrity_failure_count": integrity_count,
    }


def _publish_integrity_failure_bundle(
    output_root: Path,
    failure_rows: Sequence[Mapping[str, Any]],
    accounting: Mapping[str, Any],
) -> None:
    """Publish diagnostics, never performance, for a failed executor run."""

    integrity_rows = [
        dict(row)
        for row in failure_rows
        if row["stage"] == "evaluation" and row["status"] == "integrity_failure"
    ]
    if not integrity_rows:
        raise DiscoveryIntegrityError("integrity_failure_bundle_without_failures")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    publication_root = Path(tempfile.mkdtemp(
        prefix=f".{output_root.name}-failed-", dir=output_root.parent
    ))
    try:
        write_csv_exclusive(
            publication_root / "executor_integrity_failures.csv", integrity_rows
        )
        summary = {
            "schema": "aml.nine-strategy-discovery-screen.failure.v001",
            "status": "FAILED_EXECUTOR_INTEGRITY",
            "classification": "FAILED_EXECUTOR_INTEGRITY",
            "executor_integrity_failure_count": int(
                accounting["executor_integrity_failure_count"]
            ),
            "evaluation_accounting": dict(accounting),
            "performance_artifacts_published": False,
        }
        summary["identity"] = canonical_hash(summary)
        write_json_exclusive(publication_root / "failure_summary.json", summary)
        manifest = artifact_manifest(publication_root, {
            "publication_status": "FAILED_EXECUTOR_INTEGRITY",
            "failure_summary_identity": summary["identity"],
        })
        write_json_exclusive(publication_root / "manifest.json", manifest)
        os.replace(publication_root, output_root)
    except Exception:
        shutil.rmtree(publication_root, ignore_errors=True)
        raise


def enforce_zero_executor_integrity_failures(
    output_root: Path,
    failure_rows: Sequence[Mapping[str, Any]],
    accounting: Mapping[str, Any],
) -> None:
    """Fail before performance publication while retaining diagnostics."""

    count = int(accounting["executor_integrity_failure_count"])
    if count == 0:
        return
    _publish_integrity_failure_bundle(output_root, failure_rows, accounting)
    raise DiscoveryIntegrityError(
        f"executor_integrity_failures_prevent_publication:{count}"
    )


def _state_map(
    dataset_root: Path,
    sessions: Sequence[CalendarSession],
    symbols: Sequence[str],
    halt_map: Mapping[tuple[str, date], tuple[HaltInterval, ...]],
    actions: Mapping[str, tuple[date, ...]],
) -> dict[tuple[str, date], PartitionState]:
    return {
        (symbol, calendar.session): inspect_partition(
            dataset_root,
            symbol,
            calendar,
            halt_map.get((symbol, calendar.session), ()),
            actions.get(symbol, ()),
        )
        for calendar in sessions
        for symbol in symbols
    }


def _next_bar(
    bars: tuple[MinuteBar, ...], index: int, halts: tuple[HaltInterval, ...]
) -> NextBarOpen | None:
    expected = bars[index].timestamp + timedelta(minutes=1)
    if index + 1 >= len(bars) or bars[index + 1].timestamp != expected:
        return None
    bar = bars[index + 1]
    halted = any(item.start <= bar.timestamp < item.resume for item in halts)
    return NextBarOpen(
        security_id=bar.security_id,
        symbol=bar.symbol,
        session=bar.session,
        timestamp=bar.timestamp,
        open=bar.open,
        halted=halted,
        feed=bar.feed,
        adjustment_identity=bar.adjustment_identity,
        source_manifest_identity=bar.source_manifest_identity,
    )


def _proposal_row(proposal: Any, evidence: Mapping[str, str]) -> dict[str, Any]:
    return {
        **asdict(proposal),
        "indicator_snapshots": json.dumps(
            dict(proposal.indicator_snapshots), sort_keys=True, separators=(",", ":")
        ),
        "discovery_evidence_class": "discovery_empirical_non_authoritative_screen",
        **evidence,
    }


def run_discovery_screen(
    *,
    dataset_root: Path,
    manifest_path: Path,
    evidence_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Run the nine-strategy discovery screen and publish one write-once bundle."""

    output_root = _require_external_discovery_path(output_root)
    if output_root.exists():
        raise DiscoveryIntegrityError("discovery_output_exists")
    manifest = verify_dataset_root(dataset_root, manifest_path)
    calendar_identity, sessions = load_calendar(evidence_root / "calendar_v001.json")
    halt_identity, halt_map = load_halts(evidence_root / "halts_v001/manifest.json")
    action_identity, actions, action_counts = load_action_exclusions(
        evidence_root / "corporate_actions_v001/manifest.json"
    )
    symbols = tuple(manifest["coverage"]["symbols"])
    states = _state_map(dataset_root, sessions, symbols, halt_map, actions)
    calendar_by_date = {item.session: item for item in sessions}
    baseline_dates: dict[str, list[date]] = defaultdict(list)
    volume_history: dict[str, list[tuple[date, dict[str, float], str]]] = defaultdict(list)
    liquidity_history: dict[str, list[LiquidityHistory]] = defaultdict(list)
    proposals_by_strategy: dict[str, list[Any]] = defaultdict(list)
    proposal_rows: list[dict[str, Any]] = []
    decision_counts: Counter[tuple[str, str]] = Counter()
    failure_rows: list[dict[str, Any]] = []
    evaluation_totals: Counter[str] = Counter()
    evaluator_calls: Counter[str] = Counter()
    evidence_ids = {
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "calendar_identity": calendar_identity,
        "halt_manifest_identity": halt_identity,
        "corporate_action_manifest_identity": action_identity,
    }

    for calendar in sessions:
        session_bars: dict[str, tuple[MinuteBar, ...]] = {}
        for symbol in symbols:
            state = states[(symbol, calendar.session)]
            if (
                state.csv_path.is_file()
                and state.complete_or_halt_explained
                and not state.incompatible_halt_minutes
                and not state.action_unresolved
            ):
                session_bars[symbol] = load_minute_bars(state)
        spy = session_bars.get("SPY", ())
        spy_lookup = {item.timestamp: index for index, item in enumerate(spy)}
        for symbol in symbols:
            state = states[(symbol, calendar.session)]
            bars = session_bars.get(symbol)
            features = _session_features(bars) if bars is not None else None
            history_dates = baseline_dates[symbol][-40:]
            for strategy_id in INCLUDED_STRATEGIES:
                reason = _preflight_exclusion_reason(
                    state,
                    strategy_id,
                    states.get(("SPY", calendar.session)),
                    len(history_dates),
                )
                if reason:
                    failure_rows.append({
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "session": calendar.session.isoformat(),
                        "stage": "preflight",
                        "status": "excluded",
                        "reason": reason,
                        "count": 1,
                    })
                    continue
                assert bars is not None
                assert features is not None
                per_session: Counter[tuple[str, str]] = Counter()
                for index, current in enumerate(bars):
                    if not _window(strategy_id, features["minutes"][index]):
                        continue
                    evaluation_totals[strategy_id] += 1
                    spy_prefix: tuple[MinuteBar, ...] = ()
                    if _needs_spy(strategy_id):
                        spy_index = spy_lookup.get(current.timestamp)
                        if spy_index is None:
                            per_session[("unavailable", "SPY_exact_timestamp_missing")] += 1
                            continue
                        spy_prefix = spy[: spy_index + 1]
                    if not _candidate(
                        strategy_id, bars, index, spy_prefix, features
                    ):
                        per_session[("no_signal", "necessary_condition_false")] += 1
                        continue
                    minute = current.timestamp.strftime("%H:%M")
                    same_clock = tuple(
                        HistoricalClockVolume(
                            session=history_date,
                            minute=minute,
                            volume=volumes[minute],
                            eligible=True,
                            adjustment_identity=DATASET_FINGERPRINT,
                            source_manifest_identity=source_identity,
                        )
                        for history_date, volumes, source_identity in volume_history[symbol][-40:]
                        if minute in volumes
                    )
                    if _needs_same_clock(strategy_id):
                        eligible_volumes = [item.volume for item in same_clock[-20:]]
                        if len(eligible_volumes) < 20:
                            per_session[("unavailable", "unavailable_same_clock_history")] += 1
                            continue
                        baseline = statistics.median(eligible_volumes)
                        if baseline <= 0 or current.volume / baseline < 1.5:
                            per_session[("no_signal", "relative_volume_below_threshold")] += 1
                            continue
                    evaluator_calls[strategy_id] += 1
                    known_halts = tuple(
                        item for item in state.halts
                        if item.first_known_at <= current.timestamp + timedelta(minutes=1)
                    )
                    known_spy_halts = tuple(
                        item for item in halt_map.get(("SPY", calendar.session), ())
                        if item.first_known_at <= current.timestamp + timedelta(minutes=1)
                    )
                    value = EvaluationInput(
                        symbol_bars=bars[: index + 1],
                        next_bar=_next_bar(bars, index, known_halts),
                        scheduled_open=calendar.opened,
                        scheduled_close=calendar.closed,
                        decision_cutoff=current.timestamp + timedelta(minutes=1),
                        spy_bars=spy_prefix,
                        same_clock_history=same_clock,
                        liquidity_history=tuple(liquidity_history[symbol][-40:]),
                        halts=known_halts,
                        spy_halts=known_spy_halts,
                        halt_coverage_complete=True,
                        spy_halt_coverage_complete=True,
                        halt_manifest_identity=halt_identity,
                        spy_halt_manifest_identity=halt_identity,
                        corporate_action_coverage_complete=True,
                        corporate_action_lineage_valid=True,
                        corporate_action_manifest_identity=action_identity,
                        calendar_identity=calendar_identity,
                    )
                    result = evaluate(strategy_id, value)
                    reason_code = result.reason_codes[0] if result.reason_codes else ""
                    per_session[(result.status, reason_code)] += 1
                    decision_counts[(strategy_id, result.status)] += 1
                    if result.proposal is not None:
                        proposals_by_strategy[strategy_id].append(result.proposal)
                        proposal_rows.append(_proposal_row(result.proposal, evidence_ids))
                for (status, reason_code), count in sorted(per_session.items()):
                    failure_rows.append({
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "session": calendar.session.isoformat(),
                        "stage": "evaluation",
                        "status": status,
                        "reason": reason_code,
                        "count": count,
                    })
            if bars is not None and not calendar.early_close and not state.halts:
                volumes = {item.timestamp.strftime("%H:%M"): item.volume for item in bars}
                dollar_volume = sum(
                    ((item.high + item.low + item.close) / 3) * item.volume for item in bars
                )
                baseline_dates[symbol].append(calendar.session)
                volume_history[symbol].append((calendar.session, volumes, state.csv_sha256))
                liquidity_history[symbol].append(
                    LiquidityHistory(
                        session=calendar.session,
                        regular_dollar_volume=dollar_volume,
                        complete_session=True,
                        early_close=False,
                        adjustment_identity=DATASET_FINGERPRINT,
                        source_manifest_identity=state.csv_sha256,
                    )
                )

    proposal_counts = {
        key: len(value) for key, value in sorted(proposals_by_strategy.items())
    }
    accounting = evaluation_accounting(
        failure_rows, evaluation_totals, proposal_counts
    )
    enforce_zero_executor_integrity_failures(
        output_root, failure_rows, accounting
    )

    # Only proposal-bearing sessions are reloaded for exit simulation.
    needed = {
        (proposal.symbol, date.fromisoformat(proposal.session))
        for values in proposals_by_strategy.values() for proposal in values
    }
    bars_by_key = {key: load_minute_bars(states[key]) for key in sorted(needed)}
    base_trades: list[CompletedTrade] = []
    rejection_rows: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    classifications: dict[str, str] = {}
    scenario_trades: list[CompletedTrade] = []
    lifecycle_reconciliation: dict[str, Any] = {}
    for strategy_id in INCLUDED_STRATEGIES:
        trades, rejects = simulate_strategy(
            strategy_id,
            proposals_by_strategy[strategy_id],
            bars_by_key,
            calendar_by_date,
        )
        base_trades.extend(trades)
        rejection_rows.extend(rejects)
        projected_15 = [_project_trade(item, 1.5, "cost_1_5x") for item in trades]
        projected_20 = [_project_trade(item, 2.0, "cost_2x") for item in trades]
        scenario_trades.extend(trades + projected_15 + projected_20)
        strategy_metrics = {
            "base": trade_metrics(trades),
            "cost_1_5x": trade_metrics(projected_15),
            "cost_2x": trade_metrics(projected_20),
        }
        metrics[strategy_id] = strategy_metrics
        excluded = sum(
            item["count"] for item in failure_rows
            if item["strategy_id"] == strategy_id and item["stage"] == "preflight"
        )
        material = excluded / (len(symbols) * len(sessions)) > 0.10
        classifications[strategy_id] = classify(
            {"trade_count": len(trades), **strategy_metrics},
            material_data_limitation=material,
        )
        accepted_count = len(trades)
        rejected_count = len(rejects)
        proposal_count = proposal_counts.get(strategy_id, 0)
        if proposal_count != accepted_count + rejected_count:
            raise DiscoveryIntegrityError(
                f"proposal_trade_rejection_reconciliation_failed:{strategy_id}"
            )
        scenario_counts = {
            "base": accepted_count,
            "cost_1_5x": len(projected_15),
            "cost_2x": len(projected_20),
        }
        if len(set(scenario_counts.values())) != 1:
            raise DiscoveryIntegrityError(
                f"cost_scenario_trade_count_mismatch:{strategy_id}"
            )
        lifecycle_reconciliation[strategy_id] = {
            "proposal_count": proposal_count,
            "completed_trade_count": accepted_count,
            "rejected_proposal_count": rejected_count,
            "scenario_trade_counts": scenario_counts,
            "reconciles": True,
        }
    classifications[DEFERRED_STRATEGY] = "INCONCLUSIVE_DATA_LIMITATION"

    output_root.parent.mkdir(parents=True, exist_ok=True)
    publication_root = Path(tempfile.mkdtemp(
        prefix=f".{output_root.name}-", dir=output_root.parent
    ))
    write_csv_exclusive(publication_root / "proposals.csv", proposal_rows)
    write_csv_exclusive(
        publication_root / "failures_and_exclusions.csv", failure_rows
    )
    write_csv_exclusive(
        publication_root / "execution_rejections.csv", rejection_rows
    )
    write_csv_exclusive(
        publication_root / "completed_trades.csv",
        [asdict(item) for item in scenario_trades],
    )
    write_json_exclusive(publication_root / "metrics.json", metrics)
    summary = {
        "schema": "aml.nine-strategy-discovery-screen.v001",
        "evidence_class": "discovery_empirical_non_authoritative_screen",
        "discovery_start": DISCOVERY_START.isoformat(),
        "discovery_end": DISCOVERY_END.isoformat(),
        "later_sessions_accessed": False,
        "v002_protocol_identity": V002_PROTOCOL_IDENTITY,
        **evidence_ids,
        "strategies_executed": list(INCLUDED_STRATEGIES),
        "strategy_deferred": {
            "strategy_id": DEFERRED_STRATEGY,
            "classification": "INCONCLUSIVE_DATA_LIMITATION",
            "missing_inputs": [
                "09:25_through_09:29_ET_premarket_bars",
                "V002_complete_premarket_baselines",
                "independent_official_prior_close",
            ],
        },
        "evaluation_totals": dict(sorted(evaluation_totals.items())),
        "executor_call_totals": dict(sorted(evaluator_calls.items())),
        "proposal_counts": proposal_counts,
        "completed_trade_counts": dict(sorted(Counter(
            item.strategy_id for item in base_trades
        ).items())),
        "executor_integrity_failure_count": int(
            accounting["executor_integrity_failure_count"]
        ),
        "evaluation_accounting": accounting,
        "lifecycle_reconciliation": lifecycle_reconciliation,
        "classifications": dict(sorted(classifications.items())),
        "corporate_action_counts": dict(sorted(action_counts.items())),
        "fixed_universe_survivorship_bias": True,
    }
    summary["identity"] = canonical_hash(summary)
    write_json_exclusive(publication_root / "summary.json", summary)
    final_manifest = artifact_manifest(publication_root, {
        "screen_identity": summary["identity"],
        "dataset_fingerprint": DATASET_FINGERPRINT,
        "halt_manifest_identity": halt_identity,
        "corporate_action_manifest_identity": action_identity,
        "calendar_identity": calendar_identity,
    })
    write_json_exclusive(publication_root / "manifest.json", final_manifest)
    try:
        os.replace(publication_root, output_root)
    except Exception:
        shutil.rmtree(publication_root, ignore_errors=True)
        raise
    return {"summary": summary, "metrics": metrics, "manifest": final_manifest}


def publish_derived_analysis(
    *, screen_root: Path, preflight_summary_path: Path, output_root: Path
) -> dict[str, Any]:
    """Publish deterministic, payload-light summaries from one immutable screen."""

    output_root = _require_external_discovery_path(output_root)
    if output_root.exists():
        raise DiscoveryIntegrityError("analysis_output_exists")
    screen_manifest = _load_json(screen_root / "manifest.json")
    screen_identity = screen_manifest.pop("identity", None)
    if screen_identity != canonical_hash(screen_manifest):
        raise DiscoveryIntegrityError("screen_manifest_identity_mismatch")
    for record in screen_manifest["files"]:
        path = screen_root / record["path"]
        if _sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise DiscoveryIntegrityError("screen_artifact_hash_mismatch")
    summary = _load_json(screen_root / "summary.json")
    summary_payload = dict(summary)
    summary_identity = summary_payload.pop("identity", None)
    if summary_identity != canonical_hash(summary_payload):
        raise DiscoveryIntegrityError("screen_summary_identity_mismatch")
    metrics = _load_json(screen_root / "metrics.json")
    preflight = _load_json(preflight_summary_path)
    preflight_payload = dict(preflight)
    preflight_identity = preflight_payload.pop("identity", None)
    if preflight_identity != canonical_hash(preflight_payload):
        raise DiscoveryIntegrityError("preflight_summary_identity_mismatch")
    proposals = pd.read_csv(screen_root / "proposals.csv")
    trades = pd.read_csv(screen_root / "completed_trades.csv")
    rejections = pd.read_csv(screen_root / "execution_rejections.csv")
    failures = pd.read_csv(screen_root / "failures_and_exclusions.csv")
    base = trades[trades["cost_scenario"] == "base"].copy()
    integrity_failures = failures[
        (failures["stage"] == "evaluation")
        & (failures["status"] == "integrity_failure")
    ]
    integrity_failure_count = int(integrity_failures["count"].sum())
    if summary.get("executor_integrity_failure_count") != integrity_failure_count:
        raise DiscoveryIntegrityError(
            "summary_executor_integrity_failure_count_mismatch"
        )
    if integrity_failure_count:
        raise DiscoveryIntegrityError(
            f"executor_integrity_failures_prevent_analysis:{integrity_failure_count}"
        )

    symbol_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    concentration: dict[str, Any] = {}
    for strategy_id in INCLUDED_STRATEGIES:
        selected = base[base["strategy_id"] == strategy_id].copy()
        if not selected.empty:
            selected["month"] = selected["session"].str[:7]
        for symbol, group in selected.groupby("symbol", sort=True):
            symbol_rows.append({
                "strategy_id": strategy_id,
                "symbol": symbol,
                "trade_count": len(group),
                "net_pnl": float(group["net_pnl"].sum()),
                "wins": int((group["net_pnl"] > 0).sum()),
                "losses": int((group["net_pnl"] < 0).sum()),
            })
        for month, group in selected.groupby("month", sort=True):
            month_rows.append({
                "strategy_id": strategy_id,
                "month": month,
                "trade_count": len(group),
                "net_pnl": float(group["net_pnl"].sum()),
                "wins": int((group["net_pnl"] > 0).sum()),
                "losses": int((group["net_pnl"] < 0).sum()),
            })
        positive = selected[selected["net_pnl"] > 0]
        positive_total = float(positive["net_pnl"].sum())
        by_symbol = selected.groupby("symbol")["net_pnl"].sum() if not selected.empty else pd.Series(dtype=float)
        by_date = selected.groupby("session")["net_pnl"].sum() if not selected.empty else pd.Series(dtype=float)
        concentration[strategy_id] = {
            "positive_pnl_total": positive_total,
            "top_winning_trade": None if positive.empty else float(positive["net_pnl"].max()),
            "top_winning_trade_share_of_positive_pnl": (
                None if positive_total <= 0 else float(positive["net_pnl"].max()) / positive_total
            ),
            "top_symbol": None if by_symbol.empty else str(by_symbol.idxmax()),
            "top_symbol_net_pnl": None if by_symbol.empty else float(by_symbol.max()),
            "top_date": None if by_date.empty else str(by_date.idxmax()),
            "top_date_net_pnl": None if by_date.empty else float(by_date.max()),
        }

    data_quality = {
        "schema": "aml.discovery-data-quality-report.v001",
        "preflight_identity": preflight["identity"],
        "preflight_row_count": preflight["row_count"],
        "included_by_strategy": preflight["included_by_strategy"],
        "excluded_by_strategy_reason": preflight["excluded_by_strategy_reason"],
        "evaluation_integrity_failure_count": integrity_failure_count,
        "fixed_universe_survivorship_bias": True,
        "corporate_action_point_in_time_revision_limitation": True,
    }
    reconciliation: dict[str, Any] = {
        "schema": "aml.discovery-screen-reconciliation.v001",
        "screen_identity": summary["identity"],
        "strategies": {},
    }
    for strategy_id in INCLUDED_STRATEGIES:
        proposal_count = int((proposals["strategy_id"] == strategy_id).sum())
        base_count = int((base["strategy_id"] == strategy_id).sum())
        rejection_count = int((rejections["strategy_id"] == strategy_id).sum())
        if proposal_count != base_count + rejection_count:
            raise DiscoveryIntegrityError("proposal_trade_rejection_reconciliation_failed")
        scenarios = {
            scenario: int(((trades["strategy_id"] == strategy_id) & (trades["cost_scenario"] == scenario)).sum())
            for scenario in ("base", "cost_1_5x", "cost_2x")
        }
        if len(set(scenarios.values())) != 1:
            raise DiscoveryIntegrityError("cost_scenario_trade_count_mismatch")
        reconciliation["strategies"][strategy_id] = {
            "proposal_count": proposal_count,
            "accepted_trade_count": base_count,
            "rejected_proposal_count": rejection_count,
            "reconciles": True,
            "scenario_trade_counts": scenarios,
            "base_net_pnl": float(base[base["strategy_id"] == strategy_id]["net_pnl"].sum()),
        }
    reconciliation["identity"] = canonical_hash(reconciliation)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    publication_root = Path(tempfile.mkdtemp(
        prefix=f".{output_root.name}-", dir=output_root.parent
    ))
    write_csv_exclusive(publication_root / "symbol_breakdown.csv", symbol_rows)
    write_csv_exclusive(publication_root / "monthly_breakdown.csv", month_rows)
    write_json_exclusive(publication_root / "concentration.json", concentration)
    write_json_exclusive(
        publication_root / "data_quality_report.json", data_quality
    )
    write_json_exclusive(publication_root / "reconciliation.json", reconciliation)
    report_lines = [
        "# Nine-Strategy Discovery Screen V001",
        "",
        "Non-authoritative discovery evidence only. This is not validation, a holdout, or trading authorization.",
        "",
        f"Screen identity: `{summary['identity']}`",
        f"Artifact identity: `{screen_identity}`",
        "",
        "## Results",
        "",
        "| Strategy | Trades | Base expectancy | Base PF | 1.5x expectancy | Classification |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for strategy_id in INCLUDED_STRATEGIES:
        item = metrics[strategy_id]
        base_metrics = item["base"]
        stress = item["cost_1_5x"]
        report_lines.append(
            f"| {strategy_id} | {base_metrics['trade_count']} | "
            f"{(base_metrics['net_expectancy'] or 0):.2f} | "
            f"{(base_metrics['profit_factor'] or 0):.3f} | "
            f"{(stress['net_expectancy'] or 0):.2f} | "
            f"{summary['classifications'][strategy_id]} |"
        )
    report_lines.extend([
        f"| {DEFERRED_STRATEGY} | 0 | 0.00 | 0.000 | 0.00 | INCONCLUSIVE_DATA_LIMITATION |",
        "",
        "All strategies are formally inconclusive because material input exclusions exceed the frozen conservative coverage threshold. Eight executed strategies were negative after base costs. First-pullback continuation was positive but had only 14 completed trades and was concentrated in GME, so it does not establish repeatability.",
        "",
        "The fixed 23-symbol universe creates survivorship and selection bias. No later-period data was accessed.",
        "",
    ])
    report_path = publication_root / "DISCOVERY_SCREEN_REPORT.md"
    descriptor = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report_lines))
    analysis_manifest = artifact_manifest(publication_root, {
        "source_screen_identity": summary["identity"],
        "source_artifact_identity": screen_identity,
        "reconciliation_identity": reconciliation["identity"],
    })
    write_json_exclusive(publication_root / "manifest.json", analysis_manifest)
    try:
        os.replace(publication_root, output_root)
    except Exception:
        shutil.rmtree(publication_root, ignore_errors=True)
        raise
    return analysis_manifest


def reconcile_integrity_claims(
    *,
    raw_count: int,
    summary_count: Any,
    data_quality_count: Any,
    metadata_count: Any,
    documentation: str,
) -> None:
    """Require one zero count across raw, derived, metadata, and prose claims."""

    declared_counts = {
        "raw": raw_count,
        "summary": summary_count,
        "data_quality": data_quality_count,
        "metadata": metadata_count,
    }
    if len(set(declared_counts.values())) != 1:
        raise DiscoveryIntegrityError(
            f"published_integrity_failure_count_mismatch:{declared_counts}"
        )
    if raw_count != 0:
        raise DiscoveryIntegrityError(
            f"accepted_publication_has_integrity_failures:{raw_count}"
        )
    expected_claim = (
        f"The corrected accepted screen has `{raw_count}` executor "
        "integrity failures."
    )
    if expected_claim not in documentation:
        raise DiscoveryIntegrityError("documentation_integrity_claim_mismatch")


def verify_published_discovery_claims(
    *,
    screen_root: Path,
    preflight_summary_path: Path,
    analysis_root: Path,
    metadata_path: Path,
    documentation_path: Path,
) -> dict[str, Any]:
    """Reconcile accepted machine and human claims to immutable artifacts."""

    screen_manifest = _load_json(screen_root / "manifest.json")
    screen_artifact_identity = screen_manifest.pop("identity", None)
    if screen_artifact_identity != canonical_hash(screen_manifest):
        raise DiscoveryIntegrityError("screen_manifest_identity_mismatch")
    for record in screen_manifest["files"]:
        path = screen_root / record["path"]
        if _sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise DiscoveryIntegrityError("screen_artifact_hash_mismatch")
    summary = _load_json(screen_root / "summary.json")
    summary_payload = dict(summary)
    screen_identity = summary_payload.pop("identity", None)
    if screen_identity != canonical_hash(summary_payload):
        raise DiscoveryIntegrityError("screen_summary_identity_mismatch")
    preflight = _load_json(preflight_summary_path)
    preflight_payload = dict(preflight)
    preflight_identity = preflight_payload.pop("identity", None)
    if preflight_identity != canonical_hash(preflight_payload):
        raise DiscoveryIntegrityError("preflight_summary_identity_mismatch")
    analysis_manifest = _load_json(analysis_root / "manifest.json")
    analysis_identity = analysis_manifest.pop("identity", None)
    if analysis_identity != canonical_hash(analysis_manifest):
        raise DiscoveryIntegrityError("analysis_manifest_identity_mismatch")
    for record in analysis_manifest["files"]:
        path = analysis_root / record["path"]
        if _sha256(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise DiscoveryIntegrityError("analysis_artifact_hash_mismatch")

    failures = pd.read_csv(screen_root / "failures_and_exclusions.csv")
    integrity_count = int(failures.loc[
        (failures["stage"] == "evaluation")
        & (failures["status"] == "integrity_failure"),
        "count",
    ].sum())
    data_quality = _load_json(analysis_root / "data_quality_report.json")
    metadata = _load_json(metadata_path)
    documentation = documentation_path.read_text(encoding="utf-8")
    reconcile_integrity_claims(
        raw_count=integrity_count,
        summary_count=summary.get("executor_integrity_failure_count"),
        data_quality_count=data_quality.get("evaluation_integrity_failure_count"),
        metadata_count=metadata.get("integrity_failure_count"),
        documentation=documentation,
    )
    identity_claims = {
        "preflight_identity": preflight_identity,
        "screen_identity": screen_identity,
        "screen_artifact_identity": screen_artifact_identity,
        "analysis_artifact_identity": analysis_identity,
    }
    for field, expected in identity_claims.items():
        if metadata.get(field) != expected:
            raise DiscoveryIntegrityError(f"metadata_{field}_mismatch")

    proposals = pd.read_csv(screen_root / "proposals.csv")
    trades = pd.read_csv(screen_root / "completed_trades.csv")
    rejections = pd.read_csv(screen_root / "execution_rejections.csv")
    metrics = _load_json(screen_root / "metrics.json")
    base = trades[trades["cost_scenario"] == "base"]
    if len(proposals) != len(base) + len(rejections):
        raise DiscoveryIntegrityError(
            "proposal_trade_rejection_reconciliation_failed"
        )
    proposal_by_strategy = dict(sorted(
        (str(key), int(value))
        for key, value in proposals.groupby("strategy_id").size().items()
    ))
    rejected_by_strategy = dict(sorted(
        (str(key), int(value))
        for key, value in rejections.groupby("strategy_id").size().items()
    ))
    completed_by_strategy = dict(sorted(
        (str(key), int(value))
        for key, value in base.groupby("strategy_id").size().items()
    ))
    if summary.get("proposal_counts") != proposal_by_strategy:
        raise DiscoveryIntegrityError("summary_proposal_counts_mismatch")
    if summary.get("completed_trade_counts") != completed_by_strategy:
        raise DiscoveryIntegrityError("summary_trade_counts_mismatch")
    if metadata.get("base_completed_trades") != completed_by_strategy:
        raise DiscoveryIntegrityError("metadata_trade_counts_mismatch")
    if metadata.get("classifications") != summary.get("classifications"):
        raise DiscoveryIntegrityError("metadata_classifications_mismatch")

    expected_accounting = evaluation_accounting(
        failures.to_dict("records"),
        summary.get("evaluation_totals", {}),
        proposal_by_strategy,
    )
    if summary.get("evaluation_accounting") != expected_accounting:
        raise DiscoveryIntegrityError("summary_evaluation_accounting_mismatch")

    preflight_exclusions = failures[failures["stage"] == "preflight"]
    grouped_exclusions = dict(sorted(
        (
            f"{strategy_id}|{reason}",
            int(group["count"].sum()),
        )
        for (strategy_id, reason), group in preflight_exclusions.groupby(
            ["strategy_id", "reason"]
        )
    ))
    if preflight.get("excluded_by_strategy_reason") != grouped_exclusions:
        raise DiscoveryIntegrityError("preflight_exclusion_counts_mismatch")
    if data_quality.get("excluded_by_strategy_reason") != grouped_exclusions:
        raise DiscoveryIntegrityError("data_quality_exclusion_counts_mismatch")
    if data_quality.get("included_by_strategy") != preflight.get(
        "included_by_strategy"
    ):
        raise DiscoveryIntegrityError("data_quality_inclusion_counts_mismatch")

    for strategy_id in INCLUDED_STRATEGIES:
        proposal_count = proposal_by_strategy.get(strategy_id, 0)
        completed_count = completed_by_strategy.get(strategy_id, 0)
        rejected_count = rejected_by_strategy.get(strategy_id, 0)
        if proposal_count != completed_count + rejected_count:
            raise DiscoveryIntegrityError(
                f"strategy_lifecycle_reconciliation_failed:{strategy_id}"
            )
        lifecycle = summary.get("lifecycle_reconciliation", {}).get(strategy_id)
        if lifecycle != {
            "proposal_count": proposal_count,
            "completed_trade_count": completed_count,
            "rejected_proposal_count": rejected_count,
            "scenario_trade_counts": {
                scenario: int(len(trades[
                    (trades["strategy_id"] == strategy_id)
                    & (trades["cost_scenario"] == scenario)
                ]))
                for scenario in ("base", "cost_1_5x", "cost_2x")
            },
            "reconciles": True,
        }:
            raise DiscoveryIntegrityError(
                f"summary_lifecycle_reconciliation_mismatch:{strategy_id}"
            )

    metric_fields = (
        "trade_count",
        "gross_pnl",
        "net_pnl",
        "net_expectancy",
        "win_rate",
        "payoff_ratio",
        "profit_factor",
        "maximum_drawdown",
    )
    expected_base_metrics = {
        strategy_id: {
            field: metrics[strategy_id]["base"][field]
            for field in metric_fields
        }
        for strategy_id in INCLUDED_STRATEGIES
    }
    if metadata.get("base_metrics") != expected_base_metrics:
        raise DiscoveryIntegrityError("metadata_base_metrics_mismatch")

    for field, identity in identity_claims.items():
        label = field.replace("_", " ").title()
        if f"- Corrected {label}: `{identity}`" not in documentation:
            raise DiscoveryIntegrityError(
                f"documentation_{field}_mismatch"
            )
    return {
        "schema": "aml.discovery-publication-verification.v001",
        "executor_integrity_failure_count": integrity_count,
        "proposal_count": len(proposals),
        "completed_trade_count": len(base),
        "rejected_proposal_count": len(rejections),
        "preflight_exclusion_count": int(preflight_exclusions["count"].sum()),
        "evaluation_status_counts": expected_accounting["status_counts"],
        "identities": identity_claims,
        "verified": True,
    }
