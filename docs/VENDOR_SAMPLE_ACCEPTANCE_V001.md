# Vendor Sample Acceptance V001

**Status:** procurement quarantine gate; strategy-independent

This checker evaluates local vendor samples before any source data can enter
canonical research storage. It never contacts a vendor, loads credentials,
copies sample data into `data/research/`, or evaluates strategy outcomes.

Acceptance requires two independent passes:

1. the selected technical profile; and
2. an executed or written licensing-evidence manifest.

Marketing pages and unresolved answers never grant permission. A technically
valid sample remains rejected until licensing passes.

## Quarantine layout

Place each vendor delivery in its own non-canonical directory. Copy the files
from `examples/vendor_sample_acceptance/` as starting schemas, replace every
placeholder, and calculate SHA-256 over finalized sample bytes. Input paths in a
manifest must be relative, contained beside that manifest, and cannot be
symlinks. Repository-local `quarantine/` is ignored by Git so vendor samples and
contract references cannot be staged accidentally; it is not canonical storage.

Reports default to:

`artifacts/vendor_sample_acceptance/{profile}/{run_id}/`

The directory contains deterministic `acceptance_result.json` and `report.md`.
Exit status is 0 for acceptance and 2 for rejection. Rejected source data stays
in quarantine; accepted source data is still not copied automatically.

## Massive market-data sample

Prepare a completed copy of `market_manifest.template.json`, a bars CSV, and a
completed Massive licensing manifest. Then run:

```bash
.venv/bin/python scripts/check_vendor_sample.py market_data \
  --manifest quarantine/massive/sample-001/manifest.json \
  --licensing-manifest quarantine/massive/sample-001/licensing.json
```

The checker requires explicit SIP identity, [04:00, 09:25) ET coverage,
left-labeled XNYS regular minutes, adjustment and correction semantics,
conditions documentation, exact versioned columns, complete pagination/delivery
identity, per-page and total record-count reconciliation, finalized hashes, and
immutable release/vintage identifiers. Missing observations remain visible.
Verified full-halt minutes are reported separately but are never inferred from
the vendor's gaps.

## EDI point-in-time reference sample

Prepare the four reference CSVs, a completed reference manifest, and a completed
EDI licensing manifest. Then run:

```bash
.venv/bin/python scripts/check_vendor_sample.py reference_data \
  --manifest quarantine/edi/sample-001/manifest.json \
  --licensing-manifest quarantine/edi/sample-001/licensing.json
```

The bounded universe assertion must reconcile to its exact row count. Every
security needs canonical `security_type=common_stock` plus the vendor's
historical type code/description evidence, exchange/calendar identity, a stable
identifier, uniquely active listing and ticker intervals, correction/release
provenance, canonical record order, exact stable-identifier scope, and
corporate-action coverage. Historical ticker intervals must reconcile to
listing intervals for the same stable identifier. A no-action case requires
exactly one explicit bounded `verified_none` record per security; an empty
response is never accepted. All timestamps must carry an explicit timezone.
All as-of, known-at, publication, and correction timestamps must be strictly
before the 09:25 decision cutoff.

## Licensing evidence

Every required right must be `granted` by an `executed_order_form`,
`executed_amendment`, or `written_vendor_confirmation`. Every raw,
reconstructable, download, API, and alert restriction must be explicitly
`permitted` or `prohibited`. Exchange, display, and non-display fees must be
explicitly `applicable` or `not_applicable`. Public pricing or marketing copy is
not an allowed evidence type.

This automated result is a procurement control, not legal advice. Contract
review and an explicit production-data admission decision remain separate.

## Determinism and path boundary

Manifest and CSV fields must match schema version `1.0.0` exactly; unexpected
fields fail closed rather than being silently ignored. Referenced source files
must be relative regular files contained beside the manifest. Absolute source
paths, parent traversal, and symlinked manifests, licensing files, sample files,
or report roots are rejected. Reports contain logical input identities and
SHA-256 hashes, not source paths, credentials, authorization headers, or
machine-local directory values. Repeating identical inputs produces the same
run ID and identical report bytes.
