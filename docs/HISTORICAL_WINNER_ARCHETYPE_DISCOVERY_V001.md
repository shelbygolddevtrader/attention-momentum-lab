# Historical Winner Archetype Discovery V0.1

Status: research-contract implementation only. This protocol contains no licensed
catalyst data, empirical study, strategy evaluation, performance result, or claim
of an edge.

## Research question and interpretation ladder

Primary question:

> Which characteristics observable by a fixed decision timestamp distinguish
> historical momentum winners from otherwise comparable non-winners?

Outcome-defined winners are used only to generate hypotheses. Matched controls
test whether a trait is discriminative rather than merely memorable. A complete
eligible-cohort replay is mandatory before any association can be described as
general to the population. Untouched holdout evaluation and paper-forward
observation are mandatory before deployment could be considered.

Reports must use exactly one of these interpretation levels:

1. **Descriptive finding** — an observed summary with no inferential claim.
2. **Hypothesis** — a frozen, testable proposal generated in discovery.
3. **Validated association** — passed the predeclared internal-validation test.
4. **Out-of-sample association** — passed a separately authorized holdout test.
5. **Simulated trading edge** — requires a separate execution simulation; this
   protocol cannot produce it.
6. **Forward-observed edge** — requires prospective paper-forward evidence; this
   protocol cannot produce it.

No p-value, cluster, archetype, return label, or historical contrast is itself a
trading edge.

## Frozen experiment specification

The machine-readable contract is
`config/winner_archetype_experiment_v001.json`. Its canonical SHA-256 identity
binds every research-defining field. An outcome definition, feature definition,
matching change, or partition change therefore creates a different experiment
identity rather than silently changing this experiment.

The selection contract uses the established cohort framework:

- historical selection begins 2024-06-03;
- the initial block is the first 60 eligible XNYS sessions, ending 2024-08-27;
- extend only in complete 20-session blocks until at least 100 eligible events
  exist or 252 sessions have been included;
- never extend beyond 2025-06-04;
- warm-up is 2024-05-03 through 2024-05-31 and cannot contribute reported
  outcomes;
- selection cutoff is 09:25 America/New_York, exclusive;
- gap is at least 8%;
- premarket dollar volume is at least USD 1,000,000;
- premarket relative volume is at least 5x; and
- SIP is required for both premarket selection and regular-session labels.

The cohort extension decision uses eligible-event count only, never returns,
winner frequency, an archetype result, or strategy performance. The final cohort
length and ordered XNYS session list are frozen before outcome analysis.

## Research sequence

1. Freeze the complete eligible universe using cutoff-safe selection inputs.
2. Freeze the final ordered session list and deterministic partition plan.
3. Reconstruct and hash decision-time feature snapshots independently of labels.
4. Calculate objective outcome records from the frozen market-data manifest.
5. Discover only interpretable descriptive contrasts in the discovery partition.
6. Match each discovery winner to same-session non-winning controls.
7. Inspect balance and missingness before interpreting feature contrasts.
8. Register and freeze hypotheses and parameter hashes.
9. Execute only preregistered tests in internal validation.
10. Perform a separately authorized complete-cohort replay.
11. Access holdout labels only through the explicit holdout phase guard.
12. If warranted, observe a frozen rule prospectively in zero-capital paper mode.

Outcome discovery, feature reconstruction, hypothesis generation, population
validation, holdout evaluation, and paper-forward observation must remain
separate artifacts with separate identities.

## Chronological partitions

Random row-level splitting is prohibited. The versioned partition specification
uses the final ordered XNYS sessions and assigns contiguous blocks:

- discovery: first 50%;
- internal validation: next 25%;
- untouched holdout: final 25%; and
- paper-forward: future sessions not present in the historical manifest.

Integer counts are calculated deterministically; any remainder stays in the
holdout. Each historical partition must contain at least ten sessions. The plan
records the complete ordered list, inclusive boundary sessions, partition
version, and canonical plan ID. Duplicate, missing, overlapping, or unordered
sessions fail validation.

Holdout labels may not influence feature selection, thresholds, archetype names,
matching design, rule refinement, or model selection. Holdout access requires a
frozen hypothesis, a completed internal-validation status, and the exact frozen
parameter hash. Access must be recorded in the experiment manifest.

## Decision-time feature snapshots

Versioned snapshot contracts are defined at:

