import hashlib
import json
from pathlib import Path

import pytest

from aml.tournament_analysis_artifacts import (
    AnalysisProvenance,
    load_tournament_analysis,
    publish_tournament_analysis,
    verify_finalized_tournament,
)
from scripts.run_portfolio_dashboard import load_persisted_analysis_view


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finalized(root: Path, run_id: str = "run-001") -> tuple[Path, bytes]:
    final = root / run_id / "final"
    final.mkdir(parents=True)
    source = b"strategy_id,split,net_pnl\nattention_momentum,validation,1.0\n"
    (final / "trades.csv").write_bytes(source)
    manifest = {
        "run_id": run_id,
        "status": "completed",
        "artifact_hashes": {"trades.csv": _sha(source)},
        "source_commit": "a" * 40,
        "source_worktree_dirty": False,
    }
    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    (final / "run_manifest.json").write_bytes(manifest_bytes)
    return final, manifest_bytes


def _provenance() -> AnalysisProvenance:
    return AnalysisProvenance(
        analysis_name="attention-audit",
        analysis_version="1.0.0",
        source_commit="b" * 40,
        source_worktree_dirty=False,
        source_worktree_fingerprint="c" * 64,
        deterministic_configuration={"calendar": "trading_date", "seed": 7},
    )


def test_analysis_is_separate_write_once_and_original_manifest_is_unchanged(tmp_path):
    final, original_manifest = _finalized(tmp_path)
    original_trade = (final / "trades.csv").read_bytes()
    first = publish_tournament_analysis(
        tmp_path, "run-001", _provenance(),
        {"trades.csv": b"derived,not,source\n", "review.md": b"review\n"},
    )
    second = publish_tournament_analysis(
        tmp_path, "run-001", _provenance(),
        {"trades.csv": b"derived,not,source\n", "review.md": b"review\n"},
    )
    assert first.analysis_id == second.analysis_id
    assert first.directory == second.directory
    assert first.directory.parent.name == "analysis"
    assert first.directory != final
    assert (final / "trades.csv").read_bytes() == original_trade
    assert (final / "run_manifest.json").read_bytes() == original_manifest
    assert load_tournament_analysis(first.directory)["review.md"] == b"review\n"


def test_source_hash_mismatch_fails_closed_without_analysis_output(tmp_path):
    final, _ = _finalized(tmp_path)
    (final / "trades.csv").write_text("mutated\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        publish_tournament_analysis(
            tmp_path, "run-001", _provenance(), {"review.md": b"review\n"}
        )
    assert not (tmp_path / "run-001" / "analysis").exists()


def test_existing_analysis_bytes_cannot_be_overwritten(tmp_path):
    _finalized(tmp_path)
    first = publish_tournament_analysis(
        tmp_path, "run-001", _provenance(), {"review.md": b"review\n"}
    )
    (first.directory / "review.md").write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        publish_tournament_analysis(
            tmp_path, "run-001", _provenance(), {"review.md": b"review\n"}
        )


def test_traversal_holdout_and_symlink_components_are_rejected(tmp_path):
    _finalized(tmp_path)
    for unsafe in ("../run-001", "sealed-holdout", "a/b"):
        with pytest.raises(ValueError, match="[Uu]nsafe|Protected"):
            verify_finalized_tournament(tmp_path, unsafe)
    link = tmp_path / "linked-run"
    try:
        link.symlink_to(tmp_path / "run-001", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="Symlinked|unsafe"):
        verify_finalized_tournament(tmp_path, "linked-run")


def test_generated_names_and_analysis_identity_are_strict(tmp_path):
    _finalized(tmp_path)
    with pytest.raises(ValueError, match="Unsafe"):
        publish_tournament_analysis(
            tmp_path, "run-001", _provenance(), {"../review.md": b"review\n"}
        )
    changed = AnalysisProvenance(
        analysis_name="attention-audit",
        analysis_version="1.0.1",
        source_commit="b" * 40,
        source_worktree_dirty=False,
        source_worktree_fingerprint="c" * 64,
        deterministic_configuration={"calendar": "trading_date", "seed": 7},
    )
    one = publish_tournament_analysis(
        tmp_path, "run-001", _provenance(), {"review.md": b"review\n"}
    )
    two = publish_tournament_analysis(
        tmp_path, "run-001", changed, {"review.md": b"review\n"}
    )
    assert one.analysis_id != two.analysis_id


def test_dashboard_loads_persisted_analysis_without_recalculation(tmp_path):
    _finalized(tmp_path)
    published = publish_tournament_analysis(
        tmp_path, "run-001", _provenance(),
        {
            "table.csv": b"symbol,value\nAAA,1\n",
            "summary.json": b'{"passed":true}\n',
            "review.md": b"# Review\n",
        },
    )
    view = load_persisted_analysis_view(published.directory)
    assert view["table.csv"].to_dict("records") == [{"symbol": "AAA", "value": 1}]
    assert view["summary.json"] == {"passed": True}
    assert view["review.md"] == "# Review\n"
