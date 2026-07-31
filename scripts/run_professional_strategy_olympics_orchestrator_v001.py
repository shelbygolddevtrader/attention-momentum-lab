#!/usr/bin/env python3
"""Validate the V004 Olympics orchestrator; execution is authorization-gated."""

from __future__ import annotations

import argparse
from pathlib import Path

from aml.professional_strategy_olympics_orchestrator_v001 import (
    build_artifact_bundle,
    load_authorization,
    load_input_manifest,
    publish_artifacts,
    validate_only,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--repository-root", type=Path, default=Path.cwd())
    value.add_argument("--input-manifest", type=Path)
    value.add_argument("--execute", action="store_true")
    value.add_argument("--authorization", type=Path)
    value.add_argument("--output-root", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.repository_root.resolve()
    manifest = load_input_manifest(args.input_manifest.resolve()) if args.input_manifest else None
    if not args.execute:
        print(validate_only(root, manifest).decode("utf-8"), end="")
        return 0
    if manifest is None or args.authorization is None or args.output_root is None:
        raise SystemExit(
            "execution requires --input-manifest, --authorization, and --output-root"
        )
    authorization = load_authorization(args.authorization.resolve())
    artifacts = build_artifact_bundle(
        root, manifest, authorization, execute_requested=True
    )
    run_identity = authorization["run_identity"]
    destination = publish_artifacts(args.output_root.resolve(), run_identity, artifacts)
    print(f"published synthetic run {run_identity} to {destination.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
