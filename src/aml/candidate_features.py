"""Point-in-time, research-only context features for replay candidates.

All price and volume inputs used here are from the candidate bar or earlier.
Forward bars deliberately belong in :mod:`aml.candidate_outcomes`, not here.
"""

import numpy as np
import pandas as pd


_REQUIRED = {"timestamp", "price", "volume", "score", "open", "high", "low", "close"}


def _session_phase(timestamp: pd.Timestamp) -> str:
    """Classify an exchange-local clock time, with inclusive named boundaries."""
    minute = timestamp.hour * 60 + timestamp.minute
    if 570 <= minute <= 574:
        return "opening_auction"
    if 575 <= minute <= 599:
        return "opening_expansion"
    if 600 <= minute <= 689:
        return "morning"
    if 690 <= minute <= 839:
        return "midday"
    if 840 <= minute <= 929:
        return "afternoon"
    if 930 <= minute <= 960:
        return "close"
    return "outside_regular"


def _regular(timestamp: pd.Timestamp) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return 570 <= minute <= 960


def _empty_or_value(numerator: float, denominator: float) -> float:
    return np.nan if pd.isna(denominator) or denominator == 0 else numerator / denominator


def calculate_candidate_features(
    replay: pd.DataFrame, minimum_score: int = 55, episode_gap_minutes: int = 10
) -> pd.DataFrame:
    """Return features for score-qualified rows without changing ``replay``.

    ``return_Nm`` and VWAP slopes use the observation at exactly N clock minutes
    earlier.  Consequently a missing clock minute yields NaN rather than a
    substituted bar.  Session extrema and VWAP are cumulative through the
    current regular-session bar only.  Input timestamps retain their timezone.
    """
    missing = _REQUIRED.difference(replay.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if episode_gap_minutes < 0:
        raise ValueError("episode_gap_minutes must be non-negative")

    frame = replay.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if frame["timestamp"].isna().any() or frame["timestamp"].duplicated().any():
        raise ValueError("Timestamps must be present and unique")
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    frame["_day"] = frame["timestamp"].dt.date
    frame["_regular"] = frame["timestamp"].map(_regular)
    frame["minutes_since_open"] = np.where(
        frame["_regular"], frame["timestamp"].dt.hour * 60 + frame["timestamp"].dt.minute - 570, np.nan
    )
    frame["session_phase"] = frame["timestamp"].map(_session_phase)
    indexed = frame.set_index("timestamp", drop=False)

    feature_columns = [
        "minutes_since_open", "session_phase", "signal_ordinal_today",
        "minutes_since_previous_signal", "signals_last_5m", "signals_last_15m",
        "episode_id", "episode_signal_ordinal", "first_signal_in_episode",
        "minutes_since_episode_start", "return_from_session_open", "return_1m",
        "return_3m", "return_5m", "return_15m", "distance_from_session_high",
        "pullback_from_session_high", "distance_from_session_low", "bars_since_session_high",
        "bars_since_session_low", "vwap", "distance_from_vwap", "vwap_slope_3m",
        "vwap_slope_10m", "minutes_above_vwap", "dollar_volume",
        "volume_vs_trailing_5m_mean", "volume_vs_trailing_20m_mean",
        "volume_acceleration_3m", "volume_acceleration_5m", "bar_range_pct",
        "body_to_range_ratio", "close_location_value", "upper_wick_ratio", "lower_wick_ratio",
    ]
    for column in feature_columns:
        frame[column] = np.nan
    frame["minutes_since_open"] = np.where(
        frame["_regular"], frame["timestamp"].dt.hour * 60 + frame["timestamp"].dt.minute - 570, np.nan
    )
    frame["session_phase"] = frame["timestamp"].map(_session_phase)

    # Exact-clock close returns; no reindex/forward-fill is used.
    for minutes in (1, 3, 5, 15):
        targets = frame["timestamp"] - pd.Timedelta(minutes, unit="min")
        prior = targets.map(indexed["close"].to_dict())
        frame[f"return_{minutes}m"] = frame["close"] / prior - 1

    # Each local calendar date is a session boundary; this prevents any overnight carry.
    for _, group in frame.groupby("_day", sort=False):
        idx = group.index
        regular = group[group["_regular"]]
        if regular.empty:
            continue
        r_idx = regular.index
        open_time = regular["timestamp"].iloc[0].normalize() + pd.Timedelta(570, unit="min")
        # Rebuild 09:30 in the timestamp's timezone; exact matching intentionally matters.
        if regular["timestamp"].iloc[0].tz is not None:
            open_time = open_time.tz_localize(regular["timestamp"].iloc[0].tz) if open_time.tz is None else open_time
        open_close = indexed["close"].get(open_time, np.nan)
        frame.loc[r_idx, "return_from_session_open"] = regular["close"] / open_close - 1

        highs = regular["high"].cummax()
        lows = regular["low"].cummin()
        frame.loc[r_idx, "distance_from_session_high"] = regular["close"].to_numpy() / highs.to_numpy() - 1
        frame.loc[r_idx, "pullback_from_session_high"] = highs.to_numpy() / regular["close"].to_numpy() - 1
        frame.loc[r_idx, "distance_from_session_low"] = regular["close"].to_numpy() / lows.to_numpy() - 1
        high_positions, low_positions, last_high, last_low = [], [], -1, -1
        for pos, (_, row) in enumerate(regular.iterrows()):
            if row["high"] >= highs.iloc[pos]:
                last_high = pos
            if row["low"] <= lows.iloc[pos]:
                last_low = pos
            high_positions.append(pos - last_high)
            low_positions.append(pos - last_low)
        frame.loc[r_idx, "bars_since_session_high"] = high_positions
        frame.loc[r_idx, "bars_since_session_low"] = low_positions

        typical = (regular["high"] + regular["low"] + regular["close"]) / 3
        cumulative_volume = regular["volume"].cumsum()
        vwap = (typical * regular["volume"]).cumsum() / cumulative_volume.replace(0, np.nan)
        frame.loc[r_idx, "vwap"] = vwap.to_numpy()
        frame.loc[r_idx, "distance_from_vwap"] = regular["close"].to_numpy() / vwap.to_numpy() - 1
        vwap_map = dict(zip(regular["timestamp"], vwap))
        for minutes in (3, 10):
            prior = (regular["timestamp"] - pd.Timedelta(minutes, unit="min")).map(vwap_map)
            frame.loc[r_idx, f"vwap_slope_{minutes}m"] = vwap.to_numpy() / prior.to_numpy() - 1
        consecutive, previous_time = 0, None
        values = []
        for timestamp, close, current_vwap in zip(regular["timestamp"], regular["close"], vwap):
            if previous_time is None or timestamp - previous_time != pd.Timedelta(1, unit="min"):
                consecutive = 0
            consecutive = consecutive + 1 if pd.notna(current_vwap) and close > current_vwap else 0
            values.append(consecutive)
            previous_time = timestamp
        frame.loc[r_idx, "minutes_above_vwap"] = values

        frame.loc[r_idx, "dollar_volume"] = regular["close"].to_numpy() * regular["volume"].to_numpy()
        volume_map = dict(zip(regular["timestamp"], regular["volume"]))
        for minutes in (3, 5):
            prior = (regular["timestamp"] - pd.Timedelta(minutes, unit="min")).map(volume_map)
            frame.loc[r_idx, f"volume_acceleration_{minutes}m"] = regular["volume"].to_numpy() / prior.to_numpy() - 1
        # Clock-window means are based only on observed prior bars (current excluded).
        for minutes in (5, 20):
            means = []
            for timestamp in regular["timestamp"]:
                prior = regular.loc[(regular["timestamp"] < timestamp) & (regular["timestamp"] >= timestamp - pd.Timedelta(minutes, unit="min")), "volume"]
                means.append(prior.mean() if not prior.empty else np.nan)
            frame.loc[r_idx, f"volume_vs_trailing_{minutes}m_mean"] = regular["volume"].to_numpy() / np.asarray(means, dtype=float)

    ranges = frame["high"] - frame["low"]
    frame["bar_range_pct"] = ranges / frame["close"]
    frame["body_to_range_ratio"] = (frame["close"] - frame["open"]).abs() / ranges
    frame["close_location_value"] = (2 * frame["close"] - frame["high"] - frame["low"]) / ranges
    frame["upper_wick_ratio"] = (frame["high"] - frame[["open", "close"]].max(axis=1)) / ranges
    frame["lower_wick_ratio"] = (frame[["open", "close"]].min(axis=1) - frame["low"]) / ranges
    frame.loc[ranges == 0, ["body_to_range_ratio", "close_location_value", "upper_wick_ratio", "lower_wick_ratio"]] = np.nan

    candidates = frame.loc[frame["score"] >= minimum_score].copy()
    candidates["signal_ordinal_today"] = candidates.groupby("_day", sort=False).cumcount() + 1
    previous = candidates.groupby("_day", sort=False)["timestamp"].shift()
    candidates["minutes_since_previous_signal"] = (candidates["timestamp"] - previous).dt.total_seconds() / 60
    candidates["signals_last_5m"] = [int(((candidates["timestamp"] >= t - pd.Timedelta(5, unit="min")) & (candidates["timestamp"] <= t)).sum()) for t in candidates["timestamp"]]
    candidates["signals_last_15m"] = [int(((candidates["timestamp"] >= t - pd.Timedelta(15, unit="min")) & (candidates["timestamp"] <= t)).sum()) for t in candidates["timestamp"]]
    new_episode = previous.isna() | (candidates["minutes_since_previous_signal"] > episode_gap_minutes)
    candidates["episode_id"] = new_episode.cumsum().astype(int)
    candidates["episode_signal_ordinal"] = candidates.groupby("episode_id", sort=False).cumcount() + 1
    candidates["first_signal_in_episode"] = candidates["episode_signal_ordinal"] == 1
    starts = candidates.groupby("episode_id", sort=False)["timestamp"].transform("first")
    candidates["minutes_since_episode_start"] = (candidates["timestamp"] - starts).dt.total_seconds() / 60
    return candidates[["timestamp", *feature_columns]].reset_index(drop=True)
