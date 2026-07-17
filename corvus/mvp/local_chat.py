from __future__ import annotations

import base64
import hashlib
import hmac
import json
import shutil
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from corvus.domain.agent_runtime import (
    AgentRunEventType,
    AgentRunHandle,
    ProviderBinding,
    ProviderDiscoveryQuery,
)
from corvus.infrastructure.agent_runtimes.codex import (
    CodexAdapterError,
    CodexCliAdapter,
    LocalCodexTextRequest,
)

_CODEX_DEFAULT_LABEL = "Codex default"
_LOCAL_RUNTIME_SCOPE = UUID("39fef4c9-baf0-40c7-bada-9c2bd9165445")
_RUN_DEADLINE = timedelta(seconds=120)
_MAX_OUTPUT_BYTES = 100_000


class LocalChatError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class LocalChatConflict(LocalChatError):
    pass


class LocalChatNotFound(LocalChatError):
    pass


class LocalChatCursorError(LocalChatError):
    pass


@dataclass(frozen=True, slots=True)
class LocalChatBackendHandle:
    id: UUID
    run_id: UUID


@dataclass(frozen=True, slots=True)
class LocalChatBackendEvent:
    sequence: int
    timestamp: datetime
    type: str
    payload: dict[str, object]


class LocalChatBackend(Protocol):
    async def start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        idempotency_key: str,
    ) -> LocalChatBackendHandle: ...

    def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]: ...

    async def cancel(self, handle: LocalChatBackendHandle) -> bool: ...


@dataclass(slots=True)
class _RunRecord:
    owner: str
    handle: LocalChatBackendHandle
    request_digest: str
    idempotency_key: str
    response: dict[str, object]
    events: list[LocalChatBackendEvent]
    state: str = "running"


