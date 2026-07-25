import json
from datetime import date

import pandas as pd
import pytest

from aml.signals import SignalConfig, add_features
from aml.tournament_attention import (
    SESSION_DIAGNOSTIC_COLUMNS,
    build_attention_audit,
    build_signal_diagnostics,
    session_feature_diagnostics,
    validate_attention_integrity,
)
from aml.tournament_config import DatasetSplit
from aml.tournament_strategies import attention_momentum_feature_frame, build_strategy
from scripts.analyze_tournament_attention import _month

PARAMETERS = {
    "return_window": 5,
    "volume_window": 20,
    "acceleration_window": 5,
    "return_threshold": 0.03,
    "relative_volume_threshold": 3.0,
    "vwap_threshold": 0.01,
    "acceleration_threshold": 1.5,
    "eligible_score_threshold": 70,
}


def strategy():
    return build_strategy("attention_momentum", "0.1.1", PARAMETERS)


def bars(periods=30, day="2024-11-01", symbol="AAA"):
    timestamps = pd.date_range(
        f"{day} 09:30", periods=periods, freq="min", tz="America/New_York"
    )
    return pd.DataFrame({
        "timestamp": timestamps,
        "symbol": symbol,
        "open": 100.0,
        "high": 100.1,
        "low": 99.9,
        "close": 100.0,
        "volume": 100.0,
        "bar_vwap": 100.0,
    })


def signal_bars():
    frame = bars()
    frame.loc[10, ["open", "high", "low", "close", "volume", "bar_vwap"]] = [
        104.0, 104.1, 103.9, 104.0, 500.0, 104.0,
    ]
    return frame


def session_row(split, symbol, *, processed=True, eligible_rows=0):
    return {
        "split": split,
        "symbol": symbol,
        "trading_date": "2024-11-01" if split == "development" else "2025-11-03",
        "processed": processed,
        "row_count": 390,
        "rows_with_valid_return_feature": 385,
        "rows_with_valid_relative_volume_feature": 385,
        "rows_with_valid_vwap_feature": 390,
        "rows_with_valid_acceleration_feature": 388,
        "rows_with_all_required_features": 385,
        "rows_above_return_threshold": 1,
        "rows_above_relative_volume_threshold": 1,
        "rows_above_vwap_threshold": 1,
        "rows_above_acceleration_threshold": 1,
        "rows_above_score_threshold": eligible_rows,
        "score_sum": 100.0,
        "score_count": 390,
        "maximum_score": 100.0,
        "warning_codes": "",
    }


def signal_row(split, symbol, proposal_id):
    trading_date = "2024-11-01" if split == "development" else "2025-11-03"
    offset = "-04:00" if split == "development" else "-05:00"
    metadata = {
        "signal_metadata": {
            "source_bar_timestamp": f"{trading_date}T09:40:00{offset}",
            "information_cutoff": f"{trading_date}T09:41:00{offset}",
            "raw_return_feature": 0.04,
            "relative_volume_feature": 5.0,
            "vwap_distance_feature": 0.01,
            "acceleration_feature": 5.0,
            "return_score_component": 35,
            "relative_volume_score_component": 35,
            "vwap_score_component": 20,
            "acceleration_score_component": 10,
            "total_score": 100,
            "eligibility_threshold": 70,
            "eligible": True,
        }
    }
    return {
        "strategy_id": "attention_momentum",
        "split": split,
        "symbol": symbol,
        "trading_date": trading_date,
        "proposal_id": proposal_id,
        "signal_timestamp": f"{trading_date}T09:41:00{offset}",
        "execution_status": "accepted",
        "execution_reason": "accepted",
        "provenance_json": json.dumps(metadata),
    }


