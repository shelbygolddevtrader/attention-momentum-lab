# Strategy V0.1.1 forward-validation runbook

Status: **operations prepared; no extension acquisition or replay performed**.

This runbook operationalizes the preregistered extension in
`STRATEGY_V011_VALIDATION_EXTENSION_V001.md`. The immutable source baseline is
tag `v0.1.1-research-baseline`, commit
`378317dba28d93792d2f0a3ab4302a5d0b6abf7c`. The extension is the inclusive
calendar interval **2026-07-27 through 2028-07-26**. Strategy V0.1.1 remains
frozen. This procedure does not authorize holdout access, live trading,
optimization, replay, outcome analysis, or early unsealing.

## Prerequisites

- A clean checkout whose `HEAD` descends from the immutable baseline tag.
- Python 3.11 or newer and the repository environment installed from
  `pyproject.toml`.
- `exchange_calendars==4.13.2`, which supplies the authoritative left-labeled
  XNYS schedule and official early closes.
- An Alpaca plan entitled to historical SIP one-minute stock bars. The expected
  plan is the user-reported Algo Trader Plus plan at $99/month; entitlement is
  established only by successful authenticated requests, not by configuration.
- Enough writable local storage for write-once raw responses, normalized bars,
  metadata, failure archives, and sealed operational logs.
- Point-in-time listing, symbol-history, corporate-action, and verified-halt
  records must be obtained and validated separately before replay. A missing or
  stale record rejects the affected symbol-session; absence is never inferred
  to mean “no action” or “no halt.”

Create the environment once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]' 'ruff==0.6.9'
```

Export these variables in the operator shell. Never paste their values into a
command, log, issue, pull request, or manifest:

```bash
export ALPACA_API_KEY='...'
export ALPACA_SECRET_KEY='...'
export ALPACA_HISTORICAL_DATA_FEED='sip'
```

The preflight reports only whether credential variables are present. It never
prints their contents and never opens a network connection.

## Deterministic storage

Market data is isolated under:

```text
data/research/alpaca-sip-v011-forward-validation-2026-07-27_to_2028-07-26-v001/
```

Each symbol/date has independent `raw/`, `processed/`, and `metadata/`
partitions. Successful partitions are write-once and hash-verified. Operational
request manifests and append-only audit records are sealed under:

```text
artifacts/forward_validation/sealed/<request_id>/
  acquisition_request.json
  acquisition_audit.jsonl
```

The request ID is the first 24 hexadecimal characters of the SHA-256 of the
canonical request identity. That identity includes the baseline, source commit,
frozen strategy version, date range, SIP feed, dataset vintage, universe hash,
and explicit denial of replay, analysis, and holdout access. These generated
directories are ignored by Git and must be retained in protected research
storage with their hashes; they are not GitHub artifacts.

## Daily operating sequence

Operate only after the requested XNYS session is complete. Substitute one
completed session date for `YYYY-MM-DD`; never choose or omit a date based on an
outcome.

1. Confirm the checkout is clean and current. Run the network-free preflight:

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/run_v011_forward_validation.py \
     --start YYYY-MM-DD \
     --end YYYY-MM-DD
   ```

   Preflight verifies credentials by presence only, SIP selection, Python
   dependencies, repository cleanliness and baseline ancestry, exact frozen
   universe, XNYS sessions, writable paths, and all existing partition hashes.
   It makes zero provider requests and writes no data or artifacts.

2. Review the structural plan. Then repeat the exact command with the sole live
   authorization flag:

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/run_v011_forward_validation.py \
     --start YYYY-MM-DD \
     --end YYYY-MM-DD \
     --execute-acquisition
   ```

   This acquires SIP bars only. It never invokes a replay, emits performance
   metrics, or creates human-readable outcome tables.

3. Retain the raw response, normalized CSV, acquisition metadata, request
   manifest, and audit log. Copy them to access-controlled research storage
   without changing their bytes. Record external storage hashes in the operator
   log.

4. If interrupted, rerun the same preflight and live command. Complete
   hash-valid segments are skipped. Partial or inconsistent output fails closed.
   A recorded failed attempt is not retried automatically. After reviewing its
   cause, authorize preservation and retry explicitly:

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/run_v011_forward_validation.py \
     --start YYYY-MM-DD \
     --end YYYY-MM-DD \
     --retry-failures \
     --execute-acquisition
   ```

   The prior failure files move into a numbered `failed_attempts/` archive; no
   finalized successful partition is overwritten.

