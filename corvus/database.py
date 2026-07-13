from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from corvus.security import atomic_write, sha256_file

if TYPE_CHECKING:
    from sqlalchemy import MetaData

LEGACY_SCHEMA_VERSION = 1
CURRENT_SCHEMA_VERSION = 2
M005_001_MIGRATION = "M005-001"
SCHEMA_METADATA_TABLE = "corvus_schema"
V1_REQUIRED_TABLES = frozenset(
    {
        "deliveries",
        "memories",
        "run_events",
        "skill_versions",
    }
)
M005_001_REQUIRED_TABLES = frozenset({"external_contents", "context_envelopes"})
M005_001_APPEND_ONLY_TRIGGERS = frozenset(
    {
        "external_contents_no_delete",
        "external_contents_no_update",
        "context_envelopes_no_delete",
        "context_envelopes_no_update",
    }
)
V1_REQUIRED_COLUMNS = {
    "deliveries": frozenset(
        {
            "id",
            "run_id",
            "bundle_json",
            "approval_json",
            "checkpoint_json",
            "status",
            "created_at",
        }
    ),
    "memories": frozenset(
        {
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
        }
    ),
    "run_events": frozenset(
        {
            "id",
            "run_id",
            "sequence",
            "event_type",
            "phase",
            "payload_json",
            "previous_hash",
            "event_hash",
            "created_at",
        }
    ),
    "skill_versions": frozenset(
        {
            "id",
            "skill_name",
            "version",
            "content",
            "permissions_json",
            "evaluation_json",
            "status",
            "created_at",
        }
    ),
}
M005_001_REQUIRED_COLUMNS = {
    "external_contents": frozenset(
        {
            "id",
            "owner_kind",
            "owner_id",
            "origin",
            "source_locator_digest",
            "content_digest",
            "trust_class",
            "content_json",
            "provenance_json",
            "created_at",
        }
    ),
    "context_envelopes": frozenset(
        {
            "id",
            "owner_kind",
            "owner_id",
            "system_instruction_digest",
            "trusted_content_ids_json",
            "untrusted_content_ids_json",
            "firewall_policy_digest",
            "output_digest",
            "created_at",
        }
    ),
}
CURRENT_REQUIRED_COLUMNS = {**V1_REQUIRED_COLUMNS, **M005_001_REQUIRED_COLUMNS}


class DatabaseState(StrEnum):
    NEW = "new"
    UNSTAMPED_V1 = "complete_unstamped_v1"
    LEGACY_UNSTAMPED = "complete_unstamped_v1"
    MIGRATION_REQUIRED = "m005_001_migration_required"
    CURRENT = "current"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class DatabaseStatus:
    state: DatabaseState
    tables: frozenset[str]
    schema_version: int | None = None
    detail: str = ""
    recovery: str | None = None


@dataclass(frozen=True)
class DatabaseBackupReceipt:
    source_path: Path
    backup_path: Path
    sha256: str
    source_state: DatabaseState


class DatabaseBootstrapError(RuntimeError):
    def __init__(self, status: DatabaseStatus) -> None:
        self.status = status
        recovery = status.recovery or "manual recovery is required"
        super().__init__(
            f"database state {status.state.value} ({status.detail}) requires explicit recovery: "
            f"{recovery}; source was not modified"
        )


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _file_identity(path: Path) -> tuple[int, int, bytes]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, path.read_bytes()


def _columns_match(
    connection: sqlite3.Connection,
    expected_columns: dict[str, frozenset[str]],
) -> bool:
    for table, expected in expected_columns.items():
        columns = frozenset(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))
        if columns != expected:
            return False
    return True


def _v1_columns_match(connection: sqlite3.Connection) -> bool:
    return _columns_match(connection, V1_REQUIRED_COLUMNS)


def _m005_001_triggers_match(connection: sqlite3.Connection) -> bool:
    triggers = frozenset(
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' ORDER BY name"
        )
    )
    return triggers == M005_001_APPEND_ONLY_TRIGGERS


@contextmanager
def _classification_path(path: Path) -> Iterator[Path]:
    """Avoid touching live WAL shared-memory bytes while classifying a database."""

    wal = Path(f"{path}-wal")
    shm = Path(f"{path}-shm")
    if not wal.exists() and not shm.exists():
        yield path
        return
    tracked = tuple(candidate for candidate in (path, wal) if candidate.exists())
    before = {candidate.name: _file_identity(candidate) for candidate in tracked}
    with tempfile.TemporaryDirectory(prefix="corvus-db-classify-") as temporary_root:
        snapshot = Path(temporary_root) / path.name
        shutil.copyfile(path, snapshot)
        if wal.exists():
            shutil.copyfile(wal, Path(f"{snapshot}-wal"))
        after = {candidate.name: _file_identity(candidate) for candidate in tracked}
        if after != before:
            raise sqlite3.OperationalError(
                "database changed while its read-only snapshot was copied"
            )
        yield snapshot


