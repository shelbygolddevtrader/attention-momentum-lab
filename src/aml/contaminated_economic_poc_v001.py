"""Prospectively frozen contract for Contaminated Economic POC V001.

This module initially contains only the contract and its fail-closed validator.
The contract was committed before any economic outcome was read.  Later code in
this milestone may execute it but may not change it; a substantive change
requires a separately versioned POC V002.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from aml.benchmark_strategy_research_v001 import canonical_hash


SCHEMA_VERSION = "aml.contaminated-economic-poc.v001"
POC_VERSION = "contaminated-economic-poc-v001"
LABELS = (
    "CONTAMINATED ECONOMIC POC",
    "DEVELOPMENT DATA",
    "NOT EMPIRICAL EVIDENCE",
    "NOT VALIDATION",
    "NOT HOLDOUT",
    "NOT STATISTICAL PROOF",
    "NOT PRODUCTION",
    "NOT CAPITAL ELIGIBLE",
)


FROZEN_POC_CONTRACT: dict[str, object] = {
    "schema_version": SCHEMA_VERSION,
    "poc_version": POC_VERSION,
    "frozen_before_economic_outcome_access": True,
    "source_commit": "65fbafb08ae83d2cc81c0b3846a545829b1bc8df",
    "labels": list(LABELS),
    "claim_boundary": (
        "exploratory research-management prioritization only; no empirical, "
        "validation, holdout, statistical, production, trading, or capital claim"
    ),
    "inclusion_policy": {
        "selection_rule": (
            "all five executable exploratory mechanisms present on frozen source "
            "commit, included without outcome-based selection or post-result removal"
        ),
        "mechanisms": [
            {
                "candidate_id": "opening-drive-first-pullback-v001",
                "mechanism_identity": (
                    "1013ee3c7c57ae6cb5326aa22e09ba980dfbe4bc2815fb40c0596db4f09b7c82"
                ),
                "specification_identity": (
                    "ad9eda50f8542eacf66867b309802021b0d7c81d6cf54404fdf5d10f96d283a0"
                ),
                "implementation_identity": (
                    "896148c2197b519b3eb9b11fa9082b3215d7494322829ea9b3a826f7055e7c26"
                ),
                "executor_identity": (
                    "9affc9b5496498c3c1371674af8b7b0e83a4a5d68672e869827cbf35a2babacd"
                ),
                "simulation_strategy_id": "first_pullback_continuation_long_v002",
            },
            {
                "candidate_id": (
                    "opening-range-expansion-continuation-long-five-minute-v001"
                ),
                "mechanism_identity": (
                    "8092124c58649e112e0c8c1d137583fdcf926ec0ad6bc6397bf36db09294bedb"
                ),
                "specification_identity": (
                    "13611f02dcb749c0f8f13ffae5485dfa87df8b469baf9e59044c9d4b698a5494"
                ),
                "implementation_identity": (
                    "5e3b8f85ba8a0a369cc857b5968afc3b79a3ccdcbe9bb467200a53e80dc38977"
                ),
                "executor_identity": (
                    "5e3b8f85ba8a0a369cc857b5968afc3b79a3ccdcbe9bb467200a53e80dc38977"
                ),
                "simulation_strategy_id": "five_minute_orb_long_v002",
            },
            {
                "candidate_id": "volatility-expansion-breakout-long-adjacent-v001",
                "mechanism_identity": (
                    "89c483ed1542f63353a78a53fe60bcb4794cdece6b5bf3825cfde244a7033244"
                ),
                "specification_identity": (
                    "949424cf82d66d05228cb87ea8ace644ed7eb901fde7d25c9ee42deef6b9e4aa"
                ),
                "implementation_identity": (
                    "e5a19c85c5bd960e4ba52bbbad6a8083ff374a48b0f96c4dd4ffceed38b47610"
                ),
                "executor_identity": (
                    "e5a19c85c5bd960e4ba52bbbad6a8083ff374a48b0f96c4dd4ffceed38b47610"
                ),
                "simulation_strategy_id": "five_minute_orb_long_v002",
            },
            {
                "candidate_id": "opening-range-failed-downside-reclaim-long-v001",
                "mechanism_identity": (
                    "e0d14acd20bd47a205ca4696fd1e9b3dfe6ea6ded8609c18b85aaee3e92466de"
                ),
                "specification_identity": (
                    "8eb6d34a71940cedd9fb203342b2477f396e4b272fc158938a53462be0cc3fcb"
                ),
                "implementation_identity": (
                    "f1b5d4b559f4e2121f694f660445ba21cf50b70dca5794aeac82a0983a40bf84"
                ),
                "executor_identity": (
                    "f1b5d4b559f4e2121f694f660445ba21cf50b70dca5794aeac82a0983a40bf84"
                ),
                "simulation_strategy_id": "five_minute_orb_long_v002",
            },
            {
                "candidate_id": (
                    "vwap-downside-deviation-deceleration-reversion-long-v001"
                ),
                "mechanism_identity": (
                    "e8fa3cd13fbd2b32115fe36932ddcc7212571805374504be40f2f2033766774e"
                ),
                "specification_identity": (
                    "796855368520ab66e505064333277f155a5f0a2234004d582ea397884f10495c"
                ),
                "implementation_identity": (
                    "a1b67f9895c21be737c8281cfeb4c5dc2c5c7287ac89df47ba045f182bf0d901"
                ),
                "executor_identity": (
                    "a1b67f9895c21be737c8281cfeb4c5dc2c5c7287ac89df47ba045f182bf0d901"
                ),
                "simulation_strategy_id": "vwap_mean_reversion_fade_long_v002",
            },
        ],
    },
    "dataset": {
        "status": "contaminated_development_only_not_authorized_pit_evidence",
        "dataset_vintage": (
            "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001"
        ),
        "dataset_fingerprint": (
            "fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d"
        ),
        "manifest_relative_path": (
            "manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json"
        ),
        "manifest_sha256": (
            "b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b"
        ),
        "symbols": [
            "SPY", "QQQ", "IWM", "DIA", "TQQQ", "SQQQ", "SPXL", "SPXS",
            "GLD", "SLV", "USO", "TLT", "XLF", "XLK", "XLE", "UVXY",
            "GME", "AMC", "AAPL", "TSLA", "NVDA", "AMD", "PLTR",
        ],
        "warmup_sessions": [
            "2023-09-29", "2023-10-02", "2023-10-03", "2023-10-04",
            "2023-10-06", "2023-10-10", "2023-10-19", "2023-10-20",
            "2023-12-05", "2023-12-14", "2023-12-29", "2024-01-02",
            "2024-01-03", "2024-01-09", "2024-01-16", "2024-02-13",
            "2024-04-09", "2024-08-02", "2025-04-03", "2025-04-04",
        ],
        "evaluation_sessions": [
            "2025-04-08", "2025-04-10", "2025-10-10", "2025-10-16",
            "2025-10-17", "2025-10-22", "2025-11-06", "2025-11-17",
            "2025-11-18", "2025-11-20", "2025-11-21", "2025-12-17",
            "2026-01-14", "2026-01-30", "2026-02-03", "2026-02-04",
            "2026-02-12", "2026-02-17", "2026-02-20", "2026-02-26",
        ],
        "partition_rule": (
            "all 23 symbols over 20 fixed warm-up and 20 fixed evaluation "
            "sessions; no post-result exclusions; only frozen fail-closed integrity "
            "or lifecycle reasons may exclude a decision or proposal"
        ),
    },
    "execution": {
        "run_each_mechanism_separately": True,
        "unchanged_simulator": "aml.discovery_screen_v001.simulate_strategy",
        "initial_capital_usd": "100000.00",
        "requested_risk_budget_usd_per_trade": "250.00",
        "maximum_gross_exposure_fraction": "0.50",
        "maximum_concurrent_positions": 3,
        "daily_new_entry_loss_stop_fraction": "0.01",
        "proposal_order": [
            "signal_timestamp", "strategy_identity", "symbol",
        ],
        "rejected_proposals": "reconciliation_only_no_economic_result",
        "incomplete_lifecycles": "fail_closed_no_silent_omission",
        "unavailable_decisions": "counted_with_frozen_reason_no_trade_created",
    },
    "costs": {
        "commission_per_share_per_order_usd": "0.005",
        "minimum_commission_per_order_usd": "1.00",
        "scenarios": [
            {"scenario": "base", "friction_basis_points_per_side": "10"},
            {"scenario": "cost_1_5x", "friction_basis_points_per_side": "15"},
            {"scenario": "cost_2x", "friction_basis_points_per_side": "20"},
        ],
        "stress_rule": (
            "hold trade inclusion, quantity, raw entry, raw exit, and commissions "
            "fixed; vary adverse entry and exit friction only"
        ),
    },
    "risk_normalization": {
        "initial_risk_usd": (
            "quantity times (base-cost-adjusted entry minus frozen stop); must be positive"
        ),
        "net_r": "scenario net P&L divided by initial_risk_usd",
        "gross_r": "pre-cost gross P&L divided by initial_risk_usd",
        "illustrative_risk_usd": ["50.00", "100.00", "250.00"],
        "illustrative_only_not_position_sizing_advice": True,
    },
    "metrics": [
        "proposal_count", "completed_trade_count", "winner_count", "loser_count",
        "flat_trade_count", "exit_reason_distribution", "win_rate", "gross_pnl",
        "modeled_transaction_costs", "net_pnl", "average_net_pnl_per_trade",
        "gross_expectancy", "net_expectancy", "profit_factor", "average_winner",
        "average_loser", "payoff_ratio", "total_r", "mean_r", "median_r",
        "r_distribution", "target_percentage", "stop_percentage",
        "timeout_or_other_percentage", "maximum_drawdown", "maximum_drawdown_r",
        "longest_losing_streak", "largest_symbol_concentration",
        "top_trade_concentration",
    ],
    "aggregate": {
        "name": "all_mechanism_equal_normalized_risk_concatenation",
        "not_a_portfolio_or_allocation": True,
        "inclusion": "all completed trades from all five mechanisms",
        "ordering": [
            "exit_timestamp", "candidate_id", "proposal_identity",
        ],
        "weighting": "one actual completed trade contributes its normalized R; no mechanism weights",
        "standardized_illustrative_risk_usd": "100.00",
    },
    "interpretation": {
        "minimum_completed_trades": 30,
        "interesting": {
            "base_mean_net_r_strictly_positive": True,
            "cost_1_5x_mean_net_r_strictly_positive": True,
            "cost_2x_mean_net_r_nonnegative": True,
            "base_profit_factor_minimum_inclusive": "1.10",
            "top_trade_positive_profit_share_maximum_inclusive": "0.25",
            "largest_symbol_absolute_contribution_share_maximum_inclusive": "0.50",
        },
        "unattractive": (
            "at least 30 completed trades and nonpositive mean net R at base, "
            "1.5x, and 2x costs"
        ),
        "otherwise": "EXPLORATORY_MIXED",
        "labels": [
            "EXPLORATORY_ECONOMICALLY_UNATTRACTIVE",
            "EXPLORATORY_MIXED",
            "EXPLORATORY_ECONOMICALLY_INTERESTING",
            "EXPLORATORY_TOO_FEW_TRADES",
        ],
    },
    "precision": {
        "internal_arithmetic": "decimal_from_shortest_round_trip_input",
        "currency_output": "two_decimal_places_round_half_even",
        "ratio_and_r_output": "six_decimal_places_round_half_even",
        "count_output": "integer",
        "ordering": "lexicographic_except_explicit_chronological_trade_sequences",
    },
    "prohibited_actions": [
        "strategy_or_threshold_change", "optimization", "parameter_search",
        "outcome_based_subset_selection", "post_result_exclusion", "validation_access",
        "holdout_access", "forward_testing", "paper_trading", "live_trading",
        "broker_interaction", "olympics_execution", "capital_allocation",
    ],
    "output_namespace": "exploratory_economic_poc/v001",
}


def poc_contract_identity() -> str:
    """Return the domain-separated identity of the frozen prospective contract."""

    return canonical_hash({"domain": SCHEMA_VERSION, "contract": FROZEN_POC_CONTRACT})


def frozen_poc_contract() -> dict[str, object]:
    """Return a defensive copy of the exact prospectively frozen contract."""

    return deepcopy(FROZEN_POC_CONTRACT)


def validate_poc_contract(value: Mapping[str, object]) -> dict[str, object]:
    """Reject any semantic, inclusion, identity, or policy change."""

    if not isinstance(value, Mapping) or dict(value) != FROZEN_POC_CONTRACT:
        raise ValueError("contaminated economic POC V001 contract changed")
    if tuple(value["labels"]) != LABELS:
        raise ValueError("contaminated economic POC labels changed")
    mechanisms = value["inclusion_policy"]["mechanisms"]
    if len(mechanisms) != 5 or len({item["candidate_id"] for item in mechanisms}) != 5:
        raise ValueError("POC inclusion set is not exactly the five frozen mechanisms")
    dataset = value["dataset"]
    if len(dataset["symbols"]) != 23:
        raise ValueError("POC symbol universe changed")
    if len(dataset["warmup_sessions"]) != 20 or len(dataset["evaluation_sessions"]) != 20:
        raise ValueError("POC session universe changed")
    return deepcopy(dict(value))
