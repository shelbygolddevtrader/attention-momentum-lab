# Professional Strategy Executors V001

## Status and boundary

This milestone implements the deterministic proposal layer for all ten frozen
Professional Strategy Benchmark Olympics V002 contracts. It is synthetic-only.
It does not download or read market data, enumerate a universe, run discovery,
simulate completed trades, calculate P&L, score or rank strategies, contact a
provider, access an account, place an order, or authorize production or capital.

Olympics V002 remains the sole strategy specification. Its protocol, indicator,
input, lifecycle, cost, registry, tournament, evidence, unresolved-register and
readiness identities are unchanged. V001 remains immutable history. Executor
V001 is an implementation binding beneath V002, not a new strategy protocol and
not an empirical result.

## Architecture

The layer is split into five fail-closed components:

1. `professional_strategy_executor_models_v001.py` defines immutable canonical
   bars, normalized evidence records, evaluation inputs, audit decisions and
   proposals. A next bar is represented by timestamp and open only, so its
   future high, low, close and volume cannot enter signal logic.
2. `professional_strategy_indicators_v001.py` explicitly implements Wilder
   ATR20 and RSI14, regular and premarket HLC3 VWAP, prior-20-bar and local
   five-bar volume ratios, same-clock and premarket 20-session baselines,
   20-session historical liquidity and exact elapsed returns.
3. `professional_strategy_lifecycle_v001.py` applies the exact next-bar entry
   boundary, ten-basis-point adverse entry metadata, cent rounding, absolute
   stops, fixed or frozen-indicator targets, timeouts, commissions and the
   frozen $250 risk metadata. It creates proposals only; it does not replay an
   exit or calculate performance.
4. `professional_strategy_executors_v001.py` contains one evaluator for each of
   the ten V002 strategy identities. Each evaluator returns a proposal,
   no-signal decision, no-trade decision, unavailable decision or integrity
   failure with stable reason codes.
5. `professional_strategy_executor_registry_v001.py` binds the exact ordered
   V002 strategy registry to ten unique implementation identities and exposes a
   deterministic, immutable implementation manifest.

The validator prints only that implementation manifest and exits with status 2
because empirical readiness is intentionally blocked:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_professional_strategy_executors_v001.py
```

## Point-in-time guarantees

Inputs must be timezone-aware `America/New_York`, left-labeled, unique,
monotonic, SIP, adjusted and provenance-bound. Every supplied bar must be
complete at the decision cutoff. The source bar must end exactly at that cutoff
and the intended entry must be the exact next timestamp; delayed entry is never
substituted. SPY endpoints require exact timestamps. Exact elapsed returns also
require every intervening minute in the same uninterrupted segment.

Regular and premarket segments remain separate. Indicators reset or continue
only as V002 states. A known halt is never filled with a synthetic bar;
unclassified gaps are integrity failures. Signals are blocked during the first
five complete post-resume bars. Corporate-action coverage and lineage, complete
positive and negative halt coverage, calendar identity, official prior close,
maximum five-calendar-day staleness, historical-baseline completeness and
source identities all fail closed.
The caller supplies complete, same-session prior-entry state so the executor can
enforce each frozen entry cap and complete-bar cooldown without consulting a
portfolio, account or external store.

Comparisons use unrounded binary64 values. Stops floor to one cent and targets
ceil to one cent only at the frozen lifecycle boundary. Non-finite values,
negative volume, impossible OHLC, mixed sessions, implicit timezone conversion,
future signal state and unavailable baselines cannot qualify through Python
truthiness or a fallback value.

## Strategy coverage

The registry implements exactly:

- failed downside breakdown bullish reclaim;
- first-pullback continuation;
- five-minute and fifteen-minute opening-range breakouts as distinct contracts;
- gap-and-go momentum;
- high-of-day breakout;
- market-relative momentum with synchronized SPY and no regime filter;
- RSI exhaustion reversion;
- VWAP mean-reversion fade; and
- VWAP reclaim.

Synthetic tests cover a complete positive proposal path for every strategy,
strategy-specific negative paths, unavailable inputs, integrity failures,
threshold equality, exact windows, stale prior close, SPY alignment, sequence
and extrema tie-breaking, cooldown and entry caps, cent rounding, proposal
immutability, no-lookahead structure and cross-environment determinism. These
fixtures are deliberately invented and confer no empirical evidence or
advancement credit.

## Identities

The manifest creates deterministic identities for the executor protocol, shared
indicator implementation, shared lifecycle implementation, each strategy
executor, ordered registry, complete implementation bundle and blocked
empirical-readiness state. Shared implementation identities hash the exact
source bytes. Each strategy identity binds its frozen V002 strategy identity to
the exact executor module and function source. Consequently, executable semantic
changes necessarily change the implementation identities without changing the
frozen V002 identities.

Canonical JSON uses sorted keys and stable compact separators. The validator is
tested across multiple Python hash seeds and both UTC and America/New_York host
timezones; its bytes must remain identical.

## Remaining limitations and next gate

This layer assumes its records have already been normalized to the frozen V002
input contract. It intentionally contains no provider adapter, data loader,
universe selector, empirical orchestrator, position replay, portfolio allocator,
tournament scorer or production bridge. It does not establish data entitlement,
historical coverage, event sample sufficiency, expectancy, drawdown, execution
quality or profitability.

The next possible milestone is separately approved historical discovery and
tournament execution using licensed, manifest-bound, point-in-time inputs. That
milestone remains unauthorized here. Validation, holdout, paper, live, capital
release and production remain blocked.
