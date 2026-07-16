import type { ReactNode } from "react";

import type { WorkspaceProfile } from "../app/workspaceProfiles";
import type { components } from "../generated/api";
import { WorkspaceIdentityBlock } from "./WorkspaceSwitcher";

type Workspace = components["schemas"]["Workspace"];

interface NavigationRailProps {
  accountEmail: string;
  activeRoute: string;
  onNavigate(routeId: string): void;
  onWorkspaceSelect(workspaceId: string): void | Promise<void>;
  profile: WorkspaceProfile;
  projectContext: ReactNode;
  selectedWorkspace: Workspace;
  selectionRequired?: boolean;
  workspaces: readonly Workspace[];
}

export function NavigationRail({
  accountEmail,
  activeRoute,
  onNavigate,
  onWorkspaceSelect,
  profile,
  projectContext,
  selectedWorkspace,
  selectionRequired = false,
  workspaces
}: NavigationRailProps) {
  return (
    <aside aria-label="Workspace navigation rail" className="adaptive-rail">
      <div className="adaptive-wordmark"><span aria-hidden="true">C</span><strong>Corvus</strong></div>
      <WorkspaceIdentityBlock
        accountEmail={accountEmail}
        experience={profile.experience}
        onWorkspaceSelect={onWorkspaceSelect}
        selectedWorkspace={selectedWorkspace}
        selectionRequired={selectionRequired}
        workspaces={workspaces}
      />
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
    </aside>
  );
}
