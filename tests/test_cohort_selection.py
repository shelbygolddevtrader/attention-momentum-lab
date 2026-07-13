"""Point-in-time reference and frozen cohort-selection audit tests."""

from datetime import date
import hashlib
import json

import pandas as pd
import pytest

import aml.cohort_selection as cohort_selection
from aml.cohort_selection import (
    build_daily_selection_audit, compute_premarket_metrics,
    freeze_selection_audit, selection_audit_path,
)
from aml.research_reference_data import (
    LocalPointInTimeReferenceData, ReferenceDataError,
    validate_reference_prerequisites, validate_warmup_sufficiency,
)


DAY = date(2024, 6, 3)
CUTOFF = pd.Timestamp("2024-06-03 09:25:00-04:00")
APPROVED_TEST_SOURCES = frozenset({
    "point-in-time-test", "listing-test", "actions-test", "continuity-test",
})


def local_provider(root):
    return LocalPointInTimeReferenceData(root, APPROVED_TEST_SOURCES)


def write_reference_files(
    root,
    *,
    continuity_rows=1,
    corporate_coverage=True,
    historical_symbol="AAA",
):
    universe = root / "universe"
    universe.mkdir(parents=True)
    pd.DataFrame([{
        "as_of_timestamp": "2024-06-03T13:20:00Z", "symbol": "AAA",
        "security_type": "common_stock", "exchange": "NYSE", "calendar_id": "XNYS",
        "active": True, "source": "point-in-time-test", "dataset_vintage": "v1",
    }]).to_csv(universe / "2024-06-03.csv", index=False)
    pd.DataFrame([{
        "symbol": historical_symbol, "listing_start_timestamp": "2020-01-01T00:00:00Z",
        "listing_end_timestamp": "", "exchange": "NYSE", "calendar_id": "XNYS",
        "known_at_timestamp": "2024-06-03T13:00:00Z", "source": "listing-test",
        "dataset_vintage": "v1",
    }]).to_csv(root / "listings.csv", index=False)
    pd.DataFrame([{
        "symbol": historical_symbol, "record_type": "verified_none",
        "coverage_start_timestamp": "2020-01-01T00:00:00Z",
        "coverage_end_timestamp": "2025-01-01T00:00:00Z" if corporate_coverage else "2024-01-01T00:00:00Z",
        "effective_timestamp": "", "action_type": "", "adjustment_factor": "",
        "known_at_timestamp": "2024-06-03T13:00:00Z", "source": "actions-test",
        "dataset_vintage": "v1",
    }]).to_csv(root / "corporate_actions.csv", index=False)
    continuity = [{
        "canonical_symbol": "AAA", "historical_symbol": historical_symbol,
        "effective_start_timestamp": "2020-01-01T00:00:00Z", "effective_end_timestamp": "",
        "known_at_timestamp": "2024-06-03T13:00:00Z", "source": "continuity-test",
        "dataset_vintage": "v1",
    } for _ in range(continuity_rows)]
    pd.DataFrame(continuity).to_csv(root / "symbol_continuity.csv", index=False)


def test_missing_point_in_time_inputs_fail_closed(tmp_path):
    provider = LocalPointInTimeReferenceData(tmp_path)
    with pytest.raises(ReferenceDataError, match="Missing required universe"):
        validate_reference_prerequisites(provider, "AAA", CUTOFF)


def test_reference_adapter_requires_explicitly_approved_sources(tmp_path):
    write_reference_files(tmp_path)
    with pytest.raises(ReferenceDataError, match="No approved.*sources"):
        validate_reference_prerequisites(
            LocalPointInTimeReferenceData(tmp_path), "AAA", CUTOFF
        )
    with pytest.raises(ReferenceDataError, match="Unapproved universe source"):
        validate_reference_prerequisites(
            LocalPointInTimeReferenceData(tmp_path, frozenset({"another-source"})),
            "AAA",
            CUTOFF,
        )


def test_reference_adapter_validates_listing_actions_and_symbol_continuity(tmp_path):
    write_reference_files(tmp_path)
    result = validate_reference_prerequisites(local_provider(tmp_path), "AAA", CUTOFF)
    assert result["security_type"] == "common_stock"
    assert result["historical_symbol"] == "AAA"
    assert result["corporate_action_status"] == "verified"


def test_reference_validation_follows_historical_ticker(tmp_path):
    write_reference_files(tmp_path, historical_symbol="OLD")
    result = validate_reference_prerequisites(
        local_provider(tmp_path), "AAA", CUTOFF
    )
    assert result["historical_symbol"] == "OLD"


