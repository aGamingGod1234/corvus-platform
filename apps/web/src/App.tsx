import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  createCorvusApi,
  type Artifact,
  type AutonomyDecision,
  type Budget,
  type ChannelEvent,
  type ConversationEntry,
  type CorvusApi,
  type Effect,
  type MemoryEntry,
  type OfflineIntent,
  type Outcome,
  type Project,
  type ProviderConnection,
  type RetrievedMemory,
  type Routine,
  type SkillVersion,
  type Team,
  type WorkItem,
  type WorkItemDefinition,
  type Workflow
} from "./api";
import { ActivityIcon, PlayIcon } from "./icons";
import { OnboardingFlow } from "./app/OnboardingFlow";
import { AppShell } from "./app/AppShell";
import { WorkspaceRouter } from "./app/WorkspaceRouter";
import { WorkspaceErrorBoundary } from "./app/WorkspaceErrorBoundary";
import {
  completeLegacyPreferenceMigration,
  dismissLegacyPreferenceMigration,
  loadLegacyWorkspacePreference,
  type LegacyPreferenceCandidate
} from "./app/preferences";
import { getWorkspaceProfile } from "./app/workspaceProfiles";
import { useAuth } from "./auth/AuthProvider";
import { AuthApiError } from "./auth/authApi";
import { useWorkspaceSync } from "./sync/SyncProvider";
import { LocalRuntimeLauncher } from "./runtime/LocalRuntimeLauncher";
import { isLoopbackRuntimeHost } from "./runtime/localRuntime";
import { SyncConflictPanel } from "./components/SyncConflictPanel";

const browserApi = createCorvusApi();
const EVENT_TYPES = [
  "workflow.started",
  "workflow.succeeded",
  "work_item.running",
  "work_item.waiting_approval",
  "work_item.succeeded",
  "effect.approved"
] as const;
const DEFAULT_DEMO_BUDGET_UNITS = 10;
const DEFAULT_WORK_ITEMS: WorkItemDefinition[] = [
  {
    key: "prepare",
    title: "Prepare the governed change",
    depends_on: [],
    cost_units: 0,
    requires_approval: false
  },
  {
    key: "deliver",
    title: "Deliver the accepted outcome",
    depends_on: ["prepare"],
    cost_units: 2,
    requires_approval: true,
    effect: {
      kind: "filesystem",
      target: "demo/delivery.json",
      payload: { purpose: "Corvus browser acceptance" }
    }
  }
];

interface AppProps {
  api?: CorvusApi;
  locationHostname?: string;
  preferenceStorage?: Storage;
}

function takeDesktopPairingValue(): string | null {
  const parameters = new URLSearchParams(window.location.hash.slice(1));
  const value = parameters.get("pair");
  if (value === null) return null;
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return value.length >= 16 && value.length <= 512 ? value : null;
}

interface WorkflowDetail {
  items: WorkItem[];
  effects: Effect[];
  budget: Budget | null;
  artifacts: Artifact[];
  conversation: ConversationEntry[];
}

interface OperationsDetail {
  teams: Team[];
  providers: ProviderConnection[];
  memories: MemoryEntry[];
  skills: SkillVersion[];
  routines: Routine[];
  offlineIntents: OfflineIntent[];
  channelEvents: ChannelEvent[];
}

interface ActivityEntry {
  id: string;
  type: string;
}

const EMPTY_DETAIL: WorkflowDetail = {
  items: [],
  effects: [],
  budget: null,
  artifacts: [],
  conversation: []
};

const EMPTY_OPERATIONS: OperationsDetail = {
  teams: [],
  providers: [],
  memories: [],
  skills: [],
  routines: [],
  offlineIntents: [],
  channelEvents: []
};

