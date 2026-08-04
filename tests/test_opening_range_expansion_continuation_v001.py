from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aml.benchmark_candidate_opening_range_expansion_v001 import (
    CHILD_HYPOTHESIS_ID,
    EXECUTOR_REGISTRY,
    PARENT_LIBRARY_ENTRY_ID,
    REFERENCE_STRATEGY_ID,
    conformance_bars,
    conformance_inputs,
    evaluate_opening_range_expansion,
    evaluation_input,
    no_lookahead_conformance,
    proposal_pipeline_conformance,
    same_clock_history,
    verify_reference_binding,
)
from aml.benchmark_hypothesis_library_v001 import load_library
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json
from aml.exploratory_research_mode_v001 import LABELS, ExploratoryResearchError
from aml.opening_range_expansion_continuation_v001 import (
    CANDIDATE_SPECIFIC_LABEL,
    CANDIDATE_SPECIFIC_LABELS,
    DATASET_VINTAGE,
    FROZEN_DOWNSTREAM_PATHS,
    FROZEN_SPECIFICATION,
    OpeningRangeExpansionError,
    _evidence_manifest,
    _source_hashes,
    build_evidence,
    finalize_config,
    load_config,
    run_bounded_exploratory,
    specification_identity,
    validate_config,
    verify_evidence_directory,
    verify_opening_range_exploratory_bundle,
    write_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/opening_range_expansion_continuation_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"


def _config() -> dict[str, object]:
    return load_config(CONFIG, ROOT)


def _evidence() -> dict[str, dict[str, object]]:
    return build_evidence(repository_root=ROOT, config=_config(), library_path=LIBRARY)


def _publish_stub_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str,
) -> Path:
    import aml.opening_range_expansion_continuation_v001 as campaign

    dataset = tmp_path / DATASET_VINTAGE
    dataset.mkdir(exist_ok=True)
    output = tmp_path / f"exploratory_research/v001/{name}"
    dummy = SimpleNamespace(warning_codes=("CONTAMINATED_PARENT_DATASET",))
    records = [
        {
            "metadata_sha256": "1" * 64,
            "processed_sha256": "2" * 64,
            "role": "evaluated",
            "session": "2023-08-21",
            "symbol": "AAPL",
            "warning_codes": ["CONTAMINATED_PARENT_DATASET"],
        }
    ]
    counts = {
        "executed_trade_count": 1,
        "integrity_failure_count": 0,
        "proposal_count": 1,
        "rejected_proposal_count": 0,
        "trigger_count": 1,
        "unavailable_event_count": 0,
    }
    monkeypatch.setattr(
        campaign,
        "_load_partitions",
        lambda *_: ({("AAPL", "2023-08-21"): dummy}, records),
    )
    monkeypatch.setattr(
        campaign,
        "_evaluate_exploratory",
        lambda *_: (counts, Counter({"proposal": 1}), Counter(), [], []),
    )
    run_bounded_exploratory(
        repository_root=ROOT,
        config=_config(),
        evidence_artifacts=_evidence(),
        dataset_root=dataset,
        output_root=output,
    )
    return output


def _rehash_artifact_and_manifest(output: Path, artifact_name: str) -> None:
    artifact = output / artifact_name
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value["identity"] = canonical_hash(
        {key: item for key, item in value.items() if key != "identity"}
    )
    artifact.write_bytes(canonical_json(value))
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(item for item in manifest["files"] if item["path"] == artifact_name)
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest["identity"] = canonical_hash(
        {key: item for key, item in manifest.items() if key != "identity"}
    )
    manifest_path.write_bytes(canonical_json(manifest))


def _rehash_manifest(output: Path) -> None:
    path = output / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["identity"] = canonical_hash(
        {key: item for key, item in value.items() if key != "identity"}
    )
    path.write_bytes(canonical_json(value))


