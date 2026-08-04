from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import aml.discovery_screen_v001 as discovery
from aml.professional_strategy_executor_models_v001 import MinuteBar


NY = ZoneInfo("America/New_York")
SESSION = date(2024, 1, 3)


def _bar(minute: int, *, close: float = 10.0, low: float | None = None, high: float | None = None) -> MinuteBar:
    timestamp = datetime(2024, 1, 3, 9, 30, tzinfo=NY) + timedelta(minutes=minute)
    return MinuteBar(
        security_id="TEST",
        symbol="TEST",
        session=SESSION,
        timestamp=timestamp,
        open=close,
        high=close + 0.1 if high is None else high,
        low=close - 0.1 if low is None else low,
        close=close,
        volume=1_000 + minute,
        adjustment_identity="dataset",
        source_manifest_identity="partition",
    )


def _trade(pnl: float, symbol: str = "TEST") -> discovery.CompletedTrade:
    return discovery.CompletedTrade(
        strategy_id="first_pullback_continuation_long_v002",
        strategy_identity="identity",
        proposal_identity=f"proposal-{pnl}",
        symbol=symbol,
        session=SESSION.isoformat(),
        signal_timestamp="2024-01-03T09:30:00-05:00",
        entry_timestamp="2024-01-03T09:31:00-05:00",
        exit_timestamp="2024-01-03T09:32:00-05:00",
        raw_entry=10,
        raw_exit=10,
        stop=9,
        target=12,
        quantity=1,
        exit_reason="timeout",
        gross_pnl=pnl + 2,
        entry_commission=1,
        exit_commission=1,
        net_pnl=pnl,
        net_r_multiple=pnl / 250,
    )


def test_no_lookahead_in_session_feature_cache() -> None:
    bars = tuple(_bar(index, close=10 + index * 0.01) for index in range(40))
    changed = bars[:-1] + (replace(bars[-1], close=999, high=999),)
    first = discovery._session_features(bars)
    second = discovery._session_features(changed)
    for key in ("atr20", "vwap", "return15", "return20", "mature_hod", "mature_low"):
        assert first[key][:-1] == second[key][:-1]


def test_halt_partial_resume_bar_is_removed() -> None:
    halt = discovery.HaltInterval(
        start=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
        resume=datetime(2024, 1, 3, 9, 40, 46, tzinfo=NY),
        first_known_at=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
    )
    assert discovery._minute_overlaps_halt(_bar(5).timestamp, halt)
    assert discovery._minute_overlaps_halt(_bar(10).timestamp, halt)
    assert not discovery._minute_overlaps_halt(_bar(11).timestamp, halt)


def test_bar_loader_removes_every_minute_that_overlaps_a_halt(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "regular_1min.csv"
    csv_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2024-01-03T09:35:00-05:00,10,10.1,9.9,10,1000\n"
        "2024-01-03T09:40:00-05:00,10,10.1,9.9,10,1000\n"
        "2024-01-03T09:41:00-05:00,10,10.1,9.9,10,1000\n",
        encoding="utf-8",
    )
    halt = discovery.HaltInterval(
        start=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
        resume=datetime(2024, 1, 3, 9, 40, 46, tzinfo=NY),
        first_known_at=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
    )
    state = discovery.PartitionState(
        "TEST", SESSION, csv_path, "partition", 3, 390, 387,
        True, (), True, (halt,), (), False,
    )
    bars = discovery.load_minute_bars(state)
    assert [bar.timestamp.strftime("%H:%M") for bar in bars] == ["09:41"]


