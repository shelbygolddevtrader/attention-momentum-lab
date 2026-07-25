"""Run a deterministic synthetic-only V0.1.1 observational-shadow rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from aml.portfolio_simulator import (
    Direction,
    PortfolioConfig,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)
from aml.shadow_context import (
    PnlClassification,
    SHADOW_STRATEGY_SPECS,
    ShadowOutcomeRecord,
    compute_intraday_confirmation,
    observation_for_signal,
    segregate_shadow_pnl,
)
from aml.tournament_config import load_tournament_config


REHEARSAL_VERSION = "aml.v011-shadow-rehearsal.v001"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _bars() -> pd.DataFrame:
    periods = 80
    timestamps = pd.date_range(
        "2024-01-02 09:30", periods=periods, freq="min", tz="America/New_York"
    )
    close = np.full(periods, 100.0)
    volume = np.full(periods, 100.0)
    close[25:] = 104.0
    volume[25] = 1_000.0
    return pd.DataFrame({
        "timestamp": timestamps, "symbol": "SYNTH", "open": close,
        "high": close + 0.2, "low": close - 0.2, "close": close,
        "volume": volume, "bar_vwap": close,
    })


def _proposal(signal) -> StrategyProposal:
    return StrategyProposal(
        strategy_identifier=signal.strategy_id,
        strategy_version=signal.strategy_version,
        symbol=signal.symbol,
        signal_timestamp=signal.signal_timestamp,
        direction=Direction.LONG,
        score_or_confidence=signal.confidence,
        intended_entry_timestamp=signal.signal_timestamp,
        intended_entry_price=None,
        stop=PriceLevel.fraction(0.015),
        target=PriceLevel.fraction(0.03),
        maximum_holding_minutes=30,
        provenance={"parameter_hash": signal.parameter_hash, "synthetic_only": True},
    )


def _simulate(proposal: StrategyProposal, bars: pd.DataFrame):
    config = PortfolioConfig(
        total_capital=2_000,
        strategy_allocations=(StrategyAllocation("attention_momentum", "0.1.1", 2_000),),
        maximum_position_risk_fraction=0.005,
        maximum_concurrent_positions=1,
        maximum_symbol_concentration_fraction=1,
        maximum_strategy_concentration_fraction=1,
        daily_loss_limit_fraction=1,
        slippage_fraction=0.001,
    )
    return simulate_portfolio([proposal], {"SYNTH": bars}, config)


def rehearsal(root: Path) -> dict[str, bytes]:
    strategy = next(
        item for item in load_tournament_config(
            root / "config" / "strategy_tournament_baseline.yaml"
        ).strategies
        if item.strategy_id == "attention_momentum"
    )
    bars = _bars()
    before = strategy.evaluate(bars)
    if not before:
        raise RuntimeError("Synthetic rehearsal did not generate a V0.1.1 signal")
    proposal_before = _proposal(before[0])
    result_before = _simulate(proposal_before, bars)
    context = observation_for_signal(
        before[0],
        proposal_id=proposal_before.proposal_id,
        intraday=compute_intraday_confirmation(bars, before[0].signal_timestamp),
        missing_context_reasons=(
            "cross_sectional_source_unavailable_in_synthetic_fixture",
            "premarket_source_unavailable_in_synthetic_fixture",
        ),
    )
    after = strategy.evaluate(bars)
    proposal_after = _proposal(after[0])
    result_after = _simulate(proposal_after, bars)
    audit_parity = result_before.proposal_audit.equals(result_after.proposal_audit)
    trade_parity = result_before.trades.equals(result_after.trades)
    summary_parity = result_before.portfolio_summary == result_after.portfolio_summary
    signal_parity = before == after
    identity_parity = proposal_before.proposal_id == proposal_after.proposal_id
    if not all((audit_parity, trade_parity, summary_parity, signal_parity, identity_parity)):
        raise RuntimeError("V0.1.1 behavioral parity failed")
    shadows = (
        ShadowOutcomeRecord(
            proposal_before.proposal_id,
            "rejected_v011_counterfactual", "0.1.1-shadow",
            PnlClassification.REJECTED_SHADOW, 1.0,
            "maximum_concurrent_positions",
        ),
        ShadowOutcomeRecord(
            "synthetic-shadow-001", "attention_continuation_shadow", "0.1.0-spec",
            PnlClassification.STRATEGY_SHADOW, -1.0, None,
        ),
    )
    deployed_pnl = float(result_before.portfolio_summary["realized_pnl"])
    segregated = dict(segregate_shadow_pnl(shadows, deployed_pnl))
    summary = {
        "rehearsal_version": REHEARSAL_VERSION,
        "fixture": "synthetic_only",
        "holdout_accessed": False,
        "strategy_id": strategy.strategy_id,
        "strategy_version": strategy.strategy_version,
        "parameter_hash": strategy.parameter_hash,
        "signal_count_before": len(before),
        "signal_count_after": len(after),
        "signal_parity": signal_parity,
        "proposal_identity_parity": identity_parity,
        "proposal_audit_parity": audit_parity,
        "trade_pnl_parity": trade_parity,
        "portfolio_summary_parity": summary_parity,
        "context_is_parallel_non_decision_record": True,
        "missing_context_is_explicit": bool(context.missing_context_reasons),
        "shadow_pnl_segregated": segregated,
        "shadow_strategy_specifications": [spec.strategy_id for spec in SHADOW_STRATEGY_SPECS],
    }
    shadow_rows = pd.DataFrame([
        {
            "proposal_id": item.proposal_id,
            "shadow_strategy_id": item.shadow_strategy_id,
            "shadow_strategy_version": item.shadow_strategy_version,
            "classification": item.classification.value,
            "shadow_net_pnl": item.shadow_net_pnl,
            "deployed": item.deployed,
            "capital_allocation": item.capital_allocation,
            "included_in_portfolio_pnl": item.included_in_portfolio_pnl,
            "rejection_reason": item.rejection_reason,
        }
        for item in shadows
    ]).sort_values(["classification", "proposal_id"], kind="mergesort")
    return {
        "rehearsal_summary.json": _canonical(summary),
        "signal_observation.json": (context.canonical_json() + "\n").encode(),
        "shadow_outcomes.csv": shadow_rows.to_csv(
            index=False, lineterminator="\n", float_format="%.17g"
        ).encode(),
    }


def publish(output_root: Path, generated: dict[str, bytes]) -> Path:
    identity = {
        "rehearsal_version": REHEARSAL_VERSION,
        "configuration": "synthetic_fixed_v001",
        "generated_hashes": {name: _sha(value) for name, value in sorted(generated.items())},
    }
    rehearsal_id = _sha(_canonical(identity))[:24]
    destination = output_root / rehearsal_id
    manifest = _canonical({**identity, "rehearsal_id": rehearsal_id})
    if destination.exists():
        if (destination / "rehearsal_manifest.json").read_bytes() != manifest:
            raise ValueError("Existing rehearsal manifest differs")
        for name, expected in identity["generated_hashes"].items():
            if _sha((destination / name).read_bytes()) != expected:
                raise ValueError(f"Existing rehearsal artifact differs: {name}")
        return destination
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{rehearsal_id}.", dir=output_root))
    for name, value in generated.items():
        (temporary / name).write_bytes(value)
    (temporary / "rehearsal_manifest.json").write_bytes(manifest)
    os.replace(temporary, destination)
    return destination


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    destination = publish(args.output_root, rehearsal(args.root.resolve()))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
