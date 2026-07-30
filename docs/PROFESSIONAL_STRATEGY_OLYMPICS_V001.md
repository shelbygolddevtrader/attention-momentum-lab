# Professional Strategy Benchmark Olympics V001

Status: **design only; readiness blocked; no empirical research authorized**.

This prospective protocol asks a narrow question: under one provider-bounded
candidate universe, chronological partition plan, execution model, cost model,
and risk budget, which predefined mechanical intraday strategy families show
the strongest reproducible net performance? Popularity is not evidence of an
edge, and a medal is not advancement, statistical significance, profitability,
or permission to trade.

The canonical machine-readable artifacts are:

- protocol: `config/professional_strategy_olympics_protocol_v001.json`
- strategy registry: `config/professional_strategy_olympics_strategy_registry_v001.json`
- tournament: `config/professional_strategy_olympics_tournament_v001.json`
- blocked readiness: `config/professional_strategy_olympics_readiness_v001.json`

Their identities are respectively:

- protocol: `8a7f4c2ca1c6b133e769992ef8315186de87b0f7f1baedf6d549536db6f72f3e`
- registry: `af1e44069fd5e226ad702469fdf10c7e0b1c49c803065e20c83588b22e17bbc0`
- tournament: `10d41bf657759b5db5b5524a18158a480797ab9dcfcca59e7921672d31bb70aa`
- readiness: `ebe1179fea526e4bad0c808609ff68320840d57d2172355227edfeccaf054602`

## Isolation and scope

The Olympics has its own identity and write-once namespace,
`artifacts/professional_strategy_olympics/v001`. It changes neither Lean
Discovery V001, Winner Archetype V002, Strategy V0.1.1, nor capital governance,
and inherits no readiness credit. The Research Division is reserved but empty.
Unsupported short implementations are exhibition-only until point-in-time
borrow availability and fees exist. Exhibition entries cannot medal or advance.

The Benchmark Division contains exactly ten canonical long-only families:
five- and fifteen-minute opening-range breakouts, gap-and-go, first-pullback
continuation, VWAP reclaim, VWAP mean-reversion fade, high-of-day breakout,
failed-breakout reversal, RSI exhaustion reversion, and market-relative
momentum. Each is defined mechanically in the registry with no continuous
parameter search and no more than three permitted variants; V001 declares only
the canonical version.

## Lifecycle

1. Validate identities, entitlements, universe, partitions, data completeness,
   contracts, simulator assumptions, costs, and risk bindings.
2. Obtain a separate human authorization for discovery only.
3. Execute all eligible canonical contracts against the identical discovery
   partition and publish immutable artifacts.
4. Apply multiplicity controls and frozen advancement gates. Rankings alone do
   not advance a competitor.
5. Freeze any advancing identity before untouched validation.
6. Open validation and then one-time holdout only after their separate gates and
   approvals. Any material rule change resets evidence to discovery.
7. Continue to prospective paper-forward and later capital stages only through
   the independent capital ladder; this protocol cannot authorize them.

Readiness intentionally remains false even when documentary evidence is filled:
the empirical runner is not implemented and human authorization is separate.
The validator prints canonical artifacts; readiness returns status code 2:

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_v001.py protocol
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_v001.py readiness
```

No market, validation, holdout, broker, or provider endpoint is opened by these
commands.

## Claim ladder

The frozen levels are design only, pipeline operational, discovery result,
discovery advancement, validation passed, holdout passed, paper-forward
candidate, tiny-live candidate, self-funding candidate, and controlled-scaling
candidate. Backtest rankings may never be described as revenue. “Best
strategy,” “professional winner,” “proven edge,” “production ready,” and
“revenue generating” are forbidden Olympics conclusions.

## Limitations

All thresholds and costs are hypotheses fixed before data access, not empirical
facts. One-minute bars cannot establish queue position, precise tape order,
hidden liquidity, historical locates, or news receipt time. Bar-based stop-first
ordering is deliberately conservative but cannot reproduce every executable
path. Data entitlement and completeness remain unproven, and no performance or
capacity conclusion exists.

See the companion registry, scoring, statistics, compatibility, and execution
documents for the auditable details.
