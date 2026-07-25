# Strategy V0.1.1 development/validation baseline

Run `564345a77176524eb250` is the corrected Strategy V0.1.1 development and
validation baseline. Its integrity result passed. The holdout was not run or
inspected and remains untouched.

This designation supersedes run `52cbe99a07595ee40dba` as the corrected
baseline. The older run remains historically reproducible, but it is not a
valid baseline for the corrected engine because its five-minute return feature
could use five rows instead of requiring a price exactly five elapsed minutes
earlier when bars were missing.

## Baseline result

| Split | Strategy version | Signals | Accepted trades | Net P&L | Integrity |
| --- | --- | ---: | ---: | ---: | --- |
| Development | 0.1.1 | 159 | 120 | -$371.96 | Passed |
| Validation | 0.1.1 | 161 | 94 | +$61.15 | Passed |

The correction removed seven development signals, all from the two known gappy
GME sessions (2024-06-11 and 2024-12-05). Validation was unchanged. The run
reports an `active_symbol_distribution_shift` warning; this is an observability
warning, not an integrity failure.

## Strategy leaderboard

Gross loss is shown as a negative amount. Maximum drawdown is the persisted
leaderboard return drawdown. `no_trade` is a flat control, so rate and average
metrics are not applicable.

### Development

| Strategy | Signals | Trades | W | L | Win rate | Gross win | Gross loss | Net P&L | Exp./trade | PF | Max DD | Avg win | Avg loss | Best | Worst | Accept. | Symbols | Dates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| attention_momentum | 159 | 120 | 32 | 88 | 26.67% | $511.87 | -$883.83 | -$371.96 | -$3.10 | 0.58 | -19.36% | $16.00 | -$10.04 | $19.30 | -$10.66 | 75.47% | 3 | 60 |
| ema_momentum_cross | 2,006 | 1,966 | 787 | 1,179 | 40.03% | $4,203.48 | -$6,139.76 | -$1,936.28 | -$0.98 | 0.68 | -98.87% | $5.34 | -$5.21 | $19.31 | -$10.66 | 98.01% | 21 | 357 |
| no_trade | 0 | 0 | 0 | 0 | n/a | $0.00 | $0.00 | $0.00 | n/a | n/a | 0.00% | n/a | n/a | n/a | n/a | n/a | 0 | 0 |
| opening_range_breakout | 4,042 | 3,316 | 1,014 | 2,302 | 30.58% | $3,429.65 | -$7,249.31 | -$3,819.66 | -$1.15 | 0.47 | -191.21% | $3.38 | -$3.15 | $19.31 | -$10.66 | 82.04% | 23 | 364 |
| volume_spike_breakout | 18,918 | 13,699 | 3,216 | 10,483 | 23.48% | $9,569.07 | -$25,477.75 | -$15,908.67 | -$1.16 | 0.38 | -795.43% | $2.98 | -$2.43 | $19.31 | -$11.35 | 72.41% | 23 | 364 |
| vwap_mean_reversion | 2,343 | 1,765 | 681 | 1,084 | 38.58% | $3,244.35 | -$5,409.52 | -$2,165.17 | -$1.23 | 0.60 | -108.22% | $4.76 | -$4.99 | $19.29 | -$10.66 | 75.33% | 18 | 325 |
| vwap_reclaim | 935 | 904 | 323 | 581 | 35.73% | $1,245.24 | -$2,575.68 | -$1,330.44 | -$1.47 | 0.48 | -67.41% | $3.86 | -$4.43 | $19.29 | -$10.66 | 96.68% | 19 | 317 |

### Validation

