# Professional Strategy Olympics Scoring Clarification V003

V003 prospectively closes the mathematical ambiguity identified before the
first Professional Strategy Benchmark Olympics. It does not change any V001 or
V002 formula, weight, direction, eligibility rule, undefined-value policy, tie
field, strategy contract, executor, advancement gate, or governance rule. It
does not authorize or perform orchestration, replay, scoring, ranking, medal
assignment, validation, holdout evaluation, or capital activity.

The canonical machine-readable contract is
`config/professional_strategy_olympics_scoring_v003.json`. This document is an
explanation of that contract; the JSON identities are authoritative.

## Favorability rank and percentile

For each event, start in canonical registry order and apply a stable sort from
least favorable to most favorable. The primary comparison uses the event's
frozen direction. Raw-value ties use the event's existing tie fields, in their
existing declared order. The final unique key is the canonical immutable
strategy identity compared lexicographically as raw UTF-8 bytes.
V003 mirrors all fifteen existing event tie fields and their directions into a
machine-readable map; that map adds no field and leaves each V001 declaration
unchanged.

The final one-based position is an **ordinal favorability rank**. Every eligible
competitor has a different position. Average, competition, dense, fractional,
minimum, maximum, and shared tied ranks are prohibited.

For eligible-cohort size `n > 1` and ordinal rank `rank`:

```text
percentile = (rank - 1) / (n - 1)
event_score = 100 * percentile
```

The least favorable competitor receives percentile `0`; the most favorable
receives `1`. Calculations use exact reduced rational arithmetic. Canonical
future records must store integer numerator and positive integer denominator.
A twelve-place, round-half-even decimal may be displayed, but it must never be
used for ordering or aggregation.

For lower-is-better events, reverse the primary raw-value ordering while still
sorting least favorable to most favorable. Preserve the original metric: do not
negate, invert, normalize, or replace it.

## Cohort edges and ineligibility

One eligible competitor receives percentile `1/2` and event score `50/1`. This
is neutral and is not evidence of comparative superiority.

With no eligible competitors, nobody is ranked, no denominator exists, and no
comparative event score is produced. Existing V001 no-eligible and zero-score
behavior remains unchanged.

A missing, NaN, infinite, or otherwise non-finite required ranking value makes
that competitor event-ineligible. It is excluded from the denominator and is
never coerced or ranked. The existing ineligible score is `0/1`, assigned only
after ineligibility. V003 preserves deterministic reason codes for missing,
non-finite, duplicate-identity, and invalid-identity failures.

## Discovery-only overall ties

Traverse the existing overall tie sequence:

1. validation net expectancy;
2. holdout net expectancy;
3. lower maximum drawdown;
4. lexicographic immutable strategy identity.

A future-stage field participates only after that stage is formally opened,
the value legitimately exists for every compared competitor, and its source
artifact is valid. Otherwise skip the field. Never substitute zero, null
ordering, a sentinel, or a synthetic value.

Consequently, during discovery an unresolved overall tie uses:

1. lower discovery maximum drawdown;
2. bytewise ascending immutable strategy identity.

This is a reduction of the existing sequence, not a new performance tie-break.

## Determinism

Ordering uses stable ascending sorts, canonical registry order before event
sorting, explicit field order, UTC-normalized timestamps, and bytewise UTF-8
identity comparison. It cannot depend on locale, case folding, hash or mapping
order, filesystem or database order, task scheduling, operating system,
architecture, local timezone, or incidental input order.

## Synthetic examples

The labels below are placeholders, not registered strategies or observations.

### Three higher-is-better values

| Label | Raw scalar | Ordinal rank | Percentile | Event score |
| --- | ---: | ---: | ---: | ---: |
| A | 2 | 1 | 0/1 | 0/1 |
| B | 5 | 2 | 1/2 | 50/1 |
| C | 9 | 3 | 1/1 | 100/1 |

### Three lower-is-better values

The raw values remain unchanged. Reversing only the comparison produces:

| Label | Raw scalar | Ordinal rank | Percentile | Event score |
| --- | ---: | ---: | ---: | ---: |
| C | 9 | 1 | 0/1 | 0/1 |
| B | 5 | 2 | 1/2 | 50/1 |
| A | 2 | 3 | 1/1 | 100/1 |

### Existing tie fields

Suppose X and Y have the same primary scalar and their already-frozen first tie
field is lower-is-better. X has tie scalar `4`; Y has `2`. X is less favorable,
so X precedes Y and receives the lower ordinal position. If the first tie field
also ties, apply the next already-frozen tie field.

If every performance field ties, canonical identities `11…11` and `22…22` are
compared as UTF-8 bytes. `11…11` precedes `22…22`, producing unique ordinal
positions. Identity resolves ordering only; it is not a performance claim.

### Singleton and ineligibility

A singleton eligible cohort receives percentile `1/2` and score `50/1`. If a
second input has a missing required scalar, exclude it before calculating `n`;
the eligible singleton remains at `1/2`, while the ineligible input receives the
prior contract's zero score and a missing-value reason code.

### Discovery-only overall tie

With unopened validation and holdout stages, two otherwise tied synthetic
competitors with discovery drawdown scalars `2` and `4` are ordered with `2`
first. If both are `2`, bytewise immutable identity resolves the tie. No missing
future-stage field is read or zero-filled.

### Incidental input order

Supplying the higher-is-better rows as `A,B,C`, `C,B,A`, or any other
permutation produces the same `A,B,C` ordinal ordering and exact rational
values because input order is not a key.

## Validation

Run the design-only validator from the repository root:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_professional_strategy_olympics_scoring_v003.py
```

It validates the V003 identities, every bound V001 and V002 identity, executor
identities, capital governance, and the immutable baseline tag. It prints only
the canonical design contract. It performs no empirical or official tournament
work.
