# Alpaca SIP Engineering Rehearsal V001

**Status:** software rehearsal only; not research validation

This workflow exercises the historical software path at zero incremental cost
using the repository's normally configured Alpaca credentials. It does not
create an account, buy a subscription, place an order, inspect brokerage funds,
or authorize production data collection.

## Fixed scope

- Provider: Alpaca historical market-data API
- Requested feed: consolidated SIP
- Symbol/session: AAPL, 2026-07-15
- Premarket: [04:00, 09:25) America/New_York
- Regular session: authoritative XNYS left-labeled minutes
- Dataset vintage: `engineering-rehearsal-v001`
- Evidence class: `engineering_rehearsal_only_not_validation`

The symbol and date are compiled into workflow version 1. They cannot be
overridden, expanded, or silently substituted. The date is outside the frozen
Research Cohort V001 window. Dry run is the default and does not load credentials
or access the network.

```bash
.venv/bin/python scripts/run_engineering_rehearsal.py
.venv/bin/python scripts/run_engineering_rehearsal.py --execute
```

The execute form makes one premarket and one regular segment acquisition;
provider pagination can add page requests. Successful segments are staged and
published together. A complete cache is hash-validated and reused. Partial,
contradictory, or tampered caches fail closed. Raw pages, normalized bars, and
metadata live under:

`data/research/engineering-rehearsal-v001/sip/AAPL/2026-07-15/`

The generated fixed scope manifest lives under
`artifacts/engineering_rehearsal/alpaca_sip_aapl_2026-07-15_v001/`, and the
completed development portfolio run lives under `artifacts/portfolio/`. These
paths are ignored generated data. The normal dashboard discovers the completed
portfolio run.

## Evidence and licensing boundary

This fixture was chosen before acquisition to prove pagination, extended-hours
segmentation, provenance, hashing, replay, simulation, reconciliation, artifact
publication, resumption, and dashboard discovery. Its simulated results may not
be used to tune the strategy or claim prediction, validation, or profitability.

The workflow explicitly records that it lacks:

- a complete point-in-time common-stock universe;
- listing/delisting and symbol-continuity evidence;
- bounded negative corporate-action evidence;
- verified commercial raw-data retention rights; and
- verified subscriber-facing derived-display rights.

These gaps are acceptable only for an engineering rehearsal. They remain hard
production gates in `RESEARCH_PROVIDER_EVALUATION_V001.md` and
`RESEARCH_DATA_SCHEMAS_V001.md`.
