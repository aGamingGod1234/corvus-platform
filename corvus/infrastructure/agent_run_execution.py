from __future__ import annotations

from datetime import UTC, datetime

from corvus.application.ports import (
    AgentRunExecutionPersistenceError,
    AgentRunOperation,
)
from corvus.domain.agent_runtime import (
    AgentRunHandle,
    AgentRunRequest,
    compute_agent_run_request_digest,
)
from corvus.domain.conversations import AgentRunRecord
from corvus.domain.execution import (
    AgentRunExecutionBinding,
    ExecutionRun,
    ExecutionRunState,
    compute_agent_run_execution_binding_digest,
    compute_execution_run_digest,
)
from corvus.domain.request import RequestContext
from corvus.infrastructure.repositories.conversations import (
    ConversationRepository,
    ConversationRepositoryError,
)
from corvus.infrastructure.repositories.execution import (
    ExecutionRepository,
    ExecutionRepositoryError,
)

_PERSISTENCE_BINDING_MISMATCH = "agent_run_persistence_binding_mismatch"
_PERSISTENCE_STATE_CONFLICT = "agent_run_persistence_state_conflict"
_PERSISTENCE_TERMINAL_CONFLICT = "agent_run_persistence_terminal_conflict"
_PERSISTENCE_TERMINAL_REGRESSION = "agent_run_persistence_terminal_regression"
_PERSISTENCE_TIMESTAMP_INVALID = "agent_run_persistence_timestamp_invalid"
_PERSISTENCE_UNAVAILABLE = "agent_run_persistence_unavailable"
_CAS_CONFLICT_REASONS = frozenset(
    {
        "execution_idempotency_payload_mismatch",
        "execution_run_binding_state_missing",
        "execution_run_version_conflict",
    }
)
_TERMINAL_STATES = frozenset(
    {
        ExecutionRunState.COMPLETED,
        ExecutionRunState.FAILED,
        ExecutionRunState.CANCELLED,
    }
)


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AgentRunExecutionPersistenceError(_PERSISTENCE_TIMESTAMP_INVALID)
    return value.astimezone(UTC)


def _current_binding_matches(
    context: RequestContext,
    request: AgentRunRequest,
) -> bool:
    return (
        context.workspace_id == request.workspace_id
        and context.idempotency_key == request.idempotency_key
        and context.authorization_snapshot_id == request.authorization_proof_id
        and context.authorization_snapshot_digest == request.authorization_proof_digest
    )


def _start_parent_matches(
    parent: AgentRunRecord,
    context: RequestContext,
    request: AgentRunRequest,
) -> bool:
    return (
        parent.id == request.run_id
        and parent.workspace_id == request.workspace_id
        and parent.requester_principal_id == context.requester_id
        and parent.authorization_snapshot_id == context.authorization_snapshot_id
        and parent.authorization_snapshot_digest == context.authorization_snapshot_digest
        and parent.provider_binding_id == request.provider_binding_id
        and parent.provider_binding_version == request.provider_binding_version
        and parent.provider_binding_digest == request.provider_binding_digest
        and parent.canonical_request_digest == compute_agent_run_request_digest(request)
        and parent.idempotency_key == request.idempotency_key
    )


def _common_parent_matches(
    parent: AgentRunRecord,
    context: RequestContext,
    request: AgentRunRequest,
) -> bool:
    return (
        parent.id == request.run_id
        and parent.workspace_id == request.workspace_id
        and parent.requester_principal_id == context.requester_id
        and parent.provider_binding_id == request.provider_binding_id
        and parent.provider_binding_version == request.provider_binding_version
        and parent.provider_binding_digest == request.provider_binding_digest
        and parent.idempotency_key == request.idempotency_key
    )


