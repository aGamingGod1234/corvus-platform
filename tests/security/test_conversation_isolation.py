from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from corvus.application.conversations import (
    ConversationAuthorizationDecision,
    ConversationMutationReceipt,
    ConversationService,
)
from corvus.domain.agent_runtime import AgentRunEventType
from corvus.domain.client import ClientSurface
from corvus.domain.conversations import Thread, ThreadStatus
from corvus.domain.request import RequestContext
from corvus.infrastructure.repositories.conversations import (
    ConversationRepository,
    ConversationRepositoryError,
)
from tests.integration.test_conversation_repository import (
    _database,
    _event,
    _identity,
    _seed_run,
)

NOW = datetime(2026, 7, 17, 4, 5, 6, tzinfo=UTC)
WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")
PRINCIPAL_ID = UUID("20000000-0000-4000-8000-000000000001")


def _context(*, workspace_id: UUID = WORKSPACE_ID) -> RequestContext:
    return RequestContext(
        deployment_profile_id=uuid4(),
        deployment_instance_id=uuid4(),
        workspace_id=workspace_id,
        workspace_authority_epoch=1,
        workspace_authority_generation=7,
        authority_state_root="a" * 64,
        authority_epoch_credential_id=uuid4(),
        authority_commit_receipt_id=uuid4(),
        authority_proof_digest="b" * 64,
        scope_kind="thread",
        scope_id=uuid4(),
        scope_digest="c" * 64,
        audience_policy_snapshot_id=uuid4(),
        audience_policy_digest="d" * 64,
        requester_id=PRINCIPAL_ID,
        client_context_id=uuid4(),
        transport_principal_id=PRINCIPAL_ID,
        agent_id=uuid4(),
        agent_grant_id=uuid4(),
        access_bundle_id=uuid4(),
        policy_digest="e" * 64,
        authorization_snapshot_id=uuid4(),
        authorization_snapshot_digest="f" * 64,
        authorization_signing_key_version_id=uuid4(),
        idempotency_key="thread-create",
        correlation_id=uuid4(),
    )


def _thread(context: RequestContext) -> Thread:
    return Thread(
        id=context.scope_id,
        workspace_id=context.workspace_id,
        workspace_version=1,
        creator_principal_id=context.requester_id,
        creator_membership_version=1,
        title="Security thread",
        status=ThreadStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        version=1,
    )


class _Authorization:
    def __init__(self, *, allowed: bool = True, snapshot_mismatch: bool = False) -> None:
        self.allowed = allowed
        self.snapshot_mismatch = snapshot_mismatch

    def authorize(self, request: object) -> ConversationAuthorizationDecision:
        context = request.context  # type: ignore[attr-defined]
        return ConversationAuthorizationDecision(
            allowed=self.allowed,
            reason_code="allowed" if self.allowed else "denied",
            authorization_snapshot_id=(
                uuid4() if self.snapshot_mismatch else context.authorization_snapshot_id
            ),
            authorization_snapshot_digest=context.authorization_snapshot_digest,
        )


class _Repository:
    def __init__(self, thread: Thread | None = None) -> None:
        self.thread = thread
        self.create_calls = 0

    def create_thread(self, thread: Thread) -> Thread:
        self.create_calls += 1
        self.thread = thread
        return thread

    def get_thread(self, workspace_id: UUID, thread_id: UUID, principal_id: UUID) -> Thread | None:
        if self.thread is None:
            return None
        if self.thread.workspace_id != workspace_id or self.thread.id != thread_id:
            return None
        return self.thread


class _Lifecycle:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: object, mutation: object) -> ConversationMutationReceipt:
        self.calls += 1
        result = mutation()  # type: ignore[operator]
        return ConversationMutationReceipt(
            prior_state_root=request.context.authority_state_root,  # type: ignore[attr-defined]
            proposed_state_root="1" * 64,
            audit_receipt_id=uuid4(),
            audit_receipt_digest="2" * 64,
            finalized_result_digest=request.payload_digest,  # type: ignore[attr-defined]
            result=result,
        )


