#!/usr/bin/env python3
"""Run the synthetic, non-empirical Benchmark Research V001 vertical slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from aml.benchmark_strategy_research_v001 import (
    BenchmarkResearchError,
    bind_implementation,
    create_archive,
    create_hypothesis,
    create_observation,
    create_specification,
    create_triage,
    execute_discovery,
    market_data_identity,
    preregister,
    run_candidate_conformance,
    verify_bundle,
    write_bundle,
)


def _strict_json(path: Path) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise BenchmarkResearchError("plan JSON contains duplicate keys")
            value[key] = item
        return value

    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
        raise BenchmarkResearchError("plan JSON is missing, unsafe, or oversized")
    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                BenchmarkResearchError(f"non-finite plan value: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkResearchError("plan JSON is malformed") from exc
    if not isinstance(result, dict):
        raise BenchmarkResearchError("plan JSON root must be an object")
    return result


def build_lifecycle(
    *, repository_root: Path, plan_path: Path, bars_path: Path, output_root: Path
) -> dict[str, object]:
    plan = _strict_json(plan_path)
    if set(plan) != {
        "schema_version",
        "evidence_class",
        "observation",
        "hypothesis",
        "triage",
        "specification",
        "preregistration",
    }:
        raise BenchmarkResearchError("example plan fields are invalid")
    if plan["schema_version"] != "aml.benchmark-strategy-research.example-plan.v001":
        raise BenchmarkResearchError("example plan schema changed")
    if plan["evidence_class"] != "synthetic_non_empirical_vertical_slice":
        raise BenchmarkResearchError("only the synthetic vertical slice is authorized")
    frame = pd.read_csv(bars_path)
    if "symbol" not in frame:
        raise BenchmarkResearchError("bars are missing symbol")
    bars_by_symbol = {
        str(symbol).upper(): group.reset_index(drop=True)
        for symbol, group in frame.groupby("symbol", sort=True)
    }
    dataset_identity = market_data_identity(bars_by_symbol)
    observation = create_observation(plan["observation"])
    hypothesis = create_hypothesis(plan["hypothesis"], observation)
    triage = create_triage(
        {**plan["triage"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
    )
    specification = create_specification(
        {**plan["specification"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
        triage,
    )
    preregistration = preregister(
        {
            **plan["preregistration"],
            "observation_identity": observation["identity"],
            "hypothesis_identity": hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
        },
        observation,
        hypothesis,
        triage,
        specification,
    )
    if dataset_identity not in preregistration["payload"][
        "permitted_discovery_dataset_identities"
    ]:
        raise BenchmarkResearchError("fixture does not match preregistered dataset")
    binding = bind_implementation(
        repository_root,
        {
            "preregistration_identity": preregistration["identity"],
            "specification_identity": specification["identity"],
            "implementation_callable": (
                "aml.benchmark_research_candidate_v001."
                "evaluate_opening_range_midpoint_reclaim"
            ),
            "implementation_files": [
                "src/aml/benchmark_research_candidate_v001.py",
                "src/aml/benchmark_strategy_research_v001.py",
            ],
            "downstream_files": [
                "src/aml/discovery_screen_v001.py",
                "src/aml/portfolio_simulator.py",
            ],
            "no_frozen_file_modified": True,
        },
        preregistration,
        specification,
    )
    conformance = run_candidate_conformance(
        frame,
        dataset_identity=dataset_identity,
        hypothesis=hypothesis,
        specification=specification,
        preregistration=preregistration,
        binding=binding,
    )
    discovery, classification = execute_discovery(
        bars_by_symbol,
        repository_root=repository_root,
        dataset_identity=dataset_identity,
        hypothesis=hypothesis,
        specification=specification,
        preregistration=preregistration,
        binding=binding,
        conformance=conformance,
    )
    archive_state = (
        "rejected"
        if classification["payload"]["classification"] == "REJECT"
        else "completed"
    )
    archive = create_archive(
        hypothesis=hypothesis,
        archive_state=archive_state,
        reason=(
            "Synthetic vertical slice completed; no empirical evidence or edge claim."
        ),
        related_artifacts=(
            observation,
            triage,
            specification,
            preregistration,
            binding,
            conformance,
            discovery,
            classification,
        ),
        empirical_outcomes_accessed=False,
    )
    artifacts = (
        observation,
        hypothesis,
        triage,
        specification,
        preregistration,
        binding,
        conformance,
        discovery,
        classification,
        archive,
    )
    manifest = write_bundle(output_root, artifacts)
    verified = verify_bundle(output_root)
    return {
        "bundle_identity": manifest["identity"],
        "hypothesis_identity": hypothesis["identity"],
        "preregistration_identity": preregistration["identity"],
        "implementation_binding_identity": binding["identity"],
        "discovery_identity": discovery["identity"],
        "classification_identity": classification["identity"],
        "classification": classification["payload"]["classification"],
        "archive_identity": archive["identity"],
        "evidence_class": plan["evidence_class"],
        "verified": verified["verified"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build_lifecycle(
        repository_root=args.repository_root,
        plan_path=args.plan,
        bars_path=args.bars,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
