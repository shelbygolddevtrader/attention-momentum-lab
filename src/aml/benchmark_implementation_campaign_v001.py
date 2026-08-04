"""Deterministic implementation-readiness audit for Library V001 hypotheses.

This layer does not interpret hypothesis prose as executable strategy rules.
It proves whether each not-yet-executable Library entry has a complete research
chain and, when it does not, publishes the earliest missing capability required
to continue without weakening the frozen research architecture.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from aml.benchmark_hypothesis_library_v001 import load_library, validate_library
from aml.benchmark_strategy_research_v001 import canonical_hash, canonical_json


SCHEMA_VERSION = "aml.benchmark-implementation-campaign.v001"
CAMPAIGN_VERSION = "benchmark-implementation-campaign-v001"
ASSESSMENT_SCHEMA = "aml.benchmark-implementation-readiness.v001"
MANIFEST_SCHEMA = "aml.benchmark-implementation-campaign.manifest.v001"
BLOCKED_STATUS = "blocked"
MAX_JSON_BYTES = 4_000_000
MAX_HYPOTHESES = 1_000
HASH = re.compile(r"^[0-9a-f]{64}$")
GIT_OID = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,127}$")

CLASSIFICATION_BY_CAPABILITY = {
    "data": "BLOCKED_MISSING_AUTHORIZED_DATA",
    "execution_model": "BLOCKED_MISSING_EXECUTION_MODEL",
    "governance": "BLOCKED_MISSING_EXECUTABLE_SPECIFICATION",
    "indicator": "BLOCKED_MISSING_INDICATOR",
    "other_prerequisite": "BLOCKED_MISSING_OTHER_PREREQUISITE",
}
ARCHITECTURE_FIT_BY_CAPABILITY = {
    "data": "requires_new_authorized_point_in_time_data",
    "execution_model": "requires_versioned_execution_model",
    "governance": "supported_after_prospective_specification",
    "indicator": "requires_new_point_in_time_indicator",
    "other_prerequisite": "requires_other_prerequisite",
}
CHAIN_FIELDS = {
    "authorized_dataset_binding",
    "canonical_executable_specification",
    "conformance_evidence",
    "implementation_binding",
    "registered_executor",
}
CONFIG_FIELDS = {
    "schema_version",
    "campaign_version",
    "campaign_id",
    "created_at",
    "source_commit",
    "library_dependency",
    "existing_executable_candidate",
    "capability_inventory",
    "campaign_source_sha256",
    "policy",
    "assessments",
    "campaign_identity",
}
ASSESSMENT_FIELDS = {
    "library_entry_id",
    "registration_identity",
    "framework_hypothesis_identity",
    "library_revision",
    "status",
    "canonical_classification",
    "minimal_missing_capability",
    "architecture_fit",
    "required_indicators",
    "expected_holding_period",
    "available_reuse",
    "secondary_missing_capability_codes",
    "complete_chain",
    "required_next_milestone",
    "research_integrity_reason",
    "assessment_identity",
}


class BenchmarkImplementationCampaignError(ValueError):
    """Implementation-readiness input or immutable evidence is invalid."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 20_000:
        raise BenchmarkImplementationCampaignError(
            f"{field} must be a non-empty bounded string"
        )
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BenchmarkImplementationCampaignError(
            f"{field} contains invalid Unicode"
        ) from exc
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        raise BenchmarkImplementationCampaignError(
            f"{field} contains prohibited Unicode"
        )
    return value


def _identifier(value: object, field: str) -> str:
    result = _text(value, field)
    if not IDENTIFIER.fullmatch(result):
        raise BenchmarkImplementationCampaignError(f"{field} is malformed")
    return result


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise BenchmarkImplementationCampaignError(
            f"{field} must be a SHA-256 identity"
        )
    return value


def _git_oid(value: object, field: str) -> str:
    if not isinstance(value, str) or not GIT_OID.fullmatch(value):
        raise BenchmarkImplementationCampaignError(
            f"{field} must be a full Git commit OID"
        )
    return value


