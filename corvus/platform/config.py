from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError

_DATABASE_URL_ENV: Final = "CORVUS_DATABASE_URL"
_SESSION_SECRET_ENV: Final = "CORVUS_SESSION_SECRET"  # noqa: S105
_OAUTH_STATE_SECRET_ENV: Final = "CORVUS_OAUTH_STATE_SECRET"  # noqa: S105
_MINIMUM_SECRET_LENGTH: Final = 32
_SQLITE_DRIVERS: Final = frozenset({"sqlite", "sqlite+pysqlite"})
_POSTGRES_DRIVER: Final = "postgresql+psycopg"


def _required_environment_value(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"missing_required_setting:{name}")
    return value


def _validated_database_url(database_url: str) -> URL:
    try:
        parsed = make_url(database_url)
    except ArgumentError:
        raise ValueError("unsupported_database_url") from None
    if parsed.drivername not in {*_SQLITE_DRIVERS, _POSTGRES_DRIVER}:
        raise ValueError("unsupported_database_url")
    return parsed


def _redacted_database_url(database_url: str) -> str:
    return _validated_database_url(database_url).render_as_string(hide_password=True)


@dataclass(frozen=True, slots=True)
class PlatformSettings:
    database_url: str = field(repr=False)
    session_secret: str = field(repr=False)
    oauth_state_secret: str = field(repr=False)

    def __post_init__(self) -> None:
        _validated_database_url(self.database_url)
        for name, secret in (
            (_SESSION_SECRET_ENV, self.session_secret),
            (_OAUTH_STATE_SECRET_ENV, self.oauth_state_secret),
        ):
            if len(secret) < _MINIMUM_SECRET_LENGTH:
                raise ValueError(f"secret_too_short:{name}")
        if hmac.compare_digest(self.session_secret, self.oauth_state_secret):
            raise ValueError("secrets_must_be_distinct")

    @classmethod
    def from_env(cls) -> PlatformSettings:
        database_url = _required_environment_value(_DATABASE_URL_ENV)
        session_secret = _required_environment_value(_SESSION_SECRET_ENV)
        oauth_state_secret = _required_environment_value(_OAUTH_STATE_SECRET_ENV)
        return cls(
            database_url=database_url,
            session_secret=session_secret,
            oauth_state_secret=oauth_state_secret,
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"database_url={_redacted_database_url(self.database_url)!r}, "
            "session_secret='***', oauth_state_secret='***')"
        )


def create_platform_engine(database_url: str) -> Engine:
    parsed = _validated_database_url(database_url)
    try:
        return create_engine(parsed)
    except (ArgumentError, NoSuchModuleError):
        raise ValueError("database_engine_creation_failed") from None
