from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from aml.professional_strategy_executor_models_v001 import HaltInterval
from aml.professional_strategy_executor_registry_v001 import execute
from aml.professional_strategy_lifecycle_v001 import ceil_cent, floor_cent
from professional_strategy_synthetic_fixtures import changed, positive_fixture


def test_long_stop_floors_and_target_ceils_to_cent():
    assert floor_cent(10.129) == 10.12
    assert ceil_cent(10.121) == 10.13


def test_entry_friction_is_exactly_ten_basis_points():
    result = execute(
        "five_minute_orb_long_v002",
        positive_fixture("five_minute_orb_long_v002"),
    )
    assert result.proposal.cost_adjusted_entry == result.proposal.raw_entry_open * 1.001
    assert result.proposal.friction_basis_points_per_side == 10


def test_gap_below_stop_rejects_before_entry():
    strategy_id = "five_minute_orb_long_v002"
    value = positive_fixture(strategy_id)
    below_stop = replace(value.next_bar, open=98.0)
    result = execute(strategy_id, changed(value, next_bar=below_stop))
    assert result.status == "no_trade"
    assert result.reason_codes == ("nonpositive_risk",)


def test_frozen_indicator_target_at_or_below_entry_rejects():
    strategy_id = "vwap_mean_reversion_fade_long_v002"
    value = positive_fixture(strategy_id)
    too_high = replace(value.next_bar, open=200.0)
    result = execute(strategy_id, changed(value, next_bar=too_high))
    assert result.status == "no_trade"
    assert result.reason_codes == ("target_not_above_entry",)


def test_timeout_and_cost_metadata_are_contract_only_not_pnl():
    result = execute(
        "fifteen_minute_orb_long_v002",
        positive_fixture("fifteen_minute_orb_long_v002"),
    )
    proposal = result.proposal
    assert proposal.timeout_complete_bars == 120
    assert proposal.risk_budget_usd == 250
    assert proposal.commission_per_share_per_order == 0.005
    assert proposal.initial_capital_usd == 100_000
    assert proposal.maximum_gross_exposure_fraction == 0.5
    assert proposal.maximum_concurrent_positions == 3
    assert proposal.daily_new_entry_loss_stop_fraction == 0.01
    assert proposal.stop_target_precedence.startswith("gap_stop")
    assert "pnl" not in proposal.__dataclass_fields__


def test_early_close_liquidation_boundary_blocks_late_entry():
    strategy_id = "high_of_day_breakout_long_v002"
    value = positive_fixture(strategy_id)
    early_close = value.scheduled_open.replace(hour=10, minute=5)
    result = execute(strategy_id, changed(value, scheduled_close=early_close))
    assert result.status == "no_trade"
    assert result.reason_codes == ("entry_outside_window",)


def test_next_bar_halt_cancels_without_delayed_fill():
    strategy_id = "five_minute_orb_long_v002"
    value = positive_fixture(strategy_id)
    halt = HaltInterval(
        value.next_bar.timestamp,
        value.next_bar.timestamp + timedelta(minutes=5),
        value.next_bar.timestamp,
    )
    next_bar = replace(value.next_bar, halted=True)
    result = execute(strategy_id, changed(value, halts=(halt,), next_bar=next_bar))
    assert result.status == "no_trade"
    assert result.reason_codes == ("halt_before_entry",)
