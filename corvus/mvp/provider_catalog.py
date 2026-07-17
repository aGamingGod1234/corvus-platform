from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProviderCatalogStatus = Literal["ready", "preview", "unavailable"]
ProviderCatalogTransport = Literal["local", "api"]
ThinkingLevel = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True, slots=True)
class ProviderModel:
    id: str
    label: str
    recommended: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "recommended": self.recommended,
        }


@dataclass(frozen=True, slots=True)
class ProviderCatalogEntry:
    id: str
    name: str
    transport: ProviderCatalogTransport
    status: ProviderCatalogStatus
    status_label: str
    models: tuple[ProviderModel, ...]
    thinking_levels: tuple[ThinkingLevel, ...]
    supports_mcp: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "transport": self.transport,
            "status": self.status,
            "status_label": self.status_label,
            "models": [model.as_dict() for model in self.models],
            "thinking_levels": list(self.thinking_levels),
            "supports_mcp": self.supports_mcp,
        }


def build_provider_catalog(
    codex_available: bool,
    claude_available: bool,
) -> tuple[ProviderCatalogEntry, ...]:
    """Return the UI-safe provider catalog without local identity details."""

    return (
        ProviderCatalogEntry(
            id="codex",
            name="OpenAI Codex",
            transport="local",
            status="ready" if codex_available else "unavailable",
            status_label=(
                "Detected; sign-in is checked when a run starts"
                if codex_available
                else "Not installed"
            ),
            models=(
                ProviderModel("default", "Codex default", recommended=True),
                ProviderModel("gpt-5.6-sol", "GPT-5.6 Sol"),
                ProviderModel("gpt-5.6-terra", "GPT-5.6 Terra"),
                ProviderModel("gpt-5.5", "GPT-5.5"),
            ),
            thinking_levels=("low", "medium", "high", "xhigh"),
            supports_mcp=True,
        ),
        ProviderCatalogEntry(
            id="claude",
            name="Claude Code",
            transport="local",
            status="ready" if claude_available else "unavailable",
            status_label=(
                "Detected; sign-in is checked when a run starts"
                if claude_available
                else "Not installed"
            ),
            models=(
                ProviderModel("sonnet", "Claude Sonnet 5", recommended=True),
                ProviderModel("opus", "Claude Opus 5"),
                ProviderModel("fable", "Claude Fable"),
            ),
            thinking_levels=("low", "medium", "high", "xhigh", "max"),
            supports_mcp=False,
        ),
        ProviderCatalogEntry(
            id="gemini",
            name="Gemini CLI",
            transport="local",
            status="preview",
            status_label="Preview - safe local execution is not enabled yet",
            models=(ProviderModel("gemini-default", "Gemini recommended", recommended=True),),
            thinking_levels=("low", "medium", "high"),
            supports_mcp=False,
        ),
        ProviderCatalogEntry(
            id="cursor",
            name="Cursor Agent",
            transport="local",
            status="unavailable",
            status_label="Unavailable on this device",
            models=(ProviderModel("cursor-default", "Cursor recommended", recommended=True),),
            thinking_levels=("low", "medium", "high"),
            supports_mcp=False,
        ),
        ProviderCatalogEntry(
            id="xai",
            name="Grok by xAI",
            transport="api",
            status="preview",
            status_label="Preview - API connection is coming later",
            models=(ProviderModel("grok-default", "Grok recommended", recommended=True),),
            thinking_levels=("low", "medium", "high"),
            supports_mcp=False,
        ),
    )
