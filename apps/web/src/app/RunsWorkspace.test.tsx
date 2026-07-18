import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LocalRepository, LocalRun, LocalSafetyPreview } from "../api";
import { RunsWorkspace, type RunsApi } from "./RunsWorkspace";

const repository = {
  id: "repo-1",
  tenant_id: "local",
  display_name: "Corvus",
  path: "C:\\work\\corvus",
  remote_slug: "team/corvus",
  default_branch: "main",
  created_at: "2026-07-18T00:00:00Z",
  updated_at: "2026-07-18T00:00:00Z",
  snapshot: { branch: "main", head_sha: "a".repeat(40), clean: true, ahead: 0, behind: 0, health: "healthy", refreshed_at: "2026-07-18T00:00:00Z" }
} as LocalRepository;

const run = {
  id: "run-1",
  tenant_id: "local",
  repository_id: repository.id,
  base_sha: "a".repeat(40),
  task: "Add the demo feature",
  provider: "codex",
  model: null,
  effort: "high",
  mode: "build",
  safety_digest: "b".repeat(64),
  skill_version_id: null,
  schedule_id: null,
  occurrence_key: null,
  output_policy: "prepare_contribution",
  retry_of_run_id: null,
  status: "running",
  created_at: "2026-07-18T00:00:00Z",
  updated_at: "2026-07-18T00:00:00Z",
  started_at: "2026-07-18T00:00:00Z",
  finished_at: null
} as LocalRun;

function api(): RunsApi {
  return {
    listRepositories: vi.fn().mockResolvedValue([repository]),
    getLocalSafetyPreview: vi.fn().mockResolvedValue({ policy_digest: "b".repeat(64) } as LocalSafetyPreview),
    listLocalRuns: vi.fn().mockResolvedValue([]),
    startLocalRun: vi.fn().mockResolvedValue(run),
    getLocalRun: vi.fn().mockResolvedValue(run),
    listLocalRunEvents: vi.fn().mockResolvedValue([]),
    listLocalRunEvidence: vi.fn().mockResolvedValue([]),
    cancelLocalRun: vi.fn().mockResolvedValue({ ...run, status: "cancelled" }),
    retryLocalRun: vi.fn(),
    discardLocalRun: vi.fn(),
    getRunChanges: vi.fn(),
    getContribution: vi.fn(),
    prepareContribution: vi.fn(),
    publishContribution: vi.fn()
  };
}

describe("RunsWorkspace", () => {
  it("starts a real supervised repository run", async () => {
    const user = userEvent.setup();
    const client = api();
    render(<RunsWorkspace api={client} />);

    await user.click(await screen.findByRole("button", { name: "New run" }));
    await user.type(screen.getByLabelText("Task"), "Add the demo feature");
    await user.click(screen.getByRole("button", { name: "Start supervised run" }));

    await waitFor(() => expect(client.startLocalRun).toHaveBeenCalledWith(expect.objectContaining({
      repositoryId: repository.id,
      task: "Add the demo feature",
      mode: "build",
      safetyDigest: "b".repeat(64)
    })));
    expect(await screen.findByRole("heading", { name: "Add the demo feature" })).toBeVisible();
  });
});
