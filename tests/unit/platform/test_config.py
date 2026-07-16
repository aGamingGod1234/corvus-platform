from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from corvus.infrastructure.db import (
    M1_CURRENT_REVISION,
    current_revision_url,
    upgrade_database_url,
)
from corvus.platform import PlatformSettings, create_platform_engine

POSTGRES_URL = "postgresql+psycopg://corvus:database-password@localhost/corvus"
SESSION_SECRET = "session-secret-value-that-is-at-least-32-characters"  # noqa: S105
OAUTH_STATE_SECRET = "oauth-state-secret-value-that-is-at-least-32-characters"  # noqa: S105


def _set_hosted_environment(monkeypatch: pytest.MonkeyPatch, *, database_url: str) -> None:
    monkeypatch.setenv("CORVUS_DATABASE_URL", database_url)
    monkeypatch.setenv("CORVUS_SESSION_SECRET", SESSION_SECRET)
    monkeypatch.setenv("CORVUS_OAUTH_STATE_SECRET", OAUTH_STATE_SECRET)


def test_platform_settings_require_distinct_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORVUS_DATABASE_URL", POSTGRES_URL)
    monkeypatch.setenv("CORVUS_SESSION_SECRET", "x" * 48)
    monkeypatch.setenv("CORVUS_OAUTH_STATE_SECRET", "x" * 48)

    with pytest.raises(ValueError, match="secrets_must_be_distinct"):
        PlatformSettings.from_env()


def test_platform_settings_constructor_cannot_bypass_validation() -> None:
    reused_secret = "x" * 48

    with pytest.raises(ValueError, match="secrets_must_be_distinct"):
        PlatformSettings(
            database_url=POSTGRES_URL,
            session_secret=reused_secret,
            oauth_state_secret=reused_secret,
        )


@pytest.mark.parametrize(
    "missing_name",
    ["CORVUS_DATABASE_URL", "CORVUS_SESSION_SECRET", "CORVUS_OAUTH_STATE_SECRET"],
)
def test_platform_settings_fail_closed_when_required_value_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    _set_hosted_environment(monkeypatch, database_url=POSTGRES_URL)
    monkeypatch.delenv(missing_name)

    with pytest.raises(ValueError, match=f"missing_required_setting:{missing_name}"):
        PlatformSettings.from_env()


@pytest.mark.parametrize("secret_name", ["CORVUS_SESSION_SECRET", "CORVUS_OAUTH_STATE_SECRET"])
def test_platform_settings_reject_short_secrets(
    monkeypatch: pytest.MonkeyPatch,
    secret_name: str,
) -> None:
    _set_hosted_environment(monkeypatch, database_url=POSTGRES_URL)
    short_secret = "secret-value"  # noqa: S105
    monkeypatch.setenv(secret_name, short_secret)

    with pytest.raises(ValueError, match=f"secret_too_short:{secret_name}") as error:
        PlatformSettings.from_env()

    assert short_secret not in str(error.value)


@pytest.mark.parametrize(
    "database_url,dialect_name,driver_name",
    [
        ("sqlite+pysqlite:///:memory:", "sqlite", "pysqlite"),
        (POSTGRES_URL, "postgresql", "psycopg"),
    ],
)
def test_create_platform_engine_supports_approved_database_urls(
    database_url: str,
    dialect_name: str,
    driver_name: str,
) -> None:
    engine = create_platform_engine(database_url)
    try:
        assert isinstance(engine, Engine)
        assert engine.dialect.name == dialect_name
        assert engine.dialect.driver == driver_name
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://corvus:visible-password@localhost/corvus",
        "mysql+pymysql://corvus:visible-password@localhost/corvus",
        "not-a-database-url-visible-password",
    ],
)
def test_database_url_errors_are_redacted(database_url: str) -> None:
    with pytest.raises(ValueError, match="unsupported_database_url") as error:
        create_platform_engine(database_url)

    assert "visible-password" not in str(error.value)


def test_platform_settings_are_immutable_and_redact_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hosted_environment(monkeypatch, database_url=POSTGRES_URL)

    settings = PlatformSettings.from_env()
    rendered = repr(settings)

    assert "database-password" not in rendered
    assert SESSION_SECRET not in rendered
    assert OAUTH_STATE_SECRET not in rendered
    assert "***" in rendered
    with pytest.raises(FrozenInstanceError):
        settings.database_url = "sqlite:///:memory:"


def test_url_based_alembic_upgrade_supports_fresh_sqlite_database(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'platform.db'}"

    assert current_revision_url(database_url) is None
    assert upgrade_database_url(database_url) == M1_CURRENT_REVISION
    assert current_revision_url(database_url) == M1_CURRENT_REVISION
