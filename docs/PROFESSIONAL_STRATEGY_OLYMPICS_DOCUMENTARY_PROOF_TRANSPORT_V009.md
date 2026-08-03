# Professional Strategy Olympics Documentary Proof Transport V009

Status: design-only, prospective, no authorization, no execution.

V009 closes one gap: the future V005 operator needs seven exact values for
`validate_documentary_git_proof`, but V005–V008 did not define a package-bound
offline transport for those values. V009 adds no proof meaning and no execution
authority. The canonical contract is
`config/professional_strategy_olympics_documentary_proof_transport_v009.json`.

## Authority and precedence

- V005 remains the sole authority for documentary-proof meaning and the
  authorization lifecycle.
- V006 remains the operator-package interface authority.
- V007 remains the runtime-boundary authority.
- V008 remains the clock continuation, replay, interruption, and recovery
  authority.
- V009 governs only proof transport, identity, successor-package integration,
  and offline validation binding.

V009 does not create or approve an authorization or proof, create Git history,
implement an operator, verifier, or attestor, execute the Olympics, generate a
result, or confer trust on a repository, host, person, network, or storage
system.

## Selected transport model

There is exactly one permitted model: all six raw byte sequences are embedded
in one canonical documentary-proof envelope. Separate proof-byte files are not
permitted. This removes cross-member path selection, member ordering, partial
replacement, and dual-representation ambiguity.

The embedded members are:

1. exact canonical V005 authorization bytes;
2. exact V005 authorization tree-proof bytes;
3. raw Git commit A payload bytes;
4. exact canonical V005 documentary-binding bytes;
5. exact V005 binding tree-proof bytes;
6. raw Git commit B payload bytes.

The seventh V005 input, commit B's OID, is an explicit envelope field. It must
be exactly 40 lowercase hexadecimal SHA-1 characters. Prefixes, abbreviation,
uppercase, and whitespace are rejected. The OID must reproduce from the exact
embedded commit B payload.

## Byte representation

Each raw member is a closed object with these exact fields:

`encoding`, `encoded_length`, `decoded_length`, `sha256`, `member_identity`,
and `value`.

`value` uses standard RFC 4648 Base64 with canonical padding. Whitespace,
URL-safe alphabets, omitted or substituted padding, and alternate encodings are
rejected. Decoding must consume the whole value. Re-encoding the decoded bytes
must reproduce the input byte-for-byte. The declared lengths and SHA-256 over
the decoded bytes must match. The member identity is:

```text
SHA256(
  UTF8("aml.olympics.v009.documentary-proof-member") || 0x00 ||
  canonical_json({member_name, decoded_length, sha256})
)
```

No decompression, transcoding, newline conversion, Unicode normalization, or
trailing-byte tolerance is allowed.

## Envelope identity and lineage

The envelope schema is
`aml.professional-strategy-olympics.documentary-proof-envelope.v009`. Unknown,
missing, or duplicate fields fail closed. Its identity is the domain-separated
SHA-256 of every exact envelope field except `envelope_identity`.

It binds the V005 authorization and documentary-binding identities; commits A
and B; trees A and B; V004 contract and implementation; V005 governance and
command; V006 interface and operator package; V007 boundary and runtime
package; V008 continuation contract; and V009 transport contract. The package
binding identity separately hashes the authorization, binding, V006 package,
V007 package, V008 contract, and V009 contract identities. Any cross-version,
cross-authorization, or cross-package reuse is rejected.

## Offline Git proof validation

Only Git SHA-1 object format is supported. For object kind `K` and exact payload
`P`, the OID is:

```text
lowerhex(SHA1(ASCII(K) || 0x20 || ASCII(decimal(len(P))) || 0x00 || P))
```

The envelope must prove, entirely from packaged bytes:

- commit A hashes to the declared A OID, references the declared authorization
  tree, and has exactly one parent equal to the authorized source commit;
- commit B hashes to the declared B OID, references the declared binding tree,
  and has exactly one parent equal to commit A;
