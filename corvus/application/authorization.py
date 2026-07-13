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
from corvus.domain.deployment import (
    AuthorityEpochCredential,
    AuthorityEpochCredentialStatus,
    DeploymentInstance,
    DeploymentInstanceLease,
    DeploymentInstanceStatus,
    WorkspaceAuthority,
    WorkspaceAuthorityState,
)


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: UUID
    deployment_instance_id: UUID
    workspace_authority_epoch: int = Field(ge=1)
    workspace_authority_generation: int = Field(ge=0)
    authority_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_epoch_credential_id: UUID
    authority_commit_receipt_id: UUID
    authority_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
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


class AuthorityCommitProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: UUID
    deployment_instance_id: UUID
    authority_epoch_credential_id: UUID
    authority_epoch: int = Field(ge=1)
    authority_generation: int = Field(ge=0)
    authority_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_commit_receipt_id: UUID
    authority_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    finalized: bool


class AuthorityEvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    deployment_instance: DeploymentInstance | None
    workspace_authority: WorkspaceAuthority
    epoch_credential: AuthorityEpochCredential | None
    active_lease: DeploymentInstanceLease | None
    commit_proof: AuthorityCommitProof | None
    deployment_instance_key_available: bool
    epoch_credential_key_available: bool = True
    os_lock_held: bool


