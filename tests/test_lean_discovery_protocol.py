from copy import deepcopy
import inspect
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.lean_discovery_protocol import (
    ARTIFACT_NAMESPACE,
    REQUIRED_EVIDENCE,
    LeanProtocolError,
    authorize_discovery_path,
    build_readiness,
    canonical_protocol_bytes,
    cost_plan,
    load_protocol,
    resolve_selection_only_horizon,
    validate_claim_text,
    validate_protocol,
)
from aml.winner_archetype_contracts import canonical_json


ROOT = Path(__file__).parents[1]
PROTOCOL_PATH = ROOT / "config/lean_discovery_protocol_v001.json"
READINESS_PATH = ROOT / "config/lean_discovery_readiness_v001.json"
SESSION_PATH = ROOT / "config/winner_archetype_session_plan_v002.json"
CLI = ROOT / "scripts/plan_lean_discovery_v001.py"
PROTOCOL = load_protocol(PROTOCOL_PATH)
SESSIONS = [item["session"] for item in json.loads(SESSION_PATH.read_text())["selection_sessions"]]


def test_tracked_protocol_and_readiness_are_canonical_identity_bound_and_blocked():
    assert PROTOCOL["protocol_identity"] == (
        "52b42287f6cd7ee6404a64ece074b8bca80f75967195c2c944e48d1b26f66fa5"
    )
    assert canonical_protocol_bytes(PROTOCOL_PATH) == canonical_json(PROTOCOL)
    readiness = build_readiness(PROTOCOL)
    assert json.loads(READINESS_PATH.read_text()) == readiness
    assert readiness["readiness_identity"] == (
        "867338c763d77c55690809d18e322b07008ce0bf3f3da2bfaf20d9979e148e12"
    )
    assert readiness["status"] == "blocked"
    assert readiness["pilot_authorized"] is False
    assert readiness["maximum_claim_level"] == 0


def test_v002_is_bound_without_readiness_credit_or_mutation():
    independence = PROTOCOL["independence"]
    assert independence["v002_protocol_identity"] == (
        "11dc7d4af498dc61f166c6d5a4edc72d0038279cd9782d2584a54ac40348e580"
    )
    assert independence["v002_readiness_identity"] == (
        "01fb43fca4cc138277c8e105cc2d071e918db826e62ce78d3b6767b010d8d1b6"
    )
    assert independence["v002_readiness_credit"] == "none"
    assert independence["v002_mutation"] == "prohibited"


def test_session_candidates_are_hash_bound_and_partitions_are_independent():
    cohort = PROTOCOL["calendar_and_cohort"]
    plan = json.loads(SESSION_PATH.read_text())
    assert cohort["session_plan_identity"] == plan["manifest_identity"]
    assert cohort["selection_sessions_sha256"] == plan["component_hashes"]["selection_sessions_sha256"]
    assert len(SESSIONS) == cohort["candidate_session_count"] == 252
    assert cohort["partition_basis_points"] == {
        "discovery": 5000, "validation": 2500, "holdout": 2500
    }


def test_selection_only_horizon_stops_at_first_qualifying_plan():
    counts = [2] * len(SESSIONS)
    resolved = resolve_selection_only_horizon(PROTOCOL, SESSIONS, counts)
    assert resolved["cohort_session_count"] == 60
    assert resolved["partition_counts"] == {
        "discovery": 60, "validation": 30, "holdout": 30, "total": 120
    }
    assert resolved["boundaries"] == {
        "discovery": ["2024-06-03", "2024-07-16"],
        "validation": ["2024-07-17", "2024-08-06"],
        "holdout": ["2024-08-07", "2024-08-27"],
    }
    assert resolved["outcomes_opened"] is False


def test_selection_only_horizon_extends_without_outcome_inputs():
    counts = [1] * 60 + [3] * (len(SESSIONS) - 60)
    resolved = resolve_selection_only_horizon(PROTOCOL, SESSIONS, counts)
    assert resolved["cohort_session_count"] == 120
    assert set(inspect.signature(resolve_selection_only_horizon).parameters) == {
        "protocol", "sessions", "candidate_counts"
    }


