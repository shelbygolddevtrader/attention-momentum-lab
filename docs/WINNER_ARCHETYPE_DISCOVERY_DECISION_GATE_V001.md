# Winner Archetype V001 Discovery Decision Gate

Status: **blocked before empirical pilot**

Branch: `research/v013-discovery-execution`

Base commit: `25f571f20c9091627553d88fdff660fcb62dc4f2`

Frozen experiment identity: `f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a`

This report is a discovery-readiness artifact. It contains no discovery outcome,
validation outcome, holdout outcome, effect estimate, archetype selection, or
performance conclusion. No empirical pilot was run.

## Decision

Do not acquire the full dataset or run an empirical pilot under V001 yet. The
frozen experiment defines a complete eligible universe but does not identity-bind
the point-in-time universe or security-master rules that determine membership.
Choosing a universe now would be a new research decision outside the frozen
experiment identity. V001 also requires inputs that are not locally complete.

The next scientifically valid action is a prospectively reviewed V002 protocol
that binds an immutable universe/security-master specification and resolves the
early-close outcome boundary. V001 must not be edited or weakened.

## Deterministic session plan

The authoritative `exchange_calendars==4.13.2` XNYS calendar produces 252
selection sessions from June 3, 2024 through June 4, 2025. The warm-up interval is
May 3–31, 2024. V001 stops at the first 20-session extension where at least 100
eligible events exist, or at 252 sessions. Because eligibility cannot be counted
until the missing selection inputs and universe are fixed, there is no single
honest “exact discovery partition” yet.

The conditional discovery boundaries are:

| Cohort sessions | Discovery sessions | Discovery boundary |
| ---: | ---: | --- |
| 60 | 30 | 2024-06-03 through 2024-07-16 |
| 80 | 40 | 2024-06-03 through 2024-07-30 |
| 100 | 50 | 2024-06-03 through 2024-08-13 |
| 120 | 60 | 2024-06-03 through 2024-08-27 |
| 140 | 70 | 2024-06-03 through 2024-09-11 |
| 160 | 80 | 2024-06-03 through 2024-09-25 |
| 180 | 90 | 2024-06-03 through 2024-10-09 |
| 200 | 100 | 2024-06-03 through 2024-10-23 |
| 220 | 110 | 2024-06-03 through 2024-11-06 |
| 240 | 120 | 2024-06-03 through 2024-11-20 |
| 252 | 126 | 2024-06-03 through 2024-11-29 |

The readiness command computes these values rather than storing a hand-built
calendar:

```bash
PYTHONPATH=src .venv/bin/python scripts/plan_winner_archetype_discovery.py
```

It exits with status 2 while blocked and writes only canonical JSON to standard
output. Its current deterministic plan identity is
`36114de9d85e8b4e138f50a18637b7a62a478f4478efacb2da6a9f4871855d41`.

## Readiness inventory

### Required selection and candidate inputs

- Point-in-time eligible universe membership and stable security identifier.
- Point-in-time previous adjusted close and corporate-action state.
- SIP minute OHLC, volume, trade count, and bar VWAP from 04:00 through the
  exclusive 09:25 America/New_York cutoff.
- Twenty complete prior sessions of premarket volume and adjusted daily true
  range; immediately prior session open and close.
- Most recent licensed bid and ask at or before each snapshot cutoff.
- Broad-market input and a predeclared, point-in-time regime mapping.
- Immutable catalysts with publication and first-seen timestamps and a versioned,
  non-fuzzy category; unknown must remain distinct from confirmed absence.
- Point-in-time verified halt history and comprehensive coverage status.
- XNYS session schedule, timezone, open, close, and early-close evidence.

Candidate thresholds are fixed at gap at least 8%, premarket dollar volume at
least $1,000,000, and premarket relative volume at least 5x. The selection cutoff
is exclusive: no information timestamped 09:25:00 or later may qualify a
candidate.

### Required feature and matching inputs

Snapshots are fixed at 08:00 exclusive, 09:00 exclusive, 09:25 exclusive, and
09:35 inclusive, all in America/New_York. Every aggregate window must end at or
before its snapshot cutoff. The feature set is:

- premarket gap, dollar volume, relative volume, trend, and distance from high;
- spread in basis points;
- 20-session ATR percentage and prior-session return;
- predeclared market-regime observation;
- catalyst presence and category;
- known halt count.

Every winner and control requires complete price, premarket gap, premarket dollar
volume, premarket relative volume, 20-session ATR percentage, and spread. Controls
are same-session, without replacement, with at most two controls per winner and
the frozen deterministic ordering and tie breaks.

### Outcomes and statistics

The two long-only intraday path definitions use the 09:30 bar open through 15:59.
The primary thresholds are +10%/-5% with five sustained minutes; the sensitivity
thresholds are +20%/-10% with ten sustained minutes. Same-bar ambiguity is
downside-first. Minutes are never forward-filled; only verified halt minutes can
be excluded. A scheduled early close cannot satisfy the frozen 15:59 window and
therefore fails incomplete under V001.

