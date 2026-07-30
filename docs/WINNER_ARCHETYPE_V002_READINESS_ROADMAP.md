# Winner Archetype Protocol V002 Readiness Roadmap

Status: implementation roadmap only; discovery execution is not authorized

Assessment date: 2026-07-30

Frozen identities:

- V001 experiment: `f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a`
- V002 protocol: `11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580`
- V002 source requirements: `4a0f350cd24ae2ef5509cbfc72a6994a1bb9df9d3e2dedcfe3354b2cfe4a168c`
- Initial blocked readiness: `01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6`

This document diagnoses prerequisites without opening market, catalyst,
validation, or holdout records. Provider facts and prices are a point-in-time
desktop audit of public documentation, not capability or entitlement evidence.
No provider is approved by this document.

## What readiness means

The protocol intentionally separates five claims:

1. a provider says it has a capability;
2. the account and license permit the intended historical use and retention;
3. an immutable dataset was actually acquired;
4. expected securities, sessions, pages, conditions, corrections, and negative
   coverage reconcile without conflicts;
5. the resulting identities are bound into one discovery experiment.

The original readiness command only evaluated the static source matrix. The
repository now also accepts an optional provider-neutral readiness-evidence
ledger. The ledger contains declarations, entitlement evidence, immutable input
manifests, coverage-set hashes, and conflict state—not empirical rows. Omitting
the ledger preserves the initial readiness report and identity byte for byte.

An evidence-backed report can reach `ready`, but `pilot_authorized` remains
false. Human authorization and a frozen experiment binding are separate gates.

## Exact blockers

| Dataset | Current enforcement | Missing evidence | Type | Satisfying artifact |
| --- | --- | --- | --- | --- |
| broad_market_regime_inputs | source matrix and readiness report | bound point-in-time source, entitlement, immutable observations, session coverage | data/provider | capability + entitlement + complete discovery manifest |
| catalyst_broad_news | V002 catalyst minimum coverage | complete archive with publication, receipt, update, correction, and retraction times for every selection window | provider/data; protocol-required | licensed archive, coverage proof, normalized immutable registry manifest |
| catalyst_sec_filings | V002 catalyst minimum coverage | complete filing and amendment archive plus point-in-time CIK/security mapping | data/mapping; protocol-required | EDGAR archive manifests, acceptance timestamps, mapping manifest |
| catalyst_specialist_regulatory | unknown-category blocking rule | declared FDA, clinical, legal, enforcement, and other specialist coverage | provider/data; protocol-required | category coverage matrix and one or more complete source manifests |
| corporate_actions | knowledge-time and negative-evidence rules | all required action types, corrections/cancellations, lineage, and bounded no-action evidence | provider/data; protocol-required | point-in-time action master and complete coverage manifest |
| exchange_calendar | session contract | immutable XNYS 4.13.2 calendar and final session-plan manifests | implementation/configuration | versioned calendar manifest and deterministic session-plan identity |
| halt_market_status | absence-evidence rule | halt/resume/correction history and proven absence for every security interval | provider/data; protocol-required | authoritative status archive and coverage manifest |
| security_master | universe and stable-identity contracts | complete historical listings, types, status, exchange, issuer, and stable IDs | provider/data; protocol-required | point-in-time security-master manifest |
| sip_minute_bars | raw-tick derivation rule | deterministic eligible-trade aggregation and interval reconciliation | implementation after data | versioned condition rules, derived-bar manifest, reconciliation report |
| sip_quotes | raw market-data contract | quotes with required timestamps, conditions, sizes, venues, tape, order/sequence, corrections, and complete pagination | provider/data; protocol-required | capability/entitlement evidence plus complete quote manifests |
| sip_trades | raw market-data contract | trades with required timestamps, conditions, venues, tape, sequence, corrections/cancels, and complete pagination | provider/data; protocol-required | capability/entitlement evidence plus complete trade manifests |
| symbol_lineage | stable-identity contract | effective/known intervals, recycled symbols, transfers, relistings, revisions | provider/data/mapping; protocol-required | lineage records and reconciled lineage manifest |
| universe_snapshot | 09:25 point-in-time universe rule | one complete pre-cutoff listing population per selection session, including excluded types | data/orchestration; protocol-required | final session plan and complete immutable snapshots |

The frozen rules themselves are not blockers to repair. They are the definition
of admissible evidence. The provider adapters, tick normalizer, completeness
reconciler, calendar/session publisher, and final binding publisher remain
missing code. Configuration remains missing because no provider or entitlement
has been selected or verified. All 13 datasets remain unacquired.

## Dependency graph and critical path

