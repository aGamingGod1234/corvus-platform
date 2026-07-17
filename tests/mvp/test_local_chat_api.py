from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from corvus.infrastructure.agent_runtimes.codex import LocalBuildArtifact
from corvus.mvp import local_chat as local_chat_module
from corvus.mvp.api import create_app
from corvus.mvp.local_chat import (
    LocalChatBackendEvent,
    LocalChatBackendHandle,
    LocalChatService,
)

NOW = datetime(2026, 7, 17, 5, 0, tzinfo=UTC)


class _Backend:
    def __init__(self) -> None:
        self.starts = 0
        self.cancelled: set[UUID] = set()
        self.last_effort: str | None = None

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
        del prompt, model, mode, mcp_enabled, idempotency_key
        self.starts += 1
        self.last_effort = effort
        return LocalChatBackendHandle(id=uuid4(), run_id=run_id)

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        del handle
        events = (
            LocalChatBackendEvent(1, NOW, "started", {"status": "started"}),
            LocalChatBackendEvent(2, NOW, "message", {"text": "safe reply"}),
            LocalChatBackendEvent(3, NOW, "completed", {"status": "completed"}),
        )
        for event in events:
            if event.sequence > after_sequence:
                yield event

    async def cancel(self, handle: LocalChatBackendHandle) -> bool:
        self.cancelled.add(handle.id)
        return True

    def artifact(self, handle: LocalChatBackendHandle) -> LocalBuildArtifact | None:
        del handle
        return None


class _GatedBackend(_Backend):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        del handle
        if after_sequence < 1:
            self.started.set()
            yield LocalChatBackendEvent(1, NOW, "started", {"status": "started"})
        await self.release.wait()
        if after_sequence < 2:
            yield LocalChatBackendEvent(2, NOW, "completed", {"status": "completed"})


class _GatedStartBackend(_Backend):
    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

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
        self.starts += 1
        self.entered.set()
        await self.release.wait()
        self.last_effort = effort
        del prompt, model, mode, mcp_enabled, idempotency_key
        return LocalChatBackendHandle(id=uuid4(), run_id=run_id)


class _SingleConsumerGatedBackend(_Backend):
    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()
        self.event_calls = 0

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        del handle
        self.event_calls += 1
        if self.event_calls > 1:
            return
        if after_sequence < 1:
            yield LocalChatBackendEvent(1, NOW, "started", {"status": "started"})
        await self.release.wait()
        if after_sequence < 2:
            yield LocalChatBackendEvent(2, NOW, "completed", {"status": "completed"})


class _CancellableBackend(_Backend):
    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        if after_sequence < 1:
            yield LocalChatBackendEvent(1, NOW, "started", {"status": "started"})
        await self.release.wait()
        if after_sequence < 2:
            yield LocalChatBackendEvent(2, NOW, "cancelled", {"status": "cancelled"})

    async def cancel(self, handle: LocalChatBackendHandle) -> bool:
        accepted = await super().cancel(handle)
        self.release.set()
        return accepted


class _ArtifactBackend(_Backend):
    def __init__(self, artifact: LocalBuildArtifact) -> None:
        super().__init__()
        self._artifact = artifact

    def artifact(self, handle: LocalChatBackendHandle) -> LocalBuildArtifact | None:
        del handle
        return self._artifact


def _client(
    tmp_path: Path,
    name: str,
    local_chat: LocalChatService,
) -> tuple[TestClient, dict[str, str]]:
    token = f"bootstrap-{name}"
    client = TestClient(
        create_app(
            database=tmp_path / f"{name}.sqlite3",
            bootstrap_token=token,
            session_secret=b"s" * 32,
            local_chat_service=local_chat,
        )
    )
    assert client.post("/api/auth/pair", json={"token": token}).status_code == 200
    session = client.get("/api/auth/session").json()
    return client, {"X-CSRF-Token": session["csrf_token"]}


def _sse_events(body: str) -> list[tuple[str, dict[str, object]]]:
    parsed: list[tuple[str, dict[str, object]]] = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        parsed.append((fields["id"], json.loads(fields["data"])))
    return parsed


