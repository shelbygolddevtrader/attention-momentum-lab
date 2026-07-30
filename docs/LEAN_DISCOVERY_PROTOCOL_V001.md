# Lean Discovery Protocol V001

Status: prospective design only; pilot unauthorized; no empirical data opened

Protocol identity: `52b42287f6cd7ee6404a64ece074b8bca80f75967195c2c944e48d1b26f66fa5`

Readiness identity: `867338c763d77c55690809d18e322b07008ce0bf3f3da2bfaf20d9979e148e12`

This is an independent, provider-bounded preliminary protocol. It is not V002,
does not inherit V002 readiness credit, and cannot satisfy V002 evidence
requirements. V002 remains frozen, blocked, and authoritative for audit-grade
work. Lean results cannot establish catalyst completeness, historical-universe
completeness, live tradability, production readiness, or a deployable edge.

The separate design-only capital ladder is frozen in
`docs/LEAN_CAPITAL_GOVERNANCE_V001.md`. It binds this protocol identity but
creates no paper, live, spending or reserve-transfer authority.

## Scientific question

Among securities selected using point-in-time premarket price and volume
criteria, are there reproducible intraday outcome differences associated with
predefined price, volume, liquidity, volatility, and opening-behavior features?

The protocol tests association within a bounded provider dataset. It does not
test catalyst completeness, reconstruct a complete historical universe, or
simulate a trading strategy.

## Lifecycle and authorization

1. Verify this protocol identity, the frozen calendar-candidate binding, code
   commit, provider capability, entitlement and local-retention terms.
2. Acquire a retrieval-time asset snapshot and bar/action manifests only after
   separate human approval. No acquisition exists in this milestone.
3. Calculate candidate counts from selection-only information for every bound
   session. No opening or later outcome may be opened.
4. Select the first allowed horizon meeting the frozen count rule, publish the
   final chronological partition manifest, and seal validation and holdout.
5. Require a separate, protocol-bound human authorization artifact. The tracked
   readiness file deliberately lacks it and returns exit status 2.
6. If authorized later, discovery may run only in
   `artifacts/lean_discovery/v001`. Validation and holdout outcomes remain
   inaccessible.
7. Freeze at most three compact discovery archetypes before validation. No
   feature, threshold, band, or parameter may be chosen from validation or
   holdout outcomes.

Every incomplete, conflicting, unproven or malformed input fails closed. An
empty provider response is not proof of historical absence.

The current readiness implementation cannot authorize execution even if passed
a complete set of synthetic evidence hashes. It can only report that evidence is
complete and execution authorization remains unimplemented. A later milestone
must add and review a content-validating authorization contract before any pilot.

## Cohort and partition policy

The protocol binds the 252 calendar candidates in the V002 session manifest by
session-record hash only. This reuse supplies calendar candidates, not V002
readiness credit. The independent lean cohort starts with the first 60 sessions
(2024-06-03 through 2024-08-27) and considers 20-session extensions through
240, then the 252-session maximum.

At each allowed horizon, sessions are split chronologically 50/25/25. The first
horizon with at least 120 total candidates, including 60 discovery, 30
validation and 30 holdout candidates, is frozen. Each primary exposure group
must later contain at least 20 determinate records per partition or the analysis
is inconclusive. If the maximum horizon fails, execution remains blocked.

Selection counts may be computed for this stop rule. Intraday outcomes may not.
The complete candidate-session list and all conditional rules are identity-bound
before acquisition.

## Provider-bounded universe

The intended universe is one Alpaca asset snapshot taken at acquisition time,
restricted to active US common stocks on XASE, XNAS and XNYS with SIP bar
coverage, with a hard cap of 10,000 symbols. It is not a point-in-time historical
security master. It can omit delisted, renamed or acquired securities and can
include securities that were not historically eligible. Results therefore
describe only this retrieval-time provider universe.

Ambiguous security types, exchanges, identifiers, splits or discontinuities are
excluded. Missing membership evidence remains unknown. These rules reduce
obvious errors but do not remove survivorship bias.

## Candidate selection

All selection inputs stop strictly before 09:25 America/New_York:

- cutoff price from the last eligible 09:24 bar: $1 through $100 inclusive;
- absolute premarket gap from prior regular-session close: at least 4%;
- premarket dollar volume from 04:00 through 09:25 exclusive: at least $250,000;
- premarket relative volume against the previous 20 sessions: at least 2.0;
- prior 20-session median regular-session dollar volume: at least $5 million.

Baselines require at least 15 complete observations. Candidate direction is the
sign of the premarket gap. Missing references are never forward-filled. Any
unresolved split, reverse split or discontinuity conflict excludes the affected
security-session.

## Features and outcomes

The machine-readable configuration is authoritative. It freezes ten compact
features: gap-aligned opening return, opening dollar volume, VWAP distance,
first-pullback depth, volume acceleration, realized volatility, distance from
premarket high, market-relative return, missing-minute count, and a deliberately
limited provider-halt-or-gap indicator. Every feature declares an observation
window, a 09:45 or scheduled-close cutoff, and a missing-data rule.

