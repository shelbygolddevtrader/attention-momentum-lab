from datetime import date

import pandas as pd
import pytest

from aml.candidate_diagnostics import analyze_candidate_paths
from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.data_paths import artifact_directory
from aml.market_halts import (
    CompletenessMode, HaltRecord, HaltSchedule, MinuteClassification,
    completeness_metadata, load_verified_halts, validate_halt_schedule,
)
from aml.trade_simulator import simulate_trades


NY = "America/New_York"


def ts(value):
    return pd.Timestamp(value, tz=NY)


def record(start="2024-05-14 09:35:46", end="2024-05-14 09:40:46"):
    return HaltRecord(
        "TEST", date(2024, 5, 14), ts(start), None, ts(end),
        "M", "NYSE", "https://example.test/official-halts",
    )


def schedule(*records):
    return validate_halt_schedule(HaltSchedule("TEST", date(2024, 5, 14), tuple(records)))


def replay_frame(include_halt_bars=False):
    times = pd.date_range(ts("2024-05-14 09:35"), ts("2024-05-14 10:05"), freq="min")
    if not include_halt_bars:
        times = times.difference(pd.date_range(ts("2024-05-14 09:36"), ts("2024-05-14 09:39"), freq="min"))
    frame = pd.DataFrame({
        "timestamp": times, "symbol": "TEST", "price": 100.0,
        "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
        "score": 0,
    })
    frame.loc[frame["timestamp"].eq(ts("2024-05-14 09:35")), "score"] = 55
    return frame


def test_partial_halt_boundaries_remain_expected_and_full_minutes_are_excluded():
    halts = schedule(record())
    assert halts.classify_minute(ts("2024-05-14 09:35")) is MinuteClassification.EXPECTED_TRADABLE
    assert halts.full_halt_minutes.tolist() == list(
        pd.date_range(ts("2024-05-14 09:36"), ts("2024-05-14 09:39"), freq="min")
    )
    assert halts.classify_minute(ts("2024-05-14 09:40")) is MinuteClassification.EXPECTED_TRADABLE
    assert halts.classify_minute(ts("2024-05-14 16:00")) is MinuteClassification.OUTSIDE_REGULAR_SESSION


def test_multiple_halts_are_supported():
    second = record("2024-05-14 10:10:00", "2024-05-14 10:12:00")
    halts = schedule(record(), second)
    assert ts("2024-05-14 10:10") in halts.full_halt_minutes
    assert ts("2024-05-14 10:11") in halts.full_halt_minutes
    assert len(halts.records) == 2


def test_candidate_completeness_modes_and_exact_endpoint_return():
    frame = replay_frame()
    halts = schedule(record())
    strict = analyze_candidate_outcomes(frame, completeness_mode="strict", halt_schedule=halts).iloc[0]
    aware = analyze_candidate_outcomes(frame, completeness_mode="halt_aware", halt_schedule=halts).iloc[0]
    assert not strict["complete_5m_window"]
    assert aware["complete_5m_window"]
    assert strict["forward_5m_return"] == pytest.approx(aware["forward_5m_return"])
    assert aware["verified_halt_minutes_excluded_5m"] == 4


def test_halt_aware_does_not_hide_non_halt_missing_minute():
    frame = replay_frame().loc[lambda value: value.timestamp.ne(ts("2024-05-14 09:40"))]
    result = analyze_candidate_outcomes(
        frame, completeness_mode="halt_aware", halt_schedule=schedule(record())
    ).iloc[0]
    assert not result["complete_5m_window"]
    assert pd.isna(result["forward_5m_return"])


def test_candidate_mfe_does_not_use_bar_inside_verified_full_halt_minute():
    frame = replay_frame(include_halt_bars=True)
    frame.loc[frame.timestamp.eq(ts("2024-05-14 09:36")), "high"] = 200.0
    halts = schedule(record())
    strict = analyze_candidate_outcomes(frame, completeness_mode="strict", halt_schedule=halts).iloc[0]
    aware = analyze_candidate_outcomes(frame, completeness_mode="halt_aware", halt_schedule=halts).iloc[0]
    assert strict["mfe_30m"] == pytest.approx(1.0)
    assert aware["mfe_30m"] == pytest.approx(0.005)


