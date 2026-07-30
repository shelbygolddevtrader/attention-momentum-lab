# Professional Strategy Benchmark Olympics V002

Status: **prospectively specified, design-only, implementation not authorized**.

V001 established the benchmark families and governance boundaries but could not
support one unambiguous implementation. ATR, VWAP, volume history, lifecycle,
and several strategy anchors admitted multiple signal-changing interpretations.
V002 resolves those choices before empirical access. V001 remains unchanged and
historically identifiable; V002 is a new specification, not a reinterpretation.

The authoritative machine-readable bundle is
`config/professional_strategy_olympics_v002.json`. The validator is
`scripts/validate_professional_strategy_olympics_v002.py`. It returns status 2
even when valid because implementation and empirical execution remain blocked.

## Identity lineage

| Component | V001 | V002 |
| --- | --- | --- |
| Overall protocol | `8a7f4c2ca1c6b133e769992ef8315186de87b0f7f1baedf6d549536db6f72f3e` | `fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583` |
| Strategy registry | `af1e44069fd5e226ad702469fdf10c7e0b1c49c803065e20c83588b22e17bbc0` | `5a43302ca893bcb9323b0a0b473282abd36d0b4d0917322dfb5c817ca3bfd43a` |
| Tournament | `10d41bf657759b5db5b5524a18158a480797ab9dcfcca59e7921672d31bb70aa` | `f011b03b6d4b4249e4c4d77b029cbb74145c7f7f53486e0af89d0433da395308` |
| Readiness | `ebe1179fea526e4bad0c808609ff68320840d57d2172355227edfeccaf054602` | `fb9799d8cda9a671a58408f0d540d7a6ab39fe868163a2ce105eb6f1218de03b` |

New V002 shared identities:

- indicators: `3d1427872fc8d55e3cacc321f710a6a2b260d0a1d01259147b6ff3a422a6f852`
- inputs: `a3fc7f17fb30eaf69ec00f2955f68f1b54dc3247edc54590706abee719ba3fac`
- lifecycle: `b61fa2557718cdf1dbebc0e91990bb27be3d880111bea424d967dd96253dfe12`
- costs: `ba239ed1b835d91be06a674433559c2b679c07fd37b9820f0c4fe7cf7ada4570`
- evidence classification: `36eb12d994052735aa084f56951db088e5b1ef46d4bde856e5eba4e355d43172`
- zero-item unresolved register: `1c7e480fdf5a69a7ad4b7af6f78131181b140dbe30ef402c5bd5e5cdeb1bc0bf`

## Shared indicator resolutions

ATR20 is regular-session Wilder ATR. True range is the maximum of high minus
low and the two distances from the prior close. The first regular bar uses high
minus low, thereby excluding the overnight gap. The first ATR is the mean of 20
consecutive true ranges; subsequent values use `(19 × prior ATR + TR) / 20`.
Premarket is excluded, sessions reset, and a gap or halt requires 20 new bars.

Regular VWAP uses HLC3 times volume, starts at 09:30, excludes premarket, and
resets each session. Premarket VWAP is a separate 04:00–09:29 indicator. A
zero-volume bar leaves cumulative sums unchanged. A non-halt missing bar makes
the relevant VWAP unavailable from that point.

RSI14 uses 15 regular-session closes to seed 14 Wilder gains and losses, then
uses the Wilder recurrence. It resets by session. Both averages zero produces
50; zero loss with a gain produces 100; zero gain with a loss produces zero.

Intraday relative volume uses the median of the immediately preceding 20
complete regular bars and excludes the current bar. Same-clock relative volume
uses the exact clock minute from 20 prior complete eligible sessions, searching
no more than 40 sessions. Premarket relative dollar volume compares the complete
04:00–09:29 total against the median of 20 prior complete premarkets. Local
five-bar volume compares the five-bar sum against five times the median of the
20 bars ending before that five-bar window. No baseline is winsorized.

Exact elapsed returns require both exact timestamp endpoints. Missing endpoints
are unavailable rather than replaced by row offsets.

## Data resolutions

All minute bars are left-labeled intervals `[t, t+1 minute)` and become
available only at `t+1 minute`. The symbol and SPY require exact timestamp
alignment with zero tolerance. Prices must be positive and finite, volume must
be nonnegative, timestamps must be monotonic and unique, and every absent minute
must be explained by authoritative halt evidence.

Historical liquidity is the median regular-session HLC3 dollar volume of the
previous 20 complete non-early-close sessions, searching at most 40 sessions.
The frozen threshold is $5 million.

Prior close is the immediately preceding eligible XNYS official close, no more
than five calendar days old. Extended-hours prices cannot substitute. The gap is
`09:30 open / adjusted prior close - 1`. Splits adjust historical prices and
inverse-adjust volumes. An ex-date cash distribution is removed from prior
close before the current open. Unknown, conflicting, broken-lineage, or
mid-session actions fail closed.

Halts require both positive and negative authoritative coverage. Halt intervals
are half-open. A missing bar is a halt only when that interval proves it. No
signal is allowed during a halt or the first five complete post-resume bars;
entry during a halt is canceled. Existing positions wait for the first
executable reopen, where stop-before-target precedence applies.

Market-regime eligibility was prospectively removed from the market-relative
contract. Frozen regime labels may later be reported descriptively but cannot
filter V002 opportunities.

## Shared lifecycle

