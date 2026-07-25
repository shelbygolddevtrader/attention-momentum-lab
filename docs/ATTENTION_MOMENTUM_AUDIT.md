# Attention-Momentum Tournament Audit

The corrected elapsed-time strategy identity is `attention_momentum` v0.1.1.
Run `52cbe99a07595ee40dba` used v0.1.0 and remains historically reproducible,
but it is not a valid baseline for the corrected engine.

The tournament publishes `attention_momentum_audit.csv` and
`attention_momentum_diagnostics.csv` beside its other final artifacts. The audit
is sorted by split and symbol. Diagnostics are sorted by split, symbol, trading
date, timestamp, and proposal ID.

The compatibility strategy retains its original additive score:

- five-row return at least 3%: 35 points
- current volume at least 3 times the median of up to 20 prior rows: 35 points
- close at least 1% above causal session VWAP: 20 points
- current volume at least 1.5 times the mean of up to 5 prior rows: 10 points
- eligible score: at least 70 points

Consequently, every eligible row must pass both the return and relative-volume
thresholds. NaN comparisons are false. The first five rows of each independent
session are warm-up rows and cannot qualify. Session VWAP includes the current
row and earlier rows; volume baselines exclude the current row. Signals become
actionable one minute after the left-labeled source bar.

`return_window` now requires an observation at exactly that many elapsed minutes
before the current bar. A missing-minute or halt gap therefore produces NaN
rather than silently turning a five-minute feature into a longer-period return.
The audit still emits `non_contiguous_minute_rows`. Analysis of artifacts created
before this fix uses their original row-window calculation and emits
`legacy_row_return_semantics`, so it explains the recorded run rather than
rewriting history.

Coverage and timestamp-integrity defects fail the tournament. A change in the
number or concentration of active symbols emits a warning because it can be a
legitimate regime change.

Analyze any completed run without using timestamp timezone offsets for calendar
grouping:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_tournament_attention.py \
  --run-id <run-id>
```

Calendar month summaries use `trading_date`; timestamp parsing uses UTC where
timestamp ordering is required.

## Corrected elapsed-time defect

Run `52cbe99a07595ee40dba` exposed seven GME development signals on 2024-06-11
and 2024-12-05 where the former `pct_change(5)` implementation crossed four
unverified missing minutes. Five rows therefore spanned nine elapsed minutes.
`src/aml/signals.py` now performs an exact timestamp lookup at five elapsed
minutes. A missing exact prior timestamp yields NaN and cannot score.

The old run remains an immutable record of the former engine, and its analysis
uses legacy reconstruction to explain its stored signals. Its performance result
is invalidated for comparison with the corrected engine and must be rerun. The
known direct effect is removal or rescoring of those seven signals and their
trades; downstream metrics must be regenerated rather than adjusted by hand.
