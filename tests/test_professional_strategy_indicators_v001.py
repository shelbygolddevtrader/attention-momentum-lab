from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from aml.professional_strategy_executor_models_v001 import ExecutorIntegrityError
from aml.professional_strategy_indicators_v001 import (
    atr20_series,
    exact_elapsed_return,
    local_five_volume_ratio,
    historical_liquidity,
    premarket_volume_ratio,
    premarket_vwap,
    prior_volume_ratio,
    regular_vwap_series,
    rsi14_series,
    same_clock_volume_ratio,
    validate_evaluation_input,
)
from professional_strategy_synthetic_fixtures import (
    changed,
    histories,
    make_bars,
    make_input,
)


def test_atr20_seed_and_wilder_recurrence_are_exact():
    bars = make_bars("09:50")
    values = atr20_series(bars)
    assert values[18] is None
    assert values[19] == pytest.approx(2.0)
    widened = bars[:-1] + (replace(bars[-1], high=102.0, low=98.0),)
    assert atr20_series(widened)[-1] == pytest.approx((19 * 2 + 4) / 20)


def test_atr_resets_after_a_timestamp_gap():
    bars = make_bars("10:00")
    gappy = bars[:20] + bars[21:]
    assert atr20_series(gappy)[-1] is None


@pytest.mark.parametrize(("direction", "expected"), [(1, 100.0), (-1, 0.0)])
def test_rsi_zero_loss_and_zero_gain_rules(direction, expected):
    closes = [100.0 + direction * index for index in range(16)]
    assert rsi14_series(make_bars("09:45", closes=closes))[-1] == expected


def test_rsi_both_zero_is_fifty():
    assert rsi14_series(make_bars("09:45", closes=[100.0] * 16))[-1] == 50.0


def test_regular_vwap_uses_hlc3_and_zero_volume_does_not_move_sums():
    bars = make_bars("09:31")
    zero = replace(bars[1], high=200, low=50, close=100, volume=0)
    assert regular_vwap_series((bars[0], zero))[-1] == pytest.approx(100.0)


def test_premarket_vwap_is_separate_hlc3_calculation():
    bars = make_bars("09:31")
    assert premarket_vwap(bars) == pytest.approx(100.0)


def test_twenty_bar_volume_ratio_excludes_current_bar():
    bars = make_bars("09:50", modifications={"09:50": {"volume": 200.0}})
    assert prior_volume_ratio(bars, 20) == 2.0


def test_local_five_volume_ratio_uses_twenty_before_five_window():
    changes = {
        clock: {"volume": 200.0}
        for clock in ("09:50", "09:51", "09:52", "09:53", "09:54")
    }
    bars = make_bars("09:54", modifications=changes)
    assert local_five_volume_ratio(bars, 24) == 2.0


def test_same_clock_history_requires_all_twenty_sessions():
    bars = make_bars()
    history, _, _ = histories()
    assert same_clock_volume_ratio(bars[-1], history) == 1.0
    assert same_clock_volume_ratio(bars[-1], history[:-1]) is None


def test_history_search_cap_is_forty_sessions_before_eligibility_filter():
    bars = make_bars()
    clock, liquidity, premarket = histories()
    ineligible_clock = tuple(replace(item, eligible=False) for item in clock)
    ineligible_liquidity = tuple(
        replace(item, complete_session=False) for item in liquidity
    )
    ineligible_premarket = tuple(replace(item, complete=False) for item in premarket)
    assert same_clock_volume_ratio(bars[-1], ineligible_clock) is None
    assert historical_liquidity(ineligible_liquidity, bars[-1].session) is None
    assert premarket_volume_ratio(1.0, ineligible_premarket, bars[-1].session) is None


def test_exact_elapsed_return_never_substitutes_row_offsets():
    bars = make_bars()
    assert exact_elapsed_return(bars, 30, 15) == 0.0
    missing_endpoint = bars[:15] + bars[16:]
    assert exact_elapsed_return(missing_endpoint, 29, 15) is None


def test_unclassified_gap_is_integrity_failure():
    value = make_input(make_bars())
    with pytest.raises(ExecutorIntegrityError, match="unclassified_minute_gap"):
        validate_evaluation_input(changed(value, symbol_bars=value.symbol_bars[:10] + value.symbol_bars[11:]))


def test_future_or_incomplete_bar_is_integrity_failure():
    value = make_input(make_bars())
    future = replace(
        value.symbol_bars[-1],
        timestamp=value.decision_cutoff,
    )
    with pytest.raises(ExecutorIntegrityError, match="incomplete_or_future_bar"):
        validate_evaluation_input(changed(value, symbol_bars=value.symbol_bars + (future,)))


def test_fixed_offset_timezone_is_rejected_without_implicit_conversion():
    value = make_input(make_bars())
    naive_cutoff = value.decision_cutoff.replace(tzinfo=None)
    with pytest.raises(ExecutorIntegrityError, match="timezone_missing"):
        validate_evaluation_input(changed(value, decision_cutoff=naive_cutoff))


def test_next_bar_must_be_exact_and_exposes_open_only():
    value = make_input(make_bars())
    assert set(value.next_bar.__dataclass_fields__) == {
        "security_id", "symbol", "session", "timestamp", "open", "halted",
        "feed", "adjustment_identity", "source_manifest_identity",
    }
    delayed = replace(value.next_bar, timestamp=value.next_bar.timestamp + timedelta(minutes=1))
    with pytest.raises(ExecutorIntegrityError, match="not_exact_signal_timestamp"):
        validate_evaluation_input(changed(value, next_bar=delayed))


def test_nonfinite_supplemental_history_is_integrity_failure():
    value = make_input(make_bars())
    broken = (replace(value.liquidity_history[0], regular_dollar_volume=float("nan")),) + value.liquidity_history[1:]
    with pytest.raises(ExecutorIntegrityError, match="nonfinite"):
        validate_evaluation_input(changed(value, liquidity_history=broken))


def test_duplicate_history_session_cannot_supply_twenty_observations():
    value = make_input(make_bars())
    duplicate = (value.same_clock_history[0],) + value.same_clock_history
    with pytest.raises(ExecutorIntegrityError, match="duplicate_session_minute"):
        validate_evaluation_input(changed(value, same_clock_history=duplicate))