@pytest.mark.parametrize(
    ("start", "resume", "overlap_minutes"),
    [
        ("09:35:00", "09:40:00", ("09:35", "09:36", "09:37", "09:38", "09:39")),
        ("09:35:46", "09:40:00", ("09:35", "09:36", "09:37", "09:38", "09:39")),
        ("09:35:00", "09:40:46", ("09:35", "09:36", "09:37", "09:38", "09:39", "09:40")),
        ("09:35:46", "09:40:46", ("09:35", "09:36", "09:37", "09:38", "09:39", "09:40")),
    ],
)
def test_canonical_half_open_halt_overlap_boundaries(
    start: str, resume: str, overlap_minutes: tuple[str, ...]
) -> None:
    def timestamp(clock: str) -> datetime:
        hour, minute, second = (int(item) for item in clock.split(":"))
        return datetime(2024, 1, 3, hour, minute, second, tzinfo=NY)

    halt = discovery.HaltInterval(
        start=timestamp(start),
        resume=timestamp(resume),
        first_known_at=timestamp(start),
    )
    observed = tuple(
        f"09:{minute:02d}"
        for minute in range(34, 42)
        if discovery._minute_overlaps_halt(
            datetime(2024, 1, 3, 9, minute, tzinfo=NY), halt
        )
    )
    assert observed == overlap_minutes


def test_partial_minute_halt_start_is_explicitly_incompatible() -> None:
    halt = discovery.HaltInterval(
        start=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
        resume=datetime(2024, 1, 3, 9, 40, 46, tzinfo=NY),
        first_known_at=datetime(2024, 1, 3, 9, 35, 46, tzinfo=NY),
    )
    incompatible = discovery._incompatible_halt_minutes(
        datetime(2024, 1, 3, 9, 30, tzinfo=NY),
        datetime(2024, 1, 3, 16, 0, tzinfo=NY),
        (halt,),
    )
    assert incompatible == ("2024-01-03T09:35:00-05:00",)


@pytest.mark.parametrize(
    ("symbol", "start", "resume", "expected_minute"),
    [
        ("GME", "2024-05-13T09:35:46-04:00", "2024-05-13T09:40:46-04:00", "2024-05-13T09:35:00-04:00"),
        ("AMC", "2024-05-14T09:31:49-04:00", "2024-05-14T09:36:54-04:00", "2024-05-14T09:31:00-04:00"),
    ],
)
def test_known_amc_gme_partial_halt_patterns_are_excluded(
    symbol: str, start: str, resume: str, expected_minute: str
) -> None:
    started = datetime.fromisoformat(start).astimezone(NY)
    halt = discovery.HaltInterval(
        start=started,
        resume=datetime.fromisoformat(resume).astimezone(NY),
        first_known_at=started,
        source_record_identity=f"synthetic-{symbol}",
    )
    opened = started.replace(hour=9, minute=30, second=0, microsecond=0)
    closed = opened.replace(hour=16)
    assert expected_minute in discovery._incompatible_halt_minutes(
        opened, closed, (halt,)
    )


def test_exact_minute_start_and_intraminute_resume_are_compatible() -> None:
    halt = discovery.HaltInterval(
        start=datetime(2024, 1, 3, 9, 35, tzinfo=NY),
        resume=datetime(2024, 1, 3, 9, 40, 46, tzinfo=NY),
        first_known_at=datetime(2024, 1, 3, 9, 35, tzinfo=NY),
    )
    assert discovery._incompatible_halt_minutes(
        datetime(2024, 1, 3, 9, 30, tzinfo=NY),
        datetime(2024, 1, 3, 16, 0, tzinfo=NY),
        (halt,),
    ) == ()


def test_adjacent_halts_and_session_boundaries_use_same_interval_rule() -> None:
    opened = datetime(2024, 1, 3, 9, 30, tzinfo=NY)
    closed = datetime(2024, 1, 3, 9, 35, tzinfo=NY)
    first = discovery.HaltInterval(
        start=opened - timedelta(seconds=15),
        resume=opened + timedelta(minutes=2, seconds=30),
        first_known_at=opened - timedelta(seconds=15),
    )
    adjacent = discovery.HaltInterval(
        start=first.resume,
        resume=closed + timedelta(seconds=15),
        first_known_at=first.resume,
    )
    assert discovery._incompatible_halt_minutes(
        opened, closed, (first, adjacent)
    ) == ()
    assert discovery._minute_overlaps_halt(closed - timedelta(minutes=1), adjacent)


