from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from corvus.mvp.core import DomainConflict, DomainNotFound
from corvus.mvp.git_process import GitProcess
from corvus.mvp.models import MvpModel
from corvus.mvp.repository_workspace import RepositoryRecord
from corvus.mvp.store import SqliteStore
from corvus.safe_process import path_is_link_or_reparse


class WorktreeOwnershipError(RuntimeError):
    pass


class WorktreeLease(MvpModel):
    run_id: str
    repository_id: str
    root: Path
    base_sha: str
    ownership_digest: str
    status: Literal["creating", "active", "discarded"]
    created_at: datetime
    discarded_at: datetime | None = None


class WorktreeManager:
    def __init__(
        self,
        store: SqliteStore,
        git: GitProcess,
        *,
        root: Path,
        ownership_secret: bytes,
    ) -> None:
        if len(ownership_secret) < 16:
            raise ValueError("worktree_ownership_secret_too_short")
        self.store = store
        self.git = git
        self._configured_root = root.expanduser().absolute()
        self._ownership_secret = ownership_secret

    def create(
        self,
        repository: RepositoryRecord,
        run_id: str,
        base_sha: str,
    ) -> WorktreeLease:
        managed_root = self._initialize_root()
        normalized_run_id = self._run_id(run_id)
        if not self._valid_sha(base_sha):
            raise WorktreeOwnershipError("worktree_base_sha_invalid")
        repository_root = Path(repository.path)
        try:
            canonical_repository = repository_root.resolve(strict=True)
        except OSError as exc:
            raise WorktreeOwnershipError("worktree_repository_unavailable") from exc
        if not canonical_repository.is_dir() or path_is_link_or_reparse(canonical_repository):
            raise WorktreeOwnershipError("worktree_repository_unavailable")

        repository_directory = managed_root / repository.id
        repository_directory.mkdir(mode=0o700, exist_ok=True)
        if path_is_link_or_reparse(repository_directory):
            raise WorktreeOwnershipError("worktree_root_invalid")
        target = repository_directory / normalized_run_id
        if target.exists() or path_is_link_or_reparse(target):
            raise DomainConflict("worktree_run_already_exists")
        created_at = datetime.now(UTC)
        digest = self._ownership_digest(
            normalized_run_id,
            repository.id,
            target,
            base_sha,
        )
        try:
            with self.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO mvp_worktree_leases "
                    "(run_id, repository_id, root_path, base_sha, ownership_digest, status, "
                    "created_at, discarded_at) VALUES (?, ?, ?, ?, ?, 'creating', ?, NULL)",
                    (
                        normalized_run_id,
                        repository.id,
                        os.fspath(target),
                        base_sha,
                        digest,
                        created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("worktree_run_already_exists") from exc

        result = self.git.run(
            canonical_repository,
            ("worktree", "add", "--detach", os.fspath(target), base_sha),
            timeout=120,
        )
        if result.returncode != 0:
            self._delete_creating_lease(normalized_run_id)
            raise WorktreeOwnershipError("worktree_creation_failed")
        try:
            canonical_target = target.resolve(strict=True)
            if canonical_target != target or not canonical_target.is_relative_to(managed_root):
                raise WorktreeOwnershipError("worktree_ownership_invalid")
            if path_is_link_or_reparse(canonical_target):
                raise WorktreeOwnershipError("worktree_ownership_invalid")
            actual_sha = self.git.run(canonical_target, ("rev-parse", "--verify", "HEAD"))
            if (
                actual_sha.returncode != 0
                or actual_sha.stdout.decode("ascii", errors="strict").strip() != base_sha
            ):
                raise WorktreeOwnershipError("worktree_checkout_mismatch")
        except (OSError, UnicodeDecodeError, WorktreeOwnershipError):
            self._cleanup_failed_worktree(canonical_repository, target)
            self._delete_creating_lease(normalized_run_id)
            raise
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE mvp_worktree_leases SET root_path = ?, status = 'active' "
                "WHERE run_id = ? AND status = 'creating'",
                (os.fspath(canonical_target), normalized_run_id),
            )
        return self.get(normalized_run_id)

    def get(self, run_id: str) -> WorktreeLease:
        normalized_run_id = self._run_id(run_id)
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mvp_worktree_leases WHERE run_id = ?",
                (normalized_run_id,),
            ).fetchone()
        if row is None:
            raise DomainNotFound("worktree_lease_not_found")
        lease = WorktreeLease(
            run_id=str(row["run_id"]),
            repository_id=str(row["repository_id"]),
            root=Path(str(row["root_path"])),
            base_sha=str(row["base_sha"]),
            ownership_digest=str(row["ownership_digest"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            created_at=datetime.fromisoformat(str(row["created_at"])),
            discarded_at=(
                datetime.fromisoformat(str(row["discarded_at"]))
                if row["discarded_at"] is not None
                else None
            ),
        )
        if lease.status == "active":
            self._validate_active_lease(lease)
        return lease

    def discard(self, lease: WorktreeLease, *, run_terminal: bool) -> WorktreeLease:
        current = self.get(lease.run_id)
        if not (
            lease.repository_id == current.repository_id
            and lease.root == current.root
            and lease.base_sha == current.base_sha
            and hmac.compare_digest(lease.ownership_digest, current.ownership_digest)
        ):
            raise WorktreeOwnershipError("worktree_ownership_invalid")
        if current.status == "discarded":
            return current
        if not run_terminal:
            raise DomainConflict("worktree_run_still_active")
        canonical_root = self._validate_active_lease(current)
        with self.store.connect() as connection:
            repository_row = connection.execute(
                "SELECT canonical_path FROM mvp_repositories WHERE id = ?",
                (current.repository_id,),
            ).fetchone()
        if repository_row is None:
            raise WorktreeOwnershipError("worktree_repository_unavailable")
        repository_root = Path(str(repository_row["canonical_path"]))
        result = self.git.run(
            repository_root,
            ("worktree", "remove", "--force", os.fspath(canonical_root)),
            timeout=120,
        )
        if result.returncode != 0:
            raise WorktreeOwnershipError("worktree_discard_failed")
        if canonical_root.exists():
            try:
                canonical_root.rmdir()
            except OSError as exc:
                raise WorktreeOwnershipError("worktree_discard_unconfirmed") from exc
        discarded_at = datetime.now(UTC)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE mvp_worktree_leases SET status = 'discarded', discarded_at = ? "
                "WHERE run_id = ? AND status = 'active'",
                (discarded_at.isoformat(), current.run_id),
            )
        return self.get(current.run_id)

    def _validate_active_lease(self, lease: WorktreeLease) -> Path:
        managed_root = self._initialize_root()
        expected = managed_root / lease.repository_id / lease.run_id
        expected_digest = self._ownership_digest(
            lease.run_id,
            lease.repository_id,
            expected,
            lease.base_sha,
        )
        if lease.root != expected or not hmac.compare_digest(
            lease.ownership_digest, expected_digest
        ):
            raise WorktreeOwnershipError("worktree_ownership_invalid")
        try:
            canonical_root = lease.root.resolve(strict=True)
        except OSError as exc:
            raise WorktreeOwnershipError("worktree_ownership_invalid") from exc
        if (
            canonical_root != expected
            or not canonical_root.is_relative_to(managed_root)
            or path_is_link_or_reparse(canonical_root)
        ):
            raise WorktreeOwnershipError("worktree_ownership_invalid")
        return canonical_root

    def _initialize_root(self) -> Path:
        if self._configured_root.exists() and path_is_link_or_reparse(self._configured_root):
            raise WorktreeOwnershipError("worktree_root_invalid")
        try:
            self._configured_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            root = self._configured_root.resolve(strict=True)
        except OSError as exc:
            raise WorktreeOwnershipError("worktree_root_invalid") from exc
        if not root.is_dir() or path_is_link_or_reparse(root):
            raise WorktreeOwnershipError("worktree_root_invalid")
        return root

    def _cleanup_failed_worktree(self, repository_root: Path, target: Path) -> None:
        result = self.git.run(
            repository_root,
            ("worktree", "remove", "--force", os.fspath(target)),
            timeout=120,
        )
        if result.returncode != 0:
            raise WorktreeOwnershipError("worktree_cleanup_failed")

    def _delete_creating_lease(self, run_id: str) -> None:
        with self.store.transaction() as connection:
            connection.execute(
                "DELETE FROM mvp_worktree_leases WHERE run_id = ? AND status = 'creating'",
                (run_id,),
            )

    def _ownership_digest(
        self,
        run_id: str,
        repository_id: str,
        root: Path,
        base_sha: str,
    ) -> str:
        payload = "\0".join((run_id, repository_id, os.fspath(root), base_sha)).encode("utf-8")
        return hmac.new(self._ownership_secret, payload, hashlib.sha256).hexdigest()

    @staticmethod
    def _run_id(value: str) -> str:
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise WorktreeOwnershipError("worktree_run_id_invalid") from exc
        if str(parsed) != value.lower():
            raise WorktreeOwnershipError("worktree_run_id_invalid")
        return str(parsed)

    @staticmethod
    def _valid_sha(value: str) -> bool:
        return len(value) == 40 and all(character in "0123456789abcdef" for character in value)
