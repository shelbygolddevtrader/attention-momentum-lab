# Attention Momentum Lab

A private, modular research system for testing whether unusual price/volume momentum can be detected without look-ahead bias.

This project connects to Alpaca paper APIs, downloads one-minute bars, replays a stock-day chronologically, calculates a transparent baseline score, logs every candidate, and produces separate price and volume charts.

It is shares-only, paper-only, and research-only. It does not submit orders.

## Historical data feeds

Historical strategy research defaults to consolidated SIP data. IEX represents
activity from one exchange, so its volume and volume-derived features can differ
materially from consolidated US-market activity. IEX remains available for
feed comparisons and explicitly IEX-based workflows.

Configure credentials and the historical default in `.env` (never commit this
file):

```dotenv
ALPACA_API_KEY=your_key_id
ALPACA_SECRET_KEY=your_secret_key
ALPACA_HISTORICAL_DATA_FEED=sip  # allowed: sip or iex
```

`ALPACA_DATA_FEED` remains the legacy/live-client default. Historical commands
use `ALPACA_HISTORICAL_DATA_FEED` unless `--feed` is supplied. Unsupported
historical feed names fail during configuration parsing.

```bash
# Historical research default (SIP)
python -m aml.cli fetch --symbol GME --date 2024-05-14
python -m aml.cli replay --symbol GME --date 2024-05-14 --feed sip
.venv/bin/python scripts/analyze_candidates.py GME 2024-05-14 --feed sip
.venv/bin/python scripts/analyze_candidate_diagnostics.py GME 2024-05-14 --feed sip
.venv/bin/python scripts/simulate_trades.py GME 2024-05-14 --feed sip

# Explicit IEX comparison
python -m aml.cli fetch --symbol GME --date 2024-05-14 --feed iex
python -m aml.cli replay --symbol GME --date 2024-05-14 --feed iex
.venv/bin/python scripts/analyze_candidates.py GME 2024-05-14 --feed iex
.venv/bin/python scripts/simulate_trades.py GME 2024-05-14 --feed iex
```

Feed-qualified files use names such as `2024-05-14_sip_1min.csv` and
`2024-05-14_iex_1min.csv`; analysis artifacts are separated into `sip/` and
`iex/` directories. Acquisition metadata records the requested feed, endpoint,
parameters, page count, source raw file, and fetch time. Pagination follows
every non-null Alpaca `next_page_token` automatically.

Verify entitlement with a bounded, read-only historical request:

```bash
python -m aml.cli check-data-feed --symbol AAPL --date 2024-05-14 --feed sip
python -m aml.cli check-data-feed --symbol AAPL --date 2024-05-14 --feed iex
```

An Alpaca HTTP 403 raises an explicit feed-permission error with plan guidance.
The client never retries a denied SIP request as IEX.

Run the controlled comparison below. `--download` acquires feed- and
vintage-qualified premarket and regular files for both feeds; omit it to rerun
the deterministic comparison from the hash-verified local files. Comparison
artifacts contain fixed-order timestamp-aligned OHLCV rows and canonical JSON
under `artifacts/feed_comparisons/`.

```bash
.venv/bin/python scripts/compare_alpaca_feeds.py GME 2024-05-13 \
  --dataset-vintage alpaca-feed-validation-v001 --download
.venv/bin/python scripts/compare_alpaca_feeds.py GME 2024-05-13 \
  --dataset-vintage alpaca-feed-validation-v001
```

The initial bounded universe is `GME AMC AAPL TSLA NVDA AMD PLTR` on
`2024-05-13` and `2024-05-14`. The repository does not yet document a genuine
ordinary lower-volatility session, so none is silently invented; add one only
after it is registered in the research manifest. Do not expand this command to
a multi-year or full-market download yet.

## Three-year liquid-markets backfill

