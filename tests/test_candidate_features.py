import numpy as np
import pandas as pd
import pytest

from aml.candidate_features import calculate_candidate_features


def frame(periods=21, signals=(0,)):
    timestamps = pd.date_range("2024-01-02 09:30", periods=periods, freq="min", tz="America/New_York")
    close = np.arange(100.0, 100.0 + periods)
    return pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "price": close, "open": close - .5,
        "high": close + 1, "low": close - 1, "close": close, "volume": np.arange(10, 10 + periods),
        "score": [55 if i in signals else 0 for i in range(periods)],
    })


def test_session_boundaries_and_timezone_are_preserved():
    data = frame(1, (0,))
    extra = data.copy()
    extra["timestamp"] = pd.DatetimeIndex(["2024-01-02 09:34"], tz="America/New_York")
    result = calculate_candidate_features(pd.concat([data, extra], ignore_index=True))
    assert result["session_phase"].tolist() == ["opening_auction", "opening_auction"]
    assert result["timestamp"].dt.tz is not None


def test_signal_counts_and_episode_gap_rules():
    data = frame(17, (0, 5, 15, 16))
    result = calculate_candidate_features(data)
    assert result["signal_ordinal_today"].tolist() == [1, 2, 3, 4]
    assert result["minutes_since_previous_signal"].tolist()[1:] == [5.0, 10.0, 1.0]
    assert result["episode_id"].tolist() == [1, 1, 1, 1]
    assert result["signals_last_5m"].tolist() == [1, 2, 1, 2]
    later = frame(17, (0, 11))
    assert calculate_candidate_features(later)["episode_id"].tolist() == [1, 2]


def test_exact_clock_returns_and_missing_minutes_are_nan():
    data = frame(7, (5,)).drop(index=2).reset_index(drop=True)
    result = calculate_candidate_features(data).iloc[0]
    assert result["return_5m"] == pytest.approx(0.05)
    assert pd.isna(result["return_3m"])


def test_session_extrema_and_vwap_have_no_lookahead():
    data = frame(4, (1,))
    data.loc[:, ["high", "low", "close", "price"]] = [[101, 99, 100, 100], [102, 100, 101, 101], [150, 90, 102, 102], [103, 101, 102, 102]]
    result = calculate_candidate_features(data).iloc[0]
    assert result["distance_from_session_high"] == pytest.approx(101 / 102 - 1)
    expected_vwap = ((100 * 10) + (101 * 11)) / 21
    assert result["vwap"] == pytest.approx(expected_vwap)
    assert result["bars_since_session_low"] == 1


def test_vwap_consecutive_volume_and_candle_safety():
    data = frame(7, (5, 6))
    data.loc[:, "volume"] = [10, 20, 30, 40, 50, 60, 0]
    data.loc[6, ["high", "low"]] = [106, 106]
    result = calculate_candidate_features(data)
    row = result.iloc[0]
    assert row["minutes_above_vwap"] == 5
    assert row["volume_vs_trailing_5m_mean"] == pytest.approx(60 / 30)
    assert row["volume_acceleration_3m"] == pytest.approx(60 / 30 - 1)
    assert pd.isna(result.iloc[1]["body_to_range_ratio"])
    assert result.iloc[1]["volume_acceleration_3m"] == pytest.approx(-1.0)


def test_no_mutation_and_future_signals_do_not_change_earlier_features():
    data = frame(8, (2,))
    original = data.copy(deep=True)
    before = calculate_candidate_features(data)
    later = data.copy()
    later.loc[7, "score"] = 55
    after = calculate_candidate_features(later).iloc[0]
    pd.testing.assert_frame_equal(data, original)
    pd.testing.assert_series_equal(before.iloc[0], after, check_names=False)
