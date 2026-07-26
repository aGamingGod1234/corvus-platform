from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from corvus.application.ports import (
    AgentRunExecutionPersistenceError,
    AgentRunOperation,
)
from corvus.domain.agent_runtime import (
    AgentRunHandle,
    AgentRunRequest,
    AgentRunState,
    compute_agent_run_request_digest,
)
from corvus.domain.conversations import (
    AgentRunRecord,
    Message,
    MessageAuthorKind,
    Thread,
    ThreadStatus,
    compute_content_digest,
)
from corvus.domain.execution import (
    AgentRunExecutionBinding,
    ExecutionRun,
    ExecutionRunState,
    compute_agent_run_execution_binding_digest,
    compute_execution_run_digest,
)
from corvus.domain.identity import Principal, PrincipalKind, Workspace, WorkspaceMembership
from corvus.domain.request import RequestContext
from corvus.infrastructure.agent_run_execution import (
    RepositoryAgentRunExecutionPersistence,
)
from corvus.infrastructure.db import M1_CURRENT_REVISION, upgrade_database
from corvus.infrastructure.repositories.conversations import ConversationRepository
from corvus.infrastructure.repositories.execution import ExecutionRepository
from corvus.infrastructure.repositories.identity_scope import IdentityScopeRepository
from corvus.store import TraceStore

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
OBSERVED = datetime(2026, 7, 26, 20, 5, tzinfo=timezone(timedelta(hours=8)))