def test_mixed_dst_offsets_group_by_trading_month():
    frame = pd.DataFrame({
        "trading_date": ["2024-10-31", "2024-11-04"],
        "signal_timestamp": [
            "2024-10-31T15:00:00-04:00", "2024-11-04T15:00:00-05:00",
        ],
    })
    assert list(_month(frame)) == ["2024-10", "2024-11"]
    parsed = pd.to_datetime(frame["signal_timestamp"], utc=True, errors="coerce")
    assert parsed.notna().all()


def test_score_components_preserve_legacy_behavior_and_provenance():
    frame = signal_bars()
    enriched = add_features(frame, SignalConfig())
    legacy = (
        enriched["return_5m"].ge(0.03).astype(int) * 35
        + enriched["relative_volume"].ge(3.0).astype(int) * 35
        + enriched["vwap_distance"].ge(0.01).astype(int) * 20
        + enriched["volume_acceleration"].ge(1.5).astype(int) * 10
    )
    pd.testing.assert_series_equal(enriched["score"], legacy, check_names=False)
    signals = strategy().evaluate(frame)
    assert len(signals) == int(legacy.ge(70).sum()) == 1
    metadata = signals[0].metadata
    assert metadata["raw_return_feature"] == pytest.approx(0.04)
    assert metadata["relative_volume_score_component"] == 35
    assert metadata["total_score"] == 100
    assert metadata["eligible"] is True


def test_version_increment_changes_identity_without_changing_parameters():
    old = build_strategy("attention_momentum", "0.1.0", PARAMETERS)
    corrected = strategy()
    assert old.strategy_version == "0.1.0"
    assert corrected.strategy_version == "0.1.1"
    assert old.parameter_hash == corrected.parameter_hash
    assert old.evaluate(signal_bars())[0] != corrected.evaluate(signal_bars())[0]


def test_nan_warmup_is_ineligible_and_feature_coverage_is_reported():
    frame = attention_momentum_feature_frame(bars(), strategy())
    assert frame.loc[:4, "return_5m"].isna().all()
    assert frame.loc[:4, "relative_volume"].isna().all()
    assert not frame.loc[:4, "eligible"].any()
    audit = session_feature_diagnostics(
        bars(), strategy(), split="development", symbol="AAA",
        trading_date="2024-11-01", processed=True,
    )
    assert audit["rows_with_valid_return_feature"] == 25
    assert audit["rows_with_all_required_features"] == 25


def test_rolling_features_have_no_lookahead():
    full = signal_bars()
    prefix = full.iloc[:15].copy()
    changed = full.copy()
    changed.loc[15:, ["close", "volume", "bar_vwap"]] = [500.0, 99999.0, 500.0]
    expected = attention_momentum_feature_frame(prefix, strategy())
    actual = attention_momentum_feature_frame(changed, strategy()).iloc[:15].reset_index(drop=True)
    pd.testing.assert_frame_equal(expected, actual)


def test_five_minute_return_uses_elapsed_time_across_gaps():
    frame = bars(8)
    frame.loc[6, ["open", "high", "low", "close", "bar_vwap"]] = [
        103.0, 103.1, 102.9, 103.0, 103.0,
    ]
    frame.loc[7, "timestamp"] = pd.Timestamp(frame.loc[6, "timestamp"]) + pd.Timedelta(
        5, unit="min"
    )
    frame.loc[7, ["open", "high", "low", "close", "volume", "bar_vwap"]] = [
        104.0, 104.1, 103.9, 104.0, 500.0, 104.0,
    ]
    exact = add_features(frame, SignalConfig())
    legacy = add_features(frame, SignalConfig(), exact_elapsed_return=False)
    assert exact.loc[7, "return_5m"] == pytest.approx(104 / 103 - 1)
    assert legacy.loc[7, "return_5m"] == pytest.approx(0.04)
    assert not bool(exact.loc[7, "eligible"])
    assert bool(legacy.loc[7, "eligible"])


