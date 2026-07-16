from __future__ import annotations

import os
from collections.abc import Mapping

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from corvus.infrastructure.db import (
    M1_CURRENT_REVISION,
    M1_PROJECT_REVISION,
    current_revision_url,
    downgrade_database_url,
    upgrade_database_url,
)
from corvus.platform import create_platform_engine
from tests.postgres_safety import PostgresTestSafetyError, validate_disposable_postgres_url

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://corvus:corvus@127.0.0.1:55432/corvus_platform_test?connect_timeout=2"
)
_IMMUTABLE_TABLES = frozenset(
    {
        "access_bundles",
        "agent_grants",
        "agent_identities",
        "audit_receipts",
        "audit_result_bindings",
        "audience_policy_snapshots",
        "authority_close_certificates",
        "authority_handoff_activations",
        "authority_registries",
        "authority_registry_freshness_proofs",
        "authority_registry_trust_states",
        "authority_registry_verifier_keys",
        "authority_state_root_leaf_commitments",
        "authority_state_root_leaf_families",
        "authority_state_root_manifests",
        "authorization_decision_snapshots",
        "capability_grants",
        "delegation_grants",
        "deployment_profiles",
        "identity_workspaces",
        "principals",
        "restore_validation_receipts",
        "scopes",
        "workspace_memberships",
        "workspace_signing_key_versions",
    }
)
_DELETE_ONLY_TABLES = frozenset(
    {
        "audit_anchor_recovery_checkpoints",
        "authority_commit_intents",
        "authority_epoch_credentials",
        "authority_handoffs",
        "authority_trust_anchors",
        "deployment_instance_leases",
        "deployment_instances",
        "idempotency_envelopes",
        "workspace_authorities",
    }
)
EXPECTED_TRIGGER_NAMES = frozenset(
    {
        *(f"{table_name}_no_update" for table_name in _IMMUTABLE_TABLES),
        *(f"{table_name}_no_delete" for table_name in _IMMUTABLE_TABLES),
        *(f"{table_name}_no_delete" for table_name in _DELETE_ONLY_TABLES),
    }
)
EXPECTED_TRIGGER_FUNCTION_NAMES = frozenset(
    f"{trigger_name}_fn" for trigger_name in EXPECTED_TRIGGER_NAMES
)
EXPECTED_PARTIAL_INDEX_NAMES = frozenset(
    {
        "uq_authority_commit_intents_inflight_workspace",
        "uq_deployment_instance_leases_active_workspace_epoch",
    }
)


def _postgres_test_url() -> str:
    return os.environ.get("CORVUS_TEST_POSTGRES_URL", DEFAULT_TEST_DATABASE_URL)


def _require_reset_authorization(database_url: str) -> None:
    try:
        validate_disposable_postgres_url(database_url, environ=os.environ)
    except PostgresTestSafetyError as exc:
        pytest.skip(f"PostgreSQL destructive test disabled: {exc}")


def _schema_controls(
    connection: Connection,
) -> tuple[frozenset[str], frozenset[str], dict[str, str]]:
    triggers = frozenset(
        connection.execute(
            text(
                "SELECT trg.tgname FROM pg_trigger AS trg "
                "JOIN pg_class AS rel ON rel.oid = trg.tgrelid "
                "JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace "
                "WHERE NOT trg.tgisinternal AND ns.nspname = 'public'"
            )
        ).scalars()
    )
    functions = frozenset(
        connection.execute(
            text(
                "SELECT proc.proname FROM pg_proc AS proc "
                "JOIN pg_namespace AS ns ON ns.oid = proc.pronamespace "
                "WHERE ns.nspname = 'public' AND proc.proname LIKE '%_no_%_fn'"
            )
        ).scalars()
    )
    partial_indexes = {
        str(row.name): str(row.predicate)
        for row in connection.execute(
            text(
                "SELECT index_rel.relname AS name, "
                "pg_get_expr(idx.indpred, idx.indrelid, true) AS predicate "
                "FROM pg_index AS idx "
                "JOIN pg_class AS index_rel ON index_rel.oid = idx.indexrelid "
                "JOIN pg_class AS table_rel ON table_rel.oid = idx.indrelid "
                "JOIN pg_namespace AS ns ON ns.oid = table_rel.relnamespace "
                "WHERE ns.nspname = 'public' AND idx.indisunique "
                "AND idx.indpred IS NOT NULL"
            )
        )
    }
    return triggers, functions, partial_indexes


