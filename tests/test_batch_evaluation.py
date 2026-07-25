from datetime import date, time
from pathlib import Path

import pandas as pd
import pytest

from aml.exchange_calendar_adapter import ExchangeCalendarsAdapter
from aml.batch_evaluation import (
    batch_artifact_directory, deterministic_run_id, evaluate_batch,
    load_quality_policy, normalize_manifest, normalized_manifest_bytes,
    QualityPolicy, require_reproducible_source,
)
from aml.market_halts import HaltRecord, HaltSchedule, CompletenessMode
from aml.market_calendar import SyntheticMarketCalendar
from aml.trade_simulator import SimulationConfig
from aml.thresholds import CANDIDATE_SCORE_THRESHOLD, ELIGIBLE_SCORE_THRESHOLD


def manifest(rows=None):
    rows = rows or [("AAA", "2024-01-02", "attention_event")]
    return pd.DataFrame([{
        "symbol": symbol, "trading_date": day, "calendar_id": "SYNTHETIC_TEST",
        "session_class": classification,
        "cohort_id": "synthetic", "selection_rule": "fixed_before_test",
        "data_source": "synthetic", "data_feed": "synthetic",
        "inclusion_timestamp": "2023-12-01T00:00:00Z",
        "dataset_vintage": "v1", "matched_group_id": "group-1",
    } for symbol, day, classification in rows])


def bars(symbol="AAA", periods=390, jump_index=None, drop=()):
    timestamps = pd.date_range("2024-01-02 09:30", periods=periods, freq="min", tz="America/New_York")
    close = [100.0] * periods
    if jump_index is not None:
        close[jump_index:] = [110.0] * (periods - jump_index)
    frame = pd.DataFrame({
        "timestamp": timestamps, "symbol": symbol, "open": close, "high": close,
        "low": close, "close": close, "volume": 1000, "bar_vwap": close,
    })
    return frame.drop(index=list(drop)).reset_index(drop=True)


def quality_policy(**changes):
    values = {
        "configuration_version": "test-v1",
        "complete_session_maximum_missing_percentage": 0.01,
        "usable_session_maximum_missing_percentage": 0.05,
        "excluded_quality_bands": ("missing_heavy",),
        "exclude_quality_flagged_sessions": True,
        "require_clean_git_worktree": True,
    }
    values.update(changes)
    return QualityPolicy(**values)


def halt_schedule(symbol="AAA", trading_date="2024-01-02", halt="2024-01-02 09:35:46-05:00", resume="2024-01-02 09:40:46-05:00"):
    record = HaltRecord(
        symbol, pd.Timestamp(trading_date).date(),
        pd.Timestamp(halt), pd.Timestamp(resume), pd.Timestamp(resume),
        "M", "NYSE", "https://example.test/halts",
    )
    return HaltSchedule(symbol, pd.Timestamp(trading_date).date(), (record,), "data/market_halts/AAA/2024-01-02_verified_halts.csv")


def evaluate(frame, loader, calendar=None, input_hashes=None, policy=None, source_commit="source-commit"):
    return evaluate_batch(
        frame, loader, calendar or SyntheticMarketCalendar(), "strategy-hash",
        source_commit, input_hashes or {"input": "hash"}, policy or quality_policy(),
        SimulationConfig(),
    )


