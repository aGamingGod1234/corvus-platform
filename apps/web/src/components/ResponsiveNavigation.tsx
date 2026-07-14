import { useRef } from "react";

import type { WorkspaceProfile } from "../app/workspaceProfiles";
import type { WorkspacePreference } from "../app/preferences";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

interface ResponsiveNavigationProps {
  activeRoute: string;
  onChangeSetup: () => void;
  onNavigate: (routeId: string) => void;
  onPreferenceChange: (preference: WorkspacePreference) => void;
  preference: WorkspacePreference;
  profile: WorkspaceProfile;
}

const MOBILE_PRIMARY_COUNT = 4;

export function ResponsiveNavigation({
  activeRoute,
  onChangeSetup,
  onNavigate,
  onPreferenceChange,
  preference,
  profile
}: ResponsiveNavigationProps) {
  const menuRef = useRef<HTMLDetailsElement>(null);
  const primaryRoutes = profile.routes.slice(0, MOBILE_PRIMARY_COUNT);
  const remainingRoutes = profile.routes.slice(MOBILE_PRIMARY_COUNT);

  function closeMenu() {
    if (menuRef.current !== null) menuRef.current.open = false;
  }

  function navigate(routeId: string) {
    closeMenu();
    onNavigate(routeId);
  }

  function changePreference(nextPreference: WorkspacePreference) {
    closeMenu();
    onPreferenceChange(nextPreference);
  }

  function changeSetup() {
    closeMenu();
    onChangeSetup();
  }

  return (
    <nav aria-label="Mobile workspace navigation" className="responsive-navigation">
      {primaryRoutes.map((route) => (
        <a
          aria-label={`${route.label} mobile`}
          aria-current={activeRoute === route.id ? "page" : undefined}
          href={`#${route.id}`}
          key={route.id}
          onClick={(event) => {
            event.preventDefault();
            navigate(route.id);
          }}
        >
          {route.label}
        </a>
      ))}
      <details ref={menuRef}>
        <summary>More</summary>
        <div className="mobile-settings">
          {remainingRoutes.length > 0 && (
            <div className="mobile-settings__routes">
              {remainingRoutes.map((route) => (
                <button key={route.id} onClick={() => navigate(route.id)} type="button">
                  {route.label}
                </button>
              ))}
            </div>
          )}
          <WorkspaceSwitcher
            onChange={changePreference}
            preference={preference}
          />
          <button className="mobile-change-setup" onClick={changeSetup} type="button">
            Change workspace setup
          </button>
        </div>
      </details>
    </nav>
  );
}
