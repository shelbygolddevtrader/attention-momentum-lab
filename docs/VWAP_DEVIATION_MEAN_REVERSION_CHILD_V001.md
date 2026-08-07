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

The bounded 920-partition diagnostic and five-mechanism engineering comparison
are recorded after execution in this section. No economic metric is permitted.

_Prospective freeze recorded before exploratory execution; diagnostic counts
pending._

## Frozen boundaries

The benchmark framework, hypothesis library, existing strategies, proposal
simulator, lifecycle, integrity verifier, empirical publication, Historical PIT
Dataset Authorization, validation, holdout, Olympics, capital governance, and
broker interfaces are unchanged.
