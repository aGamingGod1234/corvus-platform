from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from corvus.domain.account import DeviceRegistration, DeviceStatus, ExperienceKind
from corvus.domain.identity import (
    MembershipStatus,
    Workspace,
    WorkspaceKind,
    WorkspaceMembership,
)


class PlatformIdentityRepositoryError(RuntimeError):
    pass


def _canonical_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PlatformIdentityRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            yield connection

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        with self.engine.connect() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            yield connection

    @staticmethod
    def _onboarding(
        connection: Connection,
        account_id: UUID,
    ) -> tuple[ExperienceKind | None, int]:
        row = connection.execute(
            text(
                "SELECT experience_kind, version FROM account_onboarding_versions "
                "WHERE account_id = :account_id ORDER BY version DESC LIMIT 1"
            ),
            {"account_id": str(account_id)},
        ).one_or_none()
        if row is not None:
            return ExperienceKind(str(row[0])), int(row[1])
        account = connection.execute(
            text("SELECT experience_kind, version FROM accounts WHERE id = :account_id"),
            {"account_id": str(account_id)},
        ).one_or_none()
        if account is None:
            raise PlatformIdentityRepositoryError("account_not_found")
        value = None if account[0] is None else ExperienceKind(str(account[0]))
        return value, int(account[1])

    def get_onboarding(self, account_id: UUID) -> tuple[ExperienceKind | None, int]:
        with self._connection() as connection:
            return self._onboarding(connection, account_id)

    def update_onboarding(
        self,
        *,
        account_id: UUID,
        experience_kind: ExperienceKind,
        expected_version: int,
        now: datetime,
    ) -> tuple[ExperienceKind, int]:
        with self._transaction() as connection:
            _current_kind, current_version = self._onboarding(connection, account_id)
            if current_version != expected_version:
                raise PlatformIdentityRepositoryError("account_version_conflict")
            version = current_version + 1
            payload = {
                "account_id": str(account_id),
                "experience_kind": experience_kind.value,
                "version": version,
                "updated_at": now.isoformat(),
            }
            connection.execute(
                text(
                    "INSERT INTO account_onboarding_versions "
                    "(account_id, version, experience_kind, updated_at, payload_json) "
                    "VALUES (:account_id, :version, :experience_kind, :updated_at, :payload_json)"
                ),
                {**payload, "payload_json": json.dumps(payload, separators=(",", ":"))},
            )
            return experience_kind, version

    @staticmethod
    def _membership_role(
        connection: Connection,
        *,
        workspace_id: UUID,
        principal_id: UUID,
    ) -> str | None:
        row = connection.execute(
            text(
                "SELECT role, status FROM workspace_memberships "
                "WHERE workspace_id = :workspace_id AND principal_id = :principal_id "
                "ORDER BY version DESC LIMIT 1"
            ),
            {"workspace_id": str(workspace_id), "principal_id": str(principal_id)},
        ).one_or_none()
        if row is None or row[1] != MembershipStatus.ACTIVE.value:
            return None
        return str(row[0]).strip().casefold()

    def list_workspaces(self, principal_id: UUID) -> list[Workspace]:
        with self._connection() as connection:
            workspace_ids = connection.scalars(
                text(
                    "SELECT DISTINCT workspace_id FROM workspace_memberships membership "
                    "WHERE principal_id = :principal_id AND status = 'active' "
                    "AND version = (SELECT MAX(version) FROM workspace_memberships current "
                    "WHERE current.workspace_id = membership.workspace_id "
                    "AND current.principal_id = membership.principal_id) ORDER BY workspace_id"
                ),
                {"principal_id": str(principal_id)},
            ).all()
            result: list[Workspace] = []
            for workspace_id in workspace_ids:
                payload = connection.scalar(
                    text(
                        "SELECT payload_json FROM identity_workspaces WHERE id = :id "
                        "ORDER BY version DESC LIMIT 1"
                    ),
                    {"id": workspace_id},
                )
                if payload is not None:
                    result.append(Workspace.model_validate_json(payload))
            return result

    @staticmethod
    def _idempotency_result(
        connection: Connection,
        *,
        account_id: UUID,
        operation: str,
        key: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                "SELECT request_digest, result_json FROM identity_idempotency "
                "WHERE account_id = :account_id AND operation = :operation "
                "AND idempotency_key = :idempotency_key"
            ),
            {
                "account_id": str(account_id),
                "operation": operation,
                "idempotency_key": key,
            },
        ).one_or_none()
        if row is None:
            return None
        if row[0] != request_digest:
            raise PlatformIdentityRepositoryError("idempotency_payload_mismatch")
        loaded = json.loads(row[1])
        if not isinstance(loaded, dict):
            raise PlatformIdentityRepositoryError("idempotency_result_invalid")
        return cast(dict[str, Any], loaded)

    @staticmethod
    def _record_idempotency(
        connection: Connection,
        *,
        account_id: UUID,
        operation: str,
        key: str,
        request_digest: str,
        result: dict[str, Any],
        now: datetime,
    ) -> None:
        connection.execute(
            text(
                "INSERT INTO identity_idempotency "
                "(account_id, operation, idempotency_key, request_digest, result_json, created_at) "
                "VALUES (:account_id, :operation, :key, :request_digest, :result_json, :created_at)"
            ),
            {
                "account_id": str(account_id),
                "operation": operation,
                "key": key,
                "request_digest": request_digest,
                "result_json": json.dumps(result, separators=(",", ":"), sort_keys=True),
                "created_at": now.isoformat(),
            },
        )

    def create_workspace(
        self,
        *,
        account_id: UUID,
        principal_id: UUID,
        name: str,
        workspace_kind: WorkspaceKind,
        idempotency_key: str,
        now: datetime,
    ) -> tuple[Workspace, bool]:
        request_digest = _canonical_digest({"name": name, "workspace_kind": workspace_kind.value})
        try:
            with self._transaction() as connection:
                repeated = self._idempotency_result(
                    connection,
                    account_id=account_id,
                    operation="workspace.create",
                    key=idempotency_key,
                    request_digest=request_digest,
                )
                if repeated is not None:
                    return Workspace.model_validate(repeated), True
                workspace = Workspace(
                    name=name.strip(),
                    workspace_kind=workspace_kind,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(
                    text(
                        "INSERT INTO identity_workspaces "
                        "(id, version, name, workspace_kind, status, created_at, updated_at, "
                        "payload_json) VALUES (:id, :version, :name, :workspace_kind, :status, "
                        ":created_at, :updated_at, :payload_json)"
                    ),
                    {
                        "id": str(workspace.id),
                        "version": workspace.version,
                        "name": workspace.name,
                        "workspace_kind": workspace.workspace_kind.value,
                        "status": workspace.status.value,
                        "created_at": workspace.created_at.isoformat(),
                        "updated_at": workspace.updated_at.isoformat(),
                        "payload_json": workspace.model_dump_json(),
                    },
                )
                membership = WorkspaceMembership(
                    workspace_id=workspace.id,
                    principal_id=principal_id,
                    role="Owner",
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(
                    text(
                        "INSERT INTO workspace_memberships "
                        "(workspace_id, principal_id, version, role, status, created_at, "
                        "updated_at, payload_json) VALUES (:workspace_id, :principal_id, "
                        ":version, :role, :status, :created_at, :updated_at, :payload_json)"
                    ),
                    {
                        "workspace_id": str(workspace.id),
                        "principal_id": str(principal_id),
                        "version": membership.version,
                        "role": membership.role,
                        "status": membership.status.value,
                        "created_at": membership.created_at.isoformat(),
                        "updated_at": membership.updated_at.isoformat(),
                        "payload_json": membership.model_dump_json(),
                    },
                )
                self._record_idempotency(
                    connection,
                    account_id=account_id,
                    operation="workspace.create",
                    key=idempotency_key,
                    request_digest=request_digest,
                    result=workspace.model_dump(mode="json"),
                    now=now,
                )
                return workspace, False
        except IntegrityError as exc:
            raise PlatformIdentityRepositoryError("workspace_create_conflict") from exc

    def update_workspace(
        self,
        *,
        principal_id: UUID,
        workspace_id: UUID,
        name: str,
        expected_version: int,
        now: datetime,
    ) -> Workspace:
        with self._transaction() as connection:
            role = self._membership_role(
                connection, workspace_id=workspace_id, principal_id=principal_id
            )
            if role is None:
                raise PlatformIdentityRepositoryError("workspace_not_found")
            if role not in {"owner", "admin", "manager"}:
                raise PlatformIdentityRepositoryError("workspace_update_forbidden")
            payload = connection.scalar(
                text(
                    "SELECT payload_json FROM identity_workspaces WHERE id = :id "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"id": str(workspace_id)},
            )
            if payload is None:
                raise PlatformIdentityRepositoryError("workspace_not_found")
            current = Workspace.model_validate_json(payload)
            if current.version != expected_version:
                raise PlatformIdentityRepositoryError("workspace_version_conflict")
            updated = current.model_copy(
                update={"name": name.strip(), "version": current.version + 1, "updated_at": now}
            )
            connection.execute(
                text(
                    "INSERT INTO identity_workspaces "
                    "(id, version, name, workspace_kind, status, created_at, updated_at, "
                    "payload_json) VALUES (:id, :version, :name, :workspace_kind, :status, "
                    ":created_at, :updated_at, :payload_json)"
                ),
                {
                    "id": str(updated.id),
                    "version": updated.version,
                    "name": updated.name,
                    "workspace_kind": updated.workspace_kind.value,
                    "status": updated.status.value,
                    "created_at": updated.created_at.isoformat(),
                    "updated_at": updated.updated_at.isoformat(),
                    "payload_json": updated.model_dump_json(),
                },
            )
            return updated

    def list_devices(self, account_id: UUID) -> list[DeviceRegistration]:
        with self._connection() as connection:
            payloads = connection.scalars(
                text(
                    "SELECT payload_json FROM device_registrations device "
                    "WHERE account_id = :account_id AND version = "
                    "(SELECT MAX(version) FROM device_registrations current "
                    "WHERE current.id = device.id AND current.account_id = device.account_id) "
                    "ORDER BY created_at, id"
                ),
                {"account_id": str(account_id)},
            ).all()
        return [DeviceRegistration.model_validate_json(payload) for payload in payloads]

    def register_device(
        self,
        *,
        account_id: UUID,
        name: str,
        public_key_digest: str,
        idempotency_key: str,
        now: datetime,
    ) -> tuple[DeviceRegistration, bool]:
        request_digest = _canonical_digest({"name": name, "public_key_digest": public_key_digest})
        try:
            with self._transaction() as connection:
                repeated = self._idempotency_result(
                    connection,
                    account_id=account_id,
                    operation="device.create",
                    key=idempotency_key,
                    request_digest=request_digest,
                )
                if repeated is not None:
                    return DeviceRegistration.model_validate(repeated), True
                device = DeviceRegistration(
                    account_id=account_id,
                    name=name.strip(),
                    public_key_digest=public_key_digest,
                    created_at=now,
                    updated_at=now,
                )
                self._insert_device(connection, device)
                self._record_idempotency(
                    connection,
                    account_id=account_id,
                    operation="device.create",
                    key=idempotency_key,
                    request_digest=request_digest,
                    result=device.model_dump(mode="json"),
                    now=now,
                )
                return device, False
        except IntegrityError as exc:
            raise PlatformIdentityRepositoryError("device_create_conflict") from exc

    @staticmethod
    def _insert_device(connection: Connection, device: DeviceRegistration) -> None:
        connection.execute(
            text(
                "INSERT INTO device_registrations "
                "(id, account_id, version, name, public_key_digest, status, revoked_at, "
                "created_at, updated_at, payload_json) VALUES (:id, :account_id, :version, "
                ":name, :public_key_digest, :status, :revoked_at, :created_at, :updated_at, "
                ":payload_json)"
            ),
            {
                "id": str(device.id),
                "account_id": str(device.account_id),
                "version": device.version,
                "name": device.name,
                "public_key_digest": device.public_key_digest,
                "status": device.status.value,
                "revoked_at": None if device.revoked_at is None else device.revoked_at.isoformat(),
                "created_at": device.created_at.isoformat(),
                "updated_at": device.updated_at.isoformat(),
                "payload_json": device.model_dump_json(),
            },
        )

    def revoke_device(
        self,
        *,
        account_id: UUID,
        device_id: UUID,
        expected_version: int,
        now: datetime,
    ) -> DeviceRegistration:
        with self._transaction() as connection:
            payload = connection.scalar(
                text(
                    "SELECT payload_json FROM device_registrations "
                    "WHERE account_id = :account_id AND id = :device_id "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"account_id": str(account_id), "device_id": str(device_id)},
            )
            if payload is None:
                raise PlatformIdentityRepositoryError("device_not_found")
            current = DeviceRegistration.model_validate_json(payload)
            if current.version != expected_version:
                raise PlatformIdentityRepositoryError("device_version_conflict")
            if current.status is DeviceStatus.REVOKED:
                return current
            revoked = current.model_copy(
                update={
                    "version": current.version + 1,
                    "status": DeviceStatus.REVOKED,
                    "revoked_at": now,
                    "updated_at": now,
                }
            )
            self._insert_device(connection, revoked)
            return revoked