def classify_database(path: Path) -> DatabaseStatus:
    """Classify SQLite state without creating the file or executing DDL."""

    if not path.exists() or path.stat().st_size == 0:
        return DatabaseStatus(
            DatabaseState.NEW,
            frozenset(),
            detail="database is missing or empty",
        )
    try:
        with (
            _classification_path(path) as inspected_path,
            closing(_connect_read_only(inspected_path)) as connection,
        ):
            tables = frozenset(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            )
            if tables == V1_REQUIRED_TABLES and _v1_columns_match(connection):
                return DatabaseStatus(
                    DatabaseState.UNSTAMPED_V1,
                    tables,
                    detail="complete V1 schema has no version stamp",
                    recovery=(
                        "create an integrity-checked SHA-256 backup, then explicitly "
                        "stamp/upgrade this V1 database"
                    ),
                )
            stamped_v1_tables = frozenset({*V1_REQUIRED_TABLES, SCHEMA_METADATA_TABLE})
            current_tables = frozenset(
                {*V1_REQUIRED_TABLES, *M005_001_REQUIRED_TABLES, SCHEMA_METADATA_TABLE}
            )
            if tables in {stamped_v1_tables, current_tables}:
                expected_columns = (
                    V1_REQUIRED_COLUMNS if tables == stamped_v1_tables else CURRENT_REQUIRED_COLUMNS
                )
                if not _columns_match(connection, expected_columns):
                    return DatabaseStatus(
                        DatabaseState.PARTIAL,
                        tables,
                        detail="database schema is missing required columns",
                        recovery="restore from a digest-verified backup; source was not modified",
                    )
                columns = {
                    row[1]
                    for row in connection.execute(f"PRAGMA table_info({SCHEMA_METADATA_TABLE})")
                }
                rows = connection.execute("SELECT schema_version FROM corvus_schema").fetchall()
                if columns == {"schema_version"} and len(rows) == 1:
                    schema_version = rows[0][0]
                    if tables == stamped_v1_tables and schema_version == LEGACY_SCHEMA_VERSION:
                        return DatabaseStatus(
                            DatabaseState.MIGRATION_REQUIRED,
                            tables,
                            schema_version=LEGACY_SCHEMA_VERSION,
                            detail=f"database requires {M005_001_MIGRATION}",
                            recovery=(
                                "create and verify the automatic pre-M005-001 backup, then "
                                "apply the transactional provenance migration"
                            ),
                        )
                    if (
                        tables == current_tables
                        and schema_version == CURRENT_SCHEMA_VERSION
                        and _m005_001_triggers_match(connection)
                    ):
                        return DatabaseStatus(
                            DatabaseState.CURRENT,
                            tables,
                            schema_version=CURRENT_SCHEMA_VERSION,
                            detail="database schema is current",
                        )
                    if isinstance(schema_version, int) and schema_version > CURRENT_SCHEMA_VERSION:
                        return DatabaseStatus(
                            DatabaseState.INCOMPATIBLE,
                            tables,
                            schema_version=schema_version,
                            detail=f"schema version {schema_version} is not supported",
                            recovery=(
                                "use a compatible Corvus release or restore from a "
                                "digest-verified backup"
                            ),
                        )
                return DatabaseStatus(
                    DatabaseState.PARTIAL,
                    tables,
                    detail="schema metadata, M005-001 tables, or append-only triggers are incomplete",
                    recovery="restore from a digest-verified backup; source was not modified",
                )
            if not tables:
                return DatabaseStatus(
                    DatabaseState.NEW,
                    tables,
                    detail="database contains no application tables",
                )
            return DatabaseStatus(
                DatabaseState.PARTIAL,
                tables,
                detail="database does not contain the complete V1 schema",
                recovery="restore from a digest-verified backup; source was not modified",
            )
    except (OSError, sqlite3.DatabaseError) as exc:
        return DatabaseStatus(
            DatabaseState.INCOMPATIBLE,
            frozenset(),
            detail=f"database is not readable as supported SQLite: {exc}",
            recovery="use a supported database or restore from a digest-verified backup",
        )


def _require_integrity(connection: sqlite3.Connection, *, label: str) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise DatabaseBootstrapError(
            DatabaseStatus(
                DatabaseState.INCOMPATIBLE,
                frozenset(),
                detail=f"{label} failed SQLite integrity check",
                recovery="restore from a digest-verified backup",
            )
        )


