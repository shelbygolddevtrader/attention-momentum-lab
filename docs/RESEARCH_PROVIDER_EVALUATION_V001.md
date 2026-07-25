# Research Cohort V001: Provider and Licensing Readiness

**Status:** procurement package; collection and purchasing not authorized
**Originally evaluated:** 2026-07-13
**Revalidated:** 2026-07-22
**Controlling specifications:** `RESEARCH_COHORT_V001_DESIGN.md`,
`RESEARCH_DATA_SCHEMAS_V001.md`, and `COHORT_SELECTION_PROTOCOL_V001.md`
**Decision:** **NO-GO** until the technical samples and written rights below pass

This document is a technical and commercial readiness assessment, not legal
advice. **Verified** means a current official provider page supports the stated
fact. **Conditional** means the public material is promising but a representative
sample or executed order form must prove the requirement. **Unresolved** means no
official public source reviewed on 2026-07-22 establishes the requirement.

## Executive decision

Research Cohort V001 still requires a multi-provider architecture unless one
vendor proves the complete reference-data contract with samples.

1. **Primary market-data candidate: Massive Stocks Business.** Its official
   materials document consolidated U.S. SIP minute flat files, 04:00–20:00 ET
   coverage, full-market daily bulk delivery, more than 20 years of history, and
   a current public business price of **$1,999/month**. The business page
   expressly describes internal tools, backtesting, and signal analysis.
   [Stocks flat files](https://massive.com/docs/flat-files/stocks/overview) ·
   [Stocks Business](https://massive.com/business-stocks)
2. **Primary reference-data candidate: Exchange Data International (EDI).** Its
   PIT_SRF product has start/end-dated listing-level history since January 2005;
   PIT_EVT adds the reason for static-data changes from corporate actions. EDI
   also offers North American corporate actions and advertises customized
   redistribution licensing. Price and exact rights require a quote and order
   form. [PIT reference data](https://www.exchange-data.com/product/securities-reference-data/) ·
   [North American corporate actions](https://www.exchange-data.com/product/north-american-corporate-actions/) ·
   [Flexible licensing](https://www.exchange-data.com/flexible-licensing/)
3. **Conditional single-provider candidate: Massive Stocks Business.** Massive
   exposes date-filtered ticker records with active/delisted status, security
   type, FIGIs, exchange, and `last_updated_utc`. It also offers corporate-action
   and ticker-event endpoints. It becomes a one-provider option only if sample
   files prove historical knowledge time, symbol continuity, corrections,
   immutable vintage, and bounded negative corporate-action coverage.
   [All Tickers](https://massive.com/docs/rest/stocks/tickers/all-tickers) ·
   [Ticker Types](https://massive.com/docs/rest/stocks/tickers/ticker-types)
4. **Market-data fallback: Alpaca SIP, only under written commercial permission.**
   Alpaca technically supplies explicit SIP historical bars since 2016 and
   extended-hours data, but its $99 Trading API plan is framed for individual
   traders. Alpaca's official support page states that Alpaca API data cannot be
   redistributed, and its customer terms prohibit commercial exploitation
   without written consent. [Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api) ·
   [Redistribution answer](https://alpaca.markets/support/redistribute-alpaca-api) ·
   [Disclosures](https://alpaca.markets/disclosures)

Do not buy an individual plan for a pilot intended to seed a future commercial
product. Massive's individual market-data terms limit use to personal,
non-business, non-commercial purposes and restrict derivative works unless
licensed. [Massive market-data terms](https://massive.com/legal/market-data-terms-of-service)

The smallest lawful pilot remains one complete point-in-time U.S. common-stock
universe on 2024-06-03 plus its exact 20 registered warm-up sessions. It tests
data contracts only and must stop after freezing the 09:25 selection audit.

## 1. Non-negotiable repository contract

### Market observations

- Consolidated CTA/UTP SIP one-minute OHLCV, not IEX-only data.
- Premarket bars in **[04:00:00, 09:25:00) America/New_York**.
- Regular bars on the authoritative XNYS left-labeled minute index, normally
  **[09:30:00, 16:00:00)**; 16:00 is not a regular-session bar.
- The complete screened universe for each date, not symbols selected after a
  move is observed.
- Twenty distinct verified warm-up sessions for every screened security.
- Missing and zero-trade minutes remain distinguishable; no interpolation.
- Raw provider pages/files, processed segments, request identity, feed,
  adjustment, timestamps, pagination, corrections, retry state, hashes, and
  immutable dataset vintage.

### Point-in-time reference evidence

- A complete U.S. common-stock universe known strictly before 09:25 ET.
- Historical security type, active status, exchange, and calendar identity.
- Listing and delisting intervals with `known_at_timestamp`.
- Symbol continuity with stable identifiers and non-overlapping effective dates.
- Corporate actions with effective and knowledge timestamps and adjustment
  provenance.
- A sourced, bounded coverage assertion when no corporate action occurred.
  Empty results do not establish `verified_none`.
- Release, snapshot, or delivery identifiers sufficient to reproduce the data
  vintage and distinguish later corrections.

### Required contractual rights

- Internal quantitative research and backtesting by the intended legal entity.
- Raw and normalized data storage, governed backups, and cloud processing.
- Retention and reproducibility after subscription termination, or an explicit
  alternative archival right.
- Creation and internal use of features, scores, simulations, and models.
- Display of non-reconstructable derived intelligence to paying subscribers.
- Explicit treatment of dashboards, alerts, reports, CSV exports, and APIs.
- Clear limits on raw data, reconstructable values, redistribution, and
  competing-data products.
- Named rights for employees, contractors, subprocessors, and disaster recovery.
- All CTA, UTP, exchange, professional-user, display, and non-display fees.

## 2. Procurement requirements matrix

Legend: **V** verified publicly; **C** conditional on sample/order form;
**N** documented mismatch; **U** unresolved; **—** not the provider's role.

| Requirement | Massive Business | EDI | Alpaca Trading API | Intrinio | Nasdaq Data Link / Sharadar | Norgate |
|---|---:|---:|---:|---:|---:|---:|
| Consolidated SIP minute bars | V | — | V | U | U | N |
| 04:00–09:25 ET coverage | V | — | C | U | U | N |
| Regular-session minute bars | V | — | V | U | U | N |
| June 2024–June 2025 history | V | V for reference | V | C | C | V, daily only |
| Market-wide bulk delivery | V | — | N | C | C | N |
| PIT common-stock universe | C | C | U | U | C | C |
| Historical security type | C | C | U | U | C | C |
| Listings and delistings | C | C | U | C | C | V, daily product |
| Ticker/symbol continuity | C | C | U | C | C | C |
| Stable identifiers | V, FIGI | V, FIGI and others | U | C | C | C |
| Corporate-action history | V endpoint; sample required | V | C | C; current page says most recent only for one feed | C | C |
| Bounded negative-action evidence | U | U | U | U | U | U |
| Knowledge/publication timestamp | C | C | U | C | C | U |
| Immutable release/vintage | U | C | U | C | C | U |
| Public business price | V, $1,999/month | Quote | V, $99/month individual | V, $333 startup / $1,250+ enterprise | Product/order-form specific | V, personal packages |
| Internal business research | V at high level; order form controls data | C | N without written consent | C | V by default terms | N |
| Raw retention after termination | N by default business terms; must amend | C | U | U | N by default terms; must amend | N |
| Paying-subscriber derived display | U; must be in order form | C; advertised as customizable | N by default | C under executed Startup/Enterprise order form | N by default; written approval required | N |
| Standard V001 fit | Best market candidate | Best reference candidate | Technical fallback only | Reference fallback only | Reference fallback only | Disqualified |

### Matrix evidence

- Massive documents the `us_stocks_sip/minute_aggs_v1` daily files, direct SIP
  processing, every major U.S. exchange plus FINRA and dark pools, unadjusted
  values, UTC timestamps, and 04:00–20:00 ET coverage.
  [Flat-file overview](https://massive.com/docs/flat-files/stocks/overview)
- Massive's current public business plan is $1,999/month and includes minute
  aggregates, flat files, historical trades and quotes, reference data, and
  corporate actions. [Business pricing](https://massive.com/business-stocks)
- Massive's default business terms prohibit derivative strategies and external
  use of information unless licensed, and require deletion of information at
  termination. The order form and third-party agreements therefore must amend
  these points explicitly. [Business terms](https://massive.com/legal/businesses-terms-of-service)
- EDI's PIT_SRF contains start/end-dated listing-level changes since January
  2005, and PIT_EVT explains reference changes using corporate-action events.
  Delivery includes S3, SFTP, API, and Snowflake. Public pricing is client
  specific. [Reference data](https://www.exchange-data.com/product/securities-reference-data/) ·
  [Pricing](https://www.exchange-data.com/competitive-pricing-edi/)
- EDI advertises flexible redistribution agreements, but marketing language is
  not the executed right to show this project's derived subscriber outputs.
  [EDI licensing](https://www.exchange-data.com/flexible-licensing/)
- Alpaca documents historical equity coverage since 2016, CTA/UTP SIP, Basic at
  200 historical calls/minute, and Algo Trader Plus at $99/month and 10,000
  calls/minute. Its support and customer materials do not grant commercial
  redistribution. [Alpaca plans](https://docs.alpaca.markets/us/docs/about-market-data-api) ·
  [Historical feed semantics](https://docs.alpaca.markets/us/v1.1/docs/historical-stock-data-1)
- Intrinio currently publishes Individual at $150/month, Startup from
  $333/month, and Enterprise from $1,250/month. Individual has no external
  display; Startup advertises display/commercial use, but the executed order
  form controls the exact datasets and rights. Its public Corporate Events
  listing describes the available corporate-action history as “most recent
  only,” which does not meet V001 without a custom historical feed.
  [Intrinio pricing](https://intrinio.com/pricing) ·
  [Intrinio terms](https://about.intrinio.com/terms)
- Nasdaq Data Link's default terms allow internal use and constrained derived
  data, but prohibit external distribution, SaaS use, and post-termination use
  unless an order form or written approval says otherwise. Premium Tables allow
  5,000 calls per 10 minutes and 720,000/day; bulk exports have separate limits.
  [Nasdaq terms](https://data.nasdaq.com/terms) ·
  [Rate limits](https://docs.data.nasdaq.com/docs/rate-limits-1)
- Norgate explicitly provides end-of-day rather than intraday data, limits its
  standard license to one natural person and personal use, prohibits commercial
  use, and requires data destruction after expiration. It cannot be a V001
  production provider. [Norgate overview](https://norgatedata.com/index.php/pricing/) ·
  [Norgate EULA](https://norgatedata.com/subscribe/eula.php)

## 3. Facts versus written confirmations

### Facts established by current official material

- Massive publicly proves the exact required SIP extended-hours window. Alpaca
  proves SIP and extended-hours support, but the exact 04:00 boundary remains a
  sample confirmation.
- Massive daily flat files are operationally superior to per-symbol REST calls
  for a roughly 4,000-symbol universe.
- EDI offers genuine point-in-time listing-level reference history and linked
  static-data events rather than only a current symbol master.
- Massive individual plans, Alpaca's ordinary customer terms, Intrinio
  Individual, Nasdaq default terms, and Norgate's standard license do not grant
  the complete future commercial use required here.
- No public material reviewed proves the exact `verified_none` corporate-action
  record or the complete post-termination archival right required by V001.

### Required written confirmation from every shortlisted vendor

1. The precise legal entity and authorized users covered by the license.
2. Whether raw deliveries, normalized files, hashes, and backups may be retained
   and used after termination for reproducibility.
3. Whether cloud storage, CI, contractors, and disaster-recovery processors are
   authorized.
4. Whether features, scores, ranks, simulated trades, charts, alerts, and model
   outputs are permitted derived data.
5. Whether those derived outputs may be displayed to paying subscribers without
   per-user exchange licenses when they cannot reconstruct source data.
6. Which dashboard, report, download, alert, API, or export forms are licensed.
7. What counts as prohibited raw, delayed, derived, reconstructable, or
   competing data.
8. Whether market-data use is display or non-display and which CTA/UTP,
   professional, exchange, audit, or subscriber fees apply.
9. Whether historical releases can be reproduced after corrections and how
   delivery versions are identified.
10. Whether a bounded symbol/date with no action can be certified as complete
    coverage rather than an empty search result.

## 4. Ranked shortlist

### Rank 1 — Massive Business plus EDI PIT/reference/actions

**Why:** best verified bulk SIP mechanics plus the strongest documented PIT
reference model.
**Open gates:** two order forms, cross-provider stable-ID mapping, archival
rights, derived subscriber display, negative-action coverage, and total quote.
**Public cash floor:** $1,999/month for Massive plus an unquoted EDI license.

### Rank 2 — Massive Business alone, conditional simplification

**Why:** one ingestion and licensing relationship; date-filtered tickers,
security types, FIGIs, delisting fields, corporate actions, and ticker events
are technically promising.
**Open gates:** PIT “known-at” semantics, corrections/vintage, recycled tickers,
complete listing intervals, and negative-action certification.
**Decision rule:** accept only if the sample passes every reference test below;
otherwise revert to Rank 1 without weakening schemas.

### Rank 3 — Massive Business plus an alternate reference source

- **Intrinio Enterprise:** consider only if a custom feed supplies historical
  PIT universe, security types, listings, actions, and symbol continuity and the
  order form grants retention and derived display.
- **Nasdaq Data Link / Sharadar:** consider only after a sample proves PIT
  fields, delisted coverage, action knowledge time, stable IDs, vintage, and
  negative coverage, with external-use and archival amendments.

### Rank 4 — Alpaca SIP plus EDI, technical contingency

The repository already integrates Alpaca pagination and explicit SIP. It is
operationally expensive for the full universe and is legally unsuitable under
ordinary individual terms. Use only if Alpaca supplies a commercial order form
covering internal research, retention, and derived display.

### Disqualified under standard public terms

- Massive Individual, Alpaca Trading API customer access, and Intrinio
  Individual for a pilot intended to seed a commercial product.
- Norgate for V001 production: no intraday data, personal-only standard license,
  and no continued use after lapse.
- Any current-universe-only source, scraped website, hindsight ticker list, or
  source that cannot establish knowledge time and symbol continuity.
- Any vendor that treats an empty corporate-action response as proof of no
  action without certifying coverage.

## 5. Sample-file acceptance protocol

Request samples before starting a trial or download. Samples must be legally
permitted for evaluation and retained only as the evaluation agreement allows.
Run every delivery through `scripts/check_vendor_sample.py` using the local-only
contracts in `VENDOR_SAMPLE_ACCEPTANCE_V001.md`. A technical pass does not admit
data unless the separate written licensing manifest also passes.

### 5.1 Market-data sample

Request the complete daily U.S. stocks minute file for 2024-06-03 and at least
one warm-up date containing a split, ticker change, thinly traded stock, ETF,
ADR, and delisted security.

Pass only if:

1. Provider documentation identifies CTA/UTP SIP provenance and included trade
   conditions.
2. Bars include eligible trades from 04:00 ET and preserve the 09:25 exclusion.
3. UTC-to-America/New_York conversion reproduces left-labeled minutes.
4. Regular normalization excludes 16:00 and respects authoritative early closes.
5. Missing minutes remain absent and zero-trade sessions are distinguishable
   from unavailable files.
6. Duplicate, out-of-order, and cross-date rows can be detected without
   silently dropping data.
7. Adjustment status is explicit; unadjusted price and volume can be aligned to
   separately versioned action factors.
8. A manifest or stable object identity proves completeness, byte hash, release
   time, and correction/version behavior.
9. The full date can be acquired as a market-wide object without hindsight
   symbol filtering.

### 5.2 Reference-data sample

Request complete U.S. listings and actions for the same dates plus curated
examples of a normal common stock, ETF, ADR, preferred, warrant, SPAC unit,
delisted company, ticker change, recycled ticker, split, reverse split, merger,
spinoff, listing transfer, and a verified no-action period.

Pass only if:

1. A complete as-of universe can be reconstructed before 09:25 ET.
2. Common stock is distinguishable from every excluded security type using
   documented historical codes.
3. Listing start/end, primary exchange, MIC, active status, and knowledge time
   are present and historically accurate.
4. Stable IDs connect old and new tickers while preventing recycled-ticker
   collisions.
5. Symbol mappings and listings have non-overlapping effective intervals.
6. Corporate actions include type, effective date/time, original publication or
   knowledge time, revisions, and adjustment factors.
7. The provider can certify complete coverage for a bounded no-action interval
   and explain how to construct `verified_none`.
8. Every delivery exposes source and immutable release/vintage identity.
9. Repeating the extraction from the same vintage is byte- or record-equivalent.
10. All fields map to `RESEARCH_DATA_SCHEMAS_V001.md` without fabricated values
    or relaxing validation.

### 5.3 Contract acceptance test

The executed order form must explicitly answer “yes” to internal research,
raw/normalized retention, governed backups, cloud processing, feature/model
creation, and the agreed subscriber-facing derived outputs. It must enumerate
prohibited outputs and post-termination duties. Marketing phrases such as
“business use,” “commercial use,” or “you own your data” do not substitute for
the order-form language.

## 6. Exact outreach questions

Send the repository schema document and the following use-case statement:

> We are building an internal historical U.S.-equity research system. It stores
> raw and normalized data, creates non-reconstructable features and simulated
> results, and may later display derived intelligence—not source market data—to
> paying subscribers. No live redistribution is requested in the pilot.

### Market-data vendor

1. Is the minute dataset consolidated CTA/UTP SIP data for all exchange-listed
   U.S. equities, including off-exchange eligible reports?
2. Does it cover 04:00–09:25 ET and [09:30, 16:00) ET for every date from
   2024-05-03 through 2025-06-04?
3. Which sale conditions update OHLCV, and when is a no-trade minute omitted?
4. Are bars left-labeled? How are DST, early closes, halts, corrections, busted
   trades, and late reports handled?
5. Are files adjusted? If not, which versioned split/action factors are supplied?
6. What object ID, checksum, release time, and correction history make a daily
   file reproducible? Are superseded versions retrievable?
7. Does a full-universe daily file have a completeness manifest?
8. May our legal entity retain raw files, normalized files, hashes, and backups
   after termination for reproducibility and audit?
9. May employees, contractors, CI systems, cloud storage, and disaster-recovery
   vendors process or store the data?
10. May we create features, scores, simulations, alerts, and model outputs?
11. May non-reconstructable derived intelligence be displayed to paying
    subscribers? Please address dashboards, reports, alerts, CSV, and APIs.
12. Which outputs trigger display, non-display, professional-user, CTA/UTP,
    exchange, or per-subscriber fees?
13. What raw or reconstructable values are prohibited from customer display or
    export?
14. Please quote the smallest business license for the 21-session pilot and the
    80-session production cohort, including retention and derived-display rights.

### Reference-data vendor

1. Can you deliver the complete U.S. exchange-listed common-stock universe as it
   was known before 09:25 ET on every historical date?
2. Which historical codes distinguish common stocks from ETFs, ETNs, ADRs,
   preferreds, warrants, units, rights, funds, and OTC securities?
3. Do records include effective-from, effective-to, known/published-at,
   correction time, source, and immutable release ID?
4. Are listing, delisting, suspension, relisting, exchange, MIC, and historical
   security-type changes included?
5. How are ticker changes, recycled tickers, mergers, share-class changes, and
   predecessors/successors linked? Which stable IDs are licensed?
6. Do corporate actions include splits, reverse splits, stock and cash
   dividends, mergers, spinoffs, special distributions, listing transfers, and
   symbol/security changes?
7. Are adjustment factors supplied with effective and original publication
   timestamps, and can later corrections be distinguished?
8. Can you certify complete action coverage for a bounded symbol/date with no
   event so we can create a sourced `verified_none` record?
9. Can deliveries be reproduced by immutable vintage, checksum, or snapshot ID?
10. Please supply samples covering each case in section 5.2 and a field-level
    data dictionary.
11. May we retain raw reference deliveries and normalized histories after
    termination for reproducibility?
12. May cohort membership, derived classifications, features, and aggregate
    intelligence be displayed to paying subscribers?
13. Which fields or derived outputs require redistribution, display, or
    per-subscriber licensing?
14. Please quote the complete U.S.-equity 21-session pilot and the 80-session
    production scope, including actions, PIT history, archival rights, and
    derived display.

## 7. Decision sequence

1. **User decision:** identify the contracting legal entity, intended users,
   cloud/subprocessors, and expected subscriber output forms.
2. Send the same written use-case and sample specification to Massive and EDI.
3. In parallel, ask Massive whether its reference endpoints alone can pass the
   section 5.2 tests; do not assume they can.
4. Obtain sample data dictionaries, samples, draft order forms, all incorporated
   third-party terms, and itemized quotes. Do not start a trial merely to bypass
   this review.
5. Run the technical acceptance tests without inspecting strategy outcomes.
6. Have qualified counsel review retention, derived-data ownership, display,
   redistribution, exchange fees, termination, and audit clauses.
7. Select either Massive-only or Massive+EDI solely from the predefined tests,
   not cost after observing market outcomes.
8. Acquire the 21-session pilot, freeze the 09:25 audit for 2024-06-03, and stop.
9. Approve the 80-session production acquisition only after the pilot's data and
   provenance checks pass.

Estimated decision time cannot be responsibly stated from public materials.
Vendor sample turnaround, legal review, and negotiated rights are unresolved.

## 8. Cost posture

Only current official public prices are stated:

| Component | Current public price | Procurement treatment |
|---|---:|---|
| Massive Stocks Business | $1,999/month | Leading market-data budget floor; order form still needs archival and derived-display rights |
| EDI PIT/reference/actions | Quote | Required reference quote unless Massive passes every PIT test |
| Alpaca Algo Trader Plus | $99/month | Individual technical fallback; not an approved commercial research license |
| Intrinio Individual | $150/month | No external display; disqualified for commercial seed data |
| Intrinio Startup | $333/month initially, then $666 and $999 | Display/commercial marketing claim; exact historical reference feeds and rights require order form |
| Intrinio Enterprise | $1,250/month minimum | Custom fallback; actual feeds and rights may add cost |
| Nasdaq Data Link / Sharadar | Product/order-form specific | No complete current public V001 quote verified |
| Norgate | Package-specific personal pricing | Disqualified regardless of price |

There is no defensible all-in estimate until EDI or another reference provider
quotes the exact coverage and both vendors price archival and subscriber-derived
display rights. Exchange, professional-user, cloud storage, legal, and
engineering costs are additional.

## 9. Explicit no-go conditions

Do not acquire production data or inspect cohort outcomes if any of these remain:

- The plan is personal/individual while the data will seed a commercial product.
- Consolidated SIP provenance or 04:00–09:25 coverage is ambiguous.
- The universe is current-only, survivorship-biased, or reconstructed after the
  selection timestamp.
- Security type, listing status, or symbol continuity cannot be proven PIT.
- Corporate-action absence is inferred from an empty response.
- The source cannot distinguish original publications from later corrections.
- Raw retention, backups, or post-termination reproducibility is prohibited.
- Feature/model creation or internal non-display research is not licensed.
- Paying-subscriber derived display is absent or ambiguous in the order form.
- Required third-party, exchange, professional-user, or audit terms are missing.
- A sample cannot map into the repository schemas without invented fields.
- The vendor refuses representative samples or a field-level specification.
- The proposed pilot uses hand-picked symbols instead of the full PIT universe.

## 10. Decisions still owned by the user

Before outreach, the user must decide:

1. The legal entity that will sign and whether any contractors need access.
2. Whether all research will run in local infrastructure or named cloud services.
3. The intended subscriber surfaces: dashboard, email alert, downloadable
   report, CSV, API, conversational assistant, or combinations.
4. Whether customers will ever see price, volume, timestamps, or other
   reconstructable market-derived values.
5. The acceptable monthly pilot budget above the verified $1,999 market-data
   floor, recognizing that reference and display rights are still unquoted.
6. Whether post-termination reproducibility is mandatory indefinitely or for a
   stated retention period.

Until those choices and the written vendor confirmations exist, the correct
project status is **procurement-ready, collection not authorized**.
