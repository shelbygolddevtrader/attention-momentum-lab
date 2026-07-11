"""Verified market-halt records and shared minute-completeness semantics."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")


class CompletenessMode(str, Enum):
    STRICT = "strict"
    HALT_AWARE = "halt_aware"


class MinuteClassification(str, Enum):
    EXPECTED_TRADABLE = "tradable_expected"
    VERIFIED_HALT = "verified_halt"
    OUTSIDE_REGULAR_SESSION = "outside_regular_session"


@dataclass(frozen=True)
class HaltRecord:
    symbol: str
    trading_date: date
    halt_timestamp: pd.Timestamp
    resume_quote_timestamp: pd.Timestamp | None
    resume_trade_timestamp: pd.Timestamp
    halt_code: str
    market: str
    source: str

    def __post_init__(self):
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "halt_timestamp", _ny_timestamp(self.halt_timestamp, "halt_timestamp"))
        object.__setattr__(self, "resume_trade_timestamp", _ny_timestamp(self.resume_trade_timestamp, "resume_trade_timestamp"))
        if self.resume_quote_timestamp is not None:
            object.__setattr__(self, "resume_quote_timestamp", _ny_timestamp(self.resume_quote_timestamp, "resume_quote_timestamp"))


@dataclass(frozen=True)
class HaltSchedule:
    symbol: str
    trading_date: date
    records: tuple[HaltRecord, ...] = ()
    source_path: str = ""

    @property
    def full_halt_minutes(self) -> pd.DatetimeIndex:
        minutes = set()
        for record in self.records:
            candidates = pd.date_range(
                record.halt_timestamp.floor("min"),
                record.resume_trade_timestamp.floor("min"), freq="min",
            )
            minutes.update(
                minute for minute in candidates
                if minute >= record.halt_timestamp
                and minute + pd.Timedelta(1, unit="min") <= record.resume_trade_timestamp
            )
        return pd.DatetimeIndex(sorted(minutes))

    def classify_minute(self, minute) -> MinuteClassification:
        minute = _ny_timestamp(minute, "minute")
        clock = minute.hour * 60 + minute.minute
        if minute.date() != self.trading_date or not 570 <= clock <= 959:
            return MinuteClassification.OUTSIDE_REGULAR_SESSION
        if minute in self.full_halt_minutes:
            return MinuteClassification.VERIFIED_HALT
        return MinuteClassification.EXPECTED_TRADABLE


def _ny_timestamp(value, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return timestamp.tz_convert(NY)


def validate_halt_schedule(schedule: HaltSchedule) -> HaltSchedule:
    previous = None
    for record in sorted(schedule.records, key=lambda item: item.halt_timestamp):
        if record.symbol != schedule.symbol or record.trading_date != schedule.trading_date:
            raise ValueError("Halt symbol/date does not match its schedule")
        if record.halt_timestamp.tzinfo is None or record.resume_trade_timestamp.tzinfo is None:
            raise ValueError("Halt timestamps must be timezone-aware")
        if record.halt_timestamp.date() != schedule.trading_date:
            raise ValueError("Halt timestamp does not match trading date")
        if record.resume_trade_timestamp <= record.halt_timestamp:
            raise ValueError("Resume trading time must be after halt time")
        if record.resume_quote_timestamp is not None and record.resume_quote_timestamp.tzinfo is None:
            raise ValueError("Resume quotation timestamp must be timezone-aware")
        if previous is not None and record.halt_timestamp < previous.resume_trade_timestamp:
            raise ValueError("Verified halt records overlap")
        previous = record
    return schedule


def halt_path(symbol: str, trading_date: date | str, root=Path("data/market_halts")) -> Path:
    return Path(root) / symbol.upper() / f"{trading_date}_verified_halts.csv"


def load_verified_halts(symbol: str, trading_date: date | str, root=Path("data/market_halts")) -> HaltSchedule:
    symbol, trading_date = symbol.upper(), date.fromisoformat(str(trading_date))
    path = halt_path(symbol, trading_date, root)
    if not path.exists():
        return HaltSchedule(symbol, trading_date)
    frame = pd.read_csv(path)
    required = {"symbol", "trading_date", "halt_timestamp", "resume_trade_timestamp", "halt_code", "market", "source"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing halt columns: {', '.join(sorted(missing))}")
    records = []
    for row in frame.itertuples(index=False):
        quote = getattr(row, "resume_quote_timestamp", None)
        records.append(HaltRecord(
            str(row.symbol).upper(), date.fromisoformat(str(row.trading_date)),
            _ny_timestamp(row.halt_timestamp, "halt_timestamp"),
            None if quote is None or pd.isna(quote) or quote == "" else _ny_timestamp(quote, "resume_quote_timestamp"),
            _ny_timestamp(row.resume_trade_timestamp, "resume_trade_timestamp"),
            str(row.halt_code), str(row.market), str(row.source),
        ))
    schedule = HaltSchedule(symbol, trading_date, tuple(sorted(records, key=lambda item: item.halt_timestamp)), str(path))
    return validate_halt_schedule(schedule)


def expected_minutes(start, end, mode=CompletenessMode.STRICT, schedule: HaltSchedule | None = None):
    """Expected clock minutes, excluding only fully halted minutes when requested."""
    mode = CompletenessMode(mode)
    expected = pd.date_range(start, end, freq="min")
    if mode is CompletenessMode.HALT_AWARE and schedule is not None:
        return expected.difference(schedule.full_halt_minutes)
    return expected


def completeness_metadata(mode, schedule: HaltSchedule | None, expected=None):
    mode = CompletenessMode(mode)
    full = schedule.full_halt_minutes if schedule is not None else pd.DatetimeIndex([])
    excluded = len(full if expected is None else full.intersection(expected)) if mode is CompletenessMode.HALT_AWARE else 0
    return {
        "completeness_mode": mode.value,
        "verified_halt_count": len(schedule.records) if schedule else 0,
        "verified_halt_minutes_excluded": excluded,
        "halt_data_path": schedule.source_path if schedule else "",
    }
