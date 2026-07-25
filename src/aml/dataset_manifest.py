"""Versioned, path-independent manifests for segmented research datasets."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from aml.market_backfill import load_universe, universe_sha256


SCHEMA_VERSION = "aml.dataset-manifest.v1"
SEGMENTS = ("premarket", "regular")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path, *, count_csv_rows: bool = False) -> tuple[str, int, int | None]:
    digest = hashlib.sha256()
    size = 0
    newline_count = 0
    last_byte = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            if count_csv_rows:
                newline_count += chunk.count(b"\n")
                last_byte = chunk[-1:]
    if not count_csv_rows:
        return digest.hexdigest(), size, None
    line_count = newline_count + (1 if size and last_byte != b"\n" else 0)
    return digest.hexdigest(), size, max(0, line_count - 1)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unreadable JSON metadata: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Metadata must be a JSON object: {path}")
    return value


def _partition_record(relative_path: Path, digest: str, size: int, rows: int | None = None) -> dict:
    record = {"path": relative_path.as_posix(), "sha256": digest, "bytes": size}
    if rows is not None:
        record["rows"] = rows
    return record


def _symbol_partition(dataset_root: Path, symbol: str, dates: tuple[str, ...], feed: str) -> dict:
    partition_records = []
    rows = {segment: 0 for segment in SEGMENTS}
    validation = {
        "successful_segments": 0,
        "missing_minute_count": 0,
        "segments_with_missing_minutes": 0,
        "duplicate_timestamp_count": 0,
        "out_of_order_segment_count": 0,
        "cross_date_bar_count": 0,
        "outside_requested_window_count": 0,
        "unexpected_1600_bar_count": 0,
        "provider_feed_echoed_segment_count": 0,
        "provider_feed_not_echoed_segment_count": 0,
    }
    validation_by_segment = {
        segment: {
            "successful_segment_count": 0,
            "processed_row_count": 0,
            "missing_minute_count": 0,
            "segments_with_missing_minutes": 0,
        }
        for segment in SEGMENTS
    }
    acquired_at = []

    for trading_date in dates:
        day_root = dataset_root / feed / symbol / trading_date
        for segment in SEGMENTS:
            raw = day_root / "raw" / f"{segment}_provider_response.json"
            processed = day_root / "processed" / f"{segment}_1min.csv"
            metadata_path = day_root / "metadata" / f"{segment}_acquisition.json"
            missing = [path for path in (raw, processed, metadata_path) if not path.is_file()]
            if missing:
                raise RuntimeError(f"Incomplete partition for {symbol} {trading_date} {segment}")

            metadata = _load_json(metadata_path)
            identity = {
                "status": "success", "provider": "alpaca", "requested_feed": feed,
                "timeframe": "1Min", "dataset_vintage": dataset_root.name,
                "symbol": symbol, "trading_date": trading_date, "segment": segment,
            }
            for field, expected in identity.items():
                if metadata.get(field) != expected:
                    raise RuntimeError(
                        f"Metadata identity mismatch for {symbol} {trading_date} {segment}: {field}"
                    )

            raw_hash, raw_size, _ = _sha256_file(raw)
            processed_hash, processed_size, processed_rows = _sha256_file(
                processed, count_csv_rows=True
            )
            metadata_hash, metadata_size, _ = _sha256_file(metadata_path)
            if raw_hash != metadata.get("raw_response_sha256"):
                raise RuntimeError(f"Raw file hash mismatch: {raw}")
            if processed_hash != metadata.get("processed_sha256"):
                raise RuntimeError(f"Processed file hash mismatch: {processed}")
            if processed_rows != metadata.get("record_count"):
                raise RuntimeError(f"Processed row count mismatch: {processed}")

            normalization = metadata.get("normalization") or {}
            if processed_rows != normalization.get("output_record_count"):
                raise RuntimeError(f"Normalization row count mismatch: {metadata_path}")
            if normalization.get("duplicate_timestamp_count") != 0:
                raise RuntimeError(f"Duplicate timestamps are not manifestable: {metadata_path}")
            if normalization.get("out_of_order") is not False:
                raise RuntimeError(f"Out-of-order timestamps are not manifestable: {metadata_path}")
            if normalization.get("cross_date_bar_count") != 0:
                raise RuntimeError(f"Cross-date bars are not manifestable: {metadata_path}")

            relative_base = day_root.relative_to(dataset_root)
            partition_records.extend((
                _partition_record(relative_base / "raw" / raw.name, raw_hash, raw_size),
                _partition_record(
                    relative_base / "processed" / processed.name,
                    processed_hash, processed_size, processed_rows,
                ),
                _partition_record(
                    relative_base / "metadata" / metadata_path.name,
                    metadata_hash, metadata_size,
                ),
            ))
            rows[segment] += processed_rows
            validation["successful_segments"] += 1
            missing_minutes = int(normalization.get("missing_timestamp_count", 0))
            validation["missing_minute_count"] += missing_minutes
            validation["segments_with_missing_minutes"] += int(missing_minutes > 0)
            validation["outside_requested_window_count"] += int(
                normalization.get("outside_requested_window_count", 0)
            )
            validation["unexpected_1600_bar_count"] += int(
                normalization.get("unexpected_1600_bar_count", 0)
            )
            segment_validation = validation_by_segment[segment]
            segment_validation["successful_segment_count"] += 1
            segment_validation["processed_row_count"] += processed_rows
            segment_validation["missing_minute_count"] += missing_minutes
            segment_validation["segments_with_missing_minutes"] += int(missing_minutes > 0)
            if metadata.get("actual_feed") == feed:
                validation["provider_feed_echoed_segment_count"] += 1
            else:
                evidence = metadata.get("actual_feed_evidence")
                if metadata.get("actual_feed") is not None or evidence != (
                    "explicit_request_parameter_provider_did_not_echo_feed"
                ):
                    raise RuntimeError(f"Ambiguous feed evidence: {metadata_path}")
                validation["provider_feed_not_echoed_segment_count"] += 1
            acquired_at.append(str(metadata["acquisition_timestamp"]))

    partition_records.sort(key=lambda item: item["path"])
    partition_hash = hashlib.sha256(b"\n".join(_canonical(row) for row in partition_records)).hexdigest()
    return {
        "symbol": symbol,
        "trading_session_count": len(dates),
        "rows": {**rows, "total": sum(rows.values())},
        "file_count": len(partition_records),
        "partition_sha256": partition_hash,
        "validation": validation,
        "validation_by_segment": validation_by_segment,
        "download_started_at": min(acquired_at),
        "download_completed_at": max(acquired_at),
    }


def build_dataset_manifest(
    root: Path,
    *,
    dataset_vintage: str,
    universe_path: Path,
    source_commit: str,
    repository: str,
    start: str,
    end: str,
    subscription_plan: str,
    subscription_price_usd_per_month: int,
    generated_at: str | None = None,
    workers: int = 4,
) -> dict:
    """Verify every immutable partition and return a path-independent manifest."""
    if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit):
        raise ValueError("source_commit must be a full lowercase Git commit SHA")
    if workers < 1:
        raise ValueError("workers must be positive")
    root = Path(root).resolve()
    dataset_root = root / "data" / "research" / dataset_vintage
    instruments = load_universe(universe_path)
    symbols = tuple(instrument.symbol for instrument in instruments)
    feed = "sip"
    symbol_dates = {}
    for symbol in symbols:
        symbol_root = dataset_root / feed / symbol
        dates = tuple(sorted(path.name for path in symbol_root.iterdir() if path.is_dir()))
        if not dates:
            raise RuntimeError(f"No dataset partitions found for {symbol}")
        symbol_dates[symbol] = dates
    reference_dates = symbol_dates[symbols[0]]
    if reference_dates[0] != start or reference_dates[-1] != end:
        raise RuntimeError("Dataset date bounds do not match the requested manifest bounds")
    for symbol, dates in symbol_dates.items():
        if dates != reference_dates:
            raise RuntimeError(f"Trading-session coverage differs for {symbol}")

    with ThreadPoolExecutor(max_workers=min(workers, len(symbols))) as executor:
        futures = {
            symbol: executor.submit(_symbol_partition, dataset_root, symbol, reference_dates, feed)
            for symbol in symbols
        }
        partitions = [futures[symbol].result() for symbol in symbols]

    total_validation = {
        key: sum(partition["validation"][key] for partition in partitions)
        for key in partitions[0]["validation"]
    }
    total_validation_by_segment = {
        segment: {
            key: sum(
                partition["validation_by_segment"][segment][key]
                for partition in partitions
            )
            for key in partitions[0]["validation_by_segment"][segment]
        }
        for segment in SEGMENTS
    }
    total_processed_rows = sum(partition["rows"]["total"] for partition in partitions)
    dataset_fingerprint = hashlib.sha256(_canonical([
        {"symbol": partition["symbol"], "partition_sha256": partition["partition_sha256"]}
        for partition in partitions
    ])).hexdigest()
    archived_failure_files = sum(
        1 for path in dataset_root.rglob("*")
        if path.is_file() and "failed_attempts" in path.parts
    )
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_vintage": dataset_vintage,
        "dataset_fingerprint_sha256": dataset_fingerprint,
        "manifest_generated_at": generated_at,
        "coverage": {
            "symbols": list(symbols),
            "symbol_count": len(symbols),
            "start_date": start,
            "end_date": end,
            "trading_session_count": len(reference_dates),
            "symbol_day_count": len(symbols) * len(reference_dates),
            "processed_row_count": total_processed_rows,
            "feed": feed,
            "timeframe": "1Min",
            "calendar": "XNYS",
            "timezone": "America/New_York",
            "sessions": [
                {"name": "premarket", "window": "[04:00,09:25)", "boundary_basis": "America/New_York"},
                {"name": "regular", "window": "[XNYS open,XNYS close)", "boundary_basis": "authoritative exchange calendar"},
            ],
        },
        "source": {
            "provider": "Alpaca Markets",
            "endpoint": "https://data.alpaca.markets/v2/stocks/{symbol}/bars",
            "requested_feed": feed,
            "adjustment": "all",
            "subscription": {
                "plan": subscription_plan,
                "price_usd_per_month": subscription_price_usd_per_month,
                "provenance": "user-reported subscription; entitlement validated by successful authenticated requests",
            },
            "feed_evidence": (
                "Every request explicitly selected SIP. Alpaca did not echo the feed in these responses, "
                "so actual_feed remains null rather than being inferred."
            ),
        },
        "software": {
            "repository": repository,
            "downloader_commit": source_commit,
            "commit_published": True,
        },
        "universe": {
            "file": universe_path.resolve().relative_to(root).as_posix(),
            "sha256": universe_sha256(universe_path),
        },
        "download": {
            "started_at": min(partition["download_started_at"] for partition in partitions),
            "completed_at": max(partition["download_completed_at"] for partition in partitions),
        },
        "validation": {
            "status": "passed",
            "file_hashes_verified": True,
            "processed_row_counts_verified": True,
            "active_failure_count": 0,
            "archived_failure_file_count": archived_failure_files,
            "verified_file_count": sum(partition["file_count"] for partition in partitions),
            "by_segment": total_validation_by_segment,
            **total_validation,
        },
        "partition_hash": {
            "algorithm": "sha256",
            "definition": (
                "SHA-256 of sorted canonical JSON records containing each partition-relative file path, "
                "actual file SHA-256, byte count, and processed CSV row count"
            ),
        },
        "partitions": partitions,
    }


def write_manifest(path: Path, manifest: dict) -> None:
    """Write the final manifest atomically with stable JSON formatting."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
