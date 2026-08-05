from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
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
from aml.exploratory_research_mode_v001 import (
    LABELS,
    ExploratoryResearchError,
    verify_bundle,
)
from aml.opening_range_expansion_continuation_v001 import (
    CANDIDATE_FREE_TEXT_DOMAIN_SCHEMA,
    CANDIDATE_IMPLEMENTATION_NOTE_CODES,
    CANDIDATE_OBSERVATION_ASSERTION_SCOPE,
    CANDIDATE_OBSERVATION_DETAILS,
    CANDIDATE_OBSERVATION_OUTCOMES,
    CANDIDATE_OBSERVATION_REASON_CODES,
    CANDIDATE_OBSERVATION_SUBJECTS,
    CANDIDATE_OBSERVATION_TYPES,
    CANDIDATE_PROHIBITED_FIELDS,
    CANDIDATE_SPECIFIC_LABEL,
    CANDIDATE_SPECIFIC_LABELS,
    CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
    DATASET_VINTAGE,
    FROZEN_DOWNSTREAM_PATHS,
    FROZEN_SPECIFICATION,
    OpeningRangeExpansionError,
    _evidence_manifest,
    _reject_candidate_prohibited_claims,
    _source_hashes,
    build_evidence,
    candidate_free_text_domain_contract,
    candidate_free_text_domain_contract_identity,
    candidate_prohibited_claim_contract_identity,
    candidate_required_inventory_contract,
    candidate_required_inventory_contract_identity,
    candidate_structured_observation_contract,
    candidate_structured_observation_contract_identity,
    create_structured_observation,
    finalize_config,
    load_config,
    normalize_candidate_claim_name,
    run_bounded_exploratory,
    specification_identity,
    validate_config,
    validate_structured_observation,
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
    record["identity"] = value["identity"]
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


def _rehash_complete_publication_chain(output: Path) -> None:
    result_path = next(output.glob("01-*.json"))
    summary_path = output / "summary.json"
    run_path = output / "run.json"
    manifest_path = output / "manifest.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["identity"] = canonical_hash(
        {key: item for key, item in result.items() if key != "identity"}
    )
    result_path.write_bytes(canonical_json(result))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["result_identity"] = result["identity"]
    summary["observation_count"] = result.get("observation_count")
    summary["observation_identities"] = result.get("observation_identities")
    summary["identity"] = canonical_hash(
        {key: item for key, item in summary.items() if key != "identity"}
    )
    summary_path.write_bytes(canonical_json(summary))
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["result_references"] = [
        {"path": result_path.name, "identity": result["identity"]}
    ]
    run["summary_reference"] = {
        "path": summary_path.name,
        "identity": summary["identity"],
    }
    run["observation_count"] = result.get("observation_count")
    run["observation_identities"] = result.get("observation_identities")
    run["identity"] = canonical_hash(
        {key: item for key, item in run.items() if key != "identity"}
    )
    run_path.write_bytes(canonical_json(run))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in manifest["files"]}
    for path, value in ((result_path, result), (summary_path, summary), (run_path, run)):
        by_path[path.name]["identity"] = value["identity"]
        by_path[path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["files"] = sorted(by_path.values(), key=lambda item: item["path"])
    manifest["identity"] = canonical_hash(
        {key: item for key, item in manifest.items() if key != "identity"}
    )
    manifest_path.write_bytes(canonical_json(manifest))


def _evidence_copy(tmp_path: Path, *, name: str) -> Path:
    target = tmp_path / name
    shutil.copytree(ROOT / "manifests/opening_range_expansion_continuation_v001", target)
    return target


def _rehash_evidence_artifact(root: Path, artifact_name: str) -> None:
    artifact = root / artifact_name
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value["identity"] = canonical_hash(
        {key: item for key, item in value.items() if key != "identity"}
    )
    artifact.write_bytes(canonical_json(value))
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(item for item in manifest["files"] if item["path"] == artifact_name)
    record["identity"] = value["identity"]
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest["identity"] = canonical_hash(
        {key: item for key, item in manifest.items() if key != "identity"}
    )
    manifest_path.write_bytes(canonical_json(manifest))


def _rehash_evidence_manifest(root: Path) -> None:
    path = root / "manifest.json"
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
        "c832be1b9b92a2b58906a597e7bfd95dee3a10aba664b6f201868d243f1e89da"
    )
    assert config["candidate_prohibited_claim_contract_identity"] == (
        "90535566580282d3746af19b2511059018a92120ad94d090526f9881ec36cc17"
    )
    assert config["candidate_required_inventory_contract_identity"] == (
        "95cc8aa48dffa373daa612cba90162856087d745e4d9222be622e08aff5532b7"
    )
    assert config["candidate_structured_observation_contract_identity"] == (
        "571d9d773b615cc4e46ee9dad997cb1e602d9a18fa7a4a709b78cf54ce9f91aa"
    )
    assert config["candidate_free_text_domain_contract_identity"] == (
        "2530347c729e5baaab4b1ba9697d1e4a256e2ecd4b7518364aa47946321127c7"
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
    assert evidence["06-implementation-binding.json"]["identity"] == (
        "9c3c42e5ccd38a6eb58a8db01ae35a7b928c84cfc2fac246768faf8415b8a661"
    )
    assert evidence["07-conformance.json"]["identity"] == (
        "84023264f928dfc63d68001785006b807b5c0ae7e58078cd997fa8b6f1d258b0"
    )
    assert evidence["08-executor-registration.json"]["identity"] == (
        "d33e589fae8a4fb46fc513ad8335ba83611783d119ef032d18ea0d594f728af4"
    )
    assert _evidence_manifest(evidence)["identity"] == (
        "5e42cbae714035ce64dbdc455e542e5e761f4d8d6b12dc777785f758121a452e"
    )
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
        assert value["candidate_prohibited_claim_contract_identity"] == (
            candidate_prohibited_claim_contract_identity()
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


def test_candidate_prohibited_contract_covers_required_fields() -> None:
    required = {
        "alpha",
        "annualized_return",
        "authorized_empirical_evidence",
        "average_loss",
        "average_win",
        "beta",
        "broker_ready",
        "buy_recommendation",
        "cagr",
        "calmar",
        "capital_allocation",
        "capital_allocation_recommended",
        "capital_efficiency",
        "capital_eligible",
        "confidence_interval",
        "deployment_ready",
        "drawdown",
        "edge",
        "empirical_edge",
        "empirical_evidence",
        "evidence_of_edge",
        "expectancy",
        "expected_value",
        "gross_pnl",
        "holdout_passed",
        "information_ratio",
        "invest",
        "live_trading_ready",
        "loss",
        "loss_rate",
        "max_drawdown",
        "maximum_drawdown",
        "net_pnl",
        "out_of_sample_passed",
        "paper_trading_ready",
        "payoff_ratio",
        "pnl",
        "position_size_recommendation",
        "production_ready",
        "profit",
        "profit_factor",
        "profitability",
        "profitable",
        "p_value",
        "ready_for_production",
        "realized_pnl",
        "recommended_capital",
        "repeatable_edge",
        "return",
        "returns",
        "risk_adjusted_return",
        "robust",
        "robustness",
        "sell_recommendation",
        "sharpe",
        "sharpe_ratio",
        "sortino",
        "sortino_ratio",
        "statistical_significance",
        "statistically_significant",
        "total_return",
        "trade_recommendation",
        "t_stat",
        "unrealized_pnl",
        "validated",
        "validation_passed",
        "volatility",
        "win_rate",
    }
    assert required <= CANDIDATE_PROHIBITED_FIELDS


@pytest.mark.parametrize(
    ("variant", "normalized"),
    [
        ("profitFactor", "profit_factor"),
        ("Maximum Drawdown", "maximum_drawdown"),
        ("sharpe-ratio", "sharpe_ratio"),
        ("validationPassed", "validation_passed"),
        ("ProductionReady", "production_ready"),
        ("TOTAL RETURNS", "total_return"),
        ("CapitalEfficiencies", "capital_efficiency"),
    ],
)
def test_candidate_claim_normalization_is_explicit_and_deterministic(
    variant: str, normalized: str
) -> None:
    assert normalize_candidate_claim_name(variant) == normalized


@pytest.mark.parametrize("field", sorted(CANDIDATE_PROHIBITED_FIELDS))
def test_every_explicit_candidate_claim_field_is_rejected(field: str) -> None:
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        _reject_candidate_prohibited_claims(
            {field: "SYNTHETIC_HOSTILE_FIELD"}, artifact_name="synthetic.json"
        )


@pytest.mark.parametrize(
    ("artifact_kind", "hostile_payload"),
    [
        ("manifest", {"net_pnl": "SYNTHETIC_HOSTILE_FIELD"}),
        ("manifest", {"maximum_drawdown": "SYNTHETIC_HOSTILE_FIELD"}),
        ("result", {"capital_efficiency": "SYNTHETIC_HOSTILE_FIELD"}),
        (
            "summary",
            {"metadata": {"statistical_significance": True}},
        ),
        ("summary", {"deployment_ready": True}),
        ("manifest", {"capital_allocation_recommended": True}),
        ("result", {"profitFactor": "SYNTHETIC_HOSTILE_FIELD"}),
        ("manifest", {"Maximum Drawdown": "SYNTHETIC_HOSTILE_FIELD"}),
        ("summary", {"sharpe-ratio": "SYNTHETIC_HOSTILE_FIELD"}),
        ("result", {"validationPassed": True}),
        ("summary", {"productionReady": True}),
        ("result", {"claims": {"empirical_edge": True}}),
        ("summary", {"diagnostics": [{"p_value": "0.01"}]}),
        (
            "summary",
            {"optional_metadata": {"capital_efficiency": "synthetic"}},
        ),
        (
            "result",
            {"claims": [{"validated": False}, {"validated": True}]},
        ),
    ],
)
def test_fully_rehashed_hostile_claim_matrix_fails_semantically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
    hostile_payload: dict[str, object],
) -> None:
    case = canonical_hash(
        {"artifact_kind": artifact_kind, "payload": hostile_payload}
    )[:12]
    output = _publish_stub_bundle(tmp_path, monkeypatch, name=f"claims-{case}")
    artifact_name = (
        next(output.glob("01-*.json")).name
        if artifact_kind == "result"
        else f"{artifact_kind}.json"
    )
    path = output / artifact_name
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(hostile_payload)
    path.write_bytes(canonical_json(value))
    if artifact_kind == "manifest":
        _rehash_manifest(output)
    else:
        _rehash_artifact_and_manifest(output, artifact_name)
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize(
    "payload",
    [
        {"claims": {"assertion": "This candidate is profitable"}},
        {"unexpected_wrapper": "deployment ready"},
        {"nested": [{"arbitrary_note": "statistically significant"}]},
    ],
)
def test_claim_value_hidden_under_unexpected_wrapper_is_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(OpeningRangeExpansionError, match="claim value"):
        _reject_candidate_prohibited_claims(
            payload, artifact_name="synthetic.json"
        )


def test_complete_fully_rehashed_hostile_bundle_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="complete-rehash")
    for path in [next(output.glob("01-*.json")), output / "summary.json"]:
        value = json.loads(path.read_text(encoding="utf-8"))
        value["claims"] = {"empirical_edge": True}
        path.write_bytes(canonical_json(value))
        _rehash_artifact_and_manifest(output, path.name)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claims"] = {"empirical_edge": True}
    manifest_path.write_bytes(canonical_json(manifest))
    _rehash_manifest(output)
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_opening_range_exploratory_bundle(output)


