# Professional Strategy Olympics Runtime Boundary V007

Status: `DESIGN_ONLY_V007_RUNTIME_BOUNDARY_VALID_NO_RUNTIME_CAPABILITY`

V007 is an additive design contract. It resolves the runtime ambiguities found
after V006 was merged, but it does not implement an operator, clock verifier,
repository attestor, authorization, or Olympics execution path.

## Why V007 is required

V005 freezes authorization and lifecycle evidence, while V006 freezes the
operator-facing package, projection, and external-trust concepts. A hostile
implementation audit found two remaining gaps:

1. V006 listed clock-bootstrap fields without freezing their types, schema
   literal, identity projection, RPC envelopes, or one socket-acquisition
   model.
2. V005 repository context has no timestamp, nonce, attestor, implementation,
   validity, or replay fields. V006 therefore correctly made no freshness
   claim, but a future operator could not reject stale or replayed operational
   attestations.

Implementing around either gap would invent security behavior. V007 freezes
only that missing boundary. V005 and V006 remain byte-for-byte unchanged.

## Inheritance and precedence

V007 inherits the exact V005 command and identities and references V006. It
supersedes V006 only for runtime-package records, clock bootstrap and RPC,
socket acquisition, replay registries, repository operational attestation, and
future operator-implementation binding. Every unaffected V006 rule remains
normative. V007 adds no authority and no lifecycle state.

## Canonical model and identities

All V007 JSON is canonical UTF-8 JSON with sorted keys, compact separators,
ASCII escapes, NFC strings, integers only, and exactly one trailing LF.
Duplicate keys, floats, NaN, infinity, BOM, CRLF, pretty JSON, invalid UTF-8,
non-NFC text, leading data, and trailing data reject.

Record identities are:

`SHA256(UTF8(domain) || 0x00 || canonical projection bytes)`

The projection excludes only the record's declared self-identity field. The
outer contract and fourteen security-critical sections have independently
frozen identities. Every field in every section is therefore covered by both
its section identity and the outer identity.

The canonical contract is 35,616 bytes. Its domain is
`aml.olympics.v007.runtime-boundary` and its identity is
`a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45`.
The section identities are:

| Section | Identity |
| --- | --- |
| inheritance | `aa9f200c0c4fce52ab25cf566be73c03e3fc8a8334ea86a0b8c4924c34ec556a` |
| capability_scope | `1c6463c621a47b686b3f1468a5a535ff0518806b9d8e73b06e3267bf8caf2de9` |
| canonicalization | `e866c4636b955e9c1156ff2a929e31b5395f5e5b8ffba468b22d29826a2e0ddc` |
| runtime_package | `0309811ffcde9b453c75c96637ac590eb71dc42140f04c988dbd9ae326ea182e` |
| runtime_schemas | `4e82fd2b0cf99efce8c053f10eb673581c77d46aa7dde70b3675c99f7bca962a` |
| socket_transport | `2e26ee2e18b04dd2b42d42cbe1e1baddb63e403c1c5acdcdb72f406e14ac14f6` |
| peer_identity | `32400675c1a769a12b272c47ef2189c22cdff32455c8707916d35d0fb1d72823` |
| clock_session_replay | `6b91e36fa8ab327dc030cc9d479fad8c5933c8660c0daaee871b57b7a69793ed` |
| repository_freshness_replay | `b39aec2006aceed475d174af5d6693264e44d505a3e46a762664032453ede98b` |
| repository_trust | `c83aa57a1890ac9c364115d0e8129ac036daad01d18b78050cc0d0624524ce9a` |
| runtime_identity_binding | `03e1a35687b841aaddb1bf5742547f0bbf915b46e6fdbc17931cf42464b6453e` |
| cross_version_binding | `478fd9e7eab006a11b1ab259068a57ae7cd597e0941d1e80d026c20d4362e4da` |
| error_status_model | `330ff6bede7cedda5fe28fccd9324d0fef0ecd7641d0ad00d14b1e0724b40847` |
| validation_manifest | `495b81c9ad1cd3717315b472c33ddaf4775ac9a3665fa0d3b4b0ddcbc226320c` |

## Runtime package

The sealed package has one unindexed, self-identifying
`runtime_package_v007.json` root. Excluding the package from its own index
avoids an impossible self-hash cycle. Its supplemental index covers exactly
the V007 records by type, identity, canonical-byte digest, relative path, and
schema version. It never duplicates V005 or V006 entries.

The V007 package and runtime envelope both bind one exact dynamic V006 operator
package identity. V006 remains the sole owner of the authorization,
documentary-binding, and complete V005 transition closure. A real package is
the disjoint union of the V006-accepted closed world and the exact V007 files;
path overlap, a second package, or any mismatched authorization, run, source,
tree, or V006-package identity rejects.

The package permits exactly the inherited V005/V006 files, canonical V005
artifact paths reachable from one transition envelope, and these V007 files:

- `authorizations/{authorization_identity}/runtime_package_v007.json`
- `runtime/{authorization_identity}/clock_bootstrap.json`
- `runtime/{authorization_identity}/clock_registry_initialization.json`
- `runtime/{authorization_identity}/clock_replay_registry.json`
- `runtime/{authorization_identity}/clock_requests/repository_request.json`
- `runtime/{authorization_identity}/clock_requests/repository_response.json`
- `runtime/{authorization_identity}/clock_responses/repository_request.json`
- `runtime/{authorization_identity}/clock_responses/repository_response.json`
- `runtime/{authorization_identity}/repository_replay_registry.json`
- `runtime/{authorization_identity}/repository_registry_initialization.json`
- `runtime/{authorization_identity}/repository_request.json`
- `runtime/{authorization_identity}/repository_response.json`
- `runtime/{authorization_identity}/runtime_envelope.json`

The runtime envelope is the single V007 graph root below the package. It binds
the authorization, source commit and tree, authoritative run, future operator
implementation, bootstrap, repository request and response, both replay
registries, and the one V005 transition envelope.

Unknown, hidden, empty, duplicate, orphaned, unindexed, path-escaping,
symlinked, hard-linked, device, socket, FIFO, mount-crossing, and case-colliding
package entries reject. Reads are descriptor-relative and mutation is checked
before, during, and immediately before claim. The operator never modifies the
sealed package.

## Clock bootstrap and transport

The bootstrap has one exact schema, field set, type system, identity domain,
self-exclusion rule, protocol version, verifier identity set, limits, timeout
set, session policy, and failure policy.

Its four initial V005 clock identities must each resolve exactly once inside
the exact bound V006 package and pass the exact V005 clock-bundle validator
against the one reachable activation artifact, using event type `activation`
and timestamp field `activated_at`. Bare, substituted, cross-package, or
incomplete bootstrap hashes cannot establish the initial clock state. The
initial V005 request nonce must already be durably registered in the bound
clock-registry epoch and be distinct from every V007 session, request, and
evidence nonce.

V007 selects path-based `AF_UNIX/SOCK_STREAM` exclusively. An inherited file
descriptor is prohibited because the frozen V005 argv has no descriptor
argument. The external verifier creates the socket before operator start. The
operator validates the parent and endpoint with `lstat`, connects once, and
verifies that the path's device, inode, ownership, mode, and type remain equal
after connection.

There is one connection per authorization invocation and multiple strictly
sequenced request/response pairs on that connection. Reconnect is prohibited.
A verifier restart invalidates the session and requires formal authorization
supersession. A partial failure rejects before claim and uses the matching V005
indeterminate route after claim.

Frames are a four-byte unsigned big-endian payload length followed by exactly
that many canonical JSON bytes. Empty, oversized, unsolicited, incomplete, or
malformed frames reject. Reads and writes loop only until the declared frame is
complete or the frozen deadline expires.

## macOS peer identity

The only supported peer mechanism is `getpeereid(3)` on the connected Unix
socket. Both effective UID and effective GID must match the bootstrap. macOS
does not provide a reliable peer PID through this primitive, so V007 neither
requires nor claims one.

Peer credentials identify an operating-system account, not verifier code.
Verifier service and implementation identities remain separately bound in the
bootstrap and every response. Unsupported platforms fail closed.

## Clock RPC and replay

The request envelope binds the authorization, run, operator implementation,
verifier service, session, exact sequence, unique request nonce, V005
transition, timestamp field, and canonical V005 event projection.

The response envelope binds the request and nonce, unique evidence nonce,
verifier actor/service/implementation, session and sequence, timestamps,
status, deterministic failure code, replay-registry result, and—on success—the
four complete canonical V005 clock records.

Success requires all four V005 records and durable unique registry writes.
Failure and indeterminate responses prohibit those payloads. Verification must
complete within five seconds. Verified time cannot precede the prior accepted
time or follow completion time.

On success, the embedded V005 request nonce is the V007 response evidence
nonce, its verifier account is the bootstrap system account, and its
attestation's event projection and timestamp equal the exact V007 request and
response. Registered V005 events also retain the request's artifact type and
timestamp field. The two V007-only repository records use the exact frozen V005
compatibility carrier `activation` / `activated_at`, because V005 cannot name
later record types; only the V007 envelope types those events. A valid V005
bundle for another event cannot satisfy a V007 clock exchange.

Session, request, and evidence nonces are unique across nonce types within one
bound external-verifier registry epoch. Its atomic operation is exclusive creation,
`F_FULLFSYNC`, close, and parent-directory fsync. A collision is replay. A
registry-write failure is indeterminate and cannot produce success.