- 08:00 America/New_York, exclusive;
- 09:00 America/New_York, exclusive;
- 09:25 America/New_York, exclusive; and
- 09:35 America/New_York, inclusive, as a separate post-open analysis.

Premarket and post-open snapshots cannot be pooled under one feature identity.
Every `FeatureSnapshot` binds session, normalized security identity, exact zoned
decision timestamp, exclusive/inclusive semantics, latest input timestamp,
feature-definition version, source-manifest hashes, completeness, explicit
missingness, and the canonical feature-value hash. Input at or after an exclusive
cutoff is rejected. No later value may be substituted for a missing earlier one.

Each `FeatureDefinition` declares name, version, family, units, observation
window, required inputs, missing behavior, whether zero differs from missing,
point-in-time safety, licensing requirement, and permitted phases.

Candidate feature families are:

- gap and price;
- premarket volume, dollar volume, relative volume, trend, and range;
- premarket VWAP relationship and distance from premarket high and low;
- spread, quote depth, and liquidity when licensed snapshots exist;
- ATR and other predeclared historical volatility measures;
- prior-session and multi-session momentum;
- predeclared point-in-time market regime and sector-relative behavior;
- catalyst presence, category, novelty, publication and first-seen timestamps,
  duplicate-story count, correction status, and source count;
- halt history known before cutoff; and
- completeness and missingness indicators.

The initial serialized feature registry contains only definitions whose inputs
and missingness semantics can already be stated precisely. Any additional family
requires a new versioned definition before extraction. This protocol implements
no NLP, sentiment score, fuzzy category, retrospective regime label, provider
extractor, or licensed-data integration.

## Objective outcome labels

Outcome labels are descriptive path properties and do not depend on Strategy
V0.1.1 entries, exits, stops, targets, or accepted trades. The primary and
sensitivity definitions explicitly bind:

- normalized security identity and session;
- definition version and complete definition hash;
- reference timestamp and price semantics;
- evaluation window and America/New_York timezone;
- upside and downside thresholds;
- declared reward-to-risk multiple;
- sustained-momentum threshold and minimum consecutive duration;
- close-reference semantics;
- halt and missing-minute treatment;
- source market-data manifest; and
- canonical result hash.

Each record reports maximum favorable excursion, maximum adverse excursion,
whether upside preceded downside, mechanically defined reward-to-risk outcome,
sustained momentum, close relationship, halt involvement, and completeness.
Exact threshold touches count. If upside and downside are both touched within one
minute bar, ordering is unknowable and the conservative result is
`ambiguous_downside_first`. Missing minutes are never forward-filled. Verified
halt minutes may be excluded only when an explicit halt interval is supplied;
they remain counted in provenance. No usable bars produces null path metrics.

These labels make no claim about fills, liquidity, slippage, tradability, or
realizable profit. Such claims require a separately preregistered execution study.

## Matched non-winner controls

Every winner remains in the match plan even when no control exists. Up to two
same-session non-winning controls are selected. Default matching is without
replacement; replacement must be explicitly enabled in a new matching contract.

Permitted pre-outcome dimensions include price, gap, premarket dollar volume,
premarket relative volume, ATR/volatility, spread/liquidity, and—only when
point-in-time and legally available—market cap, float, catalyst category, sector,
and industry. Outcome severity, MFE, MAE, future returns, target/stop status, P&L,
and any later price action are prohibited matching fields.

Distance is the weighted sum of absolute field differences divided by frozen
field scales. Missing required dimensions make a candidate ineligible rather
than silently imputing it. Ties resolve by symbol then event ID. Input order,
filesystem order, hash seed, locale, and destination path do not affect results.
Reason codes distinguish a valid match, insufficient same-session controls, and
missing matching fields. The matching-spec hash is embedded in every match and
balance diagnostic.

Balance diagnostics are mandatory before feature interpretation. They report
winner/control counts, missingness, and standardized mean differences before and
after matching. Poor balance is a limitation, not permission to revise matching
after viewing outcomes.

## Archetype discovery contract

Permitted discovery methods are predeclared rule groupings, simple univariate
contrasts, simple descriptive multivariate analysis, and deterministic clustering
of normalized decision-time features. Fuzzy storytelling is prohibited.

Every archetype records a stable ID and version, description, exact rule or
assignment method, features, discovery partition, sample/winner/control counts,
missingness, balance-diagnostic identities, and hypothesis status. Its mandatory
interpretation field is `no_performance_claim_permitted`. Every assignment binds
the event, partition, archetype, and assignment-method hash.