def test_every_manifested_candidate_artifact_is_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="derived-artifact")
    source = next(output.glob("01-*.json"))
    derived = output / "02-derived-diagnostic.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["optional_metadata"] = {"capital_efficiency": "synthetic"}
    value["identity"] = canonical_hash(
        {key: item for key, item in value.items() if key != "identity"}
    )
    derived.write_bytes(canonical_json(value))
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append(
        {
            "path": derived.name,
            "sha256": hashlib.sha256(derived.read_bytes()).hexdigest(),
        }
    )
    manifest["files"] = sorted(manifest["files"], key=lambda item: item["path"])
    manifest_path.write_bytes(canonical_json(manifest))
    _rehash_manifest(output)
    with pytest.raises(OpeningRangeExpansionError, match="candidate manifest"):
        verify_opening_range_exploratory_bundle(output)


def test_candidate_verifier_closes_frozen_global_manifest_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="global-gap")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["maximum_drawdown"] = "SYNTHETIC_HOSTILE_FIELD"
    manifest_path.write_bytes(canonical_json(manifest))
    _rehash_manifest(output)
    assert verify_bundle(output)["verified"] is True
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_opening_range_exploratory_bundle(output)


def test_negative_claim_flags_are_allowed_only_as_exact_false_boundaries() -> None:
    valid = {
        "claim_flags": {
            "capital_eligible": False,
            "empirical_evidence": False,
            "holdout": False,
            "production": False,
            "validation": False,
        }
    }
    _reject_candidate_prohibited_claims(valid, artifact_name="synthetic.json")
    invalid = copy.deepcopy(valid)
    invalid["claim_flags"]["capital_eligible"] = True
    with pytest.raises(OpeningRangeExpansionError, match="became affirmative"):
        _reject_candidate_prohibited_claims(invalid, artifact_name="synthetic.json")


