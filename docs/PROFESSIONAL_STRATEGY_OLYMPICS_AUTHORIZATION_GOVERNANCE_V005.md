# Professional Strategy Benchmark Olympics V005 authorization governance

Status: `DESIGN_ONLY_V005_CORRECTED_AUTHORIZATION_NOT_CREATED`

This prospective contract freezes the authorization layer needed after V004. It does not authorize a run, create or consume an authorization, build protected inputs, contact GitHub, or implement an Olympics runner. The machine source is `config/professional_strategy_olympics_authorization_governance_v005.json`; this document explains the same rules without adding alternatives.

## 1. Threat model

V005 defends against identity substitution, local-clock substitution, self-approval, mutable evidence, authorization replay, concurrent consumption or supersession, checkout drift, path traversal, symlink/hard-link/special-file substitution, partial or uncertain writes, archive overwrite, and a documentary commit accidentally becoming executable source. Unknown fields, unknown states, unverifiable evidence, and unsupported platforms fail closed.

The contract does not defend against a compromised GitHub TLS endpoint, kernel, filesystem implementation, root user, or physical host. It does not prove universal absence of credentials or network access. It proves only the declared observations inside the frozen trust boundary.

## 2. Trust assumptions

- Time trusts one authenticated TLS exchange with `https://api.github.com:443`. HTTPS Date evidence is not independently non-repudiable.
- Git object IDs and SHA-256 are assumed collision resistant.
- The future operator controls one local APFS host and the protected store root and its parent.
- GitHub stable numeric user IDs are the equality key. Login is normalized lowercase display metadata only.
- The future implementation correctly obtains OS file descriptors, stat data, filesystem type, owner, mode, and durability errors.

## 3. Non-goals and boundary

There are no live APIs, credentials, data downloads, strategy evaluations, rankings, scores, winners, broker operations, validation access, or holdout access in V005. The future implementation must be a separate reviewed milestone. V004 and all earlier identities remain unchanged.

## 4. Canonical form and identities

All structured records use RFC 8259 JSON with lexicographically sorted object keys, compact separators, NFC strings, strict UTF-8, no BOM, duplicate keys, non-finite values, or unknown fields, and exactly one final LF. Every schema field is present. Nullable fields use JSON `null`; omission, empty-string sentinels, and sentinel objects are forbidden.

For artifact type `T`:

`identity(T) = SHA256(UTF8(domain(T)) || 0x00 || canonical_json(record without only its self-identity field))`

The authorization proposal identity similarly excludes exactly `authorization_identity` and `approval_evidence_identity`, preventing an approval/authorization fixed-point. The governance identity excludes only `contract_identity`. The command identity excludes only `command_identity`. All other values remain included.

- Governance domain: `aml.olympics.v005.governance`
- Governance identity: `fe8708b38c8966f6db42c3b59a99103aae750b8c440e7f133e2e8aaecdfb7b88`
- Command domain: `aml.olympics.v005.command`
- Command identity: `ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb`
- Hash: SHA-256
- Domain separator: one NUL byte
- Serialization terminator: one LF, included in the hash

The JSON contract freezes distinct domains for authorization, proposal, approval, clock request, clock evidence, clock attestation, operator identity, roles, access evidence, environment, source checkout, store, claim, documentary binding, supersession, terminal lifecycle, and archive. Filenames never provide type separation.

## 5. Schema language and primitive limits

The contract’s `schema_language` is executable: `literal`, `enum`, `identity`, `nullable`, named primitive, and bounded `array` rules are the only forms. Its `primitives` section freezes types, ranges, encodings, regexes, normalization, and byte limits. JSON booleans never satisfy integer rules. Schema records freeze exact field sets, paths, domain, self-identity field, and immutable status.

## 6. Artifact inventory and exact field sets

The authoritative field rules are the `artifact_schemas` map. The exact fields are summarized below; no additional field is allowed.

