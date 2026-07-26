from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from corvus.domain.agent_runtime import (
    AgentRunEvent,
    AgentRunEventType,
    compute_agent_run_event_digest,
)
from corvus.domain.conversations import (
    AgentRunRecord,
    Message,
    MessageAuthorKind,
    RunArtifact,
    RunEventRecord,
    Thread,
    ThreadStatus,
    compute_content_digest,
    compute_lineage_digest,
)
from corvus.domain.execution import (
    ExecutionCheckpoint,
    ExecutionNextTransition,
    ExecutionRun,
    ExecutionRunState,
    ExecutionStep,
    ExecutionStepState,
    compute_execution_checkpoint_digest,
    compute_execution_run_digest,
    compute_execution_step_digest,
)
from corvus.domain.identity import Principal, PrincipalKind, Workspace, WorkspaceMembership
from corvus.infrastructure.db import M1_CURRENT_REVISION, upgrade_database
from corvus.infrastructure.repositories.conversations import ConversationRepository
from corvus.infrastructure.repositories.execution import (
    ExecutionRepository,
    ExecutionRepositoryError,
)
from corvus.infrastructure.repositories.identity_scope import IdentityScopeRepository
from corvus.store import TraceStore

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
ZERO = "0" * 64


def _test_token(label: str) -> str:
    return f"test-lease-{label}"


@dataclass(frozen=True)
class _CheckpointBinding:
    request_context_id: UUID
    authorization_snapshot_id: UUID
    lease_fence: int
    lease_token: str


def _record_bound_checkpoint(
    repository: ExecutionRepository,
    checkpoint: ExecutionCheckpoint,
    binding: _CheckpointBinding,
) -> ExecutionCheckpoint:
    return repository.record_checkpoint(
        checkpoint,
        request_context_id=binding.request_context_id,
        authorization_snapshot_id=binding.authorization_snapshot_id,
        lease_fence=binding.lease_fence,
        lease_token=binding.lease_token,
    )


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    assert upgrade_database(database) == M1_CURRENT_REVISION
    return database


