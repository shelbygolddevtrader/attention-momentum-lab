# Professional Strategy Benchmark Olympics Final Scoring V004

This prospective, design-only clarification freezes the last mathematics needed before an Olympics orchestrator may be implemented. It does not authorize or perform a synthetic, historical, validation, holdout, paper, live, or official run.

## Frozen identity and lineage

- Bundle: `205c126be0d3f1af78899b69609a6ba86a0026ec6dd55729112da78eaa4f23bc`
- Design base: `ffd76b18d635f22777e26431979037f0965ef1fd`
- V003 scoring predecessor: `7f1656ffbd4e577dd1b58019b67a50a48acf0be1d8a05646c8066758644eae81`
- Immutable V0.1.1 tag object: `746e147efd9bb09dedfdd4d2850f461e36d9f046`
- Immutable V0.1.1 tagged commit: `378317dba28d93792d2f0a3ab4302a5d0b6abf7c`

The machine-readable contract is [professional_strategy_olympics_final_scoring_v004.json](../config/professional_strategy_olympics_final_scoring_v004.json). Every section and the complete bundle have independent SHA-256 identities.

## Exact arithmetic and lifecycle

V002 lifecycle values are canonicalized at the inherited serialization boundaries: prices and P&L become integer microdollars after six-decimal half-even serialization; net R becomes an exact rational after twelve-decimal serialization. From that point forward, scoring uses integers, reduced fractions, and an exact algebraic comparator only. There is no floating tolerance, intermediate rounding, or signed zero.

The lifecycle contract freezes next-bar entry, conservative stop-before-target same-bar precedence, gap exits, timeouts, missing-minute and halt behavior, corporate actions, duplicates, and long/short P&L. Invalid post-fill information is never replaced with a convenient outcome.

Each entrant has an isolated $100,000 ledger. Exits are applied before lockout state and entries at a shared timestamp. Proposal order, whole-share sizing, three-position concurrency, 50% gross exposure, cash reservation/release, same-security conflicts, and the daily lockout are deterministic. No entrant can affect another entrant.

## Fifteen raw events

The registry freezes all 15 V001 events: net expectancy, downside-adjusted return, maximum drawdown, profit factor, payoff ratio, hit rate, tail loss, monthly stability, regime stability, validation consistency, holdout consistency, capital efficiency, trade sufficiency, execution robustness, and sensitivity robustness. Each entry defines inputs, population, timestamp, formula, precision, missing/zero/non-finite handling, minimum observations, aggregation, weight, ties, and stage availability. Weights remain 100 in total and V003 percentile/ranking behavior is unchanged.

Maximum drawdown groups exits at the same UTC instant before updating the equity path. Tail loss uses `ceil(n/20)`. Monthly stability uses New York exit months and the exact even-sample median. Regime stability requires a separately frozen pre-outcome regime manifest; it cannot be derived from results. Validation and holdout events remain unavailable until their separately governed stages are opened.

## Capital efficiency

For accepted, filled, valid, completed discovery positions:

`sum(net P&L microdollars) / sum(abs(actual quantity) × adjusted entry microdollars × (exit ns - entry ns))`

Intervals are exact, half-open, and UTC-normalized. Sequential reuse is counted only while redeployed; overlaps add; long and short notionals never net; unused cash and rejected/unfilled proposals are excluded. A zero denominator is event-ineligible rather than zero or infinity. The frozen examples cover a fully deployed position, sequential reuse, overlapping positions, cash-capped partial deployment, no trades, and a high-profit/high-capital versus modest-profit/efficient comparison.

## Cost stress

Execution robustness reuses the immutable baseline proposals, raw entry/exit prices, stops, targets, timestamps, portfolio acceptance, and actual quantities. It does not regenerate signals, reevaluate eligibility, resize, reallocate, or rerun the portfolio.

The three exact scenarios are 1x, 1.5x, and 2x. Each multiplies the combined adverse market friction, per-share commission, minimum commission, and evidenced borrow fee. The raw event is the minimum exact scenario expectancy. A stressed entry at or above the frozen target, or another unavailable/nonpositive stressed fill, makes the event ineligible. This is not silently turned into a loss or a new exit bar. Synthetic examples freeze stable/identical costs, gradual degradation, positive-baseline/negative-stress, infeasible fills, and zero/no-trade behavior; none is an empirical result.

## Failure handling and publication

The disqualification matrix separates proposal rejection, trade rejection, event failure, entrant disqualification, and tournament abort. Integrity failures never become merely poor scores. Output collision, common-input defects, sealed-boundary access, and partial publication abort the tournament. The future orchestrator must use write-once output identities and completion manifests.

All execution authorization flags are false. The next milestone may implement a versioned orchestrator against these exact bytes, but it still requires exact-head CI and separate human authorization before any trial.

## Validation

```bash
PYTHONPATH=src python scripts/validate_professional_strategy_olympics_final_scoring_v004.py
python -m pytest tests/test_professional_strategy_olympics_final_scoring_v004.py
```

The validator reads contracts and Git lineage only. It has no market-data, broker, runner, or results interface.
