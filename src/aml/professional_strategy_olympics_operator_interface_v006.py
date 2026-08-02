"""Pure validation for the design-only Olympics V006 operator interface.

This module freezes an execution boundary. It cannot create an authorization,
connect to a verifier, mutate a filesystem, invoke an Olympics runner, or emit
results.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Mapping

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_IDENTITY as V005_COMMAND_IDENTITY,
    CONTRACT_IDENTITY as V005_GOVERNANCE_IDENTITY,
    TAGGED_COMMIT,
    TAG_NAME,
    TAG_OBJECT,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    parse_canonical_timestamp,
    strict_json_bytes,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    AUTHORIZATION_FIELDS as V004_AUTHORIZATION_FIELDS,
    implementation_identity as v004_implementation_identity,
    lineage_run_identity as v004_lineage_run_identity,
)
from aml.professional_strategy_olympics_final_scoring_v004 import BUNDLE_IDENTITY
from aml.professional_strategy_olympics_orchestrator_v001 import (
    ORCHESTRATOR_IDENTITY,
    implementation_identity as orchestrator_implementation_identity,
)


CONTRACT_PATH = "config/professional_strategy_olympics_operator_interface_v006.json"
SCHEMA = "aml.professional-strategy-olympics.operator-interface.v006"
VERSION = "professional-strategy-olympics-operator-interface-v006"
CONTRACT_DOMAIN = "aml.olympics.v006.operator-interface"
COMMAND_DOMAIN = "aml.olympics.v005.command"
CONTRACT_IDENTITY = "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6"
COMMAND_IDENTITY = V005_COMMAND_IDENTITY
DESIGN_BASE_COMMIT = "763e7aa241cdbf8febe0191ee5f01a8156869931"
MAXIMUM_BYTES = 250_000
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")

SECTION_NAMES = (
    "authorization_package",
    "capability_scope",
    "command",
    "execution_mapping",
    "failure_protocol",
    "operator_preflight",
    "repository_attestation_interface",
    "trusted_clock_interface",
    "validation_manifest",
)
EXPECTED_SECTION_IDENTITIES = {
    "authorization_package": "7107aef3d8d86ace8ac9a6f4c7821a667d388d07ab1f55870e1f2296c0ec6438",
    "capability_scope": "30e49123c3399e7e08456ccb257b31e4350c3aa23e17c32cad62cdd5f3aa900d",
    "command": "511ba2e7c193676777d0b1b170a6a2b511a37de3bd0159c354e085655c1a34b9",
    "execution_mapping": "99b32fd2db4fd2d7fe4ace8f107bc4f1bd0e445ebd5de72e7de703668436c010",
    "failure_protocol": "8e8ec68a29645cb8d760a79600bd579d570ee0a6b0d23622e145542227225cb5",
    "operator_preflight": "57b3b2173f3417e024a0dc2271ed2c7b31613bf0f49e8a4a54146ee611084f46",
    "repository_attestation_interface": "dcdc92a807f05fdfdcc1ec5078f886f52c23e7a2c0c4011951a084e3b88cc695",
    "trusted_clock_interface": "8841f054645d949bdcad293b43010735b35fee1ba1174e5a9cdcd91456b94371",
    "validation_manifest": "953c8fcfbf4662c9ef81e7f030fb6d78248989c56c34d879531a95ca4addd6f3",
}

ROOT_FIELDS = {
    "authorization_package",
    "capability_scope",
    "command",
    "contract_identity",
    "execution_mapping",
    "failure_protocol",
    "historical_lineage",
    "operator_preflight",
    "prospective_as_of",
    "repository_attestation_interface",
    "schema_version",
    "section_identities",
    "trusted_clock_interface",
    "validation_manifest",
    "version",
}

COMMAND_ARGV = [
    ".venv/bin/python",
    "scripts/run_professional_strategy_olympics_v005.py",
    "--authorization",
    "{authorization_path}",
    "--source-root",
    "{detached_source_root}",
    "--consumption-root",
    "{consumption_root}",
    "--artifact-root",
    "{artifact_root}",
    "--clock-attestation",
    "{execution_clock_attestation_path}",
]
PACKAGE_MANIFEST_FIELDS = [
    "schema_version",
    "package_identity",
    "operator_interface_identity",
    "authorization_identity",
    "authorized_source_commit",
    "authorized_source_tree",
    "authoritative_run_identity",
    "record_index",
]
RECORD_INDEX_FIELDS = [
    "artifact_type",
    "artifact_identity",
    "relative_path",
    "canonical_bytes_sha256",
]
BOOTSTRAP_FIELDS = [
    "schema_version",
    "bootstrap_identity",
    "v005_governance_identity",
    "v005_command_identity",
    "system_account_identity",
    "peer_uid",
    "verifier_socket_path",
    "initial_clock_request_identity",
    "initial_clock_evidence_identity",
    "initial_clock_verifier_attestation_identity",
    "initial_clock_attestation_identity",
]


class OlympicsOperatorInterfaceV006Error(ValueError):
    """The V006 operator-interface contract is malformed or inconsistent."""


def _reject(message: str) -> None:
    raise OlympicsOperatorInterfaceV006Error(message)


def _exact_mapping(
    value: object,
    expected_keys: set[str],
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        _reject(f"{name} field inventory changed")
    return value


def _unique_strings(value: object, name: str) -> list[str]:
    if (
        type(value) is not list
        or not value
        or any(type(item) is not str or not item for item in value)
        or len(value) != len(set(value))
    ):
        _reject(f"{name} must be nonempty and unique")
    return value


def _section_projection(
    name: str,
    value: Mapping[str, object],
) -> object:
    section = value[name]
    if name == "command":
        if not isinstance(section, Mapping):
            _reject("command is malformed")
        return {key: item for key, item in section.items() if key != "command_identity"}
    return section


def validate_contract(value: Mapping[str, object], root: Path | None = None) -> dict[str, object]:
    """Validate the exact V006 design contract and predecessor bindings."""
    _exact_mapping(value, ROOT_FIELDS, "root")
    if value["schema_version"] != SCHEMA or value["version"] != VERSION:
        _reject("schema or version changed")
    parse_canonical_timestamp(value["prospective_as_of"])

    scope = _exact_mapping(
        value["capability_scope"],
        {
            "authorization_created",
            "authorization_creation_implemented",
            "execution_implemented",
            "official_run_authorized",
            "official_run_executed",
            "operator_interface_frozen",
            "protected_inputs_accessed",
            "rankings_or_results_created",
            "validation_or_holdout_accessed",
        },
        "capability scope",
    )
    if scope["operator_interface_frozen"] is not True or any(
        scope[key] is not False for key in scope if key != "operator_interface_frozen"
    ):
        _reject("design-only capability boundary changed")

    command = _exact_mapping(
        value["command"],
        {
            "argv",
            "command_identity",
            "domain",
            "entry_point",
            "environment",
            "shell",
            "working_directory",
        },
        "command",
    )
    if (
        command["argv"] != COMMAND_ARGV
        or command["domain"] != COMMAND_DOMAIN
        or command["entry_point"] != "scripts/run_professional_strategy_olympics_v005.py"
        or command["environment"]
        != {"LANG": "C", "LC_ALL": "C", "PYTHONHASHSEED": "0", "TZ": "UTC"}
        or command["shell"] is not False
        or command["working_directory"] != "detached_source_root"
    ):
        _reject("operator command changed")
    command_projection = _section_projection("command", value)
    if (
        command["command_identity"] != COMMAND_IDENTITY
        or domain_hash(COMMAND_DOMAIN, command_projection) != COMMAND_IDENTITY
    ):
        _reject("operator command identity changed")

    package = _exact_mapping(
        value["authorization_package"],
        {
            "authorization_relative_path",
            "closed_world",
            "documentary_binding_relative_path",
            "external_identity_policy",
            "identity_domain",
            "identity_equation",
            "manifest_relative_path",
            "package_manifest_fields",
            "record_index_fields",
            "record_order",
            "root_derivation",
            "schema_version",
            "storage",
            "unknown_or_duplicate_records",
        },
        "authorization package",
    )
    if (
        package["package_manifest_fields"] != PACKAGE_MANIFEST_FIELDS
        or package["record_index_fields"] != RECORD_INDEX_FIELDS
        or package["schema_version"]
        != "aml.professional-strategy-olympics.operator-package.v006"
    ):
        _reject("operator-package schema changed")

    clock = _exact_mapping(
        value["trusted_clock_interface"],
        {
            "bootstrap_authority",
            "bootstrap_fields",
            "bootstrap_format",
            "bootstrap_identity_domain",
            "bootstrap_input",
            "bootstrap_validation",
            "connection",
            "failure",
            "framing",
            "network_in_operator",
            "one_request_per_event",
            "request",
            "response",
            "timeout_milliseconds",
            "trust_boundary",
            "verifier_reuse",
        },
        "trusted clock interface",
    )
    if (
        clock["network_in_operator"] != "prohibited"
        or clock["one_request_per_event"] is not True
        or clock["timeout_milliseconds"] != 5000
        or clock["bootstrap_fields"] != BOOTSTRAP_FIELDS
        or clock["bootstrap_identity_domain"]
        != "aml.olympics.v006.clock-verifier-bootstrap"
    ):
        _reject("clock trust or timeout boundary changed")

    repository = _exact_mapping(
        value["repository_attestation_interface"],
        {"format", "freshness", "input", "network_in_operator", "substitution", "trust_boundary"},
        "repository attestation interface",
    )
    if repository["network_in_operator"] != "prohibited":
        _reject("repository-attestation network boundary changed")

    preflight = _exact_mapping(
        value["operator_preflight"],
        {"authorization_rules", "environment_rules", "package_rules"},
        "operator preflight",
    )
    for key in ("authorization_rules", "environment_rules", "package_rules"):
        _unique_strings(preflight[key], f"preflight {key}")

    mapping = _exact_mapping(
        value["execution_mapping"],
        {
            "authoritative_run_equation",
            "authoritative_run_function",
            "authoritative_run_timing",
            "build_order",
            "legacy_V003_consumption",
            "legacy_V004_consume_and_build",
            "projected_human_approval_reference",
            "projection_policy",
            "result_equivalence",
            "strategy_or_scoring_changes",
            "v004_authorization_projection",
        },
        "execution mapping",
    )
    if type(mapping["build_order"]) is not list or len(mapping["build_order"]) != 13:
        _reject("execution build order changed")
    if (
        mapping["legacy_V003_consumption"] != "must_not_be_called"
        or not str(mapping["legacy_V004_consume_and_build"]).startswith("must_not_be_called")
        or mapping["strategy_or_scoring_changes"] != "prohibited"
    ):
        _reject("legacy consumption or research-isolation boundary changed")
    projection_fields = mapping["v004_authorization_projection"]
    if not isinstance(projection_fields, Mapping) or set(projection_fields) != set(
        V004_AUTHORIZATION_FIELDS
    ):
        _reject("V004 authorization projection field inventory changed")

    _exact_mapping(
        value["failure_protocol"],
        {
            "ambiguous_external_attestation",
            "clock_verifier_disconnect",
            "crash_recovery",
            "existing_output",
            "missing_external_attestation",
            "unsupported_APFS_or_F_FULLFSYNC",
            "V004_projection_mismatch",
            "write_collision",
        },
        "failure protocol",
    )
    manifest = _exact_mapping(
        value["validation_manifest"],
        {
            "authorization_artifact_present",
            "design_only",
            "execution_entry_point_present",
            "next_required_milestone",
            "operator_contract_frozen",
            "status",
            "trial_artifacts_present",
        },
        "validation manifest",
    )
    if (
        manifest["authorization_artifact_present"] is not False
        or manifest["design_only"] is not True
        or manifest["execution_entry_point_present"] is not False
        or manifest["operator_contract_frozen"] is not True
        or manifest["trial_artifacts_present"] is not False
    ):
        _reject("validation-only status changed")

    lineage = _exact_mapping(
        value["historical_lineage"],
        {
            "design_base_commit",
            "immutable_tag_name",
            "immutable_tag_object",
            "immutable_tagged_commit",
            "v001_orchestrator_identity",
            "v001_orchestrator_implementation_identity",
            "v004_execution_contract_identity",
            "v004_execution_implementation_identity",
            "v004_scoring_identity",
            "v005_command_identity",
            "v005_governance_identity",
        },
        "historical lineage",
    )
    expected_lineage = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_name": TAG_NAME,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v001_orchestrator_identity": ORCHESTRATOR_IDENTITY,
        "v001_orchestrator_implementation_identity": "fe4bda0a9f8ad68fd099847ba2cbaed2a006a0cf832b07e03d39a3dd96a600b0",
        "v004_execution_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_execution_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v004_scoring_identity": BUNDLE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
    }
    if dict(lineage) != expected_lineage:
        _reject("historical lineage changed")

    section_identities = _exact_mapping(
        value["section_identities"], set(SECTION_NAMES), "section identities"
    )
    for name in SECTION_NAMES:
        expected = EXPECTED_SECTION_IDENTITIES[name]
        actual = domain_hash(f"aml.olympics.v006.section.{name}", _section_projection(name, value))
        if section_identities[name] != expected or actual != expected:
            _reject(f"{name} section identity changed")

    projection = {key: item for key, item in value.items() if key != "contract_identity"}
    if (
        value["contract_identity"] != CONTRACT_IDENTITY
        or domain_hash(CONTRACT_DOMAIN, projection) != CONTRACT_IDENTITY
    ):
        _reject("operator-interface identity changed")

    if root is not None:
        load_v005_contract(root)
        if v004_implementation_identity(root) != V004_IMPLEMENTATION_IDENTITY:
            _reject("V004 execution implementation identity changed")
        if orchestrator_implementation_identity(root) != expected_lineage[
            "v001_orchestrator_implementation_identity"
        ]:
            _reject("V001 orchestrator implementation identity changed")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    try:
        raw = (root / CONTRACT_PATH).read_bytes()
    except OSError as exc:
        raise OlympicsOperatorInterfaceV006Error("V006 contract is missing") from exc
    try:
        value = strict_json_bytes(raw, maximum_bytes=MAXIMUM_BYTES)
    except ValueError as exc:
        raise OlympicsOperatorInterfaceV006Error("V006 contract bytes are invalid") from exc
    return validate_contract(value, root)


def validate_repository_lineage(root: Path, *, check_tag: bool = True) -> dict[str, object]:
    """Verify merged ancestry and immutable tag without mutating the repository."""
    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise OlympicsOperatorInterfaceV006Error("repository lineage check failed") from exc

    head = git("rev-parse", "HEAD")
    if not GIT_RE.fullmatch(head):
        _reject("HEAD is not a SHA-1 commit")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", DESIGN_BASE_COMMIT, "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise OlympicsOperatorInterfaceV006Error("design base is not an ancestor") from exc
    result = {"design_base_is_ancestor": True, "head": head}
    if check_tag:
        tag_object = git("rev-parse", TAG_NAME)
        tagged_commit = git("rev-parse", f"{TAG_NAME}^{{}}")
        if tag_object != TAG_OBJECT or tagged_commit != TAGGED_COMMIT:
            _reject("immutable baseline tag changed")
        result.update({"tag_object": tag_object, "tagged_commit": tagged_commit})
    return result


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    return canonical_bytes(validate_contract(value))


def authoritative_run_identity(root: Path, authorized_source_commit: str) -> str:
    """Reproduce the run identity required in a future V005 authorization."""
    if type(authorized_source_commit) is not str or not GIT_RE.fullmatch(
        authorized_source_commit
    ):
        _reject("authorized source commit is invalid")
    load_contract(root)
    return v004_lineage_run_identity(root, authorized_source_commit)


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    report = {
        "authorization_created": False,
        "execution_implemented": False,
        "official_run_executed": False,
        "operator_command_identity": COMMAND_IDENTITY,
        "operator_interface_identity": CONTRACT_IDENTITY,
        "remaining_external_prerequisites": [
            "human_approved_authorization_package",
            "independent_clock_verifier",
            "independent_repository_attestation",
            "separately_implemented_and_audited_V005_operator",
        ],
        "status": contract["validation_manifest"]["status"],
    }
    return canonical_bytes(report)
