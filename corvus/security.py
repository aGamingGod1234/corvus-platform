from __future__ import annotations

import base64
import hashlib
import os
import re
import stat
from pathlib import Path
from typing import ClassVar


class SecurityError(RuntimeError):
    pass


class SecretRedactor:
    _TOKEN_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?([^\s'\"]+)"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    ]

    def __init__(self, secrets: list[str] | None = None) -> None:
        self._secrets: set[str] = set()
        for secret in secrets or []:
            self.register(secret)

    def register(self, secret: str) -> None:
        if len(secret) < 4:
            return
        self._secrets.add(secret)
        self._secrets.add(base64.b64encode(secret.encode()).decode())
        self._secrets.add(secret.encode().hex())

    def redact(self, text: str) -> str:
        result = text
        for secret in sorted(self._secrets, key=len, reverse=True):
            result = result.replace(secret, "[REDACTED]")
        for pattern in self._TOKEN_PATTERNS:
            if pattern.groups >= 2:
                result = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", result)
            else:
                result = pattern.sub("[REDACTED]", result)
        return result


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def resolve_under(root: Path, relative: str, *, allow_missing_leaf: bool = True) -> Path:
    if not relative or Path(relative).is_absolute():
        raise SecurityError("path must be a non-empty relative path")
    normalized = Path(relative)
    if any(part in {"..", ""} for part in normalized.parts):
        raise SecurityError("path traversal is forbidden")
    root = root.resolve(strict=True)
    cursor = root
    missing_prefix = False
    for part in normalized.parts:
        cursor = cursor / part
        if not missing_prefix and (cursor.exists() or cursor.is_symlink()):
            if _is_link_or_reparse(cursor):
                raise SecurityError(f"link or reparse-point escape rejected: {relative}")
        elif not allow_missing_leaf:
            raise SecurityError(f"path component does not exist: {part}")
        else:
            missing_prefix = True
    try:
        cursor.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise SecurityError("path escapes approved root") from exc
    return cursor


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.corvus-{os.getpid()}.tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
