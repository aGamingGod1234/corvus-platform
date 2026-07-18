import { type FormEvent, useCallback, useEffect, useState } from "react";

import type { LocalRepository, LocalRun, LocalSafetyPreview, LocalSchedule, PortableSkill } from "../api";

export interface SchedulesApi {
  listRepositories(): Promise<LocalRepository[]>;
  listPortableSkills(): Promise<PortableSkill[]>;
  getLocalSafetyPreview(mode: "chat" | "build"): Promise<LocalSafetyPreview>;
  listLocalSchedules(): Promise<LocalSchedule[]>;
  createLocalSchedule(input: {
    name: string;
    repositoryId: string;
    task: string;
    recurrence: { kind: "once" | "hourly" | "daily" | "weekdays" | "weekly"; local_time?: string; weekdays: number[]; once_at?: string };
    timezone: string;
    effort: "low" | "medium" | "high" | "xhigh";
    mode: "chat" | "build";
    safetyDigest: string;
    skillVersionId?: string;
    outputPolicy: "report_only" | "prepare_changes" | "prepare_contribution";
  }): Promise<LocalSchedule>;
  runLocalScheduleNow(scheduleId: string): Promise<LocalRun>;
  pauseLocalSchedule(scheduleId: string): Promise<LocalSchedule>;
  resumeLocalSchedule(scheduleId: string): Promise<LocalSchedule>;
  archiveLocalSchedule(scheduleId: string): Promise<LocalSchedule>;
}

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : "schedule_request_failed";
}

