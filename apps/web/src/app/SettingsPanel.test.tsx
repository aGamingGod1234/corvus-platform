import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MemoryStorage } from "../test/memoryStorage";
import type { ConversationApi } from "./conversationApi";
import { loadDevicePreferences } from "./devicePreferences";
import { SettingsPanel } from "./SettingsPanel";

function settingsApi(): Pick<ConversationApi, "getPreferences" | "listProviders" | "updatePreferences"> {
  return {
    getPreferences: vi.fn().mockResolvedValue({
      version: 2,
      default_provider: "codex",
      default_model: "gpt-5.6-sol",
      default_effort: "high",
      default_mode: "build",
      mcp_enabled: false,
      response_tone: "balanced",
      custom_rules: "",
      updated_at: "2026-07-17T10:00:00Z"
    }),
    listProviders: vi.fn().mockResolvedValue([{
      id: "codex",
      label: "Codex",
      status: "ready",
      runtime: "local",
      status_label: "Detected on this device",
      thinking_levels: ["low", "medium", "high", "xhigh"],
      supports_mcp: true,
      models: [{ id: "gpt-5.6-sol", label: "GPT-5.6 Sol", recommended: true }]
    }]),
    updatePreferences: vi.fn().mockImplementation(async (preferences) => ({
      ...preferences,
      version: preferences.expected_version + 1,
      updated_at: "2026-07-17T10:01:00Z"
    }))
  };
}

describe("SettingsPanel", () => {
  it("persists runtime guidance through the backend and appearance on this device", async () => {
    const storage = new MemoryStorage();
    const api = settingsApi();
    render(
      <SettingsPanel
        api={api}
        experience="everyday"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={storage}
        workspaceId="workspace-1"
        workspaceKind="team"
      />
    );
    const user = userEvent.setup();

    expect(screen.getByText("Everyday · Team")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Agent" }));
    await user.selectOptions(screen.getByLabelText("Response style"), "concise");
    await user.type(screen.getByLabelText("Custom rules"), "Always show the next action.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(api.updatePreferences).toHaveBeenCalledWith(expect.objectContaining({
      expected_version: 2,
      response_tone: "concise",
      custom_rules: "Always show the next action."
    })));
    expect(screen.getByText("Saved for this local runtime")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Appearance" }));
    await user.selectOptions(screen.getByLabelText("Theme"), "dark");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(loadDevicePreferences(storage, "workspace-1").theme).toBe("dark");
  });

  it("truthfully labels unavailable integrations", async () => {
    render(
      <SettingsPanel
        experience="developer"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={new MemoryStorage()}
        workspaceId="workspace-2"
        workspaceKind="individual"
      />
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Account" }));
    expect(screen.getByText("Web · Preview")).toBeVisible();
    expect(screen.getByText("Not connected")).toBeVisible();
  });

  it("explains the enforced local safety boundaries without offering a bypass", async () => {
    render(
      <SettingsPanel
        api={settingsApi()}
        experience="developer"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={new MemoryStorage()}
        workspaceId="workspace-safety"
        workspaceKind="individual"
      />
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Safety" }));
    expect(screen.getByText("Build confirmation")).toBeVisible();
    expect(screen.getByText("Always on in this alpha")).toBeVisible();
    expect(screen.getByText(/original project stays unchanged/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /full access/i })).not.toBeInTheDocument();
  });
});
