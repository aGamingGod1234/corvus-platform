import { describe, expect, it } from "vitest";

import { getWorkspaceDefaultRoute, getWorkspaceProfile } from "./workspaceProfiles";

describe("workspace profiles", () => {
  it.each([
    ["everyday", "individual", ["Conversations", "Schedule", "My Work", "Files", "Settings"]],
    ["developer", "individual", ["Repositories", "Runs", "Schedule", "Skills", "Threads", "Settings"]],
    ["everyday", "team", ["Conversations", "Schedule", "Assigned Work", "Approvals", "People", "Settings"]],
    ["developer", "team", ["Threads", "Repositories", "Runs", "Reviews", "Schedule", "Policies", "Settings"]]
  ] as const)("defines %s %s navigation", (experience, scope, labels) => {
    expect(getWorkspaceProfile(experience, scope).routes.map((route) => route.label)).toEqual(labels);
  });

  it("opens the new-thread surface even when Threads is lower in the navigation", () => {
    expect(getWorkspaceDefaultRoute(getWorkspaceProfile("developer", "individual"))).toBe("threads");
  });
});