export function App({
  api = browserApi,
  locationHostname = window.location.hostname,
  preferenceStorage = window.localStorage
}: AppProps) {
  const auth = useAuth();
  const workspaceSync = useWorkspaceSync();
  const desktopPairingAttempt = useRef<Promise<void> | null>(null);
  const workspaceGenerationRef = useRef(0);
  const [legacyPreference, setLegacyPreference] = useState<LegacyPreferenceCandidate | null>(null);
  const experience =
    workspaceSync.accountProfile?.experience_kind ?? auth.session?.experience_kind ?? null;
  const selectedWorkspace = workspaceSync.selectedWorkspace;
  const profile =
    experience === null || selectedWorkspace === null
      ? null
      : getWorkspaceProfile(experience, selectedWorkspace.workspace_kind);
  const [activeRoute, setActiveRoute] = useState("");
  const [phase, setPhase] = useState<"checking" | "pairing" | "ready">("checking");
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [detail, setDetail] = useState<WorkflowDetail>(EMPTY_DETAIL);
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [operations, setOperations] = useState<OperationsDetail>(EMPTY_OPERATIONS);
  const [autonomy, setAutonomy] = useState<AutonomyDecision | null>(null);
  const [retrievedMemories, setRetrievedMemories] = useState<RetrievedMemory[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const hostedLocalHandoff =
    selectedWorkspace !== null && !isLoopbackRuntimeHost(locationHostname);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    setLegacyPreference(loadLegacyWorkspacePreference(preferenceStorage).candidate);
  }, [auth.status, preferenceStorage]);

  useEffect(() => {
    if (
      legacyPreference === null ||
      experience === null ||
      selectedWorkspace === null ||
      workspaceSync.status !== "ready"
    ) return;
    if (
      legacyPreference.experience === experience &&
      legacyPreference.workspaceKind === selectedWorkspace.workspace_kind
    ) {
      completeLegacyPreferenceMigration(preferenceStorage, {
        experienceConfirmed: true,
        workspaceCreationConfirmed: true
      });
      setLegacyPreference(null);
    }
  }, [experience, legacyPreference, preferenceStorage, selectedWorkspace, workspaceSync.status]);

  const loadProjects = useCallback(async (generation = workspaceGenerationRef.current) => {
    const loaded = await api.listProjects();
    if (generation !== workspaceGenerationRef.current) return false;
    setProjects(loaded);
    setActiveProject((current) => current ?? loaded[0] ?? null);
    return true;
  }, [api]);

  useEffect(() => {
    if (
      profile === null ||
      selectedWorkspace === null ||
      workspaceSync.status !== "ready" ||
      hostedLocalHandoff
    ) return;
    const generation = ++workspaceGenerationRef.current;
    setPhase("checking");
    setActiveRoute(profile.routes[0].id);
    setProjects([]);
    setActiveProject(null);
    setOutcomes([]);
    setWorkflow(null);
    setDetail(EMPTY_DETAIL);
    setSelectedItem(null);
    setOperations(EMPTY_OPERATIONS);
    setAutonomy(null);
    setRetrievedMemories([]);
    setActivity([]);
    setError("");
    setBusy(false);
    let active = true;
    api
      .session()
      .then(() => loadProjects(generation))
      .then(() => active && generation === workspaceGenerationRef.current && setPhase("ready"))
      .catch(async () => {
        if (!active || generation !== workspaceGenerationRef.current) return;
        const pairingValue = takeDesktopPairingValue();
        if (pairingValue === null) {
          setPhase("pairing");
          return;
        }
        try {
          desktopPairingAttempt.current ??= api.pair(pairingValue);
          await desktopPairingAttempt.current;
          await loadProjects(generation);
          if (active && generation === workspaceGenerationRef.current) setPhase("ready");
        } catch (reason: unknown) {
          if (!active) return;
          setError(messageFor(reason));
          setPhase("pairing");
        }
      });
    return () => {
      active = false;
      if (generation === workspaceGenerationRef.current) workspaceGenerationRef.current += 1;
    };
  }, [api, hostedLocalHandoff, loadProjects, profile, selectedWorkspace, workspaceSync.status]);

  useEffect(() => {
    if (profile === null) return;
    setActiveRoute(profile.routes[0].id);
  }, [profile]);

  const refreshWorkflow = useCallback(
    async (
      workflowId: string,
      projectId: string,
      generation = workspaceGenerationRef.current
    ) => {
      const [current, items, effects, budget, artifacts, conversation] = await Promise.all([
        api.getWorkflow(workflowId),
        api.listWorkItems(workflowId),
        api.listEffects(workflowId),
        api.getBudget(projectId),
        api.listArtifacts(workflowId),
        api.listConversation(workflowId)
      ]);
      if (generation !== workspaceGenerationRef.current) return null;
      setWorkflow(current);
      setDetail({ items, effects, budget, artifacts, conversation });
      setSelectedItem((currentItem) =>
        currentItem ? items.find((item) => item.id === currentItem.id) ?? null : null
      );
      return current;
    },
    [api]
  );

  const loadOperations = useCallback(
    async (projectId: string, generation = workspaceGenerationRef.current) => {
      const [teams, providers, memories, skills, routines, offlineIntents, channelEvents] =
        await Promise.all([
          api.listTeams(projectId),
          api.listProviders(projectId),
          api.listMemories(projectId),
          api.listSkills(projectId),
          api.listRoutines(projectId),
          api.listOfflineIntents(),
          api.listChannelEvents()
        ]);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations({ teams, providers, memories, skills, routines, offlineIntents, channelEvents });
    },
    [api]
  );

  useEffect(() => {
    if (!activeProject) {
      setOutcomes([]);
      setWorkflow(null);
      setDetail(EMPTY_DETAIL);
      return;
    }
    let active = true;
    const generation = workspaceGenerationRef.current;
    const project = activeProject;
    api
      .listOutcomes(project.id)
      .then(async (loadedOutcomes) => {
        if (!active || generation !== workspaceGenerationRef.current) return;
        setOutcomes(loadedOutcomes);
        const latestOutcome = loadedOutcomes.at(-1);
        if (!latestOutcome) {
          setWorkflow(null);
          setDetail(EMPTY_DETAIL);
          return;
        }
        const loadedWorkflows = await api.listWorkflows(latestOutcome.id);
        const latestWorkflow = loadedWorkflows.at(-1) ?? null;
        if (!active || generation !== workspaceGenerationRef.current) return;
        setWorkflow(latestWorkflow);
        if (latestWorkflow) await refreshWorkflow(latestWorkflow.id, project.id, generation);
      })
      .catch((reason: unknown) => {
        if (active && generation === workspaceGenerationRef.current) {
          setError(messageFor(reason));
        }
      });
    return () => {
      active = false;
    };
  }, [activeProject, api, refreshWorkflow]);

  useEffect(() => {
    if (!activeProject) {
      setOperations(EMPTY_OPERATIONS);
      return;
    }
    let active = true;
    const generation = workspaceGenerationRef.current;
    loadOperations(activeProject.id, generation).catch((reason: unknown) => {
      if (active && generation === workspaceGenerationRef.current) setError(messageFor(reason));
    });
    return () => {
      active = false;
    };
  }, [activeProject, loadOperations]);

  useEffect(() => {
    const workflowId = workflow?.id;
    const projectId = activeProject?.id;
    const generation = workspaceGenerationRef.current;
    if (!workflowId || !projectId || typeof EventSource === "undefined") return;
    const stream = new EventSource(`/api/workflows/${workflowId}/events`);
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    let refreshing = false;
    let queued = false;
    let closed = false;

    const scheduleRefresh = () => {
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = setTimeout(async () => {
        if (refreshing) {
          queued = true;
          return;
        }
        refreshing = true;
        try {
          const current = await refreshWorkflow(workflowId, projectId, generation);
          if (current?.status === "succeeded") stream.close();
        } catch (reason) {
          if (!closed) setError(messageFor(reason));
        } finally {
          refreshing = false;
          if (queued && !closed) {
            queued = false;
            scheduleRefresh();
          }
        }
      }, 80);
    };
    EVENT_TYPES.forEach((eventType) =>
      stream.addEventListener(eventType, (event) => {
        const message = event as MessageEvent<string>;
        let eventId = `${eventType}-${Date.now()}`;
        try {
          const parsed = JSON.parse(message.data) as { id?: number };
          if (parsed.id !== undefined) eventId = String(parsed.id);
        } catch {
          // EventSource may deliver an empty test event; refresh still uses durable API state.
        }
        if (generation !== workspaceGenerationRef.current) return;
        setActivity((current) => [...current, { id: eventId, type: eventType }].slice(-8));
        scheduleRefresh();
      })
    );
    stream.onerror = () => {
      if (!closed && generation === workspaceGenerationRef.current) {
        setError("Live updates reconnecting. Durable state remains available.");
      }
    };
    return () => {
      closed = true;
      if (refreshTimer) clearTimeout(refreshTimer);
      stream.close();
    };
  }, [activeProject?.id, refreshWorkflow, workflow?.id]);

  async function pair(value: string) {
    await perform(async (generation) => {
      await api.pair(value);
      await loadProjects(generation);
      if (generation === workspaceGenerationRef.current) setPhase("ready");
    });
  }

  async function createProject(name: string) {
    await perform(async (generation) => {
      const created = await api.createProject(name);
      if (generation !== workspaceGenerationRef.current) return;
      setProjects((current) => [...current, created]);
      setActiveProject(created);
    });
  }

  async function createWorkflow(title: string, criterion: string, name: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      await api.setBudget(activeProject.id, DEFAULT_DEMO_BUDGET_UNITS);
      if (generation !== workspaceGenerationRef.current) return;
      const outcome = await api.createOutcome(activeProject.id, title, criterion);
      if (generation !== workspaceGenerationRef.current) return;
      const created = await api.createWorkflow(outcome.id, name, DEFAULT_WORK_ITEMS);
      if (generation !== workspaceGenerationRef.current) return;
      setOutcomes((current) => [...current, outcome]);
      setWorkflow(created);
      await refreshWorkflow(created.id, activeProject.id, generation);
    });
  }

  async function mutateWorkflow(action: "start" | "run") {
    if (!workflow || !activeProject) return;
    await perform(async (generation) => {
      if (action === "start") await api.startWorkflow(workflow.id);
      else await api.runNext(workflow.id);
      if (generation === workspaceGenerationRef.current) {
        await refreshWorkflow(workflow.id, activeProject.id, generation);
      }
    });
  }

  async function approve(effectId: string) {
    if (!workflow || !activeProject) return;
    await perform(async (generation) => {
      await api.approveEffect(effectId);
      if (generation === workspaceGenerationRef.current) {
        await refreshWorkflow(workflow.id, activeProject.id, generation);
      }
    });
  }

  async function reject(effectId: string) {
    if (!workflow || !activeProject) return;
    await perform(async (generation) => {
      await api.rejectEffect(effectId);
      if (generation === workspaceGenerationRef.current) {
        await refreshWorkflow(workflow.id, activeProject.id, generation);
      }
    });
  }

  async function controlWorkflow(action: "pause" | "resume" | "cancel" | "kill") {
    if (!workflow || !activeProject) return;
    await perform(async (generation) => {
      if (action === "pause") await api.pauseWorkflow(workflow.id);
      if (action === "resume") await api.resumeWorkflow(workflow.id);
      if (action === "cancel") await api.cancelWorkflow(workflow.id);
      if (action === "kill") await api.setWorkflowKillSwitch(workflow.id, true);
      if (generation === workspaceGenerationRef.current) {
        await refreshWorkflow(workflow.id, activeProject.id, generation);
      }
    });
  }

  async function updateBudget(limitUnits: number) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const budget = await api.setBudget(activeProject.id, limitUnits);
      if (generation !== workspaceGenerationRef.current) return;
      setDetail((current) => ({ ...current, budget }));
    });
  }

  async function createTeam(name: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const team = await api.createTeam(activeProject.id, name);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations((current) => ({ ...current, teams: [...current.teams, team] }));
    });
  }

  async function createProvider(provider: string, credentialRef: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const connection = await api.createProvider(activeProject.id, provider, credentialRef);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations((current) => ({
        ...current,
        providers: [...current.providers, connection]
      }));
    });
  }

  async function evaluateAutonomy() {
    if (!activeProject) return;
    await perform(async (generation) => {
      const decision = await api.evaluateAutonomy(activeProject.id, "model.generate");
      if (generation === workspaceGenerationRef.current) setAutonomy(decision);
    });
  }

  async function storeMemory(content: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const memory = await api.storeMemory(activeProject.id, content);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations((current) => ({ ...current, memories: [...current.memories, memory] }));
    });
  }

  async function searchMemory(query: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const memories = await api.retrieveMemory(activeProject.id, query);
      if (generation === workspaceGenerationRef.current) setRetrievedMemories(memories);
    });
  }

  async function createSkill(name: string, content: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const draft = await api.createSkill(activeProject.id, name, content);
      if (generation !== workspaceGenerationRef.current) return;
      const active = await api.activateSkill(draft.id);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations((current) => ({ ...current, skills: [...current.skills, active] }));
    });
  }

  async function createRoutine(name: string, skillVersionId: string) {
    if (!activeProject) return;
    await perform(async (generation) => {
      const routine = await api.createRoutine(activeProject.id, name, skillVersionId);
      if (generation !== workspaceGenerationRef.current) return;
      setOperations((current) => ({ ...current, routines: [...current.routines, routine] }));
    });
  }

  async function runRoutine(routineId: string) {
    await perform(async () => {
      await api.runRoutine(routineId);
    });
  }

  async function perform(action: (generation: number) => Promise<void>) {
    const generation = workspaceGenerationRef.current;
    setBusy(true);
    setError("");
    try {
      await action(generation);
    } catch (reason) {
      if (generation === workspaceGenerationRef.current) setError(messageFor(reason));
    } finally {
      if (generation === workspaceGenerationRef.current) setBusy(false);
    }
  }

  if (auth.status === "checking") return <LoadingScreen label="Checking your Corvus identity…" />;
  if (auth.status === "retryable_error") {
    return <RetryScreen message={auth.error?.message ?? "Corvus could not verify your identity."} onRetry={auth.retry} />;
  }
  if (auth.status === "unauthenticated") {
    return (
      <OnboardingFlow
        accountVersion={0}
        authStatus="unauthenticated"
        experienceKind={null}
        onCreateWorkspace={() => Promise.reject(new Error("session_required"))}
        onExperienceSaved={() => Promise.reject(new Error("session_required"))}
        onGoogleStart={auth.startGoogle}
        onWorkspaceConfirmed={() => undefined}
      />
    );
  }
  if (auth.session === null) return <LoadingScreen label="Checking your Corvus identity…" />;
  if (workspaceSync.status === "idle" || workspaceSync.status === "loading" || workspaceSync.status === "resyncing") {
    return <LoadingScreen label="Opening your authorized workspaces…" />;
  }
  if (workspaceSync.status === "onboarding_required") {
    return (
      <OnboardingFlow
        accountVersion={workspaceSync.accountProfile?.version ?? auth.session.account_version}
        authStatus="authenticated"
        experienceKind={experience}
        onCreateWorkspace={workspaceSync.createWorkspace}
        onDismissMigration={() => {
          dismissLegacyPreferenceMigration(preferenceStorage);
          setLegacyPreference(null);
        }}
        onExperienceSaved={async (experienceKind, expectedVersion) => {
          try {
            const saved = await workspaceSync.saveExperience(experienceKind, expectedVersion);
            await auth.reloadSession();
            return saved;
          } catch (reason) {
            if (
              reason instanceof AuthApiError &&
              reason.status === 409 &&
              reason.code === "account_version_conflict"
            ) {
              await auth.reloadSession();
            }
            throw reason;
          }
        }}
        onGoogleStart={auth.startGoogle}
        onWorkspaceConfirmed={() => {
          completeLegacyPreferenceMigration(preferenceStorage, {
            experienceConfirmed: true,
            workspaceCreationConfirmed: true
          });
          setLegacyPreference(null);
        }}
        preselection={legacyPreference}
      />
    );
  }
  if (workspaceSync.status === "selection_required" && selectedWorkspace === null) {
    return <WorkspaceSelection accountEmail={auth.session.email} onSelect={workspaceSync.selectWorkspace} workspaces={workspaceSync.workspaces} />;
  }
  if (profile === null || selectedWorkspace === null) {
    return <RetryScreen message={workspaceSync.error?.message ?? "No authorized workspace is available."} onRetry={workspaceSync.refresh} />;
  }

  const executionSurface = (
    <ExecutionCanvas
      activity={activity}
      busy={busy}
      detail={detail}
      onApprove={approve}
      onControl={controlWorkflow}
      onCreate={createWorkflow}
      onReject={reject}
      onRun={() => mutateWorkflow("run")}
      onSelectItem={setSelectedItem}
      onStart={() => mutateWorkflow("start")}
      outcome={outcomes.at(-1) ?? null}
      project={activeProject}
      selectedItem={selectedItem}
      workflow={workflow}
    />
  );
  const operationsSurface = (
    <OperationsPanel
      autonomy={autonomy}
      busy={busy}
      detail={operations}
      onCreateProvider={createProvider}
      onCreateRoutine={createRoutine}
      onCreateSkill={createSkill}
      onCreateTeam={createTeam}
      onEvaluateAutonomy={evaluateAutonomy}
      onRunRoutine={runRoutine}
      onSearchMemory={searchMemory}
      onStoreMemory={storeMemory}
      project={activeProject}
      retrievedMemories={retrievedMemories}
    />
  );

  return (
    <AppShell
      accountEmail={auth.session.email}
      activeRoute={activeRoute || profile.routes[0].id}
      error={error || workspaceSync.error?.message || ""}
      inspector={(
        <Inspector
          artifacts={detail.artifacts}
          budget={detail.budget}
          effects={detail.effects}
          item={selectedItem}
          onApprove={approve}
          onClose={() => setSelectedItem(null)}
          onReject={reject}
          onUpdateBudget={updateBudget}
          conversation={detail.conversation}
        />
      )}
      inspectorOpen={selectedItem !== null}
      legacyPreferencePending={legacyPreference !== null}
      onDismissLegacyPreference={() => {
        dismissLegacyPreferenceMigration(preferenceStorage);
        setLegacyPreference(null);
      }}
      onNavigate={(routeId) => {
        setActiveRoute(routeId);
        setSelectedItem(null);
      }}
      onWorkspaceSelect={workspaceSync.selectWorkspace}
      profile={profile}
      projectContext={(
        <ProjectRail
          activeProject={activeProject}
          busy={busy}
          onCreate={createProject}
          onSelect={setActiveProject}
          projects={projects}
        />
      )}
      selectedWorkspace={selectedWorkspace}
      selectionRequired={workspaceSync.status === "forbidden"}
      workspaces={workspaceSync.workspaces}
    >
      <WorkspaceErrorBoundary>
        {workspaceSync.status === "conflict" && workspaceSync.conflict !== null ? (
          <SyncConflictPanel
            currentVersion={workspaceSync.conflict.currentVersion}
            desiredVersion={workspaceSync.conflict.submittedExpectedVersion}
            onReload={workspaceSync.reloadConflict}
            onRetry={workspaceSync.retryConflict}
          />
        ) : (activeRoute || profile.routes[0].id) === "settings" ? (
          <WorkspaceRouter
            activeRoute="settings"
            executionSurface={executionSurface}
            operationsSurface={operationsSurface}
            profile={profile}
            projectName={activeProject?.name ?? null}
          />
        ) : hostedLocalHandoff ? (
          <LocalRuntimeLauncher
            experience={experience ?? profile.experience}
            workspaceKind={selectedWorkspace.workspace_kind}
          />
        ) : phase === "checking" ? (
          <LoadingScreen />
        ) : phase === "pairing" ? (
          <PairingScreen busy={busy} error={error} onPair={pair} />
        ) : (
          <WorkspaceRouter
            activeRoute={activeRoute || profile.routes[0].id}
            executionSurface={executionSurface}
            operationsSurface={operationsSurface}
            profile={profile}
            projectName={activeProject?.name ?? null}
          />
        )}
      </WorkspaceErrorBoundary>
    </AppShell>
  );
}

