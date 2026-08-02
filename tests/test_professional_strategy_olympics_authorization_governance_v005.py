from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from aml.professional_strategy_olympics_authorization_governance_v005 import (
    COMMAND_IDENTITY,
    CONTRACT_IDENTITY,
    EXPECTED_MATRIX_IDENTITIES,
    EXPECTED_TRANSITIONS,
    OlympicsAuthorizationGovernanceV005Error,
    artifact_identity,
    artifact_self_identity,
    canonical_bytes,
    domain_hash,
    event_projection_identity,
    strict_json_bytes,
    synthetic_archive_outcome,
    transition_spec,
    _matrix_projections,
    validate_archive_bundle,
    validate_artifact,
    validate_clock_bundle,
    validate_contract,
    validate_documentary_git_proof,
    validate_filesystem_evidence,
    validate_supersession_chain,
    validate_terminal_bundle,
    validate_transition_bundle,
    validate_typed_reference,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/professional_strategy_olympics_authorization_governance_v005.json"
SCRIPT = ROOT / "scripts/validate_professional_strategy_olympics_authorization_governance_v005.py"
ZERO = "0" * 64
ONE = "1" * 64
GIT_A = "a" * 40
GIT_B = "b" * 40
STAMP = "2030-07-31T12:00:00Z"
DATE = "Wed, 31 Jul 2030 12:00:00 GMT"
TRACE = [
    "open_root_no_follow",
    "verify_mount_device_owner_mode",
    "exclusive_create",
    "write_complete",
    "f_fullfsync_file",
    "close_file",
    "fsync_directory",
]


def contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="ascii"))


def _primitive(name: str, index: int = 0) -> object:
    values: dict[str, object] = {
        "absolute_path": f"/synthetic/root{index}",
        "argv": f"arg{index}",
        "artifact_type": "proposal",
        "base64": "",
        "boolean": False,
        "domain_name": "aml.synthetic.domain",
        "durability_event": "open_root_no_follow",
        "env_assignment": f"A{index}=value",
        "env_name": f"A{index}",
        "field_name": "proposal_identity",
        "git_oid": f"{index % 10}" * 40,
        "github_login": f"person-{index}",
        "hostname": f"host{index}.example",
        "identity": hashlib.sha256(f"identity-{index}".encode()).hexdigest(),
        "nonce": hashlib.sha256(f"nonce-{index}".encode()).hexdigest(),
        "relative_path": f"synthetic/path{index}.json",
        "rfc7231_date": DATE,
        "schema_identifier": "aml.synthetic.schema.v005",
        "semver3": "3.13.0",
        "state_name": "synthetic_state",
        "timestamp": STAMP,
        "token": f"token{index}",
        "uint31": index,
        "uint63": index + 1,
    }
    return values[name]


def _value(rule: str) -> object:
    if rule.startswith("identity:"):
        return ZERO
    if rule.startswith("nullable"):
        return None
    if rule.startswith("literal:"):
        literal = rule.split(":", 1)[1]
        if literal == "true":
            return True
        if literal == "false":
            return False
        if literal == "null":
            return None
        if literal.isdecimal():
            return int(literal)
        return literal
    if rule.startswith("enum:"):
        return rule.split(":", 1)[1].split("|")[0]
    if rule.startswith("array_identity:"):
        _, _, minimum, _, _ = rule.split(":")
        return [hashlib.sha256(f"external-{index}".encode()).hexdigest() for index in range(int(minimum))]
    if rule.startswith("array:"):
        _, primitive, minimum, _, order = rule.split(":")
        items = [_primitive(primitive, index) for index in range(int(minimum))]
        return sorted(set(items)) if order == "sorted_unique" else items
    return _primitive(rule)


def make_artifact(kind: str, **overrides: object) -> dict[str, object]:
    c = contract()
    schema = c["artifact_schemas"][kind]
    record = {name: _value(rule) for name, rule in schema["fields"].items()}
    record.update(overrides)
    record[schema["identity_field"]] = artifact_identity(record, schema)
    return record


def _account(user_id: int) -> dict[str, object]:
    return make_artifact("stable_account", github_user_id=user_id)


def _typed_reference(kind: str, record: dict[str, object], state: str | None) -> dict[str, object]:
    c = contract()
    schema = c["artifact_schemas"][kind]
    return make_artifact(
        "typed_reference",
        target_artifact_type=kind,
        target_identity=record[schema["identity_field"]],
        target_schema_version=schema["fields"]["schema_version"].split(":", 1)[1],
        target_domain=schema["domain"],
        target_identity_field=schema["identity_field"],
        target_state=state,
    )


