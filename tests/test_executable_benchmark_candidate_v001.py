"""Executable lifecycle, integrity, and determinism tests for Candidate V001."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from aml.benchmark_candidate_high_of_day_breakout_v001 import (
    CANDIDATE_ID,
    HighOfDayCandidateIntegrityError,
    evaluate_high_of_day_breakout,
)
from aml.benchmark_discovery_campaign_v001 import (
    BLOCKED_CLASSIFICATION,
    BenchmarkDiscoveryCampaignError,
    ExecutorRegistration,
    finalize_campaign_config,
    load_campaign_config,
    run_campaign,
    verify_campaign,
)
from aml.benchmark_executable_candidate_v001 import (
    EVIDENCE_CLASS,
    EXPECTED_HYPOTHESIS_IDENTITY,
    EXPECTED_REGISTRATION_IDENTITY,
    ExecutableCandidateError,
    build_candidate_bundle,
    build_preregistered_artifacts,
    candidate_dataset_identity,
    finalize_plan,
    load_dataset,
    load_plan,
)
from aml.benchmark_hypothesis_library_v001 import load_library
from aml.benchmark_strategy_research_v001 import canonical_json, verify_bundle
from scripts.run_executable_benchmark_candidate_v001 import (
    ADAPTER_ID,
    ADAPTER_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/executable_benchmark_candidate_v001.json"
CAMPAIGN = ROOT / "config/executable_benchmark_candidate_campaign_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
FIXTURE = (
    ROOT
    / "tests/fixtures/executable_benchmark_candidate_v001"
    / "high_of_day_breakout_synthetic.csv"
)
CLI = ROOT / "scripts/run_executable_benchmark_candidate_v001.py"
CANONICAL_OUTPUT = ROOT / "manifests/executable_benchmark_candidate_v001"


def _context() -> tuple[
    dict[str, object],
    pd.DataFrame,
    dict[str, dict[str, object]],
]:
    plan = load_plan(PLAN)
    frame = load_dataset(ROOT, plan)
    artifacts = build_preregistered_artifacts(
        repository_root=ROOT,
        plan=plan,
        library=load_library(LIBRARY),
        frame=frame,
    )
    return plan, frame, artifacts


def _provenance(
    artifacts: dict[str, dict[str, object]], dataset_identity: str
) -> dict[str, str]:
    return {
        "hypothesis_identity": str(artifacts["hypothesis"]["identity"]),
        "specification_identity": str(artifacts["specification"]["identity"]),
        "preregistration_identity": str(artifacts["preregistration"]["identity"]),
        "implementation_binding_identity": str(
            artifacts["implementation_binding"]["identity"]
        ),
        "dataset_identity": dataset_identity,
    }


def _registration() -> ExecutorRegistration:
    def execute(output_root: Path) -> None:
        build_candidate_bundle(
            repository_root=ROOT,
            plan_path=PLAN,
            library_path=LIBRARY,
            output_root=output_root,
        )

    return ExecutorRegistration(
        library_entry_id=CANDIDATE_ID,
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        source_root=ROOT,
        execute=execute,
    )


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plan_selects_exactly_one_unchanged_library_hypothesis() -> None:
    plan = load_plan(PLAN)
    library = load_library(LIBRARY)
    selected = plan["selected_hypothesis"]
    entry = next(
        item
        for item in library["hypotheses"]
        if item["library_entry_id"] == CANDIDATE_ID
    )
    assert selected == {
        "framework_hypothesis_identity": EXPECTED_HYPOTHESIS_IDENTITY,
        "library_entry_id": CANDIDATE_ID,
        "registration_identity": EXPECTED_REGISTRATION_IDENTITY,
        "revision": 1,
    }
    assert entry["framework_hypothesis_identity"] == EXPECTED_HYPOTHESIS_IDENTITY
    assert entry["registration_identity"] == EXPECTED_REGISTRATION_IDENTITY
    assert entry["revision"] == 1
    campaign = load_campaign_config(CAMPAIGN)
    assert CAMPAIGN.read_bytes() == canonical_json(campaign)
    assert campaign["campaign_identity"] == (
        "f31e0148844b7912b3408d17559e90b3c7d3266ed177286823a875c646cfcca3"
    )
    assert campaign["authorized_executors"][0]["executor_identity"] == (
        "a60a832484b36bfd111410e7571985114a077971bf920c038b31991f93daab47"
    )
    assert len(campaign["authorized_executors"]) == 1


def test_plan_and_dataset_are_canonical_and_exactly_bound() -> None:
    plan = load_plan(PLAN)
    frame = load_dataset(ROOT, plan)
    assert PLAN.read_bytes() == canonical_json(plan)
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == plan["dataset"][
        "file_sha256"
    ]
    assert candidate_dataset_identity(frame) == plan["dataset"]["dataset_identity"]
    assert plan["dataset"]["authorization"] == (
        "candidate_v001_synthetic_discovery_only"
    )
    assert plan["dataset"]["claim_limit"] == (
        "pipeline_evidence_only_no_empirical_edge_claim"
    )


def test_positive_path_emits_canonical_next_bar_proposal_without_lookahead() -> None:
    plan, frame, artifacts = _context()
    provenance = _provenance(artifacts, plan["dataset"]["dataset_identity"])
    prefix = frame.iloc[:21].copy(deep=True)
    original = prefix.copy(deep=True)
    decision = evaluate_high_of_day_breakout(prefix, **provenance)
    assert decision.status == "proposal"
    assert decision.reason_codes == ()
    assert decision.decision_timestamp == "2026-01-05T09:51:00-05:00"
    assert decision.proposal is not None
    assert decision.proposal.signal_timestamp.isoformat() == decision.decision_timestamp
    assert (
        decision.proposal.intended_entry_timestamp.isoformat()
        == decision.decision_timestamp
    )
    assert decision.proposal.provenance["input_last_bar_timestamp"] == (
        "2026-01-05T09:50:00-05:00"
    )
    pd.testing.assert_frame_equal(prefix, original)
    changed = frame.copy(deep=True)
    changed.loc[changed.index[21] :, ["open", "high", "low", "close"]] *= 10
    repeated = evaluate_high_of_day_breakout(changed.iloc[:21], **provenance)
    assert repeated.proposal is not None
    assert repeated.proposal.proposal_id == decision.proposal.proposal_id


def test_negative_unavailable_and_integrity_paths_fail_closed() -> None:
    plan, frame, artifacts = _context()
    provenance = _provenance(artifacts, plan["dataset"]["dataset_identity"])
    negative = frame.iloc[:21].copy(deep=True)
    negative.loc[negative.index[-1], ["high", "close", "volume"]] = [
        10.20,
        10.19,
        2200,
    ]
    decision = evaluate_high_of_day_breakout(negative, **provenance)
    assert decision.status == "no_signal"
    assert decision.proposal is None
    assert decision.reason_codes == ("high_of_day_breakout_absent",)
    unavailable = evaluate_high_of_day_breakout(frame.iloc[:20], **provenance)
    assert unavailable.status == "unavailable"
    assert unavailable.reason_codes == ("warmup_incomplete",)
    gappy = frame.drop(index=10).reset_index(drop=True)
    with pytest.raises(HighOfDayCandidateIntegrityError, match="incomplete"):
        evaluate_high_of_day_breakout(gappy.iloc[:21], **provenance)
    malformed = frame.iloc[:21].copy(deep=True)
    malformed.loc[3, "low"] = malformed.loc[3, "high"] + 1
    with pytest.raises(HighOfDayCandidateIntegrityError, match="OHLC"):
        evaluate_high_of_day_breakout(malformed, **provenance)


def test_lifecycle_identities_and_conformance_are_exact() -> None:
    plan, _, artifacts = _context()
    expected = {
        "hypothesis": EXPECTED_HYPOTHESIS_IDENTITY,
        "specification": (
            "5b1a59ff8118204966e7cebed1e4bc78acbf5308a89ed9a512938b087b0c4b69"
        ),
        "preregistration": (
            "d3335b9fbd11c895d9c4b7aee0142d02e4e448899c4f7361e73690a3a7f47345"
        ),
        "implementation_binding": (
            "973b63f8a5ca2ecf59b628c436fabec103ec9d29a5b422d0266472087ec70f9e"
        ),
        "conformance": (
            "4610d7f459406268a3ee1dc45f5fed0a5d9abace574ecf6bb49686600b4f547a"
        ),
    }
    assert {key: artifacts[key]["identity"] for key in expected} == expected
    assert artifacts["preregistration"]["payload"][
        "permitted_discovery_dataset_identities"
    ] == [plan["dataset"]["dataset_identity"]]
    assert artifacts["conformance"]["payload"]["all_checks_passed"] is True
    assert artifacts["implementation_binding"]["payload"][
        "no_frozen_file_modified"
    ] is True


def test_complete_framework_bundle_is_classified_and_archived(tmp_path: Path) -> None:
    output = tmp_path / "candidate-bundle"
    result = build_candidate_bundle(
        repository_root=ROOT,
        plan_path=PLAN,
        library_path=LIBRARY,
        output_root=output,
    )
    verified = verify_bundle(output)
    discovery = _json(output / "08-discovery.json")
    classification = _json(output / "09-classification.json")
    archive = _json(output / "10-archive.json")
    assert result["verified"] is verified["verified"] is True
    assert result["classification"] == "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    assert discovery["payload"]["proposal_count"] == 1
    assert discovery["payload"]["accepted_trade_count"] == 1
    assert discovery["payload"]["rejected_proposal_count"] == 0
    assert discovery["payload"]["executor_integrity_failure_count"] == 0
    assert discovery["payload"]["evidence_class"] == EVIDENCE_CLASS
    assert classification["payload"]["validation_eligible"] is False
    assert archive["payload"]["archive_state"] == "completed"
    with pytest.raises(Exception, match="already exists"):
        build_candidate_bundle(
            repository_root=ROOT,
            plan_path=PLAN,
            library_path=LIBRARY,
            output_root=output,
        )


def test_campaign_executes_one_and_blocks_every_other_hypothesis(
    tmp_path: Path,
) -> None:
    output = tmp_path / "campaign"
    manifest = run_campaign(
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        output_root=output,
        registrations=(_registration(),),
        repository_root=ROOT,
    )
    selected = _json(output / "entries" / CANDIDATE_ID / "result.json")
    assert manifest["result_count"] == 40
    assert manifest["executed_count"] == 1
    assert manifest["blocked_count"] == 39
    assert manifest["classification_counts"] == {
        BLOCKED_CLASSIFICATION: 39,
        "INCONCLUSIVE_INSUFFICIENT_SAMPLE": 1,
    }
    assert selected["status"] == "executed"
    assert selected["canonical_classification"] == (
        "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    )
    assert selected["execution_evidence"]["executor_integrity_failure_count"] == 0
    assert verify_campaign(
        output,
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        repository_root=ROOT,
    )["verified"] is True


def test_committed_framework_bundle_is_canonical_and_complete() -> None:
    manifest = verify_bundle(CANONICAL_OUTPUT)
    assert manifest["verified"] is True
    assert manifest["identity"] == (
        "7019dddcef0fa6c5ae9b0d3b52ab581206f43afe44dbe8ce9d8daca76d8367d1"
    )
    assert len(manifest["artifact_identities"]) == 10


def test_campaign_rejects_missing_runtime_and_source_substitution(
    tmp_path: Path,
) -> None:
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="runtime is unavailable"):
        run_campaign(
            config_path=CAMPAIGN,
            library_path=LIBRARY,
            output_root=tmp_path / "missing-runtime",
            repository_root=ROOT,
        )
    changed = _json(CAMPAIGN)
    executor = changed["authorized_executors"][0]
    executor["source_sha256"][
        "src/aml/benchmark_candidate_high_of_day_breakout_v001.py"
    ] = "d" * 64
    executor["executor_identity"] = "0" * 64
    changed["campaign_identity"] = "0" * 64
    changed = finalize_campaign_config(changed)
    changed_path = tmp_path / "changed-campaign.json"
    changed_path.write_bytes(canonical_json(changed))
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="source changed"):
        run_campaign(
            config_path=changed_path,
            library_path=LIBRARY,
            output_root=tmp_path / "changed-source",
            registrations=(_registration(),),
            repository_root=ROOT,
        )


def test_dataset_substitution_fails_before_candidate_execution(tmp_path: Path) -> None:
    plan = _json(PLAN)
    plan["dataset"]["file_sha256"] = "d" * 64
    plan["plan_identity"] = "0" * 64
    plan = finalize_plan(plan)
    changed = tmp_path / "plan.json"
    changed.write_bytes(canonical_json(plan))
    loaded = load_plan(changed)
    with pytest.raises(ExecutableCandidateError, match="file changed"):
        load_dataset(ROOT, loaded)


def test_cli_is_byte_deterministic_across_hash_seeds_and_timezones(
    tmp_path: Path,
) -> None:
    roots: list[Path] = []
    for index, (seed, timezone) in enumerate((("1", "UTC"), ("777", "Asia/Tokyo"))):
        output = tmp_path / f"campaign-{index}"
        subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--config",
                str(CAMPAIGN),
                "--plan",
                str(PLAN),
                "--library",
                str(LIBRARY),
                "--output-root",
                str(output),
                "--repository-root",
                str(ROOT),
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(ROOT / "src"),
                "TZ": timezone,
            },
            check=True,
            capture_output=True,
            text=True,
        )
        roots.append(output)
    snapshots = [
        {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        for root in roots
    ]
    assert snapshots[0] == snapshots[1]


def test_candidate_layer_has_no_prohibited_capability_or_reverse_import() -> None:
    candidate_sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "src/aml/benchmark_candidate_high_of_day_breakout_v001.py",
            "src/aml/benchmark_executable_candidate_v001.py",
            "scripts/run_executable_benchmark_candidate_v001.py",
        )
    )
    prohibited = (
        "TradingClient",
        "submit_order",
        "requests.get",
        "alpaca_rest",
        "run_professional_strategy_olympics",
        "parameter_search",
        "optimize",
    )
    assert not any(token in candidate_sources for token in prohibited)
    for frozen in (
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
        "src/aml/professional_strategy_olympics_orchestrator_v001.py",
        "src/aml/professional_strategy_executors_v001.py",
    ):
        source = (ROOT / frozen).read_text(encoding="utf-8")
        assert "benchmark_executable_candidate_v001" not in source
        assert "benchmark_candidate_high_of_day_breakout_v001" not in source
