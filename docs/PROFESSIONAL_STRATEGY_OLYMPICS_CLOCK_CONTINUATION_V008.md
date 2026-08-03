# Professional Strategy Olympics Clock Continuation V008

Status: `DESIGN_ONLY_V008_CLOCK_CONTINUATION_VALID_NO_RUNTIME_CAPABILITY`

V008 is a narrow additive successor to V007. It freezes only the nonce authority,
live-session continuation, durable evidence, replay, interruption, and recovery
semantics needed for sequence 2 and later. V004, V005, V006, and every unrelated
V007 rule remain unchanged.

V008 implements no operator, verifier, attestor, authorization, execution, result,
publication, archive, data access, network client, or trading capability.

## Identity

The canonical contract is `21,364` bytes. Its identity equation is:

`SHA256(UTF8(domain) || 0x00 || canonical_projection_bytes)`

The outer domain is `aml.olympics.v008.clock-continuation` and the frozen identity is:

`81c2d0caa1f42915acc4558585a43bb5cf0435095bfa3c3145e33e5bbbd0d0dc`

| Section | Identity |
| --- | --- |
| inheritance | `940c5e590ba1bcd471710304f85db8f9cac7fe8947017f6e4b7449a198f0098a` |
| nonce_authority | `40b41062b862810c8703fd6a85d715369fd100209580748aa7234bf8321e1d07` |
| packaged_history | `58f62c0b9f8349e37bd431885d328dcd1d930e100a43209aae473f0ae9868cbc` |
| live_session | `42e55f9c8c978a2af8e8157ea1b3df2e5a698e3f6435e8a08d1cd5e35e1e0389` |
| continuation_storage | `446edfddc5ae4d16c75ab8b1de98162cada15b6f6106fe811240ec42c9617421` |
| lifecycle_binding | `4cf588190a44d7c11b76378e92263c70778fc4a8df32603a69e4201b256dea0f` |
| interruption_replay_recovery | `3941be3e1a544e783528f7b3dc5780659b93e952a8777dbfc74dc11fcca65f92` |
| determinism | `aabc067ecd86b077f007da0fc6d979e9b08974ac062ec1fd66ca85d7450c3f41` |
| runtime_schemas | `5c29e974331d711276bc4e3a83412a458f0f975ecf1764b34845dd7b0b724269` |
| error_status_model | `578b1950ecbf0b0eaca06d1efeed1e31603b92e0422f7b912c85819daedbb57d` |
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
existing invocation claim prohibits another execution invocation; it is never a
resume signal. A proven failure before exclusive creation permits retrying only
the identical record bytes. Uncertain or post-atomicity state is indeterminate.

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

## Interruption, replay, recovery, and rollback

Any failure from entropy acquisition through binding durability closes the
session. Before a durable V005 consumption decision or claim mutation, the result
is a preclaim rejection and the authorization cannot execute; only an existing
V005 supersession route may proceed. After such a mutation, the result is
postclaim indeterminate: no success, no failure, and no reuse may be asserted.

When the store remains provably available, the operator writes one deterministic,
non-authoritative continuation-failure marker. It contains no new timestamp and
makes no clock claim. Failure to write that marker never restores reuse.

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
Continuity uncertainty is always the phase-independent class `indeterminate`.
Packaged-history replay is always preclaim rejection. Unexpected exceptions map to session interruption without
exposing exception text or host details.

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