def test_parent_is_immutable_and_ambiguity_creates_revision_two_child() -> None:
    library = load_library(LIBRARY)
    parent = next(
        item
        for item in library["hypotheses"]
        if item["library_entry_id"] == PARENT_LIBRARY_ENTRY_ID
    )
    config = _config()
    assert parent["revision"] == 1
    assert parent["framework_hypothesis_identity"] == (
        "c17be56b215a4726a6a6e90c4193b2e41a9d04ea1bf6f125e28be7c3578d6ef3"
    )
    assert config["child"] == {
        "hypothesis_id": CHILD_HYPOTHESIS_ID,
        "revision": 2,
        "version": "1.0.0",
    }
    assert FROZEN_SPECIFICATION["ambiguity_resolution"]["action"] == (
        "new_child_hypothesis"
    )


def test_specification_and_config_identities_are_frozen() -> None:
    config = _config()
    assert specification_identity() == (
        "13611f02dcb749c0f8f13ffae5485dfa87df8b469baf9e59044c9d4b698a5494"
    )
    assert config["config_identity"] == (
        "7c1e5f8327a742f64bd8d12ffadf468efd0c28890027d03a64a88cf578969126"
    )
    assert config["exploratory_dataset_binding"]["binding_identity"] == (
        "21c33ab375b57f4b9b3804068c5dedd56321befa47cbdb44fec5e0cb23bcd17c"
    )


def test_complete_specification_freezes_rule_order_and_claim_boundary() -> None:
    spec = FROZEN_SPECIFICATION
    assert spec["opening_range"]["bar_labels"] == [
        "09:30",
        "09:31",
        "09:32",
        "09:33",
        "09:34",
    ]
    assert spec["expansion"]["observation_window"] == "09:35 through 10:59 inclusive"
    assert spec["volume_confirmation"]["minimum_ratio_inclusive"] == 1.5
    assert spec["entry"]["rule"] == "exact next complete bar raw open"
    assert spec["stop"]["rule"] == "fixed opening range low"
    assert spec["target"]["rule"] == (
        "cost-adjusted entry plus two times initial per-share risk"
    )
    assert spec["lifecycle"]["maximum_complete_bars"] == 120
    assert spec["lifecycle"]["event_precedence"].startswith("gap stop")
    assert "no empirical" in spec["claim_boundary"]


def test_registered_executor_is_an_exact_frozen_alias() -> None:
    verify_reference_binding()
    assert set(EXECUTOR_REGISTRY) == {CHILD_HYPOTHESIS_ID}
    assert EXECUTOR_REGISTRY[CHILD_HYPOTHESIS_ID] is evaluate_opening_range_expansion
    positive = conformance_inputs()["positive"]
    result = evaluate_opening_range_expansion(positive)
    assert result.status == "proposal"
    assert result.proposal is not None
    assert result.proposal.strategy_id == REFERENCE_STRATEGY_ID
    assert result.proposal.strategy_identity == (
        "8092124c58649e112e0c8c1d137583fdcf926ec0ad6bc6397bf36db09294bedb"
    )


@pytest.mark.parametrize(
    ("case_id", "status"),
    [
        ("integrity-failure", "integrity_failure"),
        ("negative", "no_signal"),
        ("positive", "proposal"),
        ("unavailable", "unavailable"),
    ],
)
def test_positive_negative_unavailable_and_integrity_paths(
    case_id: str, status: str
) -> None:
    result = evaluate_opening_range_expansion(conformance_inputs()[case_id])
    assert result.status == status


def test_next_bar_entry_and_frozen_lifecycle_are_preserved() -> None:
    result = evaluate_opening_range_expansion(conformance_inputs()["positive"])
    proposal = result.proposal
    assert proposal is not None
    assert proposal.signal_timestamp == "2026-01-05T09:36:00-05:00"
    assert proposal.intended_entry_timestamp == "2026-01-05T09:36:00-05:00"
    assert proposal.raw_entry_open == 101.6
    assert proposal.stop == 99.0
    assert proposal.target == 107.11
    assert proposal.timeout_complete_bars == 120
    assert proposal.friction_basis_points_per_side == 10
    assert proposal.commission_per_share_per_order == 0.005
    assert proposal.minimum_commission_per_order == 1.0
    assert proposal_pipeline_conformance() is True


