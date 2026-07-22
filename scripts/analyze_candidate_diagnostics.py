import argparse

import pandas as pd

from aml.candidate_diagnostics import analyze_candidate_paths, distribution_statistics, feature_correlations
from aml.data_paths import (
    HISTORICAL_DATA_FEED, LEGACY_FEED, RESEARCH_FEEDS, artifact_directory,
    load_bars, validate_replay_feed,
)
from aml.market_halts import CompletenessMode, load_verified_halts

METRICS = [f"forward_{m}m_return" for m in (5, 15, 30)] + [f"{kind}_{m}m" for kind in ("mfe", "mae") for m in (5, 15, 30)]
FEATURES = ["episode_signal_ordinal", "signals_last_5m", "signals_last_15m", "minutes_since_previous_signal", "minutes_since_episode_start", "return_from_session_open", "return_3m", "return_5m", "return_15m", "distance_from_session_high", "pullback_from_session_high", "distance_from_session_low", "distance_from_vwap", "vwap_slope_3m", "vwap_slope_10m", "minutes_above_vwap", "volume_vs_trailing_5m_mean", "volume_vs_trailing_20m_mean", "volume_acceleration_3m", "volume_acceleration_5m", "bar_range_pct", "body_to_range_ratio", "close_location_value", "upper_wick_ratio", "lower_wick_ratio"]

def parser():
    p = argparse.ArgumentParser(description="Research-only candidate diagnostics")
    p.add_argument("symbol", nargs="?", default="GME")
    p.add_argument("date", nargs="?", default="2024-05-13")
    p.add_argument("--feed", choices=(*RESEARCH_FEEDS, LEGACY_FEED), default=HISTORICAL_DATA_FEED)
    p.add_argument("--completeness-mode", choices=[mode.value for mode in CompletenessMode], default=CompletenessMode.HALT_AWARE.value)
    return p

def view(frame, name):
    result, missing = distribution_statistics(frame, [], METRICS)
    result.insert(0, "view", name)
    return result, missing

def markdown_table(frame):
    if frame.empty:
        return "No rows."
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join("" if pd.isna(value) else str(value) for value in row) + " |")
    return "\n".join(lines)