@pytest.mark.asyncio
async def test_local_chat_service_streams_first_event_before_terminal(tmp_path: Path) -> None:
    backend = _GatedBackend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    started = await service.start(
        owner="local:user",
        prompt="Hello",
        provider="codex",
        model=None,
        effort="medium",
        mode="chat",
        mcp_enabled=False,
        idempotency_key="stream-once",
    )
    stream = service.events(
        owner="local:user",
        run_id=UUID(str(started["run_id"])),
        cursor=None,
    )

    _cursor, first = await asyncio.wait_for(anext(stream), timeout=0.2)

    assert first.type == "started"
    backend.release.set()
    assert [event.type async for _cursor, event in stream] == ["completed"]


@pytest.mark.asyncio
async def test_local_chat_non_following_poll_returns_after_buffered_events(tmp_path: Path) -> None:
    backend = _GatedBackend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    started = await service.start(
        owner="local:user",
        prompt="Hello",
        provider="codex",
        model=None,
        effort="medium",
        mode="chat",
        mcp_enabled=False,
        idempotency_key="poll-once",
    )
    stream = service.events(
        owner="local:user",
        run_id=UUID(str(started["run_id"])),
        cursor=None,
        follow=False,
    )

    await asyncio.wait_for(backend.started.wait(), timeout=1)
    _cursor, first = await asyncio.wait_for(anext(stream), timeout=1)
    assert first.type == "started"
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=1)
    backend.release.set()


@pytest.mark.asyncio
async def test_local_chat_stream_disconnect_does_not_cancel_provider_pump() -> None:
    backend = _SingleConsumerGatedBackend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    started = await service.start(
        owner="local:user",
        prompt="Hello",
        provider="codex",
        model=None,
        effort="medium",
        mode="chat",
        mcp_enabled=False,
        idempotency_key="disconnect-once",
    )
    run_id = UUID(str(started["run_id"]))
    first_stream = service.events(owner="local:user", run_id=run_id, cursor=None)
    first_cursor, first = await asyncio.wait_for(anext(first_stream), timeout=0.2)
    assert first.type == "started"

    await first_stream.aclose()
    backend.release.set()
    replay = service.events(owner="local:user", run_id=run_id, cursor=first_cursor)

    assert [event.type async for _cursor, event in replay] == ["completed"]
    assert backend.event_calls == 1


@pytest.mark.asyncio
async def test_local_chat_concurrent_subscribers_share_one_provider_pump() -> None:
    backend = _SingleConsumerGatedBackend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    started = await service.start(
        owner="local:user",
        prompt="Hello",
        provider="codex",
        model=None,
        effort="medium",
        mode="chat",
        mcp_enabled=False,
        idempotency_key="two-subscribers",
    )
    run_id = UUID(str(started["run_id"]))
    first_stream = service.events(owner="local:user", run_id=run_id, cursor=None)
    second_stream = service.events(owner="local:user", run_id=run_id, cursor=None)

    first, second = await asyncio.gather(anext(first_stream), anext(second_stream))
    assert first[1].type == second[1].type == "started"
    assert backend.event_calls == 1

    backend.release.set()
    assert [event.type async for _cursor, event in first_stream] == ["completed"]
    assert [event.type async for _cursor, event in second_stream] == ["completed"]


@pytest.mark.asyncio
async def test_local_chat_concurrent_idempotent_starts_launch_one_backend() -> None:
    backend = _GatedStartBackend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    request = {
        "owner": "local:user",
        "prompt": "Hello",
        "provider": "codex",
        "model": None,
        "effort": "medium",
        "mode": "chat",
        "mcp_enabled": False,
        "idempotency_key": "concurrent-once",
    }

    first = asyncio.create_task(service.start(**request))
    await asyncio.wait_for(backend.entered.wait(), timeout=0.2)
    second = asyncio.create_task(service.start(**request))
    await asyncio.sleep(0.01)
    starts_before_release = backend.starts
    backend.release.set()
    first_response, second_response = await asyncio.gather(first, second)

    assert starts_before_release == 1
    assert backend.starts == 1
    assert first_response == second_response


