from __future__ import annotations

import pytest

from tests.postgres_safety import (
    POSTGRES_RESET_OPT_IN_ENV,
    POSTGRES_RESET_OPT_IN_VALUE,
    PostgresTestSafetyError,
    validate_disposable_postgres_url,
)

LOCAL_TEST_URL = "postgresql+psycopg://corvus:corvus@127.0.0.1:55432/corvus_platform_test"


def _opted_in_environment() -> dict[str, str]:
    return {POSTGRES_RESET_OPT_IN_ENV: POSTGRES_RESET_OPT_IN_VALUE}


def test_postgres_reset_requires_explicit_opt_in() -> None:
    with pytest.raises(PostgresTestSafetyError, match="postgres_reset_opt_in_required"):
        validate_disposable_postgres_url(LOCAL_TEST_URL, environ={})


def test_postgres_reset_rejects_database_without_test_suffix() -> None:
    url = "postgresql+psycopg://corvus:corvus@127.0.0.1:55432/corvus_production"

    with pytest.raises(PostgresTestSafetyError, match="postgres_database_not_disposable"):
        validate_disposable_postgres_url(url, environ=_opted_in_environment())


def test_postgres_reset_rejects_arbitrary_remote_host() -> None:
    url = "postgresql+psycopg://corvus:corvus@database.example.com/corvus_platform_test"

    with pytest.raises(PostgresTestSafetyError, match="postgres_test_host_not_allowed"):
        validate_disposable_postgres_url(url, environ=_opted_in_environment())


def test_postgres_reset_rejects_non_psycopg_url() -> None:
    url = "sqlite+pysqlite:///corvus_platform_test"

    with pytest.raises(PostgresTestSafetyError, match="postgres_test_url_required"):
        validate_disposable_postgres_url(url, environ=_opted_in_environment())


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "postgres"])
def test_postgres_reset_accepts_local_and_compose_service_hosts(host: str) -> None:
    rendered_host = f"[{host}]" if ":" in host else host
    url = f"postgresql+psycopg://corvus:corvus@{rendered_host}/corvus_platform_test"

    validate_disposable_postgres_url(url, environ=_opted_in_environment())


def test_postgres_reset_safety_errors_do_not_expose_url_secrets() -> None:
    secret_url = (
        "postgresql+psycopg://visible-user:visible-password@database.example.com/"  # noqa: S105
        "corvus_platform_test?sslpassword=visible-query-secret"
    )

    with pytest.raises(PostgresTestSafetyError) as error:
        validate_disposable_postgres_url(secret_url, environ=_opted_in_environment())

    rendered = str(error.value)
    assert "visible-user" not in rendered
    assert "visible-password" not in rendered
    assert "visible-query-secret" not in rendered
