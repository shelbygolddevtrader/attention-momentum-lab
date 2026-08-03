"""Pure validation for Olympics execution-runtime governance V010.

V010 resolves runtime placement and command supersession only.  This module
does not create a runtime, launch a process, authorize execution, access a
network, or run the Olympics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Any
import unicodedata

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_IDENTITY as V005_COMMAND_IDENTITY,
    CONTRACT_IDENTITY as V005_GOVERNANCE_IDENTITY,
    TAGGED_COMMIT,
    TAG_OBJECT,
    V004_CONTRACT_IDENTITY,
    V004_IMPLEMENTATION_IDENTITY,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    strict_json_bytes,
    validate_artifact as validate_v005_artifact,
)
from aml.professional_strategy_olympics_clock_continuation_v008 import (
    CONTRACT_IDENTITY as V008_CLOCK_CONTINUATION_IDENTITY,
    load_contract as load_v008_contract,
    validate_continuation_record as validate_v008_continuation_record,
    validate_contract as validate_v008_contract,
)
from aml.professional_strategy_olympics_documentary_proof_transport_v009 import (
    CONTRACT_IDENTITY as V009_DOCUMENTARY_PROOF_IDENTITY,
    load_contract as load_v009_contract,
)
from aml.professional_strategy_olympics_execution_publication_v004 import (
    implementation_identity as v004_implementation_identity,
)
from aml.professional_strategy_olympics_operator_interface_v006 import (
    CONTRACT_IDENTITY as V006_OPERATOR_INTERFACE_IDENTITY,
    load_contract as load_v006_contract,
)
from aml.professional_strategy_olympics_runtime_boundary_v007 import (
    CONTRACT_IDENTITY as V007_RUNTIME_BOUNDARY_IDENTITY,
    load_contract as load_v007_contract,
)


CONTRACT_PATH = "config/professional_strategy_olympics_execution_runtime_v010.json"
SCHEMA = "aml.professional-strategy-olympics.execution-runtime.v010"
VERSION = "professional-strategy-olympics-execution-runtime-v010"
CONTRACT_DOMAIN = "aml.olympics.v010.execution-runtime"
COMMAND_DOMAIN = "aml.olympics.v010.command"
CONTRACT_IDENTITY = "1f61ef16f1e843de01cf7dcebad357ee4bfd7c16191c71270fa7ae97bb9c326a"
COMMAND_IDENTITY = "f9d7923bf58a6055e2276d4bdbe4c474f5c0ab7d7d6752dabc7648461fb04c75"
DESIGN_BASE_COMMIT = "97fe1f8439d54ba9e53f79f752972066d59bfb72"
MAXIMUM_CONTRACT_BYTES = 250_000
MAXIMUM_RECORD_BYTES = 2_000_000

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
RELATIVE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ABI_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

SECTION_NAMES = (
    "inheritance",
    "contradiction_resolution",
    "runtime_placement",
    "command_supersession",
    "runtime_schemas",
    "runtime_inventory",
    "dependency_closure",
    "virtual_environment",
    "source_boundary",
    "source_runtime_separation",
    "launch_semantics",
    "environment_closure",
    "package_integration",
    "preflight_order",
    "error_status_model",
    "authority_boundary",
    "validation_manifest",
)

EXPECTED_SECTION_IDENTITIES = {
    "inheritance": "53019322624541c6a47ac4f063dadd17e0c73c15178771f4348139ef7672398a",
    "contradiction_resolution": "b3f1f50bfb28b4498c70b9fd24a6ec6b9b655613fb0f5274672e4c7f2560c2f8",
    "runtime_placement": "ddb10b75c09a399c15d60d0c931016a325e03e79a2355bcbeb19bdf294e3e99a",
    "command_supersession": "6393f44432e6ff144527ea075175b263ed00ebef7890ff87b570f5a96f1f023a",
    "runtime_schemas": "3142a97e7888edf1c18e7ee4ffce012d032a050d9dbbf6cff8111cb30b25becb",
    "runtime_inventory": "89ab4ec2926eab286df1e8907b1955fcb262fcf78e7acff5fd47ad8fa0cd3b61",
    "dependency_closure": "f6c64cd77b461b83daa2231c5ecd11ca22edd88ca6c117ba64170eff5cb831c4",
    "virtual_environment": "be3d0e9fc90877c7489984c2edf927138f149809563ab4d66243041ade97a0c3",
    "source_boundary": "849873b0a376f692b9727c50c796c3c71b8216a0ce8d1d7a2c13b030391f685e",
    "source_runtime_separation": "2b643b139886823e80e0fa8bd21864910ae669cf9fd70650a7ebbf596c1c9ed2",
    "launch_semantics": "85983f9d1b37234fcc2c32ef89fda4c1cf2c344a000eb2a2cb143a185a963dc2",
    "environment_closure": "a275b1eff92c4c7352385eeed3cd06c30aae2323bd7d9ccf1cce0f4c9a0c1782",
    "package_integration": "c72acc8f28fecce8bdabff91f3f38e6e58f22a690f3461cfaae8ee32d7d28727",
    "preflight_order": "c62b72acb4d95197e81941b7ddaa2e254184636224099305a9543e0ea7868f54",
    "error_status_model": "ded03439466f760703ae813b6beba274d79283fdb4b3985ec58c08fcd2360a07",
    "authority_boundary": "eee5186eeb1e2c273a360850d8f733867071f7f38c5de151df2685f2ead83c7a",
    "validation_manifest": "1c3b20abc9c7618206d9cd1f9f32a132a548bfe1336b133aaab6d95e889f2f48",
}

DESCRIPTOR_FIELDS = {
    "schema_version",
    "runtime_descriptor_identity",
    "v010_contract_identity",
    "v009_documentary_proof_identity",
    "v008_clock_continuation_identity",
    "v007_runtime_boundary_identity",
    "v006_operator_interface_identity",
    "v005_governance_identity",
    "historical_v005_command_identity",
    "v004_contract_identity",
    "v004_implementation_identity",
    "successor_command_identity",
    "authorization_identity",
    "operator_implementation_identity",
    "package_binding_identity",
    "v006_operator_package_identity",
    "v007_runtime_package_identity",
    "v009_documentary_proof_package_identity",
    "runtime_root",
    "interpreter_relative_path",
    "interpreter_file_identity",
    "runtime_inventory_identity",
    "runtime_content_identity",
    "package_environment_identity",
    "dependency_lock_identity",
    "platform",
    "architecture",
    "operating_system_build",
    "platform_cache_set_identity",
    "python_implementation",
    "python_version",
    "python_abi",
    "filesystem",
    "volume_uuid",
    "root_owner_uid",
    "root_owner_gid",
    "root_mode",
    "root_acl_present",
    "root_xattrs",
    "root_file_flags",
    "mount_policy",
    "runtime_mutation_policy",
    "platform_boundary_identity",
}

INVENTORY_FIELDS = {
    "schema_version",
    "runtime_inventory_identity",
    "v010_contract_identity",
    "successor_command_identity",
    "authorization_identity",
    "operator_implementation_identity",
    "package_binding_identity",
    "runtime_content_identity",
    "runtime_root",
    "filesystem",
    "volume_uuid",
    "root_owner_uid",
    "root_owner_gid",
    "root_mode",
    "root_acl_present",
    "root_xattrs",
    "root_file_flags",
    "interpreter_relative_path",
    "python_import_roots",
    "directories",
    "files",
    "macho_dependencies",
    "platform_cache_files",
    "platform_dependencies",
    "prohibited_python_artifacts_absent",
}

FILE_FIELDS = {
    "relative_path",
    "file_identity",
    "file_type",
    "mode",
    "byte_length",
    "raw_bytes_sha256",
    "owner_uid",
    "owner_gid",
    "hard_link_count",
    "executable",
    "macho",
    "macho_dependency_count",
    "embedded_code_signature_sha256",
    "acl_present",
    "xattrs",
    "file_flags",
}
DIRECTORY_FIELDS = {
    "relative_path",
    "mode",
    "owner_uid",
    "owner_gid",
    "acl_present",
    "xattrs",
    "file_flags",
}
MACHO_FIELDS = {
    "image_relative_path",
    "load_command",
    "declared_dependency",
    "resolved_kind",
    "resolved_path",
    "dependency_file_identity",
}
PLATFORM_DEPENDENCY_FIELDS = {
    "absolute_path",
    "file_identity",
    "byte_length",
    "raw_bytes_sha256",
    "image_uuid",
    "storage_kind",
    "platform_cache_set_identity",
    "platform_boundary_identity",
}
PLATFORM_CACHE_FILE_FIELDS = {
    "absolute_path",
    "file_identity",
    "mode",
    "byte_length",
    "raw_bytes_sha256",
    "owner_uid",
    "owner_gid",
    "hard_link_count",
}

SOURCE_OBSERVATION_FIELDS = {
    "schema_version",
    "source_observation_identity",
    "authorization_identity",
    "operator_implementation_identity",
    "observation_phase",
    "source_root",
    "source_root_device_id",
    "source_root_mount_id",
    "source_root_volume_uuid",
    "source_root_inode",
    "source_root_mode",
    "source_filesystem",
    "source_read_only_mount",
    "source_local_device",
    "source_disk_image",
    "source_removable",
    "source_network_filesystem",
    "source_mutation_detected",
    "tracked_inventory_identity",
    "manifest_exclusion",
    "ignored_objects",
    "untracked_objects",
    "extra_objects",
    "symlink_objects",
    "hard_link_objects",
    "mount_crossings",
    "unsupported_objects",
    "case_aliases",
    "unicode_aliases",
    "filesystem_walk_complete",
    "git_status_used_as_sole_evidence",
}

RUNTIME_OBSERVATION_FIELDS = {
    "schema_version",
    "runtime_observation_identity",
    "runtime_descriptor_identity",
    "runtime_inventory_identity",
    "platform_boundary_identity",
    "platform_cache_set_identity",
    "observation_phase",
    "runtime_root",
    "runtime_root_device_id",
    "runtime_root_mount_id",
    "runtime_root_volume_uuid",
    "runtime_root_inode",
    "runtime_root_mode",
    "runtime_root_owner_uid",
    "runtime_root_owner_gid",
    "filesystem",
    "read_only_mount",
    "local_device",
    "disk_image",
    "removable",
    "network_filesystem",
    "inventory_complete",
    "observed_file_identities",
    "observed_directory_paths",
    "observed_platform_cache_file_identities",
    "macho_closure_complete",
    "python_import_closure_complete",
    "metadata_closure_complete",
    "symlink_objects",
    "hard_link_objects",
    "mount_crossings",
    "unsupported_objects",
    "case_aliases",
    "unicode_aliases",
    "mutation_detected",
}

PACKAGE_FIELDS = {
    "schema_version",
    "package_identity",
    "package_binding_identity",
    "v010_contract_identity",
    "successor_command_identity",
    "authorization_identity",
    "operator_implementation_identity",
    "v006_operator_package_identity",
    "v007_runtime_package_identity",
    "v008_clock_continuation_identity",
    "v009_documentary_proof_package_identity",
    "runtime_descriptor_identity",
    "runtime_inventory_identity",
    "runtime_descriptor_relative_path",
    "runtime_inventory_relative_path",
    "v006_record_index_extensions",
    "v007_supplemental_manifest_entries",
}

INDEX_V006_FIELDS = {
    "artifact_type",
    "artifact_identity",
    "relative_path",
    "canonical_bytes_sha256",
}
INDEX_V007_FIELDS = {*INDEX_V006_FIELDS, "schema_version"}


class OlympicsExecutionRuntimeV010Error(ValueError):
    """A V010 contract or runtime-boundary invariant failed."""


def _reject(code: str, detail: str) -> None:
    raise OlympicsExecutionRuntimeV010Error(f"{code}:{detail}")


def _exact(value: object, fields: set[str], detail: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _reject("V010_SCHEMA", detail)
    return value


def _identity(value: object, detail: str) -> str:
    if type(value) is not str or not HASH_RE.fullmatch(value):
        _reject("V010_SCHEMA", detail)
    return value


def _uuid(value: object, detail: str) -> str:
    if type(value) is not str or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ):
        _reject("V010_SCHEMA", detail)
    return value


def _uint(value: object, detail: str, maximum: int = 9_223_372_036_854_775_807) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        _reject("V010_SCHEMA", detail)
    return value


def _absolute_path(value: object, detail: str) -> str:
    if (
        type(value) is not str
        or not value.startswith("/")
        or value == "/"
        or value.endswith("/")
        or "//" in value
        or "\\" in value
        or len(value.encode("utf-8")) > 1024
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        _reject("V010_PATH", detail)
    if unicodedata.normalize("NFC", value) != value or "\x00" in value:
        _reject("V010_PATH", detail)
    raw_parts = value[1:].split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        _reject("V010_PATH", detail)
    if str(PurePosixPath(value)) != value:
        _reject("V010_PATH", detail)
    return value


def _relative_path(value: object, detail: str) -> str:
    if (
        type(value) is not str
        or not RELATIVE_RE.fullmatch(value)
        or value.endswith("/")
        or "//" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        _reject("V010_PATH", detail)
    if any(part in {"", ".", ".."} for part in PurePosixPath(value).parts):
        _reject("V010_PATH", detail)
    return value


def _loader_reference(value: object, detail: str) -> str:
    if type(value) is not str:
        _reject("V010_DYNAMIC_LOADER_DEPENDENCY", detail)
    if value.startswith("/"):
        return _absolute_path(value, detail)
    for prefix in ("@executable_path/", "@loader_path/"):
        if value.startswith(prefix):
            suffix = value.removeprefix(prefix)
            if not suffix or suffix.startswith("/"):
                _reject("V010_DYNAMIC_LOADER_DEPENDENCY", detail)
            _relative_path(suffix, detail)
            return value
    _reject("V010_DYNAMIC_LOADER_DEPENDENCY", detail)


def _resolve_loader_reference(
    declared: object, source: str, descriptor: Mapping[str, object]
) -> tuple[str, str]:
    value = _loader_reference(declared, "declared_dependency")
    runtime_root = str(descriptor["runtime_root"])
    if value.startswith("/"):
        runtime_prefix = f"{runtime_root}/"
        if value.startswith(runtime_prefix):
            return "runtime", _relative_path(
                value.removeprefix(runtime_prefix), "absolute_runtime_dependency"
            )
        return "platform", value
    if value.startswith("@loader_path/"):
        suffix = value.removeprefix("@loader_path/")
        base = PurePosixPath(source).parent
    else:
        suffix = value.removeprefix("@executable_path/")
        base = PurePosixPath(str(descriptor["interpreter_relative_path"])).parent
    resolved = str(base / suffix)
    return "runtime", _relative_path(resolved, "resolved_runtime_dependency")


def _metadata_absent(value: Mapping[str, object], detail: str) -> None:
    if (
        value["acl_present"] is not False
        or value["xattrs"] != []
        or value["file_flags"] != []
    ):
        _reject("V010_RUNTIME_INVENTORY", detail)


def _reject_casefold_aliases(paths: Sequence[str], detail: str) -> None:
    aliases = [path.casefold() for path in paths]
    if len(aliases) != len(set(aliases)):
        _reject("V010_PATH", detail)


def _canonical_record_bytes(value: object, detail: str) -> bytes:
    try:
        raw = canonical_bytes(value)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise OlympicsExecutionRuntimeV010Error(f"V010_SCHEMA:{detail}") from exc
    if len(raw) > MAXIMUM_RECORD_BYTES:
        _reject("V010_RESOURCE_LIMIT", detail)
    return raw


def _record_identity(domain: str, value: Mapping[str, object], field: str) -> str:
    return domain_hash(
        domain, {key: item for key, item in value.items() if key != field}
    )


RUNTIME_CONTENT_FIELDS = (
    "runtime_root",
    "filesystem",
    "volume_uuid",
    "root_owner_uid",
    "root_owner_gid",
    "root_mode",
    "root_acl_present",
    "root_xattrs",
    "root_file_flags",
    "interpreter_relative_path",
    "python_import_roots",
    "directories",
    "files",
    "macho_dependencies",
    "platform_cache_files",
    "platform_dependencies",
    "prohibited_python_artifacts_absent",
)


def runtime_content_identity(inventory: Mapping[str, object]) -> str:
    if any(field not in inventory for field in RUNTIME_CONTENT_FIELDS):
        _reject("V010_SCHEMA", "runtime_content_fields")
    return domain_hash(
        "aml.olympics.v010.runtime-content",
        {field: inventory[field] for field in RUNTIME_CONTENT_FIELDS},
    )


def dependency_lock_identity(
    inventory: Mapping[str, object], descriptor: Mapping[str, object]
) -> str:
    files = inventory.get("files")
    roots = inventory.get("python_import_roots")
    if type(files) is not list or type(roots) is not list:
        _reject("V010_SCHEMA", "dependency_lock_fields")
    file_identities = []
    for item in files:
        if not isinstance(item, Mapping) or "file_identity" not in item:
            _reject("V010_SCHEMA", "dependency_lock_file")
        file_identities.append(_identity(item["file_identity"], "dependency_file"))
    return domain_hash(
        "aml.olympics.v010.dependency-lock",
        {
            "python_implementation": descriptor["python_implementation"],
            "python_version": descriptor["python_version"],
            "python_abi": descriptor["python_abi"],
            "architecture": descriptor["architecture"],
            "interpreter_file_identity": descriptor["interpreter_file_identity"],
            "python_import_roots": roots,
            "runtime_file_identities": file_identities,
        },
    )


def descriptor_relative_path(authorization_identity: str) -> str:
    _identity(authorization_identity, "authorization_identity")
    return f"runtime/{authorization_identity}/execution_runtime_descriptor_v010.json"


def inventory_relative_path(authorization_identity: str) -> str:
    _identity(authorization_identity, "authorization_identity")
    return f"runtime/{authorization_identity}/execution_runtime_inventory_v010.json"


def package_relative_path(authorization_identity: str) -> str:
    _identity(authorization_identity, "authorization_identity")
    return (
        f"authorizations/{authorization_identity}/execution_runtime_package_v010.json"
    )


def validate_package_root(
    package_root: object,
    authorization_path: object,
    authorization_identity: object,
) -> None:
    """Require V010 to use the package root already derived by V005/V007."""
    root = _absolute_path(package_root, "package_root")
    path = _absolute_path(authorization_path, "authorization_path")
    identity = _identity(authorization_identity, "authorization_identity")
    expected = f"{root}/authorizations/{identity}/authorization.json"
    if path != expected:
        _reject("V010_PACKAGE_REACHABILITY", "package_root")


def validate_descriptor(
    descriptor: Mapping[str, object], contract: Mapping[str, object]
) -> dict[str, object]:
    validate_contract(contract)
    value = _exact(descriptor, DESCRIPTOR_FIELDS, "runtime_descriptor")
    _canonical_record_bytes(value, "runtime_descriptor")
    expected = {
        "schema_version": contract["runtime_schemas"]["descriptor"]["schema_version"],
        "v010_contract_identity": CONTRACT_IDENTITY,
        "v009_documentary_proof_identity": V009_DOCUMENTARY_PROOF_IDENTITY,
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "historical_v005_command_identity": V005_COMMAND_IDENTITY,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "successor_command_identity": COMMAND_IDENTITY,
        "interpreter_relative_path": "bin/python3",
        "platform": "macos",
        "python_implementation": "cpython",
        "filesystem": "local_apfs",
        "root_mode": "0555",
        "root_acl_present": False,
        "root_xattrs": [],
        "root_file_flags": [],
        "mount_policy": "dedicated_read_only_local_apfs_volume",
        "runtime_mutation_policy": "prohibited_before_during_and_after_invocation",
    }
    if any(value[key] != item for key, item in expected.items()):
        _reject("V010_CROSS_VERSION_SUBSTITUTION", "descriptor_binding")
    for field in (
        "runtime_descriptor_identity",
        "authorization_identity",
        "operator_implementation_identity",
        "package_binding_identity",
        "v006_operator_package_identity",
        "v007_runtime_package_identity",
        "v009_documentary_proof_package_identity",
        "interpreter_file_identity",
        "runtime_inventory_identity",
        "runtime_content_identity",
        "package_environment_identity",
        "dependency_lock_identity",
        "platform_boundary_identity",
        "platform_cache_set_identity",
    ):
        _identity(value[field], field)
    _absolute_path(value["runtime_root"], "runtime_root")
    if value["architecture"] not in {"arm64", "x86_64"}:
        _reject("V010_SCHEMA", "architecture")
    if type(value["python_version"]) is not str or not SEMVER_RE.fullmatch(
        value["python_version"]
    ):
        _reject("V010_SCHEMA", "python_version")
    version_parts = tuple(int(part) for part in value["python_version"].split("."))
    if version_parts < (3, 11, 0):
        _reject("V010_SCHEMA", "python_version_minimum")
    expected_abi = (
        f"cp{version_parts[0]}{version_parts[1]}-macosx_{value['architecture']}"
    )
    if (
        type(value["python_abi"]) is not str
        or not ABI_RE.fullmatch(value["python_abi"])
        or value["python_abi"] != expected_abi
    ):
        _reject("V010_SCHEMA", "python_abi")
    _uint(value["root_owner_uid"], "root_owner_uid", 2_147_483_647)
    _uint(value["root_owner_gid"], "root_owner_gid", 2_147_483_647)
    _uuid(value["volume_uuid"], "volume_uuid")
    if type(value["operating_system_build"]) is not str or not re.fullmatch(
        r"[0-9]{2}[A-Z][0-9]{1,4}[a-z]?", value["operating_system_build"]
    ):
        _reject("V010_SCHEMA", "operating_system_build")
    platform_boundary_identity = domain_hash(
        "aml.olympics.v010.platform-boundary",
        {
            "platform": value["platform"],
            "architecture": value["architecture"],
            "operating_system_build": value["operating_system_build"],
            "platform_cache_set_identity": value["platform_cache_set_identity"],
        },
    )
    if value["platform_boundary_identity"] != platform_boundary_identity:
        _reject("V010_PLATFORM_DEPENDENCY", "platform_boundary_identity")
    environment_identity = domain_hash(
        "aml.olympics.v010.package-environment",
        {
            "dependency_lock_identity": value["dependency_lock_identity"],
            "runtime_content_identity": value["runtime_content_identity"],
            "platform_boundary_identity": value["platform_boundary_identity"],
            "platform_cache_set_identity": value["platform_cache_set_identity"],
            "operating_system_build": value["operating_system_build"],
            "python_implementation": value["python_implementation"],
            "python_version": value["python_version"],
            "python_abi": value["python_abi"],
            "architecture": value["architecture"],
        },
    )
    if value["package_environment_identity"] != environment_identity:
        _reject("V010_DEPENDENCY_CLOSURE_UNCERTAIN", "environment_binding")
    if value["runtime_descriptor_identity"] != _record_identity(
        contract["runtime_schemas"]["descriptor"]["identity_domain"],
        value,
        "runtime_descriptor_identity",
    ):
        _reject("V010_RUNTIME_DESCRIPTOR_IDENTITY", "identity")
    return dict(value)


def _validate_file_entry(
    entry: object, descriptor: Mapping[str, object]
) -> dict[str, object]:
    item = _exact(entry, FILE_FIELDS, "runtime_file")
    path = _relative_path(item["relative_path"], "runtime_file_path")
    if item["file_type"] != "regular_file" or item["mode"] not in {"0444", "0555"}:
        _reject("V010_RUNTIME_MODE", path)
    if item["executable"] is not (item["mode"] == "0555"):
        _reject("V010_RUNTIME_MODE", path)
    if item["hard_link_count"] != 1 or type(item["hard_link_count"]) is not int:
        _reject("V010_RUNTIME_HARD_LINK", path)
    _uint(item["byte_length"], "runtime_file_length")
    _uint(item["macho_dependency_count"], "macho_dependency_count", 65_535)
    if type(item["macho"]) is not bool:
        _reject("V010_SCHEMA", "runtime_file_macho")
    if item["embedded_code_signature_sha256"] is not None:
        _identity(item["embedded_code_signature_sha256"], "code_signature_sha256")
    if item["macho"] is False and (
        item["macho_dependency_count"] != 0
        or item["embedded_code_signature_sha256"] is not None
    ):
        _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "non_macho_metadata")
    _metadata_absent(item, path)
    if (
        item["owner_uid"] != descriptor["root_owner_uid"]
        or item["owner_gid"] != descriptor["root_owner_gid"]
    ):
        _reject("V010_RUNTIME_OWNERSHIP", path)
    digest = _identity(item["raw_bytes_sha256"], "runtime_file_sha256")
    expected_identity = domain_hash(
        "aml.olympics.v010.runtime-file",
        {
            "relative_path": path,
            "file_type": "regular_file",
            "mode": item["mode"],
            "byte_length": item["byte_length"],
            "raw_bytes_sha256": digest,
            "owner_uid": item["owner_uid"],
            "owner_gid": item["owner_gid"],
            "hard_link_count": 1,
            "executable": item["executable"],
            "macho": item["macho"],
            "macho_dependency_count": item["macho_dependency_count"],
            "embedded_code_signature_sha256": item["embedded_code_signature_sha256"],
            "acl_present": False,
            "xattrs": [],
            "file_flags": [],
        },
    )
    if item["file_identity"] != expected_identity:
        _reject("V010_RUNTIME_FILE_IDENTITY", path)
    return dict(item)


def _sorted_unique(
    items: Sequence[Mapping[str, object]], field: str, detail: str
) -> None:
    values = [str(item[field]) for item in items]
    if values != sorted(values, key=lambda item: item.encode("utf-8")) or len(
        values
    ) != len(set(values)):
        _reject("V010_INVENTORY_ORDER", detail)


def validate_inventory(
    inventory: Mapping[str, object],
    descriptor: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    descriptor = validate_descriptor(descriptor, contract)
    value = _exact(inventory, INVENTORY_FIELDS, "runtime_inventory")
    _canonical_record_bytes(value, "runtime_inventory")
    expected = {
        "schema_version": contract["runtime_schemas"]["inventory"]["schema_version"],
        "v010_contract_identity": CONTRACT_IDENTITY,
        "successor_command_identity": COMMAND_IDENTITY,
        "authorization_identity": descriptor["authorization_identity"],
        "operator_implementation_identity": descriptor[
            "operator_implementation_identity"
        ],
        "package_binding_identity": descriptor["package_binding_identity"],
        "runtime_content_identity": descriptor["runtime_content_identity"],
        "runtime_root": descriptor["runtime_root"],
        "filesystem": descriptor["filesystem"],
        "volume_uuid": descriptor["volume_uuid"],
        "root_owner_uid": descriptor["root_owner_uid"],
        "root_owner_gid": descriptor["root_owner_gid"],
        "root_mode": descriptor["root_mode"],
        "root_acl_present": descriptor["root_acl_present"],
        "root_xattrs": descriptor["root_xattrs"],
        "root_file_flags": descriptor["root_file_flags"],
        "interpreter_relative_path": descriptor["interpreter_relative_path"],
        "prohibited_python_artifacts_absent": True,
    }
    if any(value[key] != item for key, item in expected.items()):
        _reject("V010_RUNTIME_INVENTORY", "binding")
    if value["runtime_content_identity"] != runtime_content_identity(value):
        _reject("V010_RUNTIME_INVENTORY", "content_identity")
    _uuid(value["volume_uuid"], "runtime_inventory_volume_uuid")
    _uint(value["root_owner_uid"], "runtime_inventory_root_owner_uid", 2_147_483_647)
    _uint(value["root_owner_gid"], "runtime_inventory_root_owner_gid", 2_147_483_647)
    if (
        value["root_acl_present"] is not False
        or value["root_xattrs"] != []
        or value["root_file_flags"] != []
    ):
        _reject("V010_RUNTIME_INVENTORY", "runtime_root_metadata")
    files_raw = value["files"]
    directories_raw = value["directories"]
    macho_raw = value["macho_dependencies"]
    cache_raw = value["platform_cache_files"]
    platform_raw = value["platform_dependencies"]
    roots = value["python_import_roots"]
    if (
        type(files_raw) is not list
        or not files_raw
        or type(directories_raw) is not list
        or not directories_raw
        or type(macho_raw) is not list
        or type(cache_raw) is not list
        or not cache_raw
        or type(platform_raw) is not list
        or not platform_raw
        or type(roots) is not list
        or roots != sorted(roots, key=lambda item: item.encode("utf-8"))
        or len(roots) != len(set(roots))
    ):
        _reject("V010_RUNTIME_INVENTORY", "collection")
    for root in roots:
        _relative_path(root, "python_import_root")
    files = [_validate_file_entry(item, descriptor) for item in files_raw]
    _sorted_unique(files, "relative_path", "files")
    file_by_path = {str(item["relative_path"]): item for item in files}
    if descriptor["interpreter_relative_path"] not in file_by_path:
        _reject("V010_INTERPRETER_ABSENT", "inventory")
    interpreter = file_by_path[str(descriptor["interpreter_relative_path"])]
    if (
        not interpreter["executable"]
        or interpreter["file_identity"] != descriptor["interpreter_file_identity"]
    ):
        _reject("V010_INTERPRETER_IDENTITY", "inventory")
    prohibited_names = {"sitecustomize.py", "usercustomize.py"}
    prohibited_venv_names = {
        "activate",
        "activate.csh",
        "activate.fish",
        "activate.ps1",
        "pyvenv.cfg",
    }
    prohibited_suffixes = (
        ".pth",
        ".egg-link",
        ".pyc",
        ".zip",
        ".whl",
        ".egg",
        ".pyz",
    )
    for path in file_by_path:
        name = PurePosixPath(path).name
        if (
            name in prohibited_names
            or name.casefold() in prohibited_venv_names
            or path.endswith(prohibited_suffixes)
        ):
            _reject("V010_PYTHON_IMPORT_INJECTION", path)
    directories = []
    for raw in directories_raw:
        item = _exact(raw, DIRECTORY_FIELDS, "runtime_directory")
        path = _relative_path(item["relative_path"], "runtime_directory_path")
        if PurePosixPath(path).name == "__pycache__":
            _reject("V010_PYTHON_IMPORT_INJECTION", path)
        if (
            item["mode"] != "0555"
            or item["owner_uid"] != descriptor["root_owner_uid"]
            or item["owner_gid"] != descriptor["root_owner_gid"]
        ):
            _reject("V010_RUNTIME_MODE", path)
        _metadata_absent(item, path)
        directories.append(dict(item))
    _sorted_unique(directories, "relative_path", "directories")
    directory_paths = {str(item["relative_path"]) for item in directories}
    if directory_paths & set(file_by_path):
        _reject("V010_RUNTIME_INVENTORY", "file_directory_path_collision")
    for path in [*file_by_path, *directory_paths]:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            if str(parent) not in directory_paths:
                _reject("V010_RUNTIME_INVENTORY", "missing_parent_directory")
            parent = parent.parent
    for root in roots:
        if root not in directory_paths:
            _reject("V010_PYTHON_IMPORT_INJECTION", "undeclared_import_root")
    _reject_casefold_aliases([*file_by_path, *directory_paths], "runtime_case_alias")

    cache_files = []
    for raw in cache_raw:
        item = _exact(raw, PLATFORM_CACHE_FILE_FIELDS, "platform_cache_file")
        path = _absolute_path(item["absolute_path"], "platform_cache_file_path")
        if (
            item["mode"] not in {"0555", "0755"}
            or item["owner_uid"] != 0
            or item["owner_gid"] not in {0, 80}
            or item["hard_link_count"] != 1
            or type(item["hard_link_count"]) is not int
        ):
            _reject("V010_PLATFORM_DEPENDENCY", path)
        _uint(item["byte_length"], "platform_cache_file_length")
        _identity(item["raw_bytes_sha256"], "platform_cache_file_sha256")
        expected_identity = domain_hash(
            "aml.olympics.v010.platform-cache-file",
            {key: entry for key, entry in item.items() if key != "file_identity"},
        )
        if item["file_identity"] != expected_identity:
            _reject("V010_PLATFORM_DEPENDENCY", "cache_file_identity")
        cache_files.append(dict(item))
    _sorted_unique(cache_files, "absolute_path", "platform_cache_files")
    _reject_casefold_aliases(
        [str(item["absolute_path"]) for item in cache_files],
        "platform_cache_case_alias",
    )
    cache_set_identity = domain_hash(
        "aml.olympics.v010.platform-cache-set",
        {
            "architecture": descriptor["architecture"],
            "operating_system_build": descriptor["operating_system_build"],
            "cache_file_identities": [item["file_identity"] for item in cache_files],
        },
    )
    if cache_set_identity != descriptor["platform_cache_set_identity"]:
        _reject("V010_PLATFORM_DEPENDENCY", "cache_set_identity")
    platform = []
    for raw in platform_raw:
        item = _exact(raw, PLATFORM_DEPENDENCY_FIELDS, "platform_dependency")
        path = _absolute_path(item["absolute_path"], "platform_dependency_path")
        if item["storage_kind"] != "dyld_shared_cache_image":
            _reject("V010_PLATFORM_DEPENDENCY", path)
        _uint(item["byte_length"], "platform_dependency_length")
        _identity(item["raw_bytes_sha256"], "platform_dependency_sha256")
        _uuid(item["image_uuid"], "platform_dependency_image_uuid")
        if (
            item["platform_boundary_identity"]
            != descriptor["platform_boundary_identity"]
            or item["platform_cache_set_identity"]
            != descriptor["platform_cache_set_identity"]
        ):
            _reject("V010_PLATFORM_DEPENDENCY", "boundary")
        expected_identity = domain_hash(
            "aml.olympics.v010.platform-dependency",
            {key: entry for key, entry in item.items() if key != "file_identity"},
        )
        if item["file_identity"] != expected_identity:
            _reject("V010_PLATFORM_DEPENDENCY", "identity")
        platform.append(dict(item))
    _sorted_unique(platform, "absolute_path", "platform_dependencies")
    _reject_casefold_aliases(
        [str(item["absolute_path"]) for item in platform],
        "platform_dependency_case_alias",
    )
    platform_by_path = {str(item["absolute_path"]): item for item in platform}
    macho = []
    graph_counts: dict[str, int] = {}
    for raw in macho_raw:
        item = _exact(raw, MACHO_FIELDS, "macho_dependency")
        source = _relative_path(item["image_relative_path"], "macho_image")
        if source not in file_by_path or file_by_path[source]["macho"] is not True:
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "image")
        if item["load_command"] not in {"LC_LOAD_DYLIB", "LC_LOAD_WEAK_DYLIB"}:
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "load_command")
        expected_kind, expected_path = _resolve_loader_reference(
            item["declared_dependency"], source, descriptor
        )
        if (
            item["resolved_kind"] != expected_kind
            or item["resolved_path"] != expected_path
        ):
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "resolution")
        if item["resolved_kind"] == "runtime":
            resolved = _relative_path(item["resolved_path"], "macho_runtime_dependency")
            target = file_by_path.get(resolved)
        elif item["resolved_kind"] == "platform":
            resolved = _absolute_path(
                item["resolved_path"], "macho_platform_dependency"
            )
            target = platform_by_path.get(resolved)
        else:
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "resolved_kind")
        if (
            target is None
            or item["dependency_file_identity"] != target["file_identity"]
        ):
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "resolved_identity")
        graph_counts[source] = graph_counts.get(source, 0) + 1
        macho.append(dict(item))
    macho_keys = [
        (
            str(item["image_relative_path"]).encode(),
            str(item["declared_dependency"]).encode(),
            str(item["resolved_path"]).encode(),
        )
        for item in macho
    ]
    if macho_keys != sorted(macho_keys) or len(macho_keys) != len(set(macho_keys)):
        _reject("V010_INVENTORY_ORDER", "macho_dependencies")
    for path, item in file_by_path.items():
        expected_count = item["macho_dependency_count"] if item["macho"] else 0
        if graph_counts.get(path, 0) != expected_count:
            _reject("V010_DYNAMIC_LOADER_DEPENDENCY", "graph_completeness")
    if descriptor["dependency_lock_identity"] != dependency_lock_identity(
        value, descriptor
    ):
        _reject("V010_DEPENDENCY_CLOSURE_UNCERTAIN", "dependency_lock_identity")
    if value["runtime_inventory_identity"] != _record_identity(
        contract["runtime_schemas"]["inventory"]["identity_domain"],
        value,
        "runtime_inventory_identity",
    ):
        _reject("V010_RUNTIME_INVENTORY", "identity")
    if value["runtime_inventory_identity"] != descriptor["runtime_inventory_identity"]:
        _reject("V010_RUNTIME_INVENTORY", "descriptor_identity")
    return dict(value)


def validate_source_observation(
    observation: Mapping[str, object],
    descriptor: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    descriptor = validate_descriptor(descriptor, contract)
    value = _exact(observation, SOURCE_OBSERVATION_FIELDS, "source_observation")
    _canonical_record_bytes(value, "source_observation")
    if (
        value["schema_version"]
        != contract["runtime_schemas"]["source_observation"]["schema_version"]
    ):
        _reject("V010_SCHEMA", "source_observation_schema")
    if (
        value["authorization_identity"] != descriptor["authorization_identity"]
        or value["operator_implementation_identity"]
        != descriptor["operator_implementation_identity"]
        or value["tracked_inventory_identity"]
        != descriptor["operator_implementation_identity"]
        or value["manifest_exclusion"]
        != "config/professional_strategy_olympics_operator_implementation_v001.json"
    ):
        _reject("V010_SOURCE_IDENTITY", "binding")
    if value["observation_phase"] not in {"preflight", "point_of_exec"}:
        _reject("V010_SCHEMA", "source_observation_phase")
    _absolute_path(value["source_root"], "source_root")
    _uuid(value["source_root_volume_uuid"], "source_root_volume_uuid")
    for field in ("source_root_device_id", "source_root_mount_id", "source_root_inode"):
        _uint(value[field], field)
    if (
        value["source_root_mode"] != "0555"
        or value["source_filesystem"] != "local_apfs"
        or value["source_read_only_mount"] is not True
        or value["source_local_device"] is not True
        or value["source_disk_image"] is not False
        or value["source_removable"] is not False
        or value["source_network_filesystem"] is not False
        or value["source_mutation_detected"] is not False
    ):
        _reject("V010_RUNTIME_CONTINUITY_INDETERMINATE", "source_mount")
    for field in (
        "ignored_objects",
        "untracked_objects",
        "extra_objects",
        "symlink_objects",
        "hard_link_objects",
        "mount_crossings",
        "unsupported_objects",
        "case_aliases",
        "unicode_aliases",
    ):
        if value[field] != []:
            _reject(
                "V010_IGNORED_SOURCE_OBJECT"
                if field == "ignored_objects"
                else "V010_SOURCE_IDENTITY",
                field,
            )
    if (
        value["filesystem_walk_complete"] is not True
        or value["git_status_used_as_sole_evidence"] is not False
    ):
        _reject("V010_SOURCE_IDENTITY", "walk_evidence")
    if value["source_observation_identity"] != _record_identity(
        contract["runtime_schemas"]["source_observation"]["identity_domain"],
        value,
        "source_observation_identity",
    ):
        _reject("V010_SOURCE_IDENTITY", "identity")
    return dict(value)


def validate_runtime_observation(
    observation: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    inventory = validate_inventory(inventory, descriptor, contract)
    descriptor = validate_descriptor(descriptor, contract)
    value = _exact(observation, RUNTIME_OBSERVATION_FIELDS, "runtime_observation")
    _canonical_record_bytes(value, "runtime_observation")
    if (
        value["schema_version"]
        != contract["runtime_schemas"]["runtime_observation"]["schema_version"]
    ):
        _reject("V010_SCHEMA", "runtime_observation_schema")
    checks = (
        (
            value["runtime_descriptor_identity"],
            descriptor["runtime_descriptor_identity"],
        ),
        (value["runtime_inventory_identity"], inventory["runtime_inventory_identity"]),
        (value["platform_boundary_identity"], descriptor["platform_boundary_identity"]),
        (
            value["platform_cache_set_identity"],
            descriptor["platform_cache_set_identity"],
        ),
        (value["runtime_root"], descriptor["runtime_root"]),
        (value["runtime_root_volume_uuid"], descriptor["volume_uuid"]),
        (value["runtime_root_mode"], descriptor["root_mode"]),
        (value["runtime_root_owner_uid"], descriptor["root_owner_uid"]),
        (value["runtime_root_owner_gid"], descriptor["root_owner_gid"]),
        (value["filesystem"], "local_apfs"),
    )
    if any(left != right for left, right in checks):
        _reject("V010_RUNTIME_OBSERVATION", "binding")
    if value["observation_phase"] not in {"preflight", "point_of_exec"}:
        _reject("V010_SCHEMA", "observation_phase")
    for field in (
        "runtime_root_device_id",
        "runtime_root_mount_id",
        "runtime_root_inode",
    ):
        _uint(value[field], field)
    required_true = (
        "read_only_mount",
        "local_device",
        "inventory_complete",
        "macho_closure_complete",
        "python_import_closure_complete",
        "metadata_closure_complete",
    )
    required_false = (
        "disk_image",
        "removable",
        "network_filesystem",
        "mutation_detected",
    )
    if any(value[field] is not True for field in required_true) or any(
        value[field] is not False for field in required_false
    ):
        _reject("V010_RUNTIME_CONTINUITY_INDETERMINATE", "mount_or_closure")
    for field in (
        "symlink_objects",
        "hard_link_objects",
        "mount_crossings",
        "unsupported_objects",
        "case_aliases",
        "unicode_aliases",
    ):
        if value[field] != []:
            _reject("V010_RUNTIME_INVENTORY", field)
    file_ids = [str(item["file_identity"]) for item in inventory["files"]]
    directory_paths = [str(item["relative_path"]) for item in inventory["directories"]]
    cache_file_ids = [
        str(item["file_identity"]) for item in inventory["platform_cache_files"]
    ]
    if value["observed_file_identities"] != sorted(
        file_ids, key=lambda item: item.encode()
    ) or value["observed_directory_paths"] != sorted(
        directory_paths, key=lambda item: item.encode()
    ):
        _reject("V010_RUNTIME_INVENTORY", "observed_inventory")
    if value["observed_platform_cache_file_identities"] != sorted(
        cache_file_ids, key=lambda item: item.encode()
    ):
        _reject("V010_PLATFORM_DEPENDENCY", "observed_cache_set")
    if value["runtime_observation_identity"] != _record_identity(
        contract["runtime_schemas"]["runtime_observation"]["identity_domain"],
        value,
        "runtime_observation_identity",
    ):
        _reject("V010_RUNTIME_OBSERVATION", "identity")
    return dict(value)


def validate_source_point_of_use(
    preflight: Mapping[str, object],
    point_of_exec: Mapping[str, object],
    descriptor: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    before = validate_source_observation(preflight, descriptor, contract)
    after = validate_source_observation(point_of_exec, descriptor, contract)
    if (
        before["observation_phase"] != "preflight"
        or after["observation_phase"] != "point_of_exec"
    ):
        _reject("V010_RUNTIME_CONTINUITY_INDETERMINATE", "source_phase")
    ignored = {"source_observation_identity", "observation_phase"}
    if {key: item for key, item in before.items() if key not in ignored} != {
        key: item for key, item in after.items() if key not in ignored
    }:
        _reject("V010_RUNTIME_MUTATION", "source_point_of_use")


def validate_source_runtime_separation(
    source: Mapping[str, object],
    runtime: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    source = validate_source_observation(source, descriptor, contract)
    runtime = validate_runtime_observation(runtime, descriptor, inventory, contract)
    source_path = PurePosixPath(str(source["source_root"]))
    runtime_path = PurePosixPath(str(runtime["runtime_root"]))
    if (
        source_path == runtime_path
        or source_path in runtime_path.parents
        or runtime_path in source_path.parents
    ):
        _reject("V010_RUNTIME_SOURCE_OVERLAP", "path_nesting")
    if (
        source["source_root_device_id"] == runtime["runtime_root_device_id"]
        or source["source_root_mount_id"] == runtime["runtime_root_mount_id"]
        or source["source_root_volume_uuid"] == runtime["runtime_root_volume_uuid"]
        or source["source_root_inode"] == runtime["runtime_root_inode"]
    ):
        _reject("V010_RUNTIME_SOURCE_OVERLAP", "storage_alias")


def validate_environment(
    environment: Mapping[str, object], contract: Mapping[str, object]
) -> dict[str, str]:
    validate_contract(contract)
    expected = contract["environment_closure"]["exact_environment"]
    if type(environment) is not dict or environment != expected:
        _reject("V010_ENVIRONMENT_MISMATCH", "closed_world")
    return dict(environment)


def validate_resolved_command(
    argv: Sequence[object],
    context: Mapping[str, object],
    descriptor: Mapping[str, object],
    contract: Mapping[str, object],
) -> list[str]:
    descriptor = validate_descriptor(descriptor, contract)
    fields = {
        "authorization_path",
        "detached_source_root",
        "consumption_root",
        "artifact_root",
        "execution_clock_attestation_path",
        "execution_runtime_descriptor_path",
    }
    context = _exact(context, fields, "command_context")
    for field in fields:
        _absolute_path(context[field], field)
    authorization_identity = str(descriptor["authorization_identity"])
    authorization_suffix = (
        f"/authorizations/{authorization_identity}/authorization.json"
    )
    authorization_path = str(context["authorization_path"])
    if not authorization_path.endswith(authorization_suffix):
        _reject("V010_PACKAGE_REACHABILITY", "authorization_path")
    package_root = authorization_path.removesuffix(authorization_suffix)
    _absolute_path(package_root, "package_root")
    if context["execution_runtime_descriptor_path"] != (
        f"{package_root}/{descriptor_relative_path(authorization_identity)}"
    ):
        _reject("V010_PACKAGE_REACHABILITY", "runtime_descriptor_path")
    if context["execution_clock_attestation_path"] != (
        f"{package_root}/runtime/{authorization_identity}/clock_bootstrap.json"
    ):
        _reject("V010_PACKAGE_REACHABILITY", "clock_bootstrap_path")
    executable = (
        f"{descriptor['runtime_root']}/{descriptor['interpreter_relative_path']}"
    )
    expected = [
        executable,
        "-s",
        "-S",
        "-B",
        "-P",
        "scripts/run_professional_strategy_olympics_v005.py",
        "--authorization",
        str(context["authorization_path"]),
        "--source-root",
        str(context["detached_source_root"]),
        "--consumption-root",
        str(context["consumption_root"]),
        "--artifact-root",
        str(context["artifact_root"]),
        "--clock-attestation",
        str(context["execution_clock_attestation_path"]),
        "--runtime-descriptor",
        str(context["execution_runtime_descriptor_path"]),
    ]
    if (
        type(argv) is not list
        or argv != expected
        or any(type(item) is not str for item in argv)
    ):
        _reject("V010_COMMAND_MISMATCH", "argv")
    return expected


def validate_python_import_path(
    sys_path: object,
    context: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> list[str]:
    """Validate the exact post-bootstrap import path without importing operator code."""
    inventory = validate_inventory(inventory, descriptor, contract)
    descriptor = validate_descriptor(descriptor, contract)
    context = _exact(
        context,
        {
            "authorization_path",
            "detached_source_root",
            "consumption_root",
            "artifact_root",
            "execution_clock_attestation_path",
            "execution_runtime_descriptor_path",
        },
        "command_context",
    )
    source_root = _absolute_path(
        context["detached_source_root"], "detached_source_root"
    )
    expected = [
        f"{source_root}/src",
        *[
            f"{descriptor['runtime_root']}/{root}"
            for root in inventory["python_import_roots"]
        ],
    ]
    if (
        type(sys_path) is not list
        or sys_path != expected
        or any(type(item) is not str for item in sys_path)
    ):
        _reject("V010_PYTHON_IMPORT_INJECTION", "sys_path")
    return expected


def validate_preflight_bindings(
    argv: Sequence[object],
    context: Mapping[str, object],
    source: Mapping[str, object],
    runtime: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Purely bind the command, source, and runtime used by one preflight."""
    resolved_argv = validate_resolved_command(argv, context, descriptor, contract)
    source = validate_source_observation(source, descriptor, contract)
    runtime = validate_runtime_observation(runtime, descriptor, inventory, contract)
    if source["observation_phase"] != "preflight" or runtime["observation_phase"] != (
        "preflight"
    ):
        _reject("V010_RUNTIME_CONTINUITY_INDETERMINATE", "preflight_phase")
    if context["detached_source_root"] != source["source_root"]:
        _reject("V010_SOURCE_IDENTITY", "command_source_root")
    validate_source_runtime_separation(source, runtime, descriptor, inventory, contract)
    return {
        "argv": resolved_argv,
        "runtime_root": runtime["runtime_root"],
        "source_root": source["source_root"],
    }


