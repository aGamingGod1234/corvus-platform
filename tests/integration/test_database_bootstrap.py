from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import corvus.database as database_module
from corvus.database import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_METADATA_TABLE,
    V1_REQUIRED_TABLES,
    DatabaseBootstrapError,
    DatabaseState,
    classify_database,
)
from corvus.security import sha256_file
from corvus.store import Base, TraceStore


def _schema_rows(path: Path) -> list[tuple[str, str, str]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()


def _source_snapshot(path: Path) -> dict[str, tuple[str, int, int]]:
    snapshot: dict[str, tuple[str, int, int]] = {}
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            stat = candidate.stat()
            snapshot[candidate.name] = (sha256_file(candidate), stat.st_size, stat.st_mtime_ns)
    return snapshot


def test_new_database_initializes_and_stamps_once(tmp_path: Path) -> None:
    database = tmp_path / "state" / "corvus.db"

    assert classify_database(database).state is DatabaseState.NEW

    first = TraceStore(database)
    first.engine.dispose()
    first_schema = _schema_rows(database)

    status = classify_database(database)
    assert status.state is DatabaseState.CURRENT
    assert status.schema_version == CURRENT_SCHEMA_VERSION
    assert status.tables == frozenset({*V1_REQUIRED_TABLES, SCHEMA_METADATA_TABLE})

    second = TraceStore(database)
    second.engine.dispose()

    assert _schema_rows(database) == first_schema
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT schema_version FROM corvus_schema").fetchall() == [
            (CURRENT_SCHEMA_VERSION,)
        ]


def test_complete_unstamped_v1_refuses_ordinary_open_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()

    with sqlite3.connect(database) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA user_version=7")
        writer.commit()
        before = _source_snapshot(database)

        status = classify_database(database)
        assert status.state is DatabaseState.UNSTAMPED_V1

        with pytest.raises(
            DatabaseBootstrapError,
            match=(
                "complete_unstamped_v1.*integrity-checked SHA-256 backup.*source was not modified"
            ),
        ):
            TraceStore(database)

        assert _source_snapshot(database) == before


def test_partial_v1_schema_fails_closed_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "partial.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE run_events DROP COLUMN event_type")
    before = _source_snapshot(database)

    status = classify_database(database)
    assert status.state is DatabaseState.PARTIAL
    assert status.recovery == "restore from a digest-verified backup; source was not modified"

    with pytest.raises(
        DatabaseBootstrapError, match="database state partial.*source was not modified"
    ):
        TraceStore(database)

    assert _source_snapshot(database) == before


def test_future_schema_version_is_incompatible_and_not_mutated(tmp_path: Path) -> None:
    database = tmp_path / "future.db"
    store = TraceStore(database)
    store.engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE corvus_schema SET schema_version = ?", (CURRENT_SCHEMA_VERSION + 1,)
        )
    before = _source_snapshot(database)

    status = classify_database(database)
    assert status.state is DatabaseState.INCOMPATIBLE
    assert status.schema_version == CURRENT_SCHEMA_VERSION + 1

    with pytest.raises(DatabaseBootstrapError, match="database state incompatible"):
        TraceStore(database)

    assert _source_snapshot(database) == before


def test_explicit_backup_precedes_legacy_stamp(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    backup = tmp_path / "backups" / "legacy.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()
    before_schema = _schema_rows(database)

    receipt = database_module.backup_and_stamp_v1(database, backup)

    assert receipt.backup_path == backup
    assert receipt.sha256 == sha256_file(backup)
    assert backup.with_suffix(".db.sha256").read_text(encoding="ascii") == receipt.sha256
    assert _schema_rows(backup) == before_schema
    assert classify_database(backup).state is DatabaseState.UNSTAMPED_V1
    assert classify_database(database).state is DatabaseState.CURRENT
    TraceStore(database).engine.dispose()


def test_restore_verifies_backup_digest_before_publish(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    backup = tmp_path / "backups" / "legacy.db"
    restored = tmp_path / "restored" / "corvus.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()
    receipt = database_module.backup_and_stamp_v1(database, backup)

    status = database_module.restore_database_backup(backup, restored)

    assert status.state is DatabaseState.UNSTAMPED_V1
    assert sha256_file(restored) == receipt.sha256
    assert _schema_rows(restored) == _schema_rows(backup)


def test_restore_rejects_tampered_backup_without_publishing(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    backup = tmp_path / "backups" / "legacy.db"
    restored = tmp_path / "restored" / "corvus.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()
    database_module.backup_and_stamp_v1(database, backup)
    with backup.open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(DatabaseBootstrapError, match="SHA-256 digest mismatch"):
        database_module.restore_database_backup(backup, restored)

    assert not restored.exists()


def test_malformed_schema_stamp_is_partial_and_not_mutated(tmp_path: Path) -> None:
    database = tmp_path / "malformed.db"
    store = TraceStore(database)
    store.engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO corvus_schema (schema_version) VALUES (?)",
            (CURRENT_SCHEMA_VERSION,),
        )
    before = _source_snapshot(database)

    status = classify_database(database)
    assert status.state is DatabaseState.PARTIAL
    with pytest.raises(DatabaseBootstrapError, match="database state partial"):
        TraceStore(database)
    assert _source_snapshot(database) == before
