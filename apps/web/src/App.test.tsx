import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CorvusApi, Outcome, Project, Workflow } from "./api";
import type { PlatformApi } from "./auth/authApi";
import { PlatformApp } from "./PlatformApp";
import { MemoryStorage } from "./test/memoryStorage";

const PROJECT: Project = {
  id: "project-1",
  name: "Launch control",
  tenant_id: "local",
  created_at: "2026-07-14T00:00:00Z"
};
const OUTCOME: Outcome = {
  id: "outcome-1",
  project_id: PROJECT.id,
  version: 1,
  title: "Browser delivery",
  acceptance_criteria: ["No reconnect storm"],
  created_at: "2026-07-14T00:00:00Z"
};
const WORKFLOW: Workflow = {
  id: "workflow-1",
  outcome_id: OUTCOME.id,
  name: "Browser flow",
  status: "running",
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z"
};

function hostedApi(): PlatformApi {
  const workspace = {
    id: "33333333-3333-4333-8333-333333333333",
    name: "Local workspace",
    workspace_kind: "individual" as const,
    status: "active" as const,
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:00:00Z",
    version: 1
  };
  return {
    applySync: vi.fn().mockResolvedValue({ acknowledged_cursor: 0, results: [] }),
    createWorkspace: vi.fn(),
    getSession: vi.fn().mockResolvedValue({
      account_id: "11111111-1111-4111-8111-111111111111",
      principal_id: "22222222-2222-4222-8222-222222222222",
      email: "operator@example.com",
      experience_kind: "developer",
      account_version: 1,
      session_version: 1,
      csrf_token: "hosted-csrf"
    }),
    getSyncPage: vi.fn().mockResolvedValue({
      requested_cursor: 0,
      next_cursor: 0,
      high_watermark: 0,
      earliest_retained_sequence: 1,
      changes: [],
      has_more: false
    }),
    getWorkspace: vi.fn().mockResolvedValue(workspace),
    listWorkspaces: vi.fn().mockResolvedValue([workspace]),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    startGoogle: vi.fn(),
    updateOnboarding: vi.fn()
  };
}

function renderApp(api: CorvusApi, preferenceStorage: Storage) {
  return render(
    <PlatformApp
      hostedApi={hostedApi()}
      locationHostname="localhost"
      loopbackApi={api}
      preferenceStorage={preferenceStorage}
    />
  );
}

function fakeApi(projects: Project[] = []): CorvusApi {
  return {
    session: vi.fn().mockRejectedValue(new Error("authentication_required")),
    pair: vi.fn().mockResolvedValue(undefined),
    listProjects: vi.fn().mockResolvedValue(projects),
    createProject: vi.fn().mockResolvedValue(PROJECT),
    listOutcomes: vi.fn().mockResolvedValue([]),
    createOutcome: vi.fn(),
    listWorkflows: vi.fn().mockResolvedValue([]),
    createWorkflow: vi.fn(),
    getWorkflow: vi.fn(),
    listWorkItems: vi.fn().mockResolvedValue([]),
    listEffects: vi.fn().mockResolvedValue([]),
    getBudget: vi.fn(),
    setBudget: vi.fn(),
    listArtifacts: vi.fn().mockResolvedValue([]),
    listConversation: vi.fn().mockResolvedValue([]),
    startWorkflow: vi.fn(),
    pauseWorkflow: vi.fn(),
    resumeWorkflow: vi.fn(),
    cancelWorkflow: vi.fn(),
    setWorkflowKillSwitch: vi.fn(),
    runNext: vi.fn(),
    approveEffect: vi.fn(),
    rejectEffect: vi.fn(),
    listTeams: vi.fn().mockResolvedValue([]),
    createTeam: vi.fn().mockResolvedValue({
      id: "team-1",
      project_id: PROJECT.id,
      name: "Operators",
      created_at: "2026-07-14T00:00:00Z"
    }),
    listProviders: vi.fn().mockResolvedValue([]),
    createProvider: vi.fn(),
    evaluateAutonomy: vi.fn(),
    listMemories: vi.fn().mockResolvedValue([]),
    storeMemory: vi.fn().mockResolvedValue({
      id: "memory-1",
      project_id: PROJECT.id,
      scope: "project",
      version: 1,
      content: "Remember the durable boundary.",
      provenance: "user:operator-1",
      status: "active",
      created_at: "2026-07-14T00:00:00Z"
    }),
    retrieveMemory: vi.fn().mockResolvedValue([]),
    listSkills: vi.fn().mockResolvedValue([]),
    createSkill: vi.fn(),
    activateSkill: vi.fn(),
    listRoutines: vi.fn().mockResolvedValue([]),
    createRoutine: vi.fn(),
    runRoutine: vi.fn(),
    listOfflineIntents: vi.fn().mockResolvedValue([]),
    listChannelEvents: vi.fn().mockResolvedValue([])
  };
}

