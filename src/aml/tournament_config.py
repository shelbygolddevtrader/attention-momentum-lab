"""Strict configuration and protected chronological splits for tournaments."""

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from aml.portfolio_simulator import PortfolioConfig, StrategyAllocation
from aml.tournament_strategies import ConfiguredStrategy, build_strategy


@dataclass(frozen=True)
class DatasetSplit:
    name: str
    start: date
    end: date
    protected: bool = False


FIXED_SPLITS = MappingProxyType({
    "development": DatasetSplit("development", date(2023, 7, 24), date(2024, 12, 31)),
    "validation": DatasetSplit("validation", date(2025, 1, 1), date(2025, 12, 31)),
    "holdout": DatasetSplit("holdout", date(2026, 1, 1), date(2026, 7, 23), True),
})


@dataclass(frozen=True)
class ExecutionAssumptions:
    starting_capital: float
    risk_fraction: float
    stop_fraction: float
    target_fraction: float
    entry_delay_bars: int
    maximum_entry_delay_minutes: int
    maximum_holding_minutes: int
    slippage_fraction: float
    cooldown_minutes: int
    commission_per_trade: float
    maximum_missing_regular_fraction: float

    def __post_init__(self) -> None:
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        for name in ("risk_fraction", "stop_fraction", "target_fraction"):
            if not 0 < getattr(self, name) < 1:
                raise ValueError(f"{name} must be within (0, 1)")
        if not 0 <= self.slippage_fraction < 1:
            raise ValueError("slippage_fraction must be within [0, 1)")
        if self.entry_delay_bars != 1:
            raise ValueError("Tournament v1 requires next-bar-open execution")
        if self.cooldown_minutes != 0 or self.commission_per_trade != 0:
            raise ValueError("Tournament v1 locks unsupported cooldown and commissions to zero")
        if self.maximum_holding_minutes < 1 or self.maximum_entry_delay_minutes < 0:
            raise ValueError("Execution time limits are invalid")
        if not 0 <= self.maximum_missing_regular_fraction <= 1:
            raise ValueError("maximum_missing_regular_fraction must be within [0, 1]")

    def portfolio_config(self, strategy: ConfiguredStrategy) -> PortfolioConfig:
        return PortfolioConfig(
            total_capital=self.starting_capital,
            strategy_allocations=(StrategyAllocation(
                strategy.strategy_id, strategy.strategy_version, self.starting_capital
            ),),
            maximum_position_risk_fraction=self.risk_fraction,
            maximum_concurrent_positions=1,
            maximum_symbol_concentration_fraction=1.0,
            maximum_strategy_concentration_fraction=1.0,
            daily_loss_limit_fraction=1.0,
            slippage_fraction=self.slippage_fraction,
            maximum_entry_delay_minutes=self.maximum_entry_delay_minutes,
        )


@dataclass(frozen=True)
class ScoringConfig:
    minimum_trades: int
    concentration_warning_fraction: float
    near_zero_exposure_fraction: float

    def __post_init__(self) -> None:
        if self.minimum_trades < 1:
            raise ValueError("minimum_trades must be positive")
        for name in ("concentration_warning_fraction", "near_zero_exposure_fraction"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be within (0, 1]")


@dataclass(frozen=True)
class TournamentConfig:
    configuration_version: str
    dataset_manifest: str
    artifact_root: str
    execution: ExecutionAssumptions
    scoring: ScoringConfig
    strategies: tuple[ConfiguredStrategy, ...]
    configuration_hash: str
    raw_payload: Mapping[str, Any]


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _strict_fields(payload: Mapping[str, Any], expected: set[str], location: str) -> None:
    if set(payload) != expected:
        raise ValueError(
            f"Invalid {location} fields: unknown={sorted(set(payload) - expected)}, "
            f"missing={sorted(expected - set(payload))}"
        )


def load_tournament_config(path: Path) -> TournamentConfig:
    """Load the repository's JSON-compatible YAML format without a new parser dependency."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed tournament configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Tournament configuration must be an object")
    _strict_fields(
        payload,
        {"configuration_version", "dataset_manifest", "artifact_root", "execution", "scoring", "strategies"},
        "tournament configuration",
    )
    if not isinstance(payload["strategies"], list) or not payload["strategies"]:
        raise ValueError("strategies must be a non-empty list")
    execution_fields = set(ExecutionAssumptions.__dataclass_fields__)
    scoring_fields = set(ScoringConfig.__dataclass_fields__)
    _strict_fields(payload["execution"], execution_fields, "execution")
    _strict_fields(payload["scoring"], scoring_fields, "scoring")
    execution = ExecutionAssumptions(**payload["execution"])
    scoring = ScoringConfig(**payload["scoring"])
    strategies = []
    identities = set()
    for record in payload["strategies"]:
        if not isinstance(record, dict):
            raise ValueError("Each strategy configuration must be an object")
        _strict_fields(record, {"strategy_id", "strategy_version", "parameters"}, "strategy")
        strategy = build_strategy(record["strategy_id"], record["strategy_version"], record["parameters"])
        if strategy.strategy_id in identities:
            raise ValueError(f"Duplicate configured strategy: {strategy.strategy_id}")
        identities.add(strategy.strategy_id)
        strategies.append(strategy)
    configuration_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return TournamentConfig(
        str(payload["configuration_version"]), str(payload["dataset_manifest"]),
        str(payload["artifact_root"]), execution, scoring, tuple(strategies),
        configuration_hash, MappingProxyType(payload),
    )


def select_splits(names: list[str] | tuple[str, ...], *, include_holdout: bool) -> tuple[DatasetSplit, ...]:
    if not names:
        names = ("development", "validation")
    unknown = set(names).difference(FIXED_SPLITS)
    if unknown:
        raise ValueError(f"Unknown dataset splits: {', '.join(sorted(unknown))}")
    if "holdout" in names and not include_holdout:
        raise ValueError("Holdout is protected; rerun with --include-holdout")
    if include_holdout and "holdout" not in names:
        names = tuple(names) + ("holdout",)
    return tuple(FIXED_SPLITS[name] for name in FIXED_SPLITS if name in names)


def execution_payload(execution: ExecutionAssumptions) -> dict[str, Any]:
    return asdict(execution)