def test_duplicate_and_conflicting_sessions_are_rejected():
    duplicate = pd.concat([manifest(), manifest()], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_manifest(duplicate)
    conflicting = manifest([("AAA", "2024-01-02", "attention_event"), ("AAA", "2024-01-02", "ordinary_control")])
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_manifest(conflicting)


@pytest.mark.parametrize("mutation,match", [
    (lambda f: f.drop(columns="data_feed"), "Missing manifest"),
    (lambda f: f.assign(trading_date="not-a-date"), "Malformed trading_date"),
    (lambda f: f.assign(session_class="winner"), "Unsupported"),
    (lambda f: f.assign(selection_rule=""), "Missing required provenance"),
])
def test_malformed_manifests_and_missing_provenance(mutation, match):
    with pytest.raises(ValueError, match=match):
        normalize_manifest(mutation(manifest()))


def test_manifest_normalization_and_run_id_ignore_row_order():
    frame = manifest([("BBB", "2024-01-03", "ordinary_control"), ("AAA", "2024-01-02", "attention_event")])
    reversed_frame = frame.iloc[::-1].reset_index(drop=True)
    assert normalized_manifest_bytes(frame) == normalized_manifest_bytes(reversed_frame)
    args = (
        "strategy", SimulationConfig(), "commit", {"b": "2", "a": "1"},
        quality_policy().fingerprint(), SyntheticMarketCalendar().identity({"SYNTHETIC_TEST"}).fingerprint(),
    )
    assert deterministic_run_id(frame, *args) == deterministic_run_id(reversed_frame, *args)


def test_run_identity_changes_only_for_content_not_execution_time():
    policy = quality_policy().fingerprint()
    calendar = SyntheticMarketCalendar().identity({"SYNTHETIC_TEST"}).fingerprint()
    first = deterministic_run_id(manifest(), "s", SimulationConfig(), "c", {"x": "1"}, policy, calendar)
    second = deterministic_run_id(manifest(), "s", SimulationConfig(), "c", {"x": "1"}, policy, calendar)
    changed = deterministic_run_id(manifest(), "s", SimulationConfig(), "c", {"x": "2"}, policy, calendar)
    assert first == second and first != changed


def test_run_identity_changes_when_only_manifest_feed_changes():
    iex = manifest().assign(data_feed="iex")
    sip = manifest().assign(data_feed="sip")
    arguments = (
        "strategy", SimulationConfig(), "commit", {"x": "1"},
        quality_policy().fingerprint(),
        SyntheticMarketCalendar().identity({"SYNTHETIC_TEST"}).fingerprint(),
    )
    assert deterministic_run_id(iex, *arguments) != deterministic_run_id(sip, *arguments)


def test_quality_policy_load_validation_and_fingerprint(tmp_path):
    path = Path(__file__).parents[1] / "config" / "batch_evaluation_v001.yaml"
    policy = load_quality_policy(path)
    assert policy.complete_session_maximum_missing_percentage == 0.01
    changed = quality_policy(complete_session_maximum_missing_percentage=0.02)
    assert changed.fingerprint() != policy.fingerprint()
    with pytest.raises(ValueError, match="between 0 and 1"):
        quality_policy(usable_session_maximum_missing_percentage=1.1)
    with pytest.raises(ValueError, match="cannot exceed"):
        quality_policy(complete_session_maximum_missing_percentage=0.2, usable_session_maximum_missing_percentage=0.1)
    with pytest.raises(ValueError, match="clean Git worktree"):
        quality_policy(require_clean_git_worktree=False)
    malformed = tmp_path / "bad.yaml"
    malformed.write_text('{"configuration_version":"x"}')
    with pytest.raises(ValueError, match="Unknown or missing"):
        load_quality_policy(malformed)


def test_quality_policy_changes_classification_and_run_id():
    frame = bars(drop=range(8))
    strict = quality_policy(complete_session_maximum_missing_percentage=0.01, usable_session_maximum_missing_percentage=0.015)
    permissive = quality_policy(complete_session_maximum_missing_percentage=0.03, usable_session_maximum_missing_percentage=0.05)
    strict_result = evaluate(manifest(), lambda row: frame, policy=strict)
    permissive_result = evaluate(manifest(), lambda row: frame, policy=permissive)
    assert strict_result.session_results.iloc[0]["data_quality_band"] == "missing_heavy"
    assert permissive_result.session_results.iloc[0]["data_quality_band"] == "complete_or_minor"
    assert strict_result.run_id != permissive_result.run_id


def test_halt_aware_quality_uses_effective_missing_metrics_and_preserves_raw_metrics():
    frame = bars(drop=(6, 7, 8, 9))
    strict = evaluate_batch(
        manifest(), lambda row: frame, SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(
            complete_session_maximum_missing_percentage=0.005,
            usable_session_maximum_missing_percentage=0.01,
        ),
        SimulationConfig(), CompletenessMode.STRICT,
        lambda row: halt_schedule(),
    )
    row = strict.session_results.iloc[0]
    assert row["missing_minute_count"] == 4
    assert row["effective_missing_minute_count"] == 4
    assert row["halt_covered_missing_minute_count"] == 4
    assert row["data_quality_band"] == row["effective_data_quality_band"]
    assert not row["included_in_aggregate"]
    halt_aware = evaluate_batch(
        manifest(), lambda row: frame, SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(
            complete_session_maximum_missing_percentage=0.005,
            usable_session_maximum_missing_percentage=0.01,
        ),
        SimulationConfig(), CompletenessMode.HALT_AWARE,
        lambda row: halt_schedule(),
    )
    row = halt_aware.session_results.iloc[0]
    assert row["missing_minute_count"] == 4
    assert row["effective_missing_minute_count"] == 0
    assert row["halt_covered_missing_minute_count"] == 4
    assert row["halt_covered_observed_minute_count"] == 0
    assert row["data_quality_band"] == "missing_heavy"
    assert row["effective_data_quality_band"] == "complete_or_minor"
    assert row["included_in_aggregate"]
    assert row["status"] == "zero_candidates"


def test_mixed_halt_covered_and_unexplained_gaps_keep_effective_quality_bands():
    frame = bars(drop=(6, 7, 8, 9, 50))
    result = evaluate_batch(
        manifest(), lambda row: frame, SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(
            complete_session_maximum_missing_percentage=0.005,
            usable_session_maximum_missing_percentage=0.01,
        ),
        SimulationConfig(), CompletenessMode.HALT_AWARE,
        lambda row: halt_schedule(),
    )
    row = result.session_results.iloc[0]
    assert row["missing_minute_count"] == 5
    assert row["halt_covered_missing_minute_count"] == 4
    assert row["effective_missing_minute_count"] == 1
    assert row["data_quality_band"] == "missing_heavy"
    assert row["effective_data_quality_band"] == "complete_or_minor"
    assert row["included_in_aggregate"]


def test_no_verified_halts_leave_raw_and_effective_quality_identical():
    frame = bars(drop=(6, 7, 8, 9))
    result = evaluate_batch(
        manifest(), lambda row: frame, SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(
            complete_session_maximum_missing_percentage=0.005,
            usable_session_maximum_missing_percentage=0.01,
        ),
        SimulationConfig(), CompletenessMode.HALT_AWARE,
        lambda row: HaltSchedule(row["symbol"], pd.Timestamp(row["trading_date"]).date()),
    )
    row = result.session_results.iloc[0]
    assert row["verified_halt_count"] == 0
    assert row["halt_covered_missing_minute_count"] == 0
    assert row["missing_minute_count"] == row["effective_missing_minute_count"] == 4
    assert row["data_quality_band"] == row["effective_data_quality_band"]
    assert not row["included_in_aggregate"]


def test_completeness_mode_changes_run_id_deterministically():
    strict = evaluate_batch(
        manifest(), lambda row: bars(), SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(),
        SimulationConfig(), CompletenessMode.STRICT,
        lambda row: halt_schedule(),
    )
    aware = evaluate_batch(
        manifest(), lambda row: bars(), SyntheticMarketCalendar(), "strategy-hash",
        "source-commit", {"input": "hash"}, quality_policy(),
        SimulationConfig(), CompletenessMode.HALT_AWARE,
        lambda row: halt_schedule(),
    )
    assert strict.run_id != aware.run_id


def test_source_commit_changes_run_id():
    first = evaluate(manifest(), lambda row: bars(), source_commit="a")
    second = evaluate(manifest(), lambda row: bars(), source_commit="b")
    assert first.run_id != second.run_id


def test_calendar_identity_changes_run_id():
    policy = quality_policy().fingerprint()
    synthetic = SyntheticMarketCalendar().identity({"SYNTHETIC_TEST"}).fingerprint()
    authoritative = ExchangeCalendarsAdapter().identity({"XNYS"}).fingerprint()
    args = (manifest(), "s", SimulationConfig(), "c", {"x": "1"}, policy)
    assert deterministic_run_id(*args, synthetic) != deterministic_run_id(*args, authoritative)


def test_authoritative_holiday_row_is_retained_without_loading_data():
    frame = manifest([("AAA", "2024-07-04", "ordinary_control")])
    frame["calendar_id"] = "XNYS"
    result = evaluate(
        frame,
        lambda row: (_ for _ in ()).throw(AssertionError("loader should not run")),
        calendar=ExchangeCalendarsAdapter(),
    )
    row = result.session_results.iloc[0]
    assert row["status"] == "non_trading_session"
    assert row["exclusion_reason"] == "not_scheduled_by_exchange_calendar"
    assert pd.isna(row["session_return"])


def test_manifest_order_does_not_change_session_results_and_equity_resets():
    frame = manifest([("BBB", "2024-01-02", "ordinary_control"), ("AAA", "2024-01-02", "attention_event")])
    data = {"AAA": bars("AAA", jump_index=20), "BBB": bars("BBB", jump_index=20)}

    def loader(row):
        return data[row["symbol"]]

    first = evaluate(frame, loader)
    second = evaluate(frame.iloc[::-1], loader)
    pd.testing.assert_frame_equal(first.session_results, second.session_results)
    if not first.trades.empty:
        assert first.trades.groupby("symbol")["equity_before_trade"].first().eq(2000).all()


def test_batch_uses_candidate_55_and_execution_70_thresholds(monkeypatch):
    replay = pd.DataFrame({
        "timestamp": bars().timestamp, "symbol": "AAA", "price": 100.0,
        "volume": 1000.0, "score": [55, 69, 70] + [0] * 387,
        "eligible": [False, False, True] + [False] * 387,
    })
    monkeypatch.setattr("aml.batch_evaluation.replay_to_frame", lambda frame: replay)
    result = evaluate(manifest(), lambda row: bars())
    assert len(result.candidates) == 3
    assert result.trades["signal_score"].tolist() == [70]
    assert SimulationConfig().candidate_score_threshold == CANDIDATE_SCORE_THRESHOLD
    assert SimulationConfig().eligible_score_threshold == ELIGIBLE_SCORE_THRESHOLD


def test_zero_candidate_zero_trade_no_data_and_processing_error_are_retained():
    zero_candidates = evaluate(manifest(), lambda row: bars())
    assert zero_candidates.session_results.iloc[0]["status"] == "zero_candidates"
    assert zero_candidates.session_results.iloc[0]["trade_count"] == 0
    zero_trades = evaluate(manifest(), lambda row: bars(jump_index=389))
    assert zero_trades.session_results.iloc[0]["status"] == "zero_trades"
    no_data = evaluate(manifest(), lambda row: (_ for _ in ()).throw(FileNotFoundError("missing")))
    assert no_data.session_results.iloc[0]["status"] == "no_data"
    failed = evaluate(manifest(), lambda row: (_ for _ in ()).throw(RuntimeError("boom")))
    assert failed.session_results.iloc[0]["status"] == "processing_error"
    for result in (no_data, failed):
        row = result.session_results.iloc[0]
        assert pd.isna(row["session_pnl"])
        assert pd.isna(row["session_return"])
        assert pd.isna(row["session_maximum_drawdown"])
        assert pd.isna(row["wins"])
        assert not row["included_in_aggregate"]
    invalid = evaluate(manifest(), lambda row: bars("BBB"))
    invalid_row = invalid.session_results.iloc[0]
    assert invalid_row["status"] == "invalid_data"
    assert pd.isna(invalid_row["session_pnl"])
    zero_candidate_row = zero_candidates.session_results.iloc[0]
    zero_trade_row = zero_trades.session_results.iloc[0]
    assert zero_candidate_row["session_pnl"] == 0
    assert zero_trade_row["session_pnl"] == 0


def test_null_failed_values_remain_blank_in_csv():
    result = evaluate(manifest(), lambda row: (_ for _ in ()).throw(FileNotFoundError("missing")))
    csv = result.session_results.to_csv(index=False)
    reloaded = pd.read_csv(pd.io.common.StringIO(csv))
    assert pd.isna(reloaded.iloc[0]["session_pnl"])


def test_early_close_coverage_missing_minutes_gap_and_quality():
    calendar = SyntheticMarketCalendar(early_closes={date(2024, 1, 2): time(13, 0)})
    result = evaluate(manifest(), lambda row: bars(periods=210, drop=(5, 6)), calendar)
    row = result.session_results.iloc[0]
    assert row["expected_minute_count"] == 210
    assert row["observed_minute_count"] == 208
    assert row["missing_minute_count"] == 2
    assert row["largest_consecutive_gap"] == 2
    assert row["data_quality_band"] == "complete_or_minor"


def test_largest_gap_includes_session_edges():
    result = evaluate(manifest(), lambda row: bars(drop=(0, 1, 2, 389)))
    assert result.session_results.iloc[0]["largest_consecutive_gap"] == 3


def test_missing_heavy_session_is_quality_flagged():
    result = evaluate(manifest(), lambda row: bars(drop=range(40)))
    row = result.session_results.iloc[0]
    assert row["status"] == "quality_flagged"
    assert not row["included_in_aggregate"]


def test_quality_inclusion_is_independent_of_performance():
    losing = bars(drop=range(40))
    winning = losing.copy()
    winning.loc[100:, ["open", "high", "low", "close", "bar_vwap"]] = 120
    first = evaluate(manifest(), lambda row: losing).session_results.iloc[0]
    second = evaluate(manifest(), lambda row: winning).session_results.iloc[0]
    assert first["data_quality_band"] == second["data_quality_band"]
    assert first["included_in_aggregate"] == second["included_in_aggregate"]


def test_mixed_symbol_and_cross_date_inputs_are_invalid_but_retained():
    mixed = bars()
    mixed.loc[0, "symbol"] = "BBB"
    assert evaluate(manifest(), lambda row: mixed).session_results.iloc[0]["status"] == "invalid_data"
    crossed = bars()
    crossed.loc[0, "timestamp"] += pd.Timedelta(1, unit="day")
    assert evaluate(manifest(), lambda row: crossed).session_results.iloc[0]["status"] == "invalid_data"


def test_future_rows_do_not_change_earlier_replay_or_completed_trade():
    full = bars(jump_index=20)
    result = evaluate(manifest(), lambda row: full)
    changed = full.copy()
    if not result.trades.empty:
        exit_time = pd.to_datetime(result.trades.iloc[0]["exit_timestamp"])
        changed.loc[changed["timestamp"] > exit_time, ["open", "high", "low", "close", "bar_vwap"]] = 500
        revised = evaluate(manifest(), lambda row: changed)
        pd.testing.assert_series_equal(result.trades.iloc[0], revised.trades.iloc[0])


def test_artifact_path_is_contained():
    root = Path("/tmp/synthetic-root")
    assert batch_artifact_directory(root, "abcdef1234").parent == (root / "artifacts" / "batch").resolve()
    with pytest.raises(ValueError):
        batch_artifact_directory(root, "../escape")


def test_batch_modules_do_not_import_prohibited_modules():
    root = Path(__file__).parents[1]
    text = "\n".join((root / path).read_text() for path in (
        "src/aml/batch_evaluation.py", "src/aml/batch_reporting.py", "scripts/run_batch_evaluation.py"
    ))
    for prohibited in ("alpaca", "aml.settings", "credentials", "order_execution"):
        assert prohibited not in text.lower()


def test_dirty_source_guard_and_ignored_artifacts():
    assert require_reproducible_source("", True)
    assert require_reproducible_source("?? artifacts/batch/output.csv\n", True)
    with pytest.raises(RuntimeError, match="must.*committed|require committed"):
        require_reproducible_source("?? src/aml/new_code.py\n", True)
    with pytest.raises(RuntimeError):
        require_reproducible_source("?? src/aml/file with spaces.py\0", True)
