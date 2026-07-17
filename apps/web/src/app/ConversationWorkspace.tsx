import { useEffect, useRef, useState, type FormEvent } from "react";

import type { ConversationApi, RunEventStream } from "./conversationApi";
import { loadDeviceThreads, saveDeviceThreads, type DeviceThread } from "./conversationStorage";

type Experience = "developer" | "everyday";
type RunStatus = "idle" | "working" | "completed" | "cancelled" | "failed";
const TITLE_MAX = 72;

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
  const noun = experience === "developer" ? "thread" : "conversation";
  const selected = threads.find((thread) => thread.id === selectedThreadId) ?? null;

  useEffect(() => () => streamRef.current?.close(), []);
  useEffect(() => saveDeviceThreads(storage, storageScope, threads), [storage, storageScope, threads]);

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
    stream.addEventListener("completed", () => finishRun("completed", assistantTextRef.current));
    stream.addEventListener("cancelled", () => finishRun("cancelled"));
    stream.addEventListener("failed", ({ data }) => {
      try {
        const event = JSON.parse(data) as { payload?: { reason_code?: unknown } };
        if (typeof event.payload?.reason_code === "string") setError(event.payload.reason_code.replaceAll("_", " "));
      } finally { finishRun("failed"); }
    });
  }

  async function send(event: FormEvent): Promise<void> {
    event.preventDefault();
    const prompt = composer.trim();
    if (prompt === "" || runStatus === "working") return;
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
    try {
      const run = await api.startRun(prompt, { model: null, effort: "normal" }, crypto.randomUUID());
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
      <aside className="thread-list" aria-label={`${noun} list`}>
        <div className="thread-list__heading"><div><span className="eyebrow">This device</span><strong>{experience === "developer" ? "Threads" : "Conversations"}</strong></div><button className="button button--quiet" onClick={createConversation} type="button">New {noun}</button></div>
        {threads.length === 0 ? <p className="thread-list__empty">No conversations yet</p> : null}
        <div className="thread-list__items">{threads.map((thread) => <button aria-current={selectedThreadId === thread.id ? "true" : undefined} key={thread.id} onClick={() => { setSelectedThreadId(thread.id); activeThreadIdRef.current = thread.id; setAssistantText(""); assistantTextRef.current = ""; }} type="button"><strong>{thread.title}</strong><span>{new Date(thread.updatedAt).toLocaleDateString()}</span></button>)}</div>
      </aside>
      <div className="conversation-panel">
        <header className="conversation-panel__header"><div><span className="eyebrow">This device</span><h1>{selected?.title ?? "What should Corvus do?"}</h1></div><div className="runtime-chip"><span aria-hidden="true" /> Local Codex · Codex default</div></header>
        <div className="run-flightline" aria-label={`Run status: ${runStatus}`} data-status={runStatus}><span>Plan</span><i /><span>Work</span><i /><span>Result</span><strong>{runStatus === "idle" ? "Ready" : runStatus[0].toUpperCase() + runStatus.slice(1)}</strong></div>
        <div className="message-transcript" aria-live="polite">
          {(selected?.messages.length ?? 0) === 0 && assistantText === "" ? <div className="conversation-empty"><p className="eyebrow">Start here</p><h2>{experience === "developer" ? "Ask Corvus to inspect, change, or explain." : "Describe the result you want."}</h2><p>Runs use your paired Local Codex. Conversation history stays on this device.</p></div> : null}
          {selected?.messages.map((message) => <article className={`message message--${message.role}`} key={message.id}><span>{message.role === "user" ? "You" : "Corvus"}</span><p>{message.content}</p></article>)}
          {assistantText !== "" ? <article className="message message--assistant"><span>Corvus</span><p>{assistantText}</p></article> : null}
        </div>
        {error ? <p className="conversation-error" role="alert">{error}</p> : null}
        <form className="composer" onSubmit={(event) => void send(event)}>
          <label className="sr-only" htmlFor="corvus-composer">Message Corvus</label><textarea aria-label="Message Corvus" id="corvus-composer" onChange={(event) => setComposer(event.target.value)} placeholder={experience === "developer" ? "Ask Corvus to work in this repository…" : "Describe what you want to get done…"} rows={3} value={composer} />
          <div className="composer__controls"><label>Provider<select aria-label="Agent provider" disabled value="codex"><option value="codex">Local Codex</option></select></label><label>Model<select aria-label="Agent model" disabled value="default"><option value="default">Codex default</option></select></label><span className="preview-chip">Others · Coming soon</span>{runStatus === "working" ? <button className="button button--danger" disabled={busy} onClick={() => void stop()} type="button">Stop run</button> : <button className="button button--primary" disabled={busy || composer.trim() === ""} type="submit">Send message</button>}</div>
        </form>
      </div>
    </section>
  );
}