def test_reference_validation_rejects_stale_or_unproven_records(tmp_path):
    stale = tmp_path / "stale"
    write_reference_files(stale)
    universe_path = stale / "universe/2024-06-03.csv"
    universe = pd.read_csv(universe_path)
    universe["as_of_timestamp"] = "2024-06-02T13:20:00Z"
    universe.to_csv(universe_path, index=False)
    with pytest.raises(ReferenceDataError, match="stale or cross-date"):
        validate_reference_prerequisites(
            local_provider(stale), "AAA", CUTOFF
        )

    unproven = tmp_path / "unproven"
    write_reference_files(unproven)
    actions_path = unproven / "corporate_actions.csv"
    actions = pd.read_csv(actions_path, dtype=object)
    actions["source"] = ""
    actions.to_csv(actions_path, index=False)
    with pytest.raises(ReferenceDataError, match="non-empty source"):
        validate_reference_prerequisites(
            local_provider(unproven), "AAA", CUTOFF
        )


def test_verified_none_cannot_mask_an_action(tmp_path):
    write_reference_files(tmp_path)
    actions_path = tmp_path / "corporate_actions.csv"
    actions = pd.read_csv(actions_path, dtype=object)
    actions.loc[0, "effective_timestamp"] = "2024-06-03T12:00:00Z"
    actions.loc[0, "action_type"] = "split"
    actions.loc[0, "adjustment_factor"] = 2
    actions.to_csv(actions_path, index=False)
    with pytest.raises(ReferenceDataError, match="verified_none.*cannot describe"):
        validate_reference_prerequisites(
            local_provider(tmp_path), "AAA", CUTOFF
        )


def test_missing_corporate_coverage_and_ambiguous_continuity_fail(tmp_path):
    first = tmp_path / "first"
    write_reference_files(first, corporate_coverage=False)
    with pytest.raises(ReferenceDataError, match="Corporate-action coverage"):
        validate_reference_prerequisites(local_provider(first), "AAA", CUTOFF)
    second = tmp_path / "second"
    write_reference_files(second, continuity_rows=2)
    with pytest.raises(ReferenceDataError, match="continuity.*ambiguous"):
        validate_reference_prerequisites(local_provider(second), "AAA", CUTOFF)


def test_warmup_requires_all_twenty_verified_sessions():
    dates = pd.bdate_range("2024-05-06", periods=20).strftime("%Y-%m-%d").tolist()
    inventory = pd.DataFrame({
        "symbol": "AAA", "trading_date": dates,
        "premarket_status": ["verified_no_trades", *("complete" for _ in range(19))],
        "regular_status": "complete", "adjustment_status": "verified",
        "reference_status": "verified",
    })
    validate_warmup_sufficiency(inventory, "AAA", dates)
    with pytest.raises(ReferenceDataError, match="Missing warm-up sessions"):
        validate_warmup_sufficiency(inventory.iloc[:-1], "AAA", dates)


def test_premarket_metrics_enforce_cutoff_and_twenty_session_baseline():
    bars = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-06-03 04:00:00-04:00", "2024-06-03 09:24:00-04:00"]),
        "close": [10.5, 11.0], "volume": [100, 200], "bar_vwap": [10.4, 10.9],
    })
    result = compute_premarket_metrics(bars, DAY, 10.0, [10.0] * 20)
    assert result["premarket_share_volume"] == 300
    assert result["premarket_dollar_volume"] == pytest.approx(3220)
    assert result["premarket_gap"] == pytest.approx(0.1)
    late = pd.concat([bars, pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-06-03 09:25:00-04:00"]),
        "close": [12.0], "volume": [1], "bar_vwap": [12.0],
    })], ignore_index=True)
    with pytest.raises(ValueError, match=r"outside \[04:00, 09:25\)"):
        compute_premarket_metrics(late, DAY, 10.0, [10.0] * 20)
    with pytest.raises(ValueError, match="Exactly 20"):
        compute_premarket_metrics(bars, DAY, 10.0, [10.0] * 19)


def test_verified_empty_premarket_is_preserved_as_zero_not_missing():
    empty = pd.DataFrame(columns=["timestamp", "close", "volume", "bar_vwap"])
    result = compute_premarket_metrics(empty, DAY, 10.0, [100.0] * 20)
    assert result["premarket_share_volume"] == 0
    assert result["premarket_dollar_volume"] == 0
    assert result["premarket_relative_volume"] == 0
    assert result["gap_direction"] == "no_trade"
    assert pd.isna(result["premarket_gap"])


def metric(symbol, gap, dollar, rvol, price=10.0, liquidity=20_000_000, atr=0.05):
    return {
        "symbol": symbol, "trading_date": str(DAY), "prerequisite_status": "verified",
        "exclusion_reason": "", "previous_close": price,
        "median_dollar_volume_20": liquidity, "atr_pct_20": atr,
        "median_premarket_volume_20": 100_000,
        "premarket_volume_inputs_20": json.dumps([100_000] * 20),
        "daily_dollar_volume_inputs_20": json.dumps([liquidity] * 20),
        "true_range_inputs_20": json.dumps([atr * price] * 20),
        "premarket_last_price": price * (1 + gap), "premarket_gap": gap,
        "premarket_share_volume": 1_000_000, "premarket_dollar_volume": dollar,
        "premarket_relative_volume": rvol, "premarket_baseline_valid": True,
        "data_feed": "sip", "dataset_vintage": "v1",
        "corporate_action_status": "verified", "corporate_action_source": "test",
        "corporate_action_effective_date": "",
        "latest_input_timestamp": "2024-06-03T13:24:00Z",
    }