def _identity(database: Path, *, suffix: str) -> tuple[Workspace, Principal]:
    workspace = Workspace(name=f"Workspace {suffix}", created_at=NOW, updated_at=NOW)
    principal = Principal(
        kind=PrincipalKind.USER,
        external_provider="test",
        external_subject=f"execution-{suffix}",
        display_name="Execution user",
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


def _seed_agent_run(
    database: Path,
    workspace: Workspace,
    principal: Principal,
) -> AgentRunRecord:
    repository = ConversationRepository(database)
    thread = repository.create_thread(
        Thread(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_version=workspace.version,
            project_id=None,
            creator_principal_id=principal.id,
            creator_membership_version=1,
            title="Execution repository",
            status=ThreadStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    message = repository.append_message(
        Message(
            id=uuid4(),
            workspace_id=workspace.id,
            thread_id=thread.id,
            sequence=1,
            content="execute",
            content_digest=compute_content_digest("execute"),
            idempotency_key="execution-message",
            producing_run_id=None,
            attachment_ids=(),
            author_kind=MessageAuthorKind.PRINCIPAL,
            author_principal_id=principal.id,
            author_membership_version=1,
            created_at=NOW,
        ),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    run = repository.create_run(
        AgentRunRecord(
            id=uuid4(),
            workspace_id=workspace.id,
            thread_id=thread.id,
            message_sequence=message.sequence,
            requester_principal_id=principal.id,
            requester_membership_version=1,
            authorization_snapshot_id=uuid4(),
            authorization_snapshot_digest="a" * 64,
            provider_binding_id=uuid4(),
            provider_binding_version=1,
            provider_binding_digest="b" * 64,
            canonical_request_digest="c" * 64,
            idempotency_key="execution-run",
            created_at=NOW,
        )
    )
    repository.close()
    return run


def _execution_run(workspace_id: UUID, run_id: UUID) -> ExecutionRun:
    payload: dict[str, object] = {
        "id": run_id,
        "workspace_id": workspace_id,
        "state": ExecutionRunState.PENDING,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return ExecutionRun(
        **{**payload, "canonical_digest": compute_execution_run_digest(payload)}  # type: ignore[arg-type]
    )


def _execution_step(workspace_id: UUID, run_id: UUID) -> ExecutionStep:
    payload: dict[str, object] = {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "run_id": run_id,
        "state": ExecutionStepState.READY,
        "fence": 1,
        "version": 1,
        "retry_count": 0,
        "attempt_count": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return ExecutionStep(
        **{**payload, "canonical_digest": compute_execution_step_digest(payload)}  # type: ignore[arg-type]
    )


def _checkpoint(
    run: ExecutionRun,
    step: ExecutionStep,
) -> ExecutionCheckpoint:
    payload: dict[str, object] = {
        "id": uuid4(),
        "workspace_id": run.workspace_id,
        "run_id": run.id,
        "step_id": step.id,
        "run_state": run.state,
        "step_state": step.state,
        "step_fence": step.fence,
        "step_version": step.version,
        "checkpoint_version": 1,
        "completed_dependency_step_ids": (),
        "output_ref_ids": (),
        "artifact_ref_ids": (),
        "retry_count": step.retry_count,
        "attempt_count": step.attempt_count,
        "last_accepted_event_sequence": 0,
        "last_accepted_event_digest": ZERO,
        "next_transition": ExecutionNextTransition.DISPATCH,
        "created_at": NOW,
    }
    return ExecutionCheckpoint(
        **{  # type: ignore[arg-type]
            **payload,
            "canonical_digest": compute_execution_checkpoint_digest(payload),
        }
    )


def _next_run_state(
    run: ExecutionRun,
    *,
    state: ExecutionRunState,
    version: int,
) -> ExecutionRun:
    payload = {
        **run.model_dump(mode="python", exclude={"canonical_digest"}),
        "state": state,
        "version": version,
        "updated_at": NOW + timedelta(minutes=version),
    }
    return ExecutionRun(
        **{**payload, "canonical_digest": compute_execution_run_digest(payload)}
    )


def _next_step_state(
    step: ExecutionStep,
    *,
    state: ExecutionStepState,
    version: int,
    fence: int,
) -> ExecutionStep:
    payload = {
        **step.model_dump(mode="python", exclude={"canonical_digest"}),
        "state": state,
        "version": version,
        "fence": fence,
        "updated_at": NOW + timedelta(minutes=version),
    }
    return ExecutionStep(
        **{**payload, "canonical_digest": compute_execution_step_digest(payload)}
    )


def _started_event(run: AgentRunRecord) -> RunEventRecord:
    payload = {"event": "started"}
    digest = compute_agent_run_event_digest(
        run_id=run.id,
        handle_id=run.id,
        sequence=1,
        timestamp=NOW,
        event_type=AgentRunEventType.STARTED,
        redacted_payload=payload,
        provider_event_id=f"started-{run.id}",
        previous_event_digest=ZERO,
        tool_call_id=None,
        effect_authorization_decision_id=None,
        effect_authorization_decision_digest=None,
    )
    return RunEventRecord(
        workspace_id=run.workspace_id,
        thread_id=run.thread_id,
        run_id=run.id,
        event=AgentRunEvent(
            run_id=run.id,
            handle_id=run.id,
            sequence=1,
            timestamp=NOW,
            event_type=AgentRunEventType.STARTED,
            redacted_payload=payload,
            provider_event_id=f"started-{run.id}",
            previous_event_digest=ZERO,
            event_digest=digest,
        ),
    )


def _next_event(
    run: AgentRunRecord,
    previous: RunEventRecord,
) -> RunEventRecord:
    payload = {"message": "working"}
    digest = compute_agent_run_event_digest(
        run_id=run.id,
        handle_id=run.id,
        sequence=2,
        timestamp=NOW + timedelta(seconds=1),
        event_type=AgentRunEventType.MESSAGE_DELTA,
        redacted_payload=payload,
        provider_event_id=f"message-{run.id}",
        previous_event_digest=previous.event.event_digest,
        tool_call_id=None,
        effect_authorization_decision_id=None,
        effect_authorization_decision_digest=None,
    )
    return RunEventRecord(
        workspace_id=run.workspace_id,
        thread_id=run.thread_id,
        run_id=run.id,
        event=AgentRunEvent(
            run_id=run.id,
            handle_id=run.id,
            sequence=2,
            timestamp=NOW + timedelta(seconds=1),
            event_type=AgentRunEventType.MESSAGE_DELTA,
            redacted_payload=payload,
            provider_event_id=f"message-{run.id}",
            previous_event_digest=previous.event.event_digest,
            event_digest=digest,
        ),
    )


def _artifact(run: AgentRunRecord) -> RunArtifact:
    artifact_id = uuid4()
    content_digest = hashlib.sha256(b"artifact").hexdigest()
    return RunArtifact(
        id=artifact_id,
        workspace_id=run.workspace_id,
        run_id=run.id,
        producing_event_sequence=1,
        display_name="result.txt",
        media_type="text/plain",
        byte_size=8,
        content_digest=content_digest,
        parent_artifact_ids=(),
        lineage_digest=compute_lineage_digest(
            workspace_id=run.workspace_id,
            artifact_id=artifact_id,
            run_id=run.id,
            producing_event_sequence=1,
            content_digest=content_digest,
            parent_artifact_ids=(),
        ),
        created_at=NOW,
    )


def _checkpoint_with(
    checkpoint: ExecutionCheckpoint,
    **updates: object,
) -> ExecutionCheckpoint:
    payload = {
        **checkpoint.model_dump(mode="python", exclude={"canonical_digest"}),
        **updates,
    }
    return ExecutionCheckpoint(
        **{
            **payload,
            "canonical_digest": compute_execution_checkpoint_digest(payload),
        }
    )


def _seed_authorization_snapshot(
    database: Path,
    workspace_id: UUID,
) -> tuple[UUID, UUID]:
    request_context_id = uuid4()
    snapshot_id = uuid4()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO authorization_decision_snapshots "
            "(id, workspace_id, request_context_id, signing_key_version_id, canonical_digest, "
            "created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(snapshot_id),
                str(workspace_id),
                str(request_context_id),
                str(uuid4()),
                "d" * 64,
                NOW.isoformat(),
                "{}",
            ),
        )
    return request_context_id, snapshot_id


def test_run_step_checkpoint_survive_reopen_and_are_workspace_scoped(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="one")
    other_workspace, _ = _identity(database, suffix="two")
    agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    request_context_id, authorization_snapshot_id = _seed_authorization_snapshot(
        database,
        workspace.id,
    )
    repository = ExecutionRepository(database)

    assert repository.record_run_state(run) == run
    assert (
        repository.create_step(
            step,
            step_key="plan",
            step_ordinal=1,
            kind="model",
            input_digest=hashlib.sha256(b"input").hexdigest(),
        )
        == step
    )
    lease = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("opaque"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    checkpoint = _checkpoint(run, step)
    assert (
        repository.record_checkpoint(
            checkpoint,
            request_context_id=request_context_id,
            authorization_snapshot_id=authorization_snapshot_id,
            lease_fence=lease.fence,
            lease_token=_test_token("opaque"),
        )
        == checkpoint
    )
    repository.close()

    reopened = ExecutionRepository(database)
    assert reopened.get_latest_run_state(workspace.id, agent_run.id) == run
    assert reopened.get_current_step_state(workspace.id, agent_run.id, step.id) == step
    assert reopened.get_active_step_lease(workspace.id, agent_run.id, step.id) == lease
    assert reopened.get_latest_checkpoint(workspace.id, agent_run.id, step.id) == checkpoint
    assert reopened.get_latest_run_state(other_workspace.id, agent_run.id) is None
    assert reopened.get_current_step_state(other_workspace.id, agent_run.id, step.id) is None
    assert reopened.get_active_step_lease(other_workspace.id, agent_run.id, step.id) is None
    assert reopened.get_latest_checkpoint(other_workspace.id, agent_run.id, step.id) is None
    reopened.close()


def test_step_reacquisition_increments_fence_and_stale_writer_cannot_checkpoint(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="reacquire")
    agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    repository = ExecutionRepository(database)
    repository.record_run_state(run)
    repository.create_step(
        step,
        step_key="plan",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"input").hexdigest(),
    )
    first = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("first"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )

    second = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-b",
        lease_token=_test_token("second"),
        acquired_at=NOW + timedelta(minutes=6),
        expires_at=NOW + timedelta(minutes=11),
    )

    assert (first.fence, second.fence) == (1, 2)
    current_step = repository.get_current_step_state(workspace.id, agent_run.id, step.id)
    assert current_step is not None
    assert (current_step.version, current_step.fence) == (2, 2)
    with pytest.raises(ExecutionRepositoryError, match="execution_step_lease_stale"):
        repository.record_checkpoint(
            _checkpoint(run, step),
            request_context_id=uuid4(),
            authorization_snapshot_id=uuid4(),
            lease_fence=first.fence,
            lease_token=_test_token("first"),
        )
    assert repository.get_latest_checkpoint(workspace.id, agent_run.id, step.id) is None
    repository.close()


def test_exact_replay_returns_stored_and_body_mismatch_writes_no_residue(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="replay")
    agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    request_context_id, authorization_snapshot_id = _seed_authorization_snapshot(
        database,
        workspace.id,
    )
    repository = ExecutionRepository(database)
    assert repository.record_run_state(run) == run
    assert repository.record_run_state(run) == run
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_idempotency_payload_mismatch",
    ):
        repository.record_run_state(
            run.model_copy(update={"state": ExecutionRunState.RUNNING})
        )

    input_digest = hashlib.sha256(b"input").hexdigest()
    assert (
        repository.create_step(
            step,
            step_key="plan",
            step_ordinal=1,
            kind="model",
            input_digest=input_digest,
        )
        == step
    )
    assert (
        repository.create_step(
            step,
            step_key="plan",
            step_ordinal=1,
            kind="model",
            input_digest=input_digest,
        )
        == step
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_idempotency_payload_mismatch",
    ):
        repository.create_step(
            step,
            step_key="plan",
            step_ordinal=1,
            kind="connector",
            input_digest=input_digest,
        )
    lease = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("replay"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    checkpoint = _checkpoint(run, step)
    binding = _CheckpointBinding(
        request_context_id=request_context_id,
        authorization_snapshot_id=authorization_snapshot_id,
        lease_fence=lease.fence,
        lease_token=_test_token("replay"),
    )
    assert _record_bound_checkpoint(repository, checkpoint, binding) == checkpoint
    assert _record_bound_checkpoint(repository, checkpoint, binding) == checkpoint
    changed_payload = {
        **checkpoint.model_dump(mode="python", exclude={"canonical_digest"}),
        "next_transition": ExecutionNextTransition.WAIT,
    }
    changed_checkpoint = ExecutionCheckpoint(
        **{
            **changed_payload,
            "canonical_digest": compute_execution_checkpoint_digest(changed_payload),
        }
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_idempotency_payload_mismatch",
    ):
        _record_bound_checkpoint(repository, changed_checkpoint, binding)

    with sqlite3.connect(database) as connection:
        counts = (
            connection.execute(
                "SELECT COUNT(*) FROM agent_run_state_versions"
            ).fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM run_steps").fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM run_step_versions"
            ).fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM run_checkpoints").fetchone()[0],
        )
    assert counts == (1, 1, 1, 1)
    repository.close()


def test_state_version_compare_and_swap_requires_exact_next_version(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="cas")
    agent_run = _seed_agent_run(database, workspace, principal)
    run_v1 = _execution_run(workspace.id, agent_run.id)
    step_v1 = _execution_step(workspace.id, agent_run.id)
    repository = ExecutionRepository(database)
    repository.record_run_state(run_v1)
    repository.create_step(
        step_v1,
        step_key="plan",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"input").hexdigest(),
    )
    run_v2 = _next_run_state(
        run_v1,
        state=ExecutionRunState.RUNNING,
        version=2,
    )
    step_v2 = _next_step_state(
        step_v1,
        state=ExecutionStepState.RUNNING,
        version=2,
        fence=2,
    )
    assert repository.append_run_state(run_v2, expected_prior_version=1) == run_v2
    assert repository.append_step_state(step_v2, expected_prior_version=1) == step_v2

    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_run_version_conflict",
    ):
        repository.append_run_state(
            _next_run_state(run_v2, state=ExecutionRunState.PAUSED, version=3),
            expected_prior_version=1,
        )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_step_version_conflict",
    ):
        repository.append_step_state(
            _next_step_state(
                step_v2,
                state=ExecutionStepState.PAUSED,
                version=3,
                fence=3,
            ),
            expected_prior_version=1,
        )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_run_version_conflict",
    ):
        repository.append_run_state(
            _next_run_state(run_v2, state=ExecutionRunState.PAUSED, version=4),
            expected_prior_version=2,
        )

    assert repository.get_latest_run_state(workspace.id, agent_run.id) == run_v2
    assert (
        repository.get_current_step_state(workspace.id, agent_run.id, step_v1.id)
        == step_v2
    )
    repository.close()


