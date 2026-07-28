from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command

from corvus.database import DatabaseState, classify_database
from corvus.domain.identity import Principal, PrincipalKind, Workspace, WorkspaceMembership
from corvus.infrastructure.db import (
    M2_CONVERSATIONS_REVISION,
    M2_DURABLE_EXECUTION_REVISION,
    M2_EXECUTION_BINDING_REVISION,
    _alembic_config_url,
    downgrade_database,
    upgrade_database,
)
from corvus.infrastructure.migrations.versions import m2_005_execution_binding
from corvus.infrastructure.repositories.identity_scope import IdentityScopeRepository
from corvus.store import TraceStore

_DURABLE_EXECUTION_REVISION = "m2_004_durable_execution"
_DURABLE_EXECUTION_MANIFEST_ID = "00000000-0000-4000-8000-000000000013"
_EXECUTION_BINDING_REVISION = "m2_005_execution_binding"
_EXECUTION_BINDING_MANIFEST_ID = "00000000-0000-4000-8000-000000000014"
_EXECUTION_BINDING_TABLE = "agent_run_execution_bindings"
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


def test_execution_binding_upgrade_adds_authoritative_append_only_family(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)

    assert upgrade_database(database) == _EXECUTION_BINDING_REVISION
    assert classify_database(database).state is DatabaseState.CURRENT
    with sqlite3.connect(database) as connection:
        columns = {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute(f"PRAGMA table_info({_EXECUTION_BINDING_TABLE})")
        }
        foreign_keys = connection.execute(
            f"PRAGMA foreign_key_list({_EXECUTION_BINDING_TABLE})"
        ).fetchall()
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?",
                (_EXECUTION_BINDING_TABLE,),
            )
        }
        current_families = {
            row[0]
            for row in connection.execute(
                "SELECT family_name FROM authority_state_root_leaf_families "
                "WHERE manifest_version_id = ?",
                (_EXECUTION_BINDING_MANIFEST_ID,),
            )
        }
        historical_families = {
            row[0]
            for row in connection.execute(
                "SELECT family_name FROM authority_state_root_leaf_families "
                "WHERE manifest_version_id = ?",
                (_DURABLE_EXECUTION_MANIFEST_ID,),
            )
        }

    assert columns == {
        "workspace_id": ("VARCHAR(36)", 1, 1),
        "run_id": ("VARCHAR(36)", 1, 2),
        "immutable_request_digest": ("VARCHAR(64)", 1, 0),
        "created_at": ("VARCHAR(40)", 1, 0),
        "canonical_digest": ("VARCHAR(64)", 1, 0),
    }
    assert {
        (row[2], row[3], row[4], row[6])
        for row in foreign_keys
    } == {
        ("agent_runs", "workspace_id", "workspace_id", "RESTRICT"),
        ("agent_runs", "run_id", "id", "RESTRICT"),
    }
    assert triggers == {
        "agent_run_execution_bindings_no_delete",
        "agent_run_execution_bindings_no_update",
    }
    assert _EXECUTION_BINDING_TABLE in current_families
    assert _EXECUTION_BINDING_TABLE not in historical_families


def test_execution_binding_schema_rejects_invalid_digests_and_history_rewrites(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    binding = (
        "10000000-0000-4000-8000-000000000001",
        "20000000-0000-4000-8000-000000000001",
        "a" * 64,
        "2026-07-26T00:00:00+00:00",
        "b" * 64,
    )

    with sqlite3.connect(database) as connection:
        for digest_column in ("immutable_request_digest", "canonical_digest"):
            invalid = list(binding)
            invalid[2 if digest_column == "immutable_request_digest" else 4] = "short"
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO agent_run_execution_bindings "
                    "(workspace_id, run_id, immutable_request_digest, created_at, "
                    "canonical_digest) VALUES (?, ?, ?, ?, ?)",
                    invalid,
                )
        connection.execute(
            "INSERT INTO agent_run_execution_bindings "
            "(workspace_id, run_id, immutable_request_digest, created_at, canonical_digest) "
            "VALUES (?, ?, ?, ?, ?)",
            binding,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE agent_run_execution_bindings SET immutable_request_digest = ?",
                ("c" * 64,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM agent_run_execution_bindings")


def test_populated_execution_binding_downgrade_refuses_before_mutation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO agent_run_execution_bindings "
            "(workspace_id, run_id, immutable_request_digest, created_at, canonical_digest) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                "a" * 64,
                "2026-07-26T00:00:00+00:00",
                "b" * 64,
            ),
        )

    with pytest.raises(RuntimeError, match="execution_binding_history_present"):
        downgrade_database(database, M2_DURABLE_EXECUTION_REVISION)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            M2_EXECUTION_BINDING_REVISION,
        )
        assert connection.execute(
            "SELECT immutable_request_digest FROM agent_run_execution_bindings"
        ).fetchone() == ("a" * 64,)
        assert connection.execute(
            "SELECT COUNT(*) FROM authority_state_root_manifests WHERE id = ?",
            (_EXECUTION_BINDING_MANIFEST_ID,),
        ).fetchone() == (1,)


