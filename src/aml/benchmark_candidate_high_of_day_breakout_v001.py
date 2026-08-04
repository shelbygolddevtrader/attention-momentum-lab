"""Point-in-time implementation of one frozen Library V001 hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Mapping

import numpy as np
import pandas as pd

from aml.portfolio_simulator import Direction, PriceLevel, StrategyProposal


CANDIDATE_ID = "high-of-day-breakout-continuation-v001"
CANDIDATE_VERSION = "1.0.0"
REQUIRED_COLUMNS = frozenset(
    {"timestamp", "symbol", "open", "high", "low", "close", "volume", "spread_bps"}
)
IDENTITY_FIELDS = (
    "hypothesis_identity",
    "specification_identity",
    "preregistration_identity",
    "implementation_binding_identity",
    "dataset_identity",
)


class HighOfDayCandidateIntegrityError(ValueError):
    """Input violates integrity rather than merely lacking evidence."""


@dataclass(frozen=True, slots=True)
class HighOfDayDecision:
    status: Literal["proposal", "no_signal", "unavailable"]
    decision_timestamp: str
    reason_codes: tuple[str, ...]
    proposal: StrategyProposal | None = None


def _prepare_prefix(prefix: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prefix, pd.DataFrame) or prefix.empty:
        raise HighOfDayCandidateIntegrityError("candidate bars must be non-empty")
    if missing := REQUIRED_COLUMNS.difference(prefix.columns):
        raise HighOfDayCandidateIntegrityError(
            f"candidate bars are missing columns:{','.join(sorted(missing))}"
        )
    frame = prefix.loc[:, sorted(REQUIRED_COLUMNS)].copy(deep=True)
    try:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise HighOfDayCandidateIntegrityError("candidate timestamps are malformed") from exc
    if frame["timestamp"].dt.tz is None:
        raise HighOfDayCandidateIntegrityError("candidate timestamps must be timezone-aware")
    if not frame["timestamp"].is_monotonic_increasing:
        raise HighOfDayCandidateIntegrityError("candidate bars must be chronological")
    if frame["timestamp"].duplicated().any():
        raise HighOfDayCandidateIntegrityError("candidate timestamps must be unique")
    if frame["symbol"].nunique() != 1:
        raise HighOfDayCandidateIntegrityError("candidate bars must contain one symbol")
    local = frame["timestamp"].dt.tz_convert("America/New_York")
    if local.dt.date.nunique() != 1:
        raise HighOfDayCandidateIntegrityError("candidate bars must contain one session")
    numeric = frame[["open", "high", "low", "close", "volume", "spread_bps"]]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise HighOfDayCandidateIntegrityError("candidate numeric inputs must be finite")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise HighOfDayCandidateIntegrityError("candidate prices must be positive")
    if (frame[["volume", "spread_bps"]] < 0).any().any():
        raise HighOfDayCandidateIntegrityError("volume and spread cannot be negative")
    malformed = (
        frame["high"].lt(frame[["open", "close"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close"]].min(axis=1))
        | frame["high"].lt(frame["low"])
    )
    if malformed.any():
        raise HighOfDayCandidateIntegrityError("candidate OHLC range is malformed")
    expected = pd.date_range(
        local.iloc[0], local.iloc[-1], freq="min", tz="America/New_York"
    )
    if not pd.DatetimeIndex(local).equals(expected):
        raise HighOfDayCandidateIntegrityError("candidate minute sequence is incomplete")
    return frame.reset_index(drop=True)


def _decision(frame: pd.DataFrame, status: str, reason: str) -> HighOfDayDecision:
    decision_timestamp = pd.Timestamp(frame.iloc[-1]["timestamp"]) + pd.offsets.Minute(1)
    return HighOfDayDecision(
        status, decision_timestamp.isoformat(), (reason,)
    )


def _atr20(prior: pd.DataFrame) -> float:
    window = prior.iloc[-20:]
    previous_close = prior["close"].shift(1).loc[window.index]
    true_range = pd.concat(
        [
            window["high"] - window["low"],
            (window["high"] - previous_close).abs(),
            (window["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(true_range.mean())


def evaluate_high_of_day_breakout(
    prefix: pd.DataFrame,
    *,
    hypothesis_identity: str,
    specification_identity: str,
    preregistration_identity: str,
    implementation_binding_identity: str,
    dataset_identity: str,
) -> HighOfDayDecision:
    """Evaluate the frozen candidate from completed bars at or before cutoff.

    Exact prospective operationalization:

    * regular-session, contiguous, left-labeled one-minute bars from 09:30;
    * at least 20 completed bars before the trigger bar;
    * the candidate level is the earliest maximum high established at least 15
      completed bars before the trigger;
    * the five immediately preceding bars span no more than 0.75 times ATR20;
    * trigger close is strictly above the level, current volume is at least 1.5
      times prior-20 median volume, spread is at most 15 basis points, and no
      more than two earlier closes tested above the level;
    * intended entry is the exact next minute, stop is consolidation low minus
      0.05 ATR20, target is trigger close plus two trigger-close risk units,
      and timeout is 90 minutes.

    No next bar is passed to or read by this function.
    """

    identities: Mapping[str, str] = {
        "hypothesis_identity": hypothesis_identity,
        "specification_identity": specification_identity,
        "preregistration_identity": preregistration_identity,
        "implementation_binding_identity": implementation_binding_identity,
        "dataset_identity": dataset_identity,
    }
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in identities.values()
    ):
        raise HighOfDayCandidateIntegrityError("candidate identities are malformed")
    frame = _prepare_prefix(prefix)
    local = frame["timestamp"].dt.tz_convert("America/New_York")
    if local.iloc[0].strftime("%H:%M") != "09:30":
        return _decision(frame, "unavailable", "scheduled_open_missing")
    if len(frame) < 21:
        return _decision(frame, "unavailable", "warmup_incomplete")
    current = frame.iloc[-1]
    current_clock = local.iloc[-1].strftime("%H:%M")
    if not "09:50" <= current_clock <= "14:30":
        return _decision(frame, "no_signal", "outside_decision_window")
    prior = frame.iloc[:-1]
    atr20 = _atr20(prior)
    median_volume20 = float(prior.iloc[-20:]["volume"].median())
    if (
        not math.isfinite(atr20)
        or atr20 <= 0
        or not math.isfinite(median_volume20)
        or median_volume20 <= 0
    ):
        return _decision(frame, "unavailable", "indicator_baseline_unavailable")
    eligible_count = len(frame) - 15
    eligible = frame.iloc[:eligible_count]
    level = float(eligible["high"].max())
    level_index = int(eligible.index[eligible["high"].eq(level)][0])
    level_timestamp = pd.Timestamp(frame.loc[level_index, "timestamp"])
    consolidation = prior.iloc[-5:]
    consolidation_high = float(consolidation["high"].max())
    consolidation_low = float(consolidation["low"].min())
    consolidation_width = consolidation_high - consolidation_low
    relative_volume = float(current["volume"]) / median_volume20
    test_count = int((prior.iloc[level_index + 1 :]["close"] > level).sum())
    if not 2 <= float(current["close"]) <= 500:
        return _decision(frame, "no_signal", "price_outside_eligibility")
    if float(current["spread_bps"]) > 15:
        return _decision(frame, "no_signal", "spread_above_threshold")
    if consolidation_width > 0.75 * atr20:
        return _decision(frame, "no_signal", "consolidation_too_wide")
    if test_count > 2:
        return _decision(frame, "no_signal", "test_count_exceeded")
    if float(current["close"]) <= level:
        return _decision(frame, "no_signal", "high_of_day_breakout_absent")
    if relative_volume < 1.5:
        return _decision(frame, "no_signal", "relative_volume_below_threshold")
    stop = consolidation_low - 0.05 * atr20
    risk = float(current["close"]) - stop
    if not math.isfinite(stop) or stop <= 0 or risk <= 0:
        return _decision(frame, "unavailable", "nonpositive_trigger_risk")
    target = float(current["close"]) + 2 * risk
    input_last_bar = pd.Timestamp(current["timestamp"])
    decision_cutoff = input_last_bar + pd.offsets.Minute(1)
    proposal = StrategyProposal(
        strategy_identifier=CANDIDATE_ID,
        strategy_version=CANDIDATE_VERSION,
        symbol=str(current["symbol"]),
        signal_timestamp=decision_cutoff,
        direction=Direction.LONG,
        score_or_confidence=1.0,
        intended_entry_timestamp=decision_cutoff,
        intended_entry_price=None,
        stop=PriceLevel.absolute(stop),
        target=PriceLevel.absolute(target),
        maximum_holding_minutes=90,
        provenance={
            **identities,
            "candidate_id": CANDIDATE_ID,
            "candidate_version": CANDIDATE_VERSION,
            "point_in_time": True,
            "input_last_bar_timestamp": input_last_bar.isoformat(),
            "decision_cutoff": decision_cutoff.isoformat(),
            "level": level,
            "level_timestamp": level_timestamp.isoformat(),
            "atr20": atr20,
            "median_volume20": median_volume20,
            "relative_volume": relative_volume,
            "spread_bps": float(current["spread_bps"]),
            "test_count": test_count,
            "consolidation_width": consolidation_width,
            "stop": stop,
            "target": target,
        },
    )
    return HighOfDayDecision("proposal", decision_cutoff.isoformat(), (), proposal)
