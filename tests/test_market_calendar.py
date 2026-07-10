from datetime import date
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import pytest

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.market_calendar import (
    CalendarDependencyError, CalendarIdentity, NonTradingSessionError,
    SyntheticMarketCalendar, UnsupportedCalendarError,
)


def adapter(provider_version=None):
    return ExchangeCalendarsAdapter(provider_version=provider_version)


def test_installed_authoritative_version_is_exact():
    assert version("exchange_calendars") == "4.13.2"
    assert adapter().provider_version == "4.13.2"


def test_normal_full_xnys_session_is_timezone_aware_and_left_closed():
    schedule = adapter().schedule(date(2024, 5, 13), "XNYS")
    assert str(schedule.open_timestamp) == "2024-05-13 09:30:00-04:00"
    assert str(schedule.close_timestamp) == "2024-05-13 16:00:00-04:00"
    assert schedule.exchange_timezone == "America/New_York"
    assert schedule.expected_minute_count == 390
    assert schedule.expected_minutes[0] == schedule.open_timestamp
    assert schedule.expected_minutes[-1] == schedule.close_timestamp - pd.Timedelta(1, unit="min")


def test_scheduled_early_close_is_210_minutes():
    schedule = adapter().schedule(date(2024, 7, 3), "XNYS")
    assert str(schedule.close_timestamp) == "2024-07-03 13:00:00-04:00"
    assert schedule.expected_minute_count == 210


@pytest.mark.parametrize("day", [date(2024, 7, 4), date(2024, 7, 6)])
def test_holiday_and_weekend_are_non_trading_sessions(day):
    with pytest.raises(NonTradingSessionError):
        adapter().schedule(day, "XNYS")


@pytest.mark.parametrize("before,after", [
    (date(2024, 3, 8), date(2024, 3, 11)),
    (date(2024, 11, 1), date(2024, 11, 4)),
])
def test_dst_changes_utc_offset_but_not_exchange_local_open(before, after):
    first = adapter().schedule(before, "XNYS")
    second = adapter().schedule(after, "XNYS")
    assert first.open_timestamp.hour == second.open_timestamp.hour == 9
    assert first.open_timestamp.minute == second.open_timestamp.minute == 30
    assert first.open_timestamp.utcoffset() != second.open_timestamp.utcoffset()


def test_calendar_fingerprint_is_canonical_and_version_sensitive():
    identity = adapter().identity({"XNYS"})
    assert identity.normalized_payload() == {
        "provider": "exchange_calendars", "provider_version": "4.13.2",
        "calendar_ids": ["XNYS"],
        "exchange_timezones": {"XNYS": "America/New_York"},
        "minute_side": "left",
    }
    assert identity.fingerprint() == adapter().identity({"XNYS"}).fingerprint()
    changed_version = CalendarIdentity(
        identity.provider, "4.13.3", identity.calendar_ids,
        identity.exchange_timezones, identity.minute_side,
    )
    assert changed_version.fingerprint() != identity.fingerprint()
    changed_identifier = CalendarIdentity(
        identity.provider, identity.provider_version, ("XNAS",),
        (("XNAS", "America/New_York"),), identity.minute_side,
    )
    assert changed_identifier.fingerprint() != identity.fingerprint()
    changed_side = CalendarIdentity(
        identity.provider, identity.provider_version, identity.calendar_ids,
        identity.exchange_timezones, "right",
    )
    assert changed_side.fingerprint() != identity.fingerprint()


def test_unsupported_calendar_and_missing_dependency_fail_without_fallback():
    with pytest.raises(UnsupportedCalendarError):
        adapter().schedule(date(2024, 5, 13), "NOT_A_CALENDAR")
    with pytest.raises(CalendarDependencyError, match="4.13.2"):
        ExchangeCalendarsAdapter(provider_module=None)
    with pytest.raises(CalendarDependencyError, match="found 4.13.3"):
        adapter("4.13.3")


def test_synthetic_calendar_remains_injectable_and_distinct():
    synthetic = SyntheticMarketCalendar()
    assert synthetic.schedule(date(2024, 1, 2), "SYNTHETIC_TEST").expected_minute_count == 390
    assert synthetic.identity({"SYNTHETIC_TEST"}).provider == "synthetic"


def test_only_adapter_imports_exchange_calendars_and_runner_has_no_synthetic_fallback():
    root = Path(__file__).parents[1]
    production = list((root / "src" / "aml").glob("*.py")) + [root / "scripts" / "run_batch_evaluation.py"]
    importers = [path.name for path in production if "import exchange_calendars" in path.read_text()]
    assert importers == ["exchange_calendar_adapter.py"]
    runner = (root / "scripts" / "run_batch_evaluation.py").read_text()
    assert "ExchangeCalendarsAdapter" in runner
    assert "SyntheticMarketCalendar" not in runner
    assert "halt" not in (root / "src" / "aml" / "market_calendar.py").read_text().lower()
