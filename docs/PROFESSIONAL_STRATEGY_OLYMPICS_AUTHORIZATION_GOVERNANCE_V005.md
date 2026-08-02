# Professional Strategy Benchmark Olympics V005 Authorization Governance

Status: `DESIGN_ONLY_V005_CORRECTED_LIFECYCLE_AUTHORIZATION_NOT_CREATED`

This milestone freezes a pure, synthetic, fail-closed authorization-governance contract. It does not create an authorization, implement an authorization consumer, execute the Olympics, access protected data, or publish results.

The authoritative machine contract is `config/professional_strategy_olympics_authorization_governance_v005.json`. This document explains that contract; it is not an alternate policy source. The validator rejects any machine lifecycle that differs from its independently declared expected matrix.

## Frozen identities

- Governance identity: `9408e2b9dcb4e14534f4f7699ea26fe0846f4a2d3f2ad416ea11758a34f2223a`
- Governance projection: `104143` canonical bytes
- Complete contract: `104230` canonical bytes
- Execution-command identity: `ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb`
- Execution-command projection: `535` canonical bytes
- V004 contract: `0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053`
- V004 implementation: `d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4`
- Design base: `2f5390a844b9187b92da124a77173669f1b3f536`
- Immutable baseline tag object: `746e147efd9bb09dedfdd4d2850f461e36d9f046`
- Immutable baseline tagged commit: `378317dba28d93792d2f0a3ab4302a5d0b6abf7c`

Identity is `SHA-256(UTF8(domain) || 0x00 || canonical_projection_bytes)`. Canonical JSON uses sorted keys, compact separators, ASCII Unicode escapes, integers only, NFC strings, and exactly one trailing LF. Duplicate keys, floats, non-finite values, invalid Unicode, Boolean-as-integer substitutions, BOMs, unknown fields, noncanonical bytes, excessive depth, and oversized inputs reject.

## Scope and trust boundary

V005 has 37 immutable typed artifact schemas and 27 transitions. Every lifecycle transition is evaluated from a closed typed bundle. A bundle has one transition envelope, one root event, an exact typed prior reference, an artifact-bound durability package, an assigned stable-account actor, and a unique documentary clock package.

The validator is intentionally pure. It validates canonical bytes, identities, typed references, deterministic equations, and internally consistent synthetic evidence. It performs no network access, TLS handshake, filesystem mutation, Git checkout, authorization creation, authorization consumption, subprocess execution, or Olympics execution.

Two facts require independent external attestations in a future implementation:

1. Real repository provenance requires a typed repository-context attestation. Portable Git objects prove content and ancestry, not the repository in which they were observed.
2. Real-world time and transport authenticity require a typed clock-verifier attestation. Caller-provided HTTP headers and Boolean transport claims cannot independently authenticate TLS origin or current time.

V005 validates those attestation records structurally and binds them cryptographically to the documentary package. It does not claim to reproduce their external trust decisions.

## Artifact inventory

The original 31 schemas remain, with generic prior-record references removed. Six schemas complete the evidence graph:

- `typed_reference`: freezes target type, schema version, domain, identity field, represented state, and exact target identity.
- `canonical_payload`: binds an artifact identity to its exact canonical bytes and SHA-256 digest.
- `durability_evidence`: binds artifact, bytes, target path, parent, filesystem evidence, transition key, and exact ordered durability trace.
- `repository_context`: records provider, immutable repository and owner numeric IDs, node IDs, canonical name, object format, retrieval evidence, and the external-attestation trust scope.
- `clock_verifier_attestation`: binds request, response, verifier account/version, host, transport evidence, verified Date, replay nonce, and explicit external-verifier scope.
- `transition_envelope`: binds transition, source/destination, role, acting stable account, root artifact, typed prior, supporting references, role assignment, and durability evidence.

No `identity:prior_record` or `identity:canonical_bytes` escape hatch exists. External V001–V004 objects remain explicitly declared compatibility edges and are not silently treated as V005 artifacts.

## Exact lifecycle

`terminal=true` means no further transition is permitted. The only terminal states are `archived`, `expired`, `rejected`, and `superseded`. A run success or failure still requires archival. An indeterminate state is nonterminal because only an explicit typed recovery route may leave it.

