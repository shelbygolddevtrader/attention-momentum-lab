from __future__ import annotations

import json
from pathlib import Path

import pytest

from aml.benchmark_discovery_campaign_v001 import (
    BenchmarkDiscoveryCampaignError,
    run_campaign,
    verify_campaign,
)
from aml.benchmark_executable_specification_v001 import (
    ExecutableSpecificationError,
    build_bundle,
    load_config,
)
from aml.benchmark_strategy_research_v001 import BenchmarkResearchError
from scripts.run_executable_specification_implementation_v001 import registrations


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/executable_specification_implementation_v001.json"
CAMPAIGN = ROOT / "config/executable_specification_implementation_campaign_v001.json"
LIBRARY = ROOT / "config/benchmark_hypothesis_library_v001.json"
SPECIFICATION = ROOT / "config/benchmark_specification_campaign_v001.json"
EXISTING_PLAN = ROOT / "config/executable_benchmark_candidate_v001.json"


def _build(path: Path):
    return build_bundle(
        repository_root=ROOT,
        config_path=CONFIG,
        library_path=LIBRARY,
        specification_campaign_path=SPECIFICATION,
        output_root=path,
    )


def test_config_and_bundle_identities_are_frozen(tmp_path: Path) -> None:
    config = load_config(CONFIG, repository_root=ROOT)
    assert config["implementation_identity"] == (
        "896148c2197b519b3eb9b11fa9082b3215d7494322829ea9b3a826f7055e7c26"
    )
    summary = _build(tmp_path / "bundle")
    assert summary == {
        "bundle_identity": "ea94a22c668c2104aa4b23624a9d74804411fbab71309d384af08c7605d0e3bd",
        "classification": "INCONCLUSIVE_DATA_LIMITATION",
        "classification_identity": "7eeff5c694460c99b60f0e6bf32ec01b3e6921143a8ab26a1ebb61a78c2726eb",
        "conformance_identity": "3e50fbc52749fa87cdd38faa2f82418aa2684c63aaecd074a1edad5f466a6a86",
        "dataset_identity": "e3a793b9f30189cbb12620461b6a26fc567fa8253ae69af5a42a9d7c3802ffcd",
        "discovery_identity": "07962f6b9afe7da53879eafce1ca8eb965b27b33f7e121bac69e636642f04c89",
        "implementation_binding_identity": "af7415bf88d12c4482c3b16c0774436066b6f5661dfbf1a752d444d4f5c80ccb",
        "preregistration_identity": "4712fe4239a5a4bb7f929d8b5ab7120b023110812913fe95a99fe3518e4a37c4",
        "specification_identity": "d46e88fc16a91c8ea99a4f91417059de61a73164a48d1fdc700f5afb5dfc8eb7",
        "verified": True,
    }


def test_bundle_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert _build(first) == _build(second)
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files


def test_bundle_is_write_once(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    _build(output)
    with pytest.raises(BenchmarkResearchError, match="already exists"):
        _build(output)


def test_registered_campaign_executes_two_and_blocks_38(tmp_path: Path) -> None:
    output = tmp_path / "campaign"
    result = run_campaign(
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        output_root=output,
        registrations=registrations(
            repository_root=ROOT,
            implementation_config=CONFIG,
            existing_plan=EXISTING_PLAN,
            library=LIBRARY,
            specification_campaign=SPECIFICATION,
        ),
        repository_root=ROOT,
    )
    assert result["verified"] is True
    assert result["executed_count"] == 2
    assert result["blocked_count"] == 38
    assert result["result_count"] == 40
    assert result["manifest_identity"] == (
        "65c7713383cf944241ccdbcd85af4f08aa1ac4bd8abce618bada1d74856df2b9"
    )
    assert verify_campaign(
        output,
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        repository_root=ROOT,
    ) == result


def test_missing_runtime_registration_fails_closed(tmp_path: Path) -> None:
    runtime = registrations(
        repository_root=ROOT,
        implementation_config=CONFIG,
        existing_plan=EXISTING_PLAN,
        library=LIBRARY,
        specification_campaign=SPECIFICATION,
    )
    with pytest.raises(BenchmarkDiscoveryCampaignError, match="runtime is unavailable"):
        run_campaign(
            config_path=CAMPAIGN,
            library_path=LIBRARY,
            output_root=tmp_path / "campaign",
            registrations=runtime[:1],
            repository_root=ROOT,
        )


def test_config_identity_tampering_fails_closed(tmp_path: Path) -> None:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    value["policy"]["optimization_count"] = 1
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ExecutableSpecificationError):
        load_config(path, repository_root=ROOT)


def test_persisted_bundle_matches_reproduction(tmp_path: Path) -> None:
    persisted = ROOT / "manifests/executable_specification_implementation_v001"
    assert verify_campaign(
        persisted,
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        repository_root=ROOT,
    )["verified"] is True
    reproduced = tmp_path / "campaign"
    run_campaign(
        config_path=CAMPAIGN,
        library_path=LIBRARY,
        output_root=reproduced,
        registrations=registrations(
            repository_root=ROOT,
            implementation_config=CONFIG,
            existing_plan=EXISTING_PLAN,
            library=LIBRARY,
            specification_campaign=SPECIFICATION,
        ),
        repository_root=ROOT,
    )
    expected = {
        path.relative_to(persisted): path.read_bytes()
        for path in persisted.rglob("*")
        if path.is_file()
    }
    actual = {
        path.relative_to(reproduced): path.read_bytes()
        for path in reproduced.rglob("*")
        if path.is_file()
    }
    assert actual == expected
