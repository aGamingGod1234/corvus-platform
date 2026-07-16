import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { AuthApiError, type PlatformApi, type SessionResponse } from "../auth/authApi";
import type { components } from "../generated/api";
import {
  emptySyncLedger,
  reduceSyncPage,
  SyncProvider,
  SyncIntegrityError
  ,useWorkspaceSync
} from "./SyncProvider";

type SyncPage = components["schemas"]["SyncPage"];
type WorkspaceChange = components["schemas"]["WorkspaceChange"];

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111";
const PRINCIPAL_ID = "22222222-2222-4222-8222-222222222222";
const WORKSPACE_ID = "33333333-3333-4333-8333-333333333333";
const DEVICE_ID = "44444444-4444-4444-8444-444444444444";
const ZERO_DIGEST = "0".repeat(64);
const SESSION: SessionResponse = {
  account_id: ACCOUNT_ID,
  principal_id: PRINCIPAL_ID,
  email: "person@example.com",
  experience_kind: "developer",
  account_version: 2,
  session_version: 1,
  csrf_token: "csrf-opaque"
};
const WORKSPACE: components["schemas"]["Workspace"] = {
  id: WORKSPACE_ID,
  name: "Corvus field desk",
  workspace_kind: "individual",
  status: "active",
  created_at: "2026-07-17T00:00:00Z",
  updated_at: "2026-07-17T00:00:00Z",
  version: 1
};

function change(
  sequence: number,
  digestMarker: string,
  overrides: Partial<WorkspaceChange> = {}
): WorkspaceChange {
  const accountChange = sequence === 1;
  return {
    workspace_id: WORKSPACE_ID,
    workspace_version: 1,
    sequence,
    previous_digest: sequence === 1 ? ZERO_DIGEST : "1".repeat(64),
    change_digest: digestMarker.repeat(64),
    kind: accountChange ? "account_profile" : "workspace_profile",
    operation: accountChange ? "set_experience" : "update",
    entity_id: accountChange ? ACCOUNT_ID : WORKSPACE_ID,
    entity_version: accountChange ? 2 : 3,
    payload: accountChange
      ? { entity_id: ACCOUNT_ID, experience_kind: "developer", version: 2 }
      : {
          entity_id: WORKSPACE_ID,
          name: "Corvus field desk",
          workspace_kind: "individual",
          status: "active",
          version: 3
        },
    account_id: ACCOUNT_ID,
    principal_id: PRINCIPAL_ID,
    membership_version: 1,
    device_id: DEVICE_ID,
    device_version: 1,
    created_at: `2026-07-17T00:00:0${sequence}Z`,
    ...overrides
  };
}

function page(changes: WorkspaceChange[], overrides: Partial<SyncPage> = {}): SyncPage {
  const next = changes.at(-1)?.sequence ?? 0;
  return {
    requested_cursor: 0,
    next_cursor: next,
    high_watermark: next,
    earliest_retained_sequence: 1,
    changes,
    has_more: false,
    ...overrides
  };
}

function completeApi(overrides: Partial<PlatformApi> = {}): PlatformApi {
  return {
    applySync: vi.fn().mockResolvedValue({ acknowledged_cursor: 0, results: [] }),
    createWorkspace: vi.fn(),
    getSession: vi.fn().mockResolvedValue(SESSION),
    getSyncPage: vi.fn().mockResolvedValue(page([])),
    getWorkspace: vi.fn().mockResolvedValue(WORKSPACE),
    listWorkspaces: vi.fn().mockResolvedValue([WORKSPACE]),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    startGoogle: vi.fn(),
    updateOnboarding: vi.fn(),
    ...overrides
  };
}

function SyncProbe() {
  const sync = useWorkspaceSync();
  const [selectionOutcome, setSelectionOutcome] = useState("idle");
  return (
    <div>
      <output aria-label="sync status">{sync.status}</output>
      <output aria-label="selected workspace">{sync.selectedWorkspace?.name ?? "none"}</output>
      <output aria-label="sync cursor">{sync.cursor}</output>
      <output aria-label="mutation authority">{sync.canMutate ? "enabled" : "blocked"}</output>
      <output aria-label="conflict versions">
        {sync.conflict == null
          ? "none"
          : `${sync.conflict.submittedExpectedVersion}:${sync.conflict.currentVersion}`}
      </output>
      <output aria-label="selection outcome">{selectionOutcome}</output>
      <button
        onClick={() => {
          setSelectionOutcome("pending");
          void sync.selectWorkspace(WORKSPACE_ID).then(
            () => setSelectionOutcome("selected"),
            () => setSelectionOutcome("failed")
          );
        }}
        type="button"
      >Select field desk</button>
      <button onClick={() => void sync.refresh()} type="button">Refresh workspace</button>
      <button onClick={() => void sync.updateWorkspaceProfile("Renamed field desk")} type="button">Rename workspace</button>
    </div>
  );
}

