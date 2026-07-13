from __future__ import annotations

import base64
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from corvus.application.ports import (
    ProjectAuditEvent,
    ProjectAuthorizationDecision,
    ProjectAuthorizationRequest,
)
from corvus.application.projects import (
    CreateProjectCommand,
    ProjectRepositoryAdapter,
    ProjectService,
)
from corvus.domain.audit import (
    AuditResultBinding,
    AuthorizationDecisionSnapshot,
    authorization_snapshot_digest,
)
from corvus.domain.deployment import (
    AuthorityCommitIntent,
    AuthorityCommitState,
    AuthorityEpochCredential,
    AuthorityMode,
    AuthorityTrustAnchor,
    AuthorityTrustAnchorKind,
    AuthProfile,
    DeploymentInstance,
    DeploymentInstanceLease,
    DeploymentProfile,
    NetworkProfile,
    StorageProfile,
    WorkspaceAuthority,
    WorkspaceAuthorityState,
    fixed_workspace_lock_name,
)
from corvus.domain.identity import Project
from corvus.infrastructure.db import upgrade_database
from corvus.infrastructure.project_audit import SignedProjectAuditAdapter
from corvus.infrastructure.project_recovery import (
    AuthorityCommitReceiptEvidence,
    ProjectAuthorityMutationPlan,
    RecoverableProjectCreateLifecycle,
    audit_result_binding_hash,
    project_mutation_digest,
)
from corvus.infrastructure.repositories.audit import AuditRepository
from corvus.infrastructure.repositories.authority import AuthorityRepository
from corvus.infrastructure.repositories.projects import ProjectRepository
from corvus.store import TraceStore

_NOW = datetime(2026, 7, 14, 20, 0, tzinfo=UTC)


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    upgrade_database(database)
    return database


def _authority(repository: AuthorityRepository, workspace_id: UUID) -> WorkspaceAuthority:
    profile = DeploymentProfile(
        authority_mode=AuthorityMode.EMBEDDED_LOCAL,
        auth_profile=AuthProfile.LOCAL_OS,
        network_profile=NetworkProfile.IN_PROCESS,
        storage_profile=StorageProfile.SQLITE,
        enabled_adapters=frozenset({"cli"}),
        protocol_version="v2alpha1",
        created_at=_NOW,
        updated_at=_NOW,
    )
    instance = DeploymentInstance(
        deployment_profile_id=profile.id,
        instance_public_key="instance-public-key",
        non_exportable_activation_key_ref="keyring://corvus/instance/current",
        device_binding_digest="a" * 64,
        activated_at=_NOW,
    )
    credential = AuthorityEpochCredential(
        workspace_id=workspace_id,
        authority_epoch=1,
        deployment_instance_id=instance.id,
        public_key="epoch-public-key",
        non_exportable_private_key_ref="keyring://corvus/epoch/current",
        device_binding_digest=instance.device_binding_digest,
        issued_at=_NOW,
    )
    anchor = AuthorityTrustAnchor(
        workspace_id=workspace_id,
        kind=AuthorityTrustAnchorKind.SEALED_LOCAL_GENERATION,
        local_lock_name=fixed_workspace_lock_name(workspace_id, 1),
        sealed_generation_ref="keyring://corvus/sealed-generation/current",
        device_binding_digest=instance.device_binding_digest,
        policy_digest="b" * 64,
        created_at=_NOW,
    )
    lease = DeploymentInstanceLease(
        workspace_id=workspace_id,
        authority_epoch=1,
        deployment_instance_id=instance.id,
        lock_name=fixed_workspace_lock_name(workspace_id, 1),
        fencing_token=1,
        acquired_at=_NOW,
    )
    authority = WorkspaceAuthority(
        workspace_id=workspace_id,
        deployment_profile_id=profile.id,
        deployment_instance_id=instance.id,
        epoch=1,
        authority_generation=4,
        authority_state_root="c" * 64,
        authority_epoch_credential_id=credential.id,
        trust_anchor_id=anchor.id,
        active_lease_id=lease.id,
        state=WorkspaceAuthorityState.ACTIVE,
        activated_at=_NOW,
    )
    repository.add_deployment_profile(profile)
    repository.add_deployment_instance(instance)
    repository.add_epoch_credential(credential)
    repository.add_trust_anchor(anchor)
    repository.acquire_lease(lease)
    repository.add_workspace_authority(authority)
    return authority


