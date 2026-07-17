from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

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

    async def start(
        self,
        *,
        run_id: UUID,
        prompt: str,
        model: str | None,
        effort: str,
        idempotency_key: str,
    ) -> LocalChatBackendHandle:
        del prompt, model, effort, idempotency_key
        self.starts += 1
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
    cancellable = owner.post(
        "/api/local-chat/runs",
        json={"prompt": "Wait for cancellation"},
        headers={**owner_headers, "Idempotency-Key": "cancel-run"},
    ).json()
    cancel_run_id = cancellable["run_id"]
    assert (
        stranger.post(
            f"/api/local-chat/runs/{cancel_run_id}/cancel", headers=stranger_headers
        ).status_code
        == 404
    )

    cancelled = owner.post(f"/api/local-chat/runs/{cancel_run_id}/cancel", headers=owner_headers)
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
