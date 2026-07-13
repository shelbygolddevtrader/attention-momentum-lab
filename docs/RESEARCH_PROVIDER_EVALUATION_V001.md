# Research Cohort V001: Data-Provider and Licensing Evaluation

**Status:** procurement recommendation; implementation not authorized
**Evaluated:** 2026-07-13
**Controlling specifications:** `RESEARCH_COHORT_V001_DESIGN.md` and
`RESEARCH_DATA_SCHEMAS_V001.md`
**Evidence convention:** **Verified** means an official provider page or contract
supports the statement. **Assumption** means a planning estimate. **Unresolved**
requires a written answer, sample data, or executed order form. This document is
not legal advice.

## Executive recommendation

Research Cohort V001 requires a multi-provider stack. No evaluated provider is
verified to supply both (a) consolidated SIP minute bars with extended-hours
coverage and (b) the complete point-in-time reference evidence required by the
repository, including dated common-stock classification, symbol continuity, and
proof of corporate-action coverage when no action occurred.

Recommended stack:

1. **Primary historical market data: Massive Stocks flat files**, subject to a
   written license covering internal research, retained raw data, and derived
   metrics. Its official stock flat-file documentation identifies a consolidated
   SIP minute-aggregate dataset, daily bulk files, 04:00–20:00 ET coverage, and
   at least five years of history on the Starter tier. Daily bulk files are a
   materially better fit for a 4,000-symbol universe than per-symbol REST calls.
   [Official stock flat-file overview](https://massive.com/docs/flat-files/stocks/overview)
2. **Reference data: Exchange Data International (EDI) PIT_SRF + PIT_EVT plus
   North American corporate actions**, subject to schema validation and a
   written license. EDI documents listing-level point-in-time records with start
   and end dates since January 2005, plus event context from its corporate-action
   service. It also advertises internal and redistribution licensing, but the
   exact permitted use must be in the order form.
   [EDI point-in-time reference data](https://www.exchange-data.com/product/securities-reference-data/)
   and [EDI developer description](https://developer.exchange-data.com/product/securities-reference-data)
3. **Compatibility fallback for market data: Alpaca SIP historical bars.** The
   repository already supports this path. Alpaca documents historical equities
   data since 2016, CTA/UTP consolidated coverage, a 200-request/minute free tier,
   and a $99/month 10,000-request/minute plan. Its public product pages do not
   settle retention or subscriber-facing derived-display rights, so collection
   should not begin until those rights are confirmed in writing.
   [Alpaca Market Data API plans](https://docs.alpaca.markets/us/docs/about-market-data-api)

The smallest lawful technical pilot is one full point-in-time universe on one
registered cohort date plus its 20 registered warm-up sessions—not a hand-picked
symbol sample. It must be conducted under provider trial or order-form language
that expressly permits internal research and retention. It can validate the
pipeline, but it cannot be used to evaluate strategy performance.

## 1. Repository-derived data contract

The provider stack must support the following without weakening the registered
cohort rules.

### Market observations

- Consolidated SIP one-minute OHLCV bars, not IEX-only observations.
- Premarket bars in **[04:00:00, 09:25:00) America/New_York**. The 09:25 minute
  and every later observation are forbidden selection inputs.
- Regular bars on the authoritative XNYS left-labeled index, normally
  **[09:30:00, 16:00:00)**. A 16:00 bar is not a regular-session minute.
- Twenty distinct, verified warm-up sessions per screened security.
- No filled or interpolated missing bars; zero observed premarket trades must be
  distinguishable from failed or unavailable acquisition.
- Raw provider pages, processed segment files, acquisition timestamps, requested
  and evidenced feed, adjustment, pagination, retry state, hashes, and an
  immutable dataset vintage.

### Point-in-time reference observations

- A daily U.S. common-stock universe known before 09:25 ET, including security
  type, exchange, calendar, active status, source, and vintage.
- Listing and delisting intervals with `known_at_timestamp`.
- Corporate actions with effective time, action type, positive adjustment
  factor, knowledge time, and coverage provenance.
- An explicit coverage assertion when no corporate action occurred. An empty
  response is not evidence of `verified_none`.
- Symbol/ticker continuity with non-overlapping effective intervals and stable
  identifiers so renamed securities do not disappear or merge incorrectly.
- Historical security-type classification, not today's type projected backward.
- Provider release/snapshot/vintage identifiers sufficient to reproduce the
  universe as it was delivered.

## 2. Must-have acceptance checklist

Do not approve a provider or start production collection until every applicable
item is checked and evidenced in a sample file, contract, or both.

### Technical and historical coverage

- [ ] SIP/CTA/UTP provenance is explicit; IEX-only data cannot masquerade as SIP.
- [ ] One-minute OHLCV includes [04:00, 09:25) ET and the full XNYS regular session.
- [ ] The provider explains trade eligibility and why a minute bar may be absent.
- [ ] June 2024 through June 2025 is within licensed historical depth.
- [ ] Timestamps, timezone, interval labeling, corrections, and adjustment rules
      are documented.
- [ ] Pagination or bulk-download completion can be proven and audited.
- [ ] Rate limits support the planned volume without an undocumented waiver.
- [ ] Raw files may be retained, backed up, hashed, and versioned.
- [ ] Corrections/revisions expose a release timestamp or immutable vintage.
- [ ] A point-in-time common-stock universe exists for every selection date.
- [ ] Listing, delisting, historical security type, corporate action, and symbol
      continuity fields satisfy the repository schemas.
- [ ] The provider can prove negative corporate-action coverage, or a contractual
      process exists to construct an auditable `verified_none` record.
- [ ] Stable identifiers (preferably FIGI plus provider security ID) join market
      and reference records through ticker changes.

### Rights and governance

- [ ] Internal quantitative research and backtesting are permitted.
- [ ] Raw and normalized data may be stored for the required retention period,
      including after subscription termination if needed.
- [ ] Disaster-recovery copies and governed cloud/subprocessor storage are allowed.
- [ ] Features, scores, ranks, models, and non-reconstructable aggregate results
      are contractually defined as permitted derived data.
- [ ] The contract addresses derived intelligence displayed to paying subscribers.
- [ ] Raw quote/bar display, delayed display, non-display use, and derived display
      are distinguished explicitly.
- [ ] API, CSV export, report, alert, dashboard, and model-output rights are listed.
- [ ] Redistribution, reconstruction, reverse engineering, and competing-product
      restrictions are understood.
- [ ] Any CTA, UTP, exchange, professional-user, or per-subscriber fees are listed.
- [ ] Audit, attribution, deletion-on-termination, correction, and breach duties
      are documented.
- [ ] The license permits the intended legal entity, personnel, contractors, and
      production environment—not merely one non-professional individual.

## 3. Capability comparison

Legend: **Yes** = verified official capability; **Partial** = some needed data is
documented but the repository contract is not fully proven; **No** = documented
mismatch; **Quote** = commercial rights/cost require a provider order form.

| Requirement | Alpaca | Massive | EDI | Intrinio | Nasdaq Data Link / Sharadar | Norgate |
|---|---|---|---|---|---|---|
| Historical consolidated SIP minute bars | Yes | Yes | No evidence | No evidence for required SIP aggregate | No evidence in evaluated reference products | No; end-of-day |
| 04:00–09:25 premarket | Yes, extended hours | Yes, files cover 04:00–20:00 | N/A | Unverified | Unverified | No intraday |
| Regular-session minute bars | Yes | Yes | N/A | Unverified | Unverified | No intraday |
| June 2024–June 2025 depth | Yes; since 2016 | Yes; Starter has 5 years | Reference only; PIT since 2005 | Partial; feed-dependent | Product-dependent | Yes for daily reference/price history |
| Point-in-time common-stock universe | No verified product | Partial; date-filtered ticker endpoint | Yes in principle; sample/schema check needed | Partial; historical as-of semantics unverified | Partial; Sharadar tables require sample validation | Partial; survivorship-bias-free daily database |
| Listing/delisting history | Partial corporate actions/assets only | Partial; active/delisted fields | Yes | Yes/Partial | Partial | Yes on higher tiers |
| Corporate actions + adjustment history | Partial; adjustment API | Yes splits/dividends/events, but negative coverage unverified | Yes | Partial; product/order-form dependent | Partial; Sharadar ACTIONS requires validation | Yes for daily adjustments |
| Ticker/symbol continuity | No verified PIT master | Partial; ticker events are not enough until validated | Yes; PIT_SRF/PIT_EVT and identifiers | Partial; previous-ticker/security history | Partial | Partial; local proprietary database |
| Historical security-type classification | No | Partial; date-filtered ticker type needs sample proof | Yes in PIT reference product, subject to sample | Partial | Partial | Partial |
| Release/vintage identifier | API fetch time only; immutable source snapshot unverified | Daily file path/date; correction versioning unresolved | Delivery-specific; confirm | Delivery-specific; confirm | Bulk metadata includes snapshot/refresh times | Database update version; export rights constrained |
| Pagination | Page token | `next_url`; flat files avoid symbol pagination | Delivery/API dependent | API paging; limits order-form dependent | Table paging and bulk exporter | Local database |
| Bulk download | No market-wide daily bulk documented | Yes, daily compressed S3 CSV | S3/SFTP/API/Snowflake | CSV/S3/Snowflake on applicable plans | Yes | Local updater; restricted export |
| Public small-user price | $0 or $99/month | $29/$79/$199 monthly individual tiers | Quote | $150 individual; Startup ramps $333/$666/$999 | Product-specific subscription/quote | $270–$787.50/year by package |
| Internal research right | Unresolved for this entity/use | Individual plans say non-pro/personal; business terms needed otherwise | Advertised, exact order form required | Individual internal only; Startup/Enterprise order form controls commercial use | Default internal use, subject to product terms | Individual use under EULA |
| Retention after termination | Unresolved | Unresolved | Provider advertises ownership/flexible licensing; contract must confirm | Unresolved/order form | Unresolved/order form | No continued database access after lapse; exports restricted |
| Paying-subscriber derived display | Unresolved; written approval required | Quote/business license | Available in principle; explicit redistribution order form required | Startup/Enterprise only as expressly granted | Prior written approval/order form | Not suitable under standard individual EULA |
| Overall V001 fit | Good REST market-data fallback | Best technical market-data fit | Best reference-data candidate | Reference fallback only after proof | Reference fallback only after proof | Internal cross-check only |

### Official evidence behind the matrix

- Alpaca says its historical equity data reaches back to 2016, its consolidated
  feed comes from CTA and UTP, Basic allows 200 historical calls/minute, and Algo
  Trader Plus allows 10,000/minute for $99/month.
  [Alpaca plans and sources](https://docs.alpaca.markets/us/docs/about-market-data-api)
  Alpaca also advertises extended hours and aggregate bars; its FAQ identifies
  `feed=sip` for consolidated historical data and explains the latest-15-minute
  restriction on the free plan.
  [Alpaca data product](https://alpaca.markets/data) and
  [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
- Massive documents daily `us_stocks_sip/minute_aggs_v1` files, all major U.S.
  exchanges/FINRA/dark pools, 04:00–20:00 ET coverage, UTC timestamps, and
  unadjusted flat files. Its official minute-file page lists 5-year Starter,
  10-year Developer, and all-history Advanced access at $29, $79, and $199 per
  month for individual plans. Those prices are not business redistribution
  quotes. [Massive flat-file overview](https://massive.com/docs/flat-files/stocks/overview)
  and [minute aggregates](https://massive.com/docs/flat-files/stocks/minute-aggregates).
  Commercial use remains subject to a business agreement.
  [Massive business terms](https://massive.com/legal/businesses-terms-of-service)
- Massive's ticker API supports a date parameter and returns active/delisted and
  classification-related fields, but this does not by itself prove the
  repository's `known_at_timestamp`, negative corporate-action coverage, or
  immutable vintage requirements.
  [Massive all tickers](https://massive.com/docs/rest/stocks/tickers/all-tickers)
- EDI documents PIT_SRF listing-level start/end-dated history since January 2005
  and PIT_EVT corporate-action context, with API/S3/SFTP/Snowflake delivery.
  [EDI security reference data](https://www.exchange-data.com/product/securities-reference-data/)
  Its public site describes pricing as client-specific.
  [EDI pricing](https://www.exchange-data.com/competitive-pricing-edi/)
- Intrinio's current public pricing lists Individual at $150/month, Startup at
  six months each of $333 and $666 then $999/month, and Enterprise at
  $1,250/month and up. Individual explicitly excludes redistribution/external
  display; Startup advertises business-wide display/commercial use, but the
  executed order form controls the actual feeds and rights.
  [Intrinio pricing](https://intrinio.com/pricing)
  Intrinio's terms say commercialization, redistribution, and display rights are
  generally available only under Startup or Enterprise order forms and warn that
  transformed or AI-generated output does not automatically avoid display
  licensing. [Intrinio terms](https://about.intrinio.com/terms)
- Nasdaq Data Link's default terms permit internal use and constrained derived
  data, but prohibit external distribution and SaaS use absent an order form or
  prior written approval. [Nasdaq Data Link terms](https://data.nasdaq.com/terms)
  Premium Tables support 5,000 calls per 10 minutes, 720,000/day, and bulk
  exports subject to separate limits.
  [Nasdaq Data Link limits](https://docs.data.nasdaq.com/docs/rate-limits-1)
- Norgate advertises survivorship-bias-free U.S. stock history and higher-tier
  delisted/historical-listing coverage, but its offering is end-of-day, Windows
  oriented, and governed by an individual-use EULA; it is not a SIP minute-feed
  solution. [Norgate packages](https://norgatedata.com/stockmarketpackages.php),
  [data coverage](https://norgatedata.com/data-content-tables.php), and
  [EULA](https://norgatedata.com/subscribe/eula.php)

## 4. Request volume, duration, and storage

### Current repository's per-symbol Alpaca acquisition path

The current implementation makes separate premarket and regular requests for
each symbol/session. Before pagination and retries:

| Scope | Symbol-sessions | Base API requests | Maximum minute slots |
|---|---:|---:|---:|
| 4,000 symbols × 80 sessions | 320,000 | 640,000 | 228,800,000 |
| 4,000 symbols × 272 sessions | 1,088,000 | 2,176,000 | 777,920,000 |

The slot counts use 325 selection-safe premarket minutes (04:00–09:25 exclusive)
plus 390 normal regular-session minutes. They are upper bounds, not expected bar
counts: providers commonly omit minutes with no qualifying trades. Early closes
also reduce regular-session minutes.

Theoretical rate-limit floors, assuming one page per segment, no retries, perfect
request saturation, and no provider/network latency:

| Plan | Published limit | 640,000 requests | 2,176,000 requests |
|---|---:|---:|---:|
| Alpaca Basic | 200/min | 53 h 20 m | 181 h 20 m (7 d 13 h 20 m) |
| Alpaca Algo Trader Plus | 10,000/min | 64 m | 217.6 m (3 h 37 m 36 s) |

These are lower bounds, not delivery promises. The current program also performs
normalization, hashing, write-once publication, and two segment-level raw captures
per symbol/session. Actual elapsed time will be materially longer, especially if
executed serially. Pagination may increase request counts.

### Bulk-file alternative

Massive's market-wide daily minute files reduce provider objects to 80 or 272
daily files rather than hundreds of thousands of symbol requests. Its official
browser reports approximately 4.7 GB compressed for all 2024 stock minute files
and 5.4 GB for 2025. A simple session-proportional estimate is roughly 1.5–1.8 GB
for 80 sessions and 5–6 GB for 272 sessions of provider gzip files. This is an
**assumption**, because daily activity and file sizes vary.

The repository must still retain normalized segments and provenance. Using the
maximum slot counts and an assumed combined 100–250 bytes per populated bar
across retained raw and canonical representations yields a deliberately broad
planning range:

- **80 sessions:** about 11–57 GB at 50–100% slot occupancy.
- **272 sessions:** about 39–195 GB at 50–100% slot occupancy.

Add metadata, checksums, indexes, backups, and at least one immutable copy. A
practical initial storage reservation is **150 GB** for 80 sessions and **500 GB**
for the maximum window until a measured pilot replaces these assumptions.

## 5. Cost scenarios

Public prices below are snapshots as of the evaluation date and exclude tax,
exchange fees, cloud storage, engineering, and negotiated reference-data rights.

### Small internal research implementation

| Component | Verified public amount | Planning treatment |
|---|---:|---|
| Massive Stocks Starter | $29/month individual | Technically sufficient five-year history and bulk minute access for V001; only use if the researcher qualifies and the license confirms the intended internal use. |
| Massive Stocks Developer | $79/month individual | Ten-year history is unnecessary for V001 but may support later research. The same individual-use qualification applies. |
| Massive Stocks Advanced | $199/month individual | More history than V001 requires; no benefit for the registered 2024–2025 window unless other features require it. |
| Alpaca Basic fallback | $0/month | The old SIP dates are technically accessible at 200 requests/minute; retention and business-use rights remain unresolved. |
| Alpaca Algo Trader Plus fallback | $99/month | Faster REST acquisition; retention and research-entity rights still require confirmation. |
| EDI PIT/reference/actions | Quote | Required reference candidate; there is no defensible public price. Request a bounded U.S.-equities pilot quote. |
| Intrinio Startup fallback | $5,994 first 12 months; $999/month thereafter | Published ramp is 6×$333 + 6×$666. Additional reference feeds or rights may cost more. |
| Intrinio Enterprise fallback | $1,250/month minimum | Custom datasets and terms; $15,000/year is only the published floor. |

The recommended pilot market-data component is therefore **$29 for one month of
Massive Starter**, while Alpaca's technical cash floor is $0 at a much slower
published request limit. In either case, the total is **market-data cost plus an
unknown reference-data quote**. A free tier or provider trial does not waive
licensing requirements. It is not valid to report a complete pilot budget until
EDI (or an accepted alternative) quotes PIT reference and action coverage.

### Future paying-subscriber product

Massive Business and EDI redistribution pricing are both custom. Public retail
prices must not be used as commercial-product estimates. For budgeting only,
not as provider quotes, reserve:

- **Assumption: $3,000–$20,000+ per month** for consolidated market data,
  point-in-time reference data, corporate actions, retention, and external
  derived-display rights. Exchange or per-user fees may be additional.
- **Assumption: $25,000–$75,000 one-time engineering/legal integration**, based
  on roughly 170–500 hours for a bulk market adapter, reference normalization,
  continuity reconciliation, vintage/correction handling, entitlement controls,
  contract review, and acceptance testing.

These ranges are procurement placeholders only. The product cannot be priced or
launched lawfully until order forms explicitly describe the subscriber-facing
outputs.

## 6. Provider-specific integration work

### Massive as primary market provider

- Add a daily gzip/S3 adapter while retaining every original daily object and
  its object identity/checksum.
- Split the market-wide file deterministically into symbol/date premarket and
  regular segments; preserve missing minutes and condition semantics.
- Record that flat files are unadjusted; apply only an audited corporate-action
  adjustment source consistent with the registered design.
- Validate minute labels, UTC-to-America/New_York conversion, early closes,
  corrections, duplicate rows, and no-trade omissions against a small sample.
- Add release/vintage handling if files can be corrected in place.

### Alpaca as market fallback

- The repository adapter already implements explicit SIP requests, pagination,
  duplicate rejection, segmented raw retention, and feed-evidence limitations.
- Add only procurement controls and measured concurrency/rate-limit scheduling
  after approval; do not bypass the write-once or feed-validation behavior.
- Obtain a written response on raw retention, business research, derived metrics,
  and subscriber-facing output before using it beyond an individual internal pilot.

### EDI as reference provider

- Map PIT_SRF/PIT_EVT records to the four repository schemas.
- Obtain a daily U.S. common-stock eligibility rule and identify the exact
  security-type codes included/excluded.
- Map provider IDs/FIGIs and exchange-level tickers into non-overlapping symbol
  continuity intervals.
- Convert action events and adjustment factors with effective and knowledge
  timestamps.
- Establish an auditable way to emit `verified_none` for a bounded symbol/date
  only when the licensed source proves complete coverage.
- Preserve delivery file identity, publication time, revisions, and source lineage.

### Intrinio reference fallback

- Request sample security-history, delisted-security, action, and previous-ticker
  responses for securities with ticker changes and split/merger histories.
- Prove historical as-of classification and `known_at_timestamp`; current public
  endpoint descriptions are not sufficient.
- Confirm whether the chosen plan includes complete historical corporate actions,
  not merely current/latest action metadata.
- Put every external display and derived-data permission in the order form.

### Nasdaq Data Link / Sharadar fallback

- Validate the exact TICKERS/ACTIONS table fields, PIT semantics, security-type
  history, delisted coverage, and provider snapshot timestamps with sample files.
- Use bulk exports rather than row pagination and persist `data_snapshot_time`
  and `last_refreshed_time` as vintage evidence.
- Obtain product-specific third-party terms and written SaaS/derived-display rights.

### Norgate cross-check only

- Useful for internal survivorship-bias comparisons if its license permits the
  exact use, but not as the canonical source: it lacks intraday SIP bars and its
  proprietary local database/export restrictions do not match the production
  portability requirement.

## 7. Smallest lawful pilot

The minimum pilot that tests the acquisition contract without changing the
cohort methodology is:

1. Select the first registered cohort date, **2024-06-03**, and its exact 20 XNYS
   warm-up sessions from **2024-05-03 through 2024-05-31**.
2. License and freeze the complete point-in-time U.S. common-stock universe for
   2024-06-03, including every security needed to prove inclusion and exclusion.
3. Acquire market data for the entire screened universe—not symbols chosen after
   observing that day's move—for all 20 warm-ups and the pilot date.
4. Acquire listing, delisting, security-type, action, and symbol-continuity
   evidence sufficient for every considered security.
5. Build and freeze the 09:25 selection audit, then stop. Do not inspect regular-
   session outcomes as part of procurement acceptance.

This is approximately 84,000 symbol-sessions if the universe contains 4,000
symbols. With the current two-request REST architecture it implies about 168,000
base requests; with daily market-wide flat files it requires 21 source files.
It validates cutoffs, joins, vintages, missing-data behavior, and provider rights.
It is **not** a strategy-validation sample. The first performance-capable V001
dataset remains the registered 80-session acquisition (20 warm-up + 60 cohort),
extended only by the preregistered stopping rule.

## 8. Written questions for provider sales/support

Send the technical schema document with these questions and request that answers
be incorporated into the order form or data specification.

### Market-data provider

1. Is the historical minute dataset consolidated CTA/UTP SIP data for every
   covered U.S. equity, including off-exchange reports, or are any venues omitted?
2. Does it include 04:00–09:25 ET and all XNYS regular-session minutes for
   2024-05-03 through 2025-06-04? Are bars omitted when no eligible trade occurs?
3. What trade conditions are included or excluded from OHLCV and VWAP aggregation?
4. Are timestamps left-labeled? How are DST, early closes, corrections, busted
   trades, late reports, and market halts represented?
5. Are files adjusted or unadjusted? Which corporate actions affect price and
   volume, and when are adjustments revised?
6. Can daily bulk files be retrieved by immutable version or checksum? If a file
   is corrected, is the old version available and is a correction notice issued?
7. What are API/bulk rate limits, concurrency limits, retry rules, and expected
   availability time? Is there a manifest proving a download is complete?
8. May we retain raw and normalized historical data, checksums, and backups
   indefinitely for reproducibility, including after termination?
9. Does the license permit internal strategy research, backtesting, feature
   engineering, model training, and storage in our cloud environment?
10. Which derived outputs—scores, ranks, alerts, aggregate statistics, model
    predictions, and non-reconstructable charts—may be shown to paying subscribers?
11. Which outputs trigger display, redistribution, non-display, professional-user,
    CTA/UTP, exchange, or per-subscriber fees?
12. May customers export reports or API results? What delay or aggregation is
    required to avoid raw-data redistribution?
13. Are contractors, affiliates, disaster-recovery vendors, and hosted analytics
    subprocessors authorized users?
14. What deletion, audit, attribution, usage-reporting, and post-termination
    obligations apply?

### Reference-data provider

1. Can you deliver the complete U.S. exchange-listed **common-stock** universe as
   it was known before 09:25 ET on each historical date, rather than reconstructing
   it using today's classifications?
2. Which codes distinguish common stock from ETF, ETN, ADR, preferred, warrant,
   unit, right, closed-end fund, SPAC unit, and OTC security?
3. Do records include effective-from, effective-to, known/published-at, source,
   correction time, and immutable dataset-release identifiers?
4. Are primary exchange, MIC, calendar, listing, suspension, delisting, and
   relisting histories included?
5. How are ticker changes, recycled tickers, mergers, share-class changes, and
   predecessor/successor securities linked? Which stable IDs are licensed?
6. Does the action history include splits, reverse splits, stock dividends,
   cash dividends, mergers, spin-offs, distributions, and symbol/security changes?
7. Are price and volume adjustment factors supplied with effective and publication
   timestamps? Can later corrections be distinguished from original releases?
8. Can the provider certify complete action coverage for a bounded symbol/date
   when no event exists, so the system can create a sourced `verified_none` row?
9. Are historical shares outstanding or market capitalization available point in
   time, and what reporting lag/knowledge timestamp applies? (This is audit-only
   in V001, not a new matching rule.)
10. Can sample files be provided for delisted companies, ticker changes, mergers,
    splits, no-action periods, and ambiguous/recycled symbols from 2024–2025?
11. May raw reference deliveries and normalized histories be retained and backed
    up after termination for reproducibility?
12. May derived classifications, cohort membership, model features, and aggregate
    intelligence be displayed to paying subscribers? Which raw fields may not be
    exposed or reconstructed?
13. Are redistribution rights inclusive of APIs, dashboards, reports, alerts,
    exports, and customer-facing AI systems, or must each be licensed separately?
14. What are the U.S.-only pilot, production internal-use, and production
    redistribution prices, implementation fees, minimum term, and annual uplift?

## 9. Decision gates and unresolved facts

Collection must remain disabled until these points are resolved:

- **License gate:** Neither Alpaca's public product page nor Massive's individual
  pricing proves the right to retain data for a business or display derived
  intelligence to paying subscribers.
- **Reference gate:** EDI is the strongest documented reference candidate, but a
  sample must prove every repository field, especially historical common-stock
  classification, knowledge timestamps, immutable vintages, and negative action
  coverage.
- **Join gate:** The market and reference providers must share or map through a
  stable licensed identifier; ticker text alone is not sufficient.
- **Correction gate:** The system needs a contractual and technical policy for
  corrected market and reference releases without mutating a frozen vintage.
- **Cost gate:** Public individual prices are not commercial quotes. Total
  subscriber-product cost remains unresolved until both providers return order
  forms covering the exact output surface.
- **Redistribution gate:** “Derived” is not a universal safe harbor. Intrinio and
  Nasdaq Data Link explicitly condition external use on order-form rights; the
  chosen providers must confirm the same issues in writing.

Until all gates pass, the lawful next action is a provider questionnaire and
sample-data review—not a historical download.
