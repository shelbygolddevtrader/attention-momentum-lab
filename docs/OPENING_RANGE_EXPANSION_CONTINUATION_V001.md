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

In addition, every candidate result, run summary, and manifest carries the
candidate-specific, identity-bound singleton field
`candidate_specific_labels: ["NOT EMPIRICAL EVIDENCE"]`. This additive field
does not rename or extend the frozen global label contract. The candidate
verifier requires the exact capitalization and spelling on every manifested
artifact and rejects missing, synonymous, inconsistent, stale, or tampered
values.

The candidate also binds prohibited-claim contract
`570f78c5fd89e9e7558ea46d11b700f06d45c37c2724e691da7aa8131edf06ab`
to its configuration, result, summary, and manifest. The exact prohibited field
vocabulary is:

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
and explicit prohibited tokens; it does not use fuzzy matching. String values
are scanned everywhere, including under unexpected wrappers and in nested
sequences. Exact frozen negative labels and the non-empirical evidence-class
value are the only permitted strings containing otherwise prohibited tokens.

The complete manifest object and every manifested artifact are scanned through
all nested mappings and sequences before bundle acceptance. The only negative
claim exceptions are the frozen `claim_flags` fields `capital_eligible`,
`empirical_evidence`, `holdout`, `production`, and `validation`, each requiring
the exact value `false`, plus the summary fields `economic_metrics_published`
and `empirical_conclusion_authorized` with the exact value `false`; an
affirmative value fails closed. The scanner applies independently of labels and
hashes:

> A fully rehashed prohibited claim remains prohibited.

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
about economic quality. The write-once run identity is
`7cc0d67b68a2d21a47d030f00a96cd236c777631fde8bb8efb39f3e2ef367b9e`
and its manifest identity is
`783031da7d6f369feb3cf5e2e53c0124bc178e5e19b74ef0976ba8cec19d00cb`.
The candidate result identity is
`2bf0ad58926f01f8d00ddb9f1f5bda61b543db33630cc51c784df44f3a540126`
and the run-summary identity is
`6517f0901c7ccbb2ad1d3e7aa73bfa19cf46214ca1cf6cdd81c72add6322eeca`.
The run binds evidence manifest
`0ee1a4dfd9d1ecd3bef9a92dc09f475d4af1aa236d120f408c4a6f5889459a41`
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