def test_legitimate_diagnostic_fields_remain_allowed() -> None:
    _reject_candidate_prohibited_claims(
        {
            "partitions_inspected": 125,
            "warm_up_partitions": 100,
            "evaluated_partitions": 25,
            "causal_decisions": 2125,
            "no_signal_counts": 1948,
            "no_signal_reasons": {"threshold_not_met": 1948},
            "trigger_count": 177,
            "proposal_count": 177,
            "completed_lifecycle_count": 10,
            "rejection_count": 167,
            "unavailable_counts": 0,
            "unavailable_reasons": {},
            "integrity_failure_count": 0,
            "implementation_anomalies": [],
            "missing_data_summary": {},
            "qualitative_engineering_observations": ["No anomaly observed."],
            "contamination_labels": list(LABELS),
            "non_evidence_labels": list(CANDIDATE_SPECIFIC_LABELS),
        },
        artifact_name="synthetic.json",
    )


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
    with pytest.raises(OpeningRangeExpansionError, match="label changed"):
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
    (output / "summary.json").write_bytes(canonical_json(summary))
    _rehash_artifact_and_manifest(output, "summary.json")
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_opening_range_exploratory_bundle(output)


def test_required_inventory_contract_is_closed_and_identity_bound() -> None:
    contract = candidate_required_inventory_contract()
    assert contract["closed_inventory"] is True
    assert contract["optional_roles"] == []
    assert {item["role"] for item in contract["exploratory_publication"]} == {
        "candidate_result",
        "candidate_summary",
        "exploratory_run",
    }
    assert len(contract["evidence"]) == 8
    assert candidate_required_inventory_contract_identity() == (
        _config()["candidate_required_inventory_contract_identity"]
    )


