# Professional Strategy Registry V001

The registry is a prospective set of complete, immutable mechanical contracts.
It is not an implementation and does not call the existing simulator. Every
contract records eligibility, required fields, observation and entry windows,
the exact completed-bar trigger, next-bar entry, stop, target, maximum hold,
end-of-day exit, sizing, costs, missing-bar and halt treatment, corporate-action
policy, conservative same-bar ordering, duplicate handling, cooldown, position
limits, regime reporting, invalidators, evidence, claim ceiling, and lookahead
prohibition.

| Contract | Mechanical defining condition | Canonical availability |
| --- | --- | --- |
| Failed-breakout reversal | breach of a 15-bar-old low, recovery within three bars, one-bar hold | long, eligible |
| First-pullback continuation | 3% early impulse, 2x volume, first 20–50% retracement, close confirmation | long, eligible |
| Five-minute ORB | close above completed five-bar opening range with 1.5x point-in-time volume | long, eligible |
| Fifteen-minute ORB | close above completed fifteen-bar opening range with 1.5x point-in-time volume | long, eligible |
| Gap-and-go | 4% gap, premarket liquidity gates, close above fixed premarket high and VWAP | long, eligible |
| High-of-day breakout | mature high, narrow five-bar consolidation, volume-confirmed close above | long, eligible |
| Market-relative momentum | 15-minute return exceeds synchronized SPY by 2 points with volume and SPY filter | long, eligible |
| RSI exhaustion reversion | RSI14 at most 25, 20-bar decline, SPY filter, completed reversal confirmation | long, eligible |
| VWAP mean-reversion fade | 1.5 ATR downside extension with three-bar deceleration and confirmation | long, eligible |
| VWAP reclaim | three closes below VWAP followed by two above and 1.2x volume | long, eligible |

There is one canonical parameterization per family and no declared alternative
variant. Adding a variant changes the contract identity, counts as another
hypothesis, and resets applicable evidence. Subjective chart interpretation,
continuous search, outcome-selected thresholds, and future information are
prohibited.

The registry deliberately omits scored short strategies. A later short contract
requires point-in-time locate availability, borrow fees, and reproducible short
execution evidence. Without those inputs it must be exhibition-only and cannot
receive a medal or advance.
