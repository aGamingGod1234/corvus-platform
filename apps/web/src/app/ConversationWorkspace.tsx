import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { BrandMark } from "../components/Brand";

import type {
  ConversationApi,
  ConversationRepository,
  ProviderCatalogEntry,
  ProviderId,
  RunnableProviderId,
  RunEventStream,
  RunMode,
  SafetyPreview,
  SafetyReceipt,
  ThinkingLevel
} from "./conversationApi";
import { loadDeviceThreads, saveDeviceThreads, type DeviceThread } from "./conversationStorage";
import { loadDevicePreferences } from "./devicePreferences";
import { FALLBACK_PROVIDERS } from "./providerDefaults";

type Experience = "developer" | "everyday";
type RunStatus = "idle" | "working" | "completed" | "cancelled" | "failed";
const TITLE_MAX = 72;
const THINKING_LABELS: Record<ThinkingLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "Extra high",
  max: "Max"
};

function MarkdownMessage({ children }: { children: string }) {
  return <div className="message-markdown"><ReactMarkdown rehypePlugins={[rehypeSanitize]} remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown></div>;
}

function Icon({ name }: { name: "history" | "new" | "send" | "stop" | "download" | "shield" | "agent" | "model" | "thinking" | "mode" }) {
  const path = {
    history: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l3 2",
    new: "M12 5v14M5 12h14",
    send: "m4 4 16 8-16 8 3-8-3-8Zm3 8h13",
    stop: "M7 7h10v10H7z",
    download: "M12 3v12m0 0 5-5m-5 5-5-5M5 21h14",
    shield: "M12 3 5 6v5c0 4.6 2.8 8.1 7 10 4.2-1.9 7-5.4 7-10V6l-7-3Zm-3 9 2 2 4-4",
    agent: "M8 9h8M9 15h6M12 3v3M6 6h12v14H6z",
    model: "M5 7h14M5 12h14M5 17h9",
    thinking: "M9 18h6M10 22h4M8 13a5 5 0 1 1 8 0c-1 1-2 2-2 3h-4c0-1-1-2-2-3",
    mode: "M4 4h16v16H4zM9 9h6v6H9z"
  }[name];
  return <svg aria-hidden="true" className="ui-icon" fill="none" viewBox="0 0 24 24"><path d={path} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></svg>;
}

function activityLabel(activity: unknown): string {
  const labels: Record<string, string> = {
    command: "Running checks",
    files: "Updating files",
    mcp: "Using an MCP tool",
    search: "Inspecting the project",
    sandbox: "Sandbox initialized",
    blocked: "Blocked an unsafe action",
    workaround: "Continuing with a safe workaround",
    screening: "Screening the finished artifact"
  };
  return typeof activity === "string" ? labels[activity] ?? "Working" : "Working";
}

function safeMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message.replaceAll("_", " ") : "Corvus could not complete that action.";
}

