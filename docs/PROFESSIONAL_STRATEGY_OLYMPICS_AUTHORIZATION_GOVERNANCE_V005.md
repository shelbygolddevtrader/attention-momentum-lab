# Professional Strategy Benchmark Olympics V005 authorization governance

Status: `DESIGN_ONLY_V005_CORRECTED_AUTHORIZATION_NOT_CREATED`

This prospective V005 contract is the final design layer between the frozen V004 publication protocol and a future, separately reviewed implementation. It validates only canonical contract data and synthetic evidence. It creates no authorization, consumes no authorization, performs no filesystem arbitration, contacts no clock service, executes no Olympics entry point, and accesses no protected input.

The machine source is `config/professional_strategy_olympics_authorization_governance_v005.json`. If this document and that contract ever differ, validation must fail and a new prospective correction is required; prose is not an alternate source of rules.

## 1. Frozen identities and lineage

- V005 governance domain: `aml.olympics.v005.governance`
- V005 governance identity: `8ad8b4b4f9864a89167d73a38a99bc38a4629a4c02d09f8bb280502407811cd8`
- Governance projection byte count: `62455`
- Command domain: `aml.olympics.v005.command`
- Command identity: `ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb`
- Command projection byte count: `535`
- Design base: `2f5390a844b9187b92da124a77173669f1b3f536`
- V004 contract: `0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053`
- V004 implementation: `d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4`
- Immutable baseline tag object: `746e147efd9bb09dedfdd4d2850f461e36d9f046`
- Immutable tagged commit: `378317dba28d93792d2f0a3ab4302a5d0b6abf7c`

## 2. Scope and trust boundary

V005 defends against schema drift, cross-type identity substitution, noncanonical bytes, local-clock substitution, cached or proxied Date evidence, role collision, authorization replay, conflicting consumption or supersession, filesystem and path substitution, uncertain durability, archive overwrite, success/failure ambiguity, and documentary Git object forgery.

It assumes SHA-256 and Git SHA-1 object calculations are collision resistant, the future consumer runs on one uncompromised macOS host and kernel, the APFS implementation reports truthful system-call evidence, and the authenticated GitHub origin is not compromised. The pure validator checks typed synthetic evidence; it does not claim to have performed the future system calls.

## 3. Exact canonical JSON

Every stored and identity-bearing JSON artifact uses one representation:

- UTF-8 bytes containing JSON whose non-ASCII characters are emitted with Python-compatible lowercase `\uXXXX` escapes;
- astral characters are lowercase UTF-16 surrogate pairs;
- input strings and keys must already be NFC;
- object keys sort by Unicode code point;
- separators are exactly comma and colon, with no whitespace;
- forward slash is not escaped;
- U+2028 and U+2029 are escaped;
- integers are allowed, but floats, booleans-as-integers, NaN, and infinities reject;
- duplicate keys, BOM, invalid UTF-8, lone surrogates, and nesting deeper than 40 reject;
- maximum input is 2,000,000 bytes;
- exactly one final LF is required.

Validation parses with duplicate-key detection, validates the value domain, canonically reserializes it, and requires byte-for-byte equality. CRLF, indentation, alternate spacing, alternate Unicode escaping, missing LF, and extra LF reject even when they would parse to the same value.

Artifact identity is:

`SHA256(UTF8(domain) || NUL || canonical_json(record excluding exactly its self-identity field))`

Governance excludes only `contract_identity`; command excludes only `command_identity`. No other governed field is excluded.

## 4. Complete artifact inventory

The contract defines 31 unique artifact domains. Unknown fields reject at every nesting level; every nullable field is present as JSON null.

