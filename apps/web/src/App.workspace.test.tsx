import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { CorvusApi } from "./api";
import { MemoryStorage } from "./test/memoryStorage";

const PROJECT = {
  id: "project-1",
  name: "Launch control",
  tenant_id: "local",
  created_at: "2026-07-14T00:00:00Z"
};

function bootstrapApi(): CorvusApi {
  return {
    session: vi.fn().mockRejectedValue(new Error("authentication_required")),
    pair: vi.fn().mockResolvedValue(undefined),
    listProjects: vi.fn().mockResolvedValue([])
  } as unknown as CorvusApi;
}

function readyApi(): CorvusApi {
  return {
    session: vi.fn().mockResolvedValue({
      csrf_token: "csrf",
      username: "operator",
      user_id: "operator-1",
      tenant_id: "local",
      expires_at: "2026-07-16T00:00:00Z"
    }),
    listProjects: vi.fn().mockResolvedValue([PROJECT]),
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

function seedPreference(
  storage: MemoryStorage,
  experience: "everyday" | "developer",
  scope: "personal" | "team"
) {
  storage.setItem(
    "corvus.workspace-preference",
    JSON.stringify({
      version: 1,
      experience,
      scope,
      runtime: "local",
      onboardingComplete: true
    })
  );
}

describe("adaptive Corvus bootstrap", () => {
  let preferenceStorage: MemoryStorage;

  beforeEach(() => {
    preferenceStorage = new MemoryStorage();
  });

  it("does not contact a workspace before the user chooses a runtime", async () => {
    const api = bootstrapApi();
    render(<App api={api} preferenceStorage={preferenceStorage} />);

    expect(await screen.findByRole("heading", { name: "How do you want Corvus to work with you?" })).toBeVisible();
    expect(api.session).not.toHaveBeenCalled();
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it("shows a truthful Cloud Preview without checkout or fake sign-in", async () => {
    const api = bootstrapApi();
    const user = userEvent.setup();
    render(<App api={api} preferenceStorage={preferenceStorage} />);

    await user.click(await screen.findByLabelText(/Developer — Repositories/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByLabelText(/My team — Assign work/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByLabelText(/Corvus Cloud \(E2B\)/));
    await user.click(screen.getByRole("button", { name: "Continue to Cloud Preview" }));

    expect(await screen.findByRole("heading", { name: "Corvus Cloud is in preview." })).toBeVisible();
    expect(screen.getByText("Cloud setup is not available in this build")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Sign in with Google" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Billing not enabled" })).toBeDisabled();
    expect(screen.queryByLabelText(/card/i)).not.toBeInTheDocument();
    expect(api.session).not.toHaveBeenCalled();
  });

  it("starts Local only after setup is complete", async () => {
    const api = bootstrapApi();
    const user = userEvent.setup();
    render(<App api={api} preferenceStorage={preferenceStorage} />);

    await user.click(await screen.findByLabelText(/Everyday — Clear plans/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByLabelText(/Just me — Private work/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByLabelText(/On this computer/));
    await user.click(screen.getByRole("button", { name: "Use this computer" }));

    await waitFor(() => expect(api.session).toHaveBeenCalledTimes(1));
    expect(await screen.findByLabelText("One-time pairing value")).toBeVisible();
  });

  it("renders profile-specific navigation and preserves the active project while switching", async () => {
    const api = readyApi();
    const user = userEvent.setup();
    seedPreference(preferenceStorage, "everyday", "personal");
    render(<App api={api} preferenceStorage={preferenceStorage} />);

    expect(await screen.findByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "My Work" })).toBeVisible();
    expect(screen.getByText("Local · Connected")).toBeVisible();
    expect(screen.getByRole("button", { name: /Launch control/ })).toBeVisible();

    await user.click(screen.getByRole("link", { name: "My Work" }));
    expect(screen.getByRole("main")).toHaveFocus();

    const desktopRail = within(screen.getByRole("complementary", { name: "Workspace navigation rail" }));
    await user.click(desktopRail.getByRole("button", { name: "Developer work style" }));
    expect(await screen.findByRole("link", { name: "Repositories" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Skills" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Launch control/ })).toBeVisible();

    await user.click(desktopRail.getByRole("button", { name: "Team workspace" }));
    expect(await screen.findByRole("link", { name: "Work Queue" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Policies" })).toBeVisible();
    expect(screen.getByText("Team features require a shared workspace capability.")).toBeVisible();
  });
});