def _timestamp(value: object, field: str) -> str:
    result = _text(value, field)
    try:
        parsed = datetime.fromisoformat(result)
    except ValueError as exc:
        raise BenchmarkImplementationCampaignError(f"{field} is malformed") from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
        or parsed.isoformat().replace("+00:00", "Z") != result
    ):
        raise BenchmarkImplementationCampaignError(f"{field} must use canonical UTC")
    return result


def _sorted_texts(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise BenchmarkImplementationCampaignError(f"{field} must be a list")
    result = [_text(item, field) for item in value]
    if result != sorted(set(result)):
        raise BenchmarkImplementationCampaignError(
            f"{field} must be sorted and unique"
        )
    return result


def _source_hashes(value: object, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise BenchmarkImplementationCampaignError(f"{field} is missing")
    result: dict[str, str] = {}
    for raw_path, raw_digest in sorted(value.items()):
        path = Path(_text(raw_path, f"{field} path"))
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise BenchmarkImplementationCampaignError(f"{field} path is unsafe")
        result[path.as_posix()] = _identity(raw_digest, f"{field} digest")
    if len(result) != len(value):
        raise BenchmarkImplementationCampaignError(f"{field} paths repeat")
    return result


def _strict_json(path: Path) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise BenchmarkImplementationCampaignError("JSON contains duplicate keys")
            result[key] = item
        return result

    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
        raise BenchmarkImplementationCampaignError("JSON is missing, unsafe, or oversized")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda item: (_ for _ in ()).throw(
                BenchmarkImplementationCampaignError(
                    f"JSON contains non-finite value:{item}"
                )
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkImplementationCampaignError("JSON is malformed") from exc
    if not isinstance(value, dict):
        raise BenchmarkImplementationCampaignError("JSON root must be an object")
    return value


def assessment_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key]
        for key in sorted(ASSESSMENT_FIELDS - {"assessment_identity"})
    }
    return canonical_hash(
        {
            "domain": "aml.benchmark-implementation-readiness.v001",
            "assessment": projection,
        }
    )


def inventory_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(value) if key != "inventory_identity"}
    return canonical_hash(
        {
            "domain": "aml.benchmark-implementation-capability-inventory.v001",
            "inventory": projection,
        }
    )


def campaign_identity(value: Mapping[str, object]) -> str:
    projection = {
        key: value[key]
        for key in sorted(CONFIG_FIELDS - {"campaign_identity"})
    }
    return canonical_hash(
        {
            "domain": "aml.benchmark-implementation-campaign.config.v001",
            "campaign": projection,
        }
    )


