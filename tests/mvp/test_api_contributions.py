from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from corvus.mvp.api import create_app
from corvus.mvp.change_review import ChangeReviewService
from corvus.mvp.contributions import ContributionService
from corvus.mvp.git_process import GitProcess
from corvus.mvp.repository_workspace import RepositoryWorkspaceService
from corvus.mvp.secret_scan import SecretScanner
from corvus.mvp.store import SqliteStore
from corvus.mvp.worktrees import WorktreeManager
from tests.mvp.test_contributions import FakeGitHub


def _git() -> GitProcess:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is unavailable")
    return GitProcess(Path(executable))


def _run(git: GitProcess, cwd: Path, *args: str) -> str:
    result = git.run(cwd, tuple(args), timeout=120)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout.decode().strip()


def test_contribution_api_reviews_prepares_confirms_and_publishes(tmp_path: Path) -> None:
    git = _git()
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _run(git, remote, "init", "--bare")
    source = tmp_path / "source"
    source.mkdir()
    _run(git, source, "init", "--initial-branch=main")
    _run(git, source, "config", "user.email", "corvus@example.test")
    _run(git, source, "config", "user.name", "Corvus Tests")
    (source / "README.md").write_text("initial\n", encoding="utf-8")
    _run(git, source, "add", "--", "README.md")
    _run(git, source, "commit", "-m", "initial")
    _run(git, source, "remote", "add", "origin", str(remote))
    _run(git, source, "push", "-u", "origin", "main")
    database = tmp_path / "corvus.sqlite3"
    store = SqliteStore(database)
    repositories = RepositoryWorkspaceService(store, git)
    repository = repositories.register_local("local", source, "Source")
    with store.transaction() as connection:
        connection.execute(
            "UPDATE mvp_repositories SET remote_slug = 'team/corvus' WHERE id = ?",
            (repository.id,),
        )
    repository = repositories.get("local", repository.id)
    worktrees = WorktreeManager(
        store,
        git,
        root=tmp_path / "worktrees",
        ownership_secret=b"worktree-test-secret",
    )
    github = FakeGitHub()
    contributions = ContributionService(
        store,
        git,
        worktrees,
        ChangeReviewService(git),
        SecretScanner(),
        github,
        confirmation_secret=b"contribution-confirmation-secret",
    )
    token = secrets.token_urlsafe(32)
    client = TestClient(
        create_app(
            database=database,
            bootstrap_token=token,
            session_secret=secrets.token_bytes(32),
            repository_workspace=repositories,
            worktree_manager=worktrees,
            contribution_service=contributions,
        )
    )
    assert client.get("/api/local/repositories").status_code == 401
    assert client.post("/api/auth/pair", json={"token": token}).status_code == 200
    csrf = cast(str, client.get("/api/auth/session").json()["csrf_token"])

    created = client.post(
        f"/api/local/repositories/{repository.id}/worktrees",
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["run_id"]
    lease = worktrees.get(run_id)
    (lease.root / "feature.txt").write_text("feature\n", encoding="utf-8")

    changes = client.get(f"/api/local/runs/{run_id}/changes")
    assert changes.status_code == 200
    assert changes.json()["files"][0]["path"] == "feature.txt"

    prepared = client.post(
        f"/api/local/runs/{run_id}/contribution/prepare",
        json={
            "selected_paths": ["feature.txt"],
            "message": "Add feature",
            "title": "Add feature",
            "body": "Reviewed by Corvus.",
            "draft": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["state"] == "committed"

    mismatch = client.post(
        f"/api/local/runs/{run_id}/contribution/publish",
        json={"expected_digest": "0" * 64},
        headers={"X-CSRF-Token": csrf},
    )
    assert mismatch.status_code == 409

    published = client.post(
        f"/api/local/runs/{run_id}/contribution/publish",
        json={"expected_digest": prepared.json()["confirmation_digest"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert published.status_code == 200, published.text
    assert published.json()["pr_number"] == 17
