import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LocalRepository, LocalSafetyPreview, LocalSchedule } from "../api";
import { SchedulesWorkspace, type SchedulesApi } from "./SchedulesWorkspace";

const repository = { id: "repo-1", display_name: "Corvus" } as LocalRepository;
const schedule = { id: "schedule-1", name: "Weekday review", task: "Review changes", status: "active", version: 1, recurrence: { kind: "weekdays", local_time: "09:00:00", weekdays: [] }, next_run_at: "2026-07-20T09:00:00Z", mode: "chat", timezone: "UTC" } as unknown as LocalSchedule;

function api(): SchedulesApi {
  return {
    listRepositories: vi.fn().mockResolvedValue([repository]),
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
      repositoryId: repository.id, timezone: "UTC", recurrence: expect.objectContaining({ kind: "weekdays" })
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
