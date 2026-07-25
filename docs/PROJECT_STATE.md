# Attention Momentum Lab Project State

**Audit date:** 2026-07-24

**Canonical repository:** `/Users/daddy/Downloads/attention-momentum-lab`

**Branch:** `main`

**Latest commit:** `66f78d0` (`feat: add bounded SIP engineering rehearsal`)

**Upstream state at audit:** 13 commits ahead of `origin/main`, 0 behind

> Old chat instructions and conversation summaries may be stale. Treat this
> document, the current Git history, executable code, tests, and versioned
> research documents as the source of truth.

## Purpose

Attention Momentum Lab is a private, shares-only, paper-only research system for
testing whether unusual short-term price and volume momentum can be detected
without look-ahead bias. It acquires and preserves historical bars, replays each
session chronologically, records candidates and diagnostics, simulates
conservative historical executions, evaluates deterministic batches, and can
combine fixed-allocation strategy proposals in a shared-capital portfolio. It
does not place live orders.

## Current architecture

- `src/aml/alpaca_rest.py`, `settings.py`, and `data_paths.py`: paper-account and
  historical Alpaca access, explicit SIP/IEX requests, pagination, metadata,
  and feed-qualified storage.
- `market_calendar.py`, `exchange_calendar_adapter.py`, and `market_halts.py`:
  authoritative XNYS sessions and source-attributed verified-halt handling.
- `replay.py`, `signals.py`, `thresholds.py`, `candidate_*`, and
  `trade_simulator.py`: point-in-time replay, scoring, candidate analysis, and
  single-strategy historical simulation.
- `batch_evaluation.py` and `batch_reporting.py`: deterministic manifest-driven
  batch evaluation with strict or halt-aware data-quality classification.
- `cohort_selection.py`, `research_acquisition.py`, and
  `research_reference_data.py`: preregistered V001 cohort selection,
  segmented premarket/regular acquisition, immutable provenance, and
  point-in-time reference-data validation.
- `portfolio_simulator.py` and `historical_portfolio.py`: deterministic
  shared-capital simulation and the adapter for the established attention
  strategy.
- `portfolio_artifacts.py`: deterministic, hash-verified, write-once portfolio
  run persistence and loading.
- `scripts/run_portfolio_dashboard.py`: read-only Streamlit display of persisted
  engine artifacts; it does not run or reinterpret the simulator.
- `engineering_rehearsal.py`: fixed-scope, development-only AAPL SIP rehearsal.
- The uncommitted `vendor_sample_acceptance.py` worktree addition provides a
  local quarantine gate for market/reference samples and licensing evidence.

## Current strategy version

`baseline_price_volume_momentum` version `0.1.0`, `research_only`, as defined in
`config/strategy_v001.yaml` and `docs/STRATEGY_CONSTITUTION_V001.md`. Live
trading, options, margin, and shorting remain disabled. This audit made no
strategy change.

## Milestone inventory

All requested milestones are present once in the canonical repository. No
duplicate implementation tree was found.

| Milestone | State | Primary evidence | History |
|---|---|---|---|
| Initial Alpaca/replay foundation | Committed | `alpaca_rest.py`, `replay.py`, `test_no_lookahead.py` | `7b4465d` |
| Candidate outcomes and diagnostics | Committed | `candidate_outcomes.py`, `candidate_diagnostics.py`, focused tests | `1480522`, `686f2dd` |
| Score-threshold separation | Committed | `thresholds.py`, signal/trade compatibility tests | `18e08b3` |
| SIP historical research support | Committed | feed-aware client, paths, CLI, acquisition tests | `faaf840` |
| Verified halt schedules | Committed | two GME verified-halt CSVs and `market_halts.py` | `f8eb40c` |
| Halt-aware candidate and trade completeness | Committed | candidate/outcome/simulator integrations and tests | `f8eb40c` |
| Halt-aware batch data quality | Committed | batch classification/reporting and tests | `b60bcdf` |
| Deterministic batch evaluation | Committed | V001 config, runner, engine, reports, tests | `3d9505b` |
| Research cohort V001 design | Committed | `RESEARCH_COHORT_V001_DESIGN.md` | `98d0a65` |
| Research acquisition foundation | Committed | acquisition/selection/reference modules and tests | `9ec28a4` |
| Reference-data schemas | Committed | `RESEARCH_DATA_SCHEMAS_V001.md` and validators | `9ec28a4` |
| Provider evaluation | Committed, with a small uncommitted cross-reference | `RESEARCH_PROVIDER_EVALUATION_V001.md` | `5a2b59f`, `0e864d4` |
| Deterministic multi-strategy portfolio simulator | Committed | simulator, demonstration,  tests | `9871cef` |
| Portfolio artifact persistence | Committed | artifact writer/loader and tests | `61b0c1b` |
| Streamlit research dashboard | Committed | read-only dashboard and README launch instructions | `61b0c1b` |

