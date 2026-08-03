from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    artifact_identity as v005_artifact_identity,
    canonical_bytes,
    domain_hash,
    load_contract as load_v005_contract,
    strict_json_bytes,
)
from aml.professional_strategy_olympics_clock_continuation_v008 import (
    load_contract as load_v008_contract,
    record_identity as v008_record_identity,
)
from aml.professional_strategy_olympics_execution_runtime_v010 import (
    COMMAND_DOMAIN,
    COMMAND_IDENTITY,
    CONTRACT_DOMAIN,
    CONTRACT_IDENTITY,
    CONTRACT_PATH,
    DESCRIPTOR_FIELDS,
    EXPECTED_SECTION_IDENTITIES,
    INVENTORY_FIELDS,
    OlympicsExecutionRuntimeV010Error,
    PACKAGE_FIELDS,
    RUNTIME_OBSERVATION_FIELDS,
    SECTION_NAMES,
    SOURCE_OBSERVATION_FIELDS,
    canonical_contract_bytes,
    diagnostic_report,
    dependency_lock_identity,
    descriptor_relative_path,
    inventory_relative_path,
    load_contract,
    package_binding_identity,
    package_identity,
    runtime_content_identity,
    validate_contract,
    validate_descriptor,
    validate_environment,
    validate_inventory,
    validate_invocation_binding,
    validate_package,
    validate_package_inventory,
    validate_package_root,
    validate_point_of_use,
    validate_preflight_bindings,
    validate_python_import_path,
    validate_resolved_command,
    validate_runtime_observation,
    validate_source_observation,
    validate_source_point_of_use,
    validate_source_runtime_separation,
    validate_v005_authorization_runtime_binding,
    validation_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "scripts/validate_professional_strategy_olympics_execution_runtime_v010.py"
)
H = "1" * 64


def v005_value(rule: str, *, index: int = 0) -> object:
    if rule.startswith("identity:"):
        return H
    if rule.startswith("nullable"):
        return None
    if rule.startswith("literal:"):
        literal = rule.split(":", 1)[1]
        if literal == "true":
            return True
        if literal == "false":
            return False
        return int(literal) if literal.isdecimal() else literal
    if rule.startswith("enum:"):
        return rule.split(":", 1)[1].split("|")[0]
    if rule.startswith("array_identity:"):
        minimum = int(rule.split(":")[2])
        return [
            hashlib.sha256(f"external-{item}".encode()).hexdigest()
            for item in range(minimum)
        ]
    if rule.startswith("array:"):
        _, primitive, minimum, _, order = rule.split(":")
        items = [v005_value(primitive, index=item) for item in range(int(minimum))]
        return sorted(set(items)) if order == "sorted_unique" else items
    values = {
        "absolute_path": f"/synthetic/path{index}",
        "argv": f"argument{index}",
        "env_assignment": f"VAR{index}=value{index}",
        "git_oid": "1" * 40,
        "identity": hashlib.sha256(f"identity-{index}".encode()).hexdigest(),
        "relative_path": f"synthetic/path{index}.json",
        "semver3": "3.12.8",
        "timestamp": "2026-08-03T00:00:00Z",
        "uint31": index,
        "uint63": index + 1,
    }
    return values[rule]


def v005_artifact(
    kind: str, v005_contract: dict[str, object], **overrides: object
) -> dict[str, object]:
    schema = v005_contract["artifact_schemas"][kind]
    record = {name: v005_value(rule) for name, rule in schema["fields"].items()}
    record.update(overrides)
    record[schema["identity_field"]] = v005_artifact_identity(record, schema)
    return record


def contract() -> dict[str, object]:
    return load_contract(ROOT)


def reseal_contract(
    value: dict[str, object], section: str | None = None
) -> dict[str, object]:
    result = copy.deepcopy(value)
    if section is not None:
        result["section_identities"][section] = domain_hash(
            f"{CONTRACT_DOMAIN}.section.{section}", result[section]
        )
    result["contract_identity"] = domain_hash(
        CONTRACT_DOMAIN,
        {key: item for key, item in result.items() if key != "contract_identity"},
    )
    return result


