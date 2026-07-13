from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from corvus.application.authorization import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
    evaluate_capability_intersection,
)
from corvus.domain.access import (
    AccessBundle,
    AgentGrant,
    CapabilityEffect,
    CapabilityGrant,
    DelegationGrant,
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


def test_missing_agent_grant_denies_without_inheriting_requester_authority() -> None:
    request, requester_bundle, requester_grant, _, agent_bundle, agent_capability = (
        _exact_allow_case()
    )

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=None,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "no_agent_grant"
    assert result.actions == frozenset()


def test_cross_workspace_agent_grant_denies_before_capability_matching() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    foreign_workspace_id = uuid4()
    foreign_bundle = agent_bundle.model_copy(update={"workspace_id": foreign_workspace_id})
    foreign_agent_grant = agent_grant.model_copy(update={"workspace_id": foreign_workspace_id})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=foreign_agent_grant,
        agent_bundle=foreign_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "cross_workspace_grant"
    assert result.actions == frozenset()


def test_requester_bundle_expiry_has_zero_grace() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    expired_bundle = requester_bundle.model_copy(update={"expires_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=expired_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "requester_grant_expired"
    assert result.actions == frozenset()


def test_project_scoped_bundle_cannot_broaden_to_another_project() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    other_project_id = uuid4()
    requester_bundle = requester_bundle.model_copy(update={"scope_id": other_project_id})
    agent_bundle = agent_bundle.model_copy(update={"scope_id": other_project_id})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "scope_mismatch"
    assert result.actions == frozenset()


def test_requester_bundle_revocation_fails_closed_with_reason() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    revoked_bundle = requester_bundle.model_copy(update={"revoked_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=revoked_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "requester_grant_revoked"
    assert result.actions == frozenset()


def test_agent_bundle_expiry_has_zero_grace() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    expired_bundle = agent_bundle.model_copy(update={"expires_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=expired_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "agent_bundle_expired"
    assert result.actions == frozenset()


def test_agent_bundle_revocation_fails_closed_with_reason() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    revoked_bundle = agent_bundle.model_copy(update={"revoked_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=revoked_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "agent_bundle_revoked"
    assert result.actions == frozenset()


def test_agent_grant_expiry_has_zero_grace() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    expired_grant = agent_grant.model_copy(update={"expires_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=expired_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "agent_grant_expired"
    assert result.actions == frozenset()


def test_agent_grant_revocation_fails_closed_with_reason() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    revoked_grant = agent_grant.model_copy(update={"revoked_at": request.evaluated_at})

    result = evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=revoked_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "agent_grant_revoked"
    assert result.actions == frozenset()


def _delegated_allow_case() -> tuple[
    AuthorizationRequest,
    AccessBundle,
    CapabilityGrant,
    AgentGrant,
    AccessBundle,
    CapabilityGrant,
    DelegationGrant,
]:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )
    child_agent_id = uuid4()
    delegated_request = request.model_copy(update={"acting_agent_id": child_agent_id})
    delegation = DelegationGrant(
        parent_agent_grant_id=agent_grant.id,
        child_agent_id=child_agent_id,
        capabilities=frozenset({request.action}),
        budget_json={"max_cost_usd": 1.0},
        depth_limit=1,
        issued_at=request.evaluated_at - timedelta(minutes=1),
        expires_at=request.evaluated_at + timedelta(minutes=30),
    )
    return (
        delegated_request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    )


def _evaluate_delegated_case(
    *,
    request: AuthorizationRequest,
    requester_bundle: AccessBundle,
    requester_grant: CapabilityGrant,
    agent_grant: AgentGrant,
    agent_bundle: AccessBundle,
    agent_capability: CapabilityGrant,
    delegation_grants: list[DelegationGrant],
) -> AuthorizationResult:
    return evaluate_capability_intersection(
        request,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=delegation_grants,
    )


def test_exact_one_hop_delegation_allows_only_the_delegated_action() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.reason_code == "delegated_capability_intersection"
    assert result.actions == frozenset({request.action})


def test_delegation_rejects_parent_grant_substitution() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"parent_agent_grant_id": uuid4()})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_parent_mismatch"


def test_delegation_rejects_child_agent_substitution() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"child_agent_id": uuid4()})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_child_mismatch"


def test_delegation_cannot_broaden_parent_capabilities() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"capabilities": frozenset({"project.write"})})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_overreach"


def test_delegation_expiry_has_zero_grace() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"expires_at": request.evaluated_at})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_expired"


def test_revoked_delegation_fails_closed() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"revoked_at": request.evaluated_at})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_revoked"


def test_delegation_cannot_be_used_before_issuance() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(
        update={"issued_at": request.evaluated_at + timedelta(seconds=1)}
    )

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_not_yet_active"


def test_zero_depth_delegation_cannot_authorize_a_child() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    delegation = delegation.model_copy(update={"depth_limit": 0})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_depth_exceeded"


def test_unlinked_multi_hop_delegation_chain_fails_closed() -> None:
    (
        request,
        requester_bundle,
        requester_grant,
        agent_grant,
        agent_bundle,
        agent_capability,
        delegation,
    ) = _delegated_allow_case()
    second_delegation = delegation.model_copy(update={"id": uuid4()})

    result = _evaluate_delegated_case(
        request=request,
        requester_bundle=requester_bundle,
        requester_grant=requester_grant,
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capability=agent_capability,
        delegation_grants=[delegation, second_delegation],
    )

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "delegation_chain_unverifiable"
