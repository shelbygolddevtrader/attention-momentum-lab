from dataclasses import dataclass
import numpy as np
import pandas as pd
from aml.thresholds import (
    ELIGIBLE_SCORE_THRESHOLD, UNSET_THRESHOLD, resolve_deprecated_threshold_alias,
)

@dataclass(frozen=True, init=False)
class SignalConfig:
    return_window: int = 5
    volume_window: int = 20
    acceleration_window: int = 5
    return_threshold: float = 0.03
    relative_volume_threshold: float = 3.0
    vwap_threshold: float = 0.01
    acceleration_threshold: float = 1.5
    eligible_score_threshold: int = ELIGIBLE_SCORE_THRESHOLD

    def __init__(
        self, return_window=5, volume_window=20, acceleration_window=5,
        return_threshold=0.03, relative_volume_threshold=3.0,
        vwap_threshold=0.01, acceleration_threshold=1.5,
        eligible_score_threshold=UNSET_THRESHOLD, *, eligible_score=UNSET_THRESHOLD,
    ):
        """Build signal config; ``eligible_score`` is a deprecated alias."""
        eligible = resolve_deprecated_threshold_alias(
            eligible_score_threshold, eligible_score, ELIGIBLE_SCORE_THRESHOLD,
            "eligible_score_threshold", "eligible_score",
        )
        values = locals()
        for name in (
            "return_window", "volume_window", "acceleration_window",
            "return_threshold", "relative_volume_threshold", "vwap_threshold",
            "acceleration_threshold",
        ):
            object.__setattr__(self, name, values[name])
        object.__setattr__(self, "eligible_score_threshold", eligible)

def add_features(bars: pd.DataFrame, cfg=None, *, exact_elapsed_return=True):
    cfg = cfg or SignalConfig()
    f = bars.copy().sort_values("timestamp").reset_index(drop=True)
    if exact_elapsed_return:
        timestamps = pd.to_datetime(f["timestamp"], utc=True, errors="coerce")
        if timestamps.isna().any() or timestamps.duplicated().any():
            raise ValueError("Feature timestamps must be valid and unique")
        close_at = dict(zip(timestamps, f["close"], strict=True))
        elapsed = pd.Timedelta(cfg.return_window, unit="min")
        prior = timestamps.map(lambda timestamp: close_at.get(timestamp - elapsed))
        f["return_5m"] = f["close"] / prior - 1
    else:
        # Required only to audit tournament artifacts created before exact
        # elapsed-minute enforcement was introduced.
        f["return_5m"] = f["close"].pct_change(cfg.return_window)
    baseline = f["volume"].shift(1).rolling(cfg.volume_window, min_periods=5).median()
    f["relative_volume"] = f["volume"] / baseline.replace(0, np.nan)
    price = f["bar_vwap"].fillna(f["close"]) if "bar_vwap" in f else f["close"]
    f["session_vwap"] = (price * f["volume"]).cumsum() / f["volume"].cumsum().replace(0, np.nan)
    f["vwap_distance"] = f["close"] / f["session_vwap"] - 1
    prior = f["volume"].shift(1).rolling(cfg.acceleration_window, min_periods=2).mean()
    f["volume_acceleration"] = f["volume"] / prior.replace(0, np.nan)
    # Keep the established score exactly additive while exposing each component
    # for point-in-time auditability. Comparisons with NaN remain False.
    f["return_score_component"] = np.where(
        f["return_5m"] >= cfg.return_threshold, 35, 0
    )
    f["relative_volume_score_component"] = np.where(
        f["relative_volume"] >= cfg.relative_volume_threshold, 35, 0
    )
    f["vwap_score_component"] = np.where(
        f["vwap_distance"] >= cfg.vwap_threshold, 20, 0
    )
    f["acceleration_score_component"] = np.where(
        f["volume_acceleration"] >= cfg.acceleration_threshold, 10, 0
    )
    f["score"] = f[
        [
            "return_score_component",
            "relative_volume_score_component",
            "vwap_score_component",
            "acceleration_score_component",
        ]
    ].sum(axis=1)
    f["eligible"] = f["score"] >= cfg.eligible_score_threshold
    return f
