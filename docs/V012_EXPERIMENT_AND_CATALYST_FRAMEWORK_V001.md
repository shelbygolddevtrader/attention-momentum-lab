# V0.1.2 Experiment Registry and Catalyst Observation Framework

## Research boundary

Strategy V0.1.1 remains frozen at baseline commit
`378317dba28d93792d2f0a3ab4302a5d0b6abf7c`. This framework is a separate,
research-only V0.1.2 layer. It does not change candidates, signals, execution,
sizing, risk, exits, simulation, or P&L. Catalyst modules are not imported by
V0.1.1 execution or forward-validation acquisition.

This version has no experiment-evaluation command. Forward-validation outcomes,
validation-extension data, and holdout data are prohibited inputs to registry
commands and the initial draft experiments.

## Experiment lifecycle

The versioned experiment schema is `aml.experiment.v001`. Supported states are:

`draft -> preregistered -> collecting -> sealed -> evaluated -> promoted|rejected`

Draft, preregistered, and collecting experiments may instead become abandoned
where the transition table allows. Invalid transitions fail closed.

Every specification has an exact field set. Missing and unknown fields,
timezone-naive timestamps, malformed metrics, invalid baselines, and dataset
permissions that expose forward outcomes are rejected. Experiment IDs must be
unique within a registry.

Preregistration computes a canonical SHA-256 hash over all research-defining
fields. Lifecycle status and the hash field itself are excluded. After
preregistration, validation recomputes that hash; changing the hypothesis,
features, population, metrics, thresholds, sample size, criteria, datasets, or
limitations invalidates the specification. Operational notes belong in a
separate append-only `.notes.jsonl` file and never change the preregistration
hash.

The three supplied proposals are drafts. Their sample sizes, thresholds,
promotion criteria, rejection criteria, and stop conditions remain explicitly
unresolved. They cannot be preregistered until those decisions are prospectively
resolved.

## Registry CLI

The CLI is `scripts/manage_experiments.py` and supports `create-draft`,
`validate`, `preregister`, `list`, `show`, `transition`, `hash`, and
`append-note`. Operational notes use a separate append-only hash chain. It has no
evaluate, replay, outcome, or promotion-selection command.

Examples:

```bash
PYTHONPATH=src .venv/bin/python scripts/manage_experiments.py list
PYTHONPATH=src .venv/bin/python scripts/manage_experiments.py validate v012-catalyst-presence
PYTHONPATH=src .venv/bin/python scripts/manage_experiments.py hash v012-catalyst-presence
```

## Catalyst contracts

The initial schema versions are:

- immutable raw records: `aml.catalyst.raw.v001`
- normalized observations: `aml.catalyst.observation.v001`
- duplicate-story clusters: `aml.catalyst.cluster.v001`
- source metadata: `aml.catalyst.source.v001`
- acquisition manifests: `aml.catalyst.manifest.v001`
- parser audits: `aml.catalyst.parser-audit.v001`

Raw vendor payloads are preserved before normalization. Raw hashes cover the
canonical payload. Normalized observation IDs cover the complete normalized
record except the ID itself. Cluster IDs similarly cover their sorted members,
creation time, basis, and parser identity.

Publication time is the source's asserted publication time. First-seen time is
when the collector first observed the record. Effective-event time is optional
and describes when the underlying event applies. Acquisition time records when
the raw record was preserved. These timestamps are not interchangeable and must
be timezone-aware. Normalized records require publication <= first seen <=
acquisition.

Direction is an observational label: positive, negative, mixed, neutral, or
unknown. It is not a model-generated sentiment score and is not an input to
Strategy V0.1.1.

## Duplicate stories

Normalized observations carry a stable duplicate-story cluster ID. Clustering
must be based only on information available to the parser at that time. Cluster
members are sorted and unique, and the cluster identity is deterministic.
Future research must avoid treating syndicated copies as independent evidence.

## External storage

Runtime data must live outside the repository in an explicitly configured,
current-user-owned directory with permissions no broader than `0700`. Traversal,
symlink components, repository-internal roots, unsafe permissions, overwrite,
and writes beneath finalized partitions fail closed.

The deterministic layout is:

```text
raw/<vendor>/<acquisition-date>/<raw-hash>.json
normalized/<publication-date>/<symbol>/<observation-id>.json
clusters/<creation-date>/<cluster-id>.json
sources/<source-id>/<metadata-version>.json
manifests/<vendor>/<acquisition-date>/<manifest-id>.json
parser-audit/<parser-version>/<parse-date>/<audit-id>.json
```

Records use canonical JSON. Credentials and forward-outcome fields are rejected.
Repository fixtures are synthetic and explicitly marked `synthetic: true`.

## Sources and licensing

Every future source needs separate metadata identifying its type, license,
license URL, redistribution permission, retention policy, review timestamp, and
metadata version. A technically accessible source is not automatically licensed
for collection, retention, normalization, or redistribution.

## Future adapters

Future Alpaca News, SEC EDGAR, investor-relations, or licensed-vendor adapters
must implement the collector protocol without changing the normalized contract.
They must preserve raw records first, distinguish all four timestamps, identify
the vendor release, carry source licensing metadata, and receive dedicated
network-isolated tests. No live adapter is included here.

## Why generic sentiment is excluded

Generic sentiment compresses source credibility, novelty, materiality,
company-specificity, timing, and ambiguity into a score whose point-in-time
behavior is not yet validated. Adding such a score now would create leakage and
interpretability risks. V0.1.2 therefore records transparent observational
fields only, makes no performance claim, and leaves Strategy V0.1.1 unchanged.
