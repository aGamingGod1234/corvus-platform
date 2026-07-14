from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final = 3

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

_MIGRATION_002 = """
CREATE TABLE mvp_teams (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_team_members (
    team_id TEXT NOT NULL REFERENCES mvp_teams(id),
    principal_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(team_id, principal_id)
);
CREATE TABLE mvp_provider_connections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    provider TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_credential_grants (
    id TEXT PRIMARY KEY,
    provider_connection_id TEXT NOT NULL REFERENCES mvp_provider_connections(id),
    principal_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    credential_ref TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(provider_connection_id, principal_id, capability)
);
CREATE TABLE mvp_oauth_flows (
    state TEXT PRIMARY KEY,
    provider_connection_id TEXT NOT NULL REFERENCES mvp_provider_connections(id),
    redirect_uri TEXT NOT NULL,
    verifier_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE mvp_autonomy_decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    principal_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    mode TEXT NOT NULL,
    requested_execution INTEGER NOT NULL,
    executed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_autonomy_evidence (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES mvp_autonomy_decisions(id),
    successful INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_autonomy_policies (
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    principal_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    mode TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, principal_id, capability)
);
CREATE TABLE mvp_memory_entries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    scope TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, id, version)
);
CREATE TABLE mvp_skill_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name, version)
);
CREATE TABLE mvp_routines (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    name TEXT NOT NULL,
    skill_version_id TEXT NOT NULL REFERENCES mvp_skill_versions(id),
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_routine_runs (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL REFERENCES mvp_routines(id),
    skill_version_id TEXT NOT NULL REFERENCES mvp_skill_versions(id),
    actor_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE mvp_envelope_actor_keys (
    actor_id TEXT PRIMARY KEY,
    public_key TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE mvp_offline_intents (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    envelope_json TEXT NOT NULL,
    status TEXT NOT NULL,
    application_count INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE mvp_channel_identities (
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(provider, external_id)
);
CREATE TABLE mvp_channel_events (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    principal_id TEXT,
    envelope_json TEXT NOT NULL,
    status TEXT NOT NULL,
    processing_count INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider, external_event_id)
);
"""

_MIGRATION_003 = """
CREATE TABLE mvp_device_flows (
    device_code TEXT PRIMARY KEY,
    user_code TEXT NOT NULL UNIQUE,
    provider_connection_id TEXT NOT NULL REFERENCES mvp_provider_connections(id),
    status TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    polling_interval_seconds INTEGER NOT NULL,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE mvp_restore_quarantine (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES mvp_projects(id),
    source_digest TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT
);
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
                versions.append(1)
            if 2 not in versions:
                connection.executescript(_MIGRATION_002)
                connection.execute(
                    "INSERT INTO mvp_schema_migrations(version, applied_at) "
                    "VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
                )
                versions.append(2)
            if 3 not in versions:
                connection.executescript(_MIGRATION_003)
                connection.execute(
                    "INSERT INTO mvp_schema_migrations(version, applied_at) "
                    "VALUES (3, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
                )