function renderSync(api: PlatformApi) {
  return render(
    <AuthProvider api={api}>
      <SyncProvider api={api}>
        <SyncProbe />
      </SyncProvider>
    </AuthProvider>
  );
}

describe("ordered workspace synchronization", () => {
  it("requires onboarding before selecting an existing workspace when experience is unset", async () => {
    const getWorkspace = vi.fn().mockResolvedValue(WORKSPACE);
    renderSync(completeApi({
      getSession: vi.fn().mockResolvedValue({ ...SESSION, experience_kind: null }),
      getWorkspace
    }));

    await waitFor(() => {
      expect(screen.getByLabelText("sync status")).toHaveTextContent("onboarding_required");
    });
    expect(getWorkspace).not.toHaveBeenCalled();
  });

  it("reduces contiguous typed changes and advances the cursor monotonically", () => {
    const first = change(1, "1");
    const second = change(2, "2");

    const reduced = reduceSyncPage(
      emptySyncLedger(),
      page([first, second]),
      { accountId: ACCOUNT_ID, principalId: PRINCIPAL_ID, workspaceId: WORKSPACE_ID }
    );

    expect(reduced.cursor).toBe(2);
    expect(reduced.highWatermark).toBe(2);
    expect(reduced.accountProfile).toEqual(first.payload);
    expect(reduced.workspaceProfile).toEqual(second.payload);
    expect(reduced.digests.get(2)).toBe("2".repeat(64));
  });

  it("ignores an exact already-applied sequence and digest", () => {
    const first = change(1, "1");
    const initial = reduceSyncPage(
      emptySyncLedger(),
      page([first]),
      { accountId: ACCOUNT_ID, principalId: PRINCIPAL_ID, workspaceId: WORKSPACE_ID }
    );

    const duplicate = reduceSyncPage(
      initial,
      page([first], { requested_cursor: 1, next_cursor: 1, high_watermark: 1 }),
      { accountId: ACCOUNT_ID, principalId: PRINCIPAL_ID, workspaceId: WORKSPACE_ID }
    );

    expect(duplicate).toEqual(initial);
  });

  it.each([
    ["sync_gap_detected", [change(2, "2")]],
    ["sync_provenance_invalid", [change(1, "1", { principal_id: DEVICE_ID })]]
  ])("rejects %s without advancing last-good state", (code, changes) => {
    const initial = emptySyncLedger();
    expect(() =>
      reduceSyncPage(initial, page(changes), {
        accountId: ACCOUNT_ID,
        principalId: PRINCIPAL_ID,
        workspaceId: WORKSPACE_ID
      })
    ).toThrow(new SyncIntegrityError(code));
    expect(initial.cursor).toBe(0);
  });

  it("rejects a changed digest for an already-applied sequence", () => {
    const initial = reduceSyncPage(emptySyncLedger(), page([change(1, "1")]), {
      accountId: ACCOUNT_ID,
      principalId: PRINCIPAL_ID,
      workspaceId: WORKSPACE_ID
    });

    expect(() =>
      reduceSyncPage(
        initial,
        page([change(1, "9")], { requested_cursor: 1, next_cursor: 1, high_watermark: 1 }),
        { accountId: ACCOUNT_ID, principalId: PRINCIPAL_ID, workspaceId: WORKSPACE_ID }
      )
    ).toThrow(new SyncIntegrityError("sync_digest_changed"));
  });

  it("rejects a changed previous digest before acknowledging the page", () => {
    const first = change(1, "1");
    const invalidSecond = change(2, "2", { previous_digest: "8".repeat(64) });

    expect(() =>
      reduceSyncPage(emptySyncLedger(), page([first, invalidSecond]), {
        accountId: ACCOUNT_ID,
        principalId: PRINCIPAL_ID,
        workspaceId: WORKSPACE_ID
      })
    ).toThrow(new SyncIntegrityError("sync_digest_chain_invalid"));
  });
});

