import type { ExperienceMode, WorkspaceKind } from "./preferences";

export interface WorkspaceRoute {
  id: string;
  label: string;
  description: string;
}

export interface WorkspaceProfile {
  experience: ExperienceMode;
  workspaceKind: WorkspaceKind;
  label: string;
  eyebrow: string;
  routes: readonly WorkspaceRoute[];
}

const SETTINGS_ROUTE: WorkspaceRoute = {
  id: "settings",
  label: "Settings",
  description: "Workspace profile and identity settings"
};

const PROFILES: Record<`${ExperienceMode}:${WorkspaceKind}`, WorkspaceProfile> = {
  "everyday:individual": {
    experience: "everyday",
    workspaceKind: "individual",
    label: "Everyday · Individual",
    eyebrow: "Your private workspace",
    routes: [
      { id: "threads", label: "Conversations", description: "Ask Corvus and follow the result" },
      { id: "schedule", label: "Schedule", description: "Create routines and run them now" },
      { id: "my-work", label: "My Work", description: "Goals, plans, progress, and results" },
      { id: "files", label: "Files", description: "Inputs, sources, and deliverables" },
      SETTINGS_ROUTE
    ]
  },
  "developer:individual": {
    experience: "developer",
    workspaceKind: "individual",
    label: "Developer · Individual",
    eyebrow: "Local engineering workspace",
    routes: [
      { id: "threads", label: "Threads", description: "Agent plans and execution context" },
      { id: "repositories", label: "Repositories", description: "Projects, branches, and worktrees" },
      { id: "runs", label: "Runs", description: "Workflows, logs, checks, and budgets" },
      { id: "schedule", label: "Schedule", description: "Authorized routines and manual runs" },
      { id: "skills", label: "Skills", description: "Versioned tools, memory, and routines" },
      SETTINGS_ROUTE
    ]
  },
  "everyday:team": {
    experience: "everyday",
    workspaceKind: "team",
    label: "Everyday · Team",
    eyebrow: "Shared work preview",
    routes: [
      { id: "threads", label: "Conversations", description: "Team-shaped conversations on this device" },
      { id: "schedule", label: "Schedule", description: "Shared routine presentation and run-now controls" },
      { id: "assigned-work", label: "Assigned Work", description: "Owners, due work, and handoffs" },
      { id: "approvals", label: "Approvals", description: "Decisions that need review" },
      { id: "people", label: "People", description: "Members, roles, and invitations" },
      SETTINGS_ROUTE
    ]
  },
  "developer:team": {
    experience: "developer",
    workspaceKind: "team",
    label: "Developer · Team",
    eyebrow: "Governed engineering preview",
    routes: [
      { id: "threads", label: "Threads", description: "Agent plans and local run context" },
      { id: "repositories", label: "Repositories", description: "Registered repositories and ownership" },
      { id: "runs", label: "Runs", description: "Run status, events, and budgets" },
      { id: "reviews", label: "Reviews", description: "Diffs, checks, comments, and approvals" },
      { id: "schedule", label: "Schedule", description: "Authorized routines and manual runs" },
      { id: "policies", label: "Policies", description: "Access, autonomy, budget, and retention" },
      SETTINGS_ROUTE
    ]
  }
};

export function getWorkspaceProfile(
  experience: ExperienceMode,
  workspaceKind: WorkspaceKind
): WorkspaceProfile {
  return PROFILES[`${experience}:${workspaceKind}`];
}
