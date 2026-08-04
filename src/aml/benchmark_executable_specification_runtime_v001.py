"""Reusable, non-empirical bindings for executable benchmark specifications.

This module supplies identity and conformance plumbing only.  Strategy semantics
remain owned by an explicitly bound frozen evaluator and lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any

from aml.benchmark_strategy_research_v001 import (
    canonical_hash,
    make_artifact,
    validate_artifact,
)


RUNTIME_VERSION = "benchmark-executable-specification-runtime-v001"
HASH = re.compile(r"^[0-9a-f]{64}$")


class ExecutableSpecificationRuntimeError(ValueError):
    """A binding, dataset authorization, or conformance invariant failed."""


@dataclass(frozen=True, slots=True)
class ConformanceCase:
    """One deterministic case against an already-frozen evaluator."""

    case_id: str
    expected_status: str
    evaluate: Callable[[], Any]
    expected_exception_types: tuple[type[Exception], ...] = ()


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ExecutableSpecificationRuntimeError(
            f"{field} must be a lowercase SHA-256 identity"
        )
    return value


def file_hashes(repository_root: Path, paths: Sequence[str]) -> dict[str, str]:
    """Hash a sorted, unique inventory without following symlinks."""

    root = Path(repository_root).resolve()
    if not paths or list(paths) != sorted(set(paths)):
        raise ExecutableSpecificationRuntimeError(
            "source inventory must be non-empty, unique, and sorted"
        )
    result: dict[str, str] = {}
    for relative in paths:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ExecutableSpecificationRuntimeError("source path is unsafe")
        path = root / candidate
        if not path.is_file() or path.is_symlink():
            raise ExecutableSpecificationRuntimeError(
                f"source path is missing or unsafe:{relative}"
            )
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def dataset_authorization_identity(binding: Mapping[str, object]) -> str:
    """Identity for a prospective, claim-limited dataset authorization."""

    return canonical_hash(
        {
            "domain": "aml.benchmark-dataset-authorization.v001",
            "binding": dict(binding),
        }
    )


def validate_dataset_authorization(
    binding: Mapping[str, object],
    *,
    repository_root: Path,
) -> dict[str, object]:
    required = {
        "authorization_id",
        "dataset_identity",
        "evidence_class",
        "file_sha256",
        "prohibited_boundaries",
        "relative_path",
        "scope",
        "authorization_identity",
    }
    if not isinstance(binding, Mapping) or set(binding) != required:
        raise ExecutableSpecificationRuntimeError(
            "dataset authorization schema is invalid"
        )
    for field in ("dataset_identity", "file_sha256", "authorization_identity"):
        _identity(binding[field], field)
    path = Path(str(binding["relative_path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ExecutableSpecificationRuntimeError("dataset path is unsafe")
    resolved = Path(repository_root).resolve() / path
    if not resolved.is_file() or resolved.is_symlink():
        raise ExecutableSpecificationRuntimeError("authorized dataset is unavailable")
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != binding["file_sha256"]:
        raise ExecutableSpecificationRuntimeError("authorized dataset bytes changed")
    if binding["evidence_class"] != "synthetic_non_empirical":
        raise ExecutableSpecificationRuntimeError("dataset is not non-empirical")
    if binding["scope"] != "discovery_pipeline_conformance_only":
        raise ExecutableSpecificationRuntimeError("dataset scope is not permitted")
    boundaries = binding["prohibited_boundaries"]
    required_boundaries = {
        "forward validation",
        "holdout",
        "live trading",
        "olympics execution",
        "paper trading",
        "validation",
    }
    if (
        not isinstance(boundaries, list)
        or boundaries != sorted(set(boundaries))
        or not required_boundaries.issubset(set(boundaries))
    ):
        raise ExecutableSpecificationRuntimeError(
            "dataset authorization omits a protected boundary"
        )
    projection = {
        key: binding[key] for key in sorted(required - {"authorization_identity"})
    }
    if binding["authorization_identity"] != dataset_authorization_identity(projection):
        raise ExecutableSpecificationRuntimeError(
            "dataset authorization identity is stale or tampered"
        )
    return dict(binding)


def implementation_binding_artifact(
    *,
    repository_root: Path,
    preregistration: Mapping[str, object],
    specification: Mapping[str, object],
    implementation_callable: str,
    reference_contract: Mapping[str, object],
    source_paths: Sequence[str],
    dataset_authorization: Mapping[str, object],
) -> dict[str, object]:
    """Create one Framework V001 binding without changing the framework."""

    validate_artifact(preregistration, "preregistration")
    validate_artifact(specification, "specification")
    validated_dataset = validate_dataset_authorization(
        dataset_authorization, repository_root=repository_root
    )
    payload = {
        "runtime_version": RUNTIME_VERSION,
        "preregistration_identity": preregistration["identity"],
        "specification_identity": specification["identity"],
        "implementation_callable": implementation_callable,
        "reference_contract": dict(reference_contract),
        "dataset_authorization_identity": validated_dataset["authorization_identity"],
        "dataset_identity": validated_dataset["dataset_identity"],
        "source_sha256": file_hashes(repository_root, source_paths),
        "frozen_downstream_modified": False,
    }
    return make_artifact(
        "implementation_binding",
        payload,
        parent_identities=(
            preregistration["identity"],
            specification["identity"],
        ),
    )


def verify_implementation_binding(
    binding: Mapping[str, object],
    *,
    repository_root: Path,
    source_paths: Sequence[str],
    dataset_authorization: Mapping[str, object],
) -> dict[str, object]:
    value = validate_artifact(binding, "implementation_binding")
    payload = value["payload"]
    if payload.get("runtime_version") != RUNTIME_VERSION:
        raise ExecutableSpecificationRuntimeError("binding runtime changed")
    if payload.get("source_sha256") != file_hashes(repository_root, source_paths):
        raise ExecutableSpecificationRuntimeError("bound implementation source changed")
    dataset = validate_dataset_authorization(
        dataset_authorization, repository_root=repository_root
    )
    if (
        payload.get("dataset_authorization_identity")
        != dataset["authorization_identity"]
        or payload.get("dataset_identity") != dataset["dataset_identity"]
        or payload.get("frozen_downstream_modified") is not False
    ):
        raise ExecutableSpecificationRuntimeError("binding authority changed")
    return value


def run_conformance(
    *,
    implementation_binding: Mapping[str, object],
    cases: Sequence[ConformanceCase],
    repeat_case_id: str,
    no_lookahead_check: Callable[[], bool],
    proposal_pipeline_check: Callable[[], bool],
) -> dict[str, object]:
    """Run generic status, determinism, causality, and pipeline checks."""

    validate_artifact(implementation_binding, "implementation_binding")
    if not cases or [case.case_id for case in cases] != sorted(
        {case.case_id for case in cases}
    ):
        raise ExecutableSpecificationRuntimeError(
            "conformance cases must be unique and sorted"
        )
    results: list[dict[str, object]] = []
    serialized: dict[str, bytes] = {}
    for case in cases:
        try:
            result = case.evaluate()
            status = getattr(result, "status", None)
            if status != case.expected_status:
                raise ExecutableSpecificationRuntimeError(
                    f"conformance status changed:{case.case_id}"
                )
            payload = result.canonical_bytes()
            serialized[case.case_id] = payload
            results.append(
                {
                    "case_id": case.case_id,
                    "expected_status": case.expected_status,
                    "observed_status": status,
                    "output_sha256": hashlib.sha256(payload).hexdigest(),
                    "passed": True,
                }
            )
        except Exception as exc:
            if (
                case.expected_status != "integrity_failure"
                or not case.expected_exception_types
                or not isinstance(exc, case.expected_exception_types)
            ):
                raise ExecutableSpecificationRuntimeError(
                    f"unexpected conformance exception:{case.case_id}:"
                    f"{type(exc).__name__}"
                ) from exc
            results.append(
                {
                    "case_id": case.case_id,
                    "expected_status": "integrity_failure",
                    "observed_status": "integrity_failure",
                    "exception_type": type(exc).__name__,
                    "passed": True,
                }
            )
    repeated = next(case for case in cases if case.case_id == repeat_case_id).evaluate()
    if repeated.canonical_bytes() != serialized[repeat_case_id]:
        raise ExecutableSpecificationRuntimeError("conformance is nondeterministic")
    if not no_lookahead_check():
        raise ExecutableSpecificationRuntimeError("no-lookahead conformance failed")
    if not proposal_pipeline_check():
        raise ExecutableSpecificationRuntimeError("proposal pipeline conformance failed")
    return make_artifact(
        "conformance",
        {
            "runtime_version": RUNTIME_VERSION,
            "implementation_binding_identity": implementation_binding["identity"],
            "cases": results,
            "deterministic_repeat": True,
            "no_lookahead": True,
            "proposal_pipeline": True,
            "all_checks_passed": True,
        },
        parent_identities=(implementation_binding["identity"],),
    )