def test_empty_execution_binding_downgrade_preserves_v10_and_reupgrades(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)

    assert (
        downgrade_database(database, M2_DURABLE_EXECUTION_REVISION)
        == M2_DURABLE_EXECUTION_REVISION
    )
    assert classify_database(database).state is DatabaseState.CURRENT
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert _EXECUTION_BINDING_TABLE not in tables
        assert connection.execute(
            "SELECT COUNT(*) FROM authority_state_root_manifests WHERE id = ?",
            (_EXECUTION_BINDING_MANIFEST_ID,),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM authority_state_root_manifests WHERE id = ?",
            (_DURABLE_EXECUTION_MANIFEST_ID,),
        ).fetchone() == (1,)

    assert upgrade_database(database) == M2_EXECUTION_BINDING_REVISION
    assert classify_database(database).state is DatabaseState.CURRENT


def test_postgres_execution_binding_downgrade_locks_before_history_check_and_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations: list[tuple[str, str]] = []

    class _Result:
        @staticmethod
        def scalar_one() -> int:
            return 0

    class _Bind:
        dialect = SimpleNamespace(name="postgresql")

        @staticmethod
        def execute(statement: object, parameters: object = None) -> _Result:
            del parameters
            operations.append(("sql", " ".join(str(statement).split())))
            return _Result()

    monkeypatch.setattr(
        m2_005_execution_binding.op,
        "get_context",
        lambda: SimpleNamespace(as_sql=False),
    )
    monkeypatch.setattr(m2_005_execution_binding.op, "get_bind", _Bind)
    monkeypatch.setattr(
        m2_005_execution_binding.op,
        "drop_table",
        lambda table_name: operations.append(("drop_table", table_name)),
    )
    monkeypatch.setattr(
        m2_005_execution_binding,
        "drop_immutable_triggers",
        lambda table_name: operations.append(("drop_triggers", table_name)),
    )
    monkeypatch.setattr(
        m2_005_execution_binding,
        "create_immutable_triggers",
        lambda table_name, label: operations.append(
            ("create_triggers", f"{table_name}:{label}")
        ),
    )

    m2_005_execution_binding.downgrade()

    assert operations[0] == (
        "sql",
        "LOCK TABLE agent_run_execution_bindings IN ACCESS EXCLUSIVE MODE",
    )
    assert operations[1] == (
        "sql",
        "SELECT COUNT(*) FROM agent_run_execution_bindings",
    )
    assert operations.index(("drop_table", "agent_run_execution_bindings")) > 1


