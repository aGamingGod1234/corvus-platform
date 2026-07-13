from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

from corvus.application.ports import (
    ProjectAuditEvent,
    ProjectCreateLifecycleError,
)
from corvus.domain.audit import (
    AuditAnchorBindingState,
    AuditAnchorRecoveryCheckpoint,
    AuditReceipt,
    AuditResultBinding,
)
from corvus.domain.deployment import AuthorityCommitIntent, AuthorityCommitState, WorkspaceAuthority
from corvus.domain.identity import Project
from corvus.infrastructure.project_audit import (
    ProjectAuditReceiptContext,
    ProjectAuditSigner,
    SignedProjectAuditAdapter,
)
from corvus.infrastructure.repositories.audit import AuditRepository
from corvus.infrastructure.repositories.projects import ProjectRepository

_INTENT_NAMESPACE = UUID("a41865d4-4ef0-4ffc-9da6-3178bc546ffe")
_CHECKPOINT_NAMESPACE = UUID("620951a5-b3dc-44b0-abd7-47eb830698ae")
_BINDING_NAMESPACE = UUID("c73f4b34-8f6b-4ed1-bb6a-b80d24c50375")


class ProjectCreateRecoveryError(ProjectCreateLifecycleError):
    pass


class AuthorityCommitReceiptEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProjectAuthorityRepositoryPort(Protocol):
    def get_workspace_authority(self, workspace_id: UUID) -> WorkspaceAuthority | None: ...

    def get_commit_intent(
        self,
        *,
        workspace_id: UUID,
        intent_id: UUID,
    ) -> AuthorityCommitIntent | None: ...

    def prepare_commit(self, intent: AuthorityCommitIntent) -> None: ...

    def advance_commit(
        self,
        intent: AuthorityCommitIntent,
        *,
        expected_state: AuthorityCommitState,
    ) -> None: ...


class ProjectAuthorityAnchorPort(Protocol):
    def reserve(self, intent: AuthorityCommitIntent) -> None: ...

    def finalize(self, intent: AuthorityCommitIntent) -> AuthorityCommitReceiptEvidence: ...


class ProjectAuthorityMutationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mutation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposed_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProjectAuthorityMutationPlannerPort(Protocol):
    def plan(
        self,
        project: Project,
        event: ProjectAuditEvent,
        authority: WorkspaceAuthority,
    ) -> ProjectAuthorityMutationPlan: ...


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def project_mutation_digest(project: Project) -> str:
    return hashlib.sha256(_canonical_json(project.model_dump(mode="json"))).hexdigest()


def audit_result_binding_hash(binding: AuditResultBinding) -> str:
    unsigned = binding.model_dump(
        mode="json",
        exclude={"binding_hash", "binding_signature"},
    )
    return hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def _stable_id(namespace: UUID, event: ProjectAuditEvent) -> UUID:
    return uuid5(namespace, f"{event.workspace_id}:{event.request_id}:{event.project_id}")


