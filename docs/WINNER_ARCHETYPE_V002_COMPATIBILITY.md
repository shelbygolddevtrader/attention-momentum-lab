# Winner Archetype V002 Compatibility Boundary

Winner Archetype V001 remains immutable and historically reproducible under its
own schemas. Its frozen experiment identity is
`f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a`.

V002 is not a migration of V001. It introduces new protocol, security-identity,
symbol-lineage, universe, session, capability, entitlement, evidence, manifest,
readiness, and experiment-binding schemas. The V002 loaders reject V001 schemas.
No V001 record is silently upgraded, reinterpreted, or assigned a V002 identity.

The principal prospective differences are:

- V002 identity-binds the complete point-in-time eligible universe and stable
  listing/security lineage.
- V002 requires authoritative SIP trades and quotes and derives minute bars from
  versioned tick rules.
- V002 makes negative quote, halt, corporate-action, and catalyst assertions
  conditional on proven bounded source coverage.
- V002 keeps early-close sessions eligible and ends evaluation at the last
  scheduled left-labeled minute rather than a fixed 15:59 boundary.
- V002 separates provider capability, account entitlement, acquired datasets,
  validated completeness, and experiment eligibility.
- V002 binds all decision-relevant parser, normalization, correction, source, and
  input identities into the discovery experiment identity.

These changes do not invalidate or rewrite a V001 artifact. They mean V001 and
V002 results, if V002 is later executed, belong to different experiments and
must never be pooled without a separate preregistered comparison protocol.

Production Strategy V0.1.1, signal generation, simulator behavior, sizing,
operator behavior, dashboard behavior, tournament results, and forward-validation
behavior remain outside V002 and unchanged.
