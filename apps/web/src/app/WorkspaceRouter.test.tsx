import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { getWorkspaceProfile } from "./workspaceProfiles";
import { WorkspaceRouter } from "./WorkspaceRouter";

describe("WorkspaceRouter", () => {
  it("renders a truthful read-only settings placeholder", () => {
    render(
      <WorkspaceRouter
        activeRoute="settings"
        executionSurface={<div>Execution</div>}
        operationsSurface={<div>Operations</div>}
        profile={getWorkspaceProfile("developer", "individual")}
        projectName="Corvus"
      />
    );

    expect(screen.getByRole("heading", { name: "Workspace settings" })).toBeVisible();
    expect(screen.getByText(/editing is not available yet/i)).toBeVisible();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
