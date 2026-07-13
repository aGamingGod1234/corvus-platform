from __future__ import annotations

import ipaddress
import json
import socket
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx

from corvus.models import ModelChunk, ModelProvider, ModelRequest


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def _validated_provider_destination(
    url: str,
    *,
    local: bool,
    resolved_addresses: tuple[str, ...] | None = None,
) -> tuple[str, str, tuple[str, ...]]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ProviderError("provider URL is invalid") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ProviderError("provider URL must use HTTP or HTTPS")
    if not local and parsed.scheme != "https":
        raise ProviderError("cloud provider URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ProviderError("provider URL cannot contain credentials")
    if parsed.query or parsed.fragment:
        raise ProviderError("provider URL cannot contain a query or fragment")
    host = parsed.hostname
    if host is None:
        raise ProviderError("provider URL must contain a host")

    addresses = resolved_addresses
    if addresses is None:
        try:
            addresses = tuple(
                sorted(
                    {
                        str(item[4][0]).split("%", maxsplit=1)[0]
                        for item in socket.getaddrinfo(
                            host,
                            port or (443 if parsed.scheme == "https" else 80),
                            type=socket.SOCK_STREAM,
                        )
                    }
                )
            )
        except OSError as exc:
            raise ProviderError("provider host could not be resolved", retryable=True) from exc
    if not addresses:
        raise ProviderError("provider host resolved to no addresses")

    try:
        parsed_addresses = tuple(
            ipaddress.ip_address(address.split("%", maxsplit=1)[0]) for address in addresses
        )
    except ValueError as exc:
        raise ProviderError("provider host resolved to an invalid address") from exc

    if local:
        for address in parsed_addresses:
            allowed = address.is_loopback or (
                address.is_private
                and not address.is_link_local
                and not address.is_unspecified
                and not address.is_multicast
                and not address.is_reserved
            )
            if not allowed:
                raise ProviderError(
                    "local provider host must resolve only to local/private addresses"
                )
    elif any(not address.is_global for address in parsed_addresses):
        raise ProviderError("cloud provider host must resolve only to globally routable addresses")
    return url, host, tuple(str(address) for address in parsed_addresses)


def validate_provider_url(
    url: str,
    *,
    local: bool,
    resolved_addresses: tuple[str, ...] | None = None,
) -> str:
    validated, _, _ = _validated_provider_destination(
        url,
        local=local,
        resolved_addresses=resolved_addresses,
    )
    return validated


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        expected_host: str,
        addresses: tuple[str, ...],
        *,
        delegate: httpcore.AsyncNetworkBackend | Any | None = None,
    ) -> None:
        self.expected_host = expected_host.casefold()
        self.addresses = addresses
        self.delegate = delegate or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if host.casefold() != self.expected_host:
            raise ProviderError("provider transport host mismatch")
        last_error: BaseException | None = None
        for address in self.addresses:
            try:
                return await self.delegate.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ProviderError("provider transport has no validated address")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise ProviderError("provider Unix sockets are forbidden")

    async def sleep(self, seconds: float) -> None:
        await self.delegate.sleep(seconds)


def _pinned_transport(url: str, *, local: bool) -> httpx.AsyncHTTPTransport:
    _, host, addresses = _validated_provider_destination(url, local=local)
    transport = httpx.AsyncHTTPTransport(trust_env=False, retries=0)
    transport._pool._network_backend = _PinnedNetworkBackend(
        host,
        addresses,
    )
    return transport


class ModelProviderClient(ABC):
    def __init__(self, config: ModelProvider, secret: str | None = None) -> None:
        self.config = config
        self.secret = secret

    @abstractmethod
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        raise NotImplementedError

    async def health(self) -> bool:
        return True


class FakeProvider(ModelProviderClient):
    def __init__(self, chunks: list[ModelChunk] | None = None) -> None:
        super().__init__(
            ModelProvider(
                name="fake", kind="ollama", base_url="memory://", model="deterministic", local=True
            )
        )
        self.chunks = chunks or [ModelChunk(type="text", text="deterministic response")]

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        del request
        for chunk in self.chunks:
            yield chunk
        yield ModelChunk(type="done")


