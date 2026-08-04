# Historical PIT Dataset Authorization V001 — Assessment

- Status: `BLOCKED_NOT_AUTHORIZED`
- Authorized: `false`
- Assessment identity: `75917f2859e132d3633cd3f26acb28798719e6a60e83e44311302ec2467544ce`
- Candidate dataset identity: `a481a52db719a8441b9edee1b79a3831ff2c1591c54f58d446e5c4503dc06f18`
- Candidate: `AAPL 2023-07-24 regular`
- Verification identity: `fb15120e00958d88676bad9c1df95d9338d88d57276bc8b2178565edd3314be0`

## Gates

| Gate | Status | Failure code |
|---|---|---|
| completeness | passed |  |
| contamination | failed | candidate-descends-from-previously-evaluated-dataset |
| deterministic_identity | passed |  |
| discovery_period_eligibility | passed |  |
| feed_identity | failed | provider-feed-identity-not-echoed |
| licensing_and_retention | failed | written-license-retention-evidence-missing |
| point_in_time_correctness | failed | point-in-time-corporate-action-lineage-unproven |
| provenance | passed |  |
| reproducibility | passed |  |

This result is a fail-closed assessment, not a dataset authorization.
No discovery, validation, holdout, forward, paper, live, or Olympics execution occurred.