def test_checkpoint_binds_authority_event_head_and_same_run_artifacts(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="bindings")
    agent_run = _seed_agent_run(database, workspace, principal)
    other_run = _seed_agent_run(database, workspace, principal)
    conversations = ConversationRepository(database)
    event = conversations.append_event(
        _started_event(agent_run),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    event_head = conversations.append_event(
        _next_event(agent_run, event),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    other_event = conversations.append_event(
        _started_event(other_run),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    artifact = conversations.record_artifact(
        _artifact(agent_run),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    other_artifact = conversations.record_artifact(
        _artifact(other_run),
        requester_principal_id=principal.id,
        requester_membership_version=1,
    )
    assert other_event.event.sequence == 1
    conversations.close()
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    request_context_id, authorization_snapshot_id = _seed_authorization_snapshot(
        database,
        workspace.id,
    )
    repository = ExecutionRepository(database)
    repository.record_run_state(run)
    repository.create_step(
        step,
        step_key="plan",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"input").hexdigest(),
    )
    lease = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("binding"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    base = _checkpoint(run, step)
    event_checkpoint = _checkpoint_with(
        base,
        last_accepted_event_sequence=event_head.event.sequence,
        last_accepted_event_digest=event_head.event.event_digest,
        artifact_ref_ids=(artifact.id,),
    )
    binding = _CheckpointBinding(
        request_context_id=request_context_id,
        authorization_snapshot_id=authorization_snapshot_id,
        lease_fence=lease.fence,
        lease_token=_test_token("binding"),
    )

    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_checkpoint_authority_context_not_found",
    ):
        _record_bound_checkpoint(
            repository,
            event_checkpoint,
            _CheckpointBinding(
                request_context_id=uuid4(),
                authorization_snapshot_id=binding.authorization_snapshot_id,
                lease_fence=binding.lease_fence,
                lease_token=binding.lease_token,
            ),
        )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_checkpoint_event_mismatch",
    ):
        _record_bound_checkpoint(
            repository,
            _checkpoint_with(
                event_checkpoint,
                last_accepted_event_sequence=event.event.sequence,
                last_accepted_event_digest=event.event.event_digest,
            ),
            binding,
        )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_checkpoint_event_mismatch",
    ):
        _record_bound_checkpoint(
            repository,
            _checkpoint_with(
                event_checkpoint,
                last_accepted_event_digest="e" * 64,
            ),
            binding,
        )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_checkpoint_artifact_not_found",
    ):
        _record_bound_checkpoint(
            repository,
            _checkpoint_with(
                event_checkpoint,
                artifact_ref_ids=(other_artifact.id,),
            ),
            binding,
        )

    assert _record_bound_checkpoint(repository, event_checkpoint, binding) == event_checkpoint
    assert (
        repository.get_latest_checkpoint(workspace.id, agent_run.id, step.id)
        == event_checkpoint
    )
    repository.close()