class HttpProvider(ModelProviderClient):
    def _headers(self) -> dict[str, str]:
        if self.config.kind == "anthropic":
            return {
                "x-api-key": self.secret or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        if self.config.kind == "gemini":
            return {"content-type": "application/json"}
        return {
            "authorization": f"Bearer {self.secret}" if self.secret else "",
            "content-type": "application/json",
        }

    def _endpoint_and_payload(self, request: ModelRequest) -> tuple[str, dict[str, Any]]:
        messages = [message.model_dump(mode="json") for message in request.messages]
        base = validate_provider_url(
            self.config.base_url,
            local=self.config.local,
        ).rstrip("/")
        if self.config.kind == "openai":
            payload: dict[str, Any] = {
                "model": self.config.model,
                "input": messages,
                "stream": True,
                "tools": [
                    {
                        "type": "function",
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    }
                    for t in request.tools
                ],
            }
            if self.config.reasoning_effort is not None:
                payload["reasoning"] = {"effort": self.config.reasoning_effort}
            return f"{base}/responses", payload
        if self.config.kind in {"openai_compatible", "openrouter"}:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "stream": True,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.input_schema,
                        },
                    }
                    for t in request.tools
                ],
            }
            # OpenAI-compatible endpoints are deliberately left at their configured default:
            # their support cannot be inferred safely. OpenRouter documents the unified object.
            if self.config.kind == "openrouter" and self.config.reasoning_effort is not None:
                payload["reasoning"] = {"effort": self.config.reasoning_effort}
            return f"{base}/chat/completions", payload
        if self.config.kind == "anthropic":
            system = "\n".join(m.content for m in request.messages if m.role == "system")
            body = [m for m in messages if m["role"] != "system"]
            payload = {
                "model": self.config.model,
                "system": system,
                "messages": body,
                "max_tokens": request.max_output_tokens or 4096,
                "stream": True,
            }
            if self.config.reasoning_effort is not None:
                payload["output_config"] = {"effort": self.config.reasoning_effort}
            return f"{base}/messages", payload
        if self.config.kind == "gemini":
            payload = {
                "contents": [
                    {
                        "role": "model" if m.role == "assistant" else "user",
                        "parts": [{"text": m.content}],
                    }
                    for m in request.messages
                    if m.role != "system"
                ],
                "systemInstruction": {
                    "parts": [
                        {
                            "text": "\n".join(
                                m.content for m in request.messages if m.role == "system"
                            )
                        }
                    ]
                },
            }
            if self.config.reasoning_effort is not None:
                payload["generationConfig"] = {
                    "thinkingConfig": {"thinkingLevel": self.config.reasoning_effort}
                }
            return f"{base}/models/{self.config.model}:streamGenerateContent", payload
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }
        if self.config.reasoning_effort is not None:
            payload["think"] = self.config.reasoning_effort
        return f"{base}/api/chat", payload

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelChunk]:
        url, payload = self._endpoint_and_payload(request)
        params = {"key": self.secret} if self.config.kind == "gemini" and self.secret else None
        transport = _pinned_transport(url, local=self.config.local)
        try:
            async with httpx.AsyncClient(
                timeout=60,
                follow_redirects=False,
                transport=transport,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST", url, headers=self._headers(), params=params, json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.removeprefix("data:").strip()
                        if not line or line == "[DONE]":
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        text = self._extract_text(data)
                        if text:
                            yield ModelChunk(type="text", text=text)
                        tool_call = self._extract_tool_call(data)
                        if tool_call:
                            yield ModelChunk(type="tool_call", data=tool_call)
                        yield ModelChunk(type="usage", data=self._extract_usage(data))
        except httpx.HTTPStatusError as exc:
            retryable = (
                exc.response.status_code in {408, 409, 429} or exc.response.status_code >= 500
            )
            raise ProviderError(
                f"provider returned HTTP {exc.response.status_code}", retryable=retryable
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("provider transport error", retryable=True) from exc
        yield ModelChunk(type="done")

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if data.get("type") in {"response.output_text.delta", "content_block_delta"}:
            delta = data.get("delta")
            if isinstance(delta, dict):
                return str(delta.get("text", ""))
            return str(delta or "")
        choices = data.get("choices") or []
        if choices:
            return str(choices[0].get("delta", {}).get("content") or "")
        message = data.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content") or "")
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(str(part.get("text", "")) for part in parts)
        return ""

    @staticmethod
    def _extract_tool_call(data: dict[str, Any]) -> dict[str, Any]:
        if data.get("type") == "response.function_call_arguments.delta":
            return {
                "id": data.get("item_id"),
                "arguments_delta": data.get("delta", ""),
            }
        choices = data.get("choices") or []
        if choices:
            calls = choices[0].get("delta", {}).get("tool_calls") or []
            if calls:
                return dict(calls[0])
        block = data.get("content_block") or {}
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return dict(block)
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "functionCall" in part:
                    return dict(part["functionCall"])
        return {}

    @staticmethod
    def _extract_usage(data: dict[str, Any]) -> dict[str, Any]:
        usage = data.get("usage") or data.get("usageMetadata") or {}
        return usage if isinstance(usage, dict) else {}

    async def health(self) -> bool:
        try:
            base_url = validate_provider_url(
                self.config.base_url,
                local=self.config.local,
            )
            transport = _pinned_transport(base_url, local=self.config.local)
            async with httpx.AsyncClient(
                timeout=5,
                follow_redirects=False,
                transport=transport,
                trust_env=False,
            ) as client:
                response = await client.get(base_url)
            return response.status_code < 300 or 400 <= response.status_code < 500
        except (httpx.HTTPError, ProviderError):
            return False


class ModelRouter:
    def __init__(self, clients: dict[str, ModelProviderClient]) -> None:
        self.clients = clients

    async def choose(
        self, providers: list[str], *, require_local: bool = False
    ) -> ModelProviderClient:
        for name in providers:
            client = self.clients.get(name)
            if client is None or (require_local and not client.config.local):
                continue
            if await client.health():
                return client
        raise ProviderError("no healthy policy-compatible provider route")
