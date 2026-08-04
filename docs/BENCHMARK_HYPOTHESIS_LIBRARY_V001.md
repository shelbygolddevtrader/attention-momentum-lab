# Benchmark Hypothesis Library V001

## Status and claim boundary

Benchmark Hypothesis Library V001 is an immutable, hypothesis-only research
catalog. It contains 40 prospectively frozen questions motivated by 22 academic,
professional, and official market-structure sources.

The library produces no trading result and makes no claim of edge,
profitability, robustness, validation eligibility, or deployability. Literature
and documented market behavior motivate falsifiable questions; they do not
constitute evidence that those questions will survive the repository's discovery
pipeline.

The library does not authorize:

- strategy implementation or discovery execution;
- optimization, parameter search, or machine learning;
- validation, holdout, or forward testing;
- paper or live trading;
- Olympics execution; or
- changes to execution, integrity, scoring, publication, reconciliation, or
  governance.

## Frozen identity

- Schema: `aml.benchmark-hypothesis-library.v001`
- Version: `benchmark-hypothesis-library-v001`
- Framework dependency commit:
  `d7651c2f31059039b8b0dc5d6baa716c53a57e4b`
- Source count: 22
- Hypothesis count: 40
- Library identity:
  `6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003`

The canonical file is
`config/benchmark_hypothesis_library_v001.json`. Any byte-level or semantic
change invalidates one or more source, Framework, registration, or library
identities.

## What “preregistered” means here

Each entry has status `preregistered_hypothesis_only`. This freezes the economic
question before implementation. It is deliberately earlier and narrower than a
Framework V001 executable preregistration.

A library entry is not eligible for discovery. Before execution, a future
milestone must independently complete:

1. triage and duplicate review;
2. one unambiguous executable specification;
3. point-in-time data and entitlement review;
4. Framework V001 preregistration with an uncontaminated discovery dataset;
5. implementation binding;
6. positive, negative, unavailable, integrity, determinism, and no-lookahead
   conformance; and
7. independent review.

The required next stage is machine-readable as
`triage_then_executable_specification_and_framework_preregistration`.

## Native Framework V001 integration

`aml.benchmark_hypothesis_library_v001.framework_artifacts` deterministically
materializes every entry as native Framework V001 `observation` and `hypothesis`
artifacts. The identities stored in the library must exactly equal those native
artifacts.

The integration is one-way:

```text
source registry
      ↓
hypothesis-only registration
      ↓
Framework V001 observation + hypothesis identities
      ↓
future triage and executable specification (not implemented here)
```

No Framework V001 or downstream module imports the library. This prevents the
research catalog from changing frozen behavior.

## Provenance and contamination

Each source record has a content identity covering its title, authors or
organization, year, stable locator, evidence scope, and interpretation limit.
The source registry distinguishes:

- peer-reviewed or working-paper academic research;
- professional trading literature; and
- official exchange market documentation.

Every source identity used to formulate a candidate becomes a source-data
identity in its Framework observation and remains in the Framework hypothesis's
contamination set. A motivating source can never later be presented as untouched
confirmation of the same hypothesis.

Source interpretation is deliberately bounded. For example:

