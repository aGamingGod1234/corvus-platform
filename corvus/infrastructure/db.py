from __future__ import annotations

from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from corvus.database import M1_AUDIT_REVISION as _M1_AUDIT_REVISION
from corvus.database import M1_AUTHORITY_REVISION as _M1_AUTHORITY_REVISION
from corvus.database import M1_AUTHORIZATION_INPUT_REVISION as _M1_AUTHORIZATION_INPUT_REVISION
from corvus.database import M1_HANDOFF_REVISION as _M1_HANDOFF_REVISION
from corvus.database import M1_IDENTITY_SCOPE_REVISION as _M1_IDENTITY_SCOPE_REVISION
from corvus.database import M1_PROJECT_REVISION as _M1_PROJECT_REVISION
from corvus.database import M1_REGISTRY_REVISION as _M1_REGISTRY_REVISION
from corvus.database import M1_ROOT_MANIFEST_REVISION as _M1_ROOT_MANIFEST_REVISION
from corvus.database import DatabaseState, classify_database

M1_PROJECT_REVISION: Final = _M1_PROJECT_REVISION
M1_AUDIT_REVISION: Final = _M1_AUDIT_REVISION
M1_AUTHORITY_REVISION: Final = _M1_AUTHORITY_REVISION
M1_REGISTRY_REVISION: Final = _M1_REGISTRY_REVISION
M1_AUTHORIZATION_INPUT_REVISION: Final = _M1_AUTHORIZATION_INPUT_REVISION
M1_HANDOFF_REVISION: Final = _M1_HANDOFF_REVISION
M1_IDENTITY_SCOPE_REVISION: Final = _M1_IDENTITY_SCOPE_REVISION
M1_ROOT_MANIFEST_REVISION: Final = _M1_ROOT_MANIFEST_REVISION
M1_CURRENT_REVISION: Final = M1_ROOT_MANIFEST_REVISION


class InfrastructureDatabaseError(RuntimeError):
    pass


def _alembic_config(database: Path) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).with_name("migrations")),
    )
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def current_revision(database: Path) -> str | None:
    if not database.is_file():
        return None
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def upgrade_database(database: Path) -> str:
    status = classify_database(database)
    if status.state is not DatabaseState.CURRENT:
        raise InfrastructureDatabaseError(
            f"database_not_ready_for_milestone_migration:{status.state.value}"
        )
    revision = current_revision(database)
    if revision not in {
        None,
        M1_PROJECT_REVISION,
        M1_AUDIT_REVISION,
        M1_AUTHORITY_REVISION,
        M1_REGISTRY_REVISION,
        M1_AUTHORIZATION_INPUT_REVISION,
        M1_HANDOFF_REVISION,
        M1_IDENTITY_SCOPE_REVISION,
        M1_CURRENT_REVISION,
    }:
        raise InfrastructureDatabaseError(f"unsupported_database_revision:{revision}")
    command.upgrade(_alembic_config(database), "head")
    upgraded = current_revision(database)
    if upgraded != M1_CURRENT_REVISION:
        raise InfrastructureDatabaseError(f"database_revision_mismatch:{upgraded or 'unstamped'}")
    return upgraded


def downgrade_database(database: Path, revision: str) -> str:
    current = current_revision(database)
    if current != M1_CURRENT_REVISION:
        raise InfrastructureDatabaseError(f"database_revision_mismatch:{current or 'unstamped'}")
    if revision not in {
        M1_PROJECT_REVISION,
        M1_AUDIT_REVISION,
        M1_AUTHORITY_REVISION,
        M1_REGISTRY_REVISION,
        M1_AUTHORIZATION_INPUT_REVISION,
        M1_HANDOFF_REVISION,
        M1_IDENTITY_SCOPE_REVISION,
    }:
        raise InfrastructureDatabaseError(f"unsupported_downgrade_revision:{revision}")
    command.downgrade(_alembic_config(database), revision)
    downgraded = current_revision(database)
    if downgraded != revision:
        raise InfrastructureDatabaseError(f"database_revision_mismatch:{downgraded or 'unstamped'}")
    return downgraded