function LoadingScreen({ label = "Opening local workspace…" }: { label?: string }) {
  return <div className="loading-screen" role="status">{label}</div>;
}

function RetryScreen({ message, onRetry }: { message: string; onRetry(): Promise<void> }) {
  return (
    <main className="pairing-screen" id="main-content">
      <section className="pairing-panel" aria-labelledby="retry-title">
        <p className="eyebrow">Connection interrupted</p>
        <h1 id="retry-title">Corvus could not finish opening.</h1>
        <p role="alert">{message}</p>
        <button className="button button--primary" onClick={() => void onRetry()} type="button">Try again</button>
      </section>
    </main>
  );
}

function WorkspaceSelection({
  accountEmail,
  onSelect,
  workspaces
}: {
  accountEmail: string;
  onSelect(workspaceId: string): Promise<void>;
  workspaces: ReturnType<typeof useWorkspaceSync>["workspaces"];
}) {
  const [busyId, setBusyId] = useState<string | null>(null);

  return (
    <main className="onboarding-shell" id="main-content">
      <section className="onboarding-panel" aria-labelledby="workspace-selection-title">
        <p className="eyebrow">Signed in as {accountEmail}</p>
        <h1 id="workspace-selection-title">Choose an authorized workspace</h1>
        <p className="onboarding-lede">Corvus never guesses when more than one workspace is available.</p>
        <div className="workspace-selection-list">
          {workspaces.map((workspace) => (
            <button
              className="choice-card"
              disabled={busyId !== null || workspace.id === undefined}
              key={workspace.id ?? workspace.name}
              onClick={() => {
                if (workspace.id === undefined) return;
                setBusyId(workspace.id);
                void onSelect(workspace.id).finally(() => setBusyId(null));
              }}
              type="button"
            >
              <span><strong>{workspace.name}</strong><small>{workspace.workspace_kind}</small></span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

function PairingScreen({
  busy,
  error,
  onPair
}: {
  busy: boolean;
  error: string;
  onPair: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const pairingValue = value;
    setValue("");
    await onPair(pairingValue);
  }

  return (
    <div className="pairing-screen">
      <section className="pairing-panel">
        <p className="eyebrow">Local authority boundary</p>
        <h1>Pair this browser with Corvus.</h1>
        <p>The pairing value is used once and is never stored by this client.</p>
        <form onSubmit={submit}>
          <label htmlFor="pairing-value">One-time pairing value</label>
          <input
            autoComplete="off"
            id="pairing-value"
            onChange={(event) => setValue(event.target.value)}
            required
            type="password"
            value={value}
          />
          <button className="button button--primary" disabled={busy} type="submit">
            {busy ? "Pairing…" : "Pair this browser"}
          </button>
        </form>
        {error && <p className="inline-error" role="alert">{error}</p>}
      </section>
    </div>
  );
}

function ProjectRail({
  activeProject,
  busy,
  onCreate,
  onSelect,
  projects
}: {
  activeProject: Project | null;
  busy: boolean;
  onCreate: (name: string) => Promise<void>;
  onSelect: (project: Project) => void;
  projects: Project[];
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onCreate(name);
    setName("");
    setCreating(false);
  }

  return (
    <section aria-label="Projects" className="project-rail" data-source-refs="docs-github-com">
      <div className="rail-heading">
        <span>Projects</span>
        <button className="text-button" onClick={() => setCreating(true)} type="button">New project</button>
      </div>
      {creating && (
        <form className="inline-form" onSubmit={submit}>
          <label htmlFor="project-name">Project name</label>
          <input id="project-name" onChange={(event) => setName(event.target.value)} required value={name} />
          <button className="button button--primary" disabled={busy} type="submit">Create project</button>
        </form>
      )}
      <nav aria-label="Projects">
        {projects.map((project, index) => (
          <button
            aria-current={project.id === activeProject?.id ? "page" : undefined}
            className="project-row"
            key={project.id}
            onClick={() => onSelect(project)}
            type="button"
          >
            <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
            <span>{project.name}</span>
          </button>
        ))}
      </nav>
    </section>
  );
}

function ExecutionCanvas({
  activity,
  busy,
  detail,
  onApprove,
  onControl,
  onCreate,
  onReject,
  onRun,
  onSelectItem,
  onStart,
  outcome,
  project,
  selectedItem,
  workflow
}: {
  activity: ActivityEntry[];
  busy: boolean;
  detail: WorkflowDetail;
  onApprove: (effectId: string) => Promise<void>;
  onControl: (action: "pause" | "resume" | "cancel" | "kill") => Promise<void>;
  onCreate: (title: string, criterion: string, name: string) => Promise<void>;
  onReject: (effectId: string) => Promise<void>;
  onRun: () => void;
  onSelectItem: (item: WorkItem) => void;
  onStart: () => void;
  outcome: Outcome | null;
  project: Project | null;
  selectedItem: WorkItem | null;
  workflow: Workflow | null;
}) {
  if (!project) {
    return <div className="empty-canvas"><p className="eyebrow">No active project</p><h1>Create a project to open an execution rail.</h1></div>;
  }
  if (!workflow) return <WorkflowBuilder busy={busy} onCreate={onCreate} project={project} />;

  const canStart = workflow.status === "draft";
  const canRun = detail.items.some((item) => item.status === "ready");
  const pendingEffects = detail.effects.filter((effect) => effect.status === "pending_approval");
  const terminal = ["cancelled", "failed", "succeeded"].includes(workflow.status);
  return (
    <section className="workflow-view">
      <div className="workflow-heading">
        <div>
          <p className="eyebrow">Outcome v{outcome?.version ?? 1}</p>
          <h1>{outcome?.title ?? workflow.name}</h1>
          <p>{outcome?.acceptance_criteria.join(" · ")}</p>
        </div>
        <div className="workflow-actions" data-component-source="shadcn-button">
          <span className={`status status--${workflow.status}`}>{workflow.status}</span>
          {canStart && <button className="button button--primary" data-component-source="shadcn-button" disabled={busy} onClick={onStart} type="button"><PlayIcon /> Start workflow</button>}
          {workflow.status === "running" && <button className="button button--primary" data-component-source="shadcn-button" disabled={busy || !canRun} onClick={onRun} type="button"><PlayIcon /> Run next</button>}
          {workflow.status === "running" && <button className="button" disabled={busy} onClick={() => onControl("pause")} type="button">Pause</button>}
          {workflow.status === "paused" && <button className="button" disabled={busy} onClick={() => onControl("resume")} type="button">Resume</button>}
          {!terminal && <button className="button" disabled={busy} onClick={() => onControl("cancel")} type="button">Cancel</button>}
          {!terminal && <button className="button button--danger" disabled={busy} onClick={() => onControl("kill")} type="button">Stop effects</button>}
        </div>
      </div>
      <div className="execution-rail" aria-label="Execution rail">
        <h2>Execution rail</h2>
        {detail.items.map((item) => (
          <button
            aria-pressed={selectedItem?.id === item.id}
            className="work-item-row"
            key={item.id}
            onClick={() => onSelectItem(item)}
            type="button"
          >
            <span className={`state-node state-node--${item.status}`} />
            <span className="work-item-copy"><strong>{item.title}</strong><small>{item.key} · attempt {item.attempt_count}</small></span>
            <span className="mono-state">{item.status.replace("_", " ")}</span>
          </button>
        ))}
      </div>
      <section className="approval-inbox" aria-label="Approval inbox">
        <div className="section-heading"><h2>Approval inbox</h2><span>{pendingEffects.length} waiting</span></div>
        {pendingEffects.length === 0 ? <p className="quiet-copy">No effects are waiting for a decision.</p> : pendingEffects.map((effect) => (
          <div className="approval-row" key={effect.id}>
            <div><strong>{effect.binding.target}</strong><small>{effect.binding.kind} · governed effect</small></div>
            <div className="row-actions">
              <button className="button" disabled={busy} onClick={() => onReject(effect.id)} type="button">Reject</button>
              <button className="button button--primary" data-component-source="shadcn-button" disabled={busy} onClick={() => onApprove(effect.id)} type="button">Approve</button>
            </div>
          </div>
        ))}
      </section>
      <section className="activity-view" aria-live="polite">
        <div className="section-heading"><h2>Live activity</h2><span>SSE</span></div>
        {activity.length === 0 ? <p className="quiet-copy">Waiting for durable execution events.</p> : activity.map((entry) => (
          <div className="activity-row" key={`${entry.id}-${entry.type}`}><span>{entry.id}</span><strong>{entry.type.replaceAll("_", " ")}</strong></div>
        ))}
      </section>
    </section>
  );
}

function WorkflowBuilder({
  busy,
  onCreate,
  project
}: {
  busy: boolean;
  onCreate: (title: string, criterion: string, name: string) => Promise<void>;
  project: Project;
}) {
  const [title, setTitle] = useState("");
  const [criterion, setCriterion] = useState("");
  const [name, setName] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onCreate(title, criterion, name);
  }

  return (
    <section className="workflow-builder">
      <p className="eyebrow">{project.name}</p>
      <h1>Define the next durable outcome.</h1>
      <p>Corvus will create a two-step dependency graph you can run and inspect locally.</p>
      <form onSubmit={submit}>
        <label htmlFor="outcome-title">Outcome</label>
        <input id="outcome-title" onChange={(event) => setTitle(event.target.value)} required value={title} />
        <label htmlFor="acceptance-criterion">Acceptance criterion</label>
        <textarea id="acceptance-criterion" onChange={(event) => setCriterion(event.target.value)} required value={criterion} />
        <label htmlFor="workflow-name">Workflow name</label>
        <input id="workflow-name" onChange={(event) => setName(event.target.value)} required value={name} />
        <button className="button button--primary" disabled={busy} type="submit">Create workflow</button>
      </form>
    </section>
  );
}

function OperationsPanel({
  autonomy,
  busy,
  detail,
  onCreateProvider,
  onCreateRoutine,
  onCreateSkill,
  onCreateTeam,
  onEvaluateAutonomy,
  onRunRoutine,
  onSearchMemory,
  onStoreMemory,
  project,
  retrievedMemories
}: {
  autonomy: AutonomyDecision | null;
  busy: boolean;
  detail: OperationsDetail;
  onCreateProvider: (provider: string, credentialRef: string) => Promise<void>;
  onCreateRoutine: (name: string, skillVersionId: string) => Promise<void>;
  onCreateSkill: (name: string, content: string) => Promise<void>;
  onCreateTeam: (name: string) => Promise<void>;
  onEvaluateAutonomy: () => Promise<void>;
  onRunRoutine: (routineId: string) => Promise<void>;
  onSearchMemory: (query: string) => Promise<void>;
  onStoreMemory: (content: string) => Promise<void>;
  project: Project | null;
  retrievedMemories: RetrievedMemory[];
}) {
  if (!project) return <div className="empty-canvas"><p className="eyebrow">No active project</p><h1>Create a project to configure governed operations.</h1></div>;
  return (
    <section className="operations-view">
      <div className="operations-heading"><p className="eyebrow">{project.name}</p><h1>Governed operations.</h1><p>Collaboration, provider references, memory, skills, routines, and untrusted ingress stay inside the same authority boundary.</p></div>
      <div className="operations-grid">
        <section className="operations-section">
          <div className="section-heading"><h2>Collaboration</h2><span>{detail.teams.length} teams</span></div>
          <TeamForm busy={busy} onCreate={onCreateTeam} />
          <RecordList empty="No teams yet." items={detail.teams.map((team) => ({ id: team.id, primary: team.name, secondary: "owner-controlled" }))} />
        </section>
        <section className="operations-section">
          <div className="section-heading"><h2>Providers</h2><span>references only</span></div>
          <ProviderForm busy={busy} onCreate={onCreateProvider} />
          <RecordList empty="No provider references yet." items={detail.providers.map((provider) => ({ id: provider.id, primary: provider.provider, secondary: provider.credential_ref }))} />
          <button className="button" disabled={busy} onClick={onEvaluateAutonomy} type="button">Evaluate shadow action</button>
          {autonomy && <p className="decision-note"><strong>{autonomy.mode}</strong> · {autonomy.executed ? "executed" : "recorded, not executed"}</p>}
        </section>
        <section className="operations-section operations-section--wide">
          <div className="section-heading"><h2>Governed memory</h2><span>untrusted on retrieval</span></div>
          <MemoryForms busy={busy} onSearch={onSearchMemory} onStore={onStoreMemory} />
          <RecordList empty="No memory entries yet." items={detail.memories.map((memory) => ({ id: memory.id, primary: memory.content, secondary: `${memory.scope} · ${memory.provenance}` }))} />
          {retrievedMemories.map((memory) => <pre className="retrieved-memory" key={memory.entry_id}>{memory.context}</pre>)}
        </section>
        <section className="operations-section">
          <div className="section-heading"><h2>Skills</h2><span>versioned</span></div>
          <SkillForm busy={busy} onCreate={onCreateSkill} />
          <RecordList empty="No active skills yet." items={detail.skills.map((skill) => ({ id: skill.id, primary: `${skill.name} v${skill.version}`, secondary: skill.status }))} />
        </section>
        <section className="operations-section">
          <div className="section-heading"><h2>Routines</h2><span>authorized runs</span></div>
          <RoutineForm busy={busy} onCreate={onCreateRoutine} skills={detail.skills} />
          {detail.routines.length === 0 ? <p className="quiet-copy">No routines yet.</p> : detail.routines.map((routine) => <div className="record-row" key={routine.id}><div><strong>{routine.name}</strong><small>{routine.skill_version_id}</small></div><button className="text-button" disabled={busy} onClick={() => onRunRoutine(routine.id)} type="button">Run</button></div>)}
        </section>
        <section className="operations-section operations-section--wide">
          <div className="section-heading"><h2>Ingress visibility</h2><span>signed and deduplicated</span></div>
          <div className="ingress-columns"><RecordList empty="No offline intents." items={detail.offlineIntents.map((intent) => ({ id: intent.id, primary: `Offline · ${intent.status}`, secondary: `${intent.application_count} applications` }))} /><RecordList empty="No channel events." items={detail.channelEvents.map((event) => ({ id: event.id, primary: `${event.provider} · ${event.status}`, secondary: `${event.processing_count} processing pass` }))} /></div>
        </section>
      </div>
    </section>
  );
}

function TeamForm({ busy, onCreate }: { busy: boolean; onCreate: (name: string) => Promise<void> }) {
  const [name, setName] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); await onCreate(name); setName(""); }
  return <form className="compact-form" onSubmit={submit}><label htmlFor="team-name">Team name</label><div className="inline-control"><input id="team-name" onChange={(event) => setName(event.target.value)} required value={name} /><button className="button" disabled={busy} type="submit">Create team</button></div></form>;
}

function ProviderForm({ busy, onCreate }: { busy: boolean; onCreate: (provider: string, credentialRef: string) => Promise<void> }) {
  const [provider, setProvider] = useState("");
  const [credentialRef, setCredentialRef] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); await onCreate(provider, credentialRef); setProvider(""); setCredentialRef(""); }
  return <form className="compact-form" onSubmit={submit}><label htmlFor="provider-name">Provider</label><input id="provider-name" onChange={(event) => setProvider(event.target.value)} required value={provider} /><label htmlFor="credential-ref">Credential reference</label><input autoComplete="off" id="credential-ref" onChange={(event) => setCredentialRef(event.target.value)} placeholder="env://REFERENCE_NAME" required value={credentialRef} /><button className="button" disabled={busy} type="submit">Add provider reference</button></form>;
}

