from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from corvus.database import DatabaseBootstrapError, DatabaseState, classify_database
from corvus.security import SecretRedactor, atomic_write, sha256_bytes, sha256_file

_CAPTURE_SCHEMA_VERSION = 1
_CONFIG_FILES = ("onboarding.json", "onboarding.yaml", "policy.yaml", "providers.yaml")
_SECRET_KEYS = {"api_key", "apikey", "password", "secret", "token"}
_MAX_CONFIG_BYTES = 1_048_576
_MAX_FILES = 10_000
_MAX_FILE_BYTES = 100 * 1_048_576
_MAX_TOTAL_BYTES = 1_024 * 1_048_576
_TABLE_QUERIES: dict[str, tuple[tuple[str, ...], str]] = {
    "deliveries": (
        (
            "id",
            "run_id",
            "bundle_json",
            "approval_json",
            "checkpoint_json",
            "status",
            "created_at",
        ),
        "SELECT id, run_id, bundle_json, approval_json, checkpoint_json, status, created_at "
        "FROM deliveries ORDER BY id",
    ),
    "memories": (
        (
            "id",
            "project_id",
            "identity_id",
            "kind",
            "content",
            "source",
            "confidence",
            "pinned",
            "expires_at",
            "created_at",
        ),
        "SELECT id, project_id, identity_id, kind, content, source, confidence, pinned, "
        "expires_at, created_at FROM memories ORDER BY id",
    ),
    "run_events": (
        (
            "id",
            "run_id",
            "sequence",
            "event_type",
            "phase",
            "payload_json",
            "previous_hash",
            "event_hash",
            "created_at",
        ),
        "SELECT id, run_id, sequence, event_type, phase, payload_json, previous_hash, "
        "event_hash, created_at FROM run_events ORDER BY run_id, sequence, id",
    ),
    "skill_versions": (
        (
            "id",
            "skill_name",
            "version",
            "content",
            "permissions_json",
            "evaluation_json",
            "status",
            "created_at",
        ),
        "SELECT id, skill_name, version, content, permissions_json, evaluation_json, status, "
        "created_at FROM skill_versions ORDER BY skill_name, version, id",
    ),
}


