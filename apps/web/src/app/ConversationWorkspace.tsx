import { useEffect, useRef, useState, type FormEvent } from "react";

import type {
  ConversationApi,
  ProviderCatalogEntry,
  ProviderId,
  RunEventStream,
  RunMode,
  ThinkingLevel
} from "./conversationApi";
import { loadDeviceThreads, saveDeviceThreads, type DeviceThread } from "./conversationStorage";

type Experience = "developer" | "everyday";
type RunStatus = "idle" | "working" | "completed" | "cancelled" | "failed";
const TITLE_MAX = 72;
const FALLBACK_PROVIDERS: ProviderCatalogEntry[] = [
  {
    id: "codex",
    label: "Codex",
    status: "unavailable",
    runtime: "local",
    status_label: "Not detected on this device",
    thinking_levels: ["low", "medium", "high", "xhigh"],
    supports_mcp: true,
    models: [
      { id: "default", label: "Codex default", recommended: true },
      { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true },
      { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", recommended: false },
      { id: "gpt-5.5", label: "GPT-5.5", recommended: false }
    ]
  },
  {
    id: "claude",
    label: "Claude",
    status: "unavailable",
    runtime: "local",
    status_label: "Not detected on this device",
    thinking_levels: ["low", "medium", "high", "xhigh", "max"],
    supports_mcp: false,
    models: [
      { id: "sonnet", label: "Claude Sonnet", recommended: true },
      { id: "opus", label: "Claude Opus", recommended: false },
      { id: "fable", label: "Claude Fable", recommended: false }
    ]
  },
  { id: "gemini", label: "Gemini", status: "preview", runtime: "local", models: [], status_label: "Preview", thinking_levels: [], supports_mcp: false },
  { id: "cursor", label: "Cursor", status: "unavailable", runtime: "local", models: [], status_label: "Unavailable", thinking_levels: [], supports_mcp: false },
  { id: "grok", label: "Grok", status: "preview", runtime: "api", models: [], status_label: "Preview", thinking_levels: [], supports_mcp: false }
];

const THINKING_LABELS: Record<ThinkingLevel, string> = {
  low: "Quick",
  medium: "Balanced",
  high: "Deep",
  xhigh: "Extra deep",
  max: "Maximum"
};

function Icon({ name }: { name: "history" | "new" | "send" | "stop" | "download" }) {
  const path = {
    history: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l3 2",
    new: "M12 5v14M5 12h14",
    send: "m4 4 16 8-16 8 3-8-3-8Zm3 8h13",
    stop: "M7 7h10v10H7z",
    download: "M12 3v12m0 0 5-5m-5 5-5-5M5 21h14"
  }[name];
  return <svg aria-hidden="true" className="ui-icon" fill="none" viewBox="0 0 24 24"><path d={path} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></svg>;
}

function activityLabel(activity: unknown): string {
  const labels: Record<string, string> = {
    command: "Running checks",
    files: "Updating files",
    mcp: "Using an MCP tool",
    search: "Inspecting the project"
  };
  return typeof activity === "string" ? labels[activity] ?? "Working" : "Working";
}

function safeMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message.replaceAll("_", " ") : "Corvus could not complete that action.";
}

