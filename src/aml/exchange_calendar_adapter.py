"""Authoritative exchange_calendars adapter for production batch research."""

from importlib.metadata import PackageNotFoundError, version

import pandas as pd

from aml.market_calendar import (
    CalendarDependencyError, CalendarIdentity, NonTradingSessionError,
    SessionSchedule, UnsupportedCalendarError,
)

try:
    import exchange_calendars as _exchange_calendars
except ImportError:  # pragma: no cover - exercised by injected missing provider
    _exchange_calendars = None

_DEFAULT_PROVIDER = object()


class ExchangeCalendarsAdapter:
    provider = "exchange_calendars"
    required_version = "4.13.2"
    minute_side = "left"

    def __init__(self, provider_module=_DEFAULT_PROVIDER, provider_version=None):
        self._provider = (
            _exchange_calendars
            if provider_module is _DEFAULT_PROVIDER
            else provider_module
        )
        if self._provider is None:
            raise CalendarDependencyError(
                "exchange_calendars==4.13.2 is required for authoritative batch runs"
            )
        if provider_version is None:
            try:
                provider_version = version("exchange_calendars")
            except PackageNotFoundError as exc:
                raise CalendarDependencyError(
                    "Cannot discover installed exchange_calendars version"
                ) from exc
        self.provider_version = provider_version
        if self.provider_version != self.required_version:
            raise CalendarDependencyError(
                f"Authoritative batch runs require exchange_calendars=={self.required_version}; "
                f"found {self.provider_version}"
            )

    def _resolve(self, calendar_id):
        available = set(self._provider.get_calendar_names(include_aliases=False))
        if calendar_id not in available:
            raise UnsupportedCalendarError(
                f"Unsupported authoritative calendar identifier: {calendar_id}"
            )
        try:
            return self._provider.get_calendar(calendar_id, side=self.minute_side)
        except Exception as exc:
            raise UnsupportedCalendarError(
                f"Unable to resolve authoritative calendar {calendar_id}: {exc}"
            ) from exc

    def identity(self, calendar_ids):
        identifiers = tuple(sorted(set(calendar_ids)))
        if not identifiers:
            raise UnsupportedCalendarError("At least one calendar identifier is required")
        timezones = tuple((identifier, str(self._resolve(identifier).tz)) for identifier in identifiers)
        return CalendarIdentity(
            self.provider, self.provider_version, identifiers, timezones, self.minute_side
        )

    def schedule(self, trading_date, calendar_id):
        calendar = self._resolve(calendar_id)
        label = pd.Timestamp(trading_date)
        if not calendar.is_session(label):
            raise NonTradingSessionError(
                f"{calendar_id} has no scheduled session on {trading_date}"
            )
        timezone = str(calendar.tz)
        open_ts = calendar.session_open(label).tz_convert(timezone)
        close_ts = calendar.session_close(label).tz_convert(timezone)
        minutes = calendar.session_minutes(label).tz_convert(timezone)
        if len(minutes) == 0 or minutes[0] != open_ts or minutes[-1] != close_ts - pd.Timedelta(1, unit="min"):
            raise CalendarDependencyError(
                f"Unexpected minute-boundary semantics for {calendar_id} {trading_date}"
            )
        return SessionSchedule(
            calendar_id, trading_date, open_ts, close_ts, minutes, timezone
        )
