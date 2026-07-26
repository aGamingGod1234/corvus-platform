from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from alembic.runtime.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError

from corvus.database import DatabaseState, classify_database
from corvus.domain.execution import (
    ExecutionCheckpoint,
    ExecutionNextTransition,
    ExecutionRun,
    ExecutionRunState,
    ExecutionStep,
    ExecutionStepLease,
    ExecutionStepState,
    compute_execution_step_digest,
)
from corvus.infrastructure.db import M2_DURABLE_EXECUTION_REVISION, current_revision

_RUN_SQL = (
    "SELECT * FROM agent_run_state_versions WHERE workspace_id = :workspace_id "
    "AND run_id = :run_id ORDER BY version DESC LIMIT 1"
)
_STEP_SQL = (
    "SELECT * FROM run_step_versions WHERE workspace_id = :workspace_id "
    "AND run_id = :run_id AND step_id = :step_id ORDER BY version DESC LIMIT 1"
)
_LEASE_SQL = (
    "SELECT * FROM run_step_leases WHERE workspace_id = :workspace_id "
    "AND run_id = :run_id AND step_id = :step_id AND released_at IS NULL "
    "ORDER BY fence DESC LIMIT 1"
)
_CHECKPOINT_SQL = (
    "SELECT * FROM run_checkpoints WHERE workspace_id = :workspace_id "
    "AND run_id = :run_id AND step_id = :step_id "
    "ORDER BY checkpoint_version DESC LIMIT 1"
)


class ExecutionRepositoryError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _uuid_values(values: dict[str, object]) -> dict[str, object]:
    return {
        key: str(value) if isinstance(value, UUID) else value
        for key, value in values.items()
    }


