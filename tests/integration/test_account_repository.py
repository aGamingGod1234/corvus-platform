from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from corvus.application.identity import IdentityService, IdentityServiceError
from corvus.database import M1_AUTHORITY_FAMILY_NAMES, DatabaseState, classify_database
from corvus.domain.access import AccessBundle, CapabilityEffect, CapabilityGrant
from corvus.domain.account import (
    Account,
    DeviceRegistration,
    DeviceStatus,
    ExperienceKind,
    ExternalIdentity,
    SessionRecord,
    SessionStatus,
)
from corvus.domain.identity import (
    MembershipStatus,
    Principal,
    PrincipalKind,
    Workspace,
    WorkspaceKind,
    WorkspaceMembership,
)
from corvus.infrastructure.db import (
    M1_AUDIT_PROOF_MANIFEST_REVISION,
    M1_CURRENT_REVISION,
    downgrade_database,
    upgrade_database,
)
from corvus.infrastructure.repositories.accounts import AccountRepository, AccountRepositoryError
from corvus.infrastructure.repositories.authorization_inputs import AuthorizationInputRepository
from corvus.infrastructure.repositories.identity_scope import IdentityScopeRepository
from corvus.store import TraceStore

_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
_GOOGLE_ISSUER = "https://accounts.google.com"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    assert upgrade_database(database) == M1_CURRENT_REVISION
    return database


def _principal(*, subject: str) -> Principal:
    return Principal(
        kind=PrincipalKind.USER,
        external_provider="corvus-account",
        external_subject=subject,
        display_name="Lucas",
        created_at=_NOW,
    )