class _SynchronizedExecutionRepository(ExecutionRepository):
    def __init__(
        self,
        delegate: ExecutionRepository,
        barrier: Barrier,
    ) -> None:
        self._delegate = delegate
        self._barrier = barrier

    def get_latest_run_state(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> ExecutionRun | None:
        current = self._delegate.get_latest_run_state(workspace_id, run_id)
        self._barrier.wait(timeout=5)
        return current

    def get_run_binding(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> AgentRunExecutionBinding | None:
        return self._delegate.get_run_binding(workspace_id, run_id)

    def append_run_state(
        self,
        run: ExecutionRun,
        *,
        expected_prior_version: int,
    ) -> ExecutionRun:
        return self._delegate.append_run_state(
            run,
            expected_prior_version=expected_prior_version,
        )


def _pending_execution(request: AgentRunRequest) -> ExecutionRun:
    payload: dict[str, object] = {
        "id": request.run_id,
        "workspace_id": request.workspace_id,
        "state": ExecutionRunState.PENDING,
        "version": 1,
        "created_at": NOW,
        "updated_at": OBSERVED.astimezone(UTC),
    }
    return ExecutionRun(
        id=request.run_id,
        workspace_id=request.workspace_id,
        state=ExecutionRunState.PENDING,
        version=1,
        created_at=NOW,
        updated_at=OBSERVED.astimezone(UTC),
        canonical_digest=compute_execution_run_digest(payload),
    )


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    assert upgrade_database(database) == M1_CURRENT_REVISION
    return database


def _identity(database: Path) -> tuple[Workspace, Principal]:
    workspace = Workspace(name="Runtime persistence", created_at=NOW, updated_at=NOW)
    principal = Principal(
        kind=PrincipalKind.USER,
        external_provider="test",
        external_subject="runtime-persistence",
        display_name="Runtime persistence user",
        created_at=NOW,
    )
    repository = IdentityScopeRepository(database)
    repository.append_workspace(workspace)
    repository.append_principal(principal)
    repository.append_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            principal_id=principal.id,
            role="owner",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repository.close()
    return workspace, principal


def _request(
    workspace_id: UUID,
    *,
    run_id: UUID,
    provider_binding_id: UUID,
    provider_binding_digest: str,
) -> AgentRunRequest:
    return AgentRunRequest(
        run_id=run_id,
        workspace_id=workspace_id,
        provider_binding_id=provider_binding_id,
        provider_binding_version=1,
        provider_binding_digest=provider_binding_digest,
        model="gpt-5.6-sol",
        effort="high",
        prompt="Persist this run.",
        authorization_proof_id=uuid4(),
        authorization_proof_digest="1" * 64,
        autonomy_grant_id=uuid4(),
        autonomy_grant_digest="2" * 64,
        credential_grant_ids=(),
        credential_proof_id=uuid4(),
        credential_proof_digest="3" * 64,
        budget_proof_id=uuid4(),
        budget_proof_digest="4" * 64,
        kill_switch_proof_id=uuid4(),
        kill_switch_proof_digest="5" * 64,
        sandbox_profile="workspace-write",
        filesystem_envelope=("repository.read",),
        network_envelope=(),
        tool_envelope=(),
        requested_effect_classes=frozenset(),
        provider_spend_limit=Decimal(0),
        corvus_budget_limit=Decimal(0),
        budget_unit="usd_micros",
        budget_requested_amount=1,
        approval_limit=0,
        max_retries=0,
        max_turns=1,
        deadline=NOW + timedelta(hours=1),
        max_output_tokens=4000,
        max_output_bytes=100_000,
        idempotency_key="runtime-persistence:run",
    )


def _context(request: AgentRunRequest, principal_id: UUID) -> RequestContext:
    return RequestContext(
        deployment_profile_id=uuid4(),
        deployment_instance_id=uuid4(),
        workspace_id=request.workspace_id,
        workspace_authority_epoch=1,
        workspace_authority_generation=0,
        authority_state_root="a" * 64,
        authority_epoch_credential_id=uuid4(),
        authority_commit_receipt_id=uuid4(),
        authority_proof_digest="b" * 64,
        scope_kind="workspace",
        scope_id=request.workspace_id,
        scope_digest="c" * 64,
        audience_policy_snapshot_id=uuid4(),
        audience_policy_digest="d" * 64,
        requester_id=principal_id,
        client_context_id=uuid4(),
        transport_principal_id=uuid4(),
        agent_id=uuid4(),
        agent_grant_id=uuid4(),
        access_bundle_id=uuid4(),
        policy_digest="e" * 64,
        authorization_snapshot_id=request.authorization_proof_id,
        authorization_snapshot_digest=request.authorization_proof_digest,
        authorization_signing_key_version_id=uuid4(),
        idempotency_key=request.idempotency_key,
        correlation_id=uuid4(),
    )


def _create_parent_run(
    repository: ConversationRepository,
    workspace: Workspace,
    principal: Principal,
    request: AgentRunRequest,
) -> AgentRunRecord:
    thread = repository.create_thread(
        Thread(
            workspace_id=workspace.id,
            workspace_version=workspace.version,
            creator_principal_id=principal.id,
            creator_membership_version=1,
            title="Runtime persistence",
            status=ThreadStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    message = repository.append_message(
        Message(
            workspace_id=workspace.id,
            thread_id=thread.id,
            sequence=1,
            content="persist",
            content_digest=compute_content_digest("persist"),
            idempotency_key="runtime-persistence:message",
            author_kind=MessageAuthorKind.PRINCIPAL,
            author_principal_id=principal.id,
            author_membership_version=1,
            created_at=NOW,
        ),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    return repository.create_run(
        AgentRunRecord(
            id=request.run_id,
            workspace_id=workspace.id,
            thread_id=thread.id,
            message_sequence=message.sequence,
            requester_principal_id=principal.id,
            requester_membership_version=1,
            authorization_snapshot_id=request.authorization_proof_id,
            authorization_snapshot_digest=request.authorization_proof_digest,
            provider_binding_id=request.provider_binding_id,
            provider_binding_version=request.provider_binding_version,
            provider_binding_digest=request.provider_binding_digest,
            canonical_request_digest=compute_agent_run_request_digest(request),
            idempotency_key=request.idempotency_key,
            created_at=NOW,
        )
    )


def test_start_intent_persists_bound_pending_run_and_survives_reopen(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )

    pending = persistence.ensure_start_intent(
        context,
        request,
        observed_at=OBSERVED,
    )

    assert pending.state is ExecutionRunState.PENDING
    assert pending.version == 1
    assert pending.created_at == NOW
    assert pending.updated_at == OBSERVED.astimezone(UTC)
    assert pending.updated_at.utcoffset() == timedelta(0)
    assert executions.get_latest_run_state(workspace.id, request.run_id) == pending
    durable_binding = executions.get_run_binding(workspace.id, request.run_id)
    assert durable_binding is not None
    assert durable_binding.immutable_request_digest == request.immutable_request_digest
    assert durable_binding.created_at == NOW
    executions.close()
    conversations.close()

    reopened = ExecutionRepository(database)
    assert reopened.get_latest_run_state(workspace.id, request.run_id) == pending
    assert reopened.get_run_binding(workspace.id, request.run_id) == durable_binding
    reopened.close()


def test_start_intent_rejects_parent_binding_substitution(tmp_path: Path) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    refreshed_authorization = request.model_copy(
        update={
            "authorization_proof_id": uuid4(),
            "authorization_proof_digest": "6" * 64,
        }
    )
    refreshed_idempotency = request.model_copy(
        update={"idempotency_key": "runtime-persistence:substitute"}
    )
    substitutions = (
        (
            request.model_copy(update={"run_id": uuid4()}),
            context,
        ),
        (
            request.model_copy(
                update={
                    "provider_binding_version": 2,
                    "provider_binding_digest": "7" * 64,
                }
            ),
            context,
        ),
        (
            request.model_copy(update={"prompt": "Substituted prompt."}),
            context,
        ),
        (
            refreshed_authorization,
            _context(refreshed_authorization, principal.id),
        ),
        (
            refreshed_idempotency,
            _context(refreshed_idempotency, principal.id),
        ),
        (
            request,
            context.model_copy(update={"requester_id": uuid4()}),
        ),
    )

    for substituted_request, substituted_context in substitutions:
        with pytest.raises(
            AgentRunExecutionPersistenceError,
            match="agent_run_persistence_binding_mismatch",
        ):
            persistence.ensure_start_intent(
                substituted_context,
                substituted_request,
                observed_at=OBSERVED,
            )

    assert executions.get_latest_run_state(workspace.id, request.run_id) is None
    executions.close()
    conversations.close()


def test_observed_handle_state_appends_once_and_same_state_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    pending = persistence.ensure_start_intent(
        context,
        request,
        observed_at=OBSERVED,
    )
    handle = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )

    running = persistence.record_handle_state(
        context,
        AgentRunOperation.START,
        request,
        handle,
        observed_at=OBSERVED + timedelta(minutes=1),
    )
    replay = persistence.record_handle_state(
        context,
        AgentRunOperation.START,
        request,
        handle,
        observed_at=OBSERVED + timedelta(minutes=2),
    )

    assert running.state is ExecutionRunState.RUNNING
    assert running.version == 2
    assert replay == running
    assert executions.list_run_states(workspace.id, request.run_id) == (
        pending,
        running,
    )
    executions.close()
    conversations.close()


def test_observed_state_accepts_refreshed_proof_but_rejects_common_substitution(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    persistence.ensure_start_intent(context, request, observed_at=OBSERVED)
    running = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )
    changed_idempotency = request.model_copy(
        update={"idempotency_key": "runtime-persistence:substitute"}
    )
    substitutions = (
        (
            request.model_copy(update={"prompt": "Substituted immutable request."}),
            context,
        ),
        (
            request.model_copy(
                update={
                    "provider_binding_version": 2,
                    "provider_binding_digest": "7" * 64,
                }
            ),
            context,
        ),
        (
            changed_idempotency,
            _context(changed_idempotency, principal.id),
        ),
        (
            request,
            context.model_copy(update={"requester_id": uuid4()}),
        ),
        (
            request,
            context.model_copy(
                update={
                    "authorization_snapshot_id": uuid4(),
                    "authorization_snapshot_digest": "8" * 64,
                }
            ),
        ),
        (
            request,
            context.model_copy(update={"workspace_id": uuid4()}),
        ),
    )

    for substituted_request, substituted_context in substitutions:
        with pytest.raises(
            AgentRunExecutionPersistenceError,
            match="agent_run_persistence_binding_mismatch",
        ):
            persistence.record_handle_state(
                substituted_context,
                AgentRunOperation.RESUME,
                substituted_request,
                running,
                observed_at=OBSERVED + timedelta(minutes=1),
            )

    refreshed = request.model_copy(
        update={
            "authorization_proof_id": uuid4(),
            "authorization_proof_digest": "9" * 64,
            "resume_handle_id": running.id,
        }
    )
    persisted = persistence.record_handle_state(
        _context(refreshed, principal.id),
        AgentRunOperation.RESUME,
        refreshed,
        running,
        observed_at=OBSERVED + timedelta(minutes=1),
    )

    assert persisted.state is ExecutionRunState.RUNNING
    assert persisted.version == 2
    executions.close()
    conversations.close()


def test_start_replay_bootstraps_legacy_binding_without_rewriting_history(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    pending = _pending_execution(request)
    executions.record_run_state(pending)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )

    replay = persistence.ensure_start_intent(
        context,
        request,
        observed_at=OBSERVED + timedelta(minutes=1),
    )

    assert replay == pending
    durable_binding = executions.get_run_binding(workspace.id, request.run_id)
    assert durable_binding is not None
    assert durable_binding.immutable_request_digest == request.immutable_request_digest
    assert executions.list_run_states(workspace.id, request.run_id) == (pending,)
    executions.close()
    conversations.close()


def test_observed_state_fails_closed_when_durable_binding_is_missing(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    pending = _pending_execution(request)
    executions.record_run_state(pending)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    running = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_binding_mismatch",
    ):
        persistence.record_handle_state(
            context,
            AgentRunOperation.RESUME,
            request,
            running,
            observed_at=OBSERVED + timedelta(minutes=1),
        )

    assert executions.list_run_states(workspace.id, request.run_id) == (pending,)
    executions.close()
    conversations.close()


def test_binding_without_initial_state_maps_to_stable_state_conflict(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    binding_payload: dict[str, object] = {
        "workspace_id": workspace.id,
        "run_id": request.run_id,
        "immutable_request_digest": request.immutable_request_digest,
        "created_at": NOW,
    }
    binding = AgentRunExecutionBinding(
        workspace_id=workspace.id,
        run_id=request.run_id,
        immutable_request_digest=request.immutable_request_digest,
        created_at=NOW,
        canonical_digest=compute_agent_run_execution_binding_digest(binding_payload),
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO agent_run_execution_bindings "
            "(workspace_id, run_id, immutable_request_digest, created_at, "
            "canonical_digest) VALUES (?, ?, ?, ?, ?)",
            (
                str(binding.workspace_id),
                str(binding.run_id),
                binding.immutable_request_digest,
                binding.created_at.isoformat(),
                binding.canonical_digest,
            ),
        )
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_state_conflict",
    ):
        persistence.ensure_start_intent(
            context,
            request,
            observed_at=OBSERVED,
        )

    assert executions.get_latest_run_state(workspace.id, request.run_id) is None
    executions.close()
    conversations.close()


def test_persistence_rejects_naive_observation_before_idempotent_replay(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    persistence.ensure_start_intent(context, request, observed_at=OBSERVED)

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_timestamp_invalid",
    ):
        persistence.ensure_start_intent(
            context,
            request,
            observed_at=datetime(2026, 7, 26, 12, 6),
        )
    handle = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )
    persistence.record_handle_state(
        context,
        AgentRunOperation.START,
        request,
        handle,
        observed_at=OBSERVED + timedelta(minutes=1),
    )
    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_timestamp_invalid",
    ):
        persistence.record_handle_state(
            context,
            AgentRunOperation.START,
            request,
            handle,
            observed_at=datetime(2026, 7, 26, 12, 7),
        )

    executions.close()
    conversations.close()


def test_observed_state_rejects_timestamp_before_latest_version(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    persistence.ensure_start_intent(context, request, observed_at=OBSERVED)
    running = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_timestamp_invalid",
    ):
        persistence.record_handle_state(
            context,
            AgentRunOperation.START,
            request,
            running,
            observed_at=OBSERVED - timedelta(minutes=1),
        )

    assert executions.list_run_states(workspace.id, request.run_id)[-1].state is (
        ExecutionRunState.PENDING
    )
    executions.close()
    conversations.close()


def test_terminal_state_rejects_regression_and_conflicting_terminal_observation(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    persistence.ensure_start_intent(context, request, observed_at=OBSERVED)
    completed = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.COMPLETED,
    )
    persistence.record_handle_state(
        context,
        AgentRunOperation.START,
        request,
        completed,
        observed_at=OBSERVED + timedelta(minutes=1),
    )
    refreshed = request.model_copy(
        update={
            "authorization_proof_id": uuid4(),
            "authorization_proof_digest": "6" * 64,
            "resume_handle_id": completed.id,
        }
    )
    refreshed_context = _context(refreshed, principal.id)

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_terminal_regression",
    ):
        persistence.record_handle_state(
            refreshed_context,
            AgentRunOperation.RESUME,
            refreshed,
            completed.model_copy(update={"state": AgentRunState.RUNNING}),
            observed_at=OBSERVED + timedelta(minutes=2),
        )
    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_terminal_conflict",
    ):
        persistence.record_handle_state(
            context,
            AgentRunOperation.CANCEL,
            request,
            completed.model_copy(update={"state": AgentRunState.FAILED}),
            observed_at=OBSERVED + timedelta(minutes=2),
        )

    assert executions.list_run_states(workspace.id, request.run_id)[-1].state is (
        ExecutionRunState.COMPLETED
    )
    executions.close()
    conversations.close()


