# Executable Specification Implementation V001

## Purpose and boundary

This milestone proves that the immutable specification selected by Benchmark
Specification Campaign V001 can enter the existing discovery pipeline without
changing a frozen downstream component. It is executable engineering evidence,
not empirical evidence. It uses no validation, holdout, forward, paper, live,
Olympics, broker, or newly acquired market data.

The candidate is `opening-drive-first-pullback-v001`, revision 1, long arm only.
Its Library hypothesis and canonical specification remain unchanged. The
candidate adapter delegates all decisions to the frozen
`first_pullback_continuation_long_v002` evaluator. The adapter does not copy or
reinterpret its signal, indicator, entry, stop, target, cost, sizing, exit, or
portfolio rules.

## Architecture

The implementation adds three upstream layers:

1. `benchmark_executable_specification_runtime_v001` validates content-addressed
   source inventories and dataset authorizations, creates native Framework V001
   implementation bindings, and executes reusable conformance cases.
2. `benchmark_candidate_opening_drive_first_pullback_v001` binds the candidate
   alias to the exact frozen reference strategy and executor identities. It
   constructs only normalized `EvaluationInput` values and delegates to the
   existing evaluator and proposal simulator.
3. `benchmark_executable_specification_v001` reconstructs the existing Library
   hypothesis, embeds the already-frozen specification, preregisters the
   authorized dataset identity, publishes a native Framework V001 lifecycle
   bundle, and uses the unchanged discovery classifier.

The existing Benchmark Discovery Campaign receives a normal
`ExecutorRegistration`. Its unchanged verifier independently checks every
identity, source hash, lineage edge, reconciliation count, cost-scenario trade
count, classification contract, and write-once bundle.

## Canonical identities

- Implementation: `896148c2197b519b3eb9b11fa9082b3215d7494322829ea9b3a826f7055e7c26`
- Dataset authorization: `9ee49e7c6c00cd41dfa2e82f0230be261e3be485884ae4f81a6d5ae26255393a`
- Existing dataset: `e3a793b9f30189cbb12620461b6a26fc567fa8253ae69af5a42a9d7c3802ffcd`
- Framework specification artifact: `d46e88fc16a91c8ea99a4f91417059de61a73164a48d1fdc700f5afb5dfc8eb7`
- Preregistration: `4712fe4239a5a4bb7f929d8b5ab7120b023110812913fe95a99fe3518e4a37c4`
- Implementation binding: `af7415bf88d12c4482c3b16c0774436066b6f5661dfbf1a752d444d4f5c80ccb`
- Conformance: `3e50fbc52749fa87cdd38faa2f82418aa2684c63aaecd074a1edad5f466a6a86`
- Registered executor: `5dee0671d82780576c3e054f30a1a7ad22a8c4ce75ec37a588e5bd0e32423c06`
- Discovery Campaign: `4e47c3727dc48fc105341c8826853fa5141cd67200412b60814f6435c77e1552`
- Campaign manifest: `65c7713383cf944241ccdbcd85af4f08aa1ac4bd8abce618bada1d74856df2b9`

The claim-limited classification is `INCONCLUSIVE_DATA_LIMITATION`. It is a
synthetic pipeline result and must not be described as profitability, edge,
validation eligibility, deployment readiness, or capital eligibility.

## Authorized dataset binding

No dataset was added. The binding reuses
`tests/fixtures/executable_benchmark_candidate_v001/high_of_day_breakout_synthetic.csv`
at its existing file and domain identities. Its scope is exactly
`discovery_pipeline_conformance_only`. The binding explicitly prohibits
validation, holdout, forward validation, Olympics execution, paper trading, and
live trading. File mutation, identity substitution, symlinks, traversal, or a
changed claim scope fail closed.

The fixture can exercise routing and input normalization, but it cannot support
an economic result. Any proposals discovered in this fixture are rejected
before economic simulation. A separate in-memory conformance case proves that
the unchanged proposal lifecycle accepts and exits a valid proposal; that case
is not an authorized research dataset.

## Conformance guarantees

The canonical conformance artifact covers:

- positive proposal;
- negative no-signal;
- unavailable input;
- encoded integrity failure;
- deterministic repeated output;
- no look-ahead when future high, low, close, and volume change while the exact
  next open remains unchanged; and
- acceptance and lifecycle evaluation by the unchanged discovery simulator.

The registered campaign reconciles 40 Library entries as two executed and 38
blocked. Both executed entries retain independent identities and bundles; one
entrant cannot alter the other's input or source binding.

## Reuse by future hypotheses

The reusable runtime can serve any future specified hypothesis that can provide:

- a canonical Framework V001 specification and preregistration;
- an exact code-owned evaluator callable;
- a content-addressed, scope-limited dataset authorization;
- positive, negative, unavailable, integrity-failure, no-lookahead, and
  proposal-pipeline conformance callbacks; and
- a Discovery Campaign executor registration.

The remaining ten specification-campaign candidates can reuse the binding,
dataset-validation, conformance, registration, publication, and reconciliation
plumbing after each receives unambiguous strategy semantics and an evaluator.
Candidates blocked on point-in-time data, synchronized indicators, or a new
execution model remain blocked on those capabilities; this runtime does not
pretend to satisfy them.

## Reproduction

From the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_executable_specification_implementation_v001.py \
  --campaign-config config/executable_specification_implementation_campaign_v001.json \
  --implementation-config config/executable_specification_implementation_v001.json \
  --existing-plan config/executable_benchmark_candidate_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --specification-campaign config/benchmark_specification_campaign_v001.json \
  --output-root /tmp/executable-specification-implementation-v001 \
  --repository-root .
```

Use `--verify-only` against the committed manifest directory to verify without
publishing another bundle.

## Remaining blocker

The selected hypothesis is fully executable through the authorized synthetic
discovery pipeline. It is not authorized for an empirical discovery campaign.
The next minimal blocker is a separately reviewed point-in-time historical
dataset authorization that satisfies every frozen field, calendar, halt,
corporate-action, completeness, licensing, contamination, and discovery-period
boundary. This milestone neither creates nor requests that authorization.
