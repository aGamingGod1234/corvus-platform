import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MemoryStorage } from "../test/memoryStorage";
import { ConversationApiError, type ConversationApi } from "./conversationApi";
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
    await user.click(await screen.findByRole("button", { name: "Save changes" }));

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

  it("uses the discovered model name instead of a vague provider default", async () => {
    const api = settingsApi();
    vi.mocked(api.getPreferences).mockResolvedValue({
      ...(await api.getPreferences()),
      default_model: null
    });
    render(
      <SettingsPanel
        api={api}
        experience="developer"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={new MemoryStorage()}
        workspaceId="workspace-model"
        workspaceKind="individual"
      />
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Models" }));
    expect(await screen.findByRole("option", { name: "GPT-5.6 Sol · Recommended" })).toBeVisible();
    expect(screen.getByLabelText("Default model")).toHaveValue("gpt-5.6-sol");
    expect(screen.queryByRole("option", { name: /provider default/i })).not.toBeInTheDocument();
  });

  it("explains the enforced local safety boundaries without offering a bypass", async () => {
    const storage = new MemoryStorage();
    render(
      <SettingsPanel
        api={settingsApi()}
        experience="developer"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={storage}
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

    await user.click(screen.getByRole("radio", { name: /Detailed safety guidance/i }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(loadDevicePreferences(storage, "workspace-safety").safetyGuidance).toBe("detailed");
  });

  it("persists the composer send-key behavior in General settings", async () => {
    const storage = new MemoryStorage();
    render(
      <SettingsPanel
        api={settingsApi()}
        experience="everyday"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={storage}
        workspaceId="workspace-keys"
        workspaceKind="individual"
      />
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("radio", { name: /Ctrl\+Enter sends/i }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(loadDevicePreferences(storage, "workspace-keys").sendKeyMode).toBe("ctrl-enter");
  });

  it("loads the current saved preferences when another session wins a save", async () => {
    const api = settingsApi();
    vi.mocked(api.updatePreferences).mockRejectedValue(new ConversationApiError(
      409,
      "preferences_version_conflict",
      null,
      {
        code: "preferences_version_conflict",
        current: {
          version: 4,
          default_provider: "codex",
          default_model: "gpt-5.6-sol",
          default_effort: "low",
          default_mode: "chat",
          mcp_enabled: false,
          response_tone: "concise",
          custom_rules: "Current saved rule.",
          updated_at: "2026-07-18T00:00:00Z"
        }
      }
    ));
    render(<SettingsPanel api={api} experience="developer" onExperienceChange={vi.fn()}
      storage={new MemoryStorage()} workspaceId="workspace-conflict" workspaceKind="individual" />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Agent" }));
    await user.selectOptions(await screen.findByLabelText("Response style"), "detailed");
    await user.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/current saved values are loaded/i);
    expect(screen.getByLabelText("Response style")).toHaveValue("concise");
    expect(screen.getByLabelText("Custom rules")).toHaveValue("Current saved rule.");
  });

  it("connects, verifies, replaces, and removes write-only provider credentials", async () => {
    const api = {
      ...settingsApi(),
      listProviderCredentials: vi.fn().mockResolvedValue([
        { provider: "openai", configured: false, source: "none" }
      ]),
      connectProviderCredential: vi.fn().mockResolvedValue(
        { provider: "openai", configured: true, source: "keyring" }
      ),
      verifyProviderCredential: vi.fn().mockResolvedValue(
        { provider: "openai", configured: true, verified: true, models: ["gpt-5.6-sol"] }
      ),
      removeProviderCredential: vi.fn().mockResolvedValue(
        { provider: "openai", configured: false, source: "none" }
      )
    } as unknown as ConversationApi;
    render(
      <SettingsPanel
        api={api}
        experience="developer"
        onExperienceChange={vi.fn().mockResolvedValue(undefined)}
        storage={new MemoryStorage()}
        workspaceId="workspace-provider"
        workspaceKind="individual"
      />
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Models" }));
    const credential = screen.getByLabelText("OpenAI API key");
    await user.type(credential, "sk-test-never-render-again");
    await user.click(screen.getByRole("button", { name: "Connect OpenAI" }));
    expect(api.connectProviderCredential).toHaveBeenCalledWith("openai", "sk-test-never-render-again");
    expect(credential).toHaveValue("");
    expect(screen.queryByDisplayValue("sk-test-never-render-again")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Verify OpenAI" }));
    expect(await screen.findByText("gpt-5.6-sol")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Remove OpenAI" }));
    expect(api.removeProviderCredential).toHaveBeenCalledWith("openai");
  });
});