def test_signal_diagnostics_flatten_score_provenance_deterministically():
    signals = pd.DataFrame([
        signal_row("validation", "BBB", "b"),
        signal_row("development", "AAA", "a"),
    ])
    one = build_signal_diagnostics(signals)
    two = build_signal_diagnostics(signals.sample(frac=1, random_state=7))
    pd.testing.assert_frame_equal(one, two)
    assert list(one["proposal_id"]) == ["a", "b"]
    assert one.loc[0, "total_score"] == 100


def test_zero_signal_symbols_and_reconciliation_are_deterministic():
    sessions = pd.DataFrame([
        session_row("development", "BBB"),
        session_row("development", "AAA", eligible_rows=1),
    ], columns=SESSION_DIAGNOSTIC_COLUMNS)
    signals = pd.DataFrame([signal_row("development", "AAA", "a")])
    trades = pd.DataFrame([{
        "strategy_id": "attention_momentum", "split": "development",
        "symbol": "AAA", "proposal_id": "a",
    }])
    audit = build_attention_audit(sessions, signals, trades)
    assert list(audit["symbol"]) == ["AAA", "BBB"]
    assert audit.set_index("symbol").loc["BBB", "warning_codes"] == "zero_signals"
    validate_attention_integrity(
        audit, build_signal_diagnostics(signals),
        (DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),),
    )
    broken = audit.copy()
    broken.loc[broken["symbol"].eq("AAA"), "executed_trade_count"] = 0
    with pytest.raises(ValueError, match="do not reconcile"):
        validate_attention_integrity(
            broken, build_signal_diagnostics(signals),
            (DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),),
        )


def test_split_isolation_and_coverage_fail_closed():
    sessions = pd.DataFrame([
        session_row("development", "AAA", processed=False)
    ], columns=SESSION_DIAGNOSTIC_COLUMNS)
    audit = build_attention_audit(sessions, pd.DataFrame(columns=[
        "strategy_id", "split", "symbol", "execution_status", "execution_reason",
        "trading_date",
    ]), pd.DataFrame(columns=["strategy_id", "split", "symbol"]))
    with pytest.raises(ValueError, match="zero processed"):
        validate_attention_integrity(
            audit, pd.DataFrame(),
            (DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),),
        )
    valid_audit = audit.copy()
    valid_audit["processed_session_count"] = 1
    valid_audit["missing_session_count"] = 0
    outside = build_signal_diagnostics(pd.DataFrame([signal_row("development", "AAA", "a")]))
    outside.loc[:, "trading_date"] = "2025-01-02"
    with pytest.raises(ValueError, match="outside split"):
        validate_attention_integrity(
            valid_audit, outside,
            (DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),),
        )


def test_concentrated_to_broad_regression_is_warning_not_failure():
    symbols = ["A", "B", "C", "D", "E", "F"]
    sessions = pd.DataFrame([
        session_row(
            split, symbol,
            eligible_rows=int(
                (split == "development" and symbol in symbols[:3])
                or split == "validation"
            ),
        )
        for split in ("development", "validation") for symbol in symbols
    ], columns=SESSION_DIAGNOSTIC_COLUMNS)
    rows = []
    for split, active in (("development", symbols[:3]), ("validation", symbols)):
        rows.extend(signal_row(split, symbol, f"{split}-{symbol}") for symbol in active)
    signals = pd.DataFrame(rows)
    trades = pd.DataFrame([{
        "strategy_id": "attention_momentum", "split": row["split"],
        "symbol": row["symbol"], "proposal_id": row["proposal_id"],
    } for row in rows])
    audit = build_attention_audit(sessions, signals, trades)
    warnings = validate_attention_integrity(
        audit, build_signal_diagnostics(signals),
        (
            DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),
            DatasetSplit("validation", date(2025, 1, 1), date(2025, 12, 31)),
        ),
    )
    assert warnings == ("active_symbol_distribution_shift",)
    assert audit.groupby("split")["signal_count"].apply(lambda value: value.gt(0).sum()).to_dict() == {
        "development": 3, "validation": 6,
    }
