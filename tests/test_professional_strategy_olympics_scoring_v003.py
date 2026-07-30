from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_scoring_v003 import (
    BASE_COMMIT,
    CAPITAL_GOVERNANCE_IDENTITY,
    EXECUTOR_IDENTITIES,
    EXECUTOR_LAYER_IDENTITIES,
    FROZEN_EVENT_TIE_FIELDS,
    REASON_MISSING,
    REASON_NONFINITE,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    V001_IDENTITIES,
    V002_IDENTITIES,
    OlympicsScoringV003Error,
    SyntheticCompetitor,
    SyntheticOverallTieRecord,
    TieField,
    canonical_bundle_bytes,
    load_bundle,
    normalize_synthetic_timestamp,
    order_synthetic_overall_ties,
    rank_synthetic_cohort,
    validate_bundle,
    validate_repository_lineage,
)
from aml.winner_archetype_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config/professional_strategy_olympics_scoring_v003.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_scoring_v003.py"
BUNDLE = load_bundle(PATH)


def identity(number: int) -> str:
    return f"{number:064x}"


def competitor(number: int, raw_value, *tie_values) -> SyntheticCompetitor:
    return SyntheticCompetitor(identity(number), raw_value, tuple(tie_values))


def reidentify(value: dict[str, object], field: str) -> None:
    value[field] = canonical_hash({key: item for key, item in value.items() if key != field})


def fraction(record, prefix: str) -> Fraction:
    return Fraction(
        getattr(record, f"{prefix}_numerator"),
        getattr(record, f"{prefix}_denominator"),
    )


def test_v003_identities_are_frozen():
    assert BUNDLE["schema_contract"]["schema_identity"] == "c9b56222811d521da8b7516100a7067476b6d86868488ad8cc37b780b31fa042"
    assert BUNDLE["scoring_clarification"]["scoring_clarification_identity"] == "666baa8a9ff365de9dd04ee4f95dd5a37f67e19f05738d29e7c9d0622999497c"
    assert BUNDLE["validation_manifest"]["validation_identity"] == "4119376a03c8896e97fb8431cd8b8823c39049c462fa880fd54cad58137775e2"
    assert BUNDLE["bundle_identity"] == "7f1656ffbd4e577dd1b58019b67a50a48acf0be1d8a05646c8066758644eae81"


def test_all_prior_lineage_is_exact():
    lineage = BUNDLE["historical_lineage"]
    assert lineage["design_base_commit"] == BASE_COMMIT
    assert {key: lineage[key] for key in V001_IDENTITIES} == V001_IDENTITIES
    assert {key: lineage[key] for key in V002_IDENTITIES} == V002_IDENTITIES
    assert lineage["capital_governance_identity"] == CAPITAL_GOVERNANCE_IDENTITY
    assert {key: lineage[key] for key in EXECUTOR_LAYER_IDENTITIES} == EXECUTOR_LAYER_IDENTITIES
    assert tuple(lineage["executor_identities"]) == EXECUTOR_IDENTITIES
    assert (lineage["immutable_tag_name"], lineage["immutable_tag_object"], lineage["immutable_tagged_commit"]) == (TAG_NAME, TAG_OBJECT, TAGGED_COMMIT)


def test_all_fifteen_existing_event_tie_fields_are_machine_bound():
    bindings = BUNDLE["scoring_clarification"]["tie_behavior"]["event_tie_fields"]
    assert bindings == FROZEN_EVENT_TIE_FIELDS
    assert len(bindings) == 15
    assert all(len(fields) == 1 for fields in bindings.values())


def test_repository_lineage_and_immutable_tag_validate():
    assert validate_repository_lineage(ROOT)["bundle_identity"] == BUNDLE["bundle_identity"]


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("schema_contract", "schema_identity"),
        ("scoring_clarification", "scoring_clarification_identity"),
        ("validation_manifest", "validation_identity"),
    ],
)
def test_nested_identity_tampering_fails(section, field):
    changed = deepcopy(BUNDLE)
    changed[section]["tampered"] = True
    reidentify(changed, "bundle_identity")
    with pytest.raises(OlympicsScoringV003Error, match=field):
        validate_bundle(changed)


