# Nine-Strategy Discovery Screen V001

## Status

This is a corrected, non-authoritative discovery-only screen. It is not validation, a holdout, a forward test, an Olympics result, or trading authorization. The accepted replacement is `run-v012`, executed from source commit `5c1fedafb6ebaff3a0ed4655d8d1f5294f4da946` over 2023-07-24 through 2024-12-31 only.

The original `run-v010` is preserved as historically reproducible evidence of a failed audit. Its trade counts and P&L are not certifiable because 704 executor integrity failures were silently omitted from aggregation. `run-v011` is preserved as the pre-commit corrective rehearsal; its output is byte-identical to `run-v012` but it is not the designated accepted replacement.

## Audit failure and root cause

The independent audit found 704 executor integrity failures in `run-v010`: 674 `bars:unclassified_minute_gap` and 30 `bars:missing_segment_start` failures, represented by 46 aggregate rows across 13 AMC/GME sessions. Its persisted data-quality report correctly contained 704, while the committed metadata and prose incorrectly claimed zero.

Bars are complete left-labeled intervals: a bar stamped `t` represents `[t,t+1 minute)`. Official halts use `[start,resume)`. The discovery adapter conservatively removed a bar whenever those intervals overlapped. The unchanged frozen executor validator, however, classified a missing minute as halt-covered only when its left-label timestamp fell inside the halt. For a halt starting at 09:35:46, the adapter removed `[09:35:00,09:36:00)`, while the validator did not recognize 09:35:00 as halted. That mismatch produced the audit failures.

Changing the validator would change a shared frozen indicator/executor implementation identity and would reinterpret already-frozen contracts. The narrow correction therefore preserves every strategy, indicator, threshold, lifecycle, cost, portfolio, classification, and research-period rule. Preflight now excludes an entire symbol-session whenever interval-overlap removal contains a minute the frozen point validator cannot represent. A successful screen is executable-code-gated on exactly zero executor integrity failures; a nonzero count publishes only diagnostic failure artifacts and never performance artifacts.

## Evidence and identities

- Dataset manifest SHA-256: `b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b`
- Dataset fingerprint: `fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d`
- Calendar identity: `8b9ea9f8edfd4a43b4b3c886496c1d14b1a81285b88cc42aab217a7896a8a4e1`
- Halt identity: `57b84efe0be071bb5be03e7b18d083a9b4972fd4091f2ed93604d218032c781a`
- Corporate-action identity: `d7436e94f6d15749a96ba2d5f474b2220337e67b7a2509cabf17fc609c07424d`
- Corrected Preflight Identity: `4193d92d02868857952ad346503a957604ce901b50332618b8cd744884ce79c4`
- Corrected Screen Identity: `c8a396e57ad6ea95add2abbc16abb991da51f79ed41c9d47844d0188feadefc1`
- Corrected Screen Artifact Identity: `b3d69ad4ebe539e79a42be346e4a3101da644fe19d6e1f1b7b954dd0a428ebd6`
- Corrected Analysis Artifact Identity: `ec05b9dcd070a3cad7268434a697a2a18029fa1fdd53d0d2e797e5893cb21451`
- Corrected reconciliation identity: `329c6ef167904f844ea1016f922f37a8348d9b92f5b95091d6c2f1138dc596c5`

Superseded `run-v010` identities are retained in `config/nine_strategy_discovery_screen_v001_metadata.json`: preflight `df473daf269d01a8e070b37264de57ff9c0b595567915b7326b89243e73b1510`, screen `6e1c58b8e09bb02965dd96a0d96a308416439ab0c7bb131781ceb4626e4cc68f`, screen artifact `43c117fbff9b25d9a1de22b0a65f455eee2929ec280b68f5f0d75fdaa97f3c82`, and analysis artifact `bb0e529d4916801dfed8ce060e0785684fc27582ed308e330fe07a768190db74`.

Nasdaq Trader supplied 527 complete daily raw responses: 14 dates contained a halt for the universe and 513 were complete negative responses. The normalized universe ledger contains 90 halts: GME 55, AMC 33, SQQQ 1, and UVXY 1. The Alpaca corporate-actions query returned 117 actions, but no historical creation/revision timestamps; retroactively adjusted observations at or before non-cash actions remain excluded.

## Corrected preflight

The deterministic preflight contains 75,348 rows: nine strategies × 23 symbols × 364 sessions. Across all strategies it records exactly 18,435 exclusions:

| Reason | Excluded strategy-session rows |
|---|---:|
| Unexplained regular gap | 9,981 |
| Corporate action unresolved | 6,453 |
| Warm-up incomplete | 1,848 |
| Halt interval incompatible with frozen validator | 144 |
| Strategy input unavailable | 9 |
| **Total** | **18,435** |

Each strategy has 1,109 unexplained-gap exclusions, 717 corporate-action exclusions, 16 incompatible-halt exclusions, and one unavailable-input exclusion. The four history-dependent strategies each also have 462 warm-up exclusions. This leaves 6,529 included rows for each non-history-dependent strategy and 6,067 for each history-dependent strategy.

