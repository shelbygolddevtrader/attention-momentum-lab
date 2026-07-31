# Professional Strategy Benchmark Olympics input manifest V002

> PROSPECTIVE CONTRACT AND ADAPTER — NOT A TRIAL, RESULT, OR AUTHORIZATION

No canonical ten-entrant manifest exists yet. No authorization artifact exists.
No Olympic trial ran, and no rankings, aggregate scores, or performance results
exist from this milestone. The official manifest must be created and reviewed in
a later pull request.

## Purpose and boundary

V001 remains frozen because its exact-field synthetic input schema cannot carry
every proposal, lifecycle, fill, cost, population, and implementation identity
needed by the canonical ten-entrant trial. Silently extending V001 would change
its meaning and invalidate its frozen identity. V002 therefore adds a new
prospective schema and a narrow validation adapter while leaving V001 bytes,
behavior, scoring, strategy logic, executors, lifecycle, and simulators alone.

V002 performs representation, validation, reconciliation, identity binding, and
projection only. It cannot generate a proposal, fill, quantity, stop, target,
exit, cost, authorization, ranking, or result. It contains no market-data,
network, provider, broker, forward-validation, or holdout interface.

The contract is
`aml.professional-strategy-olympics.input-manifest-contract.v002`; the manifest
schema is
`aml.professional-strategy-olympics.synthetic-input-manifest.v002`. The frozen
contract is at
`config/professional_strategy_olympics_input_manifest_v002.json`.

## V001 versus V002

V001 carries the minimum atoms used by the frozen orchestrator: strategy and
executor identities, completed long trades, discovery-stage identity, and the
V004 scoring identity. V002 additionally binds:

- the exact source commit and V001 contract/module/CLI implementation;
- the V002 adapter contract and byte-derived implementation identity;
- executor, simulator-source, and lifecycle registries;
- explicit entrant status rather than a single disqualification flag;
- proposal and intended-versus-actual entry atoms;
- direction, confidence, stop, adjusted exit, exit reason, and lifecycle evidence;
- gross P&L, all permitted costs, net P&L, exact net R, holding duration, and
  capital-efficiency source atoms;
- validation, holdout, execution, sensitivity, month, and prospective regime
  classifications;
- cost atoms from which 1x, 1.5x, and 2x results are derived rather than trusted;
- explicit prohibitions and deterministic ordering.

V001 accepts no V002 extensions. V002 mode rejects V001 input. Any future change
to this V002 contract after it is frozen requires a new version.

## Root contract

Exact-field validation requires the root to contain:

- `schema_name`, `schema_version`, and `manifest_identity`;
- `synthetic_only`, `fixture_identity`, and `opened_stages`;
- `v004_scoring_bundle_identity`;
- `v001_orchestrator_contract_identity` and
  `v001_orchestrator_implementation_identity`;
- `v002_adapter_contract_identity` and
  `v002_adapter_implementation_identity`;
- `executor_registry_identity`, `simulator_registry_identity`, and
  `lifecycle_identity`;
- `source_commit_identity` and `ordering_version`;
- `entrant_count` and `entrants`;
- `access_prohibitions` and `classification`.

Canonical mode requires exactly ten entrants in the frozen executor-registry
order. The only opened stage is synthetic discovery. Historical, live,
validation, holdout, extension, forward, provider, broker, and network access
must each be explicitly prohibited.

The contract accepts two explicit non-result classifications: test mathematical
specification vectors and a future `canonical_synthetic_trial_input_not_authorized`
manifest. The latter remains non-authorizing; accepting its representation does
not create it or permit execution.

The contract freezes these existing identities:

- V004 scoring bundle:
  `205c126be0d3f1af78899b69609a6ba86a0026ec6dd55729112da78eaa4f23bc`
- V001 orchestrator contract:
  `9e1af13518bc4c6588ce4faaf302e15182f9d42e5dd8c453fc6d27dd257b8d3e`
- V001 module/CLI implementation:
  `fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0`
- executor registry:
  `01c0efa7b35707ddbc837609f99051cdc3db63064410de9d10e334d601787111`
- lifecycle implementation:
  `b10c659118861f3818fc2b1f034a2700e055fdcc19bd51651969f660af94e384`

The simulator registry is a source-binding registry over the unchanged portfolio
and trade simulator bytes. It does not reinterpret or replace either simulator.

## Entrant contract

Each entrant has one exact record containing its entrant identifier, strategy,
executor, simulator, and lifecycle identities; status; disqualification reasons;
ineligibility reasons; integrity failures; active dates; validation and holdout classifications;
sensitivity expectation set; explicit trade count; ordered trades; and entrant
identity.

Statuses are distinct:

- `active`: eligible synthetic discovery evidence is represented;
- `ineligible`: evidence is insufficient without an integrity failure;
- `disqualified`: a frozen disqualification condition applies;
- `integrity_failure`: input integrity failed and cannot be scored.

The adapter retains this distinction in its status ledger. When projecting into
the older V001 structure, disqualified and integrity-failure entrants are both
fail-closed under V001's existing disqualification mechanism; the V002 ledger is
the authoritative distinction.