def test_local_chat_requires_csrf_and_idempotently_starts_this_device_run(
    tmp_path: Path,
) -> None:
    backend = _Backend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    client, headers = _client(tmp_path, "owner", service)
    body = {"prompt": "Hello", "effort": "normal"}

    assert client.post("/api/local-chat/runs", json=body).status_code == 403
    first = client.post(
        "/api/local-chat/runs",
        json=body,
        headers={**headers, "Idempotency-Key": "run-once"},
    )
    replay = client.post(
        "/api/local-chat/runs",
        json=body,
        headers={**headers, "Idempotency-Key": "run-once"},
    )
    conflict = client.post(
        "/api/local-chat/runs",
        json={**body, "prompt": "Changed"},
        headers={**headers, "Idempotency-Key": "run-once"},
    )

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert first.json()["model"] == "Codex default"
    assert first.json()["storage"] == "this_device"
    assert backend.starts == 1
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"


def test_local_chat_provider_catalog_is_truthful_and_path_free(tmp_path: Path) -> None:
    service = LocalChatService(backend=_Backend(), cursor_secret=b"c" * 32, clock=lambda: NOW)
    client, _headers = _client(tmp_path, "catalog", service)

    response = client.get("/api/local-chat/providers")

    assert response.status_code == 200
    catalog = {entry["id"]: entry for entry in response.json()}
    assert catalog["codex"]["status"] == "ready"
    assert catalog["claude"]["status"] == "unavailable"
    assert catalog["gemini"]["status"] == "preview"
    assert catalog["grok"]["status"] == "preview"
    assert "path" not in response.text.lower()


def test_local_chat_dispatches_to_selected_ready_provider(tmp_path: Path) -> None:
    codex = _Backend()
    claude = _Backend()
    service = LocalChatService(
        backends={"codex": codex, "claude": claude},
        cursor_secret=b"c" * 32,
        clock=lambda: NOW,
    )
    client, headers = _client(tmp_path, "providers", service)

    response = client.post(
        "/api/local-chat/runs",
        json={
            "prompt": "Explain this code",
            "provider": "claude",
            "model": "sonnet",
            "effort": "max",
            "mode": "chat",
            "mcp_enabled": False,
        },
        headers={**headers, "Idempotency-Key": "claude-once"},
    )

    assert response.status_code == 202
    assert response.json()["provider"] == "claude"
    assert response.json()["model"] == "sonnet"
    assert codex.starts == 0
    assert claude.starts == 1
    assert claude.last_effort == "max"

    unsupported = client.post(
        "/api/local-chat/runs",
        json={
            "prompt": "Explain this code",
            "provider": "codex",
            "effort": "max",
        },
        headers={**headers, "Idempotency-Key": "codex-max"},
    )
    assert unsupported.status_code == 503
    assert unsupported.json()["detail"] == "provider_effort_unavailable"
    assert codex.starts == 0


def test_local_build_download_is_owner_scoped(tmp_path: Path) -> None:
    archive = tmp_path / "corvus-build.zip"
    archive.write_bytes(b"PK-safe-build")
    artifact = LocalBuildArtifact(
        path=archive,
        download_name="corvus-build.zip",
        sha256_digest="a" * 64,
        size_bytes=archive.stat().st_size,
    )
    service = LocalChatService(
        backend=_ArtifactBackend(artifact),
        cursor_secret=b"c" * 32,
        clock=lambda: NOW,
    )
    owner, headers = _client(tmp_path, "builder", service)
    stranger, _stranger_headers = _client(tmp_path, "not-builder", service)
    started = owner.post(
        "/api/local-chat/runs",
        json={
            "prompt": "Build a small site",
            "provider": "codex",
            "effort": "high",
            "mode": "build",
            "mcp_enabled": False,
        },
        headers={**headers, "Idempotency-Key": "build-once"},
    )

    assert started.status_code == 202
    assert started.json()["mode"] == "build"
    run_id = started.json()["run_id"]
    owner.get(f"/api/local-chat/runs/{run_id}/events?follow=false")
    download = owner.get(f"/api/local-chat/runs/{run_id}/artifact")
    assert download.status_code == 200
    assert download.content == b"PK-safe-build"
    assert download.headers["content-disposition"].endswith('filename="corvus-build.zip"')
    assert stranger.get(f"/api/local-chat/runs/{run_id}/artifact").status_code == 404


