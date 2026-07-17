import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConversationApi, RunEventListener, RunEventStream } from "./conversationApi";
import { ConversationWorkspace } from "./ConversationWorkspace";
import { MemoryStorage } from "../test/memoryStorage";

class FakeRunStream implements RunEventStream {
  private readonly listeners = new Map<string, RunEventListener[]>();
  close = vi.fn();

  addEventListener(type: string, listener: RunEventListener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: object): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(data) });
    }
  }
}

function conversationApi(stream: FakeRunStream): ConversationApi {
  return {
    startRun: vi.fn().mockResolvedValue({ run_id: "run-1", handle_id: "handle-1", state: "running", provider: "codex", model: "Codex default", storage: "this_device", created_at: "2026-07-17T02:00:02Z" }),
    cancelRun: vi.fn().mockResolvedValue({ run_id: "run-1", state: "cancelled", accepted: true, reason_code: null }),
    openRunEvents: vi.fn().mockReturnValue(stream)
  };
}

describe("ConversationWorkspace", () => {
  it("creates a thread, runs Local Codex, and renders durable output", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="everyday" />);
    const user = userEvent.setup();

    expect(await screen.findByText("No conversations yet")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Draft release notes");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(api.startRun).toHaveBeenCalledWith("Draft release notes", { model: null, effort: "normal" }, expect.any(String));
    expect(await screen.findByText("Working")).toBeVisible();

    stream.emit("message", { type: "message", payload: { text: "Release ready." } });
    stream.emit("completed", { type: "completed", payload: {} });

    expect(await screen.findByText("Release ready.")).toBeVisible();
    expect(await screen.findByText("Completed")).toBeVisible();
  });

  it("cancels the active run without treating a closed stream as success", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "New thread" }));
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Inspect this repository");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.click(await screen.findByRole("button", { name: "Stop run" }));

    await waitFor(() => expect(api.cancelRun).toHaveBeenCalledWith("run-1"));
    expect(screen.getByText("Cancelled")).toBeVisible();
    expect(stream.close).toHaveBeenCalled();
  });
});
