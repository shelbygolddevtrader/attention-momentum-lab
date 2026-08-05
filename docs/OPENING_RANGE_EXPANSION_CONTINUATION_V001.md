# Opening Range Expansion Continuation V001

## Status and claim boundary

This milestone moves one hypothesis through specification, implementation
binding, conformance, registered execution, and a bounded diagnostic archive.
It does not produce empirical evidence.

Every exploratory artifact preserves the frozen Exploratory Research Mode V001
global labels unchanged:

- `EXPLORATORY ONLY`
- `CONTAMINATED DATA`
- `NOT AUTHORIZED FOR EMPIRICAL CONCLUSIONS`
- `NOT VALIDATION`
- `NOT HOLDOUT`
- `NOT PRODUCTION`
- `NOT CAPITAL ELIGIBLE`

In addition, every candidate result, summary, run artifact, and manifest carries the
candidate-specific, identity-bound singleton field
`candidate_specific_labels: ["NOT EMPIRICAL EVIDENCE"]`. This additive field
does not rename or extend the frozen global label contract. The candidate
verifier requires the exact capitalization and spelling on every manifested
artifact and rejects missing, synonymous, inconsistent, stale, or tampered
values.

The candidate binds prohibited-claim contract
`90535566580282d3746af19b2511059018a92120ad94d090526f9881ec36cc17`,
structured-observation contract
`571d9d773b615cc4e46ee9dad997cb1e602d9a18fa7a4a709b78cf54ce9f91aa`,
free-text-domain contract
`2530347c729e5baaab4b1ba9697d1e4a256e2ecd4b7518364aa47946321127c7`,
and closed-inventory contract
`95cc8aa48dffa373daa612cba90162856087d745e4d9222be622e08aff5532b7`
to its configuration, evidence, result, summary, run, and manifest. The exact
prohibited field vocabulary is:

- economic: `pnl`, `gross_pnl`, `net_pnl`, `realized_pnl`,
  `unrealized_pnl`, `profit`, `loss`, `expectancy`, `expected_value`,
  `profit_factor`, `return`, `returns`, `total_return`, `annualized_return`,
  `cagr`, `win_rate`, `loss_rate`, `payoff_ratio`, `average_win`, and
  `average_loss`;
- risk and performance: `drawdown`, `maximum_drawdown`, `max_drawdown`,
  `volatility`, `sharpe`, `sharpe_ratio`, `sortino`, `sortino_ratio`, `calmar`,
  `information_ratio`, `alpha`, `beta`, `capital_efficiency`, and
  `risk_adjusted_return`;
- statistical and edge claims: `statistical_significance`,
  `statistically_significant`, `p_value`, `t_stat`, `confidence_interval`,
  `edge`, `empirical_edge`, `profitable`, `profitability`, `robust`,
  `robustness`, and `repeatable_edge`;
- evidence claims: `validation_passed`, `validated`, `holdout_passed`,
  `out_of_sample_passed`, `empirical_evidence`,
  `authorized_empirical_evidence`, and `evidence_of_edge`;
- deployment claims: `deployment_ready`, `production_ready`,
  `ready_for_production`, `paper_trading_ready`, `live_trading_ready`, and
  `broker_ready`;
- capital and recommendations: `capital_eligible`, `capital_allocation`,
  `capital_allocation_recommended`, `recommended_capital`,
  `position_size_recommendation`, `trade_recommendation`, `recommendation`,
  `invest`, `buy_recommendation`, and `sell_recommendation`.

Keys are normalized deterministically with Unicode NFKC, camelCase and
PascalCase boundary splitting, ASCII case folding, separator collapse, and an
explicit relevant plural-token table. Verification uses exact normalized fields
and contiguous exact token sequences; it does not use fuzzy matching.

Candidate results contain no unrestricted observation strings. Every item in
`qualitative_observations` is a canonical object with exactly
`observation_type`, `subject`, `outcome`, `reason_code`, `details`,
`assertion_scope`, and `identity`. Type, subject, outcome, and reason are drawn
from closed registries; `assertion_scope` is exactly `ENGINEERING_ONLY`; and
`details` must be the exact one-sentence rendering registered for that tuple,
with a 160-byte maximum. The details text does not control acceptance. Unknown
enums, arbitrary subjects, altered prose, additional wrappers, and inconsistent
tuple/detail combinations fail closed even after every dependent identity is
rebuilt.

