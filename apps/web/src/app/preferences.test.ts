import { beforeEach, describe, expect, it } from "vitest";

import {
  WORKSPACE_PREFERENCE_KEY,
  loadWorkspacePreference,
  saveWorkspacePreference,
  type WorkspacePreference
} from "./preferences";
import { MemoryStorage } from "../test/memoryStorage";

const PROFILES: WorkspacePreference[] = [
  { version: 1, experience: "everyday", scope: "personal", runtime: "local", onboardingComplete: true },
  { version: 1, experience: "developer", scope: "personal", runtime: "local", onboardingComplete: true },
  { version: 1, experience: "everyday", scope: "team", runtime: "local", onboardingComplete: true },
  { version: 1, experience: "developer", scope: "team", runtime: "corvus_cloud", onboardingComplete: true }
];

describe("workspace preferences", () => {
  let storage: MemoryStorage;

  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it.each(PROFILES)("round-trips $experience $scope", (preference) => {
    saveWorkspacePreference(preference, storage);
    expect(loadWorkspacePreference(storage)).toEqual({ preference, recovered: false });
  });

  it("removes invalid or unknown preferences instead of guessing", () => {
    storage.setItem(
      WORKSPACE_PREFERENCE_KEY,
      JSON.stringify({ version: 2, experience: "expert", scope: "shared", runtime: "remote" })
    );

    expect(loadWorkspacePreference(storage)).toEqual({ preference: null, recovered: true });
    expect(storage.getItem(WORKSPACE_PREFERENCE_KEY)).toBeNull();
  });
});
