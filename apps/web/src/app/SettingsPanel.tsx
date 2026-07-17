import { useEffect, useState } from "react";

import {
  loadDevicePreferences,
  saveDevicePreferences,
  type DevicePreferences,
  type ResponseTone,
  type ThemePreference
} from "./devicePreferences";
import type { ExperienceMode, WorkspaceKind } from "./preferences";

function title(value: string): string {
  return value[0].toUpperCase() + value.slice(1);
}

export function SettingsPanel({
  experience,
  onExperienceChange,
  profileEditable = true,
  storage,
  workspaceId,
  workspaceKind
}: {
  experience: ExperienceMode;
  onExperienceChange(experience: ExperienceMode): Promise<void>;
  profileEditable?: boolean;
  storage: Storage;
  workspaceId: string;
  workspaceKind: WorkspaceKind;
}) {
  const [preferences, setPreferences] = useState<DevicePreferences>(() => loadDevicePreferences(storage, workspaceId));
  const [profileExperience, setProfileExperience] = useState<ExperienceMode>(experience);
  const [saved, setSaved] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const profileLabel = `${title(experience)} · ${title(workspaceKind)}`;

  useEffect(() => {
    setPreferences(loadDevicePreferences(storage, workspaceId));
    setSaved(false);
  }, [storage, workspaceId]);

  function update<Key extends keyof DevicePreferences>(key: Key, value: DevicePreferences[Key]): void {
    setPreferences((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function saveProfile(): Promise<void> {
    setBusy(true);
    setProfileSaved(false);
    try {
      await onExperienceChange(profileExperience);
      setProfileSaved(true);
    } finally {
      setBusy(false);
    }
  }

  function saveDevice(): void {
    saveDevicePreferences(storage, workspaceId, preferences);
    document.documentElement.dataset.theme = preferences.theme;
    setSaved(true);
  }

  return (
    <section className="settings-workspace">
      <header className="settings-heading">
        <p className="eyebrow">Settings</p>
        <h1>Make Corvus work your way.</h1>
        <p>Profile changes sync with your account. Appearance and agent guidance stay on this device.</p>
      </header>

      <div className="settings-grid">
        <section className="settings-card settings-card--profile">
          <div className="section-heading"><h2>Profile</h2><span>Account</span></div>
          <div className="profile-lockup"><span>Current setup</span><strong>{profileLabel}</strong></div>
          <label htmlFor="settings-experience">How Corvus speaks to you</label>
          <select
            id="settings-experience"
            onChange={(event) => setProfileExperience(event.target.value as ExperienceMode)}
            value={profileExperience}
          >
            <option value="everyday">Everyday</option>
            <option value="developer">Developer</option>
          </select>
          <label htmlFor="settings-workspace-kind">Workspace type</label>
          <select disabled id="settings-workspace-kind" value={workspaceKind}>
            <option value="individual">Individual</option><option value="team">Team</option>
          </select>
          <p className="field-note">Workspace type is fixed for this workspace. Create or choose another authorized workspace to switch.</p>
          <button className="button" disabled={!profileEditable || busy || profileExperience === experience} onClick={() => void saveProfile()} type="button">Save profile</button>
          {!profileEditable ? <p className="field-note">Sign in on the web app to change the synced profile for this local runtime.</p> : null}
          {profileSaved ? <p className="save-status" role="status">Profile saved to your account</p> : null}
        </section>

        <section className="settings-card">
          <div className="section-heading"><h2>Appearance</h2><span>This device</span></div>
          <label htmlFor="settings-theme">Theme</label>
          <select id="settings-theme" onChange={(event) => update("theme", event.target.value as ThemePreference)} value={preferences.theme}>
            <option value="system">Use system setting</option><option value="light">Light</option><option value="dark">Dark</option>
          </select>
          <label htmlFor="settings-tone">Response tone</label>
          <select id="settings-tone" onChange={(event) => update("responseTone", event.target.value as ResponseTone)} value={preferences.responseTone}>
            <option value="concise">Concise</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option>
          </select>
        </section>

        <section className="settings-card settings-card--wide">
          <div className="section-heading"><h2>Agent guidance</h2><span>This device</span></div>
          <label htmlFor="settings-rules">Custom rules</label>
          <textarea id="settings-rules" onChange={(event) => update("customRules", event.target.value)} placeholder="Example: Always show the next action." rows={5} value={preferences.customRules} />
          <p className="field-note">These notes shape the local experience only. They are not authority or approval policy.</p>
          <button className="button button--primary" onClick={saveDevice} type="button">Save device settings</button>
          {saved ? <p className="save-status" role="status">Saved on this device</p> : null}
        </section>

        <section className="settings-card">
          <div className="section-heading"><h2>MCP servers</h2><span>Build mode</span></div>
          <p>Your configured Codex MCP servers are available in Build mode when you explicitly enable MCP tools. MCP servers may access external systems, so leave them off for ordinary chats.</p>
          <label htmlFor="settings-mcp-notes">Server notes</label>
          <textarea id="settings-mcp-notes" onChange={(event) => update("mcpNotes", event.target.value)} placeholder="Keep setup notes on this device" rows={3} value={preferences.mcpNotes} />
        </section>

        <section className="settings-card">
          <div className="section-heading"><h2>Integrations</h2><span>Coming soon</span></div>
          <ul className="integration-list"><li><strong>GitHub</strong><span>Not connected</span></li><li><strong>Google Drive</strong><span>Not connected</span></li><li><strong>Slack</strong><span>Not connected</span></li></ul>
          <p className="field-note">No integration receives data until a real connection and approval flow is available.</p>
        </section>
      </div>
    </section>
  );
}
