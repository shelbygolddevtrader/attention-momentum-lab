# Professional Strategy Benchmark Olympics operator interface V006

Status: `DESIGN_ONLY_V006_OPERATOR_INTERFACE_NO_AUTHORIZATION_NO_EXECUTION`

## Architectural finding

The repository contains a complete synthetic comparison stack but not a fully authorized operator:

1. V001 freezes ten entrants, tournament governance, claims, and advancement gates.
2. V002 implements the ten strategy evaluators, point-in-time indicators, deterministic lifecycle, and common portfolio/cost model.
3. V003 freezes percentile, tie, and deterministic-ordering mathematics.
4. Final-scoring V004 freezes capital efficiency, cost stress, precision, lifecycle outcomes, portfolio capital, and disqualification behavior.
5. Orchestrator V001 deterministically builds and publishes the synthetic six-artifact inner result when its legacy authorization gate passes.
6. Input-manifest V003 and the canonical synthetic manifest bind ten entrants and ten committed synthetic completed trades to the unchanged orchestrator.
7. Execution/publication V004 supplies the prospective lineage wrapper and write-once outer bundle.
8. Authorization Governance V005 freezes 38 immutable evidence schemas, 27 lifecycle transitions, role separation, trusted-time evidence, documentary Git proof, APFS durability, supersession, recovery, and archival.

V005 intentionally remains a pure validator. Its frozen command names a nonexistent V005 runner and accepts one `execution_clock_attestation_path`, even though every lifecycle event requires a unique externally verified clock package. It also does not define how a future operator locates the complete authorization graph, communicates with the external verifier, receives repository provenance, projects V005 approval into V004, or avoids invoking the obsolete V003/V004 consumption paths alongside the V005 decision slot. Implementing that runner directly would invent security-critical behavior.

V006 closes this single gap prospectively and additively. It preserves the exact V005 command and defines the missing semantics behind its existing arguments. It changes no V001–V005 bytes or identity and grants no authority.

## Capability and blocker inventory

| Layer | Capability present | Guarantee | Remaining limitation |
|---|---|---|---|
| V001 governance | Ten frozen entrant identities, events, claims, readiness and advancement rules | No ad hoc entrant or claim substitution | Historical/validation stages remain separately gated |
| V002 execution | All ten deterministic strategy evaluators, point-in-time indicators, lifecycle, cost and portfolio logic | No lookahead; unavailable and integrity paths fail closed | Official use still needs authorized inputs |
| V003/V004 scoring | Exact percentile, tie, precision, capital-efficiency, cost-stress and disqualification rules | Platform-independent exact ordering and arithmetic | A scoring contract is not execution authority |
| V001 orchestrator | Validation-only preflight plus deterministic scoring, ranking and write-once inner publication | Common inputs, entrant isolation and deterministic artifacts | Legacy authorization is subordinate to later governance |
| Input manifest V003 | Canonical ten-entrant synthetic fixture and V001 projection | Fixed synthetic comparison basis and identities | Synthetic evidence is non-economic and non-performance |
| Execution/publication V004 | Lineage run identity, V004 wrapper and write-once outer result bundle | One prospective canonical synthetic result namespace | Its legacy consumption routine cannot arbitrate V005 decisions |
| Governance V005 | Pure validation of 38 schemas and 27 transitions | Typed lifecycle, roles, trusted time, documentary Git, durability, recovery and archive invariants | No operator, external verifier, authorization package or authorization exists |
| Interface V006 | Exact package, trust, projection, ordering and failure boundaries for the inherited V005 command | A future implementation no longer needs to invent security-critical interfaces | Implementation and external trust services remain deliberately absent |

The canonical synthetic manifest contains ten entrants and ten synthetic completed trades. It can exercise tournament mechanics but cannot support a claim of profitability, historical validity, or economic performance. Historical, validation, holdout, paper, live, and production boundaries remain closed.

## Frozen identities

- V006 operator-interface identity: `1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6`
- Inherited V005 operator-command identity: `ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb`
- Complete contract: 12,321 canonical bytes
- Design base: `763e7aa241cdbf8febe0191ee5f01a8156869931`
- V005 governance: `dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0`
- V005 command: `ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb`
- V004 execution contract: `0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053`
- V004 execution implementation: `d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4`
- Immutable baseline tag object: `746e147efd9bb09dedfdd4d2850f461e36d9f046`
- Immutable baseline tagged commit: `378317dba28d93792d2f0a3ab4302a5d0b6abf7c`