The reviewable universe in `config/liquid_day_trading_universe_v001.csv`
contains liquid ETF proxies for the S&P 500, Nasdaq-100, Russell 2000, Dow,
gold, silver, crude oil, Treasury bonds, major sectors, volatility, and the
existing seven research stocks. It intentionally uses SPY as the S&P 500 market
proxy instead of silently treating today's 500 constituents as a historically
point-in-time universe.

Plan the three-year SIP job without downloading anything:

```bash
.venv/bin/python scripts/backfill_liquid_markets.py \
  --start 2023-07-24 --end 2026-07-23 \
  --dataset-vintage alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001
```

Run a three-task engineering pilot, then remove `--max-tasks` for the complete
resumable job:

```bash
.venv/bin/python scripts/backfill_liquid_markets.py \
  --start 2023-07-24 --end 2026-07-23 \
  --dataset-vintage alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001 \
  --workers 3 --max-tasks 3 --execute
```

Each symbol/session writes separate premarket and regular-session raw,
processed, and hash-verified metadata files beneath the ignored
`data/research/<dataset-vintage>/` directory. Rerunning the same command verifies
and skips completed segments. Failed write-once records remain visible and
are never silently overwritten. This is market-data acquisition for research;
it never submits orders.

Transient DNS, connection, HTTP 429, and provider 5xx failures are retried with
bounded exponential backoff. If all retries are exhausted, the failed attempt
remains visible. Resume with `--retry-failures` to archive that attempt beneath
`metadata/failed_attempts/` and retry without deleting the audit record.
An advisory dataset lock prevents two downloader processes from writing the
same vintage concurrently; stale lock files are harmless because the operating
system releases the lock when its owning process exits.

After a completed backfill, create the tracked dataset manifest against the
published downloader commit. This rehashes every raw, processed, and metadata
file, verifies processed row counts, and records one stable partition hash per
symbol without placing the dataset itself in Git:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_dataset_manifest.py \
  --source-commit <full-published-commit-sha>
```

The versioned JSON beneath `manifests/` contains coverage, source and
subscription provenance, session definitions, rows per symbol, acquisition
timestamps, validation totals, and path-independent partition hashes. Manifest
generation fails closed on missing files, identity conflicts, unexpected feed
evidence, duplicate or out-of-order timestamps, row-count drift, or hash drift.

The report includes row count, timestamp bounds, duplicates, raw and
halt-adjusted missing minutes, total volume, timestamp-aligned OHLCV difference
count, and the existing quality-policy completeness result for each feed. SIP
usually improves consolidated-market coverage, but better coverage alone does
not demonstrate that the strategy is profitable.

Legacy unsuffixed files are treated as historical IEX data, never SIP. Use
`--feed legacy` to replay them. The old Python loader signature without a feed
still works but emits a deprecation warning. The old `paths(symbol, date)`
helper now intentionally resolves to SIP-qualified paths; Python callers that
need an unsuffixed path must use `legacy_paths(symbol, date)` explicitly.

## Verified-halt-aware completeness

Historical replay and analysis commands default to `halt_aware` completeness.
Canonical, source-attributed halt records live at
`data/market_halts/{SYMBOL}/{DATE}_verified_halts.csv`. Only verified records
are used; ordinary data gaps are never inferred to be halts. If no halt file
exists, halt-aware and strict completeness are equivalent.

A minute bar is timestamped at the beginning of its minute. Accordingly, only
a minute that is non-tradable for its entire interval is removed from the
expected-minute index. The partial minute in which a halt begins and a partial
minute in which trading resumes remain expected because either can contain
trades. Exact wall-clock return endpoints, observed-bar MFE/MAE, and simulator
execution are unchanged.

Use `--completeness-mode strict` on replay, candidate analysis, candidate
diagnostics, simulation, or batch evaluation to require every regular-session
clock minute. Feed and completeness mode are independent, for example:

```bash
python -m aml.cli replay --symbol GME --date 2024-05-14 --feed sip --completeness-mode strict
.venv/bin/python scripts/analyze_candidates.py GME 2024-05-14 --feed iex --completeness-mode halt_aware
```

Halt-aware completeness changes data-quality classification only. It does not
change strategy scores, entries, exits, stop/target ordering, or P&L.

Start with `FIRST_SESSION.md`.

## Strategy tournament

The research-only tournament framework runs multiple fixed, versioned intraday
strategies through the same shared simulator and frozen SIP dataset. It defaults
to development and validation; holdout access requires `--include-holdout` and
never influences the composite score.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_strategy_tournament.py --dry-run
PYTHONPATH=src .venv/bin/python scripts/run_strategy_tournament.py \
  --config config/strategy_tournament_baseline.yaml \
  --splits development validation
```

