from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from corvus.mvp.api_chat import ApiChatBackend, ApiChatError

NOW = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_openai_api_chat_streams_each_text_delta_without_buffering() -> None:
    body = "\n".join(
        (
            'data: {"type":"response.output_text.delta","delta":"Hello"}',
            "",
            'data: {"type":"response.output_text.delta","delta":" now"}',
            "",
            'data: {"type":"response.completed"}',
            "",
        )
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body, request=request))
    backend = ApiChatBackend(
        provider="openai",
        credential="sk-test-never-log",
        clock=lambda: NOW,
        http_client_factory=lambda: httpx.AsyncClient(transport=transport),
    )

    handle = await backend.start(
        run_id=uuid4(),
        prompt="Say hello",
        model="gpt-5.6-sol",
        effort="high",
        mode="chat",
        mcp_enabled=False,
        idempotency_key="api-chat-1",
    )
    events = [event async for event in backend.events(handle)]

    assert [event.type for event in events] == ["started", "message", "message", "completed"]
    assert [event.payload.get("text") for event in events[1:3]] == ["Hello", " now"]
    assert "sk-test-never-log" not in repr(backend)


@pytest.mark.asyncio
async def test_api_chat_rejects_build_and_mcp_without_a_sandbox_adapter() -> None:
    backend = ApiChatBackend(
        provider="anthropic",
        credential="test-secret-value",
        clock=lambda: NOW,
    )

    with pytest.raises(ApiChatError, match="provider_mode_unavailable"):
        await backend.start(
            run_id=uuid4(),
            prompt="Change files",
            model="claude-sonnet-4-5",
            effort="high",
            mode="build",
            mcp_enabled=True,
            idempotency_key="api-build-denied",
        )