@pytest.mark.parametrize(
    ("artifact_name", "retain_record"),
    [
        (f"01-{CHILD_HYPOTHESIS_ID}.json", False),
        (f"01-{CHILD_HYPOTHESIS_ID}.json", True),
        ("summary.json", False),
        ("run.json", False),
    ],
)
def test_fully_rehashed_missing_required_exploratory_role_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_name: str,
    retain_record: bool,
) -> None:
    output = _publish_stub_bundle(
        tmp_path,
        monkeypatch,
        name=f"missing-{artifact_name.split('.')[0]}-{retain_record}",
    )
    (output / artifact_name).unlink()
    if not retain_record:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"] = [
            item for item in manifest["files"] if item["path"] != artifact_name
        ]
        (output / "manifest.json").write_bytes(canonical_json(manifest))
        _rehash_manifest(output)
    with pytest.raises(OpeningRangeExpansionError):
        verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize(
    "artifact_name",
    [
        "06-implementation-binding.json",
        "07-conformance.json",
        "08-executor-registration.json",
    ],
)
def test_fully_rehashed_missing_required_evidence_role_fails(
    tmp_path: Path, artifact_name: str
) -> None:
    evidence = _evidence_copy(tmp_path, name=f"missing-{artifact_name}")
    (evidence / artifact_name).unlink()
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = [
        item for item in manifest["files"] if item["path"] != artifact_name
    ]
    (evidence / "manifest.json").write_bytes(canonical_json(manifest))
    _rehash_evidence_manifest(evidence)
    with pytest.raises(OpeningRangeExpansionError, match="required role inventory"):
        verify_evidence_directory(evidence, repository_root=ROOT, config=_config())