class RecoverableProjectCreateLifecycle:
    def __init__(
        self,
        *,
        authority_repository: ProjectAuthorityRepositoryPort,
        audit_repository: AuditRepository,
        project_repository: ProjectRepository,
        audit_adapter: SignedProjectAuditAdapter,
        anchor: ProjectAuthorityAnchorPort,
        mutation_planner: ProjectAuthorityMutationPlannerPort,
        signer: ProjectAuditSigner,
        clock: Callable[[], datetime],
    ) -> None:
        self.authority_repository = authority_repository
        self.audit_repository = audit_repository
        self.project_repository = project_repository
        self.audit_adapter = audit_adapter
        self.anchor = anchor
        self.mutation_planner = mutation_planner
        self.signer = signer
        self.clock = clock

    def create(self, project: Project, event: ProjectAuditEvent) -> None:
        self._validate_request(project, event)
        mutation_digest = project_mutation_digest(project)
        intent = self._load_or_prepare_intent(project, event, mutation_digest)
        if intent.state is AuthorityCommitState.QUARANTINED:
            raise ProjectCreateRecoveryError("authority_commit_quarantined")
        intent = self._reserve_anchor(intent)
        receipt = self._load_or_append_receipt(event, intent)
        checkpoint = self._load_or_prepare_checkpoint(event, receipt, mutation_digest)

        try:
            self.project_repository.add_idempotent(project)
        except Exception as exc:
            raise ProjectCreateRecoveryError("project_persistence_failed") from exc

        intent = self._commit_authority(intent)
        evidence, intent = self._finalize_authority(intent)
        checkpoint = self._mark_authority_finalized(checkpoint)
        binding = self._load_or_append_binding(
            event=event,
            receipt=receipt,
            intent=intent,
            evidence=evidence,
            prepared_result_digest=mutation_digest,
        )
        self._complete_checkpoint(checkpoint, binding)

    @staticmethod
    def _validate_request(project: Project, event: ProjectAuditEvent) -> None:
        if (
            event.action != "project.create"
            or event.decision != "allow"
            or event.workspace_id != project.workspace_id
            or event.project_id != project.id
        ):
            raise ProjectCreateRecoveryError("project_create_event_mismatch")

    def _load_or_prepare_intent(
        self,
        project: Project,
        event: ProjectAuditEvent,
        mutation_digest: str,
    ) -> AuthorityCommitIntent:
        intent_id = _stable_id(_INTENT_NAMESPACE, event)
        existing = self.authority_repository.get_commit_intent(
            workspace_id=event.workspace_id,
            intent_id=intent_id,
        )
        if existing is not None:
            if existing.mutation_digest != mutation_digest:
                raise ProjectCreateRecoveryError("project_replay_mismatch")
            return existing
        authority = self.authority_repository.get_workspace_authority(event.workspace_id)
        if authority is None:
            raise ProjectCreateRecoveryError("workspace_authority_missing")
        try:
            plan = self.mutation_planner.plan(project, event, authority)
        except Exception as exc:
            raise ProjectCreateRecoveryError("authority_root_plan_failed") from exc
        if (
            plan.mutation_digest != mutation_digest
            or plan.proposed_state_root == authority.authority_state_root
        ):
            raise ProjectCreateRecoveryError("authority_root_plan_mismatch")
        intent = AuthorityCommitIntent(
            id=intent_id,
            workspace_id=event.workspace_id,
            epoch=authority.epoch,
            deployment_instance_id=authority.deployment_instance_id,
            prior_generation=authority.authority_generation,
            next_generation=authority.authority_generation + 1,
            prior_state_root=authority.authority_state_root,
            mutation_digest=mutation_digest,
            proposed_state_root=plan.proposed_state_root,
            state=AuthorityCommitState.PREPARED,
            created_at=self.clock(),
        )
        try:
            self.authority_repository.prepare_commit(intent)
        except Exception as exc:
            raise ProjectCreateRecoveryError("authority_prepare_failed") from exc
        return intent

    def _reserve_anchor(self, intent: AuthorityCommitIntent) -> AuthorityCommitIntent:
        if intent.state is not AuthorityCommitState.PREPARED:
            return intent
        try:
            self.anchor.reserve(intent)
            reserved = intent.model_copy(update={"state": AuthorityCommitState.ANCHOR_RESERVED})
            self.authority_repository.advance_commit(
                reserved,
                expected_state=AuthorityCommitState.PREPARED,
            )
        except Exception as exc:
            raise ProjectCreateRecoveryError("authority_reservation_failed") from exc
        return reserved

    def _load_or_append_receipt(
        self,
        event: ProjectAuditEvent,
        intent: AuthorityCommitIntent,
    ) -> AuditReceipt:
        matches = [
            receipt
            for receipt in self.audit_repository.list_receipts(event.workspace_id)
            if receipt.authority_commit_intent_id == intent.id
        ]
        if len(matches) > 1:
            raise ProjectCreateRecoveryError("duplicate_authority_audit_receipt")
        if matches:
            receipt = matches[0]
            if (
                receipt.request_context_id != event.request_id
                or receipt.authorization_snapshot_id != event.authorization_snapshot_id
                or receipt.intended_mutation_digest != intent.mutation_digest
                or receipt.action != event.action
                or receipt.resource != f"project:{event.project_id}"
            ):
                raise ProjectCreateRecoveryError("audit_receipt_replay_mismatch")
            return receipt
        snapshot = self.audit_repository.get_snapshot(
            workspace_id=event.workspace_id,
            snapshot_id=event.authorization_snapshot_id,
        )
        if snapshot is None:
            raise ProjectCreateRecoveryError("authorization_snapshot_missing")
        context = ProjectAuditReceiptContext(
            request_context_id=event.request_id,
            prior_authority_epoch=intent.epoch,
            prior_authority_generation=intent.prior_generation,
            prior_authority_state_root=intent.prior_state_root,
            prior_authority_commit_receipt_id=snapshot.authority_commit_receipt_id,
            authority_commit_intent_id=intent.id,
            intended_mutation_digest=intent.mutation_digest,
            signing_key_version_id=snapshot.signing_key_version_id,
        )
        try:
            return self.audit_adapter.record_with_context(event, context)
        except Exception as exc:
            raise ProjectCreateRecoveryError("audit_persistence_failed") from exc

    def _load_or_prepare_checkpoint(
        self,
        event: ProjectAuditEvent,
        receipt: AuditReceipt,
        prepared_result_digest: str,
    ) -> AuditAnchorRecoveryCheckpoint:
        checkpoint_id = _stable_id(_CHECKPOINT_NAMESPACE, event)
        existing = self.audit_repository.get_recovery_checkpoint(
            workspace_id=event.workspace_id,
            checkpoint_id=checkpoint_id,
        )
        if existing is not None:
            if (
                existing.audit_receipt_id != receipt.id
                or existing.authority_commit_intent_id != receipt.authority_commit_intent_id
                or existing.prepared_result_digest != prepared_result_digest
            ):
                raise ProjectCreateRecoveryError("audit_recovery_replay_mismatch")
            return existing
        checkpoint = AuditAnchorRecoveryCheckpoint(
            id=checkpoint_id,
            workspace_id=event.workspace_id,
            audit_receipt_id=receipt.id,
            authority_commit_intent_id=receipt.authority_commit_intent_id,
            prepared_result_digest=prepared_result_digest,
            state=AuditAnchorBindingState.PREPARED,
            updated_at=self.clock(),
        )
        try:
            self.audit_repository.prepare_recovery(checkpoint)
        except Exception as exc:
            raise ProjectCreateRecoveryError("audit_recovery_prepare_failed") from exc
        return checkpoint

    def _commit_authority(self, intent: AuthorityCommitIntent) -> AuthorityCommitIntent:
        if intent.state is not AuthorityCommitState.ANCHOR_RESERVED:
            return intent
        committed = intent.model_copy(update={"state": AuthorityCommitState.DB_COMMITTED})
        try:
            self.authority_repository.advance_commit(
                committed,
                expected_state=AuthorityCommitState.ANCHOR_RESERVED,
            )
        except Exception as exc:
            raise ProjectCreateRecoveryError("authority_commit_failed") from exc
        return committed

    def _finalize_authority(
        self,
        intent: AuthorityCommitIntent,
    ) -> tuple[AuthorityCommitReceiptEvidence, AuthorityCommitIntent]:
        if intent.state not in {
            AuthorityCommitState.DB_COMMITTED,
            AuthorityCommitState.ANCHOR_FINALIZED,
        }:
            raise ProjectCreateRecoveryError("authority_commit_state_invalid")
        try:
            evidence = self.anchor.finalize(intent)
            if intent.state is AuthorityCommitState.DB_COMMITTED:
                finalized = intent.model_copy(
                    update={"state": AuthorityCommitState.ANCHOR_FINALIZED}
                )
                self.authority_repository.advance_commit(
                    finalized,
                    expected_state=AuthorityCommitState.DB_COMMITTED,
                )
                intent = finalized
        except Exception as exc:
            raise ProjectCreateRecoveryError("authority_finalize_failed") from exc
        return evidence, intent

    def _mark_authority_finalized(
        self,
        checkpoint: AuditAnchorRecoveryCheckpoint,
    ) -> AuditAnchorRecoveryCheckpoint:
        if checkpoint.state is not AuditAnchorBindingState.PREPARED:
            return checkpoint
        finalized = checkpoint.model_copy(
            update={
                "state": AuditAnchorBindingState.AUTHORITY_FINALIZED,
                "updated_at": self.clock(),
            }
        )
        try:
            self.audit_repository.advance_recovery(
                finalized,
                expected_state=AuditAnchorBindingState.PREPARED,
            )
        except Exception as exc:
            raise ProjectCreateRecoveryError("audit_recovery_finalize_failed") from exc
        return finalized

    def _load_or_append_binding(
        self,
        *,
        event: ProjectAuditEvent,
        receipt: AuditReceipt,
        intent: AuthorityCommitIntent,
        evidence: AuthorityCommitReceiptEvidence,
        prepared_result_digest: str,
    ) -> AuditResultBinding:
        if self.signer.signing_key_version_id != receipt.signing_key_version_id:
            raise ProjectCreateRecoveryError("audit_binding_signing_key_mismatch")
        binding_id = _stable_id(_BINDING_NAMESPACE, event)
        existing = self.audit_repository.get_result_binding(
            workspace_id=event.workspace_id,
            binding_id=binding_id,
        )
        if existing is not None:
            if (
                existing.audit_receipt_id != receipt.id
                or existing.audit_receipt_hash != receipt.receipt_hash
                or existing.authority_commit_intent_id != intent.id
                or existing.prepared_result_digest != prepared_result_digest
                or existing.finalized_authority_epoch != intent.epoch
                or existing.finalized_authority_generation != intent.next_generation
                or existing.finalized_authority_state_root != intent.proposed_state_root
                or existing.authority_commit_receipt_id != evidence.id
                or existing.authority_commit_receipt_digest != evidence.digest
                or existing.signing_key_version_id != receipt.signing_key_version_id
            ):
                raise ProjectCreateRecoveryError("audit_result_binding_replay_mismatch")
            return existing
        provisional = AuditResultBinding(
            id=binding_id,
            workspace_id=event.workspace_id,
            audit_receipt_id=receipt.id,
            audit_receipt_hash=receipt.receipt_hash,
            authority_commit_intent_id=intent.id,
            prepared_result_digest=prepared_result_digest,
            finalized_authority_epoch=intent.epoch,
            finalized_authority_generation=intent.next_generation,
            finalized_authority_state_root=intent.proposed_state_root,
            authority_commit_receipt_id=evidence.id,
            authority_commit_receipt_digest=evidence.digest,
            signing_key_version_id=self.signer.signing_key_version_id,
            binding_hash="0" * 64,
            binding_signature="pending",
            created_at=self.clock(),
        )
        binding_hash = audit_result_binding_hash(provisional)
        binding = provisional.model_copy(
            update={
                "binding_hash": binding_hash,
                "binding_signature": base64.b64encode(
                    self.signer.sign(bytes.fromhex(binding_hash))
                ).decode(),
            }
        )
        try:
            self.audit_repository.append_result_binding(binding)
        except Exception as exc:
            raise ProjectCreateRecoveryError("audit_result_binding_failed") from exc
        return binding

    def _complete_checkpoint(
        self,
        checkpoint: AuditAnchorRecoveryCheckpoint,
        binding: AuditResultBinding,
    ) -> None:
        if checkpoint.state is AuditAnchorBindingState.AUTHORITY_FINALIZED:
            checkpoint = checkpoint.model_copy(
                update={
                    "state": AuditAnchorBindingState.BINDING_PERSISTED,
                    "result_binding_id": binding.id,
                    "updated_at": self.clock(),
                }
            )
            try:
                self.audit_repository.advance_recovery(
                    checkpoint,
                    expected_state=AuditAnchorBindingState.AUTHORITY_FINALIZED,
                )
            except Exception as exc:
                raise ProjectCreateRecoveryError("audit_binding_checkpoint_failed") from exc
        if checkpoint.state is AuditAnchorBindingState.BINDING_PERSISTED:
            complete = checkpoint.model_copy(
                update={
                    "state": AuditAnchorBindingState.COMPLETE,
                    "updated_at": self.clock(),
                }
            )
            try:
                self.audit_repository.advance_recovery(
                    complete,
                    expected_state=AuditAnchorBindingState.BINDING_PERSISTED,
                )
            except Exception as exc:
                raise ProjectCreateRecoveryError("audit_completion_failed") from exc
        elif checkpoint.state is not AuditAnchorBindingState.COMPLETE:
            raise ProjectCreateRecoveryError("audit_recovery_state_invalid")
