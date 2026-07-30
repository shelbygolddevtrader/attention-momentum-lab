"""Design-only validation for Olympics scoring clarification V003.

The scalar helpers in this module exist only to prove the frozen equations with
synthetic values. They do not load replay data, execute strategies, or produce
official tournament results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from functools import cmp_to_key
import json
import math
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from aml.winner_archetype_contracts import HASH_PATTERN, canonical_hash, canonical_json


SCHEMA = "aml.professional-strategy-olympics.scoring-clarification-bundle.v003"
VERSION = "professional-strategy-olympics-scoring-clarification-v003"
BASE_COMMIT = "971c0915af7ffddb3ac53c0cde7d2bc6b5638c4d"
TAG_NAME = "v0.1.1-research-baseline"
TAG_OBJECT = "746e147efd9bb09dedfdd4d2850f461e36d9f046"
TAGGED_COMMIT = "378317dba28d93792d2f0a3ab4302a5d0b6abf7c"
V001_IDENTITIES = {
    "v001_protocol_identity": "8a7f4c2ca1c6b133e769992ef8315186de87b0f7f1baedf6d549536db6f72f3e",
    "v001_registry_identity": "af1e44069fd5e226ad702469fdf10c7e0b1c49c803065e20c83588b22e17bbc0",
    "v001_tournament_identity": "10d41bf657759b5db5b5524a18158a480797ab9dcfcca59e7921672d31bb70aa",
    "v001_readiness_identity": "ebe1179fea526e4bad0c808609ff68320840d57d2172355227edfeccaf054602",
}
V002_IDENTITIES = {
    "v002_protocol_identity": "fb4bc0623dab857320b914ad7dcd787cead3e16aaa5bfd486d539e0b8cb24583",
    "v002_indicators_identity": "3d1427872fc8d55e3cacc321f710a6a2b260d0a1d01259147b6ff3a422a6f852",
    "v002_input_schema_identity": "a3fc7f17fb30eaf69ec00f2955f68f1b54dc3247edc54590706abee719ba3fac",
    "v002_lifecycle_identity": "b61fa2557718cdf1dbebc0e91990bb27be3d880111bea424d967dd96253dfe12",
    "v002_cost_model_identity": "ba239ed1b835d91be06a674433559c2b679c07fd37b9820f0c4fe7cf7ada4570",
    "v002_registry_identity": "5a43302ca893bcb9323b0a0b473282abd36d0b4d0917322dfb5c817ca3bfd43a",
    "v002_tournament_identity": "f011b03b6d4b4249e4c4d77b029cbb74145c7f7f53486e0af89d0433da395308",
    "v002_evidence_identity": "36eb12d994052735aa084f56951db088e5b1ef46d4bde856e5eba4e355d43172",
    "v002_unresolved_identity": "1c7e480fdf5a69a7ad4b7af6f78131181b140dbe30ef402c5bd5e5cdeb1bc0bf",
    "v002_readiness_identity": "fb9799d8cda9a671a58408f0d540d7a6ab39fe868163a2ce105eb6f1218de03b",
}
CAPITAL_GOVERNANCE_IDENTITY = (
    "6defde5b21b8aac1a4a1b15c501621163dcb9c400f629abd29b257f7a51073cf"
)
EXECUTOR_IDENTITIES = (
    "38b823d7a0ab80817031f8617911fc5999204d430378ed389075db9399d63fe3",
    "9affc9b5496498c3c1371674af8b7b0e83a4a5d68672e869827cbf35a2babacd",
    "5e3b8f85ba8a0a369cc857b5968afc3b79a3ccdcbe9bb467200a53e80dc38977",
    "96113276af8ab6804e93395d13638a7d3c9a3cffc8a5dc6c6f852c5735726ff3",
    "4b14db53fc64877e9e265f007bc55acd3be6dc42936affaeb9b268aa5cd3ab66",
    "f40119e023331be5326a5589f4b56a7624cfdf5e16d54f429b13d081435c75f8",
    "96609dccbcc4d77c9b4609780825d7033e3edb22f29038a4653a574efd8bfb36",
    "ff91238ec8c878bd528747af4420b6aeb7fb6c45b25fa937c835f44c40faef82",
    "a1b67f9895c21be737c8281cfeb4c5dc2c5c7287ac89df47ba045f182bf0d901",
    "664c980a1ae0e13cfda02b533b064ec42a706e21e57a456d13136f596099ef1d",
)
EXECUTOR_LAYER_IDENTITIES = {
    "executor_protocol_identity": "92572119a8812c87e75587647ff26106f2157023f092ba5cc148863c5d053b4d",
    "shared_indicator_implementation_identity": "807103addda1e011ec5b635916cdcb72f439e970ffe25f50c2ad4a3303e78eda",
    "shared_lifecycle_implementation_identity": "b10c659118861f3818fc2b1f034a2700e055fdcc19bd51651969f660af94e384",
    "executor_registry_identity": "01c0efa7b35707ddbc837609f99051cdc3db63064410de9d10e334d601787111",
    "executor_bundle_identity": "9c03677ce4ea4e56256f6873c00a4cdc502e23b2780f36af6b3f2a0b3b45bf5d",
    "executor_readiness_identity": "9d592af6d58fdf187078b59b41b780c418995dafa72079009e4fbebca62b014a",
}
SECTION_IDENTITIES = {
    "schema_contract": "schema_identity",
    "scoring_clarification": "scoring_clarification_identity",
    "validation_manifest": "validation_identity",
}
REASON_MISSING = "V003_EVENT_INELIGIBLE_MISSING_REQUIRED_VALUE"
REASON_NONFINITE = "V003_EVENT_INELIGIBLE_NON_FINITE_REQUIRED_VALUE"
FROZEN_EVENT_TIE_FIELDS = {
    "net_expectancy": [{"field": "maximum_drawdown", "direction": "lower_is_better"}],
    "downside_adjusted_return": [{"field": "net_expectancy", "direction": "higher_is_better"}],
    "maximum_drawdown": [{"field": "net_expectancy", "direction": "higher_is_better"}],
    "profit_factor": [{"field": "net_expectancy", "direction": "higher_is_better"}],
    "payoff_ratio": [{"field": "hit_rate", "direction": "higher_is_better"}],
    "hit_rate": [{"field": "payoff_ratio", "direction": "higher_is_better"}],
    "tail_loss": [{"field": "maximum_drawdown", "direction": "lower_is_better"}],
    "monthly_stability": [{"field": "active_months", "direction": "higher_is_better"}],
    "regime_stability": [{"field": "median_regime_expectancy", "direction": "higher_is_better"}],
    "validation_consistency": [{"field": "validation_net_expectancy", "direction": "higher_is_better"}],
    "holdout_consistency": [{"field": "holdout_net_expectancy", "direction": "higher_is_better"}],
    "capital_efficiency": [{"field": "capital_constrained_net_expectancy", "direction": "higher_is_better"}],
    "trade_sufficiency": [{"field": "active_dates", "direction": "higher_is_better"}],
    "execution_robustness": [{"field": "two_x_cost_expectancy", "direction": "higher_is_better"}],
    "sensitivity_robustness": [{"field": "expectancy_range", "direction": "lower_is_better"}],
}


class OlympicsScoringV003Error(ValueError):
    """A V003 identity, equation, or research-boundary invariant failed."""


@dataclass(frozen=True)
class TieField:
    """One already-frozen synthetic tie field and its favorability direction."""

    name: str
    direction: str


@dataclass(frozen=True)
class SyntheticCompetitor:
    """Synthetic scalar input used only to prove the V003 ordering contract."""

    strategy_identity: str
    raw_value: int | float | None
    tie_values: tuple[int | float | str | None, ...] = ()


@dataclass(frozen=True)
class SyntheticRankRecord:
    strategy_identity: str
    raw_value: int | float
    ordinal_rank: int
    eligible_cohort_size: int
    percentile_numerator: int
    percentile_denominator: int
    event_score_numerator: int
    event_score_denominator: int


@dataclass(frozen=True)
class SyntheticIneligibleRecord:
    strategy_identity: str
    reason_code: str
    assigned_event_score_numerator: int = 0
    assigned_event_score_denominator: int = 1


@dataclass(frozen=True)
class SyntheticRanking:
    eligible: tuple[SyntheticRankRecord, ...]
    ineligible: tuple[SyntheticIneligibleRecord, ...]


@dataclass(frozen=True)
class SyntheticOverallTieRecord:
    strategy_identity: str
    discovery_maximum_drawdown: int | float
    validation_net_expectancy: int | float | None = None
    holdout_net_expectancy: int | float | None = None


def _strict_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise OlympicsScoringV003Error("V003 bundle is missing or oversized")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OlympicsScoringV003Error("V003 JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                OlympicsScoringV003Error(item)
            ),
        )
        canonical_json(value)
    except OlympicsScoringV003Error:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise OlympicsScoringV003Error("V003 bundle must be strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OlympicsScoringV003Error("V003 bundle root must be an object")
    return value


def _validate_identity(value: Mapping[str, object], field: str) -> str:
    identity = value.get(field)
    if not isinstance(identity, str) or not HASH_PATTERN.fullmatch(identity):
        raise OlympicsScoringV003Error(f"{field} must be a SHA-256 identity")
    payload = {key: item for key, item in value.items() if key != field}
    if canonical_hash(payload) != identity:
        raise OlympicsScoringV003Error(f"{field} is stale or tampered")
    return identity


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise OlympicsScoringV003Error("prospective_as_of must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OlympicsScoringV003Error("prospective_as_of is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OlympicsScoringV003Error("prospective_as_of must include a timezone")


def _assert_exact_contract(value: Mapping[str, object]) -> None:
    clarification = value["scoring_clarification"]
    if clarification["percentile"]["formula"] != "(rank-1)/(n-1)":
        raise OlympicsScoringV003Error("V003 percentile formula changed")
    if clarification["event_score"]["formula"] != "100*percentile":
        raise OlympicsScoringV003Error("V003 event-score formula changed")
    singleton = clarification["eligible_cohort_edges"]["single_competitor"]
    if singleton["percentile"] != {"numerator": 1, "denominator": 2}:
        raise OlympicsScoringV003Error("V003 singleton percentile changed")
    if singleton["event_score"] != {"numerator": 50, "denominator": 1}:
        raise OlympicsScoringV003Error("V003 singleton event score changed")
    ordering = clarification["favorability_ordering"]
    if ordering["rank_definition"] != "one_based_ordinal_position_in_completed_total_order":
        raise OlympicsScoringV003Error("V003 must use unique ordinal positions")
    if ordering["final_key"] != "immutable_strategy_identity_bytewise_utf8_lexicographic_ascending":
        raise OlympicsScoringV003Error("V003 identity ordering changed")
    if clarification["tie_behavior"]["event_tie_fields"] != FROZEN_EVENT_TIE_FIELDS:
        raise OlympicsScoringV003Error("V003 event tie-field bindings changed")
    overall = clarification["discovery_only_overall_ties"]
    if overall["frozen_declared_sequence"] != [
        "validation_net_expectancy",
        "holdout_net_expectancy",
        "lower_maximum_drawdown",
        "lexicographic_strategy_identity",
    ]:
        raise OlympicsScoringV003Error("Frozen overall tie sequence changed")
    if overall["discovery_only_effective_sequence"] != [
        "lower_discovery_maximum_drawdown",
        "immutable_strategy_identity_bytewise_utf8_ascending",
    ]:
        raise OlympicsScoringV003Error("Discovery-only tie reduction changed")
    if any(type(item) is not bool for item in clarification["scope"].values()):
        raise OlympicsScoringV003Error("V003 scope flags are malformed")
    if clarification["scope"] != {
        "contract_only": True,
        "empirical_data_accessed": False,
        "tournament_runner_implemented": False,
        "official_scores_created": False,
        "rankings_created": False,
        "medals_created": False,
        "winners_created": False,
        "validation_opened": False,
        "holdout_opened": False,
        "capital_activated": False,
    }:
        raise OlympicsScoringV003Error("V003 expanded beyond design-only scope")


def validate_bundle(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version",
        "clarification_version",
        "prospective_as_of",
        "bundle_identity",
        "historical_lineage",
        "schema_contract",
        "scoring_clarification",
        "validation_manifest",
        "authorization",
    }
    if set(value) != expected:
        raise OlympicsScoringV003Error("V003 root contains missing or unexpected fields")
    if value["schema_version"] != SCHEMA or value["clarification_version"] != VERSION:
        raise OlympicsScoringV003Error("Unsupported V003 scoring clarification")
    _validate_timestamp(value["prospective_as_of"])
    for section, field in SECTION_IDENTITIES.items():
        if not isinstance(value[section], Mapping):
            raise OlympicsScoringV003Error(f"{section} must be an object")
        _validate_identity(value[section], field)
    validation = value["validation_manifest"]
    if validation["scoring_clarification_identity"] != value["scoring_clarification"]["scoring_clarification_identity"]:
        raise OlympicsScoringV003Error("Validation manifest clarification binding changed")
    if validation["schema_identity"] != value["schema_contract"]["schema_identity"]:
        raise OlympicsScoringV003Error("Validation manifest schema binding changed")
    if validation["status"] != "design_clarification_complete_execution_not_authorized":
        raise OlympicsScoringV003Error("V003 validation status changed")
    authorization = value["authorization"]
    if not isinstance(authorization, Mapping) or not authorization:
        raise OlympicsScoringV003Error("V003 authorization boundary is missing")
    if any(item is not False for item in authorization.values()):
        raise OlympicsScoringV003Error("V003 cannot authorize execution or capital")
    lineage = value["historical_lineage"]
    expected_lineage = {
        "design_base_commit": BASE_COMMIT,
        **V001_IDENTITIES,
        **V002_IDENTITIES,
        "capital_governance_identity": CAPITAL_GOVERNANCE_IDENTITY,
        **EXECUTOR_LAYER_IDENTITIES,
        "executor_identities": list(EXECUTOR_IDENTITIES),
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "lineage_policy": "prospective_clarification_only_prior_contracts_and_implementations_unchanged",
    }
    if lineage != expected_lineage:
        raise OlympicsScoringV003Error("V003 historical lineage changed")
    _assert_exact_contract(value)
    _validate_identity(value, "bundle_identity")
    return dict(value)


def load_bundle(path: Path) -> dict[str, object]:
    return validate_bundle(_strict_json(path))


def canonical_bundle_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_json(validate_bundle(value))


def normalize_synthetic_timestamp(value: str) -> str:
    """Normalize a synthetic aware timestamp for deterministic ordering tests."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise OlympicsScoringV003Error("Synthetic timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OlympicsScoringV003Error("Synthetic timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _number_fraction(value: int | float) -> Fraction:
    return Fraction(str(value))


def _compare_values(left: object, right: object, direction: str) -> int:
    if _finite_number(left) and _finite_number(right):
        left_key: object = _number_fraction(left)
        right_key: object = _number_fraction(right)
    elif isinstance(left, str) and isinstance(right, str):
        left_key = left.encode("utf-8")
        right_key = right.encode("utf-8")
    else:
        raise OlympicsScoringV003Error("Synthetic tie values must have matching types")
    comparison = (left_key > right_key) - (left_key < right_key)
    if direction == "higher_is_better":
        return comparison
    if direction == "lower_is_better":
        return -comparison
    if direction == "lexicographic_ascending":
        return comparison
    raise OlympicsScoringV003Error("Unknown synthetic favorability direction")


def _required_value_reason(value: object) -> str | None:
    if value is None:
        return REASON_MISSING
    if type(value) in {int, float} and not math.isfinite(float(value)):
        return REASON_NONFINITE
    if type(value) not in {int, float, str}:
        return REASON_MISSING
    return None


def _required_numeric_reason(value: object) -> str | None:
    if value is None:
        return REASON_MISSING
    if type(value) not in {int, float}:
        return REASON_MISSING
    if not math.isfinite(float(value)):
        return REASON_NONFINITE
    return None


def rank_synthetic_cohort(
    competitors: Sequence[SyntheticCompetitor],
    *,
    direction: str,
    tie_fields: Sequence[TieField] = (),
) -> SyntheticRanking:
    """Apply V003 to synthetic scalars without any tournament or replay access."""

    if direction not in {"higher_is_better", "lower_is_better"}:
        raise OlympicsScoringV003Error("Unknown event direction")
    identities = [item.strategy_identity for item in competitors]
    if any(not HASH_PATTERN.fullmatch(item) for item in identities):
        raise OlympicsScoringV003Error("V003_INTEGRITY_INVALID_STRATEGY_IDENTITY")
    if len(set(identities)) != len(identities):
        raise OlympicsScoringV003Error("V003_INTEGRITY_DUPLICATE_STRATEGY_IDENTITY")
    if any(field.direction not in {"higher_is_better", "lower_is_better", "lexicographic_ascending"} for field in tie_fields):
        raise OlympicsScoringV003Error("Synthetic tie-field direction is invalid")

    eligible: list[SyntheticCompetitor] = []
    ineligible: list[SyntheticIneligibleRecord] = []
    for competitor in competitors:
        reason = _required_numeric_reason(competitor.raw_value)
        if reason is None:
            reason = next(
                (
                    item
                    for value in competitor.tie_values
                    if (item := _required_value_reason(value)) is not None
                ),
                None,
            )
        if len(competitor.tie_values) != len(tie_fields):
            reason = REASON_MISSING
        if reason is None:
            eligible.append(competitor)
        else:
            ineligible.append(SyntheticIneligibleRecord(competitor.strategy_identity, reason))

    def compare(left: SyntheticCompetitor, right: SyntheticCompetitor) -> int:
        primary = _compare_values(left.raw_value, right.raw_value, direction)
        if primary:
            return primary
        for index, field in enumerate(tie_fields):
            tied = _compare_values(
                left.tie_values[index], right.tie_values[index], field.direction
            )
            if tied:
                return tied
        return (left.strategy_identity.encode("utf-8") > right.strategy_identity.encode("utf-8")) - (
            left.strategy_identity.encode("utf-8") < right.strategy_identity.encode("utf-8")
        )

    ordered = sorted(eligible, key=cmp_to_key(compare))
    size = len(ordered)
    ranked: list[SyntheticRankRecord] = []
    for index, competitor in enumerate(ordered, start=1):
        percentile = Fraction(1, 2) if size == 1 else Fraction(index - 1, size - 1)
        event_score = 100 * percentile
        ranked.append(
            SyntheticRankRecord(
                strategy_identity=competitor.strategy_identity,
                raw_value=competitor.raw_value,
                ordinal_rank=index,
                eligible_cohort_size=size,
                percentile_numerator=percentile.numerator,
                percentile_denominator=percentile.denominator,
                event_score_numerator=event_score.numerator,
                event_score_denominator=event_score.denominator,
            )
        )
    return SyntheticRanking(
        tuple(ranked), tuple(sorted(ineligible, key=lambda item: item.strategy_identity.encode("utf-8")))
    )


def order_synthetic_overall_ties(
    competitors: Sequence[SyntheticOverallTieRecord],
    *,
    opened_stages: frozenset[str] = frozenset({"discovery"}),
) -> tuple[str, ...]:
    """Prove future-stage skipping with synthetic overall-tie scalar values."""

    allowed_stage_sets = {
        frozenset({"discovery"}),
        frozenset({"discovery", "validation"}),
        frozenset({"discovery", "validation", "holdout"}),
    }
    if opened_stages not in allowed_stage_sets:
        raise OlympicsScoringV003Error("Opened stages are invalid")
    identities = [item.strategy_identity for item in competitors]
    if any(not HASH_PATTERN.fullmatch(item) for item in identities) or len(set(identities)) != len(identities):
        raise OlympicsScoringV003Error("Overall tie identities are invalid or duplicated")
    for item in competitors:
        if not _finite_number(item.discovery_maximum_drawdown):
            raise OlympicsScoringV003Error("Discovery drawdown must be finite")
        if "validation" in opened_stages and not _finite_number(item.validation_net_expectancy):
            raise OlympicsScoringV003Error("Opened validation value must be finite")
        if "holdout" in opened_stages and not _finite_number(item.holdout_net_expectancy):
            raise OlympicsScoringV003Error("Opened holdout value must be finite")

    def compare(left: SyntheticOverallTieRecord, right: SyntheticOverallTieRecord) -> int:
        if "validation" in opened_stages:
            value = -_compare_values(
                left.validation_net_expectancy,
                right.validation_net_expectancy,
                "higher_is_better",
            )
            if value:
                return value
        if "holdout" in opened_stages:
            value = -_compare_values(
                left.holdout_net_expectancy,
                right.holdout_net_expectancy,
                "higher_is_better",
            )
            if value:
                return value
        drawdown = _compare_values(
            left.discovery_maximum_drawdown,
            right.discovery_maximum_drawdown,
            "higher_is_better",
        )
        if drawdown:
            return drawdown
        return (left.strategy_identity.encode("utf-8") > right.strategy_identity.encode("utf-8")) - (
            left.strategy_identity.encode("utf-8") < right.strategy_identity.encode("utf-8")
        )

    return tuple(
        item.strategy_identity for item in sorted(competitors, key=cmp_to_key(compare))
    )


def validate_repository_lineage(root: Path, *, check_tag: bool = True) -> dict[str, object]:
    """Validate V003 plus every bound prior identity; never access empirical data."""

    from aml.lean_capital_governance import load_governance
    from aml.professional_strategy_executor_registry_v001 import implementation_bundle
    from aml.professional_strategy_olympics import (
        load_protocol,
        load_readiness_artifact,
        load_registry,
        load_tournament,
    )
    from aml.professional_strategy_olympics_v002 import load_bundle as load_v002

    bundle = load_bundle(root / "config/professional_strategy_olympics_scoring_v003.json")
    protocol = load_protocol(root / "config/professional_strategy_olympics_protocol_v001.json")
    registry = load_registry(
        root / "config/professional_strategy_olympics_strategy_registry_v001.json",
        protocol,
    )
    tournament = load_tournament(
        root / "config/professional_strategy_olympics_tournament_v001.json",
        protocol,
        registry,
    )
    readiness = load_readiness_artifact(
        root / "config/professional_strategy_olympics_readiness_v001.json",
        protocol,
        registry,
        tournament,
    )
    actual_v001 = {
        "v001_protocol_identity": protocol["protocol_identity"],
        "v001_registry_identity": registry["registry_identity"],
        "v001_tournament_identity": tournament["tournament_identity"],
        "v001_readiness_identity": readiness["readiness_identity"],
    }
    if actual_v001 != V001_IDENTITIES:
        raise OlympicsScoringV003Error("A frozen V001 identity changed")
    v002 = load_v002(root / "config/professional_strategy_olympics_v002.json")
    actual_v002 = {
        "v002_protocol_identity": v002["protocol_identity"],
        "v002_indicators_identity": v002["shared_indicators"]["indicators_identity"],
        "v002_input_schema_identity": v002["input_schema"]["input_schema_identity"],
        "v002_lifecycle_identity": v002["lifecycle"]["lifecycle_identity"],
        "v002_cost_model_identity": v002["costs"]["cost_model_identity"],
        "v002_registry_identity": v002["registry"]["registry_identity"],
        "v002_tournament_identity": v002["tournament"]["tournament_identity"],
        "v002_evidence_identity": v002["evidence_classification"]["evidence_identity"],
        "v002_unresolved_identity": v002["unresolved_register"]["unresolved_identity"],
        "v002_readiness_identity": v002["readiness"]["readiness_identity"],
    }
    if actual_v002 != V002_IDENTITIES:
        raise OlympicsScoringV003Error("A frozen V002 identity changed")
    governance = load_governance(root / "config/lean_discovery_capital_governance_v001.json")
    if governance["governance_identity"] != CAPITAL_GOVERNANCE_IDENTITY:
        raise OlympicsScoringV003Error("Capital-governance identity changed")
    executors = implementation_bundle()
    actual_executor_layer = {
        "executor_protocol_identity": executors["executor_protocol_identity"],
        "shared_indicator_implementation_identity": executors["shared_indicator_implementation_identity"],
        "shared_lifecycle_implementation_identity": executors["shared_lifecycle_implementation_identity"],
        "executor_registry_identity": executors["executor_registry_identity"],
        "executor_bundle_identity": executors["implementation_bundle_identity"],
        "executor_readiness_identity": executors["blocked_empirical_readiness_identity"],
    }
    if actual_executor_layer != EXECUTOR_LAYER_IDENTITIES:
        raise OlympicsScoringV003Error("Executor-layer identity changed")
    if tuple(item["executor_identity"] for item in executors["executors"]) != EXECUTOR_IDENTITIES:
        raise OlympicsScoringV003Error("A strategy executor identity changed")
    if not all(event["tie_policy"].endswith("lexicographic strategy identity") for event in tournament["scoring_events"]):
        raise OlympicsScoringV003Error("A frozen event tie policy conflicts with V003")
    if tournament["overall_scoring"]["tie_breaking"] != bundle["scoring_clarification"]["discovery_only_overall_ties"]["frozen_declared_sequence"]:
        raise OlympicsScoringV003Error("Frozen overall tie sequence conflicts with V003")
    if check_tag:
        tag_object = subprocess.run(
            ["git", "rev-parse", f"{TAG_NAME}^{{tag}}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tagged_commit = subprocess.run(
            ["git", "rev-parse", f"{TAG_NAME}^{{}}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if (tag_object, tagged_commit) != (TAG_OBJECT, TAGGED_COMMIT):
            raise OlympicsScoringV003Error("Immutable baseline tag changed")
    return bundle
