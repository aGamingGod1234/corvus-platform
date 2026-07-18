import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LocalRepository } from "../api";
import { RepositoriesWorkspace, type RepositoryApi } from "./RepositoriesWorkspace";

const repository: LocalRepository = {
  id: "repository-1",
  tenant_id: "local",
  display_name: "Corvus",
  path: "C:\\work\\corvus",
  remote_slug: "team/corvus",
  default_branch: "main",
  created_at: "2026-07-18T00:00:00Z",
  updated_at: "2026-07-18T00:00:00Z",
  snapshot: {
    branch: "main",
    head_sha: "a".repeat(40),
    clean: true,
    ahead: 1,
    behind: 0,
    health: "healthy",
    refreshed_at: "2026-07-18T00:00:00Z"
  }
};

function apiWith(overrides: Partial<RepositoryApi> = {}): RepositoryApi {
  return {
    listRepositories: vi.fn().mockResolvedValue([]),
    registerRepository: vi.fn().mockResolvedValue(repository),
    refreshRepository: vi.fn().mockResolvedValue(repository),
    removeRepository: vi.fn().mockResolvedValue(undefined),
    ...overrides
  };
}

describe("RepositoriesWorkspace", () => {
  it("registers a folder selected by the desktop picker", async () => {
    const api = apiWith();
    const picker = vi.fn().mockResolvedValue("C:\\work\\corvus");
    render(<RepositoriesWorkspace api={api} pickDirectory={picker} />);
    const user = userEvent.setup();

    expect(await screen.findByText("No repositories connected")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Add local repository" }));
    await user.click(screen.getByRole("button", { name: "Browse" }));
    expect(screen.getByLabelText("Repository path")).toHaveValue("C:\\work\\corvus");
    expect(screen.getByLabelText("Display name")).toHaveValue("corvus");
    await user.click(screen.getByRole("button", { name: "Connect repository" }));

    expect(api.registerRepository).toHaveBeenCalledWith("C:\\work\\corvus", "corvus");
    expect(await screen.findByText("team/corvus")).toBeVisible();
  });

  it("keeps cancellation and validation honest", async () => {
    const api = apiWith();
    render(
      <RepositoriesWorkspace
        api={api}
        pickDirectory={vi.fn().mockResolvedValue(null)}
      />
    );
    const user = userEvent.setup();

    await screen.findByText("No repositories connected");
    await user.click(screen.getByRole("button", { name: "Add local repository" }));
    await user.click(screen.getByRole("button", { name: "Browse" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect repository" })).toBeDisabled();
  });

  it("shows real state and refreshes without optimistic status", async () => {
    const refreshing = { ...repository, snapshot: { ...repository.snapshot, clean: false } };
    const api = apiWith({
      listRepositories: vi.fn().mockResolvedValue([repository]),
      refreshRepository: vi.fn().mockResolvedValue(refreshing)
    });
    render(<RepositoriesWorkspace api={api} />);
    const user = userEvent.setup();

    expect(await screen.findByText("Clean")).toBeVisible();
    expect(screen.getByText(/1 ahead/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Refresh Corvus" }));
    await waitFor(() => expect(screen.getByText("Modified")).toBeVisible());
  });

  it("renders registration failures as errors", async () => {
    const api = apiWith({
      registerRepository: vi.fn().mockRejectedValue(new Error("not_a_git_repository"))
    });
    render(<RepositoriesWorkspace api={api} />);
    const user = userEvent.setup();

    await screen.findByText("No repositories connected");
    await user.click(screen.getByRole("button", { name: "Add local repository" }));
    await user.type(screen.getByLabelText("Repository path"), "C:\\plain");
    await user.type(screen.getByLabelText("Display name"), "Plain");
    await user.click(screen.getByRole("button", { name: "Connect repository" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("not_a_git_repository");
    expect(screen.queryByText("C:\\plain", { selector: "small" })).not.toBeInTheDocument();
  });
});
