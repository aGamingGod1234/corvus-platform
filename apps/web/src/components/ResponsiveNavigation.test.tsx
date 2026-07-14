import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { getWorkspaceProfile } from "../app/workspaceProfiles";
import { ResponsiveNavigation } from "./ResponsiveNavigation";

describe("ResponsiveNavigation", () => {
  it("keeps workspace controls available when a profile has no overflow routes", async () => {
    const onPreferenceChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ResponsiveNavigation
        activeRoute="home"
        onChangeSetup={vi.fn()}
        onNavigate={vi.fn()}
        onPreferenceChange={onPreferenceChange}
        preference={{
          version: 1,
          experience: "everyday",
          scope: "personal",
          runtime: "local",
          onboardingComplete: true
        }}
        profile={getWorkspaceProfile("everyday", "personal")}
      />
    );

    const menuSummary = screen.getByText("More");
    await user.click(menuSummary);
    expect(screen.getByRole("button", { name: "Change workspace setup" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Developer work style" }));

    expect(onPreferenceChange).toHaveBeenCalledWith(expect.objectContaining({ experience: "developer" }));
    expect(menuSummary.closest("details")).not.toHaveAttribute("open");
  });
});
