# Professional Strategy Advancement and Statistics V001

Discovery advancement requires at least 60 completed trades, net expectancy of
at least 0.05R, maximum drawdown no greater than 10R, three active months, two
pre-outcome regimes, no more than 35% of profit from one symbol or day, no
critical integrity failure, and an unchanged strategy identity.

Untouched validation and one-time holdout each require at least 30 completed
trades, net expectancy of at least 0.05R, a cluster-aware expectancy interval
lower bound of at least zero, drawdown no greater than 8R, two active months,
two regimes, the same 35% concentration limits, zero critical integrity
failures, and the unchanged frozen identity. Holdout may be opened once only
after human approval. Passing does not itself authorize paper or live trading.

The same gates limit the canonical-to-variant expectancy range to 0.10R and
require claim compliance. A breach blocks advancement rather than being hidden
by the overall medal score.

The ten canonical benchmark hypotheses form the primary family. Holm step-down
control uses family-wise alpha 0.05 on net expectancy. Every declared variant
would count as a separate hypothesis. Secondary metrics use Benjamini–Hochberg
at q=0.10 for descriptive screening only. Rank, medal count, nominal p-values,
and secondary discoveries are not confirmation.

Inference must cluster intraday trades by trading date. Ordinary trade-level
bootstrap may be shown only as a comparison. Confidence intervals, effective
sample limitations, inactive periods, concentration, missingness, and all
undefined metrics must be reported. No date, symbol, regime, or variant may be
selected after observing outcomes.

Changing eligibility, entry, exit, risk, costs, a parameter variant, or regime
rule resets the strategy to discovery. Formatting-only and documentation-only
changes leave evidence unchanged. Unknown changes fail closed.

## Disqualification

A competitor is disqualified for an identity mismatch, partition contamination,
future-information use, missing provenance, post-outcome contract change,
unreconciled ledger, unreported missing data, capital-governance bypass, or a
scored short trade without point-in-time borrow evidence. Disqualification is
not repaired by dropping the affected trades. The run is preserved, labeled
failed, and a corrected version starts again under a new identity.