def test_causal_decision_is_unchanged_by_future_bar_fields() -> None:
    assert no_lookahead_conformance() is True
    bars = conformance_bars()
    baseline = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=bars[6])
    )
    late = tuple([*bars, type(bars[-1])(**{
        **{field: getattr(bars[-1], field) for field in bars[-1].__dataclass_fields__},
        "timestamp": bars[-1].timestamp.replace(minute=37),
        "high": 999.0,
        "low": 1.0,
        "close": 500.0,
    })])
    changed = evaluate_opening_range_expansion(
        evaluation_input(late[:6], next_bar=late[6])
    )
    assert baseline.canonical_bytes() == changed.canonical_bytes()


def test_history_is_strictly_prior_and_twenty_records_are_required() -> None:
    bars = conformance_bars()
    unavailable = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=bars[6], history=same_clock_history(count=19))
    )
    available = evaluate_opening_range_expansion(
        evaluation_input(bars[:6], next_bar=bars[6], history=same_clock_history(count=20))
    )
    assert unavailable.status == "unavailable"
    assert unavailable.reason_codes == ("unavailable_same_clock_history",)
    assert available.status == "proposal"
    assert all(item.session < bars[0].session for item in same_clock_history(count=20))


def test_evidence_chain_is_complete_and_reconciled() -> None:
    evidence = _evidence()
    assert list(evidence) == [
        "01-observation.json",
        "02-child-hypothesis.json",
        "03-triage.json",
        "04-specification.json",
        "05-preregistration.json",
        "06-implementation-binding.json",
        "07-conformance.json",
        "08-executor-registration.json",
    ]
    preregistration = evidence["05-preregistration.json"]["payload"]
    assert preregistration["permitted_empirical_dataset_identities"] == []
    assert preregistration["research_definitions_locked"] is True
    conformance = evidence["07-conformance.json"]["payload"]
    assert conformance["all_checks_passed"] is True
    assert [item["case_id"] for item in conformance["cases"]] == [
        "integrity-failure",
        "negative",
        "positive",
        "unavailable",
    ]


def test_evidence_is_byte_deterministic_and_write_once(tmp_path: Path) -> None:
    artifacts = _evidence()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = write_evidence(first, artifacts)
    second_manifest = write_evidence(second, _evidence())
    assert first_manifest == second_manifest
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    assert verify_evidence_directory(
        first, repository_root=ROOT, config=_config()
    )["verified"] is True
    assert write_evidence(first, artifacts) == first_manifest
    (first / "01-observation.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OpeningRangeExpansionError, match="differs"):
        write_evidence(first, artifacts)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("specification_identity", "0" * 64, "specification"),
        ("reference_contract", {}, "reference contract"),
        ("source_paths", [], "source inventory"),
    ],
)
def test_config_tampering_fails_closed(
    field: str, value: object, message: str
) -> None:
    config = copy.deepcopy(_config())
    config[field] = value
    config = finalize_config(config)
    with pytest.raises(OpeningRangeExpansionError, match=message):
        validate_config(config, ROOT)


