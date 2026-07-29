# Historical Catalyst Ingestion V0.1

## Scope and isolation

This framework performs bounded, deterministic ingestion of local synthetic
JSON and JSONL catalyst records into external immutable research storage. It is
provider-neutral at its core and includes one local-file provider. It has no
HTTP client, live provider, credential integration, Alpaca adapter, SEC
adapter, scraper, cloud-storage adapter, or extension-period acquisition path.

Historical ingestion is not strategy or market-data replay. The terms used in
this document are ingestion, deterministic reprocessing, repeated ingestion,
batch reproduction, and recovery. Strategy V0.1.1, forward validation, the
operator, simulation, scoring, sizing, risk, execution, and P&L do not import or
invoke this framework.

Only explicitly synthetic input is accepted by this version. A licensed real
dataset must not be ingested until the source-specific adapter, license,
retention rules, timestamp semantics, and acceptance tests have been separately
reviewed.

## Versioned contracts

This implementation adds the following research contracts without weakening
the existing `aml.catalyst.raw.v001` or `aml.catalyst.observation.v001`
contracts:

- `aml.catalyst.historical-input.v001`
- `aml.catalyst.raw.v002`
- `aml.catalyst.observation.v002`
- `aml.catalyst.cluster.v002`
- `aml.catalyst.source-batch.v001`
- `aml.catalyst.ingestion-audit.v001`
- `aml.catalyst.ingestion-manifest.v001`

Every published artifact carries provider, source, timing, normalization, and
validation provenance. Aggregate artifacts carry sorted provider, source,
retrieval-time, and normalization-version collections where one scalar would
be misleading.

## Provider and processing interfaces

`HistoricalCatalystProvider` reads bounded source records and returns logical
records plus byte-envelope metadata. It does not normalize, cluster, publish,
or call a network. `HistoricalNormalizer` converts a validated raw record to a
versioned observation. `CatalystDeduplicator` returns a deterministic,
conservative cluster key. New providers can implement these interfaces without
changing the orchestration contract.

The only included provider is `LocalHistoricalFileProvider`. It accepts
absolute, regular, non-symlink `.json` and `.jsonl` paths. Provider names and
versions must be safe partition identifiers; path-like values are rejected.

## Input envelope

Each local logical input record has exactly these fields:

```text
schema_version
source_identifier
retrieval_timestamp
provider_release
revision_of_raw_id
payload
synthetic
```

Unknown or missing fields fail. `synthetic` must be exactly `true`. The payload
has an exact observational schema; it cannot contain strategy outcomes, P&L,
future returns, credentials, or unknown fields.

## Exact source bytes and logical identity

JSONL preserves the exact bytes of each line, including its line ending where
present. A single-object JSON file preserves the exact full-file bytes as its
record envelope. The raw artifact records:

- exact bytes encoded as bounded Base64;
- exact byte length;
- SHA-256 of the exact record bytes;
- SHA-256 and byte length of the complete source file;
- the strict UTF-8 decoded and parsed logical payload;
- SHA-256 of canonical logical JSON.

These hashes have different meanings. Canonical logical equality never implies
source-byte equality.

A JSON array does not provide a naturally separable original byte envelope for
each element. Array records therefore store no invented per-record source
bytes. They retain the bounded complete source-file hash and length, the array
index, canonical logical record identity, and an explicit
`json_array_byte_envelope_limitation` flag. Byte-for-byte per-element evidence
requires JSONL or single-object JSON.

Arbitrary binary input is unsupported. Input is never silently truncated.

## Deterministic identity

The raw identity binds schema, provider and provider version, provider release,
stable source identifier, retrieval timestamp, source-file identity, record
format and byte-envelope semantics, byte lengths, record index, exact
record-byte hash where available, logical-payload hash,
normalizer version, and explicit correction predecessor.

Observation identity binds raw identity, normalizer version, and normalized
security symbol. Its separate normalized-record hash covers every normalized
field. Cluster identity covers its security identity, event date, exact
members, providers, sources, retrieval timestamps, normalizer versions,
deduplicator version, and stated basis.

The run ID binds bounded source identities, configuration, explicit `--as-of`,
all schema and component versions, limits, and every planned artifact hash. It
does not include wall-clock time, process ID, random values, temporary names,
filesystem enumeration order, or absolute paths. Operational execution times
are not substituted for missing historical timestamps.

## Ingestion lifecycle

The deterministic pipeline is:

1. Bounded source discovery.
2. Byte-level validation.
3. Strict UTF-8 decode and strict JSON parsing.
4. Provenance validation.
5. Raw identity construction.
6. Versioned normalization.
7. Temporal validation.
8. Correction-lineage validation.
9. Conservative duplicate clustering.
10. Published-registry and destination-collision preflight.
11. Complete deterministic write-plan construction.
12. Dry-run reporting or raw publication.
13. Normalized-observation publication.
14. Cluster, source, and parser-audit publication.
15. Final manifest publication.

Every artifact is created atomically and write-once. The final manifest is the
sole publication boundary. Files present without a valid manifest are
unpublished evidence and cannot be treated as an ingested dataset.
New directory entries, completed artifact files, and their containing
directories are fsynced so the recovery boundary does not rely only on buffered
writes.

