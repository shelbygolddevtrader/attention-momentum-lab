# Alpaca V002 Capability Questionnaire

Status: unsent review draft

The common questionnaire in `V002_COMMON_QUESTIONNAIRE.md` is incorporated in
full. Alpaca should additionally confirm:

1. Do historical SIP trade and quote responses retain distinct participant and SIP receipt timestamps, complete sequence fields, and corrections/cancellations?
2. Does pagination guarantee every record and expose a stable query/file identity plus a final page-count or checksum?
3. Are historical bars derived only from correction-aware eligible SIP trades, and can the exact derivation rules be supplied?
4. Does Algo Trader Plus permit immutable local retention after subscription cancellation for internal research?
5. Can Alpaca certify historical coverage and schema behavior for 2024-05-03 through 2025-06-04?

Do not include account identifiers, credentials, or empirical samples in the request.