def leaf_paths(
    value: object, prefix: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [
            path
            for key, item in value.items()
            for path in leaf_paths(item, (*prefix, key))
        ]
    if isinstance(value, list):
        return [
            path
            for index, item in enumerate(value)
            for path in leaf_paths(item, (*prefix, index))
        ]
    return [prefix]


def replace_leaf(value: object) -> object:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return value + "x"
    if value is None:
        return "changed"
    raise AssertionError(f"unsupported synthetic leaf type: {type(value).__name__}")


CONTRACT_LEAVES = [
    (section, path)
    for section in SECTION_NAMES
    for path in leaf_paths(contract()[section])
]


def seal(record: dict[str, object], field: str, domain: str) -> dict[str, object]:
    record[field] = domain_hash(
        domain, {key: item for key, item in record.items() if key != field}
    )
    return record


def reseal_runtime_fixture(value: dict[str, object]) -> None:
    inventory = value["inventory"]
    descriptor = value["descriptor"]
    contract_value = value["contract"]
    inventory["runtime_content_identity"] = runtime_content_identity(inventory)
    descriptor["runtime_content_identity"] = inventory["runtime_content_identity"]
    descriptor["dependency_lock_identity"] = dependency_lock_identity(
        inventory, descriptor
    )
    descriptor["package_environment_identity"] = domain_hash(
        "aml.olympics.v010.package-environment",
        {
            field: descriptor[field]
            for field in (
                "dependency_lock_identity",
                "runtime_content_identity",
                "platform_boundary_identity",
                "platform_cache_set_identity",
                "operating_system_build",
                "python_implementation",
                "python_version",
                "python_abi",
                "architecture",
            )
        },
    )
    seal(
        inventory,
        "runtime_inventory_identity",
        contract_value["runtime_schemas"]["inventory"]["identity_domain"],
    )
    descriptor["runtime_inventory_identity"] = inventory["runtime_inventory_identity"]
    seal(
        descriptor,
        "runtime_descriptor_identity",
        contract_value["runtime_schemas"]["descriptor"]["identity_domain"],
    )


def runtime_file(
    path: str,
    *,
    executable: bool = False,
    macho: bool | None = None,
    dependency_count: int | None = None,
    raw: bytes = b"fixture",
) -> dict[str, object]:
    is_macho = executable if macho is None else macho
    value = {
        "relative_path": path,
        "file_identity": H,
        "file_type": "regular_file",
        "mode": "0555" if executable else "0444",
        "byte_length": len(raw),
        "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_uid": 501,
        "owner_gid": 20,
        "hard_link_count": 1,
        "executable": executable,
        "macho": is_macho,
        "macho_dependency_count": (1 if is_macho else 0)
        if dependency_count is None
        else dependency_count,
        "embedded_code_signature_sha256": "f" * 64 if is_macho else None,
        "acl_present": False,
        "xattrs": [],
        "file_flags": [],
    }
    return seal(value, "file_identity", "aml.olympics.v010.runtime-file")


def platform_cache_file() -> dict[str, object]:
    raw = b"synthetic-dyld-shared-cache"
    value = {
        "absolute_path": "/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e",
        "file_identity": H,
        "mode": "0555",
        "byte_length": len(raw),
        "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_uid": 0,
        "owner_gid": 0,
        "hard_link_count": 1,
    }
    return seal(value, "file_identity", "aml.olympics.v010.platform-cache-file")


def platform_file(
    platform_cache_set_identity: str, platform_boundary_identity: str
) -> dict[str, object]:
    raw = b"synthetic-libsystem"
    value = {
        "absolute_path": "/usr/lib/libSystem.B.dylib",
        "file_identity": H,
        "byte_length": len(raw),
        "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "image_uuid": "12345678-1234-1234-1234-123456789abc",
        "storage_kind": "dyld_shared_cache_image",
        "platform_cache_set_identity": platform_cache_set_identity,
        "platform_boundary_identity": platform_boundary_identity,
    }
    return seal(value, "file_identity", "aml.olympics.v010.platform-dependency")


def fixture() -> dict[str, object]:
    value_contract = contract()
    v005_contract = load_v005_contract(ROOT)
    files = sorted(
        [
            runtime_file("bin/python3", executable=True, raw=b"python"),
            runtime_file("lib/python3.12/json.py", raw=b"json"),
        ],
        key=lambda item: str(item["relative_path"]).encode(),
    )
    cache_file = platform_cache_file()
    cache_set_identity = domain_hash(
        "aml.olympics.v010.platform-cache-set",
        {
            "architecture": "arm64",
            "operating_system_build": "24G720",
            "cache_file_identities": [cache_file["file_identity"]],
        },
    )
    platform_boundary_identity = domain_hash(
        "aml.olympics.v010.platform-boundary",
        {
            "platform": "macos",
            "architecture": "arm64",
            "operating_system_build": "24G720",
            "platform_cache_set_identity": cache_set_identity,
        },
    )
    platform = platform_file(cache_set_identity, platform_boundary_identity)
    directories = [
        {
            "relative_path": path,
            "mode": "0555",
            "owner_uid": 501,
            "owner_gid": 20,
            "acl_present": False,
            "xattrs": [],
            "file_flags": [],
        }
        for path in ("bin", "lib", "lib/python3.12")
    ]
    macho_dependencies = [
        {
            "image_relative_path": "bin/python3",
            "load_command": "LC_LOAD_DYLIB",
            "declared_dependency": "/usr/lib/libSystem.B.dylib",
            "resolved_kind": "platform",
            "resolved_path": platform["absolute_path"],
            "dependency_file_identity": platform["file_identity"],
        }
    ]
    content_projection = {
        "runtime_root": "/volumes/aml-runtime-v010",
        "filesystem": "local_apfs",
        "volume_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "root_owner_uid": 501,
        "root_owner_gid": 20,
        "root_mode": "0555",
        "root_acl_present": False,
        "root_xattrs": [],
        "root_file_flags": [],
        "interpreter_relative_path": "bin/python3",
        "python_import_roots": ["lib/python3.12"],
        "directories": directories,
        "files": files,
        "macho_dependencies": macho_dependencies,
        "platform_cache_files": [cache_file],
        "platform_dependencies": [platform],
        "prohibited_python_artifacts_absent": True,
    }
    content_identity = domain_hash(
        "aml.olympics.v010.runtime-content", content_projection
    )
    dependency_identity = domain_hash(
        "aml.olympics.v010.dependency-lock",
        {
            "python_implementation": "cpython",
            "python_version": "3.12.8",
            "python_abi": "cp312-macosx_arm64",
            "architecture": "arm64",
            "interpreter_file_identity": files[0]["file_identity"],
            "python_import_roots": content_projection["python_import_roots"],
            "runtime_file_identities": [item["file_identity"] for item in files],
        },
    )
    package_environment_identity = domain_hash(
        "aml.olympics.v010.package-environment",
        {
            "dependency_lock_identity": dependency_identity,
            "runtime_content_identity": content_identity,
            "platform_boundary_identity": platform_boundary_identity,
            "platform_cache_set_identity": cache_set_identity,
            "operating_system_build": "24G720",
            "python_implementation": "cpython",
            "python_version": "3.12.8",
            "python_abi": "cp312-macosx_arm64",
            "architecture": "arm64",
        },
    )
    environment_manifest = v005_artifact(
        "environment_manifest",
        v005_contract,
        architecture="arm64",
        package_lock_identity=package_environment_identity,
        python_runtime="3.12.8",
        environment_variable_allowlist=[
            f"{name}={item}"
            for name, item in sorted(
                value_contract["environment_closure"]["exact_environment"].items()
            )
        ],
    )
    authorization = v005_artifact(
        "authorization",
        v005_contract,
        environment_manifest_identity=environment_manifest[
            "environment_manifest_identity"
        ],
        execution_argv=v005_contract["execution_command"]["argv"],
        execution_command_identity=v005_contract["execution_command"][
            "command_identity"
        ],
        execution_entry_point=v005_contract["execution_command"]["entry_point"],
    )
    binding_source = {
        "authorization_identity": authorization["authorization_identity"],
        "operator_implementation_identity": "b" * 64,
        "v006_operator_package_identity": "c" * 64,
        "v007_runtime_package_identity": "d" * 64,
        "v008_clock_continuation_identity": "4d3a3c7a2690decfd275b91fe80fee497953795d086a9c191480eb1ac688cda5",
        "v009_documentary_proof_package_identity": "e" * 64,
        "successor_command_identity": COMMAND_IDENTITY,
        "v010_contract_identity": CONTRACT_IDENTITY,
    }
    binding = package_binding_identity(binding_source)
    inventory = {
        "schema_version": value_contract["runtime_schemas"]["inventory"][
            "schema_version"
        ],
        "runtime_inventory_identity": H,
        "v010_contract_identity": CONTRACT_IDENTITY,
        "successor_command_identity": COMMAND_IDENTITY,
        "authorization_identity": binding_source["authorization_identity"],
        "operator_implementation_identity": binding_source[
            "operator_implementation_identity"
        ],
        "package_binding_identity": binding,
        "runtime_content_identity": content_identity,
        **content_projection,
    }
    seal(
        inventory,
        "runtime_inventory_identity",
        value_contract["runtime_schemas"]["inventory"]["identity_domain"],
    )
    descriptor = {
        "schema_version": value_contract["runtime_schemas"]["descriptor"][
            "schema_version"
        ],
        "runtime_descriptor_identity": H,
        "v010_contract_identity": CONTRACT_IDENTITY,
        "v009_documentary_proof_identity": "0d9cba96035cec3c21bef24597ac32b308d71fc83c3ac07ea81e126ea4d12794",
        "v008_clock_continuation_identity": binding_source[
            "v008_clock_continuation_identity"
        ],
        "v007_runtime_boundary_identity": "a90c60509253131e218b199cf199471ef9e6c634cd195097104af573b4a14d45",
        "v006_operator_interface_identity": "1c7d7b437d7bc61f7b62302036abe1978805c78a23c6ec337e0efee4875fbbb6",
        "v005_governance_identity": "dc976e8946c362aae7a5a72664560d8c4c3f54e7e01ab77fd93f537fc25433b0",
        "historical_v005_command_identity": "ff2c355895182af38127b9a863373fc00f7a0563d9922e782cbf0e8da9431fdb",
        "v004_contract_identity": "0dd043154b5ee90cbfa049df6977aaa8c7ec2a0f585a8c7952c77314893e7053",
        "v004_implementation_identity": "d711d18cfbdc5aeaa01975102acd07a7767c6874670fc445abb5100abe79f5c4",
        "successor_command_identity": COMMAND_IDENTITY,
        "authorization_identity": binding_source["authorization_identity"],
        "operator_implementation_identity": binding_source[
            "operator_implementation_identity"
        ],
        "package_binding_identity": binding,
        "v006_operator_package_identity": binding_source[
            "v006_operator_package_identity"
        ],
        "v007_runtime_package_identity": binding_source[
            "v007_runtime_package_identity"
        ],
        "v009_documentary_proof_package_identity": binding_source[
            "v009_documentary_proof_package_identity"
        ],
        "runtime_root": inventory["runtime_root"],
        "interpreter_relative_path": "bin/python3",
        "interpreter_file_identity": files[0]["file_identity"],
        "runtime_inventory_identity": inventory["runtime_inventory_identity"],
        "runtime_content_identity": content_identity,
        "package_environment_identity": package_environment_identity,
        "dependency_lock_identity": dependency_identity,
        "platform": "macos",
        "architecture": "arm64",
        "operating_system_build": "24G720",
        "platform_cache_set_identity": cache_set_identity,
        "python_implementation": "cpython",
        "python_version": "3.12.8",
        "python_abi": "cp312-macosx_arm64",
        "filesystem": "local_apfs",
        "volume_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "root_owner_uid": 501,
        "root_owner_gid": 20,
        "root_mode": "0555",
        "root_acl_present": False,
        "root_xattrs": [],
        "root_file_flags": [],
        "mount_policy": "dedicated_read_only_local_apfs_volume",
        "runtime_mutation_policy": "prohibited_before_during_and_after_invocation",
        "platform_boundary_identity": platform_boundary_identity,
    }
    seal(
        descriptor,
        "runtime_descriptor_identity",
        value_contract["runtime_schemas"]["descriptor"]["identity_domain"],
    )
    common = [
        {
            "artifact_type": "execution_runtime_descriptor",
            "artifact_identity": descriptor["runtime_descriptor_identity"],
            "relative_path": descriptor_relative_path(
                str(descriptor["authorization_identity"])
            ),
            "canonical_bytes_sha256": hashlib.sha256(
                canonical_bytes(descriptor)
            ).hexdigest(),
        },
        {
            "artifact_type": "execution_runtime_inventory",
            "artifact_identity": inventory["runtime_inventory_identity"],
            "relative_path": inventory_relative_path(
                str(descriptor["authorization_identity"])
            ),
            "canonical_bytes_sha256": hashlib.sha256(
                canonical_bytes(inventory)
            ).hexdigest(),
        },
    ]
    common.sort(
        key=lambda item: tuple(
            str(item[key]).encode()
            for key in ("artifact_type", "artifact_identity", "relative_path")
        )
    )
    package = {
        "schema_version": value_contract["package_integration"]["package_schema"],
        "package_identity": H,
        "package_binding_identity": binding,
        **binding_source,
        "runtime_descriptor_identity": descriptor["runtime_descriptor_identity"],
        "runtime_inventory_identity": inventory["runtime_inventory_identity"],
        "runtime_descriptor_relative_path": descriptor_relative_path(
            str(descriptor["authorization_identity"])
        ),
        "runtime_inventory_relative_path": inventory_relative_path(
            str(descriptor["authorization_identity"])
        ),
        "v006_record_index_extensions": common,
        "v007_supplemental_manifest_entries": [
            {
                **item,
                "schema_version": value_contract["runtime_schemas"][
                    "descriptor"
                    if item["artifact_type"].endswith("descriptor")
                    else "inventory"
                ]["schema_version"],
            }
            for item in common
        ],
    }
    package["package_identity"] = package_identity(package)
    source = {
        "schema_version": value_contract["runtime_schemas"]["source_observation"][
            "schema_version"
        ],
        "source_observation_identity": H,
        "authorization_identity": descriptor["authorization_identity"],
        "operator_implementation_identity": descriptor[
            "operator_implementation_identity"
        ],
        "observation_phase": "preflight",
        "source_root": "/users/research/authorized-source",
        "source_root_device_id": 10,
        "source_root_mount_id": 11,
        "source_root_volume_uuid": "11111111-2222-3333-4444-555555555555",
        "source_root_inode": 12,
        "source_root_mode": "0555",
        "source_filesystem": "local_apfs",
        "source_read_only_mount": True,
        "source_local_device": True,
        "source_disk_image": False,
        "source_removable": False,
        "source_network_filesystem": False,
        "source_mutation_detected": False,
        "tracked_inventory_identity": descriptor["operator_implementation_identity"],
        "manifest_exclusion": "config/professional_strategy_olympics_operator_implementation_v001.json",
        "ignored_objects": [],
        "untracked_objects": [],
        "extra_objects": [],
        "symlink_objects": [],
        "hard_link_objects": [],
        "mount_crossings": [],
        "unsupported_objects": [],
        "case_aliases": [],
        "unicode_aliases": [],
        "filesystem_walk_complete": True,
        "git_status_used_as_sole_evidence": False,
    }
    seal(
        source,
        "source_observation_identity",
        value_contract["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    source_exec = copy.deepcopy(source)
    source_exec["observation_phase"] = "point_of_exec"
    seal(
        source_exec,
        "source_observation_identity",
        value_contract["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    runtime_base = {
        "schema_version": value_contract["runtime_schemas"]["runtime_observation"][
            "schema_version"
        ],
        "runtime_observation_identity": H,
        "runtime_descriptor_identity": descriptor["runtime_descriptor_identity"],
        "runtime_inventory_identity": inventory["runtime_inventory_identity"],
        "platform_boundary_identity": descriptor["platform_boundary_identity"],
        "platform_cache_set_identity": descriptor["platform_cache_set_identity"],
        "observation_phase": "preflight",
        "runtime_root": descriptor["runtime_root"],
        "runtime_root_device_id": 20,
        "runtime_root_mount_id": 21,
        "runtime_root_volume_uuid": descriptor["volume_uuid"],
        "runtime_root_inode": 22,
        "runtime_root_mode": descriptor["root_mode"],
        "runtime_root_owner_uid": descriptor["root_owner_uid"],
        "runtime_root_owner_gid": descriptor["root_owner_gid"],
        "filesystem": "local_apfs",
        "read_only_mount": True,
        "local_device": True,
        "disk_image": False,
        "removable": False,
        "network_filesystem": False,
        "inventory_complete": True,
        "observed_file_identities": sorted(
            [str(item["file_identity"]) for item in files]
        ),
        "observed_directory_paths": ["bin", "lib", "lib/python3.12"],
        "observed_platform_cache_file_identities": [cache_file["file_identity"]],
        "macho_closure_complete": True,
        "python_import_closure_complete": True,
        "metadata_closure_complete": True,
        "symlink_objects": [],
        "hard_link_objects": [],
        "mount_crossings": [],
        "unsupported_objects": [],
        "case_aliases": [],
        "unicode_aliases": [],
        "mutation_detected": False,
    }
    runtime_preflight = seal(
        runtime_base,
        "runtime_observation_identity",
        value_contract["runtime_schemas"]["runtime_observation"]["identity_domain"],
    )
    runtime_exec = copy.deepcopy(runtime_preflight)
    runtime_exec["observation_phase"] = "point_of_exec"
    seal(
        runtime_exec,
        "runtime_observation_identity",
        value_contract["runtime_schemas"]["runtime_observation"]["identity_domain"],
    )
    authorization_identity = str(descriptor["authorization_identity"])
    context = {
        "authorization_path": f"/packages/authorizations/{authorization_identity}/authorization.json",
        "detached_source_root": source["source_root"],
        "consumption_root": "/stores/consumption",
        "artifact_root": "/stores/artifacts",
        "execution_clock_attestation_path": f"/packages/runtime/{authorization_identity}/clock_bootstrap.json",
        "execution_runtime_descriptor_path": f"/packages/{descriptor_relative_path(authorization_identity)}",
    }
    argv = [
        f"{descriptor['runtime_root']}/bin/python3",
        "-s",
        "-S",
        "-B",
        "-P",
        "scripts/run_professional_strategy_olympics_v005.py",
        "--authorization",
        context["authorization_path"],
        "--source-root",
        context["detached_source_root"],
        "--consumption-root",
        context["consumption_root"],
        "--artifact-root",
        context["artifact_root"],
        "--clock-attestation",
        context["execution_clock_attestation_path"],
        "--runtime-descriptor",
        context["execution_runtime_descriptor_path"],
    ]
    v008_contract = load_v008_contract(ROOT)
    invocation = {
        "schema_version": "aml.professional-strategy-olympics.clock-continuation-invocation.v008",
        "continuation_invocation_identity": H,
        "v008_clock_continuation_contract_identity": binding_source[
            "v008_clock_continuation_identity"
        ],
        "runtime_boundary_identity": descriptor["v007_runtime_boundary_identity"],
        "authorization_identity": descriptor["authorization_identity"],
        "authoritative_run_identity": "3" * 64,
        "operator_implementation_identity": descriptor[
            "operator_implementation_identity"
        ],
        "session_identity": "4" * 64,
        "packaged_sequence_1_response_identity": "5" * 64,
        "packaged_sequence_1_v005_clock_attestation_identity": "6" * 64,
        "first_live_sequence_number": 2,
        "state": "durably_claimed_before_entropy_or_socket",
        "reuse_policy": "single_invocation_no_restart_no_resume",
    }
    invocation["continuation_invocation_identity"] = v008_record_identity(
        "continuation_invocation", invocation, v008_contract
    )
    members = {
        f"authorizations/{descriptor['authorization_identity']}/execution_runtime_package_v010.json": canonical_bytes(
            package
        ),
        descriptor_relative_path(
            str(descriptor["authorization_identity"])
        ): canonical_bytes(descriptor),
        inventory_relative_path(
            str(descriptor["authorization_identity"])
        ): canonical_bytes(inventory),
    }
    return {
        "contract": value_contract,
        "descriptor": descriptor,
        "inventory": inventory,
        "package": package,
        "source": source,
        "source_exec": source_exec,
        "runtime_preflight": runtime_preflight,
        "runtime_exec": runtime_exec,
        "context": context,
        "argv": argv,
        "v008_contract": v008_contract,
        "invocation": invocation,
        "members": members,
        "v005_contract": v005_contract,
        "environment_manifest": environment_manifest,
        "authorization": authorization,
    }


RUNTIME_RECORD_IDENTITIES = {
    "descriptor": "runtime_descriptor_identity",
    "inventory": "runtime_inventory_identity",
    "package": "package_identity",
    "source": "source_observation_identity",
    "runtime_preflight": "runtime_observation_identity",
}
RUNTIME_RECORD_LEAVES = [
    (record_name, path)
    for record_name, identity_field in RUNTIME_RECORD_IDENTITIES.items()
    for path in leaf_paths(fixture()[record_name])
    if path != (identity_field,)
]


def replace_path_leaf(record: object, path: tuple[object, ...]) -> None:
    target = record
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replace_leaf(target[path[-1]])


def test_contract_is_canonical_and_design_only() -> None:
    value = contract()
    assert (ROOT / CONTRACT_PATH).read_bytes() == canonical_bytes(value)
    assert canonical_contract_bytes(value) == canonical_bytes(value)
    assert value["runtime_placement"]["permitted_model_count"] == 1
    assert value["validation_manifest"]["execution_permitted"] is False
    assert set(value["runtime_schemas"]["descriptor"]["fields"]) == DESCRIPTOR_FIELDS
    assert set(value["runtime_schemas"]["inventory"]["fields"]) == INVENTORY_FIELDS
    assert (
        set(value["runtime_schemas"]["source_observation"]["fields"])
        == SOURCE_OBSERVATION_FIELDS
    )
    assert (
        set(value["runtime_schemas"]["runtime_observation"]["fields"])
        == RUNTIME_OBSERVATION_FIELDS
    )
    assert set(value["package_integration"]["package_fields"]) == PACKAGE_FIELDS


def test_outer_command_and_sections_reproduce_independently() -> None:
    value = contract()
    assert (
        domain_hash(
            CONTRACT_DOMAIN,
            {k: v for k, v in value.items() if k != "contract_identity"},
        )
        == CONTRACT_IDENTITY
    )
    command = value["command_supersession"]["successor_command"]
    assert (
        domain_hash(
            COMMAND_DOMAIN,
            {k: v for k, v in command.items() if k != "command_identity"},
        )
        == COMMAND_IDENTITY
    )
    for name in SECTION_NAMES:
        assert (
            domain_hash(f"{CONTRACT_DOMAIN}.section.{name}", value[name])
            == EXPECTED_SECTION_IDENTITIES[name]
        )


def test_complete_positive_fixture() -> None:
    value = fixture()
    assert set(value["descriptor"]) == DESCRIPTOR_FIELDS
    assert set(value["inventory"]) == INVENTORY_FIELDS
    assert set(value["package"]) == PACKAGE_FIELDS
    assert set(value["source"]) == SOURCE_OBSERVATION_FIELDS
    assert set(value["runtime_preflight"]) == RUNTIME_OBSERVATION_FIELDS
    validate_descriptor(value["descriptor"], value["contract"])
    validate_inventory(value["inventory"], value["descriptor"], value["contract"])
    validate_package(
        value["package"], value["descriptor"], value["inventory"], value["contract"]
    )
    validate_package_inventory(
        value["members"],
        value["package"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    validate_source_observation(value["source"], value["descriptor"], value["contract"])
    validate_source_point_of_use(
        value["source"],
        value["source_exec"],
        value["descriptor"],
        value["contract"],
    )
    validate_runtime_observation(
        value["runtime_preflight"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    validate_source_runtime_separation(
        value["source"],
        value["runtime_preflight"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    validate_environment(
        value["contract"]["environment_closure"]["exact_environment"], value["contract"]
    )
    validate_resolved_command(
        value["argv"], value["context"], value["descriptor"], value["contract"]
    )
    validate_python_import_path(
        [
            f"{value['source']['source_root']}/src",
            *[
                f"{value['descriptor']['runtime_root']}/{root}"
                for root in value["inventory"]["python_import_roots"]
            ],
        ],
        value["context"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    validate_preflight_bindings(
        value["argv"],
        value["context"],
        value["source"],
        value["runtime_preflight"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    assert (
        dependency_lock_identity(value["inventory"], value["descriptor"])
        == value["descriptor"]["dependency_lock_identity"]
    )
    validate_point_of_use(
        value["runtime_preflight"],
        value["runtime_exec"],
        value["descriptor"],
        value["inventory"],
        value["contract"],
    )
    validate_invocation_binding(
        value["package"],
        value["descriptor"],
        value["invocation"],
        value["v008_contract"],
    )
    validate_v005_authorization_runtime_binding(
        value["authorization"],
        value["environment_manifest"],
        value["package"],
        value["descriptor"],
        value["v005_contract"],
        value["contract"],
    )


@pytest.mark.parametrize("section", SECTION_NAMES)
def test_resealed_contract_section_mutation_rejects(section: str) -> None:
    changed = copy.deepcopy(contract())
    target = changed[section]
    key = next(iter(target))
    original = target[key]
    if type(original) is bool:
        target[key] = not original
    elif type(original) is int:
        target[key] = original + 1
    elif type(original) is str:
        target[key] = original + "_changed"
    elif type(original) is list:
        target[key] = [*original, "changed"]
    else:
        target[key] = {**original, "unknown": True}
    changed = reseal_contract(changed, section)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_contract(changed)


@pytest.mark.parametrize(
    "section,path",
    CONTRACT_LEAVES,
    ids=lambda value: str(value),
)
def test_every_contract_leaf_resealed_mutation_rejects(
    section: str, path: tuple[object, ...]
) -> None:
    changed = copy.deepcopy(contract())
    target = changed[section]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replace_leaf(target[path[-1]])
    changed = reseal_contract(changed, section)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_contract(changed)


@pytest.mark.parametrize(
    "record_name,path",
    RUNTIME_RECORD_LEAVES,
    ids=lambda value: str(value),
)
def test_every_runtime_record_leaf_resealed_substitution_rejects(
    record_name: str, path: tuple[object, ...]
) -> None:
    value = fixture()
    record = value[record_name]
    replace_path_leaf(record, path)
    identity_field = RUNTIME_RECORD_IDENTITIES[record_name]
    if record_name == "package":
        record[identity_field] = package_identity(record)
    elif record_name == "source":
        seal(
            record,
            identity_field,
            value["contract"]["runtime_schemas"]["source_observation"][
                "identity_domain"
            ],
        )
    elif record_name == "runtime_preflight":
        seal(
            record,
            identity_field,
            value["contract"]["runtime_schemas"]["runtime_observation"][
                "identity_domain"
            ],
        )
    else:
        schema_name = "descriptor" if record_name == "descriptor" else "inventory"
        seal(
            record,
            identity_field,
            value["contract"]["runtime_schemas"][schema_name]["identity_domain"],
        )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        if record_name == "source":
            validate_source_point_of_use(
                record,
                value["source_exec"],
                value["descriptor"],
                value["contract"],
            )
        elif record_name == "runtime_preflight":
            validate_point_of_use(
                record,
                value["runtime_exec"],
                value["descriptor"],
                value["inventory"],
                value["contract"],
            )
        else:
            validate_package(
                value["package"],
                value["descriptor"],
                value["inventory"],
                value["contract"],
            )


@pytest.mark.parametrize(
    "field", sorted(DESCRIPTOR_FIELDS - {"runtime_descriptor_identity"})
)
def test_descriptor_missing_fields_reject(field: str) -> None:
    value = fixture()
    value["descriptor"].pop(field)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_descriptor(value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "version,abi",
    [
        ("3.10.14", "cp310-macosx_arm64"),
        ("3.12.8", "cp313-macosx_arm64"),
        ("3.12.8", "cp312-macosx_x86_64"),
    ],
)
def test_python_version_and_abi_substitution_rejects(version: str, abi: str) -> None:
    value = fixture()
    value["descriptor"]["python_version"] = version
    value["descriptor"]["python_abi"] = abi
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_descriptor(value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "record_name,fields,validator",
    [
        (
            "inventory",
            INVENTORY_FIELDS,
            lambda value: validate_inventory(
                value["inventory"], value["descriptor"], value["contract"]
            ),
        ),
        (
            "package",
            PACKAGE_FIELDS,
            lambda value: validate_package(
                value["package"],
                value["descriptor"],
                value["inventory"],
                value["contract"],
            ),
        ),
        (
            "source",
            SOURCE_OBSERVATION_FIELDS,
            lambda value: validate_source_observation(
                value["source"], value["descriptor"], value["contract"]
            ),
        ),
        (
            "runtime_preflight",
            RUNTIME_OBSERVATION_FIELDS,
            lambda value: validate_runtime_observation(
                value["runtime_preflight"],
                value["descriptor"],
                value["inventory"],
                value["contract"],
            ),
        ),
    ],
)
def test_every_runtime_record_field_is_required(
    record_name: str, fields: set[str], validator
) -> None:
    for field in fields:
        value = fixture()
        value[record_name].pop(field)
        with pytest.raises(OlympicsExecutionRuntimeV010Error):
            validator(value)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["argv"].__setitem__(0, ".venv/bin/python"),
        lambda value: value["argv"].__setitem__(0, "python3"),
        lambda value: value["argv"].__setitem__(1, "-E"),
        lambda value: value["argv"].append("--optional"),
        lambda value: value["argv"].__setitem__(5, "other.py"),
        lambda value: value["argv"].__setitem__(0, "/bin/sh"),
        lambda value: value["argv"].__setitem__(0, "/usr/bin/env"),
    ],
)
def test_command_substitution_rejects(mutation) -> None:
    value = fixture()
    mutation(value)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_resolved_command(
            value["argv"], value["context"], value["descriptor"], value["contract"]
        )


@pytest.mark.parametrize(
    "field",
    [
        "authorization_path",
        "execution_clock_attestation_path",
        "execution_runtime_descriptor_path",
    ],
)
def test_package_derived_command_path_substitution_rejects(field: str) -> None:
    value = fixture()
    value["context"][field] = "/alternate/substitution.json"
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_resolved_command(
            value["argv"],
            value["context"],
            value["descriptor"],
            value["contract"],
        )


def test_preflight_binds_the_command_to_the_observed_source_root() -> None:
    value = fixture()
    value["context"]["detached_source_root"] = "/alternate/source"
    value["argv"][9] = "/alternate/source"
    with pytest.raises(OlympicsExecutionRuntimeV010Error, match="V010_SOURCE_IDENTITY"):
        validate_preflight_bindings(
            value["argv"],
            value["context"],
            value["source"],
            value["runtime_preflight"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


@pytest.mark.parametrize(
    "sys_path",
    [
        ["/alternate/src", "/volumes/aml-runtime-v010/lib/python3.12"],
        [
            "/users/research/authorized-source/src",
            "/volumes/aml-runtime-v010/lib/python3.12",
            "/tmp/injection",
        ],
        [
            "/volumes/aml-runtime-v010/lib/python3.12",
            "/users/research/authorized-source/src",
        ],
    ],
)
def test_python_import_path_substitution_rejects(sys_path: list[str]) -> None:
    value = fixture()
    with pytest.raises(
        OlympicsExecutionRuntimeV010Error, match="V010_PYTHON_IMPORT_INJECTION"
    ):
        validate_python_import_path(
            sys_path,
            value["context"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


@pytest.mark.parametrize(
    "field",
    [
        "ignored_objects",
        "untracked_objects",
        "extra_objects",
        "symlink_objects",
        "hard_link_objects",
        "mount_crossings",
        "unsupported_objects",
        "case_aliases",
        "unicode_aliases",
    ],
)
def test_source_closed_world_rejects_every_extra_object_class(field: str) -> None:
    value = fixture()
    value["source"][field] = [".venv/bin/python"]
    seal(
        value["source"],
        "source_observation_identity",
        value["contract"]["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_source_observation(
            value["source"], value["descriptor"], value["contract"]
        )


@pytest.mark.parametrize(
    "field,value_new",
    [
        ("source_root_mode", "0755"),
        ("source_filesystem", "nfs"),
        ("source_read_only_mount", False),
        ("source_local_device", False),
        ("source_disk_image", True),
        ("source_removable", True),
        ("source_network_filesystem", True),
        ("source_mutation_detected", True),
    ],
)
def test_source_mount_uncertainty_rejects(field: str, value_new: object) -> None:
    value = fixture()
    value["source"][field] = value_new
    seal(
        value["source"],
        "source_observation_identity",
        value["contract"]["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_source_observation(
            value["source"], value["descriptor"], value["contract"]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["inventory"]["files"].pop(),
        lambda value: value["inventory"]["files"].append(runtime_file("extra.py")),
        lambda value: value["inventory"]["files"][0].update({"hard_link_count": 2}),
        lambda value: value["inventory"]["files"][0].update({"mode": "0777"}),
        lambda value: value["inventory"]["files"][0].update({"owner_uid": 0}),
        lambda value: value["inventory"]["files"][0].update(
            {"raw_bytes_sha256": "0" * 64}
        ),
        lambda value: value["inventory"]["files"].append(
            runtime_file("lib/python3.12/sitecustomize.py")
        ),
        lambda value: value["inventory"]["files"].append(
            runtime_file("lib/python3.12/inject.pth")
        ),
        lambda value: value["inventory"]["files"].append(runtime_file("bin/activate")),
        lambda value: value["inventory"]["files"].append(runtime_file("pyvenv.cfg")),
        lambda value: value["inventory"]["files"].append(
            runtime_file("lib/python3.12/inject.whl")
        ),
        lambda value: value["inventory"]["macho_dependencies"][0].update(
            {"resolved_path": "/tmp/libevil.dylib"}
        ),
        lambda value: value["inventory"].update(
            {"prohibited_python_artifacts_absent": False}
        ),
    ],
)
def test_runtime_inventory_mutations_reject(mutation) -> None:
    value = fixture()
    mutation(value)
    seal(
        value["inventory"],
        "runtime_inventory_identity",
        value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
    )
    value["descriptor"]["runtime_inventory_identity"] = value["inventory"][
        "runtime_inventory_identity"
    ]
    seal(
        value["descriptor"],
        "runtime_descriptor_identity",
        value["contract"]["runtime_schemas"]["descriptor"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "file_type",
    ["symlink", "directory", "device", "socket", "fifo", "unknown"],
)
def test_runtime_special_or_link_file_types_reject(file_type: str) -> None:
    value = fixture()
    value["inventory"]["files"][0]["file_type"] = file_type
    seal(
        value["inventory"],
        "runtime_inventory_identity",
        value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


def test_runtime_bytecode_cache_directory_rejects() -> None:
    value = fixture()
    value["inventory"]["directories"].append(
        {
            "relative_path": "lib/python3.12/__pycache__",
            "mode": "0555",
            "owner_uid": 501,
            "owner_gid": 20,
            "acl_present": False,
            "xattrs": [],
            "file_flags": [],
        }
    )
    value["inventory"]["directories"].sort(
        key=lambda item: str(item["relative_path"]).encode()
    )
    seal(
        value["inventory"],
        "runtime_inventory_identity",
        value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "declared",
    [
        "libevil.dylib",
        "@rpath/libevil.dylib",
        "@rpath/../evil.dylib",
        "@loader_path//evil",
        "@unknown/evil",
    ],
)
def test_dynamic_loader_reference_substitution_rejects(declared: str) -> None:
    value = fixture()
    value["inventory"]["macho_dependencies"][0]["declared_dependency"] = declared
    reseal_runtime_fixture(value)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "field,value_new",
    [
        ("read_only_mount", False),
        ("local_device", False),
        ("disk_image", True),
        ("removable", True),
        ("network_filesystem", True),
        ("inventory_complete", False),
        ("macho_closure_complete", False),
        ("python_import_closure_complete", False),
        ("metadata_closure_complete", False),
        ("mutation_detected", True),
    ],
)
def test_runtime_observation_uncertainty_rejects(field: str, value_new: object) -> None:
    value = fixture()
    value["runtime_preflight"][field] = value_new
    seal(
        value["runtime_preflight"],
        "runtime_observation_identity",
        value["contract"]["runtime_schemas"]["runtime_observation"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_runtime_observation(
            value["runtime_preflight"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


@pytest.mark.parametrize(
    "field,value_new",
    [
        ("root_acl_present", True),
        ("root_xattrs", ["com.apple.quarantine"]),
        ("root_file_flags", ["uchg"]),
        ("root_owner_uid", 0),
        ("root_mode", "0755"),
    ],
)
def test_runtime_root_metadata_is_content_bound(field: str, value_new: object) -> None:
    value = fixture()
    value["inventory"][field] = value_new
    seal(
        value["inventory"],
        "runtime_inventory_identity",
        value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


def test_dependency_lock_cannot_be_an_unrelated_identity() -> None:
    value = fixture()
    value["descriptor"]["dependency_lock_identity"] = "0" * 64
    value["descriptor"]["package_environment_identity"] = domain_hash(
        "aml.olympics.v010.package-environment",
        {
            field: value["descriptor"][field]
            for field in (
                "dependency_lock_identity",
                "runtime_content_identity",
                "platform_boundary_identity",
                "platform_cache_set_identity",
                "operating_system_build",
                "python_implementation",
                "python_version",
                "python_abi",
                "architecture",
            )
        },
    )
    seal(
        value["descriptor"],
        "runtime_descriptor_identity",
        value["contract"]["runtime_schemas"]["descriptor"]["identity_domain"],
    )
    with pytest.raises(
        OlympicsExecutionRuntimeV010Error,
        match="V010_DEPENDENCY_CLOSURE_UNCERTAIN",
    ):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "relation",
    ["equal", "runtime_nested", "source_nested", "device", "mount", "volume", "inode"],
)
def test_source_runtime_overlap_rejects(relation: str) -> None:
    value = fixture()
    if relation == "equal":
        value["source"]["source_root"] = value["runtime_preflight"]["runtime_root"]
    elif relation == "runtime_nested":
        value["runtime_preflight"]["runtime_root"] = (
            value["source"]["source_root"] + "/runtime"
        )
        value["descriptor"]["runtime_root"] = value["runtime_preflight"]["runtime_root"]
    elif relation == "source_nested":
        value["source"]["source_root"] = (
            value["runtime_preflight"]["runtime_root"] + "/source"
        )
    elif relation in {"device", "mount"}:
        value["source"][f"source_root_{relation}_id"] = value["runtime_preflight"][
            f"runtime_root_{relation}_id"
        ]
    elif relation == "volume":
        value["source"]["source_root_volume_uuid"] = value["runtime_preflight"][
            "runtime_root_volume_uuid"
        ]
    else:
        value["source"]["source_root_inode"] = value["runtime_preflight"][
            "runtime_root_inode"
        ]
    seal(
        value["source"],
        "source_observation_identity",
        value["contract"]["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    if relation == "runtime_nested":
        value["inventory"]["runtime_root"] = value["descriptor"]["runtime_root"]
        seal(
            value["inventory"],
            "runtime_inventory_identity",
            value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
        )
        value["descriptor"]["runtime_inventory_identity"] = value["inventory"][
            "runtime_inventory_identity"
        ]
        seal(
            value["descriptor"],
            "runtime_descriptor_identity",
            value["contract"]["runtime_schemas"]["descriptor"]["identity_domain"],
        )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_source_runtime_separation(
            value["source"],
            value["runtime_preflight"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


@pytest.mark.parametrize(
    "name,value_new",
    [
        ("PYTHONPATH", "/tmp"),
        ("PYTHONHOME", "/tmp"),
        ("PATH", "/usr/bin"),
        ("DYLD_LIBRARY_PATH", "/tmp"),
        ("HTTP_PROXY", "http://proxy"),
        ("GIT_DIR", "/tmp/repo"),
        ("TZ", "America/Denver"),
        ("LANG", "en_US.UTF-8"),
    ],
)
def test_environment_injection_rejects(name: str, value_new: str) -> None:
    value = fixture()
    environment = dict(value["contract"]["environment_closure"]["exact_environment"])
    environment[name] = value_new
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_environment(environment, value["contract"])


@pytest.mark.parametrize(
    "field",
    [
        "successor_command_identity",
        "authorization_identity",
        "operator_implementation_identity",
        "v006_operator_package_identity",
        "v007_runtime_package_identity",
        "v008_clock_continuation_identity",
        "v009_documentary_proof_package_identity",
        "runtime_descriptor_identity",
        "runtime_inventory_identity",
    ],
)
def test_package_substitution_rejects(field: str) -> None:
    value = fixture()
    value["package"][field] = "0" * 64
    value["package"]["package_identity"] = package_identity(value["package"])
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_package(
            value["package"], value["descriptor"], value["inventory"], value["contract"]
        )


def test_v008_invocation_binding_rejects_missing_and_none_equalities() -> None:
    value = fixture()
    validate_invocation_binding(
        value["package"],
        value["descriptor"],
        value["invocation"],
        value["v008_contract"],
    )
    for changed in ({}, {**value["invocation"], "authorization_identity": "0" * 64}):
        with pytest.raises(OlympicsExecutionRuntimeV010Error):
            validate_invocation_binding(
                value["package"],
                value["descriptor"],
                changed,
                value["v008_contract"],
            )


def test_point_of_use_mutation_rejects() -> None:
    value = fixture()
    value["runtime_exec"]["runtime_root_inode"] += 1
    seal(
        value["runtime_exec"],
        "runtime_observation_identity",
        value["contract"]["runtime_schemas"]["runtime_observation"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_point_of_use(
            value["runtime_preflight"],
            value["runtime_exec"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


def test_source_point_of_use_mutation_rejects() -> None:
    value = fixture()
    value["source_exec"]["source_root_inode"] += 1
    seal(
        value["source_exec"],
        "source_observation_identity",
        value["contract"]["runtime_schemas"]["source_observation"]["identity_domain"],
    )
    with pytest.raises(
        OlympicsExecutionRuntimeV010Error, match="V010_RUNTIME_MUTATION"
    ):
        validate_source_point_of_use(
            value["source"],
            value["source_exec"],
            value["descriptor"],
            value["contract"],
        )


@pytest.mark.parametrize(
    "path",
    [
        "/runtime//bin/python3",
        "/runtime/./bin/python3",
        "/runtime/../bin/python3",
        "/runtime\\bin\\python3",
        "/runtime/e\u0301",
    ],
)
def test_absolute_path_aliases_reject(path: str) -> None:
    value = fixture()
    value["descriptor"]["runtime_root"] = path
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_descriptor(value["descriptor"], value["contract"])


def test_command_requires_a_list_not_an_equivalent_tuple() -> None:
    value = fixture()
    with pytest.raises(
        OlympicsExecutionRuntimeV010Error, match="V010_COMMAND_MISMATCH"
    ):
        validate_resolved_command(
            tuple(value["argv"]),
            value["context"],
            value["descriptor"],
            value["contract"],
        )


@pytest.mark.parametrize("mutation", ["missing", "extra", "alternate", "bytes"])
def test_package_inventory_closed_world_rejects(mutation: str) -> None:
    value = fixture()
    members = dict(value["members"])
    descriptor_path = descriptor_relative_path(
        str(value["descriptor"]["authorization_identity"])
    )
    if mutation == "missing":
        members.pop(descriptor_path)
    elif mutation == "extra":
        members["runtime/extra.json"] = b"{}\n"
    elif mutation == "alternate":
        members["runtime/alternate-descriptor.json"] = members.pop(descriptor_path)
    else:
        members[descriptor_path] += b"\n"
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_package_inventory(
            members,
            value["package"],
            value["descriptor"],
            value["inventory"],
            value["contract"],
        )


def test_package_root_is_exactly_derived_from_authorization_path() -> None:
    value = fixture()
    identity = str(value["descriptor"]["authorization_identity"])
    validate_package_root(
        "/packages/olympics",
        f"/packages/olympics/authorizations/{identity}/authorization.json",
        identity,
    )
    for root, path in (
        (
            "/packages/alternate",
            f"/packages/olympics/authorizations/{identity}/authorization.json",
        ),
        (
            "/packages/olympics",
            f"/packages/olympics/authorizations/{identity}/other.json",
        ),
    ):
        with pytest.raises(OlympicsExecutionRuntimeV010Error):
            validate_package_root(root, path, identity)


@pytest.mark.parametrize(
    "target,field,value_new",
    [
        ("files", "acl_present", True),
        ("files", "xattrs", ["com.apple.quarantine"]),
        ("files", "file_flags", ["uchg"]),
        ("directories", "acl_present", True),
        ("directories", "xattrs", ["com.apple.quarantine"]),
        ("directories", "file_flags", ["uchg"]),
        ("platform_cache_files", "hard_link_count", 2),
        ("platform_cache_files", "raw_bytes_sha256", "0" * 64),
        ("platform_dependencies", "storage_kind", "ordinary_file"),
        ("platform_dependencies", "image_uuid", "not-a-uuid"),
    ],
)
def test_runtime_metadata_and_platform_mutations_reject(
    target: str, field: str, value_new: object
) -> None:
    value = fixture()
    value["inventory"][target][0][field] = value_new
    seal(
        value["inventory"],
        "runtime_inventory_identity",
        value["contract"]["runtime_schemas"]["inventory"]["identity_domain"],
    )
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


def test_case_colliding_runtime_paths_reject() -> None:
    value = fixture()
    value["inventory"]["files"].append(runtime_file("lib/python3.12/JSON.py"))
    value["inventory"]["files"].sort(
        key=lambda item: str(item["relative_path"]).encode()
    )
    reseal_runtime_fixture(value)
    with pytest.raises(OlympicsExecutionRuntimeV010Error, match="V010_PATH"):
        validate_inventory(value["inventory"], value["descriptor"], value["contract"])


@pytest.mark.parametrize(
    "target,field,value_new",
    [
        ("authorization", "environment_manifest_identity", "0" * 64),
        ("authorization", "execution_command_identity", "0" * 64),
        ("environment_manifest", "package_lock_identity", "0" * 64),
        ("environment_manifest", "architecture", "x86_64"),
        ("environment_manifest", "python_runtime", "3.11.9"),
        ("environment_manifest", "environment_variable_allowlist", ["LANG=C"]),
    ],
)
def test_v005_authorization_runtime_bridge_substitution_rejects(
    target: str, field: str, value_new: object
) -> None:
    value = fixture()
    record = value[target]
    record[field] = value_new
    schema = value["v005_contract"]["artifact_schemas"][
        "authorization" if target == "authorization" else "environment_manifest"
    ]
    record[schema["identity_field"]] = v005_artifact_identity(record, schema)
    with pytest.raises(OlympicsExecutionRuntimeV010Error):
        validate_v005_authorization_runtime_binding(
            value["authorization"],
            value["environment_manifest"],
            value["package"],
            value["descriptor"],
            value["v005_contract"],
            value["contract"],
        )


def test_stable_failure_diagnostic_hides_exception_and_host_path() -> None:
    first = diagnostic_report(FileNotFoundError("/machine-local/secret"))
    assert first == diagnostic_report(RuntimeError("different host detail"))
    report = json.loads(first)
    assert report == {
        "error_code": "V010_SCHEMA",
        "safe_detail_token": "unexpected_exception",
        "status": "failure",
    }
    assert b"/machine-local" not in first


@pytest.mark.parametrize(
    "raw_transform",
    [
        lambda raw: b" " + raw,
        lambda raw: raw[:-1],
        lambda raw: raw + b"\n",
        lambda raw: raw[:-1] + b"\r\n",
        lambda raw: b"\xef\xbb\xbf" + raw,
    ],
)
def test_noncanonical_contract_bytes_reject(raw_transform) -> None:
    with pytest.raises(ValueError):
        strict_json_bytes(raw_transform((ROOT / CONTRACT_PATH).read_bytes()))


def test_validation_report_is_deterministic_and_nonexecuting() -> None:
    first = validation_report(ROOT)
    assert first == validation_report(ROOT)
    report = json.loads(first)
    assert report["operator_implemented"] is False
    assert report["runtime_constructed"] is False
    assert report["execution_permitted"] is False


def test_cli_determinism_across_six_seeds_and_three_timezones() -> None:
    outputs: set[bytes] = set()
    failures: set[bytes] = set()
    for seed in ("0", "1", "2", "3", "42", "4294967295"):
        for timezone in ("UTC", "America/Denver", "Asia/Tokyo"):
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(ROOT)],
                check=True,
                capture_output=True,
                env={
                    **os.environ,
                    "PYTHONHASHSEED": seed,
                    "TZ": timezone,
                    "PYTHONPATH": str(ROOT / "src"),
                },
            )
            assert completed.stderr == b""
            outputs.add(completed.stdout)
            failed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    "/definitely-missing-v010-root",
                ],
                check=False,
                capture_output=True,
                env={
                    **os.environ,
                    "PYTHONHASHSEED": seed,
                    "TZ": timezone,
                    "PYTHONPATH": str(ROOT / "src"),
                },
            )
            assert failed.returncode == 2
            assert failed.stdout == b""
            failures.add(failed.stderr)
    assert outputs == {validation_report(ROOT)}
    assert failures == {diagnostic_report(FileNotFoundError())}


def test_validator_has_no_runtime_network_process_or_trading_capability() -> None:
    combined = (
        ROOT / "src/aml/professional_strategy_olympics_execution_runtime_v010.py"
    ).read_text() + SCRIPT.read_text()
    for token in (
        "import socket",
        "import requests",
        "import subprocess",
        "os.exec",
        "os.spawn",
        "Popen(",
        "alpaca",
        "submit_order",
        "build_artifact_bundle(",
        "consume_and_build(",
    ):
        assert token not in combined
