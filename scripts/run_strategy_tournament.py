"""Run a protected, reproducible strategy tournament over local SIP partitions."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from aml.tournament_config import load_tournament_config, select_splits
from aml.tournament_runner import (
    SourceState, build_plan, load_dataset_manifest, plan_summary, run_tournament,
)


DEFAULT_CONFIG = Path("config/strategy_tournament_baseline.yaml")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    value.add_argument("--splits", nargs="+", default=["development", "validation"])
    value.add_argument("--strategies", nargs="+")
    value.add_argument("--symbols", nargs="+")
    value.add_argument("--include-holdout", action="store_true")
    value.add_argument("--dry-run", action="store_true")
    value.add_argument("--resume", action="store_true")
    value.add_argument("--max-dates-per-split", type=int)
    value.add_argument("--artifact-root", type=Path)
    value.add_argument("--root", type=Path, default=Path.cwd())
    return value


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, stdout=subprocess.PIPE,
    ).stdout


def source_state(root: Path) -> SourceState:
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    porcelain = _git(root, "status", "--porcelain", "-z").decode()
    records = [record for record in porcelain.split("\0") if record]
    paths = tuple(sorted(record[3:].split(" -> ")[-1] for record in records))
    digest = hashlib.sha256()
    digest.update(porcelain.encode())
    for logical in paths:
        path = root / logical
        digest.update(logical.encode())
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return SourceState(commit, bool(paths), digest.hexdigest(), paths)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    config = load_tournament_config(config_path)
    splits = select_splits(args.splits, include_holdout=args.include_holdout)
    dataset_manifest = load_dataset_manifest(root, config.dataset_manifest)
    source = source_state(root)
    plan = build_plan(
        root, config, dataset_manifest, source, splits,
        strategy_ids=args.strategies, symbols=args.symbols,
        max_dates_per_split=args.max_dates_per_split,
    )
    artifact_root = args.artifact_root or Path(config.artifact_root)
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root
    print(json.dumps(plan_summary(plan, artifact_root), indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    result = run_tournament(
        root, artifact_root, config, plan, dataset_manifest, source, resume=args.resume
    )
    print(json.dumps({
        "run_id": result.run_id,
        "final_directory": str(result.final_directory),
        "completed_units": result.completed_units,
        "resumed_units": result.resumed_units,
        "runtime_seconds": result.runtime_seconds,
        "deterministic_artifact_hashes": result.deterministic_artifact_hashes,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
