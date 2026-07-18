from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from uuid import uuid4

import yaml
from pydantic import Field

from corvus.mvp.models import MvpModel
from corvus.mvp.store import SqliteStore
from corvus.safe_process import path_is_link_or_reparse

_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_PACKAGE_BYTES = 20 * 1024 * 1024
_MAX_FILES = 500
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_ALLOWED_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".ps1",
}
_EXECUTABLE_SUFFIXES = {".py", ".js", ".ts", ".sh", ".ps1"}


class SkillImportError(RuntimeError):
    pass


class SkillFinding(MvpModel):
    code: str
    severity: Literal["info", "review", "blocked"]
    location: str
    message: str


class SkillCandidate(MvpModel):
    id: str
    source: Literal["codex", "claude", "hermes", "agents", "copilot", "generic"]
    name: str
    path: Path
    kind: Literal["package", "legacy_command"] = "package"


class SkillImportPreview(MvpModel):
    candidate: SkillCandidate
    name: str
    description: str
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    compatibility: Literal["ready", "needs_review", "blocked"]
    findings: tuple[SkillFinding, ...]
    files: tuple[str, ...]
    duplicate: Literal["none", "exact", "variant"]


class PortableSkillVersion(MvpModel):
    id: str
    tenant_id: str
    name: str
    description: str
    version: int
    digest: str
    source: str
    source_path: str
    package_path: str
    status: Literal["draft", "active", "archived"]
    findings: tuple[SkillFinding, ...]
    created_at: datetime


