from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from corvus.application.authorization import (
    AuthorizationDecision,
    AuthorizationRequest,
    evaluate_capability_intersection,
)
from corvus.domain.access import (
    AccessBundle,
    AgentGrant,
    CapabilityEffect,
    CapabilityGrant,
)


def _exact_allow_case() -> tuple[
    AuthorizationRequest,
    AccessBundle,
    CapabilityGrant,
    AgentGrant,
    AccessBundle,
    CapabilityGrant,
]:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    workspace_id = uuid4()
    requester_id = uuid4()
    agent_id = uuid4()
    project_id = uuid4()
    requester_bundle = AccessBundle(
        workspace_id=workspace_id,
        principal_id=requester_id,
        scope_kind="project",
        scope_id=project_id,
        issued_by=uuid4(),
        policy_digest="a" * 64,
        expires_at=now + timedelta(hours=1),
    )
    requester_grant = CapabilityGrant(
        bundle_id=requester_bundle.id,
        workspace_id=workspace_id,
        resource_kind="project",
        resource_id=project_id,
        action="project.read",
        effect=CapabilityEffect.ALLOW,
    )
    agent_bundle = AccessBundle(
        workspace_id=workspace_id,
        principal_id=agent_id,
        scope_kind="project",
        scope_id=project_id,
        issued_by=uuid4(),
        policy_digest="b" * 64,
        expires_at=now + timedelta(hours=1),
    )
    agent_capability = CapabilityGrant(
        bundle_id=agent_bundle.id,
        workspace_id=workspace_id,
        resource_kind="project",
        resource_id=project_id,
        action="project.read",
        effect=CapabilityEffect.ALLOW,
    )
    agent_grant = AgentGrant(
        workspace_id=workspace_id,
        agent_id=agent_id,
        capability_bundle_id=agent_bundle.id,
        autonomy_level=2,
        issued_by=requester_id,
        expires_at=now + timedelta(hours=1),
    )
    request = AuthorizationRequest(
        workspace_id=workspace_id,
        requester_id=requester_id,
        acting_agent_id=agent_id,
        scope_kind="project",
        scope_id=project_id,
        resource_kind="project",
        resource_id=project_id,
        action="project.read",
        evaluated_at=now,
    )
    return (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
    )


def test_exact_requester_and_agent_grants_allow() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.reason_code == "exact_capability_intersection"
    assert result.actions == frozenset({"project.read"})


def test_missing_requester_grant_denies_with_reason() -> None:
    request, requester_bundle, _, agent_grant, agent_bundle, agent_capability = _exact_allow_case()

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "no_requester_grant"
    assert result.actions == frozenset()


def test_explicit_deny_overrides_matching_allows() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    requester_deny = CapabilityGrant(
        bundle_id=requester_bundle.id,
        workspace_id=request.workspace_id,
        resource_kind=request.resource_kind,
        resource_id=request.resource_id,
        action=request.action,
        effect=CapabilityEffect.DENY,
    )

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant, requester_deny],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "explicit_deny"
    assert result.actions == frozenset()