| Artifact | Schema/version | Exact fields |
|---|---|---|
| Clock attestation | `aml.professional-strategy-olympics.clock-attestation.v005` | schema_version, attestation_identity, github_api_origin, https_authority, request_method, request_target, request_identity, request_nonce, response_status, response_date_as_received, canonical_utc_timestamp, observation_timestamp, evidence_byte_identity |
| Human approval | `aml.professional-strategy-olympics.human-approval.v005` | schema_version, approval_evidence_identity, authorization_proposal_identity, author_identity, reviewer_identity, approval_action, approval_timestamp, clock_attestation_identity, reviewed_source_commit, reviewed_source_tree, reviewed_governance_identity, reviewed_command_identity, review_platform, review_object, review_reference |
| Authorization | `aml.professional-strategy-olympics.single-use-authorization.v005` | schema_version, authorization_identity, approval_evidence_identity, authorization_author_identity, reviewer_identity, operator_identity, authorized_source_commit, authorized_source_tree, authoritative_run_identity, V004 identities, V005 governance identity, fixture/manifest/projected V001 identities, command identity, entry point, argv, clock identity, issued/expires timestamps, environment/source/store/access identities, predecessor/superseded identities, documentary_binding_required, creation_state, maximum_execution_count |
| Documentary binding | `aml.professional-strategy-olympics.documentary-binding.v005` | schema_version, documentary_binding_identity, authorization_identity, authorization_relative_path, authorization_blob_oid, documentary_authorization_commit, documentary_authorization_tree, documentary_parent_commit |
| Operator identity | `aml.professional-strategy-olympics.operator-identity.v005` | schema_version, operator_identity, github_user_id, github_login, account_kind |
| Role assignment | `aml.professional-strategy-olympics.role-assignment.v005` | schema_version, role_assignment_identity, governance/source/authorization author identities, reviewer, operator, archive custodian, previous operator, superseding author |
| Access prohibition | `aml.professional-strategy-olympics.access-prohibition.v005` | schema_version, access_prohibition_identity, operator_identity, prohibited resources/credential names/filesystem roots/network destinations, permitted exceptions, inspected environment names/filesystem roots/network configuration, observation method, status |
| Environment | `aml.professional-strategy-olympics.environment-manifest.v005` | schema_version, environment_manifest_identity, OS, architecture, Python version, package-lock identity, locale, timezone, hash seed, working-directory policy, environment allowlist |
| Source checkout | `aml.professional-strategy-olympics.source-checkout.v005` | schema_version, source_checkout_manifest_identity, repository, commit, tree, detached status, null branch, index/worktree cleanliness, untracked policy, submodule status, symlink policy, root treatment |
| Consumption store | `aml.professional-strategy-olympics.consumption-store.v005` | schema_version, store_manifest_identity, store type facts, canonical root, filesystem type, single-host/local-only flags, coordination primitive, modes, umask, owner UID |
| Consumption claim | `aml.professional-strategy-olympics.consumption-claim.v005` | schema_version, claim_identity, authorization/operator/source/tree/clock/store identities, consumed_at, prior state |
| Supersession | `aml.professional-strategy-olympics.supersession.v005` | schema_version, supersession_identity, predecessor/successor identities, superseding author, approval, clock, timestamp, reason |
| Terminal lifecycle | `aml.professional-strategy-olympics.lifecycle-terminal.v005` | schema_version, lifecycle_terminal_identity, authorization/run/operator/clock identities, terminal timestamp/state, nullable result and failure identities |
| Archive | `aml.professional-strategy-olympics.archive-manifest.v005` | schema_version, archive_identity, authorization/claim/source/tree/run/terminal/operator/clock identities, timestamp, destination, result identities, nullable failure identity |

Every record is write-once. A correction creates a new identity under the frozen supersession rules; it never edits published bytes.

## 7. Trusted-time protocol

The request bytes are exactly:

```text
HEAD /rate_limit HTTP/1.1\r\n
Host: api.github.com\r\n
X-GitHub-Api-Version: 2022-11-28\r\n
Connection: close\r\n
\r\n
```

The scheme is HTTPS, host `api.github.com`, port 443, method `HEAD`, target `/rate_limit`, no query, no nonce, no redirect, and status 200. Request identity is SHA-256 of the clock-request domain, NUL, and these raw bytes. The response header block is preserved as ASCII CRLF bytes through the terminating CRLFCRLF. Header spelling and values remain raw; verification treats names case-insensitively only to require exactly one Date header, and removes exactly one optional space after the colon before parsing.

Date must be IMF-fixdate ending `GMT`, at whole-second precision. Evidence identity hashes a canonical record containing raw Date line, status line, SHA-256 of request bytes, and SHA-256 of the raw header block. The attestation binds request and evidence identities, received Date, parsed UTC timestamp, and observation timestamp. Observation and parsed Date are equal: skew tolerance is zero.

`authorization.issued_at = attestation.canonical_utc_timestamp`