@pytest.mark.parametrize(
    "sessions,counts,message",
    (
        (SESSIONS[:-1], [2] * 251, "every bound"),
        (list(reversed(SESSIONS)), [2] * 252, "sorted"),
        (SESSIONS, [2] * 251 + [-1], "non-negative"),
        (SESSIONS, [0] * 252, "Maximum horizon"),
    ),
)
def test_selection_only_horizon_fails_closed(sessions, counts, message):
    with pytest.raises(LeanProtocolError, match=message):
        resolve_selection_only_horizon(PROTOCOL, sessions, counts)


def test_readiness_requires_every_evidence_and_never_self_authorizes_execution():
    digest = "a" * 64
    almost = {key: digest for key in REQUIRED_EVIDENCE if key != "human_authorization"}
    assert build_readiness(PROTOCOL, almost)["pilot_authorized"] is False
    complete = {key: digest for key in REQUIRED_EVIDENCE}
    complete_state = build_readiness(PROTOCOL, complete)
    assert complete_state["status"] == "evidence_complete_execution_not_implemented"
    assert complete_state["pilot_authorized"] is False
    assert complete_state["empirical_data_opened"] is False


def test_readiness_rejects_unknown_or_malformed_evidence():
    with pytest.raises(LeanProtocolError, match="unexpected"):
        build_readiness(PROTOCOL, {"not_registered": "a" * 64})
    with pytest.raises(LeanProtocolError, match="SHA-256"):
        build_readiness(PROTOCOL, {"code_identity": "bad"})


def test_tampering_identity_version_partition_or_authorization_fails_closed():
    mutations = []
    changed = deepcopy(PROTOCOL)
    changed["scientific_question"] += " changed"
    mutations.append(changed)
    changed = deepcopy(PROTOCOL)
    changed["protocol_version"] = "lean-discovery-protocol-v002"
    mutations.append(changed)
    changed = deepcopy(PROTOCOL)
    changed["calendar_and_cohort"]["partition_basis_points"]["holdout"] = 0
    mutations.append(changed)
    changed = deepcopy(PROTOCOL)
    changed["authorization"]["pilot_authorized"] = True
    mutations.append(changed)
    for mutation in mutations:
        with pytest.raises(LeanProtocolError):
            validate_protocol(mutation)


def test_nonfinite_duplicate_key_invalid_unicode_and_oversize_inputs_fail(tmp_path):
    invalids = (
        '{"schema_version": NaN}',
        '{"schema_version":"a","schema_version":"b"}',
        '{"schema_version":"bad\\u0000text"}',
    )
    for index, text in enumerate(invalids):
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(LeanProtocolError):
            load_protocol(path)
    large = tmp_path / "large.json"
    large.write_text(" " * 1_000_001, encoding="utf-8")
    with pytest.raises(LeanProtocolError, match="oversized"):
        load_protocol(large)
    with pytest.raises(ValueError):
        canonical_json({"value": math.inf})


def test_feature_and_outcome_windows_are_cutoff_bound_and_compact():
    assert len(PROTOCOL["feature_registry"]) == 10
    assert len(PROTOCOL["outcome_registry"]) == 6
    for feature in PROTOCOL["feature_registry"]:
        assert feature["observation_window"]
        assert feature["cutoff"]
        assert feature["missing_rule"]
    assert PROTOCOL["statistical_plan"]["primary_outcome"] == "reward_before_risk_determinate_binary"
    assert PROTOCOL["statistical_plan"]["multiple_testing"].startswith("Holm_")


def test_same_bar_missing_data_and_clustered_inference_are_frozen():
    plan = PROTOCOL["statistical_plan"]
    assert plan["resampling"] == {
        "seed": 20260730,
        "date_cluster_bootstrap_replicates": 5000,
        "ordinary_trade_bootstrap": "comparison_only_not_inference",
        "date_cluster_permutation_replicates": 10000,
    }
    assert plan["same_bar_sensitivity"][0] == "exclude_indeterminate_primary"
    assert PROTOCOL["missing_data"]["general"].startswith("no_forward_fill")


