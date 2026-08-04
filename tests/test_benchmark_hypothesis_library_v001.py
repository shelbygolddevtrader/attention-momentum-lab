"""Determinism, provenance, immutability, and authority tests for Library V001."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.benchmark_hypothesis_library_v001 import (
    HypothesisLibraryError,
    derive_framework_identities,
    finalize_identities,
    framework_artifacts,
    library_identity,
    load_library,
    registration_identity,
    source_material_identity,
    validate_library,
)
from aml.benchmark_strategy_research_v001 import canonical_json, validate_artifact


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_PATH = ROOT / "config/benchmark_hypothesis_library_v001.json"
EXPECTED_LIBRARY_IDENTITY = (
    "6d9b4c8f1f279805240ac53c01de98906fb6c7853121a57350dff3395ae85003"
)


def library() -> dict[str, object]:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def test_canonical_library_loads_with_exact_frozen_identity_and_counts() -> None:
    value = load_library(LIBRARY_PATH)
    assert value["library_identity"] == EXPECTED_LIBRARY_IDENTITY
    assert value["hypothesis_count"] == 40
    assert value["source_count"] == 22
    assert LIBRARY_PATH.read_bytes() == canonical_json(value)


def test_every_registration_has_required_research_content_and_no_authority() -> None:
    value = library()
    required_text = (
        "economic_mechanism",
        "entry_concept",
        "exit_concept",
        "expected_holding_period",
        "market_assumption",
        "source_interpretation",
    )
    required_lists = (
        "anticipated_failure_modes",
        "directional_scope",
        "expected_regimes",
        "invalidation_conditions",
        "required_indicators",
        "source_ids",
        "taxonomy",
    )
    for entry in value["hypotheses"]:
        assert all(entry[field].strip() for field in required_text)
        assert all(entry[field] for field in required_lists)
        assert entry["expected_trade_frequency"]["description"].strip()
        assert entry["discovery_authorized"] is False
        assert entry["implementation_authorized"] is False
        assert entry["registration_status"] == "preregistered_hypothesis_only"


def test_source_types_and_taxonomy_cover_all_required_origin_classes() -> None:
    value = library()
    assert {source["source_type"] for source in value["sources"]} == {
        "academic_research",
        "official_market_documentation",
        "professional_literature",
    }
    used_sources = {
        source_id
        for entry in value["hypotheses"]
        for source_id in entry["source_ids"]
    }
    assert used_sources == {source["source_id"] for source in value["sources"]}
    taxonomy = {tag for entry in value["hypotheses"] for tag in entry["taxonomy"]}
    assert {
        "attention",
        "auction",
        "event-driven",
        "liquidity",
        "momentum",
        "reversal",
    }.issubset(taxonomy)


def test_all_source_and_registration_identities_reproduce() -> None:
    value = library()
    sources = {source["source_id"]: source for source in value["sources"]}
    for source in value["sources"]:
        assert source_material_identity(source) == source["source_material_identity"]
    for entry in value["hypotheses"]:
        observation_identity, hypothesis_identity = derive_framework_identities(
            entry, sources
        )
        assert observation_identity == entry["framework_observation_identity"]
        assert hypothesis_identity == entry["framework_hypothesis_identity"]
        assert registration_identity(entry) == entry["registration_identity"]
    assert library_identity(value) == value["library_identity"]


def test_framework_bridge_preserves_source_contamination_and_native_schemas() -> None:
    value = library()
    sources = {source["source_id"]: source for source in value["sources"]}
    for entry in value["hypotheses"]:
        observation, hypothesis = framework_artifacts(entry, sources)
        validate_artifact(observation, "observation")
        validate_artifact(hypothesis, "hypothesis")
        expected = sorted(
            sources[source_id]["source_material_identity"]
            for source_id in entry["source_ids"]
        )
        assert observation["payload"]["source_dataset_identities"] == expected
        assert hypothesis["payload"]["contaminated_dataset_identities"] == expected


def test_semantic_mutation_invalidates_registration_and_framework_identity() -> None:
    changed = library()
    changed["hypotheses"][0]["economic_mechanism"] += " altered"
    changed["library_identity"] = library_identity(changed)
    with pytest.raises(HypothesisLibraryError, match="framework hypothesis identity"):
        validate_library(changed)


def test_source_mutation_invalidates_source_identity() -> None:
    changed = library()
    changed["sources"][0]["stable_locator"] = "https://example.invalid/substitute"
    changed["library_identity"] = library_identity(changed)
    with pytest.raises(HypothesisLibraryError, match="source material identity"):
        validate_library(changed)


def test_timestamp_locator_and_source_class_guarantees_are_executable() -> None:
    timestamp = library()
    timestamp["hypotheses"][0]["registered_at"] = "2026-08-04T08:00:00+02:00"
    timestamp["library_identity"] = library_identity(timestamp)
    with pytest.raises(HypothesisLibraryError, match="canonical UTC"):
        validate_library(timestamp)

    locator = library()
    locator["sources"][0]["stable_locator"] = "http://example.com/source"
    locator["sources"][0]["source_material_identity"] = source_material_identity(
        locator["sources"][0]
    )
    locator["library_identity"] = library_identity(locator)
    with pytest.raises(HypothesisLibraryError, match="HTTPS URL"):
        validate_library(locator)

    source_class = library()
    for source in source_class["sources"]:
        source["source_type"] = "academic_research"
        source["source_material_identity"] = source_material_identity(source)
    source_class["library_identity"] = library_identity(source_class)
    with pytest.raises(HypothesisLibraryError, match="every required source type"):
        validate_library(source_class)


def test_semantic_duplicates_and_asymmetric_related_links_fail_closed() -> None:
    duplicate = library()
    first, second = duplicate["hypotheses"][:2]
    for field in (
        "economic_mechanism",
        "entry_concept",
        "exit_concept",
        "invalidation_conditions",
        "expected_regimes",
        "required_indicators",
        "expected_holding_period",
    ):
        second[field] = copy.deepcopy(first[field])
    with pytest.raises(HypothesisLibraryError, match="semantic hypothesis concepts"):
        finalize_identities(duplicate)

    asymmetric = library()
    related_id = asymmetric["hypotheses"][0]["related_hypothesis_ids"][0]
    peer = next(
        item for item in asymmetric["hypotheses"] if item["library_entry_id"] == related_id
    )
    peer["related_hypothesis_ids"] = []
    with pytest.raises(HypothesisLibraryError, match="links must be symmetric"):
        finalize_identities(asymmetric)


def test_authority_escalation_is_rejected_even_with_recomputed_identities() -> None:
    changed = library()
    entry = changed["hypotheses"][0]
    entry["discovery_authorized"] = True
    entry["registration_identity"] = registration_identity(entry)
    changed["library_identity"] = library_identity(changed)
    with pytest.raises(HypothesisLibraryError, match="cannot authorize"):
        validate_library(changed)


def test_unknown_source_duplicate_identity_and_nondeterministic_order_fail() -> None:
    unknown = library()
    unknown["hypotheses"][0]["source_ids"] = ["unknown-source"]
    unknown["library_identity"] = library_identity(unknown)
    with pytest.raises(HypothesisLibraryError, match="unknown source"):
        validate_library(unknown)

    duplicate = library()
    duplicate["hypotheses"][1] = copy.deepcopy(duplicate["hypotheses"][0])
    with pytest.raises(HypothesisLibraryError, match="repeat"):
        finalize_identities(duplicate)

    reordered = library()
    reordered["hypotheses"][0], reordered["hypotheses"][1] = (
        reordered["hypotheses"][1],
        reordered["hypotheses"][0],
    )
    reordered["library_identity"] = library_identity(reordered)
    with pytest.raises(HypothesisLibraryError, match="deterministically sorted"):
        validate_library(reordered)


def test_hypothesis_count_bounds_fail_closed() -> None:
    changed = library()
    changed["hypotheses"] = changed["hypotheses"][:29]
    changed["hypothesis_count"] = 29
    changed["library_identity"] = library_identity(changed)
    with pytest.raises(HypothesisLibraryError, match="30 to 50"):
        validate_library(changed)


def test_strict_loader_rejects_noncanonical_duplicate_and_symlink_files(
    tmp_path: Path,
) -> None:
    value = library()
    pretty = tmp_path / "pretty.json"
    pretty.write_text(json.dumps(value, indent=2), encoding="utf-8")
    with pytest.raises(HypothesisLibraryError, match="not canonical"):
        load_library(pretty)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"x":1,"x":2}', encoding="utf-8")
    with pytest.raises(HypothesisLibraryError, match="duplicate keys"):
        load_library(duplicate)

    link = tmp_path / "library-link.json"
    link.symlink_to(LIBRARY_PATH)
    with pytest.raises(HypothesisLibraryError, match="unsafe"):
        load_library(link)


def test_finalization_is_idempotent_and_does_not_depend_on_mapping_order() -> None:
    value = library()
    reversed_value = dict(reversed(list(value.items())))
    assert finalize_identities(value) == value
    assert finalize_identities(reversed_value) == value


def test_cli_is_deterministic_across_hash_seeds_and_timezones() -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts/validate_benchmark_hypothesis_library_v001.py"),
        "--library",
        str(LIBRARY_PATH),
    ]
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "Asia/Tokyo")):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT / "src"),
                "PYTHONHASHSEED": seed,
                "TZ": timezone,
            },
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["library_identity"] == EXPECTED_LIBRARY_IDENTITY


def test_library_does_not_modify_or_reverse_import_frozen_downstream_components() -> None:
    frozen_paths = (
        "src/aml/discovery_screen_v001.py",
        "src/aml/portfolio_simulator.py",
        "src/aml/professional_strategy_executors_v001.py",
        "src/aml/professional_strategy_lifecycle_v001.py",
    )
    for relative in frozen_paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "benchmark_hypothesis_library_v001" not in text
    new_source = (ROOT / "src/aml/benchmark_hypothesis_library_v001.py").read_text(
        encoding="utf-8"
    )
    for prohibited in (
        "submit_order",
        "TradingClient",
        "professional_strategy_olympics_orchestrator",
        "validation_extension",
        "holdout_artifact",
    ):
        assert prohibited not in new_source