class Fixture:
    def __init__(
        self,
        *,
        transition_id: str,
        operation_stamp: str | None = None,
        operation_date: str | None = None,
        actor_override: str | None = None,
        durability_path: str | None = None,
        event_times: dict[str, tuple[str, str]] | None = None,
        store_root: str = "/synthetic/root0",
        authorized_run_identity: str = ZERO,
        lifecycle_run_identity: str | None = None,
        uncertain_operation_override: str | None = None,
        recovery_outcome_override: str | None = None,
        archive_destination_override: str | None = None,
        superseder_is_author: bool = False,
    ):
        self.c = contract()
        self.transition_id = transition_id
        self.spec = transition_spec(self.c, transition_id)
        self.operation_stamp = operation_stamp
        self.operation_date = operation_date
        self.actor_override = actor_override
        self.durability_path = durability_path
        self.event_times = event_times or {}
        self.store_root = store_root
        self.authorized_run_identity = authorized_run_identity
        self.lifecycle_run_identity = (
            authorized_run_identity
            if lifecycle_run_identity is None
            else lifecycle_run_identity
        )
        self.uncertain_operation_override = uncertain_operation_override
        self.recovery_outcome_override = recovery_outcome_override
        self.archive_destination_override = archive_destination_override
        self.records: dict[str, list[dict[str, object]]] = {}
        self.serial = 0
        self.accounts = [_account(index + 1) for index in range(9)]
        (
            self.governance_author,
            self.source_author,
            self.authorization_author,
            self.reviewer,
            self.operator,
            self.archive_custodian,
            self.previous_operator,
            self.superseder,
            self.system,
        ) = [item["stable_account_identity"] for item in self.accounts]
        if superseder_is_author:
            self.superseder = self.authorization_author
        self.add_many("stable_account", self.accounts)
        self._build()

    def add(self, kind: str, record: dict[str, object]) -> dict[str, object]:
        self.records.setdefault(kind, []).append(record)
        return record

    def add_many(self, kind: str, records: list[dict[str, object]]) -> None:
        self.records.setdefault(kind, []).extend(records)

    def event(self, kind: str, timestamp_field: str, *, root: bool = False, **overrides: object) -> dict[str, object]:
        self.serial += 1
        stamp = self.operation_stamp if root and self.operation_stamp else STAMP
        date = self.operation_date if root and self.operation_date else DATE
        if kind in self.event_times:
            stamp, date = self.event_times[kind]
        if root and kind == "expiration" and self.operation_stamp is None:
            stamp = "2030-08-03T12:00:00Z"
            date = "Sat, 03 Aug 2030 12:00:00 GMT"
        event = make_artifact(kind, **overrides, **{timestamp_field: stamp}, clock_attestation_identity=ZERO)
        nonce = hashlib.sha256(f"request-{self.transition_id}-{self.serial}".encode()).hexdigest()
        raw_request = (
            b"HEAD /rate_limit HTTP/1.1\r\n"
            b"Host: api.github.com\r\n"
            b"X-GitHub-Api-Version: 2022-11-28\r\n"
            + f"X-AML-Clock-Nonce: {nonce}\r\n".encode()
            + b"Cache-Control: no-cache, no-store\r\n"
            b"Pragma: no-cache\r\n"
            b"Connection: close\r\n\r\n"
        )
        request = make_artifact("clock_request", request_nonce=nonce, raw_request_bytes_base64=base64.b64encode(raw_request).decode())
        raw_headers = f"HTTP/1.1 200 OK\r\nDate: {date}\r\n\r\n".encode()
        evidence = make_artifact(
            "clock_evidence",
            request_identity=request["clock_request_identity"],
            raw_response_headers_base64=base64.b64encode(raw_headers).decode(),
            response_date_as_received=date,
            response_elapsed_milliseconds=100,
        )
        verifier = make_artifact(
            "clock_verifier_attestation",
            request_identity=request["clock_request_identity"],
            evidence_identity=evidence["clock_evidence_identity"],
            verifier_account_identity=self.system,
            verified_date=date,
            verified_at=stamp,
            replay_nonce=nonce,
        )
        projection = event_projection_identity(event, kind, self.c, timestamp_field)
        attestation = make_artifact(
            "clock_attestation",
            request_identity=request["clock_request_identity"],
            evidence_identity=evidence["clock_evidence_identity"],
            verifier_attestation_identity=verifier["clock_verifier_attestation_identity"],
            canonical_utc_timestamp=stamp,
            bound_artifact_type=kind,
            bound_event_projection_identity=projection,
            bound_timestamp_field=timestamp_field,
        )
        event["clock_attestation_identity"] = attestation["clock_attestation_identity"]
        schema = self.c["artifact_schemas"][kind]
        event[schema["identity_field"]] = artifact_identity(event, schema)
        self.add(kind, event)
        self.add("clock_request", request)
        self.add("clock_evidence", evidence)
        self.add("clock_verifier_attestation", verifier)
        self.add("clock_attestation", attestation)
        return event

    def prior(self, kind: str, record: dict[str, object], state: str | None) -> dict[str, object]:
        return self.add("typed_reference", _typed_reference(kind, record, state))

    def _build(self) -> None:
        role = self.add(
            "role_assignment",
            make_artifact(
                "role_assignment",
                governance_author_identity=self.governance_author,
                source_author_identity=self.source_author,
                authorization_author_identity=self.authorization_author,
                reviewer_identity=self.reviewer,
                operator_identity=self.operator,
                archive_custodian_identity=self.archive_custodian,
                previous_operator_identity=self.operator,
                superseding_authorization_author_identity=self.superseder,
                system_identity=self.system,
            ),
        )
        filesystem = self.add("filesystem_evidence", make_artifact("filesystem_evidence", device_id=1, mount_id=1, durability_trace=TRACE))
        source = self.add("source_checkout", make_artifact("source_checkout", source_commit=GIT_A, source_tree=GIT_B))
        environment = self.add("environment_manifest", make_artifact("environment_manifest"))
        access = self.add(
            "access_prohibition",
            make_artifact(
                "access_prohibition",
                operator_identity=self.operator,
                prohibited_resources=["holdout"],
                prohibited_credential_names=["ALPACA_API_KEY"],
                prohibited_filesystem_roots=["/synthetic/protected"],
                prohibited_network_destinations=["api.alpaca.markets"],
                inspected_resources=["holdout"],
                inspected_environment_names=["ALPACA_API_KEY"],
                inspected_filesystem_roots=["/synthetic/protected"],
                inspected_network_destinations=["api.alpaca.markets"],
            ),
        )
        store = self.add(
            "consumption_store",
            make_artifact(
                "consumption_store",
                filesystem_evidence_identity=filesystem["filesystem_evidence_identity"],
                canonical_root=self.store_root,
            ),
        )
        repository = self.add("repository_context", make_artifact("repository_context"))
        proposal = self.event(
            "proposal",
            "proposal_timestamp",
            root=False,
            authorization_author_identity=self.authorization_author,
            authorized_source_commit=GIT_A,
            authorized_source_tree=GIT_B,
            execution_command_identity=COMMAND_IDENTITY,
            authoritative_run_identity=self.authorized_run_identity,
        )
        proposal_ref = self.prior("proposal", proposal, "proposed")
        approval = self.event(
            "human_approval",
            "approval_timestamp",
            root=self.transition_id == "proposal_approved",
            proposal_identity=proposal["proposal_identity"],
            author_identity=self.authorization_author,
            reviewer_identity=self.reviewer,
        )
        approval_ref = self.prior("human_approval", approval, "approved")
        authorization = self.event(
            "authorization",
            "issued_at",
            proposal_identity=proposal["proposal_identity"],
            approval_identity=approval["approval_identity"],
            authorization_author_identity=self.authorization_author,
            reviewer_identity=self.reviewer,
            operator_identity=self.operator,
            environment_manifest_identity=environment["environment_manifest_identity"],
            source_checkout_identity=source["source_checkout_identity"],
            consumption_store_identity=store["consumption_store_identity"],
            access_prohibition_identity=access["access_prohibition_identity"],
            role_assignment_identity=role["role_assignment_identity"],
            repository_context_identity=repository["repository_context_identity"],
            authorized_source_commit=GIT_A,
            authorized_source_tree=GIT_B,
            v005_governance_identity=CONTRACT_IDENTITY,
            execution_command_identity=COMMAND_IDENTITY,
            execution_argv=self.c["execution_command"]["argv"],
            expires_at="2030-08-03T12:00:00Z",
            authoritative_run_identity=self.authorized_run_identity,
        )
        auth = authorization["authorization_identity"]
        activation = self.event(
            "activation",
            "activated_at",
            root=self.transition_id == "authorization_activated",
            authorization_identity=auth,
            prior_reference_identity=approval_ref["typed_reference_identity"],
            operator_identity=self.operator,
        )
        activation_ref = self.prior("activation", activation, "active_unconsumed")
        superseding = self.transition_id.startswith("supersession")
        successor = None
        successor_approval = None
        if superseding:
            successor_proposal = self.event(
                "proposal",
                "proposal_timestamp",
                authorization_author_identity=self.superseder,
                authorized_source_commit=GIT_A,
                authorized_source_tree=GIT_B,
                execution_command_identity=COMMAND_IDENTITY,
                authoritative_run_identity=self.authorized_run_identity,
            )
            successor_approval = self.event(
                "human_approval",
                "approval_timestamp",
                proposal_identity=successor_proposal["proposal_identity"],
                author_identity=self.superseder,
                reviewer_identity=self.reviewer,
            )
            successor = self.event(
                "authorization",
                "issued_at",
                proposal_identity=successor_proposal["proposal_identity"],
                approval_identity=successor_approval["approval_identity"],
                authorization_author_identity=self.superseder,
                reviewer_identity=self.reviewer,
                operator_identity=self.operator,
                environment_manifest_identity=environment["environment_manifest_identity"],
                source_checkout_identity=source["source_checkout_identity"],
                consumption_store_identity=store["consumption_store_identity"],
                access_prohibition_identity=access["access_prohibition_identity"],
                role_assignment_identity=role["role_assignment_identity"],
                repository_context_identity=repository["repository_context_identity"],
                authorized_source_commit=GIT_A,
                authorized_source_tree=GIT_B,
                v005_governance_identity=CONTRACT_IDENTITY,
                execution_command_identity=COMMAND_IDENTITY,
                execution_argv=self.c["execution_command"]["argv"],
                expires_at="2030-08-03T12:00:00Z",
                previous_authorization_identity=auth,
                authoritative_run_identity=self.authorized_run_identity,
            )
        decision = self.event(
            "authorization_decision",
            "decision_timestamp",
            root=self.transition_id in {"consumption_decision_won", "supersession_decision_won"},
            authorization_identity=auth,
            activation_identity=activation["activation_identity"],
            decision_kind="supersede" if superseding else "consume",
            successor_authorization_identity=successor["authorization_identity"] if successor else None,
            actor_identity=self.superseder if superseding else self.operator,
        )
        decision_ref = self.prior("authorization_decision", decision, "superseding" if superseding else "claiming")
        claim = self.event(
            "consumption_claim",
            "consumed_at",
            root=self.transition_id == "consumption_claim_durable",
            authorization_identity=auth,
            prior_reference_identity=decision_ref["typed_reference_identity"],
            operator_identity=self.operator,
            decision_identity=decision["decision_identity"],
            source_commit=GIT_A,
            source_tree=GIT_B,
            consumption_store_identity=store["consumption_store_identity"],
        )
        claim_ref = self.prior("consumption_claim", claim, "consumed")
        build = self.event(
            "build_start",
            "build_started_at",
            root=self.transition_id == "build_started",
            authorization_identity=auth,
            prior_reference_identity=claim_ref["typed_reference_identity"],
            operator_identity=self.operator,
            claim_identity=claim["claim_identity"],
        )
        build_ref = self.prior("build_start", build, "build_started")
        run = self.event(
            "run_start",
            "run_started_at",
            root=self.transition_id == "run_started",
            authorization_identity=auth,
            prior_reference_identity=build_ref["typed_reference_identity"],
            operator_identity=self.operator,
            build_start_identity=build["build_start_identity"],
        )
        run_ref = self.prior("run_start", run, "run_started")
        result = self.add(
            "result_manifest",
            make_artifact(
                "result_manifest",
                authorization_identity=auth,
                run_identity=self.lifecycle_run_identity,
            ),
        )
        failure = self.add(
            "failure",
            make_artifact(
                "failure",
                authorization_identity=auth,
                run_identity=self.lifecycle_run_identity,
            ),
        )
        failure_path = self.transition_id in {"run_failed", "build_failed", "failure_archive_started", "run_failure_recovered"}
        terminal_prior = build_ref if self.transition_id == "build_failed" else run_ref
        terminal = self.event(
            "lifecycle_terminal",
            "terminal_timestamp",
            root=self.transition_id in {"run_succeeded", "run_failed", "build_failed"},
            authorization_identity=auth,
            prior_reference_identity=terminal_prior["typed_reference_identity"],
            operator_identity=self.operator,
            terminal_state="run_failed" if failure_path else "run_succeeded",
            result_manifest_identity=None if failure_path else result["result_manifest_identity"],
            result_identities=[] if failure_path else result["result_identities"],
            failure_identity=failure["failure_identity"] if failure_path else None,
            failure_details=failure["failure_code"] if failure_path else None,
            run_identity=self.lifecycle_run_identity,
        )
        terminal_ref = self.prior("lifecycle_terminal", terminal, "run_failed" if failure_path else "run_succeeded")
        pending = self.event(
            "archive_pending",
            "archive_started_at",
            root=self.transition_id in {"success_archive_started", "failure_archive_started"},
            authorization_identity=auth,
            prior_reference_identity=terminal_ref["typed_reference_identity"],
            operator_identity=self.archive_custodian,
            terminal_identity=terminal["terminal_identity"],
            destination_relative_path=(
                self.archive_destination_override
                or "archives/" + str(terminal["run_identity"])
            ),
        )
        pending_ref = self.prior("archive_pending", pending, "archive_pending")
        archive = self.event(
            "archive_manifest",
            "archive_timestamp",
            authorization_identity=auth,
            archive_pending_identity=pending["archive_pending_identity"],
            terminal_identity=terminal["terminal_identity"],
            destination_relative_path=pending["destination_relative_path"],
            staging_relative_path="archives/staging/" + str(pending["archive_pending_identity"]),
            expected_file_identities=sorted(
                [terminal["terminal_identity"]]
                + ([failure["failure_identity"]] if failure_path else [result["result_manifest_identity"]])
                + ([] if failure_path else list(result["result_identities"]))
            ),
            archive_state="failure" if failure_path else "success",
            result_manifest_identity=None if failure_path else result["result_manifest_identity"],
            result_identities=[] if failure_path else result["result_identities"],
            failure_identity=failure["failure_identity"] if failure_path else None,
            failure_details=failure["failure_code"] if failure_path else None,
            run_identity=self.lifecycle_run_identity,
        )
        completion = self.event(
            "completion_marker",
            "completed_at",
            root=self.transition_id == "archive_completed",
            authorization_identity=auth,
            archive_identity=archive["archive_identity"],
            terminal_state=terminal["terminal_state"],
            actor_identity=self.archive_custodian,
            run_identity=self.lifecycle_run_identity,
        )
        archive_transition = self.transition_id in {
            "success_archive_started",
            "failure_archive_started",
            "archive_completed",
            "archive_indeterminate",
            "archive_recovered",
            "archive_completion_recovered",
        }
        complete_observation = self.transition_id in {
            "archive_completed",
            "archive_completion_recovered",
        }
        recovery_observation = self.transition_id == "archive_recovered"
        indeterminate_observation = self.transition_id == "archive_indeterminate"
        observed_files = (
            list(archive["expected_file_identities"])
            if complete_observation or recovery_observation
            else []
        )
        observation = self.event(
            "archive_observation",
            "observed_at",
            authorization_identity=auth,
            run_identity=self.lifecycle_run_identity,
            archive_pending_identity=pending["archive_pending_identity"],
            archive_identity=(
                archive["archive_identity"]
                if complete_observation or recovery_observation
                else None
            ),
            completion_marker_identity=(
                completion["completion_marker_identity"]
                if complete_observation
                else None
            ),
            destination_relative_path=pending["destination_relative_path"],
            staging_relative_path=(
                "archives/staging/" + str(pending["archive_pending_identity"])
            ),
            expected_file_identities=archive["expected_file_identities"],
            observed_file_identities=observed_files,
            unexpected_file_identities=[],
            observer_identity=self.archive_custodian,
            filesystem_evidence_identity=filesystem["filesystem_evidence_identity"],
            publication_mode=(
                "verify_complete"
                if complete_observation or indeterminate_observation
                else "authorized_recovery"
                if recovery_observation
                else "first_publication"
            ),
            destination_exists=(
                complete_observation or recovery_observation or indeterminate_observation
            ),
            manifest_exists=complete_observation or recovery_observation,
            marker_exists=complete_observation,
            required_files_present=complete_observation or recovery_observation,
            all_intended_bytes_match=(
                complete_observation or recovery_observation or indeterminate_observation
            ),
            unexpected_files=False,
            recovery_authorized=recovery_observation,
            all_file_fullfsyncs=complete_observation,
            directory_fsyncs=complete_observation,
            parent_fsync=complete_observation,
            marker_fullfsync=complete_observation,
            marker_archive_identity_matches=complete_observation,
        )
        supersession = self.event(
            "supersession",
            "supersession_timestamp",
            root=self.transition_id == "supersession_durable",
            predecessor_authorization_identity=auth,
            successor_authorization_identity=successor["authorization_identity"] if successor else ONE,
            decision_identity=decision["decision_identity"],
            superseding_author_identity=self.superseder,
            approval_identity=(
                successor_approval["approval_identity"]
                if successor_approval is not None
                else approval["approval_identity"]
            ),
        )
        rejection = self.event(
            "rejection",
            "rejected_at",
            root=self.transition_id in {"proposal_rejected", "preflight_rejected"},
            authorization_identity=None if self.transition_id == "proposal_rejected" else auth,
            proposal_identity=proposal["proposal_identity"],
            prior_reference_identity=(proposal_ref if self.transition_id == "proposal_rejected" else approval_ref)["typed_reference_identity"],
            actor_identity=self.reviewer if self.transition_id == "proposal_rejected" else self.operator,
        )
        expiration = self.event(
            "expiration",
            "expired_at",
            root=self.transition_id == "authorization_expired",
            authorization_identity=auth,
            prior_reference_identity=activation_ref["typed_reference_identity"],
            actor_identity=self.system,
        )
        indeterminate_prior_by_transition = {
            "claim_indeterminate": (decision_ref, "claim"),
            "build_indeterminate": (claim_ref, "build"),
            "run_indeterminate": (run_ref, "run"),
            "archive_indeterminate": (pending_ref, "archive"),
        }
        recovery_sources = {
            "claim_recovered": (decision_ref, "claim"),
            "build_recovered": (claim_ref, "build"),
            "run_success_recovered": (run_ref, "run"),
            "run_failure_recovered": (run_ref, "run"),
            "archive_recovered": (pending_ref, "archive"),
            "archive_completion_recovered": (pending_ref, "archive"),
        }
        source_ref, uncertain = indeterminate_prior_by_transition.get(self.transition_id, recovery_sources.get(self.transition_id, (decision_ref, "claim")))
        indeterminate = self.event(
            "indeterminate",
            "recorded_at",
            root=self.transition_id.endswith("_indeterminate"),
            authorization_identity=auth,
            prior_reference_identity=source_ref["typed_reference_identity"],
            uncertain_operation=self.uncertain_operation_override or uncertain,
            actor_identity=self.system,
        )
        indeterminate_ref = self.prior("indeterminate", indeterminate, "indeterminate")
        recovered_target = {
            "claim_recovered": claim,
            "build_recovered": build,
            "run_success_recovered": terminal,
            "run_failure_recovered": terminal,
            "archive_recovered": archive,
            "archive_completion_recovered": completion,
        }.get(self.transition_id, claim)
        recovered_kind = next(kind for kind, items in self.records.items() if recovered_target in items)
        recovered_state = {
            "consumption_claim": "consumed",
            "build_start": "build_started",
            "lifecycle_terminal": terminal["terminal_state"],
            "archive_pending": "archive_pending",
            "completion_marker": "archived",
        }.get(recovered_kind)
        recovered_ref = self.prior(recovered_kind, recovered_target, recovered_state)
        existing_payload = make_artifact("canonical_payload", artifact_type=recovered_kind, artifact_identity=artifact_self_identity(recovered_target, recovered_kind, self.c), canonical_bytes_base64=base64.b64encode(canonical_bytes(recovered_target)).decode(), canonical_bytes_sha256=hashlib.sha256(canonical_bytes(recovered_target)).hexdigest())
        self.add("canonical_payload", existing_payload)
        outcome = {
            "claim_recovered": "claim_durable",
            "build_recovered": "build_durable",
            "run_success_recovered": "run_succeeded",
            "run_failure_recovered": "run_failed",
            "archive_recovered": "archive_pending",
            "archive_completion_recovered": "archived",
        }.get(self.transition_id, "claim_durable")
        recovery = self.event(
            "recovery",
            "recovered_at",
            root=self.transition_id.endswith("_recovered"),
            authorization_identity=auth,
            indeterminate_identity=indeterminate["indeterminate_identity"],
            prior_indeterminate_identity=indeterminate["indeterminate_identity"],
            recovered_reference_identity=recovered_ref["typed_reference_identity"],
            existing_payload_identity=existing_payload["canonical_payload_identity"],
            intended_payload_identity=existing_payload["canonical_payload_identity"],
            recovery_outcome=self.recovery_outcome_override or outcome,
            recovery_actor_identity=self.archive_custodian if self.transition_id.startswith("archive") else self.operator,
        )
        roots = {
            "proposal_approved": approval,
            "authorization_activated": activation,
            "consumption_decision_won": decision,
            "consumption_claim_durable": claim,
            "build_started": build,
            "run_started": run,
            "run_succeeded": terminal,
            "run_failed": terminal,
            "build_failed": terminal,
            "success_archive_started": pending,
            "failure_archive_started": pending,
            "archive_completed": completion,
            "supersession_decision_won": decision,
            "supersession_durable": supersession,
            "authorization_expired": expiration,
            "proposal_rejected": rejection,
            "preflight_rejected": rejection,
            "claim_indeterminate": indeterminate,
            "build_indeterminate": indeterminate,
            "run_indeterminate": indeterminate,
            "archive_indeterminate": indeterminate,
            "claim_recovered": recovery,
            "build_recovered": recovery,
            "run_success_recovered": recovery,
            "run_failure_recovered": recovery,
            "archive_recovered": recovery,
            "archive_completion_recovered": recovery,
        }
        prior_refs = {
            "proposal_approved": proposal_ref,
            "authorization_activated": approval_ref,
            "consumption_decision_won": activation_ref,
            "consumption_claim_durable": decision_ref,
            "build_started": claim_ref,
            "run_started": build_ref,
            "run_succeeded": run_ref,
            "run_failed": run_ref,
            "build_failed": build_ref,
            "success_archive_started": terminal_ref,
            "failure_archive_started": terminal_ref,
            "archive_completed": pending_ref,
            "supersession_decision_won": activation_ref,
            "supersession_durable": decision_ref,
            "authorization_expired": activation_ref,
            "proposal_rejected": proposal_ref,
            "preflight_rejected": approval_ref,
            "claim_indeterminate": decision_ref,
            "build_indeterminate": claim_ref,
            "run_indeterminate": run_ref,
            "archive_indeterminate": pending_ref,
        }
        root = roots[self.transition_id]
        prior_ref = indeterminate_ref if self.transition_id.endswith("_recovered") else prior_refs[self.transition_id]
        if self.actor_override is not None:
            actor_field = {
                "human_approval": "author_identity", "activation": "operator_identity", "authorization_decision": "actor_identity",
                "consumption_claim": "operator_identity", "build_start": "operator_identity", "run_start": "operator_identity",
                "lifecycle_terminal": "operator_identity", "archive_pending": "operator_identity", "completion_marker": "actor_identity",
                "supersession": "superseding_author_identity", "expiration": "actor_identity", "rejection": "actor_identity",
                "indeterminate": "actor_identity", "recovery": "recovery_actor_identity",
            }[self.spec["new_artifact_type"]]
            root[actor_field] = self.actor_override
            root[self.c["artifact_schemas"][self.spec["new_artifact_type"]]["identity_field"]] = artifact_identity(root, self.c["artifact_schemas"][self.spec["new_artifact_type"]])
        root_type = self.spec["new_artifact_type"]
        root_bytes = canonical_bytes(root)
        payload = make_artifact("canonical_payload", artifact_type=root_type, artifact_identity=artifact_self_identity(root, root_type, self.c), canonical_bytes_base64=base64.b64encode(root_bytes).decode(), canonical_bytes_sha256=hashlib.sha256(root_bytes).hexdigest())
        self.add("canonical_payload", payload)
        expected_path = self.c["artifact_schemas"][root_type]["path"]
        for field in [part.split("}")[0] for part in expected_path.split("{")[1:]]:
            expected_path = expected_path.replace("{" + field + "}", str(root[field]))
        target_path = self.durability_path or expected_path
        transition_key = domain_hash("aml.olympics.v005.transition-key", {"transition_id": self.transition_id, "source_state": self.spec["from"], "destination_state": self.spec["to"], "root_artifact_identity": artifact_self_identity(root, root_type, self.c)})
        durability = self.add("durability_evidence", make_artifact("durability_evidence", target_artifact_type=root_type, target_artifact_identity=artifact_self_identity(root, root_type, self.c), canonical_payload_identity=payload["canonical_payload_identity"], target_relative_path=target_path, parent_relative_path=target_path.rsplit("/", 1)[0], filesystem_evidence_identity=filesystem["filesystem_evidence_identity"], transition_identity=transition_key, durability_trace=TRACE))
        support_refs: list[str] = []
        if self.transition_id == "authorization_activated":
            _, binding, proof = _documentary_fixture(authorization, repository["repository_context_identity"])
            self.add("documentary_binding", binding)
            support = self.prior("documentary_binding", binding, None)
            support_refs.append(support["typed_reference_identity"])
            self.documentary_proof = proof
        else:
            self.documentary_proof = None
        if archive_transition:
            support = self.prior("archive_observation", observation, None)
            support_refs.append(support["typed_reference_identity"])
        actor_identity = {
            "authorization_author": self.authorization_author,
            "reviewer": self.reviewer,
            "operator": self.operator,
            "archive_custodian": self.archive_custodian,
            "superseding_authorization_author": self.superseder,
            "system": self.system,
        }[self.spec["actor"]]
        envelope = make_artifact("transition_envelope", transition_id=self.transition_id, source_state=self.spec["from"], destination_state=self.spec["to"], actor_role=self.spec["actor"], actor_identity=actor_identity, root_artifact_type=root_type, root_artifact_identity=artifact_self_identity(root, root_type, self.c), prior_reference_identity=prior_ref["typed_reference_identity"], supporting_reference_identities=sorted(support_refs), role_assignment_identity=role["role_assignment_identity"], durability_evidence_identity=durability["durability_evidence_identity"])
        self.add("transition_envelope", envelope)
        self.envelope = envelope
        self.root = root
        self.bundle = self._closure(envelope)

    def _closure(self, envelope: dict[str, object]) -> dict[str, list[dict[str, object]]]:
        c = self.c
        registry: dict[str, tuple[str, dict[str, object]]] = {}
        for kind, items in self.records.items():
            for record in items:
                identity = artifact_self_identity(record, kind, c)
                registry[identity] = (kind, record)
        external = set(c["compatibility_edges"]["external_types"])
        queue = [envelope["transition_envelope_identity"]]
        seen: set[str] = set()
        while queue:
            identity = str(queue.pop())
            if identity in seen:
                continue
            seen.add(identity)
            kind, record = registry[identity]
            fields = c["artifact_schemas"][kind]["fields"]
            for field, rule in fields.items():
                targets: list[tuple[str, object]] = []
                if rule.startswith("identity:"):
                    targets = [(rule.split(":", 1)[1], record[field])]
                elif rule.startswith("nullable_identity:") and record[field] is not None:
                    targets = [(rule.split(":", 1)[1], record[field])]
                elif rule.startswith("array_identity:"):
                    target = rule.split(":")[1]
                    targets = [(target, item) for item in record[field]]
                for target, target_identity in targets:
                    if target not in external and target not in {"self", "command", "governance", "event_projection"}:
                        queue.append(str(target_identity))
            if kind == "typed_reference":
                queue.append(str(record["target_identity"]))
            elif kind == "canonical_payload":
                queue.append(str(record["artifact_identity"]))
            elif kind == "durability_evidence":
                queue.append(str(record["target_artifact_identity"]))
            elif kind == "transition_envelope":
                queue.append(str(record["root_artifact_identity"]))
        bundle: dict[str, list[dict[str, object]]] = {}
        for identity in seen:
            kind, record = registry[identity]
            bundle.setdefault(kind, []).append(record)
        for items in bundle.values():
            items.sort(key=lambda item: next(value for key, value in item.items() if key.endswith("_identity")))
        return bundle