def test_adjacent_nonoverlapping_missing_minute_remains_unexplained() -> None:
    halt = discovery.HaltInterval(
        start=datetime(2024, 1, 3, 9, 35, tzinfo=NY),
        resume=datetime(2024, 1, 3, 9, 36, tzinfo=NY),
        first_known_at=datetime(2024, 1, 3, 9, 35, tzinfo=NY),
    )
    assert not discovery._minute_overlaps_halt(
        datetime(2024, 1, 3, 9, 34, tzinfo=NY), halt
    )
    assert not discovery._minute_overlaps_halt(
        datetime(2024, 1, 3, 9, 36, tzinfo=NY), halt
    )


def test_partial_open_minute_is_excluded_before_frozen_segment_validation(
    tmp_path: Path,
) -> None:
    opened = datetime(2024, 1, 3, 9, 30, tzinfo=NY)
    halt = discovery.HaltInterval(
        start=opened + timedelta(seconds=20),
        resume=opened + timedelta(minutes=1, seconds=20),
        first_known_at=opened + timedelta(seconds=20),
    )
    state = discovery.PartitionState(
        "TEST", SESSION, tmp_path / "regular_1min.csv", "partition", 389,
        390, 1, True, (), True, (halt,), (opened.isoformat(),), False,
    )
    state.csv_path.touch()
    reason = discovery._preflight_exclusion_reason(
        state, "five_minute_orb_long_v002", None, 20
    )
    assert reason == "HALT_INTERVAL_VALIDATOR_INCOMPATIBLE"


def test_genuine_missing_segment_start_still_fails_closed(tmp_path: Path) -> None:
    state = discovery.PartitionState(
        "TEST", SESSION, tmp_path / "regular_1min.csv", "partition", 389,
        390, 1, False, ("2024-01-03T09:30:00-05:00",), False, (), (), False,
    )
    state.csv_path.touch()
    reason = discovery._preflight_exclusion_reason(
        state, "five_minute_orb_long_v002", None, 20
    )
    assert reason == "UNEXPLAINED_REGULAR_GAP"


def test_same_bar_stop_precedes_target() -> None:
    bars = (
        _bar(0),
        _bar(1, close=10, low=8.5, high=12.5),
        _bar(2),
    )
    proposal = SimpleNamespace(
        intended_entry_timestamp=bars[1].timestamp.isoformat(),
        stop=9.0,
        target=12.0,
        timeout_complete_bars=60,
    )
    timestamp, raw_exit, reason = discovery._raw_exit(
        proposal, bars, datetime(2024, 1, 3, 16, 0, tzinfo=NY)
    )
    assert timestamp == bars[1].timestamp + timedelta(minutes=1)
    assert raw_exit == 9.0
    assert reason == "intrabar_stop"


@pytest.mark.parametrize("multiplier,name", [(1.5, "cost_1_5x"), (2.0, "cost_2x")])
def test_cost_scenarios_are_exact_and_worse(multiplier: float, name: str) -> None:
    base = replace(
        _trade(0), raw_entry=10, raw_exit=11, quantity=100,
        gross_pnl=97.9, net_pnl=95.9,
    )
    projected = discovery._project_trade(base, multiplier, name)
    expected = 100 * (11 * (1 - 0.001 * multiplier) - 10 * (1 + 0.001 * multiplier)) - 2
    assert projected.net_pnl == pytest.approx(expected)
    assert projected.cost_scenario == name
    assert projected.net_pnl < base.net_pnl


def test_metrics_and_classification_rules() -> None:
    trades = [_trade(100), _trade(-50), _trade(75, "OTHER")]
    metrics = discovery.trade_metrics(trades)
    assert metrics["trade_count"] == 3
    assert metrics["net_pnl"] == 125
    assert metrics["profit_factor"] == pytest.approx(3.5)
    assert discovery.classify(
        {"trade_count": 3, "base": metrics, "cost_1_5x": metrics},
        material_data_limitation=False,
    ) == "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    assert discovery.classify(
        {"trade_count": 100, "base": metrics, "cost_1_5x": metrics},
        material_data_limitation=True,
    ) == "INCONCLUSIVE_DATA_LIMITATION"


