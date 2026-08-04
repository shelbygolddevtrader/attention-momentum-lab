"""Deterministic campaign routing for Benchmark Hypothesis Library V001.

The campaign owns no strategy, execution, classification, or scoring semantics.
It routes only explicitly authorized library entries to registered adapters and
verifies the complete Framework V001 bundle those adapters publish.  Entries
without an exact executable contract receive a canonical blocked result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from aml.benchmark_hypothesis_library_v001 import (
    LIBRARY_VERSION,
    HypothesisLibraryError,
    load_library,
    validate_library,
)
from aml.benchmark_strategy_research_v001 import (
    FRAMEWORK_VERSION,
    BenchmarkResearchError,
    canonical_hash,
    canonical_json,
    verify_bundle,
)

CAMPAIGN_SCHEMA = "aml.benchmark-discovery-campaign.v001"
CAMPAIGN_VERSION = "benchmark-discovery-campaign-v001"
CAMPAIGN_MANIFEST_SCHEMA = "aml.benchmark-discovery-campaign.manifest.v001"
RESULT_SCHEMA = "aml.benchmark-discovery-campaign.result.v001"
BLOCKED_CLASSIFICATION = "BLOCKED_NOT_EXECUTABLE"
HASH = re.compile(r"^[0-9a-f]{64}$")
GIT_OID = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
MAX_CONFIG_BYTES = 2_000_000
MAX_RESULT_BYTES = 4_000_000
MAX_CAMPAIGN_ENTRIES = 1_000

CONFIG_FIELDS = {
    "schema_version",
    "campaign_version",
    "campaign_id",
    "created_at",
    "framework_dependency",
    "library_dependency",
    "campaign_source_sha256",
    "policy",
    "authorized_executors",
    "campaign_identity",
}
EXECUTOR_FIELDS = {
    "library_entry_id",
    "framework_hypothesis_identity",
    "adapter_id",
    "adapter_version",
    "dataset_identity",
    "specification_identity",
    "preregistration_identity",
    "implementation_binding_identity",
    "conformance_identity",
    "source_sha256",
    "executor_identity",
}
POLICY_FIELDS = {
    "scope",
    "blocked_classification",
    "execution_authority",
    "failure_rule",
    "downstream_boundary",
    "evidence_claim",
    "protected_boundaries",
}
RESULT_FIELDS = {
    "schema_version",
    "campaign_identity",
    "library_entry_id",
    "registration_identity",
    "framework_hypothesis_identity",
    "status",
    "canonical_classification",
    "reason_codes",
    "execution_evidence",
    "result_identity",
}
BLOCKED_REASON_CODES = (
    "conformance_evidence_missing",
    "executable_specification_missing",
    "implementation_binding_missing",
    "permitted_discovery_dataset_missing",
    "registered_executor_missing",
)


class BenchmarkDiscoveryCampaignError(ValueError):
    """Campaign configuration, routing, evidence, or publication is invalid."""


@dataclass(frozen=True, slots=True)
class ExecutorRegistration:
    """Runtime implementation for one already-authorized executor contract.

    ``execute`` must publish a complete Framework V001 lifecycle bundle at the
    provided path.  The campaign independently verifies that bundle and every
    identity before accepting its evidence.
    """

    library_entry_id: str
    adapter_id: str
    adapter_version: str
    source_root: Path
    execute: Callable[[Path], None]


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkDiscoveryCampaignError(f"{field} must be a non-empty string")
    if len(value) > 20_000:
        raise BenchmarkDiscoveryCampaignError(f"{field} exceeds the size limit")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BenchmarkDiscoveryCampaignError(f"{field} contains invalid Unicode") from exc
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise BenchmarkDiscoveryCampaignError(f"{field} contains invalid Unicode")
    return value


def _identifier(value: object, field: str) -> str:
    result = _text(value, field)
    if not IDENTIFIER.fullmatch(result):
        raise BenchmarkDiscoveryCampaignError(f"{field} is malformed")
    return result


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise BenchmarkDiscoveryCampaignError(f"{field} must be a SHA-256 identity")
    return value


def _git_oid(value: object, field: str) -> str:
    if not isinstance(value, str) or not GIT_OID.fullmatch(value):
        raise BenchmarkDiscoveryCampaignError(f"{field} must be a full Git commit OID")
    return value


def _timestamp(value: object, field: str) -> str:
    result = _text(value, field)
    try:
        parsed = datetime.fromisoformat(result)
    except ValueError as exc:
        raise BenchmarkDiscoveryCampaignError(f"{field} is malformed") from exc
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
        or canonical != result
    ):
        raise BenchmarkDiscoveryCampaignError(f"{field} must use canonical UTC")
    return result


def _strict_json(path: Path, *, maximum_bytes: int) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise BenchmarkDiscoveryCampaignError("JSON contains duplicate keys")
            result[key] = item
        return result

    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum_bytes:
        raise BenchmarkDiscoveryCampaignError("JSON path is missing, unsafe, or oversized")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                BenchmarkDiscoveryCampaignError(f"non-finite JSON value: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkDiscoveryCampaignError("JSON is malformed") from exc
    if not isinstance(value, dict):
        raise BenchmarkDiscoveryCampaignError("JSON root must be an object")
    return value


def _executor_projection(value: Mapping[str, object]) -> dict[str, object]:
    return {key: value[key] for key in sorted(EXECUTOR_FIELDS - {"executor_identity"})}


def executor_identity(value: Mapping[str, object]) -> str:
    return canonical_hash(
        {
            "domain": "aml.benchmark-discovery-campaign.executor.v001",
            "executor": _executor_projection(value),
        }
    )


def campaign_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key] for key in sorted(CONFIG_FIELDS - {"campaign_identity"})
    }
    return canonical_hash(
        {
            "domain": "aml.benchmark-discovery-campaign.config.v001",
            "campaign": projection,
        }
    )


def result_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key] for key in sorted(RESULT_FIELDS - {"result_identity"})
    }
    return canonical_hash(
        {
            "domain": "aml.benchmark-discovery-campaign.result.v001",
            "result": projection,
        }
    )


def _validate_source_hashes(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise BenchmarkDiscoveryCampaignError("executor source hashes are missing")
    result: dict[str, str] = {}
    for raw_path, raw_identity in sorted(value.items()):
        path = Path(_text(raw_path, "executor source path"))
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise BenchmarkDiscoveryCampaignError("executor source path is unsafe")
        identity = _identity(raw_identity, "executor source hash")
        result[path.as_posix()] = identity
    if list(result) != sorted(result) or len(result) != len(value):
        raise BenchmarkDiscoveryCampaignError("executor source paths repeat")
    return result


def _validate_executor(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != EXECUTOR_FIELDS:
        raise BenchmarkDiscoveryCampaignError("executor contract schema is invalid")
    _identifier(value["library_entry_id"], "library_entry_id")
    _identifier(value["adapter_id"], "adapter_id")
    _text(value["adapter_version"], "adapter_version")
    for field in (
        "framework_hypothesis_identity",
        "dataset_identity",
        "specification_identity",
        "preregistration_identity",
        "implementation_binding_identity",
        "conformance_identity",
    ):
        _identity(value[field], field)
    _validate_source_hashes(value["source_sha256"])
    if value["executor_identity"] != executor_identity(value):
        raise BenchmarkDiscoveryCampaignError("executor identity is stale or tampered")
    return dict(value)


def validate_campaign_config(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the frozen dependencies, policy, and executor allowlist."""

    if not isinstance(value, Mapping) or set(value) != CONFIG_FIELDS:
        raise BenchmarkDiscoveryCampaignError("campaign configuration schema is invalid")
    if value["schema_version"] != CAMPAIGN_SCHEMA or value["campaign_version"] != CAMPAIGN_VERSION:
        raise BenchmarkDiscoveryCampaignError("campaign schema or version changed")
    _identifier(value["campaign_id"], "campaign_id")
    _timestamp(value["created_at"], "created_at")
    framework = value["framework_dependency"]
    if not isinstance(framework, Mapping) or set(framework) != {
        "framework_version",
        "source_commit",
    }:
        raise BenchmarkDiscoveryCampaignError("framework dependency schema is invalid")
    if framework["framework_version"] != FRAMEWORK_VERSION:
        raise BenchmarkDiscoveryCampaignError("framework dependency version changed")
    _git_oid(framework["source_commit"], "framework source commit")
    library = value["library_dependency"]
    if not isinstance(library, Mapping) or set(library) != {
        "library_version",
        "source_commit",
        "library_identity",
        "file_sha256",
    }:
        raise BenchmarkDiscoveryCampaignError("library dependency schema is invalid")
    if library["library_version"] != LIBRARY_VERSION:
        raise BenchmarkDiscoveryCampaignError("library dependency version changed")
    _git_oid(library["source_commit"], "library source commit")
    for field in ("library_identity", "file_sha256"):
        _identity(library[field], f"library {field}")
    campaign_sources = _validate_source_hashes(value["campaign_source_sha256"])
    if set(campaign_sources) != {
        "scripts/run_benchmark_discovery_campaign_v001.py",
        "src/aml/benchmark_discovery_campaign_v001.py",
    }:
        raise BenchmarkDiscoveryCampaignError("campaign source inventory changed")
    policy = value["policy"]
    if not isinstance(policy, Mapping) or set(policy) != POLICY_FIELDS:
        raise BenchmarkDiscoveryCampaignError("campaign policy schema is invalid")
    for field in POLICY_FIELDS - {"protected_boundaries"}:
        _text(policy[field], f"policy.{field}")
    boundaries = policy["protected_boundaries"]
    if not isinstance(boundaries, list) or boundaries != sorted(set(boundaries)):
        raise BenchmarkDiscoveryCampaignError("protected boundaries must be unique and sorted")
    required_boundaries = {
        "forward validation",
        "holdout",
        "live trading",
        "olympics execution",
        "paper trading",
        "validation",
    }
    if not required_boundaries.issubset({_text(item, "protected boundary") for item in boundaries}):
        raise BenchmarkDiscoveryCampaignError("campaign omits a protected boundary")
    if policy["blocked_classification"] != BLOCKED_CLASSIFICATION:
        raise BenchmarkDiscoveryCampaignError("blocked classification changed")
    raw_executors = value["authorized_executors"]
    if not isinstance(raw_executors, list) or len(raw_executors) > MAX_CAMPAIGN_ENTRIES:
        raise BenchmarkDiscoveryCampaignError("authorized executor inventory is invalid")
    executors = [_validate_executor(item) for item in raw_executors]
    entry_ids = [item["library_entry_id"] for item in executors]
    if entry_ids != sorted(entry_ids) or len(set(entry_ids)) != len(entry_ids):
        raise BenchmarkDiscoveryCampaignError("authorized executors must be unique and sorted")
    if len({item["executor_identity"] for item in executors}) != len(executors):
        raise BenchmarkDiscoveryCampaignError("executor identities repeat")
    if value["campaign_identity"] != campaign_identity(value):
        raise BenchmarkDiscoveryCampaignError("campaign identity is stale or tampered")
    return dict(value)