def test_local_chat_owner_scopes_sse_cursor_and_cancel(tmp_path: Path) -> None:
    backend = _Backend()
    service = LocalChatService(backend=backend, cursor_secret=b"c" * 32, clock=lambda: NOW)
    owner, owner_headers = _client(tmp_path, "owner", service)
    stranger, stranger_headers = _client(tmp_path, "stranger", service)
    started = owner.post(
        "/api/local-chat/runs",
        json={"prompt": "Do not expose sk-secret"},
        headers={**owner_headers, "Idempotency-Key": "owner-run"},
    ).json()
    run_id = started["run_id"]

    stream = owner.get(f"/api/local-chat/runs/{run_id}/events?follow=false")
    events = _sse_events(stream.text)
    cursor = events[0][0]

    assert stream.status_code == 200
    assert [event[1]["type"] for event in events] == ["started", "message", "completed"]
    assert "sk-secret" not in stream.text
    assert (
        owner.get(
            f"/api/local-chat/runs/{run_id}/events?follow=false",
            headers={"Last-Event-ID": cursor + "tampered"},
        ).status_code
        == 400
    )
    assert stranger.get(f"/api/local-chat/runs/{run_id}/events?follow=false").status_code == 404
    cancellation_backend = _CancellableBackend()
    cancellation_service = LocalChatService(
        backend=cancellation_backend,
        cursor_secret=b"d" * 32,
        clock=lambda: NOW,
    )
    cancellation_owner, cancellation_headers = _client(
        tmp_path,
        "cancellation-owner",
        cancellation_service,
    )
    cancellation_stranger, cancellation_stranger_headers = _client(
        tmp_path,
        "cancellation-stranger",
        cancellation_service,
    )
    cancellable = cancellation_owner.post(
        "/api/local-chat/runs",
        json={"prompt": "Wait for cancellation"},
        headers={**cancellation_headers, "Idempotency-Key": "cancel-run"},
    ).json()
    cancel_run_id = cancellable["run_id"]
    assert (
        cancellation_stranger.post(
            f"/api/local-chat/runs/{cancel_run_id}/cancel",
            headers=cancellation_stranger_headers,
        ).status_code
        == 404
    )

    cancelled = cancellation_owner.post(
        f"/api/local-chat/runs/{cancel_run_id}/cancel",
        headers=cancellation_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json() == {
        "run_id": cancel_run_id,
        "state": "cancelled",
        "accepted": True,
        "reason_code": "agent_run_cancelled",
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows Codex launcher layout")
def test_default_local_chat_prefers_npm_native_codex_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    npm_root = tmp_path / "npm"
    wrapper = npm_root / "codex.cmd"
    packaged = tmp_path / "WindowsApps" / "codex.exe"
    native = (
        npm_root
        / "node_modules"
        / "@openai"
        / "codex"
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    for candidate in (wrapper, packaged, native):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(b"codex")

    candidates = {
        "codex.exe": os.fspath(packaged),
        "codex.cmd": os.fspath(wrapper),
        "codex": os.fspath(wrapper),
    }
    monkeypatch.setattr(
        local_chat_module.shutil,
        "which",
        lambda name: candidates.get(name),
    )

    service = local_chat_module.build_default_local_chat_service(
        scratch_root=tmp_path / "runs",
        cursor_secret=b"c" * 32,
    )

    assert service is not None
    backend = service._backend
    assert isinstance(backend, local_chat_module.CodexLocalChatBackend)
    assert backend._adapter._executable == native.resolve()
