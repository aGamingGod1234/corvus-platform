import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PortableSkill, SkillImportCandidate, SkillImportPreview } from "../api";
import { PortableSkillsWorkspace, type PortableSkillsApi } from "./PortableSkillsWorkspace";

const candidate = { id: "a".repeat(64), source: "claude", name: "review-pr", path: "C:\\Users\\me\\.claude\\skills\\review-pr", kind: "package" } as SkillImportCandidate;
const preview = { candidate, name: "review-pr", description: "Review a pull request", digest: "b".repeat(64), compatibility: "needs_review", findings: [{ code: "unapproved_tools", severity: "review", location: "SKILL.md", message: "Requested tools require approval." }], files: ["SKILL.md", "scripts/check.py"], duplicate: "none" } as SkillImportPreview;
const imported = { id: "skill-1", tenant_id: "local", name: "review-pr", description: "Review a pull request", version: 1, digest: preview.digest, source: "claude", source_path: candidate.path, package_path: "C:\\library\\skill-1", status: "draft", findings: preview.findings, created_at: "2026-07-18T00:00:00Z" } as PortableSkill;

function api(): PortableSkillsApi {
  return {
    listPortableSkills: vi.fn().mockResolvedValue([]),
    listSkillImportSources: vi.fn().mockResolvedValue([candidate]),
    previewSkillImport: vi.fn().mockResolvedValue(preview),
    importPortableSkill: vi.fn().mockResolvedValue(imported),
    activatePortableSkill: vi.fn(),
    archivePortableSkill: vi.fn()
  };
}

describe("PortableSkillsWorkspace", () => {
  it("discovers, reviews, and imports a cross-agent skill", async () => {
    const user = userEvent.setup();
    const client = api();
    render(<PortableSkillsWorkspace api={client} />);
    await user.click(await screen.findByRole("button", { name: /review-pr/i }));
    expect(await screen.findByRole("dialog", { name: "review-pr" })).toBeVisible();
    expect(screen.getByText("Requested tools require approval.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Package files" })).toBeVisible();
    expect(screen.getByText("scripts/check.py")).toBeVisible();
    expect(screen.getByText("Imported permissions are never granted automatically.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Close skill review" })).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "Import as draft" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "review-pr" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /review-pr/i }));
    await user.click(screen.getByRole("button", { name: "Import as draft" }));
    await waitFor(() => expect(client.importPortableSkill).toHaveBeenCalledWith(candidate.id, preview.digest));
    expect(await screen.findByText("Review a pull request")).toBeVisible();
  });
});