def test_bundle_identity_tampering_fails():
    changed = deepcopy(BUNDLE)
    changed["prospective_as_of"] = "2026-07-31T00:00:00Z"
    with pytest.raises(OlympicsScoringV003Error, match="bundle_identity"):
        validate_bundle(changed)


def test_n_two_has_inclusive_endpoints_and_exact_scores():
    result = rank_synthetic_cohort(
        [competitor(1, 2), competitor(2, 9)], direction="higher_is_better"
    )
    assert [item.ordinal_rank for item in result.eligible] == [1, 2]
    assert [fraction(item, "percentile") for item in result.eligible] == [0, 1]
    assert [fraction(item, "event_score") for item in result.eligible] == [0, 100]


def test_n_three_has_exact_midpoint():
    result = rank_synthetic_cohort(
        [competitor(1, 2), competitor(2, 5), competitor(3, 9)],
        direction="higher_is_better",
    )
    assert [fraction(item, "percentile") for item in result.eligible] == [
        Fraction(0),
        Fraction(1, 2),
        Fraction(1),
    ]
    assert [fraction(item, "event_score") for item in result.eligible] == [0, 50, 100]


def test_larger_cohort_uses_exact_reduced_rationals():
    result = rank_synthetic_cohort(
        [competitor(index, index) for index in range(1, 8)],
        direction="higher_is_better",
    )
    assert [fraction(item, "percentile") for item in result.eligible] == [
        Fraction(index, 6) for index in range(7)
    ]
    assert fraction(result.eligible[2], "event_score") == Fraction(100, 3)


def test_singleton_is_neutral():
    result = rank_synthetic_cohort([competitor(1, 7)], direction="higher_is_better")
    assert len(result.eligible) == 1
    assert fraction(result.eligible[0], "percentile") == Fraction(1, 2)
    assert fraction(result.eligible[0], "event_score") == 50


def test_empty_cohort_produces_no_ranking():
    result = rank_synthetic_cohort([], direction="higher_is_better")
    assert result.eligible == ()
    assert result.ineligible == ()


def test_higher_is_better_and_input_order_independence():
    values = [competitor(3, 9), competitor(1, 2), competitor(2, 5)]
    forward = rank_synthetic_cohort(values, direction="higher_is_better")
    reverse = rank_synthetic_cohort(list(reversed(values)), direction="higher_is_better")
    assert forward == reverse
    assert [item.strategy_identity for item in forward.eligible] == [identity(1), identity(2), identity(3)]


def test_lower_is_better_reverses_comparison_without_mutating_raw_values():
    values = [competitor(1, 2), competitor(2, 5), competitor(3, 9)]
    result = rank_synthetic_cohort(values, direction="lower_is_better")
    assert [item.strategy_identity for item in result.eligible] == [identity(3), identity(2), identity(1)]
    assert [item.raw_value for item in result.eligible] == [9, 5, 2]
    assert [item.raw_value for item in values] == [2, 5, 9]


def test_first_event_specific_tie_field_resolves_raw_tie():
    result = rank_synthetic_cohort(
        [competitor(1, 5, 2), competitor(2, 5, 4)],
        direction="higher_is_better",
        tie_fields=[TieField("drawdown", "lower_is_better")],
    )
    assert [item.strategy_identity for item in result.eligible] == [identity(2), identity(1)]


def test_multiple_event_specific_tie_fields_use_declared_order():
    result = rank_synthetic_cohort(
        [competitor(1, 5, 2, 8), competitor(2, 5, 2, 3), competitor(3, 5, 4, 1)],
        direction="higher_is_better",
        tie_fields=[
            TieField("first", "higher_is_better"),
            TieField("second", "lower_is_better"),
        ],
    )
    assert [item.strategy_identity for item in result.eligible] == [identity(1), identity(2), identity(3)]


