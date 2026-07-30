# Professional Strategy Tournament Scoring V001

Every competitor receives identical one-minute bar semantics, next-bar entry,
stop-first same-bar ordering, end-of-day liquidation, $100,000 initial capital,
$250 initial trade risk, whole-share flooring, three-position concurrency, 50%
gross-exposure limit, 1% daily new-entry stop, and the same slippage, spread,
commission, halt, missing-data, and corporate-action rules.

Two leaderboards are mandatory: equal-risk isolates trade economics before
capacity conflicts; capital-constrained applies the shared portfolio limits and
deterministic simultaneous-entry priority. Neither leaderboard overrides the
advancement gates.

## Medal events

| Event | Weight | Direction | Minimum trades |
| --- | ---: | --- | ---: |
| Net expectancy | 15 | higher | 30 |
| Downside-adjusted return | 7 | higher | 30 |
| Maximum drawdown | 10 | lower | 30 |
| Profit factor | 5 | higher | 30 |
| Payoff ratio | 4 | higher | 30 |
| Hit rate | 3 | higher | 30 |
| Tail-loss control | 7 | higher | 40 |
| Monthly stability | 6 | higher | 30 |
| Regime stability | 6 | higher | 30 |
| Validation consistency | 10 | higher | 60 |
| Holdout consistency | 12 | higher | 90 |
| Capital efficiency | 4 | higher | 30 |
| Trade sufficiency | 3 | higher | 1 |
| Execution robustness | 4 | higher | 30 |
| Sensitivity robustness | 4 | higher | 30 |

Weights total 100. The canonical JSON freezes every formula, eligibility rule,
undefined-value policy, tie policy, and winsorization rule. Event scores are
0–100 preregistered cross-sectional percentiles among eligible benchmark
competitors. Undefined or under-sampled events receive zero points rather than
an inferred favorable score. Raw-return-only ranking is prohibited.

Overall ties resolve by validation net expectancy, holdout net expectancy,
lower drawdown, then lexicographic strategy identity. Until unopened stages
exist, their events are simply ineligible; missing future-stage results cannot
be imputed. Medal tables remain descriptive.