class RepositoryAgentRunExecutionPersistence:
    """Persist runtime observations without weakening their parent-run proof.

    START must reproduce the complete immutable request binding recorded by the
    conversation repository. Later operations may carry refreshed authorization
    proofs, so they revalidate the current request/context pair while preserving
    the immutable requester, provider, workspace, run, and idempotency bindings.
    """

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        executions: ExecutionRepository,
    ) -> None:
        self._conversations = conversations
        self._executions = executions

    def ensure_start_intent(
        self,
        context: RequestContext,
        request: AgentRunRequest,
        *,
        observed_at: datetime,
    ) -> ExecutionRun:
        try:
            return self._ensure_start_intent(
                context,
                request,
                observed_at=observed_at,
            )
        except AgentRunExecutionPersistenceError:
            raise
        except ExecutionRepositoryError as exc:
            reason_code = (
                _PERSISTENCE_STATE_CONFLICT
                if exc.reason_code in _CAS_CONFLICT_REASONS
                else _PERSISTENCE_UNAVAILABLE
            )
            raise AgentRunExecutionPersistenceError(reason_code) from exc
        except ConversationRepositoryError as exc:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_UNAVAILABLE) from exc

    def _ensure_start_intent(
        self,
        context: RequestContext,
        request: AgentRunRequest,
        *,
        observed_at: datetime,
    ) -> ExecutionRun:
        updated_at = _utc_timestamp(observed_at)
        if not _current_binding_matches(context, request):
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_BINDING_MISMATCH)
        parent = self._conversations.get_run(
            request.workspace_id,
            request.run_id,
            context.requester_id,
        )
        if parent is None or not _start_parent_matches(parent, context, request):
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_BINDING_MISMATCH)
        created_at = _utc_timestamp(parent.created_at)
        if updated_at < created_at:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_TIMESTAMP_INVALID)
        states = self._executions.list_run_states(
            request.workspace_id,
            request.run_id,
        )
        initial_run = (
            states[0]
            if states
            else _pending_execution_run(
                request,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        binding_payload = {
            "workspace_id": request.workspace_id,
            "run_id": request.run_id,
            "immutable_request_digest": request.immutable_request_digest,
            "created_at": created_at,
        }
        binding = AgentRunExecutionBinding(
            workspace_id=request.workspace_id,
            run_id=request.run_id,
            immutable_request_digest=request.immutable_request_digest,
            created_at=created_at,
            canonical_digest=compute_agent_run_execution_binding_digest(binding_payload),
        )
        _, latest = self._executions.record_run_binding(binding, initial_run)
        return latest

    def record_handle_state(
        self,
        context: RequestContext,
        operation: AgentRunOperation,
        request: AgentRunRequest,
        handle: AgentRunHandle,
        *,
        observed_at: datetime,
    ) -> ExecutionRun:
        try:
            return self._record_handle_state(
                context,
                operation,
                request,
                handle,
                observed_at=observed_at,
            )
        except AgentRunExecutionPersistenceError:
            raise
        except ExecutionRepositoryError as exc:
            reason_code = (
                _PERSISTENCE_STATE_CONFLICT
                if exc.reason_code in _CAS_CONFLICT_REASONS
                else _PERSISTENCE_UNAVAILABLE
            )
            raise AgentRunExecutionPersistenceError(reason_code) from exc
        except ConversationRepositoryError as exc:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_UNAVAILABLE) from exc

    def _record_handle_state(
        self,
        context: RequestContext,
        operation: AgentRunOperation,
        request: AgentRunRequest,
        handle: AgentRunHandle,
        *,
        observed_at: datetime,
    ) -> ExecutionRun:
        updated_at = _utc_timestamp(observed_at)
        if (
            not _current_binding_matches(context, request)
            or handle.run_id != request.run_id
            or handle.provider_binding_id != request.provider_binding_id
        ):
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_BINDING_MISMATCH)
        parent = self._conversations.get_run(
            request.workspace_id,
            request.run_id,
            context.requester_id,
        )
        if parent is None or not _common_parent_matches(parent, context, request):
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_BINDING_MISMATCH)
        durable_binding = self._executions.get_run_binding(
            request.workspace_id,
            request.run_id,
        )
        if (
            durable_binding is None
            or durable_binding.workspace_id != request.workspace_id
            or durable_binding.run_id != request.run_id
            or durable_binding.immutable_request_digest != request.immutable_request_digest
            or durable_binding.created_at != _utc_timestamp(parent.created_at)
        ):
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_BINDING_MISMATCH)
        current = self._executions.get_latest_run_state(
            request.workspace_id,
            request.run_id,
        )
        if current is None:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_STATE_CONFLICT)
        target_state = ExecutionRunState(handle.state.value)
        if operation is AgentRunOperation.CANCEL and target_state not in _TERMINAL_STATES:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_STATE_CONFLICT)
        if current.state is target_state:
            return current
        if current.state in _TERMINAL_STATES:
            reason_code = (
                _PERSISTENCE_TERMINAL_CONFLICT
                if target_state in _TERMINAL_STATES
                else _PERSISTENCE_TERMINAL_REGRESSION
            )
            raise AgentRunExecutionPersistenceError(reason_code)
        if updated_at < current.updated_at:
            raise AgentRunExecutionPersistenceError(_PERSISTENCE_TIMESTAMP_INVALID)
        payload = {
            "id": current.id,
            "workspace_id": current.workspace_id,
            "state": target_state,
            "version": current.version + 1,
            "created_at": current.created_at,
            "updated_at": updated_at,
        }
        return self._executions.append_run_state(
            ExecutionRun(
                id=current.id,
                workspace_id=current.workspace_id,
                state=target_state,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=updated_at,
                canonical_digest=compute_execution_run_digest(payload),
            ),
            expected_prior_version=current.version,
        )


def _pending_execution_run(
    request: AgentRunRequest,
    *,
    created_at: datetime,
    updated_at: datetime,
) -> ExecutionRun:
    payload = {
        "id": request.run_id,
        "workspace_id": request.workspace_id,
        "state": ExecutionRunState.PENDING,
        "version": 1,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    return ExecutionRun(
        id=request.run_id,
        workspace_id=request.workspace_id,
        state=ExecutionRunState.PENDING,
        version=1,
        created_at=created_at,
        updated_at=updated_at,
        canonical_digest=compute_execution_run_digest(payload),
    )