```text
provider due diligence + written licensing
                  |
calendar manifest + candidate session plan
                  |
point-in-time security master + symbol lineage
                  |
09:25 universe snapshots for each planned session
                  |
SIP trades/quotes + actions + halts + catalysts
                  |
normalization + complete coverage reconciliation
                  |
immutable manifests + readiness-evidence ledger
                  |
final cohort/session plan and experiment binding
                  |
human authorization for first discovery-only pilot
```

Provider due diligence, point-in-time universe reconstruction, complete catalyst
coverage, and full SIP quote acquisition are the critical path. Work on parsers
can proceed against synthetic fixtures while contracts and quotes are reviewed.

| Milestone | Prerequisites | Engineering estimate | Data volume | Provider cost | Runtime | Artifacts and success criteria | Main risks |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1. capability and license due diligence | frozen matrix | 1–2 engineer-weeks | none | $0 for review | days to weeks, vendor-dependent | signed capability declarations; written historical-use/retention terms | marketing claims omit corrections, negative coverage, or PIT semantics |
| 2. calendar/session publisher | exchange_calendars 4.13.2 | 2–4 days | <10 MB | $0 | minutes | hashed XNYS calendar, initial/max session plans, DST/early-close tests | exceptional-session conflict |
| 3. security master and lineage adapter | milestone 1 | 2–4 weeks | 1–10 GB | quote-dependent | hours | all listing types reconciled; stable IDs and first-known intervals | survivor bias, recycled tickers, unavailable knowledge times |
| 4. universe snapshot publisher | milestones 2–3 | 1–2 weeks | 1–5 GB | included with reference source | hours | one complete pre-09:25 snapshot per session, exact expected counts | a daily/latest endpoint may not prove historical release time |
| 5. raw SIP acquisition and normalizer | milestones 1, 3–4 | 3–6 weeks | about 1.5–2.0 TB compressed for all-market 2024-06 through 2025-06 flat files; plan 4–6 TB working storage | at least $199 for one month of the public candidate plan | 1–7 days download; several days normalization | immutable raw ticks, full pages/files, versioned condition rules, interval reconciliation | schema omits corrections or receipt time; storage/network limits |
| 6. actions and halts | milestones 1, 3 | 2–4 weeks | <10 GB typical | free sources may be insufficient; quote-dependent | hours to days | point-in-time revisions and proven negative coverage | public halt pages do not prove complete absence |
| 7. catalyst archive and normalization | milestones 1, 3 | 4–8 weeks | 10–500+ GB, vendor-dependent | $99/month advertised starting point for one partner dataset; complete archive requires quote | days to weeks | SEC + broad news + specialist category coverage, immutable revisions | archive licensing, retractions, syndicated duplicates, missing categories |
| 8. final reconciliation and binding | milestones 2–7 | 1–2 weeks | manifests only | $0 incremental | hours | zero readiness blockers, frozen session plan, experiment identity, deterministic replay | hidden gaps or source conflicts |

Total remaining engineering is approximately 14–28 engineer-weeks, dominated by
source integration and completeness proof. This is a planning estimate, not a
delivery commitment.

## Provider and input audit

### Alpaca

Alpaca Algo Trader Plus is advertised at $99/month, with SIP coverage from all
US exchanges, historical data since 2016, no latest-15-minute restriction, and
10,000 historical calls/minute. It is useful as a corroborating source and may
cover bars, trades, and quotes over the V002 dates.

It is not currently proven sufficient for the authoritative V002 raw-tick
contract. The public trade schema documents a trade timestamp, venue, price,
size, conditions, trade ID, and tape, but does not publicly establish the full
exchange/provider-receipt timestamp pair, sequence continuity, append-only
correction/cancellation history, or bounded negative coverage demanded by V002.
Alpaca also does not satisfy the point-in-time universe, complete news,
specialist catalyst, corporate-action negative coverage, or halt absence rules.
The existing subscription therefore has $0 incremental cost but cannot clear
readiness without written capability evidence and other sources.

Official references:

- https://docs.alpaca.markets/us/docs/about-market-data-api
- https://docs.alpaca.markets/us/docs/market-data-faq
- https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data
- https://docs.alpaca.markets/us/docs/historical-api

### Massive

Massive Stocks Advanced is the least-expensive publicly priced single candidate
found for historical SIP trades and quotes: $199/month for individual use, with
20+ years, trades, quotes, reference data, corporate actions, and flat files.
Its trade API documents participant, SIP, and TRF timestamps, nanosecond
precision, sequence, conditions, correction indicator, venue, tape, and trade
ID. Its reference documentation describes point-in-time ticker details and
ticker events.

