import pandas as pd
from aml.signals import add_features
from aml.replay import replay_to_frame

def bars():
    t = pd.date_range("2024-01-02 09:30", periods=30, freq="min", tz="America/New_York")
    return pd.DataFrame({
        "timestamp": t, "symbol": ["TEST"] * 30,
        "open": [10 + i*.01 for i in range(30)], "high": [10.05 + i*.01 for i in range(30)],
        "low": [9.95 + i*.01 for i in range(30)], "close": [10 + i*.01 for i in range(30)],
        "volume": [1000 + i*10 for i in range(30)], "bar_vwap": [10 + i*.01 for i in range(30)]
    })

def test_future_rows_do_not_change_past():
    full = add_features(bars())
    cut = add_features(bars().iloc[:20])
    cols = ["return_5m", "relative_volume", "session_vwap", "vwap_distance", "volume_acceleration", "score", "eligible"]
    pd.testing.assert_frame_equal(full.loc[:19, cols].reset_index(drop=True), cut.loc[:19, cols].reset_index(drop=True))

def test_replay_length():
    result = replay_to_frame(bars())
    assert len(result) == 30
    assert result["timestamp"].is_monotonic_increasing