def test_two_state_writers_serialize_without_residue_and_history_is_scoped(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="writers")
    other_workspace, _ = _identity(database, suffix="writers-other")
    agent_run = _seed_agent_run(database, workspace, principal)
    run_v1 = _execution_run(workspace.id, agent_run.id)
    running = _next_run_state(
        run_v1,
        state=ExecutionRunState.RUNNING,
        version=2,
    )
    paused = _next_run_state(
        run_v1,
        state=ExecutionRunState.PAUSED,
        version=2,
    )
    repository = ExecutionRepository(database)
    repository.record_run_state(run_v1)
    barrier = threading.Barrier(2)

    def append(candidate: ExecutionRun) -> ExecutionRun | str:
        barrier.wait()
        try:
            return repository.append_run_state(
                candidate,
                expected_prior_version=1,
            )
        except ExecutionRepositoryError as exc:
            return exc.reason_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(append, (running, paused)))

    winners = tuple(result for result in results if isinstance(result, ExecutionRun))
    errors = tuple(result for result in results if isinstance(result, str))
    assert len(winners) == 1
    assert errors == ("execution_idempotency_payload_mismatch",)
    assert repository.list_run_states(workspace.id, agent_run.id) == (
        run_v1,
        winners[0],
    )
    assert repository.list_run_states(other_workspace.id, agent_run.id) == ()
    repository.close()


