from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from corvus.domain.agent_runtime import (
    AgentRunEventType,
    AgentRunRequest,
    AgentRunState,
    ProviderDiscoveryQuery,
    ProviderStatus,
    compute_provider_binding_digest,
)
from corvus.infrastructure.agent_runtimes.codex import (
    CodexAdapterError,
    CodexCliAdapter,
    LocalCodexTextRequest,
)
from corvus.infrastructure.agent_runtimes.process_session import (
    ProcessInvocation,
    ProcessSessionError,
    ProcessSessionEvent,
    ProcessSessionEventKind,
)

NOW = datetime(2026, 7, 17, 1, 30, tzinfo=UTC)
WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")


class _Session:
    def __init__(self, events: tuple[ProcessSessionEvent, ...]) -> None:
        self._events = events
        self.cancel_calls = 0

    async def events(self, after_sequence: int = 0) -> AsyncIterator[ProcessSessionEvent]:
        for event in self._events:
            if event.sequence > after_sequence:
                yield event

    async def cancel(self) -> ProcessSessionEvent:
        self.cancel_calls += 1
        return ProcessSessionEvent(
            sequence=max((event.sequence for event in self._events), default=0) + 1,
            kind=ProcessSessionEventKind.CANCELLED,
            reason_code="process_cancelled",
        )


class _Starter:
    def __init__(self, session: _Session) -> None:
        self.session = session
        self.invocation: ProcessInvocation | None = None

    async def __call__(self, invocation: ProcessInvocation) -> _Session:
        self.invocation = invocation
        return self.session


class _FailingStarter:
    async def __call__(self, _invocation: ProcessInvocation) -> _Session:
        raise ProcessSessionError("process_spawn_failed")


def _request(binding_id: UUID, binding_digest: str, **updates: object) -> AgentRunRequest:
    values: dict[str, object] = {
        "run_id": uuid4(),
        "workspace_id": WORKSPACE_ID,
        "provider_binding_id": binding_id,
        "provider_binding_version": 1,
        "provider_binding_digest": binding_digest,
        "model": "gpt-5.4",
        "effort": "normal",
        "prompt": "Reply with hello.",
        "authorization_proof_id": uuid4(),
        "authorization_proof_digest": "1" * 64,
        "autonomy_grant_id": uuid4(),
        "autonomy_grant_digest": "2" * 64,
        "credential_grant_ids": (),
        "kill_switch_proof_id": uuid4(),
        "kill_switch_proof_digest": "3" * 64,
        "sandbox_profile": "read-only",
        "filesystem_envelope": (),
        "network_envelope": (),
        "tool_envelope": (),
        "requested_effect_classes": frozenset(),
        "provider_spend_limit": Decimal(0),
        "corvus_budget_limit": Decimal(0),
        "budget_unit": "usd_micros",
        "budget_requested_amount": 1,
        "approval_limit": 0,
        "max_retries": 0,
        "max_turns": 1,
        "deadline": datetime(2026, 7, 18, tzinfo=UTC),
        "max_output_tokens": 2_000,
        "max_output_bytes": 100_000,
        "idempotency_key": "codex-test-run",
    }
    values.update(updates)
    return AgentRunRequest(**values)


def _adapter(
    tmp_path: Path, events: tuple[ProcessSessionEvent, ...]
) -> tuple[CodexCliAdapter, _Starter]:
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"pinned-codex")
    starter = _Starter(_Session(events))
    return (
        CodexCliAdapter(
            executable=executable,
            version="0.144.0",
            scratch_root=tmp_path / "runs",
            clock=lambda: NOW,
            session_starter=starter,
        ),
        starter,
    )


@pytest.mark.asyncio
async def test_codex_adapter_discovers_pinned_text_only_binding(tmp_path: Path) -> None:
    adapter, _starter = _adapter(tmp_path, ())

    candidates = await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID))

    assert len(candidates) == 1
    binding = candidates[0].binding
    assert binding.status is ProviderStatus.AVAILABLE
    assert binding.executable_identity is not None
    assert binding.executable_identity.version == "0.144.0"
    assert candidates[0].binding_digest == compute_provider_binding_digest(binding)
    assert binding.capabilities.text.value == "supported"
    assert binding.capabilities.tools.value == "unsupported"
    assert binding.capabilities.shell.value == "unsupported"
    assert binding.capabilities.mcp.value == "unsupported"


