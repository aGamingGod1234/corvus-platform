from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import platform
import shutil
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
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
from corvus.infrastructure.agent_runtimes.claude import (
    ClaudeAdapterError,
    ClaudeCliAdapter,
    ClaudeEffort,
    LocalClaudeTextRequest,
)
from corvus.infrastructure.agent_runtimes.codex import (
    CodexAdapterError,
    CodexCliAdapter,
    LocalBuildArtifact,
    LocalCodexTextRequest,
)
from corvus.mvp.provider_catalog import build_provider_catalog
from corvus.mvp.safety import SafetyPreview, build_safety_preview

_CODEX_DEFAULT_LABEL = "Codex default"
_LOCAL_RUNTIME_SCOPE = UUID("39fef4c9-baf0-40c7-bada-9c2bd9165445")
_RUN_DEADLINE = timedelta(seconds=120)
_MAX_OUTPUT_BYTES = 100_000
_WINDOWS_CODEX_TARGETS = {
    "amd64": ("codex-win32-x64", "x86_64-pc-windows-msvc"),
    "arm64": ("codex-win32-arm64", "aarch64-pc-windows-msvc"),
}


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
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
    ) -> LocalChatBackendHandle: ...

    def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]: ...

    async def cancel(self, handle: LocalChatBackendHandle) -> bool: ...

    def artifact(self, handle: LocalChatBackendHandle) -> LocalBuildArtifact | None: ...


@dataclass(slots=True)
class _RunRecord:
    owner: str
    backend: LocalChatBackend
    handle: LocalChatBackendHandle
    request_digest: str
    idempotency_key: str
    response: dict[str, object]
    events: list[LocalChatBackendEvent]
    safety: SafetyPreview
    state: str = "running"
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    pump_task: asyncio.Task[None] | None = None


