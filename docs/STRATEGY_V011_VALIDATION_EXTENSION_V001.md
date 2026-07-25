# Strategy V0.1.1 validation extension V001

Status: **preregistered; acquisition and results not authorized by this document**.

This design freezes `attention_momentum` Strategy V0.1.1 and prepares the next
untouched chronological validation block. It does not claim profitability. The
corrected validation result is period-concentrated and statistically
inconclusive. Optimization is not authorized.

## Protected research compartments

- Frozen production-candidate: `attention_momentum` V0.1.1, unchanged.
- Observational context: additive metadata that cannot affect decisions or P&L.
- Strategy shadows: independently versioned, zero-capital research proposals.
- Rejected-proposal shadows: non-deployed counterfactual paths, never portfolio P&L.
- Sealed holdout: remains untouched and may not be listed, read, hashed, or analyzed.

## Chronological block

The extension is the inclusive calendar interval **2026-07-27 through
2028-07-26**. July 27, 2026 is the first eligible XNYS session strictly after
this preregistration was committed, and no extension results were accessed when
the boundary was selected. The end moved by the same three calendar days as the
start, preserving the original 731-day inclusive duration. It cannot be
shortened or extended because of P&L, trade count, market conditions, data
availability, or checkpoint results.

No date in this extension may have been used for development, prior validation,
diagnosis, robustness review, parameter selection, or the sealed holdout. A date
failing that test is rejected; it is not replaced with an outcome-selected date.

## Universe and point-in-time eligibility

The ordered universe remains exactly:

`SPY, QQQ, IWM, DIA, TQQQ, SQQQ, SPXL, SPXS, GLD, SLV, USO, TLT, XLF,
XLK, XLE, UVXY, GME, AMC, AAPL, TSLA, NVDA, AMD, PLTR`.

No symbol may be added, removed, promoted, replaced, or weighted because of a
historical winner, loser, April behavior, volatility, or expected result. UVXY
remains included; TQQQ receives no preference.

For each session, a symbol must have point-in-time evidence that it was listed
and active under the historical symbol identity then effective. Delisted names
remain in the frozen universe but generate no eligible session after delisting.
Ticker changes require a verified, effective-dated symbol-history mapping; the
economic security is not duplicated under old and new tickers. Splits, reverse
splits, dividends, mergers, distributions, and other corporate actions require
effective-dated source records and consistent price/volume treatment. Missing,
malformed, stale, conflicting, or incomplete listing, symbol-history, or
corporate-action records reject the symbol-session before strategy evaluation.
Reference records must include source-as-of time and finalized source hash.

## Market data and sessions

- Feed: Alpaca SIP, one-minute bars.
- Regular session: official exchange calendar, 09:30–16:00 America/New_York,
  including official early closes.
- Premarket observational cutoff: 09:29:59 America/New_York. Premarket data is
  context only and cannot affect V0.1.1.
- Bar timestamp semantics and the exact elapsed-five-minute return behavior stay
  identical to corrected V0.1.1.
- Verified halts and resumptions are removed from effective missing-minute
  counts. Unverified gaps remain missing data.
- The existing maximum missing-regular-session fraction, validation suite,
  next-minute entry, slippage, stop, target, position-risk, one-position,
  holding-period, and exit behavior remain frozen.
- An incomplete or stale SIP partition, unavailable session metadata, malformed
  timestamps, hash mismatch, or failed quality check rejects the symbol-session.
  Failures are recorded; historical files are not silently repaired.

## Frozen strategy and accounting

Strategy ID, version, parameter hash, score components, threshold, eligibility,
entry timing, slippage, stop, target, risk fraction, maximum holding period, and
exit ordering must match the corrected baseline exactly. Context and shadow
fields are prohibited inputs to eligibility, ranking, acceptance, sizing,
execution, or exits.

The tournament replays strategy/symbol/day units with a resetting $2,000
reference allocation. Aggregate P&L divided by $2,000 is a reference-capital
statistic, not a continuously deployable portfolio return, and must always be
reported with that qualification.

## Checkpoints and permitted analysis

The corrected baseline contains 214 accepted V0.1.1 trades. Reviews occur when
the chronologically accumulated total first reaches 250, 500, and 1,000 trades.
Crossing a checkpoint never changes the fixed end boundary and never authorizes
optimization. Reaching 100 trades is only a reporting minimum, not proof of
statistical certainty.

At each checkpoint, the following fixed descriptive outputs are permitted:

- counts, acceptance, P&L, reference return, drawdown with ordering semantics;
- results by date, week, month, symbol, direction, score band, entry-time bucket,
  and exit reason;
- cumulative P&L, 20-trade rolling expectancy/win rate/profit factor;
- leave-one-date-out and leave-one-symbol-out results;
- predeclared period and symbol concentration measures;
- ordinary trade bootstrap for comparison and date-cluster bootstrap as primary,
  using a recorded deterministic seed;
- percentile intervals for net P&L, expectancy, and win rate, plus the estimated
  probability expectancy exceeds zero;
- comparison with the frozen development and corrected validation distributions;
- observational context completeness and distributions, without selection.

No threshold search, parameter sweep, date removal, symbol filtering, alternate
exit, alternate sizing, outcome-derived regime label, or shadow promotion is
permitted. Optimization remains prohibited while any checkpoint is below 1,000
cumulative trades, while the primary uncertainty interval spans zero, while
material single-date/period concentration remains, while source integrity is not
clean, or while the preregistered block is incomplete. Passing those conditions
would permit a separate authorization decision, not automatic optimization.

## Observational and shadow rules

Context schemas are versioned and point-in-time. Unavailable sector, event,
spread, benchmark, reference, or premarket information remains null with an
explicit source/status reason; it is never inferred. Event labels require a
source published no later than the decision time. Unknown is mandatory when no
valid decision-time source exists. Retrospective labels based on trade outcomes
are prohibited.

Shadow strategies and rejected-proposal outcomes receive zero capital, cannot
consume position slots, and cannot change V0.1.1 ordering or P&L. Their records
must say `deployed=false`, `capital_allocation=0`, and
`included_in_portfolio_pnl=false`. Shadow results are never combined with the
production-candidate portfolio.

## Authorization boundary

This task authorizes schema work, documentation, synthetic fixtures, and
already-approved development-only engineering rehearsal. It does not authorize
broad extension acquisition, extension replay, result inspection, holdout
access, live trading, broker execution, adaptive allocation, commit, or push.