def _git_oid(kind: str, payload: bytes) -> str:
    return hashlib.sha1(kind.encode() + b" " + str(len(payload)).encode() + b"\0" + payload).hexdigest()


def _tree_proof(path: str, leaf_oid: str) -> tuple[str, bytes]:
    child_oid = leaf_oid
    reverse_steps = []
    components = path.split("/")
    for index, component in reversed(list(enumerate(components))):
        mode = "100644" if index == len(components) - 1 else "40000"
        raw_tree = mode.encode() + b" " + component.encode() + b"\0" + bytes.fromhex(child_oid)
        tree_oid = _git_oid("tree", raw_tree)
        reverse_steps.append({"component": component, "mode": mode, "object_oid": child_oid, "object_type": "blob" if mode == "100644" else "tree", "raw_tree_base64": base64.b64encode(raw_tree).decode(), "tree_oid": tree_oid})
        child_oid = tree_oid
    return child_oid, canonical_bytes({"steps": list(reversed(reverse_steps))})


def _documentary_fixture(authorization: dict[str, object], repository_context_identity: str, *, authorization_identity: str | None = None, path: str | None = None) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    auth_bytes = canonical_bytes(authorization)
    auth_blob = _git_oid("blob", auth_bytes)
    auth_path = path or f"authorizations/{authorization['authorization_identity']}/authorization.json"
    tree_a, auth_tree_proof = _tree_proof(auth_path, auth_blob)
    commit_a_raw = f"tree {tree_a}\nparent {GIT_A}\nauthor Synthetic <s@example.com> 0 +0000\ncommitter Synthetic <s@example.com> 0 +0000\n\nauthorization\n".encode()
    commit_a = _git_oid("commit", commit_a_raw)
    binding = make_artifact("documentary_binding", authorization_identity=authorization_identity or authorization["authorization_identity"], authorization_relative_path=auth_path, authorization_blob_oid=auth_blob, authorization_tree_oid=tree_a, documentary_authorization_commit_oid=commit_a, authorized_source_parent_oid=GIT_A, repository_context_identity=repository_context_identity)
    binding_bytes = canonical_bytes(binding)
    binding_blob = _git_oid("blob", binding_bytes)
    binding_path = f"bindings/{authorization['authorization_identity']}/documentary_binding.json"
    tree_b, binding_tree_proof = _tree_proof(binding_path, binding_blob)
    commit_b_raw = f"tree {tree_b}\nparent {commit_a}\nauthor Synthetic <s@example.com> 1 +0000\ncommitter Synthetic <s@example.com> 1 +0000\n\nbinding\n".encode()
    proof = {"authorization_bytes": auth_bytes, "authorization_tree_proof_bytes": auth_tree_proof, "commit_a_raw_bytes": commit_a_raw, "binding_bytes": binding_bytes, "binding_tree_proof_bytes": binding_tree_proof, "commit_b_raw_bytes": commit_b_raw, "commit_b_oid": _git_oid("commit", commit_b_raw)}
    return authorization, binding, proof