describe("Corvus operator console", () => {
  let preferenceStorage: MemoryStorage;

  beforeEach(() => {
    preferenceStorage = new MemoryStorage();
    preferenceStorage.setItem(
      "corvus.workspace-preference",
      JSON.stringify({
        version: 1,
        experience: "developer",
        scope: "personal",
        runtime: "local",
        onboardingComplete: true
      })
    );
  });

  it("pairs once and reveals the real project workspace", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn()
      .mockRejectedValueOnce(new Error("authentication_required"))
      .mockResolvedValue({
        csrf_token: "paired-csrf",
        username: "paired-operator",
        user_id: "operator-1",
        tenant_id: "local",
        expires_at: "2026-07-15T00:00:00Z"
      });
    const user = userEvent.setup();
    renderApp(api, preferenceStorage);

    await user.type(await screen.findByLabelText("One-time pairing value"), "ephemeral-pairing-value");
    await user.click(screen.getByRole("button", { name: "Pair this browser" }));

    expect(api.pair).toHaveBeenCalledWith("ephemeral-pairing-value");
    expect(api.session).toHaveBeenCalledTimes(2);
    expect(screen.getByText("paired-operator")).toBeVisible();
    expect(await screen.findByRole("button", { name: /Launch control/ })).toBeVisible();
    expect(screen.getByText("Define the next durable outcome.")).toBeVisible();
  });

  it("consumes an ephemeral desktop pairing fragment without rendering the secret", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn()
      .mockRejectedValueOnce(new Error("authentication_required"))
      .mockResolvedValue({
        csrf_token: "desktop-csrf",
        username: "desktop-operator",
        user_id: "operator-1",
        tenant_id: "local",
        expires_at: "2026-07-15T00:00:00Z"
      });
    window.history.replaceState(null, "", "/#pair=desktop-ephemeral-token");

    renderApp(api, preferenceStorage);

    await waitFor(() => expect(api.pair).toHaveBeenCalledWith("desktop-ephemeral-token"));
    expect(await screen.findByRole("button", { name: /Launch control/ })).toBeVisible();
    expect(screen.queryByDisplayValue("desktop-ephemeral-token")).not.toBeInTheDocument();
    expect(window.location.hash).toBe("");
  });

  it("creates a project through the injected application adapter", async () => {
    const api = fakeApi();
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    const user = userEvent.setup();
    renderApp(api, preferenceStorage);

    await user.click(await screen.findByRole("button", { name: "New project" }));
    await user.type(screen.getByLabelText("Project name"), "Launch control");
    await user.click(screen.getByRole("button", { name: "Create project" }));

    expect(api.createProject).toHaveBeenCalledWith("Launch control");
    expect(await screen.findByRole("button", { name: /Launch control/ })).toBeVisible();
  });

  it("creates an approval-bearing workflow with a reserved demo budget", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    api.setBudget = vi.fn().mockResolvedValue({
      project_id: PROJECT.id,
      limit_units: 10,
      reserved_units: 0,
      settled_units: 0
    });
    api.createOutcome = vi.fn().mockResolvedValue(OUTCOME);
    api.createWorkflow = vi.fn().mockResolvedValue(WORKFLOW);
    api.getWorkflow = vi.fn().mockResolvedValue(WORKFLOW);
    api.getBudget = vi.fn().mockResolvedValue({
      project_id: PROJECT.id,
      limit_units: 10,
      reserved_units: 0,
      settled_units: 0
    });
    const user = userEvent.setup();
    renderApp(api, preferenceStorage);

    await user.type(await screen.findByLabelText("Outcome"), "Browser delivery");
    await user.type(screen.getByLabelText("Acceptance criterion"), "Approval is explicit");
    await user.type(screen.getByLabelText("Workflow name"), "Governed flow");
    await user.click(screen.getByRole("button", { name: "Create workflow" }));

    expect(api.setBudget).toHaveBeenCalledWith(PROJECT.id, 10);
    expect(api.createWorkflow).toHaveBeenCalledWith(
      OUTCOME.id,
      "Governed flow",
      expect.arrayContaining([
        expect.objectContaining({ key: "deliver", requires_approval: true, cost_units: 2 })
      ])
    );
  });

  it("coalesces an SSE event burst without reopening the stream", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    api.listOutcomes = vi.fn().mockResolvedValue([OUTCOME]);
    api.listWorkflows = vi.fn().mockResolvedValue([WORKFLOW]);
    api.getWorkflow = vi.fn().mockResolvedValue(WORKFLOW);
    api.getBudget = vi.fn().mockResolvedValue({
      project_id: PROJECT.id,
      limit_units: 0,
      reserved_units: 0,
      settled_units: 0
    });

    const streams: FakeEventSource[] = [];
    class FakeEventSource {
      readonly listeners = new Map<string, EventListener[]>();
      onerror: (() => void) | null = null;

      constructor(readonly url: string) {
        streams.push(this);
      }

      addEventListener(type: string, listener: EventListener) {
        this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
      }

      close() {}

      emit(type: string) {
        this.listeners.get(type)?.forEach((listener) => listener(new Event(type)));
      }
    }
    vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);

    renderApp(api, preferenceStorage);
    await screen.findByText("Browser delivery");
    await waitFor(() => expect(streams).toHaveLength(1));
    streams[0].emit("work_item.running");
    streams[0].emit("work_item.succeeded");
    streams[0].emit("workflow.succeeded");

    await waitFor(() => expect(api.getWorkflow).toHaveBeenCalledTimes(2));
    expect(streams).toHaveLength(1);
    vi.unstubAllGlobals();
  });

  it("operates collaboration and governed memory through connected controls", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    const user = userEvent.setup();
    renderApp(api, preferenceStorage);

    await user.click(await screen.findByRole("link", { name: "Skills" }));
    await user.type(screen.getByLabelText("Team name"), "Operators");
    await user.click(screen.getByRole("button", { name: "Create team" }));
    expect(api.createTeam).toHaveBeenCalledWith(PROJECT.id, "Operators");
    expect(await screen.findByText("Operators")).toBeVisible();

    await user.type(screen.getByLabelText("Memory content"), "Remember the durable boundary.");
    await user.click(screen.getByRole("button", { name: "Store memory" }));
    expect(api.storeMemory).toHaveBeenCalledWith(
      PROJECT.id,
      "Remember the durable boundary."
    );
    expect(await screen.findByText("Remember the durable boundary.")).toBeVisible();
  });
});
