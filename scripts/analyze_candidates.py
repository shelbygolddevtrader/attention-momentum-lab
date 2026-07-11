import argparse
from pathlib import Path

import pandas as pd

from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.candidate_features import calculate_candidate_features
from aml.thresholds import CANDIDATE_SCORE_THRESHOLD


def parser():
    p = argparse.ArgumentParser(description="Analyze historical replay candidates")
    p.add_argument("symbol", nargs="?", default="GME")
    p.add_argument("date", nargs="?", default="2024-05-13")
    p.add_argument("--candidate-score-threshold", type=int)
    p.add_argument("--minimum-score", type=int, help=argparse.SUPPRESS)
    return p


def resolve_candidate_score_threshold(p, args):
    """Resolve deprecated --minimum-score as a research-only CLI alias."""
    canonical, legacy = args.candidate_score_threshold, args.minimum_score
    if canonical is not None and legacy is not None and canonical != legacy:
        p.error(
            "conflicting thresholds: --candidate-score-threshold and deprecated "
            "--minimum-score must match"
        )
    return canonical if canonical is not None else legacy if legacy is not None else CANDIDATE_SCORE_THRESHOLD


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
    p = parser()
    args = p.parse_args()
    args.candidate_score_threshold = resolve_candidate_score_threshold(p, args)
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

    outcomes = analyze_candidate_outcomes(replay, candidate_score_threshold=args.candidate_score_threshold)
    features = calculate_candidate_features(replay, candidate_score_threshold=args.candidate_score_threshold)

    if len(outcomes) != len(features):
        raise RuntimeError(
            "Candidate outcome and feature calculations returned different row counts: "
            f"{len(outcomes)} outcomes versus {len(features)} features."
        )

    if outcomes.empty:
        feature_columns = [
            column for column in features.columns if column != "timestamp"
        ]
        output = pd.concat(
            [
                outcomes.reset_index(drop=True),
                features[feature_columns].reset_index(drop=True),
            ],
            axis=1,
        )
    else:
        output = outcomes.merge(
            features,
            on="timestamp",
            how="left",
            validate="one_to_one",
        )

    save_path = Path(f"artifacts/{symbol}/{args.date}/candidate_outcomes.csv")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(save_path, index=False)
    print(f"Saved {len(output)} candidates to {save_path}")

    if output.empty:
        print(
            f"No candidates met the candidate score threshold of {args.candidate_score_threshold}; "
            "summary groupings were not calculated."
        )
        return

    for column in ("session_phase", "episode_signal_ordinal", "first_signal_in_episode"):
        print(f"\nBy {column}:\n{_summary(output, column).to_string()}")


if __name__ == "__main__":
    main()
