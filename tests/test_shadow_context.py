from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aml.portfolio_simulator import (
    Direction,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)
from aml.shadow_context import (
    CONTEXT_SCHEMA_VERSION,
    EventContext,
    EventType,
    PnlClassification,
    SHADOW_STRATEGY_SPECS,
    ShadowOutcomeRecord,
    causal_elapsed_return,
    compute_attention_breadth_context,
    compute_exit_path_diagnostics,
    compute_intraday_confirmation,
    deterministic_competition_context,
    observation_for_signal,
    segregate_shadow_pnl,
)
from aml.tournament_config import load_tournament_config
from aml.tournament_strategies import NormalizedSignal


def _bars(periods=80):
    timestamp = pd.date_range(
        "2025-01-02 09:30", periods=periods, freq="min", tz="America/New_York"
    )
    close = np.full(periods, 100.0)
    volume = np.full(periods, 100.0)
    close[25:] = 104.0
    volume[25] = 1_000.0
    return pd.DataFrame({
        "timestamp": timestamp,
        "symbol": "TEST",
        "open": close,
        "high": close + 0.2,
        "low": close - 0.2,
        "close": close,
        "volume": volume,
        "bar_vwap": close,
    })


def _strategy():
    config = load_tournament_config(
        Path(__file__).parents[1] / "config" / "strategy_tournament_baseline.yaml"
    )
    return next(item for item in config.strategies if item.strategy_id == "attention_momentum")


def _proposal(signal: NormalizedSignal) -> StrategyProposal:
    return StrategyProposal(
        strategy_identifier=signal.strategy_id,
        strategy_version=signal.strategy_version,
        symbol=signal.symbol,
        signal_timestamp=signal.signal_timestamp,
        direction=Direction.LONG,
        score_or_confidence=signal.confidence,
        intended_entry_timestamp=signal.signal_timestamp,
        intended_entry_price=None,
        stop=PriceLevel.fraction(0.015),
        target=PriceLevel.fraction(0.03),
        maximum_holding_minutes=30,
        provenance={"parameter_hash": signal.parameter_hash, "research_only": True},
    )


def _portfolio(proposal: StrategyProposal, bars: pd.DataFrame):
    config = PortfolioConfig(
        total_capital=2_000,
        strategy_allocations=(StrategyAllocation("attention_momentum", "0.1.1", 2_000),),
        maximum_position_risk_fraction=0.005,
        maximum_concurrent_positions=1,
        maximum_symbol_concentration_fraction=1,
        maximum_strategy_concentration_fraction=1,
        daily_loss_limit_fraction=1,
        slippage_fraction=0.001,
    )
    return simulate_portfolio([proposal], {"TEST": bars}, config)


def test_v011_signal_and_trade_behavior_are_identical_after_context_observation():
    bars = _bars()
    strategy = _strategy()
    before = strategy.evaluate(bars)
    assert strategy.strategy_version == "0.1.1"
    assert before
    proposal_before = _proposal(before[0])
    result_before = _portfolio(proposal_before, bars)

    observation = observation_for_signal(
        before[0], proposal_id=proposal_before.proposal_id,
        intraday=compute_intraday_confirmation(bars, before[0].signal_timestamp),
    )
    after = strategy.evaluate(bars)
    proposal_after = _proposal(after[0])
    result_after = _portfolio(proposal_after, bars)

    assert before == after
    assert proposal_before.proposal_id == proposal_after.proposal_id
    assert observation.proposal_id == proposal_before.proposal_id
    pd.testing.assert_frame_equal(result_before.proposal_audit, result_after.proposal_audit)
    pd.testing.assert_frame_equal(result_before.trades, result_after.trades)
    assert result_before.portfolio_summary == result_after.portfolio_summary


def test_market_and_intraday_context_have_no_lookahead():
    bars = _bars()
    decision = bars.loc[30, "timestamp"]
    prefix = bars.loc[bars["timestamp"].lt(decision)].copy()
    changed_future = bars.copy()
    changed_future.loc[changed_future["timestamp"].ge(decision), ["high", "low", "close"]] = 999
    assert causal_elapsed_return(prefix, decision) == causal_elapsed_return(changed_future, decision)
    assert compute_intraday_confirmation(prefix, decision) == compute_intraday_confirmation(
        changed_future, decision
    )