- [Harris, *Trading and Exchanges*](https://doi.org/10.1093/oso/9780195144703.001.0001)
  supplies mechanisms and professional vocabulary, not proof of a strategy.
- [Lo, Mamaysky, and Wang](https://doi.org/10.3386/w7613) motivates objective
  pattern encoding, not visual discretion.
- [Gao, Han, Li, and Zhou](https://doi.org/10.1016/j.jfineco.2018.05.009)
  motivates a clock-time relationship that still requires independent testing.
- [Barber and Odean](https://doi.org/10.1093/rfs/hhm079) and
  [Da, Engelberg, and Gao](https://doi.org/10.1111/j.1540-6261.2011.01679.x)
  motivate attention questions without proving their direction or horizon.
- [NYSE auction documentation](https://www.nyse.com/trade/auctions) and the
  [NYSE imbalance specification](https://www.nyse.com/publicdocs/nyse/data/Pillar_Imbalances_Client_Specification_v2.2e.pdf)
  define observable events but make no return prediction.

## Canonical entry contract

Every registration freezes:

- economic mechanism and market assumption;
- entry and exit concepts;
- invalidation conditions;
- expected regimes;
- required indicators;
- expected trade-frequency bucket and explanation;
- expected holding period;
- anticipated failure modes;
- source interpretation and identities;
- taxonomy and multiple-testing family;
- related-candidate and distinctness records;
- native Framework observation and hypothesis identities; and
- a content-addressed registration identity.

Entry and exit fields are concepts, not executable rules. No numeric threshold,
indicator lookback, universe, sizing rule, or stop parameter may be inferred from
them. Those decisions belong in a later executable specification and must be
frozen before data evaluation.

## Catalog

### Opening, overnight, and auction discovery

| Candidate | Core question | Expected frequency | Holding concept |
|---|---|---:|---|
| `opening-auction-buy-imbalance-continuation-v001` | Does residual opening demand continue after the cross? | Medium | First hour |
| `opening-auction-imbalance-fade-v001` | Does auction displacement reverse after urgent flow completes? | Low | First hour |
| `opening-range-expansion-continuation-v001` | Does participation-confirmed range expansion persist? | Medium | Minutes to hours |
| `opening-range-failed-breakout-reversal-v001` | Does prompt re-entry trap opening breakout flow? | Low | Minutes to hours |
| `overnight-gap-continuation-with-volume-v001` | Does volume-confirmed overnight information continue? | Medium | Intraday |
| `overnight-gap-exhaustion-reversal-v001` | Do unconfirmed gaps revert toward the prior close? | Medium | Intraday |
| `opening-drive-first-pullback-v001` | Does the first controlled retracement preserve an opening drive? | Medium | Minutes to hours |
| `overnight-inventory-reversal-to-vwap-v001` | Does unconfirmed overnight inventory normalize toward VWAP? | Medium | Minutes to hours |

### Intraday momentum and relative behavior

| Candidate | Core question | Expected frequency | Holding concept |
|---|---|---:|---|
| `first-half-hour-to-close-momentum-v001` | Does early market direction predict the final interval? | High | Final hour |
| `late-day-rebalance-continuation-v001` | Does rising late institutional flow persist before the close? | Medium | Minutes |
| `cross-sectional-relative-strength-continuation-v001` | Do point-in-time relative winners and losers persist? | Medium | Hours to days |
| `market-relative-laggard-catch-up-v001` | Do liquid laggards converge to broad market impulses? | Medium | Minutes to hours |
| `high-relative-volume-price-continuation-v001` | Does abnormal participation distinguish persistent moves? | High | Minutes to session |
| `volatility-expansion-breakout-v001` | Does a break after compression mark new information? | Low | Minutes to session |
| `high-of-day-breakout-continuation-v001` | Does a confirmed new session high release queued demand? | Medium | Minutes to hours |
| `low-of-day-breakdown-continuation-v001` | Does a borrow-aware new session low release liquidation? | Medium | Minutes to hours |

### Liquidity, order flow, and reversal

| Candidate | Core question | Expected frequency | Holding concept |
|---|---|---:|---|
| `short-horizon-liquidity-shock-reversal-v001` | Does temporary liquidity withdrawal reverse after stabilization? | Medium | Minutes to session |
| `vwap-deviation-mean-reversion-v001` | Do noninformational deviations converge toward session consensus? | High | Minutes to hours |
| `order-imbalance-pressure-continuation-v001` | Does persistent signed flow continue to move price? | High | Several intervals |
| `order-imbalance-exhaustion-reversal-v001` | Does impact decay after a parent order completes? | Medium | Several intervals |
| `spread-normalization-reversal-v001` | Does price pressure reverse as quote competition returns? | Medium | Seconds to minutes |
| `price-impact-decay-reversal-v001` | Does block-flow impact decay after completion? | Low | Minutes to session |
| `failed-volume-breakout-reversal-v001` | Is high-volume failure terminal transfer rather than confirmation? | Low | Minutes to hours |
| `disposition-reference-price-breakout-v001` | Do investor reference-price clusters create supply discontinuities? | Low | Hours to days |

### Attention, sentiment, earnings, and macro events

| Candidate | Core question | Expected frequency | Holding concept |
|---|---|---:|---|
| `abnormal-volume-attention-continuation-v001` | Does newly arriving attention create short-lived persistence? | Medium | Minutes to days |
| `search-attention-spike-continuation-v001` | Does revealed search attention precede retail pressure? | Low | Days to weeks |
| `extreme-return-attention-reversal-v001` | Does crowded attention pressure later reverse? | Low | Days to weeks |
| `negative-media-pressure-reversal-v001` | Does extreme pessimistic media pressure revert? | Low | Days |
| `post-earnings-surprise-drift-v001` | Are earnings implications incorporated gradually? | Low | Days to weeks |
| `earnings-gap-overreaction-reversal-v001` | Can price response exceed point-in-time surprise information? | Very low | Days to weeks |
| `scheduled-fomc-preannouncement-drift-v001` | Does a fixed pre-FOMC window retain a market drift? | Very low | Hours to day |
| `analyst-revision-continuation-v001` | Do point-in-time forecast revisions diffuse gradually? | Low | Days to weeks |

### Halts, closing structure, index events, and derivatives

| Candidate | Core question | Expected frequency | Holding concept |
|---|---|---:|---|
| `post-halt-price-discovery-continuation-v001` | Does price discovery continue after a reopening cross? | Very low | Minutes |
| `post-halt-overshoot-reversal-v001` | Does reopening urgency overshoot after liquidity reforms? | Very low | Minutes |
| `closing-auction-imbalance-continuation-v001` | Do traders anticipate published closing demand? | Medium | Minutes to close |
| `closing-auction-imbalance-fade-v001` | Does completed closing pressure reverse next session? | Low | Overnight to session |
| `index-inclusion-demand-pressure-continuation-v001` | Does mechanical demand persist to the effective date? | Very low | Days |
| `index-rebalance-close-pressure-reversal-v001` | Does effective-close pressure decay afterward? | Very low | Sessions |
| `option-expiration-strike-pinning-reversion-v001` | Does expiration-related strike pressure release afterward? | Very low | Hours to session |
| `turnover-conditioned-momentum-reversal-switch-v001` | Does turnover state change serial-dependence direction? | Medium | Days to weeks |

## Duplicate and competing-hypothesis controls

The library preserves competing explanations rather than collapsing them. Paired
continuation and reversal records point to each other through sorted
`related_hypothesis_ids` and state why they are distinct. Examples include:

- opening imbalance continuation versus fade;
- range expansion versus failed breakout;
- gap continuation versus gap exhaustion;
- order-flow continuation versus exhaustion;
- attention continuation versus delayed reversal;
- earnings drift versus earnings-gap overreaction;
- post-halt continuation versus overshoot reversal; and
- closing imbalance continuation versus post-completion fade.

Future triage must reject exact duplicates and preserve the multiple-testing
family even when only one member is implemented.

## Immutability and change control

In-place changes are prohibited. A semantic revision requires a new child
registration identity and, once a Framework executable preregistration exists,
the Framework V001 child-hypothesis workflow. The parent remains reproducible and
all source and subsequently accessed dataset identities remain contaminated.

Removing an unsuccessful candidate is also prohibited. Rejected, abandoned,
superseded, and completed candidates must use the Framework archive lifecycle
when they reach those states.

## Validation

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_benchmark_hypothesis_library_v001.py \
  --library config/benchmark_hypothesis_library_v001.json
```

Validation fails closed on:

- stale source, observation, hypothesis, registration, or library identities;
- unknown, repeated, or nondeterministically ordered records;
- malformed, duplicate-key, noncanonical, symlinked, or oversized JSON;
- fewer than 30 or more than 50 hypotheses;
- missing required research fields or source classes;
- source-contamination mismatches;
- implementation or discovery authorization; and
- incomplete protected-action prohibitions.

## Limitations

- The library is curated; inclusion does not imply priority or plausibility.
- Source locators identify motivating material but do not bundle copyrighted
  publications or licensed datasets.
- Expected frequency and holding periods are qualitative concepts until a later
  executable specification freezes exact definitions.
- Several candidates require data not currently present, including order-book,
  signed-flow, auction, analyst, news, search, options, index-event, and halt
  records.
- No candidate may receive discovery results from merely appearing in this
  library.
- The next legitimate milestone is independent library review and triage design,
  not bulk implementation or parameter selection.
