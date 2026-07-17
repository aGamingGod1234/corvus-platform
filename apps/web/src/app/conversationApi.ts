export interface LocalChatRun {
  run_id: string;
  handle_id: string;
  state: "running" | "completed" | "failed";
  provider: "codex";
  model: string;
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
  close(): void;
}

export interface ConversationApi {
  startRun(
    prompt: string,
    request: { model: null; effort: "normal" | "high" },
    idempotencyKey: string
  ): Promise<LocalChatRun>;
  cancelRun(runId: string): Promise<LocalChatCancel>;
  openRunEvents(runId: string): RunEventStream;
}

interface ApiErrorBody { detail?: { code?: string; correlation_id?: string }; }

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
      throw new ConversationApiError(
        response.status,
        body.detail?.code ?? `request_failed_${response.status}`,
        body.detail?.correlation_id ?? null
      );
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
      return new EventSource(`${baseUrl}/api/local-chat/runs/${runId}/events?follow=true`, {
        withCredentials: true
      }) as unknown as RunEventStream;
    }
  };
}