@pytest.mark.asyncio
async def test_codex_adapter_builds_bounded_non_shell_invocation_and_normalizes_text(
    tmp_path: Path,
) -> None:
    process_events = (
        ProcessSessionEvent(
            sequence=1,
            kind=ProcessSessionEventKind.FRAME,
            frame={"type": "thread.started", "thread_id": "thread-safe"},
        ),
        ProcessSessionEvent(
            sequence=2,
            kind=ProcessSessionEventKind.FRAME,
            frame={
                "type": "item.completed",
                "item": {"id": "item-1", "type": "agent_message", "text": "hello"},
            },
        ),
        ProcessSessionEvent(
            sequence=3,
            kind=ProcessSessionEventKind.FRAME,
            frame={"type": "turn.completed", "usage": {"input_tokens": 4, "output_tokens": 1}},
        ),
        ProcessSessionEvent(sequence=4, kind=ProcessSessionEventKind.EXITED, return_code=0),
    )
    adapter, starter = _adapter(tmp_path, process_events)
    binding = (await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID)))[0]
    request = _request(binding.binding.id, binding.binding_digest)

    start = await adapter.start(request)
    events = [event async for event in adapter.events(start.handle)]

    assert starter.invocation is not None
    assert starter.invocation.executable == binding.binding.executable_identity.executable_path
    assert starter.invocation.arguments[:7] == (
        "exec",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
    )
    assert starter.invocation.arguments[-1] == request.prompt
    assert starter.invocation.stdin is None
    assert starter.invocation.cwd.parent == tmp_path / "runs"
    assert starter.invocation.limits.timeout_seconds <= 120
    assert [event.event_type for event in events] == [
        AgentRunEventType.STARTED,
        AgentRunEventType.MESSAGE_DELTA,
        AgentRunEventType.USAGE,
        AgentRunEventType.COMPLETED,
    ]
    assert events[1].redacted_payload == {"text": "hello"}
    assert start.handle.state is AgentRunState.RUNNING


@pytest.mark.asyncio
async def test_local_codex_default_omits_model_flag_and_rejects_flag_injection(
    tmp_path: Path,
) -> None:
    adapter, starter = _adapter(tmp_path, ())
    candidate = (await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID)))[0]

    await adapter.start_local_text(
        candidate.binding,
        LocalCodexTextRequest(
            run_id=uuid4(),
            prompt="hello",
            idempotency_key="local-default",
            deadline=datetime(2026, 7, 18, tzinfo=UTC),
        ),
    )

    assert starter.invocation is not None
    assert "--model" not in starter.invocation.arguments
    with pytest.raises(CodexAdapterError, match="codex_model_invalid"):
        await adapter.start_local_text(
            candidate.binding,
            LocalCodexTextRequest(
                run_id=uuid4(),
                prompt="hello",
                model="--dangerous-flag",
                idempotency_key="local-invalid",
                deadline=datetime(2026, 7, 18, tzinfo=UTC),
            ),
        )


@pytest.mark.asyncio
async def test_codex_adapter_translates_process_spawn_failure(tmp_path: Path) -> None:
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"pinned-codex")
    adapter = CodexCliAdapter(
        executable=executable,
        version="0.144.0",
        scratch_root=tmp_path / "runs",
        clock=lambda: NOW,
        session_starter=_FailingStarter(),
    )
    binding = (await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID)))[0]

    with pytest.raises(CodexAdapterError, match="^codex_process_unavailable$"):
        await adapter.start_local_text(
            binding.binding,
            LocalCodexTextRequest(
                run_id=uuid4(),
                prompt="hello",
                idempotency_key="local-spawn-failure",
                deadline=datetime(2026, 7, 18, tzinfo=UTC),
            ),
        )


@pytest.mark.asyncio
async def test_codex_adapter_blocks_tool_events_and_cancels_process(tmp_path: Path) -> None:
    adapter, starter = _adapter(
        tmp_path,
        (
            ProcessSessionEvent(
                sequence=1,
                kind=ProcessSessionEventKind.FRAME,
                frame={
                    "type": "item.started",
                    "item": {"id": "tool-1", "type": "command_execution", "command": "secret"},
                },
            ),
        ),
    )
    binding = (await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID)))[0]
    start = await adapter.start(_request(binding.binding.id, binding.binding_digest))

    events = [event async for event in adapter.events(start.handle)]

    assert [event.event_type for event in events] == [AgentRunEventType.FAILED]
    assert events[0].redacted_payload == {"reason_code": "codex_tool_event_blocked"}
    assert starter.session.cancel_calls == 1
    assert "secret" not in repr(events)


@pytest.mark.asyncio
async def test_codex_adapter_redacts_terminal_diagnostics_and_cancels_idempotently(
    tmp_path: Path,
) -> None:
    adapter, starter = _adapter(
        tmp_path,
        (
            ProcessSessionEvent(
                sequence=1,
                kind=ProcessSessionEventKind.FAILED,
                stderr="Authorization: Bearer sk-secret-token",
                reason_code="process_failed",
            ),
        ),
    )
    binding = (await adapter.discover(ProviderDiscoveryQuery(workspace_id=WORKSPACE_ID)))[0]
    start = await adapter.start(_request(binding.binding.id, binding.binding_digest))

    events = [event async for event in adapter.events(start.handle)]
    first_cancel = await adapter.cancel(start.handle, uuid4(), "4" * 64)
    second_cancel = await adapter.cancel(start.handle, uuid4(), "5" * 64)

    assert events[-1].event_type is AgentRunEventType.FAILED
    assert "sk-secret-token" not in repr(events)
    assert first_cancel.reason_code == second_cancel.reason_code == "agent_run_already_terminal"
    assert starter.session.cancel_calls == 0
