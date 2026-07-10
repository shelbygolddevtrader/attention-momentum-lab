"""Provider-neutral market-calendar interfaces and synthetic test calendar."""

from dataclasses import dataclass
from datetime import date, time
import hashlib
import json
from typing import Protocol
from zoneinfo import ZoneInfo

import pandas as pd


class CalendarError(ValueError):
    """Base error for calendar resolution failures."""


class UnsupportedCalendarError(CalendarError):
    """Raised when a calendar identifier cannot be resolved."""


class NonTradingSessionError(CalendarError):
    """Raised when a date is not a scheduled session."""


class CalendarDependencyError(CalendarError):
    """Raised when the authoritative provider is unavailable."""


@dataclass(frozen=True)
class SessionSchedule:
    calendar_id: str
    trading_date: date
    open_timestamp: pd.Timestamp
    close_timestamp: pd.Timestamp
    expected_minutes: pd.DatetimeIndex
    exchange_timezone: str

    @property
    def expected_minute_count(self):
        return len(self.expected_minutes)


@dataclass(frozen=True)
class CalendarIdentity:
    provider: str
    provider_version: str
    calendar_ids: tuple[str, ...]
    exchange_timezones: tuple[tuple[str, str], ...]
    minute_side: str

    def normalized_payload(self):
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "calendar_ids": sorted(self.calendar_ids),
            "exchange_timezones": dict(sorted(self.exchange_timezones)),
            "minute_side": self.minute_side,
        }

    def fingerprint(self):
        encoded = json.dumps(
            self.normalized_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


class MarketCalendar(Protocol):
    def identity(self, calendar_ids: set[str]) -> CalendarIdentity: ...

    def schedule(self, trading_date: date, calendar_id: str) -> SessionSchedule: ...


class SyntheticMarketCalendar:
    """Explicit calendar for synthetic tests only; never a production fallback."""

    def __init__(
        self,
        calendar_id="SYNTHETIC_TEST",
        early_closes: dict[date, time] | None = None,
        non_trading_dates: set[date] | None = None,
    ):
        self.calendar_id = calendar_id
        self.early_closes = early_closes or {}
        self.non_trading_dates = non_trading_dates or set()
        self.timezone = ZoneInfo("America/New_York")

    def identity(self, calendar_ids):
        if set(calendar_ids) != {self.calendar_id}:
            unknown = sorted(set(calendar_ids).difference({self.calendar_id}))
            raise UnsupportedCalendarError(f"Unsupported synthetic calendars: {unknown}")
        return CalendarIdentity(
            "synthetic", "test-only", (self.calendar_id,),
            ((self.calendar_id, str(self.timezone)),), "left",
        )

    def schedule(self, trading_date, calendar_id):
        self.identity({calendar_id})
        if trading_date.weekday() >= 5 or trading_date in self.non_trading_dates:
            raise NonTradingSessionError(
                f"{calendar_id} has no scheduled session on {trading_date}"
            )
        close_time = self.early_closes.get(trading_date, time(16, 0))
        open_ts = pd.Timestamp.combine(trading_date, time(9, 30)).tz_localize(self.timezone)
        close_ts = pd.Timestamp.combine(trading_date, close_time).tz_localize(self.timezone)
        minutes = pd.date_range(open_ts, close_ts, freq="min", inclusive="left")
        return SessionSchedule(
            calendar_id, trading_date, open_ts, close_ts, minutes, str(self.timezone)
        )
