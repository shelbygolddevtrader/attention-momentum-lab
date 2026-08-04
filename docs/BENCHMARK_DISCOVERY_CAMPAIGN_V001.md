# Benchmark Discovery Campaign V001

## Purpose

Campaign V001 is a deterministic routing and reconciliation layer between the
immutable Benchmark Hypothesis Library V001 and Benchmark Strategy Research
Framework V001. It answers one question for every preregistered hypothesis:

> Does an exact, reviewed, code-bound executable lifecycle exist, and if so,
> did the unchanged Framework V001 discovery pipeline publish valid evidence?

The campaign does not translate prose concepts into strategy rules. It does not
select thresholds, infer implementations, acquire data, or run validation. A
missing executable lifecycle is evidence of missing readiness, not evidence for
or against the economic hypothesis.

## Dependency lineage

The frozen configuration binds:

- Framework V001 source commit
  `d7651c2f31059039b8b0dc5d6baa716c53a57e4b`;
- Library V001 source commit
  `1b30241e73166ca931c1de3e65048dd45c758a67`;
- Library identity
  `6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003`;
- canonical Library file SHA-256
  `b6295804c4356633bc035a6da721c6b64c2c0a5103e663799e7b4ed42d2a295c`;
- Campaign identity
  `6d47d71dacdb6c65a10e32719ffac0567eca901cd27e0e25bfbd2d63a0bf857e`.

The Campaign identity also binds the exact router and CLI file hashes. Any
dependency or Campaign-code substitution fails before an executor can run.

## Execution eligibility

An entry is executable only when the Campaign configuration contains one exact
executor contract and the process supplies one matching code registration.
The contract binds:

1. Library entry and native Framework hypothesis identities.
2. Adapter identifier and version.
3. Permitted discovery dataset identity.
4. Specification, preregistration, implementation-binding, and conformance
   identities.
5. Every adapter source path and byte hash.
6. One content-addressed executor identity.

Configuration cannot name an import path. Runtime code must explicitly register
the callable, preventing untrusted JSON from selecting arbitrary Python. Missing
runtime code for an authorized contract aborts the campaign; it is an operator
failure, not a hypothesis classification.

The adapter receives a new entry-specific output path. It must use the existing
Framework V001 lifecycle and publish the standard ten-artifact Framework bundle.
Campaign V001 then independently runs `verify_bundle` and requires:

- exact hypothesis, strategy, specification, preregistration, binding,
  conformance, and dataset identities;
- the strategy identifier to equal the Library entry identifier;
- classification lineage to the exact discovery artifact;
- zero executor integrity failures;
- proposals equal accepted trades plus rejected proposals;
- identical trade counts across all frozen cost scenarios.

No campaign result is accepted merely because an adapter returned successfully.

## Blocked classification

An entry with no authorized executor receives exactly:

`BLOCKED_NOT_EXECUTABLE`

and these sorted reason codes:

- `conformance_evidence_missing`
- `executable_specification_missing`
- `implementation_binding_missing`
- `permitted_discovery_dataset_missing`
- `registered_executor_missing`

Blocked results contain no Framework bundle or performance evidence. The
initial V001 configuration intentionally contains an empty executor allowlist.
All 40 Library V001 hypotheses are therefore blocked. This is the only valid
outcome because Library V001 is hypothesis-only and Framework V001 currently
contains one unrelated vertical-slice candidate rather than executable
specifications for the Library entries.

## Failure behavior

The campaign aborts without publication when any authorized execution has:

- missing, changed, duplicated, or unauthorized registration;
- changed adapter bytes;
- execution error or incomplete bundle;
- stale or substituted identity;
- strategy-to-hypothesis identity mismatch;
- nonzero integrity failure count;
- malformed, noncanonical, oversized, or symlinked input;
- proposal or cost-scenario reconciliation failure;
- attempted output reuse or protected-boundary output.

It never converts an execution defect to `BLOCKED_NOT_EXECUTABLE` and never
publishes partial campaign evidence.

## Immutable artifacts

Publication is staged in a sibling temporary directory and atomically renamed
only after all entries reconcile. The final directory contains:

```text
manifest.json
entries/<library-entry-id>/result.json
entries/<executable-entry-id>/framework-bundle/...
```

The manifest records every result identity, file hash and size, Framework
bundle identity, classification count, and reconciliation invariant. Publication
refuses an existing destination. `verify_campaign` rehashes and revalidates the
complete tree without executing strategies.

The tracked canonical V001 output is under
`manifests/benchmark_discovery_campaign_v001/`. It has 40 blocked results, zero
executed results, zero duplicate results, and zero executor integrity failures.
Its manifest identity is
`26a59a7d0ad515366f5a6572789fd3af881eefc99ad57561508505fe8e8d8100`.

## Commands

Publish the frozen readiness campaign to a new destination:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_benchmark_discovery_campaign_v001.py \
  --config config/benchmark_discovery_campaign_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --output-root artifacts/benchmark_discovery_campaign_v001/new-run
```

Verify the committed canonical evidence without running an executor:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_benchmark_discovery_campaign_v001.py \
  --config config/benchmark_discovery_campaign_v001.json \
  --library config/benchmark_hypothesis_library_v001.json \
  --output-root manifests/benchmark_discovery_campaign_v001 \
  --verify-only
```

## Adding an executable hypothesis

Do not edit a blocked result. A separately reviewed milestone must first create
the hypothesis-specific specification, implementation, preregistration,
conformance evidence, and permitted dataset identity. A successor Campaign
configuration then freezes an executor contract and source hashes. The adapter
is registered in code and must publish the unchanged Framework V001 bundle.

If Framework V001 cannot express an unambiguous candidate, the hypothesis stays
blocked or requires a separately versioned upstream framework contract. The
campaign must never fill that gap by interpreting hypothesis prose.

## Claim boundary

Campaign readiness evidence is not a backtest and cannot establish profitability,
robustness, validation eligibility, deployment readiness, or capital eligibility.
Synthetic executable-path tests prove routing correctness only. No validation,
holdout, forward-validation, Olympics, paper-trading, live-trading, broker, or
capital-allocation capability is introduced.
