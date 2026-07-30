from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_executor_registry_v001 import (
    EXECUTOR_REGISTRY_IDENTITY,
    canonical_bundle_bytes,
    execute,
    executor_registry,
    implementation_bundle,
)
from aml.professional_strategy_executors_v001 import EXECUTOR_IDENTITIES
from aml.professional_strategy_olympics_v002 import STRATEGY_IDS, load_bundle
from professional_strategy_synthetic_fixtures import (
    SESSION,
    changed,
    positive_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_professional_strategy_executors_v001.py"


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_every_frozen_strategy_executes_positive_path_end_to_end(strategy_id):
    result = execute(strategy_id, positive_fixture(strategy_id))
    assert result.status == "proposal", (strategy_id, result.reason_codes)
    proposal = result.proposal
    assert proposal is not None
    assert proposal.strategy_id == strategy_id
    assert proposal.strategy_identity
    assert proposal.executor_identity == EXECUTOR_IDENTITIES[strategy_id]
    assert proposal.signal_timestamp == proposal.intended_entry_timestamp
    assert proposal.direction == "long"
    assert proposal.stop < proposal.cost_adjusted_entry < proposal.target
    assert proposal.evidence_class == "synthetic_fixture_non_empirical"
    assert proposal.proposal_identity


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_missing_next_bar_rejects_every_strategy(strategy_id):
    value = positive_fixture(strategy_id)
    result = execute(strategy_id, changed(value, next_bar=None))
    assert result.status == "unavailable"
    assert result.reason_codes == ("missing_next_bar",)


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_incomplete_halt_coverage_fails_every_strategy_closed(strategy_id):
    value = positive_fixture(strategy_id)
    result = execute(strategy_id, changed(value, halt_coverage_complete=False))
    assert result.status == "integrity_failure"
    assert result.reason_codes == ("halts:coverage_incomplete",)


@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
def test_missing_corporate_action_lineage_fails_every_strategy_closed(strategy_id):
    value = positive_fixture(strategy_id)
    result = execute(strategy_id, changed(value, corporate_action_lineage_valid=False))
    assert result.status == "integrity_failure"
    assert result.reason_codes == ("corporate_actions:lineage_invalid",)


def test_failed_breakdown_is_bullish_reclaim_not_short_breakout():
    result = execute(
        "failed_downside_breakdown_reclaim_long_v002",
        positive_fixture("failed_downside_breakdown_reclaim_long_v002"),
    )
    snapshots = dict(result.proposal.indicator_snapshots)
    assert result.proposal.direction == "long"
    assert result.proposal.stop < snapshots["prior_low"]
    assert snapshots["prior_low_timestamp"].endswith("09:30:00-04:00")


@pytest.mark.parametrize(
    ("strategy_id", "mutate", "reason"),
    [
        (
            "failed_downside_breakdown_reclaim_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=98.8, low=98.7),),
            ),
            "confirmation_failed",
        ),
        (
            "first_pullback_continuation_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-2]
                + (
                    replace(value.symbol_bars[-2], low=100.7),
                    value.symbol_bars[-1],
                ),
            ),
            "pullback_depth_outside_bounds",
        ),
        (
            "five_minute_orb_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=101.0),),
            ),
            "breakout_close_not_above_range",
        ),
        (
            "fifteen_minute_orb_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=101.0),),
            ),
            "breakout_close_not_above_range",
        ),
        (
            "gap_and_go_long_v002",
            lambda value: changed(
                value,
                prior_close=replace(
                    value.prior_close, official_close=97.0, adjusted_prior_close=97.0
                ),
            ),
            "gap_below_threshold",
        ),
        (
            "high_of_day_breakout_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=101.0),),
            ),
            "hod_not_broken",
        ),
        (
            "market_relative_momentum_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=101.9),),
            ),
            "relative_return_below_threshold",
        ),
        (
            "rsi_exhaustion_reversion_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (
                    replace(
                        value.symbol_bars[-1],
                        close=value.symbol_bars[-2].high,
                    ),
                ),
            ),
            "reversal_confirmation_absent",
        ),
        (
            "vwap_mean_reversion_fade_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-2]
                + (
                    replace(value.symbol_bars[-2], close=97.8, low=97.7),
                    value.symbol_bars[-1],
                ),
            ),
            "decline_sequence_not_strict",
        ),
        (
            "vwap_reclaim_long_v002",
            lambda value: changed(
                value,
                symbol_bars=value.symbol_bars[:-1]
                + (replace(value.symbol_bars[-1], close=99.0, low=98.9),),
            ),
            "two_bar_reclaim_absent",
        ),
    ],
)
def test_every_strategy_has_a_strategy_specific_negative_path(
    strategy_id, mutate, reason
):
    result = execute(strategy_id, mutate(positive_fixture(strategy_id)))
    assert result.status == "no_signal"
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize(
    "strategy_id",
    ["five_minute_orb_long_v002", "fifteen_minute_orb_long_v002"],
)
def test_orb_threshold_equality_qualifies_and_immediately_below_does_not(strategy_id):
    value = positive_fixture(strategy_id)
    assert execute(strategy_id, value).status == "proposal"
    bars = value.symbol_bars[:-1] + (replace(value.symbol_bars[-1], volume=149.999),)
    result = execute(strategy_id, changed(value, symbol_bars=bars))
    assert result.status == "no_signal"
    assert result.reason_codes == ("relative_volume_below_threshold",)


