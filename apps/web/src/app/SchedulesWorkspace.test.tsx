import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LocalProviderCatalogEntry, LocalRepository, LocalSafetyPreview, LocalSchedule } from "../api";
import { SchedulesWorkspace, type SchedulesApi } from "./SchedulesWorkspace";

const repository = { id: "repo-1", display_name: "Corvus", snapshot: { health: "healthy" } } as LocalRepository;
const codex = {
  id: "codex", label: "OpenAI Codex", runtime: "local", status: "ready",
  status_label: "CLI and login verified",
  models: [{ id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true }],
  thinking_levels: ["low", "medium", "high", "xhigh"], supports_mcp: true
} as LocalProviderCatalogEntry;
const schedule = {
  id: "schedule-1", repository_id: repository.id, name: "Weekday review", task: "Review changes",
  status: "active", version: 1, recurrence: { kind: "weekdays", local_time: "09:00:00", weekdays: [] },
  next_run_at: "2026-07-20T09:00:00Z", model: "gpt-5.6-sol", effort: "high", mode: "build",
  output_policy: "prepare_changes", skill_version_id: null, timezone: "UTC"
} as unknown as LocalSchedule;

function api(): SchedulesApi {
  return {
    listRepositories: vi.fn().mockResolvedValue([repository]),
    listLocalProviders: vi.fn().mockResolvedValue([codex]),
    listPortableSkills: vi.fn().mockResolvedValue([]),
    getLocalSafetyPreview: vi.fn().mockResolvedValue({ policy_digest: "a".repeat(64) } as LocalSafetyPreview),
    listLocalSchedules: vi.fn().mockResolvedValue([]),
    createLocalSchedule: vi.fn().mockResolvedValue(schedule),
    runLocalScheduleNow: vi.fn(),
    pauseLocalSchedule: vi.fn(),
    resumeLocalSchedule: vi.fn(),
    archiveLocalSchedule: vi.fn()
  };
}

describe("SchedulesWorkspace", () => {
  it("creates a timezone-aware supervised schedule", async () => {
    const user = userEvent.setup();
    const client = api();
    render(<SchedulesWorkspace api={client} onOpenRun={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "New schedule" }));
    await user.type(screen.getByLabelText("Name"), "Weekday review");
    await user.type(screen.getByLabelText("Task"), "Review changes");
    await user.selectOptions(screen.getByLabelText("Cadence"), "weekdays");
    await user.clear(screen.getByLabelText("Timezone"));
    await user.type(screen.getByLabelText("Timezone"), "UTC");
    await user.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(client.createLocalSchedule).toHaveBeenCalledWith(expect.objectContaining({
      repositoryId: repository.id,
      model: "gpt-5.6-sol",
      effort: "high",
      mode: "build",
      outputPolicy: "prepare_changes",
      timezone: "UTC",
      recurrence: expect.objectContaining({ kind: "weekdays" })
    })));
    expect(await screen.findByRole("heading", { name: "Weekday review" })).toBeVisible();
  });

  it("uses the backend Monday index for weekly schedules", async () => {
    const user = userEvent.setup();
    const client = api();
    render(<SchedulesWorkspace api={client} onOpenRun={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "New schedule" }));
    await user.type(screen.getByLabelText("Name"), "Monday review");
    await user.type(screen.getByLabelText("Task"), "Review every Monday");
    await user.selectOptions(screen.getByLabelText("Cadence"), "weekly");
    await user.click(screen.getByRole("button", { name: "Create schedule" }));

    await waitFor(() => expect(client.createLocalSchedule).toHaveBeenCalledWith(
      expect.objectContaining({ recurrence: expect.objectContaining({ weekdays: [0] }) })
    ));
  });
});
