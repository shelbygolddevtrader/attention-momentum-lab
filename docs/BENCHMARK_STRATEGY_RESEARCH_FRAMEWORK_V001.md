# Benchmark Strategy Research Framework V001

## Scope

V001 is the smallest executable upstream research lifecycle. It proves that one
new, preregistered candidate can move from observation through immutable archive
while using the established proposal simulator and discovery classifier without
changing either one.

The included opening-range midpoint-reclaim candidate and CSV are synthetic
engineering fixtures. They are not empirical evidence, validation, an Olympics
entrant, a profitability claim, or trading authorization.

V001 does not implement optimization, parameter search, machine learning,
validation, holdout access, Olympics execution, broker connectivity, paper
trading, live trading, or capital allocation.

## Dependency boundary

The dependency direction is one-way:

```text
observation / hypothesis / preregistration
                  |
candidate point-in-time evaluator
                  |
existing portfolio_simulator.StrategyProposal
                  |
existing portfolio simulator and reconciliation
                  |
existing discovery_screen_v001.trade_metrics and classify
                  |
immutable classification and archive
```

Frozen downstream modules do not import the research framework. The
implementation binding records SHA-256 hashes for the new implementation files
and the downstream files it calls. It does not reinterpret or alter downstream
behavior.

## Lifecycle

The executable path is:

1. **Observation** records the originating behavior, source references, and any
   datasets used to generate the idea.
2. **Hypothesis** states the assumption, mechanism, expected edge, required
   evidence, invalidation conditions, risks, indicators, regime expectation,
   holding period, and failure modes.
3. **Triage** records admission, duplicate signature, exact duplicates, reasons,
   and the deterministic pre-implementation priority vector.
4. **Specification** freezes one complete candidate contract and binds its output
   to the existing shared proposal type.
5. **Preregistration** locks observation, hypothesis, triage, specification,
   permitted datasets, contaminated datasets, and prohibited stages.
6. **Implementation binding** hashes the exact candidate implementation and the
   unchanged downstream source files.
7. **Conformance** requires positive, negative, unavailable, integrity-failure,
   no-lookahead, deterministic, and shared-proposal-pipeline paths.
8. **Discovery execution** evaluates only preregistered, uncontaminated input,
   runs the existing portfolio simulator at base, 1.5x, and 2x slippage, and
   reconciles every proposal to a completed trade or rejection.
9. **Classification** invokes `aml.discovery_screen_v001.classify` unchanged.
10. **Archive** preserves the complete lineage and result.

The current synthetic fixture produces
`INCONCLUSIVE_INSUFFICIENT_SAMPLE`. That classification proves integration only.
It provides no evidence for or against a real trading edge.

## Identity and immutability

Every entity is a strict artifact envelope containing:

- framework and schema versions;
- artifact type;
- sorted parent identities;
- canonical payload;
- SHA-256 identity over the complete envelope except the identity field.

Canonical JSON is UTF-8, key-sorted, compact, newline-terminated, and rejects
non-finite values. Timestamps are explicit UTC values. Runtime timezone, hash
seed, mapping order, and filesystem order do not affect output.

Lifecycle bundles are written through a temporary directory and atomically
renamed. Existing output paths are rejected. The manifest binds the ordered
artifact identities, file hashes, and byte sizes. Verification recalculates
every hash and artifact identity.

## Contamination and post-freeze changes

Every dataset used to generate an observation must appear in the hypothesis's
contamination set. Preregistration rejects any overlap between contaminated and
permitted discovery data. Discovery independently rechecks both conditions.

Research-defining changes after preregistration cannot modify the existing
hypothesis. `create_child_hypothesis` requires:

- the exact parent hypothesis and preregistration identities;
- an incremented revision;
- the parent identity;
- a new content identity;
- every inherited contaminated dataset; and
- every dataset accessed after the parent was frozen.

The parent remains reproducible. The child cannot claim confirmation from data
that motivated its change.

## Candidate contract

The vertical-slice candidate is
`opening-range-midpoint-reclaim-long-v001`, version `1.0.0`.

It uses only complete bars available at the decision cutoff:

- opening range: exact bars labeled 09:30 through 09:34 New York time;
- decision window: 09:36 through 10:30;
- prior close at or below the fixed range midpoint;
- current close strictly above the midpoint and below the range high;
- current close above its open;
- current volume at least 1.5 times the opening-range median;
- signal and intended entry at the next exact minute;
- stop at the frozen range low;
- target at the frozen range high;
- thirty-minute maximum holding period;
- maximum one proposal per symbol-session.

Missing required minutes are unavailable rather than interpolated. Duplicate,
nonchronological, timezone-naive, mixed-symbol, mixed-session, non-finite,
nonpositive-price, negative-volume, and malformed-OHLC inputs fail closed.

The evaluator receives only the bar prefix ending at the signal source bar. The
next bar and later path cannot influence proposal creation.

## Classification and claims

The framework does not define a new performance classifier. It supplies the
existing classifier with the existing `trade_metrics` structure:

- base costs;
- 1.5x cost stress;
- 2x cost stress;
- equal trade counts across cost scenarios;
- material-data-limitation status.

Integrity failures prevent discovery and classification. Proposal count must
equal accepted trades plus rejections. Synthetic evidence always carries the
claim ceiling `pipeline_execution_only_no_empirical_edge_claim` and can never be
validation eligible.

## Archive behavior

V001 supports immutable archive records for:

- completed lifecycle runs;
- formally rejected hypotheses;
- pre-empirical abandonment; and
- post-preregistration supersession.

An abandoned status is prohibited after empirical outcome access. Completed or
rejected archives require a classification. Superseded post-freeze hypotheses
must retain their preregistration lineage.

## Running the synthetic vertical slice

Use a new output directory:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_benchmark_strategy_research_v001.py \
  --repository-root "$PWD" \
  --plan config/benchmark_strategy_research_v001_example.json \
  --bars tests/fixtures/benchmark_research_v001/opening_reclaim_synthetic.csv \
  --output-root artifacts/benchmark_strategy_research/v001/example-run
```

The command performs no network or broker operation. It refuses to overwrite an
existing run directory.

## Produced artifacts

The bundle has stable ordered filenames:

```text
01-observation.json
02-hypothesis.json
03-triage.json
04-specification.json
05-preregistration.json
06-implementation_binding.json
07-conformance.json
08-discovery.json
09-classification.json
10-archive.json
manifest.json
```

## Current limitations

- V001 contains one candidate implementation and one synthetic fixture.
- It does not provide a general plugin-discovery mechanism.
- It does not authorize empirical data or new benchmark entrants.
- The existing generic portfolio simulator has its existing cost semantics;
  V001 does not change or reinterpret them.
- A future empirical milestone must preregister a separate, licensed,
  uncontaminated dataset identity before use.
- A future candidate requires a new identity, contract, implementation binding,
  and conformance suite; it cannot replace this candidate in place.
