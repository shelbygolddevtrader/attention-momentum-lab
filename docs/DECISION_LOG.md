# Attention Momentum Lab Decision Log

This log records only decisions already embodied in repository code, tests,
documentation, or Git history. It is descriptive, not a new strategy or data
acquisition authorization.

## SIP is preferred over IEX for historical research

Historical research defaults to consolidated SIP; IEX remains available for
explicit comparison and legacy/live uses. Feed-qualified paths and metadata
prevent an IEX file from being represented as SIP.

**Evidence:** `README.md`; `src/aml/data_paths.py`; `src/aml/settings.py`;
`src/aml/alpaca_rest.py`; `tests/test_historical_acquisition.py`; commit
`faaf840`.

## Candidate and execution thresholds are separate

Research candidate eligibility and trade execution eligibility are distinct
threshold roles. Compatibility is explicit, and a candidate may be retained
for outcome/diagnostic analysis without automatically becoming an executed
trade.

**Evidence:** `src/aml/thresholds.py`; `src/aml/signals.py`;
`src/aml/trade_simulator.py`; `tests/test_threshold_compatibility.py`; commit
`18e08b3`.

## Strict and halt-aware completeness are distinct

Strict completeness expects every authoritative regular-session minute.
Halt-aware completeness removes only minutes proven non-tradable for their
entire interval by a source-attributed verified halt schedule. It changes data
quality classification, not scores, entries, exits, stop/target ordering, or
P&L. Missing bars are never inferred to be halts.

**Evidence:** `README.md`; `src/aml/market_halts.py`;
`src/aml/batch_evaluation.py`; `tests/test_market_halts.py`;
`tests/test_batch_evaluation.py`; commits `f8eb40c` and `b60bcdf`.

## Authoritative XNYS calendars define session boundaries

Session selection and regular-session expected minutes use the XNYS calendar,
including holidays and early closes, instead of hard-coded generic weekdays.
The V001 acquisition layer persists calendar identity and uses left-labeled
authoritative regular-session minutes.

**Evidence:** `src/aml/exchange_calendar_adapter.py`;
`src/aml/research_acquisition.py`; `tests/test_market_calendar.py`;
`tests/test_research_acquisition.py`; commit `69faaa8`.

## Development and validation evidence are labeled separately

The May 2024 AAPL/GME work, synthetic portfolio demonstration, and bounded AAPL
engineering rehearsal are development, feasibility, or software-path evidence.
They are not members of the untouched V001 validation cohort and cannot support
profitability or predictive claims.

**Evidence:** `docs/RESEARCH_COHORT_V001_DESIGN.md`;
`docs/ENGINEERING_REHEARSAL_V001.md`; `README.md`;
`src/aml/engineering_rehearsal.py`; `src/aml/portfolio_artifacts.py`.

## The validation cohort may not be used for strategy tuning

Strategy, score, risk, execution, and data-quality parameters are frozen before
validation outcomes are inspected. V001 baselines and cohort outcomes may be
reported, but thresholds may not be tuned on that cohort.

**Evidence:** `docs/RESEARCH_COHORT_V001_DESIGN.md` and
`docs/STRATEGY_CONSTITUTION_V001.md`; commit `98d0a65`.

## Fixed strategy allocations precede adaptive allocation

The current portfolio engine accepts explicit fixed virtual allocations and a
fixed allocation policy. Adaptive allocation is rejected by configuration
validation and is not an implemented behavior.

**Evidence:** `src/aml/portfolio_simulator.py`;
`tests/test_portfolio_simulator.py`; fixed-allocation metadata checks in
`src/aml/portfolio_artifacts.py`; commit `9871cef`.

## The dashboard displays persisted engine truth

The Streamlit dashboard discovers only completed, schema-compatible,
hash-verified portfolio runs and displays persisted summaries, ledgers,
decisions, trades, curves, allocations, and provenance. Display-only filtering
is allowed; the dashboard does not run the simulator or recalculate outcomes.

**Evidence:** `scripts/run_portfolio_dashboard.py`; `README.md`;
`src/aml/portfolio_artifacts.py`; `tests/test_portfolio_artifacts.py`; commit
`61b0c1b`.

## Broad production acquisition requires point-in-time reference data and licensing

Production collection cannot begin from a current-only or survivorship-biased
universe. It requires point-in-time security identity/listing/action evidence,
consolidated market-data provenance, bounded completeness, and written rights
for the intended storage, processing, retention, derived works, and subscriber
surfaces. Technical sample acceptance alone is insufficient.

**Evidence:** `docs/RESEARCH_DATA_SCHEMAS_V001.md`;
`docs/RESEARCH_PROVIDER_EVALUATION_V001.md`;
`docs/RESEARCH_COHORT_V001_DESIGN.md`; `src/aml/research_reference_data.py`;
the uncommitted `docs/VENDOR_SAMPLE_ACCEPTANCE_V001.md` and
`src/aml/vendor_sample_acceptance.py`; commits `9ec28a4`, `5a2b59f`, and
`0e864d4`.
