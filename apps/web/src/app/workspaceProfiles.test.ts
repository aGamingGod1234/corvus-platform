import { describe, expect, it } from "vitest";

import { getWorkspaceProfile } from "./workspaceProfiles";

describe("workspace profiles", () => {
  it.each([
    ["everyday", "individual", ["Conversations", "Schedule", "My Work", "Files", "Settings"]],
    ["developer", "individual", ["Threads", "Repositories", "Runs", "Schedule", "Skills", "Settings"]],
    ["everyday", "team", ["Conversations", "Schedule", "Assigned Work", "Approvals", "People", "Settings"]],
    ["developer", "team", ["Threads", "Repositories", "Runs", "Reviews", "Schedule", "Policies", "Settings"]]
  ] as const)("defines %s %s navigation", (experience, scope, labels) => {
    expect(getWorkspaceProfile(experience, scope).routes.map((route) => route.label)).toEqual(labels);
  });
});
