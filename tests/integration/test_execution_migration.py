from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command

from corvus.database import DatabaseState, classify_database
from corvus.domain.identity import Principal, PrincipalKind, Workspace, WorkspaceMembership
from corvus.infrastructure.db import (
    M2_CONVERSATIONS_REVISION,
    M2_DURABLE_EXECUTION_REVISION,
    _alembic_config_url,
    downgrade_database,
    upgrade_database,
)
from corvus.infrastructure.repositories.identity_scope import IdentityScopeRepository
from corvus.store import TraceStore

_DURABLE_EXECUTION_REVISION = "m2_004_durable_execution"
_DURABLE_EXECUTION_MANIFEST_ID = "00000000-0000-4000-8000-000000000013"
_DURABLE_EXECUTION_TABLES = frozenset(
    {
        "agent_run_state_versions",
        "run_checkpoints",
        "run_checkpoint_artifacts",
        "run_step_leases",
        "run_step_versions",
        "run_steps",
    }
)


def _base_database(path: Path) -> None:
    TraceStore(path).engine.dispose()


def test_execution_upgrade_adds_manifest_families_and_refuses_populated_downgrade(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)

    assert upgrade_database(database) == _DURABLE_EXECUTION_REVISION
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        families = {
            row[0]
            for row in connection.execute(
                "SELECT family_name FROM authority_state_root_leaf_families "
                "WHERE manifest_version_id = ?",
                (_DURABLE_EXECUTION_MANIFEST_ID,),
            )
        }
        connection.execute(
            "INSERT INTO agent_run_state_versions "
            "(workspace_id, run_id, version, state, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, 1, 'pending', ?, ?, ?)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                "2026-07-26T00:00:00+00:00",
                "2026-07-26T00:00:00+00:00",
                "a" * 64,
            ),
        )
    assert _DURABLE_EXECUTION_TABLES.issubset(tables)
    assert _DURABLE_EXECUTION_TABLES.issubset(families)

    with pytest.raises(RuntimeError, match="durable_execution_history_present"):
        downgrade_database(database, M2_CONVERSATIONS_REVISION)


