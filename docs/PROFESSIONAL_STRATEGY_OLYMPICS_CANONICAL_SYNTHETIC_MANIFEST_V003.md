# Canonical Professional Strategy Olympics synthetic manifest V003

> CANONICAL SYNTHETIC INPUT — NOT AUTHORIZATION, EXECUTION, OR A RESULT

This document registers the sole official input proposed for the future inaugural
canonical synthetic Olympics trial. The committed manifest is synthetic
specification evidence, not market evidence or performance evidence. No trial
ran, no rankings or performance results exist, no authorization artifact exists,
and execution count remains zero.

## Canonical file and lineage

The manifest is
`config/professional_strategy_olympics_canonical_synthetic_manifest_v003.json`.
It uses schema
`aml.professional-strategy-olympics.synthetic-input-manifest.v003` and version
`professional-strategy-olympics-synthetic-input-manifest-v003`.

It binds the exact PR #20 merge commit
`4ec2e1e38c716351d9d592e6dc8ca0d99ee805b8`, the V001 orchestrator contract
`9e1af13518bc4c6588ce4faaf302e15182f9d42e5dd8c453fc6d27dd257b8d3e`,
V001 implementation
`fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0`,
V002 contract
`c9f6c8c3d02ba78c460c16230a6163fa0272b9464f60172c2bcae21fe0fbd3bb`,
V002 adapter contract
`4506a3c917161da771fbdd1fa5ab742903e32982421607ac38789effcf10efc5`,
V002 adapter implementation
`b656c07e0208479b85227b1d0b0e06f0e8f4ba5637bbb276ed045faf1bfce6d1`,
V003 contract
`4b33f5a806f4fb71e65dfe571b230c32e0fea7efbad5698b4f57af9e4276371f`,
V003 adapter contract
`baeb58120f458299b2d81e8381836d3c2ea00c21f28b47da703cb07a5e536261`,
V003 adapter implementation
`492fb738bf9617baff28974599dba2c019dbe23aa65fdb2570cf5c9304d2aada`,
and V004 scoring
`205c126be0d3f1af78899b69609a6ba86a0026ec6dd55729112da78eaa4f23bc`.

The executor, simulator, and lifecycle registry identities are respectively
`01c0efa7b35707ddbc837609f99051cdc3db63064410de9d10e334d601787111`,
`732fc6d982b031f0e6f428bb9e52e7c53e90a374fc883ec376504044fe7fea00`,
and `b10c659118861f3818fc2b1f034a2700e055fdcc19bd51651969f660af94e384`.

## Entrants and ordering

The ten frozen long-only entrants appear in the exact bytewise executor-binding
order required by the unchanged V001/V002/V003 stack:

1. `failed_downside_breakdown_reclaim_long_v002`
2. `first_pullback_continuation_long_v002`
3. `five_minute_orb_long_v002`
4. `fifteen_minute_orb_long_v002`
5. `gap_and_go_long_v002`
6. `high_of_day_breakout_long_v002`
7. `market_relative_momentum_long_v002`
8. `rsi_exhaustion_reversion_long_v002`
9. `vwap_mean_reversion_fade_long_v002`
10. `vwap_reclaim_long_v002`

Each entrant contains one explicit ordered synthetic trade. All ten trades are
materialized in JSON; nothing is generated during validation or future trial
execution. Entrant status is active, discovery is the only opened stage, and
validation and holdout remain unopened. Disqualification, ineligibility,
integrity, and sensitivity-expectation lists are explicit.

## Exact reconciliation

The frozen V003 validator projects the document into an in-memory V002 view and
reuses the unchanged V002 reconciliation rules. They verify exact proposal,
intended-entry, actual-entry, and exit ordering; entry delay; long direction and
positive signed quantity; stop and target placement; lifecycle evidence and exit
reason; raw and adjusted prices; commissions and supported cost atoms; gross and
net P&L; initial risk; reduced-rational net R; holding duration; capital
efficiency; 1x, 1.5x, and 2x cost stress; classifications; and every proposal,
lifecycle, cost, trade, entrant, fixture, and manifest identity.

All serialized arithmetic uses integers and reduced rationals. Floating point,
unsupported costs, short trades, absolute paths, network references, unknown
fields, missing fields, duplicate identities, and ordering changes fail closed.
No tolerance, rounding, fallback, repair, or inference is permitted.

## Frozen identities

The fixture identity is
`7093c039bb2bb06ed63fad08238e6ac6594db2747f9b975822c1f7dc9d30ddb7`.
The complete canonical manifest identity is
`fc16aed963b8c6aac0b0e01affea29148cb4d396d8dfa3e5398d68671e4788b0`.
It hashes all root and nested atoms except its own identity field. Canonical
serialization and identity are independent of file path, worktree, machine,
mapping insertion order, hash seed, timezone, and wall-clock time.

The prospective deterministic run identity is
`ad01381e5cd63dc51777c17e1d6b736af6aee0022f3773ba89794df513f3268a`.
Computing it does not authorize or execute anything. A future one-use human
authorization must bind this exact reviewed manifest, merged source, adapter,
and run identity in a separate milestone.

## Validation-only boundary

The committed validator loads the JSON, independently checks its canonical
source, fixture, manifest, entrant order, and trade counts, then invokes the
frozen V003 adapter. Its only successful status is
`VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED`. It creates no authorization, publishes no
run artifact, calculates no ranking or score, and has no network, provider,
broker, historical, live, validation, extension, forward, holdout, production,
or operator access.

This manifest must be reviewed and merged before authorization. Any modification
requires a new version and identity. No historical or live data was accessed in
its construction.
