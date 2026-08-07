# Contaminated Economic Proof of Concept V001

This milestone is a prospectively frozen, development-only economic readout of
all five executable exploratory mechanisms. It is not empirical evidence,
validation, holdout, statistical proof, production evidence, or capital
eligibility.

## Prospective freeze

The contract in `aml.contaminated_economic_poc_v001` was committed before any
economic outcome was read. It fixes the inclusion set, exact contaminated
dataset universe, execution and cost model, normalized-risk definition,
metrics, aggregation, output precision, and coarse interpretation classes.
Changing any substantive rule requires POC V002; V001 cannot be rerun with a
more favorable setting.

Every output must state:

- CONTAMINATED ECONOMIC POC
- DEVELOPMENT DATA
- NOT EMPIRICAL EVIDENCE
- NOT VALIDATION
- NOT HOLDOUT
- NOT STATISTICAL PROOF
- NOT PRODUCTION
- NOT CAPITAL ELIGIBLE

The inclusion set is opening-drive first-pullback, five-minute opening-range
expansion continuation, volatility-expansion breakout, opening-range failed
breakout reversal, and VWAP-deviation mean reversion. All run over the same 23
symbols and the same 20 fixed evaluation sessions, with the preceding 20 fixed
sessions used only for warm-up.

Each mechanism runs independently through the unchanged proposal simulator.
The simulator requests $250 risk per trade, uses $100,000 initial capital, caps
gross exposure at 50%, caps concurrency at three, and applies the frozen 1%
daily new-entry loss stop. Base costs are 10 basis points adverse friction per
side plus the frozen commission. Stress scenarios change friction to 15 and 20
basis points while holding trades, quantities, raw prices, and commissions
fixed.

Normalized R uses actual initial position risk: quantity times base-cost-
adjusted entry less the frozen stop. The all-mechanism result is a chronological
concatenation of normalized trades, not a portfolio, blend, weighting, or
allocation. Dollar translations at $50, $100, and $250 risk are illustrations
only.

R distributions use six closed, named buckets (`R <= -1`, `-1 < R < 0`,
`R = 0`, `0 < R < 1`, `1 <= R < 2`, and `R >= 2`). Medians average the two
central sorted values for an even count. Drawdown sequences are ordered by exit
timestamp, candidate identifier, and proposal identity. Top-trade concentration
uses the largest positive R divided by all positive R; symbol concentration uses
the largest absolute symbol R contribution divided by the sum of absolute
symbol contributions.

Interpretations are coarse research-priority labels. Fewer than 30 completed
trades is `EXPLORATORY_TOO_FEW_TRADES`. A mechanism is
`EXPLORATORY_ECONOMICALLY_UNATTRACTIVE` only when mean net R is nonpositive at
base, 1.5x, and 2x costs. `EXPLORATORY_ECONOMICALLY_INTERESTING` requires
positive base and 1.5x mean net R, nonnegative 2x mean net R, base profit factor
at least 1.10, top-trade positive-profit share no more than 25%, and largest
absolute symbol contribution no more than 50%. Everything else is
`EXPLORATORY_MIXED`.

No mechanism may be changed, removed, optimized, or reparameterized in response
to this POC. No validation, holdout, forward, paper, live, broker, Olympics, or
capital action is authorized.

## Frozen V001 result

The prospectively frozen contract identity is
`5757f9ca5662df78fcf2324e51f99d638660b751f0d14c98e982c31835d5fc0c`.
The completed run identity is
`3d6c4f94b9ac8391c101d55de607b7a2a80ab524d43bf9422d0952da0c722b9f`
and its manifest identity is
`5f328a98560010a5e98a4755b4cb6e6a497a81a7b500bb0b75465a84d8520075`.

