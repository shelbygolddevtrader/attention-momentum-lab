# Volatility Expansion Breakout — Prospective Child V001

## Status and claim boundary

This milestone creates and exercises one explicitly human-authorized descendant
of `volatility-expansion-breakout-v001`. It is exploratory engineering work on
contaminated development data. It is **not empirical evidence**, validation,
holdout, production evidence, trading authorization, or capital eligibility.

The child was specified and preregistered before the bounded historical
exercise. No economic outcome or alternative parameter result was inspected
while selecting its rules. The immutable parent and every frozen downstream
component remain unchanged.

## Parent ambiguity audit

The revision-1 parent directly specifies:

- a transition from compressed to expanding realized volatility;
- a completed break from a frozen compression range;
- directional-flow motivation and relative-volume input;
- invalidation inside the balance area;
- a fixed target or timeout; and
- long and short directions with an intraday-to-one-session horizon.

Its source rationale supports a volatility-state transition, a range boundary,
and delayed continuation after new information reaches price. It does **not**
select direction, universe, range construction, compression or expansion
formula, thresholds, timing, volume baseline, entry bar, stop geometry, target
multiple, timeout, duplicate policy, precedence, missing-data behavior, or
numeric semantics. It is therefore not an executable contract, and this child
is not represented as its exact semantic alias.

## Prospective human-authorized design choices

The following choices were made once for simplicity, interpretability, and
reuse before candidate outcome access:

- long only, regular XNYS sessions, and the existing liquid universe;
- the immediately preceding completed bar is the expansion bar;
- bullish true range must be at least `1.5 ×` Wilder ATR20 measured at the bar
  before expansion;
- the expansion close must be strictly above the unrounded high of the prior 15
  completed bars;
- the adjacent trigger bar must close strictly above the expansion-bar high;
- trigger volume must be at least `1.5 ×` the median same-clock volume from the
  20 most recent eligible prior sessions;
- signal at trigger-bar end and entry at the exact next bar open;
- stop at the lower of expansion-bar and trigger-bar lows, rounded down to a
  cent;
- fixed `2R` target rounded up to a cent;
- 120-complete-bar timeout, maximum one proposal per symbol-session, and no
  re-entry; and
- the unchanged shared 10-basis-point adverse-friction, risk, portfolio,
  lifecycle, collision-precedence, and session-liquidation conventions.

These are `PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES`; they were not inferred
as uniquely required by the parent and were not selected by optimization,
parameter search, or historical outcome comparison.

The canonical specification is `FROZEN_SPECIFICATION` in
`src/aml/benchmark_candidate_volatility_expansion_breakout_v001.py`. It also
freezes the exact windows, decision ordering, tie-breaking, unavailable and
integrity states, IEEE-754 arithmetic, and cent rounding needed for independent
implementations to agree.

## Capability reuse and implementation

No frozen evaluator is an exact analogue. The candidate therefore adds only a
narrow signal evaluator. It reuses unchanged:

- `validate_evaluation_input`, Wilder ATR20, same-clock-volume ratio, and
  post-halt blocking;
- the shared proposal builder, next-bar entry, cost/risk handoff, and lifecycle;
- the existing proposal simulator for lifecycle admission and exits; and
- merged Exploratory Research Mode V001 plus PR #40's exact candidate label and
  structured diagnostic observations.

The registered executor is code-bound to the child specification and its source
bytes. Synthetic conformance covers the positive path, absent expansion,
absent breakout, absent volume, insufficient ATR and volume warm-up, unavailable
next bar, malformed and gapped input, integrity failure, duplicate signal,
no-lookahead, deterministic repeatability, proposal lifecycle, stop/target
collision precedence, and timeout.

## Immutable evidence chain

Canonical evidence under
`manifests/volatility_expansion_breakout_child_v001/` contains exactly one of
each required role: observation, child hypothesis, triage, specification,
preregistration, implementation binding, conformance evidence, executor
registration, and evidence manifest. The inventory is closed and write-once.

The preregistration binds the immutable parent, child, specification,
implementation, contaminated dataset, exploratory claim ceiling, global
labels, and exact candidate-specific label:

`NOT EMPIRICAL EVIDENCE`

Any semantic revision requires another child identity.

Current identities:

