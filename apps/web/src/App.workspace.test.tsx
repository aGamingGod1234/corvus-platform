import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CorvusApi } from "./api";
import type { PlatformApi, Workspace } from "./auth/authApi";
import { PlatformApp } from "./PlatformApp";
import { MemoryStorage } from "./test/memoryStorage";

const WORKSPACES: Workspace[] = [
  {
    id: "33333333-3333-4333-8333-333333333333",
    name: "Field desk",
    workspace_kind: "individual",
    status: "active",
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:00:00Z",
    version: 1
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    name: "Operations",
    workspace_kind: "team",
    status: "active",
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:00:00Z",
    version: 1
  }
];

function hostedApi(
  workspaces: Workspace[],
  experienceKind: "everyday" | "developer" | null = "developer"
): PlatformApi {
  return {
    applySync: vi.fn().mockResolvedValue({ acknowledged_cursor: 0, results: [] }),
    createWorkspace: vi.fn(),
    getSession: vi.fn().mockResolvedValue({
      account_id: "11111111-1111-4111-8111-111111111111",
      principal_id: "22222222-2222-4222-8222-222222222222",
      email: "person@example.com",
      experience_kind: experienceKind,
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
    getWorkspace: vi.fn().mockImplementation(async (id: string) => workspaces.find((workspace) => workspace.id === id)!),
    listWorkspaces: vi.fn().mockResolvedValue(workspaces),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    startGoogle: vi.fn(),
    updateOnboarding: vi.fn()
  };
}

function readyLoopback(): CorvusApi {
  return {
    session: vi.fn().mockResolvedValue({
      csrf_token: "local-csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-18T00:00:00Z"
    }),
    listProjects: vi.fn().mockResolvedValue([]),
    listOutcomes: vi.fn().mockResolvedValue([]),
    listTeams: vi.fn().mockResolvedValue([]),
    listProviders: vi.fn().mockResolvedValue([]),
    listMemories: vi.fn().mockResolvedValue([]),
    listSkills: vi.fn().mockResolvedValue([]),
    listRoutines: vi.fn().mockResolvedValue([]),
    listOfflineIntents: vi.fn().mockResolvedValue([]),
    listChannelEvents: vi.fn().mockResolvedValue([])
  } as unknown as CorvusApi;
}

describe("adaptive Corvus bootstrap", () => {
  it("treats a legacy preference only as onboarding preselection", async () => {
    const storage = new MemoryStorage();
    storage.setItem("corvus.workspace-preference", JSON.stringify({
      version: 1,
      experience: "developer",
      scope: "team",
      runtime: "local",
      onboardingComplete: true
    }));
    const loopback = readyLoopback();

    render(
      <PlatformApp
        hostedApi={hostedApi([WORKSPACES[0]], null)}
        locationHostname="localhost"
        loopbackApi={loopback}
        preferenceStorage={storage}
      />
    );

    expect(await screen.findByRole("heading", { name: "How do you want Corvus to work with you?" })).toBeVisible();
    expect(screen.getByRole("radio", { name: /Developer/ })).toBeChecked();
    expect(loopback.session).not.toHaveBeenCalled();
  });

  it("hands hosted users to loopback without sending hosted authority to the local API", async () => {
    const loopback = readyLoopback();

    render(
      <PlatformApp
        hostedApi={hostedApi([WORKSPACES[0]])}
        locationHostname="corvus-platform.example"
        loopbackApi={loopback}
        preferenceStorage={new MemoryStorage()}
      />
    );

    expect(await screen.findByRole("heading", { name: "Open Corvus on this computer." })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open local Corvus" })).toHaveAttribute("href", "http://127.0.0.1:8080/");
    expect(screen.getByText(/hosted page never receives your local session/i)).toBeVisible();
    expect(loopback.session).not.toHaveBeenCalled();
  });

  it("keeps experience and scope read-only after explicit workspace selection", async () => {
    const user = userEvent.setup();
    const loopback = readyLoopback();

    render(
      <PlatformApp
        hostedApi={hostedApi(WORKSPACES)}
        locationHostname="localhost"
        loopbackApi={loopback}
        preferenceStorage={new MemoryStorage()}
      />
    );

    await user.click(await screen.findByRole("button", { name: /Field desk/ }));
    await waitFor(() => expect(loopback.session).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("link", { name: "Repositories" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /work style/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /team workspace/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Field desk").length).toBeGreaterThan(0);
  });
});