Each registry record binds a pre-existing independently reviewed initialization
record and epoch to its root, service, implementation, UID, GID, modes, and
filesystem. The exact canonical initialization record must already exist at
`registry_epoch_v007.json` below that root, with the frozen exclusive-creation,
durability, ownership, no-link, and mutation checks. A copy is indexed in the
sealed runtime package. Runtime creation, replacement, or reinitialization is
prohibited. Local APFS cannot cryptographically detect offline deletion,
rollback, or restoration from backup; V007 therefore makes no such claim. Any
uncertainty about epoch continuity is
`V007_REGISTRY_CONTINUITY`, an indeterminate condition that prohibits success.

Sequence zero names the bootstrap's initial V005 clock-attestation identity as
its prior attestation. Every later request names the V005 clock-attestation
identity carried by the immediately preceding successful response. Sequence
gaps, rollback, failed predecessors, cross-type nonce reuse, and chain
substitution reject. The embedded V005 bundle is validated under V005. The
V007 response binds that trusted timestamp to the V007 event; the V005
attestation does not claim to type a V007 artifact.

## Repository attestation

The request binds the authorization, source-root path, repository name, source
commit and tree, required path/blob bindings, parent graph, future operator
implementation, command, V004–V007 identities, manifest, orchestrator, unique
nonce, requester, and a matching V007 clock response containing a valid V005
clock bundle.

The response binds the exact request and nonce, a unique attestation nonce,
attestor actor/service/implementation, replay registry, observed Git and
worktree facts, source-root observation, a second matching V007 clock response,
validity interval, status, and deterministic failure code. The V007 event
projection excludes the record self-identity, timestamp, and two clock-envelope
identities, preventing an identity cycle while preserving every substantive
repository claim.

Successful attestations are valid for exactly 300 seconds in a half-open
window. They are single-use pre-claim evidence, do not survive an operator
restart, and are invalidated by source-root replacement or remount. Attestor
restart is permitted only with the same implementation identity and proven
durable-registry continuity.

The attestor may report local Git objects, commit graph, tree, paths, blobs,
configured origin text, worktree/index cleanliness, and filesystem
observations. It cannot authenticate GitHub ownership, GitHub account identity,
TLS, human identity, host kernel, physical disk reality, or remote freshness.
The response must list those non-claims exactly; unsupported claims reject.

## Future operator identity

V007 avoids a commit/self-reference cycle with a two-stage identity:

1. The future implementation identity hashes an exact manifest projection and
   a UTF-8-sorted inventory of every tracked regular file, its Git mode, and
   SHA-256 of its raw bytes.
2. Only the future manifest itself is excluded from that inventory. Symlinks,
   gitlinks, submodules, missing files, untracked files, external project code,
   and modes other than `100644` and `100755` reject.
3. After implementation merges, an authorization separately binds the final
   commit, tree, and implementation identity.
4. The attestor recomputes file and implementation identities from the
   authorized tree; the operator recomputes from `O_NOFOLLOW` file descriptors
   before validation and immediately before claim.

The two required entry points are:

- `scripts/run_professional_strategy_olympics_v005.py`
- `src/aml/professional_strategy_olympics_operator_v001.py`

## Stable failures

V007 freezes stable `V007_*` codes for schema, identity, transport, frame,
peer, timeout, verifier, replay, nonce, freshness, rollback, repository,
attestor, reachability, implementation, and registry failures. Every code maps
to pre-claim rejection, validation failure, or V005 indeterminate handling.
V007 adds no recovery or terminal state outside V005.

Diagnostics are canonical, sorted, path-safe, and contain no exception
representations, credentials, uncontrolled absolute paths, or host-time values.

## Pure verification

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_runtime_boundary_v007.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_runtime_boundary_v007.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests scripts
git diff --check
```

Independent identity reproduction uses the same byte equation without importing
the V007 module:

```bash
python3 -c 'import hashlib,json,pathlib; p=pathlib.Path("config/professional_strategy_olympics_runtime_boundary_v007.json"); v=json.loads(p.read_text()); cb=lambda x:(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)+"\n").encode("ascii"); print(len(cb(v))); print(hashlib.sha256(b"aml.olympics.v007.runtime-boundary\0"+cb({k:x for k,x in v.items() if k != "contract_identity"})).hexdigest())'
(printf 'aml.olympics.v007.runtime-boundary\0'; jq -cS 'del(.contract_identity)' config/professional_strategy_olympics_runtime_boundary_v007.json) | shasum -a 256
```

Both independent commands must reproduce the frozen outer identity above.

The validator only parses, hashes, and validates supplied values. It opens no
socket, performs no attestation, creates no authorization, consumes no claim,
and invokes no Olympics code.

## Remaining sequence

After independent audit and merge of V007:

1. Implement and independently audit the V005 operator against V006/V007.
2. Implement and independently audit the external clock verifier.
3. Implement and independently audit the repository attestor.
4. Complete integrated readiness verification.
5. Construct and independently approve one exact authorization package.
6. Execute exactly one authorized synthetic Olympics run.
7. Verify write-once publication and complete archival.

Synthetic results remain non-economic and non-performance evidence.
