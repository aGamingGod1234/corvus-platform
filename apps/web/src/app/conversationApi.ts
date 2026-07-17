export interface LocalChatRun {
  run_id: string;
  handle_id: string;
  state: "running" | "completed" | "failed";
  provider: "codex" | "claude";
  model: string;
  mode: "chat" | "build";
  storage: "this_device";
  created_at: string;
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
}

export interface ConversationApi {
  listProviders(): Promise<ProviderCatalogEntry[]>;
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