def _authority_denial_reason(
    request: AuthorizationRequest,
    context: AuthorityEvaluationContext | None,
) -> str | None:
    if context is None:
        return "authority_context_missing"
    instance = context.deployment_instance
    if instance is None:
        return "deployment_instance_missing"
    authority = context.workspace_authority
    if authority.workspace_id != request.workspace_id:
        return "cross_workspace_authority"
    if authority.state is WorkspaceAuthorityState.RESTORE_QUARANTINE:
        return "restore_quarantine"
    if authority.state is not WorkspaceAuthorityState.ACTIVE:
        return "workspace_authority_inactive"
    if instance.status is not DeploymentInstanceStatus.ACTIVE:
        return "deployment_instance_inactive"
    if not context.deployment_instance_key_available:
        return "deployment_instance_key_unavailable"
    if (
        authority.deployment_profile_id != instance.deployment_profile_id
        or authority.deployment_instance_id != instance.id
        or request.deployment_instance_id != instance.id
    ):
        return "deployment_instance_mismatch"
    if request.workspace_authority_epoch < authority.epoch:
        return "stale_authority_epoch"
    if request.workspace_authority_epoch != authority.epoch:
        return "authority_epoch_mismatch"
    if request.workspace_authority_generation < authority.authority_generation:
        return "stale_authority_generation"
    if request.workspace_authority_generation != authority.authority_generation:
        return "authority_generation_mismatch"
    if request.authority_state_root != authority.authority_state_root:
        return "authority_state_root_mismatch"
    if request.authority_epoch_credential_id != authority.authority_epoch_credential_id:
        return "authority_epoch_credential_mismatch"
    credential = context.epoch_credential
    if credential is None:
        return "authority_epoch_credential_missing"
    if credential.status is AuthorityEpochCredentialStatus.REVOKED:
        return "authority_epoch_credential_revoked"
    if credential.status is AuthorityEpochCredentialStatus.DESTROYED:
        return "authority_epoch_credential_destroyed"
    if not context.epoch_credential_key_available:
        return "authority_epoch_key_unavailable"
    if (
        credential.id != authority.authority_epoch_credential_id
        or credential.workspace_id != request.workspace_id
        or credential.authority_epoch != authority.epoch
        or credential.deployment_instance_id != instance.id
    ):
        return "authority_epoch_credential_mismatch"
    if credential.device_binding_digest != instance.device_binding_digest:
        return "authority_device_binding_mismatch"
    proof = context.commit_proof
    if proof is None:
        return "authority_commit_proof_missing"
    if not proof.finalized:
        return "authority_commit_not_finalized"
    if proof.workspace_id != request.workspace_id:
        return "cross_workspace_authority_proof"
    if proof.deployment_instance_id != instance.id:
        return "authority_proof_instance_mismatch"
    if proof.authority_epoch_credential_id != credential.id:
        return "authority_proof_credential_mismatch"
    if proof.authority_epoch < authority.epoch:
        return "stale_authority_epoch"
    if proof.authority_epoch != authority.epoch:
        return "authority_epoch_mismatch"
    if proof.authority_generation < authority.authority_generation:
        return "stale_authority_generation"
    if proof.authority_generation != authority.authority_generation:
        return "authority_generation_mismatch"
    if proof.authority_state_root != authority.authority_state_root:
        return "authority_state_root_mismatch"
    if proof.authority_commit_receipt_id != request.authority_commit_receipt_id:
        return "authority_commit_receipt_mismatch"
    if proof.authority_proof_digest != request.authority_proof_digest:
        return "authority_proof_digest_mismatch"
    if not context.os_lock_held:
        return "workspace_os_lock_not_held"
    lease = context.active_lease
    if lease is None:
        return "authority_lease_missing"
    if authority.active_lease_id != lease.id:
        return "authority_lease_mismatch"
    if lease.released_at is not None:
        return "authority_lease_released"
    if lease.acquired_at > request.evaluated_at:
        return "authority_lease_not_yet_active"
    if (
        lease.workspace_id != request.workspace_id
        or lease.authority_epoch != authority.epoch
        or lease.deployment_instance_id != instance.id
    ):
        return "authority_lease_mismatch"
    if authority.activated_at > request.evaluated_at:
        return "workspace_authority_not_yet_active"
    return None


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
    authority_context: AuthorityEvaluationContext | None,
    requester_bundle: AccessBundle,
    requester_grants: list[CapabilityGrant],
    agent_grant: AgentGrant | None,
    agent_bundle: AccessBundle,
    agent_capabilities: list[CapabilityGrant],
    delegation_grants: list[DelegationGrant],
) -> AuthorizationResult:
    authority_denial = _authority_denial_reason(request, authority_context)
    if authority_denial is not None:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code=authority_denial,
        )
    if agent_grant is None:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="no_agent_grant",
        )
    workspace_ids = {
        requester_bundle.workspace_id,
        agent_bundle.workspace_id,
        agent_grant.workspace_id,
        *(grant.workspace_id for grant in requester_grants),
        *(grant.workspace_id for grant in agent_capabilities),
    }
    if workspace_ids != {request.workspace_id}:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="cross_workspace_grant",
        )
    requested_scope = (request.scope_kind, request.scope_id)
    if any(
        (bundle.scope_kind, bundle.scope_id) != requested_scope
        for bundle in (requester_bundle, agent_bundle)
    ):
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="scope_mismatch",
        )
    if requester_bundle.revoked_at is not None:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="requester_grant_revoked",
        )
    if (
        requester_bundle.expires_at is not None
        and request.evaluated_at >= requester_bundle.expires_at
    ):
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="requester_grant_expired",
        )
    if agent_bundle.revoked_at is not None:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="agent_bundle_revoked",
        )
    if agent_bundle.expires_at is not None and request.evaluated_at >= agent_bundle.expires_at:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="agent_bundle_expired",
        )
    if agent_grant.revoked_at is not None:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="agent_grant_revoked",
        )
    if agent_grant.expires_at is not None and request.evaluated_at >= agent_grant.expires_at:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="agent_grant_expired",
        )
    delegation: DelegationGrant | None = None
    if len(delegation_grants) > 1:
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason_code="delegation_chain_unverifiable",
        )
    if delegation_grants:
        delegation = delegation_grants[0]
        if delegation.parent_agent_grant_id != agent_grant.id:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_parent_mismatch",
            )
        if delegation.child_agent_id != request.acting_agent_id:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_child_mismatch",
            )
        if delegation.revoked_at is not None:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_revoked",
            )
        if request.evaluated_at < delegation.issued_at:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_not_yet_active",
            )
        if request.evaluated_at >= delegation.expires_at:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_expired",
            )
        if delegation.depth_limit < 1:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_depth_exceeded",
            )
        if request.action not in delegation.capabilities:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason_code="delegation_overreach",
            )
    expected_bundle_principal_id = (
        agent_grant.agent_id if delegation is not None else request.acting_agent_id
    )
    bundles_match = (
        requester_bundle.workspace_id == request.workspace_id
        and requester_bundle.principal_id == request.requester_id
        and requester_bundle.scope_kind == request.scope_kind
        and requester_bundle.scope_id == request.scope_id
        and agent_bundle.workspace_id == request.workspace_id
        and agent_bundle.principal_id == expected_bundle_principal_id
        and agent_bundle.scope_kind == request.scope_kind
        and agent_bundle.scope_id == request.scope_id
        and agent_grant.workspace_id == request.workspace_id
        and agent_grant.agent_id == expected_bundle_principal_id
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
    if bundles_match and grants_current and requester_allows and agent_allows:
        return AuthorizationResult(
            decision=AuthorizationDecision.ALLOW,
            reason_code=(
                "delegated_capability_intersection"
                if delegation is not None
                else "exact_capability_intersection"
            ),
            actions=frozenset({request.action}),
        )
    return AuthorizationResult(
        decision=AuthorizationDecision.DENY,
        reason_code="capability_intersection_missing",
    )
