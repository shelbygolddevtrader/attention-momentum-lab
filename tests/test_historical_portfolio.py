"""Tests for real historical attention proposals and portfolio parity."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from aml.historical_portfolio import (
    ATTENTION_STRATEGY_IDENTIFIER,
    DEVELOPMENT_EVIDENCE_CLASS,
    HistoricalSessionProvenance,
    assert_legacy_trade_parity,
    attention_proposals_from_replay,
    historical_portfolio_config,
    order_historical_proposals,
)
from aml.market_halts import CompletenessMode, HaltRecord, HaltSchedule
from aml.portfolio_artifacts import (
    PortfolioRunContext,
    RunLabel,
    load_portfolio_run,
    write_portfolio_run,
)
from aml.portfolio_simulator import simulate_portfolio
from aml.trade_simulator import SimulationConfig, simulate_trades


START = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")


def bars(symbol: str = "AAA") -> pd.DataFrame:
    """Create one deterministic regular-session fragment."""

    frame = pd.DataFrame({
        "timestamp": pd.date_range(START, periods=40, freq="min"),
        "symbol": symbol,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 1_000,
    })
    frame.loc[2, "high"] = 107.0
    return frame


def halt_schedule(symbol: str = "AAA") -> HaltSchedule:
    """Create a verified partial-boundary halt with four full halt minutes."""

    record = HaltRecord(
        symbol=symbol,
        trading_date=date(2024, 1, 2),
        halt_timestamp=pd.Timestamp("2024-01-02 09:35:46", tz="America/New_York"),
        resume_quote_timestamp=None,
        resume_trade_timestamp=pd.Timestamp(
            "2024-01-02 09:40:46", tz="America/New_York"
        ),
        halt_code="T1",
        market="NASDAQ",
        source="authoritative_test_fixture",
    )
    return HaltSchedule(
        symbol, date(2024, 1, 2), (record,), "data/market_halts/AAA/test.csv"
    )


def session(symbol: str = "AAA") -> HistoricalSessionProvenance:
    """Build development-only session provenance."""

    return HistoricalSessionProvenance(
        symbol=symbol,
        trading_date=date(2024, 1, 2),
        feed="sip",
        dataset_vintage="fixture-v1",
        session_class="attention_event",
        cohort_id="development_fixture",
        data_source="local_fixture",
        selection_rule="development_only_not_validation",
        input_sha256="a" * 64,
        completeness_mode=CompletenessMode.HALT_AWARE,
        halt_schedule=halt_schedule(symbol),
    )


def replay(symbol: str = "AAA") -> pd.DataFrame:
    """Build point-in-time signal rows including research-only score 55."""

    return pd.DataFrame({
        "timestamp": [START, START + pd.Timedelta(1, unit="min"), START + pd.Timedelta(2, unit="min")],
        "symbol": [symbol] * 3,
        "score": [55, 70, 100],
        "eligible": [False, True, True],
    })


def test_conversion_preserves_threshold_timestamps_version_and_halt_provenance() -> None:
    source = replay()
    original = source.copy(deep=True)
    admitted = {START + pd.Timedelta(1, unit="min")}
    proposals = attention_proposals_from_replay(
        source, session(), admitted_signal_timestamps=admitted
    )
    assert len(proposals) == 2
    assert [item.score_or_confidence for item in proposals] == [70.0, 100.0]
    assert proposals[0].signal_timestamp == START + pd.Timedelta(1, unit="min")
    assert proposals[0].intended_entry_timestamp == START + pd.Timedelta(2, unit="min")
    assert proposals[0].strategy_identifier == ATTENTION_STRATEGY_IDENTIFIER
    assert proposals[0].strategy_version == "0.1.0"
    assert proposals[0].provenance["completeness_mode"] == "halt_aware"
    assert proposals[0].provenance["verified_halt_count"] == 1
    assert proposals[0].provenance["verified_full_halt_minute_count"] == 4
    assert proposals[0].provenance["not_validation_evidence"] is True
    assert proposals[0].invalidation_reason is None
    assert proposals[1].invalidation_reason == "legacy_simulator_admission_suppressed"
    pd.testing.assert_frame_equal(source, original)


def test_cross_session_order_is_deterministic_under_shuffled_inputs() -> None:
    first = attention_proposals_from_replay(
        replay("BBB"), session("BBB"), admitted_signal_timestamps=[]
    )[0]
    next_day = replace(
        first,
        symbol="AAA",
        signal_timestamp=first.signal_timestamp + pd.Timedelta(1, unit="day"),
        intended_entry_timestamp=first.intended_entry_timestamp + pd.Timedelta(1, unit="day"),
    )
    ordered = order_historical_proposals([next_day, first])
    assert ordered == [first, next_day]
    assert order_historical_proposals(list(reversed(ordered))) == ordered


def test_shared_portfolio_preserves_existing_single_trade_execution() -> None:
    config = SimulationConfig()
    frame = bars()
    signals = pd.DataFrame({
        "timestamp": [START], "symbol": ["AAA"], "score": [70], "eligible": [True]
    })
    legacy, _ = simulate_trades(
        signals, frame, config, CompletenessMode.HALT_AWARE, HaltSchedule(
            "AAA", date(2024, 1, 2)
        )
    )
    proposals = attention_proposals_from_replay(
        signals,
        replace(session(), halt_schedule=HaltSchedule("AAA", date(2024, 1, 2))),
        config,
        admitted_signal_timestamps=set(legacy["signal_timestamp"]),
    )
    portfolio = simulate_portfolio(
        proposals, {"AAA": frame}, historical_portfolio_config(config)
    )
    assert_legacy_trade_parity(legacy, portfolio.trades)
    assert portfolio.trades.iloc[0]["net_pnl"] == pytest.approx(
        legacy.iloc[0]["net_pnl"]
    )


def test_development_artifact_label_and_strategy_provenance(
    tmp_path: Path,
) -> None:
    config = SimulationConfig()
    frame = bars()
    signals = pd.DataFrame({
        "timestamp": [START], "symbol": ["AAA"], "score": [70], "eligible": [True]
    })
    proposals = attention_proposals_from_replay(
        signals,
        replace(session(), halt_schedule=HaltSchedule("AAA", date(2024, 1, 2))),
        config,
        admitted_signal_timestamps={START},
    )
    portfolio_config = historical_portfolio_config(config)
    result = simulate_portfolio(proposals, {"AAA": frame}, portfolio_config)
    context = PortfolioRunContext(
        source_commit="a" * 40,
        source_worktree_dirty=False,
        execution_timestamp=pd.Timestamp("2024-01-03T00:00:00Z"),
        run_label=RunLabel.DEVELOPMENT,
        simulator_configuration={"proposal_adapter": "historical_attention_v001"},
        input_hashes={"bars:AAA:2024-01-02:sip": "b" * 64},
        provenance={
            "evidence_class": DEVELOPMENT_EVIDENCE_CLASS,
            "not_validation_evidence": True,
        },
    )
    loaded = load_portfolio_run(write_portfolio_run(
        tmp_path, result, proposals, portfolio_config, context
    ))
    assert loaded.metadata["run_label"] == "development"
    assert loaded.metadata["provenance"]["not_validation_evidence"] is True
    assert loaded.proposals.iloc[0]["strategy_identifier"] == ATTENTION_STRATEGY_IDENTIFIER