def _validate_assessment(
    value: Mapping[str, object], entry: Mapping[str, object]
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != ASSESSMENT_FIELDS:
        raise BenchmarkImplementationCampaignError("assessment schema is invalid")
    if value["library_entry_id"] != entry["library_entry_id"]:
        raise BenchmarkImplementationCampaignError("assessment entry binding changed")
    if value["registration_identity"] != entry["registration_identity"]:
        raise BenchmarkImplementationCampaignError(
            "assessment registration binding changed"
        )
    if value["framework_hypothesis_identity"] != entry[
        "framework_hypothesis_identity"
    ]:
        raise BenchmarkImplementationCampaignError(
            "assessment hypothesis binding changed"
        )
    if value["library_revision"] != entry["revision"]:
        raise BenchmarkImplementationCampaignError("assessment revision changed")
    if value["status"] != BLOCKED_STATUS:
        raise BenchmarkImplementationCampaignError(
            "V001 readiness assessment may not claim execution"
        )
    missing = value["minimal_missing_capability"]
    if not isinstance(missing, Mapping) or set(missing) != {
        "capability_class",
        "capability_code",
        "description",
        "evidence_missing",
    }:
        raise BenchmarkImplementationCampaignError(
            "minimal missing capability schema is invalid"
        )
    capability_class = missing["capability_class"]
    if capability_class not in CLASSIFICATION_BY_CAPABILITY:
        raise BenchmarkImplementationCampaignError(
            "minimal missing capability class is invalid"
        )
    _identifier(missing["capability_code"], "minimal capability code")
    _text(missing["description"], "minimal capability description")
    _text(missing["evidence_missing"], "missing evidence")
    if value["canonical_classification"] != CLASSIFICATION_BY_CAPABILITY[
        capability_class
    ]:
        raise BenchmarkImplementationCampaignError(
            "assessment classification does not match its capability class"
        )
    if value["architecture_fit"] != ARCHITECTURE_FIT_BY_CAPABILITY[
        capability_class
    ]:
        raise BenchmarkImplementationCampaignError(
            "assessment architecture fit does not match its capability class"
        )
    if value["required_indicators"] != entry["required_indicators"]:
        raise BenchmarkImplementationCampaignError(
            "assessment required indicators changed"
        )
    if value["expected_holding_period"] != entry["expected_holding_period"]:
        raise BenchmarkImplementationCampaignError(
            "assessment holding period changed"
        )
    _sorted_texts(value["available_reuse"], "available reuse", allow_empty=True)
    secondary = _sorted_texts(
        value["secondary_missing_capability_codes"],
        "secondary missing capabilities",
        allow_empty=True,
    )
    if missing["capability_code"] in secondary:
        raise BenchmarkImplementationCampaignError(
            "minimal capability repeats as a secondary blocker"
        )
    chain = value["complete_chain"]
    if not isinstance(chain, Mapping) or set(chain) != CHAIN_FIELDS:
        raise BenchmarkImplementationCampaignError("complete chain schema is invalid")
    if any(type(item) is not bool for item in chain.values()):
        raise BenchmarkImplementationCampaignError(
            "complete chain values must be booleans"
        )
    if all(chain.values()):
        raise BenchmarkImplementationCampaignError(
            "blocked assessment cannot contain a complete executable chain"
        )
    if any(chain.values()):
        raise BenchmarkImplementationCampaignError(
            "no remaining Library V001 entry has a reviewed chain stage"
        )
    _text(value["required_next_milestone"], "required next milestone")
    _text(value["research_integrity_reason"], "research integrity reason")
    if value["assessment_identity"] != assessment_identity(value):
        raise BenchmarkImplementationCampaignError(
            "assessment identity is stale or tampered"
        )
    return dict(value)


def validate_config(
    value: Mapping[str, object], library: Mapping[str, object]
) -> dict[str, object]:
    validate_library(library)
    if not isinstance(value, Mapping) or set(value) != CONFIG_FIELDS:
        raise BenchmarkImplementationCampaignError("campaign config schema is invalid")
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["campaign_version"] != CAMPAIGN_VERSION
    ):
        raise BenchmarkImplementationCampaignError("campaign version changed")
    _identifier(value["campaign_id"], "campaign_id")
    _timestamp(value["created_at"], "created_at")
    _git_oid(value["source_commit"], "source_commit")
    dependency = value["library_dependency"]
    if not isinstance(dependency, Mapping) or set(dependency) != {
        "library_version",
        "library_identity",
        "file_sha256",
        "source_commit",
    }:
        raise BenchmarkImplementationCampaignError(
            "library dependency schema is invalid"
        )
    if (
        dependency["library_version"] != library["library_version"]
        or dependency["library_identity"] != library["library_identity"]
    ):
        raise BenchmarkImplementationCampaignError("library dependency changed")
    _identity(dependency["file_sha256"], "library file hash")
    _git_oid(dependency["source_commit"], "library source commit")
    existing = value["existing_executable_candidate"]
    if not isinstance(existing, Mapping) or set(existing) != {
        "library_entry_id",
        "framework_hypothesis_identity",
        "registration_identity",
        "campaign_identity",
        "bundle_identity",
        "classification",
    }:
        raise BenchmarkImplementationCampaignError(
            "existing executable candidate schema is invalid"
        )
    _identifier(existing["library_entry_id"], "existing candidate id")
    for field in (
        "framework_hypothesis_identity",
        "registration_identity",
        "campaign_identity",
        "bundle_identity",
    ):
        _identity(existing[field], f"existing candidate {field}")
    if existing["classification"] != "INCONCLUSIVE_INSUFFICIENT_SAMPLE":
        raise BenchmarkImplementationCampaignError(
            "existing candidate classification changed"
        )
    inventory = value["capability_inventory"]
    if not isinstance(inventory, Mapping) or set(inventory) != {
        "available_data_classes",
        "available_indicator_functions",
        "execution_capabilities",
        "unavailable_capabilities",
        "source_sha256",
        "inventory_identity",
    }:
        raise BenchmarkImplementationCampaignError(
            "capability inventory schema is invalid"
        )
    for field in (
        "available_data_classes",
        "available_indicator_functions",
        "execution_capabilities",
        "unavailable_capabilities",
    ):
        _sorted_texts(inventory[field], f"inventory {field}")
    _source_hashes(inventory["source_sha256"], "inventory source hashes")
    if inventory["inventory_identity"] != inventory_identity(inventory):
        raise BenchmarkImplementationCampaignError(
            "capability inventory identity is stale or tampered"
        )
    _source_hashes(value["campaign_source_sha256"], "campaign source hashes")
    policy = value["policy"]
    if not isinstance(policy, Mapping) or set(policy) != {
        "scope",
        "decision_rule",
        "minimal_blocker_rule",
        "mutation_rule",
        "claim_boundary",
        "prohibited_actions",
    }:
        raise BenchmarkImplementationCampaignError("campaign policy is invalid")
    for field in (
        "scope",
        "decision_rule",
        "minimal_blocker_rule",
        "mutation_rule",
        "claim_boundary",
    ):
        _text(policy[field], f"policy {field}")
    prohibited = _sorted_texts(policy["prohibited_actions"], "prohibited actions")
    required_prohibitions = {
        "forward testing",
        "holdout access",
        "live trading",
        "olympics execution",
        "optimization",
        "paper trading",
        "parameter search",
        "validation access",
    }
    if not required_prohibitions.issubset(prohibited):
        raise BenchmarkImplementationCampaignError(
            "campaign policy omits a protected action"
        )
    raw_assessments = value["assessments"]
    if (
        not isinstance(raw_assessments, list)
        or not raw_assessments
        or len(raw_assessments) > MAX_HYPOTHESES
    ):
        raise BenchmarkImplementationCampaignError(
            "assessment inventory is invalid"
        )
    entries = {
        item["library_entry_id"]: item for item in library["hypotheses"]
    }
    excluded = existing["library_entry_id"]
    if excluded not in entries:
        raise BenchmarkImplementationCampaignError(
            "existing executable candidate is absent from the library"
        )
    expected_ids = sorted(set(entries) - {excluded})
    actual_ids = [item.get("library_entry_id") for item in raw_assessments]
    if actual_ids != expected_ids:
        raise BenchmarkImplementationCampaignError(
            "assessments do not exactly cover the remaining library"
        )
    for assessment in raw_assessments:
        _validate_assessment(assessment, entries[assessment["library_entry_id"]])
    if value["campaign_identity"] != campaign_identity(value):
        raise BenchmarkImplementationCampaignError(
            "campaign identity is stale or tampered"
        )
    return dict(value)