| # | Artifact | Purpose |
|---:|---|---|
| 1 | `stable_account` | Stable GitHub numeric human-account identity |
| 2 | `display_metadata` | Mutable login snapshot, separate from security identity |
| 3 | `role_assignment` | Stable-account role allocation and separation |
| 4 | `clock_request` | Nonced direct-origin request contract |
| 5 | `clock_evidence` | Raw response headers and direct-TLS/cache/proxy evidence |
| 6 | `clock_attestation` | Exact event-projection and timestamp binding |
| 7 | `access_prohibition` | Bounded offline/protected-resource observation |
| 8 | `filesystem_evidence` | Typed macOS/APFS/path/durability facts |
| 9 | `environment_manifest` | Frozen runtime environment |
| 10 | `source_checkout` | Detached clean authorized source and tree |
| 11 | `consumption_store` | Single-host decision, claim, and supersession namespaces |
| 12 | `proposal` | Prospective authorization proposal |
| 13 | `human_approval` | Independent exact-proposal approval |
| 14 | `authorization` | Single-use authorization contract |
| 15 | `activation` | Successful preflight state |
| 16 | `authorization_decision` | Exclusive predecessor decision: consume or supersede |
| 17 | `consumption_claim` | Durable consumption evidence |
| 18 | `build_start` | Protected-input build start evidence |
| 19 | `run_start` | Runner start evidence |
| 20 | `result_manifest` | Successful result projection |
| 21 | `failure` | Failure record and detail identity |
| 22 | `lifecycle_terminal` | Mutually exclusive success or failure terminal |
| 23 | `archive_pending` | Archive transaction start |
| 24 | `archive_manifest` | Exact success or failure archive projection |
| 25 | `completion_marker` | Durable archive completion evidence |
| 26 | `supersession` | Durable predecessor-to-successor edge |
| 27 | `rejection` | Proposal or preflight rejection |
| 28 | `expiration` | Trusted-time expiry evidence |
| 29 | `indeterminate` | Uncertain durability without success/failure assertion |
| 30 | `recovery` | Narrow identical-byte or missing-archive-byte recovery authority |
| 31 | `documentary_binding` | Recomputed raw Git object proof binding |

The artifact-type registry is authoritative. Every V005 reference resolves to a supplied artifact of the exact registered type, schema, version, domain, and self-identity. Reuse of one identity as incompatible types, unresolved references, unexpected artifact types, V003/V004 substitutions, and orphan types reject. Narrow earlier-version compatibility exists only for the two exact V004 literals and declared external V004 input identity classes.

## 5. Stable accounts and role separation

`stable_account` hashes only provider, account kind, and GitHub numeric user ID. Login and display name reside in `display_metadata`; renaming changes display metadata but never role equality or authorization validity. Equal numeric user IDs are equal accounts regardless of login. Different numeric IDs remain different even if a login string matches.

The complete pair matrix remains 16 pairs. The authorization author, reviewer, and operator differ; source/governance authors differ from reviewer and operator; archive custodian differs from operator; a superseding author differs from the predecessor operator. The explicitly documented `may_match` pairs remain permitted. Unlisted role relationships reject.

## 6. Direct-origin trusted clock and timestamp equations

Clock evidence requires a synthetic record of a future direct authenticated TLS exchange with exactly:

- `HEAD https://api.github.com:443/rate_limit`;
- verified TLS peer and certificate for exact `api.github.com`;
- HTTP/1.1 status 200;
- no redirect;
- no configured or used proxy;
- no `Age`, `Via`, `Warning`, `X-Cache`, `X-Cache-Hits`, `CF-Cache-Status`, other cache-hit, or intermediary evidence;
- exactly one IMF-fixdate `Date` header in GMT;
- ASCII response headers with CRLF framing and one terminal CRLFCRLF;
- a unique 256-bit request nonce and request identity, with exact raw request bytes retaining the nonce, no-cache directives, host, API version, target, and CRLF framing;
- response elapsed time at most 5000 milliseconds.

A raw Date header alone is insufficient. The clock request, raw response header block, transport facts, and normalized attestation are separate typed artifacts.

Every timestamp-bearing lifecycle artifact has its own attestation. Its timestamp text must equal the attestation’s canonical `YYYY-MM-DDTHH:MM:SSZ` text exactly, with zero tolerance. The attestation also binds the event type, timestamp field, and the event projection excluding only self-identity, timestamp, and attestation identity. Reuse across lifecycle artifacts rejects.

This covers proposal, approval, issuance, activation, consumption decision and claim, build start, run start, terminal, archive start/publication/completion, supersession, rejection, expiration, indeterminate, and recovery. Authorization expiry equals issuance plus exactly 259200 seconds, and validity is half-open: `issued_at <= trusted_time < expires_at`.

## 7. Complete lifecycle transition bundles

String-only state membership is not validation. Every transition receives an exact typed bundle, validates all schemas and references, rejects forbidden competitors, validates the new artifact, validates every included lifecycle clock, and enforces transition-specific success/failure, decision, expiry, and identity rules.

