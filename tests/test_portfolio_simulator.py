"""Focused tests for the deterministic shared-portfolio foundation."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from aml.portfolio_simulator import (
    Direction,
    DuplicateSignalPolicy,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)
from aml.trade_simulator import SimulationConfig, simulate_trades


START = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")


def bars(
    symbol: str,
    periods: int = 40,
    start: pd.Timestamp = START,
) -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=periods, freq="min")
    return pd.DataFrame({
        "timestamp": timestamps,
        "symbol": symbol,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
    })


def proposal(
    strategy: str,
    symbol: str,
    *,
    minute: int = 0,
    stop: float = 0.03,
    target: float = 0.06,
    direction: Direction = Direction.LONG,
    signal_timestamp: pd.Timestamp | None = None,
    intended_entry_timestamp: pd.Timestamp | None = None,
    stop_level: PriceLevel | None = None,
    target_level: PriceLevel | None = None,
    maximum_holding_minutes: int = 30,
    provenance: dict | None = None,
    invalidation_reason: str | None = None,
) -> StrategyProposal:
    signal = signal_timestamp or START + pd.Timedelta(minute, unit="min")
    intended = intended_entry_timestamp or signal + pd.Timedelta(1, unit="min")
    return StrategyProposal(
        strategy_identifier=strategy,
        strategy_version="1.0.0",
        symbol=symbol,
        signal_timestamp=signal,
        direction=direction,
        score_or_confidence=70.0,
        intended_entry_timestamp=intended,
        intended_entry_price=100.0,
        stop=stop_level or PriceLevel.fraction(stop),
        target=target_level or PriceLevel.fraction(target),
        maximum_holding_minutes=maximum_holding_minutes,
        invalidation_reason=invalidation_reason,
        provenance=provenance or {
            "source": "synthetic_test", "selection_time": signal.isoformat()
        },
    )


def config(
    *strategies: str,
    total: float = 2_000.0,
    allocation: float | None = None,
    **changes,
) -> PortfolioConfig:
    per_strategy = allocation if allocation is not None else total / len(strategies)
    values = {
        "total_capital": total,
        "strategy_allocations": tuple(
            StrategyAllocation(strategy, "1.0.0", per_strategy)
            for strategy in strategies
        ),
        "maximum_position_risk_fraction": 0.005,
        "maximum_concurrent_positions": 5,
        "maximum_symbol_concentration_fraction": 1.0,
        "maximum_strategy_concentration_fraction": 1.0,
        "daily_loss_limit_fraction": 0.05,
        "slippage_fraction": 0.001,
    }
    values.update(changes)
    return PortfolioConfig(**values)


def test_single_strategy_matches_legacy_trade_semantics() -> None:
    frame = bars("TEST")
    frame.loc[2, "high"] = 107.0
    signals = pd.DataFrame({
        "timestamp": [START], "symbol": ["TEST"], "score": [70]
    })
    legacy, _ = simulate_trades(signals, frame, SimulationConfig())
    portfolio = simulate_portfolio(
        [proposal("attention", "TEST")],
        {"TEST": frame},
        config("attention"),
    ).trades
    old, new = legacy.iloc[0], portfolio.iloc[0]
    assert new["actual_entry_timestamp"] == old["actual_entry_timestamp"]
    assert new["exit_timestamp"] == old["exit_timestamp"]
    assert new["exit_reason"] == old["exit_reason"]
    assert new["quantity"] == old["quantity"]
    assert new["adjusted_entry_price"] == pytest.approx(old["adjusted_entry_price"])
    assert new["adjusted_exit_price"] == pytest.approx(old["adjusted_exit_price"])
    assert new["net_pnl"] == pytest.approx(old["net_pnl"])


def test_simultaneous_independent_trades_use_shared_portfolio() -> None:
    result = simulate_portfolio(
        [proposal("alpha", "AAA"), proposal("beta", "BBB")],
        {"AAA": bars("AAA"), "BBB": bars("BBB")},
        config(
            "alpha", "beta",
            maximum_position_risk_fraction=0.05,
            maximum_concurrent_positions=2,
        ),
    )
    assert result.proposal_audit["status"].tolist() == ["accepted", "accepted"]
    assert len(result.trades) == 2


def test_competing_strategies_on_same_symbol_are_audited() -> None:
    proposals = [proposal("zeta", "AAA"), proposal("alpha", "AAA")]
    result = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA")},
        config("alpha", "zeta", duplicate_signal_policy=DuplicateSignalPolicy.REJECT_EXACT),
    )
    audit = result.proposal_audit.set_index("strategy_identifier")
    assert audit.loc["alpha", "status"] == "accepted"
    assert audit.loc["zeta", "reason"] == "duplicate_signal"
    allowed = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA")},
        config(
            "alpha", "zeta",
            duplicate_signal_policy=DuplicateSignalPolicy.ALLOW,
            maximum_concurrent_positions=2,
        ),
    )
    assert allowed.proposal_audit["status"].eq("accepted").all()


def test_insufficient_portfolio_capital_rejects_later_proposal() -> None:
    proposals = [
        proposal("alpha", "AAA", stop=0.75),
        proposal("alpha", "BBB", stop=0.75),
        proposal("alpha", "CCC", stop=0.75),
    ]
    result = simulate_portfolio(
        proposals,
        {symbol: bars(symbol) for symbol in ("AAA", "BBB", "CCC")},
        config(
            "alpha", total=200.0, allocation=200.0,
            maximum_position_risk_fraction=0.5,
            maximum_concurrent_positions=3,
            slippage_fraction=0.0,
        ),
    )
    assert result.proposal_audit["status"].tolist() == ["accepted", "accepted", "rejected"]
    assert result.proposal_audit.iloc[-1]["reason"] == "insufficient_portfolio_capital"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"maximum_symbol_concentration_fraction": 0.05}, "symbol_concentration_limit"),
        ({"maximum_strategy_concentration_fraction": 0.05}, "strategy_concentration_limit"),
    ],
)
def test_concentration_limits_reject_explicitly(changes, reason) -> None:
    result = simulate_portfolio(
        [proposal("alpha", "AAA")],
        {"AAA": bars("AAA")},
        config("alpha", **changes),
    )
    assert result.proposal_audit.iloc[0]["reason"] == reason


def test_proposal_processing_is_deterministic_under_input_reordering() -> None:
    proposals = [proposal("zeta", "AAA"), proposal("alpha", "AAA")]
    market = {"AAA": bars("AAA")}
    settings = config("alpha", "zeta")
    first = simulate_portfolio(proposals, market, settings)
    second = simulate_portfolio(list(reversed(proposals)), market, settings)
    pd.testing.assert_frame_equal(first.proposal_audit, second.proposal_audit)
    pd.testing.assert_frame_equal(first.trades, second.trades)


def test_results_ignore_market_mapping_order_and_inputs_are_not_mutated() -> None:
    proposals = [proposal("alpha", "AAA"), proposal("beta", "BBB")]
    aaa, bbb = bars("AAA"), bars("BBB")
    originals = aaa.copy(deep=True), bbb.copy(deep=True)
    settings = config("alpha", "beta")
    first = simulate_portfolio(proposals, {"AAA": aaa, "BBB": bbb}, settings)
    second = simulate_portfolio(
        list(reversed(proposals)), {"BBB": bbb, "AAA": aaa}, settings
    )
    pd.testing.assert_frame_equal(first.proposal_audit, second.proposal_audit)
    pd.testing.assert_frame_equal(first.trades, second.trades)
    pd.testing.assert_frame_equal(aaa, originals[0])
    pd.testing.assert_frame_equal(bbb, originals[1])


def test_rejected_proposals_retain_explicit_audit_reason() -> None:
    result = simulate_portfolio(
        [proposal("alpha", "AAA", invalidation_reason="stale_source_signal")],
        {"AAA": bars("AAA")},
        config("alpha"),
    )
    audit = result.proposal_audit.iloc[0]
    assert audit["status"] == "rejected"
    assert audit["reason"] == "strategy_invalidated"
    assert audit["invalidation_reason"] == "stale_source_signal"
    assert "synthetic_test" in audit["provenance_json"]
    assert result.trades.empty


def test_daily_loss_limit_blocks_later_entries() -> None:
    losing = bars("AAA")
    losing.loc[2, "low"] = 96.0
    result = simulate_portfolio(
        [proposal("alpha", "AAA"), proposal("beta", "BBB", minute=2)],
        {"AAA": losing, "BBB": bars("BBB")},
        config("alpha", "beta", daily_loss_limit_fraction=0.001),
    )
    beta = result.proposal_audit.set_index("strategy_identifier").loc["beta"]
    assert beta["status"] == "rejected"
    assert beta["reason"] == "daily_loss_limit"


def test_portfolio_pnl_reconciles_to_trades_and_ending_equity() -> None:
    winner = bars("AAA")
    winner.loc[2, "high"] = 107.0
    loser = bars("BBB")
    loser.loc[2, "low"] = 96.0
    result = simulate_portfolio(
        [proposal("alpha", "AAA"), proposal("beta", "BBB")],
        {"AAA": winner, "BBB": loser},
        config("alpha", "beta"),
    )
    net = result.trades["net_pnl"].sum()
    assert result.portfolio_summary["realized_pnl"] == pytest.approx(net)
    assert result.portfolio_summary["ending_equity"] == pytest.approx(2_000.0 + net)
    assert result.portfolio_summary["unrealized_pnl"] == 0.0


def test_strategy_ledgers_reconcile_to_each_strategy_trades() -> None:
    winner = bars("AAA")
    winner.loc[2, "high"] = 107.0
    result = simulate_portfolio(
        [proposal("alpha", "AAA"), proposal("beta", "BBB")],
        {"AAA": winner, "BBB": bars("BBB")},
        config("alpha", "beta"),
    )
    trades = result.trades.groupby(["strategy_identifier", "strategy_version"])["net_pnl"].sum()
    for row in result.strategy_ledgers.itertuples(index=False):
        key = (row.strategy_identifier, row.strategy_version)
        assert row.realized_pnl == pytest.approx(trades.get(key, 0.0))
        assert row.available_capital == pytest.approx(row.allocated_capital + row.realized_pnl)
        assert row.unrealized_pnl == 0.0


def test_exit_at_entry_timestamp_releases_capital_before_admission() -> None:
    first = bars("AAA")
    first.loc[2, "high"] = 111.0
    result = simulate_portfolio(
        [
            proposal("alpha", "AAA", stop=0.5, target=0.1),
            proposal("alpha", "BBB", minute=1, stop=0.5, target=0.1),
        ],
        {"AAA": first, "BBB": bars("BBB")},
        config(
            "alpha", total=100.0, allocation=100.0,
            maximum_position_risk_fraction=0.5,
            maximum_concurrent_positions=1,
            slippage_fraction=0.0,
        ),
    )
    assert result.proposal_audit["status"].tolist() == ["accepted", "accepted"]
    assert result.trades.iloc[0]["exit_timestamp"] == result.trades.iloc[1]["actual_entry_timestamp"]


def test_duplicate_intent_ignores_metadata_and_subminute_signal_difference() -> None:
    first = proposal(
        "alpha", "AAA", provenance={"source": "one"}
    )
    second = proposal(
        "beta", "AAA",
        signal_timestamp=START + pd.Timedelta(30, unit="s"),
        intended_entry_timestamp=START + pd.Timedelta(1, unit="min"),
        provenance={"source": "two", "different": True},
    )
    result = simulate_portfolio(
        [second, first], {"AAA": bars("AAA")}, config("alpha", "beta")
    )
    audit = result.proposal_audit.set_index("strategy_identifier")
    assert first.proposal_id != second.proposal_id
    assert audit.loc["alpha", "status"] == "accepted"
    assert audit.loc["beta", "reason"] == "duplicate_signal"


def test_same_symbol_opposite_directions_have_explicit_policy() -> None:
    proposals = [
        proposal("alpha", "AAA"),
        proposal("beta", "AAA", direction=Direction.SHORT),
    ]
    rejected = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA")},
        config(
            "alpha", "beta",
            duplicate_signal_policy=DuplicateSignalPolicy.REJECT_SAME_SYMBOL,
        ),
    )
    assert rejected.proposal_audit["status"].tolist() == ["accepted", "rejected"]
    assert rejected.proposal_audit.iloc[1]["reason"] == "symbol_conflict"
    allowed = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA")},
        config("alpha", "beta", duplicate_signal_policy=DuplicateSignalPolicy.ALLOW),
    )
    assert allowed.proposal_audit["status"].eq("accepted").all()


def test_same_symbol_direction_policy_catches_nonidentical_intents() -> None:
    proposals = [
        proposal("alpha", "AAA", target=0.06),
        proposal("beta", "AAA", target=0.05),
    ]
    result = simulate_portfolio(
        proposals,
        {"AAA": bars("AAA")},
        config(
            "alpha", "beta",
            duplicate_signal_policy=DuplicateSignalPolicy.REJECT_SAME_SYMBOL_DIRECTION,
        ),
    )
    assert result.proposal_audit["status"].tolist() == ["accepted", "rejected"]
    assert result.proposal_audit.iloc[1]["reason"] == "correlated_signal"


@pytest.mark.parametrize(
    "shared_strategy,expected_reason",
    [(False, "symbol_concentration_limit"), (True, "strategy_concentration_limit")],
)
def test_concentration_uses_current_open_capital_exposure(shared_strategy, expected_reason) -> None:
    strategies = ("alpha",) if shared_strategy else ("alpha", "beta", "gamma")
    proposal_strategies = ("alpha", "alpha", "alpha") if shared_strategy else strategies
    symbols = ("AAA", "BBB", "CCC") if shared_strategy else ("AAA", "AAA", "AAA")
    changes = (
        {"maximum_strategy_concentration_fraction": 0.30}
        if shared_strategy
        else {"maximum_symbol_concentration_fraction": 0.30}
    )
    result = simulate_portfolio(
        [
            proposal(strategy, symbol, stop=0.10, target=target)
            for strategy, symbol, target in zip(
                proposal_strategies, symbols, (0.20, 0.19, 0.18), strict=True
            )
        ],
        {symbol: bars(symbol) for symbol in set(symbols)},
        config(
            *strategies,
            total=1_000.0,
            allocation=1_000.0 if shared_strategy else None,
            maximum_position_risk_fraction=0.02,
            duplicate_signal_policy=DuplicateSignalPolicy.ALLOW,
            slippage_fraction=0.0,
            **changes,
        ),
    )
    assert result.proposal_audit["status"].tolist() == ["accepted", "accepted", "rejected"]
    assert result.proposal_audit.iloc[-1]["reason"] == expected_reason
    assert result.proposal_audit.loc[:1, "capital_used"].sum() == pytest.approx(300.0)


@pytest.mark.parametrize(
    "direction,stop,target",
    [
        (Direction.LONG, 101.0, 110.0),
        (Direction.LONG, 90.0, 99.0),
        (Direction.SHORT, 99.0, 90.0),
        (Direction.SHORT, 110.0, 101.0),
    ],
)
def test_invalid_absolute_stop_target_orientation_is_rejected(direction, stop, target) -> None:
    result = simulate_portfolio(
        [proposal(
            "alpha", "AAA", direction=direction,
            stop_level=PriceLevel.absolute(stop),
            target_level=PriceLevel.absolute(target),
        )],
        {"AAA": bars("AAA")},
        config("alpha", slippage_fraction=0.0),
    )
    assert result.proposal_audit.iloc[0]["reason"] == "invalid_stop_target"
    ledger = result.strategy_ledgers.iloc[0]
    assert ledger["available_capital"] == ledger["allocated_capital"]
    assert ledger["realized_pnl"] == 0


def test_valid_absolute_levels_are_preserved_exactly() -> None:
    result = simulate_portfolio(
        [proposal(
            "alpha", "AAA",
            stop_level=PriceLevel.absolute(97.0),
            target_level=PriceLevel.absolute(106.0),
        )],
        {"AAA": bars("AAA")},
        config("alpha", slippage_fraction=0.0),
    )
    trade = result.trades.iloc[0]
    assert trade["stop_price"] == 97.0
    assert trade["target_price"] == 106.0


@pytest.mark.parametrize("value", [0, -0.1, float("nan"), float("inf"), "bad"])
def test_malformed_price_levels_fail_closed(value) -> None:
    with pytest.raises(ValueError):
        PriceLevel.fraction(value)


def test_malformed_proposals_and_configuration_fail_closed() -> None:
    base = proposal("alpha", "AAA")
    with pytest.raises(ValueError, match="score_or_confidence"):
        replace(base, score_or_confidence=float("nan"))
    with pytest.raises(ValueError, match="timezone-aware"):
        proposal(
            "alpha", "AAA",
            signal_timestamp=pd.Timestamp("2024-01-02 09:30"),
            intended_entry_timestamp=pd.Timestamp("2024-01-02 09:31"),
        )
    with pytest.raises(ValueError, match="allocation"):
        config("alpha", allocation_policy="adaptive")
    with pytest.raises(ValueError, match="total_capital"):
        PortfolioConfig(
            total_capital=float("nan"),
            strategy_allocations=(StrategyAllocation("alpha", "1.0.0", 100.0),),
        )


def test_provenance_is_detached_immutable_and_canonical() -> None:
    source = {"source": "fixture", "nested": {"values": [2, 1]}}
    item = proposal("alpha", "AAA", provenance=source)
    source["source"] = "mutated"
    source["nested"]["values"].append(3)
    assert item.provenance["source"] == "fixture"
    assert item.provenance["nested"]["values"] == (2, 1)
    with pytest.raises(TypeError):
        item.provenance["source"] = "blocked"
    with pytest.raises(ValueError, match="finite"):
        proposal("alpha", "AAA", provenance={"source": "x", "bad": float("nan")})


def test_daily_loss_boundary_combines_strategies_before_same_timestamp_entry() -> None:
    first = bars("AAA")
    second = bars("BBB")
    first.loc[2, "low"] = 95.0
    second.loc[2, "low"] = 95.0
    losses = [
        proposal(
            "alpha", "AAA",
            stop_level=PriceLevel.absolute(95.0),
            target_level=PriceLevel.absolute(110.0),
        ),
        proposal(
            "beta", "BBB",
            stop_level=PriceLevel.absolute(95.0),
            target_level=PriceLevel.absolute(110.0),
        ),
        proposal("gamma", "CCC", minute=1),
    ]
    result = simulate_portfolio(
        losses,
        {"AAA": first, "BBB": second, "CCC": bars("CCC")},
        config(
            "alpha", "beta", "gamma",
            maximum_position_risk_fraction=0.005,
            daily_loss_limit_fraction=0.01,
            slippage_fraction=0.0,
        ),
    )
    gamma = result.proposal_audit.set_index("strategy_identifier").loc["gamma"]
    assert result.trades["net_pnl"].sum() == pytest.approx(-20.0)
    assert gamma["decision_timestamp"] == START + pd.Timedelta(2, unit="min")
    assert gamma["reason"] == "daily_loss_limit"


def test_daily_loss_lockout_resets_on_next_date() -> None:
    losing = bars("AAA")
    losing.loc[2, "low"] = 90.0
    next_start = START + pd.Timedelta(1, unit="day")
    result = simulate_portfolio(
        [
            proposal(
                "alpha", "AAA",
                stop_level=PriceLevel.absolute(90.0),
                target_level=PriceLevel.absolute(110.0),
            ),
            proposal(
                "beta", "BBB",
                signal_timestamp=next_start,
                intended_entry_timestamp=next_start + pd.Timedelta(1, unit="min"),
            ),
        ],
        {"AAA": losing, "BBB": bars("BBB", start=next_start)},
        config(
            "alpha", "beta",
            maximum_position_risk_fraction=0.01,
            daily_loss_limit_fraction=0.01,
            slippage_fraction=0.0,
        ),
    )
    assert result.proposal_audit.set_index("strategy_identifier").loc["beta", "status"] == "accepted"


def test_short_position_risk_pnl_and_ledger_reconcile() -> None:
    frame = bars("AAA")
    frame.loc[2, "low"] = 90.0
    result = simulate_portfolio(
        [proposal("short", "AAA", direction=Direction.SHORT)],
        {"AAA": frame},
        config("short"),
    )
    trade = result.trades.iloc[0]
    ledger = result.strategy_ledgers.iloc[0]
    assert trade["exit_reason"] == "target"
    assert trade["position_risk"] == pytest.approx(
        abs(trade["adjusted_entry_price"] - trade["stop_price"]) * trade["quantity"]
    )
    assert trade["net_pnl"] > 0
    assert ledger["realized_pnl"] == pytest.approx(trade["net_pnl"])
    assert result.portfolio_summary["realized_pnl"] == pytest.approx(trade["net_pnl"])


@pytest.mark.parametrize("direction", [Direction.LONG, Direction.SHORT])
def test_same_bar_stop_and_target_remains_conservative(direction) -> None:
    frame = bars("AAA")
    frame.loc[2, ["low", "high"]] = [90.0, 110.0]
    result = simulate_portfolio(
        [proposal("alpha", "AAA", direction=direction)],
        {"AAA": frame},
        config("alpha"),
    )
    assert result.trades.iloc[0]["exit_reason"] == "stop"


@pytest.mark.parametrize(
    "direction,open_price,extreme,expected",
    [
        (Direction.LONG, 90.0, 90.0, 90.0),
        (Direction.SHORT, 110.0, 110.0, 110.0),
    ],
)
def test_gap_through_stop_uses_adverse_open(direction, open_price, extreme, expected) -> None:
    frame = bars("AAA")
    frame.loc[2, "open"] = open_price
    if direction is Direction.LONG:
        frame.loc[2, "low"] = extreme
    else:
        frame.loc[2, "high"] = extreme
    result = simulate_portfolio(
        [proposal("alpha", "AAA", direction=direction)],
        {"AAA": frame},
        config("alpha", slippage_fraction=0.0),
    )
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "stop"
    assert trade["raw_exit_price"] == expected


@pytest.mark.parametrize(
    "direction,open_price,extreme",
    [
        (Direction.LONG, 110.0, 110.0),
        (Direction.SHORT, 90.0, 90.0),
    ],
)
def test_gap_through_target_fills_at_target_like_legacy(direction, open_price, extreme) -> None:
    frame = bars("AAA")
    frame.loc[2, "open"] = open_price
    if direction is Direction.LONG:
        frame.loc[2, "high"] = extreme
    else:
        frame.loc[2, "low"] = extreme
    result = simulate_portfolio(
        [proposal("alpha", "AAA", direction=direction)],
        {"AAA": frame},
        config("alpha", slippage_fraction=0.0),
    )
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "target"
    assert trade["raw_exit_price"] == pytest.approx(trade["target_price"])


def test_end_of_data_liquidates_at_last_observed_close() -> None:
    frame = bars("AAA", periods=3)
    frame.loc[2, ["high", "close"]] = 101.0
    result = simulate_portfolio(
        [proposal("alpha", "AAA")], {"AAA": frame}, config("alpha")
    )
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "session_end"
    assert trade["exit_timestamp"] == frame.iloc[-1]["timestamp"]
    assert trade["raw_exit_price"] == 101.0


def test_bar_integrity_and_timezone_handling_fail_closed_or_convert() -> None:
    duplicate = pd.concat([bars("AAA").iloc[[0]], bars("AAA")], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": duplicate}, config("alpha"))
    reversed_bars = bars("AAA").iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="chronological"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": reversed_bars}, config("alpha"))
    contaminated = bars("AAA")
    contaminated.loc[0, "symbol"] = "BBB"
    with pytest.raises(ValueError, match="mismatched symbol"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": contaminated}, config("alpha"))
    naive = bars("AAA")
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": naive}, config("alpha"))
    malformed = bars("AAA")
    malformed.loc[0, "high"] = 99.0
    with pytest.raises(ValueError, match="malformed OHLC"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": malformed}, config("alpha"))
    utc = proposal(
        "alpha", "AAA",
        signal_timestamp=START.tz_convert("UTC"),
        intended_entry_timestamp=(START + pd.Timedelta(1, unit="min")).tz_convert("UTC"),
    )
    converted = simulate_portfolio([utc], {"AAA": bars("AAA")}, config("alpha"))
    assert converted.proposal_audit.iloc[0]["status"] == "accepted"


def test_missing_entry_bar_waits_only_within_configured_delay() -> None:
    missing = bars("AAA").drop(index=1).reset_index(drop=True)
    accepted = simulate_portfolio(
        [proposal("alpha", "AAA")], {"AAA": missing}, config("alpha")
    )
    assert accepted.trades.iloc[0]["actual_entry_timestamp"] == START + pd.Timedelta(2, unit="min")
    rejected = simulate_portfolio(
        [proposal("alpha", "AAA")],
        {"AAA": missing},
        config("alpha", maximum_entry_delay_minutes=0),
    )
    assert rejected.proposal_audit.iloc[0]["reason"] == "entry_delay_exceeded"


def test_malformed_container_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="sequence"):
        simulate_portfolio("not-proposals", {"AAA": bars("AAA")}, config("alpha"))
    with pytest.raises(ValueError, match="StrategyProposal"):
        simulate_portfolio(["bad"], {"AAA": bars("AAA")}, config("alpha"))
    with pytest.raises(ValueError, match="DataFrame"):
        simulate_portfolio([proposal("alpha", "AAA")], {"AAA": []}, config("alpha"))


def test_rejections_do_not_change_portfolio_or_strategy_state() -> None:
    result = simulate_portfolio(
        [
            proposal("alpha", "AAA", invalidation_reason="stale"),
            proposal(
                "beta", "BBB",
                stop_level=PriceLevel.absolute(101.0),
                target_level=PriceLevel.absolute(110.0),
            ),
        ],
        {"AAA": bars("AAA"), "BBB": bars("BBB")},
        config("alpha", "beta", slippage_fraction=0.0),
    )
    assert result.trades.empty
    assert result.portfolio_summary["ending_equity"] == 2_000.0
    assert result.portfolio_summary["realized_pnl"] == 0.0
    assert result.strategy_ledgers["realized_pnl"].eq(0).all()
    assert result.strategy_ledgers["available_capital"].eq(1_000.0).all()
