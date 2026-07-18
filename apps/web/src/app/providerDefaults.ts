import type { ProviderCatalogEntry, ProviderModel, ThinkingLevel } from "./conversationApi";

export const CODEX_MODELS: ProviderModel[] = [
  { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true },
  { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", recommended: false }
];

export const ALL_THINKING_LEVELS: ThinkingLevel[] = ["low", "medium", "high", "xhigh", "max"];
export const CODEX_THINKING_LEVELS: ThinkingLevel[] = ["low", "medium", "high", "xhigh"];

export const FALLBACK_PROVIDERS: ProviderCatalogEntry[] = [
  {
    id: "codex",
    label: "Codex",
    status: "unavailable",
    runtime: "local",
    status_label: "Discovery required",
    thinking_levels: CODEX_THINKING_LEVELS,
    supports_mcp: true,
    models: CODEX_MODELS
  },
  {
    id: "claude",
    label: "Claude",
    status: "unavailable",
    runtime: "local",
    status_label: "Discovery required",
    thinking_levels: ALL_THINKING_LEVELS,
    supports_mcp: false,
    models: [
      { id: "sonnet", label: "Claude Sonnet", recommended: true },
      { id: "opus", label: "Claude Opus", recommended: false }
    ]
  }
];
