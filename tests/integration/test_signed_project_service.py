from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from corvus.application.ports import (
    ProjectAuthorizationDecision,
    ProjectAuthorizationRequest,
)
from corvus.application.projects import (
    CreateProjectCommand,
    ProjectRepositoryAdapter,
    ProjectService,
)
from corvus.domain.audit import AuthorizationDecisionSnapshot, authorization_snapshot_digest
from corvus.domain.identity import Project
from corvus.infrastructure.db import upgrade_database
from corvus.infrastructure.project_audit import (
    ProjectAuditReceiptContext,
    SignedProjectAuditAdapter,
    audit_receipt_hash,
)
from corvus.infrastructure.repositories.audit import AuditRepository, AuditRepositoryError
from corvus.infrastructure.repositories.projects import ProjectRepository
from corvus.store import TraceStore

_NOW = datetime(2026, 7, 14, 18, 0, tzinfo=UTC)


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    upgrade_database(database)
    return database


def _snapshot(
    *,
    request_id: UUID,
    project: Project,
    requester_id: UUID,
    signing_key_id: UUID,
    private_key: Ed25519PrivateKey,
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
        deployment_instance_id=uuid4(),
        authority_epoch_credential_id=uuid4(),
        authority_generation=4,
        authority_state_root="a" * 64,
        authority_commit_receipt_id=uuid4(),
        authority_proof_digest="b" * 64,
        membership_version_ids=(uuid4(),),
        membership_digest="c" * 64,
        scope_kind="project",
        scope_id=project.id,
        scope_digest="d" * 64,
        audience_policy_snapshot_id=uuid4(),
        audience_digest="e" * 64,
        requester_id=requester_id,
        transport_principal_id=uuid4(),
        access_bundle_id=uuid4(),
        access_bundle_version_digest="f" * 64,
        agent_grant_id=uuid4(),
        agent_delegation_digest="0" * 64,
        policy_digest="1" * 64,
        autonomy_policy_digest="2" * 64,
        budget_snapshot_ids=(uuid4(),),
        budget_snapshot_digest="3" * 64,
        kill_switch_snapshot_ids=(uuid4(),),
        kill_switch_snapshot_digest="4" * 64,
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


class FixedContextProvider:
    def __init__(self, context: ProjectAuditReceiptContext) -> None:
        self.context = context

    def resolve(self, request_id: UUID) -> ProjectAuditReceiptContext:
        assert request_id == self.context.request_context_id
        return self.context


class Ed25519TestSigner:
    def __init__(self, signing_key_version_id: UUID, private_key: Ed25519PrivateKey) -> None:
        self.signing_key_version_id = signing_key_version_id
        self.private_key = private_key

    def sign(self, data: bytes) -> bytes:
        return self.private_key.sign(data)


def _service_fixture(tmp_path: Path):
    database = _database(tmp_path)
    project_repository = ProjectRepository(database)
    audit_repository = AuditRepository(database)
    private_key = Ed25519PrivateKey.generate()
    signing_key_id = uuid4()
    requester_id = uuid4()
    acting_agent_id = uuid4()
    project = Project(
        workspace_id=uuid4(),
        name="Signed Corvus",
        root_locator="workspace://signed-corvus",
        privacy="private",
    )
    request_id = uuid4()
    snapshot = _snapshot(
        request_id=request_id,
        project=project,
        requester_id=requester_id,
        signing_key_id=signing_key_id,
        private_key=private_key,
    )
    audit_repository.append_snapshot(snapshot)
    context = ProjectAuditReceiptContext(
        request_context_id=request_id,
        prior_authority_epoch=1,
        prior_authority_generation=snapshot.authority_generation,
        prior_authority_state_root=snapshot.authority_state_root,
        prior_authority_commit_receipt_id=snapshot.authority_commit_receipt_id,
        authority_commit_intent_id=uuid4(),
        intended_mutation_digest="5" * 64,
        signing_key_version_id=signing_key_id,
    )
    audit = SignedProjectAuditAdapter(
        repository=audit_repository,
        context_provider=FixedContextProvider(context),
        signer=Ed25519TestSigner(signing_key_id, private_key),
        clock=lambda: _NOW,
    )
    service = ProjectService(
        store=ProjectRepositoryAdapter(project_repository),
        authorization=FixedAuthorization(snapshot),
        audit=audit,
    )
    command = CreateProjectCommand(
        request_id=request_id,
        workspace_id=project.workspace_id,
        requester_id=requester_id,
        acting_agent_id=acting_agent_id,
        project=project,
    )
    return (
        service,
        command,
        project_repository,
        audit_repository,
        private_key,
        snapshot,
    )


def test_real_project_create_persists_a_verifiable_signed_receipt(tmp_path: Path) -> None:
    service, command, projects, audit, private_key, snapshot = _service_fixture(tmp_path)

    response = service.create(command)

    assert response.ok is True
    assert (
        projects.get(workspace_id=command.workspace_id, project_id=command.project.id)
        == command.project
    )
    receipts = audit.list_receipts(command.workspace_id)
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.authorization_snapshot_id == snapshot.id
    assert receipt.receipt_hash == audit_receipt_hash(receipt)
    private_key.public_key().verify(
        base64.b64decode(receipt.receipt_signature),
        bytes.fromhex(receipt.receipt_hash),
    )


def test_real_audit_write_failure_prevents_project_mutation(tmp_path: Path) -> None:
    service, command, projects, audit, _, _ = _service_fixture(tmp_path)

    def fail_append(_receipt) -> None:
        raise AuditRepositoryError("injected_audit_failure")

    audit.append_receipt = fail_append  # type: ignore[method-assign]

    response = service.create(command)

    assert response.ok is False
    assert response.reason_code == "audit_persistence_failed"
    assert projects.get(workspace_id=command.workspace_id, project_id=command.project.id) is None
    assert audit.list_receipts(command.workspace_id) == []
