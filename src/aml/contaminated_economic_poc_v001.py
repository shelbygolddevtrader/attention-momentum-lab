"""Prospectively frozen contract for Contaminated Economic POC V001.

This module initially contains only the contract and its fail-closed validator.
The contract was committed before any economic outcome was read.  Later code in
this milestone may execute it but may not change it; a substantive change
requires a separately versioned POC V002.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

from aml.benchmark_candidate_opening_drive_first_pullback_v001 import (
    REFERENCE_EXECUTOR_IDENTITY as FIRST_PULLBACK_EXECUTOR_IDENTITY,
    REFERENCE_STRATEGY_ID as FIRST_PULLBACK_STRATEGY_ID,
    REFERENCE_STRATEGY_IDENTITY as FIRST_PULLBACK_STRATEGY_IDENTITY,
    evaluate_opening_drive_first_pullback,
)
from aml.benchmark_candidate_opening_range_expansion_v001 import (
    REFERENCE_EXECUTOR_IDENTITY as ORB_EXECUTOR_IDENTITY,
    REFERENCE_STRATEGY_ID as ORB_STRATEGY_ID,
    REFERENCE_STRATEGY_IDENTITY as ORB_STRATEGY_IDENTITY,
)
from aml.benchmark_candidate_opening_range_failed_breakout_reversal_v001 import (
    CHILD_STRATEGY_IDENTITY as REVERSAL_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY as REVERSAL_EXECUTOR_IDENTITY,
    SPECIFICATION_IDENTITY as REVERSAL_SPECIFICATION_IDENTITY,
)
from aml.benchmark_candidate_volatility_expansion_breakout_v001 import (
    CHILD_STRATEGY_IDENTITY as VOLATILITY_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY as VOLATILITY_EXECUTOR_IDENTITY,
    SPECIFICATION_IDENTITY as VOLATILITY_SPECIFICATION_IDENTITY,
)
from aml.benchmark_candidate_vwap_deviation_mean_reversion_v001 import (
    CHILD_STRATEGY_IDENTITY as VWAP_STRATEGY_IDENTITY,
    EXECUTOR_IDENTITY as VWAP_EXECUTOR_IDENTITY,
    SPECIFICATION_IDENTITY as VWAP_SPECIFICATION_IDENTITY,
)
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json
from aml.discovery_screen_v001 import (
    CalendarSession,
    CompletedTrade,
    simulate_strategy,
)
from aml.opening_range_expansion_continuation_v001 import (
    _evaluate_exploratory as _evaluate_orb,
)
from aml.opening_range_failed_breakout_reversal_child_v001 import (
    _evaluate_exploratory as _evaluate_reversal,
)
from aml.professional_strategy_executor_models_v001 import EvaluationInput
from aml.professional_strategy_indicators_v001 import ExecutorIntegrityError
from aml.volatility_expansion_breakout_child_v001 import (
    _evaluate_exploratory as _evaluate_volatility,
)
from aml.vwap_deviation_mean_reversion_child_v001 import (
    _evaluate_exploratory as _evaluate_vwap,
    _load_partitions,
    _next_open,
)


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
    "metric_semantics": {
        "completed_trade": "accepted trade returned by the unchanged simulator",
        "winner_loser_flat": "scenario net P&L strictly positive, strictly negative, or exactly zero",
        "gross_pnl": "quantity times (raw exit minus raw entry), before friction and commissions",
        "modeled_transaction_costs": (
            "quantity times adverse per-side entry and exit friction plus both frozen commissions"
        ),
        "net_pnl": "gross P&L minus modeled transaction costs",
        "profit_factor": (
            "sum positive scenario net P&L divided by absolute sum negative scenario net P&L; "
            "null with explicit no-loss flag when denominator is zero"
        ),
        "initial_risk": (
            "quantity times (base 10-bps adjusted raw entry minus frozen stop)"
        ),
        "r_distribution_buckets": [
            "r_le_minus_1",
            "minus_1_lt_r_lt_0",
            "r_eq_0",
            "0_lt_r_lt_1",
            "1_le_r_lt_2",
            "r_ge_2",
        ],
        "median": "arithmetic mean of the two central sorted values for an even count",
        "target_exit_reasons": ["gap_target", "intrabar_target"],
        "stop_exit_reasons": ["gap_stop", "intrabar_stop"],
        "timeout_or_other": "every exit reason not listed as target or stop",
        "drawdown_order": [
            "exit_timestamp", "candidate_id", "proposal_identity",
        ],
        "maximum_drawdown": (
            "largest peak-to-subsequent-trough decline from zero-start cumulative scenario net P&L"
        ),
        "maximum_drawdown_r": (
            "largest peak-to-subsequent-trough decline from zero-start cumulative scenario net R"
        ),
        "longest_losing_streak": "maximum consecutive strictly negative scenario net P&L trades",
        "top_trade_concentration": (
            "largest positive net R divided by sum positive net R; zero when no positive net R"
        ),
        "largest_symbol_concentration": (
            "largest absolute symbol total net R divided by sum absolute symbol total net R; "
            "zero when denominator is zero"
        ),
    },
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
        "precedence": [
            "EXPLORATORY_TOO_FEW_TRADES",
            "EXPLORATORY_ECONOMICALLY_INTERESTING",
            "EXPLORATORY_ECONOMICALLY_UNATTRACTIVE",
            "EXPLORATORY_MIXED",
        ],
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


class ContaminatedEconomicPocError(ValueError):
    """The frozen POC contract, execution, or artifact graph is invalid."""


NY = ZoneInfo("America/New_York")
MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.000001")
SOURCE_PATHS = (
    "scripts/run_contaminated_economic_poc_v001.py",
    "src/aml/contaminated_economic_poc_v001.py",
    "src/aml/benchmark_candidate_opening_drive_first_pullback_v001.py",
    "src/aml/benchmark_candidate_opening_range_expansion_v001.py",
    "src/aml/benchmark_candidate_volatility_expansion_breakout_v001.py",
    "src/aml/benchmark_candidate_opening_range_failed_breakout_reversal_v001.py",
    "src/aml/benchmark_candidate_vwap_deviation_mean_reversion_v001.py",
    "src/aml/discovery_screen_v001.py",
    "src/aml/professional_strategy_executors_v001.py",
    "src/aml/professional_strategy_lifecycle_v001.py",
)


@dataclass(frozen=True, slots=True)
class MechanismRuntime:
    candidate_id: str
    simulation_strategy_id: str
    evaluator: Callable[..., object] | None
    first_clock: str
    last_clock: str
    state_strategy_id: str | None
    existing_exploratory: Callable[..., object] | None


RUNTIMES = (
    MechanismRuntime(
        "opening-drive-first-pullback-v001",
        FIRST_PULLBACK_STRATEGY_ID,
        evaluate_opening_drive_first_pullback,
        "09:35",
        "11:30",
        FIRST_PULLBACK_STRATEGY_ID,
        None,
    ),
    MechanismRuntime(
        "opening-range-expansion-continuation-long-five-minute-v001",
        ORB_STRATEGY_ID,
        None,
        "09:35",
        "10:59",
        None,
        _evaluate_orb,
    ),
    MechanismRuntime(
        "volatility-expansion-breakout-long-adjacent-v001",
        ORB_STRATEGY_ID,
        None,
        "09:35",
        "14:30",
        None,
        _evaluate_volatility,
    ),
    MechanismRuntime(
        "opening-range-failed-downside-reclaim-long-v001",
        ORB_STRATEGY_ID,
        None,
        "09:35",
        "14:30",
        None,
        _evaluate_reversal,
    ),
    MechanismRuntime(
        "vwap-downside-deviation-deceleration-reversion-long-v001",
        "vwap_mean_reversion_fade_long_v002",
        None,
        "09:35",
        "15:00",
        None,
        _evaluate_vwap,
    ),
)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def _ratio(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_EVEN), "f")


def _money_text(value: Decimal) -> str:
    return format(_money(value), "f")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes(repository_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        path = repository_root / relative
        if not path.is_file() or path.is_symlink():
            raise ContaminatedEconomicPocError(f"source missing:{relative}")
        result[relative] = _sha256(path)
    return result


def _strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or canonical_json(value) != path.read_bytes():
        raise ContaminatedEconomicPocError(f"noncanonical JSON:{path.name}")
    return value


def _verify_artifact(
    value: Mapping[str, object], *, schema_version: str, name: str
) -> None:
    base = {key: item for key, item in value.items() if key != "identity"}
    if value.get("identity") != canonical_hash(base):
        raise ContaminatedEconomicPocError(f"{name} identity changed")
    if value.get("schema_version") != schema_version:
        raise ContaminatedEconomicPocError(f"{name} schema changed")
    if value.get("labels") != list(LABELS):
        raise ContaminatedEconomicPocError(f"{name} labels changed")
    if value.get("contract_identity") != poc_contract_identity():
        raise ContaminatedEconomicPocError(f"{name} contract lineage changed")


def _required_inventory_paths() -> list[str]:
    paths = ["aggregate.json", "contract.json", "report.md", "run.json"]
    paths.extend(f"results/{item.candidate_id}.json" for item in RUNTIMES)
    paths.extend(f"trades/{item.candidate_id}.json" for item in RUNTIMES)
    return sorted(paths)


def _binding() -> dict[str, object]:
    dataset = FROZEN_POC_CONTRACT["dataset"]
    return {
        "dataset_fingerprint": dataset["dataset_fingerprint"],
        "symbols": list(dataset["symbols"]),
        "warmup_sessions": list(dataset["warmup_sessions"]),
        "evaluation_sessions": list(dataset["evaluation_sessions"]),
    }


def verify_frozen_mechanism_identities() -> None:
    """Reject drift in every imported frozen mechanism binding."""

    expected = {
        "opening-drive-first-pullback-v001": (
            FIRST_PULLBACK_STRATEGY_IDENTITY,
            FIRST_PULLBACK_EXECUTOR_IDENTITY,
        ),
        "opening-range-expansion-continuation-long-five-minute-v001": (
            ORB_STRATEGY_IDENTITY,
            ORB_EXECUTOR_IDENTITY,
        ),
        "volatility-expansion-breakout-long-adjacent-v001": (
            VOLATILITY_STRATEGY_IDENTITY,
            VOLATILITY_EXECUTOR_IDENTITY,
        ),
        "opening-range-failed-downside-reclaim-long-v001": (
            REVERSAL_STRATEGY_IDENTITY,
            REVERSAL_EXECUTOR_IDENTITY,
        ),
        "vwap-downside-deviation-deceleration-reversion-long-v001": (
            VWAP_STRATEGY_IDENTITY,
            VWAP_EXECUTOR_IDENTITY,
        ),
    }
    contract = {
        item["candidate_id"]: (
            item["mechanism_identity"], item["executor_identity"]
        )
        for item in FROZEN_POC_CONTRACT["inclusion_policy"]["mechanisms"]
    }
    if expected != contract:
        raise ContaminatedEconomicPocError("frozen mechanism identity drift")
    specifications = {
        "volatility-expansion-breakout-long-adjacent-v001": (
            VOLATILITY_SPECIFICATION_IDENTITY
        ),
        "opening-range-failed-downside-reclaim-long-v001": (
            REVERSAL_SPECIFICATION_IDENTITY
        ),
        "vwap-downside-deviation-deceleration-reversion-long-v001": (
            VWAP_SPECIFICATION_IDENTITY
        ),
    }
    contract_specs = {
        item["candidate_id"]: item["specification_identity"]
        for item in FROZEN_POC_CONTRACT["inclusion_policy"]["mechanisms"]
        if item["candidate_id"] in specifications
    }
    if specifications != contract_specs:
        raise ContaminatedEconomicPocError("frozen specification identity drift")


def _first_pullback_exploratory(
    partitions: Mapping[tuple[str, str], Any],
    binding: Mapping[str, object],
) -> tuple[dict[str, int], Counter[str], Counter[str], list[object], list[object]]:
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposals: list[object] = []
    integrity: list[object] = []
    eligible = 0
    for session in binding["evaluation_sessions"]:
        for symbol in binding["symbols"]:
            partition = partitions[(symbol, session)]
            opened = datetime.combine(partition.session, time(9, 30), NY)
            closed = datetime.combine(partition.session, time(16, 0), NY)
            for index, bar in enumerate(partition.bars):
                clock = bar.timestamp.strftime("%H:%M")
                if not "09:35" <= clock <= "11:30":
                    continue
                try:
                    result = evaluate_opening_drive_first_pullback(
                        EvaluationInput(
                            symbol_bars=partition.bars[: index + 1],
                            next_bar=_next_open(partition.bars, index),
                            scheduled_open=opened,
                            scheduled_close=closed,
                            decision_cutoff=bar.timestamp + timedelta(minutes=1),
                            # Portfolio admission and accepted-entry state belong to
                            # the unchanged simulator.  A proposal must not be
                            # promoted to prior-entry state by this adapter.
                            prior_strategy_entries=(),
                            halt_coverage_complete=True,
                            corporate_action_coverage_complete=True,
                            corporate_action_lineage_valid=True,
                            halt_manifest_identity=(
                                "exploratory-retrospective-halt-coverage"
                            ),
                            corporate_action_manifest_identity=(
                                "exploratory-retrospective-coverage-contaminated"
                            ),
                            calendar_identity="exploratory-fixed-normal-xnys-session",
                        )
                    )
                except ExecutorIntegrityError as exc:
                    statuses["integrity_failure"] += 1
                    reasons["integrity_failure:executor_integrity_rejected"] += 1
                    integrity.append(
                        {
                            "session": session,
                            "symbol": symbol,
                            "timestamp": bar.timestamp.isoformat(),
                            "reason": str(exc),
                        }
                    )
                    continue
                statuses[result.status] += 1
                for reason in result.reason_codes or ("none",):
                    reasons[f"{result.status}:{reason}"] += 1
                if result.status not in {"integrity_failure", "unavailable"} and not any(
                    reason in {
                        "cooldown_active", "maximum_entries_reached",
                        "post_halt_signal_block", "price_above_maximum",
                        "price_below_minimum",
                    }
                    for reason in result.reason_codes
                ):
                    eligible += 1
                if result.proposal is not None:
                    proposals.append(result.proposal)
    counts = {
        "causal_decision_count": sum(statuses.values()),
        "eligible_decision_count": eligible,
        "evaluated_partition_count": (
            len(binding["evaluation_sessions"]) * len(binding["symbols"])
        ),
        "integrity_failure_count": statuses["integrity_failure"],
        "no_signal_count": statuses["no_signal"],
        "no_trade_count": statuses["no_trade"],
        "partition_inspected_count": (
            (len(binding["warmup_sessions"]) + len(binding["evaluation_sessions"]))
            * len(binding["symbols"])
        ),
        "proposal_count": len(proposals),
        "trigger_count": len(proposals) + statuses["no_trade"],
        "unavailable_event_count": statuses["unavailable"],
        "warmup_partition_count": (
            len(binding["warmup_sessions"]) * len(binding["symbols"])
        ),
    }
    return counts, statuses, reasons, proposals, integrity


def _bars_and_calendar(
    partitions: Mapping[tuple[str, str], Any], binding: Mapping[str, object]
) -> tuple[dict[tuple[str, date], tuple[object, ...]], dict[date, CalendarSession]]:
    bars = {
        (partition.symbol, partition.session): partition.bars
        for (_, session), partition in partitions.items()
        if session in binding["evaluation_sessions"]
    }
    calendar = {
        date.fromisoformat(session): CalendarSession(
            date.fromisoformat(session),
            datetime.combine(date.fromisoformat(session), time(9, 30), NY),
            datetime.combine(date.fromisoformat(session), time(16, 0), NY),
            False,
        )
        for session in binding["evaluation_sessions"]
    }
    return bars, calendar


def _economic_trade(
    trade: CompletedTrade, candidate_id: str
) -> dict[str, object]:
    quantity = Decimal(trade.quantity)
    raw_entry = _decimal(trade.raw_entry)
    raw_exit = _decimal(trade.raw_exit)
    stop = _decimal(trade.stop)
    adjusted_entry = raw_entry * Decimal("1.001")
    initial_risk = _money(quantity * (adjusted_entry - stop))
    if initial_risk <= 0:
        raise ContaminatedEconomicPocError("completed trade has nonpositive risk")
    gross = _money(quantity * (raw_exit - raw_entry))
    commissions = _money(
        _decimal(trade.entry_commission) + _decimal(trade.exit_commission)
    )
    scenarios: dict[str, object] = {}
    for scenario in FROZEN_POC_CONTRACT["costs"]["scenarios"]:
        bps = _decimal(scenario["friction_basis_points_per_side"])
        friction = quantity * (raw_entry + raw_exit) * bps / Decimal(10_000)
        costs = _money(friction + commissions)
        net = gross - costs
        scenarios[scenario["scenario"]] = {
            "gross_pnl": _money_text(gross),
            "modeled_transaction_costs": _money_text(costs),
            "net_pnl": _money_text(net),
            "gross_r": _ratio(gross / initial_risk),
            "net_r": _ratio(net / initial_risk),
        }
    reconstructed = _decimal(scenarios["base"]["net_pnl"])
    if abs(reconstructed - _money(_decimal(trade.net_pnl))) > MONEY_QUANTUM:
        raise ContaminatedEconomicPocError("base-cost trade reconstruction changed")
    base = {
        "candidate_id": candidate_id,
        "strategy_identity": trade.strategy_identity,
        "proposal_identity": trade.proposal_identity,
        "symbol": trade.symbol,
        "session": trade.session,
        "signal_timestamp": trade.signal_timestamp,
        "entry_timestamp": trade.entry_timestamp,
        "exit_timestamp": trade.exit_timestamp,
        "exit_reason": trade.exit_reason,
        "quantity": trade.quantity,
        "raw_entry": _money_text(raw_entry),
        "raw_exit": _money_text(raw_exit),
        "stop": _money_text(stop),
        "target": _money_text(_decimal(trade.target)),
        "initial_risk_usd": _money_text(initial_risk),
        "scenarios": scenarios,
    }
    return {**base, "identity": canonical_hash(base)}


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _drawdown(values: Sequence[Decimal]) -> Decimal:
    cumulative = Decimal(0)
    peak = Decimal(0)
    maximum = Decimal(0)
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return maximum


def _r_distribution(values: Sequence[Decimal]) -> dict[str, int]:
    result = {
        "r_le_minus_1": 0,
        "minus_1_lt_r_lt_0": 0,
        "r_eq_0": 0,
        "0_lt_r_lt_1": 0,
        "1_le_r_lt_2": 0,
        "r_ge_2": 0,
    }
    for value in values:
        if value <= -1:
            result["r_le_minus_1"] += 1
        elif value < 0:
            result["minus_1_lt_r_lt_0"] += 1
        elif value == 0:
            result["r_eq_0"] += 1
        elif value < 1:
            result["0_lt_r_lt_1"] += 1
        elif value < 2:
            result["1_le_r_lt_2"] += 1
        else:
            result["r_ge_2"] += 1
    return result


def summarize_trade_records(
    records: Sequence[Mapping[str, object]],
    scenario: str,
    *,
    proposal_count: int,
    rejected_proposal_count: int,
) -> dict[str, object]:
    """Calculate the exact frozen economic metric set from canonical records."""

    ordered = sorted(
        records,
        key=lambda item: (
            item["exit_timestamp"], item["candidate_id"], item["proposal_identity"]
        ),
    )
    scenario_rows = [item["scenarios"][scenario] for item in ordered]
    net = [_decimal(item["net_pnl"]) for item in scenario_rows]
    gross = [_decimal(item["gross_pnl"]) for item in scenario_rows]
    costs = [_decimal(item["modeled_transaction_costs"]) for item in scenario_rows]
    r_values = [_decimal(item["net_r"]) for item in scenario_rows]
    winners = [value for value in net if value > 0]
    losers = [value for value in net if value < 0]
    positives_r = [value for value in r_values if value > 0]
    exit_reasons = Counter(str(item["exit_reason"]) for item in ordered)
    target_count = exit_reasons["gap_target"] + exit_reasons["intrabar_target"]
    stop_count = exit_reasons["gap_stop"] + exit_reasons["intrabar_stop"]
    other_count = len(ordered) - target_count - stop_count
    streak = longest = 0
    for value in net:
        streak = streak + 1 if value < 0 else 0
        longest = max(longest, streak)
    symbol_r: Counter[str] = Counter()
    for item, value in zip(ordered, r_values, strict=True):
        symbol_r[str(item["symbol"])] += value
    symbol_denominator = sum(abs(value) for value in symbol_r.values())
    largest_symbol = (
        min(
            (
                symbol for symbol, value in symbol_r.items()
                if abs(value) == max(abs(item) for item in symbol_r.values())
            ),
            default=None,
        )
        if symbol_r
        else None
    )
    largest_symbol_share = (
        abs(symbol_r[largest_symbol]) / symbol_denominator
        if largest_symbol is not None and symbol_denominator
        else Decimal(0)
    )
    positive_r_total = sum(positives_r, Decimal(0))
    top_trade_share = (
        max(positives_r) / positive_r_total if positive_r_total else Decimal(0)
    )
    count = len(ordered)
    gross_total = sum(gross, Decimal(0))
    cost_total = sum(costs, Decimal(0))
    net_total = sum(net, Decimal(0))
    total_r = sum(r_values, Decimal(0))
    gross_profit = sum(winners, Decimal(0))
    gross_loss = -sum(losers, Decimal(0))
    profit_factor = gross_profit / gross_loss if gross_loss else None
    payoff = (
        (sum(winners) / len(winners)) / abs(sum(losers) / len(losers))
        if winners and losers
        else None
    )
    result = {
        "scenario": scenario,
        "proposal_count": proposal_count,
        "completed_trade_count": count,
        "rejected_proposal_count": rejected_proposal_count,
        "winner_count": len(winners),
        "loser_count": len(losers),
        "flat_trade_count": count - len(winners) - len(losers),
        "win_rate": _ratio(Decimal(len(winners)) / count if count else None),
        "gross_pnl": _money_text(gross_total),
        "modeled_transaction_costs": _money_text(cost_total),
        "net_pnl": _money_text(net_total),
        "average_net_pnl_per_trade": _money_text(net_total / count) if count else None,
        "gross_expectancy": _money_text(gross_total / count) if count else None,
        "net_expectancy": _money_text(net_total / count) if count else None,
        "profit_factor": _ratio(profit_factor),
        "profit_factor_no_losses": bool(winners and not losers),
        "average_winner": _money_text(sum(winners) / len(winners)) if winners else None,
        "average_loser": _money_text(sum(losers) / len(losers)) if losers else None,
        "payoff_ratio": _ratio(payoff),
        "total_r": _ratio(total_r),
        "mean_r": _ratio(total_r / count if count else None),
        "median_r": _ratio(_median(r_values)),
        "r_distribution": _r_distribution(r_values),
        "maximum_drawdown": _money_text(_drawdown(net)),
        "maximum_drawdown_r": _ratio(_drawdown(r_values)),
        "longest_losing_streak": longest,
        "exit_reason_distribution": dict(sorted(exit_reasons.items())),
        "target_percentage": _ratio(Decimal(target_count) / count if count else None),
        "stop_percentage": _ratio(Decimal(stop_count) / count if count else None),
        "timeout_or_other_percentage": _ratio(
            Decimal(other_count) / count if count else None
        ),
        "largest_symbol": largest_symbol,
        "largest_symbol_concentration": _ratio(largest_symbol_share),
        "symbol_net_r": {
            key: _ratio(value) for key, value in sorted(symbol_r.items())
        },
        "top_trade_concentration": _ratio(top_trade_share),
        "illustrative_dollar_translations": {
            risk: _money_text(total_r * _decimal(risk))
            for risk in FROZEN_POC_CONTRACT["risk_normalization"][
                "illustrative_risk_usd"
            ]
        },
    }
    return result


def exploratory_interpretation(
    scenario_metrics: Mapping[str, Mapping[str, object]]
) -> str:
    base = scenario_metrics["base"]
    count = int(base["completed_trade_count"])
    if count < int(FROZEN_POC_CONTRACT["interpretation"]["minimum_completed_trades"]):
        return "EXPLORATORY_TOO_FEW_TRADES"
    mean_base = _decimal(base["mean_r"])
    mean_15 = _decimal(scenario_metrics["cost_1_5x"]["mean_r"])
    mean_20 = _decimal(scenario_metrics["cost_2x"]["mean_r"])
    profit_factor = (
        _decimal(base["profit_factor"])
        if base["profit_factor"] is not None
        else Decimal("Infinity") if base["profit_factor_no_losses"] else Decimal(0)
    )
    interesting = FROZEN_POC_CONTRACT["interpretation"]["interesting"]
    if (
        mean_base > 0
        and mean_15 > 0
        and mean_20 >= 0
        and profit_factor >= _decimal(interesting["base_profit_factor_minimum_inclusive"])
        and _decimal(base["top_trade_concentration"])
        <= _decimal(interesting["top_trade_positive_profit_share_maximum_inclusive"])
        and _decimal(base["largest_symbol_concentration"])
        <= _decimal(
            interesting[
                "largest_symbol_absolute_contribution_share_maximum_inclusive"
            ]
        )
    ):
        return "EXPLORATORY_ECONOMICALLY_INTERESTING"
    if mean_base <= 0 and mean_15 <= 0 and mean_20 <= 0:
        return "EXPLORATORY_ECONOMICALLY_UNATTRACTIVE"
    return "EXPLORATORY_MIXED"


def _artifact(base: Mapping[str, object]) -> dict[str, object]:
    value = dict(base)
    return {**value, "identity": canonical_hash(value)}


def _render_report(
    results: Sequence[Mapping[str, object]], aggregate: Mapping[str, object]
) -> bytes:
    lines = [
        "# Contaminated Economic POC V001", "",
        "**CONTAMINATED ECONOMIC POC — DEVELOPMENT DATA — NOT EMPIRICAL EVIDENCE — NOT VALIDATION — NOT HOLDOUT — NOT STATISTICAL PROOF — NOT PRODUCTION — NOT CAPITAL ELIGIBLE**",
        "", "This deterministic readout is a research-priority aid only.", "",
        "| Mechanism | Trades | Win rate | Total R | Net P&L at $100/R | Net expectancy | Profit factor | Max DD (R) | 1.5x / 2x mean R | Symbol concentration | Top-trade concentration | Interpretation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        base = item["scenarios"]["base"]
        stress_15 = item["scenarios"]["cost_1_5x"]
        stress_20 = item["scenarios"]["cost_2x"]
        lines.append(
            "| {candidate} | {trades} | {win} | {total_r} | {dollars} | {expectancy} | {pf} | {dd} | {s15} / {s20} | {symbol} | {trade} | {classification} |".format(
                candidate=item["candidate_id"],
                trades=base["completed_trade_count"],
                win=base["win_rate"] or "n/a",
                total_r=base["total_r"] or "n/a",
                dollars=base["illustrative_dollar_translations"]["100.00"],
                expectancy=base["net_expectancy"] or "n/a",
                pf=base["profit_factor"] or ("infinite" if base["profit_factor_no_losses"] else "n/a"),
                dd=base["maximum_drawdown_r"],
                s15=stress_15["mean_r"] or "n/a",
                s20=stress_20["mean_r"] or "n/a",
                symbol=base["largest_symbol_concentration"],
                trade=base["top_trade_concentration"],
                classification=item["exploratory_interpretation"],
            )
        )
    lines.extend(["", "## All-mechanism concatenation", ""])
    base = aggregate["scenarios"]["base"]
    lines.extend(
        [
            f"- Completed trades: {base['completed_trade_count']}",
            f"- Total R: {base['total_r']}",
            f"- Illustrative net P&L at $100/R: {base['illustrative_dollar_translations']['100.00']}",
            f"- Profit factor: {base['profit_factor']}",
            f"- Maximum drawdown R: {base['maximum_drawdown_r']}",
            f"- Interpretation: {aggregate['exploratory_interpretation']}",
            "", "This is not a portfolio, allocation, edge claim, or recommendation.", "",
        ]
    )
    return ("\n".join(lines)).encode("utf-8")


def _output_path(path: Path) -> Path:
    resolved = path.resolve()
    parts = resolved.parts
    for index in range(len(parts) - 1):
        if parts[index : index + 2] == ("exploratory_economic_poc", "v001"):
            return resolved
    raise ContaminatedEconomicPocError("output outside exploratory_economic_poc/v001")


def run_contaminated_economic_poc(
    *, repository_root: Path, dataset_root: Path, output_root: Path
) -> dict[str, object]:
    """Execute the frozen POC once and publish a closed deterministic bundle."""

    validate_poc_contract(FROZEN_POC_CONTRACT)
    verify_frozen_mechanism_identities()
    repository = repository_root.resolve()
    dataset = dataset_root.resolve()
    frozen_dataset = FROZEN_POC_CONTRACT["dataset"]
    if dataset.name != frozen_dataset["dataset_vintage"]:
        raise ContaminatedEconomicPocError("dataset vintage changed")
    manifest_path = repository / frozen_dataset["manifest_relative_path"]
    if _sha256(manifest_path) != frozen_dataset["manifest_sha256"]:
        raise ContaminatedEconomicPocError("dataset manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_fingerprint_sha256") != frozen_dataset["dataset_fingerprint"]:
        raise ContaminatedEconomicPocError("dataset fingerprint changed")
    binding = _binding()
    partitions, partition_records = _load_partitions(dataset, binding)
    bars_by_key, calendar = _bars_and_calendar(partitions, binding)
    source_hashes = _source_hashes(repository)
    source_tree_identity = canonical_hash(
        {"domain": f"{SCHEMA_VERSION}.source-tree", "source_sha256": source_hashes}
    )
    run_identity = canonical_hash(
        {
            "domain": f"{SCHEMA_VERSION}.run",
            "contract_identity": poc_contract_identity(),
            "dataset_fingerprint": frozen_dataset["dataset_fingerprint"],
            "partition_records": partition_records,
            "source_tree_identity": source_tree_identity,
        }
    )
    trade_bundles: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    all_records: list[dict[str, object]] = []
    total_proposals = 0
    total_rejections = 0
    for runtime in RUNTIMES:
        if runtime.existing_exploratory is None:
            evaluated = _first_pullback_exploratory(partitions, binding)
        else:
            evaluated = runtime.existing_exploratory(partitions, binding)
        counts, statuses, reasons, proposals, integrity = evaluated
        if integrity or statuses["integrity_failure"]:
            raise ContaminatedEconomicPocError(
                f"integrity failure:{runtime.candidate_id}"
            )
        trades, rejections = simulate_strategy(
            runtime.simulation_strategy_id, proposals, bars_by_key, calendar
        )
        if len(proposals) != len(trades) + len(rejections):
            raise ContaminatedEconomicPocError(
                f"proposal reconciliation failed:{runtime.candidate_id}"
            )
        records = [
            _economic_trade(trade, runtime.candidate_id) for trade in trades
        ]
        all_records.extend(records)
        total_proposals += len(proposals)
        total_rejections += len(rejections)
        trade_bundle = _artifact(
            {
                "schema_version": f"{SCHEMA_VERSION}.trades",
                "labels": list(LABELS),
                "contract_identity": poc_contract_identity(),
                "run_identity": run_identity,
                "candidate_id": runtime.candidate_id,
                "trade_count": len(records),
                "trades": records,
            }
        )
        trade_bundles.append(trade_bundle)
        scenario_metrics = {
            item["scenario"]: summarize_trade_records(
                records,
                item["scenario"],
                proposal_count=len(proposals),
                rejected_proposal_count=len(rejections),
            )
            for item in FROZEN_POC_CONTRACT["costs"]["scenarios"]
        }
        result = _artifact(
            {
                "schema_version": f"{SCHEMA_VERSION}.result",
                "labels": list(LABELS),
                "contract_identity": poc_contract_identity(),
                "run_identity": run_identity,
                "candidate_id": runtime.candidate_id,
                "mechanism_identity": next(
                    item["mechanism_identity"]
                    for item in FROZEN_POC_CONTRACT["inclusion_policy"]["mechanisms"]
                    if item["candidate_id"] == runtime.candidate_id
                ),
                "trade_bundle_identity": trade_bundle["identity"],
                "decision_counts": {
                    **counts,
                    "status_counts": dict(sorted(statuses.items())),
                    "reason_counts": dict(sorted(reasons.items())),
                },
                "proposal_reconciliation": {
                    "proposal_count": len(proposals),
                    "completed_trade_count": len(trades),
                    "rejected_proposal_count": len(rejections),
                    "reconciled": len(proposals) == len(trades) + len(rejections),
                },
                "scenarios": scenario_metrics,
                "exploratory_interpretation": exploratory_interpretation(
                    scenario_metrics
                ),
            }
        )
        results.append(result)
    aggregate_scenarios = {
        item["scenario"]: summarize_trade_records(
            all_records,
            item["scenario"],
            proposal_count=total_proposals,
            rejected_proposal_count=total_rejections,
        )
        for item in FROZEN_POC_CONTRACT["costs"]["scenarios"]
    }
    aggregate = _artifact(
        {
            "schema_version": f"{SCHEMA_VERSION}.aggregate",
            "labels": list(LABELS),
            "contract_identity": poc_contract_identity(),
            "run_identity": run_identity,
            "aggregation_name": FROZEN_POC_CONTRACT["aggregate"]["name"],
            "not_a_portfolio_or_allocation": True,
            "included_candidate_ids": [item.candidate_id for item in RUNTIMES],
            "mechanism_result_identities": [item["identity"] for item in results],
            "scenarios": aggregate_scenarios,
            "exploratory_interpretation": exploratory_interpretation(
                aggregate_scenarios
            ),
        }
    )
    contract_artifact = _artifact(
        {
            "schema_version": f"{SCHEMA_VERSION}.contract",
            "labels": list(LABELS),
            "contract_identity": poc_contract_identity(),
            "contract": FROZEN_POC_CONTRACT,
        }
    )
    run = _artifact(
        {
            "schema_version": f"{SCHEMA_VERSION}.run",
            "labels": list(LABELS),
            "contract_identity": poc_contract_identity(),
            "run_identity": run_identity,
            "source_tree_identity": source_tree_identity,
            "source_sha256": source_hashes,
            "dataset_fingerprint": frozen_dataset["dataset_fingerprint"],
            "dataset_partition_records": partition_records,
            "partition_count": len(partition_records),
            "included_candidate_ids": [item.candidate_id for item in RUNTIMES],
            "trade_bundle_identities": [item["identity"] for item in trade_bundles],
            "result_identities": [item["identity"] for item in results],
            "aggregate_identity": aggregate["identity"],
            "economic_outcome_access_authorized_only_for_this_poc": True,
            "validation_or_holdout_access_count": 0,
            "optimization_count": 0,
            "parameter_search_count": 0,
        }
    )
    target = _output_path(output_root)
    if target.exists():
        raise ContaminatedEconomicPocError("write-once output already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".contaminated-poc-v001-", dir=target.parent))
    try:
        files: dict[str, bytes] = {
            "contract.json": canonical_json(contract_artifact),
            "run.json": canonical_json(run),
            "aggregate.json": canonical_json(aggregate),
        }
        for bundle, result in zip(trade_bundles, results, strict=True):
            candidate = str(result["candidate_id"])
            files[f"trades/{candidate}.json"] = canonical_json(bundle)
            files[f"results/{candidate}.json"] = canonical_json(result)
        files["report.md"] = _render_report(results, aggregate)
        for relative, data in sorted(files.items()):
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
        inventory = [
            {
                "path": relative,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for relative, data in sorted(files.items())
        ]
        manifest_base = {
            "schema_version": f"{SCHEMA_VERSION}.manifest",
            "labels": list(LABELS),
            "contract_identity": poc_contract_identity(),
            "run_identity": run_identity,
            "files": inventory,
        }
        manifest_artifact = _artifact(manifest_base)
        (staging / "manifest.json").write_bytes(canonical_json(manifest_artifact))
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verified = verify_poc_directory(target)
    return {
        "contract_identity": poc_contract_identity(),
        "run_identity": run_identity,
        "manifest_identity": verified["manifest_identity"],
        "output_root": str(target),
        "verified": True,
    }


def verify_poc_directory(output_root: Path) -> dict[str, object]:
    """Verify hashes, identities, closed inventory, metrics, and lineage."""

    root = _output_path(output_root)
    manifest = _strict_json(root / "manifest.json")
    base = {key: value for key, value in manifest.items() if key != "identity"}
    if manifest.get("identity") != canonical_hash(base):
        raise ContaminatedEconomicPocError("manifest identity changed")
    if manifest.get("schema_version") != f"{SCHEMA_VERSION}.manifest":
        raise ContaminatedEconomicPocError("manifest schema changed")
    if manifest.get("contract_identity") != poc_contract_identity():
        raise ContaminatedEconomicPocError("manifest contract lineage changed")
    if manifest.get("labels") != list(LABELS):
        raise ContaminatedEconomicPocError("manifest labels changed")
    inventory = manifest.get("files", [])
    if not isinstance(inventory, list):
        raise ContaminatedEconomicPocError("manifest inventory is not a list")
    inventory_paths = [str(item.get("path")) for item in inventory]
    if inventory_paths != _required_inventory_paths():
        raise ContaminatedEconomicPocError("POC required inventory changed")
    expected = {"manifest.json"}
    for item in inventory:
        if set(item) != {"path", "bytes", "sha256"}:
            raise ContaminatedEconomicPocError("manifest entry schema changed")
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ContaminatedEconomicPocError("unsafe manifest path")
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ContaminatedEconomicPocError("manifested artifact missing")
        if path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
            raise ContaminatedEconomicPocError("manifested artifact changed")
        expected.add(relative.as_posix())
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ContaminatedEconomicPocError("POC inventory is not closed")
    contract = _strict_json(root / "contract.json")
    _verify_artifact(
        contract,
        schema_version=f"{SCHEMA_VERSION}.contract",
        name="contract",
    )
    if (
        contract["contract"] != FROZEN_POC_CONTRACT
        or contract["contract_identity"] != poc_contract_identity()
    ):
        raise ContaminatedEconomicPocError("contract artifact changed")
    run = _strict_json(root / "run.json")
    _verify_artifact(run, schema_version=f"{SCHEMA_VERSION}.run", name="run")
    if run["run_identity"] != manifest["run_identity"]:
        raise ContaminatedEconomicPocError("run identity disagreement")
    if (
        run["dataset_fingerprint"]
        != FROZEN_POC_CONTRACT["dataset"]["dataset_fingerprint"]
        or run["partition_count"] != len(run["dataset_partition_records"])
        or run["source_tree_identity"]
        != canonical_hash(
            {
                "domain": f"{SCHEMA_VERSION}.source-tree",
                "source_sha256": run["source_sha256"],
            }
        )
    ):
        raise ContaminatedEconomicPocError("run source or dataset lineage changed")
    expected_run_identity = canonical_hash(
        {
            "domain": f"{SCHEMA_VERSION}.run",
            "contract_identity": poc_contract_identity(),
            "dataset_fingerprint": run["dataset_fingerprint"],
            "partition_records": run["dataset_partition_records"],
            "source_tree_identity": run["source_tree_identity"],
        }
    )
    if run["run_identity"] != expected_run_identity:
        raise ContaminatedEconomicPocError("run identity derivation changed")
    results: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    total_proposals = 0
    total_rejections = 0
    for runtime in RUNTIMES:
        trade_bundle = _strict_json(root / "trades" / f"{runtime.candidate_id}.json")
        result = _strict_json(root / "results" / f"{runtime.candidate_id}.json")
        _verify_artifact(
            trade_bundle,
            schema_version=f"{SCHEMA_VERSION}.trades",
            name=f"trade bundle:{runtime.candidate_id}",
        )
        _verify_artifact(
            result,
            schema_version=f"{SCHEMA_VERSION}.result",
            name=f"result:{runtime.candidate_id}",
        )
        if (
            trade_bundle["run_identity"] != run["run_identity"]
            or result["run_identity"] != run["run_identity"]
            or trade_bundle["candidate_id"] != runtime.candidate_id
            or result["candidate_id"] != runtime.candidate_id
        ):
            raise ContaminatedEconomicPocError("candidate/run lineage changed")
        expected_mechanism_identity = next(
            item["mechanism_identity"]
            for item in FROZEN_POC_CONTRACT["inclusion_policy"]["mechanisms"]
            if item["candidate_id"] == runtime.candidate_id
        )
        if result["mechanism_identity"] != expected_mechanism_identity:
            raise ContaminatedEconomicPocError("mechanism identity changed")
        if trade_bundle["identity"] != result["trade_bundle_identity"]:
            raise ContaminatedEconomicPocError("trade/result lineage changed")
        candidate_records = trade_bundle["trades"]
        if trade_bundle["trade_count"] != len(candidate_records):
            raise ContaminatedEconomicPocError("trade count changed")
        for record in candidate_records:
            identity = record.get("identity")
            record_base = {key: value for key, value in record.items() if key != "identity"}
            if identity != canonical_hash(record_base):
                raise ContaminatedEconomicPocError("trade identity changed")
        proposal_count = result["proposal_reconciliation"]["proposal_count"]
        rejected = result["proposal_reconciliation"]["rejected_proposal_count"]
        if proposal_count != len(candidate_records) + rejected:
            raise ContaminatedEconomicPocError("proposal reconciliation changed")
        expected_scenarios = {
            item["scenario"]: summarize_trade_records(
                candidate_records,
                item["scenario"],
                proposal_count=proposal_count,
                rejected_proposal_count=rejected,
            )
            for item in FROZEN_POC_CONTRACT["costs"]["scenarios"]
        }
        if result["scenarios"] != expected_scenarios:
            raise ContaminatedEconomicPocError("mechanism metrics changed")
        if result["exploratory_interpretation"] != exploratory_interpretation(
            expected_scenarios
        ):
            raise ContaminatedEconomicPocError("interpretation changed")
        total_proposals += proposal_count
        total_rejections += rejected
        records.extend(candidate_records)
        results.append(result)
    aggregate = _strict_json(root / "aggregate.json")
    _verify_artifact(
        aggregate,
        schema_version=f"{SCHEMA_VERSION}.aggregate",
        name="aggregate",
    )
    if (
        aggregate["run_identity"] != run["run_identity"]
        or aggregate["included_candidate_ids"]
        != [item.candidate_id for item in RUNTIMES]
        or aggregate["mechanism_result_identities"]
        != [item["identity"] for item in results]
    ):
        raise ContaminatedEconomicPocError("aggregate lineage changed")
    aggregate_scenarios = {
        item["scenario"]: summarize_trade_records(
            records,
            item["scenario"],
            proposal_count=total_proposals,
            rejected_proposal_count=total_rejections,
        )
        for item in FROZEN_POC_CONTRACT["costs"]["scenarios"]
    }
    if aggregate["scenarios"] != aggregate_scenarios:
        raise ContaminatedEconomicPocError("aggregate metrics changed")
    if aggregate["exploratory_interpretation"] != exploratory_interpretation(
        aggregate_scenarios
    ):
        raise ContaminatedEconomicPocError("aggregate interpretation changed")
    if (
        run["included_candidate_ids"] != [item.candidate_id for item in RUNTIMES]
        or run["trade_bundle_identities"]
        != [
            _strict_json(root / "trades" / f"{item.candidate_id}.json")["identity"]
            for item in RUNTIMES
        ]
        or run["result_identities"] != [item["identity"] for item in results]
        or run["aggregate_identity"] != aggregate["identity"]
    ):
        raise ContaminatedEconomicPocError("run artifact graph changed")
    if (root / "report.md").read_bytes() != _render_report(results, aggregate):
        raise ContaminatedEconomicPocError("report changed")
    return {
        "contract_identity": poc_contract_identity(),
        "run_identity": run["run_identity"],
        "manifest_identity": manifest["identity"],
        "verified": True,
    }