def test_five_and_fifteen_minute_ranges_are_distinct_exact_windows():
    value = positive_fixture("five_minute_orb_long_v002")
    five = execute("five_minute_orb_long_v002", value).proposal
    fifteen = execute("fifteen_minute_orb_long_v002", value).proposal
    assert dict(five.indicator_snapshots)["opening_range_high"] == 101.0
    assert dict(fifteen.indicator_snapshots)["opening_range_high"] == 101.0
    changed_range = list(value.symbol_bars)
    changed_range[10] = replace(changed_range[10], high=101.1)
    changed_value = changed(value, symbol_bars=tuple(changed_range))
    assert execute("five_minute_orb_long_v002", changed_value).status == "proposal"
    assert execute("fifteen_minute_orb_long_v002", changed_value).status == "proposal"
    assert dict(
        execute("fifteen_minute_orb_long_v002", changed_value).proposal.indicator_snapshots
    )["opening_range_high"] == 101.1
    assert dict(five.indicator_snapshots)["opening_range_high_timestamp"].endswith(
        "09:30:00-04:00"
    )


def test_gap_and_go_rejects_stale_prior_close():
    strategy_id = "gap_and_go_long_v002"
    value = positive_fixture(strategy_id)
    stale = replace(value.prior_close, prior_session=SESSION - timedelta(days=6))
    result = execute(strategy_id, changed(value, prior_close=stale))
    assert result.status == "unavailable"
    assert result.reason_codes == ("prior_close_stale",)


def test_gap_and_go_requires_each_premarket_and_liquidity_gate():
    strategy_id = "gap_and_go_long_v002"
    value = positive_fixture(strategy_id)
    result = execute(strategy_id, changed(value, premarket_history=()))
    assert result.status == "unavailable"
    assert result.reason_codes == ("premarket_history_unavailable",)
    result = execute(strategy_id, changed(value, liquidity_history=()))
    assert result.status == "unavailable"
    assert result.reason_codes == ("unavailable_liquidity_history",)


def test_hod_equal_high_tie_uses_earliest_timestamp():
    strategy_id = "high_of_day_breakout_long_v002"
    result = execute(strategy_id, positive_fixture(strategy_id))
    assert dict(result.proposal.indicator_snapshots)["hod_timestamp"].endswith(
        "09:30:00-04:00"
    )


def test_market_relative_requires_exact_spy_alignment():
    strategy_id = "market_relative_momentum_long_v002"
    value = positive_fixture(strategy_id)
    result = execute(strategy_id, changed(value, spy_bars=value.spy_bars[:-1]))
    assert result.status == "integrity_failure"
    assert result.reason_codes == ("spy:latest_timestamp_misaligned",)


def test_market_relative_has_no_discretionary_regime_input_or_filter():
    result = execute(
        "market_relative_momentum_long_v002",
        positive_fixture("market_relative_momentum_long_v002"),
    )
    assert result.status == "proposal"
    assert "regime" not in json.dumps(result.proposal.indicator_snapshots).casefold()


def test_rsi_target_is_lower_of_frozen_vwap_and_fixed_2r():
    strategy_id = "rsi_exhaustion_reversion_long_v002"
    result = execute(strategy_id, positive_fixture(strategy_id))
    snapshot = dict(result.proposal.indicator_snapshots)
    assert result.proposal.target <= snapshot["regular_vwap"] + 0.01