def validate_fixture(fixture: Fixture) -> None:
    validate_transition_bundle(fixture.transition_id, fixture.spec["actor"], fixture.bundle, fixture.c, documentary_git_proof=fixture.documentary_proof)


def test_contract_identity_inventory_and_exact_transition_matrix() -> None:
    c = contract()
    validate_contract(c)
    assert c["contract_identity"] == CONTRACT_IDENTITY
    assert len(c["artifact_schemas"]) == 38
    assert c["lifecycle"]["transition_count"] == 27
    actual = {item["transition_id"]: (item["from"], item["to"], item["actor"], item["terminal"], item["prior_record_type"], item["new_artifact_type"], item["authorization_validity"]) for item in c["lifecycle"]["transitions"]}
    assert actual == EXPECTED_TRANSITIONS
    assert c["lifecycle"]["terminal_states"] == ["archived", "expired", "rejected", "superseded"]


def test_every_complete_matrix_identity_reproduces_independently() -> None:
    c = contract()
    projections = _matrix_projections(c)
    assert set(projections) == set(EXPECTED_MATRIX_IDENTITIES) == set(c["matrix_identities"])
    for name, projection in projections.items():
        assert domain_hash(f"aml.olympics.v005.matrix.{name}", projection) == EXPECTED_MATRIX_IDENTITIES[name]
        assert c["matrix_identities"][name] == EXPECTED_MATRIX_IDENTITIES[name]