Audit attention-momentum feature coverage, score provenance, execution reasons,
and DST-safe calendar-month results for a completed run:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_tournament_attention.py \
  --run-id 564345a77176524eb250
```

See `docs/ATTENTION_MOMENTUM_AUDIT.md` for score and integrity-check semantics.
The corrected Strategy V0.1.1 development/validation baseline and its read-only
robustness review are recorded in `docs/STRATEGY_V011_BASELINE.md`.

Long runs can be restarted with `--resume`. Completed strategy-symbol-day units
are hash-verified before reuse, and final leaderboards are published atomically.
See `docs/STRATEGY_TOURNAMENT_V001.md` for signal timing, strategy extension,
fixed splits, scoring, artifacts, and simulation limitations.

## Multi-strategy portfolio artifacts and dashboard

The shared-capital simulator can publish deterministic, write-once research
runs. A completed run lives under `artifacts/portfolio/{run_id}/`; its metadata
is written last and contains file hashes, source/input provenance, fixed
allocations, risk configuration, and explicit reconciliation checks. Existing
completed run directories are never overwritten.

Run metadata records both the Git commit and whether the source worktree was
dirty. Provenance and input-hash names must use logical identifiers and must not
contain credentials, secrets, or machine-local paths.

Generate the synthetic three-strategy demonstration (not performance evidence):

```bash
.venv/bin/python scripts/demonstrate_portfolio_simulation.py \
  --artifact-root artifacts/portfolio
```

Install the optional local dashboard dependency and launch the read-only UI:

```bash
.venv/bin/python -m pip install -e '.[dashboard]'
.venv/bin/streamlit run scripts/run_portfolio_dashboard.py -- \
  --artifact-root artifacts/portfolio
```

The dashboard loads only completed, schema-compatible, hash-verified runs. It
shows persisted summaries, ledgers, proposal decisions, trades, equity and
drawdown curves, cumulative strategy P&L, allocations, and provenance. It does
not rerun the engine or reinterpret trading outcomes.

Publication uses a hidden `.{run_id}.lock` file. If a process is interrupted,
the lock is deliberately left stale so publication fails closed. Before manual
recovery, confirm that no writer for that run is active and that no completed
`{run_id}/` directory exists; only then remove the corresponding lock file and
rerun publication. Hidden lock files and temporary directories are never loaded
as completed runs.

To populate the dashboard from the existing four-session local feasibility
dataset, run the development-only adapter. It verifies every registered SIP
input hash and preserves the established attention strategy parameters:

```bash
.venv/bin/python scripts/run_historical_development_portfolio.py
```

This local feasibility run is explicitly retrospective development output. It
is not part of the preregistered production cohort and is not validation or
profitability evidence.

### Zero-cost historical SIP engineering rehearsal

The fixed Alpaca rehearsal proves the end-to-end software path with AAPL on
2026-07-15 while remaining separate from Research Cohort V001. It is dry-run by
default, never prints credentials, cannot change its symbol/date/feed scope, and
is labeled development-only rather than validation evidence:

```bash
.venv/bin/python scripts/run_engineering_rehearsal.py
.venv/bin/python scripts/run_engineering_rehearsal.py --execute
```

Successful acquisition data and portfolio artifacts are hash-validated,
write-once generated files beneath ignored `data/research/` and `artifacts/`
paths. See `docs/ENGINEERING_REHEARSAL_V001.md` for scope, resumption, and the
machine-visible reference-data and licensing limitations.
