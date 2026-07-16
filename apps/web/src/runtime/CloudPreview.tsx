import type { components } from "../generated/api";
import { CloudIcon } from "../icons";

interface CloudPreviewProps {
  authAvailable: boolean;
  experience: components["schemas"]["ExperienceKind"];
  onChangeSetup: () => void;
  onUseLocal: () => void;
  workspaceKind: components["schemas"]["WorkspaceKind"];
}

export function CloudPreview({
  authAvailable,
  experience,
  onChangeSetup,
  onUseLocal,
  workspaceKind
}: CloudPreviewProps) {
  return (
    <main className="cloud-preview-shell" id="main-content">
      <section className="cloud-preview-panel">
        <div className="preview-badge"><CloudIcon /> Cloud Preview</div>
        <p className="eyebrow">{experience} · {workspaceKind}</p>
        <h1>Corvus Cloud is in preview.</h1>
        <p className="cloud-preview-lede">
          Cloud workspaces run in isolated E2B environments and sync across your signed-in devices. No payment will be collected.
        </p>
        <div className="preview-route" aria-label="Cloud workspace lifecycle">
          <span>Google account</span><i aria-hidden="true" /><span>Corvus control plane</span><i aria-hidden="true" /><span>E2B workspace</span>
        </div>
        <section className="preview-plan" aria-labelledby="preview-plan-title">
          <div>
            <p className="eyebrow">Preview plan</p>
            <h2 id="preview-plan-title">Cloud plans are coming later</h2>
            <p>Not yet available. You can continue with a Local workspace today.</p>
          </div>
          <button className="button" disabled type="button">Billing not enabled</button>
        </section>
        {authAvailable ? (
          <button className="button button--primary" type="button">Sign in with Google</button>
        ) : (
          <p className="setup-notice" role="status">Cloud setup is not available in this build</p>
        )}
        <div className="cloud-preview-actions">
          <button className="button button--primary" onClick={onUseLocal} type="button">Use local workspace</button>
          <button className="text-button" onClick={onChangeSetup} type="button">Change workspace setup</button>
        </div>
      </section>
    </main>
  );
}