def test_breadth_excludes_future_signals_and_counts_concurrency_deterministically():
    decision = pd.Timestamp("2025-01-02T10:00:00-05:00")
    signals = pd.DataFrame({
        "symbol": ["AAA", "BBB", "CCC", "FUTURE"],
        "signal_timestamp": [
            decision - pd.Timedelta(5, unit="min"), decision, decision,
            decision + pd.Timedelta(1, unit="min"),
        ],
        "direction": ["long", "long", "short", "long"],
        "premarket_dollar_volume": [1_000, 2_000, 3_000, 9_000],
        "gap": [0.01, 0.02, -0.01, 0.50],
    })
    context = compute_attention_breadth_context(
        signals, decision_timestamp=decision, eligible_universe_count=10, direction="long"
    )
    assert context.qualifying_stocks_date_to_decision == 3
    assert context.concurrent_signal_count == 2
    assert context.aggregate_qualifying_premarket_dollar_volume == 6_000
    assert context.maximum_qualifying_gap == 0.02


def test_competition_ranking_is_order_invariant_and_not_a_decision_input():
    strategy = _strategy()
    source = strategy.evaluate(_bars())[0]
    other = NormalizedSignal(
        symbol="AAA",
        signal_timestamp=source.signal_timestamp,
        direction=source.direction,
        confidence=70,
        strategy_id=source.strategy_id,
        strategy_version=source.strategy_version,
        parameter_hash=source.parameter_hash,
        metadata={},
    )
    forward = deterministic_competition_context([source, other])
    reverse = deterministic_competition_context([other, source])
    assert forward == reverse
    assert sorted(value.frozen_order_rank for value in forward.values()) == [1, 2]
    assert all(value.proposals_competing_at_entry == 2 for value in forward.values())


def test_event_provenance_is_point_in_time_and_unknown_is_explicit():
    decision = pd.Timestamp("2025-01-02T10:00:00-05:00")
    unknown = EventContext(decision)
    assert unknown.event_type is EventType.UNKNOWN
    assert unknown.missing_source_reason == "no_valid_decision_time_source"
    with pytest.raises(ValueError, match="after the decision"):
        EventContext(
            decision_timestamp=decision,
            event_type=EventType.EARNINGS_GUIDANCE,
            source_id="wire-1",
            source_uri="https://example.invalid/wire-1",
            source_published_at=decision + pd.Timedelta(1, unit="s"),
            observed_at=decision,
            missing_source_reason=None,
        )
    with pytest.raises(ValueError, match="explicit"):
        EventContext(decision_timestamp=decision, missing_source_reason=None)


def test_exit_diagnostics_stop_at_frozen_holding_boundary():
    bars = _bars(90)
    entry = bars.loc[25, "timestamp"]
    exit_time = entry + pd.Timedelta(5, unit="min")
    first = compute_exit_path_diagnostics(
        bars, entry_timestamp=entry, entry_price=104,
        exit_timestamp=exit_time, exit_reason="stop", maximum_holding_minutes=30,
    )
    changed = bars.copy()
    changed.loc[
        changed["timestamp"].gt(entry + pd.Timedelta(30, unit="min")), "high"
    ] = 10_000
    second = compute_exit_path_diagnostics(
        changed, entry_timestamp=entry, entry_price=104,
        exit_timestamp=exit_time, exit_reason="stop", maximum_holding_minutes=30,
    )
    assert first == second
    assert first.path_end <= entry + pd.Timedelta(30, unit="min")


def test_shadow_pnl_is_zero_capital_and_segregated():
    records = [
        ShadowOutcomeRecord(
            "p1", "rejected_v011", "0.1.1-shadow", PnlClassification.REJECTED_SHADOW,
            5.0, "maximum_concurrent_positions",
        ),
        ShadowOutcomeRecord(
            "p2", "attention_continuation_shadow", "0.1.0-spec",
            PnlClassification.STRATEGY_SHADOW, -2.0, None,
        ),
    ]
    totals = segregate_shadow_pnl(records, deployed_pnl=11.0)
    assert totals == {
        "deployed_portfolio_pnl": 11.0,
        "rejected_shadow_pnl": 5.0,
        "strategy_shadow_pnl": -2.0,
    }
    with pytest.raises(ValueError, match="zero-capital"):
        ShadowOutcomeRecord(
            "p3", "bad", "1", PnlClassification.STRATEGY_SHADOW, 1.0, None,
            capital_allocation=1.0,
        )


def test_exact_context_and_shadow_specification_schema():
    signal = _strategy().evaluate(_bars())[0]
    record = observation_for_signal(signal)
    assert record.schema_version == CONTEXT_SCHEMA_VERSION
    assert set(asdict(record)) == {
        "signal_context_id", "proposal_id", "strategy_id", "strategy_version",
        "symbol", "decision_timestamp", "context_available",
        "missing_context_reasons", "breadth", "cross_sectional", "crowding",
        "intraday", "event", "schema_version",
    }
    assert {spec.strategy_id for spec in SHADOW_STRATEGY_SPECS} == {
        "attention_continuation_shadow", "attention_first_pullback_shadow",
        "failed_attention_reversal_shadow", "broad_event_leader_shadow",
    }
    assert all(spec.capital_allocation == 0 for spec in SHADOW_STRATEGY_SPECS)
