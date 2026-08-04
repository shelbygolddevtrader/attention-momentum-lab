from __future__ import annotations

import copy
from pathlib import Path

import pytest

from aml.benchmark_executable_specification_runtime_v001 import (
    ExecutableSpecificationRuntimeError,
    dataset_authorization_identity,
    file_hashes,
    validate_dataset_authorization,
)
from aml.benchmark_executable_specification_v001 import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/executable_specification_implementation_v001.json"


def _config():
    return load_config(CONFIG, repository_root=ROOT)


def test_dataset_authorization_is_exact_and_reproducible() -> None:
    binding = _config()["dataset_authorization"]
    projection = {
        key: binding[key] for key in sorted(set(binding) - {"authorization_identity"})
    }
    assert dataset_authorization_identity(projection) == binding["authorization_identity"]
    assert validate_dataset_authorization(binding, repository_root=ROOT) == binding


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_identity", "0" * 64),
        ("file_sha256", "0" * 64),
        ("scope", "historical_research"),
        ("evidence_class", "empirical"),
        ("relative_path", "../secret.csv"),
    ],
)
def test_dataset_authorization_tampering_fails_closed(field: str, value: str) -> None:
    binding = copy.deepcopy(_config()["dataset_authorization"])
    binding[field] = value
    with pytest.raises(ExecutableSpecificationRuntimeError):
        validate_dataset_authorization(binding, repository_root=ROOT)


def test_dataset_authorization_requires_all_protected_boundaries() -> None:
    binding = copy.deepcopy(_config()["dataset_authorization"])
    binding["prohibited_boundaries"].remove("holdout")
    projection = {
        key: binding[key] for key in sorted(set(binding) - {"authorization_identity"})
    }
    binding["authorization_identity"] = dataset_authorization_identity(projection)
    with pytest.raises(ExecutableSpecificationRuntimeError, match="protected boundary"):
        validate_dataset_authorization(binding, repository_root=ROOT)


def test_source_inventory_rejects_nondeterministic_order_and_symlink(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("a", encoding="utf-8")
    (tmp_path / "src/b.py").symlink_to(tmp_path / "src/a.py")
    with pytest.raises(ExecutableSpecificationRuntimeError, match="sorted"):
        file_hashes(tmp_path, ["src/b.py", "src/a.py"])
    with pytest.raises(ExecutableSpecificationRuntimeError, match="unsafe"):
        file_hashes(tmp_path, ["src/b.py"])