@pytest.mark.parametrize("kind", sorted(contract()["artifact_schemas"]))
def test_every_schema_is_exact_and_identity_bound(kind: str) -> None:
    c = contract()
    record = make_artifact(kind)
    validate_artifact(record, kind, c)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_artifact({**record, "unknown": True}, kind, c)
    missing = dict(record)
    missing.pop(next(iter(record)))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_artifact(missing, kind, c)


SCHEMA_FIELDS = [
    (kind, field)
    for kind, schema in contract()["artifact_schemas"].items()
    for field in schema["fields"]
    if field != schema["identity_field"]
]


@pytest.mark.parametrize(("kind", "field"), SCHEMA_FIELDS)
def test_every_governed_schema_field_mutation_rejects(kind: str, field: str) -> None:
    c = contract()
    record = make_artifact(kind)
    original = record[field]
    if original is None:
        changed: object = ZERO
    elif type(original) is bool:
        changed = not original
    elif type(original) is int:
        changed = original + 1
    elif type(original) is str:
        changed = original + "x"
    else:
        changed = list(original) + [ONE]
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_artifact({**record, field: changed}, kind, c)


@pytest.mark.parametrize("transition_id", list(EXPECTED_TRANSITIONS))
def test_every_transition_executes_complete_reachable_synthetic_bundle(transition_id: str) -> None:
    fixture = Fixture(transition_id=transition_id)
    assert set(fixture.bundle) == set(fixture.spec["required_artifact_types"]) | ({"result_manifest"} if fixture.spec["required_one_of_artifact_type_sets"] == [["result_manifest"], ["failure"]] and "result_manifest" in fixture.bundle else {"failure"} if fixture.spec["required_one_of_artifact_type_sets"] else set())
    validate_fixture(fixture)


