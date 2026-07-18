from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

import httpx

from corvus.mvp.local_chat import (
    LocalChatBackendEvent,
    LocalChatBackendHandle,
)

ApiProvider = Literal["openai", "anthropic", "gemini", "xai"]
_HTTP_TIMEOUT_SECONDS = 120.0
_ENDPOINTS: dict[ApiProvider, str] = {
    "openai": "https://api.openai.com/v1/responses",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "xai": "https://api.x.ai/v1/chat/completions",
}


class ApiChatError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _ApiRequest:
    prompt: str
    model: str
    effort: str


class ApiChatBackend:
    """Streaming Chat-only backend. It never receives filesystem or MCP authority."""

    def __init__(
        self,
        *,
        provider: ApiProvider,
        credential: str,
        clock: Callable[[], datetime],
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        if not credential.strip():
            raise ApiChatError("provider_credential_missing")
        self._provider = provider
        self._credential = credential.strip()
        self._clock = clock
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=False)
        )
        self._requests: dict[UUID, _ApiRequest] = {}
        self._cancelled: set[UUID] = set()
        self._active_responses: dict[UUID, httpx.Response] = {}

    def __repr__(self) -> str:
        return f"<ApiChatBackend provider={self._provider}>"

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
        del idempotency_key
        if mode != "chat" or mcp_enabled:
            raise ApiChatError("provider_mode_unavailable")
        if model is None or not model.strip():
            raise ApiChatError("provider_model_required")
        if self._provider == "openai":
            effort = "medium" if effort == "normal" else effort
            if effort not in {"low", "medium", "high", "xhigh"}:
                raise ApiChatError("provider_effort_unavailable")
        handle = LocalChatBackendHandle(id=run_id, run_id=run_id)
        self._requests[handle.id] = _ApiRequest(
            prompt=prompt,
            model=model.strip(),
            effort=effort,
        )
        return handle

    async def events(
        self,
        handle: LocalChatBackendHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[LocalChatBackendEvent]:
        request = self._requests.get(handle.id)
        if request is None:
            raise ApiChatError("provider_handle_unknown")
        sequence = 1
        if sequence > after_sequence:
            yield LocalChatBackendEvent(sequence, self._clock(), "started", {"status": "started"})
        if handle.id in self._cancelled:
            sequence += 1
            if sequence > after_sequence:
                yield LocalChatBackendEvent(
                    sequence, self._clock(), "cancelled", {"status": "cancelled"}
                )
            return
        request_failed = False
        stream_completed = False
        try:
            async with self._http_client_factory() as client:
                if handle.id in self._cancelled:
                    sequence += 1
                    if sequence > after_sequence:
                        yield LocalChatBackendEvent(
                            sequence, self._clock(), "cancelled", {"status": "cancelled"}
                        )
                    return
                async with client.stream(
                    "POST",
                    self._url(request.model),
                    headers=self._headers(),
                    json=self._body(request),
                ) as response:
                    self._active_responses[handle.id] = response
                    try:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if handle.id in self._cancelled:
                                break
                            terminal_state = self._terminal_state(line)
                            if terminal_state == "failed":
                                request_failed = True
                                break
                            text = self._text_delta(line)
                            if text:
                                sequence += 1
                                if sequence > after_sequence:
                                    yield LocalChatBackendEvent(
                                        sequence, self._clock(), "message", {"text": text}
                                    )
                            if terminal_state == "completed":
                                stream_completed = True
                                break
                    finally:
                        self._active_responses.pop(handle.id, None)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            request_failed = True
        if handle.id in self._cancelled:
            sequence += 1
            if sequence > after_sequence:
                yield LocalChatBackendEvent(
                    sequence, self._clock(), "cancelled", {"status": "cancelled"}
                )
            return
        if request_failed or not stream_completed:
            sequence += 1
            if sequence > after_sequence:
                yield LocalChatBackendEvent(
                    sequence,
                    self._clock(),
                    "failed",
                    {"reason_code": "provider_request_failed"},
                )
            return
        sequence += 1
        if sequence > after_sequence:
            yield LocalChatBackendEvent(
                sequence, self._clock(), "completed", {"status": "completed"}
            )

    async def cancel(self, handle: LocalChatBackendHandle) -> bool:
        if handle.id not in self._requests:
            raise ApiChatError("provider_handle_unknown")
        self._cancelled.add(handle.id)
        response = self._active_responses.get(handle.id)
        if response is not None:
            await response.aclose()
        return True

    def artifact(self, handle: LocalChatBackendHandle) -> None:
        if handle.id not in self._requests:
            raise ApiChatError("provider_handle_unknown")
        return None

    def _url(self, model: str) -> str:
        if self._provider == "gemini":
            return f"{_ENDPOINTS['gemini']}/models/{model}:streamGenerateContent?alt=sse"
        return _ENDPOINTS[self._provider]

    def _headers(self) -> dict[str, str]:
        if self._provider == "anthropic":
            return {
                "x-api-key": self._credential,
                "anthropic-version": "2023-06-01",
                "Accept": "text/event-stream",
            }
        if self._provider == "gemini":
            return {"x-goog-api-key": self._credential, "Accept": "text/event-stream"}
        return {
            "Authorization": f"Bearer {self._credential}",
            "Accept": "text/event-stream",
        }

    def _body(self, request: _ApiRequest) -> dict[str, object]:
        if self._provider == "openai":
            body: dict[str, object] = {
                "model": request.model,
                "input": request.prompt,
                "stream": True,
            }
            if _supports_openai_reasoning_effort(request.model):
                body["reasoning"] = {"effort": request.effort}
            return body
        if self._provider == "anthropic":
            return {
                "model": request.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": request.prompt}],
                "stream": True,
            }
        if self._provider == "gemini":
            return {"contents": [{"role": "user", "parts": [{"text": request.prompt}]}]}
        return {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": True,
        }

    def _text_delta(self, line: str) -> str | None:
        if not line.startswith("data:"):
            return None
        raw = line.removeprefix("data:").strip()
        if not raw or raw == "[DONE]":
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        if self._provider == "openai":
            return (
                cast(str | None, payload.get("delta"))
                if payload.get("type") == "response.output_text.delta"
                else None
            )
        if self._provider == "anthropic":
            delta = payload.get("delta")
            return cast(str | None, delta.get("text")) if isinstance(delta, dict) else None
        if self._provider == "gemini":
            return _gemini_text(payload)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return None
        delta = choices[0].get("delta")
        return cast(str | None, delta.get("content")) if isinstance(delta, dict) else None

    def _terminal_state(self, line: str) -> Literal["completed", "failed"] | None:
        if not line.startswith("data:"):
            return None
        raw = line.removeprefix("data:").strip()
        if not raw:
            return None
        if raw == "[DONE]":
            return "completed" if self._provider == "xai" else None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        if self._provider == "openai":
            event_type = payload.get("type")
            if event_type == "response.completed":
                return "completed"
            if event_type in {"response.failed", "response.incomplete"}:
                return "failed"
            return None
        if self._provider == "anthropic":
            event_type = payload.get("type")
            if event_type == "message_stop":
                return "completed"
            return "failed" if event_type == "error" else None
        if self._provider == "gemini":
            candidates = payload.get("candidates")
            if (
                not isinstance(candidates, list)
                or not candidates
                or not isinstance(candidates[0], dict)
            ):
                return None
            reason = candidates[0].get("finishReason")
            if not isinstance(reason, str) or not reason:
                return None
            return "completed" if reason == "STOP" else "failed"
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return None
        reason = choices[0].get("finish_reason")
        if not isinstance(reason, str) or not reason:
            return None
        return "completed" if reason == "stop" else "failed"


def _supports_openai_reasoning_effort(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith(("gpt-5", "gpt-oss-", "codex-")) or bool(
        re.fullmatch(r"o\d+(?:[-.].+)?", normalized)
    )


def _gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return None
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], dict):
        return None
    text = parts[0].get("text")
    return text if isinstance(text, str) else None