def test_target_stop_diagnostics_resume_after_verified_halt():
    candidates = pd.DataFrame({"timestamp": [ts("2024-05-14 09:35")], "price": [100.0]})
    bars = replay_frame().drop(columns=["score", "price"])
    bars.loc[bars.timestamp.eq(ts("2024-05-14 09:40")), "high"] = 102.0
    halts = schedule(record())
    _, strict = analyze_candidate_paths(candidates, bars, "strict", halts)
    _, aware = analyze_candidate_paths(candidates, bars, "halt_aware", halts)

    def selector(frame):
        return frame.loc[
            (frame.horizon_minutes == 5)
            & (frame.target_fraction == .01)
            & (frame.stop_fraction == .01)
        ].iloc[0]

    assert selector(strict).outcome == "insufficient_data"
    result = selector(aware)
    assert result.outcome == "target_first"
    assert result.minutes_to_target == pytest.approx(5)


def test_simulator_changes_only_completeness_classification():
    bars = replay_frame().drop(columns=["score", "price"])
    signals = pd.DataFrame({
        "timestamp": [ts("2024-05-14 09:34")], "symbol": ["TEST"], "score": [70]
    })
    halts = schedule(record())
    strict, _ = simulate_trades(signals, bars, completeness_mode="strict", halt_schedule=halts)
    aware, _ = simulate_trades(signals, bars, completeness_mode="halt_aware", halt_schedule=halts)
    immutable = [
        "actual_entry_timestamp", "raw_entry_price", "adjusted_entry_price",
        "exit_timestamp", "exit_reason", "raw_exit_price", "adjusted_exit_price", "net_pnl",
    ]
    pd.testing.assert_series_equal(strict.iloc[0][immutable], aware.iloc[0][immutable])
    assert not strict.iloc[0].complete_window
    assert aware.iloc[0].complete_window
    assert strict.iloc[0].missing_minute_count == 4
    assert aware.iloc[0].missing_minute_count == 0


def test_missing_halt_file_is_safe_and_infers_nothing(tmp_path):
    halts = load_verified_halts("AAPL", "2024-05-14", tmp_path)
    assert halts.records == ()
    assert halts.full_halt_minutes.empty
    metadata = completeness_metadata(CompletenessMode.HALT_AWARE, halts)
    assert metadata["verified_halt_count"] == 0
    assert metadata["verified_halt_minutes_excluded"] == 0


def test_malformed_and_overlapping_halts_fail_clearly(tmp_path):
    bad = tmp_path / "TEST" / "2024-05-14_verified_halts.csv"
    bad.parent.mkdir()
    bad.write_text(
        "symbol,trading_date,halt_timestamp,resume_trade_timestamp,halt_code,market,source\n"
        "TEST,2024-05-14,2024-05-14T09:40:00-04:00,2024-05-14T09:39:00-04:00,M,NYSE,official\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="after halt"):
        load_verified_halts("TEST", "2024-05-14", tmp_path)
    with pytest.raises(ValueError, match="overlap"):
        schedule(
            record("2024-05-14 09:35:00", "2024-05-14 09:40:00"),
            record("2024-05-14 09:39:00", "2024-05-14 09:45:00"),
        )


def test_halt_records_are_feed_independent_and_artifacts_remain_separate():
    first = load_verified_halts("GME", "2024-05-13")
    second = load_verified_halts("GME", "2024-05-13")
    assert first.records == second.records
    assert artifact_directory("GME", "2024-05-13", "sip") != artifact_directory("GME", "2024-05-13", "iex")
    assert artifact_directory("GME", "2024-05-13", "legacy") != artifact_directory("GME", "2024-05-13", "sip")


def test_verified_gme_records_reproduce_known_full_halt_minute_counts():
    assert len(load_verified_halts("GME", "2024-05-13").full_halt_minutes) == 36
    assert len(load_verified_halts("GME", "2024-05-14").full_halt_minutes) == 66