@pytest.mark.parametrize(
    "level,text,allowed",
    (
        (3, "A preliminary descriptive pattern was observed.", True),
        (3, "This is a validated predictive effect.", False),
        (5, "The provider-bounded pattern was validated once.", True),
        (5, "The holdout confirmed the result.", False),
        (6, "The one-time holdout was completed.", True),
        (8, "This is a proven edge and production ready.", False),
    ),
)
def test_claim_ladder_prevents_overstatement(level, text, allowed):
    if allowed:
        validate_claim_text(level, text)
    else:
        with pytest.raises(LeanProtocolError):
            validate_claim_text(level, text)


@pytest.mark.parametrize("protected", ("validation", "holdout", "sealed", "production"))
def test_discovery_path_rejects_protected_partitions(protected, tmp_path):
    with pytest.raises(LeanProtocolError, match="protected"):
        authorize_discovery_path(Path(ARTIFACT_NAMESPACE) / protected / "result.json", tmp_path)


def test_discovery_path_rejects_traversal_escape_and_symlink(tmp_path):
    with pytest.raises(LeanProtocolError, match="traversal"):
        authorize_discovery_path(Path("../outside.json"), tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError:
        return
    with pytest.raises(LeanProtocolError, match="symlink"):
        authorize_discovery_path(linked / "result.json", tmp_path)


def test_discovery_path_requires_dedicated_namespace(tmp_path):
    allowed = Path(ARTIFACT_NAMESPACE) / "discovery" / "manifest.json"
    assert authorize_discovery_path(allowed, tmp_path) == tmp_path / allowed
    with pytest.raises(LeanProtocolError, match="namespace"):
        authorize_discovery_path(Path("artifacts/v002/result.json"), tmp_path)


def test_cost_plan_is_bounded_arithmetic_and_zero_cost_is_conditional():
    plan = cost_plan(PROTOCOL)
    assert plan["expected_bar_records"] == 9000 * 80 * 715
    assert plan["estimated_bar_page_calls"] == math.ceil(514_800_000 / 10_000)
    assert plan["estimated_total_api_calls"] == 52_000
    assert plan["recommended_free_local_storage_bytes"] == 60_000_000_000
    assert plan["incremental_provider_cost_usd"] == 0
    assert plan["incremental_cost_condition"].startswith("zero_only_if")


def test_cli_is_hashseed_timezone_and_working_directory_deterministic(tmp_path):
    outputs = []
    for seed, timezone in (("1", "UTC"), ("777", "America/New_York")):
        environment = os.environ.copy()
        environment.update(PYTHONHASHSEED=seed, TZ=timezone, PYTHONPATH=str(ROOT / "src"))
        result = subprocess.run(
            [sys.executable, str(CLI), "validate"],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["protocol_identity"] == PROTOCOL["protocol_identity"]


def test_cli_readiness_is_blocked_and_has_no_execution_or_data_command():
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, str(CLI), "readiness"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["pilot_authorized"] is False
    source = CLI.read_text(encoding="utf-8").casefold()
    for prohibited in ("run-pilot", "download", "ingest", "place_order", "paper order"):
        assert prohibited not in source


def test_lean_layer_has_no_network_client_or_order_capability():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/aml/lean_discovery_protocol.py", CLI)
    ).casefold()
    for prohibited in (
        "import requests", "import httpx", "import socket", "urllib.request",
        "alpaca_trade_api", "place_order", "submit_order",
    ):
        assert prohibited not in sources


def test_production_modules_do_not_import_lean_research_layer():
    protected = (
        "signals.py", "trade_simulator.py", "portfolio_simulator.py",
        "tournament_strategies.py", "tournament_runner.py", "forward_validation.py",
        "validation_extension.py", "operator.py",
    )
    for name in protected:
        path = ROOT / "src/aml" / name
        if path.exists():
            assert "lean_discovery" not in path.read_text(encoding="utf-8")
