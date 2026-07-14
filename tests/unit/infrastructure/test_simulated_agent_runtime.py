from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from corvus.application.ports import AgentRuntimePort
from corvus.domain.agent_runtime import (
    AgentCapabilities,
    AgentRunEventType,
    AgentRunHandle,
    AgentRunRequest,
    AgentRunState,
    ExecutableIdentity,
    ProviderBinding,
    ProviderFamily,
    ProviderStatus,
    ProviderTransport,
)
from corvus.infrastructure.agent_runtimes import (
    AgentRuntimeError,
    SimulatedAgentRuntime,
    SimulatedEventTemplate,
)

_BASE_TIME = datetime(2026, 7, 15, tzinfo=UTC)
_FUTURE = datetime(2030, 1, 1, tzinfo=UTC)


def _binding(tmp_path: Path, **updates: object) -> ProviderBinding:
    values: dict[str, object] = {
        "workspace_id": uuid4(),
        "family": ProviderFamily.CODEX,
        "transport": ProviderTransport.LOCAL_CLI,
        "status": ProviderStatus.AVAILABLE,
        "executable_identity": ExecutableIdentity(
            executable_path=(tmp_path / "codex.exe").resolve(),
            version="1.2.3",
            sha256_digest="a" * 64,
        ),
        "model": "gpt-5.6-sol",
        "capabilities": AgentCapabilities(),
        "health_checked_at": _BASE_TIME,
        "version": 1,
        "data_egress_disclosure": "Prompts leave the local process.",
        "server_storage_disclosure": "Provider retention policy applies.",
    }
    values.update(updates)
    return ProviderBinding(**values)


def _request(binding: ProviderBinding, **updates: object) -> AgentRunRequest:
    values: dict[str, object] = {
        "run_id": uuid4(),
        "workspace_id": binding.workspace_id,
        "project_id": binding.project_id,
        "workflow_id": uuid4(),
        "work_item_id": uuid4(),
        "provider_binding_id": binding.id,
        "model": binding.model,
        "effort": "high",
        "prompt": "Review the repository.",
        "untrusted_context_ref_ids": (),
        "authorization_proof_id": uuid4(),
        "authorization_proof_digest": "1" * 64,
        "autonomy_grant_id": uuid4(),
        "autonomy_grant_digest": "2" * 64,
        "credential_grant_ids": (),
        "credential_proof_id": uuid4(),
        "credential_proof_digest": "3" * 64,
        "budget_proof_id": uuid4(),
        "budget_proof_digest": "4" * 64,
        "kill_switch_proof_id": uuid4(),
        "kill_switch_proof_digest": "5" * 64,
        "sandbox_profile": "workspace-write",
        "filesystem_envelope": ("repository.read",),
        "network_envelope": (),
        "tool_envelope": (),
        "deadline": _FUTURE,
        "max_output_tokens": 4000,
        "max_output_bytes": 100_000,
        "idempotency_key": "run:001",
    }
    values.update(updates)
    return AgentRunRequest(**values)


def _runtime(
    bindings: tuple[ProviderBinding, ...],
    templates: dict[object, tuple[SimulatedEventTemplate, ...]],
) -> SimulatedAgentRuntime:
    return SimulatedAgentRuntime(bindings=bindings, event_templates=templates)


@pytest.mark.asyncio
async def test_simulator_discovers_starts_and_replays_deterministically(tmp_path: Path) -> None:
    second = _binding(tmp_path, id=uuid4(), family=ProviderFamily.CLAUDE)
    first = _binding(tmp_path, id=uuid4())
    template = (
        SimulatedEventTemplate(AgentRunEventType.STARTED, {"state": "running"}),
        SimulatedEventTemplate(AgentRunEventType.MESSAGE_DELTA, {"text": "hello"}),
        SimulatedEventTemplate(AgentRunEventType.COMPLETED, {"result": "ok"}),
    )
    runtime = _runtime((second, first), {first.id: template, second.id: template})

    assert isinstance(runtime, AgentRuntimePort)
    assert runtime.discover() == tuple(sorted((first, second), key=lambda item: str(item.id)))
    assert runtime.capabilities(first) == first.capabilities
    assert runtime.health(first) is ProviderStatus.AVAILABLE

    request = _request(first)
    handle = await runtime.start(request)
    events = [event async for event in runtime.events(handle)]
    replayed = [event async for event in runtime.events(handle, after_sequence=1)]

    assert handle.state is AgentRunState.COMPLETED
    assert [event.sequence for event in events] == [1, 2, 3]
    assert replayed == events[1:]
    assert events[0].previous_event_digest == "0" * 64
    assert events[1].previous_event_digest == events[0].event_digest
    assert events[2].previous_event_digest == events[1].event_digest