def test_frozen_downstream_hashes_match_phase_a_main() -> None:
    assert _source_hashes(ROOT) == {
        **{
            "src/aml/discovery_screen_v001.py": "42182054634c460bc4424efda436d7db5e2133ccce75bc2a458ba5cd6d460c5f",
            "src/aml/exploratory_research_mode_v001.py": "38d87992043ae8ef415af37911b69c5a8ab9e40fa5b59b244173ad2befa808a4",
            "src/aml/professional_strategy_executor_models_v001.py": "9a0f95d2a717b48e8604e18fe22f84d8fd5e56686a49a80809f2e5ffd3bbc431",
            "src/aml/professional_strategy_executors_v001.py": "6b136d9f55f079f7a0080f302b1496eefb73f96cbd15f12730368bdf72030c8b",
            "src/aml/professional_strategy_indicators_v001.py": "921243b0ce95f7575a011d0d9979fc952d494b837c41c9d0cc8b5f6470733436",
            "src/aml/professional_strategy_lifecycle_v001.py": "5123661a751ca8f34ac9d5f4917ba48ec2dfac4d280ac31760dd46adad032cbc",
        },
        **{
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in _config()["source_paths"]
        },
    }
    assert tuple(_config()["frozen_downstream_paths"]) == FROZEN_DOWNSTREAM_PATHS


def test_exploratory_bundle_is_write_once_and_non_economic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="opening-range-test")
    assert verify_opening_range_exploratory_bundle(output)["verified"] is True
    hypothesis_result = json.loads(next(output.glob("01-*.json")).read_text())
    evidence = _evidence()
    assert hypothesis_result["hypothesis"]["framework_hypothesis_identity"] == (
        evidence["02-child-hypothesis.json"]["identity"]
    )
    assert hypothesis_result["hypothesis"]["registration_identity"] == (
        evidence["08-executor-registration.json"]["identity"]
    )
    summary = json.loads((output / "summary.json").read_text())
    assert summary["evidence_binding"] == {
        "child_hypothesis_identity": evidence["02-child-hypothesis.json"]["identity"],
        "conformance_identity": evidence["07-conformance.json"]["identity"],
        "evidence_manifest_identity": _evidence_manifest(evidence)["identity"],
        "implementation_binding_identity": evidence[
            "06-implementation-binding.json"
        ]["identity"],
        "preregistration_identity": evidence["05-preregistration.json"]["identity"],
        "registration_identity": evidence["08-executor-registration.json"]["identity"],
        "specification_identity": specification_identity(),
    }
    for path in output.glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["labels"] == list(LABELS)
        assert value["candidate_specific_labels"] == list(
            CANDIDATE_SPECIFIC_LABELS
        )
        for prohibited in (
            '"expectancy"',
            '"gross_pnl"',
            '"net_pnl"',
            '"profit_factor"',
            '"return"',
            '"sharpe"',
            '"win_rate"',
        ):
            assert prohibited not in text
    with pytest.raises(ExploratoryResearchError, match="already exists"):
        dataset = tmp_path / DATASET_VINTAGE
        run_bounded_exploratory(
            repository_root=ROOT,
            config=_config(),
            evidence_artifacts=_evidence(),
            dataset_root=dataset,
            output_root=output,
        )


@pytest.mark.parametrize("artifact_kind", ["result", "summary", "manifest"])
def test_candidate_label_omission_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name=f"omit-{artifact_kind}")
    artifact_name = (
        next(output.glob("01-*.json")).name
        if artifact_kind == "result"
        else f"{artifact_kind}.json"
    )
    path = output / artifact_name
    value = json.loads(path.read_text(encoding="utf-8"))
    value.pop("candidate_specific_labels")
    path.write_bytes(canonical_json(value))
    if artifact_kind == "manifest":
        _rehash_manifest(output)
    else:
        _rehash_artifact_and_manifest(output, artifact_name)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize(
    "replacement",
    [
        "Not Empirical Evidence",
        "NOT EMPIRICAL EVIDENCE.",
        "NOT AUTHORIZED FOR EMPIRICAL CONCLUSIONS",
    ],
)
def test_candidate_label_spelling_synonym_or_punctuation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    output = _publish_stub_bundle(
        tmp_path,
        monkeypatch,
        name=hashlib.sha256(replacement.encode()).hexdigest()[:8],
    )
    artifact = next(output.glob("01-*.json"))
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value["candidate_specific_labels"] = [replacement]
    artifact.write_bytes(canonical_json(value))
    _rehash_artifact_and_manifest(output, artifact.name)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


