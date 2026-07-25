#!/usr/bin/env python3
"""Manage research-only experiment specifications; evaluation is intentionally absent."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from aml.experiment_registry import (
    append_operational_note, draft_template, load_registry, preregister, specification_hash,
    transition, validate_experiment, validate_registry_root, write_spec,
)


DEFAULT_ROOT = Path("experiments/v012")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--registry-root", type=Path, default=DEFAULT_ROOT)
    commands = value.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-draft")
    create.add_argument("--experiment-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--author", required=True)
    for command in ("validate", "preregister", "show", "hash"):
        item = commands.add_parser(command)
        item.add_argument("experiment_id")
    commands.add_parser("list")
    change = commands.add_parser("transition")
    change.add_argument("experiment_id")
    change.add_argument("status")
    note = commands.add_parser("append-note")
    note.add_argument("experiment_id")
    note.add_argument("--author", required=True)
    note.add_argument("--note", required=True)
    return value


def _root(raw: Path) -> Path:
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    return validate_registry_root(candidate).resolve()


def _path(root: Path, experiment_id: str) -> Path:
    if "/" in experiment_id or "\\" in experiment_id or ".." in experiment_id:
        raise ValueError("Malformed experiment ID")
    return root / f"{experiment_id}.json"


def _commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = _root(args.registry_root)
    if args.command == "create-draft":
        existing = {item["experiment_id"] for item in load_registry(root)} if root.exists() else set()
        if args.experiment_id in existing:
            raise ValueError("Duplicate experiment ID")
        spec = draft_template(args.experiment_id, args.name, args.author, _commit())
        write_spec(_path(root, args.experiment_id), spec)
        print(args.experiment_id)
        return 0
    if args.command == "list":
        for spec in load_registry(root):
            print(f"{spec['experiment_id']}\t{spec['status']}\t{spec['human_name']}")
        return 0
    if args.command == "append-note":
        path = append_operational_note(
            root, args.experiment_id, datetime.now(timezone.utc).isoformat(),
            args.author, args.note,
        )
        print(path)
        return 0
    matching = [
        item for item in load_registry(root)
        if item["experiment_id"] == args.experiment_id
    ]
    if len(matching) != 1:
        raise ValueError("Experiment ID is missing or duplicated")
    path = _path(root, args.experiment_id)
    spec = matching[0]
    if args.command == "validate":
        validate_experiment(spec)
        print("valid")
    elif args.command == "show":
        print(json.dumps(spec, indent=2, sort_keys=True))
    elif args.command == "hash":
        print(specification_hash(spec))
    else:
        updated = preregister(spec) if args.command == "preregister" else transition(spec, args.status)
        write_spec(path, updated, replace=True)
        print(updated["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