@dataclass(frozen=True)
class QuarantineReceipt:
    capture_id: str
    path: Path
    records_sha256: str
    seal: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _is_link_or_reparse(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def _sanitize(value: Any, redactor: SecretRedactor, *, key: str | None = None) -> Any:
    normalized_key = (key or "").casefold().replace("-", "_")
    if normalized_key in _SECRET_KEYS or normalized_key.endswith(
        ("_token", "_secret", "_password")
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize(item, redactor, key=str(item_key))
            for item_key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [_sanitize(item, redactor) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item, redactor) for item in value]
    if isinstance(value, str):
        return redactor.redact(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redactor.redact(str(value))


def _snapshot_database(database: Path, destination: Path) -> None:
    uri = f"{database.resolve().as_uri()}?mode=ro"
    with (
        closing(sqlite3.connect(uri, uri=True)) as source,
        closing(sqlite3.connect(destination)) as target,
    ):
        result = source.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise ValueError("source database failed SQLite integrity check")
        source.backup(target)
        target.commit()
        if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("quarantine database snapshot failed SQLite integrity check")


def _database_records(snapshot: Path, redactor: SecretRedactor) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    with closing(sqlite3.connect(snapshot)) as connection:
        for table, (columns, query) in sorted(_TABLE_QUERIES.items()):
            rows = connection.execute(query).fetchall()
            records[table] = [
                _sanitize(dict(zip(columns, row, strict=True)), redactor) for row in rows
            ]
    return records


def _config_records(root: Path, redactor: SecretRedactor) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name in _CONFIG_FILES:
        path = root / name
        if not path.exists():
            continue
        if not path.is_file() or _is_link_or_reparse(path):
            raise ValueError(f"unsupported quarantine config entry: {name}")
        size = path.stat().st_size
        if size > _MAX_CONFIG_BYTES:
            raise ValueError(f"quarantine config entry exceeds size limit: {name}")
        text = path.read_text(encoding="utf-8")
        loaded = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
        records[name] = _sanitize(loaded, redactor)
    return records


def _file_inventory(root: Path) -> list[dict[str, object]]:
    if not root.exists():
        return []
    if not root.is_dir() or _is_link_or_reparse(root):
        raise ValueError(f"unsupported quarantine inventory root: {root.name}")
    inventory: list[dict[str, object]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if _is_link_or_reparse(path):
            raise ValueError(
                f"link or reparse point rejected from quarantine inventory: {relative}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"unsupported quarantine inventory entry: {relative}")
        size = path.stat().st_size
        if size > _MAX_FILE_BYTES:
            raise ValueError(f"quarantine inventory file exceeds size limit: {relative}")
        total_bytes += size
        if total_bytes > _MAX_TOTAL_BYTES:
            raise ValueError("quarantine inventory exceeds total byte limit")
        inventory.append({"relative_path": relative, "sha256": sha256_file(path), "size": size})
        if len(inventory) > _MAX_FILES:
            raise ValueError("quarantine inventory exceeds file-count limit")
    return inventory


def _manifest(records_sha256: str, source_database_sha256: str) -> dict[str, object]:
    body: dict[str, object] = {
        "capture_id": records_sha256,
        "records_sha256": records_sha256,
        "schema_version": _CAPTURE_SCHEMA_VERSION,
        "seal_algorithm": "sha256",
        "source_database_sha256": source_database_sha256,
    }
    body["seal"] = sha256_bytes(_canonical_json(body))
    return body


def verify_v1_quarantine(path: Path) -> bool:
    try:
        records_bytes = (path / "records.json").read_bytes()
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        seal = manifest.pop("seal")
        records_sha256 = sha256_bytes(records_bytes)
        return bool(
            path.name == records_sha256
            and manifest.get("capture_id") == records_sha256
            and manifest.get("records_sha256") == records_sha256
            and manifest.get("schema_version") == _CAPTURE_SCHEMA_VERSION
            and manifest.get("seal_algorithm") == "sha256"
            and seal == sha256_bytes(_canonical_json(manifest))
            and isinstance(json.loads(records_bytes), dict)
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def capture_v1_quarantine(
    *,
    database: Path,
    config_root: Path,
    artifact_root: Path,
    bundle_root: Path,
    backup_root: Path,
    quarantine_root: Path,
    redactor: SecretRedactor | None = None,
) -> QuarantineReceipt:
    status = classify_database(database)
    if status.state not in {DatabaseState.UNSTAMPED_V1, DatabaseState.CURRENT}:
        raise DatabaseBootstrapError(status)
    redactor = redactor or SecretRedactor()
    quarantine_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="corvus-v1-quarantine-db-") as temporary:
        snapshot = Path(temporary) / "corvus.db"
        _snapshot_database(database, snapshot)
        records = {
            "artifacts": _file_inventory(artifact_root),
            "backups": _file_inventory(backup_root),
            "bundles": _file_inventory(bundle_root),
            "config": _config_records(config_root, redactor),
            "database": _database_records(snapshot, redactor),
            "schema_version": _CAPTURE_SCHEMA_VERSION,
            "source_database": {
                "schema_version": status.schema_version,
                "state": status.state.value,
            },
        }
        records_bytes = _canonical_json(records)
        records_sha256 = sha256_bytes(records_bytes)
        manifest = _manifest(records_sha256, sha256_file(snapshot))

    destination = quarantine_root / records_sha256
    if destination.exists():
        if not verify_v1_quarantine(destination):
            raise ValueError("existing quarantine capture failed verification")
    else:
        temporary_capture = quarantine_root / f".{records_sha256}-{uuid4().hex}.tmp"
        try:
            temporary_capture.mkdir()
            atomic_write(temporary_capture / "records.json", records_bytes)
            atomic_write(temporary_capture / "manifest.json", _canonical_json(manifest))
            try:
                os.replace(temporary_capture, destination)
            except FileExistsError:
                if not verify_v1_quarantine(destination):
                    raise ValueError("concurrent quarantine capture failed verification") from None
        finally:
            shutil.rmtree(temporary_capture, ignore_errors=True)
    return QuarantineReceipt(
        capture_id=records_sha256,
        path=destination,
        records_sha256=records_sha256,
        seal=str(manifest["seal"]),
    )
