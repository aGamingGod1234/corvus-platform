from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import platform
import shutil
import tomllib
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
from corvus.mvp.trusted_cli import TrustedCli, TrustedCliError
from corvus.safe_process import path_is_link_or_reparse

_LOCAL_RUNTIME_SCOPE = UUID("39fef4c9-baf0-40c7-bada-9c2bd9165445")
_RUN_DEADLINE = timedelta(seconds=120)
_MAX_OUTPUT_BYTES = 100_000
_PROJECT_COPY_MAX_FILES = 20_000
_PROJECT_COPY_MAX_ENTRIES = 30_000
_PROJECT_COPY_MAX_BYTES = 512 * 1024 * 1024
_PROJECT_COPY_CHUNK_BYTES = 1024 * 1024
_PROJECT_COPY_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".turbo",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)
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
    working_directory: str = ""


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
        readiness_probes: Mapping[str, Callable[[], bool]] | None = None,
        cursor_secret: bytes,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(cursor_secret) < 32:
            raise ValueError("local_chat_cursor_secret_too_short")
        if backend is not None and backends is not None:
            raise ValueError("local_chat_backend_ambiguous")
        configured = dict(backends or ({"codex": backend} if backend is not None else {}))
        self._backends = configured
        self._readiness_probes = dict(readiness_probes or {})
        self._owner_backends: dict[tuple[str, str], LocalChatBackend] = {}
        self._backend = configured.get("codex") or next(iter(configured.values()), None)
        self._cursor_secret = cursor_secret
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runs: dict[UUID, _RunRecord] = {}
        self._idempotency: dict[tuple[str, str], UUID] = {}
        self._start_locks: dict[tuple[str, str], asyncio.Lock] = {}

    def register_owner_backend(
        self,
        owner: str,
        provider: str,
        backend: LocalChatBackend,
    ) -> None:
        if not owner.strip() or not provider.strip():
            raise ValueError("owner_backend_scope_invalid")
        self._owner_backends[(owner, provider)] = backend

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
        idempotency_prompt: str | None = None,
        source_directory: Path | None = None,
    ) -> dict[str, object]:
        owner_backend = self._owner_backends.get((owner, provider))
        backend = owner_backend or self._backends.get(provider)
        if backend is None:
            raise LocalChatError("provider_unavailable")
        readiness_probe = self._readiness_probes.get(provider)
        if owner_backend is None and readiness_probe is not None and not readiness_probe():
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
            prompt if idempotency_prompt is None else idempotency_prompt,
            provider,
            model,
            effort,
            mode,
            mcp_enabled,
            safety_digest,
            os.fspath(source_directory) if source_directory is not None else None,
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
                source_directory=source_directory,
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
        source_directory: Path | None,
    ) -> dict[str, object]:
        replay_id = self._idempotency.get(idempotency_scope)
        if replay_id is not None:
            replay = self._runs[replay_id]
            if replay.request_digest != request_digest:
                raise LocalChatConflict("idempotency_conflict")
            return dict(replay.response)
        run_id = uuid4()
        try:
            if source_directory is None:
                handle = await backend.start(
                    run_id=run_id,
                    prompt=prompt,
                    model=model,
                    effort=effort,
                    mode=mode,
                    mcp_enabled=mcp_enabled,
                    idempotency_key=f"{owner}:{idempotency_key}",
                )
            else:
                start_in_workspace = getattr(backend, "start_in_workspace", None)
                if start_in_workspace is None:
                    raise LocalChatError("provider_workspace_unavailable")
                handle = await start_in_workspace(
                    run_id=run_id,
                    prompt=prompt,
                    model=model,
                    effort=effort,
                    mode=mode,
                    mcp_enabled=mcp_enabled,
                    idempotency_key=f"{owner}:{idempotency_key}",
                    source_directory=source_directory,
                )
        except (CodexAdapterError, ClaudeAdapterError) as error:
            raise LocalChatError(error.reason_code) from error
        except RuntimeError as error:
            reason_code = getattr(error, "reason_code", None) or str(error)
            raise LocalChatError(reason_code or "provider_start_failed") from error
        response: dict[str, object] = {
            "run_id": str(run_id),
            "handle_id": str(handle.id),
            "state": "running",
            "provider": provider,
            "model": model
            or (
                (_discover_codex_effective_model() or "Codex configured model")
                if provider == "codex"
                else "Claude Sonnet"
            ),
            "mode": mode,
            "storage": "this_device",
            "created_at": self._clock().isoformat(),
            "working_directory": handle.working_directory,
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
                "secret_screening": artifact.secret_screening,
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
        codex_detected = "codex" in self._backends
        codex_probe = self._readiness_probes.get("codex")
        codex_ready = codex_detected and (codex_probe is None or codex_probe())
        claude_detected = "claude" in self._backends
        claude_probe = self._readiness_probes.get("claude")
        claude_ready = claude_detected and (claude_probe is None or claude_probe())
        entries = build_provider_catalog(
            codex_available=codex_ready,
            codex_detected=codex_detected,
            claude_available=claude_ready,
            claude_detected=claude_detected,
            codex_effective_model=_discover_codex_effective_model(),
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
    def __init__(
        self, adapter: CodexCliAdapter, clock: Callable[[], datetime], scratch_root: Path
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        self._scratch_root = scratch_root.resolve(strict=False)
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
        return await self._start(
            run_id=run_id,
            prompt=prompt,
            model=model,
            effort=effort,
            mode=mode,
            mcp_enabled=mcp_enabled,
            idempotency_key=idempotency_key,
            source_directory=None,
        )

    async def start_in_workspace(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
        source_directory: Path,
    ) -> LocalChatBackendHandle:
        return await self._start(
            run_id=run_id,
            prompt=prompt,
            model=model,
            effort=effort,
            mode=mode,
            mcp_enabled=mcp_enabled,
            idempotency_key=idempotency_key,
            source_directory=source_directory,
        )

    async def _start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
        source_directory: Path | None,
    ) -> LocalChatBackendHandle:
        binding = await self._provider_binding()
        workspace = None
        if source_directory is not None:
            workspace = self._scratch_root / str(run_id)
            _copy_project(source_directory, workspace)
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
                workspace=workspace,
            ),
        )
        self._handles[result.handle.id] = result.handle
        return LocalChatBackendHandle(
            id=result.handle.id,
            run_id=run_id,
            working_directory=str((self._scratch_root / str(run_id)).resolve(strict=False)),
        )

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
    def __init__(
        self, adapter: ClaudeCliAdapter, clock: Callable[[], datetime], scratch_root: Path
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        self._scratch_root = scratch_root.resolve(strict=False)
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
        return await self._start(
            run_id=run_id,
            prompt=prompt,
            model=model,
            effort=effort,
            mode=mode,
            mcp_enabled=mcp_enabled,
            idempotency_key=idempotency_key,
            source_directory=None,
        )

    async def start_in_workspace(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
        source_directory: Path,
    ) -> LocalChatBackendHandle:
        return await self._start(
            run_id=run_id,
            prompt=prompt,
            model=model,
            effort=effort,
            mode=mode,
            mcp_enabled=mcp_enabled,
            idempotency_key=idempotency_key,
            source_directory=source_directory,
        )

    async def _start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        mode: str,
        mcp_enabled: bool,
        idempotency_key: str,
        source_directory: Path | None,
    ) -> LocalChatBackendHandle:
        if mode != "chat" or mcp_enabled:
            raise ClaudeAdapterError("claude_mode_unavailable")
        binding = await self._provider_binding()
        workspace = None
        if source_directory is not None:
            workspace = self._scratch_root / str(run_id)
            _copy_project(source_directory, workspace)
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
                workspace=workspace,
            ),
        )
        self._handles[result.handle.id] = result.handle
        return LocalChatBackendHandle(
            id=result.handle.id,
            run_id=run_id,
            working_directory=str((self._scratch_root / str(run_id)).resolve(strict=False)),
        )

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
) -> LocalChatService:
    codex_executable = _discover_codex_executable()
    claude_executable = _discover_claude_executable()

    def clock() -> datetime:
        return datetime.now(UTC)

    backends: dict[str, LocalChatBackend] = {}
    readiness_probes: dict[str, Callable[[], bool]] = {}
    if codex_executable is not None:
        codex_adapter = CodexCliAdapter(
            executable=codex_executable,
            version="local",
            scratch_root=scratch_root / "codex",
            approved_workspace_roots=(scratch_root / "codex",),
            clock=clock,
        )
        backends["codex"] = CodexLocalChatBackend(codex_adapter, clock, scratch_root / "codex")
        readiness_probes["codex"] = lambda: _verify_codex_ready(
            codex_executable,
            scratch_root.parent,
        )
    if claude_executable is not None:
        claude_adapter = ClaudeCliAdapter(
            executable=claude_executable,
            version="local",
            scratch_root=scratch_root / "claude",
            clock=clock,
        )
        backends["claude"] = ClaudeLocalChatBackend(claude_adapter, clock, scratch_root / "claude")
        readiness_probes["claude"] = lambda: _verify_claude_ready(
            claude_executable,
            scratch_root.parent,
        )
    return LocalChatService(
        backends=backends,
        readiness_probes=readiness_probes,
        cursor_secret=cursor_secret,
        clock=clock,
    )


