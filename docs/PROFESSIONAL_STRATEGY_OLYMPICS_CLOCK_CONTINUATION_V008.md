# Professional Strategy Olympics Clock Continuation V008

Status: `DESIGN_ONLY_V008_CLOCK_CONTINUATION_VALID_NO_RUNTIME_CAPABILITY`

V008 is a narrow additive successor to V007. It freezes only the nonce authority,
live-session continuation, durable evidence, replay, interruption, and recovery
semantics needed for sequence 2 and later. V004, V005, V006, and every unrelated
V007 rule remain unchanged.

V008 implements no operator, verifier, attestor, authorization, execution, result,
publication, archive, data access, network client, or trading capability.

## Identity

The canonical contract is `24,335` bytes. Its identity equation is:

`SHA256(UTF8(domain) || 0x00 || canonical_projection_bytes)`

The outer domain is `aml.olympics.v008.clock-continuation` and the frozen identity is:

`4d3a3c7a2690decfd275b91fe80fee497953795d086a9c191480eb1ac688cda5`

| Section | Identity |
| --- | --- |
| inheritance | `940c5e590ba1bcd471710304f85db8f9cac7fe8947017f6e4b7449a198f0098a` |
| nonce_authority | `40b41062b862810c8703fd6a85d715369fd100209580748aa7234bf8321e1d07` |
| packaged_history | `58f62c0b9f8349e37bd431885d328dcd1d930e100a43209aae473f0ae9868cbc` |
| live_session | `42e55f9c8c978a2af8e8157ea1b3df2e5a698e3f6435e8a08d1cd5e35e1e0389` |
| continuation_storage | `ad7cc2b06f7ac67e4fafa9fbe99689aba3592fdec1e2ff2290bec3ba2a568ae8` |
| lifecycle_binding | `ea35a70dea140c7ffb26e4dab58b07ac1e41d42a0b787f2caa6d17f6ff60f4d2` |
| interruption_replay_recovery | `e58ece2bc3d08729f30eac15a7c572d21f62d57018e91e4184eaad2a3b0e9a31` |
| determinism | `aabc067ecd86b077f007da0fc6d979e9b08974ac062ec1fd66ca85d7450c3f41` |
| runtime_schemas | `5c29e974331d711276bc4e3a83412a458f0f975ecf1764b34845dd7b0b724269` |
| error_status_model | `c5b061b9ef4c4f82991ccb014756b1ce3c194e86e433880aad71dc0d1d0fadec` |
| canonicalization | `dee3f719ce2a91d8f190d8e6173be7f0ec45d3949145334155cde5af22e6fc23` |
| capability_scope | `c90c4926e680dae01b8478dd2f969e635eb5481bf909792ef282cd95c6880e1f` |
| validation_manifest | `182fd82c30dc112e21a4a0de92f14eeb214c3bfd648a2a9ec3aa130a8cd0c8fe` |

## Nonce ownership and entropy

For every V007 request at sequence 2 or later, the exact authorized operator
process is the sole request-nonce generator. The external verifier does not
generate request nonces; it remains the exclusive durable replay-registration
and uniqueness-decision authority.

Production generation is nondeterministic. The only permitted entropy source is
one successful macOS `getentropy(2)` call requesting exactly 32 bytes. The bytes
are immediately encoded as 64 lowercase hexadecimal characters. The operator
does not buffer, batch, retry, mix, derive, log, or persist the raw bytes.

Command-line values, environment variables, files, clocks, host identifiers,
deterministic derivation, verifier challenges, repository-attestor values,
network services, and pseudorandom generators are prohibited nonce sources.

The candidate is checked against the bootstrap session nonce, packaged request
and evidence nonces, and every later request and evidence nonce observed during
the invocation. A collision is terminal for the invocation; a second entropy
call is prohibited. Missing `getentropy(2)`, a nonzero return, interruption, or
anything other than exactly 32 bytes is `V008_ENTROPY_UNAVAILABLE` with no retry
or fallback.

Pure tests may provide an explicit ordered sequence of 32-byte observations.
That seam is not reachable by the production operator.

## Packaged history and live continuation

