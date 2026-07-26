"""Add immutable agent-run execution bindings.

Revision ID: m2_005_execution_binding
Revises: m2_004_durable_execution
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from corvus.infrastructure.migrations.manifest_history import (
    M2_004_FAMILY_NAMES,
    family_proof_metadata,
)
from corvus.infrastructure.migrations.trigger_ddl import (
    create_immutable_triggers,
    drop_immutable_triggers,
)

revision: str = "m2_005_execution_binding"
down_revision: str | None = "m2_004_durable_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "agent_run_execution_bindings"
_SEED_MANIFEST_ID = "00000000-0000-4000-8000-000000000014"
_PRIOR_MANIFEST_ID = "00000000-0000-4000-8000-000000000013"
_SCHEMA_VERSION = 11
_CREATED_AT = "2026-07-26T00:00:00Z"
_HISTORY_COUNT_SQL = sa.text("SELECT COUNT(*) FROM agent_run_execution_bindings")


def _manifest_families(bind: sa.Connection) -> list[dict[str, object]]:
    if op.get_context().as_sql:
        prior = set(M2_004_FAMILY_NAMES)
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
    if prior != set(M2_004_FAMILY_NAMES):
        raise RuntimeError("prior authority manifest family set mismatch")
    families = sorted({*prior, _TABLE_NAME})
    return [
        {
            "ordinal": ordinal,
            "family_name": family_name,
            "coverage_kind": family_proof_metadata(family_name)[0],
            "external_proof_kind": family_proof_metadata(family_name)[1],
            "canonicalization_version": 1,
        }
        for ordinal, family_name in enumerate(families, start=1)
    ]


def _insert_manifest(bind: sa.Connection) -> None:
    families = _manifest_families(bind)
    body = {
        "schema_version": _SCHEMA_VERSION,
        "canonicalization_version": 1,
        "families": families,
    }
    manifest_digest = hashlib.sha256(
        json.dumps(body, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    manifest = {
        "id": _SEED_MANIFEST_ID,
        "schema_version": _SCHEMA_VERSION,
        "canonicalization_version": 1,
        "manifest_digest": manifest_digest,
        "status": "active",
        "created_at": _CREATED_AT,
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


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("immutable_request_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "length(immutable_request_digest) = 64",
            name="ck_agent_run_execution_bindings_immutable_digest",
        ),
        sa.CheckConstraint(
            "length(canonical_digest) = 64",
            name="ck_agent_run_execution_bindings_canonical_digest",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id"],
            ["agent_runs.workspace_id", "agent_runs.id"],
            name="fk_agent_run_execution_bindings_run",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "workspace_id",
            "run_id",
            name="pk_agent_run_execution_bindings",
        ),
    )
    create_immutable_triggers(_TABLE_NAME, "agent run execution bindings")
    _insert_manifest(op.get_bind())


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("execution_binding_downgrade_requires_online_history_check")
    bind = op.get_bind()
    if bind.execute(_HISTORY_COUNT_SQL).scalar_one():
        raise RuntimeError("execution_binding_history_present")
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
        "authority_state_root_leaf_families",
        "authority state-root leaf families",
    )
    drop_immutable_triggers(_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