@pytest.mark.parametrize("transition_id", list(EXPECTED_TRANSITIONS))
def test_every_transition_rejects_wrong_actor_missing_type_and_orphan(transition_id: str) -> None:
    fixture = Fixture(transition_id=transition_id)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="actor"):
        validate_transition_bundle(transition_id, "wrong_actor", fixture.bundle, fixture.c, documentary_git_proof=fixture.documentary_proof)
    missing = dict(fixture.bundle)
    missing.pop("transition_envelope")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_transition_bundle(transition_id, fixture.spec["actor"], missing, fixture.c, documentary_git_proof=fixture.documentary_proof)
    orphan = {kind: list(items) for kind, items in fixture.bundle.items()}
    orphan["stable_account"].append(_account(999))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="orphaned"):
        validate_transition_bundle(transition_id, fixture.spec["actor"], orphan, fixture.c, documentary_git_proof=fixture.documentary_proof)


@pytest.mark.parametrize("transition_id", ["consumption_decision_won", "build_started", "run_started"])
def test_authorization_dependent_operations_after_expiry_reject(transition_id: str) -> None:
    fixture = Fixture(transition_id=transition_id, operation_stamp="2030-08-04T12:00:00Z", operation_date="Sun, 04 Aug 2030 12:00:00 GMT")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="not valid"):
        validate_fixture(fixture)


@pytest.mark.parametrize(
    "transition_id",
    [
        transition_id
        for transition_id, expected in EXPECTED_TRANSITIONS.items()
        if expected[6] == "issued_at<=operation<expires_at"
    ],
)
def test_every_authorization_validity_gate_rejects_after_expiry(transition_id: str) -> None:
    fixture = Fixture(transition_id=transition_id, operation_stamp="2030-08-04T12:00:00Z", operation_date="Sun, 04 Aug 2030 12:00:00 GMT")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="not valid"):
        validate_fixture(fixture)


@pytest.mark.parametrize("transition_id", list(EXPECTED_TRANSITIONS))
def test_every_transition_rejects_backward_root_timestamp(transition_id: str) -> None:
    fixture = Fixture(transition_id=transition_id, operation_stamp="2029-07-31T12:00:00Z", operation_date="Tue, 31 Jul 2029 12:00:00 GMT")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="predates|exact frozen boundary"):
        validate_fixture(fixture)


def test_build_before_claim_rejects() -> None:
    fixture = Fixture(transition_id="build_started", operation_stamp="2029-07-31T12:00:00Z", operation_date="Tue, 31 Jul 2029 12:00:00 GMT")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="predates"):
        validate_fixture(fixture)


def test_nonroot_lifecycle_history_cannot_move_backward() -> None:
    fixture = Fixture(
        transition_id="build_started",
        event_times={
            "authorization_decision": (
                "2029-07-31T12:00:00Z",
                "Tue, 31 Jul 2029 12:00:00 GMT",
            )
        },
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="predates|outside"):
        validate_fixture(fixture)


def test_authorized_run_and_lifecycle_run_must_match() -> None:
    fixture = Fixture(
        transition_id="run_succeeded",
        authorized_run_identity=ONE,
        lifecycle_run_identity=ZERO,
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="run identity"):
        validate_fixture(fixture)


def test_consumption_store_and_filesystem_identity_details_must_match() -> None:
    fixture = Fixture(transition_id="build_started", store_root="/synthetic/other")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="consumption store"):
        validate_fixture(fixture)


def test_indeterminate_and_recovery_outcomes_are_transition_specific() -> None:
    wrong_indeterminate = Fixture(
        transition_id="claim_indeterminate",
        uncertain_operation_override="archive",
    )
    with pytest.raises(
        OlympicsAuthorizationGovernanceV005Error,
        match="indeterminate operation|wrong typed predecessor",
    ):
        validate_fixture(wrong_indeterminate)
    wrong_recovery = Fixture(
        transition_id="run_success_recovered",
        recovery_outcome_override="run_failed",
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="recovery operation"):
        validate_fixture(wrong_recovery)


