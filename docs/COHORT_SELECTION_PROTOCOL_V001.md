# Cohort Selection Protocol v0.1

**Status:** Draft — data-source feasibility pending  
**Project:** Attention Momentum Lab  
**Purpose:** Define the evaluation sample before examining strategy performance.

## Data-source activation gate

This protocol is not active for validation collection until the required data sources have been reviewed, documented, and approved.

Before activation, the project must verify that its chosen data sources can provide:

- Premarket trades and volume through the observation cutoff
- A clearly identified feed with consistent historical and prospective coverage
- Point-in-time security type and listing classification
- Point-in-time symbol and exchange-calendar identity
- Split and corporate-action information sufficient to prevent mechanical false gaps
- Twenty complete prior-session baselines
- Reproducible dataset and provider version metadata

The protocol must state whether its volume measurements use SIP, IEX, or another explicitly identified feed. Results produced from different feeds must not be combined as though they were equivalent.

If the approved feed cannot provide complete information by the selection deadline, the protocol must remain inactive or be revised under a new version before sessions are collected.

## 1. Research objective

Evaluate whether attention and momentum signals identify executable intraday opportunities more effectively during objectively defined attention-event sessions than during matched ordinary-control sessions.

This protocol governs only session selection. It does not change:

- Strategy v0.1
- Candidate-score thresholds
- Trade-simulator assumptions
- Risk rules
- Slippage assumptions
- Exit rules

## 2. Anti-hindsight rule

A session may enter the validation cohort only using information available at or before 9:25 a.m. America/New_York on its trading date.

Selection must occur before regular-session results are observed.

No symbol or date may be added because it later experienced:

- A large price increase
- A large price decrease
- High social-media attention discovered afterward
- A volatility halt discovered afterward
- Unusually profitable strategy results

The generated daily manifest must be frozen and timestamped before the regular session begins.

## 3. Initial research universe

The initial study is limited to securities using the `XNYS` market calendar.

Eligible securities must be:

- Common stocks
- Listed on an approved XNYS-mapped venue
- Priced between $2.00 and $100.00 using the previous regular-session close
- Supported by complete point-in-time classification data
- Supported by at least 20 prior valid trading sessions
- At or above $10,000,000 median daily dollar volume over the prior 20 valid sessions

Exclude:

- ETFs
- ETNs
- Mutual funds
- Closed-end funds
- Preferred shares
- Warrants
- Rights
- Units
- Depositary products unless explicitly approved later
- Test securities
- Securities with ambiguous listing or calendar history
- Securities lacking sufficient point-in-time data

Universe membership must use information known on the selection date. Present-day ticker lists must not be used to reconstruct historical membership without point-in-time evidence.

## 4. Selection timestamp

The daily selection timestamp is:

**9:25:00 a.m. America/New_York**

The observation cutoff is **9:25:00 a.m. America/New_York, exclusive**.

Only records timestamped before 9:25:00 may be used. A record stamped exactly 9:25:00 or later is not eligible.

The premarket measurement window is:

**4:00:00 a.m. inclusive through 9:25:00 a.m. exclusive, America/New_York**

The manifest must record its observation cutoff and be frozen no later than 9:28:00 a.m. America/New_York, before the regular session opens.

## 5. Attention-event qualification

An eligible stock qualifies as an attention-event candidate when all three conditions are satisfied:

1. Positive premarket gap is at least 8%.
2. Premarket dollar volume is at least $1,000,000.
3. Premarket relative volume is at least 5.0 times its prior-session baseline.

Strategy v0.1 is long-only. Negative-gap stocks may remain in the selection audit artifact, but they are not part of the primary validation cohort. A future negative-gap or short-selling study requires a separate protocol version.

### 5.1 Premarket gap

Premarket gap is calculated as:

`last eligible price before 9:25 / previous regular-session close - 1`

The last eligible price must be timestamped before 9:25:00.

If no eligible premarket trade exists, the stock does not qualify.

### 5.2 Premarket dollar volume

Premarket dollar volume is the sum of:

`trade price × trade size`

for eligible trades between 4:00:00 and 9:25:00.

The data source and feed must be recorded in the manifest.

### 5.3 Premarket relative volume

Premarket relative volume is:

`current premarket share volume / median comparable premarket share volume`

The baseline is the median premarket share volume from 4:00 through 9:25 over the prior 20 valid trading sessions.

No current-day data timestamped at or after 9:25 may enter the baseline or numerator.

All 20 prior valid sessions must be represented in the baseline:

- A verified session with no eligible premarket trades contributes zero volume.
- Missing, unavailable, or quality-failed data must not be converted to zero.
- If any required baseline session is unavailable, the baseline is invalid and the stock cannot qualify.
- If the 20-session median premarket volume is zero, relative volume is undefined and the stock cannot qualify.

### 5.4 ATR percentage

The control-matching volatility measure is calculated only from the 20 valid regular sessions preceding the selection date.

For each session:

`true range = max(high - low, abs(high - previous close), abs(low - previous close))`

Then:

`ATR20 = arithmetic mean of the 20 true-range values`

`ATR percentage = ATR20 / previous regular-session close`

All inputs must be point-in-time, split-consistent, and must not use any current-session information.

### 5.5 Corporate actions and symbol continuity

Price, volume, and ATR inputs must be placed on a consistent split-adjusted basis known as of the selection timestamp.

