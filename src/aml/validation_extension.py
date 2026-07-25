"""Frozen preregistration controls for the V0.1.1 validation extension."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


VALIDATION_EXTENSION_VERSION = "aml.v011-validation-extension.v001"
EXTENSION_START = date(2026, 7, 27)
EXTENSION_END = date(2028, 7, 26)
FROZEN_STRATEGY_ID = "attention_momentum"
FROZEN_STRATEGY_VERSION = "0.1.1"
FROZEN_UNIVERSE = (
    "SPY", "QQQ", "IWM", "DIA", "TQQQ", "SQQQ", "SPXL", "SPXS",
    "GLD", "SLV", "USO", "TLT", "XLF", "XLK", "XLE", "UVXY",
    "GME", "AMC", "AAPL", "TSLA", "NVDA", "AMD", "PLTR",
)
CHECKPOINTS = (250, 500, 1_000)
BASELINE_ACCEPTED_TRADES = 214


@dataclass(frozen=True)
class ValidationExtensionBoundary:
    start: date = EXTENSION_START
    end: date = EXTENSION_END
    strategy_id: str = FROZEN_STRATEGY_ID
    strategy_version: str = FROZEN_STRATEGY_VERSION

    def __post_init__(self) -> None:
        if self.start != EXTENSION_START or self.end != EXTENSION_END:
            raise ValueError("Validation-extension boundaries are preregistered and immutable")
        if self.strategy_id != FROZEN_STRATEGY_ID:
            raise ValueError("Validation extension requires frozen attention_momentum")
        if self.strategy_version != FROZEN_STRATEGY_VERSION:
            raise ValueError("Validation extension requires Strategy V0.1.1")


def validate_extension_request(
    start: date, end: date, symbols: tuple[str, ...]
) -> ValidationExtensionBoundary:
    """Reject boundary or universe changes before reading any market data."""
    boundary = ValidationExtensionBoundary(start=start, end=end)
    normalized = tuple(str(symbol).upper() for symbol in symbols)
    if normalized != FROZEN_UNIVERSE:
        raise ValueError("Validation-extension universe cannot be changed or reordered")
    return boundary


def validate_extension_input_path(path: Path) -> Path:
    """Reject protected, traversing, or symlinked paths before data access."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise ValueError("Path traversal is prohibited")
    protected = {"holdout", "sealed-holdout", "holdout-results", "holdout-artifacts"}
    if any(part.casefold().replace("_", "-") in protected for part in candidate.parts):
        raise ValueError("Holdout paths are sealed and prohibited")
    absolute = Path(candidate.absolute())
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("Symlinked extension inputs are prohibited")
    return absolute


def validate_reference_record(record: dict[str, object]) -> None:
    """Fail closed on unavailable, stale, malformed, or incomplete reference data."""
    required = {
        "symbol", "trading_date", "listing_status", "listing_effective_at",
        "symbol_history_status", "corporate_action_status", "source_as_of",
        "source_sha256",
    }
    if set(record) != required:
        raise ValueError("Reference record schema is incomplete or contains unknown fields")
    if record["listing_status"] != "active":
        raise ValueError("Symbol was not point-in-time active")
    if record["symbol_history_status"] != "verified":
        raise ValueError("Symbol history is unavailable or malformed")
    if record["corporate_action_status"] not in {"none", "verified"}:
        raise ValueError("Corporate-action reference data is unavailable or malformed")
    source_hash = record["source_sha256"]
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("Reference source hash is malformed")