def test_duplicate_renamed_replaced_and_unlisted_artifacts_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for case in ("duplicate", "renamed", "replaced", "unlisted"):
        output = _publish_stub_bundle(tmp_path, monkeypatch, name=f"inventory-{case}")
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result_name = f"01-{CHILD_HYPOTHESIS_ID}.json"
        if case == "duplicate":
            manifest["files"].append(copy.deepcopy(manifest["files"][0]))
            manifest["files"] = sorted(manifest["files"], key=lambda item: item["path"])
        elif case == "renamed":
            next(item for item in manifest["files"] if item["path"] == result_name)[
                "role"
            ] = "renamed_result"
        elif case == "replaced":
            result = output / result_name
            result.write_bytes((output / "summary.json").read_bytes())
            record = next(item for item in manifest["files"] if item["path"] == result_name)
            replacement = json.loads(result.read_text(encoding="utf-8"))
            record["identity"] = replacement["identity"]
            record["sha256"] = hashlib.sha256(result.read_bytes()).hexdigest()
        else:
            (output / "unlisted.json").write_bytes(canonical_json({"diagnostic": 1}))
        manifest_path.write_bytes(canonical_json(manifest))
        _rehash_manifest(output)
        with pytest.raises(OpeningRangeExpansionError):
            verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize(
    ("artifact_name", "payload"),
    [
        ("06-implementation-binding.json", {"net_pnl": 1}),
        ("07-conformance.json", {"net_pnl": 1}),
        ("08-executor-registration.json", {"net_pnl": 1}),
        ("07-conformance.json", {"statistical_significance": True}),
        ("06-implementation-binding.json", {"validation_passed": True}),
        ("08-executor-registration.json", {"deployment_ready": True}),
        ("07-conformance.json", {"metadata": {"claims": {"empirical_edge": True}}}),
    ],
)
def test_fully_rehashed_evidence_layer_claim_fails_semantically(
    tmp_path: Path, artifact_name: str, payload: dict[str, object]
) -> None:
    evidence = _evidence_copy(
        tmp_path,
        name=f"claim-{artifact_name}-{canonical_hash(payload)[:8]}",
    )
    artifact = evidence / artifact_name
    value = json.loads(artifact.read_text(encoding="utf-8"))
    value["payload"].update(payload)
    artifact.write_bytes(canonical_json(value))
    _rehash_evidence_artifact(evidence, artifact_name)
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_evidence_directory(evidence, repository_root=ROOT, config=_config())


@pytest.mark.parametrize(
    "payload",
    [
        {"net_pnl": 1},
        {"capital_allocation_recommended": True},
    ],
)
def test_fully_rehashed_evidence_manifest_claim_fails_semantically(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    evidence = _evidence_copy(tmp_path, name=f"manifest-claim-{canonical_hash(payload)[:8]}")
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(payload)
    manifest_path.write_bytes(canonical_json(manifest))
    _rehash_evidence_manifest(evidence)
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_evidence_directory(evidence, repository_root=ROOT, config=_config())


def test_fully_rehashed_run_claim_fails_semantically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="run-net-pnl")
    run_path = output / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["net_pnl"] = 1
    run_path.write_bytes(canonical_json(run))
    _rehash_artifact_and_manifest(output, "run.json")
    with pytest.raises(OpeningRangeExpansionError, match="prohibited candidate claim"):
        verify_opening_range_exploratory_bundle(output)


