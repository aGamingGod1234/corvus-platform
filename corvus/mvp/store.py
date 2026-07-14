from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final = 1

_MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS mvp_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE mvp_projects (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_outcomes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    version INTEGER NOT NULL CHECK (version > 0),
    title TEXT NOT NULL,
    acceptance_criteria_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, title, version)
);
CREATE TABLE mvp_workflows (
    id TEXT PRIMARY KEY,
    outcome_id TEXT NOT NULL REFERENCES mvp_outcomes(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE mvp_work_items (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    item_key TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    depends_on_json TEXT NOT NULL,
    cost_units INTEGER NOT NULL CHECK (cost_units >= 0),
    requires_approval INTEGER NOT NULL CHECK (requires_approval IN (0, 1)),
    effect_json TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    lease_fence INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workflow_id, item_key)
);
CREATE TABLE mvp_attempts (
    id TEXT PRIMARY KEY,
    work_item_id TEXT NOT NULL REFERENCES mvp_work_items(id),
    worker_id TEXT NOT NULL,
    lease_fence INTEGER NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE mvp_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    work_item_id TEXT NOT NULL REFERENCES mvp_work_items(id),
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_artifacts (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    work_item_id TEXT NOT NULL REFERENCES mvp_work_items(id),
    digest TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_lineage (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_conversation_entries (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    work_item_id TEXT REFERENCES mvp_work_items(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_effects (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    work_item_id TEXT NOT NULL UNIQUE REFERENCES mvp_work_items(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    binding_json TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_id TEXT,
    execution_count INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE mvp_approvals (
    id TEXT PRIMARY KEY,
    effect_id TEXT NOT NULL UNIQUE REFERENCES mvp_effects(id),
    actor_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consumed_at TEXT
);
CREATE TABLE mvp_budgets (
    project_id TEXT PRIMARY KEY REFERENCES mvp_projects(id),
    limit_units INTEGER NOT NULL CHECK (limit_units >= 0),
    reserved_units INTEGER NOT NULL CHECK (reserved_units >= 0),
    settled_units INTEGER NOT NULL CHECK (settled_units >= 0)
);
CREATE TABLE mvp_budget_reservations (
    id TEXT PRIMARY KEY,
    effect_id TEXT NOT NULL UNIQUE REFERENCES mvp_effects(id),
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    amount_units INTEGER NOT NULL CHECK (amount_units >= 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    settled_at TEXT
);
CREATE TABLE mvp_kill_switches (
    scope_kind TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(scope_kind, scope_id)
);
CREATE TABLE mvp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL REFERENCES mvp_workflows(id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX mvp_work_items_ready_idx ON mvp_work_items(workflow_id, status, item_key);
CREATE INDEX mvp_events_workflow_idx ON mvp_events(workflow_id, id);
"""


class StoreError(RuntimeError):
    pass


class SqliteStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS mvp_schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            rows = connection.execute(
                "SELECT version FROM mvp_schema_migrations ORDER BY version"
            ).fetchall()
            versions = [int(row["version"]) for row in rows]
            if any(version > SCHEMA_VERSION for version in versions):
                raise StoreError("unsupported_mvp_schema_version")
            if 1 not in versions:
                connection.executescript(_MIGRATION_001)
                connection.execute(
                    "INSERT INTO mvp_schema_migrations(version, applied_at) "
                    "VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
                )