A completed source bar labeled `t` creates a signal at `t+1 minute`. The
intended entry is the exact next bar open, which has the same timestamp as the
signal. There is no delayed fill: a missing or halted next bar rejects the
entry. Simultaneous events sort by signal time, strategy identity, then symbol.

Stops and targets are absolute adjusted prices frozen at the signal. Long stops
round down to one cent and targets round up. An open below a stop exits at the
open; an open above a target exits at the open. Stop precedes target whenever
both are possible in one bar. Indicator-derived targets, including VWAP, freeze
at the signal and never move after entry. A target not above the cost-adjusted
entry rejects the trade.

Holding periods count complete regular one-minute bars beginning with the entry
bar. Exit occurs at the close of the final holding bar or the 15:55 bar,
whichever comes first; early closes use the fifth bar before scheduled close.
Missing liquidation or non-halt position bars are integrity failures, not
fabricated fills.

Market friction is 10 basis points adverse per side, representing combined
spread and slippage. Long entry is raw open times 1.001 and long exit is raw
exit times 0.999. Commission remains $0.005 per share with a $1 minimum on each
entry and exit order. Risk is $250 per trade, capped by 50% gross exposure,
$100,000 initial capital, three concurrent positions, and the 1% daily new-entry
loss stop. Net R is net P&L divided by $250.

## Ten canonical contracts

1. `failed_downside_breakdown_reclaim_long_v002` resolves the naming conflict as
   a bullish failed downside breakdown. It breaches a mature session low by
   0.25 ATR, reclaims within three bars, confirms one bar later with relative
   volume at least 1, stops below the breach structure by 0.05 ATR, targets 2R,
   and holds at most 60 bars.
2. `first_pullback_continuation_long_v002` uses the earliest running low and
   first later 3% high with 2x local volume. The first 2–10-bar pullback must
   retrace 20–50%, preserve the 50% level, and contract volume. A close above
   the prior high triggers; stop is pullback low minus 0.05 ATR, target 2R, and
   timeout 90 bars.
3. `five_minute_orb_long_v002` uses exactly bars 09:30–09:34. The first completed
   close above the range high with 1.5x same-clock volume triggers. Range low is
   the stop, target is 2R, and timeout is 120 bars.
4. `fifteen_minute_orb_long_v002` independently uses exactly 09:30–09:44 with
   otherwise separately frozen 1.5x volume, range-stop, 2R, and 120-bar rules.
5. `gap_and_go_long_v002` requires a 4% gap, $250,000 premarket dollar volume,
   1.5x premarket ratio, and $5 million historical liquidity. After the opening
   five bars it requires a 2–10-bar consolidation no wider than 1 ATR, then a
   close above fixed premarket high and regular VWAP with 1.5x local volume.
6. `high_of_day_breakout_long_v002` uses a high established at least 15 bars
   earlier, an immediately prior five-bar consolidation at most 0.75 ATR wide,
   no more than two defined failed attempts, and 1.5x relative volume. Stop is
   consolidation low, target 2R, and timeout 90 bars.
7. `market_relative_momentum_long_v002` requires exact synchronized 15-minute
   symbol and SPY returns, positive symbol return, at least two percentage points
   outperformance, 1.5x volume, $5 million liquidity, and SPY at or above its
   regular VWAP. Stop is the 15-minute low, target 2R, timeout 120 bars.
8. `rsi_exhaustion_reversion_long_v002` requires RSI14 at most 25, price below
   regular VWAP, a symbol 20-minute return at most -2%, SPY return above -1%, and
   $5 million liquidity. Reversal requires a close above prior high and rising
   RSI. Target is the lower of frozen signal VWAP and 2R; an invalid target
   rejects entry. Timeout is 60 bars.
9. `vwap_mean_reversion_fade_long_v002` requires a 1.5 ATR downside extension,
   three immediately preceding strictly declining bars whose decline magnitudes
   strictly decrease, then a positive close confirmation while still extended.
   Stop is structure low minus 0.25 ATR and frozen signal VWAP is the target.
10. `vwap_reclaim_long_v002` selects the most recent maximal run of at least
    three closes below contemporaneous VWAP, followed immediately by two closes
    above. The second reclaim needs 1.2x volume. The selected run low is the
    stop, target is 2R, and timeout is 90 bars.

Equal extrema always use the earliest timestamp unless the contract explicitly
selects the most recent qualifying sequence. Every contract has one canonical
specification and no alternatives.

## Evidence and implementation boundary

Contract presence earns no score. A future strategy may receive discovery
results only after its complete contract-aware evaluator, every required input,
all integrity checks, minimum event sample, reconciled trade/no-trade audit, and
separate human discovery authorization pass. Synthetic fixtures are explicitly
non-empirical and cannot satisfy trade count, expectancy, drawdown, advancement,
or statistical evidence.

Each contract declares future positive, negative, unavailable, and integrity
fixture blueprints. The later empirical implementation must calculate every
indicator causally, emit canonical signal and next-entry timestamps, implement
the frozen lifecycle and costs, and preserve auditable reason codes. The generic
simulator must not be modified merely to imply compatibility; a separate
contract-aware evaluator is required.

V002 has zero material unresolved design items, but readiness remains
`design_complete_implementation_not_authorized`. No empirical data informed
V002. No discovery result, tournament score, medal, winner, validation, or
strategy-performance claim exists. No paper trading, live trading, provider
purchase, capital release, or production use is authorized.
