import { afterEach, describe, expect, it, vi } from "vitest";

import { ConversationApiError, createConversationApi } from "./conversationApi";

describe("conversation API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses paired-session mutation proofs without claiming remote storage", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      run_id: "run-1", handle_id: "handle-1", state: "running", provider: "codex",
      model: "Codex default", storage: "this_device", created_at: "2026-07-17T02:00:00Z"
    }), { status: 202, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const api = createConversationApi("csrf-local");

    await api.startRun("First task", { model: null, effort: "normal" }, "run-key");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/local-chat/runs",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Idempotency-Key": "run-key",
          "X-CSRF-Token": "csrf-local"
        }),
        body: JSON.stringify({ prompt: "First task", model: null, effort: "normal" })
      })
    );
  });

  it("surfaces a safe correlation-bearing API failure", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: "codex_unavailable", correlation_id: "corr-1" }
    }), { status: 503, headers: { "Content-Type": "application/json" } })));

    await expect(createConversationApi("csrf").startRun("test", { model: null, effort: "normal" }, "key")).rejects.toEqual(
      new ConversationApiError(503, "codex_unavailable", "corr-1")
    );
  });
});
