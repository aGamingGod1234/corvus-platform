import { invoke, isTauri } from "@tauri-apps/api/core";
import { type FormEvent, useEffect, useState } from "react";

import type { GitHubAuthStatus, GitHubRepositorySummary, LocalRepository, LocalWorktree } from "../api";
import { ContributionPanel, type ContributionApi } from "./ContributionPanel";

export interface RepositoryApi extends ContributionApi {
  listRepositories(): Promise<LocalRepository[]>;
  registerRepository(path: string, displayName: string): Promise<LocalRepository>;
  refreshRepository(repositoryId: string): Promise<LocalRepository>;
  removeRepository(repositoryId: string): Promise<void>;
  createRepositoryRun(repositoryId: string): Promise<LocalWorktree>;
  getGitHubAuthStatus?(): Promise<GitHubAuthStatus>;
  authenticateGitHub?(): Promise<GitHubAuthStatus>;
  listGitHubRepositories?(): Promise<GitHubRepositorySummary[]>;
  connectGitHubRepository?(slug: string): Promise<LocalRepository>;
  createEmptyRepository?(name: string): Promise<LocalRepository>;
}

interface RepositoriesWorkspaceProps {
  api: RepositoryApi;
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

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : "repository_request_failed";
}

export function RepositoriesWorkspace({
  api,
  pickDirectory = pickDesktopDirectory
}: RepositoriesWorkspaceProps) {
  const [repositories, setRepositories] = useState<LocalRepository[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [path, setPath] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [activeRun, setActiveRun] = useState<LocalWorktree | null>(null);
  const [githubStatus, setGitHubStatus] = useState<GitHubAuthStatus | null>(null);
  const [githubRepositories, setGitHubRepositories] = useState<GitHubRepositorySummary[]>([]);
  const [githubOpen, setGitHubOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectOpen, setNewProjectOpen] = useState(false);

  useEffect(() => {
    let active = true;
    api.listRepositories()
      .then((loaded) => {
        if (active) setRepositories(loaded);
      })
      .catch((reason: unknown) => {
        if (active) setError(readableError(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    if (api.getGitHubAuthStatus === undefined) return;
    let active = true;
    void api.getGitHubAuthStatus().then(async (status) => {
      if (!active) return;
      setGitHubStatus(status);
      if (status.authenticated && api.listGitHubRepositories !== undefined) {
        const available = await api.listGitHubRepositories();
        if (active) setGitHubRepositories(available);
      }
    }).catch(() => {
      if (active) setGitHubStatus({ hostname: "github.com", authenticated: false });
    });
    return () => { active = false; };
  }, [api]);

  async function browse(): Promise<void> {
    setError("");
    try {
      const selected = await pickDirectory();
      if (selected === null) return;
      setPath(selected);
      if (displayName.trim() === "") setDisplayName(directoryName(selected));
    } catch (reason) {
      setError(readableError(reason));
    }
  }

  async function connect(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (path.trim() === "" || displayName.trim() === "") return;
    setBusyId("new");
    setError("");
    try {
      const registered = await api.registerRepository(path.trim(), displayName.trim());
      setRepositories((current) => [
        registered,
        ...current.filter((item) => item.id !== registered.id)
      ]);
      setPath("");
      setDisplayName("");
      setCreating(false);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyId(null);
    }
  }

  async function refresh(repository: LocalRepository): Promise<void> {
    setBusyId(repository.id);
    setError("");
    try {
      const refreshed = await api.refreshRepository(repository.id);
      setRepositories((current) =>
        current.map((item) => item.id === refreshed.id ? refreshed : item)
      );
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyId(null);
    }
  }

  async function startRun(repository: LocalRepository): Promise<void> {
    setBusyId(repository.id);
    setError("");
    try {
      setActiveRun(await api.createRepositoryRun(repository.id));
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyId(null);
    }
  }

  async function authenticateGitHub(): Promise<void> {
    if (api.authenticateGitHub === undefined) return;
    setBusyId("github-auth");
    setError("");
    try {
      const status = await api.authenticateGitHub();
      setGitHubStatus(status);
      if (status.authenticated && api.listGitHubRepositories !== undefined) {
        setGitHubRepositories(await api.listGitHubRepositories());
        setGitHubOpen(true);
      }
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyId(null);
    }
  }

  async function connectGitHub(repository: GitHubRepositorySummary): Promise<void> {
    if (api.connectGitHubRepository === undefined) return;
    setBusyId(repository.slug);
    setError("");
    try {
      const connected = await api.connectGitHubRepository(repository.slug);
      setRepositories((current) => [connected, ...current.filter((item) => item.id !== connected.id)]);
      setGitHubOpen(false);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setBusyId(null);
    }
  }

  async function createEmptyProject(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (api.createEmptyRepository === undefined || newProjectName.trim() === "") return;
    setBusyId("empty-project");
    setError("");
    try {
      const created = await api.createEmptyRepository(newProjectName.trim());
      setRepositories((current) => [created, ...current]);
      setNewProjectName("");
      setNewProjectOpen(false);
    } catch (reason) {
      setError(readableError(reason));
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
        <div className="row-actions"><button className="button" disabled={busyId !== null} onClick={() => githubStatus?.authenticated ? setGitHubOpen((open) => !open) : void authenticateGitHub()} type="button">{busyId === "github-auth" ? "Complete sign-in in your browser…" : githubStatus?.authenticated ? "Add from GitHub" : "Connect GitHub"}</button><button className="button" onClick={() => setNewProjectOpen(true)} type="button">New project</button><button className="button button--primary" onClick={() => setCreating(true)} type="button">Add local repository</button></div>
      </header>

      {newProjectOpen ? <form className="repository-new-project" onSubmit={(event) => void createEmptyProject(event)}><div><label htmlFor="new-project-name">Project name</label><input autoFocus id="new-project-name" onChange={(event) => setNewProjectName(event.target.value)} placeholder="My project" value={newProjectName} /></div><div className="row-actions"><button className="button" onClick={() => setNewProjectOpen(false)} type="button">Cancel</button><button className="button button--primary" disabled={busyId !== null || newProjectName.trim() === ""} type="submit">{busyId === "empty-project" ? "Creating…" : "Create project"}</button></div></form> : null}

      {githubOpen && githubStatus?.authenticated ? <section className="github-repository-picker"><header><div><h2>Choose a GitHub repository</h2><p>Corvus clones it into its managed project area, then uses isolated worktrees for runs.</p></div><button aria-label="Close GitHub repositories" className="icon-button" onClick={() => setGitHubOpen(false)} type="button">×</button></header><div>{githubRepositories.map((repository) => <article key={repository.slug}><div><strong>{repository.slug}</strong><span>{repository.private ? "Private" : "Public"} · {repository.default_branch ?? "Default branch unavailable"}</span></div><button className="button button--primary" disabled={busyId !== null} onClick={() => void connectGitHub(repository)} type="button">{busyId === repository.slug ? "Connecting…" : "Connect"}</button></article>)}</div></section> : null}

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

      {error ? <p className="inline-error" role="alert">{error}</p> : null}
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
              <button className="button button--primary" disabled={busyId !== null} onClick={() => void startRun(repository)} type="button">
                New isolated run
              </button>
            </footer>
          </article>
        ))}
      </div>
      {activeRun ? <ContributionPanel api={api} runId={activeRun.run_id} /> : null}
    </section>
  );
}