def test_execution_upgrade_adds_manifest_families_and_refuses_populated_downgrade(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)

    assert upgrade_database(database) == _EXECUTION_BINDING_REVISION
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
        for kind, input_digest, parent_step_id in (
            ("", "9" * 64, None),
            ("x" * 101, "9" * 64, None),
            ("model", "short", None),
            ("model", "9" * 64, step_id),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO run_steps "
                    "(workspace_id, run_id, id, step_key, ordinal, kind, input_digest, "
                    "parent_step_id, created_at) VALUES (?, ?, ?, 'plan', 1, ?, ?, ?, ?)",
                    (
                        workspace_id,
                        run_id,
                        step_id,
                        kind,
                        input_digest,
                        parent_step_id,
                        timestamp,
                    ),
                )
        connection.execute(
            "INSERT INTO run_steps "
            "(workspace_id, run_id, id, step_key, ordinal, kind, input_digest, "
            "parent_step_id, created_at) VALUES (?, ?, ?, 'plan', 1, 'model', ?, NULL, ?)",
            (workspace_id, run_id, step_id, "9" * 64, timestamp),
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 1, 'ready', 1, 0, 0, ?, ?, ?)",
            (workspace_id, run_id, step_id, timestamp, timestamp, "b" * 64),
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 2, 'running', 1, 0, 1, ?, ?, ?)",
            (workspace_id, run_id, step_id, timestamp, timestamp, "c" * 64),
        )
        assert connection.execute(
            "SELECT version, fence FROM run_step_versions "
            "WHERE workspace_id = ? AND step_id = ? ORDER BY version",
            (workspace_id, step_id),
        ).fetchall() == [(1, 1), (2, 1)]
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
        connection.execute(
            "UPDATE run_step_leases SET released_at = ? "
            "WHERE workspace_id = ? AND run_id = ? AND step_id = ? AND fence = 1",
            (timestamp, workspace_id, run_id, step_id),
        )
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
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_step_leases "
                "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
                "acquired_at, heartbeat_at, expires_at, released_at) "
                "VALUES (?, ?, ?, 1, 'worker-c', ?, ?, ?, ?, ?)",
                (
                    workspace_id,
                    run_id,
                    step_id,
                    "f" * 64,
                    timestamp,
                    timestamp,
                    "2026-07-26T00:05:00+00:00",
                    timestamp,
                ),
            )
        assert connection.execute(
            "SELECT fence, released_at FROM run_step_leases ORDER BY fence"
        ).fetchall() == [(1, timestamp), (2, None)]


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
            "step_fence, step_version, request_context_id, authorization_snapshot_id, "
            "completed_dependency_step_ids_json, output_ref_ids_json, retry_count, "
            "attempt_count, last_accepted_event_sequence, "
            "last_accepted_event_digest, next_transition, created_at, canonical_digest) "
            "VALUES (?, ?, ?, ?, 1, 'pending', 'ready', 1, 1, ?, ?, '[]', '[]', "
            "0, 0, 0, ?, 'dispatch', ?, ?)",
            (
                workspace_id,
                run_id,
                step_id,
                checkpoint_id,
                "50000000-0000-4000-8000-000000000001",
                "60000000-0000-4000-8000-000000000001",
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
    assert upgrade_database(database) == M2_EXECUTION_BINDING_REVISION
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
    assert upgrade_database(database) == M2_EXECUTION_BINDING_REVISION


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
        "DROP TRIGGER agent_run_execution_bindings_no_update",
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


def test_execution_binding_classifier_rejects_weakened_digest_constraint(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (_EXECUTION_BINDING_TABLE,),
        ).fetchone()
        assert table_sql is not None
        weakened_sql = str(table_sql[0]).replace(
            "length(canonical_digest) = 64",
            "length(canonical_digest) >= 64",
        )
        assert weakened_sql != table_sql[0]
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = ?",
            (weakened_sql, _EXECUTION_BINDING_TABLE),
        )
        connection.execute("PRAGMA writable_schema=OFF")
    assert classify_database(database).state is DatabaseState.PARTIAL