The 144 incompatible rows are nine strategy evaluations for each of these 16 symbol-sessions:

- AMC: 2023-07-24, 2023-08-22, 2024-05-14, 2024-05-15, 2024-06-03, 2024-06-07, 2024-07-22.
- GME: 2024-05-13, 2024-05-14, 2024-05-15, 2024-06-03, 2024-06-06, 2024-06-07, 2024-06-11, 2024-12-05.
- UVXY: 2024-08-06.

Eighteen of those rows previously had the higher-priority corporate-action exclusion, so accepted coverage decreased by 126 rows relative to `run-v010`. The correction excludes every session with the incompatible semantics, not only the 13 sessions that happened to surface executor failures in the old run.

## Corrected empirical results after base costs

Gross P&L below is after modeled entry/exit slippage and before commissions; net P&L is after all modeled costs.

| Strategy | Trades | Gross P&L | Net P&L | Expectancy | Profit factor | Win rate | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Failed downside breakdown reclaim | 1,205 | -$59,342.71 | -$65,712.32 | -$54.53 | 0.298 | 18.3% | $65,900.40 |
| Fifteen-minute ORB | 1,227 | -$35,964.21 | -$40,364.53 | -$32.90 | 0.496 | 26.7% | $40,418.15 |
| First-pullback continuation | 14 | +$1,554.68 | +$1,014.35 | +$72.45 | 1.467 | 50.0% | $1,221.63 |
| Five-minute ORB | 1,378 | -$39,885.83 | -$44,933.85 | -$32.61 | 0.523 | 24.5% | $46,005.37 |
| High-of-day breakout | 17 | -$1,505.99 | -$1,861.48 | -$109.50 | 0.357 | 17.6% | $2,471.93 |
| Market-relative momentum | 270 | -$15,156.73 | -$17,574.26 | -$65.09 | 0.480 | 34.1% | $17,771.72 |
| RSI exhaustion reversion | 21 | -$2,758.74 | -$3,408.25 | -$162.30 | 0.273 | 23.8% | $3,408.25 |
| VWAP mean-reversion fade | 2,924 | -$82,766.68 | -$94,865.04 | -$32.44 | 0.202 | 13.5% | $94,865.50 |
| VWAP reclaim | 2,643 | -$71,544.40 | -$82,149.28 | -$31.08 | 0.359 | 17.3% | $82,304.21 |

Eight strategies are negative under base costs and deteriorate further at 1.5× and 2× variable execution costs. First-pullback continuation remains positive under all three cost assumptions, but its 14 trades are below the frozen 30-trade minimum. It is concentrated in three symbols; GME contributes $1,080.18 of net P&L and the largest winning trade contributes 47.2% of total net P&L. It does not demonstrate repeatability.

All ten classifications remain `INCONCLUSIVE_DATA_LIMITATION`. Gap-and-go still does not execute because 09:25–09:29 ET premarket bars, V002-complete historical premarket baselines, and an independent official prior close are unavailable.

## Reconciliation and integrity

The corrected screen has 92,320 proposals, 9,699 completed base trades, and 82,621 lifecycle rejections:

`92,320 proposals = 9,699 completed base trades + 82,621 rejected proposals`.

The evaluation ledger separately records 13,745,733 necessary-condition/no-signal outcomes, 186 no-trade executor outcomes, 557 unavailable outcomes, 92,320 proposal outcomes, and 18,435 preflight exclusions. Per-strategy proposal counts reconcile to completed trades plus rejections, and every 1.5× and 2× cost projection retains the same trade count as its base scenario.

The corrected accepted screen has `0` executor integrity failures.

This count is computed from raw executor rows and must agree with the screen summary, derived data-quality report, tracked metadata, and this document. `scripts/verify_nine_strategy_discovery_v001.py` checks artifact hashes, identities, preflight counts, executor status accounting, lifecycle equations, cost-scenario counts, classifications, metadata metrics, and prose claims. Any mismatch fails closed.

Independent recomputation from the immutable trade-level CSV reproduced trade count, gross and net P&L, modeled costs, expectancy, win rate, payoff ratio, profit factor, maximum drawdown, symbol and top-trade concentration, all cost-stress results, and all formal classifications. Full screen and analysis outputs were byte-identical under `PYTHONHASHSEED=1` with UTC and `PYTHONHASHSEED=777` with Asia/Tokyo.

## Remaining limitations and next action

The fixed 23-symbol universe is not point-in-time and creates survivorship and selection bias. Alpaca `adjustment=all` is a current adjusted view, while corporate-action evidence lacks historical first-known/revision lineage. Many absent minutes cannot be distinguished from true no-trade minutes under the frozen completeness contract. These limitations affect more than 10% of symbol-sessions and force every classification to `INCONCLUSIVE_DATA_LIMITATION` regardless of outcome.

The corrected results do not establish a profitable, validated, robust, repeatable, deployable, or capital-ready strategy. Optimization is not justified. The highest-value next evidence step remains independently verifiable point-in-time corporate-action lineage and complete minute-presence evidence for an additional untouched discovery sample, followed by the same frozen screen without parameter changes.
