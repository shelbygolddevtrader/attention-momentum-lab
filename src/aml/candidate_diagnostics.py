"""Research-only, path-dependent candidate diagnostics.

This module never feeds features or labels back into strategy code.  Feature
columns are caller supplied; only OHLC bars strictly after a candidate are used
for the outcome labels below.
"""
from itertools import product

import numpy as np
import pandas as pd
from aml.market_halts import (
    CompletenessMode, HaltSchedule, completeness_metadata, expected_minutes,
)

HORIZONS = (5, 15, 30)
TARGETS = (.01, .02, .03, .05)
STOPS = (.005, .01, .02)


def _check(candidates: pd.DataFrame, bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_candidates, required_bars = {"timestamp", "price"}, {"timestamp", "high", "low", "close"}
    if missing := required_candidates.difference(candidates):
        raise ValueError(f"Missing candidate columns: {', '.join(sorted(missing))}")
    if missing := required_bars.difference(bars):
        raise ValueError(f"Missing bar columns: {', '.join(sorted(missing))}")
    c, b = candidates.copy(), bars.copy()
    c["timestamp"], b["timestamp"] = pd.to_datetime(c["timestamp"]), pd.to_datetime(b["timestamp"])
    if c["timestamp"].isna().any() or b["timestamp"].isna().any() or b["timestamp"].duplicated().any():
        raise ValueError("Timestamps must be present and bar timestamps unique")
    return c.sort_values("timestamp", kind="mergesort").reset_index(drop=True), b.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def analyze_candidate_paths(
    candidates: pd.DataFrame, bars: pd.DataFrame,
    completeness_mode: str | CompletenessMode = CompletenessMode.STRICT,
    halt_schedule: HaltSchedule | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return candidate path metrics and target/stop labels.

    The entry reference is the candidate ``price``. For each horizon, every
    exact clock minute from timestamp+1 through timestamp+horizon must exist to
    label target/stop; otherwise it is ``insufficient_data``. A bar touching
    both levels is ``ambiguous_same_bar``. MFE/MAE timings use the earliest bar
    attaining the maximum high/minimum low; ties are therefore deterministic.
    """
    candidates, bars = _check(candidates, bars)
    completeness_mode = CompletenessMode(completeness_mode)
    indexed = bars.set_index("timestamp", drop=False)
    path_rows, label_rows = [], []
    for candidate in candidates.itertuples(index=False):
        timestamp, entry = pd.Timestamp(candidate.timestamp), float(candidate.price)
        metadata = completeness_metadata(completeness_mode, halt_schedule)
        path = {"timestamp": timestamp, **metadata}
        for horizon in HORIZONS:
            raw_expected = pd.date_range(timestamp + pd.Timedelta(1, unit="min"), timestamp + pd.Timedelta(horizon, unit="min"), freq="min")
            expected = expected_minutes(raw_expected[0], raw_expected[-1], completeness_mode, halt_schedule)
            window = indexed.reindex(expected)
            complete = not window[["high", "low", "close"]].isna().any().any()
            path[f"complete_{horizon}m_path"] = complete
            path[f"verified_halt_minutes_excluded_{horizon}m"] = len(raw_expected.difference(expected))
            if window.dropna(how="all").empty:
                for field in ("mfe", "mae", "minutes_to_mfe", "minutes_to_mae", "close_return_at_mfe_time", "close_return_at_mae_time"):
                    path[f"{field}_{horizon}m"] = np.nan
            else:
                observed = window.dropna(subset=["high", "low", "close"])
                max_high, min_low = observed["high"].max(), observed["low"].min()
                high_time = observed.index[observed["high"].eq(max_high)][0]
                low_time = observed.index[observed["low"].eq(min_low)][0]
                path[f"mfe_{horizon}m"] = max(0.0, max_high / entry - 1)
                path[f"mae_{horizon}m"] = min(0.0, min_low / entry - 1)
                path[f"minutes_to_mfe_{horizon}m"] = (high_time - timestamp).total_seconds() / 60
                path[f"minutes_to_mae_{horizon}m"] = (low_time - timestamp).total_seconds() / 60
                path[f"close_return_at_mfe_time_{horizon}m"] = observed.at[high_time, "close"] / entry - 1
                path[f"close_return_at_mae_time_{horizon}m"] = observed.at[low_time, "close"] / entry - 1
            for target, stop in product(TARGETS, STOPS):
                result, target_time, stop_time = "insufficient_data", np.nan, np.nan
                if complete:
                    target_price, stop_price = entry * (1 + target), entry * (1 - stop)
                    result = "neither"
                    for bar_time, row in window.iterrows():
                        hit_target, hit_stop = row.high >= target_price, row.low <= stop_price
                        if hit_target and hit_stop:
                            result = "ambiguous_same_bar"; break
                        if hit_target:
                            result, target_time = "target_first", bar_time; break
                        if hit_stop:
                            result, stop_time = "stop_first", bar_time; break
                label_rows.append({"timestamp": timestamp, "horizon_minutes": horizon, "target_fraction": target, "stop_fraction": stop, "outcome": result,
                                   "minutes_to_target": np.nan if pd.isna(target_time) else (target_time - timestamp).total_seconds() / 60,
                                   "minutes_to_stop": np.nan if pd.isna(stop_time) else (stop_time - timestamp).total_seconds() / 60,
                                   "complete_window": complete,
                                   "completeness_mode": completeness_mode.value,
                                   "verified_halt_count": metadata["verified_halt_count"],
                                   "verified_halt_minutes_excluded": len(raw_expected.difference(expected)),
                                   "halt_data_path": metadata["halt_data_path"]})
        path_rows.append(path)
    return pd.DataFrame(path_rows), pd.DataFrame(label_rows)


def distribution_statistics(frame: pd.DataFrame, group_columns: list[str], metrics: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Long-form descriptive statistics; absent requested metrics are reported."""
    rows, missing = [], [metric for metric in metrics if metric not in frame]
    present = [metric for metric in metrics if metric in frame]
    grouped = frame.groupby(group_columns, dropna=False) if group_columns else [((), frame)]
    for key, group in grouped:
        key = key if isinstance(key, tuple) else (key,)
        base = dict(zip(group_columns, key))
        for metric in present:
            values = group[metric].dropna()
            if values.empty:
                stats = dict(candidate_count=0, mean=np.nan, median=np.nan, standard_deviation=np.nan, minimum=np.nan, percentile_25=np.nan, percentile_75=np.nan, maximum=np.nan, positive_return_count=0, positive_return_rate=np.nan)
            else:
                stats = dict(candidate_count=len(values), mean=values.mean(), median=values.median(), standard_deviation=values.std(), minimum=values.min(), percentile_25=values.quantile(.25), percentile_75=values.quantile(.75), maximum=values.max(), positive_return_count=int((values > 0).sum()), positive_return_rate=(values > 0).mean())
            rows.append({**base, "metric": metric, **stats})
    return pd.DataFrame(rows), missing


def feature_correlations(frame: pd.DataFrame, features: list[str], outcomes: list[str]) -> pd.DataFrame:
    rows = []
    for feature in features:
        if feature not in frame or not pd.api.types.is_numeric_dtype(frame[feature]):
            continue
        for outcome in outcomes:
            if outcome not in frame: continue
            pair = frame[[feature, outcome]].dropna()
            # Spearman is Pearson correlation of average ranks; implementing it
            # directly avoids adding scipy as a production dependency.
            correlation = pair.iloc[:, 0].rank(method="average").corr(pair.iloc[:, 1].rank(method="average")) if len(pair) >= 2 else np.nan
            rows.append({"feature": feature, "outcome": outcome, "non_null_sample_count": len(pair), "spearman_correlation": correlation})
    return pd.DataFrame(rows)