@pytest.mark.parametrize(
    "statement",
    [
        (
            "CREATE TRIGGER agent_run_execution_bindings_block_insert "
            "BEFORE INSERT ON agent_run_execution_bindings "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        ),
        (
            "CREATE UNIQUE INDEX uq_agent_run_execution_bindings_digest "
            "ON agent_run_execution_bindings(immutable_request_digest)"
        ),
    ],
)
def test_execution_binding_classifier_rejects_unexpected_table_owned_controls(
    tmp_path: Path,
    statement: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
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


def test_execution_classifier_rejects_neutralized_active_lease_predicate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX uq_run_step_leases_active")
        connection.execute(
            "CREATE UNIQUE INDEX uq_run_step_leases_active ON run_step_leases "
            "(workspace_id, run_id, step_id) WHERE released_at IS NULL AND 0"
        )
        for fence, token in ((1, "a" * 64), (2, "b" * 64)):
            connection.execute(
                "INSERT INTO run_step_leases "
                "(workspace_id, run_id, step_id, fence, worker_id, lease_token_digest, "
                "acquired_at, heartbeat_at, expires_at, released_at) "
                "VALUES (?, ?, ?, ?, 'worker-a', ?, ?, ?, ?, NULL)",
                (
                    "10000000-0000-4000-8000-000000000001",
                    "20000000-0000-4000-8000-000000000001",
                    "30000000-0000-4000-8000-000000000001",
                    fence,
                    token,
                    timestamp,
                    timestamp,
                    "2026-07-26T00:05:00+00:00",
                ),
            )
        assert connection.execute("SELECT COUNT(*) FROM run_step_leases").fetchone() == (2,)
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_normalizes_only_identifier_quoting_case_and_whitespace(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX uq_run_step_leases_active")
        connection.execute(
            'CrEaTe   UnIqUe InDeX "uq_run_step_leases_active" '
            'ON "run_step_leases" '
            '("workspace_id", "run_id", "step_id") '
            'WhErE "released_at" Is NuLl'
        )
    assert classify_database(database).state is DatabaseState.CURRENT


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


@pytest.mark.parametrize(
    "columns",
    [
        "workspace_id, run_id, step_id, fence",
        "fence, step_id, run_id, workspace_id",
    ],
)
def test_execution_classifier_rejects_unique_step_version_fence_index(
    tmp_path: Path,
    columns: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE UNIQUE INDEX accidentally_unique_step_version_fence "
            f"ON run_step_versions({columns})"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_rejects_three_column_step_fence_uniqueness(
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
        connection.execute(
            "CREATE UNIQUE INDEX accidentally_unique_step_fence "
            "ON run_step_versions(workspace_id, step_id, fence)"
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 1, 'ready', 1, 0, 0, ?, ?, ?)",
            (workspace_id, run_id, step_id, timestamp, timestamp, "a" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_step_versions "
                "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
                "attempt_count, created_at, updated_at, canonical_digest) "
                "VALUES (?, ?, ?, 2, 'running', 1, 0, 1, ?, ?, ?)",
                (workspace_id, run_id, step_id, timestamp, timestamp, "b" * 64),
            )
    assert classify_database(database).state is DatabaseState.PARTIAL


@pytest.mark.parametrize(
    "columns",
    [
        "workspace_id, run_id, step_id",
        "workspace_id, step_id",
    ],
)
def test_execution_classifier_rejects_unique_step_identity_without_version(
    tmp_path: Path,
    columns: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    workspace_id = "10000000-0000-4000-8000-000000000001"
    run_id = "20000000-0000-4000-8000-000000000001"
    step_id = "30000000-0000-4000-8000-000000000001"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE UNIQUE INDEX accidentally_unique_step_identity "
            f"ON run_step_versions({columns})"
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 1, 'ready', 1, 0, 0, ?, ?, ?)",
            (workspace_id, run_id, step_id, timestamp, timestamp, "a" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_step_versions "
                "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
                "attempt_count, created_at, updated_at, canonical_digest) "
                "VALUES (?, ?, ?, 2, 'running', 1, 0, 1, ?, ?, ?)",
                (workspace_id, run_id, step_id, timestamp, timestamp, "b" * 64),
            )
    assert classify_database(database).state is DatabaseState.PARTIAL


@pytest.mark.parametrize(
    "columns",
    [
        "workspace_id, step_id, fence, version",
        "workspace_id, run_id, step_id, version, fence",
    ],
)
def test_execution_classifier_rejects_unexpected_version_discriminated_unique_index(
    tmp_path: Path,
    columns: str,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE UNIQUE INDEX version_discriminated_step_fence "
            f"ON run_step_versions({columns})"
        )
    assert classify_database(database).state is DatabaseState.PARTIAL


def test_execution_classifier_allows_nonunique_step_fence_index(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE INDEX nonunique_step_fence "
            "ON run_step_versions(workspace_id, step_id, fence)"
        )
    assert classify_database(database).state is DatabaseState.CURRENT


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


def test_execution_classifier_rejects_neutralized_immutable_trigger_body(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER agent_run_state_versions_no_update")
        connection.execute(
            "CREATE TRIGGER agent_run_state_versions_no_update BEFORE UPDATE "
            "ON agent_run_state_versions BEGIN SELECT RAISE(ABORT, "
            "'agent run state versions are immutable') WHERE 0; END"
        )
        connection.execute(
            "INSERT INTO agent_run_state_versions "
            "(workspace_id, run_id, version, state, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, 1, 'pending', ?, ?, ?)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                timestamp,
                timestamp,
                "a" * 64,
            ),
        )
        connection.execute(
            "UPDATE agent_run_state_versions SET state = 'running', canonical_digest = ?",
            ("b" * 64,),
        )
        assert connection.execute(
            "SELECT state FROM agent_run_state_versions"
        ).fetchone() == ("running",)
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


def test_execution_classifier_rejects_widened_run_state_check(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'agent_run_state_versions'"
        ).fetchone()
        assert table_sql is not None
        weakened_sql = str(table_sql[0]).replace(
            "'cancelled')",
            "'cancelled','corrupt')",
        )
        assert weakened_sql != table_sql[0]
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? "
            "WHERE type = 'table' AND name = 'agent_run_state_versions'",
            (weakened_sql,),
        )
        connection.execute("PRAGMA writable_schema=OFF")
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO agent_run_state_versions "
            "(workspace_id, run_id, version, state, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, 1, 'corrupt', ?, ?, ?)",
            (
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                timestamp,
                timestamp,
                "a" * 64,
            ),
        )
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


def test_execution_schema_binds_step_lineage_and_checkpoint_authority_context(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        step_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(run_steps)")
        }
        checkpoint_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(run_checkpoints)")
        }
        step_foreign_keys: dict[int, set[str]] = {}
        for row in connection.execute("PRAGMA foreign_key_list(run_steps)"):
            step_foreign_keys.setdefault(int(row[0]), set()).add(str(row[3]))
        checkpoint_foreign_keys: dict[int, set[str]] = {}
        for row in connection.execute("PRAGMA foreign_key_list(run_checkpoints)"):
            checkpoint_foreign_keys.setdefault(int(row[0]), set()).add(str(row[3]))
    missing_columns = (
        {"kind", "input_digest", "parent_step_id"} - step_columns
    ) | (
        {"request_context_id", "authorization_snapshot_id"} - checkpoint_columns
    )
    assert (
        missing_columns,
        {"workspace_id", "run_id", "parent_step_id"} in step_foreign_keys.values(),
        {
            "workspace_id",
            "request_context_id",
            "authorization_snapshot_id",
        }
        in checkpoint_foreign_keys.values(),
    ) == (set(), True, True)

    workspace_id = "10000000-0000-4000-8000-000000000001"
    other_workspace_id = "10000000-0000-4000-8000-000000000002"
    parent_run_id = "20000000-0000-4000-8000-000000000001"
    child_run_id = "20000000-0000-4000-8000-000000000002"
    parent_step_id = "30000000-0000-4000-8000-000000000001"
    child_step_id = "30000000-0000-4000-8000-000000000002"
    snapshot_id = "40000000-0000-4000-8000-000000000001"
    request_context_id = "50000000-0000-4000-8000-000000000001"
    timestamp = "2026-07-26T00:00:00+00:00"
    with sqlite3.connect(database) as connection:
        for run_id in (parent_run_id, child_run_id):
            connection.execute(
                "INSERT INTO agent_runs "
                "(workspace_id, id, thread_id, message_sequence, requester_principal_id, "
                "requester_membership_version, authorization_snapshot_id, "
                "authorization_snapshot_digest, provider_binding_id, provider_binding_version, "
                "provider_binding_digest, canonical_request_digest, idempotency_key, "
                "request_digest, parent_run_id, root_run_id, created_at) "
                "VALUES (?, ?, ?, 1, ?, 1, ?, ?, ?, 1, ?, ?, ?, ?, NULL, NULL, ?)",
                (
                    workspace_id,
                    run_id,
                    "60000000-0000-4000-8000-000000000001",
                    "70000000-0000-4000-8000-000000000001",
                    snapshot_id,
                    "a" * 64,
                    "80000000-0000-4000-8000-000000000001",
                    "b" * 64,
                    "c" * 64,
                    f"run-{run_id}",
                    "d" * 64,
                    timestamp,
                ),
            )
        connection.execute(
            "INSERT INTO run_steps "
            "(workspace_id, run_id, id, step_key, ordinal, kind, input_digest, "
            "parent_step_id, created_at) VALUES (?, ?, ?, 'parent', 1, 'model', ?, NULL, ?)",
            (workspace_id, parent_run_id, parent_step_id, "e" * 64, timestamp),
        )
        connection.execute(
            "INSERT INTO run_step_versions "
            "(workspace_id, run_id, step_id, version, state, fence, retry_count, "
            "attempt_count, created_at, updated_at, canonical_digest) "
            "VALUES (?, ?, ?, 1, 'ready', 1, 0, 0, ?, ?, ?)",
            (workspace_id, child_run_id, child_step_id, timestamp, timestamp, "f" * 64),
        )
        connection.execute(
            "INSERT INTO authorization_decision_snapshots "
            "(id, workspace_id, request_context_id, signing_key_version_id, "
            "canonical_digest, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?, '{}')",
            (
                snapshot_id,
                other_workspace_id,
                request_context_id,
                "90000000-0000-4000-8000-000000000001",
                "1" * 64,
                timestamp,
            ),
        )
        connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_steps "
                "(workspace_id, run_id, id, step_key, ordinal, kind, input_digest, "
                "parent_step_id, created_at) VALUES (?, ?, ?, 'child', 1, 'model', ?, ?, ?)",
                (
                    workspace_id,
                    child_run_id,
                    child_step_id,
                    "2" * 64,
                    parent_step_id,
                    timestamp,
                ),
            )
        connection.execute(
            "INSERT INTO run_steps "
            "(workspace_id, run_id, id, step_key, ordinal, kind, input_digest, "
            "parent_step_id, created_at) VALUES (?, ?, ?, 'child', 1, 'model', ?, NULL, ?)",
            (workspace_id, child_run_id, child_step_id, "2" * 64, timestamp),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_checkpoints "
                "(workspace_id, run_id, step_id, id, checkpoint_version, run_state, "
                "step_state, step_fence, step_version, request_context_id, "
                "authorization_snapshot_id, completed_dependency_step_ids_json, "
                "output_ref_ids_json, retry_count, attempt_count, "
                "last_accepted_event_sequence, last_accepted_event_digest, "
                "next_transition, created_at, canonical_digest) "
                "VALUES (?, ?, ?, ?, 1, 'pending', 'ready', 1, 1, ?, ?, '[]', '[]', "
                "0, 0, 0, ?, 'dispatch', ?, ?)",
                (
                    workspace_id,
                    child_run_id,
                    child_step_id,
                    "a0000000-0000-4000-8000-000000000001",
                    request_context_id,
                    snapshot_id,
                    "0" * 64,
                    timestamp,
                    "3" * 64,
                ),
            )


