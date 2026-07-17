import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  ConversationApi,
  ProviderCatalogEntry,
  ResponseTone,
  RuntimePreferences,
  ThinkingLevel
} from "./conversationApi";
import {
  loadDevicePreferences,
  saveDevicePreferences,
  type ThemePreference
} from "./devicePreferences";
import type { ExperienceMode, WorkspaceKind } from "./preferences";

type SettingsCategory = "general" | "models" | "agent" | "mcp" | "appearance" | "account";
type SettingsApi = Pick<ConversationApi, "getPreferences" | "listProviders" | "updatePreferences">;

const CATEGORIES: ReadonlyArray<{ id: SettingsCategory; label: string }> = [
  { id: "general", label: "General" },
  { id: "models", label: "Models" },
  { id: "agent", label: "Agent" },
  { id: "mcp", label: "MCP" },
  { id: "appearance", label: "Appearance" },
  { id: "account", label: "Account" }
];

const DEFAULT_RUNTIME_PREFERENCES: RuntimePreferences = {
  version: 0,
  default_provider: "codex",
  default_model: null,
  default_effort: "medium",
  default_mode: "chat",
  mcp_enabled: false,
  response_tone: "balanced",
  custom_rules: "",
  updated_at: null
};

function title(value: string): string {
  return value[0].toUpperCase() + value.slice(1);
}

function safeError(reason: unknown): string {
  return reason instanceof Error
    ? reason.message.replaceAll("_", " ")
    : "Corvus could not save these settings.";
}

function SettingsRow({ children, description, label }: {
  children: ReactNode;
  description: string;
  label: string;
}) {
  return (
    <div className="settings-row">
      <div><strong>{label}</strong><p>{description}</p></div>
      <div className="settings-row__control">{children}</div>
    </div>
  );
}