The 09:45 reference is the first eligible price at or after 09:45; feature bars
end before 09:45. Outcomes include MFE, MAE, gap-aligned 15-minute, 60-minute and
close returns, close-to-reference return, time to threshold, and a 2% reward
before 1% risk result. If both thresholds appear in the same minute, the primary
binary result is indeterminate. The prespecified sensitivity bounds assign every
ambiguous case first to reward, then first to risk.

No feature uses news, catalysts, SEC filings or future bars. No feature is a
trade instruction, sizing rule, stop, target order, or production signal.

## Statistical plan

The primary exposure is positive versus nonpositive gap-aligned opening return.
The primary outcome is determinate reward-before-risk. Primary effect sizes are
risk difference, risk ratio and odds ratio. The primary interval is a 95%
date-cluster bootstrap percentile interval using 5,000 replicates and seed
20260730; an ordinary trade bootstrap is comparison-only because intraday events
are not independent. A 10,000-replicate date-cluster permutation procedure is
the preregistered primary significance check at two-sided alpha 0.05.

Eleven secondary hypotheses are one family with Holm family-wise correction at
0.05. Exact stratification uses gap direction, with prespecified gap, price and
premarket-dollar-volume bands. Continuous descriptive summaries may be
winsorized only at discovery 1st/99th percentiles, then frozen. Missingness,
same-bar ambiguity, halt/gap flags and split conflicts are reported by reason.

Discovery is descriptive and hypothesis-forming. Any archetype is frozen before
untouched validation. Holdout is one-time after the validation decision is
frozen. Validation or holdout outcomes cannot change the protocol.

## Claim ladder

Reports are limited to the achieved level:

1. pipeline operational;
2. dataset internally consistent;
3. descriptive discovery pattern observed;
4. pattern survives internal discovery resampling;
5. frozen pattern survives untouched provider-bounded validation;
6. frozen pattern survives one-time provider-bounded holdout;
7. live trading remains unproven;
8. production consideration still requires V002-grade or equivalent evidence
   plus paper-forward validation.

“Proven edge,” “profitable strategy,” and “production ready” are never permitted
lean-protocol claims. “Predictive” or “validated” is rejected before level 5,
and holdout language is rejected before level 6. The tracked readiness state has
maximum claim level 0 because no empirical run exists.

## Alpaca sufficiency and limitations

The existing user-reported $99/month Algo Trader Plus SIP entitlement is a
planning assumption, not verified entitlement evidence. Alpaca is conditionally
sufficient only if a preflight later proves historical SIP minute bars include
premarket and regular sessions for the bound interval, pagination is complete,
local research retention is allowed, and split/reverse-split evidence is usable.

Minute bars are sufficient for this deliberately bar-based pilot; tick trades
and quotes are not required. Alpaca is not assumed to provide a historical
point-in-time universe, authoritative no-halt evidence, complete corporate-action
revision lineage, or delisting/symbol lineage. Failure of any required preflight
blocks execution and triggers a separately approved provider review. The design
does not select or purchase an alternative.

The halt indicator cannot prove “no halt.” Explicit status is used where present;
otherwise unexplained missing-minute runs remain unknown. Split data plus a price
discontinuity screen can prevent obvious errors but cannot establish complete
point-in-time action knowledge.

## Bounded acquisition estimate

The initial pull covers 20 warm-up sessions plus 60 selection sessions. At 9,000
symbols and 715 relevant one-minute intervals per symbol-session, that is 514.8
million potential bar records. At an assumed 10,000-record page, this is 51,480
bar pages plus 520 metadata, calendar and action requests, or 52,000 estimated
calls. Sparse symbols may reduce records;
provider pagination can increase calls.

Planning storage is 93 GB transferred, 20 GB compressed raw, 13 GB columnar and
60 GB recommended free local space. Runtime is estimated at 6–16 hours, subject
to actual rate limits and pagination. Incremental provider cost is $0 only if the
current entitlement supports the requested access and retention. These are
engineering estimates, not provider quotes or verified capabilities.

## Isolation and immutability

- V002 identities are read-only invariants and receive no lean readiness credit.
- Lean artifacts use only `artifacts/lean_discovery/v001`.
- Discovery path authorization rejects validation, holdout, sealed, production,
  operator and forward-validation path components, traversal and symlinks.
- Production modules may not import the lean module.
- The design exposes no download, ingestion, order, paper-trading or pilot command.
- A future run must bind protocol, partition, provider, entitlement, source
  manifests, code commit and seed identities.
- Canonical UTF-8 JSON, sorted identities, explicit timezones and a fixed seed
  make repeated planning output deterministic.

## Current readiness blockers

The tracked state remains blocked on code identity, provider capability and
entitlement evidence, the retrieval-time asset snapshot, corporate-action and
discovery-input manifests, the selection-only count and final partition
manifests, validation/holdout seal evidence, and explicit human authorization.
No empirical, validation or holdout data was opened to create this protocol.