def test_duplicate_candidate_label_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="duplicate-label")
    artifact = next(output.glob("01-*.json"))
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value["candidate_specific_labels"] = [
        CANDIDATE_SPECIFIC_LABEL,
        CANDIDATE_SPECIFIC_LABEL,
    ]
    artifact.write_bytes(canonical_json(value))
    _rehash_artifact_and_manifest(output, artifact.name)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


def test_prose_only_candidate_label_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="prose-only")
    artifact = next(output.glob("01-*.json"))
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value.pop("candidate_specific_labels")
    value["qualitative_observations"].append(CANDIDATE_SPECIFIC_LABEL)
    artifact.write_bytes(canonical_json(value))
    _rehash_artifact_and_manifest(output, artifact.name)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


def test_result_summary_manifest_disagreement_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="disagreement")
    path = output / "summary.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["candidate_specific_labels"] = [
        "NOT AUTHORIZED FOR EMPIRICAL CONCLUSIONS"
    ]
    path.write_bytes(canonical_json(value))
    _rehash_artifact_and_manifest(output, path.name)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


def test_label_tampering_cannot_retain_identity_or_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="stale-identity")
    artifact = next(output.glob("01-*.json"))
    value = json.loads(artifact.read_text(encoding="utf-8"))
    old_identity = value["identity"]
    value["candidate_specific_labels"] = ["NOT EMPIRICAL evidence"]
    assert canonical_hash(
        {key: item for key, item in value.items() if key != "identity"}
    ) != old_identity
    artifact.write_bytes(canonical_json(value))
    with pytest.raises(ExploratoryResearchError, match="hash mismatch"):
        verify_opening_range_exploratory_bundle(output)


def test_stale_pre_correction_bundle_cannot_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="legacy-bundle")
    for path in [next(output.glob("01-*.json")), output / "summary.json"]:
        value = json.loads(path.read_text(encoding="utf-8"))
        value.pop("candidate_specific_labels")
        path.write_bytes(canonical_json(value))
        _rehash_artifact_and_manifest(output, path.name)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("candidate_specific_labels")
    manifest_path.write_bytes(canonical_json(manifest))
    _rehash_manifest(output)
    with pytest.raises(OpeningRangeExpansionError, match="candidate-specific"):
        verify_opening_range_exploratory_bundle(output)


def test_corrected_bundle_is_byte_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _publish_stub_bundle(tmp_path, monkeypatch, name="determinism-a")
    first_bytes = {path.name: path.read_bytes() for path in first.iterdir()}
    second = _publish_stub_bundle(tmp_path, monkeypatch, name="determinism-b")
    assert first_bytes == {path.name: path.read_bytes() for path in second.iterdir()}


def test_exploratory_bundle_rejects_prohibited_metric_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aml.opening_range_expansion_continuation_v001 as campaign

    dataset = tmp_path / DATASET_VINTAGE
    dataset.mkdir()
    output = tmp_path / "exploratory_research/v001/tamper-test"
    dummy = SimpleNamespace(warning_codes=())
    counts = {
        "executed_trade_count": 0,
        "integrity_failure_count": 0,
        "proposal_count": 0,
        "rejected_proposal_count": 0,
        "trigger_count": 0,
        "unavailable_event_count": 0,
    }
    monkeypatch.setattr(campaign, "_load_partitions", lambda *_: ({("x", "y"): dummy}, []))
    monkeypatch.setattr(
        campaign,
        "_evaluate_exploratory",
        lambda *_: (counts, Counter(), Counter(), [], []),
    )
    run_bounded_exploratory(
        repository_root=ROOT,
        config=_config(),
        evidence_artifacts=_evidence(),
        dataset_root=dataset,
        output_root=output,
    )
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    summary["net_pnl"] = 1
    (output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ExploratoryResearchError):
        verify_opening_range_exploratory_bundle(output)
