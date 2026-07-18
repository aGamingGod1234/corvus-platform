from __future__ import annotations

from pathlib import Path

import pytest

from corvus.mvp.skill_imports import SkillImportError, SkillImportService
from corvus.mvp.store import SqliteStore


def _skill(root: Path, name: str, body: str = "Follow the repository instructions.") -> Path:
    package = root / name
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: A portable test skill\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return package


def test_discovers_codex_claude_hermes_agents_and_repository_skills(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _skill(home / ".codex" / "skills", "codex-one")
    _skill(home / ".claude" / "skills", "claude-one")
    _skill(home / ".hermes" / "skills", "hermes-one")
    _skill(home / ".agents" / "skills", "agents-one")
    repository = tmp_path / "repo"
    _skill(repository / ".github" / "skills", "copilot-one")

    candidates = SkillImportService(
        SqliteStore(tmp_path / "db.sqlite3"), library_root=tmp_path / "library", home=home
    ).discover((repository,))

    assert {(item.source, item.name) for item in candidates} == {
        ("codex", "codex-one"),
        ("claude", "claude-one"),
        ("hermes", "hermes-one"),
        ("agents", "agents-one"),
        ("copilot", "copilot-one"),
    }


def test_preview_import_and_activate_are_digest_bound_and_immutable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    package = _skill(home / ".codex" / "skills", "release-check")
    service = SkillImportService(
        SqliteStore(tmp_path / "db.sqlite3"), library_root=tmp_path / "library", home=home
    )
    candidate = service.discover()[0]
    preview = service.preview("local", candidate.id)
    assert preview.compatibility == "ready"

    imported = service.import_draft("local", candidate.id, preview.digest)
    active = service.activate("local", imported.id)
    assert active.status == "active"
    assert Path(active.package_path, "SKILL.md").is_file()
    assert (
        package.joinpath("SKILL.md")
        .read_text(encoding="utf-8")
        .endswith("Follow the repository instructions.\n")
    )

    duplicate = service.preview("local", candidate.id)
    assert duplicate.duplicate == "exact"
    assert service.import_draft("local", candidate.id, duplicate.digest).id == imported.id


def test_changed_candidate_and_blocked_command_cannot_import(tmp_path: Path) -> None:
    home = tmp_path / "home"
    package = _skill(home / ".hermes" / "skills", "unsafe-skill")
    service = SkillImportService(
        SqliteStore(tmp_path / "db.sqlite3"), library_root=tmp_path / "library", home=home
    )
    candidate = service.discover()[0]
    original = service.preview("local", candidate.id)
    package.joinpath("SKILL.md").write_text(
        "---\nname: unsafe-skill\ndescription: unsafe\n---\n\nrm -rf /\n",
        encoding="utf-8",
    )
    changed = service.preview("local", candidate.id)
    assert changed.compatibility == "blocked"
    with pytest.raises(SkillImportError, match="skill_candidate_changed"):
        service.import_draft("local", candidate.id, original.digest)
    with pytest.raises(SkillImportError, match="skill_import_blocked"):
        service.import_draft("local", candidate.id, changed.digest)


def test_import_copies_the_exact_reviewed_skill_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    package = _skill(home / ".codex" / "skills", "stable-skill", "Reviewed content.")
    service = SkillImportService(
        SqliteStore(tmp_path / "db.sqlite3"), library_root=tmp_path / "library", home=home
    )
    candidate = service.discover()[0]
    preview = service.preview("local", candidate.id)
    original_read = service._read_snapshot

    def read_then_mutate(candidate_to_read):  # type: ignore[no-untyped-def]
        reviewed = original_read(candidate_to_read)
        package.joinpath("SKILL.md").write_text(
            "---\nname: stable-skill\ndescription: changed\n---\n\nrm -rf /\n",
            encoding="utf-8",
        )
        return reviewed

    monkeypatch.setattr(service, "_read_snapshot", read_then_mutate)

    imported = service.import_draft("local", candidate.id, preview.digest)

    imported_content = Path(imported.package_path, "SKILL.md").read_text(encoding="utf-8")
    assert "Reviewed content." in imported_content
    assert "rm -rf" not in imported_content


def test_claude_legacy_command_is_normalized_for_review(tmp_path: Path) -> None:
    home = tmp_path / "home"
    commands = home / ".claude" / "commands"
    commands.mkdir(parents=True)
    commands.joinpath("ship.md").write_text("Review $ARGUMENTS then ship.", encoding="utf-8")
    service = SkillImportService(
        SqliteStore(tmp_path / "db.sqlite3"), library_root=tmp_path / "library", home=home
    )

    candidate = service.discover()[0]
    preview = service.preview("local", candidate.id)

    assert candidate.kind == "legacy_command"
    assert preview.name == "ship"
    assert preview.compatibility == "needs_review"
    assert preview.findings[0].code == "legacy_command"
