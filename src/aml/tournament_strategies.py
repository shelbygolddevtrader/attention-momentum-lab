"""Typed, point-in-time strategy definitions for research tournaments."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from aml.portfolio_simulator import Direction
from aml.signals import SignalConfig, add_features


class DirectionSupport(str, Enum):
    LONG = "long"
    SHORT = "short"
    BOTH = "both"


@dataclass(frozen=True)
class NormalizedSignal:
    """Outcome-free intent available only after its source minute has closed."""

    symbol: str
    signal_timestamp: pd.Timestamp
    direction: Direction
    confidence: float
    strategy_id: str
    strategy_version: str
    parameter_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.signal_timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("signal_timestamp must be timezone-aware")
        if not self.symbol or not self.strategy_id or not self.strategy_version:
            raise ValueError("Signal identity fields must be non-empty")
        if not math.isfinite(float(self.confidence)) or not 0 <= float(self.confidence) <= 100:
            raise ValueError("Signal confidence must be within [0, 100]")
        if len(self.parameter_hash) != 64:
            raise ValueError("parameter_hash must be SHA-256")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "signal_timestamp", timestamp.as_unit("ns"))
        object.__setattr__(self, "direction", Direction(self.direction))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "metadata", MappingProxyType(dict(sorted(self.metadata.items()))))


@runtime_checkable
class StrategyDefinition(Protocol):
    strategy_id: str
    strategy_version: str
    description: str
    direction_support: DirectionSupport
    required_lookback: int
    parameters: Mapping[str, Any]
    parameter_hash: str

    def evaluate(self, bars: pd.DataFrame) -> tuple[NormalizedSignal, ...]: ...


@dataclass(frozen=True)
class ParameterRule:
    kind: type
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[Any, ...] = ()

    def validate(self, name: str, value: Any) -> Any:
        if self.kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        elif self.kind is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            value = float(value)
        elif self.kind is bool:
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be boolean")
        elif self.kind is str:
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{name} must be at least {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{name} must be at most {self.maximum}")
        if self.choices and value not in self.choices:
            raise ValueError(f"{name} must be one of {self.choices}")
        return value


def parameter_hash(parameters: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _prepare_bars(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    if missing := required.difference(bars.columns):
        raise ValueError(f"Strategy bars are missing: {', '.join(sorted(missing))}")
    frame = bars.loc[:, [*required, *( ["bar_vwap"] if "bar_vwap" in bars else [])]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if frame.empty:
        return frame.sort_values("timestamp").reset_index(drop=True)
    if frame["timestamp"].dt.tz is None:
        raise ValueError("Strategy bar timestamps must be timezone-aware")
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("Strategy bar timestamps must be unique")
    if frame["symbol"].astype(str).str.upper().nunique() != 1:
        raise ValueError("Each strategy evaluation requires one symbol")
    numeric = frame[["open", "high", "low", "close", "volume"]]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all() or (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Strategy bars contain invalid numeric values")
    return frame


def trailing_indicators(frame: pd.DataFrame, *, volume_window: int = 20) -> pd.DataFrame:
    """Indicators whose row i uses only bars at or before i; baselines exclude i."""
    output = frame.copy()
    price = (
        output["bar_vwap"].fillna(output["close"])
        if "bar_vwap" in output else (output["high"] + output["low"] + output["close"]) / 3
    )
    cumulative_volume = output["volume"].cumsum().replace(0, np.nan)
    output["session_vwap"] = (price * output["volume"]).cumsum() / cumulative_volume
    prior_volume = output["volume"].shift(1).rolling(volume_window, min_periods=min(5, volume_window)).median()
    output["relative_volume"] = output["volume"] / prior_volume.replace(0, np.nan)
    delta = output["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    output["rsi_14"] = 100 - 100 / (1 + relative_strength)
    output.loc[(loss == 0) & (gain > 0), "rsi_14"] = 100
    return output


def ema_pair(frame: pd.DataFrame, fast_period: int, slow_period: int) -> tuple[pd.Series, pd.Series]:
    """Return causal exponential averages using current and earlier closes only."""
    if not 1 < fast_period < slow_period:
        raise ValueError("EMA periods must satisfy 1 < fast < slow")
    return (
        frame["close"].ewm(span=fast_period, adjust=False).mean(),
        frame["close"].ewm(span=slow_period, adjust=False).mean(),
    )


def _clock_at_or_before(frame: pd.DataFrame, cutoff: str) -> pd.Series:
    hour, minute = map(int, cutoff.split(":"))
    values = frame["timestamp"].dt.hour * 60 + frame["timestamp"].dt.minute
    return values <= hour * 60 + minute


def _clock_between(frame: pd.DataFrame, start: str, end: str) -> pd.Series:
    values = frame["timestamp"].dt.hour * 60 + frame["timestamp"].dt.minute
    start_h, start_m = map(int, start.split(":"))
    end_h, end_m = map(int, end.split(":"))
    return values.between(start_h * 60 + start_m, end_h * 60 + end_m)


def _signals(
    frame: pd.DataFrame,
    mask: pd.Series,
    strategy: ConfiguredStrategy,
    score: pd.Series | float,
    reason: str,
    metadata_columns: Mapping[str, str] | None = None,
) -> tuple[NormalizedSignal, ...]:
    records = []
    values = pd.Series(score, index=frame.index) if np.isscalar(score) else score
    for index in frame.index[mask.fillna(False)]:
        source_timestamp = pd.Timestamp(frame.at[index, "timestamp"])
        metadata = {
            "reason_code": reason,
            "source_bar_timestamp": source_timestamp.isoformat(),
            "information_cutoff": (source_timestamp + pd.Timedelta(1, unit="min")).isoformat(),
            "bar_timestamp_semantics": "left_labeled",
        }
        for output_name, column_name in (metadata_columns or {}).items():
            value = frame.at[index, column_name]
            metadata[output_name] = None if pd.isna(value) else (
                bool(value) if isinstance(value, (bool, np.bool_)) else float(value)
            )
        records.append(NormalizedSignal(
            symbol=str(frame.at[index, "symbol"]),
            signal_timestamp=source_timestamp + pd.Timedelta(1, unit="min"),
            direction=Direction.LONG,
            confidence=float(np.clip(values.at[index], 0, 100)),
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.strategy_version,
            parameter_hash=strategy.parameter_hash,
            metadata=metadata,
        ))
    return tuple(records)


Evaluator = Callable[[pd.DataFrame, "ConfiguredStrategy"], tuple[NormalizedSignal, ...]]


@dataclass(frozen=True)
class ConfiguredStrategy:
    strategy_id: str
    strategy_version: str
    description: str
    direction_support: DirectionSupport
    required_lookback: int
    parameters: Mapping[str, Any]
    _evaluator: Evaluator = field(repr=False, compare=False)
    parameter_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(sorted(self.parameters.items()))))
        object.__setattr__(self, "parameter_hash", parameter_hash(self.parameters))

    def evaluate(self, bars: pd.DataFrame) -> tuple[NormalizedSignal, ...]:
        return self._evaluator(_prepare_bars(bars), self)


def _opening_range(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    duration = p["opening_range_minutes"]
    indicators = trailing_indicators(frame, volume_window=20)
    opening_high = indicators["high"].iloc[:duration].max()
    threshold = opening_high * (1 + p["breakout_buffer"])
    prior_close = indicators["close"].shift(1)
    mask = (
        (indicators.index >= duration)
        & indicators["close"].gt(threshold)
        & prior_close.le(threshold)
        & indicators["relative_volume"].ge(p["minimum_relative_volume"])
        & _clock_at_or_before(indicators, p["signal_cutoff_time"])
    )
    score = 50 + 25 * (indicators["close"] / threshold - 1).clip(lower=0) / 0.01 + 10 * indicators["relative_volume"].clip(upper=3)
    return _signals(indicators, mask, strategy, score, "opening_range_breakout")


def _vwap_reclaim(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    indicators = trailing_indicators(frame, volume_window=20)
    distance = indicators["close"] / indicators["session_vwap"] - 1
    prior_below = distance.shift(1).rolling(10, min_periods=1).min().le(-p["minimum_distance_below_vwap"])
    confirmed = distance.gt(0).rolling(p["confirmation_bars"]).sum().eq(p["confirmation_bars"])
    trigger = confirmed & ~confirmed.shift(1, fill_value=False)
    mask = (
        prior_below & trigger & distance.le(p["maximum_distance_above_vwap_at_entry"])
        & indicators["relative_volume"].ge(p["minimum_relative_volume"])
    )
    score = 55 + indicators["relative_volume"].clip(upper=4) * 8
    return _signals(indicators, mask, strategy, score, "vwap_reclaim_confirmed")


def _vwap_mean_reversion(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    indicators = trailing_indicators(frame, volume_window=20)
    distance = indicators["close"] / indicators["session_vwap"] - 1
    was_extended = distance.shift(1).le(-p["minimum_vwap_deviation"])
    confirmation = indicators["close"].gt(indicators["close"].shift(1))
    if p["confirmation_bars"] > 1:
        confirmation = confirmation.rolling(p["confirmation_bars"]).sum().eq(p["confirmation_bars"])
    rsi_ok = True if not p["use_rsi_filter"] else indicators["rsi_14"].le(p["maximum_rsi"])
    mask = (
        was_extended & confirmation & rsi_ok
        & distance.lt(0)
        & _clock_between(indicators, p["start_time"], p["end_time"])
    )
    mask &= ~mask.shift(1, fill_value=False)
    score = 60 + (-distance / p["minimum_vwap_deviation"]).clip(upper=2) * 10
    return _signals(indicators, mask, strategy, score, "conservative_vwap_mean_reversion")


def _ema_momentum(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    indicators = trailing_indicators(frame, volume_window=20)
    fast, slow = ema_pair(indicators, p["fast_ema_period"], p["slow_ema_period"])
    crossed = fast.gt(slow) & fast.shift(1).le(slow.shift(1))
    momentum = fast.pct_change(3) / 3
    mask = (
        crossed & momentum.ge(p["minimum_momentum_per_bar"])
        & indicators["relative_volume"].ge(p["minimum_relative_volume"])
        & _clock_at_or_before(indicators, p["session_cutoff_time"])
    )
    score = 55 + momentum.clip(lower=0) / max(p["minimum_momentum_per_bar"], 1e-9) * 10
    return _signals(indicators, mask, strategy, score, "ema_momentum_cross")


def _volume_breakout(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    indicators = trailing_indicators(frame, volume_window=p["volume_lookback"])
    prior_high = indicators["high"].shift(1).rolling(
        p["price_breakout_lookback"], min_periods=p["price_breakout_lookback"]
    ).max()
    breakout = indicators["close"].gt(prior_high)
    confirmed = breakout.rolling(p["confirmation_bars"]).sum().eq(p["confirmation_bars"])
    trigger = confirmed & ~confirmed.shift(1, fill_value=False)
    mask = (
        trigger & indicators["relative_volume"].ge(p["volume_multiple"])
        & _clock_at_or_before(indicators, p["session_cutoff_time"])
    )
    score = 50 + indicators["relative_volume"].clip(upper=5) * 10
    return _signals(indicators, mask, strategy, score, "volume_spike_breakout")


def _attention_momentum(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    p = strategy.parameters
    enriched = attention_momentum_feature_frame(frame, strategy)
    enriched["eligibility_threshold"] = float(p["eligible_score_threshold"])
    return _signals(
        enriched, enriched["eligible"].astype(bool), strategy,
        enriched["score"].astype(float), "existing_attention_momentum_eligible",
        {
            "raw_return_feature": "return_5m",
            "relative_volume_feature": "relative_volume",
            "vwap_distance_feature": "vwap_distance",
            "acceleration_feature": "volume_acceleration",
            "return_score_component": "return_score_component",
            "relative_volume_score_component": "relative_volume_score_component",
            "vwap_score_component": "vwap_score_component",
            "acceleration_score_component": "acceleration_score_component",
            "total_score": "score",
            "eligibility_threshold": "eligibility_threshold",
            "eligible": "eligible",
        },
    )


def attention_momentum_feature_frame(
    bars: pd.DataFrame, strategy: ConfiguredStrategy, *, exact_elapsed_return: bool = True
) -> pd.DataFrame:
    """Return the exact causal feature frame used by attention momentum."""
    if strategy.strategy_id != "attention_momentum":
        raise ValueError("attention_momentum strategy is required")
    frame = _prepare_bars(bars)
    p = strategy.parameters
    return add_features(frame, SignalConfig(
        return_window=p["return_window"], volume_window=p["volume_window"],
        acceleration_window=p["acceleration_window"], return_threshold=p["return_threshold"],
        relative_volume_threshold=p["relative_volume_threshold"],
        vwap_threshold=p["vwap_threshold"], acceleration_threshold=p["acceleration_threshold"],
        eligible_score_threshold=p["eligible_score_threshold"],
    ), exact_elapsed_return=exact_elapsed_return)


def _no_trade(frame: pd.DataFrame, strategy: ConfiguredStrategy):
    return ()


STRATEGY_SPECS = {
    "opening_range_breakout": {
        "description": "Long breakout above a fixed opening range with trailing relative-volume confirmation.",
        "lookback": 20, "evaluator": _opening_range,
        "rules": {
            "opening_range_minutes": ParameterRule(int, 5, 60),
            "breakout_buffer": ParameterRule(float, 0, 0.05),
            "minimum_relative_volume": ParameterRule(float, 0, 20),
            "signal_cutoff_time": ParameterRule(str),
        },
    },
    "vwap_reclaim": {
        "description": "Long confirmed reclaim of trailing session VWAP after a measurable move below it.",
        "lookback": 20, "evaluator": _vwap_reclaim,
        "rules": {
            "confirmation_bars": ParameterRule(int, 1, 5),
            "minimum_distance_below_vwap": ParameterRule(float, 0.0001, 0.20),
            "minimum_relative_volume": ParameterRule(float, 0, 20),
            "maximum_distance_above_vwap_at_entry": ParameterRule(float, 0, 0.10),
        },
    },
    "vwap_mean_reversion": {
        "description": "Conservative long reversion after an oversold move below trailing session VWAP.",
        "lookback": 20, "evaluator": _vwap_mean_reversion,
        "rules": {
            "minimum_vwap_deviation": ParameterRule(float, 0.001, 0.30),
            "use_rsi_filter": ParameterRule(bool), "maximum_rsi": ParameterRule(float, 1, 60),
            "confirmation_bars": ParameterRule(int, 1, 5),
            "start_time": ParameterRule(str), "end_time": ParameterRule(str),
        },
    },
    "ema_momentum_cross": {
        "description": "Long fast-over-slow EMA cross with trailing volume and slope confirmation.",
        "lookback": 30, "evaluator": _ema_momentum,
        "rules": {
            "fast_ema_period": ParameterRule(int, 2, 50), "slow_ema_period": ParameterRule(int, 3, 200),
            "minimum_relative_volume": ParameterRule(float, 0, 20),
            "minimum_momentum_per_bar": ParameterRule(float, 0, 0.10),
            "session_cutoff_time": ParameterRule(str),
        },
    },
    "volume_spike_breakout": {
        "description": "Long trailing-price breakout accompanied by abnormal one-minute volume.",
        "lookback": 30, "evaluator": _volume_breakout,
        "rules": {
            "volume_lookback": ParameterRule(int, 5, 120), "volume_multiple": ParameterRule(float, 1, 20),
            "price_breakout_lookback": ParameterRule(int, 2, 120),
            "confirmation_bars": ParameterRule(int, 1, 5), "session_cutoff_time": ParameterRule(str),
        },
    },
    "attention_momentum": {
        "description": "Compatibility adapter over the existing attention-momentum feature and eligibility engine.",
        "lookback": 20, "evaluator": _attention_momentum,
        "rules": {
            "return_window": ParameterRule(int, 1, 120), "volume_window": ParameterRule(int, 5, 120),
            "acceleration_window": ParameterRule(int, 2, 60), "return_threshold": ParameterRule(float, 0, 1),
            "relative_volume_threshold": ParameterRule(float, 0, 50), "vwap_threshold": ParameterRule(float, -1, 1),
            "acceleration_threshold": ParameterRule(float, 0, 50), "eligible_score_threshold": ParameterRule(int, 0, 100),
        },
    },
    "no_trade": {
        "description": "Passive no-trade control with identical data coverage and zero market exposure.",
        "lookback": 0, "evaluator": _no_trade, "rules": {},
    },
}


def build_strategy(strategy_id: str, version: str, parameters: Mapping[str, Any]) -> ConfiguredStrategy:
    if strategy_id not in STRATEGY_SPECS:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    if not isinstance(version, str) or not version:
        raise ValueError("strategy version must be non-empty")
    spec = STRATEGY_SPECS[strategy_id]
    rules = spec["rules"]
    if set(parameters) != set(rules):
        raise ValueError(
            f"Invalid parameters for {strategy_id}: unknown={sorted(set(parameters) - set(rules))}, "
            f"missing={sorted(set(rules) - set(parameters))}"
        )
    validated = {name: rules[name].validate(name, parameters[name]) for name in sorted(rules)}
    if strategy_id == "ema_momentum_cross" and validated["fast_ema_period"] >= validated["slow_ema_period"]:
        raise ValueError("fast_ema_period must be less than slow_ema_period")
    return ConfiguredStrategy(
        strategy_id, version, spec["description"], DirectionSupport.LONG,
        spec["lookback"], validated, spec["evaluator"],
    )
