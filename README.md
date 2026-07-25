# Attention Momentum Lab

A private, modular research system for testing whether unusual price/volume momentum can be detected without look-ahead bias.

This project connects to Alpaca paper APIs, downloads one-minute bars, replays a stock-day chronologically, calculates a transparent baseline score, logs every candidate, and produces separate price and volume charts.

It is shares-only, paper-only, and research-only. It does not submit orders.

## Historical data feeds

Historical strategy research defaults to consolidated SIP data. IEX represents
activity from one exchange, so its volume and volume-derived features can differ
materially from consolidated US-market activity. IEX remains available for
feed comparisons and explicitly IEX-based workflows.

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

### Vendor sample quarantine gate

Before vendor market or reference samples can enter research, validate them
locally with the strategy-independent acceptance checker:

```bash
.venv/bin/python scripts/check_vendor_sample.py --help
```

The checker has separate `market_data` and `reference_data` profiles and also
requires a written licensing-evidence manifest. It writes deterministic JSON
and Markdown reports under ignored `artifacts/vendor_sample_acceptance/` and
never copies source samples into canonical research paths. See
`docs/VENDOR_SAMPLE_ACCEPTANCE_V001.md` and the non-proprietary templates under
`examples/vendor_sample_acceptance/`.
