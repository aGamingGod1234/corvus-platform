import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type {
  LocalRepository,
  LocalRun,
  LocalRunEvent,
  LocalRunEvidence,
  LocalSafetyPreview
} from "../api";
import { ContributionPanel, type ContributionApi } from "./ContributionPanel";

export interface RunsApi extends ContributionApi {
  listRepositories(): Promise<LocalRepository[]>;
  getLocalSafetyPreview(mode: "chat" | "build"): Promise<LocalSafetyPreview>;
  listLocalRuns(): Promise<LocalRun[]>;
  startLocalRun(input: {
    repositoryId: string;
    task: string;
    model?: string;
    effort: "low" | "medium" | "high" | "xhigh";
    mode: "chat" | "build";
    safetyDigest: string;
    outputPolicy: "report_only" | "prepare_changes" | "prepare_contribution";
  }): Promise<LocalRun>;
  getLocalRun(runId: string): Promise<LocalRun>;
  listLocalRunEvents(runId: string, after?: number): Promise<LocalRunEvent[]>;
  listLocalRunEvidence(runId: string): Promise<LocalRunEvidence[]>;
  cancelLocalRun(runId: string): Promise<LocalRun>;
  retryLocalRun(runId: string): Promise<LocalRun>;
  discardLocalRun(runId: string): Promise<LocalRun>;
}

const ACTIVE = new Set(["preparing", "running", "publishing"]);
const RETRYABLE = new Set(["completed", "cancelled", "interrupted", "failed"]);
const DISCARDABLE = new Set(["review_required", "contribution_ready", "completed", "cancelled", "interrupted", "failed"]);

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : "run_request_failed";
}

function eventSummary(event: LocalRunEvent): string {
  const message = event.payload.message ?? event.payload.status ?? event.payload.reason_code;
  return typeof message === "string" ? message : event.event_type.replaceAll(".", " ");
}