def test_identity_is_final_bytewise_tie_key_and_ranks_are_unique():
    result = rank_synthetic_cohort(
        [competitor(16, 5, "same"), competitor(15, 5, "same")],
        direction="higher_is_better",
        tie_fields=[TieField("label", "lexicographic_ascending")],
    )
    assert [item.strategy_identity for item in result.eligible] == [identity(15), identity(16)]
    assert [item.ordinal_rank for item in result.eligible] == [1, 2]
    prohibited = BUNDLE["scoring_clarification"]["favorability_ordering"]["prohibited_rank_methods"]
    assert {"average", "competition", "dense"} <= set(prohibited)


@pytest.mark.parametrize(
    ("value", "reason"),
    [(None, REASON_MISSING), (float("nan"), REASON_NONFINITE), (float("inf"), REASON_NONFINITE), (float("-inf"), REASON_NONFINITE)],
)
def test_missing_and_nonfinite_values_are_ineligible(value, reason):
    result = rank_synthetic_cohort(
        [competitor(1, 5), competitor(2, value)], direction="higher_is_better"
    )
    assert len(result.eligible) == 1
    assert result.eligible[0].eligible_cohort_size == 1
    assert fraction(result.eligible[0], "event_score") == 50
    assert result.ineligible[0].reason_code == reason
    assert result.ineligible[0].assigned_event_score_numerator == 0
    assert result.ineligible[0].assigned_event_score_denominator == 1


def test_missing_tie_value_is_ineligible_and_excluded_from_denominator():
    result = rank_synthetic_cohort(
        [competitor(1, 5, 2), competitor(2, 5)],
        direction="higher_is_better",
        tie_fields=[TieField("tie", "higher_is_better")],
    )
    assert result.eligible[0].eligible_cohort_size == 1
    assert result.ineligible[0].reason_code == REASON_MISSING


def test_duplicate_and_invalid_identities_fail_integrity():
    with pytest.raises(OlympicsScoringV003Error, match="DUPLICATE"):
        rank_synthetic_cohort(
            [competitor(1, 1), competitor(1, 2)], direction="higher_is_better"
        )
    with pytest.raises(OlympicsScoringV003Error, match="INVALID"):
        rank_synthetic_cohort(
            [SyntheticCompetitor("not-an-identity", 1)], direction="higher_is_better"
        )


def test_randomized_input_order_is_deterministic():
    source = [competitor(index, index % 3, index % 2) for index in range(1, 10)]
    expected = rank_synthetic_cohort(
        source,
        direction="higher_is_better",
        tie_fields=[TieField("tie", "higher_is_better")],
    )
    for seed in range(10):
        shuffled = list(source)
        random.Random(seed).shuffle(shuffled)
        assert rank_synthetic_cohort(
            shuffled,
            direction="higher_is_better",
            tie_fields=[TieField("tie", "higher_is_better")],
        ) == expected


def test_discovery_only_skips_both_unopened_future_stages():
    records = [
        SyntheticOverallTieRecord(identity(2), 4, validation_net_expectancy=999, holdout_net_expectancy=999),
        SyntheticOverallTieRecord(identity(1), 2, validation_net_expectancy=-999, holdout_net_expectancy=-999),
    ]
    assert order_synthetic_overall_ties(records) == (identity(1), identity(2))


def test_discovery_drawdown_then_identity_resolve_tie():
    records = [
        SyntheticOverallTieRecord(identity(2), 2),
        SyntheticOverallTieRecord(identity(1), 2),
        SyntheticOverallTieRecord(identity(3), 4),
    ]
    assert order_synthetic_overall_ties(records) == (identity(1), identity(2), identity(3))