def test_lease_release_reacquisition_and_token_storage_are_fenced(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="release")
    agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    repository = ExecutionRepository(database)
    repository.record_run_state(run)
    repository.create_step(
        step,
        step_key="plan",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"input").hexdigest(),
    )
    first = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("release"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_step_lease_active",
    ):
        repository.acquire_step_lease(
            workspace_id=workspace.id,
            run_id=agent_run.id,
            step_id=step.id,
            worker_id="worker-b",
            lease_token=_test_token("contender"),
            acquired_at=NOW + timedelta(minutes=1),
            expires_at=NOW + timedelta(minutes=6),
        )
    assert (
        repository.get_current_step_state(workspace.id, agent_run.id, step.id)
        == step
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_step_lease_stale",
    ):
        repository.release_step_lease(
            workspace_id=workspace.id,
            run_id=agent_run.id,
            step_id=step.id,
            lease_fence=first.fence,
            lease_token=_test_token("wrong"),
            released_at=NOW + timedelta(minutes=2),
        )
    released = repository.release_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        lease_fence=first.fence,
        lease_token=_test_token("release"),
        released_at=NOW + timedelta(minutes=2),
    )
    second = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-b",
        lease_token=_test_token("second-release"),
        acquired_at=NOW + timedelta(minutes=3),
        expires_at=NOW + timedelta(minutes=8),
    )

    assert released.released_at == NOW + timedelta(minutes=2)
    assert second.fence == first.fence + 1
    with sqlite3.connect(database) as connection:
        stored_tokens = tuple(
            row[0]
            for row in connection.execute(
                "SELECT lease_token_digest FROM run_step_leases ORDER BY fence"
            )
        )
    assert stored_tokens == (
        hashlib.sha256(_test_token("release").encode()).hexdigest(),
        hashlib.sha256(_test_token("second-release").encode()).hexdigest(),
    )
    assert all("token" not in value for value in stored_tokens)
    repository.close()


