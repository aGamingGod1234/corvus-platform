from __future__ import annotations

import json
import secrets
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from difflib import unified_diff
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken

from corvus.models import ApprovalGrant, Artifact, DeliveryBundle
from corvus.security import SecurityError, atomic_write, resolve_under, sha256_bytes, sha256_file


class DeliveryError(RuntimeError):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


class DeliveryManager:
    def __init__(
        self, bundle_root: Path, backup_root: Path, backup_key: bytes | None = None
    ) -> None:
        self.bundle_root = bundle_root
        self.backup_root = backup_root
        bundle_root.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(backup_key) if backup_key is not None else None

    def _cipher(self) -> Fernet:
        if self._fernet is None:
            raise DeliveryError("an OS-keyring-backed backup key is required for delivery")
        return self._fernet

    def package(
        self,
        run_id: UUID,
        destination: Path,
        candidate_files: dict[str, bytes],
        acceptance_report: dict[str, object],
        test_report: dict[str, object],
    ) -> DeliveryBundle:
        if acceptance_report.get("passed") is not True or test_report.get("passed") is not True:
            raise DeliveryError("failed or untested acceptance criteria block packaging")
        destination = destination.resolve(strict=True)
        bundle_id = uuid4()
        root = self.bundle_root / str(bundle_id)
        files_root = root / "files"
        files_root.mkdir(parents=True)
        baseline: dict[str, str | None] = {}
        artifacts: list[Artifact] = []
        patch_lines: list[str] = []
        for relative, data in sorted(candidate_files.items()):
            try:
                target = resolve_under(destination, relative)
            except SecurityError as exc:
                raise DeliveryError(str(exc)) from exc
            baseline[relative] = sha256_file(target) if target.exists() else None
            old_data = target.read_bytes() if target.exists() else b""
            try:
                patch_lines.extend(
                    unified_diff(
                        old_data.decode().splitlines(keepends=True),
                        data.decode().splitlines(keepends=True),
                        fromfile=f"a/{relative}",
                        tofile=f"b/{relative}",
                    )
                )
            except UnicodeDecodeError:
                patch_lines.append(f"Binary file changed: {relative}\n")
            staged = files_root / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(staged, data)
            artifacts.append(
                Artifact(
                    digest=sha256_bytes(data),
                    relative_path=f"files/{Path(relative).as_posix()}",
                    media_type="application/octet-stream",
                    size=len(data),
                )
            )
        patch_data = "".join(patch_lines).encode()
        atomic_write(root / "patch.diff", patch_data)
        artifacts.append(
            Artifact(
                digest=sha256_bytes(patch_data),
                relative_path="patch.diff",
                media_type="text/x-diff",
                size=len(patch_data),
            )
        )
        dependency_files = [
            item.relative_path
            for item in artifacts
            if Path(item.relative_path).name
            in {"pyproject.toml", "uv.lock", "requirements.txt", "package.json", "pnpm-lock.yaml"}
        ]
        reports: dict[str, object] = {
            "acceptance.json": acceptance_report,
            "tests.json": test_report,
            "dependency-manifest.json": {"files": dependency_files},
            "sbom.json": {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "version": 1,
                "components": [
                    {
                        "type": "file",
                        "name": item.relative_path,
                        "hashes": [{"alg": "SHA-256", "content": item.digest}],
                    }
                    for item in artifacts
                    if item.relative_path.startswith("files/")
                ],
            },
            "security.json": {
                "dependency_audit": "not_run",
                "container_scan": "not_run",
                "reason": "scanner results were not supplied to the delivery manager",
            },
            "rollback.json": {"strategy": "restore authenticated encrypted application backup"},
            "README.json": {
                "review": (
                    "Verify bundle.json, patch.diff, acceptance.json, tests.json, and SHA256SUMS."
                ),
                "undo": f"corvus undo {bundle_id}",
            },
        }
        for name, report in reports.items():
            data = _canonical_json(report)
            atomic_write(root / name, data)
            artifacts.append(
                Artifact(
                    digest=sha256_bytes(data),
                    relative_path=name,
                    media_type="application/json",
                    size=len(data),
                )
            )
        manifest_body = {
            "schema_version": 1,
            "id": str(bundle_id),
            "run_id": str(run_id),
            "destination": str(destination),
            "changed_files": sorted(candidate_files),
            "baseline_hashes": baseline,
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
        }
        manifest_digest = sha256_bytes(_canonical_json(manifest_body))
        manifest_body["manifest_digest"] = manifest_digest
        atomic_write(root / "bundle.json", _canonical_json(manifest_body))
        sums = [f"{item.digest}  {item.relative_path}" for item in artifacts]
        atomic_write(root / "SHA256SUMS", ("\n".join(sums) + "\n").encode())
        return DeliveryBundle(
            id=bundle_id,
            run_id=run_id,
            destination=destination,
            artifacts=artifacts,
            changed_files=sorted(candidate_files),
            baseline_hashes=baseline,
            manifest_digest=manifest_digest,
        )

    def approve(self, bundle: DeliveryBundle, ttl_minutes: int = 15) -> ApprovalGrant:
        return ApprovalGrant(
            run_id=bundle.run_id,
            bundle_id=bundle.id,
            destination=bundle.destination,
            manifest_digest=bundle.manifest_digest,
            approved_files=bundle.changed_files,
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            nonce=secrets.token_urlsafe(24),
        )

    @staticmethod
    def _validate_approval(bundle: DeliveryBundle, approval: ApprovalGrant) -> None:
        if approval.expires_at <= datetime.now(UTC):
            raise DeliveryError("approval expired")
        if (
            approval.run_id != bundle.run_id
            or approval.bundle_id != bundle.id
            or approval.destination.resolve() != bundle.destination.resolve()
            or approval.manifest_digest != bundle.manifest_digest
            or sorted(approval.approved_files) != sorted(bundle.changed_files)
        ):
            raise DeliveryError("approval is not bound to this exact bundle")

    def apply(self, bundle: DeliveryBundle, approval: ApprovalGrant) -> Path:
        self._validate_approval(bundle, approval)
        root = self.bundle_root / str(bundle.id)
        manifest = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
        manifest_digest = manifest.pop("manifest_digest")
        if sha256_bytes(_canonical_json(manifest)) != manifest_digest:
            raise DeliveryError("bundle manifest integrity check failed")
        backup = self.backup_root / str(bundle.id)
        backup.mkdir(parents=True, exist_ok=False)
        journal: dict[str, Any] = {"status": "applying", "files": {}}
        journal["git_ref"] = self._create_git_checkpoint(bundle)
        atomic_write(backup / "journal.json", _canonical_json(journal))
        applied: list[Path] = []
        try:
            for relative in bundle.changed_files:
                target = resolve_under(bundle.destination, relative)
                actual = sha256_file(target) if target.exists() else None
                if actual != bundle.baseline_hashes[relative]:
                    raise DeliveryError(f"destination conflict: {relative}")
                backup_file = backup / "files" / f"{relative}.enc"
                existed = target.exists()
                if existed:
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write(backup_file, self._cipher().encrypt(target.read_bytes()))
                source = root / "files" / relative
                atomic_write(target, source.read_bytes())
                applied.append(target)
                journal["files"][relative] = {
                    "existed": existed,
                    "delivered_hash": sha256_file(target),
                    "baseline_hash": bundle.baseline_hashes[relative],
                }
                atomic_write(backup / "journal.json", _canonical_json(journal))
            journal["status"] = "applied"
            atomic_write(backup / "journal.json", _canonical_json(journal))
            return backup
        except Exception:
            self._restore(bundle.destination, backup, applied_only=bundle.changed_files)
            raise

    def undo(self, bundle: DeliveryBundle) -> None:
        backup = self.backup_root / str(bundle.id)
        journal = json.loads((backup / "journal.json").read_text(encoding="utf-8"))
        if journal.get("status") not in {"applied", "rolled_back"}:
            raise DeliveryError("delivery has no restorable checkpoint")
        for relative, item in journal["files"].items():
            target = resolve_under(bundle.destination, relative)
            if not target.exists() or sha256_file(target) != item["delivered_hash"]:
                raise DeliveryError(f"undo conflict: {relative}")
        self._restore(bundle.destination, backup, applied_only=bundle.changed_files)

    def _restore(self, destination: Path, backup: Path, applied_only: list[str]) -> None:
        journal_path = backup / "journal.json"
        journal = (
            json.loads(journal_path.read_text(encoding="utf-8"))
            if journal_path.exists()
            else {"files": {}}
        )
        for relative in reversed(applied_only):
            item = journal.get("files", {}).get(relative)
            if item is None:
                continue
            target = resolve_under(destination, relative)
            source = backup / "files" / f"{relative}.enc"
            if item["existed"]:
                try:
                    plaintext = self._cipher().decrypt(source.read_bytes())
                except InvalidToken as exc:
                    raise DeliveryError("checkpoint decryption or integrity check failed") from exc
                atomic_write(target, plaintext)
            elif target.exists():
                target.unlink()
        journal["status"] = "rolled_back"
        atomic_write(journal_path, _canonical_json(journal))

    @staticmethod
    def _create_git_checkpoint(bundle: DeliveryBundle) -> str | None:
        git = shutil.which("git")
        if git is None or not (bundle.destination / ".git").exists():
            return None
        status = subprocess.run(  # noqa: S603 - resolved git executable, no shell
            [git, "status", "--porcelain"],
            cwd=bundle.destination,
            check=False,
            capture_output=True,
            text=True,
        )
        if status.returncode != 0 or status.stdout.strip():
            return None
        head = subprocess.run(  # noqa: S603 - resolved git executable, no shell
            [git, "rev-parse", "HEAD"],
            cwd=bundle.destination,
            check=False,
            capture_output=True,
            text=True,
        )
        if head.returncode != 0:
            return None
        reference = f"refs/corvus/checkpoints/{bundle.id}"
        updated = subprocess.run(  # noqa: S603 - resolved git executable, no shell
            [git, "update-ref", reference, head.stdout.strip()],
            cwd=bundle.destination,
            check=False,
            capture_output=True,
        )
        return reference if updated.returncode == 0 else None

    def load(self, bundle_id: UUID) -> DeliveryBundle:
        data = json.loads(
            (self.bundle_root / str(bundle_id) / "bundle.json").read_text(encoding="utf-8")
        )
        data.pop("schema_version", None)
        return DeliveryBundle.model_validate(data)
