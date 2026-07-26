"""Add durable execution state, steps, leases, and checkpoints.

Revision ID: m2_004_durable_execution
Revises: m2_003_conversations
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from corvus.infrastructure.migrations.manifest_history import (
    M2_003_FAMILY_NAMES,
    family_proof_metadata,
)
from corvus.infrastructure.migrations.trigger_ddl import (
    create_immutable_triggers,
    create_reject_trigger,
    drop_immutable_triggers,
    drop_reject_trigger,
)

revision: str = "m2_004_durable_execution"
down_revision: str | None = "m2_003_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_MANIFEST_ID = "00000000-0000-4000-8000-000000000013"
_PRIOR_MANIFEST_ID = "00000000-0000-4000-8000-000000000012"
_NEW_FAMILIES = {
    "agent_run_state_versions",
    "run_checkpoint_artifacts",
    "run_checkpoints",
    "run_step_leases",
    "run_step_versions",
    "run_steps",
}
_IMMUTABLE_FAMILIES = _NEW_FAMILIES - {"run_step_leases"}
_HISTORY_COUNT_SQL = sa.text(
    "SELECT (SELECT COUNT(*) FROM agent_run_state_versions) + "
    "(SELECT COUNT(*) FROM run_checkpoint_artifacts) + "
    "(SELECT COUNT(*) FROM run_checkpoints) + "
    "(SELECT COUNT(*) FROM run_step_leases) + "
    "(SELECT COUNT(*) FROM run_step_versions) + "
    "(SELECT COUNT(*) FROM run_steps)"
)
_RUN_STATES = "'pending','running','paused','completed','failed','cancelled'"
_STEP_STATES = (
    "'pending','blocked','ready','running','paused','completed','failed','cancelled'"
)
_NEXT_TRANSITIONS = "'dispatch','resume','retry','wait','complete','fail','cancel'"
_GENESIS_DIGEST = "0" * 64
_LEASE_UPDATE_TRIGGER = "run_step_leases_guard_update"


def _manifest_families(bind: sa.Connection) -> list[dict[str, object]]:
    if op.get_context().as_sql:
        prior = set(M2_003_FAMILY_NAMES)
    else:
        prior = {
            str(row[0])
            for row in bind.execute(
                sa.text(
                    "SELECT family_name FROM authority_state_root_leaf_families "
                    "WHERE manifest_version_id = :id"
                ),
                {"id": _PRIOR_MANIFEST_ID},
            ).fetchall()
        }
    if prior != set(M2_003_FAMILY_NAMES):
        raise RuntimeError("prior authority manifest family set mismatch")
    return [
        {
            "ordinal": ordinal,
            "family_name": family_name,
            "coverage_kind": family_proof_metadata(family_name)[0],
            "external_proof_kind": family_proof_metadata(family_name)[1],
            "canonicalization_version": 1,
        }
        for ordinal, family_name in enumerate(sorted(prior | _NEW_FAMILIES), start=1)
    ]


def _insert_manifest(bind: sa.Connection) -> None:
    families = _manifest_families(bind)
    body = {"schema_version": 10, "canonicalization_version": 1, "families": families}
    manifest_digest = hashlib.sha256(
        json.dumps(body, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    manifest = {
        "id": _SEED_MANIFEST_ID,
        "schema_version": 10,
        "canonicalization_version": 1,
        "manifest_digest": manifest_digest,
        "status": "active",
        "created_at": "2026-07-26T00:00:00Z",
    }
    bind.execute(
        sa.text(
            "INSERT INTO authority_state_root_manifests "
            "(id, schema_version, canonicalization_version, manifest_digest, status, "
            "created_at, payload_json) VALUES (:id, :schema_version, :canonicalization_version, "
            ":manifest_digest, :status, :created_at, :payload_json)"
        ),
        {**manifest, "payload_json": json.dumps(manifest, separators=(",", ":"))},
    )
    for family in families:
        payload = {"manifest_version_id": _SEED_MANIFEST_ID, **family}
        bind.execute(
            sa.text(
                "INSERT INTO authority_state_root_leaf_families "
                "(manifest_version_id, ordinal, family_name, coverage_kind, "
                "external_proof_kind, canonicalization_version, payload_json) "
                "VALUES (:manifest_version_id, :ordinal, :family_name, :coverage_kind, "
                ":external_proof_kind, :canonicalization_version, :payload_json)"
            ),
            {**payload, "payload_json": json.dumps(payload, separators=(",", ":"))},
        )


def _run_fk(local_run_id: str = "run_id") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", local_run_id],
        ["agent_runs.workspace_id", "agent_runs.id"],
        name=f"fk_durable_execution_{local_run_id}_run",
        ondelete="RESTRICT",
    )


def _step_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", "run_id", "step_id"],
        ["run_steps.workspace_id", "run_steps.run_id", "run_steps.id"],
        name="fk_durable_execution_step",
        ondelete="RESTRICT",
    )


def _create_tables() -> None:
    op.create_index(
        "uq_authorization_snapshots_workspace_request_id",
        "authorization_decision_snapshots",
        ["workspace_id", "request_context_id", "id"],
        unique=True,
    )
    op.create_index(
        "uq_run_artifacts_workspace_run_id",
        "run_artifacts",
        ["workspace_id", "run_id", "id"],
        unique=True,
    )
    op.create_table(
        "agent_run_state_versions",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_agent_run_state_versions_version"),
        sa.CheckConstraint(
            f"state IN ({_RUN_STATES})", name="ck_agent_run_state_versions_state"
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name="ck_agent_run_state_versions_timestamps"
        ),
        sa.CheckConstraint(
            "length(canonical_digest) = 64", name="ck_agent_run_state_versions_digest"
        ),
        _run_fk(),
        sa.PrimaryKeyConstraint(
            "workspace_id", "run_id", "version", name="pk_agent_run_state_versions"
        ),
    )
    op.create_index(
        "ix_agent_run_state_versions_recovery",
        "agent_run_state_versions",
        ["workspace_id", "state", "updated_at", "run_id", "version"],
    )
    op.create_table(
        "run_steps",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("step_key", sa.String(512), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("parent_step_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("length(trim(step_key)) >= 1", name="ck_run_steps_key"),
        sa.CheckConstraint("ordinal >= 1", name="ck_run_steps_ordinal"),
        sa.CheckConstraint(
            "length(trim(kind)) BETWEEN 1 AND 100",
            name="ck_run_steps_kind",
        ),
        sa.CheckConstraint("length(input_digest) = 64", name="ck_run_steps_input_digest"),
        sa.CheckConstraint(
            "parent_step_id IS NULL OR parent_step_id <> id",
            name="ck_run_steps_parent_not_self",
        ),
        _run_fk(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id", "parent_step_id"],
            ["run_steps.workspace_id", "run_steps.run_id", "run_steps.id"],
            name="fk_run_steps_parent",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "id", name="pk_run_steps"),
        sa.UniqueConstraint(
            "workspace_id", "run_id", "id", name="uq_run_steps_workspace_run_id"
        ),
        sa.UniqueConstraint(
            "workspace_id", "run_id", "step_key", name="uq_run_steps_key"
        ),
        sa.UniqueConstraint(
            "workspace_id", "run_id", "ordinal", name="uq_run_steps_ordinal"
        ),
    )
    op.create_index(
        "ix_run_steps_recovery",
        "run_steps",
        ["workspace_id", "run_id", "ordinal", "id"],
    )
    op.create_table(
        "run_step_versions",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("step_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("fence", sa.BigInteger(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_run_step_versions_version"),
        sa.CheckConstraint(
            f"state IN ({_STEP_STATES})", name="ck_run_step_versions_state"
        ),
        sa.CheckConstraint("fence >= 1", name="ck_run_step_versions_fence"),
        sa.CheckConstraint("retry_count >= 0", name="ck_run_step_versions_retry_count"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_run_step_versions_attempt_count"),
        sa.CheckConstraint(
            "retry_count <= attempt_count", name="ck_run_step_versions_retry_attempt"
        ),
        sa.CheckConstraint("updated_at >= created_at", name="ck_run_step_versions_timestamps"),
        sa.CheckConstraint(
            "length(canonical_digest) = 64", name="ck_run_step_versions_digest"
        ),
        _step_fk(),
        sa.PrimaryKeyConstraint(
            "workspace_id", "step_id", "version", name="pk_run_step_versions"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "run_id",
            "step_id",
            "version",
            "fence",
            name="uq_run_step_versions_checkpoint_ref",
        ),
    )
    op.create_index(
        "ix_run_step_versions_recovery",
        "run_step_versions",
        ["workspace_id", "state", "updated_at", "run_id", "step_id", "version"],
    )
    op.create_table(
        "run_step_leases",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("step_id", sa.String(36), nullable=False),
        sa.Column("fence", sa.BigInteger(), nullable=False),
        sa.Column("worker_id", sa.String(255), nullable=False),
        sa.Column("lease_token_digest", sa.String(64), nullable=False),
        sa.Column("acquired_at", sa.String(40), nullable=False),
        sa.Column("heartbeat_at", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("released_at", sa.String(40), nullable=True),
        sa.CheckConstraint("fence >= 1", name="ck_run_step_leases_fence"),
        sa.CheckConstraint("length(trim(worker_id)) >= 1", name="ck_run_step_leases_worker"),
        sa.CheckConstraint(
            "length(lease_token_digest) = 64", name="ck_run_step_leases_token_digest"
        ),
        sa.CheckConstraint(
            "heartbeat_at >= acquired_at AND expires_at > acquired_at",
            name="ck_run_step_leases_window",
        ),
        sa.CheckConstraint(
            "released_at IS NULL OR released_at >= acquired_at",
            name="ck_run_step_leases_release",
        ),
        _step_fk(),
        sa.PrimaryKeyConstraint(
            "workspace_id", "run_id", "step_id", "fence", name="pk_run_step_leases"
        ),
        sa.UniqueConstraint(
            "workspace_id", "lease_token_digest", name="uq_run_step_leases_token"
        ),
    )
    op.create_index(
        "uq_run_step_leases_active",
        "run_step_leases",
        ["workspace_id", "run_id", "step_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
        sqlite_where=sa.text("released_at IS NULL"),
    )
    op.create_index(
        "ix_run_step_leases_recovery",
        "run_step_leases",
        ["workspace_id", "expires_at", "run_id", "step_id", "fence"],
        postgresql_where=sa.text("released_at IS NULL"),
        sqlite_where=sa.text("released_at IS NULL"),
    )
    op.create_table(
        "run_checkpoints",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("step_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False),
        sa.Column("run_state", sa.String(16), nullable=False),
        sa.Column("step_state", sa.String(16), nullable=False),
        sa.Column("step_fence", sa.BigInteger(), nullable=False),
        sa.Column("step_version", sa.Integer(), nullable=False),
        sa.Column("request_context_id", sa.String(36), nullable=False),
        sa.Column("authorization_snapshot_id", sa.String(36), nullable=False),
        sa.Column("completed_dependency_step_ids_json", sa.Text(), nullable=False),
        sa.Column("output_ref_ids_json", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_accepted_event_sequence", sa.Integer(), nullable=False),
        sa.Column("last_accepted_event_digest", sa.String(64), nullable=False),
        sa.Column("next_transition", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "checkpoint_version >= 1", name="ck_run_checkpoints_checkpoint_version"
        ),
        sa.CheckConstraint(f"run_state IN ({_RUN_STATES})", name="ck_run_checkpoints_run_state"),
        sa.CheckConstraint(
            f"step_state IN ({_STEP_STATES})", name="ck_run_checkpoints_step_state"
        ),
        sa.CheckConstraint("step_fence >= 1", name="ck_run_checkpoints_step_fence"),
        sa.CheckConstraint("step_version >= 1", name="ck_run_checkpoints_step_version"),
        sa.CheckConstraint("retry_count >= 0", name="ck_run_checkpoints_retry_count"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_run_checkpoints_attempt_count"),
        sa.CheckConstraint(
            "retry_count <= attempt_count", name="ck_run_checkpoints_retry_attempt"
        ),
        sa.CheckConstraint(
            "last_accepted_event_sequence >= 0", name="ck_run_checkpoints_event_sequence"
        ),
        sa.CheckConstraint(
            "length(last_accepted_event_digest) = 64", name="ck_run_checkpoints_event_digest"
        ),
        sa.CheckConstraint(
            f"(last_accepted_event_sequence = 0) = "
            f"(last_accepted_event_digest = '{_GENESIS_DIGEST}')",
            name="ck_run_checkpoints_event_sentinel",
        ),
        sa.CheckConstraint(
            f"next_transition IN ({_NEXT_TRANSITIONS})",
            name="ck_run_checkpoints_next_transition",
        ),
        sa.CheckConstraint(
            "(next_transition = 'dispatch' AND run_state IN ('pending','running') "
            "AND step_state = 'ready') OR "
            "(next_transition = 'resume' AND run_state IN ('running','paused') "
            "AND step_state = 'paused') OR "
            "(next_transition = 'retry' AND run_state IN ('running','paused') "
            "AND step_state = 'failed') OR "
            "(next_transition = 'wait' AND "
            "((run_state = 'pending' AND step_state IN ('pending','blocked','ready')) OR "
            "(run_state = 'running' AND step_state IN "
            "('pending','blocked','ready','running','paused','completed')) OR "
            "(run_state = 'paused' AND step_state IN "
            "('pending','blocked','ready','paused')))) OR "
            "(next_transition = 'complete' AND run_state = 'completed' "
            "AND step_state = 'completed') OR "
            "(next_transition = 'fail' AND run_state = 'failed' "
            "AND step_state = 'failed') OR "
            "(next_transition = 'cancel' AND run_state = 'cancelled' "
            "AND step_state = 'cancelled')",
            name="ck_run_checkpoints_transition",
        ),
        sa.CheckConstraint(
            "length(canonical_digest) = 64", name="ck_run_checkpoints_digest"
        ),
        _step_fk(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id", "step_id", "step_version", "step_fence"],
            [
                "run_step_versions.workspace_id",
                "run_step_versions.run_id",
                "run_step_versions.step_id",
                "run_step_versions.version",
                "run_step_versions.fence",
            ],
            name="fk_run_checkpoints_step_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "request_context_id", "authorization_snapshot_id"],
            [
                "authorization_decision_snapshots.workspace_id",
                "authorization_decision_snapshots.request_context_id",
                "authorization_decision_snapshots.id",
            ],
            name="fk_run_checkpoints_authority_context",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "id", name="pk_run_checkpoints"),
        sa.UniqueConstraint(
            "workspace_id", "run_id", "id", name="uq_run_checkpoints_workspace_run_id"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "run_id",
            "step_id",
            "checkpoint_version",
            name="uq_run_checkpoints_sequence",
        ),
    )
    op.create_index(
        "ix_run_checkpoints_recovery",
        "run_checkpoints",
        ["workspace_id", "run_id", "step_id", "checkpoint_version"],
    )
    op.create_table(
        "run_checkpoint_artifacts",
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("checkpoint_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal >= 1", name="ck_run_checkpoint_artifacts_ordinal"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id", "checkpoint_id"],
            ["run_checkpoints.workspace_id", "run_checkpoints.run_id", "run_checkpoints.id"],
            name="fk_run_checkpoint_artifacts_checkpoint",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id", "artifact_id"],
            ["run_artifacts.workspace_id", "run_artifacts.run_id", "run_artifacts.id"],
            name="fk_run_checkpoint_artifacts_artifact",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "workspace_id", "checkpoint_id", "artifact_id", name="pk_run_checkpoint_artifacts"
        ),
        sa.UniqueConstraint(
            "workspace_id", "checkpoint_id", "ordinal", name="uq_run_checkpoint_artifacts_ordinal"
        ),
    )
    op.create_index(
        "ix_run_checkpoint_artifacts_lookup",
        "run_checkpoint_artifacts",
        ["workspace_id", "run_id", "artifact_id", "checkpoint_id"],
    )


def _create_lease_update_trigger() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "sqlite":
        op.execute(
            f"CREATE TRIGGER {_LEASE_UPDATE_TRIGGER} BEFORE UPDATE ON run_step_leases "
            "BEGIN "
            "SELECT CASE WHEN OLD.released_at IS NOT NULL "
            "THEN RAISE(ABORT, 'released run step lease is immutable') END; "
            "SELECT CASE WHEN "
            "NEW.workspace_id <> OLD.workspace_id OR NEW.run_id <> OLD.run_id OR "
            "NEW.step_id <> OLD.step_id OR NEW.fence <> OLD.fence OR "
            "NEW.worker_id <> OLD.worker_id OR "
            "NEW.lease_token_digest <> OLD.lease_token_digest OR "
            "NEW.acquired_at <> OLD.acquired_at "
            "THEN RAISE(ABORT, 'run step lease identity is immutable') END; "
            "SELECT CASE WHEN NEW.expires_at < OLD.expires_at "
            "THEN RAISE(ABORT, 'run step lease expiry cannot decrease') END; "
            "END"
        )
        return
    if dialect_name == "postgresql":
        op.execute(
            f"CREATE FUNCTION {_LEASE_UPDATE_TRIGGER}_fn() RETURNS trigger "
            "AS $corvus_trigger$ BEGIN "
            "IF OLD.released_at IS NOT NULL THEN "
            "RAISE EXCEPTION 'released run step lease is immutable'; END IF; "
            "IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id OR "
            "NEW.run_id IS DISTINCT FROM OLD.run_id OR "
            "NEW.step_id IS DISTINCT FROM OLD.step_id OR "
            "NEW.fence IS DISTINCT FROM OLD.fence OR "
            "NEW.worker_id IS DISTINCT FROM OLD.worker_id OR "
            "NEW.lease_token_digest IS DISTINCT FROM OLD.lease_token_digest OR "
            "NEW.acquired_at IS DISTINCT FROM OLD.acquired_at THEN "
            "RAISE EXCEPTION 'run step lease identity is immutable'; END IF; "
            "IF NEW.expires_at < OLD.expires_at THEN "
            "RAISE EXCEPTION 'run step lease expiry cannot decrease'; END IF; "
            "RETURN NEW; END; $corvus_trigger$ LANGUAGE plpgsql"
        )
        op.execute(
            f"CREATE TRIGGER {_LEASE_UPDATE_TRIGGER} BEFORE UPDATE ON run_step_leases "
            f"FOR EACH ROW EXECUTE FUNCTION {_LEASE_UPDATE_TRIGGER}_fn()"
        )
        return
    raise RuntimeError(f"unsupported_migration_dialect:{dialect_name}")


def _drop_lease_update_trigger() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "sqlite":
        op.execute(f"DROP TRIGGER {_LEASE_UPDATE_TRIGGER}")
        return
    if dialect_name == "postgresql":
        op.execute(f"DROP TRIGGER {_LEASE_UPDATE_TRIGGER} ON run_step_leases")
        op.execute(f"DROP FUNCTION {_LEASE_UPDATE_TRIGGER}_fn()")
        return
    raise RuntimeError(f"unsupported_migration_dialect:{dialect_name}")


def upgrade() -> None:
    _create_tables()
    for table_name in sorted(_IMMUTABLE_FAMILIES):
        create_immutable_triggers(table_name, table_name.replace("_", " "))
    create_reject_trigger("run_step_leases", "DELETE", "run step leases cannot be deleted")
    _create_lease_update_trigger()
    _insert_manifest(op.get_bind())


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("durable_execution_downgrade_requires_online_history_check")
    bind = op.get_bind()
    if bind.execute(_HISTORY_COUNT_SQL).scalar_one():
        raise RuntimeError("durable_execution_history_present")
    drop_immutable_triggers("authority_state_root_leaf_families")
    drop_immutable_triggers("authority_state_root_manifests")
    bind.execute(
        sa.text("DELETE FROM authority_state_root_leaf_families WHERE manifest_version_id = :id"),
        {"id": _SEED_MANIFEST_ID},
    )
    bind.execute(
        sa.text("DELETE FROM authority_state_root_manifests WHERE id = :id"),
        {"id": _SEED_MANIFEST_ID},
    )
    create_immutable_triggers("authority_state_root_manifests", "authority state-root manifests")
    create_immutable_triggers(
        "authority_state_root_leaf_families", "authority state-root leaf families"
    )
    for table_name in sorted(_IMMUTABLE_FAMILIES, reverse=True):
        drop_immutable_triggers(table_name)
    _drop_lease_update_trigger()
    drop_reject_trigger("run_step_leases", "DELETE")
    op.drop_index("ix_run_checkpoint_artifacts_lookup", table_name="run_checkpoint_artifacts")
    op.drop_table("run_checkpoint_artifacts")
    op.drop_index("ix_run_checkpoints_recovery", table_name="run_checkpoints")
    op.drop_table("run_checkpoints")
    op.drop_index("ix_run_step_leases_recovery", table_name="run_step_leases")
    op.drop_index("uq_run_step_leases_active", table_name="run_step_leases")
    op.drop_table("run_step_leases")
    op.drop_index("ix_run_step_versions_recovery", table_name="run_step_versions")
    op.drop_table("run_step_versions")
    op.drop_index("ix_run_steps_recovery", table_name="run_steps")
    op.drop_table("run_steps")
    op.drop_index(
        "ix_agent_run_state_versions_recovery", table_name="agent_run_state_versions"
    )
    op.drop_table("agent_run_state_versions")
    op.drop_index("uq_run_artifacts_workspace_run_id", table_name="run_artifacts")
    op.drop_index(
        "uq_authorization_snapshots_workspace_request_id",
        table_name="authorization_decision_snapshots",
    )