def m005_001_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.pre-m005-001.bak")


def _create_verified_backup(source: Path, backup: Path) -> str:
    sidecar = backup.with_suffix(f"{backup.suffix}.sha256")
    if backup.exists() or sidecar.exists():
        raise FileExistsError("database backup or digest sidecar already exists")
    backup.parent.mkdir(parents=True, exist_ok=True)
    temporary = backup.with_name(f".{backup.name}.backup-{uuid4().hex}.tmp")
    try:
        with closing(_connect_read_only(source)) as source_connection:
            _require_integrity(source_connection, label="source database")
            if not Path(f"{source}-wal").exists() and not Path(f"{source}-shm").exists():
                shutil.copyfile(source, temporary)
            else:
                with closing(sqlite3.connect(temporary)) as destination_connection:
                    source_connection.backup(destination_connection)
                    _require_integrity(destination_connection, label="database backup")
                    destination_connection.commit()
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        digest = sha256_file(temporary)
        os.replace(temporary, backup)
        atomic_write(sidecar, digest.encode("ascii"))
    finally:
        temporary.unlink(missing_ok=True)
    if sha256_file(backup) != digest:
        raise RuntimeError("database backup digest changed after publication")
    return digest


def _create_m005_001_triggers(connection: sqlite3.Connection) -> None:
    for table_name in sorted(M005_001_REQUIRED_TABLES):
        connection.execute(
            f"CREATE TRIGGER {table_name}_no_update BEFORE UPDATE ON {table_name} "
            "BEGIN SELECT RAISE(ABORT, 'M005-001 provenance is append-only'); END"
        )
        connection.execute(
            f"CREATE TRIGGER {table_name}_no_delete BEFORE DELETE ON {table_name} "
            "BEGIN SELECT RAISE(ABORT, 'M005-001 provenance is append-only'); END"
        )


def _create_m005_001_tables(connection: sqlite3.Connection, metadata: MetaData) -> None:
    dialect = sqlite_dialect.dialect()
    for table_name in sorted(M005_001_REQUIRED_TABLES):
        table = metadata.tables[table_name]
        connection.execute(str(CreateTable(table).compile(dialect=dialect)))
    _create_m005_001_triggers(connection)


