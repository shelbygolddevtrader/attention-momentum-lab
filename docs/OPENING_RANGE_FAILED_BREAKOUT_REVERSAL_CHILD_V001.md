# Opening Range Failed Breakout Reversal — Prospective Child V001

## Status and claim boundary

**EXPLORATORY ONLY — CONTAMINATED DATA — NOT EMPIRICAL EVIDENCE**

This milestone adds one deterministic reversal mechanism. It is not validation,
holdout evidence, a profitability result, production readiness, or capital
eligibility. No economic outcome field was inspected or published.

## Parent audit

The immutable parent `opening-range-failed-breakout-reversal-v001` fixes the
research mechanism: an opening-range excursion, a completed return inside the
range, and an internal-range objective. It intentionally leaves direction,
opening-range duration, excursion size, promptness, volume baseline, exact
target, stop, timeout, and re-entry semantics open. The parent remains
byte-identical and is not represented as an executable specification.

The new child is `opening-range-failed-downside-reclaim-long-v001`, revision 2,
with exact parent identity
`05d6ca28058f9807985eba7054afa30e5f580ce49d07d088320b6fbdd638a20c`.
Every added semantic choice is classified as:

`PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES`

The choices were frozen before this candidate accessed the contaminated
development sample. They were chosen once for simplicity, interpretability,
and reuse; no alternative threshold or outcome comparison was run.

## Frozen child

- Long only, regular-session minute OHLCV, price from $2 through $500.
- Opening range is exactly the five completed bars 09:30–09:34 New York time.
- Decisions run 09:49–11:00; entries run 09:50–11:01.
- The immediately prior completed bar must close below the opening-range low
  and reach at least `0.25 × ATR20` below it.
- The immediately adjacent completed bar must close strictly above the range
  low and strictly below the range high.
- Reclaim-bar volume must be at least `1.0 ×` the median volume at the identical
  clock minute from exactly the 20 most recent prior eligible sessions.
- Signal time is reclaim-bar end; entry is exact next-bar open.
- Stop is `0.05 × reclaim-bar ATR20` below the lower of breakdown and reclaim
  lows, rounded down to one cent.
- Target is the opening-range midpoint, rounded up to one cent. A target at or
  below cost-adjusted entry is a deterministic `no_trade`.
- Timeout is 90 complete bars. Frozen gap, stop/target collision, session exit,
  cost, risk, and portfolio precedence remain unchanged.
- At most one accepted proposal per symbol-session; no re-entry.
- Missing warm-up or next-bar input is unavailable. Malformed bars,
  unclassified gaps, and provenance failures fail closed.

The canonical specification identity is
`8eb6d34a71940cedd9fb203342b2477f396e4b272fc158938a53462be0cc3fcb`.
The strategy identity is
`e0d14acd20bd47a205ca4696fd1e9b3dfe6ea6ded8609c18b85aaee3e92466de`.

## Implementation and evidence

There is no exact frozen evaluator analogue: the V002 failed-downside reclaim
uses a rolling prior low, a different observation window, up-to-three-bar
reclaim deadline, next-bar confirmation, and fixed-R target. This child
therefore uses one candidate-specific evaluator while reusing the frozen ATR,
same-clock volume, proposal builder, lifecycle, cost/risk model, integrity
validation, and exploratory publication contracts unchanged.

Identity-bound evidence:

- child hypothesis: `203cd2429c268510402e58f7ed173f588fc81611ce4201311e04eb2f56511292`;
- specification artifact: `1e25f9a5c22a124c18e18c36a294c47ace2d8ed30b599cbf28b0aa7d1ac6d4a9`;
- preregistration: `a7a244ea93cd2b592086c02b6027a9a51d3fced9e44c2214b52e7cfcb1cf4396`;
- executor implementation: `f1b5d4b559f4e2121f694f660445ba21cf50b70dca5794aeac82a0983a40bf84`;
- implementation binding: `2761c57ffd8b7e19a82834399101dc14a5d7dc9dc0b37a816e75b32aa1162ef4`;
- conformance: `fcb4c6406a51139ba9fa8972e7f70bf955a15406f62c940c0068d3e9770ab232`;
- executor registration: `98d52a013119a29c707d2e33191d5a967bf4b058638f8840983ad32a1602d87e`;
- evidence manifest: `96c7fc70007120a29068fd51ed3d762d9cb1e42e3533877632ae4815cdc9a2ba`.

