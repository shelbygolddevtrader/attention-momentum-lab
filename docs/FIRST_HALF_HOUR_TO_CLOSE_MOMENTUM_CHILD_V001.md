# First Half-Hour To Close Momentum — Prospective Child V001

This milestone adds one lower-turnover intraday market-persistence experiment.
It is exploratory and contaminated. It is not empirical evidence, validation,
holdout research, statistical proof, production readiness, or capital eligibility.

## Parent semantic audit

The immutable `first-half-hour-to-close-momentum-v001` parent identifies a
market-level clock-time persistence relationship, directional continuation,
volume/volatility state as possible inputs, a fixed protective stop, and no
overnight position. It does not freeze the instrument, direction, first-half-hour
formula, threshold, exact entry or exit clocks, stop construction, volume rule,
precision, or missing-data semantics. Its original concept enters at a fixed
late-session time and expects a holding period below one hour.

The parent is therefore not an executable specification. The revision-2 child
is not represented as an exact alias. Its remainder-of-day holding period is an
explicit descendant experiment authorized by the milestone, not an inference
from the parent.

## Prospective human-authorized design choices

All choices below were frozen before candidate outcome access:

- long-only SPY, the market proxy, regular session only;
- exact bars 09:30–09:59 ET define the signal window;
- signal return is `close(09:59) / open(09:30) - 1`;
- inclusive signal threshold is positive 0.50%;
- no volume filter and no parameter alternatives;
- one decision at 10:00 ET and exact next-bar-open entry at 10:00;
- the first-half-hour low, floored to one cent, is the protective stop;
- no economic profit target;
- one proposal maximum and no re-entry;
- unchanged session liquidation, normally the 15:55 bar close;
- unchanged 10-basis-point-per-side friction, commission, sizing, risk, and
  lifecycle rules.

The unchanged proposal schema requires a finite target. The child freezes
`1,000,000,000,000.00` as a non-operative interface sentinel. It is outside the
permitted input price domain, is never interpreted as an objective, and lets the
unchanged simulator reach either the structure stop or session liquidation.

Expected maximum turnover is one trade per SPY session. A normal-session trade
that is not stopped is held about 356 minutes, making this economically and
mechanically distinct from the existing short-horizon mechanisms.

## Dataset and contamination

The bounded engineering exercise prospectively includes every SPY regular
session in the exact bound contaminated dataset: 753 sessions from 2023-07-24
through 2026-07-23. No indicator warm-up partitions or post-result subsets are
used. The dataset is development-only and is not authorized PIT empirical data.

## Evidence chain

The closed evidence graph contains observation, revision child, triage,
specification, preregistration, implementation binding, conformance, executor
registration, and manifest. It reuses the merged exploratory publication and
structured-observation contracts unchanged.

Conformance covers a positive proposal, threshold miss, missing regular open,
missing entry bar, malformed and gapped data, duplicate suppression,
no-lookahead behavior, stop precedence, session liquidation, and determinism.

## Stopping rules

No threshold, direction, stop, exit, universe, or dataset subset may change
after the preregistration. A semantic change requires a new child identity.
No optimization, parameter search, validation/holdout access, forward testing,
paper/live trading, broker interaction, Olympics execution, or capital
allocation is authorized.

## Contaminated engineering result

The preregistered run inspected and evaluated all 753 bound SPY sessions. It
made 753 causal and eligible decisions, emitted 19 proposals, completed all 19
lifecycles, rejected none, and recorded zero unavailable events and zero
integrity failures. Reconciliation is `753 = 734 no-signal + 19 proposals` and
`19 = 19 completed + 0 rejected`.

The write-once external exploratory run identity is
`b92807d9a8d439be672f94fe1e82d16e73ccef2135d6191e00c9b1c142205b0b`;
its manifest identity is
`c5e86d2639b61da29ad498bfed051567365411be1db809499810dbf907d2e05a`.
The merged exploratory contract requires this bundle to remain outside Git.

The 19 completed lifecycles are below Contaminated Economic POC V001's frozen
minimum of 30 completed trades. The candidate-only economic extension therefore
did not run, and no candidate economic outcome was inspected. The engineering
result establishes a distinct and genuinely lower-frequency mechanism, but it
is too sparse for the authorized contaminated economic prioritization gate.

The current dataset is broad enough for unified engineering diagnostics, but a
single SPY market-persistence rule produces too few events for this POC. A next
current-data candidate should test another prospectively frozen lower-turnover
OHLCV mechanism with a wider cross-sectional universe. Authorized PIT data,
especially independently licensed and uncontaminated minute OHLCV with proven
corporate-action lineage, remains the principal blocker to empirical claims.

NO ADDITIONAL GENERIC INFRASTRUCTURE RECOMMENDED
