# Synthetic Vendor-Sample Templates

These files are non-proprietary, schema-only examples for exercising the local
vendor-sample acceptance gate. They contain headers and explicit placeholders,
not production market data, point-in-time reference evidence, contractual
permission, validation-cohort inputs, or strategy-performance evidence.

Copy a template into an ignored `quarantine/{provider}/{sample_id}/` directory,
replace every placeholder from the actual vendor delivery and written rights
evidence, finalize the source bytes, and calculate the declared SHA-256 hashes.
Do not edit these versioned templates to contain vendor data or credentials.

For market samples, `page_record_counts` must contain one non-negative integer
per delivered page, must sum to `delivered_record_count`, and the latter must
equal the exact row count of the finalized bars CSV.
