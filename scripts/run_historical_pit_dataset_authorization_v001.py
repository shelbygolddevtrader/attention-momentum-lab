#!/usr/bin/env python3
"""Assess one existing historical PIT dataset candidate without executing research."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from aml.benchmark_strategy_research_v001 import canonical_json
from aml.historical_pit_dataset_authorization_v001 import (
    HistoricalPITAuthorizationError,
    load_assessment,
    verification_artifact,
    verify_local_candidate,
)


def _report(assessment: dict[str, object], verification: dict[str, object]) -> bytes:
    decision = assessment["authorization"]
    candidate = assessment["candidate"]
    lines = [
        "# Historical PIT Dataset Authorization V001 — Assessment",
        "",
        f"- Status: `{decision['status']}`",
        f"- Authorized: `{str(decision['authorized']).lower()}`",
        f"- Assessment identity: `{assessment['assessment_identity']}`",
        f"- Candidate dataset identity: `{candidate['dataset_identity']}`",
        f"- Candidate: `{candidate['symbol']} {candidate['trading_date']} {candidate['segment']}`",
        f"- Verification identity: `{verification['verification_identity']}`",
        "",
        "## Gates",
        "",
        "| Gate | Status | Failure code |",
        "|---|---|---|",
    ]
    for gate in assessment["gates"]:
        lines.append(
            f"| {gate['gate_id']} | {gate['status']} | {gate['failure_code'] or ''} |"
        )
    lines.extend(
        [
            "",
            "This result is a fail-closed assessment, not a dataset authorization.",
            "No discovery, validation, holdout, forward, paper, live, or Olympics execution occurred.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _write_once(path: Path, payload: bytes, *, verify_only: bool) -> None:
    if path.exists():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != payload:
            raise HistoricalPITAuthorizationError(f"immutable output differs:{path.name}")
        return
    if verify_only:
        raise HistoricalPITAuthorizationError(f"required output is missing:{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/historical_pit_dataset_authorization_v001.json"),
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("manifests/historical_pit_dataset_authorization_v001"),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        assessment = load_assessment(
            args.config, repository_root=args.repository_root
        )
        local = verify_local_candidate(assessment, dataset_root=args.dataset_root)
        verification = verification_artifact(
            assessment, local_verification=local
        )
        outputs = {
            "dataset_authorization.json": canonical_json(assessment),
            "verification.json": canonical_json(verification),
            "REPORT.md": _report(assessment, verification),
        }
        for name, payload in outputs.items():
            _write_once(args.output_root / name, payload, verify_only=args.verify_only)
    except HistoricalPITAuthorizationError as exc:
        print(f"BLOCKED:{exc}", file=sys.stderr)
        return 2
    print(
        f"{assessment['authorization']['status']} "
        f"assessment={assessment['assessment_identity']} "
        f"verification={verification['verification_identity']}"
    )
    return 0 if assessment["authorization"]["authorized"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