export function SettingsPanel({
  api,
  experience,
  onExperienceChange,
  profileEditable = true,
  storage,
  workspaceId,
  workspaceKind
}: {
  api?: SettingsApi;
  experience: ExperienceMode;
  onExperienceChange(experience: ExperienceMode): Promise<void>;
  profileEditable?: boolean;
  storage: Storage;
  workspaceId: string;
  workspaceKind: WorkspaceKind;
}) {
  const [category, setCategory] = useState<SettingsCategory>("general");
  const [theme, setTheme] = useState<ThemePreference>(() => loadDevicePreferences(storage, workspaceId).theme);
  const [runtime, setRuntime] = useState<RuntimePreferences>(DEFAULT_RUNTIME_PREFERENCES);
  const [providers, setProviders] = useState<ProviderCatalogEntry[]>([]);
  const [profileExperience, setProfileExperience] = useState<ExperienceMode>(experience);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const profileLabel = `${title(experience)} · ${title(workspaceKind)}`;
  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === runtime.default_provider),
    [providers, runtime.default_provider]
  );

  useEffect(() => {
    const device = loadDevicePreferences(storage, workspaceId);
    setTheme(device.theme);
    setProfileExperience(experience);
    setStatus("");
    setError("");
    if (api === undefined) {
      setRuntime({
        ...DEFAULT_RUNTIME_PREFERENCES,
        response_tone: device.responseTone,
        custom_rules: device.customRules
      });
      return;
    }
    let current = true;
    setBusy(true);
    void Promise.all([api.getPreferences(), api.listProviders()])
      .then(([preferences, catalog]) => {
        if (!current) return;
        setRuntime(preferences);
        setProviders(catalog);
      })
      .catch((reason) => {
        if (current) setError(safeError(reason));
      })
      .finally(() => {
        if (current) setBusy(false);
      });
    return () => { current = false; };
  }, [api, experience, storage, workspaceId]);

  function updateRuntime<Key extends keyof RuntimePreferences>(
    key: Key,
    value: RuntimePreferences[Key]
  ): void {
    setRuntime((current) => ({ ...current, [key]: value }));
    setDirty(true);
    setStatus("");
    setError("");
  }

  function updateProvider(providerId: "codex" | "claude"): void {
    const provider = providers.find((entry) => entry.id === providerId);
    const effort = provider?.thinking_levels.includes("medium")
      ? "medium"
      : provider?.thinking_levels[0] ?? "medium";
    setRuntime((current) => ({
      ...current,
      default_provider: providerId,
      default_model: provider?.models[0]?.id ?? null,
      default_effort: effort,
      default_mode: providerId === "codex" ? current.default_mode : "chat",
      mcp_enabled: providerId === "codex" ? current.mcp_enabled : false
    }));
    setDirty(true);
    setStatus("");
  }

  async function saveProfile(): Promise<void> {
    setBusy(true);
    setError("");
    try {
      await onExperienceChange(profileExperience);
      setStatus("Profile saved to your account");
    } catch (reason) {
      setError(safeError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(): Promise<void> {
    setBusy(true);
    setError("");
    setStatus("");
    const device = loadDevicePreferences(storage, workspaceId);
    saveDevicePreferences(storage, workspaceId, {
      ...device,
      theme,
      responseTone: runtime.response_tone,
      customRules: runtime.custom_rules
    });
    document.documentElement.dataset.theme = theme;
    try {
      if (api !== undefined) {
        const saved = await api.updatePreferences({
          expected_version: runtime.version,
          default_provider: runtime.default_provider,
          default_model: runtime.default_model,
          default_effort: runtime.default_effort,
          default_mode: runtime.default_mode,
          mcp_enabled: runtime.mcp_enabled,
          response_tone: runtime.response_tone,
          custom_rules: runtime.custom_rules
        });
        setRuntime(saved);
        setStatus("Saved for this local runtime");
      } else {
        setStatus("Saved on this device");
      }
      setDirty(false);
    } catch (reason) {
      setError(safeError(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settings-workspace">
      <header className="settings-heading">
        <h1>Settings</h1>
        <p>Control how Corvus looks, responds, and starts agent runs.</p>
      </header>
      <div className="settings-layout">
        <nav aria-label="Settings categories" className="settings-categories">
          {CATEGORIES.map((item) => (
            <button
              aria-current={category === item.id ? "page" : undefined}
              key={item.id}
              onClick={() => setCategory(item.id)}
              type="button"
            >{item.label}</button>
          ))}
        </nav>
        <div className="settings-section" data-category={category}>
          {category === "general" ? <>
            <div className="settings-section__heading"><h2>General</h2><p>Your workspace profile and language.</p></div>
            <SettingsRow description="Shown in the app header and used to tailor navigation." label="Current setup"><span className="settings-value">{profileLabel}</span></SettingsRow>
            <SettingsRow description="Switch between everyday and developer language." label="Experience">
              <select aria-label="Experience" onChange={(event) => setProfileExperience(event.target.value as ExperienceMode)} value={profileExperience}><option value="everyday">Everyday</option><option value="developer">Developer</option></select>
            </SettingsRow>
            <SettingsRow description="Workspace membership and authority stay attached to this workspace." label="Workspace type"><select aria-label="Workspace type" disabled value={workspaceKind}><option value="individual">Individual</option><option value="team">Team</option></select></SettingsRow>
            <div className="settings-actions"><button className="button" disabled={!profileEditable || busy || profileExperience === experience} onClick={() => void saveProfile()} type="button">Save profile</button></div>
            {!profileEditable ? <p className="field-note">Profile changes are available after signing in on the web app.</p> : null}
          </> : null}

          {category === "models" ? <>
            <div className="settings-section__heading"><h2>Models</h2><p>Defaults used when a new conversation opens.</p></div>
            <SettingsRow description="Only detected local providers can run." label="Provider"><select aria-label="Default provider" disabled={busy || providers.length === 0} onChange={(event) => updateProvider(event.target.value as "codex" | "claude")} value={runtime.default_provider}>{providers.length === 0 ? <option value={runtime.default_provider}>{title(runtime.default_provider)}</option> : providers.filter((entry) => entry.id === "codex" || entry.id === "claude").map((entry) => <option disabled={entry.status !== "ready"} key={entry.id} value={entry.id}>{entry.label} · {entry.status_label}</option>)}</select></SettingsRow>
            <SettingsRow description="Recommended models appear first in the composer." label="Model"><select aria-label="Default model" disabled={busy || (selectedProvider?.models.length ?? 0) === 0} onChange={(event) => updateRuntime("default_model", event.target.value || null)} value={runtime.default_model ?? ""}><option value="">Provider default</option>{selectedProvider?.models.map((model) => <option key={model.id} value={model.id}>{model.label}{model.recommended ? " · Recommended" : ""}</option>)}</select></SettingsRow>
            <SettingsRow description="Higher levels spend more time reasoning." label="Thinking"><select aria-label="Default thinking" disabled={busy} onChange={(event) => updateRuntime("default_effort", event.target.value as ThinkingLevel)} value={runtime.default_effort}>{(selectedProvider?.thinking_levels ?? ["medium"]).map((effort) => <option key={effort} value={effort}>{title(effort)}</option>)}</select></SettingsRow>
            <SettingsRow description="Build runs work in an isolated project sandbox and return an artifact." label="Mode"><select aria-label="Default mode" disabled={busy} onChange={(event) => { const mode = event.target.value as "chat" | "build"; updateRuntime("default_mode", mode); if (mode === "chat") updateRuntime("mcp_enabled", false); }} value={runtime.default_mode}><option value="chat">Chat</option><option disabled={runtime.default_provider !== "codex"} value="build">Build</option></select></SettingsRow>
          </> : null}

          {category === "agent" ? <>
            <div className="settings-section__heading"><h2>Agent</h2><p>Guidance applied by the backend to new runs.</p></div>
            <SettingsRow description="Choose the usual level of explanation." label="Response style"><select aria-label="Response style" onChange={(event) => updateRuntime("response_tone", event.target.value as ResponseTone)} value={runtime.response_tone}><option value="concise">Concise</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></SettingsRow>
            <div className="settings-field"><label htmlFor="settings-rules">Custom rules</label><p>Presentation guidance only. Rules cannot change sandbox, approval, credential, budget, or authority policy.</p><textarea id="settings-rules" maxLength={20_000} onChange={(event) => updateRuntime("custom_rules", event.target.value)} placeholder="Example: Always include a short verification checklist." rows={7} value={runtime.custom_rules} /></div>
          </> : null}

          {category === "mcp" ? <>
            <div className="settings-section__heading"><h2>MCP</h2><p>Let supported Build runs use MCP servers already configured in Codex.</p></div>
            <SettingsRow description="MCP tools may access external systems. Corvus keeps them off for ordinary chats." label="Enable by default"><label className="switch"><input aria-label="Enable MCP by default" checked={runtime.mcp_enabled} disabled={runtime.default_provider !== "codex" || runtime.default_mode !== "build"} onChange={(event) => updateRuntime("mcp_enabled", event.target.checked)} type="checkbox" /><span /></label></SettingsRow>
            <p className="settings-callout">Corvus does not store MCP credentials here. Configure servers through Codex, then explicitly enable them for a Build run.</p>
          </> : null}

          {category === "appearance" ? <>
            <div className="settings-section__heading"><h2>Appearance</h2><p>Visual preferences stay on this device.</p></div>
            <SettingsRow description="Follow your system or choose a fixed theme." label="Theme"><select aria-label="Theme" onChange={(event) => { setTheme(event.target.value as ThemePreference); setDirty(true); }} value={theme}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></SettingsRow>
          </> : null}

          {category === "account" ? <>
            <div className="settings-section__heading"><h2>Account</h2><p>Identity and connection status.</p></div>
            <SettingsRow description={api === undefined ? "Open the local app to run agents on this computer." : "Preferences are protected by this paired local session."} label="Runtime"><span className="settings-value">{api === undefined ? "Web · Preview" : "This computer · Connected"}</span></SettingsRow>
            <SettingsRow description="GitHub, Google Drive, and Slack connection flows are not enabled in this alpha." label="Integrations"><span className="settings-value">Not connected</span></SettingsRow>
          </> : null}

          {category !== "general" ? <div className="settings-actions"><button className="button button--primary" disabled={busy || !dirty} onClick={() => void saveSettings()} type="button">{busy ? "Saving…" : "Save changes"}</button></div> : null}
          {status ? <p className="save-status" role="status">{status}</p> : null}
          {error ? <p className="settings-error" role="alert">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
