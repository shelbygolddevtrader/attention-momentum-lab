# Strategy Constitution v0.1.0

## Hypothesis

Abnormal short-term price acceleration combined with increasing relative volume and positive distance from session VWAP may predict short-term momentum continuation better than random entry.

## Rules

1. Replay exposes only information timestamped at or before the replay clock.
2. The universe may not be selected from a hindsight list of winners.
3. Every candidate is logged, including rejected and losing candidates.
4. Any feature, threshold, fill, or risk change creates a new version.
5. Social data, AI interpretation, options, and live trading are excluded from this baseline.
6. Attractive charts are not evidence; out-of-sample and shadow results determine whether the hypothesis survives.