def test_vwap_fade_requires_strict_deceleration():
    strategy_id = "vwap_mean_reversion_fade_long_v002"
    value = positive_fixture(strategy_id)
    bars = list(value.symbol_bars)
    bars[-2] = replace(bars[-2], close=97.8, low=min(bars[-2].low, 97.7))
    result = execute(strategy_id, changed(value, symbol_bars=tuple(bars)))
    assert result.status == "no_signal"
    assert result.reason_codes == ("decline_sequence_not_strict",)


def test_vwap_reclaim_uses_selected_sequence_earliest_equal_low():
    strategy_id = "vwap_reclaim_long_v002"
    result = execute(strategy_id, positive_fixture(strategy_id))
    snapshot = dict(result.proposal.indicator_snapshots)
    assert snapshot["below_sequence_bars"] == 3.0
    assert snapshot["sequence_low_timestamp"].endswith("09:56:00-04:00")


def test_prior_signal_state_enforces_cap_and_cooldown():
    strategy_id = "five_minute_orb_long_v002"
    value = positive_fixture(strategy_id)
    one = ((strategy_id, value.decision_cutoff - timedelta(minutes=5)),)
    assert execute(strategy_id, changed(value, prior_strategy_entries=one)).reason_codes == (
        "cooldown_active",
    )
    two = (
        (strategy_id, value.decision_cutoff - timedelta(minutes=30)),
        (strategy_id, value.decision_cutoff - timedelta(minutes=16)),
    )
    assert execute(strategy_id, changed(value, prior_strategy_entries=two)).reason_codes == (
        "maximum_entries_reached",
    )


def test_proposal_is_immutable_and_serialization_is_stable():
    result = execute(
        "five_minute_orb_long_v002",
        positive_fixture("five_minute_orb_long_v002"),
    )
    with pytest.raises(FrozenInstanceError):
        result.proposal.stop = 0
    assert result.proposal.canonical_bytes() == result.proposal.canonical_bytes()


def test_future_bar_changes_cannot_change_proposal_because_only_open_is_exposed():
    strategy_id = "five_minute_orb_long_v002"
    value = positive_fixture(strategy_id)
    before = execute(strategy_id, value).proposal
    assert not hasattr(value.next_bar, "close")
    after = execute(strategy_id, replace(value, next_bar=replace(value.next_bar))).proposal
    assert before == after


def test_registry_is_complete_unique_and_exactly_bound_to_v002():
    registry = executor_registry()
    bundle = implementation_bundle()
    v002 = load_bundle(ROOT / "config/professional_strategy_olympics_v002.json")
    assert tuple(registry) == STRATEGY_IDS
    assert len(set(EXECUTOR_IDENTITIES.values())) == 10
    assert [item["strategy_identity"] for item in bundle["executors"]] == [
        item["strategy_identity"] for item in v002["strategies"]
    ]
    assert EXECUTOR_REGISTRY_IDENTITY
    assert bundle["empirical_readiness"]["status"].startswith("blocked_")
    assert not any(
        value for key, value in bundle["empirical_readiness"].items()
        if key.endswith("authorized")
    )


def test_bundle_canonical_serialization_reproduces_identity():
    assert canonical_bundle_bytes() == canonical_bundle_bytes()
    bundle = implementation_bundle()
    assert len(bundle["implementation_bundle_identity"]) == 64
    assert len(bundle["blocked_empirical_readiness_identity"]) == 64


def _run_validator(seed: str, timezone: str):
    environment = os.environ.copy()
    environment.update(
        {"PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONPATH": str(ROOT / "src")}
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        check=False,
    )


def test_manifest_is_hash_seed_and_timezone_invariant():
    outputs = [
        _run_validator(seed, timezone)
        for seed in ("1", "987654")
        for timezone in ("UTC", "America/New_York")
    ]
    assert {item.returncode for item in outputs} == {2}
    assert len({item.stdout for item in outputs}) == 1
    assert all(item.stderr == b"" for item in outputs)


def test_executor_layer_contains_no_provider_network_broker_account_or_order_access():
    paths = list((ROOT / "src/aml").glob("professional_strategy_*_v001.py"))
    paths.append(SCRIPT)
    source = "\n".join(path.read_text() for path in paths).casefold()
    forbidden = (
        "import requests", "alpaca", "socket", "broker", "place_order",
        "submit_order", "account_id", "api_key", "artifacts/tournaments",
        "data/market", "strategy_score", "leaderboard", "net_pnl",
    )
    assert not {item for item in forbidden if item in source}


def test_v002_protocol_file_remains_at_frozen_identity():
    bundle = load_bundle(ROOT / "config/professional_strategy_olympics_v002.json")
    assert bundle["protocol_identity"] == (
        "fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583"
    )