The result's former implementation-note prose is now a closed list of codes:
`EVALUATOR_BINDING_VERIFIED`, `EVALUATOR_INVOCATION_REFUSED`,
`FROZEN_COMPONENTS_REUSED`, and `MISSING_INPUT_NOT_SUBSTITUTED`. Warning codes,
decision statuses, decision reasons, missing-field identifiers, anomaly codes,
labels, paths, and identities likewise have closed or exactly validated
domains. Evidence-design prose is exact frozen content and is reconstructed
canonically during verification. Consequently, there is no accepted arbitrary
publication-prose channel.

The exact observation vocabularies are:

- types: `ARTIFACT_VERIFICATION`, `DATA_AVAILABILITY`, `DATA_QUALITY`,
  `DETERMINISM`, `EVALUATOR_PATH`, `IMPLEMENTATION_BEHAVIOR`,
  `INTEGRITY_BEHAVIOR`, `LIFECYCLE_BEHAVIOR`, `MISSING_INPUT`,
  `NO_SIGNAL_REASON`, `PARSER_PATH`, `RECONCILIATION`, and
  `UNAVAILABLE_REASON`;
- outcomes: `ABSENT`, `ACCEPTED_AS_DIAGNOSTIC`, `BYTE_IDENTICAL`, `EXERCISED`,
  `INTEGRITY_FAILURE`, `MALFORMED`, `MATCHED`, `MISSING`, `NOT_EXERCISED`,
  `NO_SIGNAL`, `PRESENT`, `RECONCILED`, `REJECTED`, and `UNAVAILABLE`;
- subjects: `breakout_condition`, `candidate_result`,
  `edge_case_parser_branch`, `empirical_edge_claim`, `frozen_evaluator`,
  `frozen_evaluator_and_lifecycle`, `historical_spread_input`,
  `production_flag`, `proposal_lifecycle`, `range_invalidation`,
  `relative_volume_threshold`, `required_source_field`,
  `same_clock_volume_warmup`, `validation_input_field`, and
  `validation_outcome_access`;
- reasons: `BRANCH_COVERAGE`, `CONDITION_NOT_MET`, `COUNTS_RECONCILED`,
  `DETERMINISM_CONFIRMED`, `FIELD_NOT_PRESENT`, `FROZEN_COMPONENT_REUSED`,
  `INPUT_UNAVAILABLE`, `INSUFFICIENT_WARMUP`, `INTEGRITY_REJECTED`,
  `NO_EMPIRICAL_CLAIM`, `NO_PROPOSAL_EMITTED`, `NO_VALIDATION_ACCESS`, and
  `PROPOSAL_EMITTED`;
- scope: exactly `ENGINEERING_ONLY`.

Only prospectively registered tuple/detail combinations are valid. Adding an
enum value, subject, reason, or prose template changes the structured contract
identity and therefore requires an explicit successor contract.

The free-text-domain inventory classifies every candidate string as one of:
controlled enum, controlled identifier, exact frozen label, exact frozen text,
identity/hash, safe relative path, closed warning/reason code, or bounded
structured engineering details. `unrestricted_string_channels` is the empty
list. This distinction permits exact negative engineering statements such as
`No validation outcome was accessed.` while preventing open-ended assertions
such as `This strategy earns positive returns.`.

| Artifact domain | String treatment |
| --- | --- |
| Configuration | Exact canonical schema; frozen enums, identifiers, labels, paths, and selection text |
| Observation, child, triage, specification, preregistration | Exact frozen text reconstructed from the immutable source graph |
| Implementation binding, conformance, executor registration | Closed schemas containing controlled identifiers, booleans, hashes, and enum values |
| Evidence manifest | Closed role/path inventory with exact identities and hashes |
| Candidate result | Structured observations, controlled note/anomaly/warning/reason/status registries, exact labels, identifiers, and hashes |
| Candidate summary and run | Closed schemas; exact result/observation references, controlled counts, paths, labels, identities, and hashes |
| Exploratory manifest | Closed role/path inventory with exact labels, identities, and hashes |

No domain permits an arbitrary string that can independently assert candidate
performance, evidence status, validation, deployment readiness, or capital use.