Archetypes below the configured minimum of 30 events are explicitly exploratory.
Names must describe observable structure, not profitability or famous examples.

## Hypothesis registry and phase guards

Hypothesis records are append-only and ordered by consecutive integer sequence.
They include stable ID/version, statement, source archetype, allowed features,
direction, proposed test, discovery-partition version, validation/holdout/rejection
status, backward-only supersession, and the parameter-freeze hash. Duplicate IDs,
sequence gaps, cycles, forward supersession, or self-supersession fail closed.

A human-authored creation timestamp is metadata only and is excluded from
identity. Freezing hashes the complete proposed parameter set. Changing a rule
requires a new hypothesis version; it cannot mutate the frozen record. Validation
and holdout result identities must be append-only and may not overwrite earlier
results.

The explicit phase guard allows discovery to read discovery only, validation to
read discovery and validation, holdout to read holdout only after freeze checks,
and paper-forward to read future paper observations only. Discovery access to
holdout-labeled outcomes fails immediately.

## Statistical safeguards

The specification freezes a 95% confidence level, 10,000 deterministic bootstrap
iterations, seed `20260729`, Benjamini-Hochberg false-discovery control, and a
minimum archetype sample of 30. Session-cluster resampling is primary because
same-day intraday events are dependent; event-level resampling is secondary and
must be labeled as such. Symbol clustering and repeated-issuer sensitivity must
also be reported when sample support permits.

Reports must include base rates, absolute and standardized effect sizes,
confidence intervals, corrected multiple-hypothesis results, and sample counts.
Sensitivity analyses are frozen across outcome definitions, control matching,
missing-data handling, chronological blocks, and predeclared market regimes.
Regime definitions may use only information available at the decision cutoff and
cannot be created from realized outcomes.

Small samples, wide intervals, poor balance, failed corrections, or instability
must be reported as inconclusive. They cannot be repaired by post-hoc threshold
selection.

## Leakage and contamination audit

Before any analysis, fail or explicitly report checks for:

- market observations at or after an exclusive cutoff;
- revised fundamentals not carrying historical-vintage provenance;
- modern symbol mappings applied to the wrong historical security;
- catalyst corrections or retractions learned after the cutoff;
- confusion between publication, first-seen, retrieval, and effective timestamps;
- delisted, renamed, merged, and split-adjusted securities;
- survivorship-biased universe construction;
- unlogged holdout access;
- feature-definition changes after outcomes were inspected;
- manually selected winners or famous-event cherry-picking;
- duplicate events or sessions across partitions;
- same issuer crossing discovery and holdout, reported as dependence rather than
  silently treated as independent;
- repeated intraday observations treated as separate independent events; and
- warm-up observations included in reported performance.

The experiment manifest binds input manifests, definitions, ordered sessions,
partition boundaries, matching contract, hypothesis registry, and holdout-access
state. A changed component produces a new identity.

## Failure handling and integrity

Strict schemas reject missing or unexpected fields, boolean-as-integer values,
NaN/infinity, invalid Unicode, malformed dates/timestamps, missing timezones,
ambiguous cutoff semantics, duplicate definitions, overlapping sessions,
post-cutoff features, prohibited outcome matching fields, and unfrozen holdout
access. Inputs are bounded. Sorting and canonical JSON make identities independent
of Python hash seed and host state.

Incomplete market windows remain incomplete. Unmatched winners remain visible.
Missing values use explicit null plus a missingness flag; zero never silently
means missing. Validation failures produce no replacement data or fallback rule.

## Research-only CLI

`scripts/research_winner_archetypes.py` supports only:

- `validate-spec`;
- `partition-plan` over deterministic synthetic sessions;
- `synthetic-outcome`;
- `synthetic-match`; and
- `validate-hypothesis`.

Example:

```bash
PYTHONPATH=src .venv/bin/python scripts/research_winner_archetypes.py \
  --spec config/winner_archetype_experiment_v001.json validate-spec
```

The CLI disables bytecode creation before importing research modules and writes
nothing. It has no provider, network, download, real-study, strategy-evaluation,
holdout-read, registry-mutation, or publication command.

## What this release does not establish

This release establishes contracts and deterministic synthetic tests only. It
does not establish that any feature is discriminative, any archetype exists in
real data, any association validates, or any trading rule has value. Licensed
catalyst ingestion, the complete historical study, holdout access, execution
simulation, strategy changes, and deployment are separate future decisions.
