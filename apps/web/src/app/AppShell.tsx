import { useEffect, useRef, type ReactNode } from "react";

import type { components } from "../generated/api";
import { ConnectionBanner } from "../components/ConnectionBanner";
import { NavigationRail } from "../components/NavigationRail";
import { ResponsiveNavigation } from "../components/ResponsiveNavigation";
import type { WorkspaceProfile } from "./workspaceProfiles";

type Workspace = components["schemas"]["Workspace"];

interface AppShellProps {
  accountEmail: string;
  activeRoute: string;
  children: ReactNode;
  error: string;
  inspector: ReactNode;
  inspectorOpen: boolean;
  onNavigate(routeId: string): void;
  onWorkspaceSelect(workspaceId: string): void | Promise<void>;
  profile: WorkspaceProfile;
  projectContext: ReactNode;
  selectedWorkspace: Workspace;
  selectionRequired: boolean;
  workspaces: readonly Workspace[];
}

export function AppShell({
  accountEmail,
  activeRoute,
  children,
  error,
  inspector,
  inspectorOpen,
  onNavigate,
  onWorkspaceSelect,
  profile,
  projectContext,
  selectedWorkspace,
  selectionRequired,
  workspaces
}: AppShellProps) {
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    mainRef.current?.focus();
  }, [activeRoute]);

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div
        className="adaptive-shell"
        data-experience={profile.experience}
        data-scope={profile.workspaceKind}
      >
        <NavigationRail
          accountEmail={accountEmail}
          activeRoute={activeRoute}
          onNavigate={onNavigate}
          onWorkspaceSelect={onWorkspaceSelect}
          profile={profile}
          projectContext={projectContext}
          selectedWorkspace={selectedWorkspace}
          selectionRequired={selectionRequired}
          workspaces={workspaces}
        />
        <header className="adaptive-topbar">
          <div><span className="mobile-wordmark">Corvus</span><strong>{profile.label}</strong></div>
          <ConnectionBanner error={error} />
        </header>
        <main className="adaptive-main" id="main-content" ref={mainRef} tabIndex={-1}>{children}</main>
        <div className={`adaptive-inspector-slot${inspectorOpen ? " adaptive-inspector-slot--open" : ""}`}>{inspector}</div>
        <ResponsiveNavigation
          accountEmail={accountEmail}
          activeRoute={activeRoute}
          onNavigate={onNavigate}
          onWorkspaceSelect={onWorkspaceSelect}
          profile={profile}
          selectedWorkspace={selectedWorkspace}
          selectionRequired={selectionRequired}
          workspaces={workspaces}
        />
      </div>
    </>
  );
}
