# VWAP Deviation Mean Reversion — Prospective Child V001

## Scientific boundary

This milestone is **EXPLORATORY ONLY**, uses **CONTAMINATED DATA**, and is
**NOT EMPIRICAL EVIDENCE**, **NOT VALIDATION**, **NOT HOLDOUT**, **NOT
PRODUCTION**, and **NOT CAPITAL ELIGIBLE**. It does not inspect or publish an
economic outcome.

## Parent semantic audit

The immutable `vwap-deviation-mean-reversion-v001` parent supplies the market
assumption, convergence mechanism, directional arms, developing-VWAP concept,
failure-to-extend concept, liquidity qualification concept, and VWAP-or-partial
convergence exit concept. It deliberately does not fix direction, deviation
normalizer or threshold, liquidity/spread rule, failure-to-extend sequence,
timing, stop, exact target, timeout, duplicate policy, or missing-data
precedence. The parent therefore remains unchanged and is not itself executable.

## PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES

Before any exploratory outcome access, revision 2 freezes a long-only exact
semantic alias of the existing `vwap_mean_reversion_fade_long_v002` contract.
The choice is based on simplicity, interpretability, OHLCV compatibility, and
exact reuse—not observed performance.

- XNYS regular-session minute bars only; decisions 09:50–15:00 and entries
  09:51–15:01 New York time.
- Frozen cumulative regular-session HLC3-volume VWAP and Wilder ATR20.
- Current close must remain at least `1.5 × ATR20` below current VWAP.
- The three bars immediately before confirmation must each decline, with
  strictly decreasing positive decline magnitudes from oldest to newest.
- Confirmation is the next completed bar closing strictly above the immediately
  prior close while the `1.5 × ATR20` extension remains true.
- Signal is confirmation-bar end; entry is the exact next-bar open.
- Stop is the minimum low of the three decline bars and confirmation bar minus
  `0.25 × ATR20`, rounded down to one cent.
- Target is signal-time VWAP, frozen for lifecycle and rounded under the shared
  lifecycle contract.
- Timeout is 60 complete bars. Shared gap/stop/target/session precedence,
  cost, risk, and portfolio admission remain unchanged.
- Maximum two entries per symbol-session with a 20-complete-bar cooldown.
- Missing next bar, ATR20, or VWAP is unavailable; malformed or unclassified
  input fails integrity closed. No interpolation or forward fill is permitted.

The child identity and canonical specification are content-addressed. Any later
semantic change requires a new child identity.

## Existing capability audit

`vwap_reclaim_long_v002` is materially different: it requires a three-bar
below-VWAP sequence, two closes above contemporaneous VWAP, and prior-bar
relative volume. `vwap_mean_reversion_fade_long_v002` is exact: its deviation,
deceleration, confirmation, entry, stop, target, timeout, duplicate, missing
data, integrity, and precedence rules match this child field-for-field. The
adapter delegates every decision to that frozen evaluator and verifies its
strategy, executor, indicator, and lifecycle identities before use.

## Preregistration and conformance

The preregistration binds the immutable parent, child, specification, exact
reference executor, synthetic conformance fixture, contaminated dataset
fingerprint, and claim ceiling before the bounded exercise. Conformance covers
positive proposal, absent deceleration, insufficient extension, absent positive
confirmation, ATR warm-up, missing next bar, cooldown, maximum entries,
malformed/gapped integrity failure, no-lookahead, lifecycle completion,
stop-before-target collision, timeout, and deterministic repeatability.

## Exploratory diagnostics

The prospective freeze was committed before execution. The bounded run then
inspected 920 partitions (460 selection-warm-up, 460 evaluated) and made
149,960 causal decisions, of which 109,859 passed common/state availability
gates. It recorded:

- 411 triggers: 406 proposals and five deterministic pre-entry `no_trade`
  decisions;
- 194 completed lifecycles and 212 lifecycle rejections;
- 149,549 no-signal decisions, zero unavailable decisions, and zero integrity
  failures;
- exact decision reconciliation:
  `149,960 = 149,549 + 5 + 406 + 0`;
- exact lifecycle reconciliation: `406 = 194 + 212`.

The dominant no-signal reasons were non-strict deceleration (101,864), maximum
entries reached (20,037), price above the frozen ceiling (12,283), outside the
observation window (6,189), cooldown active (4,847), price below the frozen
floor (2,934), missing positive confirmation (953), and extension below the
frozen threshold (442). These are implementation diagnostics, not economic
results.

The write-once run identity is
`0296941d9ab20f61b538b35d9d8675cb6f5e048f6f72cadee5f9d483515f13d5`;
the exploratory manifest identity is
`4c279bdaa524260edfca3ee97c3ab902818df1de8adaf8a29953c0fede696f0e`;
and the candidate-result identity is
`b400983034d7e0c8765e1b8070ed44b099a67aeca5f9ce86e22095cea2220fc8`.
Runs under `PYTHONHASHSEED=1, TZ=UTC` and `PYTHONHASHSEED=777,
TZ=Asia/Tokyo` were byte-identical.

## Five-mechanism engineering comparison

| Mechanism | Engineering behavior | Principal dependency / complexity |
|---|---|---|
| First-pullback continuation | Executable multi-stage impulse, retracement, and resumption chain; committed records do not provide a like-for-like 460-partition diagnostic | OHLCV, ATR, local volume; highest state complexity |
| Opening-range expansion continuation | 25 evaluated partitions; 177 proposals; 10 completed, 167 rejected; zero unavailable/integrity | Five-minute range plus 20-session same-clock volume |
| Volatility-expansion breakout | 460 evaluated; 194 proposals; 128 completed, 66 rejected; 6,602 ATR warm-up unavailable; zero integrity | ATR20, prior-15 high, adjacent continuation, same-clock volume |
| Opening-range failed-breakout reversal | 460 evaluated; 145 triggers, 102 proposals; 88 completed, 14 rejected; 413 ATR warm-up unavailable; zero integrity | Opening range, ATR20, adjacent reclaim, same-clock volume, midpoint feasibility |
| VWAP-deviation mean reversion | 460 evaluated; 411 triggers, 406 proposals; 194 completed, 212 rejected; zero unavailable/integrity | Session VWAP, ATR20, four-bar deceleration/confirmation; exact frozen-evaluator reuse |

This adds a fifth genuinely distinct mechanism: continuous session-consensus
reversion rather than opening structure or directional continuation. The local
dataset is broad enough for a unified contaminated engineering campaign across
the mechanisms, but not for authorized empirical conclusions.

The aggregate completed-lifecycle volume now justifies designing a separate,
explicitly contaminated economic proof-of-concept readout solely to test cost,
metric, and reconciliation plumbing. Such a future readout must prospectively
include every mechanism, prohibit selection/ranking and rule changes, remain in
a separate non-evidence namespace, use no validation/holdout data, confer no
advancement or capital status, and state that its outputs cannot support an edge
claim. No economic field was inspected in this milestone.

The next current-data mechanism recommended for prospective design is
`first-half-hour-to-close-momentum-v001`, because it adds a time-of-day,
longer-horizon mechanism without new data. The largest remaining data-family
unlock is authorized point-in-time auction/imbalance and signed-flow history;
authorized PIT provenance and licensing remain the principal blocker to any
empirical conclusion.

**NO ADDITIONAL GENERIC INFRASTRUCTURE RECOMMENDED.**

## Frozen boundaries

The benchmark framework, hypothesis library, existing strategies, proposal
simulator, lifecycle, integrity verifier, empirical publication, Historical PIT
Dataset Authorization, validation, holdout, Olympics, capital governance, and
broker interfaces are unchanged.
