import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  ConversationApi,
  ProviderCatalogEntry,
  ProviderCredentialId,
  ProviderCredentialStatus,
  ResponseTone,
  RuntimePreferences,
  ThinkingLevel
} from "./conversationApi";
import { ConversationApiError } from "./conversationApi";
import {
  loadDevicePreferences,
  saveDevicePreferences,
  type SafetyGuidance,
  type SendKeyMode,
  type ThemePreference
} from "./devicePreferences";
import type { ExperienceMode, WorkspaceKind } from "./preferences";

type SettingsCategory = "general" | "models" | "agent" | "mcp" | "safety" | "appearance" | "account";
type SettingsApi = Pick<ConversationApi, "getPreferences" | "listProviders" | "updatePreferences" | "listProviderCredentials" | "connectProviderCredential" | "verifyProviderCredential" | "removeProviderCredential">;

const API_PROVIDERS: ReadonlyArray<{ id: ProviderCredentialId; label: string; environment: string }> = [
  { id: "openai", label: "OpenAI", environment: "OPENAI_API_KEY" },
  { id: "anthropic", label: "Anthropic", environment: "ANTHROPIC_API_KEY" },
  { id: "gemini", label: "Gemini", environment: "GEMINI_API_KEY" },
  { id: "xai", label: "xAI", environment: "XAI_API_KEY" }
];

const THINKING_LABELS: Record<ThinkingLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  xhigh: "Extra high",
  max: "Max"
};