def load_campaign_config(path: Path) -> dict[str, object]:
    value = _strict_json(path, maximum_bytes=MAX_CONFIG_BYTES)
    validate_campaign_config(value)
    if path.read_bytes() != canonical_json(value):
        raise BenchmarkDiscoveryCampaignError("campaign configuration bytes are not canonical")
    return value


def finalize_campaign_config(value: Mapping[str, object]) -> dict[str, object]:
    """Pure authoring helper for freezing executor and campaign identities."""

    result = json.loads(canonical_json(value))
    for executor in result["authorized_executors"]:
        executor["executor_identity"] = executor_identity(executor)
    result["campaign_identity"] = campaign_identity(result)
    validate_campaign_config(result)
    return result


def _validate_dependencies(
    config: Mapping[str, object],
    library: Mapping[str, object],
    library_path: Path,
) -> None:
    validate_campaign_config(config)
    try:
        validate_library(library)
    except HypothesisLibraryError as exc:
        raise BenchmarkDiscoveryCampaignError("hypothesis library is invalid") from exc
    dependency = config["library_dependency"]
    if library["library_identity"] != dependency["library_identity"]:
        raise BenchmarkDiscoveryCampaignError("campaign library identity changed")
    if hashlib.sha256(library_path.read_bytes()).hexdigest() != dependency["file_sha256"]:
        raise BenchmarkDiscoveryCampaignError("campaign library file hash changed")
    if library["framework_dependency"]["source_commit"] != config["framework_dependency"][
        "source_commit"
    ]:
        raise BenchmarkDiscoveryCampaignError("campaign framework lineage changed")