## Tests

The current worktree has **243 passing tests**. The focused Alpaca/acquisition,
portfolio, historical-portfolio, engineering-rehearsal, and artifact subset has
**105 passing tests**. Both counts include the current uncommitted vendor-sample
acceptance tests where applicable. Four dependency deprecation warnings from
`exchange_calendars`/pandas utilities remain; there are no test failures.

## Committed versus uncommitted work

The milestone implementation through the bounded SIP engineering rehearsal is
committed locally. Those commits have not been pushed: `main` is 13 commits
ahead of `origin/main` and 0 behind.

Pre-existing uncommitted work adds a strategy-independent vendor-sample
quarantine/acceptance gate:

- modified: `.gitignore`, `README.md`,
  `docs/RESEARCH_PROVIDER_EVALUATION_V001.md`;
- untracked: `docs/VENDOR_SAMPLE_ACCEPTANCE_V001.md`,
  `scripts/check_vendor_sample.py`, `src/aml/vendor_sample_acceptance.py`,
  `tests/test_vendor_sample_acceptance.py`, and the templates under
  `examples/vendor_sample_acceptance/`;
- created by this audit and still untracked: `docs/PROJECT_STATE.md` and
  `docs/DECISION_LOG.md`.

No stash, submodule, second worktree, or additional local branch was found.

## Repository hygiene

- `.env` is ignored and untracked; only `.env.example` is tracked, and no
  tracked secret/API-key/private-key pattern was found.
- Research downloads under `data/research/`, generated outputs under
  `artifacts/`, logs, caches, the virtual environment, and the uncommitted
  `quarantine/` path are ignored. Important source, tests, configs, research
  designs, schemas, and vendor templates are not ignored.
- No unresolved merge-conflict marker or abandoned `.tmp`, `.temp`, `.orig`,
  `.rej`, or editor-backup file was found.
- Two ignored macOS metadata files exist at `artifacts/AAPL/.DS_Store` and
  `artifacts/GME/.DS_Store`; they were not deleted during this audit.
- One packaging hygiene exception predates this audit: five generated files in
  `src/attention_momentum_lab.egg-info/` are tracked and the directory is not
  ignored. Removing them or changing ignore rules was outside this audit's
  requested documentation-only changes.

## Known development-only results

Ignored local artifacts contain three persisted portfolio runs. They are not
validation or profitability evidence:

- development run `0dee4741950a870961b1`: $2,000 starting capital, one trade,
  ending equity $1,990.537902537182;
- engineering-rehearsal development run `9b0bf1974e703cec5950`: $2,000 starting
  capital, zero trades, ending equity $2,000;
- synthetic run `a7506bbba395170da159`: $3,000 starting capital, two accepted
  proposals and one rejection, ending equity $3,015.299082.

The local AAPL/GME May 2024 artifacts and batches are also development or
pipeline-feasibility outputs. None belongs to the untouched V001 validation
cohort.

## Validation boundary

Validated now:

- deterministic point-in-time, acquisition, completeness, batch, portfolio,
  and artifact behavior covered by the passing test suite;
