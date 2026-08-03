# Nine-Strategy Discovery Screen V001

## Status

This milestone is a non-authoritative discovery-only screen. It is not validation, a holdout, a forward test, an Olympics result, or trading authorization.

The screen used only 2023-07-24 through 2024-12-31. No later dataset session was opened by the adapter. The fixed 23-symbol universe creates material survivorship and selection bias.

## Evidence

- Dataset manifest SHA-256: `b8358cb55c43342e832c18e3d7a3cd2b2943326f58cbc76a60fde6fac70ae53b`
- Dataset fingerprint: `fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d`
- Calendar identity: `8b9ea9f8edfd4a43b4b3c886496c1d14b1a81285b88cc42aab217a7896a8a4e1`
- Halt identity: `57b84efe0be071bb5be03e7b18d083a9b4972fd4091f2ed93604d218032c781a`
- Corporate-action identity: `d7436e94f6d15749a96ba2d5f474b2220337e67b7a2509cabf17fc609c07424d`
- Preflight identity: `df473daf269d01a8e070b37264de57ff9c0b595567915b7326b89243e73b1510`
- Screen identity: `6e1c58b8e09bb02965dd96a0d96a308416439ab0c7bb131781ceb4626e4cc68f`
- Screen artifact identity: `43c117fbff9b25d9a1de22b0a65f455eee2929ec280b68f5f0d75fdaa97f3c82`
- Analysis artifact identity: `bb0e529d4916801dfed8ce060e0785684fc27582ed308e330fe07a768190db74`

Nasdaq Trader supplied 527 complete daily raw responses: 14 dates contained a halt for the universe and 513 were complete negative responses. The normalized universe ledger contains 90 halts: GME 55, AMC 33, SQQQ 1, and UVXY 1. The 25 stored GME records for May 13–14, 2024 reconcile exactly.

The Alpaca Market Data corporate-actions query completed in one page for all 23 symbols. It returned 117 actions: 110 cash dividends, three reverse splits, one forward split, one stock dividend, one spin-off, and one stock merger. The endpoint supplied no historical creation/revision timestamps. Retroactively adjusted observations at or before non-cash actions were therefore excluded rather than treated as point-in-time data.

## Preflight

The deterministic preflight contains 75,348 rows (nine strategies × 23 symbols × 364 sessions). It found, per strategy, 1,109 unexplained regular-gap symbol-sessions and 719 corporate-action-unresolved symbol-sessions. History-dependent strategies also had 462 warm-up exclusions. A coverage loss greater than 10% is treated conservatively as material and forces `INCONCLUSIVE_DATA_LIMITATION`; this rule depends only on input coverage, not outcomes.

## Empirical results after base costs

| Strategy | Trades | Net P&L | Expectancy | Profit factor | Win rate | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Failed downside breakdown reclaim | 1,201 | -$64,798.08 | -$53.95 | 0.313 | 18.7% | $64,990.91 |
| Fifteen-minute ORB | 1,227 | -$40,364.53 | -$32.90 | 0.496 | 26.7% | $40,418.15 |
| First-pullback continuation | 14 | +$1,014.35 | +$72.45 | 1.467 | 50.0% | $1,221.63 |
| Five-minute ORB | 1,382 | -$45,163.02 | -$32.68 | 0.521 | 24.7% | $46,169.62 |
| High-of-day breakout | 17 | -$1,861.48 | -$109.50 | 0.357 | 17.6% | $2,471.93 |
| Market-relative momentum | 273 | -$17,598.64 | -$64.46 | 0.487 | 34.1% | $17,796.10 |
| RSI exhaustion reversion | 21 | -$3,408.25 | -$162.30 | 0.273 | 23.8% | $3,408.25 |
| VWAP mean-reversion fade | 2,909 | -$94,987.27 | -$32.65 | 0.201 | 13.5% | $94,987.69 |
| VWAP reclaim | 2,647 | -$82,812.98 | -$31.29 | 0.354 | 17.1% | $82,812.98 |

Eight strategies were negative under base costs and deteriorated further at 1.5× and 2× variable execution costs. First-pullback continuation remained positive under all three cost assumptions, but 14 trades are below the frozen 30-trade minimum. Its base net profit was also dominated by GME ($1,080.18) while PLTR lost $311.35, and the largest winning trade contributed 47.2% of total net profit. It therefore does not demonstrate repeatability.

All ten classifications are `INCONCLUSIVE_DATA_LIMITATION`. For gap-and-go specifically, the missing inputs are 09:25–09:29 ET premarket bars, V002-complete historical premarket baselines, and an independent official prior close. It did not execute.

## Lifecycle and integrity

The adapter uses the unchanged frozen V002 proposal evaluators, next-bar entry, stop-before-target ordering, complete-bar timeouts, early-close liquidation, exact halt intervals (including removal of every partially overlapping minute), $250 risk budget, 10 basis points per side, and the frozen commission schedule. The 1.5× and 2× scenarios change only variable execution friction. Proposal counts reconcile exactly to accepted trades plus lifecycle rejections, and each cost scenario has the same completed-trade count. The accepted screen has zero executor integrity failures.

Candidate gates encode necessary conditions only. They cannot create a proposal; every surviving candidate is decided by the unchanged frozen evaluator.

## Remaining limitations and next action

The fixed universe is not a point-in-time universe. Alpaca `adjustment=all` is a current adjusted view, while the corporate-action endpoint lacks historical first-known/revision lineage. Many no-trade minutes appear as absent bars and cannot be distinguished from missing data under the frozen completeness contract. These limitations affect more than 10% of symbol-sessions.

The highest-value next action is to obtain or construct independently verifiable point-in-time corporate-action lineage and complete minute-presence evidence for an additional untouched discovery sample. Then rerun the same frozen screen without changing parameters. Only if first-pullback continuation reaches adequate, less-concentrated evidence should broader discovery be considered; optimization is not justified now.