def test_negative_strategy_rejects_after_minimum_sample() -> None:
    losing = discovery.trade_metrics([_trade(-10) for _ in range(30)])
    result = discovery.classify(
        {"trade_count": 30, "base": losing, "cost_1_5x": losing},
        material_data_limitation=False,
    )
    assert result == "REJECT"


def test_positive_nonqualifying_result_is_not_mislabeled_reject() -> None:
    positive_but_concentrated = discovery.trade_metrics(
        [_trade(10) for _ in range(30)]
    )
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="screening_classification_rules_do_not_cover_result",
    ):
        discovery.classify(
            {
                "trade_count": 30,
                "base": positive_but_concentrated,
                "cost_1_5x": positive_but_concentrated,
            },
            material_data_limitation=False,
        )


def test_prior_session_realizations_cannot_trip_next_day_loss_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(discovery, "DAILY_LOSS_LIMIT", 0.007)
    first_day = date(2024, 1, 3)
    second_day = date(2024, 1, 4)

    def proposal(symbol: str, day: date) -> SimpleNamespace:
        entry = datetime(day.year, day.month, day.day, 9, 31, tzinfo=NY)
        return SimpleNamespace(
            intended_entry_timestamp=entry.isoformat(),
            signal_timestamp=(entry - timedelta(minutes=1)).isoformat(),
            strategy_identity="strategy",
            proposal_identity=f"proposal-{symbol}-{day}",
            symbol=symbol,
            session=day.isoformat(),
            cost_adjusted_entry=10.01,
            raw_entry_open=10.0,
            stop=5.0,
            target=20.0,
            timeout_complete_bars=1,
        )

    proposals = [
        proposal(symbol, first_day) for symbol in ("A", "B", "C")
    ] + [proposal("D", second_day)]
    bars_by_key = {}
    for item in proposals:
        day = date.fromisoformat(item.session)
        timestamp = datetime(day.year, day.month, day.day, 9, 31, tzinfo=NY)
        bars_by_key[(item.symbol, day)] = (
            replace(
                _bar(1, close=10, low=4),
                security_id=item.symbol,
                symbol=item.symbol,
                session=day,
                timestamp=timestamp,
            ),
        )
    calendar = {
        day: discovery.CalendarSession(
            day,
            datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY),
            datetime(day.year, day.month, day.day, 16, 0, tzinfo=NY),
            False,
        )
        for day in (first_day, second_day)
    }
    trades, rejections = discovery.simulate_strategy(
        "high_of_day_breakout_long_v002", proposals, bars_by_key, calendar
    )
    assert len(trades) == 4
    assert rejections == []


def test_gap_and_go_cannot_enter_executable_strategy_set() -> None:
    assert discovery.DEFERRED_STRATEGY not in discovery.INCLUDED_STRATEGIES
    assert set(discovery.INCLUDED_STRATEGIES) == set(discovery.STRATEGIES) - {
        discovery.DEFERRED_STRATEGY
    }


def test_discovery_boundary_and_output_namespace_are_explicit() -> None:
    assert discovery.DISCOVERY_START.isoformat() == "2023-07-24"
    assert discovery.DISCOVERY_END.isoformat() == "2024-12-31"
    source = Path(discovery.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("broker", "live_order", "paper_trading", "holdout_root"):
        assert forbidden not in source


def test_outputs_require_external_non_authoritative_namespace(
    tmp_path: Path,
) -> None:
    allowed = (
        tmp_path / "protected" / "discovery_screening"
        / "nine_strategy_v001" / "run-v001"
    )
    assert discovery._require_external_discovery_path(allowed) == allowed.resolve()
    with pytest.raises(
        discovery.DiscoveryIntegrityError, match="non_discovery_output_namespace"
    ):
        discovery._require_external_discovery_path(tmp_path / "arbitrary")
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="discovery_output_inside_git_repository",
    ):
        discovery._require_external_discovery_path(
            repository / "discovery_screening" / "nine_strategy_v001" / "run"
        )


