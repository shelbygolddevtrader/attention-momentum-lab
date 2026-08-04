# Executable Benchmark Candidate V001

## Status and claim boundary

This milestone makes exactly one Benchmark Hypothesis Library V001 entry
executable through the unchanged Benchmark Strategy Research Framework V001,
Campaign V001 router, portfolio simulator, and discovery classifier:

`high-of-day-breakout-continuation-v001`

The committed input is deliberately synthetic. It proves that the real,
previously preregistered hypothesis has a complete and auditable executable
research chain. It is not historical performance evidence and cannot establish
an edge, profitability, robustness, validation eligibility, deployment
readiness, or capital eligibility. The other 39 Library V001 hypotheses remain
canonically `BLOCKED_NOT_EXECUTABLE`.

No optimization, threshold search, validation, holdout, forward execution,
Olympics execution, paper trading, live trading, or broker capability is
introduced.

## Why this candidate

The selection was made before implementation because this entry is the
simplest Library V001 hypothesis that the existing architecture can express
without narrowing or revising the frozen hypothesis:

- its original directional scope includes long execution;
- all inputs are completed one-minute OHLCV bars plus point-in-time spread;
- no catalyst, news, auction, options, order-book, or cross-market feed is
  required; and
- the existing `StrategyProposal`, simulator, cost scenarios, metrics, and
  classification contracts can consume it unchanged.

This is revision 1 of the original hypothesis. No library field was mutated and
no child hypothesis was required.

## Frozen executable specification

Bars are regular-session, left-labeled one-minute intervals `[t, t+1 minute)`.
The decision occurs only after the trigger bar is complete.

| Element | Frozen rule |
|---|---|
| Direction | Long only |
| Decision window | 09:50–14:30 America/New_York |
| Warm-up | 20 prior completed, contiguous bars from 09:30 |
| Level | Earliest maximum high established at least 15 completed bars before the trigger |
| Consolidation | Previous five bars span no more than 0.75 ATR20 |
| Trigger | Completed close strictly above the level |
| Volume | Trigger volume at least 1.5 times prior-20 median volume |
| Liquidity | Spread no greater than 15 basis points; price from $2 through $500 |
| Prior tests | No more than two prior completed closes above the level |
| Entry | Exact next one-minute bar open; zero allowed delay |
| Stop | Five-bar consolidation low minus 0.05 ATR20 |
| Target | Trigger close plus two trigger-close-to-stop risk units |
| Timeout | 90 minutes |
| Frequency cap | One proposal per symbol-session |
| Missing data | Unavailable; never filled or interpolated |
| Integrity defect | Fail closed; never publish accepted performance |

The complete machine-readable specification is frozen in
`config/executable_benchmark_candidate_v001.json`. A semantic change requires a
new preregistration lineage; it cannot rewrite this artifact.

## Point-in-time and conformance guarantees

The evaluator receives only a prefix ending at the completed trigger bar. It
cannot read the intended-entry bar. Its canonical signal and intended-entry
timestamp is the next exact minute, whose open is resolved by the unchanged
simulator.

Conformance evidence requires all of these paths to pass before execution:

- positive signal and proposal;
- negative/no-signal;
- unavailable warm-up;
- integrity failure;
- deterministic repeated evaluation;
- future-bar mutation with an unchanged proposal identity; and
- acceptance by the existing proposal pipeline.

Duplicate, missing, nonchronological, timezone-naive, nonfinite,
nonpositive-price, negative-volume, negative-spread, mixed-symbol,
mixed-session, and malformed-OHLC input fails closed.

## Dataset authorization

The only authorized input is the committed synthetic fixture:

`tests/fixtures/executable_benchmark_candidate_v001/high_of_day_breakout_synthetic.csv`

- File SHA-256:
  `b2cf391e8cbdb1002a1b7b804284aed8681810bf3c65f3a3175b0eadaaaefc55`
- Dataset identity:
  `e3a793b9f30189cbb12620461b6a26fc567fa8253ae69af5a42a9d7c3802ffcd`
