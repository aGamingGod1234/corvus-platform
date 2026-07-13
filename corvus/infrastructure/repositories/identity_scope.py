from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from uuid import UUID

from corvus.database import DatabaseState, classify_database
from corvus.domain.identity import AgentIdentity, Principal, Workspace, WorkspaceMembership
from corvus.domain.scope import (
    ChannelScope,
    ConversationScope,
    ProjectScope,
    ThreadScope,
    WorkspaceScope,
)
from corvus.infrastructure.db import M1_CURRENT_REVISION, current_revision

type Scope = WorkspaceScope | ProjectScope | ChannelScope | ThreadScope | ConversationScope


class IdentityScopeRepositoryError(RuntimeError):
    pass


def _digest(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _scope_identity(scope: Scope) -> tuple[str, UUID]:
    if isinstance(scope, WorkspaceScope):
        return scope.kind, scope.workspace_id
    if isinstance(scope, ProjectScope):
        return scope.kind, scope.project_id
    if isinstance(scope, ChannelScope):
        return scope.kind, scope.channel_id
    if isinstance(scope, ThreadScope):
        return scope.kind, scope.thread_id
    return scope.kind, scope.conversation_id


def _scope_parent(scope: Scope) -> tuple[str | None, UUID | None]:
    if isinstance(scope, ConversationScope):
        return scope.parent_scope_kind, scope.parent_scope_id
    if isinstance(scope, ThreadScope):
        return "channel", scope.channel_id
    if isinstance(scope, ChannelScope) and scope.project_id is not None:
        return "project", scope.project_id
    if isinstance(scope, ThreadScope) and scope.project_id is not None:
        return "project", scope.project_id
    return None, None


def _parse_scope(payload: str) -> Scope:
    raw = json.loads(payload)
    kind = raw.get("kind")
    if kind == "workspace":
        return WorkspaceScope.model_validate(raw)
    if kind == "project":
        return ProjectScope.model_validate(raw)
    if kind == "channel":
        return ChannelScope.model_validate(raw)
    if kind == "thread":
        return ThreadScope.model_validate(raw)
    if kind == "conversation":
        return ConversationScope.model_validate(raw)
    raise IdentityScopeRepositoryError("scope_kind_unknown")


class IdentityScopeRepository:
    def __init__(self, database: Path) -> None:
        revision = current_revision(database)
        if revision != M1_CURRENT_REVISION:
            raise IdentityScopeRepositoryError(
                f"database_revision_mismatch:{revision or 'unstamped'}"
            )
        status = classify_database(database)
        if status.state is not DatabaseState.CURRENT:
            raise IdentityScopeRepositoryError(f"database_state_mismatch:{status.state.value}")
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def append_workspace(self, workspace: Workspace) -> None:
        self._insert(
            "INSERT INTO identity_workspaces "
            "(id, version, name, status, created_at, updated_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(workspace.id),
                workspace.version,
                workspace.name,
                workspace.status.value,
                workspace.created_at.isoformat(),
                workspace.updated_at.isoformat(),
                workspace.model_dump_json(),
            ),
            "workspace_identity_conflict",
        )

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        row = self._one(
            "SELECT payload_json FROM identity_workspaces WHERE id = ? "
            "ORDER BY version DESC LIMIT 1",
            (str(workspace_id),),
        )
        return None if row is None else Workspace.model_validate_json(row[0])

    def append_principal(self, principal: Principal) -> None:
        self._insert(
            "INSERT INTO principals "
            "(id, kind, external_provider, external_subject, created_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(principal.id),
                principal.kind.value,
                principal.external_provider,
                principal.external_subject,
                principal.created_at.isoformat(),
                principal.model_dump_json(),
            ),
            "principal_identity_conflict",
        )

    def get_principal(self, principal_id: UUID) -> Principal | None:
        row = self._one(
            "SELECT payload_json FROM principals WHERE id = ?",
            (str(principal_id),),
        )
        return None if row is None else Principal.model_validate_json(row[0])

    def append_membership(self, membership: WorkspaceMembership) -> None:
        self._insert(
            "INSERT INTO workspace_memberships "
            "(workspace_id, principal_id, version, role, status, created_at, updated_at, "
            "payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(membership.workspace_id),
                str(membership.principal_id),
                membership.version,
                membership.role,
                membership.status.value,
                membership.created_at.isoformat(),
                membership.updated_at.isoformat(),
                membership.model_dump_json(),
            ),
            "membership_identity_conflict",
        )

    def get_membership(
        self,
        workspace_id: UUID,
        principal_id: UUID,
    ) -> WorkspaceMembership | None:
        row = self._one(
            "SELECT payload_json FROM workspace_memberships "
            "WHERE workspace_id = ? AND principal_id = ? ORDER BY version DESC LIMIT 1",
            (str(workspace_id), str(principal_id)),
        )
        return None if row is None else WorkspaceMembership.model_validate_json(row[0])

    def append_agent(self, agent: AgentIdentity) -> None:
        self._insert(
            "INSERT INTO agent_identities "
            "(id, workspace_id, version, name, role, model_route, status, created_at, "
            "updated_at, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(agent.id),
                str(agent.workspace_id),
                agent.version,
                agent.name,
                agent.role,
                agent.model_route,
                agent.status.value,
                agent.created_at.isoformat(),
                agent.updated_at.isoformat(),
                agent.model_dump_json(),
            ),
            "agent_identity_conflict",
        )

    def get_agent(self, workspace_id: UUID, agent_id: UUID) -> AgentIdentity | None:
        row = self._one(
            "SELECT payload_json FROM agent_identities WHERE workspace_id = ? AND id = ? "
            "ORDER BY version DESC LIMIT 1",
            (str(workspace_id), str(agent_id)),
        )
        return None if row is None else AgentIdentity.model_validate_json(row[0])

    def append_scope(self, scope: Scope) -> None:
        kind, scope_id = _scope_identity(scope)
        parent_kind, parent_id = _scope_parent(scope)
        self._insert(
            "INSERT INTO scopes "
            "(workspace_id, kind, scope_id, parent_scope_kind, parent_scope_id, "
            "scope_digest, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(scope.workspace_id),
                kind,
                str(scope_id),
                parent_kind,
                None if parent_id is None else str(parent_id),
                _digest(scope),
                scope.model_dump_json(),
            ),
            "scope_identity_conflict",
        )

    def get_scope(self, workspace_id: UUID, kind: str, scope_id: UUID) -> Scope | None:
        row = self._one(
            "SELECT payload_json FROM scopes WHERE workspace_id = ? AND kind = ? AND scope_id = ?",
            (str(workspace_id), kind, str(scope_id)),
        )
        return None if row is None else _parse_scope(row[0])

    def _insert(self, statement: str, values: tuple[object, ...], reason: str) -> None:
        try:
            with self._transaction() as connection:
                connection.execute(statement, values)
        except sqlite3.IntegrityError as exc:
            raise IdentityScopeRepositoryError(reason) from exc

    def _one(self, statement: str, values: tuple[object, ...]) -> tuple[str] | None:
        with self._connect() as connection:
            row = connection.execute(statement, values).fetchone()
        return cast(tuple[str] | None, row)

    def close(self) -> None:
        return None