def finalize_config(
    value: Mapping[str, object], library: Mapping[str, object]
) -> dict[str, object]:
    """Pure authoring helper for canonical assessment and campaign identities."""

    result = json.loads(canonical_json(value))
    inventory = result["capability_inventory"]
    inventory["inventory_identity"] = inventory_identity(inventory)
    for assessment in result["assessments"]:
        assessment["assessment_identity"] = assessment_identity(assessment)
    result["campaign_identity"] = campaign_identity(result)
    validate_config(result, library)
    return result


def load_config(path: Path, library: Mapping[str, object]) -> dict[str, object]:
    value = _strict_json(path)
    validate_config(value, library)
    if path.read_bytes() != canonical_json(value):
        raise BenchmarkImplementationCampaignError(
            "campaign config bytes are not canonical"
        )
    return value


def _validate_dependencies(
    *,
    config: Mapping[str, object],
    library_path: Path,
    repository_root: Path,
) -> None:
    if hashlib.sha256(library_path.read_bytes()).hexdigest() != config[
        "library_dependency"
    ]["file_sha256"]:
        raise BenchmarkImplementationCampaignError("library file hash changed")
    root = repository_root.resolve()
    inventory_sources = _source_hashes(
        config["capability_inventory"]["source_sha256"],
        "inventory source hashes",
    )
    campaign_sources = _source_hashes(
        config["campaign_source_sha256"], "campaign source hashes"
    )
    if set(inventory_sources).intersection(campaign_sources):
        raise BenchmarkImplementationCampaignError(
            "campaign and inventory source bindings overlap"
        )
    sources = {**inventory_sources, **campaign_sources}
    for relative, expected in sorted(sources.items()):
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise BenchmarkImplementationCampaignError(
                f"bound repository source changed:{relative}"
            )