def _snapshot(
    *,
    request_id: UUID,
    project: Project,
    requester_id: UUID,
    signing_key_id: UUID,
    private_key: Ed25519PrivateKey,
    authority: WorkspaceAuthority,
) -> AuthorizationDecisionSnapshot:
    canonical_inputs = {
        "action": "project.create",
        "resource": f"project:{project.id}",
    }
    source_versions = {"access_bundle": 1, "agent_grant": 1}
    canonical_digest = authorization_snapshot_digest(canonical_inputs, source_versions)
    unsigned = AuthorizationDecisionSnapshot(
        workspace_id=project.workspace_id,
        request_context_id=request_id,
        deployment_instance_id=authority.deployment_instance_id,
        authority_epoch_credential_id=authority.authority_epoch_credential_id,
        authority_generation=authority.authority_generation,
        authority_state_root=authority.authority_state_root,
        authority_commit_receipt_id=uuid4(),
        authority_proof_digest="d" * 64,
        membership_version_ids=(uuid4(),),
        membership_digest="e" * 64,
        scope_kind="project",
        scope_id=project.id,
        scope_digest="f" * 64,
        audience_policy_snapshot_id=uuid4(),
        audience_digest="0" * 64,
        requester_id=requester_id,
        transport_principal_id=uuid4(),
        access_bundle_id=uuid4(),
        access_bundle_version_digest="1" * 64,
        agent_grant_id=uuid4(),
        agent_delegation_digest="2" * 64,
        policy_digest="3" * 64,
        autonomy_policy_digest="4" * 64,
        budget_snapshot_ids=(uuid4(),),
        budget_snapshot_digest="5" * 64,
        kill_switch_snapshot_ids=(uuid4(),),
        kill_switch_snapshot_digest="6" * 64,
        decision="allow",
        reason_code="authorized",
        canonical_inputs_json=canonical_inputs,
        source_record_version_map=source_versions,
        canonical_digest=canonical_digest,
        signing_key_version_id=signing_key_id,
        snapshot_signature="pending",
        created_at=_NOW,
    )
    signature = base64.b64encode(private_key.sign(unsigned.canonical_digest.encode())).decode()
    return unsigned.model_copy(update={"snapshot_signature": signature})


class Ed25519Signer:
    def __init__(self, key_id: UUID, private_key: Ed25519PrivateKey) -> None:
        self.signing_key_version_id = key_id
        self.private_key = private_key

    def sign(self, data: bytes) -> bytes:
        return self.private_key.sign(data)


class FixedAuthorization:
    def __init__(self, snapshot: AuthorizationDecisionSnapshot) -> None:
        self.snapshot = snapshot

    def authorize(self, request: ProjectAuthorizationRequest) -> ProjectAuthorizationDecision:
        assert request.request_id == self.snapshot.request_context_id
        return ProjectAuthorizationDecision(
            allowed=True,
            reason_code="authorized",
            authorization_snapshot_id=self.snapshot.id,
        )


class IdempotentAnchor:
    def __init__(self) -> None:
        self.reserved: set[UUID] = set()
        self.finalized: set[UUID] = set()

    def reserve(self, intent: AuthorityCommitIntent) -> None:
        self.reserved.add(intent.id)

    def finalize(self, intent: AuthorityCommitIntent) -> AuthorityCommitReceiptEvidence:
        self.finalized.add(intent.id)
        return AuthorityCommitReceiptEvidence(
            id=UUID("00000000-0000-0000-0000-000000000099"),
            digest="9" * 64,
        )


class FixedManifestPlanner:
    def plan(
        self,
        project: Project,
        event: ProjectAuditEvent,
        authority: WorkspaceAuthority,
    ) -> ProjectAuthorityMutationPlan:
        assert event.workspace_id == authority.workspace_id
        return ProjectAuthorityMutationPlan(
            mutation_digest=project_mutation_digest(project),
            proposed_state_root="7" * 64,
        )


class FailDbCommitOnce:
    def __init__(self, repository: AuthorityRepository) -> None:
        self.repository = repository
        self.failed = False

    def get_workspace_authority(self, workspace_id: UUID):
        return self.repository.get_workspace_authority(workspace_id)

    def get_commit_intent(self, *, workspace_id: UUID, intent_id: UUID):
        return self.repository.get_commit_intent(workspace_id=workspace_id, intent_id=intent_id)

    def prepare_commit(self, intent: AuthorityCommitIntent) -> None:
        self.repository.prepare_commit(intent)

    def advance_commit(
        self,
        intent: AuthorityCommitIntent,
        *,
        expected_state: AuthorityCommitState,
    ) -> None:
        if intent.state is AuthorityCommitState.DB_COMMITTED and not self.failed:
            self.failed = True
            raise RuntimeError("injected authority DB commit failure")
        self.repository.advance_commit(intent, expected_state=expected_state)


