from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from corvus.domain.access import (
    AccessBundle,
    AccessContractError,
    AgentGrant,
    CapabilityEffect,
    CapabilityGrant,
    CredentialKind,
    CredentialRef,
    validate_access_bundle,
)


def test_credential_reference_rejects_plaintext_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CredentialRef(
            workspace_id=uuid4(),
            provider_connection_id=uuid4(),
            kind=CredentialKind.OS_KEYRING,
            opaque_locator="plaintext-secret-value",
            scopes={"models.invoke"},
        )

    assert exc_info.value.errors()[0]["ctx"]["reason_code"] == (
        "credential_locator_must_be_opaque_reference"
    )


def test_access_bundle_rejects_cross_workspace_capability_grant() -> None:
    bundle = AccessBundle(
        workspace_id=uuid4(),
        principal_id=uuid4(),
        scope_kind="workspace",
        scope_id=uuid4(),
        issued_by=uuid4(),
        policy_digest="a" * 64,
    )
    grant = CapabilityGrant(
        bundle_id=bundle.id,
        workspace_id=uuid4(),
        resource_kind="project",
        resource_id=uuid4(),
        action="project.read",
        effect=CapabilityEffect.ALLOW,
    )

    with pytest.raises(AccessContractError) as exc_info:
        validate_access_bundle(bundle, [grant])

    assert exc_info.value.reason_code == "cross_workspace_capability_grant"


def test_access_bundle_rejects_naive_expiry() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AccessBundle(
            workspace_id=uuid4(),
            principal_id=uuid4(),
            scope_kind="workspace",
            scope_id=uuid4(),
            issued_by=uuid4(),
            policy_digest="c" * 64,
            expires_at=datetime(2026, 7, 14, 12, 0),
        )

    assert exc_info.value.errors()[0]["ctx"]["reason_code"] == "expiry_must_be_timezone_aware"


def test_agent_grant_references_bundle_instead_of_embedding_capabilities() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AgentGrant.model_validate(
            {
                "workspace_id": str(uuid4()),
                "agent_id": str(uuid4()),
                "capability_bundle_id": str(uuid4()),
                "autonomy_level": 3,
                "issued_by": str(uuid4()),
                "capabilities": ["workspace.admin"],
            }
        )

    assert tuple(exc_info.value.errors()[0]["loc"]) == ("capabilities",)
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"
