from datetime import date
from pathlib import Path

import pytest

from aml.validation_extension import (
    EXTENSION_END,
    EXTENSION_START,
    FROZEN_UNIVERSE,
    ValidationExtensionBoundary,
    validate_extension_input_path,
    validate_extension_request,
    validate_reference_record,
)


def test_exact_preregistered_boundaries_and_universe_are_enforced():
    assert validate_extension_request(
        EXTENSION_START, EXTENSION_END, FROZEN_UNIVERSE
    ) == ValidationExtensionBoundary()
    with pytest.raises(ValueError, match="boundaries"):
        validate_extension_request(
            date(2026, 7, 28), EXTENSION_END, FROZEN_UNIVERSE
        )
    with pytest.raises(ValueError, match="universe"):
        validate_extension_request(
            EXTENSION_START, EXTENSION_END, FROZEN_UNIVERSE[:-1]
        )


def test_holdout_traversal_and_symlink_paths_are_rejected(tmp_path):
    for path in (Path("sealed-holdout/results.csv"), Path("a/../b")):
        with pytest.raises(ValueError, match="Holdout|traversal"):
            validate_extension_input_path(path)
    source = tmp_path / "source"
    source.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="Symlinked"):
        validate_extension_input_path(link / "bars.csv")


def test_reference_data_fails_closed_and_schema_is_exact():
    valid = {
        "symbol": "AAPL",
        "trading_date": "2026-07-27",
        "listing_status": "active",
        "listing_effective_at": "1980-12-12T00:00:00Z",
        "symbol_history_status": "verified",
        "corporate_action_status": "none",
        "source_as_of": "2026-07-27T13:29:59Z",
        "source_sha256": "a" * 64,
    }
    validate_reference_record(valid)
    with pytest.raises(ValueError, match="schema"):
        validate_reference_record({**valid, "unknown": True})
    with pytest.raises(ValueError, match="point-in-time active"):
        validate_reference_record({**valid, "listing_status": "unknown"})
    with pytest.raises(ValueError, match="Corporate-action"):
        validate_reference_record({**valid, "corporate_action_status": "stale"})
