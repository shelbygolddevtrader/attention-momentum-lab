# Benchmark Implementation Campaign V001

## Purpose and outcome

Implementation Campaign V001 evaluates every Benchmark Hypothesis Library V001
entry that was still blocked after Executable Benchmark Candidate V001. It asks
whether the repository already contains every fact and capability needed to
create an unambiguous executable research chain without changing the hypothesis
or a frozen downstream component.

The answer is fail-closed:

- Library hypotheses: 40
- Previously executable and therefore excluded: 1
- Remaining hypotheses assessed: 39
- New complete executable chains: 0
- Canonically blocked: 39

This is a readiness result, not a trading result. No strategy was executed, no
empirical outcome was accessed, and no hypothesis was rejected economically.

## Why no additional strategy was implemented

Library V001 deliberately freezes economic concepts rather than numeric trading
rules. A strategy may be implemented only when all five links exist:

1. canonical executable specification;
2. authorized discovery-dataset binding;
3. implementation binding;
4. passing conformance evidence; and
5. registered executor.

None of the 39 remaining entries has even the first complete chain. Eleven are
compatible with the current minute-bar architecture but still require a
prospectively reviewed specification. The remaining 28 need data, an indicator,
or an execution model that is absent. Selecting thresholds, substituting a
price-only proxy for unavailable data, or silently translating a multi-session
or quote-level idea into the one-minute simulator would invent semantics after
hypothesis preregistration. Campaign V001 therefore blocks those entries rather
than manufacturing results.

## Capability inventory

The campaign binds exact byte hashes for the Library, first executable
candidate, static universe, Framework V001, discovery classifier, portfolio
simulator, existing professional indicators and executors, catalyst ingestion,
and halt handling.

Repository-proven capabilities include:

- committed synthetic one-minute OHLCV plus spread inputs;
- a static liquid-symbol universe;
- two verified GME halt-session schedules;
- synthetic catalyst schema fixtures, but no empirical catalyst history;
- ATR20, RSI14, VWAP, elapsed-return, and several relative-volume indicators;
- deterministic long and short next-bar proposals;
- fixed stops, targets, minute timeouts, portfolio risk, and cost scenarios; and
- write-once Framework V001 lifecycle bundles.

The inventory does not claim that an ignored local dataset, an installed API
credential, or a vendor entitlement exists. Only repository-verifiable and
identity-bound capabilities count.

## Canonical blocker taxonomy

| Capability class | Classification | Count | Meaning |
|---|---|---:|---|
| Data | `BLOCKED_MISSING_AUTHORIZED_DATA` | 24 | Required point-in-time data is absent or unlicensed in the repository |
| Governance | `BLOCKED_MISSING_EXECUTABLE_SPECIFICATION` | 11 | Current bars and execution can support a future candidate, but exact rules are not frozen |
| Execution model | `BLOCKED_MISSING_EXECUTION_MODEL` | 3 | Cross-sectional, multi-session, or sub-minute semantics are not represented |
| Indicator | `BLOCKED_MISSING_INDICATOR` | 1 | Inputs are conceptually bar-derived, but no reviewed synchronized indicator exists |

The minimal blocker is the earliest independently reviewable capability that
prevents a complete chain. Secondary lifecycle blockers remain recorded in each
artifact so that removing one blocker cannot be mistaken for execution
authorization.

## Specification-ready candidates

These eleven concepts fit the current bar/proposal architecture after a new,
prospective design milestone freezes every numeric and lifecycle rule:

- `failed-volume-breakout-reversal-v001`
- `first-half-hour-to-close-momentum-v001`
- `high-relative-volume-price-continuation-v001`
- `opening-drive-first-pullback-v001`
- `opening-range-expansion-continuation-v001`
- `opening-range-failed-breakout-reversal-v001`
- `overnight-gap-continuation-with-volume-v001`
- `overnight-gap-exhaustion-reversal-v001`
- `overnight-inventory-reversal-to-vwap-v001`
- `volatility-expansion-breakout-v001`
- `vwap-deviation-mean-reversion-v001`

Existing evaluators or indicators are identified as reusable where their
semantics overlap. They do not become evidence or an implementation binding
merely because reusable code exists.

## Missing data families

The 24 data-blocked hypotheses require one or more of these point-in-time
families:

- attention or retail-flow history;
- analyst revisions and as-was consensus;
- opening, closing, or reopening auction imbalance messages;
- earnings actuals and historical consensus;
- index inclusion and rebalance events;
- options strikes, expiration, and open interest;
- signed trades, order imbalance, quotes, midpoint, and effective spread;
- media sentiment or search attention;
- historical borrow availability;
- beta and contemporaneous news state;
- official FOMC event calendars bound to market data; or
- historical volume-at-price and signed-flow state.

Acquiring a dataset is not enough. A future milestone must establish licensing,
point-in-time semantics, completeness, immutable identity, contamination status,
and an explicit discovery authorization before specification execution.

## Missing execution and indicator capabilities

Three entries require a versioned execution-model extension:

- synchronized cross-sectional ranking;
- cross-sectional multi-session regime execution; and
- sub-minute quote-event ordering and fills.

`late-day-rebalance-continuation-v001` separately requires a synchronized,
point-in-time market-breadth and intraday-volume-profile indicator. None of
these capabilities may be hidden inside a strategy adapter because that would
bypass common conformance and execution review.

## Immutable evidence

The frozen configuration is
`config/benchmark_implementation_campaign_v001.json`.

- Capability-inventory identity:
  `bca080a54e65ec01f574063002b1e095e5a27e40cd054197bfa883685000c9a1`
- Campaign identity:
  `56e9326744b5b593a2d2a60ebd51f6c848ed4b6e2180ad6a03e0a7b023dd18c1`
- Manifest identity:
  `f1af6b11aa8092a08db62e04a80259c5e31508c0b5d51aeb99c8cf6ecef9a961`

The tracked output is under
`manifests/benchmark_implementation_campaign_v001/` and contains:

```text
manifest.json
IMPLEMENTATION_READINESS_REPORT.md
assessments/<library-entry-id>/readiness.json
```

Each readiness artifact binds the unchanged Library identity, registration,
revision, required indicators, expected holding period, minimal blocker,
secondary blockers, architecture fit, and exact next milestone. Publication is
atomic and write-once. Verification rejects missing, additional, modified, or
symlinked files.

## Commands

Publish to a new unused path:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_benchmark_implementation_campaign_v001.py \
  --config config/benchmark_implementation_campaign_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --output-root artifacts/benchmark_implementation_campaign_v001/new-run \
  --repository-root .
```

Verify the committed evidence without reassessment:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_benchmark_implementation_campaign_v001.py \
  --config config/benchmark_implementation_campaign_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --output-root manifests/benchmark_implementation_campaign_v001 \
  --repository-root . \
  --verify-only
```

## Research and production boundaries

Campaign V001 does not import or call an evaluator, simulator, broker, network
client, Olympics runner, validation loader, or holdout loader. It does not
optimize, tune, score, rank performance, or access results. Existing Library,
Framework, Campaign router, execution, integrity, publication, reconciliation,
Olympics, and governance files remain unchanged.

The shortest next evidence-producing path is a separate, design-first milestone
for one of the eleven specification-ready concepts. That milestone must select
its rules before accessing outcomes and must create a new executable chain; it
must not edit this readiness evidence.