| # | Transition | Source → destination | Actor | Typed prior | Root record | Validity | Terminal |
|---:|---|---|---|---|---|---|:---:|
| 1 | `proposal_approved` | proposed → approved | authorization author | proposal | human approval | n/a | no |
| 2 | `authorization_activated` | approved → active_unconsumed | operator | human approval | activation | valid | no |
| 3 | `consumption_decision_won` | active_unconsumed → claiming | operator | activation | authorization decision | valid | no |
| 4 | `consumption_claim_durable` | claiming → consumed | operator | authorization decision | consumption claim | valid | no |
| 5 | `build_started` | consumed → build_started | operator | consumption claim | build start | valid | no |
| 6 | `run_started` | build_started → run_started | operator | build start | run start | valid | no |
| 7 | `run_succeeded` | run_started → run_succeeded | operator | run start | lifecycle terminal | valid | no |
| 8 | `run_failed` | run_started → run_failed | operator | run start | lifecycle terminal | valid | no |
| 9 | `build_failed` | build_started → run_failed | operator | build start | lifecycle terminal | valid | no |
| 10 | `success_archive_started` | run_succeeded → archive_pending | archive custodian | lifecycle terminal | archive pending | valid | no |
| 11 | `failure_archive_started` | run_failed → archive_pending | archive custodian | lifecycle terminal | archive pending | valid | no |
| 12 | `archive_completed` | archive_pending → archived | archive custodian | archive pending | completion marker | valid | yes |
| 13 | `supersession_decision_won` | active_unconsumed → superseding | superseding author | activation | authorization decision | valid | no |
| 14 | `supersession_durable` | superseding → superseded | superseding author | authorization decision | supersession | valid | yes |
| 15 | `authorization_expired` | active_unconsumed → expired | system | activation | expiration | exact expiry | yes |
| 16 | `proposal_rejected` | proposed → rejected | reviewer | proposal | rejection | n/a | yes |
| 17 | `preflight_rejected` | approved → rejected | operator | human approval | rejection | valid | yes |
| 18 | `claim_indeterminate` | claiming → indeterminate | system | authorization decision | indeterminate | valid | no |
| 19 | `build_indeterminate` | consumed → indeterminate | system | consumption claim | indeterminate | valid | no |
| 20 | `run_indeterminate` | run_started → indeterminate | system | run start | indeterminate | valid | no |
| 21 | `archive_indeterminate` | archive_pending → indeterminate | system | archive pending | indeterminate | valid | no |
| 22 | `claim_recovered` | indeterminate → consumed | operator | indeterminate | recovery | valid | no |
| 23 | `build_recovered` | indeterminate → build_started | operator | indeterminate | recovery | valid | no |
| 24 | `run_success_recovered` | indeterminate → run_succeeded | operator | indeterminate | recovery | valid | no |
| 25 | `run_failure_recovered` | indeterminate → run_failed | operator | indeterminate | recovery | valid | no |
| 26 | `archive_recovered` | indeterminate → archive_pending | archive custodian | indeterminate | recovery | valid | no |
| 27 | `archive_completion_recovered` | indeterminate → archived | archive custodian | indeterminate | recovery | valid | yes |

Each machine transition also freezes the exact required artifact types, any conditional success/failure set, forbidden competitors, timestamp equation, identity equations, atomicity, durability, retry, idempotency, recovery route, and actor.

## Authorization validity and timestamp order

Authorization lifetime is exactly 259200 seconds and half-open:

`issued_at <= operation_timestamp < expires_at`

Every authorization-dependent transition applies that equation at its own root-event timestamp. Expiration alone requires `operation_timestamp == expires_at`. Proposal approval and proposal rejection do not require an authorization.

Every root timestamp must be greater than or equal to the timestamp of its typed prior record. Equality is permitted because the trusted Date representation has one-second resolution. The graph therefore enforces:

`proposal <= approval <= issuance <= activation <= decision <= claim <= build <= run <= terminal <= archive_pending <= archive_manifest <= completion`

Supersession begins after activation. Rejection follows its proposal or approval. Expiration follows activation and occurs exactly at expiry. Indeterminate records follow the uncertain predecessor. Recovery follows the exact indeterminate record. Backward timestamps reject even when every individual clock record is internally self-consistent.

## Typed prior and closed-bundle model

Every transition envelope references one `typed_reference`. That reference declares and proves:

- target artifact type;
- target schema version;
- identity domain;
- identity-field name;
- exact target identity;
- exact source state represented.

The validator resolves all internal references recursively. Dynamic references in typed references, canonical payloads, durability records, and transition envelopes receive the same type checks as static schema references. Every supplied internal record must be referenced by another record or be the single transition envelope root. Extra stable accounts, clock records, role assignments, prior candidates, results, terminals, recoveries, byte-identical duplicates, and conflicting duplicates reject.

## Actor identity and role separation

The caller’s role string is never sufficient. The transition envelope names the acting stable-account identity; the role assignment maps the declared role to that identity; the root event independently names the same actor; and the stable-account artifact resolves to an immutable GitHub numeric user ID.

Display login metadata is never used for identity or separation. The complete frozen role matrix is validated for every transition. Operator, reviewer, authorization author, governance author, source author, archive custodian, system actor, previous operator, and superseding author constraints therefore apply throughout the lifecycle, including supersession and recovery.

## Documentary Git and repository context

The raw Git proof recomputes authorization and documentary-binding blobs, every tree step, commit A, and commit B. Commit A has exactly one parent—the authorized source commit—and contains the authorization at exactly:

`authorizations/{authorization_identity}/authorization.json`