function MemoryForms({ busy, onSearch, onStore }: { busy: boolean; onSearch: (query: string) => Promise<void>; onStore: (content: string) => Promise<void> }) {
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("");
  async function store(event: FormEvent) { event.preventDefault(); await onStore(content); setContent(""); }
  async function search(event: FormEvent) { event.preventDefault(); await onSearch(query); }
  return <div className="split-forms"><form className="compact-form" onSubmit={store}><label htmlFor="memory-content">Memory content</label><textarea id="memory-content" onChange={(event) => setContent(event.target.value)} required value={content} /><button className="button" disabled={busy} type="submit">Store memory</button></form><form className="compact-form" onSubmit={search}><label htmlFor="memory-query">Retrieval query</label><input id="memory-query" onChange={(event) => setQuery(event.target.value)} required value={query} /><button className="button" disabled={busy} type="submit">Retrieve as untrusted data</button></form></div>;
}

function SkillForm({ busy, onCreate }: { busy: boolean; onCreate: (name: string, content: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); await onCreate(name, content); setName(""); setContent(""); }
  return <form className="compact-form" onSubmit={submit}><label htmlFor="skill-name">Skill name</label><input id="skill-name" onChange={(event) => setName(event.target.value)} required value={name} /><label htmlFor="skill-content">Skill instruction</label><textarea id="skill-content" onChange={(event) => setContent(event.target.value)} required value={content} /><button className="button" disabled={busy} type="submit">Create and activate</button></form>;
}