- parent hypothesis: `b0fac2d106396657709dce6924b485c1b496bc290b1d38ce3b0ae870e11efc5a`;
- child hypothesis: `5ca72019d0ed95770e71edfab93c003f79f673acccd934252cdab750ac3349e5`;
- strategy: `89c483ed1542f63353a78a53fe60bcb4794cdece6b5bf3825cfde244a7033244`;
- specification contract: `949424cf82d66d05228cb87ea8ace644ed7eb901fde7d25c9ee42deef6b9e4aa`;
- specification artifact: `7c294cdfb136dd45e841b49b9de6d14a66f3bf8551c8f6d7f261749c91b90896`;
- preregistration: `cc8efa0eb54d0fbbee82cd27c09dfc1fb25ba71a7733bfc0608ad77e248ba9ac`;
- implementation: `e5a19c85c5bd960e4ba52bbbad6a8083ff374a48b0f96c4dd4ffceed38b47610`;
- implementation binding: `7b24644e8bec60e4ba0fa2e5c9708d44e2a9262c09949c94b2db6d83700ceac6`;
- conformance: `40720da7ae659fad69e462fc2a32be1671cf1bf96d18c9abcf26b3d50a565bd8`;
- executor registration: `90c1235e8d9ccd07f324b30470f70c2f54037daa9121ff82cacad5fb3aaf673c`;
- contaminated dataset binding: `bdbd47988dc1827d3b72dc01a1fa22e72e45258bb04771176ba15ed105b3f383`;
- evidence manifest: `66df0fa0aea2cb8df4b9fd5124d07084b473e8e6369699338e695686253bffb0`.

## Bounded contaminated-data exercise

The dataset binding uses the already-present contaminated Alpaca SIP development
vintage and grants no empirical authorization. The selection rule is the
earliest 40 sessions for which every one of the 23 frozen-universe symbols
passes the unchanged regular-minute partition validator. The first 20 sessions
are warm-up only; the next 20 are evaluated. This yields 920 inspected
partitions and 460 evaluation partitions—materially broader than PR #40's 25
evaluated partitions.

The early calendar sessions rejected during selection contained genuine
unclassified minute gaps in at least one symbol. They were not repaired,
imputed, or reclassified. The structural selection was frozen before any
candidate outcome access.

The write-once result, summary, run, and manifest live outside Git beneath an
`exploratory_research/v001` namespace. Each carries all frozen global labels,
the exact candidate-specific label, closed structured observations, and only
non-economic counts and reason codes.

The verified diagnostic reconciliation is:

- 920 partitions inspected: 460 warm-up and 460 evaluated;
- 136,160 causal decisions and 89,119 eligible decisions;
- 194 triggers/proposals;
- 128 completed lifecycles and 66 portfolio rejections;
- 129,364 no-signal decisions;
- 6,602 unavailable decisions, all ATR20 warm-up incomplete;
- zero integrity failures; and
- `194 proposals = 128 completed lifecycles + 66 rejections`.

The dominant no-signal reason was expansion ratio below the prospectively fixed
threshold (81,721), followed by the one-proposal-per-session state gate
(26,602), price ceiling (11,173), non-bullish expansion bar (3,965), price floor
(2,664), expansion close below the recent high (2,441), absent adjacent
continuation (680), and below-threshold same-clock volume (118). These are
engineering-frequency observations only.

The exploratory run identity is
`79928e0b20af1f2d83e8e0b98db180917d7c6d4e5545ff1ff687b1872f68e520`;
its manifest identity is
`c345db6d2c4d1ae222964fd55c4e3668058ec4669b616742b50667f86ae46b5d`.

## Comparative engineering view

The three exercised mechanisms are distinct:

| Candidate | Mechanism | Data burden | Engineering behavior |
| --- | --- | --- | --- |
| Opening-drive first pullback | Opening impulse, controlled retracement, resumption | Intraday OHLCV, ATR, local volume | Complex multi-stage state; synthetic executable chain and earlier exploratory diagnostics |
| Opening-range expansion continuation | First five-minute range breakout with same-clock volume | OHLCV plus 20-session same-clock warm-up | Opening-window-specific; 25 evaluated partitions, 177 proposals, 10 completed lifecycles, 167 rejections, zero unavailable/integrity events |
| Volatility-expansion breakout child | Intraday abnormal true range, recent-high escape, adjacent continuation | OHLCV, ATR20, 15-bar range, 20-session same-clock warm-up | Non-opening-specific, single adjacent-bar setup over a broader 460-partition sample |

This table compares implementation and evaluability only. It does not compare
profitability or rank candidates as trading strategies.

## Reproduction

Use the repository source path explicitly:

```bash
PYTHONPATH=/absolute/repository/src .venv/bin/python \
  scripts/run_volatility_expansion_breakout_child_v001.py \
  --repository-root /absolute/repository --verify-only
```

An exploratory rerun additionally requires the already-present contaminated
dataset and a new write-once output path outside Git containing the exact path
segments `exploratory_research/v001`. It must never target an existing output.

## Remaining limits and next step

The local dataset is adequate for broad engineering exercise but remains
contaminated and lacks the licensing, provider-echoed feed, point-in-time
corporate-action lineage, and uncontaminated discovery-period evidence required
for empirical authorization. Authorized PIT data therefore remains the primary
blocker to an empirical discovery result.

The next current-data mechanism should be another simple OHLCV/ATR hypothesis
with a prospectively authorized child, preferably a reversal mechanism to add
mechanism diversity. Point-in-time catalyst data would unlock the largest
distinct group of currently blocked event-driven hypotheses.

**NO ADDITIONAL GENERIC INFRASTRUCTURE RECOMMENDED**