def _assessment_artifact(
    config: Mapping[str, object], assessment: Mapping[str, object]
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": ASSESSMENT_SCHEMA,
        "campaign_identity": config["campaign_identity"],
        **dict(assessment),
    }
    value["artifact_identity"] = canonical_hash(
        {
            "domain": "aml.benchmark-implementation-readiness.artifact.v001",
            "artifact": value,
        }
    )
    return value


def _markdown_report(
    config: Mapping[str, object], artifacts: Sequence[Mapping[str, object]]
) -> bytes:
    capability_counts = Counter(
        item["minimal_missing_capability"]["capability_class"] for item in artifacts
    )
    classification_counts = Counter(item["canonical_classification"] for item in artifacts)
    lines = [
        "# Benchmark Implementation Campaign V001 readiness report",
        "",
        "This deterministic report evaluates implementation readiness only. It does not",
        "execute a strategy, access empirical outcomes, or establish a trading edge.",
        "",
        f"- Campaign identity: `{config['campaign_identity']}`",
        f"- Library identity: `{config['library_dependency']['library_identity']}`",
        f"- Remaining hypotheses assessed: {len(artifacts)}",
        "- Complete executable chains found: 0",
        f"- Canonically blocked: {len(artifacts)}",
        "- Previously executable candidate excluded from reassessment: "
        f"`{config['existing_executable_candidate']['library_entry_id']}`",
        "",
        "## Minimal blocker counts",
        "",
    ]
    for key, count in sorted(capability_counts.items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Canonical classification counts", ""])
    for key, count in sorted(classification_counts.items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## Per-hypothesis readiness",
            "",
            "| Hypothesis | Classification | Minimal capability | Architecture fit |",
            "|---|---|---|---|",
        ]
    )
    for item in artifacts:
        missing = item["minimal_missing_capability"]
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                item["library_entry_id"],
                item["canonical_classification"],
                missing["capability_code"],
                item["architecture_fit"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A blocked classification is not evidence against the economic hypothesis. It",
            "identifies the earliest capability that must be reviewed before an executable",
            "specification can be claimed. No threshold or trading rule was inferred from",
            "hypothesis prose, and every frozen downstream component remained unchanged.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _manifest_identity(value: Mapping[str, object]) -> str:
    projection = {key: value[key] for key in sorted(value) if key != "manifest_identity"}
    return canonical_hash(
        {
            "domain": "aml.benchmark-implementation-campaign.manifest.v001",
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
    repository_root: Path,
) -> dict[str, object]:
    """Publish the complete implementation-readiness campaign atomically."""

    library = load_library(library_path)
    config = load_config(config_path, library)
    _validate_dependencies(
        config=config,
        library_path=library_path,
        repository_root=repository_root,
    )
    raw_output = Path(output_root)
    if ".." in raw_output.parts or _protected_output(raw_output):
        raise BenchmarkImplementationCampaignError(
            "campaign output crosses a protected boundary"
        )
    root = raw_output.resolve()
    if root.exists():
        raise BenchmarkImplementationCampaignError("campaign output already exists")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-", dir=root.parent))
    try:
        artifacts = [
            _assessment_artifact(config, assessment)
            for assessment in config["assessments"]
        ]
        files: list[dict[str, object]] = []
        for artifact in artifacts:
            relative = Path("assessments") / str(artifact["library_entry_id"]) / "readiness.json"
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=False)
            data = canonical_json(artifact)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            files.append(
                {
                    "path": relative.as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
        report = _markdown_report(config, artifacts)
        report_relative = "IMPLEMENTATION_READINESS_REPORT.md"
        (staging / report_relative).write_bytes(report)
        files.append(
            {
                "path": report_relative,
                "sha256": hashlib.sha256(report).hexdigest(),
                "bytes": len(report),
            }
        )
        classification_counts = dict(
            sorted(Counter(item["canonical_classification"] for item in artifacts).items())
        )
        capability_counts = dict(
            sorted(
                Counter(
                    item["minimal_missing_capability"]["capability_class"]
                    for item in artifacts
                ).items()
            )
        )
        blocked_count = sum(item["status"] == BLOCKED_STATUS for item in artifacts)
        complete_chain_count = sum(
            all(item["complete_chain"].values()) for item in artifacts
        )
        manifest_base: dict[str, object] = {
            "schema_version": MANIFEST_SCHEMA,
            "campaign_version": CAMPAIGN_VERSION,
            "campaign_identity": config["campaign_identity"],
            "library_identity": library["library_identity"],
            "library_hypothesis_count": library["hypothesis_count"],
            "existing_executable_count": 1,
            "assessment_count": len(artifacts),
            "blocked_count": blocked_count,
            "complete_chain_count": complete_chain_count,
            "classification_counts": classification_counts,
            "capability_class_counts": capability_counts,
            "assessment_identities": [item["assessment_identity"] for item in artifacts],
            "artifact_identities": [item["artifact_identity"] for item in artifacts],
            "files": files,
            "reconciliation": {
                "all_library_hypotheses_accounted_for": (
                    len(artifacts) + 1 == library["hypothesis_count"]
                ),
                "blocked_plus_complete_equals_assessed": (
                    blocked_count + complete_chain_count == len(artifacts)
                ),
                "duplicate_assessment_count": len(artifacts)
                - len({item["library_entry_id"] for item in artifacts}),
                "empirical_outcome_access_count": 0,
                "strategy_execution_count": 0,
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
            repository_root=repository_root,
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
    repository_root: Path,
) -> dict[str, object]:
    """Verify every immutable readiness artifact without executing a strategy."""

    root = Path(output_root).resolve()
    library = load_library(library_path)
    config = load_config(config_path, library)
    _validate_dependencies(
        config=config,
        library_path=library_path,
        repository_root=repository_root,
    )
    manifest = _strict_json(root / "manifest.json")
    required_manifest_fields = {
        "schema_version",
        "campaign_version",
        "campaign_identity",
        "library_identity",
        "library_hypothesis_count",
        "existing_executable_count",
        "assessment_count",
        "blocked_count",
        "complete_chain_count",
        "classification_counts",
        "capability_class_counts",
        "assessment_identities",
        "artifact_identities",
        "files",
        "reconciliation",
        "immutable",
        "manifest_identity",
    }
    if set(manifest) != required_manifest_fields:
        raise BenchmarkImplementationCampaignError("manifest schema is invalid")
    if (
        manifest["schema_version"] != MANIFEST_SCHEMA
        or manifest["campaign_version"] != CAMPAIGN_VERSION
        or manifest["campaign_identity"] != config["campaign_identity"]
        or manifest["library_identity"] != library["library_identity"]
        or manifest["immutable"] is not True
        or manifest["manifest_identity"] != _manifest_identity(manifest)
    ):
        raise BenchmarkImplementationCampaignError(
            "manifest identity or dependency changed"
        )
    assessments = config["assessments"]
    if (
        manifest["assessment_count"] != len(assessments)
        or manifest["blocked_count"] != len(assessments)
        or manifest["complete_chain_count"] != 0
        or manifest["existing_executable_count"] != 1
        or manifest["library_hypothesis_count"] != library["hypothesis_count"]
        or not isinstance(manifest["files"], list)
        or len(manifest["files"]) != len(assessments) + 1
    ):
        raise BenchmarkImplementationCampaignError(
            "manifest inventory does not reconcile"
        )
    artifacts: list[dict[str, object]] = []
    expected_file_paths = [
        f"assessments/{item['library_entry_id']}/readiness.json"
        for item in assessments
    ] + ["IMPLEMENTATION_READINESS_REPORT.md"]
    expected_tree = sorted(expected_file_paths + ["manifest.json"])
    actual_tree = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    if actual_tree != expected_tree:
        raise BenchmarkImplementationCampaignError(
            "campaign output contains an unexpected or missing file"
        )
    for expected, record in zip(expected_file_paths, manifest["files"], strict=True):
        if not isinstance(record, Mapping) or set(record) != {"path", "sha256", "bytes"}:
            raise BenchmarkImplementationCampaignError("manifest file record is invalid")
        if record["path"] != expected:
            raise BenchmarkImplementationCampaignError("manifest file ordering changed")
        _identity(record["sha256"], "manifest file hash")
        if type(record["bytes"]) is not int or not 0 < record["bytes"] <= MAX_JSON_BYTES:
            raise BenchmarkImplementationCampaignError("manifest file size is invalid")
        path = root / expected
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != record["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]
        ):
            raise BenchmarkImplementationCampaignError("manifest file hash mismatch")
        if expected.endswith("readiness.json"):
            artifact = _strict_json(path)
            assessment = assessments[len(artifacts)]
            expected_artifact = _assessment_artifact(config, assessment)
            if artifact != expected_artifact:
                raise BenchmarkImplementationCampaignError(
                    "readiness artifact does not match its frozen assessment"
                )
            artifacts.append(artifact)
    if (root / "IMPLEMENTATION_READINESS_REPORT.md").read_bytes() != _markdown_report(
        config, artifacts
    ):
        raise BenchmarkImplementationCampaignError("readiness report changed")
    classification_counts = dict(
        sorted(Counter(item["canonical_classification"] for item in artifacts).items())
    )
    capability_counts = dict(
        sorted(
            Counter(
                item["minimal_missing_capability"]["capability_class"]
                for item in artifacts
            ).items()
        )
    )
    if (
        manifest["assessment_identities"]
        != [item["assessment_identity"] for item in artifacts]
        or manifest["artifact_identities"]
        != [item["artifact_identity"] for item in artifacts]
        or manifest["classification_counts"] != classification_counts
        or manifest["capability_class_counts"] != capability_counts
        or manifest["reconciliation"]
        != {
            "all_library_hypotheses_accounted_for": True,
            "blocked_plus_complete_equals_assessed": True,
            "duplicate_assessment_count": 0,
            "empirical_outcome_access_count": 0,
            "strategy_execution_count": 0,
        }
    ):
        raise BenchmarkImplementationCampaignError(
            "campaign aggregates do not reconcile"
        )
    return {**manifest, "verified": True}
