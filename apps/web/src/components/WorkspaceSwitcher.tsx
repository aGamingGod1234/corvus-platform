import type { WorkspacePreference } from "../app/preferences";

interface WorkspaceSwitcherProps {
  onChange: (preference: WorkspacePreference) => void;
  preference: WorkspacePreference;
}

export function WorkspaceSwitcher({ onChange, preference }: WorkspaceSwitcherProps) {
  return (
    <div className="workspace-switcher" data-component-source="shadcn-tabs">
      <div aria-label="Work style" className="segmented-control" role="group">
        <button
          aria-label="Everyday work style"
          aria-pressed={preference.experience === "everyday"}
          onClick={() => onChange({ ...preference, experience: "everyday" })}
          type="button"
        >
          Everyday
        </button>
        <button
          aria-label="Developer work style"
          aria-pressed={preference.experience === "developer"}
          onClick={() => onChange({ ...preference, experience: "developer" })}
          type="button"
        >
          Developer
        </button>
      </div>
      <div aria-label="Workspace scope" className="segmented-control" role="group">
        <button
          aria-label="Personal workspace"
          aria-pressed={preference.scope === "personal"}
          onClick={() => onChange({ ...preference, scope: "personal" })}
          type="button"
        >
          Personal
        </button>
        <button
          aria-label="Team workspace"
          aria-pressed={preference.scope === "team"}
          onClick={() => onChange({ ...preference, scope: "team" })}
          type="button"
        >
          Team
        </button>
      </div>
    </div>
  );
}
