# Benchmark Specification Campaign V001

## Status and scientific boundary

This design-only campaign converts exactly one immutable Benchmark Hypothesis
Library V001 entry into a complete prospective executable specification:

`opening-drive-first-pullback-v001`

Its canonical classification is `SPECIFIED_READY_FOR_IMPLEMENTATION`. That
classification means the experiment is now unambiguous enough for two
independent implementations to produce the same decisions. It does not mean an
implementation, dataset authorization, registered executor, discovery result,
edge, profitability, validation eligibility, Olympics eligibility, deployment
readiness, or capital eligibility exists.

The campaign reads no market outcomes and runs no strategy. It leaves the
Framework, Library, Discovery Campaign, Implementation Campaign, execution,
proposal, lifecycle, integrity, publication, classification, Olympics, and
governance components unchanged.

## Prospective selection

The selection used only implementation-readiness evidence. Performance and
outcomes were prohibited. The ordered criteria were:

1. fewest new assumptions;
2. closest semantic fit to an existing frozen contract;
3. greatest reuse of existing data, indicators, execution, and lifecycle;
4. fewest unresolved tie or missing-data semantics; and
5. library identifier as the final deterministic tie-break.

The chosen hypothesis has a one-to-one frozen analogue in
`first_pullback_continuation_long_v002`. That analogue already resolves
one-minute timing, the opening impulse, relative volume, pullback construction,
trigger, ATR stop, next-bar entry, fixed target, timeout, tie-breaking,
missing-data states, and conservative lifecycle behavior. The Library record's
directional scope explicitly includes `long`, so specifying the long arm does
not mutate the hypothesis. The unchosen short arm remains unspecified and
unauthorized; it may not be inferred by symmetry.

### Why the other ten were not selected

| Hypothesis | Existing fit | Remaining ambiguity |
|---|---|---|
| Failed-volume breakout reversal | Partial downside-reclaim reuse | Breakout side, balance target, and level definition |
| First-half-hour-to-close momentum | Indicator only | Entry clock, market-volume state, return threshold, stop, and exit |
| High-relative-volume continuation | Indicator only | Cumulative baseline, directional move, liquidity, and persistence exit |
| Opening-range expansion | Two competing reusable contracts | Opening-range duration and invalidation reference |
| Opening-range failed breakout | None | Range duration, excursion, internal target, and renewed failure |
| Gap continuation with volume | Partial gap-and-go reuse | Opening hold, relative volume, and gap-fill invalidation |
| Gap exhaustion reversal | None | Exhaustion test, countertrend reference, opening extreme, and target |
| Overnight inventory reversal | Partial VWAP reuse | Overnight return, failure to extend, and target precedence |
| Volatility-expansion breakout | Indicator only | Compression, expansion, range boundary, and volume confirmation |
| VWAP-deviation mean reversion | Partial VWAP reuse | Normalizer, failure to extend, liquidity, and convergence target |

The machine-readable selection review preserves these decisions for all 11
specification-ready hypotheses.

## Frozen executable experiment

### Market assumption and mechanism

The unchanged Library assumption is that a directional opening drive with broad
participation can reveal informed demand before slower traders complete their
orders. The proposed mechanism is that the first controlled retracement supplies
liquidity without destroying the drive's information content.

### Time, session, and information set

- Use the point-in-time XNYS calendar and `America/New_York` timestamps.
- Bars are complete, left-labeled one-minute intervals `[t, t+1 minute)`.
- The evaluator receives only the current symbol-session prefix beginning at
  09:30. No future bar is visible while deciding whether a signal exists.
- Source bars may trigger from 09:35 through 11:30. The exact next-minute entry
  window is therefore 09:36 through 11:31.
- The impulse must end no later than 10:00.
- Only the isolated next exact bar open may be exposed after the signal, for the
  unchanged next-bar entry lifecycle.

### Eligibility and indicators

- Direction: long only.
- Current close: $2 through $500 inclusive.
- Opening impulse: at least 3% from the then-current opening anchor low.
- Impulse participation: final-five-bar mean volume at least 2.0 times the
  preceding-20-bar median.
- Pullback depth: 20% through 50% inclusive.
- Pullback duration: 2 through 10 completed bars inclusive.
- ATR: Wilder ATR20, seeded from the first 20 true ranges, updated causally, and
  reset after a timestamp gap or session boundary.

The exact formulas, inclusive/strict comparisons, and unavailable behavior are
content-addressed in the canonical JSON. No interpolation or forward filling is
allowed.

### Deterministic setup and trigger

Scan from 09:31 while maintaining the earliest running minimum low from 09:30;
an equal low does not replace the anchor. Select the earliest completed bar no
later than 10:00 that satisfies both the 3% high-over-anchor-low impulse and the
2.0 local-volume ratio. The trigger bar itself is not an impulse candidate.