A stock must be excluded when the system cannot reliably resolve a relevant:

- Stock split or reverse split
- Symbol change
- Merger or acquisition
- Spinoff
- Special distribution
- Listing transfer

The corporate-action source, adjustment status, and effective date must be recorded. A mechanical corporate-action price adjustment must not be treated as an attention-event gap.

## 6. Daily event selection

Select no more than five attention-event stocks per trading date.

When more than five stocks qualify:

1. Rank by premarket dollar volume, highest first.
2. Break exact ties alphabetically by canonical ticker symbol.

All qualifying stocks, including those below the daily top-five cutoff, must remain recorded in the selection audit artifact.

## 7. Matched ordinary controls

Select two ordinary-control stocks for each chosen attention-event stock.

A control must:

- Belong to the same point-in-time eligible universe
- Use the same trading date
- Use the same `XNYS` calendar
- Not qualify as an attention event
- Have a previous close within 30% of the event stock
- Have 20-session median dollar volume between 0.5 and 2.0 times the event stock
- Have 20-session ATR percentage within 30% of the event stock

### 7.1 Control distance

Among stocks passing the required limits, rank controls using:

`distance = price_distance + liquidity_distance + volatility_distance`

Where:

- `price_distance = abs(log(control previous close / event previous close))`
- `liquidity_distance = abs(log(control median dollar volume / event median dollar volume))`
- `volatility_distance = abs(control ATR percent - event ATR percent) / event ATR percent`

Select the two controls with the lowest distance.

Break exact ties alphabetically by canonical ticker symbol.

Controls are selected without replacement within each trading date. Process event stocks in event-ranking order. Once a stock is assigned as a control, it cannot be assigned to another event on that date.

Controls must never be manually selected based on charts, news, later returns, familiarity, or expected strategy performance.

If fewer than two controls qualify, retain the event row and explicitly record the control shortage.

## 8. Development exclusions

The following are development examples and must not be counted as validation evidence:

- GME on 2024-05-13
- AAPL on 2024-05-13
- Any symbol/date used to design, debug, or tune Strategy v0.1
- Any symbol/date used to design or debug the candidate analyzer
- Any symbol/date used to design or debug the trade simulator

Development sessions may be reported separately as in-sample examples.

## 9. Frozen strategy and simulator

During validation collection, do not change:

- Minimum candidate score
- Signal weights
- Entry-delay rules
- Maximum entry delay
- Position-sizing rules
- Starting equity
- Risk per trade
- Stop-loss percentage
- Profit-target percentage
- Maximum holding time
- Slippage assumptions
- Cooldown duration
- Missing-data treatment

Any later modification must create a new strategy or simulator version and a separately registered validation cohort.

Results from different versions must not be combined as though they came from one unchanged experiment.

## 10. Data-quality policy

The version-controlled batch-evaluation quality configuration determines whether a processed session enters the quality-qualified aggregate.

Data-quality exclusion must never depend on:

- Profit or loss
- Return
- Win rate
- Exit reason
- Signal count
- Whether excluding the session improves results

Every requested session must remain visible in the all-requested-session report.

Missing timestamps are coverage gaps only. They must not be labeled as halts without independent evidence.

## 11. Required manifest fields

Every selected event and control session must record:

- Symbol
- Trading date
- Session class
- Cohort ID
- Selection rule version
- Calendar ID
- Data source
- Data feed
- Selection timestamp
- Observation cutoff
- Manifest frozen timestamp
- Inclusion timestamp
- Dataset vintage
- Previous close
- Gap direction
- Corporate-action status
- Corporate-action source
- Corporate-action effective date
- 20-session median dollar volume
- 20-session ATR percentage
- Premarket gap
- Premarket share volume
- Premarket dollar volume
- Premarket relative volume
- Premarket baseline validity
- Event ranking
- Matched-group ID
- Control distance
- Selection status
- Status detail

The daily manifest must be immutable after the selection deadline, except for append-only correction records that preserve the original values.

## 12. Minimum validation sample

Do not make a final edge determination until the frozen cohort contains at least:

- 100 selected attention-event stock sessions
- Up to 200 matched ordinary-control sessions
- At least 30 distinct trading dates

Report concentration by:

- Symbol
- Date
- Event
- Trade
- Time of day
- Exit reason

A result dependent on one symbol, one date, or one winning trade is not considered durable evidence.

## 13. Primary comparisons

The primary analysis compares:

- Attention-event sessions versus matched ordinary controls
- Quality-qualified results versus all processed results
- Zero-trade rates
- Trade expectancy
- Profit factor
- Median session return
- Profitable-session rate
- Session drawdown distribution
- Largest-trade and largest-session profit concentration

Both trade-weighted and session-weighted statistics must be reported.

## 14. Interpretation standard

A positive historical result is not proof of future profitability.

The system should not be considered to have demonstrated a durable edge unless results:

- Remain positive after realistic slippage
- Are not dependent on one exceptional winner
- Persist across many dates and symbols
- Outperform matched controls
- Survive predetermined data-quality rules
- Remain directionally consistent in a later untouched holdout cohort

## 15. Change control

Any change to this protocol requires:

- A new protocol version
- A documented reason
- A Git commit before new sessions are collected
- No retroactive application to already observed outcomes unless clearly labeled as exploratory

Previously collected cohorts remain associated with the protocol version active at their selection time.
