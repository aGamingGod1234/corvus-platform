import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { PortableSkill, SkillImportCandidate, SkillImportPreview } from "../api";

export interface PortableSkillsApi {
  listPortableSkills(): Promise<PortableSkill[]>;
  listSkillImportSources(): Promise<SkillImportCandidate[]>;
  previewSkillImport(candidateId: string): Promise<SkillImportPreview>;
  importPortableSkill(candidateId: string, expectedDigest: string): Promise<PortableSkill>;
  activatePortableSkill(skillId: string): Promise<PortableSkill>;
  archivePortableSkill(skillId: string): Promise<PortableSkill>;
}

const SOURCE_LABELS: Record<string, string> = {
  agents: "Agent Skills",
  codex: "Codex",
  claude: "Claude Code",
  hermes: "Hermes Agent",
  copilot: "GitHub Copilot",
  generic: "Other folders"
};

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : "skill_request_failed";
}

export function PortableSkillsWorkspace({
  api,
  onOpenRuns
}: {
  api: PortableSkillsApi;
  onOpenRuns?: (skillId: string) => void;
}) {
  const [skills, setSkills] = useState<PortableSkill[]>([]);
  const [candidates, setCandidates] = useState<SkillImportCandidate[]>([]);
  const [preview, setPreview] = useState<SkillImportPreview | null>(null);
  const [discovering, setDiscovering] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<Set<string>>(new Set());
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);

  const refresh = useCallback(async () => {
    setDiscovering(true);
    setError("");
    try {
      const [library, discovered] = await Promise.all([
        api.listPortableSkills(), api.listSkillImportSources()
      ]);
      setSkills(library);
      setCandidates(discovered);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setDiscovering(false);
    }
  }, [api]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    if (preview === null) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const closeButton = dialogRef.current?.querySelector<HTMLElement>("button");
    closeButton?.focus();
    return () => previousFocus?.focus();
  }, [preview]);

  const sourceCounts = useMemo(() => Object.keys(SOURCE_LABELS).map((source) => ({
    source,
    count: candidates.filter((candidate) => candidate.source === source).length
  })), [candidates]);

  async function review(candidate: SkillImportCandidate): Promise<void> {
    setBusy(true);
    setError("");
    try {
      setTechnicalOpen(false);
      setPreview(await api.previewSkillImport(candidate.id));
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function importSkill(): Promise<void> {
    if (!preview || preview.compatibility === "blocked") return;
    setBusy(true);
    setError("");
    try {
      const imported = await api.importPortableSkill(preview.candidate.id, preview.digest);
      setSkills((current) => [imported, ...current.filter((skill) => skill.id !== imported.id)]);
      setPreview(null);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function importSelected(): Promise<void> {
    if (selectedCandidateIds.size === 0) return;
    setBusy(true);
    setError("");
    try {
      const outcomes = await Promise.all(
        candidates
          .filter((item) => selectedCandidateIds.has(item.id))
          .map(async (candidate) => {
            try {
              const candidatePreview = await api.previewSkillImport(candidate.id);
              if (candidatePreview.compatibility === "blocked" || candidatePreview.duplicate === "exact") {
                return { candidateId: candidate.id, imported: null, failed: false, requiresReview: false };
              }
              if (candidatePreview.compatibility === "needs_review") {
                return { candidateId: candidate.id, imported: null, failed: false, requiresReview: true };
              }
              return {
                candidateId: candidate.id,
                imported: await api.importPortableSkill(candidate.id, candidatePreview.digest),
                failed: false,
                requiresReview: false
              };
            } catch {
              return { candidateId: candidate.id, imported: null, failed: true, requiresReview: false };
            }
          })
      );
      const imported = outcomes
        .map((outcome) => outcome.imported)
        .filter((skill): skill is PortableSkill => skill !== null);
      const uniqueImported = [...new Map(imported.map((skill) => [skill.id, skill])).values()];
      setSkills((current) => [...uniqueImported, ...current.filter((skill) => !uniqueImported.some((item) => item.id === skill.id))]);
      const failedIds = outcomes.filter((outcome) => outcome.failed).map((outcome) => outcome.candidateId);
      const reviewIds = outcomes.filter((outcome) => outcome.requiresReview).map((outcome) => outcome.candidateId);
      setSelectedCandidateIds(new Set([...failedIds, ...reviewIds]));
      const notices: string[] = [];
      if (reviewIds.length > 0) {
        notices.push(`${reviewIds.length} selected skill${reviewIds.length === 1 ? "" : "s"} require${reviewIds.length === 1 ? "s" : ""} individual review and were not imported.`);
      }
      if (failedIds.length > 0) {
        notices.push(`${failedIds.length} selected skill${failedIds.length === 1 ? "" : "s"} could not be imported.`);
      }
      if (notices.length > 0) setError(`${notices.join(" ")} Safe imports completed.`);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(skill: PortableSkill, action: "activate" | "archive"): Promise<void> {
    setBusy(true);
    setError("");
    try {
      const updated = action === "activate"
        ? await api.activatePortableSkill(skill.id)
        : await api.archivePortableSkill(skill.id);
      const library = await api.listPortableSkills();
      setSkills(library.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusy(false);
    }
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === "Escape") {
      event.preventDefault();
      setPreview(null);
      return;
    }
    if (event.key !== "Tab") return;
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
      "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    ));
    if (controls.length === 0) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return <section aria-labelledby="portable-skills-title" className="portable-skills-workspace">
    <header className="resource-heading"><div><p className="eyebrow">Portable Agent Skills</p><h1 id="portable-skills-title">Skills</h1><p>Bring trusted workflows from Codex, Claude Code, Hermes, Copilot, and the open Agent Skills format.</p></div><button className="button button--primary" disabled={discovering} onClick={() => void refresh()} type="button">{discovering ? "Discovering…" : "Discover skills"}</button></header>
    {error ? <p className="inline-error" role="alert">{error}</p> : null}
    <div className="skill-source-grid" aria-label="Skill sources">{sourceCounts.map(({ source, count }) => <article key={source}><strong>{SOURCE_LABELS[source]}</strong><span>{count} found</span></article>)}</div>
    {onOpenRuns && skills.some((skill) => skill.status === "active") ? <div className="skill-run-shortcuts" aria-label="Active skills ready for a run"><span>Active skills are reviewed and selectable in Runs.</span>{skills.filter((skill) => skill.status === "active").map((skill) => <button className="button button--primary" disabled={busy} key={skill.id} onClick={() => onOpenRuns(skill.id)} type="button">Use {skill.name} in Runs</button>)}</div> : null}
    <div className="skill-library-layout"><section><div className="section-heading"><h2>Discovered</h2><div className="skill-bulk-actions"><span>{candidates.length}</span><button className="button button--quiet" disabled={busy || candidates.length === 0} onClick={() => setSelectedCandidateIds(new Set(candidates.map((candidate) => candidate.id)))} type="button">Select all</button><button className="button button--quiet" disabled={busy || selectedCandidateIds.size === 0} onClick={() => setSelectedCandidateIds(new Set())} type="button">Clear</button><button className="button" disabled={busy || selectedCandidateIds.size === 0} onClick={() => void importSelected()} type="button">Import selected ({selectedCandidateIds.size})</button></div></div><div className="skill-candidates">{candidates.length === 0 && !discovering ? <div className="resource-empty"><strong>No importable skills found</strong><span>Add a SKILL.md under a supported tool’s skills directory, then discover again.</span></div> : candidates.map((candidate) => <article key={candidate.id}><label><input aria-label={`Select ${candidate.name}`} checked={selectedCandidateIds.has(candidate.id)} onChange={(event) => setSelectedCandidateIds((current) => { const next = new Set(current); if (event.target.checked) next.add(candidate.id); else next.delete(candidate.id); return next; })} type="checkbox" /></label><button onClick={() => void review(candidate)} type="button"><span className="skill-source-badge">{SOURCE_LABELS[candidate.source] ?? candidate.source}</span><strong>{candidate.name}</strong><small>{candidate.kind === "legacy_command" ? "Legacy command · converts for review" : candidate.path}</small></button></article>)}</div></section><section><div className="section-heading"><h2>Library</h2><span>{skills.length} versions</span></div><div className="portable-skill-list">{skills.length === 0 ? <div className="resource-empty"><strong>Your library is empty</strong><span>Review a discovered skill and import a digest-pinned copy.</span></div> : skills.map((skill) => <article key={skill.id}><div><span className="skill-source-badge">{skill.source}</span><strong>{skill.name} <small>v{skill.version}</small></strong><p>{skill.description}</p></div><span className="run-status" data-status={skill.status}>{skill.status}</span><div className="row-actions">{skill.status !== "active" && skill.status !== "archived" ? <button className="button" disabled={busy} onClick={() => void changeStatus(skill, "activate")} type="button">Activate</button> : null}{skill.status !== "archived" ? <button className="button" disabled={busy} onClick={() => void changeStatus(skill, "archive")} type="button">Archive</button> : null}</div></article>)}</div></section></div>
    {preview ? <div className="skill-review-backdrop" role="presentation">
      <section aria-labelledby="skill-review-title" aria-modal="true" className="skill-review" onKeyDown={handleDialogKeyDown} ref={dialogRef} role="dialog">
        <header>
          <div><p className="eyebrow">Review import</p><h2 id="skill-review-title">{preview.name}</h2><p>{preview.description}</p></div>
          <button aria-label="Close skill review" className="icon-button" onClick={() => setPreview(null)} type="button">×</button>
        </header>
        <div className="skill-review__facts">
          <span data-status={preview.compatibility}>{preview.compatibility.replaceAll("_", " ")}</span>
          <span>{SOURCE_LABELS[preview.candidate.source] ?? preview.candidate.source}</span>
          <span>{preview.files.length} files</span>
          <span>{preview.duplicate === "none" ? "New skill" : `${preview.duplicate} duplicate`}</span>
        </div>
        {preview.findings.length ? <div className="skill-findings"><h3>Review findings</h3>{preview.findings.map((finding, index) => <article data-severity={finding.severity} key={`${finding.code}-${index}`}><strong>{finding.message}</strong><small>{finding.location} · {finding.code}</small></article>)}</div> : <p className="skill-review__clean">No compatibility or security findings. Import still copies the package without executing it.</p>}
        <p className="skill-review__authority">Imported permissions are never granted automatically.</p>
        <button aria-expanded={technicalOpen} className="skill-review__technical-toggle" onClick={() => setTechnicalOpen((open) => !open)} type="button">Technical package details</button>
        {technicalOpen ? <div className="skill-review__technical"><div className="skill-review__digest"><span>Immutable package digest</span><code title={preview.digest}>{preview.digest}</code></div><section className="skill-review__files"><h3>Package files</h3><p>Normalized paths copied into the Corvus-owned draft.</p><ul>{preview.files.map((file) => <li key={file}><code>{file}</code></li>)}</ul></section></div> : null}
        <footer><button className="button" onClick={() => setPreview(null)} type="button">Cancel</button><button className="button button--primary" disabled={busy || preview.compatibility === "blocked" || preview.duplicate === "exact"} onClick={() => void importSkill()} type="button">{preview.duplicate === "exact" ? "Already imported" : busy ? "Importing…" : "Import as draft"}</button></footer>
      </section>
    </div> : null}
  </section>;
}