describe("SyncProvider", () => {
  it("auto-selects exactly one authorized workspace and acknowledges only reduced changes", async () => {
    const changes = [change(1, "1"), change(2, "2")];
    const applySync = vi.fn().mockResolvedValue({ acknowledged_cursor: 2, results: [] });
    const api = completeApi({
      applySync,
      getSyncPage: vi.fn().mockResolvedValue(page(changes))
    });

    renderSync(api);

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("Corvus field desk");
    expect(screen.getByLabelText("sync cursor")).toHaveTextContent("2");
    expect(applySync).toHaveBeenCalledWith(
      WORKSPACE_ID,
      { acknowledged_cursor: 2, mutations: [] },
      "csrf-opaque"
    );
  });

  it("requires explicit selection when multiple workspaces are authorized", async () => {
    const second = { ...WORKSPACE, id: DEVICE_ID, name: "Second workspace" };
    const getWorkspace = vi.fn().mockResolvedValue(WORKSPACE);
    const api = completeApi({
      getWorkspace,
      listWorkspaces: vi.fn().mockResolvedValue([WORKSPACE, second])
    });
    renderSync(api);

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("selection_required"));
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("none");
    expect(getWorkspace).not.toHaveBeenCalled();

    await userEvent.setup().click(screen.getByRole("button", { name: "Select field desk" }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));
    expect(getWorkspace).toHaveBeenCalledWith(WORKSPACE_ID);
  });

  it("rejects a failed explicit selection so the shell cannot announce success", async () => {
    const second = { ...WORKSPACE, id: DEVICE_ID, name: "Second workspace" };
    renderSync(completeApi({
      getWorkspace: vi.fn().mockRejectedValue(new AuthApiError(403, "membership_forbidden")),
      listWorkspaces: vi.fn().mockResolvedValue([WORKSPACE, second])
    }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("selection_required"));

    await userEvent.setup().click(screen.getByRole("button", { name: "Select field desk" }));

    await waitFor(() => expect(screen.getByLabelText("selection outcome")).toHaveTextContent("failed"));
    expect(screen.getByLabelText("sync status")).toHaveTextContent("forbidden");
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("none");
  });

  it("preserves last-good display while offline without claiming mutation authority", async () => {
    const getSyncPage = vi
      .fn()
      .mockResolvedValueOnce(page([]))
      .mockRejectedValueOnce(new AuthApiError(0, "network_unavailable"));
    renderSync(completeApi({ getSyncPage }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));

    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh workspace" }));

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("offline"));
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("Corvus field desk");
    expect(screen.getByLabelText("mutation authority")).toHaveTextContent("blocked");
  });

  it("invalidates mutation authority on 403 and requires explicit selection from a fresh list", async () => {
    const getSyncPage = vi
      .fn()
      .mockResolvedValueOnce(page([]))
      .mockRejectedValueOnce(new AuthApiError(403, "membership_forbidden"))
      .mockResolvedValueOnce(page([]));
    const listWorkspaces = vi.fn().mockResolvedValue([WORKSPACE]);
    renderSync(completeApi({ getSyncPage, listWorkspaces }));
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));

    await user.click(screen.getByRole("button", { name: "Refresh workspace" }));

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("forbidden"));
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("Corvus field desk");
    expect(screen.getByLabelText("mutation authority")).toHaveTextContent("blocked");
    expect(listWorkspaces).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "Select field desk" }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));
  });

  it("shows both submitted and current versions for an explicit sync conflict", async () => {
    const applySync = vi.fn().mockRejectedValue(
      new AuthApiError(409, "sync_version_conflict", "conflict-correlation", {
        code: "sync_version_conflict",
        mutation_index: 0,
        submitted_expected_version: 1,
        current_version: 3,
        current_profile: {
          entity_id: WORKSPACE_ID,
          name: "Current server name",
          workspace_kind: "individual",
          status: "active",
          version: 3
        }
      })
    );
    renderSync(completeApi({ applySync }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));

    await userEvent.setup().click(screen.getByRole("button", { name: "Rename workspace" }));

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("conflict"));
    expect(screen.getByLabelText("conflict versions")).toHaveTextContent("1:3");
    expect(screen.getByLabelText("selected workspace")).toHaveTextContent("Corvus field desk");
    expect(screen.getByLabelText("mutation authority")).toHaveTextContent("blocked");
  });

  it("performs explicit resync by refetching session and workspace before the boundary", async () => {
    const boundary = page([], {
      requested_cursor: 1,
      next_cursor: 1,
      high_watermark: 1,
      earliest_retained_sequence: 2
    });
    const getSyncPage = vi
      .fn()
      .mockResolvedValueOnce(page([]))
      .mockRejectedValueOnce(
        new AuthApiError(409, "sync_resync_required", "resync-correlation", {
          code: "sync_resync_required",
          earliest_available: 2,
          latest_sequence: 1,
          resume_cursor: 1,
          resources: ["/api/v2/session", `/api/v2/workspaces/${WORKSPACE_ID}`]
        })
      )
      .mockResolvedValueOnce(boundary);
    const getSession = vi.fn().mockResolvedValue(SESSION);
    const getWorkspace = vi.fn().mockResolvedValue(WORKSPACE);
    renderSync(completeApi({ getSession, getSyncPage, getWorkspace }));
    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));

    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh workspace" }));

    await waitFor(() => expect(screen.getByLabelText("sync status")).toHaveTextContent("ready"));
    expect(getSession).toHaveBeenCalledTimes(2);
    expect(getWorkspace).toHaveBeenCalledTimes(3);
    expect(getSyncPage).toHaveBeenLastCalledWith(WORKSPACE_ID, 1);
    expect(screen.getByLabelText("sync cursor")).toHaveTextContent("1");
  });
});
