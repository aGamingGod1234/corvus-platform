import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CorvusApi } from "./api";
import { AuthApiError, type PlatformApi, type Workspace } from "./auth/authApi";
import { PlatformApp } from "./PlatformApp";
import { MemoryStorage } from "./test/memoryStorage";

const SESSION = {
  account_id: "11111111-1111-4111-8111-111111111111",
  principal_id: "22222222-2222-4222-8222-222222222222",
  email: "person@example.com",
  experience_kind: "developer" as const,
  account_version: 1,
  session_version: 1,
  csrf_token: "csrf-opaque"
};
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

function platformApi(overrides: Partial<PlatformApi> = {}): PlatformApi {
  return {
    applySync: vi.fn().mockResolvedValue({ acknowledged_cursor: 0, results: [] }),
    createWorkspace: vi.fn(),
    getSession: vi.fn().mockResolvedValue(SESSION),
    getSyncPage: vi.fn().mockResolvedValue({
      requested_cursor: 0,
      next_cursor: 0,
      high_watermark: 0,
      earliest_retained_sequence: 1,
      changes: [],
      has_more: false
    }),
    getWorkspace: vi.fn().mockImplementation(async (id: string) => WORKSPACES.find((workspace) => workspace.id === id)!),
    listWorkspaces: vi.fn().mockResolvedValue(WORKSPACES),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    startGoogle: vi.fn(),
    updateOnboarding: vi.fn(),
    ...overrides
  };
}

describe("PlatformApp composition", () => {
  it("does not contact the loopback API before hosted authentication succeeds", async () => {
    const hostedApi = platformApi({
      getSession: vi.fn().mockRejectedValue(new AuthApiError(401, "session_required"))
    });
    const loopbackApi = { session: vi.fn() } as unknown as CorvusApi;

    render(<PlatformApp hostedApi={hostedApi} loopbackApi={loopbackApi} preferenceStorage={new MemoryStorage()} />);

    expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeVisible();
    expect(loopbackApi.session).not.toHaveBeenCalled();
    expect(hostedApi.listWorkspaces).not.toHaveBeenCalled();
  });

  it("requires explicit workspace selection before opening the selected local boundary", async () => {
    const hostedApi = platformApi();
    const loopbackApi = {
      session: vi.fn().mockRejectedValue(new Error("authentication_required"))
    } as unknown as CorvusApi;
    const user = userEvent.setup();

    render(
      <PlatformApp
        hostedApi={hostedApi}
        locationHostname="localhost"
        loopbackApi={loopbackApi}
        preferenceStorage={new MemoryStorage()}
      />
    );

    expect(await screen.findByRole("heading", { name: "Choose an authorized workspace" })).toBeVisible();
    expect(loopbackApi.session).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Field desk/ }));

    await waitFor(() => expect(loopbackApi.session).toHaveBeenCalledTimes(1));
    expect(await screen.findByLabelText("One-time pairing value")).toBeVisible();
  });
});
