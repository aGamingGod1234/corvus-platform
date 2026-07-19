import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LocalProviderCatalogEntry, LocalRepository, LocalRun, LocalSafetyPreview, PortableSkill } from "../api";
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
  model: "gpt-5.6-sol",
  effort: "high",
  mode: "build",
  safety_digest: "b".repeat(64),
  skill_version_id: "skill-1",
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

const codex = {
  id: "codex",
  label: "OpenAI Codex",
  runtime: "local",
  status: "ready",
  status_label: "CLI and login verified",
  models: [
    { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true },
    { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", recommended: false }
  ],
  thinking_levels: ["low", "medium", "high", "xhigh"],
  supports_mcp: true
} as LocalProviderCatalogEntry;

const skill = {
  id: "skill-1",
  name: "safe-review",
  version: 1,
  status: "active"
} as PortableSkill;

function api(): RunsApi {
  return {
    listRepositories: vi.fn().mockResolvedValue([repository]),
    listLocalProviders: vi.fn().mockResolvedValue([codex]),
    listPortableSkills: vi.fn().mockResolvedValue([skill]),
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
    getContribution: vi.fn().mockRejectedValue(new Error("contribution_not_found")),
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
    await user.selectOptions(screen.getByLabelText("Model"), "gpt-5.6-terra");
    await user.selectOptions(screen.getByLabelText("Thinking"), "xhigh");
    await user.selectOptions(screen.getByLabelText("Skill"), "skill-1");
    await user.selectOptions(screen.getByLabelText("Output policy"), "prepare_changes");
    await user.click(screen.getByRole("button", { name: "Start supervised run" }));

    await waitFor(() => expect(client.startLocalRun).toHaveBeenCalledWith(expect.objectContaining({
      repositoryId: repository.id,
      task: "Add the demo feature",
      model: "gpt-5.6-terra",
      effort: "xhigh",
      skillVersionId: "skill-1",
      mode: "build",
      outputPolicy: "prepare_changes",
      safetyDigest: "b".repeat(64)
    })));
    expect(await screen.findByRole("heading", { name: "Add the demo feature" })).toBeVisible();
  });

  it("keeps runs disabled until provider discovery is verified and supports retry", async () => {
    const client = api();
    vi.mocked(client.listLocalProviders)
      .mockRejectedValueOnce(new Error("discovery failed"))
      .mockResolvedValueOnce([codex]);
    const user = userEvent.setup();
    render(<RunsWorkspace api={client} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/provider discovery failed/i);
    expect(screen.getByRole("button", { name: "New run" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Retry providers" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "New run" })).toBeEnabled());
    expect(client.listLocalProviders).toHaveBeenCalledTimes(2);
  });
});