`authorization.expires_at = issued_at + 259200 seconds`

Execution is valid exactly when `issued_at <= execution_attestation_time < expires_at`. Missing, duplicate, stale, future, local-clock, non-GMT, altered, redirected, incomplete, or mismatched evidence rejects.

## 8. Human approval and identity evidence

Only canonical GitHub `APPROVED` review evidence on the reviewed source, tree, governance, command, and authorization proposal is accepted. Comments, reactions, informal prose, mutable URLs, and self-attestation are not approvals. The record stores the PR number and stable review database ID. A changed proposal, source, or command needs a new approval.

Human accounts only are allowed. Numeric GitHub user ID controls equality across login case changes or account renames. Bots, organizations, deleted accounts, zero IDs, and unknown identities reject.

## 9. Role-separation matrix

Unlisted pairs reject. `must differ` compares numeric GitHub user ID.

| Pair | Rule |
|---|---|
| authorization author / reviewer | must differ |
| authorization author / operator | must differ |
| reviewer / operator | must differ |
| source author / reviewer | must differ |
| source author / operator | must differ |
| archive custodian / operator | must differ |
| governance author / reviewer | must differ |
| governance author / operator | must differ |
| superseding authorization author / previous operator | must differ |
| authorization author / governance author | may match |
| authorization author / source author | may match |
| authorization author / archive custodian | may match |
| governance author / source author | may match |
| governance author / archive custodian | may match |
| reviewer / archive custodian | may match |
| source author / archive custodian | may match |

## 10. Access-prohibition evidence

The record proves only that the future implementation inspected the declared environment names, declared filesystem roots, declared process network configuration, and its enforced allowlist at observation time. It does not prove universal absence outside those scopes. Any prohibited item observed, uninspected declared scope, non-offline runtime, unknown exception, or missing evidence rejects.

## 11. Source and environment evidence

Execution requires exact source commit/tree, detached HEAD, null branch, empty porcelain status including untracked files, clean index/worktree, absent submodules, no symlinks, and the fixed origin URL. The absolute checkout root is not hashed; its policy and source identities are. The environment binds macOS, allowed architecture, exact Python semver, package-lock identity, `C` locale, UTC, hash seed 0, detached-root working directory, and a sorted allowlist. Volatile hostnames, process IDs, and temporary names are excluded.

## 12. Non-circular documentary binding

Authorization bytes cannot contain the commit that contains those same bytes. V005 therefore uses two commits:

1. Commit A has exactly the authorized source commit as its sole parent and adds the canonical authorization at `authorizations/{authorization_identity}/authorization.json`. Commit A is documentary only.
2. Commit B is the direct child of A and adds the binding record. That record binds the authorization identity/blob/path, commit A, tree A, and the authorized source parent.

Authorization and approval avoid their own cycle by having approval bind the proposal projection, while final authorization binds approval evidence. A verifier recomputes proposal, approval, authorization, Git blob, tree, and commits. Only the earlier authorized source commit/tree executes. Neither A nor B may execute, and their addition cannot alter the bound source tree.

## 13. Lifecycle state machine

The JSON transition table is authoritative. Every transition freezes source, target, actor, trigger, evidence, atomic write, timestamp source, retry, idempotency, rollback (`false`), and terminal status.

```text
proposed -> approved -> active_unconsumed -> claiming -> consumed
  -> build_started -> run_started -> run_succeeded|run_failed
  -> archive_pending -> archived
active_unconsumed -> superseded|expired
any uncertain durability boundary -> indeterminate
```

Only the twenty listed transitions are permitted. There is no consumed-to-active transition. Rejection and indeterminate are terminal. A later build, run, or archive failure never restores authorization usability.

## 14. Atomic consumption and concurrency

V005 supports exactly one host and one local APFS filesystem. Network filesystems and cross-host operation reject. Consumption and supersession share `run-locks/{run_identity}.json`. Exclusive creation itself—not check-then-create—is arbitration.

The future implementation opens a validated directory FD and uses relative `openat` with `O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW`, mode `0600`, under mode-`0700` directories and umask `0077`. It writes all canonical bytes with EINTR handling, verifies the byte count, checks regular type/owner/mode/device/link count one, fsyncs the file, closes successfully, and fsyncs the parent. It repeats this for the claim. Only after both directory durability points may state become consumed and protected build begin.

