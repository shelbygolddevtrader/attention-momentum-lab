# Attention observational and shadow context V001

This schema is research-only and additive. It cannot affect Strategy V0.1.1
eligibility, score, proposal ordering, acceptance, sizing, execution, stop,
target, or exit. Context is stored in a parallel record so adding it does not
change the signal or proposal identity.

## Point-in-time context

`aml.attention-shadow-context.v001` can record:

- qualifying names observed so far on the date and in the same hour;
- eligible-universe fraction, concurrent signals, premarket dollar volume,
  qualifying gaps, and same-direction breadth;
- causal SPY/QQQ returns, relative returns, return/gap dispersion, and verified
  point-in-time classifications;
- proposals competing at the intended entry time, the frozen engine order,
  score difference from the first proposal in that order, existing exposure,
  rejection reason, and position-limit-only rejection;
- VWAP position and slope, 15-minute opening-range position/state, session-high
  distance/time, pullback, recent higher highs/lows, volume persistence, bar
  range liquidity proxy, entry delay, and adverse movement before fill;
- post-trade MFE, MAE, times to each, fixed-interval returns, stop recovery,
  target continuation, and a reproducible holding-boundary path hash.

Counts described as “on the date” mean observed no later than the decision
timestamp. Later same-day signals are excluded. Fill and exit-path fields are
post-decision diagnostics and are never exposed to the strategy evaluator.
Exit-path calculations stop at the already-frozen maximum holding boundary.

The existing tournament engine has deterministic admission order, not a
score-based capital ranking. The recorded `frozen_order_rank` follows that
existing order. Score difference is descriptive and does not reorder proposals.

## Event provenance

`aml.attention-event-context.v001` supports earnings/guidance, corporate action,
regulatory/legal, analyst/product, sector, macro/index, social/retail,
short-squeeze, halt/resumption, and unknown labels. A non-unknown label requires
a source ID, URI, publication time, and observation time no later than the
decision. Without such a source, the label is `unknown` with an explicit
missing-source reason. Outcomes are never a labeling source.

## Deferred fields

The following remain unavailable unless a valid point-in-time source is later
approved:

- sector and industry classifications;
- event labels for historical signals;
- quote-derived spreads and depth (bar range is only a labeled proxy);
- consolidated premarket dollar volume and gaps when premarket partitions or
  reference closes are incomplete;
- cross-sectional breadth in the current single-symbol tournament unit until a
  separate, causal multi-symbol context pass supplies all contemporaneous names;
- rejected-proposal shadow paths when the complete entry-to-boundary bar path is
  unavailable.

Unavailable values remain null with a source-status or missing-reason field.
They are not inferred.

## P&L compartments

Shadow outcome rows have one of two classifications:

- `rejected_shadow`: a non-deployed outcome for a V0.1.1 proposal rejected by
  portfolio constraints;
- `strategy_shadow`: an independently defined shadow research proposal.

Both require `deployed=false`, `capital_allocation=0`, and
`included_in_portfolio_pnl=false`. They never enter deployed portfolio totals.

## Shadow specifications

The following definitions are versioned `0.1.0-spec` and intentionally remain
specification-only:

- `attention_continuation_shadow`;
- `attention_first_pullback_shadow`;
- `failed_attention_reversal_shadow`;
- `broad_event_leader_shadow`.

Each records its required observations and unresolved definitions. Thresholds
for sustained attention, consolidation, pullback control, volume contraction,
support loss, reversal confirmation, high breadth, and leader weighting have
not been chosen. Choosing them from corrected validation outcomes is prohibited.
No shadow strategy receives capital or has a profitability claim.

## Rehearsal

`scripts/run_v011_shadow_rehearsal.py` uses only a fixed synthetic fixture. It
asserts signal, proposal identity, audit, trades, and portfolio summary parity;
records explicit missing context; and demonstrates separate deployed,
rejected-shadow, and strategy-shadow totals. Outputs are deterministic and
write-once for the same rehearsal identity.