class SkillImportService:
    """Read-only vendor discovery plus reviewed, immutable local package imports."""

    def __init__(self, store: SqliteStore, *, library_root: Path, home: Path | None = None) -> None:
        self.store = store
        self.library_root = library_root.expanduser().absolute()
        self.home = (home or Path.home()).expanduser().absolute()

    def discover(self, repository_roots: tuple[Path, ...] = ()) -> tuple[SkillCandidate, ...]:
        roots: list[tuple[str, Path]] = [
            ("agents", self.home / ".agents" / "skills"),
            ("codex", Path(os.environ.get("CODEX_HOME", self.home / ".codex")) / "skills"),
            ("claude", self.home / ".claude" / "skills"),
            ("hermes", self.home / ".hermes" / "skills"),
        ]
        for repository in repository_roots:
            roots.extend(
                (
                    ("codex", repository / ".codex" / "skills"),
                    ("claude", repository / ".claude" / "skills"),
                    ("agents", repository / ".agents" / "skills"),
                    ("copilot", repository / ".github" / "skills"),
                    ("copilot", repository / ".copilot" / "skills"),
                )
            )
        candidates: dict[str, SkillCandidate] = {}
        for source, root in roots:
            for package in self._package_directories(root):
                candidate = self._candidate(cast(AnySource, source), package, "package")
                candidates[candidate.id] = candidate
        command_roots = [self.home / ".claude" / "commands"] + [
            root / ".claude" / "commands" for root in repository_roots
        ]
        for root in command_roots:
            if not self._safe_directory(root):
                continue
            for command in sorted(root.glob("*.md")):
                if command.is_file() and not path_is_link_or_reparse(command):
                    candidate = self._candidate("claude", command, "legacy_command")
                    candidates[candidate.id] = candidate
        return tuple(
            sorted(candidates.values(), key=lambda item: (item.source, item.name, str(item.path)))
        )

    def preview(
        self,
        tenant_id: str,
        candidate_id: str,
        repository_roots: tuple[Path, ...] = (),
    ) -> SkillImportPreview:
        candidate = self._resolve_candidate(candidate_id, repository_roots)
        preview, _files = self._read_snapshot(candidate)
        return self._with_duplicate(tenant_id, preview)

    def _with_duplicate(
        self,
        tenant_id: str,
        preview: SkillImportPreview,
    ) -> SkillImportPreview:
        with self.store.connect() as connection:
            exact = connection.execute(
                "SELECT 1 FROM mvp_portable_skill_versions WHERE tenant_id = ? AND digest = ?",
                (tenant_id, preview.digest),
            ).fetchone()
            variant = connection.execute(
                "SELECT 1 FROM mvp_portable_skill_versions WHERE tenant_id = ? AND name = ?",
                (tenant_id, preview.name),
            ).fetchone()
        duplicate = "exact" if exact is not None else "variant" if variant is not None else "none"
        return preview.model_copy(update={"duplicate": duplicate})

    def import_draft(
        self,
        tenant_id: str,
        candidate_id: str,
        expected_digest: str,
        repository_roots: tuple[Path, ...] = (),
    ) -> PortableSkillVersion:
        candidate = self._resolve_candidate(candidate_id, repository_roots)
        reviewed_preview, reviewed_files = self._read_snapshot(candidate)
        preview = self._with_duplicate(tenant_id, reviewed_preview)
        if preview.digest != expected_digest:
            raise SkillImportError("skill_candidate_changed")
        if preview.compatibility == "blocked":
            raise SkillImportError("skill_import_blocked")
        if preview.duplicate == "exact":
            with self.store.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM mvp_portable_skill_versions WHERE tenant_id = ? AND digest = ?",
                    (tenant_id, preview.digest),
                ).fetchone()
            assert row is not None
            return self._version(row)
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version "
                "FROM mvp_portable_skill_versions WHERE tenant_id = ? AND name = ?",
                (tenant_id, preview.name),
            ).fetchone()
        version = int(row["version"])
        identifier = str(uuid4())
        target = self.library_root / identifier / str(version)
        staging = self.library_root / ".staging" / identifier
        if staging.exists():
            raise SkillImportError("skill_staging_conflict")
        staging.mkdir(parents=True)
        try:
            self._copy_reviewed(reviewed_files, staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        record = PortableSkillVersion(
            id=identifier,
            tenant_id=tenant_id,
            name=preview.name,
            description=preview.description,
            version=version,
            digest=preview.digest,
            source=preview.candidate.source,
            source_path=str(preview.candidate.path),
            package_path=str(target),
            status="draft",
            findings=preview.findings,
            created_at=datetime.now(UTC),
        )
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO mvp_portable_skill_versions "
                "(id, tenant_id, name, description, version, digest, source, source_path, "
                "package_path, status, findings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.tenant_id,
                    record.name,
                    record.description,
                    record.version,
                    record.digest,
                    record.source,
                    record.source_path,
                    record.package_path,
                    record.status,
                    json.dumps([item.model_dump(mode="json") for item in record.findings]),
                    record.created_at.isoformat(),
                ),
            )
        return record

    def list(self, tenant_id: str) -> tuple[PortableSkillVersion, ...]:
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mvp_portable_skill_versions WHERE tenant_id = ? "
                "ORDER BY name, version DESC",
                (tenant_id,),
            ).fetchall()
        return tuple(self._version(row) for row in rows)

    def activate(self, tenant_id: str, skill_id: str) -> PortableSkillVersion:
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM mvp_portable_skill_versions WHERE tenant_id = ? AND id = ?",
                (tenant_id, skill_id),
            ).fetchone()
            if row is None:
                raise SkillImportError("skill_not_found")
            connection.execute(
                "UPDATE mvp_portable_skill_versions SET status = 'draft' "
                "WHERE tenant_id = ? AND name = ? AND status = 'active'",
                (tenant_id, row["name"]),
            )
            connection.execute(
                "UPDATE mvp_portable_skill_versions SET status = 'active' WHERE id = ?",
                (skill_id,),
            )
        return next(item for item in self.list(tenant_id) if item.id == skill_id)

    def archive(self, tenant_id: str, skill_id: str) -> PortableSkillVersion:
        with self.store.transaction() as connection:
            cursor = connection.execute(
                "UPDATE mvp_portable_skill_versions SET status = 'archived' "
                "WHERE tenant_id = ? AND id = ?",
                (tenant_id, skill_id),
            )
            if cursor.rowcount != 1:
                raise SkillImportError("skill_not_found")
        return next(item for item in self.list(tenant_id) if item.id == skill_id)

    def instructions(self, tenant_id: str, skill_id: str) -> str:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mvp_portable_skill_versions "
                "WHERE tenant_id = ? AND id = ? AND status = 'active'",
                (tenant_id, skill_id),
            ).fetchone()
        if row is None:
            raise SkillImportError("skill_not_found")
        try:
            library_root = self.library_root.resolve(strict=True)
            package = Path(str(row["package_path"])).resolve(strict=True)
        except OSError as exc:
            raise SkillImportError("skill_package_unsafe") from exc
        if (
            not package.is_relative_to(library_root)
            or not self._safe_directory(library_root)
            or not self._safe_directory(package)
        ):
            raise SkillImportError("skill_package_unsafe")
        files = self._read_package(package)
        if not hmac.compare_digest(self._files_digest(files), str(row["digest"])):
            raise SkillImportError("skill_package_changed")
        instructions = dict(files).get("SKILL.md")
        if instructions is None:
            raise SkillImportError("skill_manifest_missing")
        return instructions

    @staticmethod
    def _safe_directory(path: Path) -> bool:
        try:
            return path.is_dir() and not path_is_link_or_reparse(path)
        except OSError:
            return False

    def _package_directories(self, root: Path) -> tuple[Path, ...]:
        if not self._safe_directory(root):
            return ()
        found: list[Path] = []
        for skill_file in root.glob("*/SKILL.md"):
            package = skill_file.parent
            if self._safe_directory(package) and not path_is_link_or_reparse(skill_file):
                found.append(package)
        return tuple(found)

    def _resolve_candidate(
        self,
        candidate_id: str,
        repository_roots: tuple[Path, ...],
    ) -> SkillCandidate:
        candidate = next(
            (item for item in self.discover(repository_roots) if item.id == candidate_id),
            None,
        )
        if candidate is None:
            raise SkillImportError("skill_candidate_not_found")
        return candidate

    @staticmethod
    def _candidate(
        source: AnySource, path: Path, kind: Literal["package", "legacy_command"]
    ) -> SkillCandidate:
        canonical = path.resolve(strict=True)
        name = _slug(path.stem if kind == "legacy_command" else path.name)
        identifier = hashlib.sha256(f"{source}\0{kind}\0{canonical}".encode()).hexdigest()
        return SkillCandidate(id=identifier, source=source, name=name, path=canonical, kind=kind)

    def _read_snapshot(
        self,
        candidate: SkillCandidate,
    ) -> tuple[SkillImportPreview, tuple[tuple[str, str], ...]]:
        findings: list[SkillFinding] = []
        files: tuple[tuple[str, str], ...]
        if candidate.kind == "legacy_command":
            content = self._read_file(candidate.path)
            name = candidate.name
            description = f"Imported Claude command: {candidate.path.stem}"
            files = (("SKILL.md", _render_skill(name, description, content)),)
            findings.append(
                SkillFinding(
                    code="legacy_command",
                    severity="review",
                    location="SKILL.md",
                    message="Claude command was normalized into an Agent Skill.",
                )
            )
        else:
            files = self._read_package(candidate.path)
            skill_content = dict(files).get("SKILL.md")
            if skill_content is None:
                raise SkillImportError("skill_manifest_missing")
            name, description, metadata = _frontmatter(skill_content)
            if name != candidate.name:
                findings.append(
                    SkillFinding(
                        code="name_directory_mismatch",
                        severity="blocked",
                        location="SKILL.md",
                        message="Skill name must match its directory.",
                    )
                )
            allowed_tools = metadata.get("allowed-tools")
            if allowed_tools:
                findings.append(
                    SkillFinding(
                        code="unapproved_tools",
                        severity="review",
                        location="SKILL.md",
                        message=f"Requested tools require approval: {allowed_tools}",
                    )
                )
        for relative, content in files:
            suffix = PurePosixPath(relative).suffix.lower()
            if suffix in _EXECUTABLE_SUFFIXES:
                findings.append(
                    SkillFinding(
                        code="executable_content",
                        severity="review",
                        location=relative,
                        message="Executable content is imported disabled and requires review.",
                    )
                )
            lowered = content.lower()
            if "curl " in lowered or "wget " in lowered or "invoke-webrequest" in lowered:
                findings.append(
                    SkillFinding(
                        code="network_command",
                        severity="review",
                        location=relative,
                        message="Network command detected.",
                    )
                )
            if "rm -rf" in lowered or "remove-item -recurse" in lowered:
                findings.append(
                    SkillFinding(
                        code="destructive_command",
                        severity="blocked",
                        location=relative,
                        message="Destructive recursive command detected.",
                    )
                )
            if re.search(r"(?:sk-|ghp_|github_pat_)[a-z0-9_-]{16,}", content, re.IGNORECASE):
                findings.append(
                    SkillFinding(
                        code="possible_secret",
                        severity="blocked",
                        location=relative,
                        message="Possible embedded credential detected.",
                    )
                )
            if "${claude_skill_dir}" in lowered or "!`" in content:
                findings.append(
                    SkillFinding(
                        code="vendor_dynamic_substitution",
                        severity="review",
                        location=relative,
                        message="Vendor-specific dynamic substitution requires review.",
                    )
                )
        compatibility: Literal["ready", "needs_review", "blocked"] = "ready"
        if any(item.severity == "blocked" for item in findings):
            compatibility = "blocked"
        elif findings:
            compatibility = "needs_review"
        return (
            SkillImportPreview(
                candidate=candidate,
                name=name,
                description=description,
                digest=self._files_digest(files),
                compatibility=compatibility,
                findings=tuple(findings),
                files=tuple(relative for relative, _ in files),
                duplicate="none",
            ),
            files,
        )

    def _read_package(self, root: Path) -> tuple[tuple[str, str], ...]:
        if not self._safe_directory(root):
            raise SkillImportError("skill_package_unsafe")
        values: list[tuple[str, str]] = []
        total = 0
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                if path_is_link_or_reparse(path):
                    raise SkillImportError("skill_package_link_forbidden")
                continue
            if not path.is_file() or path_is_link_or_reparse(path):
                raise SkillImportError("skill_package_link_forbidden")
            relative = path.relative_to(root).as_posix()
            if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
                raise SkillImportError("skill_package_path_escape")
            if path.suffix.lower() not in _ALLOWED_SUFFIXES:
                raise SkillImportError("skill_package_file_type_unsupported")
            size = path.stat().st_size
            if size > _MAX_FILE_BYTES:
                raise SkillImportError("skill_package_file_too_large")
            total += size
            if total > _MAX_PACKAGE_BYTES or len(values) >= _MAX_FILES:
                raise SkillImportError("skill_package_too_large")
            values.append((relative, self._read_file(path)))
        return tuple(values)

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SkillImportError("skill_package_text_invalid") from exc

    @staticmethod
    def _files_digest(files: tuple[tuple[str, str], ...]) -> str:
        digest = hashlib.sha256()
        for relative, content in files:
            digest.update(relative.encode("utf-8") + b"\0" + content.encode("utf-8") + b"\0")
        return digest.hexdigest()

    @staticmethod
    def _copy_reviewed(files: tuple[tuple[str, str], ...], target: Path) -> None:
        for relative, content in files:
            destination = target / PurePosixPath(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content.encode("utf-8"))

    @staticmethod
    def _version(row: object) -> PortableSkillVersion:
        item = cast(dict[str, object], row)
        return PortableSkillVersion(
            id=str(item["id"]),
            tenant_id=str(item["tenant_id"]),
            name=str(item["name"]),
            description=str(item["description"]),
            version=int(cast(int, item["version"])),
            digest=str(item["digest"]),
            source=str(item["source"]),
            source_path=str(item["source_path"]),
            package_path=str(item["package_path"]),
            status=cast(Literal["draft", "active", "archived"], str(item["status"])),
            findings=tuple(
                SkillFinding.model_validate(value)
                for value in json.loads(str(item["findings_json"]))
            ),
            created_at=datetime.fromisoformat(str(item["created_at"])),
        )


type AnySource = Literal["codex", "claude", "hermes", "agents", "copilot", "generic"]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:64]
    if not slug or not _NAME.fullmatch(slug):
        raise SkillImportError("skill_name_invalid")
    return slug


def _frontmatter(content: str) -> tuple[str, str, dict[str, object]]:
    if not content.startswith("---\n"):
        raise SkillImportError("skill_frontmatter_missing")
    marker = content.find("\n---", 4)
    if marker < 0:
        raise SkillImportError("skill_frontmatter_invalid")
    try:
        metadata = yaml.safe_load(content[4:marker])
    except yaml.YAMLError as exc:
        raise SkillImportError("skill_frontmatter_invalid") from exc
    if not isinstance(metadata, dict):
        raise SkillImportError("skill_frontmatter_invalid")
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise SkillImportError("skill_name_invalid")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        raise SkillImportError("skill_description_invalid")
    return name, description.strip(), cast(dict[str, object], metadata)


def _render_skill(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {json.dumps(description)}\n---\n\n{body.strip()}\n"
