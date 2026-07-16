import { describe, expect, it } from "vitest";

import { getWorkspaceProfile } from "./workspaceProfiles";

describe("workspace profiles", () => {
  it.each([
    ["everyday", "individual", ["Home", "My Work", "Automations", "Files", "Settings"]],
    ["developer", "individual", ["Repositories", "Threads", "Changes", "Runs", "Skills", "Settings"]],
    ["everyday", "team", ["Team Home", "Assigned Work", "Approvals", "Knowledge", "People", "Settings"]],
    ["developer", "team", ["Repositories", "Work Queue", "Reviews", "Environments", "Policies", "Settings"]]
  ] as const)("defines %s %s navigation", (experience, scope, labels) => {
    expect(getWorkspaceProfile(experience, scope).routes.map((route) => route.label)).toEqual(labels);
  });
});
