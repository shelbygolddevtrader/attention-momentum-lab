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