Identity is `SHA-256(UTF8(domain) || 0x00 || canonical_projection_bytes)`. The contract also freezes nine independently declared section identities.

## Authorization package

The future operator receives an external, reviewed, read-only package root. The authorization argument must resolve exactly to:

`authorizations/{authorization_identity}/authorization.json`

The package manifest lives beside it as `operator_package_v006.json`. Its index binds every record's type, identity, relative path, and canonical-byte digest. Every internal V005 reference must resolve exactly once, all supplied records must be reachable, and only V005-declared external compatibility edges may remain external. Unknown, duplicate, orphaned, path-escaping, symlinked, noncanonical, or byte-mismatched records reject.

The package is not the authorized source tree. Documentary commits remain evidence only; execution occurs from a clean detached checkout of `authorized_source_commit` and `authorized_source_tree`.

## External trust interfaces

The operator performs no Internet access. Repository provenance arrives through the authorization package as one externally attested V005 `repository_context` plus its provider evidence. V005 does not freeze a timestamp field for repository-context evidence, so V006 does not falsely claim machine-verifiable freshness; this attestation proves reviewed provenance, not operation time.

The frozen `--clock-attestation` argument points to a canonical V006 bootstrap document. Its exact schema binds the V005 governance and command identities, initial complete V005 clock bundle, system account, peer UID, and absolute local verifier socket path. Its identity uses the frozen `aml.olympics.v006.clock-verifier-bootstrap` domain. The bootstrap is a transport locator, not an independent source of authority; authority remains the V005 role assignment and each external verifier attestation.

Trusted time then comes from that separate local verifier over a pre-opened Unix-domain stream socket. Messages use a four-byte unsigned big-endian length followed by at most 2,000,000 bytes of canonical JSON. The operator sends one event projection per lifecycle event. Each response contains the complete V005 request, response evidence, verifier attestation, and event clock attestation. The peer UID must match the bound environment owner. Timeout, disconnect, malformed framing, identity reuse, or replay rejects without a local-clock fallback.

The verifier—not the operator—owns TLS, GitHub Date freshness, proxy/cache rejection, and the cross-bundle replay registry. This preserves V005's honest external trust boundary.

## Execution and consumption mapping

The future implementation must:

1. Validate the complete authorization package and documentary proof.
2. Verify the detached source, environment, repository attestation, APFS roots, and absence of competing lifecycle evidence.
3. Publish activation, consume decision, and consumption claim through V005 transitions and durability rules.
4. Project V005 approval into the exact frozen V004 authorization fields using the machine-readable field-by-field map in the V006 contract. The projection includes no authority absent from V005 and its identity is derived only after all mapped fields are complete.
5. Produce byte-equivalent V004/V001 computation without calling legacy V003 consumption or V004 `consume_and_build`; V005 exclusively owns the decision slot and claim.
6. Publish build, run, terminal, archive-pending, archive, and completion evidence using unique trusted-time packages and the exact V005 state machine.

No strategy, indicator, signal, lifecycle, cost, portfolio, scoring, ranking, or disqualification rule may change.

The authoritative run identity is computed with the frozen V004 `lineage_run_identity` function using the detached authorized source commit. It is computed only after the operator implementation has merged, before the proposal, and is recomputed during every preflight. Consequently, this design PR intentionally does not publish a future authoritative run identity that would become stale when implementation code is added.

## Failure behavior

Missing or ambiguous external evidence rejects before a transition. Unsupported APFS or `F_FULLFSYNC` has no fallback. Uncertain atomicity enters only the matching V005 indeterminate route. Recovery uses only the exact typed V005 recovery transition and never deletes or replaces bytes. Existing completed output is verification-only; incomplete or conflicting output cannot be treated as a result.

## Remaining path to the first authorized run

After V006 is reviewed and merged, four prerequisites remain:

1. Implement and independently audit the V005 command using the frozen V006 interface.
2. Implement or approve independent clock-verifier and repository-attestation services matching these interfaces.
3. Create and independently review one complete V006/V005 authorization package bound to the eventual merged operator source commit.
4. Execute only after a separate explicit human approval confirms the exact package, source, run, roots, and command.

This milestone creates none of those artifacts and does not make the Olympics executable.

## Verification

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_operator_interface_v006.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_operator_interface_v006.py
PYTHONPATH=src .venv/bin/python -m pytest
.venv/bin/python -m ruff check .
git diff --check
```