| # | Transition | From → to | Actor | New durable record |
|---:|---|---|---|---|
| 1 | `proposal_approved` | proposed → approved | authorization author | human approval |
| 2 | `authorization_activated` | approved → active unused | operator | activation |
| 3 | `consumption_decision_won` | active unused → claiming | operator | consume decision |
| 4 | `consumption_claim_durable` | claiming → consumed | operator | claim |
| 5 | `build_started` | consumed → build started | operator | build start |
| 6 | `run_started` | build started → run started | operator | run start |
| 7 | `run_succeeded` | run started → run succeeded | operator | success terminal |
| 8 | `run_failed` | run started → run failed | operator | failure terminal |
| 9 | `build_failed` | build started → run failed | operator | failure terminal |
| 10 | `success_archive_started` | run succeeded → archive pending | archive custodian | archive pending |
| 11 | `failure_archive_started` | run failed → archive pending | archive custodian | archive pending |
| 12 | `archive_completed` | archive pending → archived | archive custodian | completion marker |
| 13 | `supersession_decision_won` | active unused → superseding | superseding author | supersede decision |
| 14 | `supersession_durable` | superseding → superseded | superseding author | supersession edge |
| 15 | `authorization_expired` | active unused → expired | system | expiration |
| 16 | `proposal_rejected` | proposed → rejected | reviewer | rejection |
| 17 | `preflight_rejected` | approved → rejected | operator | rejection |
| 18 | `claim_indeterminate` | claiming → indeterminate | system | indeterminate record |
| 19 | `run_indeterminate` | run started → indeterminate | system | indeterminate record |
| 20 | `archive_indeterminate` | archive pending → indeterminate | system | indeterminate record |

Each machine transition freezes exact source, destination, actor, required artifacts, conditional success/failure evidence, forbidden competing artifacts, atomicity, durability, crash boundaries, retry, idempotency, recovery, and terminal status. The atomicity pattern is exclusive create, complete canonical write, `F_FULLFSYNC`, close, and parent-directory fsync. Before atomicity, the same identity may retry. After exclusive creation but before proven durability, state is indeterminate and only typed recovery may proceed. After durability, only identical-byte reconciliation is idempotent. Rollback and identity substitution are never allowed.

## 8. Consumption and supersession arbitration

The predecessor decision slot is:

`authorization-decisions/{predecessor_authorization_identity}.json`

That one exclusive immutable record is either `consume` or `supersede`, never both. Consumption and supersession race only for that predecessor-owned path. The winner is the first exact decision reaching file `F_FULLFSYNC`, successful close, and parent-directory fsync. An existing conflicting record loses and rejects. An uncertain write becomes indeterminate; it is never deleted, replaced, or treated as a new opportunity.

After a consume decision, the matching claim is written under:

`consumption-claims/{predecessor_authorization_identity}.json`

After a supersede decision, the matching edge is written under:

`supersessions/{predecessor_authorization_identity}.json`

The successor later uses its own independent decision slot:

`authorization-decisions/{successor_authorization_identity}.json`

Therefore a predecessor supersession marker cannot block successor consumption. Consumption and supersession cannot both validly succeed because the predecessor owns exactly one exclusive decision. A successor must preserve run, fixture, manifests, dataset, command, V004, source commit, and source tree bindings; obtains new approval and time evidence; names exactly one predecessor; and is the unique outgoing edge chosen by the predecessor decision.

Only `active_unconsumed` can be superseded. Expired, rejected, claiming, consumed, already superseded, stale, missing, forked, duplicate, and cyclic predecessors reject. Chains allow one incoming and one outgoing edge and are walked for cycles. Multiple successor proposals are harmless: only the successor named in the durable predecessor decision may publish.

### Arbitration race matrix

| Condition | Result |
|---|---|
| Neither exclusive create reached | Retry while still valid |
| Consume decision durable first | Consumption wins; supersession rejects |
| Supersede decision durable first | Supersession wins; consumption rejects |
| Both claimed durable | Integrity failure; impossible under valid exclusive create |
| Crash before exclusive create | No state change; retry same identity |
| Crash after create, before durability | Indeterminate; recovery only |
| Crash after durable decision, before follow-up | Reconcile exact decision and complete its matching follow-up |
| Duplicate identical retry | Verify same bytes and durability only |
| Conflicting retry | Reject |
| Multiple successors | Only durable decision’s successor may publish |
| Successor consumes later | Uses successor-owned decision path; predecessor path is irrelevant |

## 9. Terminal and archive exclusivity

A successful terminal has state `run_succeeded`, one non-null result manifest, one or more exact result identities, null failure identity, null failure details, and no failure artifact. A failed terminal has state `run_failed`, one non-null resolved failure identity and details, null result manifest, an empty result list, and no result artifact.

Archive state and all result/failure projections must equal the terminal exactly. A completion marker binds the archive, run, authorization, and terminal state. Every invalid cross-product rejects. Indeterminate records assert neither success nor failure and contain only known durable identities, uncertain operation, and recovery restrictions.