export function SchedulesWorkspace({ api, onOpenRun }: { api: SchedulesApi; onOpenRun(): void }) {
  const [schedules, setSchedules] = useState<LocalSchedule[]>([]);
  const [repositories, setRepositories] = useState<LocalRepository[]>([]);
  const [skills, setSkills] = useState<PortableSkill[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [task, setTask] = useState("");
  const [cadence, setCadence] = useState<"hourly" | "daily" | "weekdays" | "weekly">("daily");
  const [localTime, setLocalTime] = useState("09:00");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [mode, setMode] = useState<"chat" | "build">("chat");
  const [effort, setEffort] = useState<"low" | "medium" | "high" | "xhigh">("high");
  const [skillId, setSkillId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [loadedSchedules, loadedRepositories, loadedSkills] = await Promise.all([
      api.listLocalSchedules(), api.listRepositories(), api.listPortableSkills()
    ]);
    setSchedules(loadedSchedules);
    setRepositories(loadedRepositories);
    setSkills(loadedSkills.filter((skill) => skill.status === "active"));
    setRepositoryId((current) => current || loadedRepositories[0]?.id || "");
  }, [api]);
  useEffect(() => { void load().catch((reason: unknown) => setError(readableError(reason))); }, [load]);

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!name.trim() || !task.trim() || !repositoryId) return;
    setBusy(true); setError("");
    try {
      const preview = await api.getLocalSafetyPreview(mode);
      const recurrence = cadence === "hourly"
        ? { kind: cadence, weekdays: [] }
        : cadence === "weekly"
          ? { kind: cadence, local_time: `${localTime}:00`, weekdays: [0] }
          : { kind: cadence, local_time: `${localTime}:00`, weekdays: [] };
      const record = await api.createLocalSchedule({
        name: name.trim(), repositoryId, task: task.trim(), recurrence, timezone,
        effort, mode, safetyDigest: preview.policy_digest,
        skillVersionId: skillId || undefined,
        outputPolicy: mode === "build" ? "prepare_changes" : "report_only"
      });
      setSchedules((current) => [record, ...current]);
      setName(""); setTask(""); setCreating(false);
    } catch (reason) { setError(readableError(reason)); } finally { setBusy(false); }
  }

  async function action(schedule: LocalSchedule, kind: "run" | "pause" | "resume" | "archive"): Promise<void> {
    setBusy(true); setError("");
    try {
      if (kind === "run") {
        await api.runLocalScheduleNow(schedule.id);
        onOpenRun();
        return;
      }
      const updated = kind === "pause" ? await api.pauseLocalSchedule(schedule.id)
        : kind === "resume" ? await api.resumeLocalSchedule(schedule.id)
          : await api.archiveLocalSchedule(schedule.id);
      setSchedules((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) { setError(readableError(reason)); } finally { setBusy(false); }
  }

  return <section aria-labelledby="schedules-title" className="schedules-workspace">
    <header className="resource-heading"><div><p className="eyebrow">Local automation</p><h1 id="schedules-title">Schedule</h1><p>Run ordinary supervised tasks on a reliable cadence. Code changes always stop for review.</p></div><button className="button button--primary" disabled={!repositories.length} onClick={() => setCreating(true)} type="button">New schedule</button></header>
    <div className="schedule-notice"><strong>Runs while Corvus is open</strong><span>The computer must be awake. Missed occurrences do not create an unsafe backlog.</span></div>
    {creating ? <form className="schedule-editor" onSubmit={(event) => void create(event)}><label>Name<input autoFocus onChange={(event) => setName(event.target.value)} placeholder="Weekday repository review" value={name} /></label><label>Repository<select onChange={(event) => setRepositoryId(event.target.value)} value={repositoryId}>{repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.display_name}</option>)}</select></label><label className="schedule-editor__task">Task<textarea onChange={(event) => setTask(event.target.value)} placeholder="Review recent changes and prepare a concise risk report…" rows={4} value={task} /></label><label>Cadence<select onChange={(event) => setCadence(event.target.value as typeof cadence)} value={cadence}><option value="hourly">Every hour</option><option value="daily">Every day</option><option value="weekdays">Weekdays</option><option value="weekly">Every Monday</option></select></label>{cadence !== "hourly" ? <label>Local time<input onChange={(event) => setLocalTime(event.target.value)} type="time" value={localTime} /></label> : null}<label>Timezone<input onChange={(event) => setTimezone(event.target.value)} value={timezone} /></label><label>Skill<select onChange={(event) => setSkillId(event.target.value)} value={skillId}><option value="">No skill</option>{skills.map((skill) => <option key={skill.id} value={skill.id}>{skill.name} v{skill.version}</option>)}</select></label><label>Mode<select onChange={(event) => setMode(event.target.value as "chat" | "build")} value={mode}><option value="chat">Report only</option><option value="build">Prepare changes</option></select></label><label>Reasoning<select onChange={(event) => setEffort(event.target.value as typeof effort)} value={effort}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="xhigh">Extra high</option></select></label><div className="row-actions schedule-editor__actions"><button className="button" onClick={() => setCreating(false)} type="button">Cancel</button><button className="button button--primary" disabled={busy || !name.trim() || !task.trim() || !repositoryId} type="submit">{busy ? "Saving…" : "Create schedule"}</button></div></form> : null}
    {error ? <p className="inline-error" role="alert">{error}</p> : null}
    <div className="schedule-card-grid">{schedules.length === 0 ? <div className="resource-empty"><strong>No schedules yet</strong><span>Create a report-only cadence or a change task that stops at review.</span></div> : schedules.map((schedule) => <article className="schedule-card" key={schedule.id}><header><span className="run-status" data-status={schedule.status}>{schedule.status}</span><small>v{schedule.version}</small></header><h2>{schedule.name}</h2><p>{schedule.task}</p><dl><div><dt>Cadence</dt><dd>{schedule.recurrence.kind}</dd></div><div><dt>Next run</dt><dd>{schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString() : "Finished"}</dd></div><div><dt>Mode</dt><dd>{schedule.mode === "build" ? "Prepare changes" : "Report only"}</dd></div><div><dt>Timezone</dt><dd>{schedule.timezone}</dd></div></dl><footer><button className="button button--primary" disabled={busy || schedule.status === "archived"} onClick={() => void action(schedule, "run")} type="button">Run now</button>{schedule.status === "active" ? <button className="button" disabled={busy} onClick={() => void action(schedule, "pause")} type="button">Pause</button> : schedule.status === "paused" ? <button className="button" disabled={busy} onClick={() => void action(schedule, "resume")} type="button">Resume</button> : null}{schedule.status !== "archived" ? <button className="button" disabled={busy} onClick={() => void action(schedule, "archive")} type="button">Archive</button> : null}</footer></article>)}</div>
  </section>;
}