export function ConversationWorkspace({ api, experience, newThreadSignal = 0, onOpenProjects, storage, storageScope, workingDirectory }: {
  api: ConversationApi;
  experience: Experience;
  newThreadSignal?: number;
  onOpenProjects?(): void;
  storage: Storage;
  storageScope: string;
  workingDirectory?: string;
}) {
  const streamRef = useRef<RunEventStream | null>(null);
  const [threads, setThreads] = useState<DeviceThread[]>(() => loadDeviceThreads(storage, storageScope));
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(() => threads[0]?.id ?? null);
  const activeThreadIdRef = useRef<string | null>(selectedThreadId);
  const assistantTextRef = useRef("");
  const activePromptRef = useRef("");
  const [composer, setComposer] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [providers, setProviders] = useState<ProviderCatalogEntry[]>(FALLBACK_PROVIDERS);
  const [providerError, setProviderError] = useState("");
  const [providerRefresh, setProviderRefresh] = useState(0);
  const [providerId, setProviderId] = useState<RunnableProviderId>("codex");
  const [modelId, setModelId] = useState(FALLBACK_PROVIDERS[0].models[0]?.id ?? "");
  const [thinking, setThinking] = useState<ThinkingLevel>("medium");
  const [mode, setMode] = useState<RunMode>("chat");
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [runNote, setRunNote] = useState("");
  const [thinkingNote, setThinkingNote] = useState("");
  const [artifactReady, setArtifactReady] = useState(false);
  const [safetyPreview, setSafetyPreview] = useState<SafetyPreview | null>(null);
  const [safetyLoading, setSafetyLoading] = useState(true);
  const [safetyError, setSafetyError] = useState("");
  const [safetyRefresh, setSafetyRefresh] = useState(0);
  const [safetyDetailsOpen, setSafetyDetailsOpen] = useState(false);
  const [confirmation, setConfirmation] = useState<{ prompt: string; safety: SafetyPreview } | null>(null);
  const [interruption, setInterruption] = useState<{ prompt: string; detail: string } | null>(null);
  const [receipt, setReceipt] = useState<SafetyReceipt | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);
  const [repositories, setRepositories] = useState<ConversationRepository[]>([]);
  const newThreadSignalRef = useRef(newThreadSignal);
  const noun = experience === "developer" ? "thread" : "conversation";
  const sendKeyMode = loadDevicePreferences(storage, storageScope).sendKeyMode;
  const selected = threads.find((thread) => thread.id === selectedThreadId) ?? null;
  const provider = providers.find((entry) => entry.id === providerId) ?? FALLBACK_PROVIDERS[0];
  const providerModels = provider.models ?? [];
  const providerThinkingLevels = provider.thinking_levels ?? [];

  useEffect(() => () => streamRef.current?.close(), []);
  useEffect(() => saveDeviceThreads(storage, storageScope, threads), [storage, storageScope, threads]);
  useEffect(() => {
    if (api.listRepositories === undefined) return;
    let current = true;
    void api.listRepositories().then((items) => {
      if (current) setRepositories(items);
    }).catch(() => {
      if (current) setRepositories([]);
    });
    return () => { current = false; };
  }, [api]);
  useEffect(() => {
    let current = true;
    setSafetyLoading(true);
    setSafetyError("");
    setSafetyPreview(null);
    void api.getSafetyPreview(providerId, mode, mode === "build" && mcpEnabled).then((preview) => {
      if (current) setSafetyPreview(preview);
    }).catch(() => {
      if (current) setSafetyError("Safety policy unavailable. Runs are paused until Corvus can verify it.");
    }).finally(() => {
      if (current) setSafetyLoading(false);
    });
    return () => { current = false; };
  }, [api, providerId, mode, mcpEnabled, safetyRefresh]);
  useEffect(() => {
    let current = true;
    void Promise.all([api.listProviders(), api.getPreferences()]).then(([catalog, preferences]) => {
      if (!current) return;
      if (catalog.length === 0) {
        setProviders(FALLBACK_PROVIDERS);
        setProviderError("No supported local agents were detected. Install Codex CLI or Claude Code, then retry.");
        return;
      }
      const readyCatalog = catalog.filter((entry) => entry.status === "ready");
      if (readyCatalog.length === 0) {
        setProviders(FALLBACK_PROVIDERS);
        setProviderError("No configured agents are ready. Configure a local CLI or API key in Settings, then retry.");
        return;
      }
      setProviders(readyCatalog);
      setProviderError("");
      const preferred = catalog.find((entry) =>
        entry.id === preferences.default_provider && entry.status === "ready"
      );
      const ready = preferred ?? catalog.find((entry) =>
        entry.status === "ready"
      );
      if (ready !== undefined) {
        const readyModels = ready.models ?? [];
        const readyThinkingLevels = ready.thinking_levels ?? [];
        setProviderId(ready.id as RunnableProviderId);
        setModelId(
          preferences.default_model !== null ? preferences.default_model : readyModels[0]?.id ?? ""
        );
        setThinking(
          readyThinkingLevels.includes(preferences.default_effort)
            ? preferences.default_effort
            : readyThinkingLevels.includes("medium") ? "medium" : readyThinkingLevels[0] ?? "medium"
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

  const createConversation = useCallback((repository: ConversationRepository | null = null): DeviceThread => {
    const now = new Date().toISOString();
    const created: DeviceThread = {
      id: crypto.randomUUID(),
      title: experience === "developer" ? "New thread" : "New conversation",
      createdAt: now,
      updatedAt: now,
      repositoryId: repository?.id,
      repositoryName: repository?.display_name,
      workingDirectory: repository?.path,
      messages: []
    };
    setThreads((current) => [created, ...current]);
    setSelectedThreadId(created.id);
    activeThreadIdRef.current = created.id;
    setAssistantText("");
    assistantTextRef.current = "";
    setHistoryOpen(false);
    return created;
  }, [experience]);

  function selectRepository(repository: ConversationRepository | null): void {
    if (selected) {
      setThreads((current) => current.map((item) => item.id === selected.id ? {
        ...item,
        repositoryId: repository?.id,
        repositoryName: repository?.display_name,
        workingDirectory: repository?.path
      } : item));
    } else {
      createConversation(repository);
    }
    setProjectMenuOpen(false);
  }

  useEffect(() => {
    if (newThreadSignalRef.current === newThreadSignal) return;
    newThreadSignalRef.current = newThreadSignal;
    createConversation();
  }, [createConversation, newThreadSignal]);

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

  function loadSafetyReceipt(activeRunId: string): void {
    void api.getSafetyReceipt(activeRunId).then(setReceipt).catch(() => {
      setError("The run ended, but its safety receipt is not available yet.");
    });
  }

  function listen(stream: RunEventStream, activeRunId: string): void {
    streamRef.current?.close();
    streamRef.current = stream;
    stream.addEventListener("started", () => setRunNote("Protected runtime started"));
    stream.addEventListener("message", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { text?: unknown } } | null;
        if (typeof event?.payload?.text === "string") {
          assistantTextRef.current += event.payload.text;
          setAssistantText(assistantTextRef.current);
        }
      } catch { setError("Corvus received an unreadable run event."); }
    });
    stream.addEventListener("thinking", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { text?: unknown; summary?: unknown } } | null;
        const note = event?.payload?.summary ?? event?.payload?.text;
        if (typeof note === "string") setThinkingNote(note);
      } catch { setError("Corvus received an unreadable thinking event."); }
    });
    stream.addEventListener("status", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { activity?: unknown } } | null;
        setRunNote(activityLabel(event?.payload?.activity));
      } catch { setError("Corvus received an unreadable status event."); }
    });
    stream.addEventListener("artifact", () => setArtifactReady(true));
    stream.addEventListener("completed", () => {
      loadSafetyReceipt(activeRunId);
      finishRun("completed", assistantTextRef.current);
    });
    stream.addEventListener("cancelled", () => {
      loadSafetyReceipt(activeRunId);
      finishRun("cancelled");
    });
    stream.addEventListener("failed", ({ data }) => {
      let reasonCode = "run_failed";
      try {
        const event = JSON.parse(data) as { payload?: { reason_code?: unknown } } | null;
        if (typeof event?.payload?.reason_code === "string") reasonCode = event.payload.reason_code;
      } finally {
        loadSafetyReceipt(activeRunId);
        const partialResponse = assistantTextRef.current;
        if (safetyPreview?.level === "read_only" && (
          reasonCode.startsWith("process_") || reasonCode.includes("sandbox") || reasonCode.includes("permission")
        )) {
          setError("");
          setInterruption({
            prompt: activePromptRef.current,
            detail: "Read-only mode prevented this run from making the requested change. The response already received is preserved."
          });
        } else if (reasonCode.includes("model")) {
          setError("The selected model is not available for this provider. Change it in Settings, then try again.");
        } else {
          setError("This run stopped before it could finish. You can retry or change its safety mode.");
        }
        finishRun("failed", partialResponse);
      }
    });
    stream.onTerminalError(() => {
      if (streamRef.current !== stream) return;
      setError("Connection to this run ended before completion. Start the run again to continue.");
      finishRun("failed");
    });
  }

  async function startPrompt(prompt: string, safety: SafetyPreview): Promise<void> {
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
    activePromptRef.current = prompt;
    setRunStatus("working");
    setBusy(true);
    setError("");
    setRunNote("");
    setThinkingNote("");
    setArtifactReady(false);
    setReceipt(null);
    setInterruption(null);
    try {
      const run = await api.startRun(prompt, {
        provider: providerId,
        model: modelId || null,
        effort: thinking,
        mode,
        mcp_enabled: mode === "build" && mcpEnabled,
        safety_digest: safety.policy_digest,
        ...(thread.repositoryId ? { repository_id: thread.repositoryId } : {})
      }, crypto.randomUUID());
      setRunId(run.run_id);
      if (run.working_directory) {
        setThreads((current) => current.map((item) => item.id === thread.id
          ? { ...item, workingDirectory: run.working_directory }
          : item));
      }
      listen(api.openRunEvents(run.run_id), run.run_id);
    } catch (reason) {
      setRunStatus("failed");
      setError(safeMessage(reason));
    } finally { setBusy(false); }
  }

  async function send(event: FormEvent): Promise<void> {
    event.preventDefault();
    const prompt = composer.trim();
    if (
      prompt === "" || runStatus === "working" || provider.status !== "ready" ||
      safetyPreview === null || safetyLoading
    ) return;
    if (safetyPreview.requires_confirmation) {
      setConfirmation({ prompt, safety: safetyPreview });
      return;
    }
    await startPrompt(prompt, safetyPreview);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    const modifierSend = event.ctrlKey || event.metaKey;
    const shouldSend = modifierSend || sendKeyMode === "enter" || (
      sendKeyMode === "adaptive" && !composer.includes("\n")
    );
    if (!shouldSend) return;
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  async function stop(): Promise<void> {
    if (runId === null) return;
    const activeRunId = runId;
    setBusy(true);
    try {
      const result = await api.cancelRun(activeRunId);
      if (result.state === "running") {
        setRunNote("Cancellation was not accepted; the run is still working.");
        return;
      }
      loadSafetyReceipt(activeRunId);
      finishRun(result.state);
    } catch (reason) { setError(safeMessage(reason)); }
    finally { setBusy(false); }
  }

  return (
    <section className="conversation-workspace" aria-label="Corvus conversations">
      <div className="conversation-panel">
        <header className="conversation-panel__header">
          <div><h1>{selected?.title ?? (experience === "developer" ? "New thread" : "New conversation")}</h1><span className="conversation-context" title={selected?.workingDirectory ?? workingDirectory}>{selected?.workingDirectory ?? workingDirectory ?? "Corvus agent workspace"}</span></div>
          <div className="conversation-actions">
            <button aria-expanded={historyOpen} aria-label="Conversation history" className="icon-button" data-component-source="lucide-message-square" onClick={() => setHistoryOpen((open) => !open)} type="button"><Icon name="history" /></button>
            <button aria-label={`New ${noun}`} className="icon-button" onClick={() => createConversation()} type="button"><Icon name="new" /></button>
          </div>
          {historyOpen ? <div className="conversation-history" role="dialog" aria-label="Conversation history panel">
            <strong>{experience === "developer" ? "Threads" : "Conversations"}</strong>
            {threads.length === 0 ? <p className="thread-list__empty">No conversations yet</p> : null}
            <div className="thread-list__items">{threads.map((thread) => <button aria-current={selectedThreadId === thread.id ? "true" : undefined} key={thread.id} onClick={() => { setSelectedThreadId(thread.id); activeThreadIdRef.current = thread.id; setAssistantText(""); assistantTextRef.current = ""; setHistoryOpen(false); }} type="button"><strong>{thread.title}</strong><span>{new Date(thread.updatedAt).toLocaleDateString()}</span></button>)}</div>
          </div> : null}
        </header>
        <div className="message-transcript">
          {(selected?.messages.length ?? 0) === 0 && assistantText === "" ? <div className="conversation-empty"><BrandMark className="conversation-mark" decorative /><h2>{experience === "developer" ? "What would you like to start?" : "What can Corvus help you finish?"}</h2><p>Ask a question or hand off a complete task. Build mode works in an isolated sandbox and returns the finished project.</p><div className="starter-prompts">{(experience === "developer" ? ["Inspect this repository", "Fix the failing tests", "Build a small feature"] : ["Plan my week", "Draft a clear update", "Organize these notes"]).map((starter) => <button key={starter} onClick={() => setComposer(starter)} type="button">{starter}</button>)}</div></div> : null}
          {selected?.messages.map((message) => <article className={`message message--${message.role}`} key={message.id}><span>{message.role === "user" ? "You" : "Corvus"}</span><MarkdownMessage>{message.content}</MarkdownMessage></article>)}
          {runStatus === "working" ? <section className="run-activity" aria-label="Run status: working"><div className="run-activity__status" role="status"><span className="activity-pulse" /><strong>Working</strong>{runNote ? <span>{runNote}</span> : null}</div><ol aria-label="Safety timeline" className="safety-timeline"><li><Icon name="shield" /><span><strong>{safetyPreview?.label ?? "Policy verified"}</strong><small>Policy locked for this run</small></span></li>{runNote ? <li><span className="safety-timeline__dot" /><span><strong>{runNote}</strong><small>Observed runtime activity</small></span></li> : null}</ol>{thinkingNote ? <details open><summary>Thinking</summary><p>{thinkingNote}</p></details> : null}</section> : null}
          {assistantText !== "" ? <article className="message message--assistant"><span>Corvus</span><MarkdownMessage>{assistantText}</MarkdownMessage></article> : null}
          {artifactReady && runId !== null ? <a className="artifact-download" href={api.artifactUrl(runId)}><Icon name="download" />Download finished project</a> : null}
          {receipt ? <section aria-label="Safety receipt" className="safety-receipt"><header><Icon name="shield" /><div><strong>Safety receipt</strong><span>{receipt.status === "completed" ? "Run completed inside its locked policy" : `Run ${receipt.status}`}</span></div></header><div className="safety-receipt__facts"><span>Original project unchanged</span><span>No blanket host access</span>{receipt.artifact?.secret_screening === "passed" ? <span>Artifact screening passed</span> : receipt.artifact ? <span>Artifact was not secret-screened</span> : null}</div>{receipt.activities.length > 0 ? <ul>{receipt.activities.map((activity) => <li key={activity}>{activity}</li>)}</ul> : null}<details><summary>Verification details</summary><p>{receipt.approval}</p><code>{receipt.safety.policy_digest}</code></details></section> : null}
          {runStatus !== "idle" && runStatus !== "working" ? <p className="run-result-status" aria-label={`Run status: ${runStatus}`} data-status={runStatus}>{runStatus[0].toUpperCase() + runStatus.slice(1)}</p> : null}
          {interruption ? <section aria-label="Run paused by safety settings" className="run-interruption">
            <div><Icon name="shield" /><div><strong>Corvus paused this run</strong><p>{interruption.detail}</p></div></div>
            <div className="run-interruption__actions"><button className="button button--primary" onClick={() => { setMode("build"); setMcpEnabled(false); setComposer(interruption.prompt); setInterruption(null); setError(""); }} type="button">Switch to Build</button><button className="button" onClick={() => { setInterruption(null); setError(""); }} type="button">Stop here</button></div>
          </section> : null}
        </div>
        {providerError ? <p className="conversation-error" role="alert">{providerError} <button aria-label="Retry providers" className="text-button" onClick={() => setProviderRefresh((value) => value + 1)} type="button">Retry</button></p> : null}
        {safetyError ? <p className="conversation-error" role="alert">{safetyError} <button aria-label="Retry safety policy" className="text-button" onClick={() => setSafetyRefresh((value) => value + 1)} type="button">Retry</button></p> : null}
        {error ? <p className="conversation-error" role="alert">{error}</p> : null}
        <form className="composer" onSubmit={(event) => void send(event)}>
          <label className="sr-only" htmlFor="corvus-composer">Message Corvus</label><textarea aria-label="Message Corvus" id="corvus-composer" onChange={(event) => setComposer(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder={experience === "developer" ? "Ask Corvus to work in this repository…" : "Describe what you want to get done…"} rows={2} value={composer} />
          <div className="composer__controls">
            <div className="composer-project"><button aria-expanded={projectMenuOpen} className="composer-project__trigger" onClick={() => setProjectMenuOpen((open) => !open)} type="button">Project · {selected?.repositoryName ?? "Agent directory"}</button>{projectMenuOpen ? <section aria-label="Project context" className="composer-project__menu"><strong>Project context</strong><button aria-current={selected?.repositoryId === undefined ? "true" : undefined} onClick={() => selectRepository(null)} type="button"><span>Agent directory</span><small>A fresh Corvus workspace for this thread</small></button>{repositories.map((repository) => <button aria-current={selected?.repositoryId === repository.id ? "true" : undefined} key={repository.id} onClick={() => selectRepository(repository)} type="button"><span>{repository.display_name}</span><small>{repository.path}</small></button>)}<button onClick={() => { setProjectMenuOpen(false); onOpenProjects?.(); }} type="button"><span>Connect or create a project</span><small>GitHub repository, local folder, or new project</small></button></section> : null}</div>
            <span className="composer-leading-icon" title="Agent provider"><Icon name="agent" /></span>
            <label className="sr-only" htmlFor="composer-provider">Provider</label><select aria-label="Agent provider" className="composer-control composer-control--provider" disabled={runStatus === "working"} id="composer-provider" onChange={(event) => {
              const next = event.target.value as ProviderId;
              const nextProvider = providers.find((entry) => entry.id === next);
              if (nextProvider?.status !== "ready") return;
              setProviderId(next as RunnableProviderId);
              const nextModels = nextProvider.models ?? [];
              const nextThinkingLevels = nextProvider.thinking_levels ?? [];
              setModelId(nextModels[0]?.id ?? "");
              setThinking(nextThinkingLevels.includes("medium") ? "medium" : nextThinkingLevels[0] ?? "medium");
              if (next !== "codex") { setMode("chat"); setMcpEnabled(false); }
            }} value={providerId}>{providers.filter((entry) => entry.status === "ready").map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}</select>
            <span className="composer-leading-icon" title="Model"><Icon name="model" /></span><label className="sr-only" htmlFor="composer-model">Model</label><select aria-label="Agent model" className="composer-control composer-control--model" disabled={runStatus === "working" || (providerModels.length === 0 && modelId === "")} id="composer-model" onChange={(event) => setModelId(event.target.value)} value={modelId}>{modelId !== "" && !providerModels.some((entry) => entry.id === modelId) ? <option value={modelId}>{modelId}</option> : null}{providerModels.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}</select>
            <span className="composer-leading-icon" title="Thinking effort"><Icon name="thinking" /></span><label className="sr-only" htmlFor="composer-thinking">Thinking</label><select aria-label="Thinking level" className="composer-control" disabled={runStatus === "working" || providerThinkingLevels.length === 0} id="composer-thinking" onChange={(event) => setThinking(event.target.value as ThinkingLevel)} value={thinking}>{providerThinkingLevels.map((level) => <option key={level} value={level}>{THINKING_LABELS[level]}</option>)}</select>
            <span className="composer-leading-icon" title="Run mode"><Icon name="mode" /></span><label className="sr-only" htmlFor="composer-mode">Mode</label><select aria-label="Run mode" className="composer-control" disabled={runStatus === "working"} id="composer-mode" onChange={(event) => { const next = event.target.value as RunMode; setMode(next); if (next === "chat") setMcpEnabled(false); }} value={mode}><option value="chat">Chat</option><option disabled={providerId !== "codex"} value="build">Build</option></select>
            {mode === "build" ? <label className="mcp-toggle"><input aria-label="Allow configured MCP servers" checked={mcpEnabled} onChange={(event) => setMcpEnabled(event.target.checked)} type="checkbox" /><span>MCP</span></label> : null}
            <button aria-expanded={safetyDetailsOpen} aria-label="View safety details" className={`safety-chip safety-chip--${safetyPreview?.level ?? "loading"}`} disabled={safetyLoading} onClick={() => setSafetyDetailsOpen((open) => !open)} title="Click to see details" type="button"><Icon name="shield" /><span>{safetyLoading ? "Checking safety" : safetyPreview?.label ?? "Safety unavailable"}</span></button>
            {runStatus === "working" ? <button aria-label="Stop" className="composer-submit composer-submit--stop" disabled={busy} onClick={() => void stop()} type="button"><Icon name="stop" /></button> : <button aria-label={mode === "build" ? "Build project" : "Send message"} className="composer-submit" data-component-source="shadcn-button" disabled={busy || composer.trim() === "" || provider.status !== "ready" || safetyPreview === null || safetyLoading} type="submit"><Icon name="send" /></button>}
          </div>
          {safetyDetailsOpen && safetyPreview ? <section aria-label="Safety details" className="safety-details"><header><Icon name="shield" /><div><strong>{safetyPreview.label}</strong><span>{safetyPreview.summary}</span></div></header><dl><div><dt>Files</dt><dd>{safetyPreview.filesystem}</dd></div><div><dt>Network</dt><dd>{safetyPreview.network}</dd></div><div><dt>Tools</dt><dd>{safetyPreview.mcp}</dd></div><div><dt>Output</dt><dd>{safetyPreview.output}</dd></div></dl></section> : null}
          {mode === "build" && mcpEnabled ? <p className="composer__notice">Configured MCP servers may access external systems. Corvus will work only inside a fresh build sandbox.</p> : null}
        </form>
        {confirmation ? <div aria-label="Confirm protected build" aria-modal="true" className="safety-confirmation" role="dialog"><div className="safety-confirmation__sheet"><header><Icon name="shield" /><div><span>{confirmation.safety.label}</span><h2>Confirm protected build</h2></div></header><p>{confirmation.safety.summary}</p><dl><div><dt>Workspace</dt><dd>{confirmation.safety.filesystem}</dd></div><div><dt>Network</dt><dd>{confirmation.safety.network}</dd></div><div><dt>External tools</dt><dd>{confirmation.safety.mcp}</dd></div><div><dt>Approval</dt><dd>{confirmation.safety.approvals}</dd></div></dl><div className="safety-confirmation__actions"><button className="text-button" onClick={() => setConfirmation(null)} type="button">Cancel</button><button className="primary-action" onClick={() => { const pending = confirmation; setConfirmation(null); void startPrompt(pending.prompt, pending.safety); }} type="button">Continue in sandbox</button></div></div></div> : null}
      </div>
    </section>
  );
}
