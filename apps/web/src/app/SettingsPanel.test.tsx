import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MemoryStorage } from "../test/memoryStorage";
import { loadDevicePreferences } from "./devicePreferences";
import { SettingsPanel } from "./SettingsPanel";

describe("SettingsPanel", () => {
  it("saves clearly device-only appearance and agent guidance", async () => {
    const storage = new MemoryStorage();
    render(
      <SettingsPanel
        experience="everyday"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={storage}
        workspaceId="workspace-1"
        workspaceKind="team"
      />
    );
    const user = userEvent.setup();

    expect(screen.getByText("Everyday · Team")).toBeVisible();
    expect(screen.getAllByText("This device").length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Theme"), "dark");
    await user.selectOptions(screen.getByLabelText("Response tone"), "concise");
    await user.type(screen.getByLabelText("Custom rules"), "Always show the next action.");
    await user.click(screen.getByRole("button", { name: "Save device settings" }));

    expect(loadDevicePreferences(storage, "workspace-1")).toMatchObject({
      theme: "dark",
      responseTone: "concise",
      customRules: "Always show the next action."
    });
    expect(screen.getByText("Saved on this device")).toBeVisible();
    expect(screen.getByText(/configured Codex MCP servers are available in Build mode/i)).toBeVisible();
    expect(screen.getByText(/may access external systems/i)).toBeVisible();
  });
});
