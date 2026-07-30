# Professional Strategy Dataset Compatibility V001

The planned compatibility target is the same provider-bounded Alpaca SIP
one-minute scope and point-in-time candidate-universe rules defined by Lean
Discovery V001. This is a planning binding, not proof that an entitlement or
dataset is complete.

Required shared inputs are complete left-labeled one-minute OHLCV bars,
premarket bars where the strategy requires them, synchronized SPY bars,
point-in-time session calendars, prior closes, point-in-time VWAP and rolling
features, and corporate-action provenance. The gap-and-go contract additionally
requires premarket coverage. Volume-baseline contracts require only prior
information and must record their warm-up source.

| Family | Regular OHLCV | Premarket | SPY | VWAP | Daily/reference history | Bar-compatible plan |
| --- | --- | --- | --- | --- | --- | --- |
| Five-minute ORB | required | no | no | no | same-minute volume baseline | yes, conditional on completeness |
| Fifteen-minute ORB | required | no | no | no | same-minute volume baseline | yes, conditional on completeness |
| Gap-and-go | required | required | no | required | prior close and liquidity history | yes, conditional on premarket coverage |
| First pullback | required | no | no | no | volume baseline | yes, conditional on completeness |
| VWAP reclaim | required | no | no | required | warm-up bars | yes, conditional on completeness |
| VWAP fade | required | no | no | required | warm-up bars | yes, conditional on completeness |
| High-of-day breakout | required | no | no | no | warm-up bars | yes, conditional on completeness |
| Failed-breakout reversal | required | no | no | no | warm-up bars | yes, conditional on completeness |
| RSI exhaustion | required | no | required | required | warm-up bars | yes, conditional on synchronization |
| Market-relative momentum | required | no | required | SPY VWAP | warm-up bars | yes, conditional on synchronization |

Alpaca SIP bars may support the long-only bar-based contracts if entitlement,
retention, adjustment, timestamp, session, and completeness evidence passes the
future readiness gate. The protocol does not assume that this evidence exists.
Historical short locates and borrow fees are not supplied by ordinary bar data;
therefore short versions are not scored. Level II, hidden liquidity, queue
position, precise tape sequence, options flow, and news receipt timestamps are
outside scope.

Missing exact timestamps invalidate elapsed-time features and candidates rather
than shortening windows. Missing required opening-range, premarket, SPY, entry,
or warm-up bars are reported as exclusions. Halts prevent entry and use the
first executable post-halt bar for conservative open-position handling.
Corporate-action adjustment must be point-in-time and provenance-bound.

No acquisition, provider connection, market-data inspection, or replay was
performed for this design milestone.