def test_archive_start_destination_is_exact() -> None:
    fixture = Fixture(
        transition_id="success_archive_started",
        archive_destination_override="archives/wrong",
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="archive start"):
        validate_fixture(fixture)


def test_terminal_and_archive_foundational_cross_bindings_reject() -> None:
    result = make_artifact("result_manifest", authorization_identity=ZERO, run_identity=ZERO)
    terminal = make_artifact("lifecycle_terminal", authorization_identity=ONE, run_identity=ONE, terminal_state="run_succeeded", result_manifest_identity=result["result_manifest_identity"], result_identities=result["result_identities"], failure_identity=None, failure_details=None)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="mismatch"):
        validate_terminal_bundle(terminal, result, None, contract())
    terminal = make_artifact("lifecycle_terminal", authorization_identity=ZERO, run_identity=ZERO, terminal_state="run_succeeded", result_manifest_identity=result["result_manifest_identity"], result_identities=result["result_identities"], failure_identity=None, failure_details=None)
    archive = make_artifact("archive_manifest", authorization_identity=ZERO, run_identity=ZERO, terminal_identity=terminal["terminal_identity"], archive_state="success", result_manifest_identity=result["result_manifest_identity"], result_identities=result["result_identities"], failure_identity=None, failure_details=None)
    completion = make_artifact("completion_marker", authorization_identity=ONE, run_identity=ONE, archive_identity=archive["archive_identity"], terminal_state="run_succeeded")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="foundational"):
        validate_archive_bundle(archive, terminal, completion, result, None, contract())


def test_documentary_binding_requires_exact_authorization_path_and_context() -> None:
    fixture = Fixture(transition_id="authorization_activated")
    authorization = fixture.bundle["authorization"][0]
    repository = authorization["repository_context_identity"]
    _, binding, proof = _documentary_fixture(authorization, repository)
    validate_documentary_git_proof(binding, authorization, contract(), proof)
    for wrong_identity, wrong_path in [(ONE, None), (None, "wrong/authorization.json")]:
        _, forged, forged_proof = _documentary_fixture(authorization, repository, authorization_identity=wrong_identity, path=wrong_path)
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="canonical path|authorization"):
            validate_documentary_git_proof(forged, authorization, contract(), forged_proof)


def test_clock_requires_external_verifier_and_rejects_unknown_headers() -> None:
    fixture = Fixture(transition_id="proposal_approved")
    evidence = fixture.bundle["clock_evidence"][0]
    request = next(item for item in fixture.bundle["clock_request"] if item["clock_request_identity"] == evidence["request_identity"])
    verifier = next(item for item in fixture.bundle["clock_verifier_attestation"] if item["evidence_identity"] == evidence["clock_evidence_identity"])
    attestation = next(item for item in fixture.bundle["clock_attestation"] if item["evidence_identity"] == evidence["clock_evidence_identity"])
    validate_clock_bundle(request, evidence, verifier, attestation, fixture.c)
    attacked = make_artifact("clock_evidence", **{**evidence, "clock_evidence_identity": ZERO, "raw_response_headers_base64": base64.b64encode(b"HTTP/1.1 200 OK\r\nDate: Wed, 31 Jul 2030 12:00:00 GMT\r\nX-Proxy-Cache: HIT\r\n\r\n").decode()})
    attacked_verifier = make_artifact("clock_verifier_attestation", **{**verifier, "clock_verifier_attestation_identity": ZERO, "evidence_identity": attacked["clock_evidence_identity"]})
    attacked_attestation = make_artifact("clock_attestation", **{**attestation, "clock_attestation_identity": ZERO, "evidence_identity": attacked["clock_evidence_identity"], "verifier_attestation_identity": attacked_verifier["clock_verifier_attestation_identity"]})
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="allowlist"):
        validate_clock_bundle(request, attacked, attacked_verifier, attacked_attestation, fixture.c)
    missing = {kind: list(items) for kind, items in fixture.bundle.items()}
    missing.pop("clock_verifier_attestation")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_transition_bundle("proposal_approved", "authorization_author", missing, fixture.c)


def test_clock_replay_nonce_and_freshness_are_bound() -> None:
    fixture = Fixture(transition_id="proposal_approved")
    evidence = fixture.bundle["clock_evidence"][0]
    request = next(
        item
        for item in fixture.bundle["clock_request"]
        if item["clock_request_identity"] == evidence["request_identity"]
    )
    verifier = next(
        item
        for item in fixture.bundle["clock_verifier_attestation"]
        if item["evidence_identity"] == evidence["clock_evidence_identity"]
    )
    attestation = next(
        item
        for item in fixture.bundle["clock_attestation"]
        if item["evidence_identity"] == evidence["clock_evidence_identity"]
    )
    wrong_nonce = make_artifact(
        "clock_verifier_attestation",
        **{
            **verifier,
            "clock_verifier_attestation_identity": ZERO,
            "replay_nonce": ONE,
        },
    )
    wrong_nonce_attestation = make_artifact(
        "clock_attestation",
        **{
            **attestation,
            "clock_attestation_identity": ZERO,
            "verifier_attestation_identity": wrong_nonce[
                "clock_verifier_attestation_identity"
            ],
        },
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="replay"):
        validate_clock_bundle(
            request,
            evidence,
            wrong_nonce,
            wrong_nonce_attestation,
            fixture.c,
        )
    stale = make_artifact(
        "clock_verifier_attestation",
        **{
            **verifier,
            "clock_verifier_attestation_identity": ZERO,
            "verified_at": "2030-07-31T12:00:06Z",
        },
    )
    stale_attestation = make_artifact(
        "clock_attestation",
        **{
            **attestation,
            "clock_attestation_identity": ZERO,
            "verifier_attestation_identity": stale[
                "clock_verifier_attestation_identity"
            ],
        },
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="freshness"):
        validate_clock_bundle(
            request,
            evidence,
            stale,
            stale_attestation,
            fixture.c,
        )


def test_actor_and_artifact_bound_durability_attacks_reject() -> None:
    wrong_actor = Fixture(transition_id="build_started")
    envelope = dict(wrong_actor.bundle["transition_envelope"][0], actor_identity=wrong_actor.authorization_author)
    envelope["transition_envelope_identity"] = artifact_identity(envelope, wrong_actor.c["artifact_schemas"]["transition_envelope"])
    wrong_actor.bundle["transition_envelope"] = [envelope]
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="assigned"):
        validate_fixture(wrong_actor)
    wrong_path = Fixture(transition_id="build_started", durability_path="wrong/build.json")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="durability"):
        validate_fixture(wrong_path)
    filesystem = make_artifact(
        "filesystem_evidence",
        device_id=1,
        mount_id=1,
        durability_trace=TRACE + ["rename_exclusive"],
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="exactly"):
        validate_filesystem_evidence(filesystem, contract())