| Mechanism | Proposals | Trades | Base win rate | Base net P&L | Base net expectancy | Base total R | Base profit factor | Base max DD (R) | 1.5x / 2x mean R | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Opening-drive first pullback | 0 | 0 | n/a | $0.00 | n/a | 0.000000 | n/a | 0.000000 | n/a / n/a | `EXPLORATORY_TOO_FEW_TRADES` |
| Five-minute opening-range continuation | 2,915 | 88 | 39.77% | $370.04 | $4.20 | -40.797549 | 1.051314 | 44.698330 | -0.582031 / -0.700933 | `EXPLORATORY_ECONOMICALLY_UNATTRACTIVE` |
| Volatility-expansion breakout | 194 | 128 | 19.53% | -$8,427.30 | -$65.84 | -245.615189 | 0.438659 | 247.209209 | -2.154339 / -2.389654 | `EXPLORATORY_ECONOMICALLY_UNATTRACTIVE` |
| Opening-range failed-breakout reversal | 102 | 88 | 22.73% | -$7,191.15 | -$81.72 | -132.095516 | 0.201347 | 132.095516 | -1.727179 / -1.952563 | `EXPLORATORY_ECONOMICALLY_UNATTRACTIVE` |
| VWAP-deviation mean reversion | 406 | 194 | 12.37% | -$18,398.47 | -$94.84 | -424.291254 | 0.183620 | 424.291254 | -2.559436 / -2.931758 | `EXPLORATORY_ECONOMICALLY_UNATTRACTIVE` |

The five-mechanism concatenation reconciles 3,617 proposals to 498 completed
trades and 3,119 rejections. At base costs it contains 104 winners and 394
losers, has -$33,646.88 actual simulator net P&L, -$67.56 net expectancy,
0.374185 profit factor, -842.799508 total normalized R, and 842.799508 maximum
drawdown R. At 1.5x and 2x costs its mean R is -1.958828 and -2.225190.

The fixed $100-per-R illustration is -$84,279.95. It is not the simulator's
actual-dollar result and is not a position-size or capital recommendation.
Exit reconciliation is 108 targets, 326 stops, and 64 timeout/session or other
exits, totaling 498. No mechanism survives the frozen 1.5x or 2x cost stress.

## Research-management interpretation

This development-data POC is informative because four mechanisms have between
88 and 194 completed trades and the aggregate has 498. It is not encouraging:
none reaches the frozen `EXPLORATORY_ECONOMICALLY_INTERESTING` class. The
opening-range continuation is the least adverse in actual base-cost dollars,
but its normalized mean R is negative and the apparent base-cost result does
not survive higher costs. Apparent results are not dominated by one symbol or
one trade: aggregate base symbol concentration is 10.68% and top-trade
concentration is 4.24%.

This does not establish absence of an edge. The data are contaminated,
development-only, potentially incomplete, and unauthorized for empirical
conclusions. It does mean that the current mechanisms do not, by themselves,
provide a strong economic reason to make a substantial authorized-data
purchase now. The next research dollar is better spent implementing one more
genuinely different, low-turnover OHLCV mechanism—prospectively, the
`first-half-hour-to-close-momentum-v001` family—before reconsidering a major
data purchase. Its clock-time, market-level, late-session mechanism diversifies
the current opening, breakout, and short-horizon reversal set and may reduce
cost sensitivity; that is a test rationale, not a predicted favorable result.

For hypotheses that current OHLCV cannot exercise, the broadest missing family
is point-in-time market-microstructure data: opening/closing/reopening auction
imbalances plus signed trades and quotes. Authorized PIT data remains mandatory
before any empirical conclusion, but the POC does not yet justify purchasing it
on expected strategy economics alone.

No additional generic infrastructure is recommended.

## Reproduction

Run once into a new write-once namespace:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_contaminated_economic_poc_v001.py \
  --repository-root . \
  --dataset-root /absolute/path/to/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001 \
  --output-root /new/path/exploratory_economic_poc/v001
```

Verify the tracked bundle without market-data access:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_contaminated_economic_poc_v001.py \
  --repository-root . \
  --output-root manifests/exploratory_economic_poc/v001 \
  --verify-only
```
