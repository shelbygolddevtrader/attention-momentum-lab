"""Fail-closed point-in-time reference-data contracts for cohort selection."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd


SCHEMAS = {
    "universe": (
        "as_of_timestamp", "symbol", "security_type", "exchange", "calendar_id",
        "active", "source", "dataset_vintage",
    ),
    "listings": (
        "symbol", "listing_start_timestamp", "listing_end_timestamp", "exchange",
        "calendar_id", "known_at_timestamp", "source", "dataset_vintage",
    ),
    "corporate_actions": (
        "symbol", "record_type", "coverage_start_timestamp", "coverage_end_timestamp",
        "effective_timestamp", "action_type", "adjustment_factor",
        "known_at_timestamp", "source", "dataset_vintage",
    ),
    "symbol_continuity": (
        "canonical_symbol", "historical_symbol", "effective_start_timestamp",
        "effective_end_timestamp", "known_at_timestamp", "source", "dataset_vintage",
    ),
}


class ReferenceDataError(ValueError):
    """Raised when point-in-time reference data is absent or unverifiable."""


class PointInTimeReferenceData(Protocol):
    """Provider contract for locally reproducible point-in-time reference data."""

    def universe(self, trading_date: date) -> pd.DataFrame: ...
    def listings(self) -> pd.DataFrame: ...
    def corporate_actions(self) -> pd.DataFrame: ...
    def symbol_continuity(self) -> pd.DataFrame: ...


def _load_schema(
    path: Path,
    schema: str,
    approved_sources: frozenset[str],
) -> pd.DataFrame:
    if not path.exists():
        raise ReferenceDataError(f"Missing required {schema} reference data: {path}")
    frame = pd.read_csv(path)
    required = set(SCHEMAS[schema])
    if missing := required.difference(frame.columns):
        raise ReferenceDataError(
            f"Missing {schema} columns: {', '.join(sorted(missing))}"
        )
    result = frame.loc[:, SCHEMAS[schema]].copy()
    source_values = result["source"].astype("string").str.strip()
    if source_values.isna().any() or source_values.eq("").any():
        raise ReferenceDataError(f"{schema} requires non-empty source provenance")
    if not approved_sources:
        raise ReferenceDataError(
            "No approved point-in-time reference-data sources are configured"
        )
    observed_sources = set(source_values)
    unapproved = observed_sources.difference(approved_sources)
    if unapproved:
        raise ReferenceDataError(
            f"Unapproved {schema} source: {', '.join(sorted(unapproved))}"
        )
    return result


@dataclass(frozen=True)
class LocalPointInTimeReferenceData:
    """Load local CSVs only from an explicitly approved source set."""

    root: Path
    approved_sources: frozenset[str] = frozenset()

    def universe(self, trading_date: date) -> pd.DataFrame:
        return _load_schema(
            Path(self.root) / "universe" / f"{trading_date}.csv",
            "universe",
            self.approved_sources,
        )

    def listings(self) -> pd.DataFrame:
        return _load_schema(
            Path(self.root) / "listings.csv", "listings", self.approved_sources
        )

    def corporate_actions(self) -> pd.DataFrame:
        return _load_schema(
            Path(self.root) / "corporate_actions.csv",
            "corporate_actions",
            self.approved_sources,
        )

    def symbol_continuity(self) -> pd.DataFrame:
        return _load_schema(
            Path(self.root) / "symbol_continuity.csv",
            "symbol_continuity",
            self.approved_sources,
        )


def _timestamps(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(result[column], utc=True, errors="coerce")
    return result


def _require_valid_timestamps(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    label: str,
) -> None:
    for column in columns:
        if frame[column].isna().any():
            raise ReferenceDataError(f"{label} contains invalid {column} values")


def _require_provenance(frame: pd.DataFrame, label: str) -> None:
    for column in ("source", "dataset_vintage"):
        values = frame[column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ReferenceDataError(f"{label} requires non-empty {column} provenance")


def _validate_intervals(
    frame: pd.DataFrame,
    start_column: str,
    end_column: str,
    label: str,
) -> None:
    invalid = frame[end_column].notna() & frame[end_column].le(frame[start_column])
    if invalid.any():
        raise ReferenceDataError(f"{label} contains an invalid effective interval")


def _active_interval(
    frame: pd.DataFrame,
    start_column: str,
    end_column: str,
    timestamp: pd.Timestamp,
) -> pd.DataFrame:
    start = frame[start_column].le(timestamp)
    end = frame[end_column].isna() | frame[end_column].gt(timestamp)
    return frame.loc[start & end]


def validate_reference_prerequisites(
    provider: PointInTimeReferenceData,
    symbol: str,
    selection_timestamp: pd.Timestamp | str,
) -> dict[str, object]:
    """Validate common-stock, listing, action, and symbol history as of cutoff.

    Every record must have been known before ``selection_timestamp``. The
    universe snapshot must be from the selection date, and listing lookup uses
    the historical ticker active at that instant.
    """
    symbol = symbol.upper()
    cutoff = pd.Timestamp(selection_timestamp)
    if cutoff.tzinfo is None:
        raise ReferenceDataError("selection_timestamp must be timezone-aware")
    cutoff_utc = cutoff.tz_convert("UTC")
    day = cutoff.tz_convert("America/New_York").date()

    universe = _timestamps(provider.universe(day), ("as_of_timestamp",))
    _require_valid_timestamps(universe, ("as_of_timestamp",), "Universe data")
    _require_provenance(universe, "Universe data")
    local_dates = universe["as_of_timestamp"].dt.tz_convert("America/New_York").dt.date
    if not local_dates.eq(day).all():
        raise ReferenceDataError("Universe snapshot contains a stale or cross-date record")
    universe = universe.loc[
        universe["symbol"].astype(str).str.upper().eq(symbol)
        & universe["as_of_timestamp"].lt(cutoff_utc)
    ].sort_values("as_of_timestamp")
    if universe.empty:
        raise ReferenceDataError(f"No point-in-time universe record for {symbol}")
    latest_as_of = universe["as_of_timestamp"].max()
    if universe["as_of_timestamp"].eq(latest_as_of).sum() != 1:
        raise ReferenceDataError(f"Point-in-time universe record is ambiguous for {symbol}")
    security = universe.iloc[-1]
    active = str(security["active"]).lower() in {"true", "1", "yes"}
    if (
        security["security_type"] != "common_stock"
        or not active
        or security["calendar_id"] != "XNYS"
    ):
        raise ReferenceDataError(
            f"{symbol} is not an active XNYS common stock at selection time"
        )

    continuity = _timestamps(
        provider.symbol_continuity(),
        (
            "effective_start_timestamp", "effective_end_timestamp",
            "known_at_timestamp",
        ),
    )
    _require_valid_timestamps(
        continuity,
        ("effective_start_timestamp", "known_at_timestamp"),
        "Symbol-continuity data",
    )
    _require_provenance(continuity, "Symbol-continuity data")
    _validate_intervals(
        continuity, "effective_start_timestamp", "effective_end_timestamp",
        "Symbol-continuity data",
    )
    continuity = continuity.loc[
        continuity["canonical_symbol"].astype(str).str.upper().eq(symbol)
        & continuity["known_at_timestamp"].lt(cutoff_utc)
    ]
    continuity = _active_interval(
        continuity, "effective_start_timestamp", "effective_end_timestamp", cutoff_utc
    )
    if len(continuity) != 1:
        raise ReferenceDataError(f"Symbol continuity is missing or ambiguous for {symbol}")
    historical_symbol = str(continuity.iloc[0]["historical_symbol"]).strip().upper()
    if not historical_symbol:
        raise ReferenceDataError(f"Symbol continuity lacks a historical symbol for {symbol}")

    listings = _timestamps(
        provider.listings(),
        ("listing_start_timestamp", "listing_end_timestamp", "known_at_timestamp"),
    )
    _require_valid_timestamps(
        listings, ("listing_start_timestamp", "known_at_timestamp"), "Listing data"
    )
    _require_provenance(listings, "Listing data")
    _validate_intervals(
        listings, "listing_start_timestamp", "listing_end_timestamp", "Listing data"
    )
    listings = listings.loc[
        listings["symbol"].astype(str).str.upper().eq(historical_symbol)
        & listings["known_at_timestamp"].lt(cutoff_utc)
    ]
    listings = _active_interval(
        listings, "listing_start_timestamp", "listing_end_timestamp", cutoff_utc
    )
    if len(listings) != 1 or listings.iloc[0]["calendar_id"] != "XNYS":
        raise ReferenceDataError(
            f"Listing history does not uniquely cover {historical_symbol} at selection time"
        )

    actions = _timestamps(
        provider.corporate_actions(),
        (
            "coverage_start_timestamp", "coverage_end_timestamp", "effective_timestamp",
            "known_at_timestamp",
        ),
    )
    _require_valid_timestamps(
        actions,
        ("coverage_start_timestamp", "coverage_end_timestamp", "known_at_timestamp"),
        "Corporate-action data",
    )
    _require_provenance(actions, "Corporate-action data")
    _validate_intervals(
        actions, "coverage_start_timestamp", "coverage_end_timestamp",
        "Corporate-action data",
    )
    actions = actions.loc[
        actions["symbol"].astype(str).str.upper().eq(historical_symbol)
        & actions["known_at_timestamp"].lt(cutoff_utc)
        & actions["coverage_start_timestamp"].le(cutoff_utc)
        & actions["coverage_end_timestamp"].gt(cutoff_utc)
    ]
    if actions.empty:
        raise ReferenceDataError(
            f"Corporate-action coverage is missing for {historical_symbol}"
        )
    if not actions["record_type"].isin({"action", "verified_none"}).all():
        raise ReferenceDataError("Corporate-action record_type must be action or verified_none")
    if actions["record_type"].nunique() != 1:
        raise ReferenceDataError(
            "Corporate-action coverage cannot mix verified_none and action records"
        )
    actual_actions = actions.loc[actions["record_type"].eq("action")]
    if not actual_actions.empty:
        factors = pd.to_numeric(actual_actions["adjustment_factor"], errors="coerce")
        action_types = actual_actions["action_type"].astype("string").str.strip()
        if (
            actual_actions["effective_timestamp"].isna().any()
            or action_types.isna().any()
            or action_types.eq("").any()
            or factors.isna().any()
            or factors.le(0).any()
        ):
            raise ReferenceDataError(
                "Corporate-action records require an effective time, type, and positive factor"
            )
    else:
        none_rows = actions.loc[actions["record_type"].eq("verified_none")]
        unexpected = (
            none_rows["effective_timestamp"].notna()
            | none_rows["action_type"].astype("string").fillna("").str.strip().ne("")
            | pd.to_numeric(none_rows["adjustment_factor"], errors="coerce").notna()
        )
        if unexpected.any():
            raise ReferenceDataError(
                "verified_none corporate-action records cannot describe an action"
            )

    action_sources = ";".join(sorted(actions["source"].astype(str).unique()))
    action_vintages = ";".join(
        sorted(actions["dataset_vintage"].astype(str).unique())
    )

    return {
        "symbol": symbol,
        "security_type": security["security_type"],
        "exchange": security["exchange"],
        "calendar_id": security["calendar_id"],
        "universe_source": security["source"],
        "dataset_vintage": security["dataset_vintage"],
        "historical_symbol": historical_symbol,
        "corporate_action_status": "verified",
        "corporate_action_source": action_sources,
        "corporate_action_dataset_vintage": action_vintages,
        "corporate_action_count": len(actual_actions),
    }


WARMUP_COLUMNS = (
    "symbol", "trading_date", "premarket_status", "regular_status",
    "adjustment_status", "reference_status",
)


def validate_warmup_sufficiency(
    inventory: pd.DataFrame,
    symbol: str,
    expected_dates: list[str] | tuple[str, ...] | pd.Index,
    *,
    required_session_count: int = 20,
) -> None:
    """Require exactly 20 distinct, verified prior sessions for each security."""
    if missing := set(WARMUP_COLUMNS).difference(inventory.columns):
        raise ReferenceDataError(f"Missing warm-up columns: {', '.join(sorted(missing))}")
    dates = [str(value) for value in expected_dates]
    if len(dates) != required_session_count or len(set(dates)) != required_session_count:
        raise ReferenceDataError(
            f"Exactly {required_session_count} distinct warm-up dates are required"
        )
    frame = inventory.loc[
        inventory["symbol"].astype(str).str.upper().eq(symbol.upper())
    ].copy()
    frame["trading_date"] = frame["trading_date"].astype(str)
    if frame["trading_date"].duplicated().any():
        raise ReferenceDataError("Duplicate warm-up inventory dates")
    frame = frame.set_index("trading_date").reindex(dates)
    if frame.isna().all(axis=1).any():
        missing_dates = frame.index[frame.isna().all(axis=1)].tolist()
        raise ReferenceDataError(f"Missing warm-up sessions: {', '.join(missing_dates)}")
    valid_premarket = frame["premarket_status"].isin({"complete", "verified_no_trades"})
    valid = (
        valid_premarket
        & frame["regular_status"].eq("complete")
        & frame["adjustment_status"].eq("verified")
        & frame["reference_status"].eq("verified")
    )
    if not valid.all():
        failed = frame.index[~valid].tolist()
        raise ReferenceDataError(f"Invalid warm-up sessions: {', '.join(failed)}")
