# Attention Momentum Lab Project State

**Audit date:** 2026-07-25

**Repository role:** isolated recovery branch based on canonical `main`

**Branch:** `recovery/tournament-v011`

**History:** canonical `8c3cebb`, recovered through merge `29be99c`; all five
original recovered commits remain ancestors

**Publication state:** local only; this recovery branch has not been pushed

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
- `vendor_sample_acceptance.py` provides a local quarantine gate for
  market/reference samples and licensing evidence.

## Current strategy version

The tournament production-candidate is frozen `attention_momentum` V0.1.1. Its
corrected development/validation baseline is run `564345a77176524eb250`:
development 120 trades and -$371.955421; validation 94 trades and +$61.145100.
The validation result is period-concentrated and statistically inconclusive.
The +3.057255% figure uses a resetting $2,000 reference allocation per replay
unit and is not a continuously deployable portfolio return.

No optimization is authorized. The next step is the preregistered untouched
validation extension in `STRATEGY_V011_VALIDATION_EXTENSION_V001.md`. New
context fields are observational only, shadow strategies receive no capital,
retrospective winner/loser symbol selection is prohibited, and the sealed
holdout remains untouched. The earlier `baseline_price_volume_momentum` V0.1.0
configuration remains legacy research context; it is not a replacement version
for frozen tournament Strategy V0.1.1.

Completed tournament artifacts are immutable. Derived analyses now use a
separate hash-verified analysis directory and fail closed on source mutation.
The corrected baseline's audit and diagnostic CSVs were previously rewritten
after finalization; that mismatch is documented and is not retroactively
repaired.

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
| Provider evaluation | Committed | `RESEARCH_PROVIDER_EVALUATION_V001.md` | `5a2b59f`, `0e864d4` |
| Deterministic multi-strategy portfolio simulator | Committed | simulator, demonstration,  tests | `9871cef` |
| Portfolio artifact persistence | Committed | artifact writer/loader and tests | `61b0c1b` |
| Streamlit research dashboard | Committed | read-only dashboard and README launch instructions | `61b0c1b` |

## Tests

Recovery verification covers acquisition, manifests, tournament behavior,
immutable analysis, prospective-boundary controls, observational shadow
context, and the complete suite. Exact counts belong in the recovery report and
CI output so this state document does not become stale. Dependency deprecation
warnings from `exchange_calendars`/NumPy utilities remain non-failing.

## Recovered and subsequent work

The recovery merge preserves canonical history and the five original recovered
commits without squashing or replacement hashes. Immutable tournament-analysis
publishing, prospective validation-extension controls, observational shadow
context, and this documentation reconciliation are separate local commits.
Nothing in this recovery has been pushed.

## Repository hygiene

- `.env` is ignored and untracked; only `.env.example` is tracked, and no
  tracked secret/API-key/private-key pattern was found.
- Research downloads under `data/research/`, generated outputs under
  `artifacts/`, logs, caches, the virtual environment, and the local
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

## Result-access boundary

No ignored market data, generated tournament output, validation-extension
result, or sealed-holdout material was copied into or accessed during recovery.
The deterministic shadow rehearsal is synthetic and segregates all shadow P&L
from deployed-strategy accounting.

## Validation boundary

The frozen V0.1.1 extension is prospectively preregistered for the inclusive
calendar interval 2026-07-27 through 2028-07-26. July 27 is the first eligible
XNYS session strictly after the immutable preregistration commit. The 731-day
inclusive duration is unchanged from the earlier draft; the boundary was not
selected from results. Acquisition and replay remain unauthorized by the
preregistration document.

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
4. Tracked `src/attention_momentum_lab.egg-info/` packaging metadata and two
   ignored `.DS_Store` files remain repository-hygiene cleanup candidates.

## Next three approved tasks

These are the next repository-defined steps in order; this document does not
authorize broad acquisition or strategy tuning:

1. Review the local recovery history and verification report before deciding
   whether to promote or push it.
2. Resolve the user-owned contracting, infrastructure, subscriber-display, and
   retention decisions; request legally permitted bounded samples and written
   rights evidence from Massive and EDI.
3. Keep V0.1.1 frozen. Any future extension acquisition requires separate
   authorization and must preserve the prospective boundary; the sealed
   holdout remains inaccessible.

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
