import { useEffect, useRef, type ReactNode } from "react";

import type { WorkspacePreference } from "./preferences";
import type { WorkspaceProfile } from "./workspaceProfiles";
import { ConnectionBanner } from "../components/ConnectionBanner";
import { NavigationRail } from "../components/NavigationRail";
import { ResponsiveNavigation } from "../components/ResponsiveNavigation";

interface AppShellProps {
  activeRoute: string;
  children: ReactNode;
  error: string;
  inspector: ReactNode;
  inspectorOpen: boolean;
  onChangeSetup: () => void;
  onNavigate: (routeId: string) => void;
  onPreferenceChange: (preference: WorkspacePreference) => void;
  preference: WorkspacePreference;
  profile: WorkspaceProfile;
  projectContext: ReactNode;
}

export function AppShell({
  activeRoute,
  children,
  error,
  inspector,
  inspectorOpen,
  onChangeSetup,
  onNavigate,
  onPreferenceChange,
  preference,
  profile,
  projectContext
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
        data-experience={preference.experience}
        data-scope={preference.scope}
      >
        <NavigationRail
          activeRoute={activeRoute}
          onChangeSetup={onChangeSetup}
          onNavigate={onNavigate}
          onPreferenceChange={onPreferenceChange}
          preference={preference}
          profile={profile}
          projectContext={projectContext}
        />
        <header className="adaptive-topbar">
          <div>
            <span className="mobile-wordmark">Corvus</span>
            <strong>{profile.label}</strong>
          </div>
          <ConnectionBanner error={error} />
        </header>
        <main className="adaptive-main" id="main-content" ref={mainRef} tabIndex={-1}>{children}</main>
        <div
          className={`adaptive-inspector-slot${inspectorOpen ? " adaptive-inspector-slot--open" : ""}`}
        >
          {inspector}
        </div>
        <ResponsiveNavigation
          activeRoute={activeRoute}
          onChangeSetup={onChangeSetup}
          onNavigate={onNavigate}
          onPreferenceChange={onPreferenceChange}
          preference={preference}
          profile={profile}
        />
      </div>
    </>
  );
}