`EEXIST` means already claimed. Symlinks, hard links, special files, wrong owners/modes/devices, partial writes, close/fsync failures, or uncertain durability fail closed. Partial or orphaned records are never deleted or replaced; only identical-byte durability reconciliation is allowed. Exactly one local process/thread winner is possible. There is no cross-host claim.

## 15. Crash recovery

- Before exclusive arbitration: no state change; retry may be allowed while authorization remains valid.
- During or after arbitration but before parent fsync: indeterminate, non-runnable, no new claim.
- After durable claim: authorization remains consumed forever, even if build never starts.
- During build/run: write immutable failure or mark indeterminate; no new consumption.
- After terminal state but before archive: archive pending; repair only archive.
- During archive: readers reject until durable complete marker; repair only missing identical bytes.
- Uncertain complete-marker or directory fsync: indeterminate archive; authorization still consumed.

## 16. Path security

Roots are absolute NFC UTF-8 POSIX paths, at most 1024 bytes, owned by the declared UID, mode `0700`, and local APFS. Relative components are 1–128 bytes of lowercase ASCII letters, digits, dot, underscore, or hyphen; dot/dot-dot, empty components, slash, backslash, colon, NUL, drive paths, UNC paths, alternate separators, and paths over 1024 bytes reject.

The future implementation opens the trusted root once with `O_DIRECTORY|O_NOFOLLOW`, then walks only through directory FDs with `openat`, validating owner, mode, device, type, and no symlink at every component. Leaf creation uses exclusive relative open and post-open `fstat`. No descendant device crossing is allowed. `realpath` alone is never evidence because it does not prevent parent replacement races.

## 17. Supersession

The first authorization has `previous_authorization_identity: null`. Supersession is a linear chain with one predecessor and one successor; forks, cycles, missing links, and multiple active authorizations reject. Only active-unconsumed, expired, or rejected-unused predecessors are eligible. Consumed authorizations cannot be superseded.

The successor preserves run, fixture, manifest, command, V004, and source bindings, obtains a new clock and independent approval, and identifies the predecessor. Supersession and consumption race on the same exclusive run arbitration file. The first fully durable arbitration record wins; the loser rejects. The superseding author must differ from the previous operator.

## 18. Write-once archive transaction

Success and failure runs both archive. The custodian exclusively creates `archives/{run_identity}`, writes each canonical file with exclusive no-follow open, verifies/hash-checks/fsyncs each file, fsyncs the directory, then exclusively creates `archive.complete` and fsyncs marker, directory, and parent. Readers accept only a durable marker plus matching manifest/data identities.

An existing destination or overwrite attempt rejects. A partial archive enters archive-pending or indeterminate. Recovery may add only missing bytes that exactly match the frozen manifest; it never replaces. Success archives require results and no failure identity. Failed-run archives require a failure identity. Archive failure never makes authorization reusable.

## 19. Rejection taxonomy

- `schema`: missing/unknown fields, wrong primitive, invalid null, bounds, Unicode, JSON, or identity.
- `clock`: unsupported origin/request/status/Date, redirect, mismatch, stale/future/expired evidence.
- `lineage`: source/tree/V004/governance/command/checkout mismatch.
- `approval`: absent, wrong action/object/source/proposal, self-approval, or role collision.
- `path`: traversal, injection, link, device, mount, owner, mode, or containment failure.
- `claim`: existing, partial, malformed, nondurable, wrong store/operator/source, or replay.
- `state`: unlisted transition, rollback, post-consumption reuse, or uncertain recovery.
- `supersession`: ineligible predecessor, fork, cycle, race loss, identity or role mismatch.
- `archive`: existing destination, mismatch, partial write, nondurable marker, or overwrite.

All categories are fail-closed and emit no protected artifact.

## 20. Future implementation obligations

A later PR must implement the frozen GitHub evidence capture, role verification, detached checkout inspection, APFS/root inspection, exclusive/durable claim, lifecycle store, supersession arbitration, and archive transaction exactly. It must add fault injection for partial writes, file/directory fsync and close failures, concurrent processes, parent replacement, hard links, special files, network filesystems, crash boundaries, and archive recovery. It must not silently broaden platform support.

This PR remains design, schema, pure validation, synthetic tests, and documentation only. No real authorization or Olympics execution is permitted by it.

## Validation

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_authorization_governance_v005.py --root .
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_authorization_governance_v005.py
```

The report must say authorization false, execution capability false, official authorization false, and official execution false.