def test_execution_classifier_rejects_weakened_authority_context_fk(tmp_path: Path) -> None:
    database = tmp_path / "corvus.db"
    _base_database(database)
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'run_checkpoints'"
        ).fetchone()
        assert table_sql is not None
        original = (
            "REFERENCES authorization_decision_snapshots "
            "(workspace_id, request_context_id, id) ON DELETE RESTRICT"
        )
        weakened = (
            "REFERENCES authorization_decision_snapshots "
            "(workspace_id, request_context_id, id) ON DELETE CASCADE"
        )
        weakened_sql = str(table_sql[0]).replace(original, weakened)
        assert weakened_sql != table_sql[0]
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'run_checkpoints'",
            (weakened_sql,),
        )
        connection.execute("PRAGMA writable_schema=OFF")
    assert classify_database(database).state is DatabaseState.PARTIAL


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
    assert "create table agent_run_execution_bindings" in rendered
    assert "constraint pk_agent_run_execution_bindings" in rendered
    assert "constraint fk_agent_run_execution_bindings_run" in rendered
    assert "foreign key(workspace_id, run_id) references agent_runs" in rendered
    assert "length(immutable_request_digest) = 64" in rendered
    assert "length(canonical_digest) = 64" in rendered
    assert "create trigger agent_run_execution_bindings_no_update" in rendered
    assert "create trigger agent_run_execution_bindings_no_delete" in rendered
    assert "create table agent_run_state_versions" in rendered
    assert "create table run_checkpoints" in rendered
    assert "parent_step_id varchar(36)" in rendered
    assert "request_context_id varchar(36) not null" in rendered
    assert "authorization_snapshot_id varchar(36) not null" in rendered
    assert "foreign key(workspace_id, run_id, parent_step_id)" in rendered
    assert "foreign key(workspace_id, request_context_id, authorization_snapshot_id)" in rendered
    assert "references authorization_decision_snapshots" in rendered
    assert "foreign key(workspace_id, run_id, step_id, step_version, step_fence)" in rendered
    assert "references run_step_versions" in rendered
    assert "constraint fk_run_checkpoints_step_version" in rendered
    assert "uq_run_step_versions_fence" not in rendered
    assert "fk_run_step_leases_fence" not in rendered
    assert "create unique index uq_run_step_leases_active" in rendered
    assert "create unique index uq_authorization_snapshots_workspace_request_id" in rendered
    assert "where released_at is null" in rendered
    assert "create trigger run_checkpoints_no_update" in rendered
    assert "create trigger run_step_leases_no_delete" in rendered
    assert "create function run_step_leases_guard_update_fn()" in rendered
    assert "new.expires_at < old.expires_at" in rendered
    assert "create trigger run_step_leases_guard_update" in rendered
