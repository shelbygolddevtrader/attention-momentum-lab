"""Deterministic, write-once artifacts for portfolio simulation results.

The writer publishes a completed run directory atomically.  All data files are
written into a private sibling directory, ``run_metadata.json`` is written last
as the completion marker, and only then is the directory renamed into place.
The corresponding loader fails closed on missing, malformed, or hash-mismatched
artifacts and never recalculates trading outcomes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from aml.portfolio_simulator import (
    AUDIT_COLUMNS,
    LEDGER_COLUMNS,
    TRADE_COLUMNS,
    PortfolioConfig,
    PortfolioSimulationResult,
    StrategyProposal,
)


PORTFOLIO_ARTIFACT_SCHEMA_VERSION = "1.0.0"
PORTFOLIO_ENGINE_IDENTIFIER = "aml.portfolio_simulator.simulate_portfolio"
RUN_ID_LENGTH = 20

DATA_FILES = (
    "portfolio_summary.json",
    "strategy_ledgers.csv",
    "proposals.csv",
    "accepted_proposals.csv",
    "rejected_proposals.csv",
    "portfolio_trades.csv",
    "equity_curve.csv",
    "drawdown_curve.csv",
)
COMPLETION_MARKER = "run_metadata.json"
REQUIRED_FILES = DATA_FILES + (COMPLETION_MARKER,)
PROPOSAL_COLUMNS = [
    "proposal_id", "strategy_identifier", "strategy_version", "symbol",
    "signal_timestamp", "direction", "score_or_confidence",
    "intended_entry_timestamp", "intended_entry_price", "stop_kind",
    "stop_value", "target_kind", "target_value", "maximum_holding_minutes",
    "invalidation_reason", "provenance_json",
]
PERSISTED_TRADE_COLUMNS = TRADE_COLUMNS + [
    "cumulative_portfolio_pnl", "cumulative_strategy_pnl",
]
EQUITY_COLUMNS = [
    "event_sequence", "timestamp", "proposal_id", "strategy_identifier",
    "strategy_version", "net_pnl", "cumulative_portfolio_pnl", "portfolio_equity",
]
DRAWDOWN_COLUMNS = EQUITY_COLUMNS + ["peak_equity", "drawdown", "drawdown_fraction"]
CSV_SCHEMAS = {
    "strategy_ledgers.csv": LEDGER_COLUMNS,
    "proposals.csv": PROPOSAL_COLUMNS,
    "accepted_proposals.csv": AUDIT_COLUMNS,
    "rejected_proposals.csv": AUDIT_COLUMNS,
    "portfolio_trades.csv": PERSISTED_TRADE_COLUMNS,
    "equity_curve.csv": EQUITY_COLUMNS,
    "drawdown_curve.csv": DRAWDOWN_COLUMNS,
}
TIMESTAMP_COLUMNS = {
    "proposals.csv": ("signal_timestamp", "intended_entry_timestamp"),
    "accepted_proposals.csv": (
        "signal_timestamp", "intended_entry_timestamp", "decision_timestamp",
        "actual_entry_timestamp",
    ),
    "rejected_proposals.csv": (
        "signal_timestamp", "intended_entry_timestamp", "decision_timestamp",
        "actual_entry_timestamp",
    ),
    "portfolio_trades.csv": (
        "signal_timestamp", "intended_entry_timestamp", "actual_entry_timestamp",
        "exit_timestamp",
    ),
    "equity_curve.csv": ("timestamp",),
    "drawdown_curve.csv": ("timestamp",),
}
NUMERIC_COLUMNS = {
    "strategy_ledgers.csv": tuple(LEDGER_COLUMNS[2:]),
    "proposals.csv": (
        "score_or_confidence", "intended_entry_price", "stop_value", "target_value",
        "maximum_holding_minutes",
    ),
    "accepted_proposals.csv": (
        "score_or_confidence", "quantity", "capital_used", "position_risk",
    ),
    "rejected_proposals.csv": (
        "score_or_confidence", "quantity", "capital_used", "position_risk",
    ),
    "portfolio_trades.csv": tuple(
        column for column in PERSISTED_TRADE_COLUMNS
        if column not in {
            "proposal_id", "strategy_identifier", "strategy_version", "symbol",
            "signal_timestamp", "direction", "intended_entry_timestamp",
            "actual_entry_timestamp", "exit_timestamp", "exit_reason", "provenance_json",
        }
    ),
    "equity_curve.csv": (
        "event_sequence", "net_pnl", "cumulative_portfolio_pnl", "portfolio_equity",
    ),
    "drawdown_curve.csv": (
        "event_sequence", "net_pnl", "cumulative_portfolio_pnl", "portfolio_equity",
        "peak_equity", "drawdown", "drawdown_fraction",
    ),
}
REQUIRED_VALUE_COLUMNS = {
    "strategy_ledgers.csv": tuple(LEDGER_COLUMNS),
    "proposals.csv": tuple(
        column for column in PROPOSAL_COLUMNS
        if column not in {"intended_entry_price", "invalidation_reason"}
    ),
    "accepted_proposals.csv": tuple(
        column for column in AUDIT_COLUMNS if column != "invalidation_reason"
    ),
    "rejected_proposals.csv": tuple(
        column for column in AUDIT_COLUMNS
        if column not in {
            "invalidation_reason", "actual_entry_timestamp", "quantity", "capital_used",
            "position_risk",
        }
    ),
    "portfolio_trades.csv": tuple(
        column for column in PERSISTED_TRADE_COLUMNS if column != "intended_entry_price"
    ),
    "equity_curve.csv": tuple(EQUITY_COLUMNS),
    "drawdown_curve.csv": tuple(DRAWDOWN_COLUMNS),
}
SENSITIVE_KEY_PARTS = {
    "api_key", "apikey", "authorization", "credentials", "password",
    "access_token", "refresh_token", "secret",
}


class RunLabel(str, Enum):
    """Permitted non-production classifications for persisted runs."""

    SYNTHETIC = "synthetic"
    DEVELOPMENT = "development"
    VALIDATION = "validation"


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise ValueError("Metadata timestamps must be timezone-aware")
        return value.isoformat()
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if not isinstance(key, str) or not key:
                raise ValueError("Metadata keys must be non-empty strings")
            output[key] = _json_value(item)
        return output
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Metadata numbers must be finite")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"Value is not deterministically serializable: {type(value).__name__}")


def _freeze_json(value: Any) -> Any:
    normalized = _json_value(value)
    if isinstance(normalized, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(_freeze_json(item) for item in normalized)
    return normalized


def _reject_sensitive_keys(value: Any, location: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_").replace(" ", "_")
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                raise ValueError(f"Sensitive metadata key is not allowed in {location}: {key}")
            _reject_sensitive_keys(item, location)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_sensitive_keys(item, location)


def _reject_machine_paths(value: Any, location: str) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_machine_paths(item, location)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_machine_paths(item, location)
    elif isinstance(value, str) and (Path(value).is_absolute() or value.startswith("~")):
        raise ValueError(f"Machine-local paths are not allowed in {location}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON with a single trailing newline."""

    return (
        json.dumps(
            _json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _validate_hashes(hashes: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(hashes, Mapping) or not hashes:
        raise ValueError("At least one source/input hash is required")
    normalized: dict[str, str] = {}
    for key, digest in sorted(hashes.items()):
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Input hash names must be non-empty strings")
        logical_name = key.strip()
        _reject_sensitive_keys({logical_name: None}, "input hashes")
        if Path(logical_name).is_absolute() or logical_name.startswith("~"):
            raise ValueError("Input hash names must be logical identifiers, not local paths")
        if logical_name in normalized:
            raise ValueError(f"Duplicate normalized input hash name: {logical_name}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise ValueError(f"Input hash for {key!r} must be a SHA-256 digest")
        normalized[logical_name] = digest.lower()
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class PortfolioRunContext:
    """Immutable provenance required to identify and publish one portfolio run.

    ``execution_timestamp`` records when the engine was invoked but deliberately
    does not affect the deterministic run ID.  ``simulator_configuration`` holds
    execution-engine semantics distinct from the shared ``PortfolioConfig`` risk
    controls.  ``provenance`` must describe the source/selection context without
    credentials or mutable objects.
    """

    source_commit: str
    source_worktree_dirty: bool
    execution_timestamp: pd.Timestamp
    run_label: RunLabel
    simulator_configuration: Mapping[str, Any]
    input_hashes: Mapping[str, str]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_commit, str)
            or not 7 <= len(self.source_commit.strip()) <= 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_commit.strip().lower()
            )
        ):
            raise ValueError("source_commit must be a hexadecimal Git commit")
        object.__setattr__(self, "source_commit", self.source_commit.strip().lower())
        if not isinstance(self.source_worktree_dirty, bool):
            raise ValueError("source_worktree_dirty must be boolean")
        timestamp = pd.Timestamp(self.execution_timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("execution_timestamp must be timezone-aware")
        object.__setattr__(self, "execution_timestamp", timestamp.as_unit("ns"))
        try:
            label = RunLabel(self.run_label)
        except (TypeError, ValueError) as exc:
            raise ValueError("run_label must be synthetic, development, or validation") from exc
        object.__setattr__(self, "run_label", label)
        if not isinstance(self.simulator_configuration, Mapping) or not self.simulator_configuration:
            raise ValueError("simulator_configuration is required")
        _reject_sensitive_keys(self.simulator_configuration, "simulator configuration")
        _reject_sensitive_keys(self.provenance, "run provenance")
        _reject_machine_paths(self.simulator_configuration, "simulator configuration")
        _reject_machine_paths(self.provenance, "run provenance")
        simulator = _freeze_json(dict(self.simulator_configuration))
        provenance = _freeze_json(dict(self.provenance)) if isinstance(self.provenance, Mapping) else None
        if not provenance:
            raise ValueError("run provenance is required")
        object.__setattr__(self, "simulator_configuration", simulator)
        object.__setattr__(self, "input_hashes", _validate_hashes(self.input_hashes))
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True)
class CompletedPortfolioRun:
    """Validated persisted engine outputs exposed to read-only consumers."""

    directory: Path
    metadata: Mapping[str, Any]
    portfolio_summary: Mapping[str, Any]
    strategy_ledgers: pd.DataFrame
    proposals: pd.DataFrame
    accepted_proposals: pd.DataFrame
    rejected_proposals: pd.DataFrame
    portfolio_trades: pd.DataFrame
    equity_curve: pd.DataFrame
    drawdown_curve: pd.DataFrame


def file_sha256(path: Path) -> str:
    """Hash a finalized artifact file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_sha256(frame: pd.DataFrame) -> str:
    """Hash a frame using the artifact writer's deterministic CSV encoding."""

    return hashlib.sha256(_csv_bytes(frame)).hexdigest()


def _portfolio_config_payload(config: PortfolioConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["strategy_allocations"] = sorted(
        payload["strategy_allocations"],
        key=lambda item: (item["strategy_identifier"], item["strategy_version"]),
    )
    return _json_value(payload)


def _proposal_records(proposals: Sequence[StrategyProposal]) -> pd.DataFrame:
    records = [{
        "proposal_id": item.proposal_id,
        "strategy_identifier": item.strategy_identifier,
        "strategy_version": item.strategy_version,
        "symbol": item.symbol,
        "signal_timestamp": item.signal_timestamp,
        "direction": item.direction.value,
        "score_or_confidence": item.score_or_confidence,
        "intended_entry_timestamp": item.intended_entry_timestamp,
        "intended_entry_price": item.intended_entry_price,
        "stop_kind": item.stop.kind.value,
        "stop_value": item.stop.value,
        "target_kind": item.target.kind.value,
        "target_value": item.target.value,
        "maximum_holding_minutes": item.maximum_holding_minutes,
        "invalidation_reason": item.invalidation_reason,
        "provenance_json": json.dumps(
            _json_value(item.provenance), sort_keys=True, separators=(",", ":")
        ),
    } for item in proposals]
    frame = pd.DataFrame.from_records(records, columns=PROPOSAL_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["signal_timestamp", "strategy_identifier", "strategy_version", "symbol", "proposal_id"],
        kind="mergesort",
    ).reset_index(drop=True)


def _sorted_frame(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    copied = frame.copy(deep=True)
    available = [column for column in columns if column in copied]
    if available and not copied.empty:
        copied = copied.sort_values(available, kind="mergesort").reset_index(drop=True)
    return copied


def _trade_outputs(trades: pd.DataFrame, total_capital: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = _sorted_frame(
        trades,
        ["exit_timestamp", "strategy_identifier", "strategy_version", "symbol", "proposal_id"],
    )
    ordered["cumulative_portfolio_pnl"] = (
        ordered["net_pnl"].cumsum() if not ordered.empty else pd.Series(dtype=float)
    )
    ordered["cumulative_strategy_pnl"] = (
        ordered.groupby(["strategy_identifier", "strategy_version"], sort=True)["net_pnl"].cumsum()
        if not ordered.empty else pd.Series(dtype=float)
    )
    if ordered.empty:
        equity = pd.DataFrame(columns=EQUITY_COLUMNS)
    else:
        equity = pd.DataFrame({
            "event_sequence": np.arange(1, len(ordered) + 1),
            "timestamp": ordered["exit_timestamp"],
            "proposal_id": ordered["proposal_id"],
            "strategy_identifier": ordered["strategy_identifier"],
            "strategy_version": ordered["strategy_version"],
            "net_pnl": ordered["net_pnl"],
            "cumulative_portfolio_pnl": ordered["cumulative_portfolio_pnl"],
            "portfolio_equity": total_capital + ordered["cumulative_portfolio_pnl"],
        })
    if equity.empty:
        drawdown = pd.DataFrame(columns=DRAWDOWN_COLUMNS)
    else:
        drawdown = equity.copy(deep=True)
        drawdown["peak_equity"] = drawdown["portfolio_equity"].cummax().clip(lower=total_capital)
        drawdown["drawdown"] = drawdown["portfolio_equity"] - drawdown["peak_equity"]
        drawdown["drawdown_fraction"] = drawdown["drawdown"] / drawdown["peak_equity"]
    return ordered, equity, drawdown


def _reconciliation(
    result: PortfolioSimulationResult,
    proposals: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, Any]:
    summary = result.portfolio_summary
    ledger_pnl = float(result.strategy_ledgers["realized_pnl"].sum())
    portfolio_pnl = _finite(summary["realized_pnl"], "portfolio realized P&L")
    trade_pnl = float(trades["net_pnl"].sum()) if not trades.empty else 0.0
    total_capital = _finite(summary["total_capital"], "total capital")
    ending_equity = _finite(summary["ending_equity"], "ending equity")
    accepted = int(result.proposal_audit["status"].eq("accepted").sum())
    rejected = int(result.proposal_audit["status"].eq("rejected").sum())
    ledger_trades = int(result.strategy_ledgers["trade_count"].sum())
    checks = {
        "portfolio_pnl_equals_strategy_pnl": math.isclose(portfolio_pnl, ledger_pnl, abs_tol=1e-9),
        "portfolio_pnl_equals_trade_pnl": math.isclose(portfolio_pnl, trade_pnl, abs_tol=1e-9),
        "ending_equity_reconciles": math.isclose(
            ending_equity, total_capital + portfolio_pnl, abs_tol=1e-9
        ),
        "proposal_counts_reconcile": accepted + rejected == len(proposals),
        "trade_counts_reconcile": len(trades) == accepted == ledger_trades == int(summary["trade_count"]),
    }
    reconciliation = {
        **checks,
        "portfolio_realized_pnl": portfolio_pnl,
        "summed_strategy_realized_pnl": ledger_pnl,
        "summed_trade_net_pnl": trade_pnl,
        "pnl_reconciliation_delta": portfolio_pnl - ledger_pnl,
        "starting_equity": total_capital,
        "ending_equity": ending_equity,
        "reconciled_ending_equity": total_capital + portfolio_pnl,
        "proposal_count": len(proposals),
        "accepted_proposal_count": accepted,
        "rejected_proposal_count": rejected,
        "trade_count": len(trades),
        "summed_strategy_trade_count": ledger_trades,
    }
    if not all(checks.values()):
        failed = ", ".join(key for key, passed in checks.items() if not passed)
        raise ValueError(f"Portfolio result failed reconciliation: {failed}")
    return reconciliation


def _prepared_file_content(
    result: PortfolioSimulationResult,
    proposals: Sequence[StrategyProposal],
    config: PortfolioConfig,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    proposal_frame = _proposal_records(proposals)
    if proposal_frame["proposal_id"].duplicated().any():
        raise ValueError("Duplicate proposal identities cannot be persisted")
    audit = _sorted_frame(
        result.proposal_audit,
        ["decision_timestamp", "strategy_identifier", "strategy_version", "symbol", "proposal_id"],
    )
    accepted = audit.loc[audit["status"].eq("accepted")].reset_index(drop=True)
    rejected = audit.loc[audit["status"].eq("rejected")].reset_index(drop=True)
    trades, equity, drawdown = _trade_outputs(result.trades, config.total_capital)
    ledgers = _sorted_frame(result.strategy_ledgers, ["strategy_identifier", "strategy_version"])
    reconciliation = _reconciliation(result, proposal_frame, trades)
    summary = {**_json_value(dict(result.portfolio_summary)), "reconciliation": reconciliation}
    frames = {
        "strategy_ledgers.csv": ledgers,
        "proposals.csv": proposal_frame,
        "accepted_proposals.csv": accepted,
        "rejected_proposals.csv": rejected,
        "portfolio_trades.csv": trades,
        "equity_curve.csv": equity,
        "drawdown_curve.csv": drawdown,
    }
    for filename, frame in frames.items():
        _validate_artifact_frame(frame, filename)
    content = {
        "portfolio_summary.json": canonical_json_bytes(summary),
        **{filename: _csv_bytes(frame) for filename, frame in frames.items()},
    }
    return content, reconciliation


def _run_id_from_artifact_hashes(
    *,
    source_commit: str,
    source_worktree_dirty: bool,
    run_label: str,
    simulator_configuration: Mapping[str, Any],
    portfolio_risk_configuration: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    provenance: Mapping[str, Any],
    artifact_hashes: Mapping[str, str],
) -> str:
    payload = {
        "schema_version": PORTFOLIO_ARTIFACT_SCHEMA_VERSION,
        "engine": PORTFOLIO_ENGINE_IDENTIFIER,
        "source_commit": source_commit,
        "source_worktree_dirty": source_worktree_dirty,
        "run_label": run_label,
        "simulator_configuration": simulator_configuration,
        "portfolio_risk_configuration": portfolio_risk_configuration,
        "input_hashes": input_hashes,
        "provenance": provenance,
        "artifact_hashes": artifact_hashes,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:RUN_ID_LENGTH]


def deterministic_portfolio_run_id(
    result: PortfolioSimulationResult,
    proposals: Sequence[StrategyProposal],
    config: PortfolioConfig,
    context: PortfolioRunContext,
) -> str:
    """Derive stable identity from every data artifact, source, and configuration."""

    content, _ = _prepared_file_content(result, proposals, config)
    artifact_hashes = {
        filename: hashlib.sha256(content[filename]).hexdigest() for filename in DATA_FILES
    }
    return _run_id_from_artifact_hashes(
        source_commit=context.source_commit,
        source_worktree_dirty=context.source_worktree_dirty,
        run_label=context.run_label.value,
        simulator_configuration=context.simulator_configuration,
        portfolio_risk_configuration=_portfolio_config_payload(config),
        input_hashes=context.input_hashes,
        provenance=context.provenance,
        artifact_hashes=artifact_hashes,
    )


def portfolio_artifact_directory(root: Path, run_id: str) -> Path:
    """Resolve a contained run directory beneath the supplied artifact root."""

    if (
        not isinstance(run_id, str)
        or len(run_id) != RUN_ID_LENGTH
        or any(character not in "0123456789abcdef" for character in run_id)
    ):
        raise ValueError("Invalid deterministic portfolio run ID")
    base = Path(root).resolve()
    unresolved = base / run_id
    if unresolved.is_symlink():
        raise ValueError("Portfolio artifact destination cannot be a symlink")
    destination = unresolved.resolve()
    if destination.parent != base:
        raise ValueError("Portfolio artifact path escapes its root")
    return destination


def _csv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy(deep=True)
    for column in output.columns:
        if isinstance(output[column].dtype, pd.DatetimeTZDtype):
            output[column] = output[column].map(
                lambda value: "" if pd.isna(value) else pd.Timestamp(value).isoformat()
            )
        elif output[column].dtype == object:
            output[column] = output[column].map(
                lambda value: pd.Timestamp(value).isoformat()
                if isinstance(value, (pd.Timestamp, datetime, date)) and not pd.isna(value)
                else value
            )
    return output


def _validate_csv_values(frame: pd.DataFrame, name: str) -> None:
    numeric = frame.select_dtypes(include=[np.number])
    if not numeric.empty and np.isinf(numeric.to_numpy(dtype=float)).any():
        raise ValueError(f"{name} contains infinite numeric values")
    for column in frame.select_dtypes(include=["object"]).columns:
        for value in frame[column]:
            if value is None or value is pd.NA or value is pd.NaT:
                continue
            if isinstance(value, float) and math.isnan(value):
                continue
            if not isinstance(
                value,
                (str, int, float, bool, np.integer, np.floating, pd.Timestamp, datetime, date),
            ):
                raise ValueError(
                    f"{name}.{column} contains unsupported value type: {type(value).__name__}"
                )


def _validate_artifact_frame(frame: pd.DataFrame, filename: str) -> None:
    expected_columns = CSV_SCHEMAS[filename]
    if frame.columns.tolist() != expected_columns:
        raise ValueError(f"Portfolio artifact has incompatible columns: {filename}")
    _validate_csv_values(frame, filename)
    if frame.loc[:, REQUIRED_VALUE_COLUMNS[filename]].isna().any().any():
        raise ValueError(f"Portfolio artifact has missing required values: {filename}")
    for column in NUMERIC_COLUMNS[filename]:
        if pd.api.types.is_bool_dtype(frame[column].dtype):
            raise ValueError(f"Portfolio artifact numeric column is boolean: {filename}.{column}")
        try:
            values = pd.to_numeric(frame[column].dropna(), errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Portfolio artifact has malformed numeric values: {filename}.{column}"
            ) from exc
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Portfolio artifact has non-finite values: {filename}.{column}")
    for column in TIMESTAMP_COLUMNS.get(filename, ()):
        for value in frame[column].dropna():
            try:
                timestamp = pd.Timestamp(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Portfolio artifact has malformed timestamps: {filename}.{column}"
                ) from exc
            if timestamp.tzinfo is None:
                raise ValueError(
                    f"Portfolio artifact timestamp lost timezone: {filename}.{column}"
                )


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    _validate_csv_values(frame, "CSV artifact")
    return _csv_frame(frame).to_csv(
        index=False,
        lineterminator="\n",
        na_rep="",
        float_format="%.17g",
    ).encode("utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_portfolio_run(
    artifact_root: Path,
    result: PortfolioSimulationResult,
    proposals: Sequence[StrategyProposal],
    config: PortfolioConfig,
    context: PortfolioRunContext,
) -> Path:
    """Atomically publish one immutable, fully reconciled portfolio run.

    The caller retains ownership of all frames and proposals.  A pre-existing
    completed run is never overwritten.  Any exception removes the unpublished
    temporary directory and leaves no destination directory behind.
    """

    if not isinstance(result, PortfolioSimulationResult):
        raise ValueError("result must be a PortfolioSimulationResult")
    if not isinstance(config, PortfolioConfig):
        raise ValueError("config must be a PortfolioConfig")
    if not isinstance(context, PortfolioRunContext):
        raise ValueError("context must be a PortfolioRunContext")
    if isinstance(proposals, (str, bytes)) or not isinstance(proposals, Sequence):
        raise ValueError("proposals must be a sequence")
    file_content, reconciliation = _prepared_file_content(result, proposals, config)
    artifact_hashes = {
        filename: hashlib.sha256(file_content[filename]).hexdigest()
        for filename in DATA_FILES
    }
    run_id = _run_id_from_artifact_hashes(
        source_commit=context.source_commit,
        source_worktree_dirty=context.source_worktree_dirty,
        run_label=context.run_label.value,
        simulator_configuration=context.simulator_configuration,
        portfolio_risk_configuration=_portfolio_config_payload(config),
        input_hashes=context.input_hashes,
        provenance=context.provenance,
        artifact_hashes=artifact_hashes,
    )
    root = Path(artifact_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = portfolio_artifact_directory(root, run_id)
    lock_path = root / f".{run_id}.lock"
    try:
        lock_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f"Portfolio run is locked or already publishing: {run_id}") from exc
    os.close(lock_descriptor)

    temporary: Path | None = None
    try:
        if destination.exists():
            raise FileExistsError(f"Completed portfolio run already exists: {destination}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=root))
        for filename in DATA_FILES:
            _write_bytes(temporary / filename, file_content[filename])
        finalized_hashes = {
            filename: file_sha256(temporary / filename) for filename in DATA_FILES
        }
        if finalized_hashes != artifact_hashes:
            raise OSError("Finalized portfolio artifact hashes changed during publication")
        metadata = {
            "status": "completed",
            "schema_version": PORTFOLIO_ARTIFACT_SCHEMA_VERSION,
            "run_id": run_id,
            "run_label": context.run_label.value,
            "execution_timestamp": context.execution_timestamp.isoformat(),
            "source_commit": context.source_commit,
            "source_worktree_dirty": context.source_worktree_dirty,
            "engine": PORTFOLIO_ENGINE_IDENTIFIER,
            "strategy_versions": [
                {"strategy_identifier": allocation.strategy_identifier,
                 "strategy_version": allocation.strategy_version}
                for allocation in sorted(
                    config.strategy_allocations,
                    key=lambda item: (item.strategy_identifier, item.strategy_version),
                )
            ],
            "simulator_configuration": context.simulator_configuration,
            "portfolio_risk_configuration": _portfolio_config_payload(config),
            "fixed_allocations": [
                {
                    "strategy_identifier": item.strategy_identifier,
                    "strategy_version": item.strategy_version,
                    "allocated_capital": item.allocated_capital,
                }
                for item in sorted(
                    config.strategy_allocations,
                    key=lambda item: (item.strategy_identifier, item.strategy_version),
                )
            ],
            "input_hashes": context.input_hashes,
            "provenance": context.provenance,
            "artifact_hashes": finalized_hashes,
            "reconciliation": reconciliation,
        }
        _write_bytes(temporary / COMPLETION_MARKER, canonical_json_bytes(metadata))
        _fsync_directory(temporary)
        if destination.exists():
            raise FileExistsError(f"Completed portfolio run already exists: {destination}")
        os.rename(temporary, destination)
        _fsync_directory(root)
    except Exception:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        lock_path.unlink(missing_ok=True)
    return destination


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed portfolio artifact JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Portfolio artifact JSON must be an object: {path.name}")
    return value


def load_portfolio_run(directory: Path) -> CompletedPortfolioRun:
    """Load only a completed, compatible, hash-verified portfolio run."""

    unresolved_directory = Path(directory)
    if unresolved_directory.is_symlink():
        raise ValueError("Portfolio run directory cannot be a symlink")
    directory = unresolved_directory.resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Portfolio run directory does not exist: {directory}")
    metadata_path = directory / COMPLETION_MARKER
    if not metadata_path.is_file():
        raise ValueError("Portfolio run is incomplete: run_metadata.json is absent")
    metadata = _read_json(metadata_path)
    if metadata.get("status") != "completed":
        raise ValueError("Portfolio run metadata is not marked completed")
    if metadata.get("schema_version") != PORTFOLIO_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("Portfolio run artifact schema is incompatible")
    run_id = metadata.get("run_id")
    if run_id != directory.name:
        raise ValueError("Portfolio run ID does not match its directory")
    portfolio_artifact_directory(directory.parent, directory.name)
    missing = [filename for filename in REQUIRED_FILES if not (directory / filename).is_file()]
    if missing:
        raise ValueError(f"Portfolio run is incomplete: missing {', '.join(missing)}")
    entries = {path.name for path in directory.iterdir()}
    if entries != set(REQUIRED_FILES):
        unexpected = sorted(entries.difference(REQUIRED_FILES))
        raise ValueError(
            "Portfolio run contains unexpected files: " + ", ".join(unexpected)
        )
    if any((directory / filename).is_symlink() for filename in REQUIRED_FILES):
        raise ValueError("Portfolio run artifacts cannot be symlinks")
    hashes = metadata.get("artifact_hashes")
    if not isinstance(hashes, dict) or set(hashes) != set(DATA_FILES):
        raise ValueError("Portfolio run metadata has an invalid artifact hash manifest")
    for filename in DATA_FILES:
        if hashes[filename] != file_sha256(directory / filename):
            raise ValueError(f"Portfolio artifact hash mismatch: {filename}")
    required_metadata = {
        "source_commit", "source_worktree_dirty", "execution_timestamp", "engine",
        "strategy_versions",
        "simulator_configuration", "portfolio_risk_configuration", "fixed_allocations",
        "input_hashes", "provenance", "reconciliation",
    }
    if missing_metadata := required_metadata.difference(metadata):
        raise ValueError(
            "Portfolio run metadata is incomplete: " + ", ".join(sorted(missing_metadata))
        )
    try:
        PortfolioRunContext(
            source_commit=metadata["source_commit"],
            source_worktree_dirty=metadata["source_worktree_dirty"],
            execution_timestamp=metadata["execution_timestamp"],
            run_label=metadata["run_label"],
            simulator_configuration=metadata["simulator_configuration"],
            input_hashes=metadata["input_hashes"],
            provenance=metadata["provenance"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Portfolio run context metadata is malformed") from exc
    if metadata["engine"] != PORTFOLIO_ENGINE_IDENTIFIER:
        raise ValueError("Portfolio run engine is incompatible")
    if not isinstance(metadata["portfolio_risk_configuration"], dict):
        raise ValueError("Portfolio risk configuration metadata is malformed")
    if not isinstance(metadata["fixed_allocations"], list) or not metadata["fixed_allocations"]:
        raise ValueError("Fixed-allocation metadata is malformed")
    if not isinstance(metadata["strategy_versions"], list) or not metadata["strategy_versions"]:
        raise ValueError("Strategy-version metadata is malformed")
    configured_allocations = metadata["portfolio_risk_configuration"].get(
        "strategy_allocations"
    )
    if configured_allocations != metadata["fixed_allocations"]:
        raise ValueError("Fixed allocations disagree with portfolio risk configuration")
    expected_versions = [
        {
            "strategy_identifier": item["strategy_identifier"],
            "strategy_version": item["strategy_version"],
        }
        for item in metadata["fixed_allocations"]
    ]
    if expected_versions != metadata["strategy_versions"]:
        raise ValueError("Strategy versions disagree with fixed allocations")
    expected_run_id = _run_id_from_artifact_hashes(
        source_commit=metadata["source_commit"],
        source_worktree_dirty=metadata["source_worktree_dirty"],
        run_label=metadata["run_label"],
        simulator_configuration=metadata["simulator_configuration"],
        portfolio_risk_configuration=metadata["portfolio_risk_configuration"],
        input_hashes=metadata["input_hashes"],
        provenance=metadata["provenance"],
        artifact_hashes=hashes,
    )
    if expected_run_id != run_id:
        raise ValueError("Portfolio run identity does not match its metadata and artifacts")
    summary = _read_json(directory / "portfolio_summary.json")
    if summary.get("reconciliation") != metadata.get("reconciliation"):
        raise ValueError("Portfolio reconciliation metadata disagrees with the summary")
    reconciliation = metadata["reconciliation"]
    required_checks = {
        "portfolio_pnl_equals_strategy_pnl", "portfolio_pnl_equals_trade_pnl",
        "ending_equity_reconciles", "proposal_counts_reconcile", "trade_counts_reconcile",
    }
    if not isinstance(reconciliation, dict) or not all(
        reconciliation.get(check) is True for check in required_checks
    ):
        raise ValueError("Portfolio run reconciliation is absent or failed")

    def csv(filename: str) -> pd.DataFrame:
        try:
            frame = pd.read_csv(directory / filename)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise ValueError(f"Malformed portfolio artifact CSV: {filename}") from exc
        _validate_artifact_frame(frame, filename)
        return frame

    strategy_ledgers = csv("strategy_ledgers.csv")
    proposals = csv("proposals.csv")
    accepted = csv("accepted_proposals.csv")
    rejected = csv("rejected_proposals.csv")
    trades = csv("portfolio_trades.csv")
    equity = csv("equity_curve.csv")
    drawdown = csv("drawdown_curve.csv")
    ledger_allocations = strategy_ledgers[[
        "strategy_identifier", "strategy_version", "allocated_capital"
    ]].to_dict("records")
    if ledger_allocations != metadata["fixed_allocations"]:
        raise ValueError("Strategy ledgers disagree with fixed allocations")
    try:
        configured_total = float(metadata["portfolio_risk_configuration"]["total_capital"])
        summary_total = float(summary["total_capital"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Portfolio total-capital metadata is malformed") from exc
    if not math.isclose(configured_total, summary_total, abs_tol=1e-9):
        raise ValueError("Portfolio summary disagrees with configured total capital")
    try:
        persisted_values = {
            "portfolio_realized_pnl": float(summary["realized_pnl"]),
            "summed_strategy_realized_pnl": float(strategy_ledgers["realized_pnl"].sum()),
            "summed_trade_net_pnl": float(trades["net_pnl"].sum()) if not trades.empty else 0.0,
            "proposal_count": len(proposals),
            "accepted_proposal_count": len(accepted),
            "rejected_proposal_count": len(rejected),
            "trade_count": len(trades),
            "summed_strategy_trade_count": int(strategy_ledgers["trade_count"].sum()),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Portfolio artifacts lack required reconciliation fields") from exc
    for key, actual in persisted_values.items():
        expected = reconciliation.get(key)
        if isinstance(actual, float):
            matches = isinstance(expected, (int, float)) and math.isclose(
                actual, float(expected), abs_tol=1e-8
            )
        else:
            matches = actual == expected
        if not matches:
            raise ValueError(f"Persisted portfolio reconciliation failed: {key}")
    if len(accepted) + len(rejected) != len(proposals):
        raise ValueError("Persisted proposal counts do not reconcile")
    if len(trades) != len(accepted):
        raise ValueError("Persisted trade counts do not reconcile")
    try:
        proposal_ids = Counter(proposals["proposal_id"].astype(str))
        decision_ids = Counter(
            pd.concat([accepted["proposal_id"], rejected["proposal_id"]], ignore_index=True)
            .astype(str)
        )
        accepted_ids = Counter(accepted["proposal_id"].astype(str))
        trade_ids = Counter(trades["proposal_id"].astype(str))
    except KeyError as exc:
        raise ValueError("Portfolio artifacts lack proposal identity fields") from exc
    if proposal_ids != decision_ids:
        raise ValueError("Persisted proposal decisions do not match proposed identities")
    if accepted_ids != trade_ids:
        raise ValueError("Persisted trades do not match accepted proposal identities")
    if not accepted.empty and not accepted["status"].eq("accepted").all():
        raise ValueError("Accepted proposal artifact contains another status")
    if not rejected.empty and not rejected["status"].eq("rejected").all():
        raise ValueError("Rejected proposal artifact contains another status")

    return CompletedPortfolioRun(
        directory=directory,
        metadata=MappingProxyType(metadata),
        portfolio_summary=MappingProxyType(summary),
        strategy_ledgers=strategy_ledgers,
        proposals=proposals,
        accepted_proposals=accepted,
        rejected_proposals=rejected,
        portfolio_trades=trades,
        equity_curve=equity,
        drawdown_curve=drawdown,
    )


def discover_completed_runs(artifact_root: Path) -> list[Path]:
    """Return validated completed run paths in deterministic newest-first order."""

    root = Path(artifact_root)
    if not root.exists():
        return []
    completed: list[tuple[pd.Timestamp, str, Path]] = []
    for path in sorted(
        (item for item in root.iterdir() if item.is_dir() and not item.is_symlink()),
        key=lambda item: item.name,
    ):
        try:
            run = load_portfolio_run(path)
            timestamp = pd.Timestamp(run.metadata["execution_timestamp"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        completed.append((timestamp, path.name, path.resolve()))
    return [item[2] for item in sorted(completed, key=lambda item: (item[0], item[1]), reverse=True)]
