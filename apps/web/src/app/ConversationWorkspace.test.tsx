import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConversationApi, RunEventListener, RunEventStream } from "./conversationApi";
import { ConversationWorkspace } from "./ConversationWorkspace";
import { MemoryStorage } from "../test/memoryStorage";

class FakeRunStream implements RunEventStream {
  private readonly listeners = new Map<string, RunEventListener[]>();
  private readonly terminalListeners: Array<() => void> = [];
  close = vi.fn();

  addEventListener(type: string, listener: RunEventListener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: object): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(data) });
    }
  }

  onTerminalError(listener: () => void): void {
    this.terminalListeners.push(listener);
  }

  failTerminal(): void {
    for (const listener of this.terminalListeners) listener();
  }
}

function conversationApi(stream: FakeRunStream): ConversationApi {
  const preview = (mode: "chat" | "build", mcpEnabled: boolean) => ({
    policy_digest: (mcpEnabled ? "c" : mode === "build" ? "b" : "a").repeat(64),
    level: mcpEnabled ? "elevated" as const : mode === "build" ? "protected" as const : "read_only" as const,
    label: mcpEnabled ? "External tools on" : mode === "build" ? "Protected build" : "Read-only",
    summary: mode === "build" ? "Work happens in a fresh writable sandbox." : "The agent can inspect context without writing files.",
    execution: "Codex CLI runs ephemerally.",
    filesystem: mode === "build" ? "The original project is not modified." : "The sandbox is read-only.",
    network: "Corvus grants no separate network permission.",
    mcp: mcpEnabled ? "Configured MCP tools may act on external systems." : "Configured MCP servers are not loaded.",
    approvals: "No blanket host approval is granted.",
    output: mode === "build" ? "A screened ZIP can be downloaded." : "No artifact is exported.",
    requires_confirmation: mode === "build"
  });
  return {
    getPreferences: vi.fn().mockResolvedValue({
      version: 0,
      default_provider: "codex",
      default_model: null,
      default_effort: "medium",
      default_mode: "chat",
      mcp_enabled: false,
      response_tone: "balanced",
      custom_rules: "",
      updated_at: null
    }),
    updatePreferences: vi.fn(),
    listProviders: vi.fn().mockResolvedValue([
      { id: "codex", label: "Codex", status: "ready", runtime: "local", models: [
        { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true },
        { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", recommended: false },
        { id: "gpt-5.5", label: "GPT-5.5", recommended: false }
      ], status_label: "Detected on this device", thinking_levels: ["low", "medium", "high", "xhigh"], supports_mcp: true },
      { id: "claude", label: "Claude", status: "ready", runtime: "local", models: [
        { id: "sonnet", label: "Claude Sonnet", recommended: true },
        { id: "opus", label: "Claude Opus", recommended: false }
      ], status_label: "Detected on this device", thinking_levels: ["low", "medium", "high", "xhigh", "max"], supports_mcp: false },
      { id: "gemini", label: "Gemini", status: "preview", runtime: "local", models: [], status_label: "Preview", thinking_levels: [], supports_mcp: false },
      { id: "grok", label: "Grok", status: "preview", runtime: "api", models: [], status_label: "Preview", thinking_levels: [], supports_mcp: false }
    ]),
    getSafetyPreview: vi.fn((_provider, mode, mcpEnabled) => Promise.resolve(preview(mode, mcpEnabled))),
    getSafetyReceipt: vi.fn().mockResolvedValue({
      run_id: "run-1", status: "completed", safety: preview("build", true),
      activities: ["Files changed only inside the scratch workspace"], mcp_used: true,
      approval: "No blanket host approval was granted.", original_project_modified: false,
      artifact: { download_name: "corvus-project.zip", sha256_digest: "d".repeat(64), size_bytes: 42, secret_screening: "passed" }
    }),
    startRun: vi.fn().mockResolvedValue({ run_id: "run-1", handle_id: "handle-1", state: "running", provider: "codex", model: "gpt-5.6-sol", mode: "chat", storage: "this_device", created_at: "2026-07-17T02:00:02Z", safety: preview("chat", false) }),
    cancelRun: vi.fn().mockResolvedValue({ run_id: "run-1", state: "cancelled", accepted: true, reason_code: null }),
    openRunEvents: vi.fn().mockReturnValue(stream),
    artifactUrl: vi.fn((runId: string) => `/api/local-chat/runs/${runId}/artifact`)
  };
}

function unavailableConversationApi(stream: FakeRunStream): ConversationApi {
  return {
    ...conversationApi(stream),
    listProviders: vi.fn().mockRejectedValue(new Error("catalog unavailable"))
  };
}

function emptyConversationApi(stream: FakeRunStream): ConversationApi {
  return {
    ...conversationApi(stream),
    listProviders: vi.fn().mockResolvedValue([])
  };
}

describe("ConversationWorkspace", () => {
  it("creates a thread, runs Local Codex, and renders durable output", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    const storage = new MemoryStorage();
    const view = render(<ConversationWorkspace api={api} storage={storage} storageScope="device" experience="everyday" />);
    const user = userEvent.setup();

    expect(screen.queryByLabelText("Run status: idle")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Conversation history" }));
    expect(screen.getByText("No conversations yet")).toBeVisible();
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Draft release notes");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(api.startRun).toHaveBeenCalledWith("Draft release notes", {
      provider: "codex", model: "gpt-5.6-sol", effort: "medium", mode: "chat", mcp_enabled: false,
      safety_digest: "a".repeat(64)
    }, expect.any(String));
    expect(screen.getByLabelText("Run status: working")).toBeVisible();
    expect(await screen.findByText("Working")).toBeVisible();

    stream.emit("message", { type: "message", payload: { text: "Release ready." } });
    stream.emit("completed", { type: "completed", payload: {} });

    expect(await screen.findByText("Release ready.")).toBeVisible();
    expect(await screen.findByText("Completed")).toBeVisible();
    expect(screen.queryByText("Starting the model")).not.toBeInTheDocument();
    view.unmount();
    render(<ConversationWorkspace api={api} storage={storage} storageScope="device" experience="everyday" />);
    expect(screen.getByText("Release ready.")).toBeVisible();
  });

  it("keeps history on demand and exposes provider, model, thinking, and Build controls", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    expect(screen.queryByRole("complementary", { name: "thread list" })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Claude" })).toBeEnabled();
    expect(screen.queryByRole("option", { name: /Gemini|Grok|Unavailable|Preview/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Codex default/i })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Agent provider" }), "claude");
    expect(screen.getByRole("option", { name: "Claude Sonnet (recommended)" })).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: "Agent model" }), "opus");
    expect(screen.getByRole("option", { name: "Max" })).toHaveValue("max");
    await user.selectOptions(screen.getByRole("combobox", { name: "Thinking level" }), "max");
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Review this change");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(api.startRun).toHaveBeenCalledWith("Review this change", {
      provider: "claude", model: "opus", effort: "max", mode: "chat", mcp_enabled: false,
      safety_digest: "a".repeat(64)
    }, expect.any(String));
    stream.emit("completed", { type: "completed", payload: {} });
    expect(await screen.findByText("Completed")).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: "Agent provider" }), "codex");
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Agent provider" })).toHaveValue("codex"));
    await user.selectOptions(screen.getByRole("combobox", { name: "Run mode" }), "build");
    expect(screen.getByRole("checkbox", { name: "Allow configured MCP servers" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Thinking level" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Conversation history" }));
    expect(screen.getAllByText("Review this change").length).toBeGreaterThan(0);
  });

  it("streams safe thinking and work status, then offers the finished project", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Build a landing page");
    await user.selectOptions(screen.getByRole("combobox", { name: "Run mode" }), "build");
    await user.click(screen.getByRole("checkbox", { name: "Allow configured MCP servers" }));
    expect(screen.getByText(/may access external systems/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Build project" }));
    expect(api.startRun).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Confirm protected build" })).toBeVisible();
    expect(screen.getByText(/original project is not modified/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Continue in sandbox" }));
    expect(api.startRun).toHaveBeenCalledWith("Build a landing page", {
      provider: "codex", model: "gpt-5.6-sol", effort: "medium", mode: "build", mcp_enabled: true,
      safety_digest: "c".repeat(64)
    }, expect.any(String));
    stream.emit("thinking", { type: "thinking", payload: { text: "Checking the project structure" } });
    expect(await screen.findByText("Checking the project structure")).toBeVisible();
    stream.emit("status", { type: "status", payload: { activity: "files" } });
    expect((await screen.findAllByText("Updating files"))[0]).toBeVisible();
    stream.emit("artifact", { type: "artifact", payload: { download_name: "corvus-project.zip" } });
    stream.emit("completed", { type: "completed", payload: {} });
    expect(await screen.findByRole("link", { name: "Download finished project" })).toHaveAttribute(
      "href", "/api/local-chat/runs/run-1/artifact"
    );
    expect(await screen.findByRole("region", { name: "Safety receipt" })).toHaveTextContent(/screening passed/i);
  });

  it("shows the server-authored protection summary in the composer", async () => {
    const api = conversationApi(new FakeRunStream());
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    expect(await screen.findByRole("button", { name: "View safety details" })).toHaveTextContent("Read-only");
    expect(screen.getByRole("button", { name: "View safety details" })).toHaveAttribute(
      "title",
      "Click to see details"
    );
    await user.click(screen.getByRole("button", { name: "View safety details" }));
    expect(screen.getByRole("region", { name: "Safety details" })).toHaveTextContent(/no separate network permission/i);
  });

  it("sends a single line with Enter and a multiline draft with Control+Enter", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="everyday" />);
    const user = userEvent.setup();
    const composer = screen.getByRole("textbox", { name: "Message Corvus" });

    await user.type(composer, "Send this{enter}");
    await waitFor(() => expect(api.startRun).toHaveBeenCalledTimes(1));
    stream.emit("completed", { type: "completed", payload: {} });
    await screen.findByText("Completed");

    await user.type(composer, "First line{shift>}{enter}{/shift}Second line{enter}");
    expect(api.startRun).toHaveBeenCalledTimes(1);
    expect(composer).toHaveValue("First line\nSecond line\n");
    await user.type(composer, "{control>}{enter}{/control}");
    await waitFor(() => expect(api.startRun).toHaveBeenCalledTimes(2));
    expect(api.startRun).toHaveBeenLastCalledWith(
      "First line\nSecond line",
      expect.any(Object),
      expect.any(String)
    );
  });

  it("renders streamed and durable messages as sanitized GitHub-flavored Markdown", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Use **safe** markdown");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    stream.emit("message", {
      type: "message",
      payload: { text: "**Done**\n\n- checked\n\n[Docs](https://example.com)\n\n<script>alert(1)</script>" }
    });

    expect(await screen.findByText("Done")).toHaveStyle({ fontWeight: "bold" });
    expect(screen.getByText("checked").closest("ul")).toBeVisible();
    expect(screen.getByRole("link", { name: "Docs" })).toHaveAttribute("href", "https://example.com");
    expect(document.querySelector("script")).toBeNull();
  });

  it("loads the safety receipt when a run is cancelled", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Inspect this repository");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    stream.emit("cancelled", { type: "cancelled", payload: {} });

    await waitFor(() => expect(api.getSafetyReceipt).toHaveBeenCalledWith("run-1"));
    expect(await screen.findByRole("region", { name: "Safety receipt" })).toBeVisible();
  });

  it("fails closed when provider discovery is unavailable and allows retry", async () => {
    const stream = new FakeRunStream();
    const api = unavailableConversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="everyday" />);
    const user = userEvent.setup();

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not verify local providers/i);
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Do not send this");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(api.startRun).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Retry providers" }));
    expect(api.listProviders).toHaveBeenCalledTimes(2);
  });

  it("explains how to install a provider when discovery returns an empty catalog", async () => {
    const stream = new FakeRunStream();
    const api = emptyConversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="everyday" />);
    const user = userEvent.setup();

    expect(await screen.findByRole("alert")).toHaveTextContent(/install Codex CLI or Claude Code/i);
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Do not send this");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(api.startRun).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Retry providers" }));
    expect(api.listProviders).toHaveBeenCalledTimes(2);
  });

  it("cancels the active run without treating a closed stream as success", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "New thread" }));
    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Inspect this repository");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.click(await screen.findByRole("button", { name: "Stop" }));

    await waitFor(() => expect(api.cancelRun).toHaveBeenCalledWith("run-1"));
    expect(screen.getByText("Cancelled")).toBeVisible();
    expect(stream.close).toHaveBeenCalled();
  });

  it("leaves working state when the run event stream closes permanently", async () => {
    const stream = new FakeRunStream();
    const api = conversationApi(stream);
    render(<ConversationWorkspace api={api} storage={new MemoryStorage()} storageScope="device" experience="developer" />);
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: "Message Corvus" }), "Inspect this repository");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Working")).toBeVisible();

    stream.failTerminal();

    expect(await screen.findByText("Failed")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(/connection to this run ended/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/start the run again/i);
    expect(stream.close).toHaveBeenCalled();
  });
});
