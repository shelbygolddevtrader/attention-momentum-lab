import pandas as pd
from aml.signals import add_features

def replay_to_frame(bars: pd.DataFrame):
    ordered = bars.sort_values("timestamp").reset_index(drop=True)
    events = []
    for i in range(len(ordered)):
        row = add_features(ordered.iloc[: i + 1]).iloc[-1]
        events.append({
            "timestamp": row["timestamp"],
            "symbol": row.get("symbol", ""),
            "price": float(row["close"]),
            "volume": float(row["volume"]),
            "return_5m": None if pd.isna(row["return_5m"]) else float(row["return_5m"]),
            "relative_volume": None if pd.isna(row["relative_volume"]) else float(row["relative_volume"]),
            "session_vwap": None if pd.isna(row["session_vwap"]) else float(row["session_vwap"]),
            "vwap_distance": None if pd.isna(row["vwap_distance"]) else float(row["vwap_distance"]),
            "volume_acceleration": None if pd.isna(row["volume_acceleration"]) else float(row["volume_acceleration"]),
            "score": int(row["score"]),
            "eligible": bool(row["eligible"]),
        })
    return pd.DataFrame(events)
