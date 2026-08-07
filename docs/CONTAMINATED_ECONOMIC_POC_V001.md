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
