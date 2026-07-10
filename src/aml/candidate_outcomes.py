"""Point-in-time candidate outcome analysis for completed historical replays."""

from collections.abc import Iterable

import numpy as np
import pandas as pd

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
    minimum_score: int = 55,
    horizons: Iterable[int] = HORIZONS,
) -> pd.DataFrame:
    """Calculate outcomes without silently bridging missing minute bars."""
    frame = _validated_frame(replay)
    horizons = tuple(horizons)
    if any(minutes <= 0 for minutes in horizons):
        raise ValueError("Forward horizons must be positive")
    indexed = frame.set_index("timestamp", drop=False)
    records = []
    for row in frame.loc[frame["score"] >= minimum_score].itertuples(index=False):
        entry_time = pd.Timestamp(row.timestamp).as_unit("ns")
        entry_price = float(row.price)
        record = {
            "timestamp": entry_time,
            "symbol": getattr(row, "symbol", ""),
            "price": entry_price,
            "score": int(row.score),
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

        end = entry_time + pd.Timedelta(30, unit="min")
        window = frame.loc[
            (frame["timestamp"] > entry_time) & (frame["timestamp"] <= end)
        ]
        expected = pd.date_range(entry_time + pd.Timedelta(1, unit="min"), end, freq="min")
        observed = pd.DatetimeIndex(window["timestamp"])
        record["observed_minutes_30m"] = len(window)
        record["missing_minutes_30m"] = len(expected.difference(observed))
        record["complete_30m_window"] = record["missing_minutes_30m"] == 0
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
    for minutes in horizons:
        columns.extend([f"forward_{minutes}m_return", f"forward_{minutes}m_available"])
    columns.extend(["mfe_30m", "mae_30m", "observed_minutes_30m", "missing_minutes_30m", "complete_30m_window"])
    return pd.DataFrame.from_records(records, columns=columns)
