import { render, screen, waitFor, within } from "@testing-library/react";
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

  it("pairs once and reveals the repository workspace without a project rail", async () => {
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
    await user.click(await screen.findByRole("link", { name: "Repositories" }));

    expect(api.pair).toHaveBeenCalledWith("ephemeral-pairing-value");
    expect(api.session).toHaveBeenCalledTimes(2);
    expect(screen.getByText("paired-operator")).toBeVisible();
    expect(screen.getByText("Define the next durable outcome.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Launch control/ })).not.toBeInTheDocument();
  });

  it("uses one local left navigation and omits permanent secondary rails", async () => {
    const api = fakeApi([PROJECT]);
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    const { container } = renderApp(api, preferenceStorage);

    const sidebar = await screen.findByRole("complementary", { name: "Local workspace" });
    expect(sidebar).toContainElement(screen.getByRole("navigation", { name: "Local runtime navigation" }));
    expect(sidebar.querySelectorAll("nav svg[aria-hidden='true']")).toHaveLength(6);
    expect(container.querySelector(".project-rail")).toBeNull();
    expect(screen.queryByLabelText("Work item details")).not.toBeInTheDocument();
    expect(screen.getByText("Developer · Individual")).toBeVisible();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
    expect(container.querySelector("main#main-content")).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("main", { name: "Threads" })).toBeVisible();
    expect(container.querySelector(".local-topbar")).toBeNull();
  });

  it.each([
    ["everyday", "personal", ["Conversations", "Schedule", "My Work", "Files", "Settings"]],
    ["developer", "personal", ["Threads", "Repositories", "Runs", "Schedule", "Skills", "Settings"]],
    ["everyday", "team", ["Conversations", "Schedule", "Assigned Work", "Approvals", "People", "Settings"]],
    ["developer", "team", ["Threads", "Repositories", "Runs", "Reviews", "Schedule", "Policies", "Settings"]]
  ] as const)("provides accessible local routes for the %s %s profile", async (experience, scope, labels) => {
    preferenceStorage.setItem("corvus.workspace-preference", JSON.stringify({
      version: 1,
      experience,
      scope,
      runtime: "local",
      onboardingComplete: true
    }));
    const api = fakeApi([PROJECT]);
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    renderApp(api, preferenceStorage);
    const user = userEvent.setup();

    const navigation = await screen.findByRole("navigation", { name: "Local runtime navigation" });
    expect(screen.getByText(new RegExp(`${experience}.*${scope === "personal" ? "individual" : "team"}`, "i"))).toBeVisible();
    expect(within(navigation).getAllByRole("link").map((link) => link.textContent)).toEqual(labels);
    for (const label of labels) {
      await user.click(within(navigation).getByRole("link", { name: label }));
      expect(screen.getByRole("main", { name: label })).toBeVisible();
    }
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
    expect(await screen.findByRole("heading", { name: "What do you want to build?" })).toBeVisible();
    expect(screen.queryByDisplayValue("desktop-ephemeral-token")).not.toBeInTheDocument();
    expect(window.location.hash).toBe("");
  });

  it("does not expose project creation as a second local navigation rail", async () => {
    const api = fakeApi();
    api.session = vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-15T00:00:00Z"
    });
    const { container } = renderApp(api, preferenceStorage);

    await screen.findByRole("navigation", { name: "Local runtime navigation" });
    expect(screen.queryByRole("button", { name: "New project" })).not.toBeInTheDocument();
    expect(container.querySelector(".project-rail")).toBeNull();
    expect(api.createProject).not.toHaveBeenCalled();
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
    await user.click(await screen.findByRole("link", { name: "Repositories" }));

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

    const user = userEvent.setup();
    renderApp(api, preferenceStorage);
    await user.click(await screen.findByRole("link", { name: "Repositories" }));
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