Packaged sequences 0 and 1 are immutable historical evidence for the repository
request and response. They are validated before connecting, but are never sent
or re-registered over the live socket. Attempting to send either is
`V008_PACKAGED_HISTORY_REPLAY`.

The one live connection begins at sequence 2. Its first request names the V005
clock-attestation identity from packaged response 1. The verifier must establish
the exact session, epoch, registry, and packaged-history continuity before
accepting sequence 2. There is no additional handshake or unbound resumption
token. Later sequences increment by one and name the immediately preceding
successful response's V005 clock-attestation identity.

There is exactly one successful exchange for each timestamped V005 lifecycle
artifact created during the invocation. A failed or indeterminate response,
connection loss, process restart, or verifier restart terminates the invocation.
Reconnect and same-authorization session resume are prohibited.

Before entropy acquisition or socket connection, the operator durably publishes
one deterministic, write-once continuation-invocation claim and its write
evidence. It binds the authorization, run, operator, V007 boundary, session,
packaged response 1, its V005 clock attestation, and first sequence 2. Any
existing complete canonical invocation claim and write evidence is replay and
prohibits another execution invocation; it is never a resume signal. A malformed,
partial, unverifiable, or evidence-incomplete existing claim is continuity
indeterminate. Exactly one exclusive-creation attempt is permitted. A proven
failure before creation is a preclaim rejection requiring formal V005
supersession; there is no retry. Uncertain or post-creation state is continuity
indeterminate.

## Durable continuation evidence

All later envelopes are durable; none are ephemeral. They are written below the
exact V005 consumption-store canonical root using the V005 APFS ownership,
permissions, `openat`/`O_NOFOLLOW`, exclusive-creation, `F_FULLFSYNC`, close, and
parent-fsync rules.

Paths are:

- `evidence/clock/v008/{authorization_identity}/requests/{sequence_decimal_10_digits}-{request_identity}.json`
- `evidence/clock/v008/{authorization_identity}/responses/{sequence_decimal_10_digits}-{response_identity}.json`
- `evidence/clock/v008/{authorization_identity}/bindings/{sequence_decimal_10_digits}-{continuation_binding_identity}.json`
- `evidence/clock/v008/{authorization_identity}/durability/{target_record_type}-{target_identity}.json`
- `evidence/clock/v008/{authorization_identity}/invocation.json`
- `evidence/clock/v008/{authorization_identity}/continuation_failure.json`

The request and its V008 write-evidence record become durable before socket
transmission. A received response is fully decoded and validated, then it and its
write evidence become durable before its embedded V005 bundle is used. The
lifecycle binding and its write evidence become durable only after the
corresponding V005 root artifact and transition envelope are durable. Write
evidence binds the target identity, path, canonical-byte hash, APFS device and
mount, owner and group, modes, link and symlink state, exclusive creation,
`F_FULLFSYNC`, close, parent fsync, and exact ordered durability trace.

The closed world contains exactly one invocation and write-evidence pair;
exactly one request, response, and binding plus one write-evidence record for
each of them per successful sequence; and at most one failure marker and its
write evidence. No terminal success or primary failure classification may be
reported until closed-world, reopen, rehash, stat, and required write-evidence
validation completes. Any uncertainty is continuity indeterminate.

The sealed V006/V007 package is never modified. For sequence 2 and later, the
V008 continuation binding is the additive reachability edge from the V007
request/response to the exact V005 transition envelope. This is V008's only
clarification of V007's orphan rule.

## Lifecycle binding

One continuation binding exists for each successful later exchange and one
successful exchange exists for each timestamped V005 root artifact. It binds:

- authorization, authoritative run, operator, session, and sequence;
- V007 request, response, and V005 clock attestation;
- V005 root artifact type and identity;
- V005 transition ID and transition-envelope identity;
- timestamp field and exact verified timestamp;
- request, response, root, and binding durability state; and
- the previous binding or, at sequence 2, packaged response 1.

The request event projection and transition are fixed before the clock exchange.
The verified timestamp completes the V005 root. The complete V005 transition
validates before the binding is written. A binding is evidence only and grants no
authorization, lifecycle, consumption, publication, archive, or recovery power.

