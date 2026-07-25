# Research Cohort v0.1 Design

**Status:** preregistration design; collection not activated
**Strategy:** `baseline_price_volume_momentum` v0.1.1
**Selection protocol:** `COHORT_SELECTION_PROTOCOL_V001.md`
**Historical feed:** consolidated SIP
**Calendar:** XNYS, left-labeled minutes
**Completeness:** halt-aware, using only canonical verified halt records

## Purpose and evidence boundary

This cohort tests whether the frozen attention-momentum strategy contains
descriptive or predictive information. It is not designed to maximize P&L.
No strategy, score, risk, execution, or data-quality parameter may be changed
after cohort outcomes are inspected.

The AAPL and GME sessions dated 2024-05-13 and 2024-05-14 are development and
pipeline-validation examples. They are never validation evidence. A local
feasibility batch may report them, but it must use a cohort ID and selection
rule containing `development_only_not_validation`.

## Frozen historical sampling frame

The initial untouched historical window begins on 2024-06-03, the first XNYS
session of the first complete calendar month after the known May 2024
development examples. Its first 60 sessions end on 2024-08-27. Collection
proceeds through consecutive XNYS sessions; dates may not be skipped because of
market behavior or strategy results.

Begin with 60 consecutive sessions. If fewer than 100 attention-event sessions
qualify, extend the window in consecutive 20-session blocks without inspecting
strategy outcomes, up to 252 sessions. Stop when the first block reaches at
least 100 events or when 252 sessions have been screened (ending 2025-06-04).
This sample-size stopping rule depends only on qualification counts, never
returns or P&L.

At least 20 prior valid sessions must also be acquired for every screened
security to calculate point-in-time premarket volume, liquidity, and ATR
baselines. The initial 20-session warm-up runs from 2024-05-03 through
2024-05-31. Warm-up sessions are inputs, not cohort observations.

## Point-in-time selection

Apply the rules in `COHORT_SELECTION_PROTOCOL_V001.md` exactly:

- Universe membership, security type, listing, corporate actions, and all
  matching variables must be known by the selection timestamp.
- The observation cutoff is 09:25:00 America/New_York, exclusive.
- An event requires a positive premarket gap of at least 8%, premarket dollar
  volume of at least $1,000,000, and premarket relative volume of at least 5.0.
- Select at most five events per date by premarket dollar volume, then symbol.
- Select up to two controls per event without replacement on the same date.
- Controls must pass the registered price, median-dollar-volume, and ATR-percent
  tolerances and are ranked by the registered deterministic distance formula.

Same-date matching controls calendar period and broad market regime by design.
Price, trailing dollar volume, and ATR percentage control size, liquidity, and
volatility. Market capitalization is retained as an audit variable only when a
reliable point-in-time shares-outstanding source is available; it is not added
retroactively as a matching rule in this protocol version.

## Required data and provenance

Production collection requires:

- SIP trades or bars covering 04:00 through 09:25 ET for selection;
- SIP one-minute bars covering the regular session for replay and simulation;
- 20 complete prior-session regular and comparable premarket histories;
- point-in-time common-stock and listing classification;
- point-in-time symbol/calendar identity;
- split and corporate-action history with adjustment provenance;
- an auditable point-in-time universe snapshot;
- acquisition manifests recording endpoint, feed, adjustment, pagination,
  timestamps, provider, fetch time, and dataset vintage.

The current one-session fetcher begins at 09:30 and therefore cannot construct
this cohort by itself. Existing local AAPL/GME files also lack the 20-session
warm-up histories and point-in-time security-master evidence.

## Registered comparisons

All executable comparisons use the unchanged simulator, capital, slippage,
entry delay, stop, target, maximum hold, cooldown, and halt-aware quality rules.

1. **Current strategy:** the frozen composite score and eligibility decision.
2. **Score-threshold-only identity check:** because v0.1 eligibility is exactly
   `score >= 70`, this must reproduce the current strategy and is not treated as
   an independent baseline.
3. **Price-momentum baseline:** signal when the existing backward-looking
   five-minute return is at least 3%, ignoring the other score components.
4. **Relative-volume baseline:** signal when existing relative volume is at
   least 3.0, ignoring the other score components.
5. **Time-matched random baseline:** for each strategy trade, select an eligible
   minute from the same symbol/session and 30-minute clock bucket using a seed
   derived from the frozen cohort ID, symbol, date, and replicate number.
   Selection cannot inspect future prices. Report the distribution across 1,000
   deterministic replicates rather than one favorable draw.

Baselines must be reported separately by session class and may not be used to
tune strategy thresholds on this cohort.

## Minimum interpretation standard

No edge conclusion is permitted before there are at least 100 selected event
sessions, up to 200 controls, and 30 distinct dates. Report both all-processed
and quality-qualified scopes, symbol/date concentration, zero-trade sessions,
trade- and session-weighted results, score/time/exit groupings, and sensitivity
to the largest trade and largest session. A later untouched holdout cohort is
required before calling any relationship durable.
