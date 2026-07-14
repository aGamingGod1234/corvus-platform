import type { ExperienceMode, WorkspaceScope } from "./preferences";

export interface WorkspaceRoute {
  id: string;
  label: string;
  description: string;
}

export interface WorkspaceProfile {
  experience: ExperienceMode;
  scope: WorkspaceScope;
  label: string;
  eyebrow: string;
  routes: readonly WorkspaceRoute[];
}

const PROFILES: Record<`${ExperienceMode}:${WorkspaceScope}`, WorkspaceProfile> = {
  "everyday:personal": {
    experience: "everyday",
    scope: "personal",
    label: "Everyday · Personal",
    eyebrow: "Your private workspace",
    routes: [
      { id: "home", label: "Home", description: "Today, recent outcomes, and next steps" },
      { id: "my-work", label: "My Work", description: "Goals, plans, progress, and results" },
      { id: "automations", label: "Automations", description: "Scheduled and repeatable work" },
      { id: "files", label: "Files", description: "Inputs, sources, and deliverables" }
    ]
  },
  "developer:personal": {
    experience: "developer",
    scope: "personal",
    label: "Developer · Personal",
    eyebrow: "Local engineering workspace",
    routes: [
      { id: "repositories", label: "Repositories", description: "Projects, branches, and worktrees" },
      { id: "threads", label: "Threads", description: "Agent plans and execution context" },
      { id: "changes", label: "Changes", description: "Files, diffs, and artifacts" },
      { id: "runs", label: "Runs", description: "Workflows, logs, checks, and budgets" },
      { id: "skills", label: "Skills", description: "Versioned tools, memory, and routines" }
    ]
  },
  "everyday:team": {
    experience: "everyday",
    scope: "team",
    label: "Everyday · Team",
    eyebrow: "Shared work preview",
    routes: [
      { id: "team-home", label: "Team Home", description: "Shared outcomes and team activity" },
      { id: "assigned-work", label: "Assigned Work", description: "Owners, due work, and handoffs" },
      { id: "approvals", label: "Approvals", description: "Decisions that need review" },
      { id: "knowledge", label: "Knowledge", description: "Shared sources and decisions" },
      { id: "people", label: "People", description: "Members, roles, and invitations" }
    ]
  },
  "developer:team": {
    experience: "developer",
    scope: "team",
    label: "Developer · Team",
    eyebrow: "Governed engineering preview",
    routes: [
      { id: "repositories", label: "Repositories", description: "Registered repositories and ownership" },
      { id: "work-queue", label: "Work Queue", description: "Assignments, dependencies, and runs" },
      { id: "reviews", label: "Reviews", description: "Diffs, checks, comments, and approvals" },
      { id: "environments", label: "Environments", description: "Runtime readiness without secrets" },
      { id: "policies", label: "Policies", description: "Access, autonomy, budget, and retention" }
    ]
  }
};

export function getWorkspaceProfile(
  experience: ExperienceMode,
  scope: WorkspaceScope
): WorkspaceProfile {
  return PROFILES[`${experience}:${scope}`];
}