def _lifecycle(
    *,
    authority,
    audit_repository: AuditRepository,
    project_repository: ProjectRepository,
    anchor: IdempotentAnchor,
    signer: Ed25519Signer,
) -> RecoverableProjectCreateLifecycle:
    return RecoverableProjectCreateLifecycle(
        authority_repository=authority,
        audit_repository=audit_repository,
        project_repository=project_repository,
        audit_adapter=SignedProjectAuditAdapter(
            repository=audit_repository,
            context_provider=None,
            signer=signer,
            clock=lambda: _NOW,
        ),
        anchor=anchor,
        mutation_planner=FixedManifestPlanner(),
        signer=signer,
        clock=lambda: _NOW,
    )


def test_project_create_recovers_after_project_commit_before_authority_commit(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    authority_repository = AuthorityRepository(database)
    audit_repository = AuditRepository(database)
    project_repository = ProjectRepository(database)
    project = Project(
        workspace_id=uuid4(),
        name="Recoverable Corvus",
        root_locator="workspace://recoverable-corvus",
        privacy="private",
    )
    authority = _authority(authority_repository, project.workspace_id)
    request_id = uuid4()
    requester_id = uuid4()
    signing_key_id = uuid4()
    private_key = Ed25519PrivateKey.generate()
    signer = Ed25519Signer(signing_key_id, private_key)
    snapshot = _snapshot(
        request_id=request_id,
        project=project,
        requester_id=requester_id,
        signing_key_id=signing_key_id,
        private_key=private_key,
        authority=authority,
    )
    audit_repository.append_snapshot(snapshot)
    command = CreateProjectCommand(
        request_id=request_id,
        workspace_id=project.workspace_id,
        requester_id=requester_id,
        acting_agent_id=uuid4(),
        project=project,
    )
    anchor = IdempotentAnchor()
    fail_once = FailDbCommitOnce(authority_repository)
    failing_lifecycle = _lifecycle(
        authority=fail_once,
        audit_repository=audit_repository,
        project_repository=project_repository,
        anchor=anchor,
        signer=signer,
    )
    failing_service = ProjectService(
        store=ProjectRepositoryAdapter(project_repository),
        authorization=FixedAuthorization(snapshot),
        audit=failing_lifecycle.audit_adapter,
        create_lifecycle=failing_lifecycle,
    )

    failed = failing_service.create(command)

    assert failed.ok is False
    assert failed.reason_code == "authority_commit_failed"

    assert (
        project_repository.get(workspace_id=project.workspace_id, project_id=project.id) == project
    )
    assert len(audit_repository.list_receipts(project.workspace_id)) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state FROM authority_commit_intents WHERE workspace_id = ?",
            (str(project.workspace_id),),
        ).fetchone() == (AuthorityCommitState.ANCHOR_RESERVED.value,)
        assert connection.execute(
            "SELECT state FROM audit_anchor_recovery_checkpoints WHERE workspace_id = ?",
            (str(project.workspace_id),),
        ).fetchone() == ("prepared",)

    lifecycle = _lifecycle(
        authority=authority_repository,
        audit_repository=audit_repository,
        project_repository=project_repository,
        anchor=anchor,
        signer=signer,
    )
    service = ProjectService(
        store=ProjectRepositoryAdapter(project_repository),
        authorization=FixedAuthorization(snapshot),
        audit=lifecycle.audit_adapter,
        create_lifecycle=lifecycle,
    )
    recovered = service.create(command)
    replayed = service.create(command)

    assert recovered.ok is True
    assert replayed.ok is True

    advanced = authority_repository.get_workspace_authority(project.workspace_id)
    assert advanced is not None
    assert advanced.authority_generation == authority.authority_generation + 1
    assert len(audit_repository.list_receipts(project.workspace_id)) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state FROM authority_commit_intents WHERE workspace_id = ?",
            (str(project.workspace_id),),
        ).fetchone() == (AuthorityCommitState.ANCHOR_FINALIZED.value,)
        assert connection.execute(
            "SELECT state FROM audit_anchor_recovery_checkpoints WHERE workspace_id = ?",
            (str(project.workspace_id),),
        ).fetchone() == ("complete",)
        binding_row = connection.execute(
            "SELECT payload_json FROM audit_result_bindings"
        ).fetchone()
        assert binding_row is not None
        binding = AuditResultBinding.model_validate_json(binding_row[0])
        assert connection.execute("SELECT COUNT(*) FROM audit_result_bindings").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone() == (1,)
    assert binding.binding_hash == audit_result_binding_hash(binding)
    private_key.public_key().verify(
        base64.b64decode(binding.binding_signature),
        bytes.fromhex(binding.binding_hash),
    )
    assert len(anchor.reserved) == 1
    assert len(anchor.finalized) == 1
