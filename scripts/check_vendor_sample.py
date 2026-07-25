#!/usr/bin/env python3
"""Validate quarantined local vendor samples without network or secrets."""

from __future__ import annotations

import argparse
from pathlib import Path

from aml.vendor_sample_acceptance import (
    SampleProfile,
    evaluate_vendor_sample,
    write_acceptance_report,
)


def parser() -> argparse.ArgumentParser:
    """Build the deterministic local-only acceptance CLI."""

    value = argparse.ArgumentParser(
        description="Validate a quarantined market or reference vendor sample"
    )
    value.add_argument("profile", choices=[item.value for item in SampleProfile])
    value.add_argument("--manifest", type=Path, required=True)
    value.add_argument("--licensing-manifest", type=Path, required=True)
    value.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/vendor_sample_acceptance"),
    )
    return value


def main(argv: list[str] | None = None) -> int:
    """Evaluate local files, publish reports, and return nonzero on rejection."""

    args = parser().parse_args(argv)
    result = evaluate_vendor_sample(
        args.profile, args.manifest, args.licensing_manifest
    )
    destination = write_acceptance_report(result, args.output_root)
    status = "ACCEPTED" if result.accepted else "REJECTED"
    print(
        f"{status} run={result.run_id} profile={result.profile} "
        f"technical_pass={result.technical_pass} licensing_pass={result.licensing_pass}"
    )
    print(f"Reports: {destination}")
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