## Proposal and completed-trade atoms

Every trade explicitly carries:

- proposal identity and timestamp, symbol, direction, and exact confidence;
- intended and actual entry timestamps plus exact entry delay;
- raw and 10-bps-adjusted entry price, signed actual quantity, stop, and target;
- raw and adjusted exit price, exit timestamp, exit reason, and lifecycle evidence;
- entry commission, exit commission, and other permitted cost atoms;
- gross and net P&L, initial risk, and reduced-rational net R;
- elapsed holding nanoseconds;
- the per-trade numerator and denominator atoms used by capital efficiency;
- New York month and prospective regime label;
- validation, holdout, execution, and sensitivity classifications;
- cost-stress source atoms and the trade identity.

Prices, P&L, risk, and costs are integer microdollars. Times and durations are
integer nanoseconds. Confidence, net R, sensitivity values, and derived stress
results are reduced numerator/denominator fractions. Floating-point
scoring-critical inputs are rejected.

## Exact reconciliation

Validation fails closed rather than repairing or inferring atoms:

1. The proposal precedes the intended entry, the intended entry does not follow
   the actual entry, and the actual entry precedes exit. Entry delay and holding
   duration must equal their timestamp differences.
2. Long quantity is positive; short quantity is negative. Long stops are below
   and targets above adjusted entry. Short placement is the reverse.
3. Entry and exit adjustments use exact ten-basis-point arithmetic with Python's
   integer half-even rounding, matching frozen V001 long-trade behavior.
4. Gross P&L is recomputed from signed direction, absolute filled quantity, and
   adjusted prices. Net P&L subtracts entry commission, exit commission, and
   permitted other costs.
5. Net R must equal net P&L divided by initial risk as a reduced fraction.
6. The capital-efficiency numerator equals net P&L. Its denominator equals
   `abs(quantity) × adjusted entry microdollars × elapsed nanoseconds`.
7. Exit month is derived from the exit instant in `America/New_York`.
8. Exit reason must have matching lifecycle evidence. If stop and target are both
   reachable in one bar, the result must be `stop`.
9. Cost-stress source atoms reproduce the base trade and derive 1x, 1.5x, and 2x
   results. Entrant-supplied final stressed scores are never trusted.
10. Validation and holdout remain stage-unopened. All identities, field sets,
    counts, bindings, and canonical order must reconcile.

The V002 contract can validate short mathematical specification vectors. The
frozen ten entrants and V001 internal structure are long-only, so the adapter
fails closed instead of inventing a short projection. Likewise, V001 cannot
represent non-commission other costs; a future canonical manifest must use the
frozen supported zero-other-cost convention or introduce a later reviewed
adapter version.

## Canonical identities and ordering

Canonical JSON is UTF-8, key-sorted, and compact. SHA-256 identities exclude only
their own identity field:

- proposal identity binds proposal timestamp, symbol, direction, confidence,
  intended entry, stop, and target;
- lifecycle evidence identity binds every lifecycle flag;
- cost-source identity binds every cost atom;
- trade identity binds every proposal, fill, lifecycle, cost, classification,
  and economic atom;
- entrant identity binds every entrant field and ordered trade;
- fixture identity binds the opened stages, ordered entrant identities, and
  non-result classification;
- manifest identity binds every root field and all nested identities;
- adapter implementation identity binds its contract plus exact validator,
  adapter, and CLI bytes.

These identities do not depend on file path, worktree, operating system,
wall-clock time, local timezone, Python hash seed, or mapping insertion order.
Entrants follow the frozen executor registry. Trades are ordered by exit time,
entry time, UTF-8 symbol bytes, then UTF-8 proposal-identity bytes. Input is
rejected rather than silently reordered.

## Adapter and validation-only lifecycle

The adapter first validates the full V002 graph, then projects already-fixed,
supported fields into the exact V001 internal manifest. It does not regenerate
any proposal, fill, stop, target, quantity, timestamp, or cost. The projected
manifest must pass the unchanged V001 validator.

Validation-only mode invokes the unchanged V001 validation-only gate and returns:

`VALIDATION_ONLY_TRIAL_NOT_AUTHORIZED`

It publishes no artifact, creates no authorization, executes no trial, and emits
no rankings, aggregate scores, or performance claims. The adapter has no method
that can authorize execution. Any future execution must pass the existing V001
identity-bound authorization gate.

A future run identity is derived from the exact merged source commit, V001
orchestrator contract and implementation identities, V002 adapter implementation
identity, V004 scoring identity, and V002 manifest identity. Computing that value
does not authorize a run.

## Future canonical-manifest workflow

In a later pull request, reviewers must create the official ten-entrant manifest
from reviewed synthetic mathematical inputs, bind the exact merged source commit,
validate every identity and reconciliation, verify deterministic bytes across
hash seeds and timezones, and separately review any authorization artifact. This
milestone intentionally provides no official entrant set and no execution path.

The committed test builders are mathematical specification vectors only. They
are non-performance inputs and cannot be treated as an official manifest,
economic evidence, a ranking, or a trial result.
