# Winner Archetype Protocol V002

Status: prospective protocol; empirical execution is not authorized

Schema: `aml.winner-archetype.protocol.v002`

Canonical specification: `config/winner_archetype_protocol_v002.json`

Source requirements: `config/winner_archetype_source_requirements_v002.json`

Canonical protocol identity:
`11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580`

Source-requirements identity:
`4a0f350cd24ae2ef5509cbfc72a6994a1bb9df9d3e2dedcfe3354b2cfe4a168c`

Initial blocked-readiness identity:
`01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6`

V002 resolves the methodological ambiguity found at the V001 discovery decision
gate. It defines the population, knowledge-time rules, source roles, market-data
semantics, early-close behavior, completeness state machine, immutable identities,
and technical phase boundaries before any candidate or outcome record is opened.
It does not authorize acquisition or empirical analysis.

## Research boundary

The research question remains whether characteristics observable by a fixed
decision timestamp distinguish historical intraday momentum winners from
comparable non-winners. V002 changes the input and reconstruction contract, not
the production strategy.

This milestone performs no candidate scan, eligible-event count, matching,
labeling, archetype assignment, effect estimation, return calculation, or
performance assessment. Discovery can begin only after every required source is
capability-verified, entitlement-verified where applicable, acquired, coverage
validated, conflict-free, and bound into a discovery experiment identity.

## Cohort planning and phase freeze

V002 preserves the prospective V001 planning structure:

- selection begins June 3, 2024;
- the initial cohort contains 60 authoritative XNYS sessions;
- selection-only inputs extend the cohort by 20 sessions until at least 100
  eligible events exist;
- the maximum is 252 sessions, ending no later than June 4, 2025;
- final sessions are chronologically partitioned 50% discovery, 25% validation,
  and 25% holdout;
- the final session plan and every discovery input identity must be frozen before
  any validation or holdout input can be opened.

Outcome records cannot be used to choose the final cohort length. The readiness
CLI deliberately does not calculate eligible-event counts.

## Point-in-time eligible universe

Every selection session requires one complete point-in-time universe snapshot
strictly before 09:25 America/New_York. The snapshot must reconcile its expected
constituent count and every constituent identity to bounded authoritative source
coverage. A present-day ticker list, current survivors, or symbols selected after
a price move are prohibited.

### Included population

Only active operating-company common stock with a primary national-exchange
listing on XNYS, XNAS, or XASE is eligible. A listing must be historically:

- active at the selection timestamp;
- tradable;
- quoteable;
- covered by the consolidated SIP.

Marginability, shortability, easy-to-borrow status, and fractionability are not
eligibility requirements because the study is long-only and those account flags
are often not historically point-in-time. Current provider account flags are not
valid historical evidence.

### Explicit exclusions

ADRs and other depositary receipts, ETFs, ETNs, closed-end funds, preferred
shares, warrants, rights, units, SPAC units, OTC securities, test symbols,
SPAC components and pre-combination blank-check companies, tracking stocks,
foreign ordinary shares, limited partnerships, when-issued
securities, and every other non-common-equity type are excluded. Unknown security
type blocks the constituent rather than defaulting to common stock.

Multiple common-stock share classes are evaluated as distinct listings with
distinct listing identifiers, although they may share an issuer identifier.
Duplicate rows for one listing are conflicts, not extra securities.

### Listing events

- IPOs and direct listings become eligible at the first complete active snapshot
  at or after the effective listing time.
- Relistings require a new listing interval and listing identifier. A stable
  security identifier may be reused only when authoritative lineage proves
  continuity.
- Delistings and suspensions make a listing ineligible at their effective time,
  never before their first-known time.
- A merger predecessor remains independently eligible until its effective
  termination; a successor requires its own listing interval.
- Bankruptcy or liquidation does not retrospectively remove an actively listed
  common stock. Eligibility follows point-in-time listing evidence.
- Exchange transfers retain the security identity only when authoritative
  evidence proves continuity and supplies the new listing interval.
- Temporary or when-issued symbols remain excluded unless a later permanent
  common-stock listing independently qualifies.
- Recycled tickers must map to different security or listing identifiers.

## Stable identity and symbol lineage

A ticker is never a stable identity. V002 binds:

1. an opaque canonical security identifier;
2. a listing identifier for each exchange listing or class;
3. an issuer identifier where available;
4. symbol intervals with effective-from, effective-to, and first-known times;
5. identifier source, source version, revision, correction, and supersession.

Symbol changes alter the symbol-lineage identity while preserving the canonical
security identity when continuity is proven. Intervals cannot overlap. Conflicts
between an authoritative security master, exchange identifiers, and corroborating
mappings block the affected snapshot. A future ticker, merger, delisting, or
identifier correction cannot change an earlier discovery view.

## Calendar and session contract

The authoritative calendar implementation is `exchange_calendars==4.13.2` with
calendar `XNYS` and left-labeled minutes. Market timestamps are constructed in
`America/New_York` with IANA timezone rules and then converted deterministically
to UTC. This handles daylight-saving transitions without fixed-offset assumptions.

