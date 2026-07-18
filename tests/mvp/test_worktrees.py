from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from corvus.mvp.core import DomainConflict
from corvus.mvp.git_process import GitProcess
from corvus.mvp.repository_workspace import RepositoryWorkspaceService
from corvus.mvp.store import SqliteStore
from corvus.mvp.worktrees import WorktreeManager, WorktreeOwnershipError


def _git_process() -> GitProcess:
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is unavailable")
    return GitProcess(Path(executable))


def _run(git: GitProcess, cwd: Path, *args: str) -> str:
    result = git.run(cwd, tuple(args))
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout.decode().strip()


def _workspace(tmp_path: Path) -> tuple[GitProcess, SqliteStore, object, Path, str]:
    repository_root = tmp_path / "source"
    repository_root.mkdir()
    git = _git_process()
    _run(git, repository_root, "init", "--initial-branch=main")
    _run(git, repository_root, "config", "user.email", "corvus@example.test")
    _run(git, repository_root, "config", "user.name", "Corvus Tests")
    (repository_root / "README.md").write_text("initial\n", encoding="utf-8")
    _run(git, repository_root, "add", "--", "README.md")
    _run(git, repository_root, "commit", "-m", "initial")
    base_sha = _run(git, repository_root, "rev-parse", "HEAD")
    store = SqliteStore(tmp_path / "corvus.sqlite3")
    repository = RepositoryWorkspaceService(store, git).register_local(
        "local", repository_root, "Source"
    )
    return git, store, repository, repository_root, base_sha


def test_create_checks_out_exact_sha_without_modifying_original(tmp_path: Path) -> None:
    git, store, repository, original, base_sha = _workspace(tmp_path)
    before_status = _run(git, original, "status", "--porcelain=v1")
    run_id = str(uuid4())
    manager = WorktreeManager(
        store,
        git,
        root=tmp_path / "managed-worktrees",
        ownership_secret=b"worktree-test-secret",
    )

    lease = manager.create(repository, run_id, base_sha)  # type: ignore[arg-type]

    assert lease.root.is_relative_to((tmp_path / "managed-worktrees").resolve())
    assert _run(git, lease.root, "rev-parse", "HEAD") == base_sha
    assert _run(git, lease.root, "branch", "--show-current") == ""
    (lease.root / "README.md").write_text("worktree change\n", encoding="utf-8")
    assert (original / "README.md").read_text(encoding="utf-8") == "initial\n"
    assert _run(git, original, "status", "--porcelain=v1") == before_status


def test_duplicate_run_is_refused_and_discard_requires_terminal_run(tmp_path: Path) -> None:
    git, store, repository, _, base_sha = _workspace(tmp_path)
    run_id = str(uuid4())
    manager = WorktreeManager(
        store,
        git,
        root=tmp_path / "managed-worktrees",
        ownership_secret=b"worktree-test-secret",
    )
    lease = manager.create(repository, run_id, base_sha)  # type: ignore[arg-type]

    with pytest.raises(DomainConflict, match="worktree_run_already_exists"):
        manager.create(repository, run_id, base_sha)  # type: ignore[arg-type]
    with pytest.raises(DomainConflict, match="worktree_run_still_active"):
        manager.discard(lease, run_terminal=False)

    manager.discard(lease, run_terminal=True)
    assert not lease.root.exists()
    assert manager.get(run_id).status == "discarded"
    with pytest.raises(DomainConflict, match="worktree_run_already_exists"):
        manager.create(repository, run_id, base_sha)  # type: ignore[arg-type]


def test_discard_rejects_tampered_database_path(tmp_path: Path) -> None:
    git, store, repository, _, base_sha = _workspace(tmp_path)
    run_id = str(uuid4())
    manager = WorktreeManager(
        store,
        git,
        root=tmp_path / "managed-worktrees",
        ownership_secret=b"worktree-test-secret",
    )
    manager.create(repository, run_id, base_sha)  # type: ignore[arg-type]
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with store.transaction() as connection:
        connection.execute(
            "UPDATE mvp_worktree_leases SET root_path = ? WHERE run_id = ?",
            (str(outside), run_id),
        )

    with pytest.raises(WorktreeOwnershipError, match="ownership_invalid"):
        manager.get(run_id)
    assert marker.read_text(encoding="utf-8") == "keep"


def test_create_rejects_untrusted_sha_and_linked_root(tmp_path: Path) -> None:
    git, store, repository, _, _ = _workspace(tmp_path)
    root = tmp_path / "managed-worktrees"
    outside = tmp_path / "outside-root"
    outside.mkdir()
    try:
        root.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    manager = WorktreeManager(
        store,
        git,
        root=root,
        ownership_secret=b"worktree-test-secret",
    )

    with pytest.raises(WorktreeOwnershipError, match="root_invalid"):
        manager.create(repository, str(uuid4()), "not-a-sha")  # type: ignore[arg-type]
