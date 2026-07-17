from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import JsonValue

from corvus.application.ports import AgentRuntimePort
from corvus.domain.agent_runtime import (
    AgentCapabilities,
    AgentRunEvent,
    AgentRunEventType,
    AgentRunHandle,
    AgentRunRequest,
    AgentRunStartResult,
    AgentRunState,
    CancellationResult,
    CapabilitySupport,
    ExecutableIdentity,
    ProviderBinding,
    ProviderCandidate,
    ProviderDiscoveryQuery,
    ProviderFamily,
    ProviderHealth,
    ProviderStatus,
    ProviderTransport,
    compute_agent_run_event_digest,
    compute_provider_binding_digest,
)
from corvus.infrastructure.agent_runtimes.process_session import (
    ProcessInvocation,
    ProcessSession,
    ProcessSessionError,
    ProcessSessionEvent,
    ProcessSessionEventKind,
    ProcessSessionLimits,
)

_FIRST_EVENT_DIGEST = "0" * 64
_DEFAULT_MODEL_LABEL = "Codex default"
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
_MAX_TIMEOUT_SECONDS = 120.0
_MAX_STDERR_BYTES = 64_000
_MAX_FRAME_BYTES = 1_000_000
_MAX_FRAMES = 10_000
_TOOL_ITEM_TYPES = frozenset(
    {
        "command_execution",
        "file_change",
        "mcp_tool_call",
        "tool_call",
        "web_search",
    }
)


class CodexAdapterError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LocalCodexTextRequest:
    run_id: UUID
    prompt: str
    idempotency_key: str
    deadline: datetime
    model: str | None = None
    max_output_bytes: int = 100_000


class _ProcessSessionLike(Protocol):
    def events(self, after_sequence: int = 0) -> AsyncIterator[ProcessSessionEvent]: ...

    async def cancel(self) -> bool: ...


SessionStarter = Callable[[ProcessInvocation], Awaitable[_ProcessSessionLike]]


async def _start_process_session(invocation: ProcessInvocation) -> _ProcessSessionLike:
    return await ProcessSession.start(invocation)


class _RunSession:
    def __init__(self, process: _ProcessSessionLike) -> None:
        self.process = process
        self.events: tuple[AgentRunEvent, ...] | None = None
        self.lock = asyncio.Lock()
        self.terminal_state: AgentRunState | None = None


