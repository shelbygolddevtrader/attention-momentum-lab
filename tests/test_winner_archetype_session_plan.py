from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.winner_archetype_session_plan import (
    SessionPlanError,
    build_session_plan,
    canonical_session_plan_bytes,
    load_session_plan,
    protocol_file_sha256,
    validate_session_plan,
)
from aml.winner_archetype_v002 import load_protocol_v002


ROOT = Path(__file__).parents[1]
PROTOCOL_PATH = ROOT / "config/winner_archetype_protocol_v002.json"
MANIFEST_PATH = ROOT / "config/winner_archetype_session_plan_v002.json"
CLI = ROOT / "scripts/publish_winner_archetype_session_plan_v002.py"
PROTOCOL = load_protocol_v002(PROTOCOL_PATH)
PROTOCOL_HASH = protocol_file_sha256(PROTOCOL_PATH)


def manifest():
    return build_session_plan(PROTOCOL, protocol_file_hash=PROTOCOL_HASH)


def test_tracked_manifest_is_canonical_and_identity_bound():
    loaded = load_session_plan(MANIFEST_PATH, PROTOCOL_PATH)
    assert MANIFEST_PATH.read_bytes() == canonical_session_plan_bytes(PROTOCOL_PATH)
    assert loaded["protocol_identity"] == PROTOCOL.identity
    assert loaded["protocol_file_sha256"] == PROTOCOL_HASH
    assert loaded["manifest_identity"] == (
        "167847cf198764f72b76c976a4993f7d8f4a4e262d4dc53018ec9317c7d6196c"
    )
    assert loaded["pilot_authorized"] is False
    assert loaded["empirical_data_opened"] is False


def test_calendar_sessions_holidays_early_closes_and_ad_hoc_closure():
    value = manifest()
    sessions = {item["session"]: item for item in value["selection_sessions"]}
    excluded = {item["date"]: item["classification"] for item in value["excluded_calendar_dates"]}
    assert "2024-07-04" not in sessions
    assert excluded["2024-07-04"] == "holiday"
    assert excluded["2025-01-09"] == "ad_hoc_closure"
    assert sessions["2024-07-03"]["early_close"] is True
    assert sessions["2024-07-03"]["scheduled_close"].endswith("13:00:00-04:00")
    assert sum(item["early_close"] for item in sessions.values()) == 3


def test_dst_offsets_change_without_changing_local_cutoff_or_open():
    sessions = {item["session"]: item for item in manifest()["selection_sessions"]}
    summer = sessions["2024-06-03"]
    winter = sessions["2024-11-04"]
    assert summer["selection_cutoff"].endswith("09:25:00-04:00")
    assert winter["selection_cutoff"].endswith("09:25:00-05:00")
    assert summer["scheduled_open"].endswith("09:30:00-04:00")
    assert winter["scheduled_open"].endswith("09:30:00-05:00")


def test_sessions_and_partitions_are_ordered_unique_complete_and_isolated():
    value = manifest()
    sessions = [item["session"] for item in value["selection_sessions"]]
    assert len(sessions) == 252
    assert sessions == sorted(set(sessions))
    for plan in value["conditional_partition_plans"]:
        assignments = plan["assignments"]
        discovery = set(assignments["discovery"])
        validation = set(assignments["validation"])
        holdout = set(assignments["holdout"])
        assert not discovery & validation
        assert not discovery & holdout
        assert not validation & holdout
        combined = assignments["discovery"] + assignments["validation"] + assignments["holdout"]
        assert combined == sessions[: plan["cohort_session_count"]]


def test_initial_and_maximum_partition_boundaries_are_exact_but_final_is_unresolved():
    value = manifest()
    initial = value["conditional_partition_plans"][0]
    maximum = value["conditional_partition_plans"][-1]
    assert initial["counts"] == {"discovery": 30, "validation": 15, "holdout": 15}
    assert initial["boundaries"] == {
        "discovery": ["2024-06-03", "2024-07-16"],
        "validation": ["2024-07-17", "2024-08-06"],
        "holdout": ["2024-08-07", "2024-08-27"],
    }
    assert maximum["counts"] == {"discovery": 126, "validation": 63, "holdout": 63}
    assert maximum["boundaries"] == {
        "discovery": ["2024-06-03", "2024-11-29"],
        "validation": ["2024-12-02", "2025-03-05"],
        "holdout": ["2025-03-06", "2025-06-04"],
    }
    assert value["final_cohort_status"].startswith("unresolved")
    assert value["final_partition_identity"] is None


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value["selection_sessions"].__setitem__(1, value["selection_sessions"][0]),
        lambda value: value["conditional_partition_plans"][0]["assignments"]["holdout"].append("2024-06-03"),
        lambda value: value["calendar"].__setitem__("provider_version", "4.13.3"),
        lambda value: value.__setitem__("protocol_identity", "0" * 64),
    ),
)
def test_tampered_duplicate_conflicting_or_identity_drifted_manifest_fails(mutation):
    value = deepcopy(manifest())
    mutation(value)
    with pytest.raises(SessionPlanError, match="tampered"):
        validate_session_plan(value, PROTOCOL, PROTOCOL_HASH)


def test_conflicting_closure_evidence_and_bad_protocol_hash_fail_closed():
    with pytest.raises(SessionPlanError, match="Conflicting closure"):
        build_session_plan(
            PROTOCOL,
            protocol_file_hash=PROTOCOL_HASH,
            conflicting_closure_dates=("2025-01-09",),
        )
    with pytest.raises(SessionPlanError, match="SHA-256"):
        build_session_plan(PROTOCOL, protocol_file_hash="bad")


def test_cli_is_hashseed_and_timezone_deterministic_and_writes_nothing(tmp_path):
    outputs = []
    for seed in ("1", "777"):
        for timezone in ("UTC", "America/New_York"):
            environment = os.environ.copy()
            environment.update(PYTHONHASHSEED=seed, TZ=timezone, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(
                [sys.executable, str(CLI)],
                cwd=tmp_path,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            outputs.append(result.stdout)
    assert len(set(outputs)) == 1
    assert json.loads(outputs[0])["manifest_identity"] == manifest()["manifest_identity"]


@pytest.mark.parametrize("protected", ("validation", "holdout", "sealed", "production"))
def test_publisher_cannot_write_into_protected_partitions(protected):
    result = subprocess.run(
        [sys.executable, str(CLI), "--output", f"{protected}/plan.json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "protected" in result.stderr