The pullback begins on the earliest later bar whose low is strictly below the
preceding bar low. Pullback membership runs through the candidate trigger bar,
inclusive. Every pullback close must remain at or above the 50% retracement,
every post-impulse low must remain at or above the impulse anchor, and mean
pullback volume must be strictly below mean final-five impulse volume.

The signal is the earliest eligible pullback bar whose completed close is
strictly above the immediately preceding completed bar high. Its signal
timestamp is the exclusive end of the trigger bar.

### Entry, risk, exit, and lifecycle

- Intended entry: exact next left-labeled minute, with zero allowed delay.
- Cost-adjusted entry: next-bar open multiplied by 1.001.
- Stop: pullback low minus 0.05 ATR20, floored to one cent.
- Target: cost-adjusted entry plus 2 initial per-share risk units, ceiled to one
cent.
- Timeout: 90 completed bars.
- Requested size: whole-share floor of $250 divided by cost-adjusted-entry
  minus rounded-stop risk; zero shares is no-trade and the unchanged portfolio
  exposure, concurrency, and loss gates remain authoritative.
- Session exit: earlier of timeout or the 15:55 completed-bar close; on an early
  close, use the fifth completed bar before scheduled close.
- Same-bar precedence: gap stop, intrabar stop, gap target, intrabar target.
- One entry maximum per symbol-session; re-entry is prohibited after the first
  pullback resolves.

The shared frozen cost and risk assumptions are restated exactly in the JSON so
an implementation cannot select substitutes: 10 basis points adverse friction
per side, $0.005/share/order with a $1 minimum, $250 initial risk, $100,000
initial capital, 50% maximum gross exposure, three concurrent positions, and a
1% daily new-entry loss stop.

All indicator and lifecycle arithmetic uses IEEE-754 binary64 with
round-to-nearest/ties-to-even and no comparison epsilon. A 20-value median is
the arithmetic mean of the tenth and eleventh values after ascending sort.
Cent rounding converts the binary64 value to its shortest round-trip decimal
string before decimal floor/ceiling quantization. These rules remove
cross-implementation rounding ambiguity.

## Event order and states

The specification fixes the following precedence:

1. integrity failure;
2. common eligibility or state no-signal;
3. unavailable required input or indicator;
4. absent or invalid setup;
5. absent trigger;
6. pre-entry unavailable/no-trade;
7. proposal.

Allowed terminal decisions are `proposal`, `no_signal`, `unavailable`,
`no_trade`, and `integrity_failure`. The canonical specification enumerates the
reason families in each state. An integrity defect cannot be downgraded to
unavailable or no-signal.

## Missing data, invalidation, and fail-closed behavior

An unclassified minute gap, incomplete halt coverage, invalid adjustment
lineage, malformed OHLC, nonfinite input, future bar, mixed identity, or
provenance substitution is an integrity failure. A halt-covered gap is not
silently filled: consecutive indicators reset and remain unavailable until
their windows rewarm. The next exact bar must exist and must match the signal
timestamp, security, symbol, session, feed, and provenance.

Setup invalidations include pullback depth or duration outside the frozen
bounds, a close below the midpoint, a new low below the impulse anchor,
non-contracted pullback volume, or nonpositive entry risk. The full exact list
is in the canonical artifact.

## Immutability and identities

The source config is canonical JSON. The specification identity hashes the
complete rule object with a domain separator. The selection identity hashes the
complete 11-entry review. The campaign identity binds both plus the exact
Library and Implementation Campaign identities, source hashes, timestamp,
source commit, and no-execution policy.

Any semantic modification requires a new versioned child hypothesis identity.
Rewriting this revision is prohibited. The publication command is write-once,
and verification rejects changed, missing, extra, symlinked, or noncanonical
artifacts.

Canonical artifacts are under:

`manifests/benchmark_specification_campaign_v001/`

They contain the selection review, executable specification, verification
report, and manifest. These are specification evidence only.

## Verification commands

Verify the committed artifacts without publishing or executing a strategy:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_benchmark_specification_campaign_v001.py \
  --output-root manifests/benchmark_specification_campaign_v001 \
  --verify-only
```

Publish a byte-identical copy to a new unused temporary path:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/validate_benchmark_specification_campaign_v001.py \
  --output-root /tmp/benchmark-specification-campaign-v001
```

Neither command imports a proposal simulator or strategy evaluator, accesses a
dataset, or executes a strategy.

## Remaining gate

The next independent milestone may implement this exact specification. It must
create a separately content-addressed implementation binding, positive,
negative, unavailable, integrity, and no-lookahead conformance evidence, an
authorized dataset binding, and a registered executor. Until every item exists,
the Discovery Campaign must continue to classify this hypothesis as blocked.
