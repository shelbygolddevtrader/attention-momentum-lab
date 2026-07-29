"""Deterministic, provider-neutral Winner Archetype Discovery research tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import math
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from aml.winner_archetype_contracts import (
    BALANCE_SCHEMA,
    FEATURE_SNAPSHOT_SCHEMA,
    MATCHED_CONTROL_SCHEMA,
    OUTCOME_RECORD_SCHEMA,
    BalanceDiagnostic,
    CohortPartitionSpec,
    ControlMatchingSpec,
    DecisionSnapshotSpec,
    FeatureSnapshot,
    HypothesisRecord,
    ExperimentManifest,
    MANIFEST_SCHEMA,
    MatchedControlRecord,
    OutcomeDefinition,
    OutcomeRecord,
    WinnerArchetypeError,
    canonical_hash,
    is_outcome_derived_field,
)


MAX_MINUTE_BARS = 1_000
MAX_CANDIDATES = 100_000


@dataclass(frozen=True)
class PartitionPlan:
    plan_id: str
    partition_version: str
    ordered_sessions: tuple[str, ...]
    assignments: Mapping[str, tuple[str, ...]]
    boundaries: Mapping[str, tuple[str, str]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MinuteBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float

    def parsed_timestamp(self) -> datetime:
        try:
            value = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WinnerArchetypeError("Minute-bar timestamp is malformed") from exc
        if value.tzinfo is None or value.utcoffset() is None:
            raise WinnerArchetypeError("Minute-bar timestamp must include a timezone")
        return value

    def validate(self) -> None:
        self.parsed_timestamp()
        values = (self.open, self.high, self.low, self.close)
        if any(type(item) not in {int, float} or not math.isfinite(float(item)) or item <= 0 for item in values):
            raise WinnerArchetypeError("Minute-bar prices must be positive and finite")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise WinnerArchetypeError("Minute-bar OHLC values are inconsistent")


@dataclass(frozen=True)
class CandidateEvent:
    event_id: str
    session: str
    symbol: str
    security_identifier: str
    winner: bool
    pre_outcome_features: Mapping[str, float | str | bool | None]

    def validate(self) -> None:
        if not self.event_id or not self.session or not self.symbol or not self.security_identifier:
            raise WinnerArchetypeError("Candidate identity fields are required")
        try:
            date.fromisoformat(self.session)
        except ValueError as exc:
            raise WinnerArchetypeError("Candidate session is malformed") from exc
        if self.symbol != self.symbol.upper():
            raise WinnerArchetypeError("Candidate symbol must be normalized")
        if type(self.winner) is not bool:
            raise WinnerArchetypeError("Candidate winner eligibility must be boolean")
        for field, value in self.pre_outcome_features.items():
            if is_outcome_derived_field(field):
                raise WinnerArchetypeError("Post-outcome candidate fields are prohibited")
            if value is None:
                continue
            if type(value) in {int, float}:
                if not math.isfinite(float(value)):
                    raise WinnerArchetypeError("Candidate matching values must be finite")
            elif type(value) is str:
                if not value.strip():
                    raise WinnerArchetypeError("Categorical matching values must be non-empty")
            elif type(value) is not bool:
                raise WinnerArchetypeError("Candidate matching values have an unsupported type")


def plan_chronological_partitions(
    ordered_sessions: Sequence[str], spec: CohortPartitionSpec
) -> PartitionPlan:
    """Assign unique ordered sessions without randomization or host-dependent state."""
    parsed: list[str] = []
    for item in ordered_sessions:
        try:
            parsed.append(date.fromisoformat(item).isoformat())
        except (TypeError, ValueError) as exc:
            raise WinnerArchetypeError("Partition sessions must be ISO dates") from exc
    if tuple(parsed) != tuple(sorted(set(parsed))):
        raise WinnerArchetypeError("Partition sessions must be strictly ordered and unique")
    minimum = spec.minimum_sessions_per_partition
    if len(parsed) < minimum * 3:
        raise WinnerArchetypeError("Too few sessions for chronological partitions")
    discovery_count = len(parsed) * spec.discovery_basis_points // 10_000
    validation_count = len(parsed) * spec.validation_basis_points // 10_000
    if discovery_count < minimum or validation_count < minimum:
        raise WinnerArchetypeError("A chronological partition is below its minimum")
    holdout_count = len(parsed) - discovery_count - validation_count
    if holdout_count < minimum:
        raise WinnerArchetypeError("Holdout partition is below its minimum")
    assignments = {
        "discovery": tuple(parsed[:discovery_count]),
        "validation": tuple(parsed[discovery_count:discovery_count + validation_count]),
        "holdout": tuple(parsed[discovery_count + validation_count:]),
    }
    if set().union(*(set(value) for value in assignments.values())) != set(parsed):
        raise WinnerArchetypeError("Partition plan does not cover every session")
    boundaries = {
        key: (values[0], values[-1]) for key, values in assignments.items()
    }
    payload = {
        "partition_version": spec.partition_version,
        "ordered_sessions": parsed,
        "assignments": assignments,
        "boundaries": boundaries,
    }
    return PartitionPlan(
        plan_id=canonical_hash(payload),
        partition_version=spec.partition_version,
        ordered_sessions=tuple(parsed),
        assignments=assignments,
        boundaries=boundaries,
    )


def build_feature_snapshot(
    *,
    session: str,
    symbol: str,
    security_identifier: str,
    snapshot_spec: DecisionSnapshotSpec,
    latest_input_timestamp: str,
    feature_definition_version: str,
    source_manifest_hashes: Iterable[str],
    completeness_status: str,
    feature_values: Mapping[str, object],
) -> FeatureSnapshot:
    session_date = date.fromisoformat(session)
    local_time = datetime.strptime(snapshot_spec.local_time, "%H:%M").time()
    decision = datetime.combine(
        session_date, local_time, ZoneInfo(snapshot_spec.timezone)
    )
    values = {key: feature_values[key] for key in sorted(feature_values)}
    missingness = {key: values[key] is None for key in values}
    return FeatureSnapshot(
        schema_version=FEATURE_SNAPSHOT_SCHEMA,
        session=session,
        symbol=symbol,
        security_identifier=security_identifier,
        decision_timestamp=decision.isoformat(),
        latest_input_timestamp=latest_input_timestamp,
        timezone=snapshot_spec.timezone,
        cutoff_semantics=snapshot_spec.cutoff_semantics,
        snapshot_version=snapshot_spec.snapshot_version,
        snapshot_spec_hash=snapshot_spec.identity,
        feature_definition_version=feature_definition_version,
        source_manifest_hashes=tuple(sorted(set(source_manifest_hashes))),
        completeness_status=completeness_status,
        feature_values=values,
        missingness=missingness,
        canonical_feature_hash=canonical_hash(values),
    )


def _halt_minutes(
    intervals: Sequence[tuple[str, str]], zone: ZoneInfo
) -> set[datetime]:
    result: set[datetime] = set()
    for raw_start, raw_end in intervals:
        try:
            start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(zone)
            end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")).astimezone(zone)
        except ValueError as exc:
            raise WinnerArchetypeError("Halt interval timestamp is malformed") from exc
        if start > end or start.second or end.second or start.microsecond or end.microsecond:
            raise WinnerArchetypeError("Halt intervals must be ordered whole minutes")
        current = start
        while current <= end:
            result.add(current)
            current += timedelta(minutes=1)
            if len(result) > MAX_MINUTE_BARS:
                raise WinnerArchetypeError("Halt interval input exceeds the bound")
    return result


def calculate_outcome(
    *,
    symbol: str,
    security_identifier: str,
    session: str,
    definition: OutcomeDefinition,
    bars: Sequence[MinuteBar],
    input_manifest_hash: str,
    verified_halt_intervals: Sequence[tuple[str, str]] = (),
    declared_reference_price: float | None = None,
) -> OutcomeRecord:
    """Calculate descriptive labels without fill inference or tradability claims."""
    if len(bars) > MAX_MINUTE_BARS:
        raise WinnerArchetypeError("Minute-bar input exceeds the bounded limit")
    zone = ZoneInfo(definition.session_timezone)
    day = date.fromisoformat(session)
    reference_time = datetime.combine(
        day, datetime.strptime(definition.reference_time, "%H:%M").time(), zone
    )
    window_start = datetime.combine(
        day, datetime.strptime(definition.evaluation_start, "%H:%M").time(), zone
    )
    window_end = datetime.combine(
        day, datetime.strptime(definition.evaluation_end, "%H:%M").time(), zone
    )
    indexed: dict[datetime, MinuteBar] = {}
    for bar in bars:
        bar.validate()
        timestamp = bar.parsed_timestamp().astimezone(zone)
        if timestamp.second or timestamp.microsecond:
            raise WinnerArchetypeError("Minute bars must use whole-minute timestamps")
        if timestamp.date() != day:
            raise WinnerArchetypeError("Minute bar falls outside the declared session")
        if timestamp in indexed:
            raise WinnerArchetypeError("Minute-bar timestamps must be unique")
        indexed[timestamp] = bar
    if tuple(indexed) != tuple(sorted(indexed)):
        raise WinnerArchetypeError("Minute bars must be chronological")
    reference_bar = indexed.get(reference_time)
    if definition.reference_price_semantics == "declared_external":
        if declared_reference_price is None or not math.isfinite(declared_reference_price) or declared_reference_price <= 0:
            raise WinnerArchetypeError("A positive declared reference price is required")
        reference_price = float(declared_reference_price)
    elif reference_bar is None:
        reference_price = None
    elif definition.reference_price_semantics == "bar_open":
        reference_price = float(reference_bar.open)
    else:
        reference_price = float(reference_bar.close)

    halts = _halt_minutes(verified_halt_intervals, zone)
    expected: list[datetime] = []
    current = window_start
    while current <= window_end:
        expected.append(current)
        current += timedelta(minutes=1)
    expected_nonhalt = [item for item in expected if item not in halts]
    usable = [(timestamp, indexed[timestamp]) for timestamp in expected_nonhalt if timestamp in indexed]
    missing = len(expected_nonhalt) - len(usable)
    halt_count = len(set(expected) & halts)
    if reference_price is None or not usable:
        completeness = "no_usable_bars"
    elif missing:
        completeness = "incomplete"
    elif halt_count:
        completeness = "halt_adjusted_complete"
    else:
        completeness = "complete"

    mfe: float | None = None
    mae: float | None = None
    threshold_order = "unavailable"
    reward_to_risk: bool | None = None
    sustained: bool | None = None
    closed_above: bool | None = None
    if reference_price is not None and usable:
        mfe = max(float(bar.high) / reference_price - 1 for _, bar in usable)
        mae = min(float(bar.low) / reference_price - 1 for _, bar in usable)
        threshold_order = "neither"
        for _, bar in usable:
            hit_upside = bar.high / reference_price - 1 >= definition.upside_threshold
            hit_downside = bar.low / reference_price - 1 <= -definition.downside_threshold
            if hit_upside and hit_downside:
                threshold_order = "ambiguous_downside_first"
                break
            if hit_downside:
                threshold_order = "downside_first"
                break
            if hit_upside:
                threshold_order = "upside_first"
                break
        reward_to_risk = mfe >= definition.reward_to_risk_multiple * definition.downside_threshold
        run = 0
        sustained = False
        for _, bar in usable:
            if bar.close / reference_price - 1 >= definition.sustained_momentum_threshold:
                run += 1
                sustained = sustained or run >= definition.sustained_minutes
            else:
                run = 0
        closed_above = usable[-1][1].close > reference_price

    definition_hash = definition.identity
    result = {
        "schema_version": OUTCOME_RECORD_SCHEMA,
        "symbol": symbol,
        "security_identifier": security_identifier,
        "session": session,
        "outcome_definition_version": definition.definition_version,
        "outcome_definition_hash": definition_hash,
        "reference_timestamp": reference_time.isoformat(),
        "reference_price": reference_price,
        "evaluation_window": (window_start.isoformat(), window_end.isoformat()),
        "input_manifest_hash": input_manifest_hash,
        "completeness_status": completeness,
        "missing_minutes": missing,
        "verified_halt_minutes": halt_count,
        "maximum_favorable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "threshold_order": threshold_order,
        "reward_to_risk_achieved": reward_to_risk,
        "sustained_momentum_achieved": sustained,
        "closed_above_reference": closed_above,
        "halt_involved": bool(halt_count),
    }
    result_hash = canonical_hash(result)
    identity_payload = {
        "symbol": symbol,
        "security_identifier": security_identifier,
        "session": session,
        "outcome_definition_version": definition.definition_version,
        "outcome_definition_hash": definition_hash,
        "reference_timestamp": reference_time.isoformat(),
        "reference_price": result["reference_price"],
        "evaluation_window": result["evaluation_window"],
        "halt_treatment": completeness,
        "input_manifest_hash": input_manifest_hash,
        "canonical_result_hash": result_hash,
    }
    return OutcomeRecord(
        outcome_id=canonical_hash(identity_payload),
        canonical_result_hash=result_hash,
        **result,
    )


def _distance(
    winner: CandidateEvent, control: CandidateEvent, spec: ControlMatchingSpec
) -> float | None:
    total = 0.0
    for field in spec.matching_fields:
        left = winner.pre_outcome_features.get(field)
        right = control.pre_outcome_features.get(field)
        if left is None or right is None:
            return None
        if type(left) in {int, float} and type(right) in {int, float}:
            difference = abs(float(left) - float(right)) / float(spec.field_scales[field])
        elif type(left) is type(right) and type(left) in {str, bool}:
            difference = 0.0 if left == right else 1.0
        else:
            raise WinnerArchetypeError("Matching field types are inconsistent")
        total += difference * float(spec.field_weights[field])
    return total


def plan_matched_controls(
    candidates: Sequence[CandidateEvent], spec: ControlMatchingSpec
) -> tuple[MatchedControlRecord, ...]:
    """Select deterministic same-session controls using pre-outcome values only."""
    if len(candidates) > MAX_CANDIDATES:
        raise WinnerArchetypeError("Candidate input exceeds the bounded limit")
    for candidate in candidates:
        candidate.validate()
    identifiers = [item.event_id for item in candidates]
    if len(set(identifiers)) != len(identifiers):
        raise WinnerArchetypeError("Candidate event IDs must be unique")
    ordered = sorted(candidates, key=lambda item: (item.session, item.symbol, item.event_id))
    winners = [item for item in ordered if item.winner]
    controls = [item for item in ordered if not item.winner]
    used: set[str] = set()
    records: list[MatchedControlRecord] = []
    matching_spec_hash = spec.identity
    for winner in winners:
        pool: list[tuple[float, CandidateEvent]] = []
        missing_fields = False
        for control in controls:
            if control.session != winner.session:
                continue
            if not spec.with_replacement and control.event_id in used:
                continue
            distance = _distance(winner, control, spec)
            if distance is None:
                missing_fields = True
                continue
            pool.append((distance, control))
        pool.sort(key=lambda item: (item[0], item[1].symbol, item[1].event_id))
        selected = pool[:spec.maximum_controls]
        for rank, (distance, control) in enumerate(selected, start=1):
            if not spec.with_replacement:
                used.add(control.event_id)
            payload = {
                "matching_version": spec.matching_version,
                "matching_spec_hash": matching_spec_hash,
                "winner_event_id": winner.event_id,
                "control_event_id": control.event_id,
                "session": winner.session,
                "rank": rank,
                "distance": distance,
                "with_replacement": spec.with_replacement,
                "reason_code": "matched",
                "fields_used": spec.matching_fields,
            }
            records.append(MatchedControlRecord(
                schema_version=MATCHED_CONTROL_SCHEMA,
                match_id=canonical_hash(payload),
                **payload,
            ))
        for rank in range(len(selected) + 1, spec.maximum_controls + 1):
            reason = "missing_matching_fields" if missing_fields and not selected else "insufficient_controls"
            payload = {
                "matching_version": spec.matching_version,
                "matching_spec_hash": matching_spec_hash,
                "winner_event_id": winner.event_id,
                "control_event_id": None,
                "session": winner.session,
                "rank": rank,
                "distance": None,
                "with_replacement": spec.with_replacement,
                "reason_code": reason,
                "fields_used": spec.matching_fields,
            }
            records.append(MatchedControlRecord(
                schema_version=MATCHED_CONTROL_SCHEMA,
                match_id=canonical_hash(payload),
                **payload,
            ))
    return tuple(records)


def balance_diagnostics(
    candidates: Sequence[CandidateEvent],
    matches: Sequence[MatchedControlRecord],
    spec: ControlMatchingSpec,
) -> tuple[BalanceDiagnostic, ...]:
    """Return pre/post standardized mean differences and missingness counts."""
    by_id = {item.event_id: item for item in candidates}
    winners = [item for item in candidates if item.winner]
    all_controls = [item for item in candidates if not item.winner]
    matched_winner_ids = {item.winner_event_id for item in matches if item.control_event_id}
    matched_control_ids = [item.control_event_id for item in matches if item.control_event_id]
    result: list[BalanceDiagnostic] = []
    matching_spec_hash = spec.identity
    for stage, left_group, right_group in (
        ("before", winners, all_controls),
        (
            "after",
            [by_id[item] for item in sorted(matched_winner_ids)],
            [by_id[item] for item in matched_control_ids],
        ),
    ):
        for field in spec.matching_fields:
            left_raw = [item.pre_outcome_features.get(field) for item in left_group]
            right_raw = [item.pre_outcome_features.get(field) for item in right_group]
            left_nonmissing = [item for item in left_raw if item is not None]
            right_nonmissing = [item for item in right_raw if item is not None]
            variants: list[tuple[str, list[float], list[float]]] = []
            combined = left_nonmissing + right_nonmissing
            if all(type(item) in {int, float} for item in combined):
                variants.append((
                    field,
                    [float(item) for item in left_nonmissing],
                    [float(item) for item in right_nonmissing],
                ))
            else:
                categories = sorted(set(combined), key=lambda item: (type(item).__name__, str(item)))
                for category in categories:
                    suffix = canonical_hash({"category": category})[:12]
                    variants.append((
                        f"{field}.category-{suffix}",
                        [1.0 if item == category else 0.0 for item in left_nonmissing],
                        [1.0 if item == category else 0.0 for item in right_nonmissing],
                    ))
            if not variants:
                variants.append((field, [], []))
            for diagnostic_field, left_valid, right_valid in variants:
                smd: float | None = None
                if left_valid and right_valid:
                    pooled = math.sqrt((pstdev(left_valid) ** 2 + pstdev(right_valid) ** 2) / 2)
                    difference = fmean(left_valid) - fmean(right_valid)
                    smd = difference / pooled if pooled else (0.0 if difference == 0 else None)
                payload = {
                    "matching_version": spec.matching_version,
                    "matching_spec_hash": matching_spec_hash,
                    "feature_name": diagnostic_field,
                    "stage": stage,
                    "winner_count": len(left_group),
                    "control_count": len(right_group),
                    "standardized_mean_difference": smd,
                    "missing_winner_count": len(left_raw) - len(left_nonmissing),
                    "missing_control_count": len(right_raw) - len(right_nonmissing),
                }
                result.append(BalanceDiagnostic(
                    schema_version=BALANCE_SCHEMA,
                    diagnostic_id=canonical_hash(payload),
                    **payload,
                ))
    return tuple(result)


def validate_hypothesis_registry(records: Sequence[HypothesisRecord]) -> str:
    """Validate deterministic append-only ordering and supersession linkage."""
    if not records:
        raise WinnerArchetypeError("Hypothesis registry cannot be empty")
    identifiers = [item.hypothesis_id for item in records]
    sequences = [item.sequence for item in records]
    if len(set(identifiers)) != len(identifiers):
        raise WinnerArchetypeError("Duplicate hypothesis IDs")
    if sequences != list(range(1, len(records) + 1)):
        raise WinnerArchetypeError("Hypothesis registry sequence is not append-only")
    seen: set[str] = set()
    for record in records:
        if record.supersedes_hypothesis_id is not None:
            if record.supersedes_hypothesis_id not in seen:
                raise WinnerArchetypeError("Hypothesis supersession must point backward")
            predecessor = next(item for item in records if item.hypothesis_id == record.supersedes_hypothesis_id)
            if predecessor.rejection_status != "superseded":
                raise WinnerArchetypeError("Superseded hypothesis must be marked superseded")
        seen.add(record.hypothesis_id)
    return canonical_hash([record.identity_payload() for record in records])


def authorize_phase_access(
    *,
    execution_phase: str,
    requested_partition: str,
    hypothesis: HypothesisRecord | None = None,
    supplied_parameter_hash: str | None = None,
) -> None:
    """Fail closed at discovery/validation/holdout phase boundaries."""
    if execution_phase not in {"discovery", "validation", "holdout", "paper_forward"}:
        raise WinnerArchetypeError("Execution phase is unsupported")
    if requested_partition not in {"discovery", "validation", "holdout", "paper_forward"}:
        raise WinnerArchetypeError("Requested partition is unsupported")
    allowed = {
        "discovery": {"discovery"},
        "validation": {"discovery", "validation"},
        "holdout": {"holdout"},
        "paper_forward": {"paper_forward"},
    }
    if requested_partition not in allowed[execution_phase]:
        raise WinnerArchetypeError("Phase contamination guard rejected partition access")
    if requested_partition == "holdout":
        if hypothesis is None or not hypothesis.frozen:
            raise WinnerArchetypeError("Holdout access requires a frozen hypothesis")
        if hypothesis.validation_status not in {"passed", "inconclusive"}:
            raise WinnerArchetypeError("Holdout access requires completed internal validation")
        if supplied_parameter_hash != hypothesis.parameter_freeze_hash:
            raise WinnerArchetypeError("Holdout parameter hash does not match the freeze")


def freeze_hypothesis(record: HypothesisRecord, parameters: Mapping[str, object]) -> HypothesisRecord:
    """Return a new immutable frozen record; the timestamp metadata is identity-neutral."""
    if record.frozen:
        raise WinnerArchetypeError("Hypothesis is already frozen")
    payload = asdict(record)
    payload["frozen"] = True
    payload["parameter_freeze_hash"] = canonical_hash(parameters)
    return HypothesisRecord(**payload)


def validate_append_only_result(
    existing_identity_hashes: Mapping[str, str], result_id: str, result_hash: str
) -> None:
    """Allow a new immutable result or an exact idempotent duplicate, never replacement."""
    if len(result_id) != 64 or len(result_hash) != 64:
        raise WinnerArchetypeError("Result identity and hash must be SHA-256 digests")
    try:
        int(result_id, 16)
        int(result_hash, 16)
    except ValueError as exc:
        raise WinnerArchetypeError("Result identity and hash must be SHA-256 digests") from exc
    if result_id in existing_identity_hashes and existing_identity_hashes[result_id] != result_hash:
        raise WinnerArchetypeError("An immutable result identity cannot be overwritten")


def build_experiment_manifest(
    *,
    experiment_spec_hash: str,
    partition_plan: PartitionPlan,
    source_manifest_hashes: Iterable[str],
    feature_definition_hashes: Iterable[str],
    outcome_definition_hashes: Iterable[str],
    control_matching_hash: str,
    hypothesis_registry_hash: str | None,
    holdout_accessed: bool,
) -> ExperimentManifest:
    payload = {
        "experiment_spec_hash": experiment_spec_hash,
        "partition_plan_id": partition_plan.plan_id,
        "ordered_sessions": partition_plan.ordered_sessions,
        "partition_boundaries": partition_plan.boundaries,
        "source_manifest_hashes": tuple(sorted(set(source_manifest_hashes))),
        "feature_definition_hashes": tuple(sorted(set(feature_definition_hashes))),
        "outcome_definition_hashes": tuple(sorted(set(outcome_definition_hashes))),
        "control_matching_hash": control_matching_hash,
        "hypothesis_registry_hash": hypothesis_registry_hash,
        "holdout_accessed": holdout_accessed,
    }
    return ExperimentManifest(
        schema_version=MANIFEST_SCHEMA,
        manifest_id=canonical_hash(payload),
        **payload,
    )