def package_identity(package: Mapping[str, object]) -> str:
    return _record_identity(
        "aml.olympics.v010.execution-runtime-package", package, "package_identity"
    )


def package_binding_identity(package: Mapping[str, object]) -> str:
    fields = (
        "authorization_identity",
        "operator_implementation_identity",
        "v006_operator_package_identity",
        "v007_runtime_package_identity",
        "v008_clock_continuation_identity",
        "v009_documentary_proof_package_identity",
        "successor_command_identity",
        "v010_contract_identity",
    )
    if any(field not in package for field in fields):
        _reject("V010_SCHEMA", "package_binding_fields")
    return domain_hash(
        "aml.olympics.v010.execution-runtime-package-binding",
        {field: package[field] for field in fields},
    )


def validate_package(
    package: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> dict[str, object]:
    descriptor = validate_descriptor(descriptor, contract)
    inventory = validate_inventory(inventory, descriptor, contract)
    value = _exact(package, PACKAGE_FIELDS, "runtime_package")
    _canonical_record_bytes(value, "runtime_package")
    auth = str(descriptor["authorization_identity"])
    if value["schema_version"] != contract["package_integration"]["package_schema"]:
        _reject("V010_SCHEMA", "package_schema")
    checks = (
        (value["v010_contract_identity"], CONTRACT_IDENTITY),
        (value["successor_command_identity"], COMMAND_IDENTITY),
        (value["authorization_identity"], auth),
        (
            value["operator_implementation_identity"],
            descriptor["operator_implementation_identity"],
        ),
        (value["v008_clock_continuation_identity"], V008_CLOCK_CONTINUATION_IDENTITY),
        (
            value["runtime_descriptor_identity"],
            descriptor["runtime_descriptor_identity"],
        ),
        (value["runtime_inventory_identity"], inventory["runtime_inventory_identity"]),
        (value["runtime_descriptor_relative_path"], descriptor_relative_path(auth)),
        (value["runtime_inventory_relative_path"], inventory_relative_path(auth)),
        (value["package_binding_identity"], descriptor["package_binding_identity"]),
        (
            value["v006_operator_package_identity"],
            descriptor["v006_operator_package_identity"],
        ),
        (
            value["v007_runtime_package_identity"],
            descriptor["v007_runtime_package_identity"],
        ),
        (
            value["v009_documentary_proof_package_identity"],
            descriptor["v009_documentary_proof_package_identity"],
        ),
    )
    if any(left != right for left, right in checks):
        _reject("V010_PACKAGE_SUBSTITUTION", "binding")
    for field in (
        "v006_operator_package_identity",
        "v007_runtime_package_identity",
        "v009_documentary_proof_package_identity",
    ):
        _identity(value[field], field)
    descriptor_raw = _canonical_record_bytes(descriptor, "descriptor")
    inventory_raw = _canonical_record_bytes(inventory, "inventory")
    common = [
        {
            "artifact_type": "execution_runtime_descriptor",
            "artifact_identity": descriptor["runtime_descriptor_identity"],
            "relative_path": descriptor_relative_path(auth),
            "canonical_bytes_sha256": hashlib.sha256(descriptor_raw).hexdigest(),
        },
        {
            "artifact_type": "execution_runtime_inventory",
            "artifact_identity": inventory["runtime_inventory_identity"],
            "relative_path": inventory_relative_path(auth),
            "canonical_bytes_sha256": hashlib.sha256(inventory_raw).hexdigest(),
        },
    ]
    expected_v006 = sorted(
        common,
        key=lambda item: tuple(
            str(item[key]).encode()
            for key in ("artifact_type", "artifact_identity", "relative_path")
        ),
    )
    expected_v007 = [
        {
            **item,
            "schema_version": contract["runtime_schemas"][
                "descriptor"
                if item["artifact_type"].endswith("descriptor")
                else "inventory"
            ]["schema_version"],
        }
        for item in expected_v006
    ]
    if (
        value["v006_record_index_extensions"] != expected_v006
        or value["v007_supplemental_manifest_entries"] != expected_v007
    ):
        _reject("V010_PACKAGE_REACHABILITY", "index_extensions")
    if value["package_binding_identity"] != package_binding_identity(value):
        _reject("V010_PACKAGE_IDENTITY", "binding_identity")
    if value["package_identity"] != package_identity(value):
        _reject("V010_PACKAGE_IDENTITY", "identity")
    return dict(value)


def validate_package_inventory(
    members: Mapping[str, bytes],
    package: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    """Validate the exact three-file V010 closed-world package projection."""
    package = validate_package(package, descriptor, inventory, contract)
    authorization_identity = str(package["authorization_identity"])
    expected = {
        package_relative_path(authorization_identity): package,
        descriptor_relative_path(authorization_identity): descriptor,
        inventory_relative_path(authorization_identity): inventory,
    }
    if type(members) is not dict or set(members) != set(expected):
        _reject("V010_PACKAGE_REACHABILITY", "closed_world_members")
    for path, record in expected.items():
        _relative_path(path, "package_member_path")
        raw = members[path]
        if type(raw) is not bytes or len(raw) > MAXIMUM_RECORD_BYTES:
            _reject("V010_RESOURCE_LIMIT", "package_member")
        try:
            parsed = strict_json_bytes(raw, maximum_bytes=MAXIMUM_RECORD_BYTES)
        except ValueError as exc:
            raise OlympicsExecutionRuntimeV010Error(
                "V010_PACKAGE_REACHABILITY:canonical_member"
            ) from exc
        if parsed != record or raw != canonical_bytes(record):
            _reject("V010_PACKAGE_REACHABILITY", "member_binding")


def validate_v005_authorization_runtime_binding(
    authorization: Mapping[str, object],
    environment_manifest: Mapping[str, object],
    package: Mapping[str, object],
    descriptor: Mapping[str, object],
    v005_contract: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    """Bridge one frozen V005 approval to one V010 package environment."""
    try:
        authorization = validate_v005_artifact(
            authorization, "authorization", v005_contract
        )
        environment_manifest = validate_v005_artifact(
            environment_manifest, "environment_manifest", v005_contract
        )
    except ValueError as exc:
        raise OlympicsExecutionRuntimeV010Error(
            "V010_PACKAGE_SUBSTITUTION:v005_artifact"
        ) from exc
    package = _exact(package, PACKAGE_FIELDS, "runtime_package")
    descriptor = _exact(descriptor, DESCRIPTOR_FIELDS, "runtime_descriptor")
    validate_contract(contract)
    checks = (
        (
            authorization["authorization_identity"],
            package["authorization_identity"],
        ),
        (
            authorization["authorization_identity"],
            descriptor["authorization_identity"],
        ),
        (
            authorization["environment_manifest_identity"],
            environment_manifest["environment_manifest_identity"],
        ),
        (
            environment_manifest["package_lock_identity"],
            descriptor["package_environment_identity"],
        ),
        (environment_manifest["architecture"], descriptor["architecture"]),
        (environment_manifest["python_runtime"], descriptor["python_version"]),
        (authorization["execution_command_identity"], V005_COMMAND_IDENTITY),
        (authorization["execution_argv"], v005_contract["execution_command"]["argv"]),
    )
    if any(left != right for left, right in checks):
        _reject("V010_PACKAGE_SUBSTITUTION", "v005_environment_binding")
    expected_environment = [
        f"{name}={value}"
        for name, value in sorted(
            contract["environment_closure"]["exact_environment"].items(),
            key=lambda item: item[0].encode(),
        )
    ]
    if environment_manifest["environment_variable_allowlist"] != expected_environment:
        _reject("V010_ENVIRONMENT_MISMATCH", "v005_environment_allowlist")
    if authorization["execution_entry_point"] != (
        "scripts/run_professional_strategy_olympics_v005.py"
    ):
        _reject("V010_COMMAND_MISMATCH", "v005_entry_point")


def validate_invocation_binding(
    package: Mapping[str, object],
    descriptor: Mapping[str, object],
    invocation: Mapping[str, object],
    v008_contract: Mapping[str, object],
) -> None:
    package = _exact(package, PACKAGE_FIELDS, "runtime_package")
    descriptor = _exact(descriptor, DESCRIPTOR_FIELDS, "runtime_descriptor")
    try:
        validate_v008_contract(v008_contract)
        invocation = validate_v008_continuation_record(
            "continuation_invocation", invocation, v008_contract
        )
    except ValueError as exc:
        raise OlympicsExecutionRuntimeV010Error(
            "V010_PACKAGE_SUBSTITUTION:v008_invocation_schema"
        ) from exc
    checks = (
        (
            package.get("authorization_identity"),
            invocation.get("authorization_identity"),
        ),
        (
            package.get("operator_implementation_identity"),
            invocation.get("operator_implementation_identity"),
        ),
        (
            descriptor.get("authorization_identity"),
            invocation.get("authorization_identity"),
        ),
    )
    if any(left is None or right is None or left != right for left, right in checks):
        _reject("V010_PACKAGE_SUBSTITUTION", "v008_invocation")


def validate_point_of_use(
    preflight: Mapping[str, object],
    point_of_exec: Mapping[str, object],
    descriptor: Mapping[str, object],
    inventory: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    before = validate_runtime_observation(preflight, descriptor, inventory, contract)
    after = validate_runtime_observation(point_of_exec, descriptor, inventory, contract)
    if (
        before["observation_phase"] != "preflight"
        or after["observation_phase"] != "point_of_exec"
    ):
        _reject("V010_RUNTIME_CONTINUITY_INDETERMINATE", "phase")
    ignored = {"runtime_observation_identity", "observation_phase"}
    if {key: item for key, item in before.items() if key not in ignored} != {
        key: item for key, item in after.items() if key not in ignored
    }:
        _reject("V010_RUNTIME_MUTATION", "point_of_use")


def _section_projection(name: str, contract: Mapping[str, object]) -> object:
    return contract[name]


def validate_contract(
    value: Mapping[str, object], root: Path | None = None
) -> dict[str, object]:
    required = {
        "schema_version",
        "version",
        "prospective_as_of",
        "contract_identity",
        "section_identities",
        *SECTION_NAMES,
    }
    value = _exact(value, required, "contract_fields")
    if value["schema_version"] != SCHEMA or value["version"] != VERSION:
        _reject("V010_SCHEMA", "contract_header")
    if value["prospective_as_of"] != "2026-08-03T00:00:00Z":
        _reject("V010_SCHEMA", "prospective_as_of")
    sections = _exact(
        value["section_identities"], set(SECTION_NAMES), "section_identities"
    )
    for name in SECTION_NAMES:
        actual = domain_hash(
            f"{CONTRACT_DOMAIN}.section.{name}", _section_projection(name, value)
        )
        if (
            sections[name] != EXPECTED_SECTION_IDENTITIES[name]
            or actual != EXPECTED_SECTION_IDENTITIES[name]
        ):
            _reject("V010_CONTRACT_IDENTITY", f"section_{name}")
    projection = {
        key: item for key, item in value.items() if key != "contract_identity"
    }
    if (
        value["contract_identity"] != CONTRACT_IDENTITY
        or domain_hash(CONTRACT_DOMAIN, projection) != CONTRACT_IDENTITY
    ):
        _reject("V010_CONTRACT_IDENTITY", "outer")
    command = value["command_supersession"]["successor_command"]
    command_projection = {
        key: item for key, item in command.items() if key != "command_identity"
    }
    if (
        command["command_identity"] != COMMAND_IDENTITY
        or domain_hash(COMMAND_DOMAIN, command_projection) != COMMAND_IDENTITY
    ):
        _reject("V010_COMMAND_IDENTITY", "successor")
    lineage = value["inheritance"]
    expected_lineage = {
        "design_base_commit": DESIGN_BASE_COMMIT,
        "immutable_tag_object": TAG_OBJECT,
        "immutable_tagged_commit": TAGGED_COMMIT,
        "v004_contract_identity": V004_CONTRACT_IDENTITY,
        "v004_implementation_identity": V004_IMPLEMENTATION_IDENTITY,
        "v005_governance_identity": V005_GOVERNANCE_IDENTITY,
        "v005_command_identity": V005_COMMAND_IDENTITY,
        "v006_operator_interface_identity": V006_OPERATOR_INTERFACE_IDENTITY,
        "v007_runtime_boundary_identity": V007_RUNTIME_BOUNDARY_IDENTITY,
        "v008_clock_continuation_identity": V008_CLOCK_CONTINUATION_IDENTITY,
        "v009_documentary_proof_identity": V009_DOCUMENTARY_PROOF_IDENTITY,
    }
    if lineage != expected_lineage:
        _reject("V010_CROSS_VERSION_SUBSTITUTION", "lineage")
    if root is not None:
        load_v005_contract(root)
        load_v006_contract(root)
        load_v007_contract(root)
        load_v008_contract(root)
        load_v009_contract(root)
        if v004_implementation_identity(root) != V004_IMPLEMENTATION_IDENTITY:
            _reject("V010_CROSS_VERSION_SUBSTITUTION", "v004_implementation")
    return dict(value)


def load_contract(root: Path) -> dict[str, object]:
    path = root / CONTRACT_PATH
    raw = path.read_bytes()
    if len(raw) > MAXIMUM_CONTRACT_BYTES:
        _reject("V010_RESOURCE_LIMIT", "contract")
    try:
        value = strict_json_bytes(raw, maximum_bytes=MAXIMUM_CONTRACT_BYTES)
    except ValueError as exc:
        raise OlympicsExecutionRuntimeV010Error("V010_SCHEMA:contract_bytes") from exc
    return validate_contract(value, root)


def canonical_contract_bytes(value: Mapping[str, object]) -> bytes:
    validate_contract(value)
    return canonical_bytes(value)


def validation_report(root: Path) -> bytes:
    contract = load_contract(root)
    return canonical_bytes(
        {
            "authorization_created": False,
            "contract_identity": contract["contract_identity"],
            "execution_permitted": False,
            "operator_implemented": False,
            "olympics_executed": False,
            "runtime_constructed": False,
            "selected_runtime_model": contract["runtime_placement"]["selected_model"],
            "status": contract["validation_manifest"]["status"],
            "successor_command_identity": COMMAND_IDENTITY,
            "validation_order": contract["preflight_order"]["mandatory_order"],
        }
    )


def diagnostic_report(error: BaseException) -> bytes:
    """Return a stable, path-free diagnostic for a failed V010 validation."""
    if isinstance(error, OlympicsExecutionRuntimeV010Error):
        message = str(error)
        code, separator, detail = message.partition(":")
        if (
            not separator
            or not re.fullmatch(r"V010_[A-Z_]+", code)
            or not re.fullmatch(r"[a-z0-9_./-]+", detail)
        ):
            code, detail = "V010_SCHEMA", "invalid_diagnostic"
    else:
        code, detail = "V010_SCHEMA", "unexpected_exception"
    return canonical_bytes(
        {
            "error_code": code,
            "safe_detail_token": detail,
            "status": "failure",
        }
    )