class ExecutionRepository:
    def __init__(self, database: Path | Engine) -> None:
        self._owns_engine = isinstance(database, Path)
        if isinstance(database, Path):
            revision = current_revision(database)
            if revision != M2_DURABLE_EXECUTION_REVISION:
                raise ExecutionRepositoryError(
                    f"database_revision_mismatch:{revision or 'unstamped'}"
                )
            status = classify_database(database)
            if status.state is not DatabaseState.CURRENT:
                raise ExecutionRepositoryError(
                    f"database_state_mismatch:{status.state.value}"
                )
            self.engine = create_engine(
                f"sqlite:///{database}",
                connect_args={"timeout": 30},
            )
        else:
            self.engine = database
            with self.engine.connect() as connection:
                revision = MigrationContext.configure(connection).get_current_revision()
            if revision != M2_DURABLE_EXECUTION_REVISION:
                raise ExecutionRepositoryError(
                    f"database_revision_mismatch:{revision or 'unstamped'}"
                )
        if self.engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ExecutionRepositoryError("unsupported_repository_dialect")

    @staticmethod
    def _enable_sqlite_foreign_keys(connection: Connection) -> None:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    @contextmanager
    def _transaction(self) -> Iterator[Connection]:
        with self.engine.connect() as connection:
            self._enable_sqlite_foreign_keys(connection)
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    yield connection
                except Exception:
                    connection.rollback()
                    raise
                else:
                    connection.commit()
                return
            with connection.begin():
                yield connection

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        with self.engine.connect() as connection:
            self._enable_sqlite_foreign_keys(connection)
            yield connection

    @staticmethod
    def _locked(statement: str, connection: Connection) -> str:
        return f"{statement} FOR UPDATE" if connection.dialect.name == "postgresql" else statement

    @staticmethod
    def _run_from_row(row: RowMapping) -> ExecutionRun:
        try:
            return ExecutionRun(
                id=UUID(row["run_id"]),
                workspace_id=UUID(row["workspace_id"]),
                state=ExecutionRunState(row["state"]),
                version=int(row["version"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                canonical_digest=row["canonical_digest"],
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ExecutionRepositoryError("execution_run_integrity_invalid") from exc

    @staticmethod
    def _step_from_row(row: RowMapping) -> ExecutionStep:
        try:
            return ExecutionStep(
                id=UUID(row["step_id"]),
                workspace_id=UUID(row["workspace_id"]),
                run_id=UUID(row["run_id"]),
                state=ExecutionStepState(row["state"]),
                fence=int(row["fence"]),
                version=int(row["version"]),
                retry_count=int(row["retry_count"]),
                attempt_count=int(row["attempt_count"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                canonical_digest=row["canonical_digest"],
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ExecutionRepositoryError("execution_step_integrity_invalid") from exc

    @staticmethod
    def _lease_from_row(row: RowMapping) -> ExecutionStepLease:
        try:
            return ExecutionStepLease(
                workspace_id=UUID(row["workspace_id"]),
                run_id=UUID(row["run_id"]),
                step_id=UUID(row["step_id"]),
                fence=int(row["fence"]),
                worker_id=row["worker_id"],
                lease_token_digest=row["lease_token_digest"],
                acquired_at=row["acquired_at"],
                heartbeat_at=row["heartbeat_at"],
                expires_at=row["expires_at"],
                released_at=row["released_at"],
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ExecutionRepositoryError("execution_step_lease_integrity_invalid") from exc

    @classmethod
    def _checkpoint_from_row(
        cls,
        connection: Connection,
        row: RowMapping,
    ) -> ExecutionCheckpoint:
        artifact_ids = tuple(
            UUID(value)
            for value in connection.scalars(
                text(
                    "SELECT artifact_id FROM run_checkpoint_artifacts "
                    "WHERE workspace_id = :workspace_id AND checkpoint_id = :checkpoint_id "
                    "ORDER BY ordinal"
                ),
                {
                    "workspace_id": row["workspace_id"],
                    "checkpoint_id": row["id"],
                },
            ).all()
        )
        try:
            return ExecutionCheckpoint(
                id=UUID(row["id"]),
                workspace_id=UUID(row["workspace_id"]),
                run_id=UUID(row["run_id"]),
                step_id=UUID(row["step_id"]),
                run_state=ExecutionRunState(row["run_state"]),
                step_state=ExecutionStepState(row["step_state"]),
                step_fence=int(row["step_fence"]),
                step_version=int(row["step_version"]),
                checkpoint_version=int(row["checkpoint_version"]),
                completed_dependency_step_ids=tuple(
                    UUID(value)
                    for value in json.loads(row["completed_dependency_step_ids_json"])
                ),
                output_ref_ids=tuple(
                    UUID(value) for value in json.loads(row["output_ref_ids_json"])
                ),
                artifact_ref_ids=artifact_ids,
                retry_count=int(row["retry_count"]),
                attempt_count=int(row["attempt_count"]),
                last_accepted_event_sequence=int(row["last_accepted_event_sequence"]),
                last_accepted_event_digest=row["last_accepted_event_digest"],
                next_transition=ExecutionNextTransition(row["next_transition"]),
                created_at=row["created_at"],
                canonical_digest=row["canonical_digest"],
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            raise ExecutionRepositoryError("execution_checkpoint_integrity_invalid") from exc

    def record_run_state(self, run: ExecutionRun) -> ExecutionRun:
        with self._transaction() as connection:
            parent = connection.execute(
                text(
                    self._locked(
                        "SELECT 1 FROM agent_runs WHERE workspace_id = :workspace_id "
                        "AND id = :run_id",
                        connection,
                    )
                ),
                {"workspace_id": str(run.workspace_id), "run_id": str(run.id)},
            ).first()
            if parent is None:
                raise ExecutionRepositoryError("execution_run_not_found")
            if run.version != 1:
                raise ExecutionRepositoryError(
                    "execution_run_initial_version_invalid"
                )
            existing = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM agent_run_state_versions "
                            "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                            "AND version = :version",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(run.workspace_id),
                        "run_id": str(run.id),
                        "version": run.version,
                    },
                )
                .mappings()
                .first()
            )
            if existing is not None:
                stored = self._run_from_row(existing)
                if stored == run:
                    return stored
                raise ExecutionRepositoryError(
                    "execution_idempotency_payload_mismatch"
                )
            try:
                connection.execute(
                    text(
                        "INSERT INTO agent_run_state_versions "
                        "(workspace_id, run_id, version, state, created_at, updated_at, "
                        "canonical_digest) VALUES (:workspace_id, :run_id, :version, :state, "
                        ":created_at, :updated_at, :canonical_digest)"
                    ),
                    {
                        "workspace_id": str(run.workspace_id),
                        "run_id": str(run.id),
                        "version": run.version,
                        "state": run.state.value,
                        "created_at": run.created_at.isoformat(),
                        "updated_at": run.updated_at.isoformat(),
                        "canonical_digest": run.canonical_digest,
                    },
                )
            except IntegrityError as exc:
                raise ExecutionRepositoryError("execution_run_binding_invalid") from exc
            return run

    def create_step(
        self,
        step: ExecutionStep,
        *,
        step_key: str,
        step_ordinal: int,
        kind: str,
        input_digest: str,
        parent_step_id: UUID | None = None,
    ) -> ExecutionStep:
        with self._transaction() as connection:
            run = connection.execute(
                text(
                    self._locked(
                        "SELECT 1 FROM agent_runs WHERE workspace_id = :workspace_id "
                        "AND id = :run_id",
                        connection,
                    )
                ),
                {
                    "workspace_id": str(step.workspace_id),
                    "run_id": str(step.run_id),
                },
            ).first()
            if run is None:
                raise ExecutionRepositoryError("execution_run_not_found")
            if step.version != 1 or step.fence != 1:
                raise ExecutionRepositoryError(
                    "execution_step_initial_version_invalid"
                )
            existing_identity = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_steps WHERE workspace_id = :workspace_id "
                            "AND id = :step_id",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(step.workspace_id),
                        "step_id": str(step.id),
                    },
                )
                .mappings()
                .first()
            )
            if existing_identity is not None:
                existing_version = (
                    connection.execute(
                        text(
                            self._locked(
                                "SELECT * FROM run_step_versions "
                                "WHERE workspace_id = :workspace_id "
                                "AND run_id = :run_id AND step_id = :step_id "
                                "AND version = :version",
                                connection,
                            )
                        ),
                        {
                            "workspace_id": str(step.workspace_id),
                            "run_id": str(step.run_id),
                            "step_id": str(step.id),
                            "version": step.version,
                        },
                    )
                    .mappings()
                    .first()
                )
                stored_parent = existing_identity["parent_step_id"]
                replay_matches = (
                    existing_identity["run_id"] == str(step.run_id)
                    and existing_identity["step_key"] == step_key
                    and int(existing_identity["ordinal"]) == step_ordinal
                    and existing_identity["kind"] == kind
                    and existing_identity["input_digest"] == input_digest
                    and stored_parent
                    == (None if parent_step_id is None else str(parent_step_id))
                    and existing_identity["created_at"] == step.created_at.isoformat()
                    and existing_version is not None
                    and self._step_from_row(existing_version) == step
                )
                if replay_matches:
                    return step
                raise ExecutionRepositoryError(
                    "execution_idempotency_payload_mismatch"
                )
            if parent_step_id is not None:
                parent = connection.execute(
                    text(
                        self._locked(
                            "SELECT 1 FROM run_steps WHERE workspace_id = :workspace_id "
                            "AND run_id = :run_id AND id = :parent_step_id",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(step.workspace_id),
                        "run_id": str(step.run_id),
                        "parent_step_id": str(parent_step_id),
                    },
                ).first()
                if parent is None:
                    raise ExecutionRepositoryError("execution_step_parent_not_found")
            try:
                connection.execute(
                    text(
                        "INSERT INTO run_steps (workspace_id, run_id, id, step_key, ordinal, "
                        "kind, input_digest, parent_step_id, created_at) VALUES (:workspace_id, "
                        ":run_id, :id, :step_key, :ordinal, :kind, :input_digest, "
                        ":parent_step_id, :created_at)"
                    ),
                    {
                        "workspace_id": str(step.workspace_id),
                        "run_id": str(step.run_id),
                        "id": str(step.id),
                        "step_key": step_key,
                        "ordinal": step_ordinal,
                        "kind": kind,
                        "input_digest": input_digest,
                        "parent_step_id": (
                            None if parent_step_id is None else str(parent_step_id)
                        ),
                        "created_at": step.created_at.isoformat(),
                    },
                )
                self._insert_step_version(connection, step)
            except IntegrityError as exc:
                raise ExecutionRepositoryError("execution_step_binding_invalid") from exc
            return step

    def append_run_state(
        self,
        run: ExecutionRun,
        *,
        expected_prior_version: int,
    ) -> ExecutionRun:
        with self._transaction() as connection:
            parent = connection.execute(
                text(
                    self._locked(
                        "SELECT 1 FROM agent_runs WHERE workspace_id = :workspace_id "
                        "AND id = :run_id",
                        connection,
                    )
                ),
                {"workspace_id": str(run.workspace_id), "run_id": str(run.id)},
            ).first()
            if parent is None:
                raise ExecutionRepositoryError("execution_run_not_found")
            rows = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM agent_run_state_versions "
                            "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                            "ORDER BY version",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(run.workspace_id),
                        "run_id": str(run.id),
                    },
                )
                .mappings()
                .all()
            )
            if not rows:
                raise ExecutionRepositoryError("execution_run_state_not_found")
            existing = next(
                (row for row in rows if int(row["version"]) == run.version),
                None,
            )
            if existing is not None:
                stored = self._run_from_row(existing)
                if stored == run:
                    return stored
                raise ExecutionRepositoryError(
                    "execution_idempotency_payload_mismatch"
                )
            latest = self._run_from_row(rows[-1])
            if (
                latest.version != expected_prior_version
                or run.version != expected_prior_version + 1
                or run.created_at != latest.created_at
            ):
                raise ExecutionRepositoryError("execution_run_version_conflict")
            try:
                connection.execute(
                    text(
                        "INSERT INTO agent_run_state_versions "
                        "(workspace_id, run_id, version, state, created_at, updated_at, "
                        "canonical_digest) VALUES (:workspace_id, :run_id, :version, "
                        ":state, :created_at, :updated_at, :canonical_digest)"
                    ),
                    {
                        "workspace_id": str(run.workspace_id),
                        "run_id": str(run.id),
                        "version": run.version,
                        "state": run.state.value,
                        "created_at": run.created_at.isoformat(),
                        "updated_at": run.updated_at.isoformat(),
                        "canonical_digest": run.canonical_digest,
                    },
                )
            except IntegrityError as exc:
                raise ExecutionRepositoryError(
                    "execution_run_version_conflict"
                ) from exc
            return run

    def append_step_state(
        self,
        step: ExecutionStep,
        *,
        expected_prior_version: int,
    ) -> ExecutionStep:
        with self._transaction() as connection:
            identity = connection.execute(
                text(
                    self._locked(
                        "SELECT 1 FROM run_steps WHERE workspace_id = :workspace_id "
                        "AND run_id = :run_id AND id = :step_id",
                        connection,
                    )
                ),
                {
                    "workspace_id": str(step.workspace_id),
                    "run_id": str(step.run_id),
                    "step_id": str(step.id),
                },
            ).first()
            if identity is None:
                raise ExecutionRepositoryError("execution_step_not_found")
            rows = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_step_versions "
                            "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                            "AND step_id = :step_id ORDER BY version",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(step.workspace_id),
                        "run_id": str(step.run_id),
                        "step_id": str(step.id),
                    },
                )
                .mappings()
                .all()
            )
            if not rows:
                raise ExecutionRepositoryError("execution_step_state_not_found")
            existing = next(
                (row for row in rows if int(row["version"]) == step.version),
                None,
            )
            if existing is not None:
                stored = self._step_from_row(existing)
                if stored == step:
                    return stored
                raise ExecutionRepositoryError(
                    "execution_idempotency_payload_mismatch"
                )
            latest = self._step_from_row(rows[-1])
            if (
                latest.version != expected_prior_version
                or step.version != expected_prior_version + 1
                or step.fence != latest.fence + 1
                or step.created_at != latest.created_at
            ):
                raise ExecutionRepositoryError("execution_step_version_conflict")
            try:
                self._insert_step_version(connection, step)
            except IntegrityError as exc:
                raise ExecutionRepositoryError(
                    "execution_step_version_conflict"
                ) from exc
            return step

    @staticmethod
    def _insert_step_version(connection: Connection, step: ExecutionStep) -> None:
        connection.execute(
            text(
                "INSERT INTO run_step_versions (workspace_id, run_id, step_id, version, "
                "state, fence, retry_count, attempt_count, created_at, updated_at, "
                "canonical_digest) VALUES (:workspace_id, :run_id, :step_id, :version, "
                ":state, :fence, :retry_count, :attempt_count, :created_at, :updated_at, "
                ":canonical_digest)"
            ),
            {
                "workspace_id": str(step.workspace_id),
                "run_id": str(step.run_id),
                "step_id": str(step.id),
                "version": step.version,
                "state": step.state.value,
                "fence": step.fence,
                "retry_count": step.retry_count,
                "attempt_count": step.attempt_count,
                "created_at": step.created_at.isoformat(),
                "updated_at": step.updated_at.isoformat(),
                "canonical_digest": step.canonical_digest,
            },
        )

    def acquire_step_lease(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
        worker_id: str,
        lease_token: str,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> ExecutionStepLease:
        lease = ExecutionStepLease(
            workspace_id=workspace_id,
            run_id=run_id,
            step_id=step_id,
            fence=1,
            worker_id=worker_id,
            lease_token_digest=_token_digest(lease_token),
            acquired_at=acquired_at,
            heartbeat_at=acquired_at,
            expires_at=expires_at,
        )
        with self._transaction() as connection:
            step_row = (
                connection.execute(
                    text(self._locked(_STEP_SQL, connection)),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .first()
            )
            if step_row is None:
                raise ExecutionRepositoryError("execution_step_not_found")
            step = self._step_from_row(step_row)
            prior_lease_rows = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_step_leases WHERE "
                            "workspace_id = :workspace_id AND run_id = :run_id "
                            "AND step_id = :step_id ORDER BY fence",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .all()
            )
            active_row = next(
                (row for row in reversed(prior_lease_rows) if row["released_at"] is None),
                None,
            )
            if active_row is not None:
                active = self._lease_from_row(active_row)
                if active.expires_at > acquired_at:
                    raise ExecutionRepositoryError("execution_step_lease_active")
                connection.execute(
                    text(
                        "UPDATE run_step_leases SET released_at = :released_at "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "AND step_id = :step_id AND fence = :fence "
                        "AND released_at IS NULL"
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                        "fence": active.fence,
                        "released_at": acquired_at.isoformat(),
                    },
                )
            if prior_lease_rows:
                next_fence = max(int(row["fence"]) for row in prior_lease_rows) + 1
                step_payload = {
                    **step.model_dump(mode="python", exclude={"canonical_digest"}),
                    "fence": next_fence,
                    "version": step.version + 1,
                    "updated_at": acquired_at,
                }
                step = ExecutionStep(
                    **{
                        **step_payload,
                        "canonical_digest": compute_execution_step_digest(step_payload),
                    }
                )
                try:
                    self._insert_step_version(connection, step)
                except IntegrityError as exc:
                    raise ExecutionRepositoryError(
                        "execution_step_lease_fence_conflict"
                    ) from exc
            lease = lease.model_copy(update={"fence": step.fence})
            try:
                connection.execute(
                    text(
                        "INSERT INTO run_step_leases (workspace_id, run_id, step_id, fence, "
                        "worker_id, lease_token_digest, acquired_at, heartbeat_at, expires_at, "
                        "released_at) VALUES (:workspace_id, :run_id, :step_id, :fence, "
                        ":worker_id, :lease_token_digest, :acquired_at, :heartbeat_at, "
                        ":expires_at, NULL)"
                    ),
                    {
                        **_uuid_values(lease.model_dump(mode="python")),
                        "acquired_at": lease.acquired_at.isoformat(),
                        "heartbeat_at": lease.heartbeat_at.isoformat(),
                        "expires_at": lease.expires_at.isoformat(),
                    },
                )
            except IntegrityError as exc:
                raise ExecutionRepositoryError("execution_step_lease_active") from exc
            return lease

    def record_checkpoint(
        self,
        checkpoint: ExecutionCheckpoint,
        *,
        request_context_id: UUID,
        authorization_snapshot_id: UUID,
        lease_fence: int,
        lease_token: str,
    ) -> ExecutionCheckpoint:
        with self._transaction() as connection:
            run_row = (
                connection.execute(
                    text(self._locked(_RUN_SQL, connection)),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                    },
                )
                .mappings()
                .first()
            )
            if run_row is None:
                raise ExecutionRepositoryError("execution_run_not_found")
            run = self._run_from_row(run_row)
            step_row = (
                connection.execute(
                    text(self._locked(_STEP_SQL, connection)),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                        "step_id": str(checkpoint.step_id),
                    },
                )
                .mappings()
                .first()
            )
            if step_row is None:
                raise ExecutionRepositoryError("execution_step_not_found")
            step = self._step_from_row(step_row)
            checkpoint_rows = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_checkpoints "
                            "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                            "AND step_id = :step_id ORDER BY checkpoint_version",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                        "step_id": str(checkpoint.step_id),
                    },
                )
                .mappings()
                .all()
            )
            existing_checkpoint = next(
                (
                    row
                    for row in checkpoint_rows
                    if row["id"] == str(checkpoint.id)
                    or int(row["checkpoint_version"])
                    == checkpoint.checkpoint_version
                ),
                None,
            )
            if existing_checkpoint is not None:
                stored = self._checkpoint_from_row(connection, existing_checkpoint)
                if (
                    stored == checkpoint
                    and existing_checkpoint["request_context_id"]
                    == str(request_context_id)
                    and existing_checkpoint["authorization_snapshot_id"]
                    == str(authorization_snapshot_id)
                ):
                    return stored
                raise ExecutionRepositoryError(
                    "execution_idempotency_payload_mismatch"
                )
            expected_checkpoint_version = (
                1
                if not checkpoint_rows
                else int(checkpoint_rows[-1]["checkpoint_version"]) + 1
            )
            if checkpoint.checkpoint_version != expected_checkpoint_version:
                raise ExecutionRepositoryError(
                    "execution_checkpoint_version_conflict"
                )
            if step.fence != checkpoint.step_fence:
                raise ExecutionRepositoryError("execution_step_lease_stale")
            if (
                run.state is not checkpoint.run_state
                or step.state is not checkpoint.step_state
                or step.version != checkpoint.step_version
                or step.retry_count != checkpoint.retry_count
                or step.attempt_count != checkpoint.attempt_count
            ):
                raise ExecutionRepositoryError("execution_checkpoint_state_stale")
            lease_row = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_step_leases WHERE "
                            "workspace_id = :workspace_id AND run_id = :run_id "
                            "AND step_id = :step_id AND fence = :fence "
                            "AND released_at IS NULL",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                        "step_id": str(checkpoint.step_id),
                        "fence": lease_fence,
                    },
                )
                .mappings()
                .first()
            )
            if lease_row is None or lease_row["lease_token_digest"] != _token_digest(
                lease_token
            ):
                raise ExecutionRepositoryError("execution_step_lease_stale")
            lease = self._lease_from_row(lease_row)
            if (
                lease.fence != checkpoint.step_fence
                or checkpoint.created_at < lease.acquired_at
                or checkpoint.created_at >= lease.expires_at
            ):
                raise ExecutionRepositoryError("execution_step_lease_stale")
            authority = connection.execute(
                text(
                    self._locked(
                        "SELECT 1 FROM authorization_decision_snapshots "
                        "WHERE workspace_id = :workspace_id "
                        "AND request_context_id = :request_context_id "
                        "AND id = :authorization_snapshot_id",
                        connection,
                    )
                ),
                {
                    "workspace_id": str(checkpoint.workspace_id),
                    "request_context_id": str(request_context_id),
                    "authorization_snapshot_id": str(authorization_snapshot_id),
                },
            ).first()
            if authority is None:
                raise ExecutionRepositoryError(
                    "execution_checkpoint_authority_context_not_found"
                )
            event_head = connection.execute(
                text(
                    self._locked(
                        "SELECT sequence, event_digest FROM agent_run_events "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "ORDER BY sequence DESC LIMIT 1",
                        connection,
                    )
                ),
                {
                    "workspace_id": str(checkpoint.workspace_id),
                    "run_id": str(checkpoint.run_id),
                },
            ).first()
            event_matches = (
                event_head is None
                and checkpoint.last_accepted_event_sequence == 0
                and checkpoint.last_accepted_event_digest == "0" * 64
            ) or (
                event_head is not None
                and int(event_head.sequence)
                == checkpoint.last_accepted_event_sequence
                and event_head.event_digest
                == checkpoint.last_accepted_event_digest
            )
            if not event_matches:
                raise ExecutionRepositoryError("execution_checkpoint_event_mismatch")
            for artifact_id in sorted(checkpoint.artifact_ref_ids, key=str):
                artifact = connection.execute(
                    text(
                        self._locked(
                            "SELECT 1 FROM run_artifacts WHERE workspace_id = :workspace_id "
                            "AND run_id = :run_id AND id = :artifact_id",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                        "artifact_id": str(artifact_id),
                    },
                ).first()
                if artifact is None:
                    raise ExecutionRepositoryError(
                        "execution_checkpoint_artifact_not_found"
                    )
            try:
                connection.execute(
                    text(
                        "INSERT INTO run_checkpoints (workspace_id, run_id, step_id, id, "
                        "checkpoint_version, run_state, step_state, step_fence, step_version, "
                        "request_context_id, authorization_snapshot_id, "
                        "completed_dependency_step_ids_json, output_ref_ids_json, retry_count, "
                        "attempt_count, last_accepted_event_sequence, "
                        "last_accepted_event_digest, next_transition, created_at, "
                        "canonical_digest) VALUES (:workspace_id, :run_id, :step_id, :id, "
                        ":checkpoint_version, :run_state, :step_state, :step_fence, "
                        ":step_version, :request_context_id, :authorization_snapshot_id, "
                        ":completed_dependency_step_ids_json, :output_ref_ids_json, "
                        ":retry_count, :attempt_count, :last_accepted_event_sequence, "
                        ":last_accepted_event_digest, :next_transition, :created_at, "
                        ":canonical_digest)"
                    ),
                    {
                        "workspace_id": str(checkpoint.workspace_id),
                        "run_id": str(checkpoint.run_id),
                        "step_id": str(checkpoint.step_id),
                        "id": str(checkpoint.id),
                        "checkpoint_version": checkpoint.checkpoint_version,
                        "run_state": checkpoint.run_state.value,
                        "step_state": checkpoint.step_state.value,
                        "step_fence": checkpoint.step_fence,
                        "step_version": checkpoint.step_version,
                        "request_context_id": str(request_context_id),
                        "authorization_snapshot_id": str(
                            authorization_snapshot_id
                        ),
                        "completed_dependency_step_ids_json": json.dumps(
                            [str(value) for value in checkpoint.completed_dependency_step_ids],
                            separators=(",", ":"),
                        ),
                        "output_ref_ids_json": json.dumps(
                            [str(value) for value in checkpoint.output_ref_ids],
                            separators=(",", ":"),
                        ),
                        "retry_count": checkpoint.retry_count,
                        "attempt_count": checkpoint.attempt_count,
                        "last_accepted_event_sequence": (
                            checkpoint.last_accepted_event_sequence
                        ),
                        "last_accepted_event_digest": (
                            checkpoint.last_accepted_event_digest
                        ),
                        "next_transition": checkpoint.next_transition.value,
                        "created_at": checkpoint.created_at.isoformat(),
                        "canonical_digest": checkpoint.canonical_digest,
                    },
                )
                for ordinal, artifact_id in enumerate(
                    checkpoint.artifact_ref_ids,
                    start=1,
                ):
                    connection.execute(
                        text(
                            "INSERT INTO run_checkpoint_artifacts "
                            "(workspace_id, run_id, checkpoint_id, artifact_id, ordinal) "
                            "VALUES (:workspace_id, :run_id, :checkpoint_id, "
                            ":artifact_id, :ordinal)"
                        ),
                        {
                            "workspace_id": str(checkpoint.workspace_id),
                            "run_id": str(checkpoint.run_id),
                            "checkpoint_id": str(checkpoint.id),
                            "artifact_id": str(artifact_id),
                            "ordinal": ordinal,
                        },
                    )
            except IntegrityError as exc:
                raise ExecutionRepositoryError(
                    "execution_checkpoint_binding_invalid"
                ) from exc
            return checkpoint

    def release_step_lease(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
        lease_fence: int,
        lease_token: str,
        released_at: datetime,
    ) -> ExecutionStepLease:
        with self._transaction() as connection:
            step_row = (
                connection.execute(
                    text(self._locked(_STEP_SQL, connection)),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .first()
            )
            if step_row is None:
                raise ExecutionRepositoryError("execution_step_not_found")
            step = self._step_from_row(step_row)
            lease_row = (
                connection.execute(
                    text(
                        self._locked(
                            "SELECT * FROM run_step_leases WHERE "
                            "workspace_id = :workspace_id AND run_id = :run_id "
                            "AND step_id = :step_id AND fence = :fence",
                            connection,
                        )
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                        "fence": lease_fence,
                    },
                )
                .mappings()
                .first()
            )
            if lease_row is None:
                raise ExecutionRepositoryError("execution_step_lease_stale")
            lease = self._lease_from_row(lease_row)
            if (
                step.fence != lease_fence
                or lease.lease_token_digest != _token_digest(lease_token)
            ):
                raise ExecutionRepositoryError("execution_step_lease_stale")
            released = ExecutionStepLease(
                **{
                    **lease.model_dump(mode="python"),
                    "released_at": released_at,
                }
            )
            if lease.released_at is not None:
                if lease.released_at == released_at:
                    return lease
                raise ExecutionRepositoryError("execution_step_lease_stale")
            try:
                connection.execute(
                    text(
                        "UPDATE run_step_leases SET released_at = :released_at "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "AND step_id = :step_id AND fence = :fence "
                        "AND released_at IS NULL"
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                        "fence": lease_fence,
                        "released_at": released_at.isoformat(),
                    },
                )
            except IntegrityError as exc:
                raise ExecutionRepositoryError(
                    "execution_step_lease_release_invalid"
                ) from exc
            return released

    def get_latest_run_state(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> ExecutionRun | None:
        with self._connection() as connection:
            row = (
                connection.execute(
                    text(_RUN_SQL),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                    },
                )
                .mappings()
                .first()
            )
            return None if row is None else self._run_from_row(row)

    def list_run_states(
        self,
        workspace_id: UUID,
        run_id: UUID,
    ) -> tuple[ExecutionRun, ...]:
        with self._connection() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT * FROM agent_run_state_versions "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "ORDER BY version"
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                    },
                )
                .mappings()
                .all()
            )
            return tuple(self._run_from_row(row) for row in rows)

    def get_current_step_state(
        self,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
    ) -> ExecutionStep | None:
        with self._connection() as connection:
            row = (
                connection.execute(
                    text(_STEP_SQL),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .first()
            )
            return None if row is None else self._step_from_row(row)

    def list_step_states(
        self,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
    ) -> tuple[ExecutionStep, ...]:
        with self._connection() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT * FROM run_step_versions "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "AND step_id = :step_id ORDER BY version"
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .all()
            )
            return tuple(self._step_from_row(row) for row in rows)

    def get_active_step_lease(
        self,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
    ) -> ExecutionStepLease | None:
        with self._connection() as connection:
            row = (
                connection.execute(
                    text(_LEASE_SQL),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .first()
            )
            return None if row is None else self._lease_from_row(row)

    def get_latest_checkpoint(
        self,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
    ) -> ExecutionCheckpoint | None:
        with self._connection() as connection:
            row = (
                connection.execute(
                    text(_CHECKPOINT_SQL),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .first()
            )
            return (
                None
                if row is None
                else self._checkpoint_from_row(connection, row)
            )

    def list_checkpoints(
        self,
        workspace_id: UUID,
        run_id: UUID,
        step_id: UUID,
    ) -> tuple[ExecutionCheckpoint, ...]:
        with self._connection() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT * FROM run_checkpoints "
                        "WHERE workspace_id = :workspace_id AND run_id = :run_id "
                        "AND step_id = :step_id ORDER BY checkpoint_version"
                    ),
                    {
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "step_id": str(step_id),
                    },
                )
                .mappings()
                .all()
            )
            return tuple(
                self._checkpoint_from_row(connection, row) for row in rows
            )

    def close(self) -> None:
        if self._owns_engine:
            self.engine.dispose()