def test_execution_schema_enforces_states_versions_fences_and_one_active_lease(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    workspace_id = "10000000-0000-4000-8000-000000000001"
    run_id = "20000000-0000-4000-8000-000000000001"
    step_id = "30000000-0000-4000-8000-000000000001"
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO agent_run_state_versions "
                "(workspace_id, run_id, version, state, created_at, updated_at, canonical_digest) "
                "VALUES (?, ?, 1, 'unknown', ?, ?, ?)",
                (workspace_id, run_id, timestamp, timestamp, "a" * 64),
            )
        connection.execute(
            "INSERT INTO run_steps "
            "(workspace_id, run_id, id, step_key, ordinal, created_at) "
            "VALUES (?, ?, ?, 'plan', 1, ?)",
            (workspace_id, run_id, step_id, timestamp),
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 1, 'ready', 1, 0, 0, ?, ?, ?)",
            (workspace_id, run_id, step_id, timestamp, timestamp, "b" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_step_versions "
                "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
                "attempt_count, created_at, updated_at, canonical_digest) "
                "VALUES (?, ?, ?, 2, 'running', 1, 0, 1, ?, ?, ?)",
                (workspace_id, run_id, step_id, timestamp, timestamp, "c" * 64),
            )
        connection.execute(
            "INSERT INTO run_step_leases "
            "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
            "acquired_at, heartbeat_at, expires_at, released_at) "
            "VALUES (?, ?, ?, 1, 'worker-a', ?, ?, ?, ?, NULL)",
            (
                workspace_id,
                run_id,
                step_id,
                "d" * 64,
                timestamp,
                timestamp,
                "2026-07-26T00:05:00+00:00",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_step_leases "
                "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
                "acquired_at, heartbeat_at, expires_at, released_at) "
                "VALUES (?, ?, ?, 2, 'worker-b', ?, ?, ?, ?, NULL)",
                (
                    workspace_id,
                    run_id,
                    step_id,
                    "e" * 64,
                    timestamp,
                    timestamp,
                    "2026-07-26T00:05:00+00:00",
                ),
            )


def test_execution_state_checkpoint_history_is_immutable_and_leases_cannot_be_deleted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    workspace_id = "10000000-0000-4000-8000-000000000001"
    run_id = "20000000-0000-4000-8000-000000000001"
    step_id = "30000000-0000-4000-8000-000000000001"
    checkpoint_id = "40000000-0000-4000-8000-000000000001"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO agent_run_state_versions "
            "(workspace_id, run_id, version, state, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, 1, 'pending', ?, ?, ?)",
            (workspace_id, run_id, timestamp, timestamp, "a" * 64),
        )
        connection.execute(
            "INSERT INTO run_checkpoints "
            "(workspace_id, run_id, step_id, id, checkpoint_version, run_state, step_state, "
            "step_fence, step_version, completed_dependency_step_ids_json, output_ref_ids_json, "
            "retry_count, attempt_count, last_accepted_event_sequence, "
            "last_accepted_event_digest, next_transition, created_at, canonical_digest) "
            "VALUES (?, ?, ?, ?, 1, 'pending', 'ready', 1, 1, '[]', '[]', "
            "0, 0, 0, ?, 'dispatch', ?, ?)",
            (
                workspace_id,
                run_id,
                step_id,
                checkpoint_id,
                "0" * 64,
                timestamp,
                "b" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO run_step_leases "
            "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
            "acquired_at, heartbeat_at, expires_at, released_at) "
            "VALUES (?, ?, ?, 1, 'worker-a', ?, ?, ?, ?, NULL)",
            (
                workspace_id,
                run_id,
                step_id,
                "c" * 64,
                timestamp,
                timestamp,
                "2026-07-26T00:05:00+00:00",
            ),
        )
        for statement in (
            "UPDATE agent_run_state_versions SET state = 'running'",
            "DELETE FROM agent_run_state_versions",
            "UPDATE run_checkpoints SET next_transition = 'wait'",
            "DELETE FROM run_checkpoints",
            "DELETE FROM run_step_leases",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)


def test_empty_execution_downgrade_and_reupgrade_are_deterministic(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    assert upgrade_database(database) == M2_DURABLE_EXECUTION_REVISION
    assert downgrade_database(database, M2_CONVERSATIONS_REVISION) == M2_CONVERSATIONS_REVISION
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        manifests = connection.execute(
            "SELECT schema_version FROM authority_state_root_manifests ORDER BY schema_version"
        ).fetchall()
    assert _DURABLE_EXECUTION_TABLES.isdisjoint(tables)
    assert manifests[-1] == (9,)
    assert upgrade_database(database) == M2_DURABLE_EXECUTION_REVISION


def test_execution_downgrade_to_conversations_preserves_conversation_history(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    workspace = Workspace(name="Preserved conversations")
    principal = Principal(
        kind=PrincipalKind.USER,
        external_provider="test",
        external_subject="durable-downgrade",
        display_name="Durable downgrade",
    )
    identities = IdentityScopeRepository(database)
    identities.append_workspace(workspace)
    identities.append_principal(principal)
    identities.append_membership(
        WorkspaceMembership(workspace_id=workspace.id, principal_id=principal.id, role="owner")
    )
    identities.close()
    thread_id = "20000000-0000-4000-8000-000000000001"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO threads "
            "(workspace_id, id, workspace_version, creator_principal_id, "
            "creator_membership_version, created_at) VALUES (?, ?, 1, ?, 1, ?)",
            (
                str(workspace.id),
                thread_id,
                str(principal.id),
                "2026-07-26T00:00:00+00:00",
            ),
        )

    assert downgrade_database(database, M2_CONVERSATIONS_REVISION) == M2_CONVERSATIONS_REVISION
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT workspace_id, id FROM threads WHERE id = ?", (thread_id,)
        ).fetchone() == (str(workspace.id), thread_id)


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TRIGGER run_checkpoints_no_update",
        "DROP INDEX ix_run_step_leases_recovery",
        "DROP INDEX uq_run_step_leases_active",
    ],
)
def test_execution_classifier_requires_history_guards_and_recovery_indexes(
    tmp_path: Path,
    statement: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    assert classify_database(database).state is DatabaseState.CURRENT
    with sqlite3.connect(database) as connection:
        connection.execute(statement)
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_wrong_active_lease_scope(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX uq_run_step_leases_active")
        connection.execute(
            "CREATE UNIQUE INDEX uq_run_step_leases_active ON run_step_leases(step_id) "
            "WHERE released_at IS NULL"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_wrong_recovery_index_definition(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX ix_run_step_leases_recovery")
        connection.execute(
            "CREATE INDEX ix_run_step_leases_recovery ON run_step_leases(step_id)"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_same_name_no_op_history_trigger(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER run_checkpoints_no_update")
        connection.execute(
            "CREATE TRIGGER run_checkpoints_no_update BEFORE UPDATE ON run_checkpoints "
            "WHEN 0 BEGIN SELECT RAISE(ABORT, 'run checkpoints are immutable'); END"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_weakened_table_foreign_key_action(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'run_step_versions'"
        ).fetchone()
        assert table_sql is not None
        weakened_sql = str(table_sql[0]).replace(
            "ON DELETE RESTRICT",
            "ON DELETE CASCADE",
        )
        assert weakened_sql != table_sql[0]
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'run_step_versions'",
            (weakened_sql,),
        )
        connection.execute("PRAGMA writable_schema=OFF")
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_same_name_no_op_lease_guard(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER run_step_leases_guard_update")
        connection.execute(
            "CREATE TRIGGER run_step_leases_guard_update BEFORE UPDATE ON run_step_leases "
            "BEGIN SELECT 1; END"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_foreign_keys_are_workspace_composite(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        for table_name in _DURABLE_EXECUTION_TABLES:
            constraints: dict[int, set[str]] = {}
            for row in connection.execute(f'PRAGMA foreign_key_list("{table_name}")'):
                constraints.setdefault(int(row[0]), set()).add(str(row[3]))
            assert constraints
            assert all("workspace_id" in columns for columns in constraints.values())


@pytest.mark.parametrize(
    "mutation",
    ["identity", "expiry_decrease", "reactivate", "after_release"],
)
def test_execution_lease_update_guard_rejects_history_rewrites(
    tmp_path: Path,
    mutation: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO run_step_leases "
            "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
            "acquired_at, heartbeat_at, expires_at, released_at) "
            "VALUES (?, ?, ?, 1, 'worker-a', ?, ?, ?, ?, NULL)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                "30000000-0000-4000-8000-000000000001",
                "a" * 64,
                timestamp,
                timestamp,
                "2026-07-26T00:05:00+00:00",
            ),
        )
        if mutation in {"reactivate", "after_release"}:
            connection.execute(
                "UPDATE run_step_leases SET released_at = "
                "'2026-07-26T00:01:00+00:00'"
            )
        statements = {
            "identity": "UPDATE run_step_leases SET fence = 2, worker_id = 'worker-b'",
            "expiry_decrease": (
                "UPDATE run_step_leases SET expires_at = '2026-07-26T00:04:00+00:00'"
            ),
            "reactivate": "UPDATE run_step_leases SET released_at = NULL",
            "after_release": (
                "UPDATE run_step_leases SET heartbeat_at = '2026-07-26T00:02:00+00:00'"
            ),
        }
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statements[mutation])


def test_execution_lease_update_guard_allows_monotonic_expiry_and_one_release(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO run_step_leases "
            "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
            "acquired_at, heartbeat_at, expires_at, released_at) "
            "VALUES (?, ?, ?, 1, 'worker-a', ?, ?, ?, ?, NULL)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                "30000000-0000-4000-8000-000000000001",
                "a" * 64,
                timestamp,
                timestamp,
                "2026-07-26T00:05:00+00:00",
            ),
        )
        connection.execute(
            "UPDATE run_step_leases SET heartbeat_at = ?, expires_at = ?",
            ("2026-07-26T00:01:00+00:00", "2026-07-26T00:10:00+00:00"),
        )
        connection.execute(
            "UPDATE run_step_leases SET released_at = ?",
            ("2026-07-26T00:02:00+00:00",),
        )
        assert connection.execute(
            "SELECT heartbeat_at, expires_at, released_at FROM run_step_leases"
        ).fetchone() == (
            "2026-07-26T00:01:00+00:00",
            "2026-07-26T00:10:00+00:00",
            "2026-07-26T00:02:00+00:00",
        )


def test_execution_migration_renders_portable_offline_postgres_ddl(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _alembic_config_url("postgresql+psycopg://corvus:test@127.0.0.1/corvus_test")
    command.upgrade(config, "head", sql=True)
    rendered = capsys.readouterr().out.casefold()
    assert "create table agent_run_state_versions" in rendered
    assert "create table run_checkpoints" in rendered
    assert "foreign key(workspace_id, run_id, step_id, step_version, step_fence)" in rendered
    assert "references run_step_versions" in rendered
    assert "create unique index uq_run_step_leases_active" in rendered
    assert "where released_at is null" in rendered
    assert "create trigger run_checkpoints_no_update" in rendered
    assert "create trigger run_step_leases_no_delete" in rendered
    assert "create function run_step_leases_guard_update_fn()" in rendered
    assert "new.expires_at < old.expires_at" in rendered
    assert "create trigger run_step_leases_guard_update" in rendered
