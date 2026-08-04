"""One preregisterable research candidate for the V001 vertical slice.

This module is intentionally upstream of the frozen execution stack.  It reads
only bars that are complete at the decision timestamp and emits the existing
``portfolio_simulator.StrategyProposal`` type.  It has no execution, scoring,
validation, Olympics, broker, or data-acquisition capability.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Mapping

import numpy as np
import pandas as pd

from aml.portfolio_simulator import Direction, PriceLevel, StrategyProposal


CANDIDATE_ID = "opening-range-midpoint-reclaim-long-v001"
CANDIDATE_VERSION = "1.0.0"
REQUIRED_COLUMNS = frozenset(
    {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
)


class CandidateIntegrityError(ValueError):
    """Candidate input violates an integrity rule rather than lacking evidence."""


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    """One deterministic point-in-time candidate decision."""

    status: Literal["proposal", "no_signal", "unavailable"]
    decision_timestamp: str
    reason_codes: tuple[str, ...]
    proposal: StrategyProposal | None = None


def _prepare_prefix(prefix: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prefix, pd.DataFrame) or prefix.empty:
        raise CandidateIntegrityError("candidate bars must be a non-empty DataFrame")
    if missing := REQUIRED_COLUMNS.difference(prefix.columns):
        raise CandidateIntegrityError(
            f"candidate bars are missing columns: {', '.join(sorted(missing))}"
        )
    frame = prefix.loc[:, sorted(REQUIRED_COLUMNS)].copy(deep=True)
    try:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise CandidateIntegrityError("candidate timestamps are malformed") from exc
    if frame["timestamp"].dt.tz is None:
        raise CandidateIntegrityError("candidate timestamps must be timezone-aware")
    if not frame["timestamp"].is_monotonic_increasing:
        raise CandidateIntegrityError("candidate bars must be chronological")
    if frame["timestamp"].duplicated().any():
        raise CandidateIntegrityError("candidate timestamps must be unique")
    if frame["symbol"].nunique() != 1:
        raise CandidateIntegrityError("candidate bars must contain exactly one symbol")
    if frame["timestamp"].dt.date.nunique() != 1:
        raise CandidateIntegrityError("candidate bars must contain exactly one session")
    numeric = frame[["open", "high", "low", "close", "volume"]]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise CandidateIntegrityError("candidate numeric inputs must be finite")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise CandidateIntegrityError("candidate prices must be positive")
    if (frame["volume"] < 0).any():
        raise CandidateIntegrityError("candidate volume cannot be negative")
    malformed = (
        frame["high"].lt(frame[["open", "close"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close"]].min(axis=1))
        | frame["high"].lt(frame["low"])
    )
    if malformed.any():
        raise CandidateIntegrityError("candidate OHLC range is malformed")
    return frame.reset_index(drop=True)


def _unavailable(frame: pd.DataFrame, reason: str) -> CandidateDecision:
    return CandidateDecision(
        "unavailable", pd.Timestamp(frame.iloc[-1]["timestamp"]).isoformat(), (reason,)
    )


def _no_signal(frame: pd.DataFrame, reason: str) -> CandidateDecision:
    return CandidateDecision(
        "no_signal", pd.Timestamp(frame.iloc[-1]["timestamp"]).isoformat(), (reason,)
    )


def evaluate_opening_range_midpoint_reclaim(
    prefix: pd.DataFrame,
    *,
    hypothesis_identity: str,
    specification_identity: str,
    preregistration_identity: str,
    implementation_binding_identity: str,
    dataset_identity: str,
) -> CandidateDecision:
    """Evaluate the fixed midpoint-reclaim contract using only ``prefix``.

    Contract:

    * exact one-minute bars from 09:30 through the current complete bar;
    * opening range is the five bars labeled 09:30 through 09:34;
    * decision window is 09:36 through 10:30 New York time;
    * preceding close is at or below the range midpoint;
    * current close crosses strictly above the midpoint, remains below the range
      high, closes above its open, and volume is at least 1.5 times the opening
      range median;
    * intended entry is the next exact minute; stop and target are the frozen
      opening-range low and high; timeout is 30 minutes.

    The next bar is never passed to or read by this function.
    """

    identity_fields: Mapping[str, str] = {
        "hypothesis_identity": hypothesis_identity,
        "specification_identity": specification_identity,
        "preregistration_identity": preregistration_identity,
        "implementation_binding_identity": implementation_binding_identity,
        "dataset_identity": dataset_identity,
    }
    if any(
        not isinstance(value, str) or len(value) != 64
        for value in identity_fields.values()
    ):
        raise CandidateIntegrityError("candidate provenance identities are malformed")
    frame = _prepare_prefix(prefix)
    current_timestamp = pd.Timestamp(frame.iloc[-1]["timestamp"])
    local = frame["timestamp"].dt.tz_convert("America/New_York")
    if not local.dt.date.eq(local.iloc[-1].date()).all():
        raise CandidateIntegrityError("candidate local session dates disagree")
    expected = pd.date_range(
        local.iloc[0], local.iloc[-1], freq="min", tz="America/New_York"
    )
    if not pd.DatetimeIndex(local).equals(expected):
        return _unavailable(frame, "required_interval_incomplete")
    if local.iloc[0].strftime("%H:%M") != "09:30":
        return _unavailable(frame, "scheduled_open_missing")
    clock = local.iloc[-1].strftime("%H:%M")
    if clock < "09:36" or clock > "10:30":
        return _no_signal(frame, "outside_decision_window")
    opening = frame.loc[local.dt.strftime("%H:%M").between("09:30", "09:34")]
    if len(opening) != 5:
        return _unavailable(frame, "opening_range_incomplete")
    if len(frame) < 7:
        return _unavailable(frame, "confirmation_history_incomplete")
    range_high = float(opening["high"].max())
    range_low = float(opening["low"].min())
    midpoint = (range_high + range_low) / 2
    opening_median_volume = float(opening["volume"].median())
    if not math.isfinite(opening_median_volume) or opening_median_volume <= 0:
        return _unavailable(frame, "opening_volume_baseline_unavailable")
    prior = frame.iloc[-2]
    current = frame.iloc[-1]
    if float(prior["close"]) > midpoint:
        return _no_signal(frame, "prior_close_not_below_midpoint")
    if not midpoint < float(current["close"]) < range_high:
        return _no_signal(frame, "midpoint_reclaim_absent")
    if float(current["close"]) <= float(current["open"]):
        return _no_signal(frame, "bullish_confirmation_absent")
    if float(current["volume"]) < 1.5 * opening_median_volume:
        return _no_signal(frame, "confirmation_volume_below_threshold")
    decision_cutoff = current_timestamp + pd.Timedelta(1, unit="min")
    proposal = StrategyProposal(
        strategy_identifier=CANDIDATE_ID,
        strategy_version=CANDIDATE_VERSION,
        symbol=str(current["symbol"]),
        signal_timestamp=decision_cutoff,
        direction=Direction.LONG,
        score_or_confidence=1.0,
        intended_entry_timestamp=decision_cutoff,
        intended_entry_price=None,
        stop=PriceLevel.absolute(range_low),
        target=PriceLevel.absolute(range_high),
        maximum_holding_minutes=30,
        provenance={
            **identity_fields,
            "candidate_id": CANDIDATE_ID,
            "candidate_version": CANDIDATE_VERSION,
            "decision_cutoff": decision_cutoff.isoformat(),
            "input_last_bar_timestamp": current_timestamp.isoformat(),
            "point_in_time": True,
        },
    )
    return CandidateDecision(
        "proposal",
        decision_cutoff.isoformat(),
        (),
        proposal,
    )
