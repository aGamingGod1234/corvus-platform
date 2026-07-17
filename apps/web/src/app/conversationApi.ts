export interface LocalChatRun {
  run_id: string;
  handle_id: string;
  state: "running" | "completed" | "failed";
  provider: "codex" | "claude";
  model: string;
  mode: "chat" | "build";
  storage: "this_device";
  created_at: string;
  safety: SafetyPreview;
}

export interface LocalChatCancel {
  run_id: string;
  state: "cancelled" | "completed" | "failed";
  accepted: boolean;
  reason_code: string | null;
}

export interface RunEventMessage { data: string; }
export type RunEventListener = (event: RunEventMessage) => void;
export interface RunEventStream {
  addEventListener(type: string, listener: RunEventListener): void;
  onTerminalError(listener: () => void): void;
  close(): void;
}

class BrowserRunEventStream implements RunEventStream {
  constructor(private readonly source: EventSource) {}

  addEventListener(type: string, listener: RunEventListener): void {
    this.source.addEventListener(type, listener as unknown as EventListener);
  }

  onTerminalError(listener: () => void): void {
    this.source.addEventListener("error", () => {
      if (this.source.readyState === this.source.CLOSED) listener();
    });
  }

  close(): void {
    this.source.close();
  }
}

export type ProviderId = "codex" | "claude" | "gemini" | "cursor" | "grok";
export type ThinkingLevel = "low" | "medium" | "high" | "xhigh" | "max";
export type RunMode = "chat" | "build";
export type SafetyLevel = "read_only" | "protected" | "elevated";

export interface SafetyPreview {
  policy_digest: string;
  level: SafetyLevel;
  label: string;
  summary: string;
  execution: string;
  filesystem: string;
  network: string;
  mcp: string;
  approvals: string;
  output: string;
  requires_confirmation: boolean;
}

export interface SafetyReceipt {
  run_id: string;
  status: "completed" | "failed" | "cancelled";
  safety: SafetyPreview;
  activities: string[];
  mcp_used: boolean;
  approval: string;
  original_project_modified: boolean;
  artifact: {
    download_name: string;
    sha256_digest: string;
    size_bytes: number;
    secret_screening: "passed";
  } | null;
}

export interface ProviderModel {
  id: string;
  label: string;
  recommended: boolean;
}

export interface ProviderCatalogEntry {
  id: ProviderId;
  label: string;
  status: "ready" | "preview" | "unavailable";
  runtime: "local" | "api";
  models: ProviderModel[];
  status_label: string;
  thinking_levels: ThinkingLevel[];
  supports_mcp: boolean;
}

export interface LocalChatRequest {
  provider: "codex" | "claude";
  model: string | null;
  effort: ThinkingLevel;
  mode: RunMode;
  mcp_enabled: boolean;
  safety_digest?: string | null;
}

export type ResponseTone = "concise" | "balanced" | "detailed";

export interface RuntimePreferences {
  version: number;
  default_provider: "codex" | "claude";
  default_model: string | null;
  default_effort: ThinkingLevel;
  default_mode: RunMode;
  mcp_enabled: boolean;
  response_tone: ResponseTone;
  custom_rules: string;
  updated_at: string | null;
}

export interface RuntimePreferencesUpdate extends Omit<RuntimePreferences, "version" | "updated_at"> {
  expected_version: number;
}

export interface ConversationApi {
  listProviders(): Promise<ProviderCatalogEntry[]>;
  getPreferences(): Promise<RuntimePreferences>;
  updatePreferences(preferences: RuntimePreferencesUpdate): Promise<RuntimePreferences>;
  getSafetyPreview(
    provider: "codex" | "claude",
    mode: RunMode,
    mcpEnabled: boolean
  ): Promise<SafetyPreview>;
  getSafetyReceipt(runId: string): Promise<SafetyReceipt>;
  startRun(
    prompt: string,
    request: LocalChatRequest,
    idempotencyKey: string
  ): Promise<LocalChatRun>;
  cancelRun(runId: string): Promise<LocalChatCancel>;
  openRunEvents(runId: string): RunEventStream;
  artifactUrl(runId: string): string;
}

interface ApiErrorDetail { code?: string; correlation_id?: string; }
interface ApiErrorBody { detail?: string | ApiErrorDetail; }

export class ConversationApiError extends Error {
  constructor(readonly status: number, readonly code: string, readonly correlationId: string | null) {
    super(code);
    this.name = "ConversationApiError";
  }
}

export function createConversationApi(csrfToken: string, baseUrl = ""): ConversationApi {
  async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: { Accept: "application/json", ...init.headers }
    });
    if (!response.ok) {
      let body: ApiErrorBody = {};
      try { body = await response.json() as ApiErrorBody; } catch { /* Never expose raw bodies. */ }
      const detail = body.detail;
      const code = typeof detail === "string"
        ? detail
        : detail?.code ?? `request_failed_${response.status}`;
      const correlationId = typeof detail === "object" && detail !== null
        ? detail.correlation_id ?? null
        : null;
      throw new ConversationApiError(response.status, code, correlationId);
    }
    return await response.json() as T;
  }

  function mutationHeaders(idempotencyKey?: string): Record<string, string> {
    if (csrfToken === "") throw new ConversationApiError(401, "paired_session_required", null);
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {})
    };
  }

  return {
    listProviders: () => requestJson("/api/local-chat/providers", {
      method: "GET",
      headers: { Accept: "application/json" }
    }),
    getPreferences: () => requestJson("/api/local-chat/preferences", {
      method: "GET",
      headers: { Accept: "application/json" }
    }),
    updatePreferences: (preferences) => requestJson("/api/local-chat/preferences", {
      method: "PUT",
      headers: mutationHeaders(),
      body: JSON.stringify(preferences)
    }),
    getSafetyPreview: (provider, mode, mcpEnabled) => {
      const query = new URLSearchParams({
        provider,
        mode,
        mcp_enabled: String(mcpEnabled)
      });
      return requestJson(`/api/local-chat/safety-preview?${query.toString()}`, {
        method: "GET",
        headers: { Accept: "application/json" }
      });
    },
    getSafetyReceipt: (runId) => requestJson(
      `/api/local-chat/runs/${encodeURIComponent(runId)}/safety-receipt`,
      { method: "GET", headers: { Accept: "application/json" } }
    ),
    startRun: (prompt, request, idempotencyKey) => requestJson("/api/local-chat/runs", {
      method: "POST",
      headers: mutationHeaders(idempotencyKey),
      body: JSON.stringify({ prompt, ...request })
    }),
    cancelRun: (runId) => requestJson(`/api/local-chat/runs/${runId}/cancel`, {
      method: "POST",
      headers: mutationHeaders()
    }),
    openRunEvents(runId) {
      return new BrowserRunEventStream(new EventSource(`${baseUrl}/api/local-chat/runs/${runId}/events?follow=true`, {
        withCredentials: true
      }));
    },
    artifactUrl: (runId) => `${baseUrl}/api/local-chat/runs/${runId}/artifact`
  };
}
