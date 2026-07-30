#!/usr/bin/env python3
"""Report V002 discovery readiness without opening empirical inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from aml.winner_archetype_contracts import canonical_json
from aml.winner_archetype_v002 import (
    authorize_discovery_path,
    build_readiness_report,
    load_protocol_v002,
    load_source_requirements_v002,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/winner_archetype_protocol_v002.json"),
    )
    result.add_argument(
        "--source-requirements",
        type=Path,
        default=Path("config/winner_archetype_source_requirements_v002.json"),
    )
    result.add_argument("--format", choices=("json", "text"), default="json")
    return result


def render_text(report: dict[str, object]) -> str:
    lines = [
        "Winner Archetype Protocol V002 readiness",
        f"status: {report['status']}",
        f"protocol_identity: {report['protocol_identity']}",
        f"source_requirements_identity: {report['source_requirements_identity']}",
        f"readiness_identity: {report['readiness_identity']}",
        "pilot_authorized: false",
        "empirical_data_opened: false",
        "eligible_event_count_calculated: false",
        "unresolved_by_category:",
    ]
    categories = report["unresolved_by_category"]
    for key in sorted(categories):
        lines.append(f"  {key}: {categories[key]}")
    lines.append("prerequisites:")
    for item in report["prerequisites"]:
        failures = ",".join(item["failures"]) if item["failures"] else "none"
        lines.append(
            f"  {item['dataset']} / {item['required_capability']}: "
            f"{'ready' if item['ready'] else 'blocked'} [{failures}]"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    protocol_path = authorize_discovery_path(args.protocol, REPOSITORY_ROOT)
    matrix_path = authorize_discovery_path(args.source_requirements, REPOSITORY_ROOT)
    report = build_readiness_report(
        load_protocol_v002(protocol_path),
        load_source_requirements_v002(matrix_path),
    )
    if args.format == "json":
        print(canonical_json(report).decode("utf-8"), end="")
    else:
        print(render_text(report), end="")
    return 2 if report["status"] != "ready" else 0


if __name__ == "__main__":
    raise SystemExit(main())