def test_service_fails_closed_before_write_without_authority_lifecycle() -> None:
    context = _context()
    repository = _Repository()
    service = ConversationService(repository=repository, authorization=_Authorization())
    response = service.create_thread(context, ClientSurface.CLI, _thread(context))
    assert response.ok is False
    assert response.reason_code == "conversation_authority_lifecycle_unavailable"
    assert repository.create_calls == 0


def test_service_binds_authorization_snapshot_and_lifecycle_receipt() -> None:
    context = _context()
    repository = _Repository()
    lifecycle = _Lifecycle()
    service = ConversationService(
        repository=repository,
        authorization=_Authorization(),
        mutation_lifecycle=lifecycle,
    )
    response = service.create_thread(context, ClientSurface.DESKTOP, _thread(context))
    assert response.ok is True
    assert response.thread == _thread(context)
    assert lifecycle.calls == 1
    assert repository.create_calls == 1

    mismatched_repository = _Repository()
    mismatched = ConversationService(
        repository=mismatched_repository,
        authorization=_Authorization(snapshot_mismatch=True),
        mutation_lifecycle=_Lifecycle(),
    ).create_thread(context, ClientSurface.CLI, _thread(context))
    assert mismatched.ok is False
    assert mismatched.reason_code == "conversation_authorization_snapshot_mismatch"
    assert mismatched_repository.create_calls == 0


def test_reads_are_non_enumerating_across_denial_and_workspace_transplant() -> None:
    context = _context()
    thread = _thread(context)
    denied = ConversationService(
        repository=_Repository(thread),
        authorization=_Authorization(allowed=False),
    ).get_thread(context, ClientSurface.WEB, thread.id)
    assert denied.ok is False
    assert denied.reason_code == "conversation_not_found"

    other_context = _context(workspace_id=uuid4())
    transplanted = ConversationService(
        repository=_Repository(thread),
        authorization=_Authorization(),
    ).get_thread(other_context, ClientSurface.WEB, thread.id)
    assert transplanted.ok is False
    assert transplanted.reason_code == "conversation_not_found"


@pytest.mark.parametrize(
    ("statement", "value"),
    [
        (
            "UPDATE agent_run_events SET payload_json = ? "
            "WHERE workspace_id = ? AND run_id = ? AND sequence = 1",
            '{"event":"tampered"}',
        ),
        (
            "UPDATE agent_run_events SET previous_event_digest = ? "
            "WHERE workspace_id = ? AND run_id = ? AND sequence = 1",
            "9" * 64,
        ),
    ],
)
def test_persisted_event_payload_or_chain_tampering_fails_with_stable_integrity_error(
    tmp_path: Path,
    statement: str,
    value: str,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    repository = ConversationRepository(database)
    _, _, run, _ = _seed_run(repository, workspace, principal)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER agent_run_events_no_update")
        connection.execute(
            statement,
            (value, str(workspace.id), str(run.id)),
        )
    with pytest.raises(ConversationRepositoryError, match="run_event_integrity_invalid"):
        repository.page_events(
            workspace.id,
            run.id,
            principal.id,
            after_sequence=0,
            limit=10,
        )
    repository.close()


def test_changed_provider_replay_and_cursor_workspace_transplant_are_denied(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    other_workspace, other_principal = _identity(database, suffix="security-other")
    repository = ConversationRepository(database)
    thread, _, run, started = _seed_run(repository, workspace, principal)
    changed = _event(
        workspace,
        thread,
        run,
        event_type=AgentRunEventType.MESSAGE_DELTA,
        sequence=2,
        previous_digest=started.event.event_digest,
        provider_event_id="started",
    )
    with pytest.raises(
        ConversationRepositoryError,
        match="conversation_idempotency_payload_mismatch",
    ):
        repository.append_event(
            changed,
            requester_principal_id=principal.id,
            requester_membership_version=1,
        )
    with pytest.raises(ConversationRepositoryError, match="run_not_found"):
        repository.page_events(
            other_workspace.id,
            run.id,
            other_principal.id,
            after_sequence=0,
            limit=10,
        )
    repository.close()