- Premarket: `[04:00:00, 09:25:00)` America/New_York.
- Selection cutoff: 09:25:00 exclusive.
- Regular session: `[authoritative scheduled open, authoritative scheduled close)`.
- Holidays and authoritative non-sessions are excluded.
- An unscheduled full closure is excluded when the versioned calendar marks no
  session.
- An exchange-wide delayed opening requires a corrected authoritative schedule.
  A security-specific delayed opening is market-status evidence, not a calendar
  rewrite.
- Exceptional sessions require a complete versioned record. Conflicting calendar
  evidence blocks the session; there is no synthetic fallback.

### Early closes

Early-close sessions remain eligible. This is an explicit prospective V002
change from V001's fixed 15:59 outcome boundary. The evaluation window ends at
the final left-labeled minute before the authoritative scheduled close—for
example 12:59 for a 13:00 close. Matching remains same-session. No minutes after
the scheduled close are expected or imputed.

## Historical market data

Authoritative inputs are historical CTA/UTP SIP trades and quotes. Minute bars
are deterministically derived from the bound eligible trades; provider bars may
corroborate them but cannot replace the raw tick contract.

Required raw fields include exchange timestamp, provider receipt or first-
availability timestamp, price, size, quote side, trade or quote condition,
exchange, tape, sequence/order field where available, correction/cancellation
state, source record identity, and pagination/file identity. Quote bid and ask
sizes retain their source units. Tick precision must never be coarser than
microseconds; nanoseconds are preserved when supplied.

### Deterministic normalization

- order by exchange timestamp, sequence, then immutable source record identity;
- use version-bound CTA/UTP eligible-sale and NBBO quote-condition allowlists;
- preserve source order separately;
- append corrections and cancellations; never overwrite prior payloads;
- a late report is not available to a feature before its receipt time even when
  its exchange timestamp is earlier;
- include odd-lot trades only when SIP-disseminated and condition-eligible;
- exclude non-protected odd-lot quotes from the NBBO;
- treat a locked two-sided eligible market as a valid zero spread;
- treat an unresolved crossed market at cutoff as invalid for spread and block
  the event;
- reject non-positive and non-finite prices;
- derive left-labeled OHLCV, trade count, and trade-price VWAP.

The last eligible quote at a required snapshot must be no older than 60 seconds.
A naturally sparse minute is not automatically missing. Every expected interval
must be classified as observed, proven no-trade, verified halt, market-closed,
not applicable, invalid, conflicting, corrected, or unavailable. All pages,
sequences, conditions, corrections, and expected intervals must reconcile. No
forward fill is permitted.

Raw intraday data remain unadjusted. Historical lookbacks may be adjusted only by
corporate actions both known and effective at the decision timestamp. IEX,
delayed, indicative, or vendor-derived consolidated data cannot silently replace
SIP.

## Security master and corporate actions

The point-in-time security master supplies security, listing, issuer, exchange,
type, status, symbol lineage, and source/revision evidence. Corporate-action
coverage must include splits, reverse splits, cash and stock dividends, spin-
offs, mergers, acquisitions, reorganizations, liquidations, distributions, name
and identifier changes, exchange transfers, and listing changes.

Where applicable, records preserve announcement, provider publication,
retrieval, first-known, effective, ex, record, payable, correction, and
cancellation timestamps. A record is visible only after first-known time; an
adjustment is usable only after both knowledge and effective time. A bounded
“no action” conclusion requires complete source coverage, never an empty query.
Unresolved action terms, identity, or timing block the security-session.

## Halt and market-status evidence

Coverage includes regulatory and operational halts, LULD pauses, news-pending
halts, trading suspensions, delayed openings, quote-only states, resume times,
and applicable market-wide circuit breakers.

Source precedence is:

1. listing exchange or regulator;
2. consolidated SIP status feed;
3. corroborating market-data provider.

Corrections and resume updates are append-only. Conflicts in start, resume, type,
or coverage block the event. The absence of a row is never “no halt.” Absence
requires complete authoritative coverage for the security and interval.

## Catalyst evidence

Provider-neutral raw and normalized records cover SEC filings; earnings releases,
results, and guidance; shelf, ATM, registered-direct, private-placement, and
other offerings; FDA and regulatory events; clinical trials; analyst actions;
M&A and strategic alternatives; corporate and product announcements; management
changes; material contracts; legal or enforcement events; bankruptcy; rumors;
and unknown/unclassified events.

Records preserve original publication, provider receipt, first ingestion,
retrieval, update, correction, retraction, and filing acceptance timestamps where
applicable. Raw stories remain individually immutable. Deterministic clustering
uses source identity, canonical document identity, and versioned exact-content
rules; outcome-informed fuzzy clustering is prohibited. Syndicated stories link
to the earliest proven point-in-time publication while preserving every source.

An empirical run requires both:

- complete SEC filing coverage with issuer/security mapping; and
- a complete broad-news and corporate-disclosure archive for every eligible
  security-selection window.