class CodexCliAdapter(AgentRuntimePort):
    """Bounded, text-only adapter for the locally authenticated Codex CLI."""

    def __init__(
        self,
        *,
        executable: Path,
        version: str,
        scratch_root: Path,
        clock: Callable[[], datetime],
        session_starter: SessionStarter = _start_process_session,
    ) -> None:
        self._executable = executable.resolve(strict=False)
        self._version = version
        self._scratch_root = scratch_root.resolve(strict=False)
        self._clock = clock
        self._session_starter = session_starter
        self._bindings: dict[UUID, ProviderBinding] = {}
        self._sessions: dict[UUID, _RunSession] = {}

    async def discover(self, query: ProviderDiscoveryQuery) -> tuple[ProviderCandidate, ...]:
        if not self._executable.is_file():
            return ()
        executable_digest = _sha256_file(self._executable)
        identity = ExecutableIdentity(
            executable_path=self._executable,
            version=self._version,
            sha256_digest=executable_digest,
        )
        binding_id = uuid5(
            NAMESPACE_URL,
            "corvus:codex:"
            f"{query.workspace_id}:{query.project_id or 'workspace'}:{self._executable}:{executable_digest}",
        )
        binding = ProviderBinding(
            id=binding_id,
            workspace_id=query.workspace_id,
            project_id=query.project_id,
            family=ProviderFamily.CODEX,
            transport=ProviderTransport.LOCAL_CLI,
            status=ProviderStatus.AVAILABLE,
            executable_identity=identity,
            model=_DEFAULT_MODEL_LABEL,
            capabilities=_text_only_capabilities(),
            health_checked_at=self._clock(),
            version=1,
            data_egress_disclosure="Prompts are sent through the user's local Codex login.",
            server_storage_disclosure="OpenAI retention follows the user's Codex account policy.",
        )
        self._bindings[binding.id] = binding
        digest = compute_provider_binding_digest(binding)
        return (ProviderCandidate(binding=binding, binding_version=1, binding_digest=digest),)

    def capabilities(self, binding: ProviderBinding) -> AgentCapabilities:
        self._require_binding(binding)
        return _text_only_capabilities()

    async def health(self, binding: ProviderBinding) -> ProviderHealth:
        self._require_binding(binding)
        status = ProviderStatus.AVAILABLE
        identity = binding.executable_identity
        if identity is None or not self._executable.is_file():
            status = ProviderStatus.UNAVAILABLE
        elif _sha256_file(self._executable) != identity.sha256_digest:
            status = ProviderStatus.UNHEALTHY
        return ProviderHealth(
            binding_id=binding.id,
            binding_version=binding.version,
            binding_digest=compute_provider_binding_digest(binding),
            status=status,
            observed_at=self._clock(),
        )

    async def start(self, request: AgentRunRequest) -> AgentRunStartResult:
        binding = self._binding_for_request(request)
        prompt = request.prompt or "\n".join(request.messages or ())
        return await self._start_text(
            binding=binding,
            run_id=request.run_id,
            prompt=prompt,
            model=request.model,
            idempotency_key=request.idempotency_key,
            deadline=request.deadline,
            max_output_bytes=request.max_output_bytes,
        )

    async def start_local_text(
        self,
        binding: ProviderBinding,
        request: LocalCodexTextRequest,
    ) -> AgentRunStartResult:
        self._require_binding(binding)
        return await self._start_text(
            binding=binding,
            run_id=request.run_id,
            prompt=request.prompt,
            model=request.model,
            idempotency_key=request.idempotency_key,
            deadline=request.deadline,
            max_output_bytes=request.max_output_bytes,
        )

    async def _start_text(
        self,
        *,
        binding: ProviderBinding,
        run_id: UUID,
        prompt: str,
        model: str | None,
        idempotency_key: str,
        deadline: datetime,
        max_output_bytes: int,
    ) -> AgentRunStartResult:
        existing = next(
            (
                handle
                for handle, session in self._sessions.items()
                if getattr(session, "request_key", None) == idempotency_key
            ),
            None,
        )
        if existing is not None:
            return AgentRunStartResult(
                handle=AgentRunHandle(
                    id=existing,
                    run_id=run_id,
                    provider_binding_id=binding.id,
                    created_at=self._clock(),
                    state=AgentRunState.RUNNING,
                ),
                replayed=True,
            )
        if not prompt:
            raise CodexAdapterError("codex_prompt_required")
        if model is not None and _MODEL_PATTERN.fullmatch(model) is None:
            raise CodexAdapterError("codex_model_invalid")
        scratch = self._scratch_root / str(run_id)
        scratch.mkdir(parents=True, exist_ok=False)
        arguments = [
            "exec",
            "--json",
            "--color",
            "never",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
        ]
        if model is not None:
            arguments.extend(("--model", model))
        arguments.append(prompt)
        limits = ProcessSessionLimits(
            max_stdout_bytes=max_output_bytes,
            max_stderr_bytes=min(max_output_bytes, _MAX_STDERR_BYTES),
            max_frame_bytes=min(max_output_bytes, _MAX_FRAME_BYTES),
            max_frames=_MAX_FRAMES,
            max_events=_MAX_FRAMES + 1,
            timeout_seconds=min(
                _MAX_TIMEOUT_SECONDS,
                max(1.0, (deadline - self._clock()).total_seconds()),
            ),
        )
        invocation = ProcessInvocation(
            executable=self._executable,
            executable_sha256=binding.executable_identity.sha256_digest,  # type: ignore[union-attr]
            arguments=tuple(arguments),
            cwd=scratch,
            approved_roots=(self._scratch_root,),
            environment=MappingProxyType({"NO_COLOR": "1"}),
            limits=limits,
        )
        try:
            process = await self._session_starter(invocation)
        except ProcessSessionError as error:
            raise CodexAdapterError("codex_process_unavailable") from error
        handle = AgentRunHandle(
            run_id=run_id,
            provider_binding_id=binding.id,
            created_at=self._clock(),
            state=AgentRunState.RUNNING,
        )
        run_session = _RunSession(process)
        run_session.request_key = idempotency_key  # type: ignore[attr-defined]
        self._sessions[handle.id] = run_session
        return AgentRunStartResult(handle=handle, replayed=False)

    async def events(
        self,
        handle: AgentRunHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[AgentRunEvent]:
        session = self._require_session(handle)
        async with session.lock:
            if session.events is None:
                session.events = await self._normalize_events(handle, session)
        for event in session.events:
            if event.sequence > after_sequence:
                yield event

    async def cancel(
        self,
        handle: AgentRunHandle,
        current_kill_switch_proof_id: UUID,
        current_kill_switch_proof_digest: str,
    ) -> CancellationResult:
        del current_kill_switch_proof_id, current_kill_switch_proof_digest
        session = self._require_session(handle)
        if session.terminal_state is not None:
            return CancellationResult(
                handle_id=handle.id,
                handle=handle.model_copy(update={"state": session.terminal_state}),
                accepted=False,
                terminal=True,
                reason_code="agent_run_already_terminal",
                timestamp=self._clock(),
            )
        await session.process.cancel()
        session.terminal_state = AgentRunState.CANCELLED
        return CancellationResult(
            handle_id=handle.id,
            handle=handle.model_copy(update={"state": AgentRunState.CANCELLED}),
            accepted=True,
            terminal=True,
            reason_code="agent_run_cancelled",
            timestamp=self._clock(),
        )

    async def cancel_local(self, handle: AgentRunHandle) -> CancellationResult:
        session = self._require_session(handle)
        if session.terminal_state is not None:
            return CancellationResult(
                handle_id=handle.id,
                handle=handle.model_copy(update={"state": session.terminal_state}),
                accepted=False,
                terminal=True,
                reason_code="agent_run_already_terminal",
                timestamp=self._clock(),
            )
        await session.process.cancel()
        session.terminal_state = AgentRunState.CANCELLED
        return CancellationResult(
            handle_id=handle.id,
            handle=handle.model_copy(update={"state": AgentRunState.CANCELLED}),
            accepted=True,
            terminal=True,
            reason_code="agent_run_cancelled",
            timestamp=self._clock(),
        )

    async def resume(
        self,
        handle: AgentRunHandle,
        request_with_fresh_proofs: AgentRunRequest,
    ) -> AgentRunHandle:
        del handle, request_with_fresh_proofs
        raise CodexAdapterError("codex_resume_unsupported")

    def _require_binding(self, binding: ProviderBinding) -> ProviderBinding:
        registered = self._bindings.get(binding.id)
        if registered != binding:
            raise CodexAdapterError("codex_binding_unknown")
        return registered

    def _binding_for_request(self, request: AgentRunRequest) -> ProviderBinding:
        binding = self._bindings.get(request.provider_binding_id)
        if (
            binding is None
            or binding.version != request.provider_binding_version
            or compute_provider_binding_digest(binding) != request.provider_binding_digest
        ):
            raise CodexAdapterError("codex_binding_mismatch")
        return binding

    def _require_session(self, handle: AgentRunHandle) -> _RunSession:
        session = self._sessions.get(handle.id)
        if session is None:
            raise CodexAdapterError("codex_handle_unknown")
        return session

    async def _normalize_events(
        self,
        handle: AgentRunHandle,
        session: _RunSession,
    ) -> tuple[AgentRunEvent, ...]:
        normalized: list[AgentRunEvent] = []
        terminal = False

        def emit(event_type: AgentRunEventType, payload: dict[str, JsonValue]) -> None:
            previous = normalized[-1].event_digest if normalized else _FIRST_EVENT_DIGEST
            sequence = len(normalized) + 1
            timestamp = self._clock()
            digest = compute_agent_run_event_digest(
                run_id=handle.run_id,
                handle_id=handle.id,
                sequence=sequence,
                timestamp=timestamp,
                event_type=event_type,
                redacted_payload=payload,
                provider_event_id=None,
                previous_event_digest=previous,
                tool_call_id=None,
                effect_authorization_decision_id=None,
                effect_authorization_decision_digest=None,
            )
            normalized.append(
                AgentRunEvent(
                    run_id=handle.run_id,
                    handle_id=handle.id,
                    sequence=sequence,
                    timestamp=timestamp,
                    event_type=event_type,
                    redacted_payload=payload,
                    previous_event_digest=previous,
                    event_digest=digest,
                )
            )

        async for event in session.process.events():
            if terminal:
                continue
            if event.kind is ProcessSessionEventKind.FRAME and event.frame is not None:
                frame_type = event.frame.get("type")
                item = event.frame.get("item")
                item_type = item.get("type") if isinstance(item, Mapping) else None
                if item_type in _TOOL_ITEM_TYPES:
                    await session.process.cancel()
                    emit(AgentRunEventType.FAILED, {"reason_code": "codex_tool_event_blocked"})
                    session.terminal_state = AgentRunState.FAILED
                    terminal = True
                elif frame_type == "thread.started":
                    emit(AgentRunEventType.STARTED, {"status": "started"})
                elif item_type == "agent_message" and isinstance(item, Mapping):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        emit(AgentRunEventType.MESSAGE_DELTA, {"text": text})
                elif frame_type == "turn.completed":
                    usage = event.frame.get("usage")
                    if isinstance(usage, Mapping):
                        safe_usage: dict[str, JsonValue] = {
                            key: value
                            for key, value in usage.items()
                            if key in {"input_tokens", "cached_input_tokens", "output_tokens"}
                            and isinstance(value, int)
                            and not isinstance(value, bool)
                            and value >= 0
                        }
                        emit(AgentRunEventType.USAGE, safe_usage)
                    emit(AgentRunEventType.COMPLETED, {"status": "completed"})
                    session.terminal_state = AgentRunState.COMPLETED
                    terminal = True
            elif event.kind is ProcessSessionEventKind.CANCELLED:
                emit(AgentRunEventType.CANCELLED, {"reason_code": "agent_run_cancelled"})
                session.terminal_state = AgentRunState.CANCELLED
                terminal = True
            elif event.kind is ProcessSessionEventKind.FAILED:
                emit(
                    AgentRunEventType.FAILED,
                    {"reason_code": event.reason_code or "codex_process_failed"},
                )
                session.terminal_state = AgentRunState.FAILED
                terminal = True
            elif event.kind is ProcessSessionEventKind.EXITED and not terminal:
                if event.return_code == 0:
                    emit(AgentRunEventType.COMPLETED, {"status": "completed"})
                    session.terminal_state = AgentRunState.COMPLETED
                else:
                    emit(AgentRunEventType.FAILED, {"reason_code": "codex_process_failed"})
                    session.terminal_state = AgentRunState.FAILED
                terminal = True
        if not terminal:
            emit(AgentRunEventType.FAILED, {"reason_code": "codex_stream_incomplete"})
            session.terminal_state = AgentRunState.FAILED
        return tuple(normalized)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_only_capabilities() -> AgentCapabilities:
    unsupported = CapabilitySupport.UNSUPPORTED
    return AgentCapabilities(
        text=CapabilitySupport.SUPPORTED,
        streaming=CapabilitySupport.SUPPORTED,
        tools=unsupported,
        repository_read=unsupported,
        repository_write=unsupported,
        shell=unsupported,
        mcp=unsupported,
        session_resume=unsupported,
        usage_cost_reporting=CapabilitySupport.SUPPORTED,
        provider_side_budget=unsupported,
        provider_side_cancellation=CapabilitySupport.SUPPORTED,
    )
