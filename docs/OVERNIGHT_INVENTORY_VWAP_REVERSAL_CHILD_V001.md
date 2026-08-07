# Overnight Inventory / VWAP Reversal — Prospective Child V001

This milestone adds one lower-turnover overnight-inventory reversal experiment.
It is contaminated exploratory work. It is not empirical evidence, validation,
holdout research, statistical proof, production readiness, or capital eligibility.

## Immutable parent and semantic audit

`overnight-inventory-reversal-to-vwap-v001` is the closest library parent. It
explicitly hypothesizes that one-sided overnight inventory may normalize toward
developing session VWAP. The gap-exhaustion parent instead targets prior-close
gap closure and introduces low-volume nonconfirmation.

The selected parent fixes the economic mechanism, opposite-gap direction, VWAP
role, intraday horizon, and required prior close. It does not fix a direction,
universe, gap threshold, observation clock, failure test, entry, stop, target
precedence, timeout, or missing-data rules. It is therefore not executable and
the child is not represented as an exact alias.

## Prospective human-authorized design choices

All rules below were frozen before candidate outcome access:

- long-only gap-down reversal in `DIA`, `IWM`, `QQQ`, and `SPY`;
- gap is current 09:30 open divided by the immediately prior bound regular-
  session final minute close, minus one;
- inclusive gap threshold is negative 0.50 percent;
- one decision after bars 09:30–09:44;
- 09:44 close must exceed 09:43 high and remain below developing session VWAP;
- entry is the exact 09:45 next-bar open;
- stop is the first-fifteen-minute low, floored to one cent;
- target is signal-time HLC3-volume session VWAP, frozen and ceiled to one cent;
- timeout is 120 complete bars with unchanged session fallback;
- maximum one proposal and no re-entry per symbol-session;
- unchanged shared costs, sizing, lifecycle, and conservative event precedence.

These are **PROSPECTIVE HUMAN-AUTHORIZED DESIGN CHOICES**, not rules uniquely
implied by the parent. No alternative direction, threshold, clock, or exit was
tested or compared.

Expected mechanical turnover is at most one trade per symbol-session. Expected
holding time is minutes to two hours, materially slower than repeatedly scanned
intraday mechanisms while retaining a single early-session decision.

## Data compatibility and limitation

The existing contaminated dataset contains all required regular-session minute
OHLCV, session VWAP inputs, session closes, and the prior bound session's final
minute close for the four fixed ETFs. The prior-close input inherits Alpaca's
`adjustment=all` historical-bar lineage. It is sufficient only for contaminated
development exercise; it is not an independently authoritative PIT official
close and cannot support empirical conclusions.

The first of 753 sessions per symbol supplies prior-close warm-up. The remaining
752 sessions per symbol are evaluated prospectively, for 3,008 decisions from
3,012 inspected partitions. No outcome-based partition selection is permitted.

## Conditional economic POC

The candidate-only contaminated economic POC is prospectively bound to the
merged Contaminated Economic POC V001 methodology. It may run only if the frozen
engineering exercise completes at least 30 lifecycles. It uses the same base,
1.5×, and 2× cost cases, R semantics, metrics, and coarse interpretations. It
does not authorize any strategy change or empirical conclusion.

## Boundaries

No optimization, parameter search, validation, holdout access, forward test,
paper/live trading, broker interaction, Olympics execution, or capital action is
authorized. Any semantic revision requires a new child identity.

## Bounded engineering result

The immutable child inspected 3,012 partitions, including four prior-close
warm-up partitions, and evaluated 3,008 symbol-sessions. It produced 3,008
causal decisions: 2,592 no-signal, 8 pre-entry no-trade, 21 proposals, and 387
unavailable. The unchanged lifecycle completed 12 proposals and rejected 9;
there were zero integrity failures.

Reconciliation is `3,008 = 2,592 + 8 + 21 + 387` and `21 = 12 + 9`.
Dominant no-signal reasons were insufficient gap magnitude (2,219), absent
adjacent upside reversal (300), and signal close not below VWAP (73). The eight
pre-entry failures had no target room after next-open friction. Unavailability
was entirely fail-closed source completeness: 287 current sessions and 100
prior-close sessions contained source-declared regular-minute gaps.

The frozen 30-completed-lifecycle gate was not met, so the candidate-only
contaminated economic POC did not run and no economic outcome was inspected.
The result adds a distinct mechanism and shows that the current data can exercise
it broadly, but sparse signals and incomplete regular sessions prevent an
informative candidate economics readout under V001.

The next current-data mechanism should be a prospective
`failed-volume-breakout-reversal-v001` child, which can use existing OHLCV and
volume primitives while adding a distinct rejection/reversal mechanism.

NO ADDITIONAL GENERIC INFRASTRUCTURE RECOMMENDED