const CATEGORIES: ReadonlyArray<{ id: SettingsCategory; label: string }> = [
  { id: "general", label: "General" },
  { id: "models", label: "Models" },
  { id: "agent", label: "Agent" },
  { id: "mcp", label: "MCP" },
  { id: "safety", label: "Safety" },
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
  const [sendKeyMode, setSendKeyMode] = useState<SendKeyMode>(() => loadDevicePreferences(storage, workspaceId).sendKeyMode);
  const [safetyGuidance, setSafetyGuidance] = useState<SafetyGuidance>(() => loadDevicePreferences(storage, workspaceId).safetyGuidance);
  const [runtime, setRuntime] = useState<RuntimePreferences>(DEFAULT_RUNTIME_PREFERENCES);
  const [providers, setProviders] = useState<ProviderCatalogEntry[]>([]);
  const [credentials, setCredentials] = useState<ProviderCredentialStatus[]>([]);
  const [credentialDrafts, setCredentialDrafts] = useState<Partial<Record<ProviderCredentialId, string>>>({});
  const [verifiedModels, setVerifiedModels] = useState<Partial<Record<ProviderCredentialId, string[]>>>({});
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
  const selectedModels = selectedProvider?.models ?? [];
  const selectedThinkingLevels = selectedProvider?.thinking_levels ?? ["medium"];

  useEffect(() => {
    const device = loadDevicePreferences(storage, workspaceId);
    setTheme(device.theme);
    setSendKeyMode(device.sendKeyMode);
    setSafetyGuidance(device.safetyGuidance);
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
        const selected = catalog.find((provider) => provider.id === preferences.default_provider);
        const models = selected?.models ?? [];
        const defaultModel = models.some((model) => model.id === preferences.default_model)
          ? preferences.default_model
          : models[0]?.id ?? null;
        setRuntime({ ...preferences, default_model: defaultModel });
        setProviders(catalog);
      })
      .catch((reason) => {
        if (current) setError(safeError(reason));
      })
      .finally(() => {
        if (current) setBusy(false);
      });
    if (api.listProviderCredentials !== undefined) {
      void api.listProviderCredentials().then((statuses) => {
        if (current) setCredentials(statuses);
      }).catch(() => {
        if (current) setError("Provider credentials could not be checked. No key was read or exposed.");
      });
    }
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
    const thinkingLevels = provider?.thinking_levels ?? [];
    const models = provider?.models ?? [];
    const effort = thinkingLevels.includes("medium")
      ? "medium"
      : thinkingLevels[0] ?? "medium";
    setRuntime((current) => ({
      ...current,
      default_provider: providerId,
      default_model: models[0]?.id ?? null,
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
      customRules: runtime.custom_rules,
      sendKeyMode,
      safetyGuidance
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
      if (
        reason instanceof ConversationApiError
        && reason.status === 409
        && reason.code === "preferences_version_conflict"
        && reason.detail?.current !== undefined
      ) {
        setRuntime(reason.detail.current);
        setDirty(false);
        setError("Settings changed in another session. The current saved values are loaded for review.");
      } else {
        setError(safeError(reason));
      }
    } finally {
      setBusy(false);
    }
  }

  async function connectCredential(provider: ProviderCredentialId): Promise<void> {
    const credential = credentialDrafts[provider]?.trim() ?? "";
    if (credential === "" || api?.connectProviderCredential === undefined) return;
    setBusy(true);
    setError("");
    try {
      const saved = await api.connectProviderCredential(provider, credential);
      setCredentials((current) => [...current.filter((entry) => entry.provider !== provider), saved]);
      setCredentialDrafts((current) => ({ ...current, [provider]: "" }));
      setStatus("Credential stored in the operating system keyring");
    } catch (reason) {
      setError(safeError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function verifyCredential(provider: ProviderCredentialId): Promise<void> {
    if (api?.verifyProviderCredential === undefined) return;
    setBusy(true);
    setError("");
    try {
      const verified = await api.verifyProviderCredential(provider);
      setVerifiedModels((current) => ({ ...current, [provider]: verified.models }));
      setStatus("Provider verified with its authenticated model catalog");
    } catch (reason) {
      setError(safeError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function removeCredential(provider: ProviderCredentialId): Promise<void> {
    if (api?.removeProviderCredential === undefined) return;
    setBusy(true);
    setError("");
    try {
      const saved = await api.removeProviderCredential(provider);
      setCredentials((current) => [...current.filter((entry) => entry.provider !== provider), saved]);
      setVerifiedModels((current) => ({ ...current, [provider]: [] }));
      setStatus(saved.configured ? "Environment credential remains configured" : "Provider credential removed");
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
            <div className="settings-field"><span className="settings-field__label">Send messages</span><p>Adaptive sends single-line prompts with Enter and multiline prompts with Ctrl+Enter.</p><div className="segmented-choice" role="radiogroup" aria-label="Composer send keys"><label><input checked={sendKeyMode === "adaptive"} onChange={() => { setSendKeyMode("adaptive"); setDirty(true); }} type="radio" />Adaptive</label><label><input checked={sendKeyMode === "enter"} onChange={() => { setSendKeyMode("enter"); setDirty(true); }} type="radio" />Enter sends</label><label><input checked={sendKeyMode === "ctrl-enter"} onChange={() => { setSendKeyMode("ctrl-enter"); setDirty(true); }} type="radio" />Ctrl+Enter sends</label></div></div>
            <div className="settings-actions"><button className="button" disabled={!profileEditable || busy || profileExperience === experience} onClick={() => void saveProfile()} type="button">Save profile</button></div>
            {!profileEditable ? <p className="field-note">Profile changes are available after signing in on the web app.</p> : null}
          </> : null}

          {category === "models" ? <>
            <div className="settings-section__heading"><h2>Models</h2><p>Defaults used when a new conversation opens.</p></div>
            <SettingsRow description="Only detected local providers can run." label="Provider"><select aria-label="Default provider" disabled={busy || providers.length === 0} onChange={(event) => updateProvider(event.target.value as "codex" | "claude")} value={runtime.default_provider}>{providers.length === 0 ? <option value={runtime.default_provider}>{title(runtime.default_provider)}</option> : providers.filter((entry) => entry.id === "codex" || entry.id === "claude").map((entry) => <option disabled={entry.status !== "ready"} key={entry.id} value={entry.id}>{entry.label} · {entry.status_label}</option>)}</select></SettingsRow>
            <SettingsRow description="Recommended models appear first in the composer." label="Model"><select aria-label="Default model" disabled={busy || selectedModels.length === 0} onChange={(event) => updateRuntime("default_model", event.target.value)} value={runtime.default_model ?? ""}>{selectedModels.map((model) => <option key={model.id} value={model.id}>{model.label}{model.recommended ? " · Recommended" : ""}</option>)}</select></SettingsRow>
            <SettingsRow description="Higher levels spend more time reasoning." label="Thinking"><select aria-label="Default thinking" disabled={busy} onChange={(event) => updateRuntime("default_effort", event.target.value as ThinkingLevel)} value={runtime.default_effort}>{selectedThinkingLevels.map((effort) => <option key={effort} value={effort}>{THINKING_LABELS[effort]}</option>)}</select></SettingsRow>
            <SettingsRow description="Build runs work in an isolated project sandbox and return an artifact." label="Mode"><select aria-label="Default mode" disabled={busy} onChange={(event) => { const mode = event.target.value as "chat" | "build"; updateRuntime("default_mode", mode); if (mode === "chat") updateRuntime("mcp_enabled", false); }} value={runtime.default_mode}><option value="chat">Chat</option><option disabled={runtime.default_provider !== "codex"} value="build">Build</option></select></SettingsRow>
            <div className="provider-connections"><div className="settings-section__subheading"><h3>API providers</h3><p>Keys are write-only and remain in your operating system keyring. API providers are Chat-only until a verified sandbox adapter exists.</p></div>{API_PROVIDERS.map((provider) => { const credentialStatus = credentials.find((entry) => entry.provider === provider.id); const configured = credentialStatus?.configured ?? false; return <section className="provider-connection" key={provider.id}><div><strong>{provider.label}</strong><span>{configured ? `Connected via ${credentialStatus?.source}` : `Not connected · or set ${provider.environment}`}</span>{(verifiedModels[provider.id]?.length ?? 0) > 0 ? <small>{verifiedModels[provider.id]?.join(", ")}</small> : null}</div><label className="sr-only" htmlFor={`provider-key-${provider.id}`}>{provider.label} API key</label><input autoComplete="off" id={`provider-key-${provider.id}`} onChange={(event) => setCredentialDrafts((current) => ({ ...current, [provider.id]: event.target.value }))} placeholder={configured ? "Paste a replacement key" : "Paste API key"} type="password" value={credentialDrafts[provider.id] ?? ""} /><div className="provider-connection__actions"><button disabled={busy || (credentialDrafts[provider.id]?.trim() ?? "") === ""} onClick={() => void connectCredential(provider.id)} type="button">{configured ? `Replace ${provider.label}` : `Connect ${provider.label}`}</button>{configured ? <><button disabled={busy} onClick={() => void verifyCredential(provider.id)} type="button">Verify {provider.label}</button><button disabled={busy || credentialStatus?.source === "environment"} onClick={() => void removeCredential(provider.id)} title={credentialStatus?.source === "environment" ? `Remove ${provider.environment} from the environment` : undefined} type="button">Remove {provider.label}</button></> : null}</div></section>; })}</div>
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

          {category === "safety" ? <>
            <div className="settings-section__heading"><h2>Safety</h2><p>Enforced boundaries for local agent runs.</p></div>
            <SettingsRow description="Every Build is bound to the exact policy shown before it starts." label="Build confirmation"><span className="settings-value">Always on in this alpha</span></SettingsRow>
            <SettingsRow description="Build work uses a fresh scratch workspace; your original project stays unchanged." label="Workspace isolation"><span className="settings-value">Enforced by runtime</span></SettingsRow>
            <SettingsRow description="Network behavior follows the selected CLI sandbox policy. Corvus grants no separate permission." label="Network"><span className="settings-value">No additional grant</span></SettingsRow>
            <SettingsRow description="Stop remains available while a run is active and sends an owner-scoped cancellation." label="Emergency stop"><span className="settings-value">Available during every run</span></SettingsRow>
            <div className="settings-field"><span className="settings-field__label">Safety guidance</span><p>Choose how much evidence Corvus shows while it works. This never weakens confirmation, isolation, MCP warnings, or sandbox enforcement.</p><div className="segmented-choice" role="radiogroup" aria-label="Safety guidance"><label><input checked={safetyGuidance === "standard"} onChange={() => { setSafetyGuidance("standard"); setDirty(true); }} type="radio" />Standard safety guidance</label><label><input checked={safetyGuidance === "detailed"} onChange={() => { setSafetyGuidance("detailed"); setDirty(true); }} type="radio" />Detailed safety guidance</label></div></div>
            <p className="settings-callout">Completed Build runs include an owner-scoped receipt with the locked policy, observed activity, artifact hash, and screening result.</p>
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

          {category !== "account" ? <div className="settings-actions"><button className="button button--primary" disabled={busy || !dirty} onClick={() => void saveSettings()} type="button">{busy ? "Saving…" : "Save changes"}</button></div> : null}
          {status ? <p className="save-status" role="status">{status}</p> : null}
          {error ? <p className="settings-error" role="alert">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