def test_structured_observation_contract_is_closed_and_identity_bound() -> None:
    contract = candidate_structured_observation_contract()
    assert contract["schema_version"] == CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA
    assert contract["observation_types"] == sorted(CANDIDATE_OBSERVATION_TYPES)
    assert contract["outcomes"] == sorted(CANDIDATE_OBSERVATION_OUTCOMES)
    assert contract["subjects"] == sorted(CANDIDATE_OBSERVATION_SUBJECTS)
    assert contract["reason_codes"] == sorted(CANDIDATE_OBSERVATION_REASON_CODES)
    assert contract["assertion_scopes"] == [CANDIDATE_OBSERVATION_ASSERTION_SCOPE]
    assert contract["details_policy"]["arbitrary_prose_permitted"] is False
    assert candidate_structured_observation_contract_identity() == _config()[
        "candidate_structured_observation_contract_identity"
    ]


def test_free_text_domain_has_no_unrestricted_channels() -> None:
    contract = candidate_free_text_domain_contract()
    assert contract["schema_version"] == CANDIDATE_FREE_TEXT_DOMAIN_SCHEMA
    assert contract["arbitrary_prose_permitted"] is False
    assert contract["unrestricted_string_channels"] == []
    assert candidate_free_text_domain_contract_identity() == _config()[
        "candidate_free_text_domain_contract_identity"
    ]


@pytest.mark.parametrize(
    ("signature", "details"), sorted(CANDIDATE_OBSERVATION_DETAILS.items())
)
def test_canonical_structured_observations_are_deterministic(
    signature: tuple[str, str, str, str], details: str
) -> None:
    first = create_structured_observation(*signature)
    second = create_structured_observation(*signature)
    assert first == second
    assert first["details"] == details
    assert validate_structured_observation(first) == first


@pytest.mark.parametrize(
    "sentence",
    [
        "This strategy earns positive returns.",
        "The candidate generated net P&L of 100 dollars.",
        "The strategy outperformed the benchmark.",
        "The candidate has favorable risk-adjusted performance.",
        "The strategy should receive investment capital.",
        "The candidate passed out-of-sample testing.",
        "The strategy is profitable.",
        "The candidate has alpha.",
        "The system is ready for production.",
        "Begin paper trading.",
        "This has statistical significance.",
        "The candidate is validated.",
        "The strategy deserves capital allocation.",
        "Returns were favorable.",
        "The result proves an edge.",
        "This strategy earned positive return.",
        "The candidate was validated.",
        "The result has riskAdjustedReturn.",
        "The result has risk-adjusted returns.",
        "The strategy earns positive returns．",
    ],
)
def test_arbitrary_details_cannot_carry_claims(sentence: str) -> None:
    observation = create_structured_observation(
        "EVALUATOR_PATH",
        "frozen_evaluator",
        "EXERCISED",
        "PROPOSAL_EMITTED",
    )
    observation["details"] = sentence
    observation["identity"] = canonical_hash(
        {
            "domain": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
            "observation": {
                key: item for key, item in observation.items() if key != "identity"
            },
        }
    )
    with pytest.raises(
        OpeningRangeExpansionError,
        match="details changed|prohibited candidate claim value",
    ):
        validate_structured_observation(observation)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observation_type", "PROFITABILITY"),
        ("subject", "positive_returns"),
        ("outcome", "OUTPERFORMED"),
        ("reason_code", "VALIDATION_PASSED"),
        ("assertion_scope", "EMPIRICAL"),
    ],
)
def test_unknown_or_claim_bearing_observation_vocabulary_fails(
    field: str, value: str
) -> None:
    observation = create_structured_observation(
        "EVALUATOR_PATH",
        "frozen_evaluator",
        "EXERCISED",
        "PROPOSAL_EMITTED",
    )
    observation[field] = value
    observation["identity"] = canonical_hash(
        {
            "domain": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
            "observation": {
                key: item for key, item in observation.items() if key != "identity"
            },
        }
    )
    with pytest.raises(OpeningRangeExpansionError):
        validate_structured_observation(observation)


def test_implementation_notes_are_controlled_codes() -> None:
    assert CANDIDATE_IMPLEMENTATION_NOTE_CODES == {
        "EVALUATOR_BINDING_VERIFIED",
        "EVALUATOR_INVOCATION_REFUSED",
        "FROZEN_COMPONENTS_REUSED",
        "MISSING_INPUT_NOT_SUBSTITUTED",
    }