Commit B has exactly one parent—commit A—and contains the documentary binding at its frozen path. Alternate authorization identity, alternate path, mode, object type, tree, parent, or bytes reject.

The documentary binding and authorization must name the same repository-context identity. Raw Git objects establish content and ancestry only. The typed external repository-context attestation supplies provider and immutable repository/owner identifiers. V005 does not claim that raw objects alone prove GitHub repository origin.

## Clock-verifier model

Each timestamp-bearing artifact has a unique request, response, external verifier attestation, and event attestation. The raw documentary HTTP response uses exact ASCII CRLF framing, status 200, and a strict Date-only header allowlist. `Age`, `Via`, `Warning`, `X-Cache`, `X-Proxy-Cache`, and every other unrecognized response header therefore reject.

The external verifier attestation records the verified host, transport-evidence identity, certificate/TLS result, proxy/redirect/cache results, Date, verifier version/account, and replay nonce. The pure validator binds those claims and does not independently authenticate them. A future external verifier must maintain the replay registry and establish real TLS and current-time facts. An event without that typed verifier attestation rejects.

## Transition-specific APFS durability

Every transition root has one `durability_evidence` record and one exact `canonical_payload`. The validator binds:

- target artifact type and identity;
- exact canonical bytes and SHA-256;
- exact rendered schema path and parent directory;
- filesystem-evidence identity;
- deterministic transition key;
- exclusive-create result;
- file `F_FULLFSYNC` result;
- close result;
- directory fsync result;
- immutable final state.

The exact ordered trace is:

1. `open_root_no_follow`
2. `verify_mount_device_owner_mode`
3. `exclusive_create`
4. `write_complete`
5. `f_fullfsync_file`
6. `close_file`
7. `fsync_directory`

Filesystem evidence must describe local APFS on macOS, a trusted descriptor-relative root, correct UID/GID/modes, no symlinks, no cross-device traversal, one hard link, and no ACL, xattrs, flags, network mount, disk image, overlay, synthetic, or removable backing. Generic durability strings cannot authorize a transition.

## Supersession

The predecessor decision slot is exclusive and can contain exactly one durable consume or supersede decision. Complete supersession validation requires the predecessor authorization, activation evidence, decision, successor, supersession record, accounts, and role assignment. It rejects any supplied claim, expiration, rejection, terminal, indeterminate, or earlier supersession evidence.

The predecessor must be active, unconsumed, unexpired, unrejected, nonterminal, determinate, and not already superseded at the decision time. The successor must name exactly that predecessor and preserve run, fixture, manifest, dataset, command, V004, source commit, and source tree identities. The superseding author must differ from the previous operator by immutable numeric account ID. Forks, duplicate incoming edges, cycles, stale records, missing links, and conflicting decisions reject.

## Reachable recovery

Recovery is no longer prose-only. Six explicit transitions resolve claim, build, run-success, run-failure, archive-pending, and archive-completion uncertainty. A recovery artifact references the exact indeterminate artifact, a typed recovered artifact, existing and intended canonical payload identities, recovery actor, outcome, and unique clock evidence.

Recovery may reconcile identical intended bytes or add only explicitly permitted missing archive bytes. It cannot delete, truncate, replace, change identity, assert an outcome unsupported by typed evidence, bypass expiry, or skip durability. Recovery itself is a durable transition root and is subject to the same actor, clock, monotonicity, validity, path, payload, and APFS checks.

## Archive state machine

Canonical destination: `archives/{run_identity}`

Canonical staging path: `archives/staging/{archive_pending_identity}`

The archive manifest binds the pending record, terminal, authorization, run, outcome projection, expected file identities, destination, and staging path. The completion marker binds the same authorization, run, archive identity, and terminal state. Pending time must not exceed manifest time; manifest time must not exceed completion time.

The pure archive classifier returns exactly one of:

- `publication_permitted`
- `recovery_permitted`
- `already_complete_and_valid`
- `indeterminate`
- `invalid_conflicting`

| Condition | Result |
|---|---|
| Destination absent and no files, manifest, marker, or durability claims | publication permitted |
| Existing incomplete matching destination with explicit recovery authority | recovery permitted |
| Destination, required files, manifest, marker, bytes, identities, and durability all match | already complete and valid |
| Evidence incomplete but not contradictory | indeterminate |
| Destination absent with files/manifest/marker/durability assertions | invalid/conflicting |
| Marker without manifest or required files | invalid/conflicting |
| Marker names another archive | invalid/conflicting |
| Unexpected files or conflicting bytes | invalid/conflicting |
| First publication into an existing destination | invalid/conflicting |
| Recovery without an existing partial destination | invalid/conflicting |

An archived state is valid only after a matching durable completion marker.

## Verification commands

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_authorization_governance_v005.py
PYTHONPATH=src .venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests scripts
git diff --check origin/main...HEAD
```

The validator CLI reports only immutable design metadata. It cannot create or consume an authorization and cannot execute the Olympics.
