# Professional Strategy Benchmark Olympics Orchestrator V001

> **No Olympic trial has been run. No performance result exists.** This implementation is authorization-gated and validation-only by default. The 19 V004 vectors are mathematical specification tests, not market, economic, or performance evidence.

## Identity and scope

- Orchestrator contract identity: `9e1af13518bc4c6588ce4faaf302e15182f9d42e5dd8c453fc6d27dd257b8d3e`
- Exact module/CLI implementation identity: `fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0`
- V004 scoring bundle: `205c126be0d3f1af78899b69609a6ba86a0026ec6dd55729112da78eaa4f23bc`
- Implementation base: `4285bcf4fea27a21647d6dd82ca4df639eef260f`
- Executor bundle: `9c03677ce4ea4e56256f6873c00a4cdc502e23b2780f36af6b3f2a0b3b45bf5d`

The orchestrator coordinates frozen inputs. It does not alter strategy, proposal, signal, executor, lifecycle, fill, sizing, stop, target, exit-time, scoring, or tie behavior. Its narrow input adapter accepts immutable completed-trade atoms from the existing synthetic executor/lifecycle layer. It does not regenerate proposals or access data.

## Stages

1. Verify V001–V004 lineage and the immutable V0.1.1 tag.
2. Validate an explicitly named strict synthetic input manifest.
3. Bind all ten frozen strategy and executor identities in canonical order.
4. Validate completed-trade atoms, exact fractions, timestamps, and proposal uniqueness.
5. Classify disqualification and event eligibility.
6. Calculate all 15 V004 raw events with integer, rational, or frozen algebraic arithmetic.
7. Apply V003 unique ordinal percentiles and exact event scores.
8. Aggregate the frozen weights and apply discovery-only overall ties.
9. Build ten identity-bound canonical artifacts.
10. Publish through an atomic, write-once directory rename.

An integrity defect never becomes a low score. Proposal rejection, trade rejection, event ineligibility, strategy disqualification, and tournament integrity failure remain distinct categories.

## Authorization gate

Ordinary invocation runs validation only and reports `VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED`. Trial execution requires both:

- the explicit `--execute` flag; and
- a strict authorization artifact bound to the exact orchestrator identity, V004 identity, input-manifest identity, deterministic run identity, synthetic trial kind, and a nonempty human-approval reference.

Neither is present or authorized in this milestone. An input manifest alone, an output path, or a casual CLI invocation cannot execute a trial.

```bash
PYTHONPATH=src python scripts/run_professional_strategy_olympics_orchestrator_v001.py
```

The command above validates repository lineage only. It writes nothing and performs no trial.

## Input manifest

The manifest is strict UTF-8 JSON with no unknown fields. It must declare synthetic discovery-only scope, the exact V004 identity, a canonical manifest identity, all ten strategy/executor bindings, and canonically ordered completed-trade atoms. Every trade binds:

- immutable proposal identity and symbol;
- exact entry and exit nanoseconds;
- actual whole-share quantity and adjusted entry microdollars;
- net P&L microdollars and reduced-rational net R;
- reconciled New York exit month and pre-outcome regime label;
- the exact 1x, 1.5x, and 2x fixed-population cost-stress net-R atoms.

Missing, duplicate, noncanonical, reordered, mismatched, or malformed critical records fail closed. The adapter contains no historical, network, broker, forward, validation, or holdout loader.

## Artifact bundle

A separately authorized future synthetic trial will produce exactly:

1. `run_manifest.json`
2. `input_manifest.json`
3. `identity_manifest.json`
4. `raw_event_registry.json`
5. `eligibility_disqualification_ledger.json`
6. `event_score_ledger.json`
7. `aggregate_score_ledger.json`
8. `ranking_ledger.json`
9. `integrity_report.json`
10. `SUMMARY.md`

JSON uses canonical UTF-8 sorted-key serialization. The run identity depends only on the orchestrator, scoring bundle, input manifest, opened stage, and synthetic trial kind. Wall-clock time and absolute paths are excluded. Publication uses exclusive file creation inside an incomplete sibling directory followed by atomic rename. A byte-different collision aborts; an identical complete bundle is verification, not a rewrite.

The Markdown summary is derived only from canonical identity records and cannot add an independent result or interpretation.

## Determinism and replay

Validation and pure scoring are invariant to process hash seed, host time zone, and repeated invocation. Inputs with a required canonical order must arrive in that order; order-independent calculations use exact commutative sums. A future replay verifies the same input identity and run identity and must reproduce byte-identical artifacts.

## Forbidden behavior

This layer has no permission or interface to:

- access historical, live, forward, extension, validation, or holdout data;
- contact a provider, network service, broker, or order interface;
- tune strategies or change frozen executors;
- mutate proposals, quantities, stops, targets, fills, or exit timestamps;
- use floating-point tolerance or hidden rounding;
- overwrite a completed run;
- describe synthetic output as revenue, profitability, or trading evidence.

## Readiness

After this implementation passes exact-head CI, the repository may be classified **READY FOR SEPARATE SYNTHETIC TRIAL AUTHORIZATION**. That classification does not itself authorize or execute the trial. A separate human-approved, identity-bound authorization milestone remains mandatory.