Specialist categories must also have declared coverage. Any uncovered required
category remains unknown and blocks a complete catalyst feature. Unknown category
or coverage is never “no catalyst.”

## Provider-neutral source roles

Protocol requirements describe capabilities, not vendors. A provider capability
declaration is distinct from:

1. account entitlement evidence;
2. an actually acquired immutable dataset;
3. validated coverage and completeness;
4. eligibility for a particular experiment.

Each declaration binds dataset, capability, historical interval, market,
security and session coverage, feed, precision, point-in-time guarantees,
correction/revision support, pagination/file identity, completeness evidence,
source role, licensing, retention, and declaration time.

Roles are authoritative, substitute, and corroborating. A substitute must meet
the identical requirement; it is never an automatic fallback. Source precedence
is protocol-bound. An unresolved authoritative conflict blocks readiness.
Provider eligibility does not prove that a particular account is entitled.

The deterministic source matrix contains the following columns for every row:
dataset, required capability, authoritative role, acceptable substitute,
corroborating source, point-in-time requirement, completeness requirement,
historical range, security coverage, session coverage, entitlement status,
provider candidate, cost status, readiness state, and blocking reason.

## Provenance and immutable identity

Every applicable record or manifest binds schema, source role/name/version,
query or file identity, retrieval and coverage timestamps, raw and normalized
SHA-256 values, parser and normalizer versions, completeness state, revision,
correction time, and supersession lineage. Canonical serialization is UTF-8 JSON
with sorted keys, compact separators, one trailing newline, and no NaN, infinity,
invalid Unicode, duplicate keys, or host-dependent ordering.

The discovery experiment identity binds:

- protocol and source-requirements identities;
- calendar and final session plan;
- every universe snapshot, security master, and symbol lineage;
- corporate actions;
- SIP trades, quotes, and derived bars;
- halts and catalysts;
- capability and entitlement declarations;
- parser and normalization identities;
- all raw and normalized manifests.

Changing any decision-relevant identity creates a different experiment identity.

## Completeness and conflict state machine

Typed states are `complete`, `incomplete`, `conflicting`, `corrected`,
`superseded`, `unavailable`, `invalid`, `not_applicable`, `coverage_unknown`, and
`entitlement_unverified`.

Only `complete`, a fully lineage-proven current `corrected` revision, and genuine
`not_applicable` can be non-blocking. Every other unresolved required state
blocks readiness. The system never silently drops securities, sessions, records,
pages, revisions, or conflicts; substitutes a feed; treats missing as false;
treats unavailable as zero; or reconstructs an earlier view with future data.

Positive evidence requires source records. Negative evidence requires a bounded
complete coverage manifest. Unknown evidence cannot claim complete coverage.

## Discovery isolation

The V002 module and CLI are protocol/readiness-only and do not import production,
operator, forward-validation, simulation, tournament execution, or empirical
runner modules. During discovery they reject paths containing validation,
holdout, sealed, paper-forward, production, operator, forward-validation,
validation-extension, or future-empirical-artifacts components. Traversal,
symlinks, absolute escapes, non-discovery manifests, and V001 schemas are rejected
before reading.

## Readiness command

```bash
PYTHONPATH=src .venv/bin/python scripts/plan_winner_archetype_discovery_v002.py

PYTHONPATH=src .venv/bin/python scripts/plan_winner_archetype_discovery_v002.py \
  --format text
```

The command reads only the tracked protocol and source matrix. It reports
capability, entitlement, acquisition, coverage, completeness, and conflict
failures separately. It emits deterministic JSON or deterministic text, writes
nothing, performs no empirical analysis, and exits 2 while blocked.

## Compatibility

V001 remains frozen at experiment identity
`f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a`.
V002 uses distinct schemas and performs no automatic migration or reinterpretation.
V001 manifests are explicitly rejected as V002 inputs. Strategy V0.1.1,
production signals, simulation, sizing, operator, dashboard, tournament, and
forward-validation behavior are unchanged.

See `docs/WINNER_ARCHETYPE_V002_COMPATIBILITY.md` for the compatibility boundary.

## Decision log and remaining human choices

Methodological choices fixed prospectively by V002:

- national-exchange operating common stock only;
- stable security/listing identity, not ticker identity;
- SIP ticks as authoritative market evidence;
- dynamically scheduled early-close outcome end;
- strict 60-second quote freshness;
- complete catalyst source families rather than missing-as-none;
- session-cluster and statistical rules remain those already preregistered unless
  a later prospective protocol explicitly versions them.

Human choices still required before acquisition:

1. select and approve provider candidates for every source-matrix row;
2. approve licensing, retention, internal research, cloud/CI processing, and
   derived-output rights;
3. approve costs and any trials or purchases;
4. approve provider-specific parser and normalization versions after sample
   acceptance;
5. approve an authoritative stable-ID mapping when sources use different IDs;
6. determine whether available specialist catalyst sources can prove all required
   category coverage without weakening the protocol;
7. review any source conflict and decide only through a new prospective protocol
   version—never from outcomes.

Until these are resolved and all manifests validate, the readiness state is
blocked and no pilot is authorized.