def _validate_campaign_source(
    config: Mapping[str, object], repository_root: Path
) -> None:
    root = Path(repository_root).resolve()
    for relative, expected in _validate_source_hashes(
        config["campaign_source_sha256"]
    ).items():
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise BenchmarkDiscoveryCampaignError(f"campaign source changed:{relative}")


def _verify_registration_source(
    contract: Mapping[str, object], registration: ExecutorRegistration
) -> None:
    if registration.library_entry_id != contract["library_entry_id"]:
        raise BenchmarkDiscoveryCampaignError("runtime registration entry changed")
    if registration.adapter_id != contract["adapter_id"]:
        raise BenchmarkDiscoveryCampaignError("runtime adapter identity changed")
    if registration.adapter_version != contract["adapter_version"]:
        raise BenchmarkDiscoveryCampaignError("runtime adapter version changed")
    root = Path(registration.source_root).resolve()
    for relative, expected in _validate_source_hashes(contract["source_sha256"]).items():
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise BenchmarkDiscoveryCampaignError(f"authorized executor source changed:{relative}")


def _load_bundle_artifacts(root: Path) -> dict[str, dict[str, object]]:
    verified = verify_bundle(root)
    artifacts: dict[str, dict[str, object]] = {}
    for record in verified["files"]:
        path = root / str(record["path"])
        value = _strict_json(path, maximum_bytes=MAX_RESULT_BYTES)
        artifact_type = str(value.get("artifact_type", ""))
        artifacts[artifact_type] = value
    return artifacts