| Strategy | Signals | Trades | W | L | Win rate | Gross win | Gross loss | Net P&L | Exp./trade | PF | Max DD | Avg win | Avg loss | Best | Worst | Accept. | Symbols | Dates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| attention_momentum | 161 | 94 | 40 | 54 | 42.55% | $563.82 | -$502.68 | +$61.15 | +$0.65 | 1.12 | -4.01% | $14.10 | -$9.31 | $19.30 | -$10.65 | 58.39% | 20 | 29 |
| ema_momentum_cross | 1,392 | 1,369 | 531 | 838 | 38.79% | $2,732.01 | -$4,499.80 | -$1,767.80 | -$1.29 | 0.61 | -88.55% | $5.15 | -$5.37 | $19.28 | -$10.66 | 98.35% | 22 | 236 |
| no_trade | 0 | 0 | 0 | 0 | n/a | $0.00 | $0.00 | $0.00 | n/a | n/a | 0.00% | n/a | n/a | n/a | n/a | n/a | 0 | 0 |
| opening_range_breakout | 2,701 | 2,125 | 613 | 1,512 | 28.85% | $2,003.92 | -$4,667.70 | -$2,663.78 | -$1.25 | 0.43 | -133.19% | $3.27 | -$3.09 | $19.31 | -$10.66 | 78.67% | 23 | 249 |
| volume_spike_breakout | 11,499 | 8,532 | 1,964 | 6,568 | 23.02% | $5,699.12 | -$16,086.34 | -$10,387.22 | -$1.22 | 0.35 | -519.13% | $2.90 | -$2.45 | $19.31 | -$10.66 | 74.20% | 23 | 250 |
| vwap_mean_reversion | 1,628 | 1,243 | 490 | 753 | 39.42% | $2,333.08 | -$3,840.42 | -$1,507.35 | -$1.21 | 0.61 | -75.81% | $4.76 | -$5.10 | $19.30 | -$10.66 | 76.35% | 21 | 196 |
| vwap_reclaim | 746 | 723 | 273 | 450 | 37.76% | $1,171.82 | -$2,086.65 | -$914.83 | -$1.27 | 0.56 | -45.79% | $4.29 | -$4.64 | $19.30 | -$10.66 | 96.92% | 23 | 212 |

## Development versus validation

- No active strategy was profitable in both splits or profitable only in
  development.
- `attention_momentum` was profitable only in validation. Its win rate, profit
  factor, drawdown, and expectancy improved, while its acceptance rate fell and
  its active-symbol count rose from 3 to 20.
- `ema_momentum_cross`, `opening_range_breakout`, `volume_spike_breakout`,
  `vwap_mean_reversion`, and `vwap_reclaim` were unprofitable in both splits.
- `no_trade` was the flat control, not a profitable strategy.
- With the configured 100-trade minimum, validation `attention_momentum` (94
  trades) and `no_trade` have insufficient samples. Development
  `attention_momentum` clears the threshold narrowly with 120 trades.

The large attention-momentum active-symbol shift remains a robustness warning.
It is not explained by missing processed sessions or reconciliation failures in
the corrected artifacts.

## Validation breakdown and concentration

All 14,086 accepted validation trades were long; the persisted run contains no
short-side observations. The artifacts have no explicit market-regime label,
so date and month are the available volatility-period proxies.

### Attention-momentum by symbol

| Symbol | Trades | Wins | Net P&L | Symbol | Trades | Wins | Net P&L |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| TQQQ | 11 | 6 | +$36.65 | NVDA | 3 | 1 | -$1.38 |
| AAPL | 2 | 2 | +$29.58 | DIA | 2 | 1 | -$2.03 |
| USO | 3 | 2 | +$22.78 | IWM | 5 | 2 | -$4.16 |
| XLF | 1 | 1 | +$19.28 | SPXS | 2 | 0 | -$19.82 |
| XLE | 1 | 1 | +$18.53 | GME | 5 | 2 | -$27.97 |
| AMD | 4 | 2 | +$17.47 | AMC | 11 | 3 | -$35.61 |
| PLTR | 4 | 2 | +$16.81 | UVXY | 18 | 5 | -$48.08 |
| SQQQ | 2 | 1 | +$10.74 |  |  |  |  |
| TSLA | 3 | 2 | +$7.21 |  |  |  |  |
| SPY | 2 | 1 | +$6.76 |  |  |  |  |
| XLK | 2 | 1 | +$6.18 |  |  |  |  |
| QQQ | 2 | 1 | +$5.81 |  |  |  |  |
| SPXL | 11 | 4 | +$2.41 |  |  |  |  |

Across the full validation portfolio, every strategy had all-long exposure.
The best aggregate symbol was SPY at -$279.56, so no symbol was profitable
after aggregating every strategy. Strategy-specific extremes were: EMA
TSLA +$27.47 versus UVXY -$501.70; opening-range breakout had no profitable
symbol; volume-spike breakout had no profitable symbol; VWAP mean reversion
SPY +$1.32 versus UVXY -$308.91; and VWAP reclaim GME +$24.93 versus UVXY
-$192.70.

