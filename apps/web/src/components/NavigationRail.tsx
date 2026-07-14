import type { ReactNode } from "react";

import type { WorkspaceProfile } from "../app/workspaceProfiles";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import type { WorkspacePreference } from "../app/preferences";

interface NavigationRailProps {
  activeRoute: string;
  onChangeSetup: () => void;
  onNavigate: (routeId: string) => void;
  onPreferenceChange: (preference: WorkspacePreference) => void;
  preference: WorkspacePreference;
  profile: WorkspaceProfile;
  projectContext: ReactNode;
}

export function NavigationRail({
  activeRoute,
  onChangeSetup,
  onNavigate,
  onPreferenceChange,
  preference,
  profile,
  projectContext
}: NavigationRailProps) {
  return (
    <aside aria-label="Workspace navigation rail" className="adaptive-rail">
      <div className="adaptive-wordmark"><span aria-hidden="true">C</span><strong>Corvus</strong></div>
      <WorkspaceSwitcher onChange={onPreferenceChange} preference={preference} />
      <div className="profile-caption">
        <span>{profile.eyebrow}</span>
        <strong>{profile.label}</strong>
      </div>
      <nav aria-label={`${profile.label} navigation`} className="profile-navigation">
        {profile.routes.map((route, index) => (
          <a
            aria-current={activeRoute === route.id ? "page" : undefined}
            href={`#${route.id}`}
            key={route.id}
            onClick={(event) => {
              event.preventDefault();
              onNavigate(route.id);
            }}
            title={route.description}
          >
            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            {route.label}
          </a>
        ))}
      </nav>
      {projectContext}
      <button className="change-setup-button" onClick={onChangeSetup} type="button">Change workspace setup</button>
    </aside>
  );
}
