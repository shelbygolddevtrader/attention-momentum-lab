# Strategy Tournament v1

This framework compares fixed, named intraday strategies against the same local
Alpaca SIP partitions. It is research-only: it has no broker calls, order
submission, paper-trading activation, or real-money execution.

## Existing architecture reused

Tournament strategies produce `NormalizedSignal` values and a single adapter
converts them to the existing `StrategyProposal` contract. All fills, sizing,
slippage, stops, targets, holding limits, session-end exits, long/short math,
and risk limits therefore remain in `aml.portfolio_simulator`. Strategies never
implement execution.

Each strategy-symbol-day is persisted with `aml.portfolio_artifacts`, including
its deterministic ID, input hashes, proposal audit, trades, reconciliation,
private staging directory, atomic rename, completion marker, and hash-verifying
loader. The exchange-calendar, verified-halt, existing attention replay, and
versioned dataset-manifest components are reused rather than duplicated.

## Signal timing and lookahead protection

Alpaca minute bars are left-labeled. A bar labeled 09:30 is not complete until
09:31. Indicators may use the current completed bar and earlier bars only;
rolling volume baselines explicitly shift by one bar before calculation. A
signal based on the 09:30 bar therefore has an information-availability time of
09:31 and the earliest possible fill is the 09:31 open. Future rows never enter
an indicator or signal decision.

Full-day volume, future corporate-action information, outcome labels, and
future prices are not strategy inputs. Adjustment mode is inherited from the
frozen dataset and disclosed by its manifest; this framework does not perform
new corporate-action inference.

## Strategies and configuration

`config/strategy_tournament_baseline.yaml` is JSON-compatible YAML, matching the
repository's dependency-free configuration convention. It defines one fixed
parameter set for:

- opening-range breakout
- VWAP reclaim
- conservative VWAP mean reversion
- EMA momentum cross
- volume-spike breakout
- the existing attention-momentum baseline
- a no-trade control

Unknown keys, missing keys, invalid ranges, duplicate strategies, and invalid
EMA ordering fail closed. Parameter keys are sorted before SHA-256 identity is
calculated, so mapping order does not change a run.

To add a strategy, add a causal evaluator and strict `ParameterRule` map to
`aml.tournament_strategies.STRATEGY_SPECS`, add one fixed versioned entry to the
configuration, and add synthetic no-lookahead and known-signal tests. The
evaluator must return normalized signals; it must not call execution code.

## Fixed splits and holdout protection

- Development: 2023-07-24 through 2024-12-31
- Validation: 2025-01-01 through 2025-12-31
- Holdout: 2026-01-01 through 2026-07-23

Default commands select development and validation only. Naming `holdout`
without `--include-holdout` is rejected. `--include-holdout` records
`holdout_used=true`, but holdout metrics never enter the composite score.

## Running and resuming

```bash
PYTHONPATH=src .venv/bin/python scripts/run_strategy_tournament.py --dry-run

PYTHONPATH=src .venv/bin/python scripts/run_strategy_tournament.py \
  --config config/strategy_tournament_baseline.yaml \
  --splits development validation

PYTHONPATH=src .venv/bin/python scripts/run_strategy_tournament.py \
  --strategies opening_range_breakout vwap_reclaim \
  --symbols AAPL TSLA NVDA --splits development --resume
```

The dry run reports strategies, symbols, dates, splits, parameter hashes,
estimated symbol-days, and output location without running a backtest.
`--resume` reuses only hash-verified, provenance-compatible completed units.
Partial or corrupt units block the run. A run lock prevents concurrent writers.
Final aggregate artifacts are staged privately and atomically renamed into
`artifacts/tournaments/{run_id}/final/`; generated outputs remain ignored by
Git.

## Metrics and composite score

`leaderboard.csv` retains raw metrics for independent sorting. The validation
composite is a transparent weighted score:

- 20% profit factor
- 15% Sharpe ratio
- 10% Sortino ratio
- 15% inverse maximum drawdown
- 10% profitable-month consistency
- 10% profitable-symbol consistency
- 10% minimum-trade-count confidence
- 10% development-to-validation stability

Each component is bounded to `[0,1]`. Penalties apply for symbol/month profit
concentration, severe development-to-validation degradation, invalid ratios,
near-zero exposure, and insufficient evidence. Zero-trade strategies receive a
zero composite. Holdout results are displayed separately and never scored.

Sharpe and Sortino use calendar-day P&L aggregated across selected symbols and
annualized by `sqrt(252)`. They are descriptive and are flagged when unstable;
no statistical-significance claim is made.

## Interpretation and limitations

All competitors use the same fixed execution assumptions. Tournament v1 locks
commissions and cooldown to zero because the existing shared portfolio
simulator does not implement those settings; nonzero values are rejected rather
than silently ignored. Capital is reset for each strategy-symbol-day unit, so
aggregate returns are a research comparison rather than a compounded brokerage
account curve. Missing regular minutes above the configured threshold are
explicit exclusions; only source-verified halt minutes receive halt treatment.

Simulated fills cannot reproduce queue position, latency, market impact,
borrow availability, or every corporate-action and venue condition. A favorable
leaderboard is a hypothesis-screening result, not evidence of deployable or
real-money performance.