def _migrate_m005_001(path: Path, metadata: MetaData) -> DatabaseStatus:
    status = classify_database(path)
    if status.state is not DatabaseState.MIGRATION_REQUIRED:
        raise DatabaseBootstrapError(status)
    _create_verified_backup(path, m005_001_backup_path(path))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = frozenset(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            )
            expected = frozenset({*V1_REQUIRED_TABLES, SCHEMA_METADATA_TABLE})
            version_rows = connection.execute("SELECT schema_version FROM corvus_schema").fetchall()
            if (
                tables != expected
                or not _v1_columns_match(connection)
                or version_rows != [(LEGACY_SCHEMA_VERSION,)]
            ):
                raise DatabaseBootstrapError(
                    DatabaseStatus(
                        DatabaseState.PARTIAL,
                        tables,
                        detail="schema changed before M005-001 migration",
                        recovery="restore from the verified pre-M005-001 backup",
                    )
                )
            _create_m005_001_tables(connection, metadata)
            connection.execute(
                "UPDATE corvus_schema SET schema_version = ?",
                (CURRENT_SCHEMA_VERSION,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    with path.open("rb+") as handle:
        os.fsync(handle.fileno())
    migrated = classify_database(path)
    if migrated.state is not DatabaseState.CURRENT:
        raise RuntimeError(f"M005-001 migration failed classification: {migrated.detail}")
    return migrated


def backup_and_stamp_v1(source: Path, backup: Path) -> DatabaseBackupReceipt:
    """Back up and explicitly stamp a complete legacy V1 database.

    The verified backup and its digest are durable before the source schema is modified.
    """

    status = classify_database(source)
    if status.state is not DatabaseState.UNSTAMPED_V1:
        raise DatabaseBootstrapError(status)
    digest = _create_verified_backup(source, backup)
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = frozenset(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            )
            if tables != V1_REQUIRED_TABLES or not _v1_columns_match(connection):
                raise DatabaseBootstrapError(
                    DatabaseStatus(
                        DatabaseState.PARTIAL,
                        tables,
                        detail="legacy schema changed before stamp",
                        recovery="restore from the verified backup; source was not stamped",
                    )
                )
            connection.execute("CREATE TABLE corvus_schema (schema_version INTEGER NOT NULL)")
            connection.execute(
                "INSERT INTO corvus_schema (schema_version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
            _create_m005_001_tables(connection, _resolved_metadata(None))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    with source.open("rb+") as handle:
        os.fsync(handle.fileno())

    stamped = classify_database(source)
    if stamped.state is not DatabaseState.CURRENT:
        raise RuntimeError(f"stamped database failed classification: {stamped.detail}")
    return DatabaseBackupReceipt(
        source_path=source,
        backup_path=backup,
        sha256=digest,
        source_state=status.state,
    )


def restore_database_backup(backup: Path, destination: Path) -> DatabaseStatus:
    """Verify and atomically publish a database backup without stamping or upgrading it."""

    sidecar = backup.with_suffix(f"{backup.suffix}.sha256")
    if destination.exists():
        raise FileExistsError("restore destination already exists")
    try:
        expected = sidecar.read_text(encoding="ascii").strip().casefold()
    except OSError as exc:
        raise DatabaseBootstrapError(
            DatabaseStatus(
                DatabaseState.INCOMPATIBLE,
                frozenset(),
                detail="database backup digest sidecar is unavailable",
                recovery="supply the original SHA-256 sidecar",
            )
        ) from exc
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise DatabaseBootstrapError(
            DatabaseStatus(
                DatabaseState.INCOMPATIBLE,
                frozenset(),
                detail="database backup digest sidecar is malformed",
                recovery="supply the original SHA-256 sidecar",
            )
        )
    if not backup.is_file() or sha256_file(backup) != expected:
        raise DatabaseBootstrapError(
            DatabaseStatus(
                DatabaseState.INCOMPATIBLE,
                frozenset(),
                detail="database backup SHA-256 digest mismatch",
                recovery="use the untampered backup matching the sidecar",
            )
        )
    backup_status = classify_database(backup)
    if backup_status.state not in {
        DatabaseState.UNSTAMPED_V1,
        DatabaseState.MIGRATION_REQUIRED,
        DatabaseState.CURRENT,
    }:
        raise DatabaseBootstrapError(backup_status)
    with closing(_connect_read_only(backup)) as connection:
        _require_integrity(connection, label="database backup")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.restore-{uuid4().hex}.tmp")
    try:
        shutil.copyfile(backup, temporary)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        if sha256_file(temporary) != expected:
            raise RuntimeError("restored temporary database digest changed during copy")
        restored_status = classify_database(temporary)
        if restored_status != backup_status:
            raise RuntimeError("restored temporary database classification changed during copy")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return classify_database(destination)


def _resolved_metadata(metadata: MetaData | None) -> MetaData:
    if metadata is not None:
        return metadata
    from corvus.store import Base

    return Base.metadata


def _create_schema(path: Path, metadata: MetaData) -> None:
    dialect = sqlite_dialect.dialect()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for table in sorted(metadata.sorted_tables, key=lambda item: item.name):
                connection.execute(str(CreateTable(table).compile(dialect=dialect)))
            indexes = sorted(
                (index for table in metadata.tables.values() for index in table.indexes),
                key=lambda item: item.name or "",
            )
            for index in indexes:
                connection.execute(str(CreateIndex(index).compile(dialect=dialect)))
            _create_m005_001_triggers(connection)
            connection.execute(
                f"CREATE TABLE {SCHEMA_METADATA_TABLE} (schema_version INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO corvus_schema (schema_version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    with path.open("rb+") as handle:
        os.fsync(handle.fileno())


def initialize_database(path: Path, metadata: MetaData | None = None) -> DatabaseStatus:
    """Atomically create and stamp a database only when classification is ``new``."""

    initial = classify_database(path)
    if initial.state is not DatabaseState.NEW:
        raise RuntimeError(
            f"database initialization requires state new, found {initial.state.value}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.initialize-{uuid4().hex}.tmp")
    try:
        _create_schema(temporary, _resolved_metadata(metadata))
        created = classify_database(temporary)
        if created.state is not DatabaseState.CURRENT:
            raise RuntimeError(f"initialized database failed classification: {created.detail}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return classify_database(path)


def bootstrap_database(path: Path, metadata: MetaData | None = None) -> DatabaseStatus:
    """Open the current schema or initialize a new database; all other states fail closed."""

    status = classify_database(path)
    if status.state is DatabaseState.NEW:
        return initialize_database(path, metadata)
    if status.state is DatabaseState.MIGRATION_REQUIRED:
        return _migrate_m005_001(path, _resolved_metadata(metadata))
    if status.state is DatabaseState.CURRENT:
        return status
    raise DatabaseBootstrapError(status)
