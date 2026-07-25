import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aml.tournament_config import load_tournament_config
from aml.tournament_strategies import (
    StrategyDefinition, build_strategy, ema_pair, parameter_hash, trailing_indicators,
)


def bars(periods=80):
    timestamps = pd.date_range("2024-01-02 09:30", periods=periods, freq="min", tz="America/New_York")
    close = np.linspace(100, 101, periods)
    return pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "open": close,
        "high": close + 0.1, "low": close - 0.1, "close": close,
        "volume": np.linspace(100, 200, periods), "bar_vwap": close,
    })


def configured():
    return load_tournament_config(
        Path(__file__).parents[1] / "config" / "strategy_tournament_baseline.yaml"
    ).strategies


def test_protocol_parameter_hash_and_strict_parameter_validation():
    strategy = configured()[0]
    assert isinstance(strategy, StrategyDefinition)
    assert parameter_hash({"b": 2, "a": 1}) == parameter_hash({"a": 1, "b": 2})
    with pytest.raises(ValueError, match="unknown"):
        build_strategy("opening_range_breakout", "1", {
            **dict(strategy.parameters), "future_close": True,
        })


def test_indicators_use_trailing_volume_and_known_vwap():
    frame = bars(6)
    frame["volume"] = [10, 20, 30, 40, 50, 600]
    enriched = trailing_indicators(frame, volume_window=5)
    expected_vwap = (frame["bar_vwap"] * frame["volume"]).cumsum() / frame["volume"].cumsum()
    pd.testing.assert_series_equal(enriched["session_vwap"], expected_vwap, check_names=False)
    assert enriched.loc[5, "relative_volume"] == pytest.approx(600 / 30)
    fast, slow = ema_pair(frame, 2, 5)
    pd.testing.assert_series_equal(fast, frame["close"].ewm(span=2, adjust=False).mean())
    pd.testing.assert_series_equal(slow, frame["close"].ewm(span=5, adjust=False).mean())


def test_all_strategies_are_lookahead_invariant_and_signal_next_bar():
    full = bars()
    full.loc[35:, "close"] += 3
    full.loc[35:, "high"] = full.loc[35:, "close"] + 0.1
    prefix = full.iloc[:50].copy()
    cutoff = prefix["timestamp"].iloc[-1] + pd.Timedelta(1, unit="min")
    for strategy in configured():
        complete = [signal for signal in strategy.evaluate(full) if signal.signal_timestamp <= cutoff]
        partial = list(strategy.evaluate(prefix))
        assert complete == partial, strategy.strategy_id
        for signal in partial:
            source = pd.Timestamp(signal.metadata["source_bar_timestamp"])
            assert signal.signal_timestamp == source + pd.Timedelta(1, unit="min")


def test_opening_range_and_volume_breakout_known_signals():
    frame = bars(40)
    frame.loc[:, ["open", "high", "low", "close"]] = [100, 100.1, 99.9, 100]
    frame["volume"] = 100
    frame.loc[20, ["open", "high", "low", "close", "volume"]] = [100, 102.2, 99.9, 102, 1000]
    opening = build_strategy("opening_range_breakout", "1", {
        "opening_range_minutes": 15, "breakout_buffer": 0.001,
        "minimum_relative_volume": 1.5, "signal_cutoff_time": "11:30",
    })
    volume = build_strategy("volume_spike_breakout", "1", {
        "volume_lookback": 10, "volume_multiple": 2.0,
        "price_breakout_lookback": 10, "confirmation_bars": 1,
        "session_cutoff_time": "14:30",
    })
    assert opening.evaluate(frame)[0].metadata["reason_code"] == "opening_range_breakout"
    assert volume.evaluate(frame)[0].metadata["reason_code"] == "volume_spike_breakout"


def test_configuration_rejects_unknown_strategy_parameter(tmp_path):
    source = json.loads((Path(__file__).parents[1] / "config/strategy_tournament_baseline.yaml").read_text())
    source["strategies"][0]["parameters"]["unknown"] = 1
    path = tmp_path / "bad.yaml"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="unknown"):
        load_tournament_config(path)
