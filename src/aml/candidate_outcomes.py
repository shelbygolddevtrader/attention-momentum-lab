"""Point-in-time candidate outcome analysis for completed historical replays."""

from collections.abc import Iterable

import numpy as np
import pandas as pd
from aml.thresholds import CANDIDATE_SCORE_THRESHOLD
from aml.market_halts import (
    CompletenessMode, HaltSchedule, completeness_metadata, expected_minutes,
)

HORIZONS = (5, 15, 30)


def _validated_frame(replay: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "price", "score"}
    missing = required.difference(replay.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    frame = replay.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if frame["timestamp"].isna().any():
        raise ValueError("Timestamps must not be missing")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Replay rows must be in chronological order")
    if frame["timestamp"].duplicated().any():
        raise ValueError("Replay timestamps must be unique")
    return frame.reset_index(drop=True)


def analyze_candidate_outcomes(
    replay: pd.DataFrame,
    candidate_score_threshold: int = CANDIDATE_SCORE_THRESHOLD,
    horizons: Iterable[int] = HORIZONS,
    completeness_mode: str | CompletenessMode = CompletenessMode.STRICT,
    halt_schedule: HaltSchedule | None = None,
) -> pd.DataFrame:
    """Calculate outcomes without silently bridging missing minute bars."""
    frame = _validated_frame(replay)
    horizons = tuple(horizons)
    completeness_mode = CompletenessMode(completeness_mode)
    if any(minutes <= 0 for minutes in horizons):
        raise ValueError("Forward horizons must be positive")
    indexed = frame.set_index("timestamp", drop=False)
    records = []
    for row in frame.loc[frame["score"] >= candidate_score_threshold].itertuples(index=False):
        entry_time = pd.Timestamp(row.timestamp).as_unit("ns")
        entry_price = float(row.price)
        record = {
            "timestamp": entry_time,
            "symbol": getattr(row, "symbol", ""),
            "price": entry_price,
            "score": int(row.score),
            **completeness_metadata(completeness_mode, halt_schedule),
        }
        for minutes in horizons:
            target = entry_time + pd.Timedelta(int(minutes), unit="min")
            if target in indexed.index:
                target_price = float(indexed.at[target, "price"])
                record[f"forward_{minutes}m_return"] = target_price / entry_price - 1
                record[f"forward_{minutes}m_available"] = True
            else:
                record[f"forward_{minutes}m_return"] = np.nan
                record[f"forward_{minutes}m_available"] = False

            raw_expected = pd.date_range(
                entry_time + pd.Timedelta(1, unit="min"), target, freq="min"
            )
            expected = expected_minutes(
                raw_expected[0], raw_expected[-1], completeness_mode, halt_schedule
            )
            observed = pd.DatetimeIndex(frame.loc[
                (frame["timestamp"] > entry_time) & (frame["timestamp"] <= target), "timestamp"
            ])
            record[f"missing_minutes_{minutes}m"] = len(expected.difference(observed))
            record[f"complete_{minutes}m_window"] = record[f"missing_minutes_{minutes}m"] == 0
            record[f"verified_halt_minutes_excluded_{minutes}m"] = len(raw_expected.difference(expected))

        end = entry_time + pd.Timedelta(30, unit="min")
        window = frame.loc[
            (frame["timestamp"] > entry_time) & (frame["timestamp"] <= end)
        ]
        if completeness_mode is CompletenessMode.HALT_AWARE and halt_schedule is not None:
            window = window.loc[~window["timestamp"].isin(halt_schedule.full_halt_minutes)]
        record["observed_minutes_30m"] = len(window)
        if window.empty:
            record["mfe_30m"] = np.nan
            record["mae_30m"] = np.nan
        else:
            favorable = window["high"] if "high" in window else window["price"]
            adverse = window["low"] if "low" in window else window["price"]
            record["mfe_30m"] = max(
                0.0, float(favorable.max()) / entry_price - 1
            )
            record["mae_30m"] = min(
                0.0, float(adverse.min()) / entry_price - 1
            )
        records.append(record)

    columns = ["timestamp", "symbol", "price", "score"]
    columns.extend(["completeness_mode", "verified_halt_count", "verified_halt_minutes_excluded", "halt_data_path"])
    for minutes in horizons:
        columns.extend([
            f"forward_{minutes}m_return", f"forward_{minutes}m_available",
            f"missing_minutes_{minutes}m", f"complete_{minutes}m_window",
            f"verified_halt_minutes_excluded_{minutes}m",
        ])
    columns.extend(["mfe_30m", "mae_30m", "observed_minutes_30m"])
    return pd.DataFrame.from_records(records, columns=columns)
