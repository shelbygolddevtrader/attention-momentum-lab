"""Bounded Alpaca SIP engineering rehearsal for the historical research stack.

The workflow is intentionally separate from Research Cohort V001.  It proves
software plumbing with one fixed symbol/session and carries machine-readable
evidence gaps; it cannot create validation evidence or a production manifest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd

from aml.historical_portfolio import (
    ATTENTION_STRATEGY_IDENTIFIER,
    HistoricalSessionProvenance,
    assert_legacy_trade_parity,
    attention_proposals_from_replay,
    historical_portfolio_config,
    order_historical_proposals,
)
from aml.market_halts import CompletenessMode, load_verified_halts
from aml.portfolio_artifacts import (
    PortfolioRunContext,
    RunLabel,
    deterministic_portfolio_run_id,
    file_sha256,
    load_portfolio_run,
    portfolio_artifact_directory,
    write_portfolio_run,
)
from aml.portfolio_simulator import simulate_portfolio
from aml.replay import replay_to_frame
from aml.research_acquisition import (
    AcquisitionDataError,
    AcquisitionRequest,
    SegmentPaths,
    acquire_research_session,
    requests_for_session,
    research_segment_paths,
)
from aml.trade_simulator import SimulationConfig, simulate_trades


ENGINEERING_REHEARSAL_VERSION = "1.0.0"
ENGINEERING_REHEARSAL_ID = "alpaca_sip_aapl_2026-07-15_v001"
ENGINEERING_EVIDENCE_CLASS = "engineering_rehearsal_only_not_validation"
FIXED_SYMBOL = "AAPL"
FIXED_TRADING_DATE = date(2026, 7, 15)
FIXED_DATASET_VINTAGE = "engineering-rehearsal-v001"


@dataclass(frozen=True)
class EngineeringRehearsalScope:
    """Immutable network and evidence boundary for rehearsal version 1."""

    workflow_id: str = ENGINEERING_REHEARSAL_ID
    workflow_version: str = ENGINEERING_REHEARSAL_VERSION
    symbol: str = FIXED_SYMBOL
    trading_date: date = FIXED_TRADING_DATE
    feed: str = "sip"
    dataset_vintage: str = FIXED_DATASET_VINTAGE
    calendar_id: str = "XNYS"

    def __post_init__(self) -> None:
        expected = (
            ENGINEERING_REHEARSAL_ID,
            ENGINEERING_REHEARSAL_VERSION,
            FIXED_SYMBOL,
            FIXED_TRADING_DATE,
            "sip",
            FIXED_DATASET_VINTAGE,
            "XNYS",
        )
        actual = (
            self.workflow_id,
            self.workflow_version,
            self.symbol,
            self.trading_date,
            self.feed,
            self.dataset_vintage,
            self.calendar_id,
        )
        if actual != expected:
            raise ValueError("Engineering rehearsal scope is fixed and cannot be changed")


@dataclass(frozen=True)
class EngineeringRehearsalResult:
    """Paths and counts from a completed or cache-resumed rehearsal."""

    run_id: str
    artifact_directory: Path
    scope_manifest: Path
    acquisition_cache_reused: bool
    premarket_bar_count: int
    regular_bar_count: int
    proposal_count: int
    accepted_count: int
    rejected_count: int
    trade_count: int
    realized_pnl: float


def rehearsal_scope_manifest(
    scope: EngineeringRehearsalScope | None = None,
) -> dict[str, Any]:
    """Return deterministic, outcome-free scope and evidence limitations."""

    value = scope or EngineeringRehearsalScope()
    return {
        "schema_version": "1.0.0",
        "workflow_id": value.workflow_id,
        "workflow_version": value.workflow_version,
        "evidence_class": ENGINEERING_EVIDENCE_CLASS,
        "not_validation_evidence": True,
        "production_cohort_member": False,
        "production_cohort_rules_modified": False,
        "provider": "alpaca",
        "requested_feed": value.feed,
        "symbol": value.symbol,
        "trading_date": value.trading_date.isoformat(),
        "calendar_id": value.calendar_id,
        "dataset_vintage": value.dataset_vintage,
        "segments": {
            "premarket": {
                "start_inclusive": "04:00:00 America/New_York",
                "end_exclusive": "09:25:00 America/New_York",
            },
            "regular": "authoritative XNYS left-labeled session minutes",
        },
        "segment_request_count": 2,
        "pagination_may_add_requests": True,
        "new_subscription_or_purchase_authorized": False,
        "incremental_cost_usd": 0,
        "point_in_time_universe": "unavailable_not_required_for_engineering_rehearsal",
        "listing_and_symbol_continuity": "unavailable_not_required_for_engineering_rehearsal",
        "negative_corporate_action_evidence": "unavailable_not_required_for_engineering_rehearsal",
        "commercial_retention_rights": "unverified_not_granted_by_rehearsal",
        "subscriber_display_rights": "unverified_not_granted_by_rehearsal",
        "permitted_interpretation": "software_process_only_no_validation_tuning_or_profitability_claim",
    }


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _publish_or_validate(path: Path, content: bytes) -> Path:
    path = Path(path)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != content:
            raise FileExistsError(f"Rehearsal manifest conflicts with write-once path: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def persist_rehearsal_scope_manifest(
    root: Path, scope: EngineeringRehearsalScope | None = None
) -> Path:
    """Publish or verify the immutable generated rehearsal scope manifest."""

    value = scope or EngineeringRehearsalScope()
    path = Path(root) / "artifacts" / "engineering_rehearsal" / value.workflow_id
    return _publish_or_validate(
        path / "scope_manifest.json", _canonical_json(rehearsal_scope_manifest(value))
    )


def _validated_segment(
    root: Path,
    request: AcquisitionRequest,
) -> tuple[SegmentPaths, pd.DataFrame, dict[str, Any]]:
    paths = research_segment_paths(root, request)
    if not all(path.is_file() and not path.is_symlink() for path in asdict(paths).values()):
        raise AcquisitionDataError(
            f"Cached rehearsal segment is absent or incomplete: {request.segment.value}"
        )
    try:
        metadata = json.loads(paths.metadata.read_text(encoding="utf-8"))
        raw = json.loads(paths.raw_response.read_text(encoding="utf-8"))
        bars = pd.read_csv(paths.processed_bars)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcquisitionDataError(
            f"Cached rehearsal segment is malformed: {request.segment.value}"
        ) from exc
    expected = {
        "status": "success",
        "provider": "alpaca",
        "symbol": request.symbol,
        "trading_date": request.trading_date.isoformat(),
        "segment": request.segment.value,
        "requested_feed": request.requested_feed,
        "dataset_vintage": request.dataset_vintage,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise AcquisitionDataError(
            f"Cached rehearsal metadata identity mismatch: {request.segment.value}"
        )
    if metadata.get("actual_feed") not in {None, request.requested_feed}:
        raise AcquisitionDataError("Cached rehearsal feed contradicts the SIP request")
    expected_feed_evidence = (
        "provider_response_field"
        if metadata.get("actual_feed") == request.requested_feed
        else "explicit_request_parameter_provider_did_not_echo_feed"
    )
    if metadata.get("actual_feed_evidence") != expected_feed_evidence:
        raise AcquisitionDataError("Cached rehearsal feed provenance is insufficient")
    pagination = metadata.get("pagination")
    pages = raw.get("provider_pages") if isinstance(raw, dict) else None
    if not isinstance(pagination, dict) or not isinstance(pages, list) or not pages:
        raise AcquisitionDataError("Cached raw response lacks complete provider pages")
    page_count = pagination.get("page_count")
    if not isinstance(page_count, int) or page_count < 1 or len(pages) != page_count:
        raise AcquisitionDataError("Cached raw response page count is inconsistent")
    if any(
        not isinstance(page, dict)
        or not isinstance(page.get("bars"), (list, type(None)))
        or "next_page_token" not in page
        for page in pages
    ):
        raise AcquisitionDataError("Cached raw response contains a malformed provider page")
    if pages[-1].get("next_page_token") is not None:
        raise AcquisitionDataError("Cached raw response ends before pagination completed")
    raw_bars = raw.get("bars")
    page_record_counts = pagination.get("page_record_counts")
    if (
        not isinstance(raw_bars, list)
        or not isinstance(page_record_counts, list)
        or len(page_record_counts) != page_count
        or any(not isinstance(count, int) or count < 0 for count in page_record_counts)
        or sum(page_record_counts) != len(raw_bars)
        or metadata.get("provider_record_count") != len(raw_bars)
    ):
        raise AcquisitionDataError("Cached raw response record counts are inconsistent")
    if file_sha256(paths.raw_response) != metadata.get("raw_response_sha256"):
        raise AcquisitionDataError("Cached rehearsal raw-response hash mismatch")
    if file_sha256(paths.processed_bars) != metadata.get("processed_sha256"):
        raise AcquisitionDataError("Cached rehearsal processed-file hash mismatch")
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    if missing := required.difference(bars.columns):
        raise AcquisitionDataError(
            f"Cached rehearsal bars are missing: {', '.join(sorted(missing))}"
        )
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    if bars["timestamp"].dt.tz is None:
        raise AcquisitionDataError("Cached rehearsal timestamps must be timezone-aware")
    if bars["timestamp"].duplicated().any() or not bars["timestamp"].is_monotonic_increasing:
        raise AcquisitionDataError("Cached rehearsal timestamps are duplicated or unsorted")
    if not bars["symbol"].astype(str).str.upper().eq(request.symbol).all():
        raise AcquisitionDataError("Cached rehearsal bars contain another symbol")
    if len(bars) != metadata.get("record_count"):
        raise AcquisitionDataError("Cached rehearsal record count mismatch")
    return paths, bars, metadata


def acquire_or_resume_rehearsal(
    client: Any,
    calendar: Any,
    root: Path,
    scope: EngineeringRehearsalScope | None = None,
) -> tuple[
    tuple[SegmentPaths, pd.DataFrame, dict[str, Any]],
    tuple[SegmentPaths, pd.DataFrame, dict[str, Any]],
    bool,
]:
    """Acquire both fixed segments atomically, or verify and reuse both.

    Network acquisition occurs only when neither final segment exists. Any
    partial or contradictory cache fails closed. Provider failures remain in a
    temporary staging tree and cannot masquerade as a resumable success.
    """

    value = scope or EngineeringRehearsalScope()
    root = Path(root).resolve()
    schedule = calendar.schedule(value.trading_date, value.calendar_id)
    requests = requests_for_session(
        value.symbol,
        value.trading_date,
        schedule,
        value.dataset_vintage,
        value.feed,
    )
    final_paths = [research_segment_paths(root, request) for request in requests]
    final_session = final_paths[0].raw_response.parents[1]
    existing = [path.exists() for paths in final_paths for path in asdict(paths).values()]
    if all(existing):
        return tuple(_validated_segment(root, request) for request in requests) + (True,)
    if any(existing):
        raise AcquisitionDataError("Rehearsal cache is partial; refusing implicit repair")
    if final_session.exists():
        raise AcquisitionDataError("Rehearsal cache directory is non-empty or unrecognized")

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".engineering-rehearsal-", dir=root) as name:
        staging_root = Path(name)
        acquire_research_session(
            client,
            calendar,
            staging_root,
            symbol=value.symbol,
            trading_date=value.trading_date,
            dataset_vintage=value.dataset_vintage,
            feed=value.feed,
            calendar_id=value.calendar_id,
        )
        for request in requests:
            _validated_segment(staging_root, request)
        staged_session = research_segment_paths(
            staging_root, requests[0]
        ).raw_response.parents[1]
        final_session.parent.mkdir(parents=True, exist_ok=True)
        if final_session.exists():
            raise FileExistsError(f"Rehearsal acquisition destination already exists: {final_session}")
        os.rename(staged_session, final_session)
    return tuple(_validated_segment(root, request) for request in requests) + (False,)


def run_engineering_rehearsal(
    client: Any,
    calendar: Any,
    root: Path,
    artifact_root: Path,
    *,
    source_commit: str,
    source_worktree_dirty: bool,
    execution_timestamp: pd.Timestamp,
    scope: EngineeringRehearsalScope | None = None,
) -> EngineeringRehearsalResult:
    """Execute the fixed rehearsal through acquisition, replay, and artifacts."""

    value = scope or EngineeringRehearsalScope()
    manifest_path = persist_rehearsal_scope_manifest(root, value)
    acquired = acquire_or_resume_rehearsal(client, calendar, root, value)
    premarket, regular, cache_reused = acquired
    premarket_paths, premarket_bars, premarket_metadata = premarket
    regular_paths, regular_bars, regular_metadata = regular

    replay = replay_to_frame(regular_bars)
    simulation_config = SimulationConfig()
    completeness_mode = CompletenessMode.HALT_AWARE
    halts = load_verified_halts(value.symbol, value.trading_date)
    legacy_trades, _ = simulate_trades(
        replay, regular_bars, simulation_config, completeness_mode, halts
    )
    session = HistoricalSessionProvenance(
        symbol=value.symbol,
        trading_date=value.trading_date,
        feed=value.feed,
        dataset_vintage=value.dataset_vintage,
        session_class="fixed_engineering_fixture",
        cohort_id=value.workflow_id,
        data_source="alpaca_historical_sip_engineering_rehearsal",
        selection_rule="fixed_before_acquisition_not_point_in_time_cohort_selection",
        input_sha256=file_sha256(regular_paths.processed_bars),
        completeness_mode=completeness_mode,
        halt_schedule=halts,
    )
    proposals = order_historical_proposals(attention_proposals_from_replay(
        replay,
        session,
        simulation_config,
        admitted_signal_timestamps=set(legacy_trades.get("signal_timestamp", [])),
    ))
    portfolio_config = historical_portfolio_config(simulation_config)
    portfolio_result = simulate_portfolio(
        proposals, {value.symbol: regular_bars}, portfolio_config
    )
    assert_legacy_trade_parity(legacy_trades, portfolio_result.trades)

    input_hashes = {"scope_manifest": file_sha256(manifest_path)}
    for segment, paths in (("premarket", premarket_paths), ("regular", regular_paths)):
        input_hashes[f"{segment}_raw_response"] = file_sha256(paths.raw_response)
        input_hashes[f"{segment}_processed_bars"] = file_sha256(paths.processed_bars)
        input_hashes[f"{segment}_acquisition_metadata"] = file_sha256(paths.metadata)
    strategy_path = Path(root) / "config" / "strategy_v001.yaml"
    input_hashes["strategy_configuration"] = file_sha256(strategy_path)

    acquisition_provenance = []
    for metadata in (premarket_metadata, regular_metadata):
        acquisition_provenance.append({
            "segment": metadata["segment"],
            "requested_feed": metadata["requested_feed"],
            "actual_feed": metadata["actual_feed"],
            "actual_feed_evidence": metadata["actual_feed_evidence"],
            "page_count": metadata["pagination"]["page_count"],
            "pagination_occurred": metadata["pagination"]["pagination_occurred"],
            "record_count": metadata["record_count"],
            "missing_timestamp_count": metadata["normalization"]["missing_timestamp_count"],
        })
    context = PortfolioRunContext(
        source_commit=source_commit,
        source_worktree_dirty=source_worktree_dirty,
        execution_timestamp=execution_timestamp,
        run_label=RunLabel.DEVELOPMENT,
        simulator_configuration={
            "engine": "simulate_portfolio",
            "proposal_adapter": "historical_attention_v001",
            "rehearsal_workflow_version": value.workflow_version,
            "legacy_simulation_config": asdict(simulation_config),
            "completeness_mode": completeness_mode.value,
        },
        input_hashes=input_hashes,
        provenance={
            **rehearsal_scope_manifest(value),
            "acquisition": acquisition_provenance,
            "strategy_employee": {
                "strategy_identifier": ATTENTION_STRATEGY_IDENTIFIER,
                "strategy_version": simulation_config.strategy_version,
            },
            "verified_halt_count": len(halts.records),
            "verified_full_halt_minute_count": len(halts.full_halt_minutes),
        },
    )
    run_id = deterministic_portfolio_run_id(
        portfolio_result, proposals, portfolio_config, context
    )
    destination = portfolio_artifact_directory(artifact_root, run_id)
    if destination.exists():
        completed = load_portfolio_run(destination)
    else:
        completed = load_portfolio_run(write_portfolio_run(
            artifact_root, portfolio_result, proposals, portfolio_config, context
        ))
    return EngineeringRehearsalResult(
        run_id=run_id,
        artifact_directory=completed.directory,
        scope_manifest=manifest_path,
        acquisition_cache_reused=bool(cache_reused),
        premarket_bar_count=len(premarket_bars),
        regular_bar_count=len(regular_bars),
        proposal_count=len(completed.proposals),
        accepted_count=len(completed.accepted_proposals),
        rejected_count=len(completed.rejected_proposals),
        trade_count=len(completed.portfolio_trades),
        realized_pnl=float(completed.portfolio_summary["realized_pnl"]),
    )