def test_checkpoint_sequence_is_exact_and_step_checkpoint_history_is_scoped(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="checkpoint-sequence")
    other_workspace, _ = _identity(database, suffix="checkpoint-sequence-other")
    agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, agent_run.id)
    step = _execution_step(workspace.id, agent_run.id)
    request_context_id, authorization_snapshot_id = _seed_authorization_snapshot(
        database,
        workspace.id,
    )
    repository = ExecutionRepository(database)
    repository.record_run_state(run)
    repository.create_step(
        step,
        step_key="plan",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"input").hexdigest(),
    )
    lease = repository.acquire_step_lease(
        workspace_id=workspace.id,
        run_id=agent_run.id,
        step_id=step.id,
        worker_id="worker-a",
        lease_token=_test_token("checkpoint"),
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    checkpoint_v1 = _checkpoint(run, step)
    binding = _CheckpointBinding(
        request_context_id=request_context_id,
        authorization_snapshot_id=authorization_snapshot_id,
        lease_fence=lease.fence,
        lease_token=_test_token("checkpoint"),
    )
    _record_bound_checkpoint(repository, checkpoint_v1, binding)
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_checkpoint_version_conflict",
    ):
        _record_bound_checkpoint(
            repository,
            _checkpoint_with(
                checkpoint_v1,
                id=uuid4(),
                checkpoint_version=3,
                created_at=NOW + timedelta(minutes=1),
            ),
            binding,
        )
    checkpoint_v2 = _checkpoint_with(
        checkpoint_v1,
        id=uuid4(),
        checkpoint_version=2,
        created_at=NOW + timedelta(minutes=1),
    )
    assert _record_bound_checkpoint(repository, checkpoint_v2, binding) == checkpoint_v2

    assert repository.list_step_states(workspace.id, agent_run.id, step.id) == (step,)
    assert repository.list_checkpoints(workspace.id, agent_run.id, step.id) == (
        checkpoint_v1,
        checkpoint_v2,
    )
    assert repository.list_step_states(other_workspace.id, agent_run.id, step.id) == ()
    assert repository.list_checkpoints(other_workspace.id, agent_run.id, step.id) == ()
    repository.close()


