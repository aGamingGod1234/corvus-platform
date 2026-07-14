import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OnboardingFlow } from "./OnboardingFlow";

describe("OnboardingFlow", () => {
  it("collects work style, scope, and same-machine Local runtime", async () => {
    const onComplete = vi.fn();
    const user = userEvent.setup();
    render(<OnboardingFlow onComplete={onComplete} />);

    expect(screen.getByRole("heading", { name: "How do you want Corvus to work with you?" })).toBeVisible();
    await user.click(screen.getByLabelText(/Everyday — Clear plans/));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "Who is this workspace for?" })).toHaveFocus();
    await user.click(screen.getByLabelText(/Just me — Private work/));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByText(/Corvus and your data stay on this device/)).toBeVisible();
    expect(screen.getByText(/Cloud Preview; billing comes later/)).toBeVisible();
    await user.click(screen.getByLabelText(/On this computer/));
    await user.click(screen.getByRole("button", { name: "Use this computer" }));

    expect(onComplete).toHaveBeenCalledWith({
      version: 1,
      experience: "everyday",
      scope: "personal",
      runtime: "local",
      onboardingComplete: true
    });
  });

  it("uses real radio semantics and supports arrow-key choice", async () => {
    const user = userEvent.setup();
    render(<OnboardingFlow onComplete={vi.fn()} />);

    const everyday = screen.getByRole("radio", { name: /Everyday/ });
    everyday.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("radio", { name: /Developer/ })).toBeChecked();
  });
});
