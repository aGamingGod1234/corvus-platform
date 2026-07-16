from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from corvus.infrastructure.db import (
    M1_CURRENT_REVISION,
    current_revision_url,
    upgrade_database_url,
)
from corvus.platform import create_platform_engine

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://corvus:corvus@127.0.0.1:55432/corvus_platform_test?connect_timeout=2"
)


def _postgres_test_url() -> str:
    return os.environ.get("CORVUS_TEST_POSTGRES_URL", DEFAULT_TEST_DATABASE_URL)


def test_fresh_postgres_database_upgrades_to_head_with_constraints() -> None:
    database_url = _postgres_test_url()
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

        with engine.connect() as connection:
            immutable_trigger_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE '%\\_no\\_%' ESCAPE '\\'"
                )
            ).scalar_one()
            partial_index_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexdef LIKE '% WHERE %'"
                )
            ).scalar_one()

        assert immutable_trigger_count > 0
        assert partial_index_count >= 2
    finally:
        engine.dispose()