export function RunsWorkspace({ api }: { api: RunsApi }) {
  const [repositories, setRepositories] = useState<LocalRepository[]>([]);
  const [runs, setRuns] = useState<LocalRun[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<LocalRunEvent[]>([]);
  const [evidence, setEvidence] = useState<LocalRunEvidence[]>([]);
  const [creating, setCreating] = useState(false);
  const [repositoryId, setRepositoryId] = useState("");
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"chat" | "build">("build");
  const [effort, setEffort] = useState<"low" | "medium" | "high" | "xhigh">("high");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? null,
    [runs, selectedId]
  );

  const load = useCallback(async () => {
    const [loadedRepositories, loadedRuns] = await Promise.all([
      api.listRepositories(),
      api.listLocalRuns()
    ]);
    setRepositories(loadedRepositories);
    setRuns(loadedRuns);
    setSelectedId((current) => current ?? loadedRuns[0]?.id ?? null);
    setRepositoryId((current) => current || loadedRepositories[0]?.id || "");
  }, [api]);

  useEffect(() => {
    void load().catch((reason: unknown) => setError(readableError(reason)));
  }, [load]);

  useEffect(() => {
    if (selectedId === null) {
      setEvents([]);
      setEvidence([]);
      return;
    }
    let active = true;
    async function refreshDetail(): Promise<void> {
      const [record, loadedEvents, loadedEvidence] = await Promise.all([
        api.getLocalRun(selectedId!),
        api.listLocalRunEvents(selectedId!),
        api.listLocalRunEvidence(selectedId!)
      ]);
      if (!active) return;
      setRuns((current) => current.map((item) => item.id === record.id ? record : item));
      setEvents(loadedEvents);
      setEvidence(loadedEvidence);
    }
    void refreshDetail().catch((reason: unknown) => active && setError(readableError(reason)));
    const timer = window.setInterval(() => {
      if (selected && ACTIVE.has(selected.status)) {
        void refreshDetail().catch((reason: unknown) => active && setError(readableError(reason)));
      }
    }, 750);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, selectedId, selected?.status]);

  async function start(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!repositoryId || !task.trim()) return;
    setBusy(true);
    setError("");
    try {
      const preview = await api.getLocalSafetyPreview(mode);
      const run = await api.startLocalRun({
        repositoryId,
        task: task.trim(),
        effort,
        mode,
        safetyDigest: preview.policy_digest,
        outputPolicy: mode === "build" ? "prepare_contribution" : "report_only"
      });
      setRuns((current) => [run, ...current]);
      setSelectedId(run.id);
      setTask("");
      setCreating(false);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function mutate(action: "cancel" | "retry" | "discard"): Promise<void> {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const record = action === "cancel"
        ? await api.cancelLocalRun(selected.id)
        : action === "retry"
          ? await api.retryLocalRun(selected.id)
          : await api.discardLocalRun(selected.id);
      if (action === "retry") {
        setRuns((current) => [record, ...current]);
        setSelectedId(record.id);
      } else {
        setRuns((current) => current.map((item) => item.id === record.id ? record : item));
      }
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="runs-title" className="runs-workspace">
      <header className="resource-heading">
        <div><p className="eyebrow">Supervised execution</p><h1 id="runs-title">Runs</h1><p>Build in an isolated worktree, inspect durable evidence, then choose what leaves your machine.</p></div>
        <button className="button button--primary" disabled={repositories.length === 0} onClick={() => setCreating(true)} type="button">New run</button>
      </header>
      {creating ? <form className="run-composer" onSubmit={(event) => void start(event)}>
        <label htmlFor="run-repository">Repository</label>
        <select id="run-repository" onChange={(event) => setRepositoryId(event.target.value)} value={repositoryId}>{repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.display_name}</option>)}</select>
        <label htmlFor="run-task">Task</label>
        <textarea autoFocus id="run-task" onChange={(event) => setTask(event.target.value)} placeholder="Describe the focused change to build…" rows={5} value={task} />
        <div className="run-composer__options"><label>Mode<select onChange={(event) => setMode(event.target.value as "chat" | "build")} value={mode}><option value="build">Build changes</option><option value="chat">Inspect only</option></select></label><label>Reasoning<select onChange={(event) => setEffort(event.target.value as typeof effort)} value={effort}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="xhigh">Extra high</option></select></label></div>
        <div className="row-actions"><button className="button" onClick={() => setCreating(false)} type="button">Cancel</button><button className="button button--primary" disabled={busy || !repositoryId || !task.trim()} type="submit">{busy ? "Starting…" : "Start supervised run"}</button></div>
      </form> : null}
      {repositories.length === 0 ? <div className="resource-empty"><strong>Connect a repository first</strong><span>Runs need a real Git checkout and create no changes in the source directory.</span></div> : null}
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <div className="runs-layout">
        <div aria-label="Run history" className="run-list">{runs.length === 0 ? <div className="resource-empty"><strong>No runs yet</strong><span>Start one to see its live state and evidence here.</span></div> : runs.map((run) => <button aria-pressed={run.id === selectedId} className="run-list__item" key={run.id} onClick={() => setSelectedId(run.id)} type="button"><span className="run-status" data-status={run.status}>{run.status.replaceAll("_", " ")}</span><strong>{run.task}</strong><small>{repositories.find((repo) => repo.id === run.repository_id)?.display_name ?? "Repository"} · {new Date(run.created_at).toLocaleString()}</small></button>)}</div>
        {selected ? <article className="run-detail"><header><div><span className="run-status" data-status={selected.status}>{selected.status.replaceAll("_", " ")}</span><h2>{selected.task}</h2></div><div className="row-actions">{ACTIVE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("cancel")} type="button">Stop</button> : null}{RETRYABLE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("retry")} type="button">Retry</button> : null}{DISCARDABLE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("discard")} type="button">Discard worktree</button> : null}</div></header><dl className="run-metadata"><div><dt>Mode</dt><dd>{selected.mode}</dd></div><div><dt>Reasoning</dt><dd>{selected.effort}</dd></div><div><dt>Base</dt><dd>{selected.base_sha.slice(0, 8)}</dd></div><div><dt>Run</dt><dd>{selected.id.slice(0, 8)}</dd></div></dl><section><h3>Activity</h3><ol className="run-events">{events.length === 0 ? <li>Waiting for provider activity…</li> : events.map((item) => <li key={item.sequence}><span>{item.sequence}</span><div><strong>{eventSummary(item)}</strong><small>{item.event_type}</small></div></li>)}</ol></section>{evidence.length > 0 ? <section><h3>Evidence</h3>{evidence.map((item) => <div className="evidence-card" key={item.id}><strong>{item.kind}</strong><span>{item.summary}</span></div>)}</section> : null}</article> : null}
      </div>
      {selected?.status === "review_required" || selected?.status === "contribution_ready" ? <ContributionPanel api={api} runId={selected.id} /> : null}
    </section>
  );
}