Conformance covers a positive proposal, absent excursion, absent adjacent
reclaim, below-threshold and unavailable volume, ATR warm-up, malformed and
gapped bars, duplicate state, next-bar absence, no-lookahead, lifecycle
admission, 90-bar timeout, and stop-before-target collision precedence.

## Bounded diagnostic exercise

The fixed sample contains 23 symbols and 40 sessions: 20 warm-up sessions and
20 evaluation sessions. All 920 partitions use the already-present contaminated
development dataset. No download or provider call occurred.

Diagnostics:

- 920 partitions inspected: 460 warm-up and 460 evaluated;
- 136,160 causal decisions and 95,903 eligible decisions;
- 145 setup triggers;
- 43 deterministic `no_trade` decisions because the internal midpoint target
  was not above cost-adjusted entry;
- 102 proposals;
- 88 completed lifecycles and 14 portfolio rejections;
- 135,602 no-signal decisions;
- 413 unavailable decisions, all ATR20 warm-up at the first 09:49 decision;
- zero integrity failures;
- `136,160 = 135,602 + 43 + 102 + 413`; and
- `102 proposals = 88 completed lifecycles + 14 rejections`.

Dominant no-signal reasons were outside-window decisions (71,172), the
one-proposal state gate (26,007), insufficient downside excursion (15,943),
price ceiling (11,173), absent adjacent reclaim (8,136), price floor (2,664),
breakdown close not below the range (356), and below-threshold same-clock
volume (151). These are engineering-frequency observations only.

The write-once run identity is
`9c3fa5606e841084f8af64367024556e08c3a05fad88a05efd1f13c313f872c4`;
the manifest identity is
`064082998420eb1b301f97268f0f18bc08c00e9947128b45d79af1abaae4c5d0`.

## Comparative engineering view

| Mechanism | Evaluability and diagnostic behavior | Engineering burden |
| --- | --- | --- |
| First-pullback continuation | Multi-stage opening impulse, controlled retracement, and resumption; executable synthetic chain and earlier bounded exploratory diagnostics | Intraday OHLCV, ATR, local volume; highest state complexity |
| Opening-range expansion continuation | 25 evaluated partitions; 177 proposals; 10 completed, 167 rejected; no unavailable or integrity events | Five-minute range plus 20-session same-clock volume |
| Volatility-expansion breakout | 460 evaluated partitions; 194 proposals; 128 completed, 66 rejected; 6,602 ATR warm-up unavailable; zero integrity failures | ATR20, prior-15 high, adjacent continuation, same-clock volume |
| Opening-range failed-breakout reversal | 460 evaluated partitions; 145 triggers, 102 proposals; 88 completed, 14 rejected; 413 ATR warm-up unavailable; zero integrity failures | Five-minute range, ATR20, adjacent reclaim, same-clock volume, midpoint feasibility |

This comparison addresses reachability and implementation only. It neither
ranks economic quality nor supports an edge claim.

## Reproduction

Verify committed evidence without accessing market data:

```bash
PYTHONPATH=/absolute/repository/src .venv/bin/python \
  scripts/run_opening_range_failed_breakout_reversal_child_v001.py \
  --repository-root /absolute/repository --verify-only
```

An exploratory rerun requires the existing contaminated dataset and a new
write-once output beneath `exploratory_research/v001`. UTC/hash-seed 1 and
Asia/Tokyo/hash-seed 777 generated byte-identical bundles.

## North Star decision

This adds a fourth genuinely distinct exercisable mechanism and demonstrates
that the local OHLCV sample is broad enough for a multi-strategy engineering
campaign. A VWAP-deviation mean-reversion child is the next useful current-data
mechanism because it adds non-opening, non-breakout reversion while reusing
OHLCV and VWAP. Point-in-time catalyst/attention history would unlock the
largest remaining hypothesis family. Authorized uncontaminated PIT market data
remains the blocker to empirical conclusions.

**NO ADDITIONAL GENERIC INFRASTRUCTURE RECOMMENDED**