def test_cancel_operation_rejects_nonterminal_observation(tmp_path: Path) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    persistence = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    )
    persistence.ensure_start_intent(context, request, observed_at=OBSERVED)
    running = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )

    with pytest.raises(
        AgentRunExecutionPersistenceError,
        match="agent_run_persistence_state_conflict",
    ):
        persistence.record_handle_state(
            context,
            AgentRunOperation.CANCEL,
            request,
            running,
            observed_at=OBSERVED + timedelta(minutes=1),
        )

    assert executions.list_run_states(workspace.id, request.run_id)[-1].state is (
        ExecutionRunState.PENDING
    )
    executions.close()
    conversations.close()


def test_concurrent_conflicting_state_observations_return_stable_cas_conflict(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database)
    request = _request(
        workspace.id,
        run_id=uuid4(),
        provider_binding_id=uuid4(),
        provider_binding_digest="f" * 64,
    )
    context = _context(request, principal.id)
    conversations = ConversationRepository(database)
    _create_parent_run(conversations, workspace, principal, request)
    executions = ExecutionRepository(database)
    RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=executions,
    ).ensure_start_intent(context, request, observed_at=OBSERVED)
    barrier = Barrier(2)
    first = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=_SynchronizedExecutionRepository(executions, barrier),
    )
    second = RepositoryAgentRunExecutionPersistence(
        conversations=conversations,
        executions=_SynchronizedExecutionRepository(executions, barrier),
    )
    running = AgentRunHandle(
        run_id=request.run_id,
        provider_binding_id=request.provider_binding_id,
        created_at=OBSERVED,
        state=AgentRunState.RUNNING,
    )
    completed = running.model_copy(update={"state": AgentRunState.COMPLETED})

    def record(
        persistence: RepositoryAgentRunExecutionPersistence,
        handle: AgentRunHandle,
    ) -> tuple[str, str]:
        try:
            persisted = persistence.record_handle_state(
                context,
                AgentRunOperation.START,
                request,
                handle,
                observed_at=OBSERVED + timedelta(minutes=1),
            )
        except AgentRunExecutionPersistenceError as exc:
            return ("error", exc.reason_code)
        return ("ok", persisted.state.value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            future.result(timeout=10)
            for future in (
                pool.submit(record, first, running),
                pool.submit(record, second, completed),
            )
        )

    assert sum(result[0] == "ok" for result in results) == 1
    assert ("error", "agent_run_persistence_state_conflict") in results
    assert len(executions.list_run_states(workspace.id, request.run_id)) == 2
    executions.close()
    conversations.close()