def test_one_executor_integrity_failure_prevents_performance_publication(
    tmp_path: Path,
) -> None:
    strategy_id = "five_minute_orb_long_v002"
    failure_rows = [{
        "strategy_id": strategy_id,
        "symbol": "TEST",
        "session": SESSION.isoformat(),
        "stage": "evaluation",
        "status": "integrity_failure",
        "reason": "bars:unclassified_minute_gap",
        "count": 1,
    }]
    accounting = discovery.evaluation_accounting(
        failure_rows, {strategy_id: 1}, {}
    )
    output = (
        tmp_path / "discovery_screening" / "nine_strategy_v001"
        / "failed-run" / "screen"
    )
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="executor_integrity_failures_prevent_publication:1",
    ):
        discovery.enforce_zero_executor_integrity_failures(
            output, failure_rows, accounting
        )
    summary = json.loads((output / "failure_summary.json").read_text())
    assert summary["status"] == "FAILED_EXECUTOR_INTEGRITY"
    assert summary["executor_integrity_failure_count"] == 1
    assert summary["performance_artifacts_published"] is False
    assert not (output / "completed_trades.csv").exists()
    assert not (output / "metrics.json").exists()


def test_evaluation_accounting_rejects_hidden_or_unknown_outcomes() -> None:
    strategy_id = "five_minute_orb_long_v002"
    rows = [{
        "strategy_id": strategy_id,
        "symbol": "TEST",
        "session": SESSION.isoformat(),
        "stage": "evaluation",
        "status": "proposal",
        "reason": "",
        "count": 1,
    }]
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="evaluation_accounting_mismatch",
    ):
        discovery.evaluation_accounting(rows, {strategy_id: 2}, {strategy_id: 1})

    rows[0]["status"] = "silently_dropped"
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="unknown_evaluation_accounting_status",
    ):
        discovery.evaluation_accounting(rows, {strategy_id: 1}, {})


def test_evaluation_accounting_reconciles_preflight_and_executor_statuses() -> None:
    strategy_id = "five_minute_orb_long_v002"
    rows = [
        {
            "strategy_id": strategy_id,
            "symbol": "TEST",
            "session": SESSION.isoformat(),
            "stage": "preflight",
            "status": "excluded",
            "reason": "HALT_INTERVAL_VALIDATOR_INCOMPATIBLE",
            "count": 1,
        },
        {
            "strategy_id": strategy_id,
            "symbol": "OTHER",
            "session": SESSION.isoformat(),
            "stage": "evaluation",
            "status": "unavailable",
            "reason": "missing_next_bar",
            "count": 2,
        },
        {
            "strategy_id": strategy_id,
            "symbol": "OTHER",
            "session": SESSION.isoformat(),
            "stage": "evaluation",
            "status": "proposal",
            "reason": "",
            "count": 3,
        },
    ]
    accounting = discovery.evaluation_accounting(
        rows, {strategy_id: 5}, {strategy_id: 3}
    )
    assert accounting["preflight_exclusion_counts"] == {strategy_id: 1}
    assert accounting["status_counts"] == {
        f"{strategy_id}|proposal": 3,
        f"{strategy_id}|unavailable": 2,
    }
    assert accounting["executor_integrity_failure_count"] == 0


def test_metadata_cannot_claim_zero_when_data_quality_is_nonzero() -> None:
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="published_integrity_failure_count_mismatch",
    ):
        discovery.reconcile_integrity_claims(
            raw_count=1,
            summary_count=1,
            data_quality_count=1,
            metadata_count=0,
            documentation=(
                "The corrected accepted screen has `1` executor integrity failures."
            ),
        )


def test_documentation_claim_must_match_immutable_integrity_count() -> None:
    with pytest.raises(
        discovery.DiscoveryIntegrityError,
        match="documentation_integrity_claim_mismatch",
    ):
        discovery.reconcile_integrity_claims(
            raw_count=0,
            summary_count=0,
            data_quality_count=0,
            metadata_count=0,
            documentation=(
                "The corrected accepted screen has `704` executor integrity failures."
            ),
        )


def test_all_metrics_are_finite_or_explicitly_null() -> None:
    metrics = discovery.trade_metrics([])
    for value in metrics.values():
        if isinstance(value, float):
            assert math.isfinite(value)
