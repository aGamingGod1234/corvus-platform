import { describe, expect, it } from "vitest";

import { getWorkspaceProfile } from "./workspaceProfiles";

describe("workspace profiles", () => {
  it.each([
    ["everyday", "personal", ["Home", "My Work", "Automations", "Files"]],
    ["developer", "personal", ["Repositories", "Threads", "Changes", "Runs", "Skills"]],
    ["everyday", "team", ["Team Home", "Assigned Work", "Approvals", "Knowledge", "People"]],
    ["developer", "team", ["Repositories", "Work Queue", "Reviews", "Environments", "Policies"]]
  ] as const)("defines %s %s navigation", (experience, scope, labels) => {
    expect(getWorkspaceProfile(experience, scope).routes.map((route) => route.label)).toEqual(labels);
  });
});
