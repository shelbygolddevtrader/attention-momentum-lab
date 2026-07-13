"""Focused tests for deterministic, immutable portfolio-run artifacts."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pandas as pd
import pytest

import aml.portfolio_artifacts as artifacts
from aml.portfolio_artifacts import (
    DATA_FILES,
    PortfolioRunContext,
    RunLabel,
    deterministic_portfolio_run_id,
    discover_completed_runs,
    load_portfolio_run,
    write_portfolio_run,
)
from aml.portfolio_simulator import (
    Direction,
    PortfolioConfig,
    PortfolioSimulationResult,
    PriceLevel,
    StrategyAllocation,
    StrategyProposal,
    simulate_portfolio,
)


START = pd.Timestamp("2024-01-02 09:30", tz="America/New_York")


def bars(symbol: str) -> pd.DataFrame:
    """Return deterministic synthetic input bars."""

    frame = pd.DataFrame({
        "timestamp": pd.date_range(START, periods=10, freq="min"),
        "symbol": symbol,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
    })
    if symbol == "AAA":
        frame.loc[2, "high"] = 103.0
    return frame


def proposal(strategy: str, symbol: str) -> StrategyProposal:
    """Create one valid synthetic strategy proposal."""

    return StrategyProposal(
        strategy_identifier=strategy,
        strategy_version="1.0.0",
        symbol=symbol,
        signal_timestamp=START,
        direction=Direction.LONG,
        score_or_confidence=70.0,
        intended_entry_timestamp=START + pd.Timedelta(1, unit="min"),
        intended_entry_price=100.0,
        stop=PriceLevel.fraction(0.02),
        target=PriceLevel.fraction(0.02),
        maximum_holding_minutes=5,
        provenance={"source": "synthetic_test", "outcome_free": True},
    )


@pytest.fixture
def run_inputs():
    """Build a reconciled two-strategy simulation and fixed run context."""

    proposals = [proposal("alpha", "AAA"), proposal("beta", "BBB")]
    config = PortfolioConfig(
        total_capital=2_000.0,
        strategy_allocations=(
            StrategyAllocation("alpha", "1.0.0", 1_000.0),
            StrategyAllocation("beta", "1.0.0", 1_000.0),
        ),
        maximum_position_risk_fraction=0.02,
        maximum_concurrent_positions=2,
        maximum_symbol_concentration_fraction=1.0,
        maximum_strategy_concentration_fraction=1.0,
        slippage_fraction=0.0,
    )
    inputs = {"AAA": bars("AAA"), "BBB": bars("BBB")}
    result = simulate_portfolio(proposals, inputs, config)
    context = PortfolioRunContext(
        source_commit="a" * 40,
        source_worktree_dirty=False,
        execution_timestamp=pd.Timestamp("2024-01-03T12:00:00Z"),
        run_label=RunLabel.SYNTHETIC,
        simulator_configuration={"engine": "simulate_portfolio", "revision": 1},
        input_hashes={
            symbol: artifacts.dataframe_sha256(frame)
            for symbol, frame in sorted(inputs.items())
        },
        provenance={"purpose": "artifact_test", "performance_evidence": False},
    )
    return result, proposals, config, context


def test_run_id_is_deterministic_and_execution_time_independent(run_inputs) -> None:
    result, proposals, config, context = run_inputs
    first = deterministic_portfolio_run_id(result, proposals, config, context)
    later = replace(
        context, execution_timestamp=pd.Timestamp("2025-01-03T12:00:00Z")
    )
    assert deterministic_portfolio_run_id(result, list(reversed(proposals)), config, later) == first
    changed = replace(context, run_label=RunLabel.VALIDATION)
    assert deterministic_portfolio_run_id(result, proposals, config, changed) != first
    dirty = replace(context, source_worktree_dirty=True)
    assert deterministic_portfolio_run_id(result, proposals, config, dirty) != first
    reordered_config = replace(
        config, strategy_allocations=tuple(reversed(config.strategy_allocations))
    )
    assert deterministic_portfolio_run_id(
        result, proposals, reordered_config, context
    ) == first


def test_file_contents_are_deterministic_and_metadata_is_success_marker(
    tmp_path: Path, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    first = write_portfolio_run(tmp_path / "one", result, proposals, config, context)
    second = write_portfolio_run(tmp_path / "two", result, proposals, config, context)
    assert first.name == second.name
    assert [path.name for path in first.iterdir()] == [path.name for path in second.iterdir()]
    for filename in (*DATA_FILES, "run_metadata.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    loaded = load_portfolio_run(first)
    assert loaded.metadata["status"] == "completed"
    assert loaded.metadata["run_label"] == "synthetic"
    assert loaded.portfolio_trades["cumulative_portfolio_pnl"].iloc[-1] == pytest.approx(
        loaded.portfolio_summary["realized_pnl"]
    )


def test_completed_runs_are_write_once(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    write_portfolio_run(tmp_path, result, proposals, config, context)
    with pytest.raises(FileExistsError, match="already exists"):
        write_portfolio_run(tmp_path, result, proposals, config, context)


def test_atomic_failure_leaves_no_run_or_partial_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    original = artifacts._write_bytes
    calls = 0

    def fail_during_publication(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated write failure")
        original(path, content)

    monkeypatch.setattr(artifacts, "_write_bytes", fail_during_publication)
    with pytest.raises(OSError, match="simulated"):
        write_portfolio_run(tmp_path, result, proposals, config, context)
    assert list(tmp_path.iterdir()) == []


def test_metadata_is_written_after_all_data_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    original = artifacts._write_bytes
    order: list[str] = []

    def record(path: Path, content: bytes) -> None:
        order.append(path.name)
        original(path, content)

    monkeypatch.setattr(artifacts, "_write_bytes", record)
    write_portfolio_run(tmp_path, result, proposals, config, context)
    assert order == [*DATA_FILES, "run_metadata.json"]


def test_writer_rejects_failed_reconciliation(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    malformed_summary = dict(result.portfolio_summary)
    malformed_summary["realized_pnl"] = float(malformed_summary["realized_pnl"]) + 1
    malformed = PortfolioSimulationResult(
        result.proposal_audit,
        result.trades,
        result.strategy_ledgers,
        malformed_summary,
    )
    with pytest.raises(ValueError, match="reconciliation"):
        write_portfolio_run(tmp_path, malformed, proposals, config, context)
    assert list(tmp_path.iterdir()) == []


def test_loader_rejects_incomplete_hash_mismatch_and_malformed_metadata(
    tmp_path: Path, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    (directory / "portfolio_trades.csv").write_text("corrupt\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_portfolio_run(directory)

    other_root = tmp_path / "other"
    other = write_portfolio_run(
        other_root,
        result,
        proposals,
        config,
        replace(context, run_label=RunLabel.DEVELOPMENT),
    )
    (other / "run_metadata.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        load_portfolio_run(other)

    incomplete = tmp_path / ("b" * 20)
    incomplete.mkdir()
    with pytest.raises(ValueError, match="incomplete"):
        load_portfolio_run(incomplete)


@pytest.mark.parametrize("label", list(RunLabel))
def test_explicit_nonproduction_labels_are_persisted(
    tmp_path: Path, run_inputs, label: RunLabel
) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(
        tmp_path / label.value,
        result,
        proposals,
        config,
        replace(context, run_label=label),
    )
    assert load_portfolio_run(directory).metadata["run_label"] == label.value


def test_discovery_returns_only_valid_completed_runs(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    completed = write_portfolio_run(tmp_path, result, proposals, config, context)
    incomplete = tmp_path / ("f" * 20)
    incomplete.mkdir()
    (incomplete / "portfolio_summary.json").write_text("{}", encoding="utf-8")
    assert discover_completed_runs(tmp_path) == [completed.resolve()]


def test_context_requires_hashes_labels_provenance_and_aware_time() -> None:
    base = {
        "source_commit": "a" * 40,
        "source_worktree_dirty": False,
        "execution_timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
        "run_label": RunLabel.DEVELOPMENT,
        "simulator_configuration": {"engine": "test"},
        "input_hashes": {"bars": "b" * 64},
        "provenance": {"purpose": "test"},
    }
    with pytest.raises(ValueError, match="timezone-aware"):
        PortfolioRunContext(**{**base, "execution_timestamp": pd.Timestamp("2024-01-01")})
    with pytest.raises(ValueError, match="SHA-256"):
        PortfolioRunContext(**{**base, "input_hashes": {"bars": "not-a-hash"}})
    with pytest.raises(ValueError, match="run_label"):
        PortfolioRunContext(**{**base, "run_label": "production"})
    with pytest.raises(ValueError, match="provenance"):
        PortfolioRunContext(**{**base, "provenance": {}})


def test_writer_does_not_mutate_engine_frames(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    audit = result.proposal_audit.copy(deep=True)
    trades = result.trades.copy(deep=True)
    ledgers = result.strategy_ledgers.copy(deep=True)
    write_portfolio_run(tmp_path, result, proposals, config, context)
    pd.testing.assert_frame_equal(result.proposal_audit, audit)
    pd.testing.assert_frame_equal(result.trades, trades)
    pd.testing.assert_frame_equal(result.strategy_ledgers, ledgers)


def test_loader_rejects_reconciliation_disagreement(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    metadata_path = directory / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["reconciliation"]["trade_counts_reconcile"] = False
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    with pytest.raises(ValueError, match="disagrees"):
        load_portfolio_run(directory)


def test_loader_rejects_malformed_context_even_with_untampered_data_files(
    tmp_path: Path, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    metadata_path = directory / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source_commit"] = "not-a-commit"
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    with pytest.raises(ValueError, match="context metadata is malformed"):
        load_portfolio_run(directory)


def test_duplicate_proposal_identities_fail_closed(tmp_path: Path, run_inputs) -> None:
    _, proposals, config, context = run_inputs
    duplicates = [proposals[0], proposals[0]]
    result = simulate_portfolio(duplicates, {"AAA": bars("AAA")}, config)
    with pytest.raises(ValueError, match="Duplicate proposal identities"):
        write_portfolio_run(tmp_path, result, duplicates, config, context)


def test_zero_proposal_and_zero_trade_runs_round_trip(tmp_path: Path, run_inputs) -> None:
    _, _, config, context = run_inputs
    empty = simulate_portfolio([], {}, config)
    empty_run = load_portfolio_run(
        write_portfolio_run(tmp_path / "empty", empty, [], config, context)
    )
    assert empty_run.proposals.empty
    assert empty_run.accepted_proposals.empty
    assert empty_run.rejected_proposals.empty
    assert empty_run.portfolio_trades.empty
    assert empty_run.strategy_ledgers["trade_count"].eq(0).all()

    invalid = replace(proposal("alpha", "AAA"), invalidation_reason="stale")
    rejected = simulate_portfolio([invalid], {"AAA": bars("AAA")}, config)
    rejected_run = load_portfolio_run(
        write_portfolio_run(
            tmp_path / "rejected",
            rejected,
            [invalid],
            config,
            replace(context, run_label=RunLabel.DEVELOPMENT),
        )
    )
    assert rejected_run.accepted_proposals.empty
    assert len(rejected_run.rejected_proposals) == 1
    assert rejected_run.portfolio_trades.empty


def test_short_trade_and_timestamp_offsets_are_preserved(tmp_path: Path, run_inputs) -> None:
    _, _, config, context = run_inputs
    short = replace(proposal("alpha", "AAA"), direction=Direction.SHORT)
    result = simulate_portfolio([short], {"AAA": bars("AAA")}, config)
    run = load_portfolio_run(
        write_portfolio_run(tmp_path, result, [short], config, context)
    )
    assert run.proposals.iloc[0]["direction"] == "short"
    assert run.portfolio_trades.iloc[0]["direction"] == "short"
    assert pd.Timestamp(run.proposals.iloc[0]["signal_timestamp"]).tzinfo is not None
    assert pd.Timestamp(run.portfolio_trades.iloc[0]["exit_timestamp"]).tzinfo is not None


def test_stale_lock_fails_closed_and_is_not_discovered(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    run_id = deterministic_portfolio_run_id(result, proposals, config, context)
    lock = tmp_path / f".{run_id}.lock"
    lock.write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError, match="locked"):
        write_portfolio_run(tmp_path, result, proposals, config, context)
    assert lock.exists()
    assert discover_completed_runs(tmp_path) == []


def test_loader_rejects_extra_files_symlinks_and_schema_tampering(
    tmp_path: Path, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path / "extra", result, proposals, config, context)
    (directory / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected files"):
        load_portfolio_run(directory)

    target = write_portfolio_run(
        tmp_path / "target",
        result,
        proposals,
        config,
        replace(context, run_label=RunLabel.VALIDATION),
    )
    link = tmp_path / "link" / target.name
    link.parent.mkdir()
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        load_portfolio_run(link)
    assert discover_completed_runs(link.parent) == []

    schema_run = write_portfolio_run(
        tmp_path / "schema",
        result,
        proposals,
        config,
        replace(context, provenance={"purpose": "schema_tamper"}),
    )
    ledger_path = schema_run / "strategy_ledgers.csv"
    ledger = pd.read_csv(ledger_path)
    ledger["unexpected"] = 1
    ledger.to_csv(ledger_path, index=False, lineterminator="\n")
    metadata_path = schema_run / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["artifact_hashes"]["strategy_ledgers.csv"] = artifacts.file_sha256(ledger_path)
    new_run_id = artifacts._run_id_from_artifact_hashes(
        source_commit=metadata["source_commit"],
        source_worktree_dirty=metadata["source_worktree_dirty"],
        run_label=metadata["run_label"],
        simulator_configuration=metadata["simulator_configuration"],
        portfolio_risk_configuration=metadata["portfolio_risk_configuration"],
        input_hashes=metadata["input_hashes"],
        provenance=metadata["provenance"],
        artifact_hashes=metadata["artifact_hashes"],
    )
    metadata["run_id"] = new_run_id
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    schema_run = schema_run.rename(schema_run.with_name(new_run_id))
    with pytest.raises(ValueError, match="incompatible columns"):
        load_portfolio_run(schema_run)


def test_sensitive_or_machine_local_provenance_fails_closed(run_inputs) -> None:
    _, _, _, context = run_inputs
    with pytest.raises(ValueError, match="Sensitive metadata key"):
        replace(context, provenance={"api_key": "do-not-store"})
    with pytest.raises(ValueError, match="Machine-local paths"):
        replace(context, provenance={"input": "/Users/example/private.csv"})
    with pytest.raises(ValueError, match="source_worktree_dirty"):
        replace(context, source_worktree_dirty=1)


def test_loaded_frame_mutation_does_not_change_persisted_truth(
    tmp_path: Path, run_inputs
) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    loaded = load_portfolio_run(directory)
    loaded.strategy_ledgers.loc[0, "realized_pnl"] = 999_999
    reloaded = load_portfolio_run(directory)
    assert reloaded.strategy_ledgers.loc[0, "realized_pnl"] != 999_999


def test_valid_but_tampered_identity_metadata_is_rejected(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    metadata_path = directory / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source_commit"] = "b" * 40
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    with pytest.raises(ValueError, match="run identity"):
        load_portfolio_run(directory)


def test_rehashed_boolean_in_numeric_column_is_rejected(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    trades_path = directory / "portfolio_trades.csv"
    trades = pd.read_csv(trades_path, dtype=str)
    trades.loc[0, "quantity"] = "True"
    trades.to_csv(trades_path, index=False, lineterminator="\n")
    metadata_path = directory / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["artifact_hashes"]["portfolio_trades.csv"] = artifacts.file_sha256(trades_path)
    new_run_id = artifacts._run_id_from_artifact_hashes(
        source_commit=metadata["source_commit"],
        source_worktree_dirty=metadata["source_worktree_dirty"],
        run_label=metadata["run_label"],
        simulator_configuration=metadata["simulator_configuration"],
        portfolio_risk_configuration=metadata["portfolio_risk_configuration"],
        input_hashes=metadata["input_hashes"],
        provenance=metadata["provenance"],
        artifact_hashes=metadata["artifact_hashes"],
    )
    metadata["run_id"] = new_run_id
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    directory = directory.rename(directory.with_name(new_run_id))
    with pytest.raises(ValueError, match="malformed numeric values"):
        load_portfolio_run(directory)


def test_redundant_allocation_metadata_cannot_diverge(tmp_path: Path, run_inputs) -> None:
    result, proposals, config, context = run_inputs
    directory = write_portfolio_run(tmp_path, result, proposals, config, context)
    metadata_path = directory / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["fixed_allocations"][0]["allocated_capital"] += 1
    metadata_path.write_bytes(artifacts.canonical_json_bytes(metadata))
    with pytest.raises(ValueError, match="Fixed allocations disagree"):
        load_portfolio_run(directory)