def test_duplicate_and_same_type_ambiguity_attacks_reject() -> None:
    fixture = Fixture(transition_id="run_succeeded")
    duplicate = {kind: list(items) for kind, items in fixture.bundle.items()}
    duplicate["stable_account"].append(duplicate["stable_account"][0])
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="duplicate"):
        validate_transition_bundle("run_succeeded", "operator", duplicate, fixture.c)
    second_terminal = make_artifact("lifecycle_terminal")
    ambiguous = {kind: list(items) for kind, items in fixture.bundle.items()}
    ambiguous["lifecycle_terminal"].append(second_terminal)
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_transition_bundle("run_succeeded", "operator", ambiguous, fixture.c)
    extra_prior = {kind: list(items) for kind, items in fixture.bundle.items()}
    extra_prior["typed_reference"].append(_typed_reference("proposal", fixture.bundle["proposal"][0], "proposed"))
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="orphaned|duplicate"):
        validate_transition_bundle("run_succeeded", "operator", extra_prior, fixture.c)
    orphan_recovery = {kind: list(items) for kind, items in fixture.bundle.items()}
    orphan_recovery["recovery"] = [make_artifact("recovery")]
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
        validate_transition_bundle("run_succeeded", "operator", orphan_recovery, fixture.c)


def test_supersession_requires_active_state_role_and_no_competing_records() -> None:
    fixture = Fixture(transition_id="supersession_durable")
    records = fixture.bundle["supersession"]
    decisions = fixture.bundle["authorization_decision"]
    auths = {item["authorization_identity"]: item for item in fixture.bundle["authorization"]}
    accounts = {item["stable_account_identity"]: item for item in fixture.bundle["stable_account"]}
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="lacks active"):
        validate_supersession_chain(records, decisions, auths, fixture.c, activations={}, competing_records={}, role_assignment=fixture.bundle["role_assignment"][0], accounts=accounts)
    activations = {item["authorization_identity"]: item for item in fixture.bundle["activation"]}
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="no longer active"):
        validate_supersession_chain(records, decisions, auths, fixture.c, activations=activations, competing_records={"consumption_claim": [make_artifact("consumption_claim")]}, role_assignment=fixture.bundle["role_assignment"][0], accounts=accounts)
    wrong_previous = make_artifact(
        "role_assignment",
        **{
            **fixture.bundle["role_assignment"][0],
            "role_assignment_identity": ZERO,
            "previous_operator_identity": fixture.previous_operator,
        },
    )
    all_accounts = {
        item["stable_account_identity"]: item for item in fixture.accounts
    }
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="equality|role"):
        validate_supersession_chain(
            records,
            decisions,
            auths,
            fixture.c,
            activations=activations,
            competing_records={},
            role_assignment=wrong_previous,
            accounts=all_accounts,
        )
    self_supersession = Fixture(
        transition_id="supersession_decision_won",
        superseder_is_author=True,
    )
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="role separation"):
        validate_fixture(self_supersession)


def test_archive_truth_table_rejects_impossible_states() -> None:
    absent = {"destination_exists": False, "manifest_exists": False, "marker_exists": False, "required_files_present": False, "all_intended_bytes_match": False, "unexpected_files": False, "recovery_authorized": False, "all_file_fullfsyncs": False, "directory_fsyncs": False, "parent_fsync": False, "marker_fullfsync": False, "marker_archive_identity_matches": False}
    assert synthetic_archive_outcome("first_publication", absent) == "publication_permitted"
    impossible = dict(absent, marker_exists=True, marker_fullfsync=True)
    assert synthetic_archive_outcome("first_publication", impossible) == "invalid_conflicting"
    partial = dict(absent, destination_exists=True, manifest_exists=True, required_files_present=True, all_intended_bytes_match=True, recovery_authorized=True)
    assert synthetic_archive_outcome("authorized_recovery", partial) == "recovery_permitted"
    complete = {key: True for key in absent}
    complete["unexpected_files"] = False
    assert synthetic_archive_outcome("verify_complete", complete) == "already_complete_and_valid"
    assert synthetic_archive_outcome("first_publication", complete) == "invalid_conflicting"
    assert synthetic_archive_outcome("authorized_recovery", complete) == "invalid_conflicting"
    assert (
        synthetic_archive_outcome(
            "first_publication",
            dict(absent, marker_archive_identity_matches=True),
        )
        == "invalid_conflicting"
    )
    assert (
        synthetic_archive_outcome(
            "first_publication", dict(absent, recovery_authorized=True)
        )
        == "invalid_conflicting"
    )


def test_no_generic_prior_escape_hatch_and_recovery_is_reachable() -> None:
    c = contract()
    rules = [rule for schema in c["artifact_schemas"].values() for rule in schema["fields"].values()]
    assert "identity:prior_record" not in rules
    transitions = {item["transition_id"] for item in c["lifecycle"]["transitions"]}
    assert {"claim_recovered", "build_recovered", "run_success_recovered", "run_failure_recovered", "archive_recovered", "archive_completion_recovered"} <= transitions


def test_typed_prior_claimed_state_must_match_resolved_record() -> None:
    c = contract()
    failure = make_artifact("failure", authorization_identity=ZERO, run_identity=ZERO)
    terminal = make_artifact(
        "lifecycle_terminal",
        authorization_identity=ZERO,
        run_identity=ZERO,
        terminal_state="run_failed",
        result_manifest_identity=None,
        result_identities=[],
        failure_identity=failure["failure_identity"],
        failure_details=failure["failure_code"],
    )
    forged = _typed_reference("lifecycle_terminal", terminal, "run_succeeded")
    with pytest.raises(OlympicsAuthorizationGovernanceV005Error, match="resolved artifact state"):
        validate_typed_reference(
            forged,
            {terminal["terminal_identity"]: ("lifecycle_terminal", terminal)},
            c,
            expected_type="lifecycle_terminal",
            expected_state="run_succeeded",
        )


def test_canonical_json_attacks_reject() -> None:
    canonical = canonical_bytes({"a": 1})
    assert strict_json_bytes(canonical) == {"a": 1}
    for raw in [b'{"a":1,"a":1}\n', b'{"a":true }\n', b'{"a":1.0}\n', b'\xef\xbb\xbf{"a":1}\n', canonical + b"\n"]:
        with pytest.raises(OlympicsAuthorizationGovernanceV005Error):
            strict_json_bytes(raw)


def test_contract_file_and_cli_are_canonical_pure_and_deterministic() -> None:
    raw = CONTRACT_PATH.read_bytes()
    assert raw == canonical_bytes(contract())
    outputs = []
    for seed, timezone_name in [("0", "UTC"), ("1", "America/Denver"), ("999", "Asia/Tokyo")]:
        env = {**os.environ, "PYTHONHASHSEED": seed, "TZ": timezone_name, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
        completed = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT)], check=True, capture_output=True, env=env)
        outputs.append(completed.stdout)
    assert len(set(outputs)) == 1
    report = json.loads(outputs[0])
    assert report["authorization_created"] is False
    assert report["official_run_executed"] is False
    assert report["artifact_schema_count"] == 38
    assert report["lifecycle_transition_count"] == 27


def test_no_execution_network_or_authorization_consumer_capability() -> None:
    source = (ROOT / "src/aml/professional_strategy_olympics_authorization_governance_v005.py").read_text(encoding="utf-8")
    for forbidden in ["requests", "urllib", "socket", "import subprocess", "os.system", "eval(", "exec(", "run_professional_strategy_olympics_v005.py\""]:
        assert forbidden not in source
    assert not list(ROOT.glob("authorizations/**/*.json"))
    assert not list(ROOT.glob("archives/**/*.json"))
