import argparse
from pathlib import Path

import pandas as pd

from aml.candidate_outcomes import analyze_candidate_outcomes


def parser():
    p = argparse.ArgumentParser(description="Analyze historical replay candidates")
    p.add_argument("symbol", nargs="?", default="GME")
    p.add_argument("date", nargs="?", default="2024-05-13")
    p.add_argument("--minimum-score", type=int, default=55)
    return p


def main():
    args = parser().parse_args()
    symbol = args.symbol.upper()
    path = Path(f"artifacts/{symbol}/{args.date}/replay_log.csv")
    replay = pd.read_csv(path)
    replay["timestamp"] = pd.to_datetime(replay["timestamp"])

    bars_path = Path(f"data/processed/{symbol}/{args.date}_1min.csv")
    if bars_path.exists():
        bars = pd.read_csv(bars_path, usecols=["timestamp", "high", "low"])
        bars["timestamp"] = pd.to_datetime(bars["timestamp"])
        replay = replay.merge(bars, on="timestamp", how="left", validate="one_to_one")

    output = analyze_candidate_outcomes(replay, minimum_score=args.minimum_score)
    save_path = Path(f"artifacts/{symbol}/{args.date}/candidate_outcomes.csv")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(save_path, index=False)
    print(f"Saved {len(output)} candidates to {save_path}")


if __name__ == "__main__":
    main()