Lifecycle validation receives and validates the exact V007 clock registry in its
registry argument and the V007 contract in its contract argument. It also requires
packaged response 1, the previous binding and its write evidence for sequences
after 2, invocation, request, response, and binding write evidence, and the
complete V005 transition artifact bundle. It validates the invocation claim,
prior binding durability, V007 exchange, and complete V005 transition bundle.
At sequence 2, the request's prior clock
attestation must equal the invocation's packaged sequence-1 attestation. Later
requests must name the immediately preceding binding's attestation. Request,
response, attestation, root, transition, and binding identities are unique within
the invocation.

## Interruption, replay, recovery, and rollback

Any failure from entropy acquisition through binding durability closes the
session. Before a durable V005 consumption decision or claim mutation, the result
is a preclaim rejection and the authorization cannot execute; only an existing
V005 supersession route may proceed. After such a mutation, the result is
postclaim indeterminate: no success, no failure, and no reuse may be asserted.

When the store remains provably available, the operator writes one deterministic,
non-authoritative continuation-failure marker. It contains no new timestamp and
makes no clock claim. The marker's durable-identity set is exactly the sorted,
unique invocation and invocation-write-evidence identities plus every request,
request-write-evidence, response, response-write-evidence, V005 root, V005
durability-evidence, V005 transition, binding, and binding-write-evidence identity
durably published for the failed sequence. It excludes prior sequences and the
failure marker and its own evidence to avoid a self-cycle. The marker and its
write evidence each receive one exclusive-creation attempt. Failure or uncertainty
while creating, publishing, or validating either is continuity indeterminate and
never restores reuse.

V008 implements no recovery transition. Same-authorization restart, reconnect,
session resume, nonce reuse, or continuation replay is prohibited. Preclaim
recovery requires formal V005 supersession with a new authorization and session.
Postclaim handling is limited to an existing, separately authorized future V005
typed-recovery implementation; V008 invents none.

Missing, truncated, reordered, replaced, restored, or contradictory continuation
records, registry markers, or prior bindings are
`V008_CONTINUITY_INDETERMINATE`. Offline APFS rollback, deletion, and backup
restoration remain outside local cryptographic proof; uncertainty prohibits
success.

## Determinism and failures

Production nonces are intentionally nondeterministic. Given identical package,
source, environment, ordered nonce observations, socket frames, and filesystem
observations, every request, response, binding, failure record, classification,
path, and write order is byte-identical. Outputs are independent of hash seed,
locale, and timezone.

V008 adds only these closed failure codes:

- `V008_ENTROPY_UNAVAILABLE`
- `V008_NONCE_COLLISION`
- `V008_PACKAGED_HISTORY_REPLAY`
- `V008_SEQUENCE_CONTINUITY`
- `V008_CONTINUATION_STORAGE`
- `V008_CONTINUATION_REPLAY`
- `V008_CONTINUITY_INDETERMINATE`
- `V008_LIFECYCLE_BINDING`
- `V008_SESSION_INTERRUPTED`
- `V008_RECOVERY_PROHIBITED`

Ordinary phase-dependent failures are preclaim rejection before a durable V005
consumption decision or claim mutation and postclaim indeterminate afterward.
Continuity uncertainty is always the phase-independent class `indeterminate` and
overrides replay or phase-dependent classifications whenever existence, contents,
atomicity, durability, registry state, or terminal continuity is uncertain.
Packaged-history replay is always preclaim rejection. Unexpected exceptions map
to session interruption without exposing exception text or host details.

## Pure verification

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_clock_continuation_v008.py --root .
.venv/bin/python -m pytest tests/test_professional_strategy_olympics_clock_continuation_v008.py
.venv/bin/python -m pytest
.venv/bin/ruff check .
git diff --check
```

The validator parses, hashes, and validates supplied values only. It calls no
entropy source, opens no socket, writes no evidence, creates no authorization,
and runs no Olympics code.

## Remaining sequence

After independent audit and merge of V008:

1. Implement and independently audit the V005 operator against V006/V007/V008.
2. Implement and independently audit the external clock verifier.
3. Implement and independently audit the repository attestor.
4. Perform integrated readiness verification.
5. Create and independently approve one exact authorization package.
6. Run exactly one authorized synthetic Olympics trial.

Synthetic results remain non-economic and non-performance evidence.
