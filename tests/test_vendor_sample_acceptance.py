"""Focused fail-closed tests for quarantined vendor sample acceptance."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aml.vendor_sample_acceptance import (
    SampleProfile,
    evaluate_vendor_sample,
    file_sha256,
    write_acceptance_report,
)


def licensing(provider: str = "test_vendor") -> dict:
    """Create synthetic executed evidence for every required license decision."""

    evidence = {
        "status": "granted",
        "evidence_type": "executed_order_form",
        "evidence_reference": "order-form-section-1",
    }
    restriction = {
        "status": "prohibited",
        "evidence_type": "executed_order_form",
        "evidence_reference": "order-form-section-2",
    }
    fee = {
        "status": "not_applicable",
        "evidence_type": "written_vendor_confirmation",
        "evidence_reference": "vendor-email-2024-05-01",
    }
    return {
        "schema_version": "1.0.0",
        "provider": provider,
        "contracting_entity": "Example Research LLC",
        "agreement_id": "agreement-001",
        "effective_date": "2024-05-01",
        "rights": {
            name: dict(evidence) for name in (
                "internal_research", "raw_storage", "normalized_storage", "backups",
                "cloud_processing", "contractor_access", "post_termination_retention",
                "derived_works", "subscriber_dashboard_display",
                "subscriber_conversational_display",
            )
        },
        "restrictions": {
            name: dict(restriction) for name in (
                "raw_display", "reconstructable_display", "downloads", "api", "alerts",
            )
        },
        "fees": {
            name: dict(fee) for name in (
                "exchange_fees", "display_fees", "non_display_fees",
            )
        },
    }


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def market_sample(root: Path, *, mutation=None) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    bars = pd.DataFrame({
        "timestamp": [
            "2024-06-03T08:00:00Z", "2024-06-03T13:24:00Z",
            "2024-06-03T13:30:00Z", "2024-06-03T19:59:00Z",
        ],
        "symbol": ["AAPL"] * 4,
        "segment": ["premarket", "premarket", "regular", "regular"],
        "open": [100.0] * 4,
        "high": [101.0] * 4,
        "low": [99.0] * 4,
        "close": [100.0] * 4,
        "volume": [1000] * 4,
    })
    bars_path = root / "bars.csv"
    bars.to_csv(bars_path, index=False)
    manifest = {
        "schema_version": "1.0.0",
        "profile": "market_data",
        "provider": "test_vendor",
        "sample_id": "market-sample-001",
        "bars_file": "bars.csv",
        "trading_date": "2024-06-03",
        "expected_symbols": ["AAPL"],
        "requested_feed": "sip",
        "consolidated_sip_asserted": True,
        "feed_identity_evidence_reference": "data-dictionary-section-1",
        "timeframe": "1Min",
        "timestamp_timezone": "UTC",
        "interval_label": "left",
        "premarket_start_inclusive": "2024-06-03T04:00:00-04:00",
        "premarket_end_exclusive": "2024-06-03T09:25:00-04:00",
        "premarket_status_by_symbol": {"AAPL": "observed"},
        "regular_start_inclusive": "2024-06-03T09:30:00-04:00",
        "regular_end_exclusive": "2024-06-03T16:00:00-04:00",
        "regular_calendar_id": "XNYS",
        "adjustment_semantics": "unadjusted",
        "adjustment_policy_reference": "data-dictionary-section-2",
        "delivery_complete_asserted": True,
        "missing_minute_semantics": "omitted_when_no_eligible_trade",
        "zero_trade_minute_semantics": (
            "zero_trade_minutes_not_emitted_and_not_equated_with_delivery_failure"
        ),
        "interpolation_performed": False,
        "interpolation_policy_reference": "no-fill-policy-v1",
        "condition_policy_reference": "sale-condition-guide-v1",
        "correction_policy_reference": "correction-guide-v1",
        "pagination_complete": True,
        "page_count": 1,
        "page_record_counts": [len(bars)],
        "delivered_record_count": len(bars),
        "delivery_id": "delivery-001",
        "release_id": "release-001",
        "dataset_vintage": "vintage-001",
        "source_sha256": {"bars": file_sha256(bars_path)},
    }
    if mutation:
        mutation(manifest, bars, bars_path)
        manifest["source_sha256"] = {"bars": file_sha256(bars_path)}
    return write_json(root / "manifest.json", manifest), write_json(
        root / "licensing.json", licensing()
    )


def reference_sample(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    values = {
        "universe": pd.DataFrame([{
            "as_of_timestamp": "2024-06-03T13:00:00Z", "symbol": "AAPL",
            "stable_identifier": "FIGI-AAPL", "security_type": "common_stock",
            "security_type_code": "CS",
            "security_type_description": "Common Stock", "common_stock_eligible": True,
            "exchange": "XNAS", "calendar_id": "XNYS", "active": True,
            "source": "test_vendor", "dataset_vintage": "vintage-001",
            "release_id": "release-001",
        }]),
        "listings": pd.DataFrame([{
            "stable_identifier": "FIGI-AAPL", "symbol": "AAPL",
            "listing_start_timestamp": "1980-12-12T00:00:00Z",
            "listing_end_timestamp": "", "exchange": "XNAS", "calendar_id": "XNYS",
            "known_at_timestamp": "2024-06-03T13:00:00Z", "source": "test_vendor",
            "dataset_vintage": "vintage-001", "release_id": "release-001",
        }]),
        "symbol_history": pd.DataFrame([{
            "stable_identifier": "FIGI-AAPL", "canonical_symbol": "AAPL",
            "historical_symbol": "AAPL",
            "effective_start_timestamp": "1980-12-12T00:00:00Z",
            "effective_end_timestamp": "",
            "known_at_timestamp": "2024-06-03T13:00:00Z", "source": "test_vendor",
            "dataset_vintage": "vintage-001", "release_id": "release-001",
        }]),
        "corporate_actions": pd.DataFrame([{
            "stable_identifier": "FIGI-AAPL", "symbol": "AAPL",
            "record_type": "verified_none",
            "coverage_start_timestamp": "2024-05-01T00:00:00Z",
            "coverage_end_timestamp": "2024-07-01T00:00:00Z",
            "effective_timestamp": "", "action_type": "", "adjustment_factor": "",
            "adjustment_method": "", "publication_timestamp": "2024-06-03T13:00:00Z",
            "known_at_timestamp": "2024-06-03T13:00:00Z",
            "correction_status": "original", "correction_timestamp": "",
            "source": "test_vendor", "dataset_vintage": "vintage-001",
            "release_id": "release-001",
        }]),
    }
    files = {}
    for name, frame in values.items():
        path = root / f"{name}.csv"
        frame.to_csv(path, index=False)
        files[name] = path
    manifest = {
        "schema_version": "1.0.0", "profile": "reference_data",
        "provider": "test_vendor", "sample_id": "reference-sample-001",
        "decision_timestamp": "2024-06-03T09:25:00-04:00",
        "coverage_start_timestamp": "2024-05-01T00:00:00Z",
        "coverage_end_timestamp": "2024-07-01T00:00:00Z",
        "complete_bounded_universe_asserted": True, "expected_universe_count": 1,
        "universe_scope": "complete_test_us_common_stock_universe",
        "security_type_dictionary_reference": "security-types-v1",
        "correction_policy_reference": "corrections-v1",
        "delivery_id": "delivery-001", "release_id": "release-001",
        "dataset_vintage": "vintage-001",
        "universe_file": "universe.csv", "listings_file": "listings.csv",
        "symbol_history_file": "symbol_history.csv",
        "corporate_actions_file": "corporate_actions.csv",
        "source_sha256": {name: file_sha256(path) for name, path in files.items()},
    }
    return write_json(root / "manifest.json", manifest), write_json(
        root / "licensing.json", licensing()
    )


def rewrite_reference_file(
    manifest: Path, logical_name: str, mutation
) -> None:
    """Mutate one synthetic reference file and reconcile its declared hash."""

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    path = manifest.parent / payload[f"{logical_name}_file"]
    frame = pd.read_csv(path)
    mutation(frame)
    frame.to_csv(path, index=False)
    payload["source_sha256"][logical_name] = file_sha256(path)
    write_json(manifest, payload)


def test_market_sample_passes_with_visible_missing_minutes(tmp_path: Path) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    result = evaluate_vendor_sample(SampleProfile.MARKET_DATA, manifest, license_path)
    assert result.accepted
    assert result.technical_pass and result.licensing_pass
    assert any(item.code == "market.missing_visible" for item in result.findings)
    assert result.summary["sessions"][0]["expected_regular_minutes"] == 390
    assert result.summary["sessions"][0]["unexplained_missing_minutes"] == 388


def test_market_duplicate_boundary_and_hash_fail_closed(tmp_path: Path) -> None:
    def mutate(manifest, bars, path):
        bars.loc[1, "timestamp"] = bars.loc[0, "timestamp"]
        bars.loc[1, "segment"] = "premarket"
        bars.to_csv(path, index=False)
        manifest["premarket_end_exclusive"] = "2024-06-03T09:26:00-04:00"

    manifest, license_path = market_sample(tmp_path / "market", mutation=mutate)
    payload = json.loads(manifest.read_text())
    payload["source_sha256"]["bars"] = "0" * 64
    write_json(manifest, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    codes = {item.code for item in result.findings}
    assert {"hash.bars", "market.duplicates", "market.premarket_end"}.issubset(codes)


def test_market_naive_or_out_of_order_timestamps_fail(tmp_path: Path) -> None:
    def reverse(_manifest, bars, path):
        bars = bars.iloc[::-1].reset_index(drop=True)
        bars.to_csv(path, index=False)

    manifest, license_path = market_sample(tmp_path / "ordered", mutation=reverse)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "market.order" for item in result.findings)

    def naive(_manifest, bars, path):
        bars["timestamp"] = pd.to_datetime(bars["timestamp"]).dt.tz_localize(None)
        bars.to_csv(path, index=False)

    manifest, license_path = market_sample(tmp_path / "naive", mutation=naive)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "market.timezone" for item in result.findings)


def test_reference_sample_passes_with_verified_none(tmp_path: Path) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    assert result.accepted
    assert result.summary["universe_count"] == 1
    assert not result.findings


def test_reference_stable_identifier_survives_ticker_change(tmp_path: Path) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")

    def add_old_listing(listings: pd.DataFrame) -> None:
        listings.loc[0, "listing_start_timestamp"] = "2000-01-01T00:00:00Z"
        old = listings.iloc[0].copy()
        old["symbol"] = "AAP"
        old["listing_start_timestamp"] = "1980-12-12T00:00:00Z"
        old["listing_end_timestamp"] = "2000-01-01T00:00:00Z"
        listings.loc[len(listings)] = old
        listings.sort_values(
            ["stable_identifier", "listing_start_timestamp", "symbol"],
            inplace=True,
            ignore_index=True,
        )

    def add_old_symbol(symbols: pd.DataFrame) -> None:
        symbols.loc[0, "effective_start_timestamp"] = "2000-01-01T00:00:00Z"
        old = symbols.iloc[0].copy()
        old["historical_symbol"] = "AAP"
        old["effective_start_timestamp"] = "1980-12-12T00:00:00Z"
        old["effective_end_timestamp"] = "2000-01-01T00:00:00Z"
        symbols.loc[len(symbols)] = old
        symbols.sort_values(
            ["stable_identifier", "effective_start_timestamp", "historical_symbol"],
            inplace=True,
            ignore_index=True,
        )

    rewrite_reference_file(manifest, "listings", add_old_listing)
    rewrite_reference_file(manifest, "symbol_history", add_old_symbol)
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    assert result.accepted
    assert not result.findings


def test_reference_action_provenance_passes_with_effective_boundary(
    tmp_path: Path,
) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")

    def add_action(actions: pd.DataFrame) -> None:
        actions[["effective_timestamp", "action_type", "adjustment_method"]] = (
            actions[["effective_timestamp", "action_type", "adjustment_method"]]
            .astype("string")
        )
        actions.loc[0, "record_type"] = "action"
        actions.loc[0, "effective_timestamp"] = "2024-06-01T00:00:00Z"
        actions.loc[0, "action_type"] = "split"
        actions.loc[0, "adjustment_factor"] = 0.5
        actions.loc[0, "adjustment_method"] = "price_multiply_volume_divide"
        actions.loc[0, "publication_timestamp"] = "2024-05-31T12:00:00Z"

    rewrite_reference_file(manifest, "corporate_actions", add_action)
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    assert result.accepted
    assert not result.findings


def test_reference_lookahead_and_invalid_negative_evidence_fail(tmp_path: Path) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")
    actions_path = manifest.parent / "corporate_actions.csv"
    actions = pd.read_csv(actions_path)
    actions.loc[0, "known_at_timestamp"] = "2024-06-03T13:25:00Z"
    actions.loc[0, "adjustment_factor"] = 2.0
    actions.to_csv(actions_path, index=False)
    payload = json.loads(manifest.read_text())
    payload["source_sha256"]["corporate_actions"] = file_sha256(actions_path)
    write_json(manifest, payload)
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    assert not result.technical_pass
    codes = {item.code for item in result.findings}
    assert "reference.lookahead.corporate_actions" in codes
    assert "reference.actions.verified_none" in codes


def test_unresolved_marketing_license_rejects_technical_pass(tmp_path: Path) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    payload = json.loads(license_path.read_text())
    payload["rights"]["post_termination_retention"] = {
        "status": "unresolved",
        "evidence_type": "marketing_page",
        "evidence_reference": "public-pricing-page",
    }
    write_json(license_path, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert result.technical_pass
    assert not result.licensing_pass
    assert not result.accepted


def test_reports_are_deterministic_quarantined_and_path_safe(tmp_path: Path) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    repeated = evaluate_vendor_sample("reference_data", manifest, license_path)
    assert result.run_id == repeated.run_id
    output = tmp_path / "quarantine"
    first = write_acceptance_report(result, output)
    second = write_acceptance_report(result, output)
    assert first == second
    assert (first / "acceptance_result.json").read_bytes() == (
        second / "acceptance_result.json"
    ).read_bytes()
    (first / "unexpected.txt").write_text("tamper", encoding="utf-8")
    with pytest.raises(FileExistsError, match="conflicts"):
        write_acceptance_report(result, output)
    with pytest.raises(ValueError, match="canonical data"):
        write_acceptance_report(result, Path.cwd() / "data" / "research")


def test_sample_paths_cannot_escape_manifest_directory(tmp_path: Path) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    payload = json.loads(manifest.read_text())
    payload["bars_file"] = "../outside.csv"
    write_json(manifest, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "market.bars_file" for item in result.findings)


def test_missing_malformed_and_symlinked_inputs_fail_closed(tmp_path: Path) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    manifest.unlink()
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "manifest.json" for item in result.findings)

    manifest, license_path = market_sample(tmp_path / "malformed")
    license_path.write_text("{not-json", encoding="utf-8")
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert result.technical_pass
    assert not result.licensing_pass
    assert any(item.code == "licensing.json" for item in result.findings)

    manifest, license_path = market_sample(tmp_path / "symlink-target")
    linked_manifest = tmp_path / "manifest-link.json"
    linked_manifest.symlink_to(manifest)
    result = evaluate_vendor_sample("market_data", linked_manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "manifest.json" for item in result.findings)

    linked_license = tmp_path / "license-link.json"
    linked_license.symlink_to(license_path)
    result = evaluate_vendor_sample("market_data", manifest, linked_license)
    assert result.technical_pass
    assert not result.licensing_pass
    assert any(item.code == "licensing.json" for item in result.findings)


def test_exact_market_schema_counts_and_safe_identity_fail_closed(tmp_path: Path) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["unexpected_field"] = "schema drift"
    payload["page_count"] = True
    payload["page_record_counts"] = [3]
    payload["delivered_record_count"] = 4
    payload["delivery_id"] = "/tmp/machine-local-delivery"
    write_json(manifest, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    codes = {item.code for item in result.findings}
    assert not result.technical_pass
    assert {
        "manifest.schema",
        "market.page_count",
        "market.delivery_count_reconciliation",
        "manifest.delivery_id.format",
    }.issubset(codes)

    manifest, license_path = market_sample(tmp_path / "columns")
    bars_path = manifest.parent / "bars.csv"
    bars = pd.read_csv(bars_path)
    bars["vendor_extra"] = "not-versioned"
    bars.to_csv(bars_path, index=False)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["source_sha256"]["bars"] = file_sha256(bars_path)
    write_json(manifest, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    assert not result.technical_pass
    assert any(item.code == "market.schema" for item in result.findings)


def test_reference_naive_stale_extra_scope_and_source_fail_closed(tmp_path: Path) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")

    def corrupt(universe: pd.DataFrame) -> None:
        universe.loc[0, "as_of_timestamp"] = "2024-06-02 13:00:00"
        extra = universe.iloc[0].copy()
        extra["stable_identifier"] = "FIGI-EXTRA"
        extra["symbol"] = "EXTRA"
        extra["source"] = "contradictory_vendor"
        universe.loc[len(universe)] = extra

    rewrite_reference_file(manifest, "universe", corrupt)
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    codes = {item.code for item in result.findings}
    assert not result.technical_pass
    assert "reference.universe.as_of_timestamp.timezone" in codes
    assert "reference.universe_date" in codes
    assert "reference.universe.source_identity" in codes
    assert "reference.universe_count" in codes


def test_reference_order_duplicates_identity_and_intervals_fail_closed(
    tmp_path: Path,
) -> None:
    manifest, license_path = reference_sample(tmp_path / "reference")

    def duplicate_listing(listings: pd.DataFrame) -> None:
        listings.loc[len(listings)] = listings.iloc[0]

    rewrite_reference_file(manifest, "listings", duplicate_listing)

    def contradict_action(actions: pd.DataFrame) -> None:
        actions.loc[0, "symbol"] = "WRONG"
        actions.loc[0, "coverage_end_timestamp"] = actions.loc[
            0, "coverage_start_timestamp"
        ]

    rewrite_reference_file(manifest, "corporate_actions", contradict_action)
    result = evaluate_vendor_sample("reference_data", manifest, license_path)
    codes = {item.code for item in result.findings}
    assert not result.technical_pass
    assert "reference.listings.duplicates" in codes
    assert "reference.listings.overlap" in codes
    assert "reference.actions.coverage_interval" in codes
    assert "reference.actions.coverage_bounds" in codes
    assert "reference.actions.symbol_identity" in codes


def test_licensing_schema_placeholders_and_report_root_symlink_fail_closed(
    tmp_path: Path,
) -> None:
    manifest, license_path = market_sample(tmp_path / "market")
    payload = json.loads(license_path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    payload["rights"]["internal_research"]["unexpected"] = "drift"
    payload["rights"]["raw_storage"]["evidence_reference"] = "replace_with_evidence"
    write_json(license_path, payload)
    result = evaluate_vendor_sample("market_data", manifest, license_path)
    codes = {item.code for item in result.findings}
    assert result.technical_pass
    assert not result.licensing_pass
    assert "licensing.schema" in codes
    assert "licensing.rights.internal_research.schema" in codes
    assert "licensing.rights.raw_storage.evidence_reference" in codes

    real_output = tmp_path / "real-output"
    real_output.mkdir()
    linked_output = tmp_path / "linked-output"
    linked_output.symlink_to(real_output, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        write_acceptance_report(result, linked_output)
