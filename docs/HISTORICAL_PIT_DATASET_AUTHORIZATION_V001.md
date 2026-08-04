# Historical PIT Dataset Authorization V001

## Outcome

Historical PIT Dataset Authorization V001 is a deterministic **fail-closed
assessment**. It does not grant authorization.

- Assessment status: `BLOCKED_NOT_AUTHORIZED`
- Assessment identity: `75917f2859e132d3633cd3f26acb28798719e6a60e83e44311302ec2467544ce`
- Candidate dataset identity: `a481a52db719a8441b9edee1b79a3831ff2c1591c54f58d446e5c4503dc06f18`
- Verification identity: `fb15120e00958d88676bad9c1df95d9338d88d57276bc8b2178565edd3314be0`
- Discovery execution permitted: `false`

Calling this package an authorization, or using it to execute discovery, is a
protocol violation. A successful replacement requires a new immutable version;
V001 cannot be edited into an authorization after review.

## Why a blocked artifact is the correct deliverable

The requested milestone requires provenance, licensing, completeness,
point-in-time correctness, contamination eligibility, discovery-period
eligibility, reproducibility, and a deterministic identity. Access to bytes is
not equivalent to satisfying those gates. The repository's Vendor Sample
Acceptance V001 explicitly rejects marketing pages, subscription access, and
unresolved answers as licensing evidence.

Four independent gates fail:

1. **Licensing and retention.** The source manifest records a user-reported
   Algo Trader Plus subscription and successful authenticated requests. It does
   not contain an executed order form, amendment, or written vendor
   confirmation granting the required internal-research, raw-storage,
   normalized-storage, derived-work, and post-termination-retention rights.
2. **Feed identity.** Requests selected `sip`, but Alpaca did not echo the feed.
   `actual_feed` is correctly `null`; successful access cannot prove the
   returned feed identity.
3. **Point-in-time corporate-action lineage.** The bars were retrieved in 2026
   with `adjustment=all`. The associated corporate-action evidence lacks the
   historical creation and revision timestamps required to reconstruct what
   was knowable at the 2023 session.
4. **Contamination.** The parent dataset fingerprint was already used by
   accepted discovery screen `run-v012`, which evaluated
   `first_pullback_continuation_long_v002`. That frozen evaluator is the exact
   analogue used by `opening-drive-first-pullback-v001`. Reusing a subset would
   not provide fresh discovery evidence.

None of these failures is repaired by changing strategy code, relaxing a
validator, or relabeling the prior screen.

## Smallest candidate selection

The assessment selected exactly one regular symbol-session using an
outcome-blind rule: the earliest frozen discovery date, then the
lexicographically smallest symbol with exactly 390 regular one-minute rows.

| Field | Value |
|---|---|
| Provider | Alpaca Markets |
| Dataset vintage | `alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001` |
| Symbol | `AAPL` |
| Trading date | `2023-07-24` |
| Session | regular `[09:30,16:00)` America/New_York |
| Timeframe | one minute |
| Requested feed | `sip` |
| Actual feed | unknown / not echoed |
| Adjustment | `all` |
| Processed rows | 390 |

The raw provider response, normalized CSV, and acquisition metadata remain in
ignored local research storage. Git contains only hashes and non-proprietary
authorization evidence. The local verification reads only the selected three
files and does not inspect a strategy result.

## Binding

The assessment binds the candidate to these existing immutable identities:

- Executable specification: `ad9eda50f8542eacf66867b309802021b0d7c81d6cf54404fdf5d10f96d283a0`
- Implementation: `896148c2197b519b3eb9b11fa9082b3215d7494322829ea9b3a826f7055e7c26`
- Framework hypothesis: `f00ebf1e2d873e816998ed02fc0b9eea39b08c9761de0e7d0263efeebb752fec`
- Registration: `7b15827b59b021bc7dec7a11122ce8f7f0a5f0e3e5fb98af085b04ddeda3f2cb`
- Source dataset fingerprint: `fe830c09317d3264fc8f73b2ab19ca1513d67d36dd367fbf4710c624940a959d`
- Calendar: `8b9ea9f8edfd4a43b4b3c886496c1d14b1a81285b88cc42aab217a7896a8a4e1`
- Halt manifest: `57b84efe0be071bb5be03e7b18d083a9b4972fd4091f2ed93604d218032c781a`
- Corporate-action manifest: `d7436e94f6d15749a96ba2d5f474b2220337e67b7a2509cabf17fc609c07424d`

The binding grants no validation, holdout, forward, paper, live, Olympics, or
broker authority.

## Reproduction

The source data must already exist locally. The command performs no network
request and exits with status 2 because the decision is blocked:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_historical_pit_dataset_authorization_v001.py \
  --dataset-root data/research/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001
```

Verify the committed package without overwriting it:

```bash
PYTHONPATH=src .venv/bin/python \
  scripts/run_historical_pit_dataset_authorization_v001.py \
  --dataset-root data/research/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001 \
  --verify-only
```

The nonzero exit is intentional and machine-significant. A caller that ignores
it still cannot obtain permission because `authorized` and
`discovery_execution_permitted` are both false.

## Immutability and failure handling

The implementation enforces exact schemas, safe relative paths, exact source
manifest bytes, domain-separated identities, a complete sorted gate inventory,
and a decision derived solely from gate states. Existing output files must be
byte-identical; the tool never overwrites a differing artifact.

Tests prove that failed evidence cannot be represented as authorization,
tampered hashes and missing minutes fail, unsafe paths fail, identities
reproduce, and no discovery or network client is imported.

## Next minimal blocker

Before the repository can produce its first empirical discovery result, it
needs one **fresh, uncontaminated discovery dataset** whose provider-asserted
feed, written usage-and-retention rights, and complete point-in-time
corporate-action/adjustment lineage all pass the same gate. That is an external
data-and-entitlement prerequisite, not a strategy or execution change.
