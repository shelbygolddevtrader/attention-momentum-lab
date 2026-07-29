from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from aml.winner_archetype_contracts import WinnerArchetypeError, load_experiment_spec
from aml.winner_archetype_execution import (
    DISCOVERY_INPUT_SCHEMA,
    DiscoveryInputBinding,
    build_discovery_readiness_plan,
    load_discovery_input_binding,
)


ROOT = Path(__file__).parents[1]
SPEC_PATH = ROOT / "config/winner_archetype_experiment_v001.json"
SPEC = load_experiment_spec(SPEC_PATH)


def binding_mapping(**changes):
    value = {
        "schema_version": DISCOVERY_INPUT_SCHEMA,
        "experiment_identity": SPEC.identity,
        "phase": "discovery",
        "provider": "provider-neutral-test",
        "feed": "sip",
        "entitlement_plan": "licensed-test-plan",
        "retrieval_timestamp": "2026-07-29T12:00:00+00:00",
        "normalization_version": "normalization-v001",
        "timezone": "America/New_York",
        "universe_definition_id": "point-in-time-universe-v001",
        "universe_manifest_sha256": "1" * 64,
        "security_master_manifest_sha256": "2" * 64,
        "calendar_manifest_sha256": "3" * 64,
        "market_bars_manifest_sha256": "4" * 64,
        "quotes_manifest_sha256": "5" * 64,
        "catalyst_registry_manifest_sha256": "6" * 64,
        "halt_registry_manifest_sha256": "7" * 64,
        "corporate_actions_manifest_sha256": "8" * 64,
        "raw_payload_sha256": ["9" * 64],
        "normalized_record_sha256": ["a" * 64],
    }
    value.update(changes)
    return value


def load_mapping(value):
    return DiscoveryInputBinding.from_mapping(
        value,
        expected_experiment_identity=SPEC.identity,
        as_of=datetime(2026, 7, 29, 13, tzinfo=timezone.utc),
    )


def test_readiness_plan_is_deterministic_and_matches_frozen_identity():
    first = build_discovery_readiness_plan(SPEC_PATH)
    second = build_discovery_readiness_plan(SPEC_PATH)
    assert first == second
    assert first["experiment_identity"] == (
        "f72e8f7f9b1e19dac707f941dc09ec30e19e4e2260ea57454f3ffc7fc19d520a"
    )
    assert first["selection_session_count"] == 252
    assert first["selection_end"] == "2025-06-04"
    assert first["pilot_authorized"] is False
    assert first["outcome_access_performed"] is False
    assert first["status"] == "blocked_protocol_revision_required"
    assert first["conditional_discovery_partitions"][0] == {
        "cohort_session_count": 60,
        "discovery_session_count": 30,
        "discovery_start": "2024-06-03",
        "discovery_end": "2024-07-16",
        "partition_plan_id": (
            "c41887f94e1e728057d00ca8935e15ddd7a08b99dcc218db9e25621d8a87cc5d"
        ),
    }


def test_binding_identity_changes_when_any_bound_input_changes():
    first = load_mapping(binding_mapping())
    second = load_mapping(binding_mapping(quotes_manifest_sha256="b" * 64))
    assert first.identity != second.identity


@pytest.mark.parametrize(
    "change,message",
    [
        ({"phase": "validation"}, "Only discovery"),
        ({"feed": "iex"}, "SIP"),
        ({"experiment_identity": "b" * 64}, "another experiment"),
        ({"retrieval_timestamp": "2026-07-30T00:00:00+00:00"}, "future-dated"),
        ({"quotes_manifest_sha256": "bad"}, "SHA-256"),
        ({"raw_payload_sha256": []}, "non-empty"),
        ({"timezone": "Not/AZone"}, "IANA"),
        ({"provider": "bad\ud800"}, "Unicode"),
    ],
)
def test_binding_fails_closed_for_conflicting_incomplete_or_future_inputs(change, message):
    with pytest.raises(WinnerArchetypeError, match=message):
        load_mapping(binding_mapping(**change))


def test_binding_loader_rejects_protected_paths_and_symlinks(tmp_path):
    protected = tmp_path / "validation" / "binding.json"
    protected.parent.mkdir()
    protected.write_text(json.dumps(binding_mapping()), encoding="utf-8")
    with pytest.raises(WinnerArchetypeError, match="protected"):
        load_discovery_input_binding(
            protected,
            expected_experiment_identity=SPEC.identity,
            as_of=datetime(2026, 7, 29, 13, tzinfo=timezone.utc),
        )
    real = tmp_path / "real"
    real.mkdir()
    (real / "binding.json").write_text(json.dumps(binding_mapping()), encoding="utf-8")
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(WinnerArchetypeError, match="symlink"):
        load_discovery_input_binding(
            linked / "binding.json",
            expected_experiment_identity=SPEC.identity,
            as_of=datetime(2026, 7, 29, 13, tzinfo=timezone.utc),
        )


def test_bound_plan_retains_fail_closed_protocol_gate():
    plan = build_discovery_readiness_plan(SPEC_PATH, input_binding=load_mapping(binding_mapping()))
    assert plan["input_binding_identity"]
    assert plan["pilot_authorized"] is False
    assert plan["blockers"] == ["eligible_universe_definition_not_bound_by_frozen_v001"]