@pytest.mark.asyncio
async def test_cancel_is_idempotent_and_records_one_terminal_event(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    runtime = _runtime(
        (binding,),
        {
            binding.id: (
                SimulatedEventTemplate(AgentRunEventType.STARTED, {"state": "running"}),
            )
        },
    )
    handle = await runtime.start(_request(binding))
    proof_id = uuid4()

    first = await runtime.cancel(handle, proof_id)
    second = await runtime.cancel(handle, proof_id)
    events = [event async for event in runtime.events(handle)]

    assert first == second
    assert first.accepted and first.terminal
    assert first.reason_code == "agent_run_cancelled"
    assert [event.event_type for event in events].count(AgentRunEventType.CANCELLED) == 1


@pytest.mark.asyncio
async def test_cancel_requires_current_kill_switch_proof(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    runtime = _runtime((binding,), {binding.id: ()})
    handle = await runtime.start(_request(binding))

    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.cancel(handle, None)  # type: ignore[arg-type]

    assert exc_info.value.reason_code == "current_kill_switch_proof_required"


@pytest.mark.asyncio
async def test_simulator_snapshots_mutable_event_templates(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    payload = {"state": "original"}
    runtime = _runtime(
        (binding,),
        {
            binding.id: (
                SimulatedEventTemplate(AgentRunEventType.STARTED, payload),
            )
        },
    )
    payload["state"] = "mutated"

    handle = await runtime.start(_request(binding))
    events = [event async for event in runtime.events(handle)]

    assert events[0].redacted_payload == {"state": "original"}


@pytest.mark.asyncio
async def test_resume_rejects_substitution_and_terminal_handle(tmp_path: Path) -> None:
    binding = _binding(tmp_path)
    other = _binding(tmp_path)
    runtime = _runtime(
        (binding, other),
        {
            binding.id: (
                SimulatedEventTemplate(AgentRunEventType.STARTED, {"state": "running"}),
            ),
            other.id: (),
        },
    )
    request = _request(binding)
    handle = await runtime.start(request)

    with pytest.raises(AgentRuntimeError) as run_exc:
        await runtime.resume(
            handle,
            _request(binding, run_id=uuid4(), resume_handle_id=handle.id),
        )
    assert run_exc.value.reason_code == "resume_run_substitution"

    with pytest.raises(AgentRuntimeError) as provider_exc:
        await runtime.resume(
            handle,
            _request(
                other,
                run_id=request.run_id,
                resume_handle_id=handle.id,
            ),
        )
    assert provider_exc.value.reason_code == "resume_provider_binding_substitution"

    before = [event async for event in runtime.events(handle)]
    resumed = await runtime.resume(
        handle,
        _request(binding, run_id=request.run_id, resume_handle_id=handle.id),
    )
    after = [event async for event in runtime.events(resumed)]
    assert resumed == handle
    assert after == before

    await runtime.cancel(handle, uuid4())
    with pytest.raises(AgentRuntimeError) as terminal_exc:
        await runtime.resume(
            handle,
            _request(binding, run_id=request.run_id, resume_handle_id=handle.id),
        )
    assert terminal_exc.value.reason_code == "agent_run_terminal"


@pytest.mark.asyncio
async def test_unknown_unavailable_and_post_terminal_resources_have_stable_errors(
    tmp_path: Path,
) -> None:
    available = _binding(tmp_path)
    unavailable = _binding(tmp_path, status=ProviderStatus.UNAVAILABLE)
    runtime = _runtime(
        (available, unavailable),
        {
            available.id: (
                SimulatedEventTemplate(AgentRunEventType.COMPLETED, {"result": "ok"}),
                SimulatedEventTemplate(AgentRunEventType.MESSAGE_DELTA, {"text": "late"}),
            ),
            unavailable.id: (),
        },
    )

    with pytest.raises(AgentRuntimeError) as unknown_binding:
        await runtime.start(_request(available, provider_binding_id=uuid4()))
    assert unknown_binding.value.reason_code == "unknown_provider_binding"

    with pytest.raises(AgentRuntimeError) as unavailable_binding:
        await runtime.start(_request(unavailable))
    assert unavailable_binding.value.reason_code == "provider_binding_unavailable"

    unknown_handle = AgentRunHandle(
        run_id=uuid4(),
        provider_binding_id=available.id,
        created_at=_BASE_TIME,
        state=AgentRunState.RUNNING,
    )
    with pytest.raises(AgentRuntimeError) as unknown_handle_exc:
        _ = [event async for event in runtime.events(unknown_handle)]
    assert unknown_handle_exc.value.reason_code == "unknown_agent_run_handle"

    with pytest.raises(AgentRuntimeError) as terminal_template:
        await runtime.start(_request(available))
    assert terminal_template.value.reason_code == "event_after_terminal"