This makes Massive the leading due-diligence candidate, not an approved source.
Written confirmation is still required for the exact flat-file fields,
correction/cancellation history, complete file publication and checksums,
historical reference release/first-known times, negative coverage, license, and
retention. The public all-market files show the scale: quotes are 1.31 TB for
2024 and 1.63 TB for 2025; trades are 392 GB and 547 GB respectively. A
date-bounded 2024-06 through 2025-06 acquisition is therefore expected to be
roughly 1.5–2.0 TB compressed before duplication and normalization.

Official references:

- https://massive.com/pricing?product=stocks
- https://massive.com/docs/rest/stocks/trades-quotes/trades
- https://massive.com/docs/flat-files/stocks/quotes
- https://massive.com/docs/flat-files/stocks/trades
- https://massive.com/knowledge-base/article/how-does-polygon-handle-ticker-changes-and-acquisitions

### SEC EDGAR

SEC EDGAR is the authoritative and least-cost filing source. Public submissions
and bulk archives require no API key and have no data charge. They include
filing history and authoritative acceptance metadata, but a complete V002 input
still needs immutable raw filing/index archives, fair-access compliance,
amendment reconciliation, and a point-in-time CIK-to-security mapping.

Official references:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/developer-resources

### Exchange directories, calendars, and halts

`exchange_calendars==4.13.2` is already protocol-bound and costs nothing. Nasdaq
Trader publishes current symbol-directory files and a dated historical halt RSS
query; NYSE publishes current/historical halt pages and market-status materials.
These are useful authoritative inputs, but current directory files do not prove
historical pre-09:25 snapshots, and the public NYSE halt page advertises only one
year of historical halt/LULD data. They cannot alone prove complete 2024–2025
absence coverage. A licensed consolidated status archive or retained daily
authoritative snapshots is still required.

Official references:

- https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs
- https://classic.nasdaqtrader.com/snippets/tradehaltaccordion.html
- https://beta.nyse.com/trade/trading-halts
- https://www.nyse.com/market-data/historical

### Broad news and specialist catalysts

Benzinga advertises historical news and security-master/corporate-action APIs;
Massive advertises Benzinga partner datasets starting at $99/month per dataset.
Neither public price page proves the complete historical archive, correction and
retraction semantics, all V002 specialist categories, or the intended research
license. Those require a written scope and quote. SEC EDGAR covers filings, not
broad news, analyst actions, rumors, FDA/clinical, and every legal/enforcement
category.

Official references:

- https://www.benzinga.com/apis/
- https://massive.com/pricing?product=stocks

### Cost conclusion

The publicly advertised lower-bound candidate stack is $298 for one month
($199 Massive Stocks Advanced plus one $99 partner dataset), or $199 if the news
dataset is deferred. The existing Alpaca subscription adds no incremental cost.
This lower bound is **not a compliant acquisition estimate**: specialist news,
historical archive licensing, halt/status coverage, storage, and possibly a
stronger security master remain quote-dependent. A defensible total cannot be
stated until vendors answer the capability checklist. For planning only, reserve
$1,000–$10,000+ for data, storage, and quote-based archives; treat that range as
uncertain and do not purchase against it without a signed coverage matrix.

## Implemented readiness plumbing

The optional readiness-evidence ledger is schema-strict, canonical, and bound to
the frozen protocol and source-matrix identities. It requires exactly one row per
source requirement and validates:

- capability dataset/capability matching and as-of time;
- entitlement-to-capability identity and as-of time;
- discovery-only immutable manifests and as-of time;
- deterministic unique manifest ordering;
- expected-versus-observed security and session set hashes;
- independent coverage evidence hashes;
- explicit clear, conflicting, or unverified conflict state.

Missing rows, future evidence, identity drift, mismatched set hashes, missing
manifests, or unresolved conflicts fail closed. The ledger is supplied with:

```bash
PYTHONPATH=src .venv/bin/python scripts/plan_winner_archetype_discovery_v002.py \
  --readiness-evidence path/to/manifest-only-readiness-evidence.json \
  --format text
```

No sample ledger pretends that a provider, entitlement, acquisition, or coverage
proof exists. Synthetic tests exercise the interface without creating a
production-looking evidence file.

## Next milestone recommendation

Run a documentation-only vendor due-diligence milestone. Obtain written answers
and sample schemas—without acquiring historical data—for Massive (raw SIP,
reference data, corporate actions), the selected news archive, and a complete
halt/status source. Record license/retention terms and exact quotes in capability
and entitlement drafts. In parallel, implement the calendar/session-plan
publisher using synthetic tests. Do not acquire data until the capability matrix
shows that every protocol-required field and completeness proof has a source.
