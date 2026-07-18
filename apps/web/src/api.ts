import createClient from "openapi-fetch";

import type { components, paths } from "./generated/api";

export type Artifact = components["schemas"]["ArtifactRecord"];
export type Approval = components["schemas"]["ApprovalRecord"];
export type AutonomyDecision = components["schemas"]["AutonomyDecision"];
export type Budget = components["schemas"]["BudgetAccount"];
export type ChannelEvent = components["schemas"]["ChannelEventRecord"];
export type ChangeSet = components["schemas"]["ChangeSet"];
export type Contribution = components["schemas"]["ContributionRecord"];
export type ConversationEntry = components["schemas"]["ConversationEntry"];
export type Effect = components["schemas"]["EffectRecord"];
export type MemoryEntry = components["schemas"]["MemoryEntry"];
export type LocalRepository = components["schemas"]["RepositoryRecord"];
export type LocalWorktree = components["schemas"]["LocalWorktreeResponse"];
export type OfflineIntent = components["schemas"]["OfflineIntentRecord"];
export type Outcome = components["schemas"]["OutcomeContract"];
export type Project = components["schemas"]["Project"];
export type ProviderConnection = components["schemas"]["ProviderConnection"];
export type RetrievedMemory = components["schemas"]["RetrievedMemory"];
export type Routine = components["schemas"]["Routine"];
export type RoutineRun = components["schemas"]["RoutineRun"];
export type Session = components["schemas"]["SessionPrincipal"];
export type SkillVersion = components["schemas"]["SkillVersion"];
export type Team = components["schemas"]["Team"];
export type WorkItem = components["schemas"]["WorkItem"];
export type WorkItemDefinition = components["schemas"]["WorkItemDefinition"];
export type Workflow = components["schemas"]["Workflow"];

export interface CorvusApi {
  session(): Promise<Session>;
  pair(value: string): Promise<void>;
  listProjects(): Promise<Project[]>;
  listRepositories(): Promise<LocalRepository[]>;
  registerRepository(path: string, displayName: string): Promise<LocalRepository>;
  refreshRepository(repositoryId: string): Promise<LocalRepository>;
  removeRepository(repositoryId: string): Promise<void>;
  createRepositoryRun(repositoryId: string): Promise<LocalWorktree>;
  getRunChanges(runId: string): Promise<ChangeSet>;
  getContribution(runId: string): Promise<Contribution>;
  prepareContribution(
    runId: string,
    input: {
      selectedPaths: string[];
      message: string;
      title: string;
      body: string;
      draft: boolean;
    }
  ): Promise<Contribution>;
  publishContribution(runId: string, expectedDigest: string): Promise<Contribution>;
  createProject(name: string): Promise<Project>;
  listOutcomes(projectId: string): Promise<Outcome[]>;
  createOutcome(projectId: string, title: string, criterion: string): Promise<Outcome>;
  listWorkflows(outcomeId: string): Promise<Workflow[]>;
  createWorkflow(
    outcomeId: string,
    name: string,
    items: WorkItemDefinition[]
  ): Promise<Workflow>;
  getWorkflow(workflowId: string): Promise<Workflow>;
  listWorkItems(workflowId: string): Promise<WorkItem[]>;
  listEffects(workflowId: string): Promise<Effect[]>;
  getBudget(projectId: string): Promise<Budget>;
  setBudget(projectId: string, limitUnits: number): Promise<Budget>;
  listArtifacts(workflowId: string): Promise<Artifact[]>;
  listConversation(workflowId: string): Promise<ConversationEntry[]>;
  startWorkflow(workflowId: string): Promise<Workflow>;
  pauseWorkflow(workflowId: string): Promise<Workflow>;
  resumeWorkflow(workflowId: string): Promise<Workflow>;
  cancelWorkflow(workflowId: string): Promise<Workflow>;
  setWorkflowKillSwitch(workflowId: string, enabled: boolean): Promise<void>;
  runNext(workflowId: string): Promise<WorkItem>;
  approveEffect(effectId: string): Promise<void>;
  rejectEffect(effectId: string): Promise<Approval>;
  listTeams(projectId: string): Promise<Team[]>;
  createTeam(projectId: string, name: string): Promise<Team>;
  listProviders(projectId: string): Promise<ProviderConnection[]>;
  createProvider(
    projectId: string,
    provider: string,
    credentialRef: string
  ): Promise<ProviderConnection>;
  evaluateAutonomy(projectId: string, capability: string): Promise<AutonomyDecision>;
  listMemories(projectId: string): Promise<MemoryEntry[]>;
  storeMemory(projectId: string, content: string): Promise<MemoryEntry>;
  retrieveMemory(projectId: string, query: string): Promise<RetrievedMemory[]>;
  listSkills(projectId: string): Promise<SkillVersion[]>;
  createSkill(projectId: string, name: string, content: string): Promise<SkillVersion>;
  activateSkill(skillId: string): Promise<SkillVersion>;
  listRoutines(projectId: string): Promise<Routine[]>;
  createRoutine(projectId: string, name: string, skillVersionId: string): Promise<Routine>;
  runRoutine(routineId: string): Promise<RoutineRun>;
  listOfflineIntents(): Promise<OfflineIntent[]>;
  listChannelEvents(): Promise<ChannelEvent[]>;
}

