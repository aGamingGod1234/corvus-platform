import type { ReactNode } from "react";

import type { WorkspaceProfile } from "./workspaceProfiles";

interface WorkspaceRouterProps {
  activeRoute: string;
  executionSurface: ReactNode;
  operationsSurface: ReactNode;
  profile: WorkspaceProfile;
  projectName: string | null;
}

const EXECUTION_ROUTES = new Set(["repositories", "threads", "changes", "runs", "my-work"]);
const OPERATIONS_ROUTES = new Set(["skills"]);

export function WorkspaceRouter({
  activeRoute,
  executionSurface,
  operationsSurface,
  profile,
  projectName
}: WorkspaceRouterProps) {
  const route = profile.routes.find((candidate) => candidate.id === activeRoute) ?? profile.routes[0];
  const teamNotice = profile.workspaceKind === "team" ? (
    <p className="capability-notice" role="status">
      <strong>Team features require a shared workspace capability.</strong>
      This profile previews the team information architecture without creating members or permissions.
    </p>
  ) : null;

  let surface: ReactNode;
  if (route.id === "settings") {
    surface = (
      <section className="workspace-landing">
        <p className="eyebrow">Workspace identity</p>
        <h1>Workspace settings</h1>
        <p className="workspace-lede">
          Profile editing is not available yet. Your current workspace identity remains read-only.
        </p>
      </section>
    );
  } else if (profile.workspaceKind === "individual" && OPERATIONS_ROUTES.has(route.id)) {
    surface = operationsSurface;
  } else if (profile.workspaceKind === "individual" && EXECUTION_ROUTES.has(route.id)) {
    surface = executionSurface;
  } else {
    surface = (
      <section className="workspace-landing">
        <p className="eyebrow">{profile.eyebrow}</p>
        <h1>{route.label}</h1>
        <p className="workspace-lede">{route.description}.</p>
        <div className="workspace-flightpath" aria-hidden="true"><span /><i /><span /><i /><span /></div>
        <div className="workspace-summary">
          <div><span>Workspace</span><strong>{projectName ?? "No project selected"}</strong></div>
          <div><span>Runtime</span><strong>On this computer</strong></div>
          <div><span>Next</span><strong>{profile.workspaceKind === "team" ? "Connect a shared workspace later" : "Choose a project to begin"}</strong></div>
        </div>
      </section>
    );
  }

  return <>{teamNotice}{surface}</>;
}