def _execution_evidence(
    *,
    bundle_root: Path,
    contract: Mapping[str, object],
    entry: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    """Verify accepted evidence was produced by Framework V001 unchanged."""

    try:
        bundle = verify_bundle(bundle_root)
        artifacts = _load_bundle_artifacts(bundle_root)
    except (BenchmarkResearchError, BenchmarkDiscoveryCampaignError) as exc:
        raise BenchmarkDiscoveryCampaignError("executor did not publish a valid Framework bundle") from exc
    required = {
        "hypothesis",
        "specification",
        "preregistration",
        "implementation_binding",
        "conformance",
        "discovery",
        "classification",
    }
    if not required.issubset(artifacts):
        raise BenchmarkDiscoveryCampaignError("executor evidence lifecycle is incomplete")
    expected = {
        "hypothesis": contract["framework_hypothesis_identity"],
        "specification": contract["specification_identity"],
        "preregistration": contract["preregistration_identity"],
        "implementation_binding": contract["implementation_binding_identity"],
        "conformance": contract["conformance_identity"],
    }
    if entry["framework_hypothesis_identity"] != expected["hypothesis"]:
        raise BenchmarkDiscoveryCampaignError("executor is bound to another library hypothesis")
    for artifact_type, identity in expected.items():
        if artifacts[artifact_type].get("identity") != identity:
            raise BenchmarkDiscoveryCampaignError(f"executor {artifact_type} identity changed")
    specification_payload = artifacts["specification"].get("payload")
    if (
        not isinstance(specification_payload, Mapping)
        or specification_payload.get("strategy_id") != entry["library_entry_id"]
        or artifacts["hypothesis"].get("payload", {}).get("hypothesis_id")
        != entry["library_entry_id"]
    ):
        raise BenchmarkDiscoveryCampaignError(
            "executor strategy identity does not match the library entry"
        )
    binding_payload = artifacts["implementation_binding"].get("payload")
    recorded_sources = (
        binding_payload.get("source_sha256")
        if isinstance(binding_payload, Mapping)
        else None
    )
    contract_sources = _validate_source_hashes(contract["source_sha256"])
    if not isinstance(recorded_sources, Mapping) or any(
        contract_sources.get(path) != identity
        for path, identity in recorded_sources.items()
    ):
        raise BenchmarkDiscoveryCampaignError(
            "executor contract does not bind every Framework implementation source"
        )
    discovery = artifacts["discovery"]
    classification = artifacts["classification"]
    payload = discovery.get("payload")
    classification_payload = classification.get("payload")
    if not isinstance(payload, Mapping) or not isinstance(classification_payload, Mapping):
        raise BenchmarkDiscoveryCampaignError("executor evidence payload is invalid")
    if payload.get("dataset_identity") != contract["dataset_identity"]:
        raise BenchmarkDiscoveryCampaignError("executor dataset identity changed")
    lineage = {
        "hypothesis_identity": contract["framework_hypothesis_identity"],
        "specification_identity": contract["specification_identity"],
        "preregistration_identity": contract["preregistration_identity"],
        "implementation_binding_identity": contract["implementation_binding_identity"],
        "conformance_identity": contract["conformance_identity"],
    }
    if any(payload.get(field) != identity for field, identity in lineage.items()):
        raise BenchmarkDiscoveryCampaignError("executor discovery lineage changed")
    if payload.get("executor_integrity_failure_count") != 0:
        raise BenchmarkDiscoveryCampaignError("executor integrity failure prevents publication")
    proposal_count = payload.get("proposal_count")
    accepted = payload.get("accepted_trade_count")
    rejected = payload.get("rejected_proposal_count")
    if any(type(item) is not int or item < 0 for item in (proposal_count, accepted, rejected)):
        raise BenchmarkDiscoveryCampaignError("executor reconciliation counts are invalid")
    if proposal_count != accepted + rejected:
        raise BenchmarkDiscoveryCampaignError("executor proposals do not reconcile")
    scenario_counts = payload.get("cost_scenario_trade_counts")
    if (
        not isinstance(scenario_counts, Mapping)
        or set(scenario_counts) != {"base", "cost_1_5x", "cost_2x"}
        or len(set(scenario_counts.values())) != 1
        or scenario_counts.get("base") != accepted
    ):
        raise BenchmarkDiscoveryCampaignError("executor cost scenarios do not reconcile")
    if classification_payload.get("discovery_identity") != discovery.get("identity"):
        raise BenchmarkDiscoveryCampaignError("executor classification lineage changed")
    allowed_classifications = {
        "INCONCLUSIVE_DATA_LIMITATION",
        "INCONCLUSIVE_INSUFFICIENT_SAMPLE",
        "PROMISING_FOR_BROADER_DISCOVERY",
        "REJECT",
    }
    if (
        classification_payload.get("classification_function")
        != "aml.discovery_screen_v001.classify"
        or classification_payload.get("validation_eligible") is not False
        or classification_payload.get("classification") not in allowed_classifications
    ):
        raise BenchmarkDiscoveryCampaignError(
            "executor did not use the frozen discovery classification contract"
        )
    classification_value = _text(
        classification_payload.get("classification"), "canonical classification"
    )
    evidence = {
        "executor_identity": contract["executor_identity"],
        "bundle_identity": bundle["identity"],
        "discovery_identity": discovery["identity"],
        "classification_identity": classification["identity"],
        "dataset_identity": contract["dataset_identity"],
        "evaluation_count": payload.get("evaluation_count"),
        "proposal_count": proposal_count,
        "accepted_trade_count": accepted,
        "rejected_proposal_count": rejected,
        "executor_integrity_failure_count": 0,
        "cost_scenario_trade_counts": dict(sorted(scenario_counts.items())),
        "evidence_class": payload.get("evidence_class"),
    }
    canonical_json(evidence)
    return classification_value, evidence


def _blocked_result(
    config: Mapping[str, object], entry: Mapping[str, object]
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "campaign_identity": config["campaign_identity"],
        "library_entry_id": entry["library_entry_id"],
        "registration_identity": entry["registration_identity"],
        "framework_hypothesis_identity": entry["framework_hypothesis_identity"],
        "status": "blocked",
        "canonical_classification": BLOCKED_CLASSIFICATION,
        "reason_codes": list(BLOCKED_REASON_CODES),
        "execution_evidence": None,
    }
    return {**value, "result_identity": result_identity(value)}


def _executed_result(
    config: Mapping[str, object],
    entry: Mapping[str, object],
    classification: str,
    evidence: Mapping[str, object],
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "campaign_identity": config["campaign_identity"],
        "library_entry_id": entry["library_entry_id"],
        "registration_identity": entry["registration_identity"],
        "framework_hypothesis_identity": entry["framework_hypothesis_identity"],
        "status": "executed",
        "canonical_classification": classification,
        "reason_codes": [],
        "execution_evidence": dict(evidence),
    }
    return {**value, "result_identity": result_identity(value)}


def validate_result(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != RESULT_FIELDS:
        raise BenchmarkDiscoveryCampaignError("campaign result schema is invalid")
    if value["schema_version"] != RESULT_SCHEMA:
        raise BenchmarkDiscoveryCampaignError("campaign result schema changed")
    for field in (
        "campaign_identity",
        "registration_identity",
        "framework_hypothesis_identity",
        "result_identity",
    ):
        _identity(value[field], field)
    _identifier(value["library_entry_id"], "library_entry_id")
    if value["status"] not in {"blocked", "executed"}:
        raise BenchmarkDiscoveryCampaignError("campaign result status is invalid")
    if not isinstance(value["reason_codes"], list) or value["reason_codes"] != sorted(
        set(value["reason_codes"])
    ):
        raise BenchmarkDiscoveryCampaignError("campaign reason codes are invalid")
    for reason in value["reason_codes"]:
        _identifier(reason.replace("_", "-"), "reason code")
    if value["status"] == "blocked":
        if (
            value["canonical_classification"] != BLOCKED_CLASSIFICATION
            or tuple(value["reason_codes"]) != BLOCKED_REASON_CODES
            or value["execution_evidence"] is not None
        ):
            raise BenchmarkDiscoveryCampaignError("blocked result semantics changed")
    else:
        _text(value["canonical_classification"], "canonical classification")
        if value["reason_codes"] or not isinstance(value["execution_evidence"], Mapping):
            raise BenchmarkDiscoveryCampaignError("executed result evidence is invalid")
        if value["execution_evidence"].get("executor_integrity_failure_count") != 0:
            raise BenchmarkDiscoveryCampaignError("executed result contains integrity failures")
    if value["result_identity"] != result_identity(value):
        raise BenchmarkDiscoveryCampaignError("campaign result identity is stale or tampered")
    return dict(value)


def _manifest_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(value) if key != "manifest_identity"}
    return canonical_hash(
        {
            "domain": "aml.benchmark-discovery-campaign.manifest.v001",
            "manifest": projection,
        }
    )


def _protected_output(path: Path) -> bool:
    protected = {
        "forward-validation",
        "holdout",
        "live",
        "olympics",
        "paper-trading",
        "validation",
    }
    return any(part.casefold().replace("_", "-") in protected for part in path.parts)


def run_campaign(
    *,
    config_path: Path,
    library_path: Path,
    output_root: Path,
    registrations: Sequence[ExecutorRegistration] = (),
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Execute every authorized entry and canonically block every other entry."""

    config = load_campaign_config(config_path)
    library = load_library(library_path)
    _validate_dependencies(config, library, library_path)
    source_root = (
        Path(repository_root)
        if repository_root is not None
        else Path(config_path).resolve().parent.parent
    )
    _validate_campaign_source(config, source_root)
    raw_output = Path(output_root)
    if ".." in raw_output.parts or _protected_output(raw_output):
        raise BenchmarkDiscoveryCampaignError("campaign output crosses a protected boundary")
    root = raw_output.resolve()
    if root.exists():
        raise BenchmarkDiscoveryCampaignError("campaign output already exists")
    contracts = {
        item["library_entry_id"]: item for item in config["authorized_executors"]
    }
    runtime: dict[str, ExecutorRegistration] = {}
    for registration in registrations:
        if registration.library_entry_id in runtime:
            raise BenchmarkDiscoveryCampaignError("runtime executor registration repeats")
        if registration.library_entry_id not in contracts:
            raise BenchmarkDiscoveryCampaignError("runtime executor is not authorized")
        _verify_registration_source(contracts[registration.library_entry_id], registration)
        runtime[registration.library_entry_id] = registration
    missing_runtime = sorted(set(contracts) - set(runtime))
    if missing_runtime:
        raise BenchmarkDiscoveryCampaignError(
            "authorized executor runtime is unavailable:" + ",".join(missing_runtime)
        )
    entries = library["hypotheses"]
    known_entries = {entry["library_entry_id"] for entry in entries}
    if not set(contracts).issubset(known_entries):
        raise BenchmarkDiscoveryCampaignError("executor contract references an unknown hypothesis")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    try:
        results: list[dict[str, object]] = []
        files: list[dict[str, object]] = []
        bundle_identities: dict[str, str] = {}
        for entry in entries:
            entry_id = entry["library_entry_id"]
            entry_root = staging / "entries" / entry_id
            entry_root.mkdir(parents=True, exist_ok=False)
            if entry_id not in contracts:
                result = _blocked_result(config, entry)
            else:
                contract = contracts[entry_id]
                bundle_root = entry_root / "framework-bundle"
                try:
                    runtime[entry_id].execute(bundle_root)
                except Exception as exc:
                    raise BenchmarkDiscoveryCampaignError(
                        f"authorized executor failed:{entry_id}"
                    ) from exc
                classification, evidence = _execution_evidence(
                    bundle_root=bundle_root,
                    contract=contract,
                    entry=entry,
                )
                result = _executed_result(config, entry, classification, evidence)
                bundle_identities[entry_id] = str(evidence["bundle_identity"])
            validate_result(result)
            relative = Path("entries") / entry_id / "result.json"
            data = canonical_json(result)
            if len(data) > MAX_RESULT_BYTES:
                raise BenchmarkDiscoveryCampaignError("campaign result is oversized")
            descriptor = os.open(staging / relative, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            files.append(
                {
                    "path": relative.as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
            results.append(result)
        blocked_count = sum(item["status"] == "blocked" for item in results)
        executed_count = sum(item["status"] == "executed" for item in results)
        classifications: dict[str, int] = {}
        for result in results:
            key = str(result["canonical_classification"])
            classifications[key] = classifications.get(key, 0) + 1
        manifest_base: dict[str, object] = {
            "schema_version": CAMPAIGN_MANIFEST_SCHEMA,
            "campaign_version": CAMPAIGN_VERSION,
            "campaign_identity": config["campaign_identity"],
            "library_identity": library["library_identity"],
            "library_hypothesis_count": len(entries),
            "result_count": len(results),
            "executed_count": executed_count,
            "blocked_count": blocked_count,
            "classification_counts": dict(sorted(classifications.items())),
            "result_identities": [item["result_identity"] for item in results],
            "bundle_identities": dict(sorted(bundle_identities.items())),
            "files": files,
            "reconciliation": {
                "all_library_entries_accounted_for": len(results) == len(entries),
                "executed_plus_blocked_equals_total": (
                    executed_count + blocked_count == len(entries)
                ),
                "duplicate_result_count": len(results)
                - len({item["library_entry_id"] for item in results}),
                "executor_integrity_failure_count": 0,
            },
            "immutable": True,
        }
        manifest = {
            **manifest_base,
            "manifest_identity": _manifest_identity(manifest_base),
        }
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        verified = verify_campaign(
            staging,
            config_path=config_path,
            library_path=library_path,
            repository_root=source_root,
        )
        os.replace(staging, root)
        return verified
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_campaign(
    output_root: Path,
    *,
    config_path: Path,
    library_path: Path,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Reconcile and verify a published campaign without executing anything."""

    root = Path(output_root).resolve()
    config = load_campaign_config(config_path)
    library = load_library(library_path)
    _validate_dependencies(config, library, library_path)
    source_root = (
        Path(repository_root)
        if repository_root is not None
        else Path(config_path).resolve().parent.parent
    )
    _validate_campaign_source(config, source_root)
    manifest = _strict_json(root / "manifest.json", maximum_bytes=MAX_RESULT_BYTES)
    required = {
        "schema_version",
        "campaign_version",
        "campaign_identity",
        "library_identity",
        "library_hypothesis_count",
        "result_count",
        "executed_count",
        "blocked_count",
        "classification_counts",
        "result_identities",
        "bundle_identities",
        "files",
        "reconciliation",
        "immutable",
        "manifest_identity",
    }
    if set(manifest) != required:
        raise BenchmarkDiscoveryCampaignError("campaign manifest schema is invalid")
    if (
        manifest["schema_version"] != CAMPAIGN_MANIFEST_SCHEMA
        or manifest["campaign_version"] != CAMPAIGN_VERSION
        or manifest["campaign_identity"] != config["campaign_identity"]
        or manifest["library_identity"] != library["library_identity"]
        or manifest["immutable"] is not True
    ):
        raise BenchmarkDiscoveryCampaignError("campaign manifest dependencies changed")
    if manifest["manifest_identity"] != _manifest_identity(manifest):
        raise BenchmarkDiscoveryCampaignError("campaign manifest identity is stale or tampered")
    entries = library["hypotheses"]
    expected_ids = [entry["library_entry_id"] for entry in entries]
    if (
        manifest["library_hypothesis_count"] != len(entries)
        or manifest["result_count"] != len(entries)
        or not isinstance(manifest["files"], list)
        or len(manifest["files"]) != len(entries)
    ):
        raise BenchmarkDiscoveryCampaignError("campaign result inventory does not reconcile")
    results: list[dict[str, object]] = []
    actual_bundle_identities: dict[str, str] = {}
    for entry, record in zip(entries, manifest["files"], strict=True):
        if not isinstance(record, Mapping) or set(record) != {"path", "sha256", "bytes"}:
            raise BenchmarkDiscoveryCampaignError("campaign file record is invalid")
        expected_path = f"entries/{entry['library_entry_id']}/result.json"
        if record["path"] != expected_path:
            raise BenchmarkDiscoveryCampaignError("campaign result order changed")
        _identity(record["sha256"], "campaign result file hash")
        if type(record["bytes"]) is not int or not 0 < record["bytes"] <= MAX_RESULT_BYTES:
            raise BenchmarkDiscoveryCampaignError("campaign result size is invalid")
        path = root / expected_path
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != record["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise BenchmarkDiscoveryCampaignError("campaign result file hash mismatch")
        result = validate_result(_strict_json(path, maximum_bytes=MAX_RESULT_BYTES))
        if (
            result["library_entry_id"] != entry["library_entry_id"]
            or result["registration_identity"] != entry["registration_identity"]
            or result["framework_hypothesis_identity"]
            != entry["framework_hypothesis_identity"]
        ):
            raise BenchmarkDiscoveryCampaignError("campaign result library binding changed")
        bundle_root = path.parent / "framework-bundle"
        if result["status"] == "executed":
            bundle = verify_bundle(bundle_root)
            if bundle["identity"] != result["execution_evidence"]["bundle_identity"]:
                raise BenchmarkDiscoveryCampaignError("campaign bundle identity changed")
            actual_bundle_identities[entry["library_entry_id"]] = bundle["identity"]
        elif bundle_root.exists():
            raise BenchmarkDiscoveryCampaignError("blocked hypothesis contains execution evidence")
        results.append(result)
    blocked = sum(item["status"] == "blocked" for item in results)
    executed = sum(item["status"] == "executed" for item in results)
    classification_counts: dict[str, int] = {}
    for result in results:
        key = str(result["canonical_classification"])
        classification_counts[key] = classification_counts.get(key, 0) + 1
    if (
        manifest["result_identities"] != [item["result_identity"] for item in results]
        or manifest["blocked_count"] != blocked
        or manifest["executed_count"] != executed
        or manifest["classification_counts"] != dict(sorted(classification_counts.items()))
        or manifest["bundle_identities"] != dict(sorted(actual_bundle_identities.items()))
    ):
        raise BenchmarkDiscoveryCampaignError("campaign aggregate counts changed")
    reconciliation = manifest["reconciliation"]
    if reconciliation != {
        "all_library_entries_accounted_for": True,
        "executed_plus_blocked_equals_total": True,
        "duplicate_result_count": 0,
        "executor_integrity_failure_count": 0,
    }:
        raise BenchmarkDiscoveryCampaignError("campaign reconciliation failed")
    if expected_ids != [item["library_entry_id"] for item in results]:
        raise BenchmarkDiscoveryCampaignError("campaign entry ordering changed")
    return {**manifest, "verified": True}
