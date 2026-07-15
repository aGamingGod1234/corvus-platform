import type { WorkspacePreference } from "../app/preferences";
import { localWorkspaceUrl } from "./localRuntime";

interface LocalRuntimeLauncherProps {
  onChangeSetup: () => void;
  preference: WorkspacePreference;
}

export function LocalRuntimeLauncher({
  onChangeSetup,
  preference
}: LocalRuntimeLauncherProps) {
  return (
    <main className="local-launch-shell" id="main-content">
      <section className="local-launch-panel" aria-labelledby="local-launch-title">
        <div className="preview-badge">Local workspace</div>
        <p className="eyebrow">{preference.experience} · {preference.scope}</p>
        <h1 id="local-launch-title">Open Corvus on this computer.</h1>
        <p className="local-launch-lede">
          The hosted page never receives your local session or pairing value. Continue on the
          same-origin local page so Corvus can keep its cookie, CSRF, and authority boundaries
          intact.
        </p>
        <ol className="local-launch-steps">
          <li><span>1</span><p><strong>Start Corvus locally</strong><small>Run the desktop app or the documented local server command.</small></p></li>
          <li><span>2</span><p><strong>Open the workspace</strong><small>Your browser moves to the loopback-only Corvus service.</small></p></li>
          <li><span>3</span><p><strong>Pair once</strong><small>The one-time value stays on this computer.</small></p></li>
        </ol>
        <div className="cloud-preview-actions">
          <a className="button button--primary" href={localWorkspaceUrl()}>Open local Corvus</a>
          <button className="text-button" onClick={onChangeSetup} type="button">Change workspace setup</button>
        </div>
        <p className="local-launch-note">Requires Corvus to be running at 127.0.0.1:8080.</p>
      </section>
    </main>
  );
}
