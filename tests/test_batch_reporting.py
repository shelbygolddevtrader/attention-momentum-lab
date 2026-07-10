import json

import pandas as pd
import pytest

from aml.batch_reporting import build_reports


def sessions():
    return pd.DataFrame([
        {"symbol":"AAA","trading_date":"2024-01-02","session_class":"attention_event","status":"completed","included_in_aggregate":True,"candidate_count":2,"trade_count":2,"session_pnl":15.0,"session_return":0.0075,"session_maximum_drawdown":-0.01,"data_quality_band":"complete_or_minor"},
        {"symbol":"BBB","trading_date":"2024-01-03","session_class":"ordinary_control","status":"zero_trades","included_in_aggregate":True,"candidate_count":1,"trade_count":0,"session_pnl":0.0,"session_return":0.0,"session_maximum_drawdown":0.0,"data_quality_band":"moderate_gaps"},
        {"symbol":"CCC","trading_date":"2024-01-04","session_class":"ordinary_control","status":"completed","included_in_aggregate":True,"candidate_count":1,"trade_count":1,"session_pnl":-5.0,"session_return":-0.0025,"session_maximum_drawdown":-0.005,"data_quality_band":"complete_or_minor"},
        {"symbol":"DDD","trading_date":"2024-01-05","session_class":"attention_event","status":"quality_flagged","included_in_aggregate":False,"candidate_count":1,"trade_count":1,"session_pnl":50.0,"session_return":0.025,"session_maximum_drawdown":-0.02,"data_quality_band":"missing_heavy"},
        {"symbol":"EEE","trading_date":"2024-01-06","session_class":"ordinary_control","status":"no_data","included_in_aggregate":False,"candidate_count":None,"trade_count":None,"session_pnl":None,"session_return":None,"session_maximum_drawdown":None,"data_quality_band":"missing_heavy"},
    ])


def trades():
    return pd.DataFrame([
        {"symbol":"AAA","trading_date":"2024-01-02","session_class":"attention_event","actual_entry_timestamp":"2024-01-02 09:45:00-05:00","signal_score":55,"exit_reason":"target","net_pnl":20.0},
        {"symbol":"AAA","trading_date":"2024-01-02","session_class":"attention_event","actual_entry_timestamp":"2024-01-02 10:45:00-05:00","signal_score":70,"exit_reason":"stop","net_pnl":-5.0},
        {"symbol":"CCC","trading_date":"2024-01-04","session_class":"ordinary_control","actual_entry_timestamp":"2024-01-04 14:15:00-05:00","signal_score":65,"exit_reason":"stop","net_pnl":-5.0},
        {"symbol":"DDD","trading_date":"2024-01-05","session_class":"attention_event","actual_entry_timestamp":"2024-01-05 12:15:00-05:00","signal_score":80,"exit_reason":"target","net_pnl":50.0},
    ])


def test_dual_overall_scope_status_counts_and_undefined_exclusion():
    overall = build_reports(sessions(), trades())["overall"]
    assert overall["total_requested_sessions"] == 5
    assert overall["completed_valid_sessions"] == 4
    assert overall["failed_sessions"] == 1
    assert overall["counts_by_processing_status"]["no_data"] == 1
    all_sessions = overall["all_processed_sessions"]
    qualified = overall["quality_qualified_sessions"]
    assert all_sessions["eligible_session_count"] == 4
    assert qualified["eligible_session_count"] == 3
    assert all_sessions["trade_count"] == 4
    assert qualified["trade_count"] == 3
    assert all_sessions["mean_session_return"] != qualified["mean_session_return"]
    assert qualified["mean_session_return"] == pytest.approx((0.0075 + 0 - 0.0025) / 3)


def test_all_grouped_reports_contain_both_scopes():
    reports = build_reports(sessions(), trades())
    for name in ("by_session_class","by_symbol","by_date","by_data_quality","by_time_bucket","by_score_band","by_exit_reason"):
        assert set(reports[name]["aggregation_scope"]) == {"all_processed_sessions", "quality_qualified_sessions"}
    assert set(reports["by_session_class"]["session_class"]) == {"attention_event", "ordinary_control"}


def test_concentration_and_largest_winner_exclusions_are_scope_specific():
    overall = build_reports(sessions(), trades())["overall"]
    all_sessions = overall["all_processed_sessions"]
    qualified = overall["quality_qualified_sessions"]
    assert all_sessions["largest_winning_trade"] == 50
    assert qualified["largest_winning_trade"] == 20
    assert qualified["net_pnl_excluding_largest_winning_trade"] == -10
    assert qualified["largest_winning_session"] == 15
    assert qualified["net_pnl_excluding_largest_winning_session"] == -5


def test_session_weighted_and_trade_weighted_calculations_differ():
    qualified = build_reports(sessions(), trades())["overall"]["quality_qualified_sessions"]
    assert qualified["expectancy"] == pytest.approx(10 / 3)
    assert qualified["mean_session_return"] == pytest.approx((0.0075 + 0 - 0.0025) / 3)


def test_undefined_profit_factor_edges_are_null():
    no_trades = build_reports(sessions().iloc[[1]], pd.DataFrame())["overall"]["all_processed_sessions"]
    assert no_trades["profit_factor"] is None
    only_wins = build_reports(sessions().iloc[[0]], trades().iloc[[0]])["overall"]["all_processed_sessions"]
    assert only_wins["profit_factor"] is None
    only_losses = build_reports(sessions().iloc[[2]], trades().iloc[[2]])["overall"]["all_processed_sessions"]
    assert only_losses["profit_factor"] == 0


def test_failed_undefined_return_is_never_averaged_as_zero():
    overall = build_reports(sessions(), trades())["overall"]["all_processed_sessions"]
    expected = (0.0075 + 0 - 0.0025 + 0.025) / 4
    assert overall["mean_session_return"] == pytest.approx(expected)


def test_quality_flagged_zero_results_count_in_all_processed_scope():
    frame = sessions().iloc[[3]].copy()
    frame.loc[:, ["candidate_count", "trade_count", "session_pnl", "session_return"]] = [0, 0, 0.0, 0.0]
    overall = build_reports(frame, pd.DataFrame())["overall"]
    assert overall["all_processed_sessions"]["zero_candidate_count"] == 1
    assert overall["all_processed_sessions"]["zero_trade_count"] == 1
    assert overall["quality_qualified_sessions"]["eligible_session_count"] == 0


def test_undefined_metrics_serialize_as_json_null():
    failed = sessions().iloc[[4]]
    report = build_reports(failed, pd.DataFrame())["overall"]
    encoded = json.dumps(report)
    assert '"mean_session_return": null' in encoded