- the authorization tree proof resolves the canonical authorization path to a
  mode `100644` blob of the exact authorization bytes;
- the binding tree proof resolves the canonical binding path to a mode `100644`
  blob of the exact documentary-binding bytes; and
- the documentary-binding artifact carries the exact V005 authorization,
  source-parent, tree, blob, repository-context, and commit-A equations.

The last validation step invokes the unchanged V005
`validate_documentary_git_proof`. V009 does not add claims about GitHub,
repository ownership, human identity, TLS, or host integrity.

## Package integration

The proof envelope path is:

```text
proofs/{authorization_identity}/documentary_git_proof_v009.json
```

The unindexed V009 successor package root is:

```text
authorizations/{authorization_identity}/documentary_proof_package_v009.json
```

The package root binds one exact sealed V006 operator-package identity, one
exact sealed V007 runtime-package identity, and one proof envelope. It carries:

- one exact V006 four-field record-index extension entry; and
- one exact V007 five-field supplemental-manifest entry.

Both entries describe the same `documentary_git_proof` record, identity, path,
and canonical-byte digest; the V007 entry additionally fixes the envelope
schema. V006 and V007 sealed manifests are never mutated. The V009 package root
is the sole additive successor root. A valid closed-world inventory contains
exactly the package root and envelope, with no alternate, duplicate, hidden,
unindexed, or unreachable proof member.

Pure storage observations cover exactly those two members and bind relative
path, regular-file type, filesystem mode `0600`, review Git mode `100644`, link
count one, symlink absence, same-device status, durability, byte length, and
SHA-256. Missing, duplicated, linked, mode-substituted, or uncertain storage
evidence cannot pass.

The future V008 invocation is bound transitively by equality of authorization,
V006 package, V007 runtime package, and the literal V008 contract identity. No
V008 schema is changed.

## Detached source and offline isolation

Commit B may postdate and be absent from the detached authorized source. The
proof is therefore self-contained. Validation does not read the source Git
object database and never installs objects, refs, alternates, or worktree/index
changes.

The following are prohibited proof sources: network retrieval, GitHub APIs,
remote fetches, object-database scanning, descendant discovery, refs, reflogs,
alternate object directories, global Git configuration, incidental clones,
unbound caches, caller-selected external paths, and environment overrides.
Any attempted fallback is `V009_FALLBACK_PROHIBITED`.

## Canonicalization and limits

All JSON uses the exact V005 canonical form: UTF-8, NFC strings, ASCII escaping,
keys sorted by Unicode code point, compact separators, integers only, no
duplicate keys, and exactly one terminal LF. Paths are lowercase ASCII POSIX
relative paths with no empty, dot, dot-dot, NUL, absolute, or trailing-slash
forms.

The frozen limits are listed in the contract, including explicit decoded and
Base64-encoded ceilings for every member. Key limits are 800,000 envelope
bytes, 832,768 total V009 package bytes, 500,000 total decoded proof bytes, 32
tree-proof steps, one parent per commit, 1,024 path bytes, and six raw members.
Oversize and structural failures are rejected before expensive validation
where possible.

## Failure handling

V009 has closed failure codes for absence, duplication, unreadability,
identity/package mismatch, missing/extra/oversize/hash-mismatched raw members,
malformed Git objects, OID/tree/path/mode/blob/parent/artifact mismatch,
authorization or binding mismatch, cross-version substitution, reachability or
durability uncertainty, unsupported object format, and prohibited fallback.
Uncertainty never succeeds. V009 does not collapse an indeterminate package or
durability state into ordinary rejection.

## Independent verification

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_professional_strategy_olympics_documentary_proof_transport_v009.py \
  --root .

PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_professional_strategy_olympics_documentary_proof_transport_v009.py

.venv/bin/python -m pytest
.venv/bin/ruff check .
git diff --check
```

The validator is pure and validation-only. It accepts no proof path, network
location, repository selector, authorization creation request, or execution
argument.
