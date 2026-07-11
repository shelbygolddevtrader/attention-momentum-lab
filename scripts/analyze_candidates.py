import argparse

import pandas as pd

from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.candidate_features import calculate_candidate_features
from aml.data_paths import (
    HISTORICAL_DATA_FEED, LEGACY_FEED, RESEARCH_FEEDS, artifact_directory,
    load_bars, validate_replay_feed,
)
from aml.thresholds import CANDIDATE_SCORE_THRESHOLD
from aml.market_halts import CompletenessMode, load_verified_halts


def parser():
    p = argparse.ArgumentParser(description="Analyze historical replay candidates")
    p.add_argument("symbol", nargs="?", default="GME")
    p.add_argument("date", nargs="?", default="2024-05-13")
    p.add_argument("--feed", choices=(*RESEARCH_FEEDS, LEGACY_FEED), default=HISTORICAL_DATA_FEED)
    p.add_argument("--completeness-mode", choices=[mode.value for mode in CompletenessMode], default=CompletenessMode.HALT_AWARE.value)
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
    root = artifact_directory(symbol, args.date, args.feed)
    validate_replay_feed(root, args.feed, args.completeness_mode)
    halts = load_verified_halts(symbol, args.date)
    print(
        f"Feed={args.feed}; completeness_mode={args.completeness_mode}; "
        f"verified_halts={len(halts.records)}; "
        f"full_halt_minutes={len(halts.full_halt_minutes)}"
    )
    path = root / "replay_log.csv"
    replay = pd.read_csv(path)
    replay["timestamp"] = pd.to_datetime(replay["timestamp"])

    bars = load_bars(symbol, args.date, args.feed)
    replay = replay.merge(
        bars[["timestamp", "open", "high", "low", "close"]],
        on="timestamp", how="left", validate="one_to_one",
    )

    outcomes = analyze_candidate_outcomes(
        replay, candidate_score_threshold=args.candidate_score_threshold,
        completeness_mode=args.completeness_mode, halt_schedule=halts,
    )
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

    save_path = root / "candidate_outcomes.csv"
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