def test_daily_selection_is_deterministic_and_matches_controls_without_replacement():
    inputs = pd.DataFrame([
        metric("EVENT", .10, 5_000_000, 8),
        metric("CTRL1", .01, 100_000, 1, price=9.5, liquidity=19_000_000, atr=.052),
        metric("CTRL2", .00, 50_000, .8, price=10.5, liquidity=21_000_000, atr=.048),
        metric("FAR", .00, 20_000, .5, price=50, liquidity=100_000_000, atr=.2),
    ])
    first = build_daily_selection_audit(inputs)
    second = build_daily_selection_audit(inputs.sample(frac=1, random_state=7))
    pd.testing.assert_frame_equal(first, second)
    third = build_daily_selection_audit(inputs.loc[:, reversed(inputs.columns)])
    pd.testing.assert_frame_equal(first, third)
    assert first["universe_considered"].all()
    assert first.loc[first["symbol"].eq("EVENT"), "selected_event"].item()
    assert set(first.loc[first["selected_control"], "symbol"]) == {"CTRL1", "CTRL2"}
    assert first.loc[first["selected_control"], "matched_group_id"].nunique() == 1


def test_daily_selection_rejects_metrics_timestamped_at_cutoff():
    inputs = pd.DataFrame([metric("EVENT", .10, 5_000_000, 8)])
    inputs["latest_input_timestamp"] = "2024-06-03T13:25:00Z"
    with pytest.raises(ValueError, match="strictly before 09:25"):
        build_daily_selection_audit(inputs)


def test_selection_builder_rejects_outcome_or_unknown_inputs():
    inputs = pd.DataFrame([metric("EVENT", .10, 5_000_000, 8)])
    with pytest.raises(ValueError, match="outcome columns.*return_30m"):
        build_daily_selection_audit(inputs.assign(return_30m=0.2))
    with pytest.raises(ValueError, match="Unexpected selection inputs.*unregistered"):
        build_daily_selection_audit(inputs.assign(unregistered="value"))


def test_frozen_selection_audit_is_hashed_immutable_and_outcome_free(tmp_path):
    audit = build_daily_selection_audit(pd.DataFrame([metric("EVENT", .10, 5_000_000, 8)]))
    path = tmp_path / "2024-06-03_selection_audit.csv"
    audit_path, metadata_path = freeze_selection_audit(
        audit, path, frozen_at="2024-06-03 09:27:00-04:00"
    )
    metadata = json.loads(metadata_path.read_text())
    assert metadata["status"] == "frozen"
    assert metadata["audit_sha256"] == hashlib.sha256(audit_path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError, match="immutable"):
        freeze_selection_audit(audit, path, frozen_at="2024-06-03 09:27:00-04:00")
    with pytest.raises(ValueError, match="before 09:25"):
        freeze_selection_audit(
            audit, tmp_path / "early.csv",
            frozen_at="2024-06-03 09:24:59-04:00",
        )
    historical_backfill, _ = freeze_selection_audit(
        audit, tmp_path / "backfill.csv",
        frozen_at="2026-07-13 12:00:00-04:00",
    )
    assert historical_backfill.exists()
    with pytest.raises(ValueError, match="outcome columns"):
        freeze_selection_audit(
            audit.assign(net_pnl=1), tmp_path / "outcome.csv",
            frozen_at="2024-06-03 09:27:00-04:00",
        )


def test_freeze_is_atomic_and_cleans_partial_pair(tmp_path, monkeypatch):
    audit = build_daily_selection_audit(
        pd.DataFrame([metric("EVENT", .10, 5_000_000, 8)])
    )
    path = tmp_path / "atomic.csv"
    original = cohort_selection._exclusive_publish_text
    calls = 0

    def fail_metadata(output_path, content):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated metadata publication failure")
        original(output_path, content)

    monkeypatch.setattr(cohort_selection, "_exclusive_publish_text", fail_metadata)
    with pytest.raises(OSError, match="publication failure"):
        freeze_selection_audit(
            audit, path, frozen_at="2024-06-03 09:27:00-04:00"
        )
    assert not path.exists()
    assert not path.with_suffix(".metadata.json").exists()
    assert not path.with_suffix(".csv.lock").exists()


def test_canonical_selection_audit_path_is_versionable(tmp_path):
    path = selection_audit_path(tmp_path, "cohort-v001", DAY)
    assert path == tmp_path / "data/selection_audits/cohort-v001/2024-06-03.csv"
    with pytest.raises(ValueError, match="cohort_id"):
        selection_audit_path(tmp_path, "../escape", DAY)
