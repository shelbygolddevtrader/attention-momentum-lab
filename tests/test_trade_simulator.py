import pandas as pd
import pytest

from aml.trade_simulator import SimulationConfig, simulate_trades, summarize_trades


def bars(periods=40, drop=()):
    timestamps = pd.date_range("2024-01-02 09:30", periods=periods, freq="min", tz="America/New_York")
    frame = pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "open": 100.0,
        "high": 100.0, "low": 100.0, "close": 100.0,
    })
    return frame.drop(index=list(drop)).reset_index(drop=True)


def signals(minutes=(0,), scores=None):
    scores = scores or [55] * len(minutes)
    return pd.DataFrame({
        "timestamp": [pd.Timestamp("2024-01-02 09:30", tz="America/New_York") + pd.Timedelta(m, unit="min") for m in minutes],
        "symbol": "TEST", "score": scores,
    })


def config(**changes):
    values = SimulationConfig().__dict__ | changes
    return SimulationConfig(**values)


def test_first_qualifying_signal_enters_next_bar():
    trades, _ = simulate_trades(signals((0, 2), (54, 55)), bars())
    assert trades.iloc[0]["signal_score"] == 55
    assert trades.iloc[0]["actual_entry_timestamp"].minute == 33


def test_never_enters_on_signal_bar():
    trades, _ = simulate_trades(signals(), bars())
    assert trades.iloc[0]["actual_entry_timestamp"] > trades.iloc[0]["signal_timestamp"]


def test_signals_during_open_position_are_not_separate_trades():
    trades, _ = simulate_trades(signals((0, 2, 5)), bars(), config(cooldown_minutes=0))
    assert len(trades) == 1


def test_missing_intended_entry_waits_for_next_bar():
    trades, _ = simulate_trades(signals(), bars(drop=(1,)))
    assert trades.iloc[0]["actual_entry_timestamp"].minute == 32
    assert trades.iloc[0]["entry_delay_minutes"] == 2


def test_entry_delay_over_five_minutes_is_rejected():
    trades, _ = simulate_trades(signals(), bars(drop=(1, 2, 3, 4, 5)))
    assert trades.empty


def test_position_size_uses_current_equity_risk():
    trades, _ = simulate_trades(signals(), bars())
    expected = int((2_000 * 0.005) // (100.1 * 0.03))
    assert trades.iloc[0]["quantity"] == expected


def test_position_size_cannot_exceed_available_cash():
    trades, _ = simulate_trades(
        signals(), bars(), config(starting_equity=150, risk_fraction=1.0)
    )
    assert trades.iloc[0]["quantity"] == 1
    assert trades.iloc[0]["capital_used"] <= 150


def test_trade_is_rejected_when_cash_cannot_purchase_one_share():
    trades, _ = simulate_trades(signals(), bars(), config(starting_equity=50))
    assert trades.empty


def test_stop_exit():
    frame = bars()
    frame.loc[2, "low"] = 96
    trades, _ = simulate_trades(signals(), frame)
    assert trades.iloc[0]["exit_reason"] == "stop"


def test_target_exit():
    frame = bars()
    frame.loc[2, "high"] = 107
    trades, _ = simulate_trades(signals(), frame)
    assert trades.iloc[0]["exit_reason"] == "target"


def test_same_bar_stop_and_target_uses_stop_first():
    frame = bars()
    frame.loc[2, ["low", "high"]] = [96, 107]
    trades, _ = simulate_trades(signals(), frame)
    assert trades.iloc[0]["exit_reason"] == "stop"


def test_time_limit_exit():
    trades, _ = simulate_trades(signals(), bars())
    assert trades.iloc[0]["exit_reason"] == "time_limit"
    assert trades.iloc[0]["exit_timestamp"] - trades.iloc[0]["actual_entry_timestamp"] == pd.Timedelta(30, unit="min")


def test_session_end_exit():
    trades, _ = simulate_trades(signals(), bars(periods=10))
    assert trades.iloc[0]["exit_reason"] == "session_end"
    assert trades.iloc[0]["exit_timestamp"] == bars(periods=10).iloc[-1]["timestamp"]


def test_multiple_sessions_are_rejected_to_prevent_overnight_positions():
    frame = bars()
    next_day = frame.iloc[[0]].copy()
    next_day["timestamp"] += pd.Timedelta(1, unit="day")
    with pytest.raises(ValueError, match="one trading session"):
        simulate_trades(signals(), pd.concat([frame, next_day], ignore_index=True))


def test_entry_and_exit_slippage_are_adverse():
    trades, _ = simulate_trades(signals(), bars())
    trade = trades.iloc[0]
    assert trade["adjusted_entry_price"] == pytest.approx(trade["raw_entry_price"] * 1.001)
    assert trade["adjusted_exit_price"] == pytest.approx(trade["raw_exit_price"] * 0.999)
    assert trade["net_pnl"] < trade["gross_pnl"]


def test_cooldown_blocks_reentry_until_thirty_minutes_after_exit():
    frame = bars(periods=80)
    frame.loc[2, "high"] = 107
    trades, _ = simulate_trades(signals((0, 10, 32)), frame)
    assert trades["signal_timestamp"].dt.minute.tolist() == [30, 2]


def test_missing_minutes_are_counted_without_halt_claim():
    trades, _ = simulate_trades(signals(), bars(drop=(5,)))
    assert trades.iloc[0]["missing_minute_count"] == 1
    assert not trades.iloc[0]["complete_window"]
    assert not any("halt" in column for column in trades.columns)


def test_equity_updates_by_net_pnl():
    frame = bars()
    frame.loc[2, "high"] = 107
    trades, summary = simulate_trades(signals(), frame)
    trade = trades.iloc[0]
    assert trade["equity_after_trade"] == pytest.approx(trade["equity_before_trade"] + trade["net_pnl"])
    assert summary["ending_equity"] == pytest.approx(trade["equity_after_trade"])


def test_maximum_drawdown_uses_running_equity_peak():
    trades = pd.DataFrame({"net_pnl": [100, -200, 50], "equity_after_trade": [2100, 1900, 1950]})
    summary = summarize_trades(trades)
    assert summary["maximum_drawdown"] == pytest.approx(1900 / 2100 - 1)


def test_future_bars_after_exit_do_not_change_trade():
    frame = bars()
    frame.loc[2, "high"] = 107
    original, _ = simulate_trades(signals(), frame)
    changed = frame.copy()
    changed.loc[3:, ["open", "high", "low", "close"]] = [500, 600, 400, 500]
    revised, _ = simulate_trades(signals(), changed)
    pd.testing.assert_series_equal(original.iloc[0], revised.iloc[0])
