import pandas as pd
import pytest

from aml.candidate_diagnostics import analyze_candidate_paths, distribution_statistics


def data(highs, lows, closes=None):
    t = pd.date_range("2024-01-02 09:30", periods=len(highs) + 1, freq="min", tz="America/New_York")
    closes = closes or [100] * len(highs)
    return pd.DataFrame({"timestamp": t[1:], "high": highs, "low": lows, "close": closes}), pd.DataFrame({"timestamp": [t[0]], "price": [100.]})


def outcome(highs, lows, target=.01, stop=.01):
    bars, candidates = data(highs, lows)
    _, labels = analyze_candidate_paths(candidates, bars)
    return labels[(labels.horizon_minutes == 5) & (labels.target_fraction == target) & (labels.stop_fraction == stop)].iloc[0]


def test_target_stop_neither_and_ambiguous():
    assert outcome([102] + [100]*4, [99.5]*5)["outcome"] == "target_first"
    assert outcome([100]*5, [98] + [99.5]*4)["outcome"] == "stop_first"
    assert outcome([100.5]*5, [99.5]*5)["outcome"] == "neither"
    assert outcome([102] + [100]*4, [98] + [99]*4)["outcome"] == "ambiguous_same_bar"


def test_incomplete_exact_boundary_and_earliest_times():
    bars, candidates = data([100]*4, [99]*4)
    _, labels = analyze_candidate_paths(candidates, bars)
    assert labels[labels.horizon_minutes.eq(5)].iloc[0]["outcome"] == "insufficient_data"
    bars, candidates = data([101, 102, 101, 100, 100], [99.5]*5)
    paths, labels = analyze_candidate_paths(candidates, bars)
    row = labels[(labels.horizon_minutes.eq(5)) & (labels.target_fraction.eq(.01)) & (labels.stop_fraction.eq(.01))].iloc[0]
    assert row["minutes_to_target"] == 1
    assert paths.iloc[0]["minutes_to_mfe_5m"] == 2


def test_mae_timing_timezone_no_mutation_and_statistics():
    bars, candidates = data([101, 101, 101, 101, 101], [99, 98, 98, 99, 99])
    original = bars.copy(deep=True)
    paths, _ = analyze_candidate_paths(candidates, bars)
    assert paths.iloc[0]["minutes_to_mae_5m"] == 2
    assert paths.timestamp.dt.tz is not None
    pd.testing.assert_frame_equal(bars, original)
    stats, missing = distribution_statistics(pd.DataFrame({"kind":["a","a","b"], "return_5m":[.1, -.1, .2]}), ["kind"], ["return_5m", "mfe_5m"])
    a = stats[stats.kind.eq("a")].iloc[0]
    assert a["median"] == pytest.approx(0)
    assert a["positive_return_rate"] == pytest.approx(.5)
    assert missing == ["mfe_5m"]