def _verify_codex_ready(executable: Path, cwd: Path) -> bool:
    """Verify both the discovered binary and the user's local Codex login."""

    try:
        cli = TrustedCli(executable)
        version = cli.run(cwd, ("--version",), timeout=10)
        if version.returncode != 0 or not version.stdout.strip():
            return False
        login = cli.run(cwd, ("login", "status"), timeout=10)
        return login.returncode == 0
    except (OSError, TrustedCliError):
        return False


def _verify_claude_ready(executable: Path, cwd: Path) -> bool:
    """Verify the Claude binary and login without exposing account details."""

    try:
        cli = TrustedCli(executable)
        version = cli.run(cwd, ("--version",), timeout=10)
        if version.returncode != 0 or not version.stdout.strip():
            return False
        auth = cli.run(cwd, ("auth", "status"), timeout=10)
        return auth.returncode == 0
    except (OSError, TrustedCliError):
        return False


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


def discover_codex_executable() -> Path | None:
    """Return the trusted local Codex executable used by desktop runtimes."""
    return _discover_codex_executable()


def _discover_claude_executable() -> Path | None:
    direct = shutil.which("claude.exe" if os.name == "nt" else "claude")
    if direct is None:
        return None
    candidate = Path(direct)
    if candidate.suffix.lower() not in {"", ".exe"} or not candidate.is_file():
        return None
    return candidate.resolve()


