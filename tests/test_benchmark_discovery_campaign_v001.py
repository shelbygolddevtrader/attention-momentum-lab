"""Routing, reconciliation, fail-closed, and determinism tests for Campaign V001."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from aml.benchmark_discovery_campaign_v001 import (
    BLOCKED_CLASSIFICATION,
    BenchmarkDiscoveryCampaignError,
    ExecutorRegistration,
    canonical_json,
    finalize_campaign_config,
    load_campaign_config,
    run_campaign,
    verify_campaign,
)
from aml.benchmark_hypothesis_library_v001 import (
    finalize_identities,
    framework_artifacts,
    validate_library,
)
from aml.benchmark_strategy_research_v001 import (
    bind_implementation,
    create_archive,
    create_specification,
    create_triage,
    execute_discovery,
    market_data_identity,
    preregister,
    run_candidate_conformance,
    write_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/benchmark_discovery_campaign_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
PLAN = ROOT / "config/benchmark_strategy_research_v001_example.json"
BARS = ROOT / "tests/fixtures/benchmark_research_v001/opening_reclaim_synthetic.csv"
CANDIDATE_ID = "opening-range-midpoint-reclaim-long-v001"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_canonical(path: Path, value: object) -> None:
    path.write_bytes(canonical_json(value))


def _read_results(root: Path) -> list[dict[str, object]]:
    return [
        _json(path)
        for path in sorted((root / "entries").glob("*/result.json"))
    ]


def test_frozen_config_and_dependencies_are_canonical() -> None:
    config = load_campaign_config(CONFIG)
    library = _json(LIBRARY)
    assert config["campaign_identity"] == (
        "6d47d71dacdb6c65a10e32719ffac0567eca901cd27e0e25bfbd2d63a0bf857e"
    )
    assert config["authorized_executors"] == []
    assert config["library_dependency"]["library_identity"] == library[
        "library_identity"
    ]
    assert config["library_dependency"]["file_sha256"] == hashlib.sha256(
        LIBRARY.read_bytes()
    ).hexdigest()


def test_every_current_library_hypothesis_is_canonically_blocked(
    tmp_path: Path,
) -> None:
    output = tmp_path / "campaign"
    manifest = run_campaign(
        config_path=CONFIG,
        library_path=LIBRARY,
        output_root=output,
    )
    results = _read_results(output)
    assert manifest["verified"] is True
    assert manifest["result_count"] == manifest["library_hypothesis_count"] == 40
    assert manifest["blocked_count"] == 40
    assert manifest["executed_count"] == 0
    assert manifest["classification_counts"] == {BLOCKED_CLASSIFICATION: 40}
    assert len(results) == 40
    assert {item["status"] for item in results} == {"blocked"}
    assert {item["canonical_classification"] for item in results} == {
        BLOCKED_CLASSIFICATION
    }
    assert all(item["execution_evidence"] is None for item in results)
    assert all(not (path.parent / "framework-bundle").exists() for path in sorted(
        (output / "entries").glob("*/result.json")
    ))


def test_campaign_is_write_once_and_rejects_protected_boundaries(
    tmp_path: Path,
) -> None:
    output = tmp_path / "campaign"
    run_campaign(config_path=CONFIG, library_path=LIBRARY, output_root=output)
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="already exists"):
        run_campaign(config_path=CONFIG, library_path=LIBRARY, output_root=output)
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="protected boundary"):
        run_campaign(
            config_path=CONFIG,
            library_path=LIBRARY,
            output_root=tmp_path / "holdout" / "campaign",
        )


def test_dependency_and_executor_substitution_fail_before_execution(
    tmp_path: Path,
) -> None:
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="campaign source changed"):
        run_campaign(
            config_path=CONFIG,
            library_path=LIBRARY,
            output_root=tmp_path / "source-substitution",
            repository_root=tmp_path,
        )
    changed = _json(CONFIG)
    changed["library_dependency"]["library_identity"] = "d" * 64
    changed["campaign_identity"] = "0" * 64
    changed = finalize_campaign_config(changed)
    changed_path = tmp_path / "changed.json"
    _write_canonical(changed_path, changed)
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="library identity"):
        run_campaign(
            config_path=changed_path,
            library_path=LIBRARY,
            output_root=tmp_path / "changed-run",
            repository_root=ROOT,
        )
    registration = ExecutorRegistration(
        library_entry_id="abnormal-volume-attention-continuation-v001",
        adapter_id="unauthorized-adapter",
        adapter_version="1.0.0",
        source_root=ROOT,
        execute=lambda _: pytest.fail("unauthorized adapter was called"),
    )
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="not authorized"):
        run_campaign(
            config_path=CONFIG,
            library_path=LIBRARY,
            output_root=tmp_path / "unauthorized-run",
            registrations=(registration,),
        )


def test_verifier_rejects_result_tampering_and_blocked_bundle_injection(
    tmp_path: Path,
) -> None:
    output = tmp_path / "campaign"
    run_campaign(config_path=CONFIG, library_path=LIBRARY, output_root=output)
    first = min((output / "entries").glob("*/result.json"))
    original = first.read_bytes()
    first.write_bytes(original + b" ")
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="file hash mismatch"):
        verify_campaign(output, config_path=CONFIG, library_path=LIBRARY)
    first.write_bytes(original)
    (first.parent / "framework-bundle").mkdir()
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="contains execution evidence"):
        verify_campaign(output, config_path=CONFIG, library_path=LIBRARY)


def _executable_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, ExecutorRegistration]:
    """Create a test-only Library member that exactly matches Framework's candidate."""

    library = _json(LIBRARY)
    old_id = "opening-range-expansion-continuation-v001"
    entry = next(item for item in library["hypotheses"] if item["library_entry_id"] == old_id)
    entry.update(
        {
            "library_entry_id": CANDIDATE_ID,
            "title": "Opening-range midpoint reclaim continuation",
            "market_assumption": (
                "The first five regular-session minutes establish a short-lived "
                "reference range followed by two-sided price discovery."
            ),
            "economic_mechanism": (
                "A high-volume midpoint reclaim after a close below it may reflect "
                "failed early selling and renewed demand."
            ),
            "entry_concept": (
                "After 09:35, require the prior close at or below the fixed five-minute "
                "range midpoint and a bullish high-volume close above it."
            ),
            "exit_concept": (
                "Enter at the next bar, stop at the fixed range low, target the fixed "
                "range high, and time out after thirty minutes."
            ),
            "invalidation_conditions": sorted(
                [
                    "any required opening minute is unavailable",
                    "the target is not above the eventual entry",
                ]
            ),
            "expected_regimes": ["two-sided opening price discovery"],
            "required_indicators": sorted(
                [
                    "fixed five-minute opening range",
                    "opening-range median volume",
                    "opening-range midpoint",
                ]
            ),
            "expected_holding_period": "zero to thirty complete one-minute bars",
            "anticipated_failure_modes": sorted(
                ["midpoint whipsaw", "opening auction noise"]
            ),
            "taxonomy": sorted(["continuation", "intraday", "opening"]),
            "related_hypothesis_ids": [],
        }
    )
    for peer in library["hypotheses"]:
        peer["related_hypothesis_ids"] = sorted(
            CANDIDATE_ID if value == old_id else value
            for value in peer["related_hypothesis_ids"]
            if peer["library_entry_id"] != CANDIDATE_ID
        )
        if peer["library_entry_id"] != CANDIDATE_ID and CANDIDATE_ID in peer[
            "related_hypothesis_ids"
        ]:
            entry["related_hypothesis_ids"] = sorted(
                set(entry["related_hypothesis_ids"] + [peer["library_entry_id"]])
            )
    library["hypotheses"] = sorted(
        library["hypotheses"], key=lambda item: item["library_entry_id"]
    )
    library = finalize_identities(library)
    validate_library(library)
    library_path = tmp_path / "library.json"
    _write_canonical(library_path, library)
    entry = next(
        item for item in library["hypotheses"] if item["library_entry_id"] == CANDIDATE_ID
    )
    sources = {item["source_id"]: item for item in library["sources"]}
    observation, hypothesis = framework_artifacts(entry, sources)
    plan = _json(PLAN)
    triage = create_triage(
        {**plan["triage"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
    )
    specification = create_specification(
        {**plan["specification"], "hypothesis_identity": hypothesis["identity"]},
        hypothesis,
        triage,
    )
    frame = pd.read_csv(BARS)
    dataset_identity = market_data_identity({"TEST": frame})
    registration = preregister(
        {
            **plan["preregistration"],
            "observation_identity": observation["identity"],
            "hypothesis_identity": hypothesis["identity"],
            "triage_identity": triage["identity"],
            "specification_identity": specification["identity"],
            "permitted_discovery_dataset_identities": [dataset_identity],
            "contaminated_dataset_identities": hypothesis["payload"][
                "contaminated_dataset_identities"
            ],
        },
        observation,
        hypothesis,
        triage,
        specification,
    )
    binding = bind_implementation(
        ROOT,
        {
            "preregistration_identity": registration["identity"],
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
        registration,
        specification,
    )
    conformance = run_candidate_conformance(
        frame,
        dataset_identity=dataset_identity,
        hypothesis=hypothesis,
        specification=specification,
        preregistration=registration,
        binding=binding,
    )
    discovery, classification = execute_discovery(
        {"TEST": frame},
        repository_root=ROOT,
        dataset_identity=dataset_identity,
        hypothesis=hypothesis,
        specification=specification,
        preregistration=registration,
        binding=binding,
        conformance=conformance,
    )
    archive = create_archive(
        hypothesis=hypothesis,
        archive_state=(
            "rejected"
            if classification["payload"]["classification"] == "REJECT"
            else "completed"
        ),
        reason="Test-only synthetic campaign execution; no empirical claim.",
        related_artifacts=(
            observation,
            triage,
            specification,
            registration,
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
        registration,
        binding,
        conformance,
        discovery,
        classification,
        archive,
    )
    bound_source_paths = (
        "src/aml/benchmark_research_candidate_v001.py",
        "src/aml/benchmark_strategy_research_v001.py",
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
    )
    executor = {
        "library_entry_id": CANDIDATE_ID,
        "framework_hypothesis_identity": hypothesis["identity"],
        "adapter_id": "test-opening-range-midpoint-adapter",
        "adapter_version": "1.0.0",
        "dataset_identity": dataset_identity,
        "specification_identity": specification["identity"],
        "preregistration_identity": registration["identity"],
        "implementation_binding_identity": binding["identity"],
        "conformance_identity": conformance["identity"],
        "source_sha256": {
            source_path: hashlib.sha256((ROOT / source_path).read_bytes()).hexdigest()
            for source_path in bound_source_paths
        },
        "executor_identity": "0" * 64,
    }
    config = _json(CONFIG)
    config["library_dependency"] = {
        "library_version": library["library_version"],
        "source_commit": "e" * 40,
        "library_identity": library["library_identity"],
        "file_sha256": hashlib.sha256(library_path.read_bytes()).hexdigest(),
    }
    config["authorized_executors"] = [executor]
    config["campaign_identity"] = "0" * 64
    config = finalize_campaign_config(config)
    config_path = tmp_path / "campaign.json"
    _write_canonical(config_path, config)

    def execute(output: Path) -> None:
        write_bundle(output, artifacts)

    runtime = ExecutorRegistration(
        library_entry_id=CANDIDATE_ID,
        adapter_id="test-opening-range-midpoint-adapter",
        adapter_version="1.0.0",
        source_root=ROOT,
        execute=execute,
    )
    return config_path, library_path, runtime


def test_authorized_executable_runs_through_unchanged_framework_pipeline(
    tmp_path: Path,
) -> None:
    config_path, library_path, registration = _executable_fixture(tmp_path)
    output = tmp_path / "campaign-output"
    manifest = run_campaign(
        config_path=config_path,
        library_path=library_path,
        output_root=output,
        registrations=(registration,),
        repository_root=ROOT,
    )
    result = _json(output / "entries" / CANDIDATE_ID / "result.json")
    assert manifest["executed_count"] == 1
    assert manifest["blocked_count"] == 39
    assert result["status"] == "executed"
    assert result["execution_evidence"]["executor_integrity_failure_count"] == 0
    assert result["execution_evidence"]["proposal_count"] == (
        result["execution_evidence"]["accepted_trade_count"]
        + result["execution_evidence"]["rejected_proposal_count"]
    )
    assert verify_campaign(
        output,
        config_path=config_path,
        library_path=library_path,
        repository_root=ROOT,
    )["verified"] is True


def test_authorized_executor_failure_aborts_without_partial_publication(
    tmp_path: Path,
) -> None:
    config_path, library_path, registration = _executable_fixture(tmp_path)
    failed = ExecutorRegistration(
        library_entry_id=registration.library_entry_id,
        adapter_id=registration.adapter_id,
        adapter_version=registration.adapter_version,
        source_root=registration.source_root,
        execute=lambda _: (_ for _ in ()).throw(RuntimeError("test failure")),
    )
    output = tmp_path / "failed-output"
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="executor failed"):
        run_campaign(
            config_path=config_path,
            library_path=library_path,
            output_root=output,
            registrations=(failed,),
            repository_root=ROOT,
        )
    assert not output.exists()


def test_authorized_contract_requires_runtime_and_exact_source_bytes(
    tmp_path: Path,
) -> None:
    config_path, library_path, registration = _executable_fixture(tmp_path)
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="runtime is unavailable"):
        run_campaign(
            config_path=config_path,
            library_path=library_path,
            output_root=tmp_path / "missing-runtime",
            repository_root=ROOT,
        )
    changed = _json(config_path)
    source_hashes = changed["authorized_executors"][0]["source_sha256"]
    first_source = min(source_hashes)
    source_hashes[first_source] = "d" * 64
    changed["campaign_identity"] = "0" * 64
    changed["authorized_executors"][0]["executor_identity"] = "0" * 64
    changed = finalize_campaign_config(changed)
    changed_path = tmp_path / "changed-source.json"
    _write_canonical(changed_path, changed)
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="source changed"):
        run_campaign(
            config_path=changed_path,
            library_path=library_path,
            output_root=tmp_path / "changed-source-output",
            registrations=(registration,),
            repository_root=ROOT,
        )


def test_cli_output_is_deterministic_across_hash_seeds_and_timezones(
    tmp_path: Path,
) -> None:
    roots = []
    for index, (seed, timezone) in enumerate((('1', 'UTC'), ('777', 'Asia/Tokyo'))):
        output = tmp_path / f"campaign-{index}"
        environment = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": str(ROOT / "src"),
            "TZ": timezone,
        }
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_benchmark_discovery_campaign_v001.py"),
                "--config",
                str(CONFIG),
                "--library",
                str(LIBRARY),
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        roots.append(output)
    first = {
        path.relative_to(roots[0]).as_posix(): path.read_bytes()
        for path in sorted(roots[0].rglob("*"))
        if path.is_file()
    }
    second = {
        path.relative_to(roots[1]).as_posix(): path.read_bytes()
        for path in sorted(roots[1].rglob("*"))
        if path.is_file()
    }
    assert first == second


def test_campaign_layer_has_no_prohibited_capability_or_reverse_import() -> None:
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "src/aml/benchmark_discovery_campaign_v001.py",
            "scripts/run_benchmark_discovery_campaign_v001.py",
        )
    )
    prohibited = (
        "submit_order",
        "TradingClient",
        "requests.get",
        "alpaca_rest",
        "run_professional_strategy_olympics",
    )
    assert not any(token in sources for token in prohibited)
    for frozen in (
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
        "src/aml/professional_strategy_olympics_orchestrator_v001.py",
        "src/aml/professional_strategy_executors_v001.py",
    ):
        assert "benchmark_discovery_campaign_v001" not in (
            ROOT / frozen
        ).read_text(encoding="utf-8")
