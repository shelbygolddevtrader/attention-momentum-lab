# Professional Strategy Benchmark Olympics Execution and Publication V004

Status: prospective frozen contract; not an authorization and not a trial.

V003 remains immutable. Its authorization identity binds the V003 adapter but predates the
execution/publication wrapper, so extending V003 would silently change a frozen identity.
V004 closes that gap additively by requiring the future authorization to name the exact
checked-out merged source commit, then binding the unchanged V003 contract and implementation
identities, the V004 execution/publication implementation,
the canonical synthetic fixture and manifest, the unchanged V001 orchestrator, and V004
scoring into one authoritative lineage run identity.

## Lifecycle

1. Strictly validate a separately created, human-approved V004 authorization.
2. Atomically consume its immutable identity before generating any artifact.
3. Project the canonical V003 manifest and approval into the unchanged V001 orchestrator.
4. Build the deterministic V001 artifact set.
5. Add authorization, consumption, lineage, and hash-index artifacts.
6. Atomically publish under the authoritative outer lineage run identity.

Both authorization reuse and any pre-existing destination fail closed. Identical bytes are
not treated as permission to republish. The inner V001 run identity remains auditable but is
subordinate to the authoritative V004 lineage identity.

## Boundaries

The committed contract explicitly forbids authorization creation and any execution or
publication without an external authorization. Those operations require a future, separately
reviewed human-approval artifact. Tests use only
an approval labeled `test-only-not-official-authorization` in temporary directories. No
official authorization, result, ranking, or published artifact is committed by this milestone.

Historical, validation, holdout, extension, forward, live, provider, broker, production, and
network access remain prohibited. Synthetic results, when separately authorized, are
non-performance and non-economic evidence only.
