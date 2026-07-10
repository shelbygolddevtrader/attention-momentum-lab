from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class SignalConfig:
    return_window: int = 5
    volume_window: int = 20
    acceleration_window: int = 5
    return_threshold: float = 0.03
    relative_volume_threshold: float = 3.0
    vwap_threshold: float = 0.01
    acceleration_threshold: float = 1.5
    eligible_score: int = 70

def add_features(bars: pd.DataFrame, cfg=None):
    cfg = cfg or SignalConfig()
    f = bars.copy().sort_values("timestamp").reset_index(drop=True)
    f["return_5m"] = f["close"].pct_change(cfg.return_window)
    baseline = f["volume"].shift(1).rolling(cfg.volume_window, min_periods=5).median()
    f["relative_volume"] = f["volume"] / baseline.replace(0, np.nan)
    price = f["bar_vwap"].fillna(f["close"]) if "bar_vwap" in f else f["close"]
    f["session_vwap"] = (price * f["volume"]).cumsum() / f["volume"].cumsum().replace(0, np.nan)
    f["vwap_distance"] = f["close"] / f["session_vwap"] - 1
    prior = f["volume"].shift(1).rolling(cfg.acceleration_window, min_periods=2).mean()
    f["volume_acceleration"] = f["volume"] / prior.replace(0, np.nan)
    f["score"] = 0
    f.loc[f["return_5m"] >= cfg.return_threshold, "score"] += 35
    f.loc[f["relative_volume"] >= cfg.relative_volume_threshold, "score"] += 35
    f.loc[f["vwap_distance"] >= cfg.vwap_threshold, "score"] += 20
    f.loc[f["volume_acceleration"] >= cfg.acceleration_threshold, "score"] += 10
    f["eligible"] = f["score"] >= cfg.eligible_score
    return f