The frozen analysis requires at least 30 observations per archetype, 95%
confidence, 10,000 bootstrap iterations, session-cluster primary resampling,
standardized mean/proportion differences, and Benjamini–Hochberg correction over
`all_predeclared_archetype_feature_contrasts_v001`. Sensitivities are limited to
the predeclared outcome, matching, missing-data, chronological-block, and
point-in-time regime dimensions.

## Provenance and immutable outputs

Before execution, one provider-neutral discovery input binding must contain the
frozen experiment identity, discovery phase, provider and entitlement, SIP feed,
retrieval timestamp, normalization version, timezone, universe definition, and
SHA-256 manifests for:

- universe, security master, calendar, bars, quotes, catalysts, halts, and
  corporate actions;
- every immutable raw payload;
- every normalized record set.

Changing any bound hash changes the input-binding identity and therefore the run
provenance. Raw payloads, normalized records, feature snapshots, partition plan,
candidate/event records, outcome records, matches, balance diagnostics,
archetype assignments, statistical-family registration, summary report, and run
manifest must be write-once and hash-linked. Credentials, licensed payloads, and
machine-local paths remain untracked.

The loader rejects validation, holdout, sealed, and paper-forward path components,
symlinked inputs, non-discovery phase bindings, non-SIP bindings, future-dated
retrievals, malformed or duplicate JSON, missing hashes, and experiment identity
mismatches.

## Local data and missing inputs

The repository contains contracts, deterministic synthetic tests, calendar and
acquisition infrastructure, cohort-selection utilities, halt/catalyst registries,
outcome sequencing, matching, balance diagnostics, and hypothesis-freeze guards.
Synthetic fixtures are not empirical data.

An existing ignored 4.6 GB Alpaca SIP dataset contains 9,878,220 one-minute rows,
17,319 symbol-days, and 23 fixed liquid symbols for July 24, 2023–July 23, 2026.
It is insufficient for this study because it is not the complete point-in-time
eligible universe and does not provide all mandatory historical quotes,
catalysts, security-master/corporate-action evidence, or comprehensive halts.

No Alpaca credentials are available in the isolated checkout or process
environment. The connected account entitlement therefore has not been verified
by an authenticated request. No live provider was contacted.

## Provider capability, volume, and cost

Alpaca's current public documentation says Algo Trader Plus costs $99/month,
offers full US-equity SIP coverage, historical data since 2016, unrestricted
historical recency, and up to 10,000 market-data calls per minute. Alpaca exposes
historical SIP bars and historical SIP quotes, so it can cover those two input
families. These public terms do not prove the connected account is entitled, and
they do not by themselves provide the frozen point-in-time universe definition,
catalyst registry, comprehensive halt evidence, or the study's regime mapping.

- [Alpaca market-data plans](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api)
- [Alpaca historical stock quotes](https://docs.alpaca.markets/us/reference/stockquotesingle-1)
- [Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)

An exact acquisition count cannot be calculated until the protocol fixes the
eligible universe of `U` symbol-security identities and candidate selection fixes
the final cohort and discovery event count `D`. That inability is itself a
pre-acquisition stop condition. The lower-bound planning quantities are:

- 252 selection sessions plus 20 prior warm-up sessions for each of `U` symbols;
- up to four historical quote snapshot windows per selection symbol-session;
- discovery regular-session outcome bars for `D` eligible events and their
  matched-control pool;
- pagination-dependent raw responses for each source family;
- at least raw payload, normalized record, and metadata/hash records for every
  immutable response.

Request batching and pagination make request count different from record count.
No scientifically honest storage estimate follows without `U`, quote density,
candidate count, and source choices. If the paid entitlement is active, Alpaca's
incremental API charge is expected to be $0 beyond the existing $99 subscription;
the cost of missing licensed catalysts, halts, or security-master data is unknown.
No purchase or upgrade is authorized.

## Pilot decision gate

Pilot scope: **not run**. Eligible, complete, and incomplete event counts,
matching rates, balance diagnostics, archetypes, discovery effect sizes,
uncertainty estimates, and multiple-testing adjustments are therefore **not
available**. Running a 23-symbol partial-universe pilot would test a different
study and was deliberately rejected.

Required human decisions before a future empirical pilot:

1. Approve a prospective V002 specification that identity-binds the complete
   point-in-time universe/security-master rules and defines early-close behavior.
2. Select approved point-in-time sources for catalysts, comprehensive halts,
   corporate actions/security identity, and the predeclared market regime.
3. Supply Alpaca credentials through an approved untracked mechanism, verify the
   authenticated SIP entitlement with a discovery-date request, and record only
   non-secret entitlement evidence.
4. Recalculate exact request, file, storage, and cost totals from the approved
   universe before authorizing any acquisition.

Recommendation: **fix the protocol and data readiness; do not proceed to full
discovery**.