def main():
    args = parser().parse_args()
    root = artifact_directory(args.symbol, args.date, args.feed)
    validate_replay_feed(root, args.feed, args.completeness_mode)
    halts = load_verified_halts(args.symbol, args.date)
    print(
        f"Feed={args.feed}; completeness_mode={args.completeness_mode}; "
        f"verified_halts={len(halts.records)}; "
        f"full_halt_minutes={len(halts.full_halt_minutes)}"
    )
    candidates = pd.read_csv(root / "candidate_outcomes.csv")
    candidates["timestamp"] = pd.to_datetime(candidates["timestamp"])

    if candidates.empty:
        diagnostic_columns = [
            "grouping",
            "metric",
            "candidate_count",
            "mean",
            "median",
            "standard_deviation",
            "minimum",
            "percentile_25",
            "percentile_75",
            "maximum",
            "positive_return_count",
            "positive_return_rate",
        ]
        target_stop_columns = [
            "timestamp",
            "horizon_minutes",
            "target_fraction",
            "stop_fraction",
            "outcome",
            "minutes_to_target",
            "minutes_to_stop",
        ]

        pd.DataFrame(columns=diagnostic_columns).to_csv(
            root / "candidate_diagnostics.csv",
            index=False,
        )
        pd.DataFrame(columns=target_stop_columns).to_csv(
            root / "target_stop_outcomes.csv",
            index=False,
        )

        summary = [
            f"# Candidate diagnostics: {args.symbol.upper()} {args.date}",
            "",
            "Dataset: 0 candidates; 0 episodes.",
            f"Feed: {args.feed}; completeness mode: {args.completeness_mode}; "
            f"verified halts: {len(halts.records)}; full halt minutes: {len(halts.full_halt_minutes)}.",
            "",
            "No candidates met the configured minimum score, so candidate-path "
            "and feature diagnostics were not calculated.",
            "",
            "## Limitations",
            "A zero-candidate session is a negative-control result, not evidence "
            "that the strategy is profitable or unprofitable.",
        ]
        (root / "diagnostic_summary.md").write_text(
            "\n".join(summary) + "\n"
        )

        print(f"Saved zero-candidate diagnostics to {root}")
        return

    bars = load_bars(args.symbol, args.date, args.feed)
    paths, labels = analyze_candidate_paths(
        candidates, bars, args.completeness_mode, halts
    )
    # Keep the independently calculated path metrics under their canonical
    # names; the source candidate artifact's 30m outcome columns remain intact.
    duplicates = [column for column in paths.columns if column != "timestamp" and column in candidates.columns]
    enriched = candidates.drop(columns=duplicates).merge(paths, on="timestamp", validate="one_to_one")
    labels.to_csv(root / "target_stop_outcomes.csv", index=False)
    groups = ["first_signal_in_episode", "session_phase", "episode_signal_ordinal", "signal_ordinal_today", ["first_signal_in_episode", "session_phase"]]
    pieces, missing = [], []
    for group in groups:
        cols = [group] if isinstance(group, str) else group
        stats, absent = distribution_statistics(enriched, cols, METRICS)
        stats.insert(0, "grouping", "+".join(cols))
        pieces.append(stats)
        missing.extend(absent)
    for name, subset in [("all", enriched), ("excluding_first_episode", enriched[enriched.episode_id != enriched.episode_id.min()]), ("excluding_opening_expansion", enriched[enriched.session_phase != "opening_expansion"])]:
        stats, absent = view(subset, name)
        pieces.append(stats)
        missing.extend(absent)
    diagnostics = pd.concat(pieces, ignore_index=True)
    diagnostics.to_csv(root / "candidate_diagnostics.csv", index=False)
    correlations = feature_correlations(enriched, FEATURES, ["forward_5m_return", "forward_15m_return", "forward_30m_return", "mfe_30m", "mae_30m"])
    first_later = enriched.assign(signal_group=enriched.episode_signal_ordinal.map(lambda n: "first" if n == 1 else "second" if n == 2 else "third_or_later"))
    comparison, _ = distribution_statistics(first_later, ["signal_group"], ["forward_5m_return", "forward_15m_return", "forward_30m_return", "mfe_30m", "mae_30m"])
    target = labels[(labels.horizon_minutes == 30) & (((labels.target_fraction == .01) & (labels.stop_fraction == .01)) | ((labels.target_fraction == .02) & (labels.stop_fraction == .01)) | ((labels.target_fraction == .03) & (labels.stop_fraction == .02)))].groupby(["target_fraction", "stop_fraction", "outcome"]).size().rename("candidate_count").reset_index()
    strongest = correlations.dropna(subset=["spearman_correlation"]).reindex(correlations.spearman_correlation.abs().sort_values(ascending=False).index).head(10)
    summary = [f"# Candidate diagnostics: {args.symbol.upper()} {args.date}", "", f"Dataset: {len(enriched)} candidates; {enriched.episode_id.nunique()} episodes.", f"Feed: {args.feed}; completeness mode: {args.completeness_mode}; verified halts: {len(halts.records)}; full halt minutes: {len(halts.full_halt_minutes)}.", f"Missing requested outcome columns: {', '.join(sorted(set(missing))) or 'none'}.", "", "## First / second / third-or-later", markdown_table(comparison), "", "## Target-before-stop (30m)", markdown_table(target), "", "## Strongest descriptive rank associations", markdown_table(strongest), "", "## Limitations", "Single symbol/date descriptive analysis only. Missing non-halt expected clock minutes produce insufficient target/stop labels; no forward filling or halt inference is used. Associations are not claims of prediction, profitability, or statistical significance."]
    (root / "diagnostic_summary.md").write_text("\n".join(summary) + "\n")
    print(f"Saved diagnostics for {len(enriched)} candidates to {root}")
    print(target.to_string(index=False))

if __name__ == "__main__":
    main()
