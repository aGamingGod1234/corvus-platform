import { invoke, isTauri } from "@tauri-apps/api/core";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import type { GitHubAuthStatus, GitHubRepositorySummary, LocalRepository } from "../api";
import { featureErrorMessage } from "./featureFeedback";

export interface RepositoryApi {
  listRepositories(): Promise<LocalRepository[]>;
  registerRepository(path: string, displayName: string): Promise<LocalRepository>;
  refreshRepository(repositoryId: string): Promise<LocalRepository>;
  removeRepository(repositoryId: string): Promise<void>;
  getGitHubAuthStatus?(): Promise<GitHubAuthStatus>;
  authenticateGitHub?(): Promise<GitHubAuthStatus>;
  listGitHubRepositories?(): Promise<GitHubRepositorySummary[]>;
  connectGitHubRepository?(slug: string): Promise<LocalRepository>;
  createEmptyRepository?(name: string): Promise<LocalRepository>;
}

interface RepositoriesWorkspaceProps {
  api: RepositoryApi;
  onOpenRuns?(repositoryId: string): void;
  pickDirectory?: () => Promise<string | null>;
}

async function pickDesktopDirectory(): Promise<string | null> {
  if (!isTauri()) return null;
  return invoke<string | null>("select_repository_directory");
}

function directoryName(path: string): string {
  const trimmed = path.replace(/[\\/]+$/, "");
  return trimmed.split(/[\\/]/).at(-1) ?? "Repository";
}