## Structural validation, replay, and publication are separate

Acquisition normalizes each response and fails on malformed timestamps,
duplicate timestamps, invalid OHLCV, symbol/feed mismatch, cross-date bars, or
unsafe regular-session boundaries. Missing minutes remain missing. Verified
halts are applied only later from source-attributed halt records; ordinary gaps
are never relabeled as halts.

After the full preregistered interval is complete, a second operator should run
the existing offline dataset-manifest validator over the exact frozen bounds and
universe. Before doing so, create a separately approved, empty sealed output
destination; `scripts/build_dataset_manifest.py` must never be pointed at an
existing manifest because its general-purpose writer is replace-capable. The
validator checks every partition, file hash, row count, feed identity, date
coverage, and universe coverage without replaying the strategy. Its invocation
must be recorded prospectively in the evaluation protocol.

The future structural-validation command is below. It is deliberately not run
until 2028-07-26 is complete, every scheduled partition has been acquired, and
an operator has exclusively reserved the new output path:

```bash
test ! -e artifacts/forward_validation/sealed/full-window-dataset-manifest.json
PYTHONPATH=src .venv/bin/python scripts/build_dataset_manifest.py \
  --dataset-vintage alpaca-sip-v011-forward-validation-2026-07-27_to_2028-07-26-v001 \
  --universe config/liquid_day_trading_universe_v001.csv \
  --start 2026-07-27 \
  --end 2028-07-26 \
  --source-commit "$(git rev-parse HEAD)" \
  --output artifacts/forward_validation/sealed/full-window-dataset-manifest.json
```

If that destination exists, stop; do not run the validator against it. Hash and
retain the new manifest immediately after successful validation.

Strategy replay is a later, separately authorized command. It must consume only
the finalized structural manifest and validated point-in-time reference data.
Replay output remains sealed until the designated evaluation point. Analysis
and publication occur only after the preregistered block or an authorized fixed
checkpoint, under the preregistered descriptive rules. The acquisition wrapper
has no replay or analysis option, and rejects command tokens attempting to add
one.

## Fail-closed conditions

Stop without acquisition if any of these occurs:

- a date is before 2026-07-27, after 2028-07-26, reversed, or not an XNYS session;
- `HEAD` is dirty, the baseline tag moved, or the baseline is not an ancestor;
- the feed is not SIP, credentials are absent, or a dependency is missing;
- the ordered universe differs from the 23 preregistered symbols;
- any path traverses, uses a symlink, names a holdout compartment, enters a
  tournament/finalized artifact directory, or is not writable;
- an existing partition is partial, inconsistent, malformed, or fails a hash;
- a sealed request manifest differs, or its directory contains an unexpected
  report/result file;
- point-in-time reference data is unavailable, stale, conflicting, or malformed.

## Operators must never

- modify V0.1.1 logic or the preregistered dates/universe;
- use IEX in place of SIP, fill missing minutes, infer halts, or silently repair
  historical files;
- overwrite raw data, metadata, manifests, reports, finalized artifacts, or the
  immutable tag;
- combine acquisition with replay, analysis, optimization, or publication;
- print credentials or store them in manifests;
- inspect extension outcomes before authorization, shorten the block because of
  outcomes, or access any sealed-holdout path;
- schedule live acquisition in GitHub Actions, cron, or another unattended job;
- commit generated market data, operational logs, manifests, or results.

The future manual decision is when the research owner designates the evaluation
point and separately authorizes structural-manifest publication, replay, and
descriptive analysis. Nothing in this runbook grants that authorization.