function RoutineForm({ busy, onCreate, skills }: { busy: boolean; onCreate: (name: string, skillVersionId: string) => Promise<void>; skills: SkillVersion[] }) {
  const [name, setName] = useState("");
  const [skillId, setSkillId] = useState("");
  const activeSkills = skills.filter((skill) => skill.status === "active");
  async function submit(event: FormEvent) { event.preventDefault(); await onCreate(name, skillId); setName(""); }
  return <form className="compact-form" onSubmit={submit}><label htmlFor="routine-name">Routine name</label><input id="routine-name" onChange={(event) => setName(event.target.value)} required value={name} /><label htmlFor="routine-skill">Active skill</label><select id="routine-skill" onChange={(event) => setSkillId(event.target.value)} required value={skillId}><option value="">Select a skill</option>{activeSkills.map((skill) => <option key={skill.id} value={skill.id}>{skill.name} v{skill.version}</option>)}</select><button className="button" disabled={busy || activeSkills.length === 0} type="submit">Create routine</button></form>;
}

function RecordList({ empty, items }: { empty: string; items: { id: string; primary: string; secondary: string }[] }) {
  if (items.length === 0) return <p className="quiet-copy">{empty}</p>;
  return <div className="record-list">{items.map((item) => <div className="record-row" key={item.id}><div><strong>{item.primary}</strong><small>{item.secondary}</small></div></div>)}</div>;
}