## 10. Pure raw Git documentary proof

The validator trusts no caller-supplied object ID without recomputation. The review bundle supplies:

- exact canonical authorization bytes;
- raw tree objects for every component of the authorization path;
- raw commit A bytes;
- exact canonical documentary-binding bytes;
- raw tree objects for every component of the binding path;
- raw commit B bytes and its expected object ID.

The validator reconstructs Git object framing and computes SHA-1 blob, tree, commit A, and commit B IDs. Every tree step verifies raw bytes, mode (`40000` for trees, `100644` for files), component name, type, and child ID. Commit A must have exactly one parent—the authorized source commit—and its tree must contain the exact authorization blob. Commit B must have exactly one parent—commit A—and its tree must contain the exact binding blob.

Commit B’s ID is deliberately not a field inside the binding that commit B contains. It is supplied in the external review proof and checked against raw commit B, avoiding a new self-reference. The binding freezes repository identity, SHA-1 object format, path, authorization blob/tree/commit A, and authorized source parent. Wrong repository, object format, path, mode, content, parent count, object byte, final LF, or one-byte mutation rejects. Only the earlier authorized source commit is executable; documentary commits A and B never execute.

## 11. APFS path and durability evidence

The future consumer supports one macOS host and local APFS only. The typed filesystem record attests APFS subtype, local/nonremovable/non-network/non-overlay/non-FUSE/non-disk-image mount, device and mount IDs, exact owner UID/group GID, directory mode 0700, file mode 0600, umask 0077, no ACLs, xattrs, file flags, symlinks, cross-device traversal, or hard links (`st_nlink == 1`). Case-sensitive and case-insensitive APFS are accepted only as attested, and case-colliding paths reject.

Root acquisition begins from a trusted preopened parent and uses descriptor-relative `openat` with `O_DIRECTORY|O_NOFOLLOW`. Every intermediate directory is opened and verified by descriptor. Leaves use `O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW`. Realpath strings are never authority.

Files require `F_FULLFSYNC`, successful close, then directory fsync. Directories require fsync; parent publication requires parent fsync. Unsupported `F_FULLFSYNC`, any error, device change, reordered trace, or missing durability event becomes indeterminate. The V005 validator verifies only typed synthetic syscall/fault traces and implements none of these operations.

## 12. Archive publication and recovery

Archive operation has three explicit modes:

1. `first_publication`: destination must not exist; staging and every file are exclusive.
2. `authorized_recovery`: destination is incomplete and an immutable recovery record grants only missing-byte completion.
3. `verify_complete`: destination and durable marker already exist; validation is read-only and idempotent.

Files are written to a unique staging directory, fully synced and closed, the staging directory is synced, and exclusive rename publishes the destination. Manifest bytes are written and synced, followed by the completion marker, destination fsync, and parent fsync. Readers accept only a durable marker plus a complete exact manifest and byte hashes.

Recovery may add only missing bytes equal to the frozen intended canonical bytes. Existing identical bytes are reused; conflicting bytes, replacement, truncation, unexpected files, unauthorized recovery, or marker-with-incomplete-archive reject. A durable archive missing only its marker can receive that marker through authorized recovery. A complete archive with marker is verification-only.

### Archive crash matrix

| Crash state | Allowed action |
|---|---|
| Before destination exists | Retry first publication |
| Partial staging | Authorized exact-byte recovery or reject |
| Destination exists without marker | Authorized recovery or indeterminate |
| Complete durable archive without marker | Authorized recovery may add marker |
| Marker exists but content incomplete/conflicting | Indeterminate and reject |
| Complete content and durable marker | Verify only; no write |

## 13. Failure handling and future implementation boundary

Malformed, missing, unresolved, cross-version, stale, contradictory, nondurable, unsupported, or uncertain evidence fails closed. Uncertainty never authorizes execution and never makes an authorization reusable. Recovery is an immutable record with a distinct attestation and narrow action; it cannot delete or replace bytes.

A later implementation milestone must implement the consumer exactly as frozen and undergo independent adversarial review before any authorization is created. That later code must perform the real GitHub direct-origin evidence capture, Git review evidence capture, detached-checkout inspection, APFS system calls, decision arbitration, lifecycle writes, and archive transaction. None exists in this PR.

## 14. Validation commands

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_authorization_governance_v005.py --root .
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_authorization_governance_v005.py
```

The report must state 31 artifact schemas, 20 transitions, no authorization, no execution capability, no official authorization, and no official execution.
