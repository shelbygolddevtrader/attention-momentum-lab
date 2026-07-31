# Professional Strategy Benchmark Olympics input manifest V003

> PROSPECTIVE IDENTITY-CORRECTION CONTRACT — NOT A TRIAL OR RESULT

V003 exists solely to correct one missing direct lineage edge in V002:
`v002_contract_identity`. No canonical ten-entrant manifest exists yet. No
authorization artifact exists. No trial ran, no rankings or performance results
exist, and execution count remains zero.

## The V002 omission

The frozen V002 manifest uses exact-field validation but does not include the
identity of the V002 contract governing its interpretation. Its manifest identity
therefore cannot prove which exact contract defined its fields and reconciliation
rules. Adding the field to a V002 document is rejected as an unknown field.

A companion registration record is insufficient: it could bind a V002 manifest
identity to a contract externally, but the manifest's own identity would still
omit that contract. The canonical input must carry and hash the lineage edge
directly.

V002 remains frozen. Changing its field set would alter its contract and adapter
identities after review. V003 is additive, independently versioned, and delegates
all inherited validation and projection to the unchanged V002 and V001 layers.

## Versions and identities

The V003 manifest schema is:

`aml.professional-strategy-olympics.synthetic-input-manifest.v003`

The version is:

`professional-strategy-olympics-synthetic-input-manifest-v003`

The V003 contract is
`config/professional_strategy_olympics_input_manifest_v003.json`. Its identity is
derived by canonical SHA-256 over every contract field except
`contract_identity` itself. This nonrecursive pattern is the repository's
established identity design.

Every V003 manifest directly contains:

`v002_contract_identity = c9f6c8c3d02ba78c460c16230a6163fa0272b9464f60172c2bcae21fe0fbd3bb`

The value is mandatory, exact, and never inferred, defaulted, repaired, or read
from a companion file.

V003 also carries separately versioned V003 contract and adapter identities. This
is necessary to bind the new validator and projection layer without changing the
meaning of the inherited V002 adapter fields.

## V002 versus V003

V003 preserves all V002 root, entrant, lifecycle, cost, proposal, and trade fields
and adds these versioned identity edges:

- `v002_contract_identity` — the correction required by this milestone;
- `v003_contract_identity` — the governing V003 contract;
- `v003_adapter_contract_identity` — the non-executing V003 adapter contract;
- `v003_adapter_implementation_identity` — exact validator, adapter, and CLI bytes.

The additional V003 identity fields are version-lineage necessities. They do not
expand any economic, strategy, execution, lifecycle, scoring, data, or
authorization capability.

## Manifest identity

The V003 manifest identity is canonical SHA-256 over every root field and every
nested entrant and trade atom except `manifest_identity` itself. Consequently it
directly binds:

- V003 schema and version;
- V002 and V003 contract identities;
- V001 orchestrator contract and implementation;
- inherited V002 adapter contract and implementation;
- V003 adapter contract and implementation;
- V004 scoring bundle;
- executor, simulator, and lifecycle registries;
- exact source commit and deterministic ordering policy;
- access prohibitions and stage classifications;
- fixture identity, entrants, proposals, trades, costs, and nested identities.

Changing `v002_contract_identity` changes the manifest identity. A stale manifest
identity fails before lineage validation; recomputing the manifest identity around
an incorrect V002 contract value then fails the exact contract-binding check.

Canonical serialization is independent of mapping insertion order, operating
system, file path, worktree, hash seed, local timezone, and wall-clock time.

## Inherited reconciliation

After V003 verifies its exact schema, manifest identity, direct V002 contract
binding, and V003 identity fields, it creates an in-memory V002 validation view.
That view removes only V003-specific identity fields, restores the frozen V002
schema/version, and recomputes the V002 view identity. It is then passed through
the unchanged V002 validator.

This retains all frozen V002 checks for:

- exact root, entrant, lifecycle, cost, and trade field sets;
- ten frozen entrants and canonical ordering;
- proposal, intended-entry, actual-entry, and exit timestamp ordering;
- exact entry delay and holding duration;
- direction, confidence, signed quantity, stop, and target;
- raw and adjusted entry/exit prices;
- exit reason and conservative lifecycle evidence;
- commissions, supported costs, gross/net P&L, initial risk, and reduced net R;
- capital-efficiency numerator and denominator atoms;
- month, regime, validation, holdout, execution, and sensitivity classifications;
- exact 1x, 1.5x, and 2x cost-stress derivation;
- proposal, lifecycle, cost, trade, entrant, fixture, and manifest identities.

V003 does not silently upgrade a V001 or V002 document. V003 mode accepts only a
V003 manifest with all required V003 fields.

## Adapter architecture

The V003 adapter validates the V003 identity graph, projects an in-memory frozen
V002 view, and calls the unchanged V002 adapter. That adapter continues to project
supported fixed atoms into the unchanged V001 orchestrator structure.

No layer regenerates proposals, prices, fills, quantities, stops, targets, costs,
timestamps, or outcomes. The V003 adapter has no execution, authorization,
publication, provider, broker, or network interface.

Validation-only mode returns exactly:

`VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED`

The report surfaces both the V002 and V003 contract identities. It creates no
authorization, publishes no artifact, executes no trial, and calculates no
ranking or aggregate score.

## Future run identity and authorization

The prospective V003 future run identity binds:

- exact source commit;
- V001 contract and implementation;
- V002 contract and adapter implementation;
- V003 contract and adapter implementation;
- V004 scoring bundle;
- V003 manifest identity.

Therefore changing `v002_contract_identity` changes the run-identity payload. An
invalid binding is rejected before any run identity is made available for use.
Computing the valid future identity is not authorization. Any future execution
must still pass the existing V001 one-use, identity-bound human authorization
gate.

## Preservation and next milestone

V001 and V002 remain byte-for-byte and behaviorally unchanged. V004 scoring,
strategies, executors, simulators, lifecycle rules, production, operators,
forward-validation, holdout behavior, and authorization semantics are unchanged.

The next reviewed milestone may create the official canonical ten-entrant V003
synthetic manifest. It must bind the exact merged V003 source, materialize every
atom, pass validation-only mode, and be reviewed and merged before any separate
authorization is considered.

This milestone does not create that manifest. Any change to the V003 contract or
adapter after freezing requires another explicit version and identity.