def test_opened_validation_and_holdout_values_participate_in_frozen_order():
    records = [
        SyntheticOverallTieRecord(identity(1), 1, 2, 9),
        SyntheticOverallTieRecord(identity(2), 9, 3, 1),
    ]
    assert order_synthetic_overall_ties(records, opened_stages=frozenset({"discovery", "validation"})) == (identity(2), identity(1))
    assert order_synthetic_overall_ties(records, opened_stages=frozenset({"discovery", "validation", "holdout"})) == (identity(2), identity(1))

    holdout_decides = [
        SyntheticOverallTieRecord(identity(1), 1, 2, 9),
        SyntheticOverallTieRecord(identity(2), 1, 2, 1),
    ]
    assert order_synthetic_overall_ties(
        holdout_decides,
        opened_stages=frozenset({"discovery", "validation", "holdout"}),
    ) == (identity(1), identity(2))


def test_opened_future_stage_requires_finite_values_for_every_competitor():
    records = [SyntheticOverallTieRecord(identity(1), 1)]
    with pytest.raises(OlympicsScoringV003Error, match="validation"):
        order_synthetic_overall_ties(
            records, opened_stages=frozenset({"discovery", "validation"})
        )
    holdout_missing = [SyntheticOverallTieRecord(identity(1), 1, 2)]
    with pytest.raises(OlympicsScoringV003Error, match="holdout"):
        order_synthetic_overall_ties(
            holdout_missing,
            opened_stages=frozenset({"discovery", "validation", "holdout"}),
        )


def test_future_stages_cannot_open_out_of_order():
    records = [SyntheticOverallTieRecord(identity(1), 1, 2, 3)]
    with pytest.raises(OlympicsScoringV003Error, match="Opened stages"):
        order_synthetic_overall_ties(
            records, opened_stages=frozenset({"discovery", "holdout"})
        )


def test_contract_freezes_utc_stable_bytewise_ordering_and_no_authority():
    ordering = BUNDLE["scoring_clarification"]["deterministic_ordering"]
    assert ordering["sort_algorithm_requirement"] == "stable_ascending"
    assert ordering["pre_sort_order"] == "canonical_registry_order"
    assert ordering["timestamps"] == "normalize_to_utc_before_comparison"
    assert ordering["text"] == "canonical_utf8_bytes"
    assert all(value is False for value in BUNDLE["authorization"].values())
    assert BUNDLE["validation_manifest"]["official_run_authorized"] is False


def test_equivalent_synthetic_offsets_normalize_to_identical_utc_timestamp():
    assert normalize_synthetic_timestamp("2030-01-02T12:00:00-05:00") == "2030-01-02T17:00:00Z"
    assert normalize_synthetic_timestamp("2030-01-02T09:00:00-08:00") == "2030-01-02T17:00:00Z"
    with pytest.raises(OlympicsScoringV003Error, match="timezone"):
        normalize_synthetic_timestamp("2030-01-02T17:00:00")


def run_validator(seed: str, timezone: str, language: str = "C"):
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "LANG": language,
            "LC_ALL": "C",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
    )


def test_hashseed_timezone_and_locale_independence():
    outputs = [
        run_validator("1", "UTC"),
        run_validator("987654", "UTC"),
        run_validator("1", "America/New_York"),
        run_validator("987654", "America/New_York"),
        run_validator("1", "UTC", "en_US.UTF-8"),
    ]
    assert {item.returncode for item in outputs} == {0}
    assert len({item.stdout for item in outputs}) == 1
    assert outputs[0].stdout == canonical_bundle_bytes(BUNDLE)
    assert all(item.stderr == b"" for item in outputs)


def test_design_scope_contains_no_runner_or_official_artifacts():
    scope = BUNDLE["scoring_clarification"]["scope"]
    assert scope["contract_only"] is True
    assert scope["tournament_runner_implemented"] is False
    assert scope["empirical_data_accessed"] is False
    assert scope["official_scores_created"] is False
    assert scope["rankings_created"] is False
    assert scope["medals_created"] is False
    assert scope["winners_created"] is False
