import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type {
  LocalProviderCatalogEntry,
  LocalRepository,
  LocalRun,
  LocalRunEvent,
  LocalRunEvidence,
  LocalSafetyPreview,
  PortableSkill
} from "../api";
import { ContributionPanel, type ContributionApi } from "./ContributionPanel";

export interface RunsApi extends ContributionApi {
  listRepositories(): Promise<LocalRepository[]>;
  listLocalProviders(): Promise<LocalProviderCatalogEntry[]>;
  listPortableSkills(): Promise<PortableSkill[]>;
  getLocalSafetyPreview(mode: "chat" | "build"): Promise<LocalSafetyPreview>;
  listLocalRuns(): Promise<LocalRun[]>;
  startLocalRun(input: {
    repositoryId: string;
    task: string;
    model?: string;
    effort: "low" | "medium" | "high" | "xhigh";
    mode: "chat" | "build";
    safetyDigest: string;
    skillVersionId?: string;
    outputPolicy: "report_only" | "prepare_changes" | "prepare_contribution";
  }): Promise<LocalRun>;
  getLocalRun(runId: string): Promise<LocalRun>;
  listLocalRunEvents(runId: string, after?: number): Promise<LocalRunEvent[]>;
  listLocalRunEvidence(runId: string): Promise<LocalRunEvidence[]>;
  cancelLocalRun(runId: string): Promise<LocalRun>;
  retryLocalRun(runId: string): Promise<LocalRun>;
  discardLocalRun(runId: string): Promise<LocalRun>;
}

type OutputPolicy = "report_only" | "prepare_changes" | "prepare_contribution";
type Effort = "low" | "medium" | "high" | "xhigh";

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

function effortLabel(effort: string): string {
  return effort === "xhigh" ? "Extra high" : effort[0].toUpperCase() + effort.slice(1);
}

