# Research Data Schemas V001

These schemas support `RESEARCH_COHORT_V001_DESIGN.md`. They are acquisition
contracts, not substitutes for an authoritative point-in-time provider.
Missing files, missing columns, stale `known_at_timestamp` values, uncovered
dates, and ambiguous symbol mappings fail closed.
The local adapter also requires an explicit set of approved source identifiers;
non-empty source text alone is not treated as proof that a provider is trusted.

## Segmented market data

Each symbol/date/feed/vintage is stored beneath:

`data/research/{vintage}/{feed}/{symbol}/{date}/`

The `premarket` and `regular` segments have separate raw provider responses,
processed CSVs, and acquisition metadata. Premarket is exactly 04:00 inclusive
through 09:25 exclusive, America/New_York. Regular observations are restricted
to the authoritative XNYS left-labeled minute index. Missing minutes remain
absent; they are never filled.

Metadata records the provider, requested and actual feed, timestamps, calendar,
timezone assumptions, dataset vintage, pagination, retries/failure status,
normalization findings, counts, paths, and SHA-256 hashes. The client sends the
requested Alpaca feed as an explicit request parameter. When the response does
not echo a feed field, `actual_feed` remains null and
`actual_feed_evidence` records that limitation; the request is not mislabeled as
independent provider confirmation. Every parsed provider page is retained in
the raw response. Files are write-once within a vintage, published atomically,
and hashed only after their final bytes have been published. Acquisition
metadata is the final success marker.

Frozen dataset builds have a tracked JSON manifest beneath `manifests/`. The
manifest records the published downloader commit, exact universe and coverage,
source/feed evidence, acquisition timestamps, row totals, validation results,
and one path-independent SHA-256 partition fingerprint per symbol. A partition
fingerprint commits to the relative path, actual SHA-256, byte count, and CSV
row count of every raw, processed, and acquisition-metadata file. Regeneration
rehashes the local files and fails closed before replacing the manifest.

Deterministic IEX-versus-SIP comparisons are stored beneath
`artifacts/feed_comparisons/{vintage}/{symbol}/{date}/{comparison_id}/`.
`ohlcv_differences.csv` has fixed column order and `comparison.json` is written
last as the completion marker. The comparison identity includes the requested
feed pair, quality-policy fingerprint, input hashes, symbol, date, and
completeness mode. Loading rejects incomplete directories and hash changes.

Large provider data beneath `data/research/` is intentionally ignored by Git
and must be preserved in the governed research-data store. Frozen daily
selection audits use the versionable canonical path:

`data/selection_audits/{cohort_id}/{YYYY-MM-DD}.csv`

Those audit records and their metadata sidecars are not ignored by the
repository. They are deterministic, outcome-free, and write-once. The
`selection_timestamp` remains the historical 09:25 ET cutoff; `frozen_at` is
the actual time the backfill artifact was generated and must not be backdated
to resemble a contemporaneous historical run. Outcome evaluation must consume
the already-frozen artifact.

## Point-in-time universe snapshot

One file per selection date:

`universe/{YYYY-MM-DD}.csv`

Required columns:

`as_of_timestamp,symbol,security_type,exchange,calendar_id,active,source,dataset_vintage`

The record must have been known by the 09:25 selection timestamp. Present-day
membership is not an allowed fallback. Its local `as_of_timestamp` date must
equal the selection date, and source and vintage provenance must be non-empty.

## Listing and delisting history

`listings.csv`

Required columns:

`symbol,listing_start_timestamp,listing_end_timestamp,exchange,calendar_id,known_at_timestamp,source,dataset_vintage`

An empty end timestamp means the listing remained active through the provider's
documented coverage, not that current listing status may be projected backward.
Listing lookup uses the historical ticker established by symbol continuity.

## Corporate actions

`corporate_actions.csv`

Required columns:

`symbol,record_type,coverage_start_timestamp,coverage_end_timestamp,effective_timestamp,action_type,adjustment_factor,known_at_timestamp,source,dataset_vintage`

`record_type` is `action` or `verified_none`. A `verified_none` row is required
to prove coverage when no action exists; absence of a row is missing data. It
must include coverage bounds, the time the absence was known, source, and
vintage. A `verified_none` row cannot also describe an effective action. Action
rows require an effective timestamp, action type, and positive adjustment
factor.

## Symbol continuity

`symbol_continuity.csv`

Required columns:

`canonical_symbol,historical_symbol,effective_start_timestamp,effective_end_timestamp,known_at_timestamp,source,dataset_vintage`

Exactly one mapping must cover a symbol at the selection timestamp. Effective
intervals must be valid and the mapping must have non-empty source and vintage
provenance.

## Warm-up inventory

Required columns:

`symbol,trading_date,premarket_status,regular_status,adjustment_status,reference_status`

All 20 registered prior sessions are required. Premarket status may be
`complete` or `verified_no_trades`; unavailable data is never converted to zero.

## Provider capability boundary

The repository currently supports paginated Alpaca minute-bar acquisition with
explicit SIP feed requests. It does not currently have an approved provider for
historical point-in-time universe membership, listing/delisting history,
corporate actions, or symbol continuity. The local adapter validates supplied
files but does not fabricate them. Provider licensing, retention, and
redistribution rights remain external requirements to verify before production
collection; this document does not assert those rights.