def _account(principal: Principal, *, email: str = "lucas@example.com") -> Account:
    return Account(
        principal_id=principal.id,
        normalized_email=email,
        experience_kind=ExperienceKind.DEVELOPER,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _preprovisioned_account(repository: AccountRepository) -> Account:
    principal = _principal(subject=f"preprovisioned:{uuid4()}")
    account = _account(principal)
    repository.create_preprovisioned_account(principal=principal, account=account)
    return account


def test_google_identity_creates_user_principal_account_and_identity_atomically(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    repository = AccountRepository(database)
    service = IdentityService(repository)

    account = service.complete_google_identity(
        issuer=_GOOGLE_ISSUER,
        subject="google-new-user",
        email=" Lucas@Example.COM ",
        email_verified=True,
        display_name="Lucas",
        now=_NOW,
    )
    repeated = service.complete_google_identity(
        issuer=_GOOGLE_ISSUER,
        subject="google-new-user",
        email="lucas@example.com",
        email_verified=True,
        display_name="Changed upstream name",
        now=_NOW + timedelta(minutes=1),
    )

    assert repeated == account
    assert account.normalized_email == "lucas@example.com"
    principal = repository.get_principal(account.principal_id)
    assert principal is not None
    assert principal.kind is PrincipalKind.USER
    assert repository.get_external_identity(_GOOGLE_ISSUER, "google-new-user") is not None


def test_verified_google_email_attaches_only_to_zero_identity_preprovisioned_account(
    tmp_path: Path,
) -> None:
    repository = AccountRepository(_database(tmp_path))
    expected = _preprovisioned_account(repository)
    service = IdentityService(repository)

    attached = service.complete_google_identity(
        issuer=_GOOGLE_ISSUER,
        subject="google-preprovisioned",
        email="LUCAS@example.com",
        email_verified=True,
        display_name="Lucas",
        now=_NOW,
    )

    assert attached == expected
    identities = repository.list_external_identities(expected.id)
    assert [identity.subject for identity in identities] == ["google-preprovisioned"]


@pytest.mark.parametrize(
    ("issuer", "verified", "reason"),
    [
        (_GOOGLE_ISSUER, False, "google_email_unverified"),
        ("https://login.example.com", True, "google_issuer_required"),
    ],
)
def test_google_identity_rejects_unverified_or_non_google_claims_without_writes(
    tmp_path: Path,
    issuer: str,
    verified: bool,
    reason: str,
) -> None:
    repository = AccountRepository(_database(tmp_path))
    service = IdentityService(repository)

    with pytest.raises(IdentityServiceError, match=reason):
        service.complete_google_identity(
            issuer=issuer,
            subject="subject",
            email="lucas@example.com",
            email_verified=verified,
            display_name="Lucas",
            now=_NOW,
        )

    assert repository.get_account_by_email("lucas@example.com") is None


def test_google_identity_rejects_email_link_when_account_already_has_an_identity(
    tmp_path: Path,
) -> None:
    repository = AccountRepository(_database(tmp_path))
    account = _preprovisioned_account(repository)
    repository.append_external_identity(
        ExternalIdentity(
            account_id=account.id,
            issuer=_GOOGLE_ISSUER,
            subject="existing-subject",
            normalized_email=account.normalized_email,
            email_verified=True,
            created_at=_NOW,
        )
    )

    with pytest.raises(IdentityServiceError, match="identity_email_link_conflict"):
        IdentityService(repository).complete_google_identity(
            issuer=_GOOGLE_ISSUER,
            subject="different-subject",
            email=account.normalized_email,
            email_verified=True,
            display_name="Lucas",
            now=_NOW,
        )

    assert repository.get_external_identity(_GOOGLE_ISSUER, "different-subject") is None


def test_external_identity_issuer_subject_is_globally_unique(tmp_path: Path) -> None:
    repository = AccountRepository(_database(tmp_path))
    first = _preprovisioned_account(repository)
    second_principal = _principal(subject=f"preprovisioned:{uuid4()}")
    second = _account(second_principal, email="other@example.com")
    repository.create_preprovisioned_account(principal=second_principal, account=second)
    identity = ExternalIdentity(
        account_id=first.id,
        issuer=_GOOGLE_ISSUER,
        subject="unique-subject",
        normalized_email=first.normalized_email,
        email_verified=True,
        created_at=_NOW,
    )
    repository.append_external_identity(identity)

    with pytest.raises(AccountRepositoryError, match="external_identity_conflict"):
        repository.append_external_identity(
            identity.model_copy(
                update={
                    "account_id": second.id,
                    "normalized_email": second.normalized_email,
                }
            )
        )


def test_membership_access_uses_existing_bundle_and_grant_contracts_and_is_tenant_scoped(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    identities = IdentityScopeRepository(database)
    authorization = AuthorizationInputRepository(database)
    workspace = Workspace(
        name="Corvus Team",
        workspace_kind=WorkspaceKind.TEAM,
        created_at=_NOW,
        updated_at=_NOW,
    )
    foreign_workspace = Workspace(
        name="Foreign",
        workspace_kind=WorkspaceKind.INDIVIDUAL,
        created_at=_NOW,
        updated_at=_NOW,
    )
    principal = _principal(subject="membership-principal")
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        principal_id=principal.id,
        role="owner",
        status=MembershipStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    bundle = AccessBundle(
        workspace_id=workspace.id,
        principal_id=principal.id,
        scope_kind="workspace",
        scope_id=workspace.id,
        issued_by=principal.id,
        policy_digest="c" * 64,
        created_at=_NOW,
        updated_at=_NOW,
    )
    grant = CapabilityGrant(
        bundle_id=bundle.id,
        workspace_id=workspace.id,
        resource_kind="workspace",
        resource_id=workspace.id,
        action="workspace.manage",
        effect=CapabilityEffect.ALLOW,
        created_at=_NOW,
    )

    identities.append_workspace(workspace)
    identities.append_workspace(foreign_workspace)
    identities.append_principal(principal)
    identities.append_membership(membership)
    authorization.append_access_bundle(bundle, [grant])

    assert identities.get_workspace(workspace.id) == workspace
    assert identities.get_membership_access(workspace.id, principal.id) == ((bundle, (grant,)),)
    assert identities.get_membership(foreign_workspace.id, principal.id) is None
    assert identities.get_membership_access(foreign_workspace.id, principal.id) == ()


def test_session_rotation_is_atomic_digest_only_and_rejects_predecessor_replay(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    repository = AccountRepository(database)
    account = _preprovisioned_account(repository)
    device = DeviceRegistration(
        account_id=account.id,
        name="Desktop",
        public_key_digest="d" * 64,
        status=DeviceStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    original_token = "raw-original-session-token"  # noqa: S105
    replacement_token = "raw-replacement-session-token"  # noqa: S105
    session = SessionRecord(
        account_id=account.id,
        device_id=device.id,
        token_digest=_digest(original_token),
        status=SessionStatus.ACTIVE,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )
    repository.append_device(device)
    repository.create_session(session)

    rotated = repository.rotate_session(
        account_id=account.id,
        session_id=session.id,
        presented_digest=_digest(original_token),
        replacement_digest=_digest(replacement_token),
        now=_NOW + timedelta(minutes=5),
        expires_at=_NOW + timedelta(hours=2),
    )

    assert rotated.version == 2
    assert rotated.predecessor_digest == _digest(original_token)
    assert rotated.token_digest == _digest(replacement_token)
    with pytest.raises(AccountRepositoryError, match="session_replay_detected"):
        repository.rotate_session(
            account_id=account.id,
            session_id=session.id,
            presented_digest=_digest(original_token),
            replacement_digest="e" * 64,
            now=_NOW + timedelta(minutes=6),
            expires_at=_NOW + timedelta(hours=2),
        )

    with sqlite3.connect(database) as connection:
        payloads = "\n".join(
            row[0] for row in connection.execute("SELECT payload_json FROM session_records")
        )
    assert original_token not in payloads
    assert replacement_token not in payloads


def test_device_revocation_versions_history_and_invalidates_bound_sessions(tmp_path: Path) -> None:
    repository = AccountRepository(_database(tmp_path))
    account = _preprovisioned_account(repository)
    device = DeviceRegistration(
        account_id=account.id,
        name="Desktop",
        public_key_digest="f" * 64,
        status=DeviceStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    digest = "1" * 64
    session = SessionRecord(
        account_id=account.id,
        device_id=device.id,
        token_digest=digest,
        status=SessionStatus.ACTIVE,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )
    repository.append_device(device)
    repository.create_session(session)
    assert repository.get_active_session(account_id=account.id, token_digest=digest, now=_NOW)

    revoked = repository.revoke_device(
        account_id=account.id,
        device_id=device.id,
        revoked_at=_NOW + timedelta(minutes=1),
    )

    assert revoked.version == 2
    assert revoked.status is DeviceStatus.REVOKED
    assert (
        repository.get_active_session(account_id=account.id, token_digest=digest, now=_NOW) is None
    )
    with pytest.raises(AccountRepositoryError, match="session_device_revoked"):
        repository.rotate_session(
            account_id=account.id,
            session_id=session.id,
            presented_digest=digest,
            replacement_digest="2" * 64,
            now=_NOW + timedelta(minutes=2),
            expires_at=_NOW + timedelta(hours=2),
        )


def test_session_revocation_appends_a_version_and_denies_the_revoked_digest(tmp_path: Path) -> None:
    repository = AccountRepository(_database(tmp_path))
    account = _preprovisioned_account(repository)
    device = DeviceRegistration(
        account_id=account.id,
        name="Desktop",
        public_key_digest="3" * 64,
        status=DeviceStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    digest = "4" * 64
    session = SessionRecord(
        account_id=account.id,
        device_id=device.id,
        token_digest=digest,
        status=SessionStatus.ACTIVE,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(hours=1),
    )
    repository.append_device(device)
    repository.create_session(session)

    revoked = repository.revoke_session(
        account_id=account.id,
        session_id=session.id,
        presented_digest=digest,
        revoked_at=_NOW + timedelta(minutes=1),
    )

    assert revoked.version == 2
    assert revoked.status is SessionStatus.REVOKED
    assert revoked.token_digest is None
    assert revoked.predecessor_digest == digest
    assert (
        repository.get_active_session(account_id=account.id, token_digest=digest, now=_NOW) is None
    )


def test_m2_identity_migration_is_reversible_and_manifest_covers_revocation_history(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    required_tables = {"accounts", "external_identities", "device_registrations", "session_records"}

    assert required_tables <= classify_database(database).tables
    with sqlite3.connect(database) as connection:
        latest_manifest = connection.execute(
            "SELECT id FROM authority_state_root_manifests ORDER BY schema_version DESC LIMIT 1"
        ).fetchone()
        assert latest_manifest is not None
        families = {
            row[0]
            for row in connection.execute(
                "SELECT family_name FROM authority_state_root_leaf_families "
                "WHERE manifest_version_id = ?",
                (latest_manifest[0],),
            )
        }
    assert required_tables <= families
    assert families == M1_AUTHORITY_FAMILY_NAMES

    assert (
        downgrade_database(database, M1_AUDIT_PROOF_MANIFEST_REVISION)
        == M1_AUDIT_PROOF_MANIFEST_REVISION
    )
    assert classify_database(database).state is DatabaseState.CURRENT
    with sqlite3.connect(database) as connection:
        downgraded_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
    assert required_tables.isdisjoint(downgraded_tables)
    assert upgrade_database(database) == M1_CURRENT_REVISION
    assert classify_database(database).state is DatabaseState.CURRENT


def test_repositories_accept_caller_owned_sqlalchemy_engine(tmp_path: Path) -> None:
    database = _database(tmp_path)
    engine = create_engine(f"sqlite:///{database}")
    accounts = AccountRepository(engine)
    identities = IdentityScopeRepository(engine)
    principal = _principal(subject="engine-contract")
    account = _account(principal, email="engine@example.com")

    accounts.create_preprovisioned_account(principal=principal, account=account)
    accounts.close()
    identities.close()

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM accounts")) == 1
    engine.dispose()
