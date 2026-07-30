#!/usr/bin/env python3
"""Publish or print the deterministic, non-empirical V002 session plan."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from aml.winner_archetype_session_plan import canonical_session_plan_bytes
from aml.winner_archetype_v002 import PROTECTED_DISCOVERY_PARTS


ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/winner_archetype_protocol_v002.json"),
    )
    result.add_argument("--output", type=Path)
    return result


def _inside_repository(path: Path) -> Path:
    normalized = {part.casefold().replace("_", "-") for part in path.parts}
    protected = {part.casefold().replace("_", "-") for part in PROTECTED_DISCOVERY_PARTS}
    if normalized & protected:
        raise ValueError("Session-plan paths cannot enter protected research partitions")
    candidate = path if path.is_absolute() else ROOT / path
    candidate = candidate.absolute()
    if ".." in path.parts:
        raise ValueError("Session-plan output path is unsafe")
    cursor = candidate
    while cursor != cursor.parent:
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("Session-plan paths cannot contain symlinks")
        cursor = cursor.parent
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Session-plan output must remain inside the repository") from exc
    return candidate


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    protocol = _inside_repository(args.protocol)
    payload = canonical_session_plan_bytes(protocol)
    if args.output is None:
        print(payload.decode("utf-8"), end="")
        return 0
    output = _inside_repository(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if output.read_bytes() != payload:
            raise ValueError("Immutable session-plan output already exists with different bytes")
        return 0
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
