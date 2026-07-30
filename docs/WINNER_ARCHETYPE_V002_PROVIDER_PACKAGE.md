# V002 Session Plan and Provider Confirmation Package

Status: non-empirical readiness tooling; pilot not authorized

This package freezes deterministic calendar evidence and creates review-ready
provider contracts without contacting a provider or opening empirical records.

## Session plan

The tracked manifest is `config/winner_archetype_session_plan_v002.json`. It is
bound to `exchange_calendars==4.13.2`, XNYS, left-labeled minutes,
America/New_York, the V002 protocol identity and protocol-file SHA-256.

There are 252 selection sessions from 2024-06-03 through 2025-06-04, three early
closes, and one provider-declared ad hoc closure in the interval (2025-01-09).
Holidays, weekends, regular sessions, early closes, and the ad hoc closure are
explicitly classified.

The final cohort is intentionally unresolved. Exact conditional plans are
published for 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, and 252 sessions.
The final plan may be selected only by the frozen selection-only eligible-event
rule. Calendar publication cannot inspect outcomes or authorize the pilot.

- Manifest identity: `167847cf198764f72b76c976a4993f7d8f4a4e262d4dc53018ec9317c7d6196c`
- Manifest file SHA-256: `59d5b159eb957d972015aec3b54eb305dbbdd8a6626b029d20ffc308ed71ad47`
- Session-records SHA-256: `ab8d89c20ab0d7af854f8025f2746a0879e3e9fdbd40e9e2b46f2942477d8dc2`
- Excluded-date SHA-256: `93625687bd4e6e00021552814702f4f6024ba2a66922fa5d7f164a4f4593cf86`
- Conditional-plan SHA-256: `cc95546189bc7b9a84a9eccb6ee8a10792ca1ee288b2876bc52f2780c3bb7ac3`

## Capability contract and matrix

The machine-readable capability contract covers all 13 source families and
separates provider claims, public documentation, written confirmation, schema
verification, license confirmation, and empirical completeness evidence. Claims
and public documentation receive no readiness credit.

The deterministic decision matrix evaluates five provider roles across all 65
provider/source-family cells. Every current cell is `claimed` or `unknown`, every
`readiness_credit` is false, and no minimum compliant source set exists yet.
Advertised prices and storage ranges are planning fields, not verified quotes or
readiness evidence.

- Capability-contract identity: `4a73a61d56e2b8085b02d2afdf3ffbaf45af0a54a2549b7d30e4a4eaf01afe83`
- Capability-contract file SHA-256: `fab1ab53b77996e429fc7750a87e1d06089ac2857bc577301fea698cde4f432c`
- Decision-matrix identity: `8d44c588be7c0501d746a2b476ea6ca42157feae1854db7bd9e1024b7bf4a1db`
- Decision-matrix file SHA-256: `318d7799b3a02d1c9c1aeb83e1b48eb3107ad927b304d25935487ed226063190`

## Outreach boundary

Questionnaires under `docs/provider_outreach/` are drafts only. Sending them,
contacting providers, purchasing access, or requesting empirical samples requires
separate human approval. The first outreach wave should request written and
schema-only answers from Massive, Alpaca, and a point-in-time security-master
provider before broad-news or exchange-status purchasing decisions.