def _assert_head_schema_controls(connection: Connection) -> None:
    triggers, functions, partial_indexes = _schema_controls(connection)
    assert triggers == EXPECTED_TRIGGER_NAMES
    assert functions == EXPECTED_TRIGGER_FUNCTION_NAMES
    assert set(partial_indexes) == EXPECTED_PARTIAL_INDEX_NAMES
    lease_predicate = partial_indexes[
        "uq_deployment_instance_leases_active_workspace_epoch"
    ].casefold()
    intent_predicate = partial_indexes["uq_authority_commit_intents_inflight_workspace"].casefold()
    assert "released_at" in lease_predicate
    assert "is null" in lease_predicate
    assert "state" in intent_predicate
    assert "anchor_finalized" in intent_predicate
    assert "quarantined" in intent_predicate


def _assert_rejected(
    connection: Connection,
    statement: str,
    parameters: Mapping[str, object],
    *,
    error_type: type[DBAPIError],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        with connection.begin_nested():
            connection.execute(text(statement), parameters)


def _assert_runtime_constraints(connection: Connection) -> None:
    manifest_id = "00000000-0000-4000-8000-000000000009"
    _assert_rejected(
        connection,
        "UPDATE authority_state_root_manifests SET status = 'disabled' WHERE id = :id",
        {"id": manifest_id},
        error_type=DBAPIError,
        message="authority state-root manifests are immutable",
    )
    _assert_rejected(
        connection,
        "DELETE FROM authority_state_root_manifests WHERE id = :id",
        {"id": manifest_id},
        error_type=DBAPIError,
        message="authority state-root manifests cannot be deleted",
    )

    connection.execute(
        text(
            "INSERT INTO deployment_profiles (id, version, created_at, payload_json) "
            "VALUES ('profile-1', 1, '2026-07-16T00:00:00Z', '{}')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO deployment_instances "
            "(id, deployment_profile_id, status, device_binding_digest, activated_at, "
            "payload_json) VALUES "
            "('instance-1', 'profile-1', 'active', :digest, "
            "'2026-07-16T00:00:00Z', '{}')"
        ),
        {"digest": "a" * 64},
    )
    connection.execute(
        text(
            "INSERT INTO deployment_instance_leases "
            "(id, workspace_id, authority_epoch, deployment_instance_id, lock_name, "
            "fencing_token, acquired_at, released_at, payload_json) VALUES "
            "('lease-1', 'workspace-1', 1, 'instance-1', 'authority', 1, "
            "'2026-07-16T00:00:00Z', NULL, '{}')"
        )
    )
    _assert_rejected(
        connection,
        "INSERT INTO deployment_instance_leases "
        "(id, workspace_id, authority_epoch, deployment_instance_id, lock_name, "
        "fencing_token, acquired_at, released_at, payload_json) VALUES "
        "('lease-2', 'workspace-1', 1, 'instance-1', 'authority', 2, "
        "'2026-07-16T00:00:01Z', NULL, '{}')",
        {},
        error_type=IntegrityError,
        message="uq_deployment_instance_leases_active_workspace_epoch",
    )
    connection.execute(
        text(
            "INSERT INTO deployment_instance_leases "
            "(id, workspace_id, authority_epoch, deployment_instance_id, lock_name, "
            "fencing_token, acquired_at, released_at, payload_json) VALUES "
            "('lease-3', 'workspace-1', 1, 'instance-1', 'authority', 3, "
            "'2026-07-16T00:00:02Z', '2026-07-16T00:00:03Z', '{}')"
        )
    )

    connection.execute(
        text(
            "INSERT INTO authority_commit_intents "
            "(id, workspace_id, epoch, deployment_instance_id, prior_generation, "
            "next_generation, prior_state_root, mutation_digest, proposed_state_root, "
            "state, created_at, payload_json) VALUES "
            "('intent-1', 'workspace-2', 1, 'instance-1', 0, 1, :prior_root, "
            ":mutation, :proposed_root, 'prepared', '2026-07-16T00:00:00Z', '{}')"
        ),
        {"prior_root": "b" * 64, "mutation": "c" * 64, "proposed_root": "d" * 64},
    )
    _assert_rejected(
        connection,
        "INSERT INTO authority_commit_intents "
        "(id, workspace_id, epoch, deployment_instance_id, prior_generation, "
        "next_generation, prior_state_root, mutation_digest, proposed_state_root, "
        "state, created_at, payload_json) VALUES "
        "('intent-2', 'workspace-2', 1, 'instance-1', 1, 2, :prior_root, "
        ":mutation, :proposed_root, 'prepared', '2026-07-16T00:00:01Z', '{}')",
        {"prior_root": "d" * 64, "mutation": "e" * 64, "proposed_root": "f" * 64},
        error_type=IntegrityError,
        message="uq_authority_commit_intents_inflight_workspace",
    )
    connection.execute(
        text(
            "INSERT INTO authority_commit_intents "
            "(id, workspace_id, epoch, deployment_instance_id, prior_generation, "
            "next_generation, prior_state_root, mutation_digest, proposed_state_root, "
            "state, created_at, payload_json) VALUES "
            "('intent-3', 'workspace-2', 1, 'instance-1', 1, 2, :prior_root, "
            ":mutation, :proposed_root, 'anchor_finalized', "
            "'2026-07-16T00:00:02Z', '{}')"
        ),
        {"prior_root": "d" * 64, "mutation": "e" * 64, "proposed_root": "f" * 64},
    )
    quarantined_statement = (
        "INSERT INTO authority_commit_intents "
        "(id, workspace_id, epoch, deployment_instance_id, prior_generation, "
        "next_generation, prior_state_root, mutation_digest, proposed_state_root, "
        "state, created_at, payload_json) VALUES "
        "(:id, 'workspace-3', 1, 'instance-1', 0, 1, :prior_root, "
        ":mutation, :proposed_root, 'quarantined', '2026-07-16T00:00:03Z', '{}')"
    )
    quarantined_parameters = {
        "id": "intent-quarantined-1",
        "prior_root": "1" * 64,
        "mutation": "2" * 64,
        "proposed_root": "3" * 64,
    }
    connection.execute(text(quarantined_statement), quarantined_parameters)
    connection.execute(
        text(quarantined_statement),
        {**quarantined_parameters, "id": "intent-quarantined-2"},
    )


def test_fresh_postgres_database_upgrade_constraints_and_migration_cycle() -> None:
    database_url = _postgres_test_url()
    _require_reset_authorization(database_url)
    engine = create_platform_engine(database_url)
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except OperationalError as exc:
            if getattr(exc.orig, "sqlstate", None) is not None:
                raise
            pytest.skip(f"PostgreSQL test service unavailable: {exc.__class__.__name__}")

        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))

        assert upgrade_database_url(database_url) == M1_CURRENT_REVISION
        assert current_revision_url(database_url) == M1_CURRENT_REVISION
        with engine.begin() as connection:
            _assert_head_schema_controls(connection)
            _assert_runtime_constraints(connection)

        assert downgrade_database_url(database_url, M1_PROJECT_REVISION) == M1_PROJECT_REVISION
        with engine.connect() as connection:
            triggers, functions, partial_indexes = _schema_controls(connection)
            assert triggers == frozenset()
            assert functions == frozenset()
            assert partial_indexes == {}

        assert upgrade_database_url(database_url) == M1_CURRENT_REVISION
        with engine.connect() as connection:
            _assert_head_schema_controls(connection)
    finally:
        engine.dispose()
