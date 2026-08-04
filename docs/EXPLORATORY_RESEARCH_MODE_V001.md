# Exploratory Research Mode V001

> **EXPLORATORY ONLY — NOT AUTHORIZED FOR EMPIRICAL CONCLUSIONS — CONTAMINATED DATA — NOT VALIDATION — NOT HOLDOUT — NOT PRODUCTION — NOT CAPITAL ELIGIBLE**

Exploratory Research Mode V001 is an engineering and research-prioritization
path. It is not a relaxed dataset authorization gate and it does not publish
accepted research. It permits already available, contaminated discovery-period
bars to reach already frozen evaluators so researchers can inspect trigger
reachability, proposal flow, lifecycle reachability, unavailable inputs, and
integrity defects.

## Boundary

The mode can answer whether an implementation runs, whether an input is absent,
whether a hypothesis emits proposals, and whether proposal accounting
reconciles. It cannot answer whether a strategy has an edge, is profitable, is
statistically significant, is validated, is suitable for capital, or is ready
for paper, live, production, or Olympics execution.

V001 does not publish P&L, expectancy, win rate, profit factor, returns, Sharpe,
or any other economic performance field. The result validator recursively
rejects those keys. Every artifact repeats all seven mandatory warning labels,
uses the evidence class `exploratory_non_empirical_contaminated`, carries only
false research/capital claim flags, and is written outside Git under the
`exploratory_research/v001` namespace.

## Frozen components

V001 changes none of the existing executor, lifecycle, integrity, discovery,
classification, publication, Olympics, governance, benchmark strategy, or
hypothesis-library files. Opening-drive evaluation delegates to the frozen
`first_pullback_continuation_long_v002` executor through the existing exact
alias. Accepted proposals pass through the unchanged discovery lifecycle
simulator. The separate exploratory writer retains only counts and exit-reason-
free lifecycle totals; trade records and economic values are not serialized.

## Bounded exercise

The canonical plan selects five symbols and the first five frozen discovery
sessions without inspecting outcomes. Those 25 symbol-sessions are descendants
of a dataset previously used in discovery and are intentionally marked
contaminated. Validation, holdout, extension, forward, paper, live, and Olympics
periods remain inaccessible.

Two immutable Library V001 hypotheses are registered:

| Hypothesis | V001 behavior |
|---|---|
| `opening-drive-first-pullback-v001` | Runs through its frozen exact-alias evaluator and lifecycle. |
| `high-of-day-breakout-continuation-v001` | Fails unavailable because stored bars lack `spread_bps`; V001 never fabricates the field. |

The second result is intentional evidence about engineering readiness, not a
negative trading result.

## Artifact contract

Each hypothesis result contains:

- trigger, proposal, executed-trade, rejected-proposal, unavailable-event, and
  integrity-failure counts;
- deterministic decision-status and reason counts;
- qualitative observations and implementation notes generated from those
  counts;
- obvious anomaly codes and a missing-data summary;
- confidence warnings, evidence class, claim ceiling, and false claim flags;
- immutable hypothesis, registration, evaluator, and result identities.

`summary.json` binds the exact plan, dataset fingerprint, partition hashes,
source-code hashes (including the frozen evaluator and lifecycle), and all
hypothesis statuses. `manifest.json` hashes every output file. Publication
uses an exclusive destination and fails if the run path already exists. The
verifier rejects unmanifested files, altered bytes, missing warning labels,
affirmative evidence claims, unsafe paths, or prohibited economic fields.

## Running

Use a new output directory outside every Git checkout:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_exploratory_research_mode_v001.py \
  --dataset-root /absolute/path/to/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001 \
  --output-root /absolute/path/to/artifacts/exploratory_research/v001/run-001
```

The data is read locally. The command has no API client, credentials, network,
broker, order, optimization, validation, holdout, or accepted-publication path.

## Interpretation and prioritization

V001 prioritization is limited to implementation usefulness:

- An exercised hypothesis with clean integrity and observable proposal flow is
  useful for further engineering review; this says nothing about its edge.
- A no-trigger result suggests inspecting specification reachability and test
  fixtures, not relaxing thresholds.
- An unavailable result identifies a concrete input dependency.
- An integrity failure blocks even exploratory interpretation until corrected.

With the current data, opening-drive first-pullback is the next useful
implementation to inspect because its complete frozen path is reachable.
High-of-day breakout cannot be completely evaluated because historical spread
observations are absent. The largest general unlock remains authorized
point-in-time event and microstructure data: the Implementation Campaign found
24 hypotheses blocked by data, while spread/quote history would immediately
unlock the high-of-day candidate's required input.

## Limitations

- Data contamination is permanent and cannot be cured by relabeling.
- Provider feed echo, written retention rights, and historical corporate-action
  revision lineage remain unresolved.
- The bounded five-session selection is an engineering fixture, not a sample.
- Only registered complete implementations run. A hypothesis is never assigned
  an evaluator merely because a similar strategy exists.
- Absence or presence of triggers cannot support an economic conclusion.
