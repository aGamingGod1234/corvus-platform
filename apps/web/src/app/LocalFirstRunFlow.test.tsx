import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocalFirstRunFlow } from "./LocalFirstRunFlow";

describe("LocalFirstRunFlow", () => {
  it("introduces Corvus before an explicitly local profile setup", async () => {
    const onComplete = vi.fn();
    const user = userEvent.setup();
    render(<LocalFirstRunFlow onComplete={onComplete} />);

    expect(screen.getByRole("heading", { name: "Welcome to Corvus" })).toBeVisible();
    expect(screen.getByText(/device-local identity/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Google/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start local setup" }));
    await user.click(screen.getByRole("radio", { name: "Everyday" }));
    await user.click(screen.getByRole("button", { name: "Open Corvus" }));
    expect(onComplete).toHaveBeenCalledWith("everyday", "individual");
  });
});
