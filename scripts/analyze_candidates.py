import argparse
from pathlib import Path

import pandas as pd

from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.candidate_features import calculate_candidate_features


def parser():
    p = argparse.ArgumentParser(description="Analyze historical replay candidates")
    p.add_argument("symbol", nargs="?", default="GME")
    p.add_argument("date", nargs="?", default="2024-05-13")
    p.add_argument("--minimum-score", type=int, default=55)
    return p


def _summary(output: pd.DataFrame, group: str) -> pd.DataFrame:
    return output.groupby(group, dropna=False).agg(
        candidate_count=("timestamp", "size"),
        mean_return_5m=("forward_5m_return", "mean"),
        mean_return_15m=("forward_15m_return", "mean"),
        mean_return_30m=("forward_30m_return", "mean"),
        mean_mfe_30m=("mfe_30m", "mean"),
        mean_mae_30m=("mae_30m", "mean"),
    )


def main():
    args = parser().parse_args()
    symbol = args.symbol.upper()
    path = Path(f"artifacts/{symbol}/{args.date}/replay_log.csv")
    replay = pd.read_csv(path)
    replay["timestamp"] = pd.to_datetime(replay["timestamp"])

    bars_path = Path(f"data/processed/{symbol}/{args.date}_1min.csv")
    if bars_path.exists():
        bars = pd.read_csv(
            bars_path,
            usecols=["timestamp", "open", "high", "low", "close"],
        )
        bars["timestamp"] = pd.to_datetime(bars["timestamp"])
        replay = replay.merge(bars, on="timestamp", how="left", validate="one_to_one")

    outcomes = analyze_candidate_outcomes(replay, minimum_score=args.minimum_score)
    features = calculate_candidate_features(replay, minimum_score=args.minimum_score)
    output = outcomes.merge(features, on="timestamp", how="left", validate="one_to_one")
    save_path = Path(f"artifacts/{symbol}/{args.date}/candidate_outcomes.csv")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(save_path, index=False)
    print(f"Saved {len(output)} candidates to {save_path}")
    for column in ("session_phase", "episode_signal_ordinal", "first_signal_in_episode"):
        print(f"\nBy {column}:\n{_summary(output, column).to_string()}")


if __name__ == "__main__":
    main()