class LocalChatService:
    """Daemon-lifetime, owner-scoped local Codex runs. No durable transcript storage."""

    def __init__(
        self,
        *,
        backend: LocalChatBackend | None = None,
        backends: Mapping[str, LocalChatBackend] | None = None,
        cursor_secret: bytes,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(cursor_secret) < 32:
            raise ValueError("local_chat_cursor_secret_too_short")
        if backend is not None and backends is not None:
            raise ValueError("local_chat_backend_ambiguous")
        configured = dict(backends or ({"codex": backend} if backend is not None else {}))
        if not configured:
            raise ValueError("local_chat_backend_required")
        self._backends = configured
        self._backend = configured.get("codex") or next(iter(configured.values()))
        self._cursor_secret = cursor_secret
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runs: dict[UUID, _RunRecord] = {}
        self._idempotency: dict[tuple[str, str], UUID] = {}
        self._start_locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def start(
        self,
        *,
        owner: str,
        prompt: str,
        provider: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
        safety_digest: str | None = None,
    ) -> dict[str, object]:
        backend = self._backends.get(provider)
        if backend is None:
            raise LocalChatError("provider_unavailable")
        if provider == "codex" and effort == "max":
            raise LocalChatError("provider_effort_unavailable")
        if provider != "codex" and (mode != "chat" or mcp_enabled):
            raise LocalChatError("provider_mode_unavailable")
        try:
            safety = build_safety_preview(
                provider=provider,
                mode=mode,
                mcp_enabled=mcp_enabled,
            )
        except ValueError as error:
            raise LocalChatError(str(error)) from error
        if safety.requires_confirmation and not hmac.compare_digest(
            safety.policy_digest,
            safety_digest or "",
        ):
            raise LocalChatConflict("safety_digest_mismatch")
        request_digest = _request_digest(
            prompt,
            provider,
            model,
            effort,
            mode,
            mcp_enabled,
            safety_digest,
        )
        idempotency_scope = (owner, idempotency_key)
        start_lock = self._start_locks.setdefault(idempotency_scope, asyncio.Lock())
        async with start_lock:
            return await self._start_once(
                owner=owner,
                prompt=prompt,
                provider=provider,
                model=model,
                effort=effort,
                mode=mode,
                mcp_enabled=mcp_enabled,
                safety_digest=safety_digest,
                safety=safety,
                idempotency_key=idempotency_key,
                idempotency_scope=idempotency_scope,
                request_digest=request_digest,
                backend=backend,
            )

    async def _start_once(
        self,
        *,
        owner: str,
        prompt: str,
        provider: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        safety_digest: str | None,
        safety: SafetyPreview,
        idempotency_key: str,
        idempotency_scope: tuple[str, str],
        request_digest: str,
        backend: LocalChatBackend,
    ) -> dict[str, object]:
        replay_id = self._idempotency.get(idempotency_scope)
        if replay_id is not None:
            replay = self._runs[replay_id]
            if replay.request_digest != request_digest:
                raise LocalChatConflict("idempotency_conflict")
            return dict(replay.response)
        run_id = uuid4()
        try:
            handle = await backend.start(
                run_id=run_id,
                prompt=prompt,
                model=model,
                effort=effort,
                mode=mode,
                mcp_enabled=mcp_enabled,
                idempotency_key=f"{owner}:{idempotency_key}",
            )
        except (CodexAdapterError, ClaudeAdapterError) as error:
            raise LocalChatError(error.reason_code) from error
        response: dict[str, object] = {
            "run_id": str(run_id),
            "handle_id": str(handle.id),
            "state": "running",
            "provider": provider,
            "model": model or (_CODEX_DEFAULT_LABEL if provider == "codex" else "Claude Sonnet 5"),
            "mode": mode,
            "storage": "this_device",
            "created_at": self._clock().isoformat(),
            "safety": safety.as_dict(),
        }
        record = _RunRecord(
            owner=owner,
            backend=backend,
            handle=handle,
            request_digest=request_digest,
            idempotency_key=idempotency_key,
            response=response,
            events=[],
            safety=safety,
        )
        self._runs[run_id] = record
        self._idempotency[idempotency_scope] = run_id
        record.pump_task = asyncio.create_task(
            self._pump_events(record),
            name=f"corvus-local-chat-{run_id}",
        )
        return dict(response)

    def events(
        self,
        *,
        owner: str,
        run_id: UUID,
        cursor: str | None,
        follow: bool = True,
    ) -> AsyncIterator[tuple[str, LocalChatBackendEvent]]:
        record = self._owned_run(owner, run_id)
        after_sequence = self._decode_cursor(owner, run_id, cursor) if cursor else 0

        async def stream() -> AsyncIterator[tuple[str, LocalChatBackendEvent]]:
            latest = after_sequence
            while True:
                async with record.condition:
                    pending = [event for event in record.events if event.sequence > latest]
                    if not pending:
                        if not follow or record.state in {"completed", "failed", "cancelled"}:
                            return
                        await record.condition.wait()
                        continue
                for event in pending:
                    latest = event.sequence
                    yield self._encode_cursor(owner, run_id, event.sequence), event
                if not follow:
                    return

        return stream()

    async def _pump_events(self, record: _RunRecord) -> None:
        latest = 0
        try:
            async for event in record.backend.events(record.handle, latest):
                if event.sequence <= latest:
                    continue
                latest = event.sequence
                async with record.condition:
                    record.events.append(event)
                    if event.type in {"completed", "failed", "cancelled"}:
                        record.state = event.type
                    record.condition.notify_all()
            if record.state == "running":
                await self._append_runtime_failure(record, latest, "local_chat_stream_ended")
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._append_runtime_failure(record, latest, "local_chat_runtime_failed")

    async def _append_runtime_failure(
        self,
        record: _RunRecord,
        latest: int,
        reason_code: str,
    ) -> None:
        async with record.condition:
            if record.state != "running":
                return
            record.events.append(
                LocalChatBackendEvent(
                    sequence=latest + 1,
                    timestamp=self._clock(),
                    type="failed",
                    payload={"reason_code": reason_code},
                )
            )
            record.state = "failed"
            record.condition.notify_all()

    def artifact(self, *, owner: str, run_id: UUID) -> LocalBuildArtifact:
        record = self._owned_run(owner, run_id)
        artifact = record.backend.artifact(record.handle)
        if artifact is None:
            raise LocalChatNotFound("local_chat_artifact_not_found")
        return artifact

    def safety_receipt(self, *, owner: str, run_id: UUID) -> dict[str, object]:
        record = self._owned_run(owner, run_id)
        if record.state == "running":
            raise LocalChatConflict("safety_receipt_not_ready")
        activity_labels = {
            "command": "Commands ran inside the selected sandbox",
            "files": "Files changed only inside the scratch workspace",
            "mcp": "A configured MCP tool was used",
            "search": "Project context was inspected",
        }
        activity_keys = {
            event.payload.get("activity")
            for event in record.events
            if event.type == "status" and isinstance(event.payload.get("activity"), str)
        }
        activities = [label for key, label in activity_labels.items() if key in activity_keys]
        artifact_payload: dict[str, object] | None = None
        artifact = record.backend.artifact(record.handle)
        if artifact is not None:
            artifact_payload = {
                "download_name": artifact.download_name,
                "sha256_digest": artifact.sha256_digest,
                "size_bytes": artifact.size_bytes,
                "secret_screening": "passed",
            }
        return {
            "run_id": str(run_id),
            "status": record.state,
            "safety": record.safety.as_dict(),
            "activities": activities,
            "mcp_used": "mcp" in activity_keys,
            "approval": (
                "No blanket host approval was granted; the run remained inside its selected policy."
            ),
            "original_project_modified": False,
            "artifact": artifact_payload,
        }

    async def cancel(self, *, owner: str, run_id: UUID) -> dict[str, object]:
        record = self._owned_run(owner, run_id)
        if record.state in {"completed", "failed", "cancelled"}:
            return {
                "run_id": str(run_id),
                "state": record.state,
                "accepted": False,
                "reason_code": "agent_run_already_terminal",
            }
        accepted = await record.backend.cancel(record.handle)
        if accepted:
            async with record.condition:
                record.state = "cancelled"
                record.condition.notify_all()
        return {
            "run_id": str(run_id),
            "state": record.state,
            "accepted": accepted,
            "reason_code": "agent_run_cancelled" if accepted else "agent_run_already_terminal",
        }

    def provider_catalog(self) -> tuple[dict[str, object], ...]:
        entries = build_provider_catalog(
            codex_available="codex" in self._backends,
            claude_available="claude" in self._backends,
        )
        return tuple(
            {
                "id": "grok" if entry.id == "xai" else entry.id,
                "label": entry.name,
                "runtime": entry.transport,
                "status": entry.status,
                "status_label": entry.status_label,
                "models": [model.as_dict() for model in entry.models],
                "thinking_levels": list(entry.thinking_levels),
                "supports_mcp": entry.supports_mcp,
            }
            for entry in entries
        )

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
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
    ) -> LocalChatBackendHandle:
        binding = await self._provider_binding()
        result = await self._adapter.start_local_text(
            binding,
            LocalCodexTextRequest(
                run_id=run_id,
                prompt=prompt,
                model=model,
                effort=_normalize_codex_effort(effort),
                mode=_normalize_mode(mode),
                mcp_enabled=mcp_enabled,
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

    def artifact(self, handle: LocalChatBackendHandle) -> LocalBuildArtifact | None:
        agent_handle = self._handles.get(handle.id)
        if agent_handle is None:
            raise CodexAdapterError("codex_handle_unknown")
        return self._adapter.artifact(agent_handle)


class ClaudeLocalChatBackend:
    def __init__(self, adapter: ClaudeCliAdapter, clock: Callable[[], datetime]) -> None:
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
                raise ClaudeAdapterError("claude_unavailable")
            self._binding = candidates[0].binding
        return self._binding

    async def start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
    ) -> LocalChatBackendHandle:
        if mode != "chat" or mcp_enabled:
            raise ClaudeAdapterError("claude_mode_unavailable")
        binding = await self._provider_binding()
        result = await self._adapter.start_local_text(
            binding,
            LocalClaudeTextRequest(
                run_id=run_id,
                prompt=prompt,
                model=model or "sonnet",
                effort=_normalize_claude_effort(effort),
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
            raise ClaudeAdapterError("claude_handle_unknown")
        async for event in self._adapter.events(agent_handle, after_sequence):
            yield LocalChatBackendEvent(
                sequence=event.sequence,
                timestamp=event.timestamp,
                type=_event_name(event.event_type),
                payload=dict(event.redacted_payload),
            )

    async def cancel(self, handle: LocalChatBackendHandle) -> bool:
        agent_handle = self._handles.get(handle.id)
        if agent_handle is None:
            raise ClaudeAdapterError("claude_handle_unknown")
        result = await self._adapter.cancel_local(agent_handle)
        return result.accepted

    def artifact(self, handle: LocalChatBackendHandle) -> LocalBuildArtifact | None:
        if handle.id not in self._handles:
            raise ClaudeAdapterError("claude_handle_unknown")
        return None


def build_default_local_chat_service(
    *,
    scratch_root: Path,
    cursor_secret: bytes,
) -> LocalChatService | None:
    codex_executable = _discover_codex_executable()
    claude_executable = _discover_claude_executable()
    if codex_executable is None and claude_executable is None:
        return None

    def clock() -> datetime:
        return datetime.now(UTC)

    backends: dict[str, LocalChatBackend] = {}
    if codex_executable is not None:
        codex_adapter = CodexCliAdapter(
            executable=codex_executable,
            version="local",
            scratch_root=scratch_root / "codex",
            clock=clock,
        )
        backends["codex"] = CodexLocalChatBackend(codex_adapter, clock)
    if claude_executable is not None:
        claude_adapter = ClaudeCliAdapter(
            executable=claude_executable,
            version="local",
            scratch_root=scratch_root / "claude",
            clock=clock,
        )
        backends["claude"] = ClaudeLocalChatBackend(claude_adapter, clock)
    return LocalChatService(
        backends=backends,
        cursor_secret=cursor_secret,
        clock=clock,
    )


def _discover_codex_executable() -> Path | None:
    if os.name == "nt":
        npm_binary = _windows_npm_codex_executable()
        if npm_binary is not None:
            return npm_binary
        direct = shutil.which("codex.exe")
    else:
        direct = shutil.which("codex")
    if direct is None:
        return None
    candidate = Path(direct)
    if candidate.suffix.lower() not in {"", ".exe"} or not candidate.is_file():
        return None
    return candidate.resolve()


def _discover_claude_executable() -> Path | None:
    direct = shutil.which("claude.exe" if os.name == "nt" else "claude")
    if direct is None:
        return None
    candidate = Path(direct)
    if candidate.suffix.lower() not in {"", ".exe"} or not candidate.is_file():
        return None
    return candidate.resolve()


def _windows_npm_codex_executable() -> Path | None:
    target = _WINDOWS_CODEX_TARGETS.get(platform.machine().lower())
    wrapper = shutil.which("codex.cmd")
    if target is None or wrapper is None:
        return None
    package_name, target_triple = target
    package_root = Path(wrapper).resolve().parent / "node_modules" / "@openai" / "codex"
    candidates = (
        package_root
        / "node_modules"
        / "@openai"
        / package_name
        / "vendor"
        / target_triple
        / "bin"
        / "codex.exe",
        package_root / "vendor" / target_triple / "bin" / "codex.exe",
    )
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def _request_digest(
    prompt: str,
    provider: str,
    model: str | None,
    effort: str,
    mode: str,
    mcp_enabled: bool,
    safety_digest: str | None,
) -> str:
    payload = json.dumps(
        {
            "prompt": prompt,
            "provider": provider,
            "model": model,
            "effort": effort,
            "mode": mode,
            "mcp_enabled": mcp_enabled,
            "safety_digest": safety_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _event_name(event_type: AgentRunEventType) -> str:
    mapping: dict[
        AgentRunEventType,
        Literal[
            "started",
            "thinking",
            "message",
            "status",
            "usage",
            "artifact",
            "completed",
            "failed",
            "cancelled",
        ],
    ] = {
        AgentRunEventType.STARTED: "started",
        AgentRunEventType.REASONING_DELTA: "thinking",
        AgentRunEventType.MESSAGE_DELTA: "message",
        AgentRunEventType.CHECKPOINT: "status",
        AgentRunEventType.USAGE: "usage",
        AgentRunEventType.ARTIFACT: "artifact",
        AgentRunEventType.COMPLETED: "completed",
        AgentRunEventType.FAILED: "failed",
        AgentRunEventType.CANCELLED: "cancelled",
    }
    return mapping[event_type]


def _normalize_codex_effort(effort: str) -> Literal["low", "medium", "high", "xhigh"]:
    if effort in {"normal", "medium"}:
        return "medium"
    if effort == "low":
        return "low"
    if effort == "high":
        return "high"
    if effort == "xhigh":
        return "xhigh"
    raise LocalChatError("thinking_level_invalid")


def _normalize_claude_effort(effort: str) -> ClaudeEffort:
    if effort == "max":
        return "max"
    return _normalize_codex_effort(effort)


def _normalize_mode(mode: str) -> Literal["chat", "build"]:
    if mode == "chat":
        return "chat"
    if mode == "build":
        return "build"
    raise LocalChatError("local_chat_mode_invalid")