The complete configuration, evidence manifest, eight evidence artifacts,
exploratory manifest, result, summary, and run artifact are scanned through all
nested mappings and sequences before bundle acceptance. The only negative
claim exceptions are the frozen `claim_flags` fields `capital_eligible`,
`empirical_evidence`, `holdout`, `production`, and `validation`, each requiring
the exact value `false`, plus the summary fields `economic_metrics_published`
and `empirical_conclusion_authorized` with the exact value `false`; an
affirmative value fails closed. The scanner applies independently of labels and
hashes:

> A fully rehashed prohibited claim remains prohibited.

The result, summary, and run repeat the exact observation count and ordered
observation identities. Any mismatch fails lineage verification. Manifests bind
the exact files containing those identities, so derived artifacts cannot add,
remove, or replace observations independently.

The evidence inventory is closed at exactly eight fixed role/path pairs:
observation, child hypothesis, triage, specification, implementation binding,
conformance evidence, executor registration, and their evidence manifest. The
exploratory inventory is closed at exactly one candidate result, one candidate
summary, one run artifact, and their manifest. Every inventory record binds the
exact role, path, content identity, and SHA-256. Result, summary, run, config,
dataset, implementation, and evidence identities reconcile across the graph.
Deleting, renaming, duplicating, replacing, or adding a file fails even after a
complete canonical rehash:

> A hash-consistent bundle is incomplete unless every required canonical role
> is present exactly once.

Economic metrics—including P&L, returns, expectancy, profit factor, Sharpe, and
win rate—are recursively prohibited from the published bundle. The exercise
cannot authorize validation, holdout, paper trading, live trading, an Olympics
run, deployment, or capital allocation.

## Why a child hypothesis was required

The immutable library entry
`opening-range-expansion-continuation-v001` is revision 1. It supports long and
short directions but deliberately does not select an opening-range duration,
numeric volume threshold, stop, target, or lifecycle. Choosing those rules in
place would change its meaning.

This milestone therefore creates the revision-2 child
`opening-range-expansion-continuation-long-five-minute-v001`. The child makes
no new trading-rule choice: it is an exact semantic alias of the already-frozen
`five_minute_orb_long_v002` contract. The parent remains unchanged.

## Frozen rule summary

The canonical specification in
`src/aml/opening_range_expansion_continuation_v001.py` freezes the complete
contract. In summary:

- Regular XNYS one-minute bars use left-labeled `[t,t+1 minute)` intervals.
- The opening range is the unrounded high and low of the complete 09:30–09:34
  bars and becomes available at 09:35 New York time.
- Decisions occur from 09:35 through 10:59 on completed bars.
- A long trigger requires a close strictly above the range high and same-clock
  volume at least 1.5 times the median of exactly 20 eligible prior sessions.
- Any post-range close below the range low before a trigger invalidates the
  setup.
- Entry is the exact next complete bar's raw open with the frozen 10-basis-point
  adverse-friction assumption.
- The stop is the range low rounded down to one cent; the target is two times
  initial risk above the cost-adjusted entry, rounded up to one cent.
- The frozen lifecycle applies the shared event precedence, 120-complete-bar
  timeout, session liquidation, commissions, exposure, and risk rules.
- Missing range bars, fewer than 20 eligible histories, or a missing next bar
  produce unavailable/no-trade decisions. Values are never forward-filled.
- Duplicate or non-monotonic timestamps and invalid OHLCV values fail through
  the unchanged integrity path.

The canonical specification identity is
`13611f02dcb749c0f8f13ffae5485dfa87df8b469baf9e59044c9d4b698a5494`.

## Implementation and identity binding

The child executor in
`src/aml/benchmark_candidate_opening_range_expansion_v001.py` delegates every
decision to `five_minute_orb_long_v002`. Before evaluation it verifies the
frozen strategy, executor, and lifecycle identities. The executable evidence
binds:

- the immutable parent and new child identities;
- the canonical specification;
- the exact source-file hashes;
- the frozen reference strategy, executor, and lifecycle identities;
- a committed synthetic fixture used only for conformance;
- the registered child evaluator;
- positive, negative, unavailable, integrity-failure, causal, deterministic,
  and proposal-lifecycle checks.

Canonical evidence is written as immutable JSON beneath
`manifests/opening_range_expansion_continuation_v001/`.

