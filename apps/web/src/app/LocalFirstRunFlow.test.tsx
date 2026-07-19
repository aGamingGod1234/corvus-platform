import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocalFirstRunFlow } from "./LocalFirstRunFlow";

describe("LocalFirstRunFlow", () => {
  it("introduces Corvus before Google and profile setup", async () => {
    const onGoogleStart = vi.fn();
    const onComplete = vi.fn();
    const user = userEvent.setup();
    render(<LocalFirstRunFlow onComplete={onComplete} onGoogleStart={onGoogleStart} />);

    expect(screen.getByRole("heading", { name: "Welcome to Corvus" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Start setup" }));
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(onGoogleStart).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: /I finished signing in/ }));
    await user.click(screen.getByRole("radio", { name: "Everyday" }));
    await user.click(screen.getByRole("button", { name: "Open Corvus" }));
    expect(onComplete).toHaveBeenCalledWith("everyday", "individual");
  });
});