- Authorization: `candidate_v001_synthetic_discovery_only`
- Claim limit: `pipeline_evidence_only_no_empirical_edge_claim`

Every field consumed by the evaluator or simulator is included in the dataset
identity. File or semantic substitution fails before evaluation. Validation,
holdout, forward-validation, and extension labels remain prohibited by the
preregistration.

## Immutable lifecycle identities

- Library hypothesis:
  `3545e9db49dca14f2598541afaa3da65a66cf63e5cc9ded12b4a826f15abef86`
- Library registration:
  `a58bfa6327704c4b693e99f1837a783ae9d7448b667adac304232df05646d5b7`
- Candidate plan:
  `29625ff60f92e81bfc465a8e4d37b54578b9611dd420221accd4c4116a553452`
- Executable specification:
  `5b1a59ff8118204966e7cebed1e4bc78acbf5308a89ed9a512938b087b0c4b69`
- Framework preregistration:
  `d3335b9fbd11c895d9c4b7aee0142d02e4e448899c4f7361e73690a3a7f47345`
- Implementation binding:
  `973b63f8a5ca2ecf59b628c436fabec103ec9d29a5b422d0266472087ec70f9e`
- Conformance:
  `4610d7f459406268a3ee1dc45f5fed0a5d9abace574ecf6bb49686600b4f547a`
- Executor:
  `a60a832484b36bfd111410e7571985114a077971bf920c038b31991f93daab47`
- Successor campaign:
  `f31e0148844b7912b3408d17559e90b3c7d3266ed177286823a875c646cfcca3`

The implementation binding hashes the candidate implementation and the exact
unchanged discovery classifier and simulator. The executor contract adds the
code-owned runner. Any bound-source substitution aborts before publication.

## Canonical result

The synthetic fixture produces one proposal, one accepted completed trade,
zero rejected proposals, and zero executor integrity failures across all three
unchanged cost scenarios. The frozen discovery classifier therefore returns:

`INCONCLUSIVE_INSUFFICIENT_SAMPLE`

That is a canonical pipeline classification, not an empirical conclusion. The
archive state is `completed` because the preregistered synthetic lifecycle
completed; it does not mean the hypothesis succeeded economically.

The tracked write-once native Framework V001 archive bundle is under
`manifests/executable_benchmark_candidate_v001/`. The registered successor
campaign separately reconciles one executed hypothesis plus 39 blocked
hypotheses to all 40 Library entries; that complete routing path is reproduced
in the deterministic test suite.

- Discovery identity:
  `c8a5faf69b1f753c64daaa2587847112d1de0fdfc22c550f22d09a3763aee631`
- Classification identity:
  `36642e1d721eb1359e45788d9bbff3df61110f864d3a84830686dcdd1517839c`
- Archive identity:
  `db22554193753d514ae746c5488453c974032cbe219a2f9b0de91eca5d652b51`
- Framework bundle identity:
  `7019dddcef0fa6c5ae9b0d3b52ab581206f43afe44dbe8ce9d8daca76d8367d1`

## Commands

Publish to a new, unused destination:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_executable_benchmark_candidate_v001.py \
  --config config/executable_benchmark_candidate_campaign_v001.json \
  --plan config/executable_benchmark_candidate_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --output-root artifacts/executable_benchmark_candidate_v001/new-run \
  --repository-root .
```

Verify the committed evidence without executing the candidate:

```bash
PYTHONPATH=src .venv/bin/python -c \
  'from pathlib import Path; from aml.benchmark_strategy_research_v001 import verify_bundle; print(verify_bundle(Path("manifests/executable_benchmark_candidate_v001")))'
```

## Limitations and next research gate

- The fixture contains one synthetic symbol-session and one synthetic trade.
- No licensed historical dataset is authorized by this milestone.
- Spread is a supplied point-in-time fixture field; no quote-feed acquisition is
  introduced.
- The result cannot be compared with historical benchmark performance.
- A future empirical discovery requires a separately reviewed, uncontaminated,
  entitled dataset binding and prospective authorization. It must not reuse the
  synthetic classification as evidence of an edge.
