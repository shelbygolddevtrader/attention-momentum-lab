# Professional Strategy Benchmark Olympics Authorization Governance V005

Status: design-only governance contract. No authorization exists and no run is authorized.

V004 remains unchanged. V005 resolves two prospective gaps before any official result exists:
the prior authorization shape lacked canonical time, validity, command, and storage rules; and
binding executable source to the authorization repository's current `HEAD` created a paradox.

## Authorized source and documentary authorization

An authorization binds `authorized_source_commit` and that commit's exact Git tree object.
Execution must use a clean detached checkout whose `HEAD` and tree equal those values. The
authorization file must remain outside that checkout. Its later repository commit is a
documentary, append-only governance record and is never the executable source. This permits
authorization review and archival without changing the code authorized to execute.

The authorized commit must be reachable from `origin/main` at review time. Sparse checkout,
submodules, untracked files, tracked changes, alternate remotes, source mutation, and execution
from another commit all fail closed.

## Canonical authorization and time

The future authorization schema has an exact required field list and rejects unknown fields.
Its identity is SHA-256 over canonical UTF-8 JSON excluding only `authorization_identity`.
Canonical JSON uses sorted keys, compact separators, one trailing LF, unique keys, finite
numbers, and valid Unicode.

Every authorization timestamp is exactly `YYYY-MM-DDTHH:MM:SSZ`: UTC only, whole seconds,
with no offsets, fractional seconds, or leap seconds. The authorization review PR's GitHub
`createdAt` is `authorization_created_at`; `not_before` equals it; and `expires_at` is exactly
259,200 seconds later. Validity is the half-open interval `[not_before, expires_at)`.

Before consumption, a separate preflight captures the HTTPS `api.github.com` server `Date`
header and canonical response-header hash. The attestation must be no older than 300 seconds.
All network access ends before authorization validation or consumption; the trial itself is
network-free. Missing, stale, malformed, or non-HTTPS evidence blocks execution.

## Frozen entry point

The future implementation must provide only this exact entry point:

`scripts/run_professional_strategy_olympics_v005.py`

It must execute the frozen argv template directly without shell interpretation, from the
detached source root, with `TZ=UTC`, `LANG=C`, `LC_ALL=C`, and `PYTHONHASHSEED=0`. The command
identity is `278f812e47cb0d290e9188fcdaf93c7eb4b01e60f70b503471e67b7d31f54a1a`.
Fallback commands, alternate parameters, alternate datasets, and regenerated identities are
prohibited. The authorization must also bind the Python binary, version, and installed
distribution hashes through an execution-environment manifest identity.

## Review, storage, consumption, and replay prevention

The authorization is stored once beneath a path keyed by its identity. Corrections never edit
published bytes. An expired unused authorization may be superseded by a new identity that
references it; a consumed authorization or consumed run identity can never be reauthorized.
Only one active authorization may exist for a run.

Approval requires a GitHub `APPROVED` review on the exact head from a reviewer other than the
author, successful CI, zero unresolved threads, recalculation of every identity, verification
of the immutable baseline tag, and proof that the authorization and run remain unused. A head
change invalidates approval.

After validation, the implementation must atomically claim the authorization in its single
declared operator store before generating any artifact. The authorization binds that store and
one operator instance. Reuse, another operator, a pre-existing claim, or a publication collision
fails closed. A failure after consumption remains consumed and produces failure evidence.

Post-execution archival is append-only and contains the authorization, clock attestation,
environment manifest, consumption evidence, lineage manifest, artifact index, and complete V004
bundle. Interpretation of any result is a separate future milestone.

## Independent review of PR #24

From a fresh clone, replace `<approved-head>` with the exact PR head:

```bash
git fetch origin main research/v035-olympics-authorization-governance-v005
git checkout --detach <approved-head>
git status --porcelain=v1 --untracked-files=all
git show -s --format='%H %P %T %s' HEAD
git diff --check origin/main...HEAD
git diff --name-status origin/main...HEAD
```

Recalculate the frozen design identities:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from aml.winner_archetype_contracts import canonical_hash

path = Path('config/professional_strategy_olympics_authorization_governance_v005.json')
value = json.loads(path.read_text(encoding='utf-8'))
command = dict(value['execution_command'])
claimed_command = command.pop('command_identity')
claimed_contract = value.pop('contract_identity')
print('command', canonical_hash(command), claimed_command)
print('contract', canonical_hash(value), claimed_contract)
PY
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_authorization_governance_v005.py --root .
```

Run verification:

```bash
.venv/bin/python -m pytest tests/test_professional_strategy_olympics_authorization_governance_v005.py
.venv/bin/python -m pytest
.venv/bin/ruff check src tests scripts
git diff --check origin/main...HEAD
```

Confirm the design-only boundary and immutable tag:

```bash
find governance/authorizations artifacts/professional_strategy_olympics -type f 2>/dev/null
git grep -nE 'authorization_status.*authorized_unused|ranking_ledger|aggregate_score_ledger' -- ':!tests/**'
git rev-parse v0.1.1-research-baseline
git rev-parse 'v0.1.1-research-baseline^{}'
git status --short
```

Expected: no authorization or Olympics result artifact, no operator V005 execution script,
tag object `746e147efd9bb09dedfdd4d2850f461e36d9f046`, tagged commit
`378317dba28d93792d2f0a3ab4302a5d0b6abf7c`, and a clean checkout.

## Remaining milestones

PR #25 may implement this frozen contract without changing its rules. PR #26 is the independent
audit and controlled merge. Only afterward may a separate authorization PR be created. This
V005 design milestone cannot create, approve, consume, execute, publish, score, rank, or interpret
an Olympics run.

The previously calculated run identity `95b4204fef27f47d5abbd510157f615a9418467b95dea5f87ecf82f7c88e0491`
describes the pre-V005 source commit only. It was never authorized. Because the V004 lineage
formula includes `authorized_source_commit`, the implementation milestone's final merged source
will deterministically produce a new prospective run identity. That new identity must be frozen
in the later authorization; the pre-V005 identity cannot be substituted or reused.