export function RunsWorkspace({
  api,
  initialRepositoryId,
  initialSkillId,
  onNavigate
}: {
  api: RunsApi;
  initialRepositoryId?: string;
  initialSkillId?: string;
  onNavigate?(route: "settings" | "repositories" | "skills"): void;
}) {
  const [repositories, setRepositories] = useState<LocalRepository[]>([]);
  const [providers, setProviders] = useState<LocalProviderCatalogEntry[]>([]);
  const [skills, setSkills] = useState<PortableSkill[]>([]);
  const [runs, setRuns] = useState<LocalRun[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<LocalRunEvent[]>([]);
  const [evidence, setEvidence] = useState<LocalRunEvidence[]>([]);
  const [creating, setCreating] = useState(false);
  const [repositoryId, setRepositoryId] = useState("");
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"chat" | "build">("build");
  const [effort, setEffort] = useState<Effort>("high");
  const [model, setModel] = useState("");
  const [skillId, setSkillId] = useState("");
  const [outputPolicy, setOutputPolicy] = useState<OutputPolicy>("prepare_contribution");
  const [providerError, setProviderError] = useState("");
  const [providerRefresh, setProviderRefresh] = useState(0);
  const [providerLoading, setProviderLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? null,
    [runs, selectedId]
  );
  const codex = useMemo(
    () => providers.find((provider) => provider.id === "codex") ?? null,
    [providers]
  );
  const codexReady = codex?.status === "ready";
  const activeSkills = useMemo(
    () => skills.filter((skill) => skill.status === "active"),
    [skills]
  );
  const healthyRepositories = useMemo(
    () => repositories.filter((repository) => repository.snapshot.health === "healthy"),
    [repositories]
  );

  const load = useCallback(async () => {
    const [loadedRepositories, loadedRuns, loadedSkills] = await Promise.all([
      api.listRepositories(),
      api.listLocalRuns(),
      api.listPortableSkills()
    ]);
    setRepositories(loadedRepositories);
    setRuns(loadedRuns);
    setSkills(loadedSkills);
    setSelectedId((current) => current ?? loadedRuns[0]?.id ?? null);
    setRepositoryId((current) => (
      initialRepositoryId && loadedRepositories.some((repository) => repository.id === initialRepositoryId)
        ? initialRepositoryId
        : current || loadedRepositories[0]?.id || ""
    ));
    setSkillId((current) => (
      initialSkillId && loadedSkills.some((skill) => skill.id === initialSkillId && skill.status === "active")
        ? initialSkillId
        : current
    ));
  }, [api, initialRepositoryId, initialSkillId]);

  useEffect(() => {
    void load().catch((reason: unknown) => setError(readableError(reason)));
  }, [load]);

  useEffect(() => {
    let active = true;
    setProviderError("");
    setProviderLoading(true);
    void api.listLocalProviders().then((catalog) => {
      if (!active) return;
      setProviders(catalog);
      const verifiedCodex = catalog.find((provider) => provider.id === "codex" && provider.status === "ready");
      if (verifiedCodex === undefined) {
        setModel("");
        setProviderError("Codex is not verified. Check the CLI login, then retry provider discovery.");
        return;
      }
      setModel((current) => verifiedCodex.models.some((candidate) => candidate.id === current)
        ? current
        : verifiedCodex.models[0]?.id ?? "");
      setEffort((current) => verifiedCodex.thinking_levels.includes(current)
        ? current
        : "medium");
    }).catch(() => {
      if (!active) return;
      setProviders([]);
      setModel("");
      setProviderError("Provider discovery failed. Runs remain disabled until the backend verifies Codex.");
    }).finally(() => {
      if (active) setProviderLoading(false);
    });
    return () => { active = false; };
  }, [api, providerRefresh]);

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
    if (!repositoryId || !task.trim() || !codexReady || !model) return;
    setBusy(true);
    setError("");
    try {
      const preview = await api.getLocalSafetyPreview(mode);
      const run = await api.startLocalRun({
        repositoryId,
        task: task.trim(),
        model,
        effort,
        mode,
        safetyDigest: preview.policy_digest,
        skillVersionId: skillId || undefined,
        outputPolicy: mode === "chat" ? "report_only" : outputPolicy
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
        <button className="button button--primary" disabled={healthyRepositories.length === 0 || !codexReady || model === ""} onClick={() => setCreating(true)} title={providerLoading ? "Verifying Codex and login" : !codexReady ? "Verify Codex in Settings before starting a run" : undefined} type="button">New run</button>
      </header>

      <section aria-label="Demo readiness" className="demo-readiness">
        <header><strong>Recordable demo path</strong><span>Settings - Repository - Skill - Run - Contribution - Schedule</span></header>
        <ol>
          <li data-ready={codexReady && model.startsWith("gpt-5.6-")}><span />{providerLoading ? "Verifying Codex and login..." : "Verified Codex + GPT-5.6"}{!providerLoading && !codexReady && onNavigate ? <button onClick={() => onNavigate("settings")} type="button">Open Settings</button> : null}</li>
          <li data-ready={healthyRepositories.length > 0}><span />Healthy repository{healthyRepositories.length === 0 && onNavigate ? <button onClick={() => onNavigate("repositories")} type="button">Add repository</button> : null}</li>
          <li data-ready={activeSkills.length > 0}><span />Active reviewed skill{activeSkills.length === 0 && onNavigate ? <button onClick={() => onNavigate("skills")} type="button">Review skills</button> : null}</li>
        </ol>
        <p>Corvus records only backend evidence. Test results and full safety receipts stay marked unavailable unless this run actually produces them.</p>
      </section>

      {providerError ? <p className="inline-error provider-recovery" role="alert">{providerError} <button className="text-button" onClick={() => setProviderRefresh((value) => value + 1)} type="button">Retry providers</button></p> : null}
      {creating ? <form className="run-composer" onSubmit={(event) => void start(event)}>
        <label htmlFor="run-repository">Repository</label>
        <select id="run-repository" onChange={(event) => setRepositoryId(event.target.value)} value={repositoryId}>{healthyRepositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.display_name}</option>)}</select>
        <label htmlFor="run-task">Task</label>
        <textarea autoFocus id="run-task" onChange={(event) => setTask(event.target.value)} placeholder="Describe the focused change to build..." rows={5} value={task} />
        <div className="run-composer__options run-composer__options--truthful">
          <label>Provider<select aria-label="Provider" disabled value="codex"><option value="codex">OpenAI Codex - verified local CLI</option></select></label>
          <label>Model<select aria-label="Model" onChange={(event) => setModel(event.target.value)} value={model}>{codex?.models.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}</select></label>
          <label>Thinking<select aria-label="Thinking" onChange={(event) => setEffort(event.target.value as Effort)} value={effort}>{codex?.thinking_levels.filter((level) => level !== "max").map((level) => <option key={level} value={level}>{effortLabel(level)}</option>)}</select></label>
          <label>Skill<select aria-label="Skill" onChange={(event) => setSkillId(event.target.value)} value={skillId}><option value="">No skill</option>{activeSkills.map((skill) => <option key={skill.id} value={skill.id}>{skill.name} v{skill.version}</option>)}</select></label>
          <label>Mode<select aria-label="Mode" onChange={(event) => { const next = event.target.value as "chat" | "build"; setMode(next); setOutputPolicy(next === "chat" ? "report_only" : "prepare_contribution"); }} value={mode}><option value="build">Build changes</option><option value="chat">Inspect only</option></select></label>
          <label>Output policy<select aria-label="Output policy" disabled={mode === "chat"} onChange={(event) => setOutputPolicy(event.target.value as OutputPolicy)} value={mode === "chat" ? "report_only" : outputPolicy}><option value="report_only">Report only</option>{mode === "build" ? <><option value="prepare_changes">Prepare changes for review</option><option value="prepare_contribution">Prepare draft contribution</option></> : null}</select></label>
        </div>
        <p className="run-composer__boundary">No run can merge or force-push. Prepare draft contribution stops at review before any GitHub mutation.</p>
        <div className="row-actions"><button className="button" onClick={() => setCreating(false)} type="button">Cancel</button><button className="button button--primary" disabled={busy || !repositoryId || !task.trim() || !codexReady || !model} type="submit">{busy ? "Starting..." : "Start supervised run"}</button></div>
      </form> : null}
      {repositories.length === 0 ? <div className="resource-empty"><strong>Connect a repository first</strong><span>Runs need a real Git checkout and create no changes in the source directory.</span></div> : null}
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      <div className="runs-layout">
        <div aria-label="Run history" className="run-list">{runs.length === 0 ? <div className="resource-empty"><strong>No runs yet</strong><span>Start one to see its live state and evidence here.</span></div> : runs.map((run) => <button aria-pressed={run.id === selectedId} className="run-list__item" key={run.id} onClick={() => setSelectedId(run.id)} type="button"><span className="run-status" data-status={run.status}>{run.status.replaceAll("_", " ")}</span><strong>{run.task}</strong><small>{repositories.find((repo) => repo.id === run.repository_id)?.display_name ?? "Repository"} - {new Date(run.created_at).toLocaleString()}</small></button>)}</div>
        {selected ? <article className="run-detail">
          <header><div><span className="run-status" data-status={selected.status}>{selected.status.replaceAll("_", " ")}</span><h2>{selected.task}</h2></div><div className="row-actions">{ACTIVE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("cancel")} type="button">Stop</button> : null}{RETRYABLE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("retry")} type="button">Retry</button> : null}{DISCARDABLE.has(selected.status) ? <button className="button" disabled={busy} onClick={() => void mutate("discard")} type="button">Discard worktree</button> : null}</div></header>
          <dl className="run-metadata"><div><dt>Provider</dt><dd>Codex</dd></div><div><dt>Model</dt><dd>{selected.model ?? "Provider default"}</dd></div><div><dt>Thinking</dt><dd>{selected.effort}</dd></div><div><dt>Skill</dt><dd>{skills.find((skill) => skill.id === selected.skill_version_id)?.name ?? (selected.skill_version_id ? "Selected skill" : "None")}</dd></div><div><dt>Output</dt><dd>{selected.output_policy.replaceAll("_", " ")}</dd></div><div><dt>Base</dt><dd>{selected.base_sha.slice(0, 12)}</dd></div></dl>
          <section><h3>Activity</h3><ol className="run-events">{events.length === 0 ? <li>Waiting for provider activity...</li> : events.map((item) => <li key={item.sequence}><span>{item.sequence}</span><div><strong>{eventSummary(item)}</strong><small>{item.event_type}</small></div></li>)}</ol></section>
          <section><h3>Evidence</h3>{evidence.map((item) => <div className="evidence-card" key={item.id}><strong>{item.kind.replaceAll("_", " ")}</strong><span>{item.summary}</span><code title={item.digest}>{item.digest.slice(0, 12)}</code></div>)}<div className="evidence-card evidence-card--unavailable"><strong>Test result unavailable</strong><span>No independently captured test command and exit code exist for this run. Do not claim tests passed.</span></div><div className="evidence-card evidence-card--unavailable"><strong>Full safety receipt unavailable</strong><span>The durable run records its locked policy digest above; owner-scoped chat receipts are a separate surface.</span></div></section>
        </article> : null}
      </div>
      {selected?.status === "review_required" || selected?.status === "contribution_ready" ? <ContributionPanel api={api} runId={selected.id} /> : null}
    </section>
  );
}
