import pandas as pd
import pytest

from aml.candidate_outcomes import analyze_candidate_outcomes


def replay(prices=None):
    prices = prices or [100.0 + i for i in range(31)]
    timestamps = pd.date_range(
        "2024-01-02 09:30", periods=len(prices), freq="min", tz="America/New_York"
    )
    return pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "price": prices,
        "high": [price + 1 for price in prices],
        "low": [price - 1 for price in prices],
        "score": [55] + [0] * (len(prices) - 1),
    })


def test_forward_returns_use_exact_clock_horizons():
    result = analyze_candidate_outcomes(replay()).iloc[0]
    assert result["forward_5m_return"] == pytest.approx(0.05)
    assert result["forward_15m_return"] == pytest.approx(0.15)
    assert result["forward_30m_return"] == pytest.approx(0.30)


def test_maximum_favorable_excursion_uses_future_highs():
    assert analyze_candidate_outcomes(replay()).iloc[0]["mfe_30m"] == pytest.approx(0.31)


def test_maximum_adverse_excursion_uses_future_lows():
    prices = [100.0, 95.0] + [101.0 + i for i in range(29)]
    assert analyze_candidate_outcomes(replay(prices)).iloc[0]["mae_30m"] == pytest.approx(-0.06)


def test_window_entirely_below_entry_has_zero_mfe():
    prices = [100.0] + [90.0] * 30
    frame = replay(prices)
    frame.loc[1:, "high"] = 99.0
    assert analyze_candidate_outcomes(frame).iloc[0]["mfe_30m"] == 0.0


def test_window_entirely_above_entry_has_zero_mae():
    prices = [100.0] + [110.0] * 30
    frame = replay(prices)
    frame.loc[1:, "low"] = 101.0
    assert analyze_candidate_outcomes(frame).iloc[0]["mae_30m"] == 0.0


def test_mixed_window_has_positive_mfe_and_negative_mae():
    frame = replay([100.0] + [100.0] * 30)
    frame.loc[1, "high"] = 112.0
    frame.loc[2, "low"] = 93.0
    result = analyze_candidate_outcomes(frame).iloc[0]
    assert result["mfe_30m"] == pytest.approx(0.12)
    assert result["mae_30m"] == pytest.approx(-0.07)


def test_missing_target_minute_is_not_replaced_by_later_data():
    result = analyze_candidate_outcomes(replay().drop(index=5).reset_index(drop=True)).iloc[0]
    assert pd.isna(result["forward_5m_return"])
    assert not result["forward_5m_available"]
    assert result["missing_minutes_30m"] == 1
    assert not result["complete_30m_window"]
    assert result["verified_halt_count"] == 0


def test_insufficient_future_data_is_explicit():
    result = analyze_candidate_outcomes(replay()[:10]).iloc[0]
    assert pd.isna(result["forward_15m_return"])
    assert pd.isna(result["forward_30m_return"])
    assert result["observed_minutes_30m"] == 9
    assert result["missing_minutes_30m"] == 21


def test_all_candidates_at_or_above_threshold_are_included():
    frame = replay()
    frame.loc[1, "score"] = 54
    frame.loc[2, "score"] = 55
    frame.loc[3, "score"] = 100
    assert analyze_candidate_outcomes(frame)["score"].tolist() == [55, 55, 100]


def test_candidate_threshold_boundaries_include_research_only_scores():
    frame = replay()
    frame.loc[:3, "score"] = [54, 55, 69, 70]
    assert analyze_candidate_outcomes(frame)["score"].tolist() == [55, 69, 70]


def test_non_chronological_input_is_rejected():
    frame = replay()
    frame.iloc[[1, 2]] = frame.iloc[[2, 1]].to_numpy()
    with pytest.raises(ValueError, match="chronological"):
        analyze_candidate_outcomes(frame)


def test_appending_future_rows_does_not_change_known_returns():
    full = analyze_candidate_outcomes(replay()).iloc[0]
    cut = analyze_candidate_outcomes(replay()[:16]).iloc[0]
    assert cut["forward_5m_return"] == full["forward_5m_return"]
    assert cut["forward_15m_return"] == full["forward_15m_return"]