export class ApiFailure extends Error {
  readonly status: number;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `request_failed_${status}`);
    this.name = "ApiFailure";
    this.status = status;
  }
}

export function createCorvusApi(baseUrl = ""): CorvusApi {
  const client = createClient<paths>({ baseUrl, credentials: "include" });
  let csrfToken = "";

  function mutationHeaders(): Record<string, string> {
    if (!csrfToken) {
      throw new ApiFailure(401, "session_required");
    }
    return { "X-CSRF-Token": csrfToken };
  }

  async function loadSession(): Promise<Session> {
    const session = requireData(await client.GET("/api/auth/session"));
    csrfToken = session.csrf_token;
    return session;
  }

  return {
    session: loadSession,
    async pair(value) {
      const result = await client.POST("/api/auth/pair", { body: { token: value } });
      if (result.error) {
        throw new ApiFailure(result.response.status, readDetail(result.error));
      }
      await loadSession();
    },
    async listProjects() {
      const result = await client.GET("/api/projects");
      return requireData(result);
    },
    async listRepositories() {
      const result = await client.GET("/api/local/repositories");
      return requireData(result);
    },
    async registerRepository(path, displayName) {
      const result = await client.POST("/api/local/repositories", {
        body: { path, display_name: displayName },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async refreshRepository(repositoryId) {
      const result = await client.POST("/api/local/repositories/{repository_id}/refresh", {
        params: { path: { repository_id: repositoryId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async removeRepository(repositoryId) {
      const result = await client.DELETE("/api/local/repositories/{repository_id}", {
        params: { path: { repository_id: repositoryId } },
        headers: mutationHeaders()
      });
      if (result.error) {
        throw new ApiFailure(result.response.status, readDetail(result.error));
      }
    },
    async createRepositoryRun(repositoryId) {
      const result = await client.POST("/api/local/repositories/{repository_id}/worktrees", {
        params: { path: { repository_id: repositoryId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async getRunChanges(runId) {
      const result = await client.GET("/api/local/runs/{run_id}/changes", {
        params: { path: { run_id: runId } }
      });
      return requireData(result);
    },
    async getContribution(runId) {
      const result = await client.GET("/api/local/runs/{run_id}/contribution", {
        params: { path: { run_id: runId } }
      });
      return requireData(result);
    },
    async prepareContribution(runId, input) {
      const result = await client.POST("/api/local/runs/{run_id}/contribution/prepare", {
        params: { path: { run_id: runId } },
        body: {
          selected_paths: input.selectedPaths,
          message: input.message,
          title: input.title,
          body: input.body,
          draft: input.draft
        },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async publishContribution(runId, expectedDigest) {
      const result = await client.POST("/api/local/runs/{run_id}/contribution/publish", {
        params: { path: { run_id: runId } },
        body: { expected_digest: expectedDigest },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async createProject(name) {
      const result = await client.POST("/api/projects", {
        body: { name },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listOutcomes(projectId) {
      const result = await client.GET("/api/projects/{project_id}/outcomes", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async createOutcome(projectId, title, criterion) {
      const result = await client.POST("/api/projects/{project_id}/outcomes", {
        params: { path: { project_id: projectId } },
        body: { title, acceptance_criteria: [criterion] },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listWorkflows(outcomeId) {
      const result = await client.GET("/api/outcomes/{outcome_id}/workflows", {
        params: { path: { outcome_id: outcomeId } }
      });
      return requireData(result);
    },
    async createWorkflow(outcomeId, name, items) {
      const result = await client.POST("/api/outcomes/{outcome_id}/workflows", {
        params: { path: { outcome_id: outcomeId } },
        body: { name, items },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async getWorkflow(workflowId) {
      const result = await client.GET("/api/workflows/{workflow_id}", {
        params: { path: { workflow_id: workflowId } }
      });
      return requireData(result);
    },
    async listWorkItems(workflowId) {
      const result = await client.GET("/api/workflows/{workflow_id}/work-items", {
        params: { path: { workflow_id: workflowId } }
      });
      return requireData(result);
    },
    async listEffects(workflowId) {
      const result = await client.GET("/api/workflows/{workflow_id}/effects", {
        params: { path: { workflow_id: workflowId } }
      });
      return requireData(result);
    },
    async getBudget(projectId) {
      const result = await client.GET("/api/projects/{project_id}/budget", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async setBudget(projectId, limitUnits) {
      const result = await client.PUT("/api/projects/{project_id}/budget", {
        params: { path: { project_id: projectId } },
        body: { limit_units: limitUnits },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listArtifacts(workflowId) {
      const result = await client.GET("/api/workflows/{workflow_id}/artifacts", {
        params: { path: { workflow_id: workflowId } }
      });
      return requireData(result);
    },
    async listConversation(workflowId) {
      const result = await client.GET("/api/workflows/{workflow_id}/conversation", {
        params: { path: { workflow_id: workflowId } }
      });
      return requireData(result);
    },
    async startWorkflow(workflowId) {
      const result = await client.POST("/api/workflows/{workflow_id}/start", {
        params: { path: { workflow_id: workflowId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async pauseWorkflow(workflowId) {
      const result = await client.POST("/api/workflows/{workflow_id}/pause", {
        params: { path: { workflow_id: workflowId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async resumeWorkflow(workflowId) {
      const result = await client.POST("/api/workflows/{workflow_id}/resume", {
        params: { path: { workflow_id: workflowId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async cancelWorkflow(workflowId) {
      const result = await client.POST("/api/workflows/{workflow_id}/cancel", {
        params: { path: { workflow_id: workflowId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async setWorkflowKillSwitch(workflowId, enabled) {
      const result = await client.PUT("/api/workflows/{workflow_id}/kill-switch", {
        params: { path: { workflow_id: workflowId } },
        body: { enabled },
        headers: mutationHeaders()
      });
      requireData(result);
    },
    async runNext(workflowId) {
      const result = await client.POST("/api/workflows/{workflow_id}/run-next", {
        params: { path: { workflow_id: workflowId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async approveEffect(effectId) {
      const result = await client.POST("/api/effects/{effect_id}/approve", {
        params: { path: { effect_id: effectId } },
        headers: mutationHeaders()
      });
      requireData(result);
    },
    async rejectEffect(effectId) {
      const result = await client.POST("/api/effects/{effect_id}/reject", {
        params: { path: { effect_id: effectId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listTeams(projectId) {
      const result = await client.GET("/api/projects/{project_id}/teams", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async createTeam(projectId, name) {
      const result = await client.POST("/api/projects/{project_id}/teams", {
        params: { path: { project_id: projectId } },
        body: { name },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listProviders(projectId) {
      const result = await client.GET("/api/projects/{project_id}/providers", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async createProvider(projectId, provider, credentialRef) {
      const result = await client.POST("/api/projects/{project_id}/providers", {
        params: { path: { project_id: projectId } },
        body: { provider, credential_ref: credentialRef },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async evaluateAutonomy(projectId, capability) {
      const result = await client.POST("/api/projects/{project_id}/autonomy/evaluate", {
        params: { path: { project_id: projectId } },
        body: { capability, requested_execution: true },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listMemories(projectId) {
      const result = await client.GET("/api/projects/{project_id}/memories", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async storeMemory(projectId, content) {
      const result = await client.POST("/api/projects/{project_id}/memories", {
        params: { path: { project_id: projectId } },
        body: { scope: "project", content },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async retrieveMemory(projectId, query) {
      const result = await client.GET("/api/projects/{project_id}/memories/retrieve", {
        params: { path: { project_id: projectId }, query: { query } }
      });
      return requireData(result);
    },
    async listSkills(projectId) {
      const result = await client.GET("/api/projects/{project_id}/skills", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async createSkill(projectId, name, content) {
      const result = await client.POST("/api/projects/{project_id}/skills", {
        params: { path: { project_id: projectId } },
        body: { name, content },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async activateSkill(skillId) {
      const result = await client.POST("/api/skills/{skill_id}/activate", {
        params: { path: { skill_id: skillId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listRoutines(projectId) {
      const result = await client.GET("/api/projects/{project_id}/routines", {
        params: { path: { project_id: projectId } }
      });
      return requireData(result);
    },
    async createRoutine(projectId, name, skillVersionId) {
      const result = await client.POST("/api/projects/{project_id}/routines", {
        params: { path: { project_id: projectId } },
        body: { name, skill_version_id: skillVersionId },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async runRoutine(routineId) {
      const result = await client.POST("/api/routines/{routine_id}/run", {
        params: { path: { routine_id: routineId } },
        headers: mutationHeaders()
      });
      return requireData(result);
    },
    async listOfflineIntents() {
      const result = await client.GET("/api/offline-intents");
      return requireData(result);
    },
    async listChannelEvents() {
      const result = await client.GET("/api/channel/events");
      return requireData(result);
    }
  };
}

function readDetail(error: unknown): unknown {
  if (typeof error === "object" && error !== null && "detail" in error) {
    return error.detail;
  }
  return error;
}

function requireData<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.error || result.data === undefined) {
    throw new ApiFailure(result.response.status, readDetail(result.error));
  }
  return result.data;
}