class LocalChatService:
    """Daemon-lifetime, owner-scoped local Codex runs. No durable transcript storage."""

    def __init__(
        self,
        *,
        backend: LocalChatBackend,
        cursor_secret: bytes,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(cursor_secret) < 32:
            raise ValueError("local_chat_cursor_secret_too_short")
        self._backend = backend
        self._cursor_secret = cursor_secret
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runs: dict[UUID, _RunRecord] = {}
        self._idempotency: dict[tuple[str, str], UUID] = {}

    async def start(
        self,
        *,
        owner: str,
        prompt: str,
        model: str | None,
        effort: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        request_digest = _request_digest(prompt, model, effort)
        replay_id = self._idempotency.get((owner, idempotency_key))
        if replay_id is not None:
            replay = self._runs[replay_id]
            if replay.request_digest != request_digest:
                raise LocalChatConflict("idempotency_conflict")
            return dict(replay.response)
        run_id = uuid4()
        try:
            handle = await self._backend.start(
                run_id=run_id,
                prompt=prompt,
                model=model,
                effort=effort,
                idempotency_key=f"{owner}:{idempotency_key}",
            )
        except CodexAdapterError as error:
            raise LocalChatError(error.reason_code) from error
        response: dict[str, object] = {
            "run_id": str(run_id),
            "handle_id": str(handle.id),
            "state": "running",
            "provider": "codex",
            "model": model or _CODEX_DEFAULT_LABEL,
            "storage": "this_device",
            "created_at": self._clock().isoformat(),
        }
        self._runs[run_id] = _RunRecord(
            owner=owner,
            handle=handle,
            request_digest=request_digest,
            idempotency_key=idempotency_key,
            response=response,
            events=[],
        )
        self._idempotency[(owner, idempotency_key)] = run_id
        return dict(response)

    async def events(
        self,
        *,
        owner: str,
        run_id: UUID,
        cursor: str | None,
    ) -> tuple[tuple[str, LocalChatBackendEvent], ...]:
        record = self._owned_run(owner, run_id)
        after_sequence = self._decode_cursor(owner, run_id, cursor) if cursor else 0
        latest = record.events[-1].sequence if record.events else 0
        async for event in self._backend.events(record.handle, latest):
            record.events.append(event)
            if event.type in {"completed", "failed", "cancelled"}:
                record.state = event.type
        return tuple(
            (self._encode_cursor(owner, run_id, event.sequence), event)
            for event in record.events
            if event.sequence > after_sequence
        )

    async def cancel(self, *, owner: str, run_id: UUID) -> dict[str, object]:
        record = self._owned_run(owner, run_id)
        if record.state in {"completed", "failed", "cancelled"}:
            return {
                "run_id": str(run_id),
                "state": record.state,
                "accepted": False,
                "reason_code": "agent_run_already_terminal",
            }
        accepted = await self._backend.cancel(record.handle)
        if accepted:
            record.state = "cancelled"
        return {
            "run_id": str(run_id),
            "state": record.state,
            "accepted": accepted,
            "reason_code": "agent_run_cancelled" if accepted else "agent_run_already_terminal",
        }

    def _owned_run(self, owner: str, run_id: UUID) -> _RunRecord:
        record = self._runs.get(run_id)
        if record is None or not hmac.compare_digest(record.owner, owner):
            raise LocalChatNotFound("local_chat_run_not_found")
        return record

    def _encode_cursor(self, owner: str, run_id: UUID, sequence: int) -> str:
        payload = json.dumps(
            {"owner": owner, "run_id": str(run_id), "sequence": sequence},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + signature).decode("ascii").rstrip("=")

    def _decode_cursor(self, owner: str, run_id: UUID, cursor: str) -> int:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            signed = base64.urlsafe_b64decode(padded.encode("ascii"))
            payload, signature = signed[:-32], signed[-32:]
            expected = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
            values = json.loads(payload)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise LocalChatCursorError("local_chat_cursor_invalid") from error
        if not hmac.compare_digest(signature, expected):
            raise LocalChatCursorError("local_chat_cursor_invalid")
        if values.get("owner") != owner or values.get("run_id") != str(run_id):
            raise LocalChatCursorError("local_chat_cursor_invalid")
        sequence = values.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise LocalChatCursorError("local_chat_cursor_invalid")
        return sequence


class CodexLocalChatBackend:
    def __init__(self, adapter: CodexCliAdapter, clock: Callable[[], datetime]) -> None:
        self._adapter = adapter
        self._clock = clock
        self._binding: ProviderBinding | None = None
        self._handles: dict[UUID, AgentRunHandle] = {}

    async def _provider_binding(self) -> ProviderBinding:
        if self._binding is None:
            candidates = await self._adapter.discover(
                ProviderDiscoveryQuery(workspace_id=_LOCAL_RUNTIME_SCOPE)
            )
            if not candidates:
                raise CodexAdapterError("codex_unavailable")
            self._binding = candidates[0].binding
        return self._binding

    async def start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        idempotency_key: str,
    ) -> LocalChatBackendHandle:
        del effort
        binding = await self._provider_binding()
        result = await self._adapter.start_local_text(
            binding,
            LocalCodexTextRequest(
                run_id=run_id,
                prompt=prompt,
                model=model,
                idempotency_key=idempotency_key,
                deadline=self._clock() + _RUN_DEADLINE,
                max_output_bytes=_MAX_OUTPUT_BYTES,
            ),
        )
        self._handles[result.handle.id] = result.handle
        return LocalChatBackendHandle(id=result.handle.id, run_id=run_id)

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        agent_handle = self._handles.get(handle.id)
        if agent_handle is None:
            raise CodexAdapterError("codex_handle_unknown")
        async for event in self._adapter.events(agent_handle, after_sequence):
            event_name = _event_name(event.event_type)
            yield LocalChatBackendEvent(
                sequence=event.sequence,
                timestamp=event.timestamp,
                type=event_name,
                payload=dict(event.redacted_payload),
            )

    async def cancel(self, handle: LocalChatBackendHandle) -> bool:
        agent_handle = self._handles.get(handle.id)
        if agent_handle is None:
            raise CodexAdapterError("codex_handle_unknown")
        result = await self._adapter.cancel_local(agent_handle)
        return result.accepted


def build_default_local_chat_service(
    *,
    scratch_root: Path,
    cursor_secret: bytes,
) -> LocalChatService | None:
    executable = shutil.which("codex.exe") or shutil.which("codex")
    if executable is None or Path(executable).suffix.lower() not in {"", ".exe"}:
        return None
    def clock() -> datetime:
        return datetime.now(UTC)

    adapter = CodexCliAdapter(
        executable=Path(executable),
        version="local",
        scratch_root=scratch_root,
        clock=clock,
    )
    return LocalChatService(
        backend=CodexLocalChatBackend(adapter, clock),
        cursor_secret=cursor_secret,
        clock=clock,
    )


def _request_digest(prompt: str, model: str | None, effort: str) -> str:
    payload = json.dumps(
        {"prompt": prompt, "model": model, "effort": effort},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _event_name(event_type: AgentRunEventType) -> str:
    mapping: dict[AgentRunEventType, Literal["started", "message", "usage", "completed", "failed", "cancelled"]] = {
        AgentRunEventType.STARTED: "started",
        AgentRunEventType.MESSAGE_DELTA: "message",
        AgentRunEventType.USAGE: "usage",
        AgentRunEventType.COMPLETED: "completed",
        AgentRunEventType.FAILED: "failed",
        AgentRunEventType.CANCELLED: "cancelled",
    }
    return mapping[event_type]