The current candidate configuration identity is
`c832be1b9b92a2b58906a597e7bfd95dee3a10aba664b6f201868d243f1e89da`.
The implementation binding is
`9c3c42e5ccd38a6eb58a8db01ae35a7b928c84cfc2fac246768faf8415b8a661`,
conformance is
`84023264f928dfc63d68001785006b807b5c0ae7e58078cd997fa8b6f1d258b0`,
and executor registration is
`d33e589fae8a4fb46fc513ad8335ba83611783d119ef032d18ea0d594f728af4`.

## Bounded exploratory dataset

The diagnostic plan is frozen before outcome access. It uses the already
available contaminated Alpaca SIP research vintage and does not authorize it as
point-in-time empirical evidence. The selection is five lexicographically
fixed liquid symbols (`AAPL`, `AMD`, `NVDA`, `PLTR`, `TSLA`), the first 20 XNYS
sessions in the dataset as same-clock-volume warm-up, and the next five sessions
for evaluation. This is 125 inspected symbol-session partitions: 100 warm-up
and 25 evaluated.

The source manifest, dataset fingerprint, selected dates, symbols, partition
hashes, implementation hashes, and claim policy are content-bound. Missing,
gappy, rehashed, or malformed partitions fail closed. Exploratory outputs are
write-once, outside Git, and limited to:

- partitions inspected;
- trigger, proposal, completed-lifecycle, rejection, unavailable, and integrity
  counts;
- deterministic decision reasons;
- missing-data and contamination warnings;
- qualitative engineering observations.

No raw provider payload, trade economics, or accepted research publication is
stored in the repository.

## Bounded diagnostic result

**EXPLORATORY ONLY — CONTAMINATED DATA — NOT EMPIRICAL EVIDENCE**

After the specification, identities, and conformance tests were frozen, the
bounded exercise inspected 125 partitions (100 warm-up and 25 evaluated) and
made 2,125 causal decision evaluations. It recorded:

- 177 triggers/proposals;
- 10 completed lifecycles;
- 167 lifecycle rejections;
- zero unavailable evaluations;
- zero integrity failures;
- 1,948 no-signal decisions: 515 below the range-break condition, 978 after
  range invalidation, and 455 below the volume threshold.

These counts are engineering diagnostics only. They say that the implementation
triggers and reconciles under this bounded contaminated input; they say nothing
about economic quality. The persisted non-economic bundle was structurally
migrated without rerunning external market data. Its write-once run identity is
`e85c407578c94484b54a4fde04e57a47baa6346980004f6c8b29ef8998f3426e`
and its manifest identity is
`aa3d0f3c9747a1dcc9b4e10d4b3ecebb69fae3e151fceb52e80ad756b89389ac`.
The candidate result identity is
`8dcaf85125255321a5b7b8a83d204c7264aac4095760d8286baeba7bd69e4245`
and the run-summary identity is
`9010fc6e6b9ff602c6bd06a2440fe4fdac1a8d7845af25183898797af271001f`.
The explicit run-artifact identity is
`ce6ceadc177c806f79b3d34613992c95e997908f566e6f303e7226503df6fdcc`.
The run binds evidence manifest
`5e42cbae714035ce64dbdc455e542e5e761f4d8d6b12dc777785f758121a452e`
and its exact child, preregistration, implementation, conformance, and executor
registration identities.
Independent runs under `PYTHONHASHSEED=1, TZ=UTC` and
`PYTHONHASHSEED=777, TZ=Asia/Tokyo` were byte-identical.

## Commands

Build and verify the canonical non-empirical evidence:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_opening_range_expansion_continuation_v001.py
PYTHONPATH=src .venv/bin/python scripts/run_opening_range_expansion_continuation_v001.py --verify-only
```

The bounded exercise additionally requires the exact pre-existing dataset root
and a new path under an external `exploratory_research/v001/` namespace:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_opening_range_expansion_continuation_v001.py \
  --dataset-root /path/to/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001 \
  --exploratory-output-root /external/path/exploratory_research/v001/run-id
```

An existing output path is always rejected; reruns require a distinct empty
destination and must reproduce the same run and file identities.

## Remaining empirical blocker

Historical point-in-time dataset authorization remains unresolved. The current
dataset lacks the evidence required by the frozen authorization assessment,
including written licensing/retention proof, provider-echoed feed identity,
point-in-time corporate-action lineage, and an uncontaminated discovery sample.
Accordingly, this milestone cannot produce or support a conclusion about edge,
profitability, robustness, validation eligibility, or capital use.
