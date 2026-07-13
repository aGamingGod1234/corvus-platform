from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from corvus.domain.access import (
    AccessBundle,
    AgentGrant,
    CapabilityEffect,
    CapabilityGrant,
    DelegationGrant,
)


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: UUID
    requester_id: UUID
    acting_agent_id: UUID
    scope_kind: Literal["workspace", "project", "channel", "thread", "conversation"]
    scope_id: UUID
    resource_kind: str = Field(min_length=1, max_length=100)
    resource_id: UUID
    action: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime


class AuthorizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    decision: AuthorizationDecision
    reason_code: str = Field(min_length=1, max_length=200)
    actions: frozenset[str] = Field(default_factory=frozenset)


def _bundle_is_current(bundle: AccessBundle, *, at: datetime) -> bool:
    return bundle.revoked_at is None and (bundle.expires_at is None or at < bundle.expires_at)


def _grant_targets_request(
    grant: CapabilityGrant,
    *,
    bundle: AccessBundle,
    request: AuthorizationRequest,
) -> bool:
    return (
        grant.bundle_id == bundle.id
        and grant.workspace_id == request.workspace_id
        and grant.resource_kind == request.resource_kind
        and grant.resource_id == request.resource_id
        and grant.action == request.action
    )


def _grant_matches(
    grant: CapabilityGrant,
    *,
    bundle: AccessBundle,
    request: AuthorizationRequest,
) -> bool:
    return _grant_targets_request(grant, bundle=bundle, request=request) and (
        grant.effect is CapabilityEffect.ALLOW
    )


def evaluate_capability_intersection(
    request: AuthorizationRequest,
    *,
    requester_bundle: AccessBundle,
    requester_grants: list[CapabilityGrant],
    agent_grant: AgentGrant,
    agent_bundle: AccessBundle,
    agent_capabilities: list[CapabilityGrant],
    delegation_grants: list[DelegationGrant],
) -> AuthorizationResult:
    bundles_match = (
        requester_bundle.workspace_id == request.workspace_id
        and requester_bundle.principal_id == request.requester_id
        and requester_bundle.scope_kind == request.scope_kind
        and requester_bundle.scope_id == request.scope_id
        and agent_bundle.workspace_id == request.workspace_id
        and agent_bundle.principal_id == request.acting_agent_id
        and agent_bundle.scope_kind == request.scope_kind
        and agent_bundle.scope_id == request.scope_id
        and agent_grant.workspace_id == request.workspace_id
        and agent_grant.agent_id == request.acting_agent_id
        and agent_grant.capability_bundle_id == agent_bundle.id
    )
    grants_current = (
        _bundle_is_current(requester_bundle, at=request.evaluated_at)
        and _bundle_is_current(agent_bundle, at=request.evaluated_at)
        and agent_grant.revoked_at is None
        and (agent_grant.expires_at is None or request.evaluated_at < agent_grant.expires_at)
    )
    requester_allows = any(
        _grant_matches(grant, bundle=requester_bundle, request=request)
        for grant in requester_grants
    )
    agent_allows = any(
        _grant_matches(grant, bundle=agent_bundle, request=request) for grant in agent_capabilities
    )
    explicit_deny = any(
        _grant_targets_request(grant, bundle=bundle, request=request)
        and grant.effect is CapabilityEffect.DENY
        for bundle, grants in (
            (requester_bundle, requester_grants),
            (agent_bundle, agent_capabilities),
        )
        for grant in grants
    )
    if explicit_deny:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="explicit_deny",
        )
    if not requester_allows:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="no_requester_grant",
        )
    if (
        bundles_match
        and grants_current
        and requester_allows
        and agent_allows
        and not delegation_grants
    ):
        return AuthorizationResult(
            decision=AuthorizationDecision.ALLOW,
            reason_code="exact_capability_intersection",
            actions=frozenset({request.action}),
        )
    return AuthorizationResult(
        decision=AuthorizationDecision.DENY,
        reason_code="capability_intersection_missing",
    )