## Validation stages

The reader requires explicit positive limits for total source bytes, per-record
bytes, record count, nesting depth, string length, headline length, summary
length, and source-file count. It rejects UTF-8 BOMs, invalid UTF-8, lone
surrogates, disallowed control characters, duplicate object keys, non-finite
numbers, malformed JSON, excessive nesting, oversized values, and unsupported
file types.

Schema validation rejects unknown fields, unsupported versions, missing
provenance, unsafe provider identifiers, malformed hashes, non-boolean Boolean
fields, silent numeric coercion, credentials, outcome fields, and non-synthetic
records.

Temporal validation requires an explicit timezone-aware `--as-of`. Retrieval
cannot exceed `--as-of`; publication cannot exceed retrieval; first seen cannot
precede publication or exceed retrieval. Effective-event time is nullable, but
its origin must explicitly be `provider-reported`, `source-derived`, or
`unknown`. A missing timestamp is never inferred from a later observation or
the ingestion execution clock.

## Correction lineage

Corrections never overwrite prior evidence. A correction must explicitly name
its predecessor raw ID. The predecessor must have the same provider and stable
provider source identifier, a different logical payload hash, and an earlier
retrieval timestamp. It must be the sole unambiguous predecessor, and the graph
must remain acyclic.

Symbol, headline, URL, approximate timing, or text similarity never creates a
revision link. Missing or competing predecessor evidence fails with an
ambiguity error rather than selecting a likely record.

## Deduplication

The initial deduplicator is intentionally conservative. It clusters only exact
matches on stable security identity, event date, headline, and normalized
summary. It does not use embeddings, fuzzy matching, external models, web
lookups, or generated sentiment.

Deduplication never removes raw records or observations. It assigns cluster
membership only and cannot cross security identities or event dates.

## Dry-run and validation

`validate`, `dry-run`, and `plan` execute the full bounded reader,
normalization, temporal checks, lineage checks, clustering, published-registry
scan, collision preflight, and deterministic plan construction. They create no
file, directory, permission change, registry mutation, or network request.
The CLI disables project bytecode-cache creation before importing ingestion
modules, so a dry run does not create `__pycache__` files.

Example, with an already-created private external root:

```bash
PYTHONPATH=src .venv/bin/python scripts/ingest_historical_catalysts.py dry-run \
  --provider synthetic-local \
  --provider-version provider-v001 \
  --source /private/research-input/synthetic_batch.jsonl \
  --destination-root /private/research-registry \
  --as-of 2024-12-31T23:59:59+00:00 \
  --normalizer-version historical-synthetic-normalizer-v001 \
  --deduplicator-version exact-observational-content-v001 \
  --max-total-source-bytes 200000 \
  --max-record-bytes 50000 \
  --max-records 20 \
  --max-nesting-depth 10 \
  --max-string-length 10000 \
  --max-headline-length 1000 \
  --max-summary-length 5000 \
  --max-source-files 10
```

Use `publish` with the same explicit arguments only after reviewing the plan.
There is no default destination inside the repository.

## Failure and recovery

A validation failure publishes nothing. If execution stops during publication,
already-created evidence is retained and the batch remains unpublished because
its manifest is absent. A normal rerun detects the partial batch and fails with
an instruction to use explicit recovery.

`status --destination-root <root> --run-id <id>` reports absent, unpublished
incomplete, or published state. It never changes storage.

`recover` reconstructs the plan from the same bounded inputs and configuration.
Every existing partial file must match the planned canonical bytes exactly.
Matching files are retained; missing files may be atomically created. Any
mismatch or unexpected crash-leftover file stops recovery. Recovery never
deletes, overwrites, truncates, or silently quarantines evidence. The manifest
is written only after every planned artifact exists and verifies byte-for-byte.
Repeating explicit recovery after successful publication verifies the identical
manifest and artifacts and returns without rewriting them.

If the original deterministic inputs are unavailable or a partial artifact
differs, the incomplete batch must remain unpublished for manual review. A
future quarantine tool may add an external status marker, but it must not move
or mutate preserved evidence silently.

## Immutability and provenance guarantees

- Published artifacts are content-addressed and write-once.
- Corrections create new raw and observation identities.
- Original source bytes are distinct from canonical logical content.
- Absolute local paths never enter identities or manifests.
- Only manifests authorize readers to treat a batch as published.
- Every manifest hashes every artifact it references.
- Published registry scans verify referenced bytes before accepting lineage.
- Repeated ingestion with identical inputs and configuration yields the same
  run ID and plan, then fails as an already-published collision.

## Remaining decisions before licensed data

Before any licensed historical dataset is used, the project must decide and
document source licensing, redistribution, retention, correction semantics,
stable identifier guarantees, timestamp definitions, source-file byte-envelope
capabilities, permitted symbols and dates, and provider-specific acceptance
fixtures. A provider adapter must remain network-free for local ingestion and
receive its own bounded failure tests. None of those decisions may be inferred
from research outcomes.