export function ConversationWorkspace({ api, experience, storage, storageScope }: {
  api: ConversationApi;
  experience: Experience;
  storage: Storage;
  storageScope: string;
}) {
  const streamRef = useRef<RunEventStream | null>(null);
  const [threads, setThreads] = useState<DeviceThread[]>(() => loadDeviceThreads(storage, storageScope));
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(() => threads[0]?.id ?? null);
  const activeThreadIdRef = useRef<string | null>(selectedThreadId);
  const assistantTextRef = useRef("");
  const [composer, setComposer] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [providers, setProviders] = useState<ProviderCatalogEntry[]>(FALLBACK_PROVIDERS);
  const [providerError, setProviderError] = useState("");
  const [providerRefresh, setProviderRefresh] = useState(0);
  const [providerId, setProviderId] = useState<"codex" | "claude">("codex");
  const [modelId, setModelId] = useState("default");
  const [thinking, setThinking] = useState<ThinkingLevel>("medium");
  const [mode, setMode] = useState<RunMode>("chat");
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [runNote, setRunNote] = useState("");
  const [thinkingNote, setThinkingNote] = useState("");
  const [artifactReady, setArtifactReady] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const noun = experience === "developer" ? "thread" : "conversation";
  const selected = threads.find((thread) => thread.id === selectedThreadId) ?? null;
  const provider = providers.find((entry) => entry.id === providerId) ?? FALLBACK_PROVIDERS[0];

  useEffect(() => () => streamRef.current?.close(), []);
  useEffect(() => saveDeviceThreads(storage, storageScope, threads), [storage, storageScope, threads]);
  useEffect(() => {
    let current = true;
    void Promise.all([api.listProviders(), api.getPreferences()]).then(([catalog, preferences]) => {
      if (!current) return;
      if (catalog.length === 0) {
        setProviders(FALLBACK_PROVIDERS);
        setProviderError("No supported local agents were detected. Install Codex CLI or Claude Code, then retry.");
        return;
      }
      setProviders(catalog);
      setProviderError("");
      const preferred = catalog.find((entry) =>
        entry.id === preferences.default_provider && entry.status === "ready"
      );
      const ready = preferred ?? catalog.find((entry) =>
        (entry.id === "codex" || entry.id === "claude") && entry.status === "ready"
      );
      if (ready !== undefined) {
        setProviderId(ready.id as "codex" | "claude");
        setModelId(
          preferences.default_model !== null && ready.models.some((model) => model.id === preferences.default_model)
            ? preferences.default_model
            : ready.models[0]?.id ?? "default"
        );
        setThinking(
          ready.thinking_levels.includes(preferences.default_effort)
            ? preferences.default_effort
            : ready.thinking_levels.includes("medium") ? "medium" : ready.thinking_levels[0] ?? "medium"
        );
        const preferredMode = ready.id === "codex" ? preferences.default_mode : "chat";
        setMode(preferredMode);
        setMcpEnabled(preferredMode === "build" && ready.supports_mcp && preferences.mcp_enabled);
      }
    }).catch(() => {
      if (current) setProviderError("Corvus could not verify local providers. Retry discovery before starting a run.");
    });
    return () => { current = false; };
  }, [api, providerRefresh]);

  function createConversation(): DeviceThread {
    const now = new Date().toISOString();
    const created: DeviceThread = {
      id: crypto.randomUUID(),
      title: experience === "developer" ? "New thread" : "New conversation",
      createdAt: now,
      updatedAt: now,
      messages: []
    };
    setThreads((current) => [created, ...current]);
    setSelectedThreadId(created.id);
    activeThreadIdRef.current = created.id;
    setAssistantText("");
    assistantTextRef.current = "";
    setHistoryOpen(false);
    return created;
  }

  function finishRun(status: Exclude<RunStatus, "idle" | "working">, text?: string): void {
    const threadId = activeThreadIdRef.current;
    if (text && threadId) {
      const now = new Date().toISOString();
      setThreads((current) => current.map((thread) => thread.id === threadId ? {
        ...thread,
        updatedAt: now,
        messages: [...thread.messages, { id: crypto.randomUUID(), role: "assistant", content: text, createdAt: now }]
      } : thread));
    }
    setAssistantText("");
    assistantTextRef.current = "";
    setRunStatus(status);
    setRunNote("");
    setThinkingNote("");
    streamRef.current?.close();
    streamRef.current = null;
  }

  function listen(stream: RunEventStream): void {
    streamRef.current?.close();
    streamRef.current = stream;
    stream.addEventListener("message", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { text?: unknown } };
        if (typeof event.payload?.text === "string") {
          assistantTextRef.current += event.payload.text;
          setAssistantText(assistantTextRef.current);
        }
      } catch { setError("Corvus received an unreadable run event."); }
    });
    stream.addEventListener("thinking", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { text?: unknown; summary?: unknown } };
        const note = event.payload?.summary ?? event.payload?.text;
        if (typeof note === "string") setThinkingNote(note);
      } catch { setError("Corvus received an unreadable thinking event."); }
    });
    stream.addEventListener("status", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { activity?: unknown } };
        setRunNote(activityLabel(event.payload?.activity));
      } catch { setError("Corvus received an unreadable status event."); }
    });
    stream.addEventListener("artifact", () => setArtifactReady(true));
    stream.addEventListener("completed", () => finishRun("completed", assistantTextRef.current));
    stream.addEventListener("cancelled", () => finishRun("cancelled"));
    stream.addEventListener("failed", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { reason_code?: unknown } };
        if (typeof event.payload?.reason_code === "string") setError(event.payload.reason_code.replaceAll("_", " "));
      } finally { finishRun("failed"); }
    });
    stream.onTerminalError(() => {
      if (streamRef.current !== stream) return;
      setError("Connection to this run ended before completion. Start the run again to continue.");
      finishRun("failed");
    });
  }

  async function send(event: FormEvent): Promise<void> {
    event.preventDefault();
    const prompt = composer.trim();
    if (prompt === "" || runStatus === "working" || provider.status !== "ready") return;
    const thread = selected ?? createConversation();
    const now = new Date().toISOString();
    setThreads((current) => current.map((item) => item.id === thread.id ? {
      ...item,
      title: item.messages.length === 0 ? prompt.slice(0, TITLE_MAX) : item.title,
      updatedAt: now,
      messages: [...item.messages, { id: crypto.randomUUID(), role: "user", content: prompt, createdAt: now }]
    } : item));
    setComposer("");
    setAssistantText("");
    assistantTextRef.current = "";
    activeThreadIdRef.current = thread.id;
    setRunStatus("working");
    setBusy(true);
    setError("");
    setRunNote(mode === "build" ? "Preparing a clean sandbox" : "Starting the model");
    setThinkingNote("");
    setArtifactReady(false);
    try {
      const run = await api.startRun(prompt, {
        provider: providerId,
        model: modelId === "default" ? null : modelId,
        effort: thinking,
        mode,
        mcp_enabled: mode === "build" && mcpEnabled
      }, crypto.randomUUID());
      setRunId(run.run_id);
      listen(api.openRunEvents(run.run_id));
    } catch (reason) {
      setRunStatus("failed");
      setError(safeMessage(reason));
    } finally { setBusy(false); }
  }

  async function stop(): Promise<void> {
    if (runId === null) return;
    setBusy(true);
    try {
      const result = await api.cancelRun(runId);
      finishRun(result.state === "cancelled" ? "cancelled" : result.state);
    } catch (reason) { setError(safeMessage(reason)); }
    finally { setBusy(false); }
  }

  return (
    <section className="conversation-workspace" aria-label="Corvus conversations">
      <div className="conversation-panel">
        <header className="conversation-panel__header">
          <div><h1>{selected?.title ?? (experience === "developer" ? "New thread" : "New conversation")}</h1><span className="conversation-context">This computer</span></div>
          <div className="conversation-actions">
            <button aria-expanded={historyOpen} aria-label="Conversation history" className="icon-button" data-component-source="lucide-message-square" onClick={() => setHistoryOpen((open) => !open)} type="button"><Icon name="history" /></button>
            <button aria-label={`New ${noun}`} className="icon-button" onClick={createConversation} type="button"><Icon name="new" /></button>
          </div>
          {historyOpen ? <div className="conversation-history" role="dialog" aria-label="Conversation history panel">
            <strong>{experience === "developer" ? "Threads" : "Conversations"}</strong>
            {threads.length === 0 ? <p className="thread-list__empty">No conversations yet</p> : null}
            <div className="thread-list__items">{threads.map((thread) => <button aria-current={selectedThreadId === thread.id ? "true" : undefined} key={thread.id} onClick={() => { setSelectedThreadId(thread.id); activeThreadIdRef.current = thread.id; setAssistantText(""); assistantTextRef.current = ""; setHistoryOpen(false); }} type="button"><strong>{thread.title}</strong><span>{new Date(thread.updatedAt).toLocaleDateString()}</span></button>)}</div>
          </div> : null}
        </header>
        <div className="message-transcript">
          {(selected?.messages.length ?? 0) === 0 && assistantText === "" ? <div className="conversation-empty"><div className="conversation-mark" aria-hidden="true">C</div><h2>{experience === "developer" ? "What do you want to build?" : "What can Corvus help you finish?"}</h2><p>Ask a question or hand off a complete task. Build mode works in an isolated sandbox and returns the finished project.</p><div className="starter-prompts">{(experience === "developer" ? ["Inspect this repository", "Fix the failing tests", "Build a small feature"] : ["Plan my week", "Draft a clear update", "Organize these notes"]).map((starter) => <button key={starter} onClick={() => setComposer(starter)} type="button">{starter}</button>)}</div></div> : null}
          {selected?.messages.map((message) => <article className={`message message--${message.role}`} key={message.id}><span>{message.role === "user" ? "You" : "Corvus"}</span><p>{message.content}</p></article>)}
          {runStatus === "working" ? <section className="run-activity" aria-label="Run status: working"><div className="run-activity__status" role="status"><span className="activity-pulse" /><strong>Working</strong>{runNote ? <span>{runNote}</span> : null}</div>{thinkingNote ? <details open><summary>Thinking</summary><p>{thinkingNote}</p></details> : null}</section> : null}
          {assistantText !== "" ? <article className="message message--assistant"><span>Corvus</span><p>{assistantText}</p></article> : null}
          {artifactReady && runId !== null ? <a className="artifact-download" href={api.artifactUrl(runId)}><Icon name="download" />Download finished project</a> : null}
          {runStatus !== "idle" && runStatus !== "working" ? <p className="run-result-status" aria-label={`Run status: ${runStatus}`} data-status={runStatus}>{runStatus[0].toUpperCase() + runStatus.slice(1)}</p> : null}
        </div>
        {providerError ? <p className="conversation-error" role="alert">{providerError} <button aria-label="Retry providers" className="text-button" onClick={() => setProviderRefresh((value) => value + 1)} type="button">Retry</button></p> : null}
        {error ? <p className="conversation-error" role="alert">{error}</p> : null}
        <form className="composer" onSubmit={(event) => void send(event)}>
          <label className="sr-only" htmlFor="corvus-composer">Message Corvus</label><textarea aria-label="Message Corvus" id="corvus-composer" onChange={(event) => setComposer(event.target.value)} placeholder={experience === "developer" ? "Ask Corvus to work in this repository…" : "Describe what you want to get done…"} rows={2} value={composer} />
          <div className="composer__controls">
            <label className="sr-only" htmlFor="composer-provider">Provider</label><select aria-label="Agent provider" className="composer-control composer-control--provider" disabled={runStatus === "working"} id="composer-provider" onChange={(event) => {
              const next = event.target.value as ProviderId;
              if (next !== "codex" && next !== "claude") return;
              const nextProvider = providers.find((entry) => entry.id === next);
              if (nextProvider?.status !== "ready") return;
              setProviderId(next);
              setModelId(nextProvider.models[0]?.id ?? "default");
              setThinking(nextProvider.thinking_levels.includes("medium") ? "medium" : nextProvider.thinking_levels[0] ?? "medium");
              if (next !== "codex") { setMode("chat"); setMcpEnabled(false); }
            }} value={providerId}>{providers.map((entry) => <option disabled={entry.status !== "ready"} key={entry.id} value={entry.id}>{entry.label}{entry.status === "ready" ? " (Detected)" : entry.status === "preview" ? " (Preview)" : " (Unavailable)"}</option>)}</select>
            <label className="sr-only" htmlFor="composer-model">Model</label><select aria-label="Agent model" className="composer-control composer-control--model" disabled={runStatus === "working" || provider.models.length === 0} id="composer-model" onChange={(event) => setModelId(event.target.value)} value={modelId}>{provider.models.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}{entry.recommended ? " (recommended)" : ""}</option>)}</select>
            <label className="sr-only" htmlFor="composer-thinking">Thinking</label><select aria-label="Thinking level" className="composer-control" disabled={runStatus === "working" || provider.thinking_levels.length === 0} id="composer-thinking" onChange={(event) => setThinking(event.target.value as ThinkingLevel)} value={thinking}>{provider.thinking_levels.map((level) => <option key={level} value={level}>{THINKING_LABELS[level]}</option>)}</select>
            <label className="sr-only" htmlFor="composer-mode">Mode</label><select aria-label="Run mode" className="composer-control" disabled={runStatus === "working"} id="composer-mode" onChange={(event) => { const next = event.target.value as RunMode; setMode(next); if (next === "chat") setMcpEnabled(false); }} value={mode}><option value="chat">Chat</option><option disabled={providerId !== "codex"} value="build">Build</option></select>
            {mode === "build" ? <label className="mcp-toggle"><input aria-label="Allow configured MCP servers" checked={mcpEnabled} onChange={(event) => setMcpEnabled(event.target.checked)} type="checkbox" /><span>MCP</span></label> : null}
            {runStatus === "working" ? <button aria-label="Stop" className="composer-submit composer-submit--stop" disabled={busy} onClick={() => void stop()} type="button"><Icon name="stop" /></button> : <button aria-label={mode === "build" ? "Build project" : "Send message"} className="composer-submit" data-component-source="shadcn-button" disabled={busy || composer.trim() === "" || provider.status !== "ready"} type="submit"><Icon name="send" /></button>}
          </div>
          {mode === "build" && mcpEnabled ? <p className="composer__notice">Configured MCP servers may access external systems. Corvus will work only inside a fresh build sandbox.</p> : null}
        </form>
      </div>
    </section>
  );
}