export function RepositoriesWorkspace({
  api,
  onOpenRuns,
  pickDirectory = pickDesktopDirectory
}: RepositoriesWorkspaceProps) {
  const [repositories, setRepositories] = useState<LocalRepository[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [path, setPath] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [githubError, setGithubError] = useState("");
  const [githubStatus, setGitHubStatus] = useState<GitHubAuthStatus | null>(null);
  const [githubRepositories, setGitHubRepositories] = useState<GitHubRepositorySummary[]>([]);
  const [githubOpen, setGitHubOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);
  const githubAvailable = api.getGitHubAuthStatus !== undefined
    && api.authenticateGitHub !== undefined
    && api.listGitHubRepositories !== undefined
    && api.connectGitHubRepository !== undefined;

  const loadRepositories = useCallback(async (): Promise<void> => {
    setLoading(true);
    setLoadFailed(false);
    setError("");
    try {
      setRepositories(await api.listRepositories());
    } catch (reason) {
      setLoadFailed(true);
      setError(featureErrorMessage(reason, "repository"));
    } finally {
      setLoading(false);
    }
  }, [api]);

  const loadGitHub = useCallback(async (): Promise<void> => {
    if (api.getGitHubAuthStatus === undefined) return;
    setGithubError("");
    try {
      const status = await api.getGitHubAuthStatus();
      setGitHubStatus(status);
      if (status.authenticated && api.listGitHubRepositories !== undefined) {
        setGitHubRepositories(await api.listGitHubRepositories());
      }
    } catch (reason) {
      setGitHubStatus(null);
      setGithubError(featureErrorMessage(reason, "github"));
    }
  }, [api]);

  useEffect(() => { void loadRepositories(); }, [loadRepositories]);
  useEffect(() => { void loadGitHub(); }, [loadGitHub]);

  async function browse(): Promise<void> {
    setError("");
    try {
      const selected = await pickDirectory();
      if (selected === null) return;
      setPath(selected);
      if (displayName.trim() === "") setDisplayName(directoryName(selected));
    } catch (reason) {
      setError(featureErrorMessage(reason, "repository"));
    }
  }

  async function connect(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (path.trim() === "" || displayName.trim() === "") return;
    setBusyId("new");
    setError("");
    setNotice("");
    try {
      const registered = await api.registerRepository(path.trim(), displayName.trim());
      setRepositories((current) => [
        registered,
        ...current.filter((item) => item.id !== registered.id)
      ]);
      setPath("");
      setDisplayName("");
      setCreating(false);
      setNotice(`${registered.display_name} is connected and ready for repository checks.`);
    } catch (reason) {
      setError(featureErrorMessage(reason, "repository"));
    } finally {
      setBusyId(null);
    }
  }

  async function refresh(repository: LocalRepository): Promise<void> {
    setBusyId(repository.id);
    setError("");
    setNotice("");
    try {
      const refreshed = await api.refreshRepository(repository.id);
      setRepositories((current) =>
        current.map((item) => item.id === refreshed.id ? refreshed : item)
      );
      setNotice(`${refreshed.display_name} was refreshed. Git reports ${refreshed.snapshot.health}.`);
    } catch (reason) {
      setError(featureErrorMessage(reason, "repository"));
    } finally {
      setBusyId(null);
    }
  }

  async function authenticateGitHub(): Promise<void> {
    if (api.authenticateGitHub === undefined) return;
    setBusyId("github-auth");
    setError("");
    setGithubError("");
    setNotice("");
    try {
      const status = await api.authenticateGitHub();
      setGitHubStatus(status);
      if (status.authenticated && api.listGitHubRepositories !== undefined) {
        setGitHubRepositories(await api.listGitHubRepositories());
        setGitHubOpen(true);
      }
      if (!status.authenticated) setGithubError("GitHub sign-in did not complete. Try again when you are ready.");
    } catch (reason) {
      setGithubError(featureErrorMessage(reason, "github"));
    } finally {
      setBusyId(null);
    }
  }

  async function connectGitHub(repository: GitHubRepositorySummary): Promise<void> {
    if (api.connectGitHubRepository === undefined) return;
    setBusyId(repository.slug);
    setError("");
    setNotice("");
    try {
      const connected = await api.connectGitHubRepository(repository.slug);
      setRepositories((current) => [connected, ...current.filter((item) => item.id !== connected.id)]);
      setGitHubOpen(false);
      setNotice(`${connected.display_name} was cloned into the managed project area.`);
    } catch (reason) {
      setError(featureErrorMessage(reason, "github"));
    } finally {
      setBusyId(null);
    }
  }

  async function createEmptyProject(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (api.createEmptyRepository === undefined || newProjectName.trim() === "") return;
    setBusyId("empty-project");
    setError("");
    setNotice("");
    try {
      const created = await api.createEmptyRepository(newProjectName.trim());
      setRepositories((current) => [created, ...current]);
      setNewProjectName("");
      setNewProjectOpen(false);
      setNotice(`${created.display_name} was created in the Corvus projects directory.`);
    } catch (reason) {
      setError(featureErrorMessage(reason, "repository"));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(repository: LocalRepository): Promise<void> {
    setBusyId(repository.id);
    setError("");
    setNotice("");
    try {
      await api.removeRepository(repository.id);
      setRepositories((current) => current.filter((item) => item.id !== repository.id));
      setConfirmRemoveId(null);
      setNotice(`${repository.display_name} was removed from Corvus. Files on disk were not deleted.`);
    } catch (reason) {
      setError(featureErrorMessage(reason, "repository"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section aria-labelledby="repositories-title" className="repositories-workspace">
      <header className="resource-heading">
        <div>
          <p className="eyebrow">This computer</p>
          <h1 id="repositories-title">Repositories</h1>
          <p>Connect real Git checkouts. Corvus runs changes in separate managed worktrees.</p>
        </div>
        <button aria-expanded={addOpen} className="button button--primary" disabled={busyId !== null} onClick={() => setAddOpen((open) => !open)} type="button">Add repository</button>
      </header>

      {addOpen ? <section aria-label="Add repository options" className="repository-add-options">
        <button aria-label="GitHub" className="repository-add-option" disabled={busyId !== null || !githubAvailable} onClick={() => { setAddOpen(false); if (githubStatus?.authenticated) setGitHubOpen(true); else void authenticateGitHub(); }} title={!githubAvailable ? "GitHub connections require the installed Corvus runtime" : undefined} type="button"><strong>GitHub</strong><span>{githubAvailable ? "Connect an account or choose an authorized repository." : "Available in the installed Corvus desktop runtime."}</span></button>
        <button aria-label="Local folder" className="repository-add-option" onClick={() => { setAddOpen(false); setCreating(true); }} type="button"><strong>Local folder</strong><span>Register an existing Git checkout on this computer.</span></button>
        <button aria-label="Empty project" className="repository-add-option" disabled={api.createEmptyRepository === undefined} onClick={() => { setAddOpen(false); setNewProjectOpen(true); }} type="button"><strong>Empty project</strong><span>Create a new repository inside Corvus projects.</span></button>
      </section> : null}

      <section aria-label="GitHub readiness" className="github-readiness" data-ready={githubStatus?.authenticated ?? false}>
        <div><strong>{!githubAvailable ? "GitHub connection unavailable" : githubError ? "GitHub status unavailable" : githubStatus === null ? "Checking GitHub" : githubStatus.authenticated ? "GitHub authenticated" : "GitHub not authenticated"}</strong><span>{!githubAvailable ? "Use the installed Corvus desktop runtime to connect GitHub. Local repositories remain available." : githubError || (githubStatus?.authenticated ? `Ready to list repositories and create a human-confirmed draft pull request on ${githubStatus.hostname}.` : "Local repositories still work, but publishing a draft pull request remains unavailable.")}</span></div>
        {githubError ? <button className="button" disabled={busyId !== null} onClick={() => void loadGitHub()} type="button">Retry GitHub</button> : null}
      </section>

      {newProjectOpen ? <form className="repository-new-project" onSubmit={(event) => void createEmptyProject(event)}><div><label htmlFor="new-project-name">Project name</label><input autoFocus id="new-project-name" onChange={(event) => setNewProjectName(event.target.value)} placeholder="My project" value={newProjectName} /></div><div className="row-actions"><button className="button" onClick={() => setNewProjectOpen(false)} type="button">Cancel</button><button className="button button--primary" disabled={busyId !== null || newProjectName.trim() === ""} type="submit">{busyId === "empty-project" ? "Creating…" : "Create project"}</button></div></form> : null}

      {githubOpen && githubStatus?.authenticated ? <section className="github-repository-picker"><header><div><h2>Choose a GitHub repository</h2><p>Corvus clones it into its managed project area, then uses isolated worktrees for runs.</p></div><button aria-label="Close GitHub repositories" className="icon-button" onClick={() => setGitHubOpen(false)} type="button">×</button></header><div>{githubRepositories.length === 0 ? <div className="resource-empty"><strong>No authorized repositories found</strong><span>Grant repository access in GitHub, then retry the connection.</span></div> : githubRepositories.map((repository) => <article key={repository.slug}><div><strong>{repository.slug}</strong><span>{repository.private ? "Private" : "Public"} · {repository.default_branch ?? "Default branch unavailable"}</span></div><button className="button button--primary" disabled={busyId !== null} onClick={() => void connectGitHub(repository)} type="button">{busyId === repository.slug ? "Connecting…" : "Connect"}</button></article>)}</div></section> : null}

      {creating ? (
        <form className="repository-connect" onSubmit={(event) => void connect(event)}>
          <div className="repository-connect__path">
            <label htmlFor="repository-path">Repository path</label>
            <div>
              <input
                autoFocus
                id="repository-path"
                onChange={(event) => setPath(event.target.value)}
                placeholder="C:\\work\\project"
                value={path}
              />
              <button className="button" onClick={() => void browse()} type="button">Browse</button>
            </div>
          </div>
          <div>
            <label htmlFor="repository-display-name">Display name</label>
            <input
              id="repository-display-name"
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Project name"
              value={displayName}
            />
          </div>
          <div className="row-actions">
            <button className="button" onClick={() => setCreating(false)} type="button">Cancel</button>
            <button
              className="button button--primary"
              disabled={busyId !== null || path.trim() === "" || displayName.trim() === ""}
              type="submit"
            >
              {busyId === "new" ? "Connecting…" : "Connect repository"}
            </button>
          </div>
        </form>
      ) : null}

      {notice ? <p className="inline-success" role="status">{notice}</p> : null}
      {error ? <p className="inline-error" role="alert">{error} {loadFailed && !loading ? <button className="text-button" onClick={() => void loadRepositories()} type="button">Retry repositories</button> : null}</p> : null}
      {loading ? <div className="resource-empty"><strong>Loading repositories…</strong></div> : null}
      {!loading && repositories.length === 0 ? (
        <div className="resource-empty">
          <strong>No repositories connected</strong>
          <span>Add an existing Git checkout to unlock isolated runs and contribution review.</span>
        </div>
      ) : null}
      <div aria-label="Connected repositories" className="repository-grid">
        {repositories.map((repository) => (
          <article className="repository-card" key={repository.id}>
            <header>
              <div>
                <h2>{repository.display_name}</h2>
                <span>{repository.remote_slug ?? "Local only"}</span>
              </div>
              <span className="repository-health" data-health={repository.snapshot.health}>
                {repository.snapshot.health}
              </span>
            </header>
            <small title={repository.path}>{repository.path}</small>
            <dl>
              <div><dt>Branch</dt><dd>{repository.snapshot.branch || "Detached"}</dd></div>
              <div><dt>Working tree</dt><dd>{repository.snapshot.clean ? "Clean" : "Modified"}</dd></div>
              <div><dt>Sync</dt><dd>{repository.snapshot.ahead} ahead · {repository.snapshot.behind} behind</dd></div>
              <div><dt>HEAD</dt><dd>{repository.snapshot.head_sha.slice(0, 8)}</dd></div>
            </dl>
            <footer>
              <button
                className="button"
                disabled={busyId !== null}
                onClick={() => void refresh(repository)}
                type="button"
              >
                {busyId === repository.id ? "Refreshing…" : `Refresh ${repository.display_name}`}
              </button>
              <button className="button button--primary" disabled={busyId !== null || repository.snapshot.health !== "healthy" || onOpenRuns === undefined} onClick={() => onOpenRuns?.(repository.id)} title={repository.snapshot.health !== "healthy" ? "Refresh this repository until Git reports it healthy" : undefined} type="button">
                Use in Runs
              </button>
              {confirmRemoveId === repository.id ? <span className="repository-remove-confirm"><span>Remove from Corvus?</span><button className="button" disabled={busyId !== null} onClick={() => setConfirmRemoveId(null)} type="button">Keep</button><button className="button" disabled={busyId !== null} onClick={() => void remove(repository)} type="button">Remove</button></span> : <button className="button button--quiet" disabled={busyId !== null} onClick={() => setConfirmRemoveId(repository.id)} type="button">Remove</button>}
            </footer>
          </article>
        ))}
      </div>
    </section>
  );
}