def test_run_and_step_creation_reject_cross_scope_or_invalid_initial_bindings_atomically(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    workspace, principal = _identity(database, suffix="creation")
    other_workspace, _ = _identity(database, suffix="creation-other")
    first_agent_run = _seed_agent_run(database, workspace, principal)
    second_agent_run = _seed_agent_run(database, workspace, principal)
    run = _execution_run(workspace.id, first_agent_run.id)
    second_run = _execution_run(workspace.id, second_agent_run.id)
    repository = ExecutionRepository(database)
    repository.record_run_state(run)
    repository.record_run_state(second_run)
    wrong_workspace_payload = {
        **run.model_dump(mode="python", exclude={"canonical_digest"}),
        "workspace_id": other_workspace.id,
    }
    wrong_workspace_run = ExecutionRun(
        **{
            **wrong_workspace_payload,
            "canonical_digest": compute_execution_run_digest(
                wrong_workspace_payload
            ),
        }
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_run_not_found",
    ):
        repository.record_run_state(wrong_workspace_run)
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_run_initial_version_invalid",
    ):
        repository.record_run_state(
            _next_run_state(
                second_run,
                state=ExecutionRunState.RUNNING,
                version=2,
            )
        )

    parent = _execution_step(workspace.id, first_agent_run.id)
    repository.create_step(
        parent,
        step_key="parent",
        step_ordinal=1,
        kind="model",
        input_digest=hashlib.sha256(b"parent").hexdigest(),
    )
    child = _execution_step(workspace.id, first_agent_run.id)
    assert (
        repository.create_step(
            child,
            step_key="child",
            step_ordinal=2,
            kind="connector",
            input_digest=hashlib.sha256(b"child").hexdigest(),
            parent_step_id=parent.id,
        )
        == child
    )
    cross_run_child = _execution_step(workspace.id, second_agent_run.id)
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_step_parent_not_found",
    ):
        repository.create_step(
            cross_run_child,
            step_key="cross-run",
            step_ordinal=1,
            kind="model",
            input_digest=hashlib.sha256(b"cross-run").hexdigest(),
            parent_step_id=parent.id,
        )
    invalid_initial = _next_step_state(
        _execution_step(workspace.id, second_agent_run.id),
        state=ExecutionStepState.READY,
        version=2,
        fence=2,
    )
    with pytest.raises(
        ExecutionRepositoryError,
        match="execution_step_initial_version_invalid",
    ):
        repository.create_step(
            invalid_initial,
            step_key="invalid-initial",
            step_ordinal=1,
            kind="model",
            input_digest=hashlib.sha256(b"invalid").hexdigest(),
        )

    with sqlite3.connect(database) as connection:
        orphan_count = connection.execute(
            "SELECT COUNT(*) FROM run_steps WHERE id IN (?, ?)",
            (str(cross_run_child.id), str(invalid_initial.id)),
        ).fetchone()[0]
        run_state_count = connection.execute(
            "SELECT COUNT(*) FROM agent_run_state_versions"
        ).fetchone()[0]
    assert (orphan_count, run_state_count) == (0, 2)
    repository.close()