def _discover_codex_effective_model() -> str | None:
    config_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    try:
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    model = config.get("model")
    if not isinstance(model, str):
        return None
    normalized = model.strip()
    return normalized if 0 < len(normalized) <= 100 else None


def _windows_npm_codex_executable() -> Path | None:
    target = _WINDOWS_CODEX_TARGETS.get(platform.machine().lower())
    if target is None:
        return None
    package_name, target_triple = target
    wrapper_candidates: list[Path] = []
    discovered_wrapper = shutil.which("codex.cmd")
    if discovered_wrapper is not None:
        wrapper_candidates.append(Path(discovered_wrapper))
    appdata = os.environ.get("APPDATA")
    if appdata:
        wrapper_candidates.append(Path(appdata) / "npm" / "codex.cmd")
    candidates: list[Path] = []
    for wrapper in dict.fromkeys(wrapper_candidates):
        if not wrapper.is_file():
            continue
        package_root = wrapper.resolve().parent / "node_modules" / "@openai" / "codex"
        candidates.extend(
            (
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
    source_directory: str | None,
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
            "source_directory": source_directory,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _copy_project(source_directory: Path, destination: Path) -> None:
    try:
        source = source_directory.resolve(strict=True)
    except OSError as error:
        raise LocalChatError("local_chat_project_unavailable") from error
    if not source.is_dir() or path_is_link_or_reparse(source):
        raise LocalChatError("local_chat_project_unavailable")
    files_to_copy: list[tuple[Path, Path, int]] = []
    directories_to_create: list[Path] = []
    total_bytes = 0
    try:
        for root, directories, files in os.walk(source, topdown=True):
            root_path = Path(root)
            if path_is_link_or_reparse(root_path):
                raise LocalChatError("local_chat_project_links_forbidden")
            relative_root = root_path.relative_to(source)
            directories_to_create.append(relative_root)
            if len(directories_to_create) + len(files_to_copy) > _PROJECT_COPY_MAX_ENTRIES:
                raise LocalChatError("local_chat_project_too_large")
            retained_directories: list[str] = []
            for name in directories:
                child = root_path / name
                if path_is_link_or_reparse(child):
                    raise LocalChatError("local_chat_project_links_forbidden")
                if name not in _PROJECT_COPY_IGNORED_DIRECTORIES:
                    retained_directories.append(name)
            directories[:] = retained_directories
            for name in files:
                source_file = root_path / name
                if path_is_link_or_reparse(source_file):
                    raise LocalChatError("local_chat_project_links_forbidden")
                try:
                    size = source_file.stat().st_size
                except OSError as error:
                    raise LocalChatError("local_chat_project_copy_failed") from error
                if not source_file.is_file():
                    raise LocalChatError("local_chat_project_unavailable")
                total_bytes += size
                files_to_copy.append((source_file, relative_root / name, size))
                if (
                    len(files_to_copy) > _PROJECT_COPY_MAX_FILES
                    or len(directories_to_create) + len(files_to_copy) > _PROJECT_COPY_MAX_ENTRIES
                    or total_bytes > _PROJECT_COPY_MAX_BYTES
                ):
                    raise LocalChatError("local_chat_project_too_large")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir()
        for relative_directory in directories_to_create:
            (destination / relative_directory).mkdir(parents=True, exist_ok=True)
        copied_bytes = 0
        for source_file, relative_file, expected_size in files_to_copy:
            if path_is_link_or_reparse(source_file) or source_file.stat().st_size != expected_size:
                raise LocalChatError("local_chat_project_changed_during_copy")
            target_file = destination / relative_file
            with source_file.open("rb") as source_stream, target_file.open("xb") as target_stream:
                while chunk := source_stream.read(_PROJECT_COPY_CHUNK_BYTES):
                    copied_bytes += len(chunk)
                    if copied_bytes > _PROJECT_COPY_MAX_BYTES:
                        raise LocalChatError("local_chat_project_too_large")
                    target_stream.write(chunk)
            shutil.copystat(source_file, target_file, follow_symlinks=False)
    except LocalChatError:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    except OSError as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise LocalChatError("local_chat_project_copy_failed") from error


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