### Score/confidence, time, and exits

For attention-momentum, score bands 70-79, 80-89, and 90-100 produced 2, 2,
and 90 trades with net P&L of -$5.47, -$10.55, and +$77.16. This is descriptive
only; the lower bands are too small for comparative inference.

Its 09:30-10:29, 10:30-13:29, and 13:30-16:00 buckets produced 19, 64, and 11
trades with net P&L of -$48.95, +$136.36, and -$26.27. Exit results were:
session end, 2 trades and +$4.74; stop, 51 and -$493.47; target, 28 and
+$491.07; time limit, 13 and +$58.81.

All five losing active strategies were negative in each broad time bucket.
Across them, stop exits and time-limit exits were the main loss sources;
target exits were positive. This does not establish causality because entry
selection, price path, and exit type are jointly determined.

### Date and outlier concentration

The full validation portfolio lost $17,179.83. Attention-momentum supplied 100%
of positive strategy-level net P&L, but its $61.15 gain offset only 0.36% of the
other strategies' aggregate loss. The portfolio's top date was 2025-04-09 at
+$444.47; it equaled 58.31% of all positive-day P&L and offset 2.59% of the
total portfolio loss. The top five trades totaled +$96.52, only 0.67% of the
$14,503.76 gross positive trade P&L, so the full portfolio was not dominated by
one winning trade.

Attention-momentum itself was date-concentrated. TQQQ supplied $36.65, or
59.93% of its net P&L, although only 18.30% of its positive-symbol P&L.
2025-04-09 supplied $211.35, or 345.66% of attention-momentum net P&L and
72.53% of its positive-day P&L. Excluding that date changes its result to
-$150.21. April supplied +$170.46; excluding April changes the result to
-$109.31. Its top five trades totaled +$96.25, or 157.42% of net P&L but only
17.07% of gross positive trade P&L. The largest single trade was 3.42% of gross
positive trade P&L. The concern is therefore date/period concentration, not a
single oversized trade.

The full portfolio's strongest dates were 2025-04-09 (+$444.47), 2025-05-30
(+$79.40), 2025-08-22 (+$60.26), and 2025-10-10 (+$45.79). Its weakest included
2025-04-07 (-$406.99), 2025-04-08 (-$294.25), 2025-04-10 (-$222.52), and
2025-04-30 (-$208.57).

## Descriptive observations and hypotheses

Descriptive observations supported by persisted artifacts:

- Only attention-momentum was profitable in validation, and it had fewer than
  100 validation trades.
- Its validation gain disappears without 2025-04-09 or without April 2025.
- The adjacent 2025-04-07 through 2025-04-10 period contains the best portfolio
  date and three of the four worst listed dates.
- No individual winning trade dominates aggregate gross positive P&L.
- Integrity and count/P&L reconciliation passed; the active-symbol shift is a
  warning rather than an input-coverage failure.

Hypotheses requiring additional pre-specified research:

- The April cluster may reflect an event-driven or elevated-volatility regime.
- Attention-momentum may respond differently to that environment than the
  other strategies.
- The broader validation symbol participation may be a real feature-distribution
  change rather than a defect.

No regime conclusion can be made from this run because regime labels were not
persisted. No parameter tuning is recommended or performed in this review.

## Reconciliation and artifact provenance

For every split-strategy pair, signal counts reconcile between `signals.csv`
and `session_results.csv`; accepted statuses reconcile with `trades.csv` and
the leaderboard trade count; and trade net P&L reconciles with both session
results and `leaderboard.csv`. Signal counts also reconcile with accepted plus
rejected counts. No holdout artifact was used.

All reviewed inputs are persisted under:

`artifacts/tournaments/564345a77176524eb250/final/`

Specifically: `run_manifest.json`, `leaderboard.csv`, `session_results.csv`,
`signals.csv`, `trades.csv`, `strategy_symbol_metrics.csv`,
`strategy_month_metrics.csv`, `attention_momentum_audit.csv`,
`attention_momentum_diagnostics.csv`, `attention_momentum_analysis.txt`, and
`summary.md`.