function Inspector({
  artifacts,
  budget,
  conversation,
  effects,
  item,
  onApprove,
  onClose,
  onReject,
  onUpdateBudget
}: {
  artifacts: Artifact[];
  budget: Budget | null;
  conversation: ConversationEntry[];
  effects: Effect[];
  item: WorkItem | null;
  onApprove: (effectId: string) => Promise<void>;
  onClose: () => void;
  onReject: (effectId: string) => Promise<void>;
  onUpdateBudget: (limitUnits: number) => Promise<void>;
}) {
  const effect = effects.find((candidate) => candidate.work_item_id === item?.id) ?? null;
  useEffect(() => {
    if (item === null) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [item, onClose]);

  return (
    <aside
      aria-label="Work item details"
      aria-modal={item ? true : undefined}
      className={`inspector ${item ? "inspector--open" : ""}`}
      data-source-refs="vercel-com-2 lucide-activity"
      role={item ? "dialog" : undefined}
    >
      <div className="inspector-heading">
        <span><ActivityIcon /> Inspector</span>
        {item && <button className="text-button" onClick={onClose} type="button">Close</button>}
      </div>
      {!item ? <p className="inspector-empty">Select a work item to inspect its durable state.</p> : (
        <div className="inspector-content">
          <p className="eyebrow">{item.key}</p>
          <h2>{item.title}</h2>
          <Definition label="State" value={item.status.replace("_", " ")} />
          <Definition label="Attempts" value={String(item.attempt_count)} />
          <Definition label="Cost" value={`${item.cost_units} units`} />
          {effect && (
            <section className="inspector-section">
              <h3>Effect</h3>
              <Definition label="Target" value={effect.binding.target} />
              <Definition label="Status" value={effect.status.replace("_", " ")} />
              {effect.status === "pending_approval" && <div className="row-actions"><button className="button" onClick={() => onReject(effect.id)} type="button">Reject</button><button className="button button--primary" data-component-source="shadcn-button" onClick={() => onApprove(effect.id)} type="button">Approve effect</button></div>}
            </section>
          )}
          {budget && (
            <section className="inspector-section">
              <h3>Budget</h3>
              <Definition label="Limit" value={String(budget.limit_units)} />
              <Definition label="Settled" value={String(budget.settled_units)} />
              <Definition label="Reserved" value={String(budget.reserved_units)} />
              <BudgetEditor current={budget.limit_units} onUpdate={onUpdateBudget} />
            </section>
          )}
          <section className="inspector-section">
            <h3>Artifacts</h3>
            <p>{artifacts.filter((artifact) => artifact.work_item_id === item.id).length} attached</p>
          </section>
          <section className="inspector-section">
            <h3>Conversation</h3>
            {conversation.filter((entry) => entry.work_item_id === item.id).length === 0 ? <p className="quiet-copy">No entries for this item.</p> : conversation.filter((entry) => entry.work_item_id === item.id).map((entry) => <p className="conversation-entry" key={entry.id}><strong>{entry.role}</strong>{entry.content}</p>)}
          </section>
        </div>
      )}
    </aside>
  );
}

function BudgetEditor({
  current,
  onUpdate
}: {
  current: number;
  onUpdate: (limitUnits: number) => Promise<void>;
}) {
  const [value, setValue] = useState(String(current));

  useEffect(() => setValue(String(current)), [current]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onUpdate(Number(value));
  }

  return (
    <form className="compact-form" onSubmit={submit}>
      <label htmlFor="budget-limit">Budget limit</label>
      <div className="inline-control"><input id="budget-limit" min="0" onChange={(event) => setValue(event.target.value)} required type="number" value={value} /><button className="button" type="submit">Update</button></div>
    </form>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return <div className="definition"><dt>{label}</dt><dd>{value}</dd></div>;
}

function messageFor(reason: unknown): string {
  return reason instanceof Error ? reason.message.replaceAll("_", " ") : "Request failed";
}
