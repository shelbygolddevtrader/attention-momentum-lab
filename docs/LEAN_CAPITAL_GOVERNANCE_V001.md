# Lean Capital Release and Self-Funding Governance V001

Status: design only; paper, live execution, reserve transfers and provider
purchases are unauthorized

Governance identity: `6defde5b21b8aac1a4a1b15c501621163dcb9c400f629abd29b257f7a51073cf`

Bound lean-protocol identity:
`52b42287f6cd7ee6404a64ece074b8bca80f75967195c2c944e48d1b26f66fa5`

The long-term objective is to permit verified, settled trading profits to fund
better data, storage and platform development. This document creates no trading
or spending authority. It is governance engineering, not financial, tax, legal
or business advice.

## Non-negotiable capital boundary

No live stage can begin until discovery, untouched validation, the one-time
holdout and prospective paper-forward validation have all passed under one
unchanged strategy identity. Household, emergency, tax, payroll, borrowed and
business-operating funds are never eligible risk capital.

The tiny-live test must use a separately declared disposable-risk amount. Margin,
averaging down, martingale sizing and loss-driven capital replenishment are
prohibited. Its risk per trade is the lower of 0.25% of account equity or the
frozen strategy's validated limit. Daily loss stops at 0.5%; weekly loss stops at
1.5%. Reaching a limit revokes authorization—it is not an alert to override.

Any data-integrity, execution-integrity, identity or strategy-drift failure stops
activity. This implementation can revoke a modeled authorization but cannot
create one and exposes no broker interface.

## Frozen capital ladder

| Stage | Minimum evidence period and sample | Expectancy and drawdown gate | Capital/risk boundary |
|---|---|---|---|
| Discovery research | 30 discovery sessions; 60 signals; no trades | Descriptive only; 99.5% data completeness; zero integrity failures | No capital; research formation only |
| Untouched validation | Entire partition; 30 signals and 30 frozen counterfactual trades | At least 0.10R net/trade with interval lower bound at least 0; drawdown no more than 10% and 10R | No capital; no strategy changes |
| One-time holdout | Entire partition; 30 signals and 30 trades | At least 0.10R; interval lower bound at least 0; drawdown no more than 8% and 8R | One unseal only; no changes |
| Prospective paper-forward | At least 180 days and 100 completed paper trades | At least 0.10R; lower bound at least 0; drawdown no more than 6% and 8R; at least 95% signal capture | Simulated risk only; paper fills are not live evidence or revenue |
| Tiny live-capital test | At least 180 days and 100 completed live trades | At least 0.05R after all costs; lower bound at least 0; drawdown no more than 5% and 8R; 95% capture, median shortfall no more than 15 bps | Disposable risk only; risk/trade no more than lower of 0.25% or validated limit; daily 0.5%, weekly 1.5% |
| Limited self-funding | At least 180 additional days and 200 additional completed live trades | At least 0.08R; lower bound at least 0; drawdown no more than 5% and 8R; 97% capture, median shortfall no more than 12 bps | Risk no more than 0.3125%; daily 0.625%, weekly 1.875%; reserve mechanics may be reviewed |
| Controlled scaling | At least 12 months and 500 cumulative live trades; later gates require 90 days and 100 new trades | At least 0.10R; lower bound at least 0; drawdown no more than 6% and 10R; 98% capture, median shortfall no more than 10 bps | Each human-approved capital or risk increase is at most 25%; absolute risk/trade cap 0.5% and never above validated limit |

The machine-readable specification contains the complete entry evidence,
execution thresholds, data thresholds, shutdown rules, human-approval evidence
and regression conditions for every stage. Threshold failure results in
de-scaling, regression or suspension; it never justifies changing the threshold.

## Strategy changes and regression

Changes to strategy logic, signals, thresholds, stops, targets, holding periods,
sizing, risk or market-data semantics return evidence to discovery. A material
execution adapter or broker-routing change returns to paper-forward validation.
Documentation-only changes do not reset evidence. Unknown changes fail closed.

No validation, holdout, paper or live outcome may be used to revise the strategy
and retain the old evidence stage.

## Realized-profit reserve

Reserve eligibility begins only after the tiny-live stage passes and limited
self-funding is approved. Eligible profit is settled, net realized trading profit
above the prior account high-water mark. It must reconcile to completed-trade
hashes and account and reconciliation manifests.

Deposits, borrowed funds, unrealized gains, paper gains, backtest gains, forecast
profits and the recovery of prior losses are ineligible. No provider purchase may
be justified by forecast profit or exceed settled cleared reserve cash.

The provisional allocation defaults are:

- 50% retained in trading capital;
- 30% transferred to a separate data/platform reserve;
- 20% reserved for taxes and operational uncertainty.

These percentages are governance defaults for human review, not tax or financial
conclusions. Transfers occur no more than monthly after reconciliation. Every
transfer must bind completed trades, account statement, prior high-water mark,
reconciliation manifest and transfer receipt. The current code calculates an
auditable proposed allocation but always returns `transfer_authorized: false`.

## Claim ladder

1. **Research signal** — discovery pattern only.
2. **Validated historical signal** — frozen signal survives untouched validation
   and one-time holdout.
3. **Paper-forward performance** — prospective paper evidence; paper gains are
   not revenue.
4. **Live execution evidence** — reconciled tiny-live fills; not proof of a
   scalable business.
5. **Realized trading profits** — settled net live profit above the prior
   high-water mark, bound to completed trades.
6. **Self-funding capability** — limited self-funding gate plus auditable reserve
   transfers.
7. **Scalable business revenue** — controlled scaling plus separate accounting,
   legal, tax, operational and business evidence.

Backtest gains, paper gains, deposits, recovered losses and unrealized gains can
never be described as revenue. Passing a trading stage does not itself establish
business revenue.

## Limitations

Thresholds are conservative governance defaults, not estimates of likely
performance. Historical fills cannot prove execution quality, paper fills cannot
prove live fills, and a small live sample cannot prove stable capacity. Tax,
entity, licensing, broker, employment and household-finance questions require
separate qualified review. The ladder does not guarantee profitability, prevent
all loss, or authorize using money needed for any other purpose.

No paper or live trading, credentials, orders, reserve transfer, data purchase or
provider contact occurred in this milestone.
