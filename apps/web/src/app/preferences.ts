export const WORKSPACE_PREFERENCE_KEY = "corvus.workspace-preference";
export const WORKSPACE_PREFERENCE_VERSION = 1 as const;

export type ExperienceMode = "everyday" | "developer";
export type WorkspaceScope = "personal" | "team";
export type RuntimeMode = "local" | "corvus_cloud";

export interface WorkspacePreference {
  version: typeof WORKSPACE_PREFERENCE_VERSION;
  experience: ExperienceMode;
  scope: WorkspaceScope;
  runtime: RuntimeMode;
  workspaceId?: string;
  onboardingComplete: boolean;
}

export interface PreferenceLoadResult {
  preference: WorkspacePreference | null;
  recovered: boolean;
}

function isWorkspacePreference(value: unknown): value is WorkspacePreference {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.version === WORKSPACE_PREFERENCE_VERSION &&
    (candidate.experience === "everyday" || candidate.experience === "developer") &&
    (candidate.scope === "personal" || candidate.scope === "team") &&
    (candidate.runtime === "local" || candidate.runtime === "corvus_cloud") &&
    typeof candidate.onboardingComplete === "boolean" &&
    (candidate.workspaceId === undefined || typeof candidate.workspaceId === "string")
  );
}

export function loadWorkspacePreference(storage: Storage): PreferenceLoadResult {
  const serialized = storage.getItem(WORKSPACE_PREFERENCE_KEY);
  if (serialized === null) return { preference: null, recovered: false };

  try {
    const parsed: unknown = JSON.parse(serialized);
    if (isWorkspacePreference(parsed) && parsed.onboardingComplete) {
      return { preference: parsed, recovered: false };
    }
  } catch {
    // The invalid value is removed below so setup can recover deterministically.
  }

  storage.removeItem(WORKSPACE_PREFERENCE_KEY);
  return { preference: null, recovered: true };
}

export function saveWorkspacePreference(
  preference: WorkspacePreference,
  storage: Storage
): void {
  if (!isWorkspacePreference(preference) || !preference.onboardingComplete) {
    throw new Error("invalid_workspace_preference");
  }
  storage.setItem(WORKSPACE_PREFERENCE_KEY, JSON.stringify(preference));
}

export function clearWorkspacePreference(storage: Storage): void {
  storage.removeItem(WORKSPACE_PREFERENCE_KEY);
}