- Alpaca paper authentication (`ACTIVE`) on 2026-07-24;
- entitlement for one explicit, bounded SIP request: AAPL, 2026-07-15,
  04:00-04:05 ET, returning six provider bars;
- one-page live metadata and deterministic multi-page token-following/error
  behavior in tests;
- V001 requests implement premarket `[04:00, 09:25)` and authoritative XNYS
  regular-session boundaries.

Not validated:

- strategy profitability, predictive value, out-of-sample performance, or live
  execution;
- the untouched Research Cohort V001;
- point-in-time production universe, security type, listings/delistings, symbol
  continuity, or bounded negative corporate-action coverage;
- vendor contractual rights for raw retention, derived works, subscriber
  display, redistribution, cloud use, or post-termination reproducibility;
- live multi-page pagination in the tiny smoke sample (it was one page);
- provider-independent confirmation that returned bars were SIP, because Alpaca
  accepted the explicit `feed=sip` request but did not echo a feed field.

## Providers and current entitlements

- **Alpaca paper/trading API:** configured and paper authentication succeeds.
- **Alpaca historical market data:** the general `.env` feed is `iex`; historical
  research defaults explicitly to `sip`. The upgraded account successfully
  retrieved the bounded SIP premarket sample. Credentials are stored only in an
  ignored local `.env` and were not printed.
- **Massive:** evaluated as the leading market-data procurement candidate; no
  approved contract, sample acceptance, or production entitlement is recorded.
- **EDI:** evaluated for point-in-time reference/listing/action data; no approved
  contract, sample acceptance, or production entitlement is recorded.
- Other providers in the evaluation remain fallbacks or are disqualified for
  the documented V001 requirements.

## Unresolved provider and reference-data requirements

Production research still requires point-in-time common-stock universe and
security-type evidence, listings/delistings, stable identifiers and symbol
history, corporate actions including explicit no-action coverage, publication
and correction timestamps, consolidated SIP provenance, immutable vintages,
complete delivery/pagination evidence, and written licensing for storage,
backups, processing, derived works, subscriber display, fees, and retention.

## Current blockers

1. The contracting entity, intended users/infrastructure, subscriber output
   forms, and retention requirement have not been fixed for vendor outreach.
2. Representative Massive/EDI samples and written field-level/licensing
   evidence have not passed the local acceptance criteria.
3. The point-in-time reference-data and commercial licensing gates prevent the
   21-session pilot and broad production acquisition from being authorized.
4. The vendor-sample acceptance implementation and this audit documentation are
   uncommitted and require review as one coherent worktree change.
5. Tracked `src/attention_momentum_lab.egg-info/` packaging metadata and two
   ignored `.DS_Store` files remain repository-hygiene cleanup candidates.

## Next three approved tasks

These are the next repository-defined steps in order; this document does not
authorize broad acquisition or strategy tuning:

1. Review this audit and the existing uncommitted vendor-sample acceptance gate,
   then decide the exact commit/push scope.
2. Resolve the user-owned contracting, infrastructure, subscriber-display, and
   retention decisions; request legally permitted bounded samples and written
   rights evidence from Massive and EDI.
3. Run the strategy-independent sample acceptance checks. Only after technical
   and licensing approval, acquire the predefined 21-session pilot, freeze the
   first 09:25 audit, and stop for review before any production expansion.

## Commands

Install and launch the read-only dashboard:

```bash
.venv/bin/python -m pip install -e '.[dashboard]'
.venv/bin/streamlit run scripts/run_portfolio_dashboard.py -- \
  --artifact-root artifacts/portfolio
```

Run focused tests:

```bash
.venv/bin/python -m pytest -q \
  tests/test_historical_acquisition.py \
  tests/test_research_acquisition.py \
  tests/test_engineering_rehearsal.py \
  tests/test_portfolio_simulator.py \
  tests/test_historical_portfolio.py \
  tests/test_portfolio_artifacts.py
```

Run the full suite and lint:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts
git diff --check
```