@pytest.mark.parametrize(
    "sentence",
    [
        "This strategy earns positive returns.",
        "The candidate generated net P&L of 100 dollars.",
        "The strategy outperformed the benchmark.",
        "The candidate has favorable risk-adjusted performance.",
        "The strategy should receive investment capital.",
        "The candidate passed out-of-sample testing.",
        "The strategy is profitable.",
        "The candidate has alpha.",
        "The system is ready for production.",
        "Begin paper trading.",
        "This has statistical significance.",
        "The candidate is validated.",
        "The strategy deserves capital allocation.",
        "Returns were favorable.",
        "The result proves an edge.",
    ],
)
def test_fully_rehashed_observation_claim_fails_semantically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sentence: str,
) -> None:
    output = _publish_stub_bundle(
        tmp_path,
        monkeypatch,
        name=f"observation-claim-{hashlib.sha256(sentence.encode()).hexdigest()[:10]}",
    )
    result_path = next(output.glob("01-*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    observation = result["qualitative_observations"][0]
    observation["details"] = sentence
    observation["identity"] = canonical_hash(
        {
            "domain": CANDIDATE_STRUCTURED_OBSERVATION_SCHEMA,
            "observation": {
                key: item for key, item in observation.items() if key != "identity"
            },
        }
    )
    result["observation_identities"][0] = observation["identity"]
    result["observation_identities"] = sorted(result["observation_identities"])
    result_path.write_bytes(canonical_json(result))
    _rehash_complete_publication_chain(output)
    with pytest.raises(
        OpeningRangeExpansionError,
        match="details changed|prohibited candidate claim value",
    ):
        verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("implementation_notes", ["THIS_STRATEGY_EARNS_POSITIVE_RETURNS"]),
        ("obvious_anomalies", ["VALIDATION_PASSED"]),
        ("confidence_warnings", ["capital allocation recommended"]),
    ],
)
def test_fully_rehashed_other_string_channel_claim_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    payload: list[str],
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name=f"string-channel-{field}")
    result_path = next(output.glob("01-*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result[field] = payload
    result_path.write_bytes(canonical_json(result))
    _rehash_complete_publication_chain(output)
    with pytest.raises(OpeningRangeExpansionError):
        verify_opening_range_exploratory_bundle(output)


def test_nested_or_wrapped_observation_claim_cannot_enter_closed_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="nested-observation-claim")
    result_path = next(output.glob("01-*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["qualitative_observations"][0]["wrapper"] = {
        "claims": ["This strategy earns positive returns."]
    }
    result_path.write_bytes(canonical_json(result))
    _rehash_complete_publication_chain(output)
    with pytest.raises(OpeningRangeExpansionError):
        verify_opening_range_exploratory_bundle(output)


@pytest.mark.parametrize("artifact_name", ["summary.json", "run.json"])
def test_fully_rehashed_observation_reconciliation_mismatch_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_name: str,
) -> None:
    output = _publish_stub_bundle(
        tmp_path, monkeypatch, name=f"observation-reconciliation-{artifact_name}"
    )
    path = output / artifact_name
    value = json.loads(path.read_text(encoding="utf-8"))
    value["observation_count"] += 1
    path.write_bytes(canonical_json(value))
    _rehash_artifact_and_manifest(output, artifact_name)
    with pytest.raises(OpeningRangeExpansionError, match="result-summary-run graph"):
        verify_opening_range_exploratory_bundle(output)


def test_published_observations_are_structured_and_reconciled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _publish_stub_bundle(tmp_path, monkeypatch, name="structured-observations")
    result = json.loads(next(output.glob("01-*.json")).read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    observations = result["qualitative_observations"]
    assert observations
    assert all(validate_structured_observation(item) == item for item in observations)
    identities = [item["identity"] for item in observations]
    assert identities == sorted(identities)
    assert result["observation_count"] == len(observations)
    assert result["observation_identities"] == identities
    assert summary["observation_count"] == len(observations)
    assert summary["observation_identities"] == identities
    assert run["observation_count"] == len(observations)
    assert run["observation_identities"] == identities
