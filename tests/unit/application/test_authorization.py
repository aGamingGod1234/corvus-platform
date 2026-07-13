from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from corvus.application.authorization import (
    AuthorityCommitProof,
    AuthorityEvaluationContext,
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
    BudgetRuntimeVerificationProof,
    CredentialVerificationProof,
    RegistryVerificationProof,
    evaluate_capability_intersection,
)
from corvus.domain.access import (
    AccessBundle,
    AgentGrant,
    CapabilityEffect,
    CapabilityGrant,
    CredentialKind,
    CredentialRef,
    CredentialStatus,
    DelegationGrant,
)
from corvus.domain.deployment import (
    AuthorityEpochCredential,
    AuthorityEpochCredentialStatus,
    AuthorityRegistryFreshnessProof,
    AuthorityRegistryTrustState,
    AuthorityRegistryVerifierKeyVersion,
    AuthorityStateRootLeafFamily,
    AuthorityStateRootManifestVersion,
    AuthorityTrustAnchor,
    AuthorityTrustAnchorKind,
    CoverageKind,
    DeploymentInstance,
    DeploymentInstanceLease,
    RegistryVerifierKeyStatus,
    WorkspaceAuthority,
    WorkspaceAuthorityState,
    fixed_workspace_lock_name,
)
from corvus.domain.execution import ExecutionKind, ExecutionPlacement, ExecutionStatus


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
        request_context_id=uuid4(),
        deployment_instance_id=uuid4(),
        workspace_authority_epoch=3,
        workspace_authority_generation=4,
        authority_state_root="2" * 64,
        authority_epoch_credential_id=uuid4(),
        authority_commit_receipt_id=uuid4(),
        authority_proof_digest="3" * 64,
        trust_anchor_id=uuid4(),
        registry_trust_metadata_version=4,
        registry_history_head_digest="6" * 64,
        registry_freshness_proof_id=uuid4(),
        registry_freshness_sequence=10,
        authority_manifest_version_id=uuid4(),
        authority_manifest_digest="7" * 64,
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


def _valid_authority_context(request: AuthorizationRequest) -> AuthorityEvaluationContext:
    deployment_profile_id = uuid4()
    deployment_instance = DeploymentInstance(
        id=request.deployment_instance_id,
        deployment_profile_id=deployment_profile_id,
        instance_public_key="instance-public-key",
        non_exportable_activation_key_ref="keyring://corvus/instance/current",
        device_binding_digest="1" * 64,
        activated_at=request.evaluated_at - timedelta(minutes=5),
    )
    epoch = request.workspace_authority_epoch
    epoch_credential = AuthorityEpochCredential(
        id=request.authority_epoch_credential_id,
        workspace_id=request.workspace_id,
        authority_epoch=epoch,
        deployment_instance_id=deployment_instance.id,
        public_key="epoch-public-key",
        non_exportable_private_key_ref="keyring://corvus/epoch/current",
        device_binding_digest=deployment_instance.device_binding_digest,
        issued_at=request.evaluated_at - timedelta(minutes=4),
    )
    lease = DeploymentInstanceLease(
        workspace_id=request.workspace_id,
        authority_epoch=epoch,
        deployment_instance_id=deployment_instance.id,
        lock_name=fixed_workspace_lock_name(request.workspace_id, epoch),
        fencing_token=1,
        acquired_at=request.evaluated_at - timedelta(minutes=3),
    )
    authority = WorkspaceAuthority(
        workspace_id=request.workspace_id,
        deployment_profile_id=deployment_profile_id,
        deployment_instance_id=deployment_instance.id,
        epoch=epoch,
        authority_generation=request.workspace_authority_generation,
        authority_state_root=request.authority_state_root,
        authority_epoch_credential_id=epoch_credential.id,
        trust_anchor_id=request.trust_anchor_id,
        active_lease_id=lease.id,
        state=WorkspaceAuthorityState.ACTIVE,
        activated_at=request.evaluated_at - timedelta(minutes=2),
    )
    commit_proof = AuthorityCommitProof(
        workspace_id=request.workspace_id,
        deployment_instance_id=deployment_instance.id,
        authority_epoch_credential_id=epoch_credential.id,
        authority_epoch=epoch,
        authority_generation=request.workspace_authority_generation,
        authority_state_root=request.authority_state_root,
        authority_commit_receipt_id=request.authority_commit_receipt_id,
        authority_proof_digest=request.authority_proof_digest,
        finalized=True,
    )
    registry_id = uuid4()
    assert request.registry_trust_metadata_version is not None
    assert request.registry_history_head_digest is not None
    assert request.registry_freshness_proof_id is not None
    assert request.registry_freshness_sequence is not None
    previous_registry_trust_state = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=3,
        latest_verifier_key_version=2,
        complete_history_head_digest="4" * 64,
        issued_at=request.evaluated_at - timedelta(minutes=10),
        expires_at=request.evaluated_at + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="5" * 64,
    )
    registry_trust_state = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=request.registry_trust_metadata_version,
        latest_verifier_key_version=3,
        complete_history_head_digest=request.registry_history_head_digest,
        issued_at=request.evaluated_at - timedelta(minutes=5),
        expires_at=request.evaluated_at + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="8" * 64,
        previous_metadata_digest=previous_registry_trust_state.canonical_digest,
    )
    registry_verifier_key = AuthorityRegistryVerifierKeyVersion(
        registry_id=registry_id,
        key_version=registry_trust_state.latest_verifier_key_version,
        public_key="registry-public-key",
        status=RegistryVerifierKeyStatus.ACTIVE,
        valid_from=request.evaluated_at - timedelta(days=1),
        threshold_attestation_digest="9" * 64,
    )
    registry_freshness_proof = AuthorityRegistryFreshnessProof(
        id=request.registry_freshness_proof_id,
        registry_id=registry_id,
        trust_state_metadata_version=registry_trust_state.metadata_version,
        complete_history_head_digest=registry_trust_state.complete_history_head_digest,
        registry_sequence=request.registry_freshness_sequence,
        challenge_nonce_digest="a" * 64,
        response_digest="b" * 64,
        issued_at=request.evaluated_at - timedelta(seconds=5),
        expires_at=request.evaluated_at + timedelta(minutes=5),
        verifier_key_version_id=registry_verifier_key.id,
        registry_signature="verified-registry-signature",
    )
    registry_verification_proof = RegistryVerificationProof(
        registry_id=registry_id,
        trust_state_digest=registry_trust_state.canonical_digest,
        freshness_proof_id=registry_freshness_proof.id,
        freshness_response_digest=registry_freshness_proof.response_digest,
        verifier_key_version_id=registry_verifier_key.id,
        trust_state_threshold_signatures_verified=True,
        freshness_signature_verified=True,
        finalized=True,
    )
    trust_anchor = AuthorityTrustAnchor(
        id=request.trust_anchor_id,
        workspace_id=request.workspace_id,
        kind=AuthorityTrustAnchorKind.REGISTRY_GENERATION,
        anchor_registry_id=registry_id,
        pinned_registry_root_digest="c" * 64,
        policy_digest="d" * 64,
        created_at=request.evaluated_at - timedelta(days=1),
    )
    authority_manifest = AuthorityStateRootManifestVersion(
        id=request.authority_manifest_version_id,
        schema_version=1,
        canonicalization_version=1,
        manifest_digest=request.authority_manifest_digest,
        created_at=request.evaluated_at - timedelta(days=1),
    )
    authority_manifest_families = (
        AuthorityStateRootLeafFamily(
            manifest_version_id=authority_manifest.id,
            ordinal=1,
            family_name="workspace_memberships",
            coverage_kind=CoverageKind.IN_ROOT,
            canonicalization_version=1,
        ),
        AuthorityStateRootLeafFamily(
            manifest_version_id=authority_manifest.id,
            ordinal=2,
            family_name="access_bundles",
            coverage_kind=CoverageKind.IN_ROOT,
            canonicalization_version=1,
        ),
    )
    return AuthorityEvaluationContext(
        deployment_instance=deployment_instance,
        workspace_authority=authority,
        epoch_credential=epoch_credential,
        active_lease=lease,
        commit_proof=commit_proof,
        trust_anchor=trust_anchor,
        previous_registry_trust_state=previous_registry_trust_state,
        registry_trust_state=registry_trust_state,
        registry_freshness_proof=registry_freshness_proof,
        registry_verifier_key=registry_verifier_key,
        registry_verification_proof=registry_verification_proof,
        minimum_registry_sequence=9,
        expected_registry_nonce_digest="a" * 64,
        authority_manifest=authority_manifest,
        authority_manifest_families=authority_manifest_families,
        mutable_authority_families=frozenset({"workspace_memberships", "access_bundles"}),
        deployment_instance_key_available=True,
        os_lock_held=True,
    )


def test_exact_requester_and_agent_grants_allow() -> None:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = (
        _exact_allow_case()
    )

    result = evaluate_capability_intersection(
        request,
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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
        authority_context=_valid_authority_context(request),
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


def _evaluate_direct_case(
    case: tuple[
        AuthorizationRequest,
        AccessBundle,
        CapabilityGrant,
        AgentGrant,
        AccessBundle,
        CapabilityGrant,
    ],
    authority_context: AuthorityEvaluationContext | None,
) -> AuthorizationResult:
    request, requester_bundle, requester_grant, agent_grant, agent_bundle, agent_capability = case
    return evaluate_capability_intersection(
        request,
        authority_context=authority_context,
        requester_bundle=requester_bundle,
        requester_grants=[requester_grant],
        agent_grant=agent_grant,
        agent_bundle=agent_bundle,
        agent_capabilities=[agent_capability],
        delegation_grants=[],
    )


def test_missing_authority_context_fails_closed() -> None:
    result = _evaluate_direct_case(_exact_allow_case(), None)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_context_missing"


def test_missing_deployment_instance_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"deployment_instance": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "deployment_instance_missing"


def test_missing_deployment_instance_key_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={"deployment_instance_key_available": False}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "deployment_instance_key_unavailable"


def test_missing_epoch_credential_key_binding_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={"epoch_credential_key_available": False}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_epoch_key_unavailable"


def test_missing_os_lock_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"os_lock_held": False})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "workspace_os_lock_not_held"


def test_missing_authority_lease_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"active_lease": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_lease_missing"


def test_released_authority_lease_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.active_lease is not None
    released_lease = context.active_lease.model_copy(update={"released_at": case[0].evaluated_at})
    context = context.model_copy(update={"active_lease": released_lease})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_lease_released"


def test_wrong_deployment_instance_binding_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    authority = context.workspace_authority.model_copy(update={"deployment_instance_id": uuid4()})
    context = context.model_copy(update={"workspace_authority": authority})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "deployment_instance_mismatch"


def test_restore_quarantine_cannot_authorize_mutation() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    authority = context.workspace_authority.model_copy(
        update={"state": WorkspaceAuthorityState.RESTORE_QUARANTINE}
    )
    context = context.model_copy(update={"workspace_authority": authority})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "restore_quarantine"


def test_revoked_epoch_credential_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.epoch_credential is not None
    credential = context.epoch_credential.model_copy(
        update={
            "status": AuthorityEpochCredentialStatus.REVOKED,
            "revoked_at": case[0].evaluated_at,
        }
    )
    context = context.model_copy(update={"epoch_credential": credential})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_epoch_credential_revoked"


def test_missing_authority_commit_proof_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"commit_proof": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_commit_proof_missing"


def test_non_finalized_authority_commit_proof_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(update={"finalized": False})
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_commit_not_finalized"


def test_stale_external_authority_generation_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(
        update={"authority_generation": case[0].workspace_authority_generation - 1}
    )
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "stale_authority_generation"


def test_external_authority_state_root_mismatch_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(update={"authority_state_root": "9" * 64})
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_state_root_mismatch"


def test_authority_commit_receipt_substitution_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(update={"authority_commit_receipt_id": uuid4()})
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_commit_receipt_mismatch"


def test_authority_proof_deployment_instance_substitution_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(update={"deployment_instance_id": uuid4()})
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_proof_instance_mismatch"


def test_authority_proof_digest_substitution_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.commit_proof is not None
    proof = context.commit_proof.model_copy(update={"authority_proof_digest": "8" * 64})
    context = context.model_copy(update={"commit_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_proof_digest_mismatch"


def test_missing_trust_anchor_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"trust_anchor": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_trust_anchor_missing"


def test_stale_registry_trust_state_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_trust_state is not None
    stale = context.registry_trust_state.model_copy(update={"metadata_version": 3})
    context = context.model_copy(update={"registry_trust_state": stale})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "stale_registry_trust_state"


def test_expired_registry_trust_state_has_zero_grace() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_trust_state is not None
    expired = context.registry_trust_state.model_copy(update={"expires_at": case[0].evaluated_at})
    context = context.model_copy(update={"registry_trust_state": expired})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_trust_state_expired"


def test_registry_trust_state_prefix_replay_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_trust_state is not None
    replayed = context.registry_trust_state.model_copy(
        update={"previous_metadata_digest": "f" * 64}
    )
    context = context.model_copy(update={"registry_trust_state": replayed})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_metadata_prefix_mismatch"


def test_stale_registry_freshness_proof_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_freshness_proof is not None
    stale = context.registry_freshness_proof.model_copy(update={"trust_state_metadata_version": 3})
    context = context.model_copy(update={"registry_freshness_proof": stale})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "stale_registry_freshness_proof"


def test_expired_registry_freshness_proof_has_zero_grace() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_freshness_proof is not None
    expired = context.registry_freshness_proof.model_copy(
        update={"expires_at": case[0].evaluated_at}
    )
    context = context.model_copy(update={"registry_freshness_proof": expired})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_freshness_proof_expired"


def test_registry_freshness_sequence_replay_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"minimum_registry_sequence": 10})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_sequence_replay"


def test_registry_verifier_rollback_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_verifier_key is not None
    rolled_back = context.registry_verifier_key.model_copy(update={"key_version": 2})
    context = context.model_copy(update={"registry_verifier_key": rolled_back})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_verifier_version_rollback"


def test_revoked_registry_verifier_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_verifier_key is not None
    revoked = context.registry_verifier_key.model_copy(
        update={
            "status": RegistryVerifierKeyStatus.REVOKED,
            "revoked_at": case[0].evaluated_at,
        }
    )
    context = context.model_copy(update={"registry_verifier_key": revoked})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_verifier_revoked_at_verification_time"


def test_compromised_registry_verifier_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_verifier_key is not None
    compromised = context.registry_verifier_key.model_copy(
        update={
            "status": RegistryVerifierKeyStatus.COMPROMISED,
            "compromise_effective_at": case[0].evaluated_at,
        }
    )
    context = context.model_copy(update={"registry_verifier_key": compromised})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_verifier_compromised_at_verification_time"


def test_missing_registry_signature_verification_proof_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={"registry_verification_proof": None}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_verification_proof_missing"


def test_unverified_registry_trust_state_signatures_fail_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_verification_proof is not None
    proof = context.registry_verification_proof.model_copy(
        update={"trust_state_threshold_signatures_verified": False}
    )
    context = context.model_copy(update={"registry_verification_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_trust_signatures_unverified"


def test_unverified_registry_freshness_signature_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.registry_verification_proof is not None
    proof = context.registry_verification_proof.model_copy(
        update={"freshness_signature_verified": False}
    )
    context = context.model_copy(update={"registry_verification_proof": proof})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "registry_freshness_signature_unverified"


def test_missing_authority_manifest_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(update={"authority_manifest": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_manifest_missing"


def test_authority_manifest_digest_substitution_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0])
    assert context.authority_manifest is not None
    substituted = context.authority_manifest.model_copy(update={"manifest_digest": "f" * 64})
    context = context.model_copy(update={"authority_manifest": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "authority_manifest_mismatch"


def test_unlisted_mutable_authority_family_fails_closed() -> None:
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={"authority_manifest_families": ()}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "unlisted_authority_family"


def _placement_bound_case() -> tuple[
    tuple[
        AuthorizationRequest,
        AccessBundle,
        CapabilityGrant,
        AgentGrant,
        AccessBundle,
        CapabilityGrant,
    ],
    AuthorityEvaluationContext,
    ExecutionPlacement,
]:
    case = _exact_allow_case()
    placement = ExecutionPlacement(
        kind=ExecutionKind.LOCAL_RUNNER,
        runner_id=uuid4(),
        sandbox_profile="strict-build",
        data_policy_digest="e" * 64,
        created_at=case[0].evaluated_at - timedelta(minutes=1),
    )
    request = case[0].model_copy(update={"execution_placement_id": placement.id})
    bound_case = (
        request,
        case[1],
        case[2],
        case[3],
        case[4],
        case[5],
    )
    context = _valid_authority_context(request).model_copy(
        update={"execution_placement": placement}
    )
    return bound_case, context, placement


def test_exact_active_execution_placement_allows() -> None:
    case, context, _ = _placement_bound_case()

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.reason_code == "exact_capability_intersection"


def test_missing_execution_placement_fails_closed() -> None:
    case, context, _ = _placement_bound_case()
    context = context.model_copy(update={"execution_placement": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_missing"


def test_execution_placement_substitution_fails_closed() -> None:
    case, context, placement = _placement_bound_case()
    substituted = placement.model_copy(update={"id": uuid4()})
    context = context.model_copy(update={"execution_placement": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_mismatch"


def test_unavailable_execution_placement_fails_closed() -> None:
    case, context, placement = _placement_bound_case()
    unavailable = placement.model_copy(update={"status": ExecutionStatus.UNAVAILABLE})
    context = context.model_copy(update={"execution_placement": unavailable})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_unavailable"


def test_revoked_execution_placement_fails_closed() -> None:
    case, context, placement = _placement_bound_case()
    revoked = placement.model_copy(update={"status": ExecutionStatus.REVOKED})
    context = context.model_copy(update={"execution_placement": revoked})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_revoked"


def test_future_execution_placement_fails_closed() -> None:
    case, context, placement = _placement_bound_case()
    future = placement.model_copy(
        update={"created_at": case[0].evaluated_at + timedelta(seconds=1)}
    )
    context = context.model_copy(update={"execution_placement": future})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_not_yet_active"


def test_unsolicited_execution_placement_fails_closed() -> None:
    case = _exact_allow_case()
    placement = ExecutionPlacement(
        kind=ExecutionKind.LOCAL_RUNNER,
        runner_id=uuid4(),
        sandbox_profile="strict-build",
        data_policy_digest="e" * 64,
        created_at=case[0].evaluated_at - timedelta(minutes=1),
    )
    context = _valid_authority_context(case[0]).model_copy(
        update={"execution_placement": placement}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "execution_placement_unsolicited"


def _credential_bound_case() -> tuple[
    tuple[
        AuthorizationRequest,
        AccessBundle,
        CapabilityGrant,
        AgentGrant,
        AccessBundle,
        CapabilityGrant,
    ],
    AuthorityEvaluationContext,
    CredentialRef,
    CredentialVerificationProof,
]:
    case, context, placement = _placement_bound_case()
    request_context_id = uuid4()
    provider_connection_id = uuid4()
    credential_ref_id = uuid4()
    credential_version_id = uuid4()
    credential_grant_id = uuid4()
    request = case[0].model_copy(
        update={
            "request_context_id": request_context_id,
            "provider_connection_id": provider_connection_id,
            "credential_ref_id": credential_ref_id,
            "credential_version_id": credential_version_id,
            "credential_grant_id": credential_grant_id,
        }
    )
    bound_case = (request, case[1], case[2], case[3], case[4], case[5])
    credential_ref = CredentialRef(
        id=credential_ref_id,
        workspace_id=request.workspace_id,
        owner_principal_id=request.requester_id,
        provider_connection_id=provider_connection_id,
        kind=CredentialKind.OS_KEYRING,
        opaque_locator="keyring://corvus/provider/current",
        scopes=frozenset({"model.invoke"}),
        expires_at=request.evaluated_at + timedelta(hours=1),
        version=3,
        created_at=request.evaluated_at - timedelta(hours=1),
        updated_at=request.evaluated_at - timedelta(minutes=1),
    )
    proof = CredentialVerificationProof(
        request_context_id=request.request_context_id,
        workspace_id=request.workspace_id,
        provider_connection_id=provider_connection_id,
        credential_ref_id=credential_ref_id,
        credential_ref_version=credential_ref.version,
        credential_version_id=credential_version_id,
        credential_grant_id=credential_grant_id,
        acting_agent_id=request.acting_agent_id,
        execution_placement_id=placement.id,
        operation=request.action,
        rotation_epoch=4,
        nonce_digest="f" * 64,
        use_limit=2,
        use_count=0,
        issued_at=request.evaluated_at - timedelta(minutes=1),
        expires_at=request.evaluated_at + timedelta(minutes=5),
        credential_version_active=True,
        credential_grant_active=True,
        finalized=True,
    )
    context = context.model_copy(
        update={
            "credential_ref": credential_ref,
            "credential_verification_proof": proof,
            "expected_credential_rotation_epoch": proof.rotation_epoch,
            "expected_credential_nonce_digest": proof.nonce_digest,
        }
    )
    return bound_case, context, credential_ref, proof


def test_exact_current_credential_binding_allows() -> None:
    case, context, _, _ = _credential_bound_case()

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.reason_code == "exact_capability_intersection"


def test_partial_credential_claims_fail_closed() -> None:
    case, context, _, _ = _credential_bound_case()
    request = case[0].model_copy(update={"credential_version_id": None})
    case = (request, case[1], case[2], case[3], case[4], case[5])

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_claims_incomplete"


def test_credential_without_request_placement_fails_closed() -> None:
    case, context, _, _ = _credential_bound_case()
    request = case[0].model_copy(update={"execution_placement_id": None})
    case = (request, case[1], case[2], case[3], case[4], case[5])
    context = context.model_copy(update={"execution_placement": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_placement_missing"


def test_missing_credential_ref_fails_closed() -> None:
    case, context, _, _ = _credential_bound_case()
    context = context.model_copy(update={"credential_ref": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_ref_missing"


def test_provider_connection_substitution_fails_closed() -> None:
    case, context, credential_ref, _ = _credential_bound_case()
    substituted = credential_ref.model_copy(update={"provider_connection_id": uuid4()})
    context = context.model_copy(update={"credential_ref": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_ref_mismatch"


def test_revoked_credential_ref_fails_closed() -> None:
    case, context, credential_ref, _ = _credential_bound_case()
    revoked = credential_ref.model_copy(update={"status": CredentialStatus.REVOKED})
    context = context.model_copy(update={"credential_ref": revoked})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_ref_revoked"


def test_expired_credential_ref_fails_closed() -> None:
    case, context, credential_ref, _ = _credential_bound_case()
    expired = credential_ref.model_copy(update={"expires_at": case[0].evaluated_at})
    context = context.model_copy(update={"credential_ref": expired})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_ref_expired"


def test_missing_credential_verification_proof_fails_closed() -> None:
    case, context, _, _ = _credential_bound_case()
    context = context.model_copy(update={"credential_verification_proof": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_missing"


def test_credential_proof_request_substitution_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    substituted = proof.model_copy(update={"request_context_id": uuid4()})
    context = context.model_copy(update={"credential_verification_proof": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_mismatch"


def test_credential_proof_agent_substitution_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    substituted = proof.model_copy(update={"acting_agent_id": uuid4()})
    context = context.model_copy(update={"credential_verification_proof": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_mismatch"


def test_credential_proof_placement_substitution_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    substituted = proof.model_copy(update={"execution_placement_id": uuid4()})
    context = context.model_copy(update={"credential_verification_proof": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_mismatch"


def test_credential_proof_operation_overreach_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    substituted = proof.model_copy(update={"operation": "project.write"})
    context = context.model_copy(update={"credential_verification_proof": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_mismatch"


def test_exhausted_credential_grant_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    exhausted = proof.model_copy(update={"use_count": proof.use_limit})
    context = context.model_copy(update={"credential_verification_proof": exhausted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_grant_use_limit_exhausted"


def test_expired_credential_verification_proof_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    expired = proof.model_copy(update={"expires_at": case[0].evaluated_at})
    context = context.model_copy(update={"credential_verification_proof": expired})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_proof_expired"


def test_inactive_credential_version_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    inactive = proof.model_copy(update={"credential_version_active": False})
    context = context.model_copy(update={"credential_verification_proof": inactive})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_version_inactive"


def test_inactive_credential_grant_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    inactive = proof.model_copy(update={"credential_grant_active": False})
    context = context.model_copy(update={"credential_verification_proof": inactive})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_grant_inactive"


def test_unfinalized_credential_verification_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    unfinalized = proof.model_copy(update={"finalized": False})
    context = context.model_copy(update={"credential_verification_proof": unfinalized})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_verification_not_finalized"


def test_credential_owner_substitution_fails_closed() -> None:
    case, context, credential_ref, _ = _credential_bound_case()
    substituted = credential_ref.model_copy(update={"owner_principal_id": uuid4()})
    context = context.model_copy(update={"credential_ref": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_owner_mismatch"


def test_future_credential_ref_fails_closed() -> None:
    case, context, credential_ref, _ = _credential_bound_case()
    future = credential_ref.model_copy(
        update={"updated_at": case[0].evaluated_at + timedelta(seconds=1)}
    )
    context = context.model_copy(update={"credential_ref": future})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_ref_not_yet_current"


def test_credential_rotation_epoch_mismatch_fails_closed() -> None:
    case, context, _, proof = _credential_bound_case()
    context = context.model_copy(
        update={"expected_credential_rotation_epoch": proof.rotation_epoch + 1}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_rotation_epoch_mismatch"


def test_credential_nonce_mismatch_fails_closed() -> None:
    case, context, _, _ = _credential_bound_case()
    context = context.model_copy(update={"expected_credential_nonce_digest": "0" * 64})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_nonce_mismatch"


def test_unsolicited_credential_evidence_fails_closed() -> None:
    _, _, credential_ref, proof = _credential_bound_case()
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={
            "credential_ref": credential_ref,
            "credential_verification_proof": proof,
            "expected_credential_rotation_epoch": proof.rotation_epoch,
            "expected_credential_nonce_digest": proof.nonce_digest,
        }
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "credential_evidence_unsolicited"


def _budget_bound_case() -> tuple[
    tuple[
        AuthorizationRequest,
        AccessBundle,
        CapabilityGrant,
        AgentGrant,
        AccessBundle,
        CapabilityGrant,
    ],
    AuthorityEvaluationContext,
    BudgetRuntimeVerificationProof,
]:
    case = _exact_allow_case()
    snapshot_ids = (uuid4(), uuid4())
    budget_snapshot_digest = "1" * 64
    runtime_limit_digest = "2" * 64
    budget_unit = "micro_usd"
    budget_requested_amount = 5
    request = case[0].model_copy(
        update={
            "budget_snapshot_ids": snapshot_ids,
            "budget_snapshot_digest": budget_snapshot_digest,
            "runtime_limit_digest": runtime_limit_digest,
            "budget_unit": budget_unit,
            "budget_requested_amount": budget_requested_amount,
        }
    )
    bound_case = (request, case[1], case[2], case[3], case[4], case[5])
    account_ids = (uuid4(), uuid4(), uuid4())
    proof = BudgetRuntimeVerificationProof(
        request_context_id=request.request_context_id,
        workspace_id=request.workspace_id,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
        action=request.action,
        budget_snapshot_ids=snapshot_ids,
        budget_snapshot_digest=budget_snapshot_digest,
        runtime_limit_digest=runtime_limit_digest,
        unit=budget_unit,
        requested_amount=budget_requested_amount,
        canonical_account_ids=account_ids,
        canonical_account_closure_digest="3" * 64,
        expected_account_count=len(account_ids),
        minimum_remaining_amount=10,
        runtime_limit_ms=60_000,
        runtime_consumed_ms=1_000,
        period_starts_at=request.evaluated_at - timedelta(hours=1),
        period_ends_at=request.evaluated_at + timedelta(hours=1),
        observed_at=request.evaluated_at - timedelta(seconds=1),
        expires_at=request.evaluated_at + timedelta(minutes=5),
        hierarchy_verified=True,
        period_non_overlapping_verified=True,
        all_accounts_active=True,
        finalized=True,
    )
    context = _valid_authority_context(request).model_copy(
        update={"budget_runtime_verification_proof": proof}
    )
    return bound_case, context, proof


def test_exact_budget_and_runtime_evidence_allows() -> None:
    case, context, _ = _budget_bound_case()

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.ALLOW
    assert result.reason_code == "exact_capability_intersection"


def test_partial_budget_claims_fail_closed() -> None:
    case, context, _ = _budget_bound_case()
    request = case[0].model_copy(update={"runtime_limit_digest": None})
    case = (request, case[1], case[2], case[3], case[4], case[5])

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_claims_incomplete"


def test_missing_budget_runtime_proof_fails_closed() -> None:
    case, context, _ = _budget_bound_case()
    context = context.model_copy(update={"budget_runtime_verification_proof": None})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_verification_proof_missing"


def test_budget_snapshot_substitution_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    substituted = proof.model_copy(update={"budget_snapshot_digest": "4" * 64})
    context = context.model_copy(update={"budget_runtime_verification_proof": substituted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_verification_proof_mismatch"


def test_unfinalized_budget_verification_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    unfinalized = proof.model_copy(update={"finalized": False})
    context = context.model_copy(update={"budget_runtime_verification_proof": unfinalized})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_verification_not_finalized"


def test_unverified_budget_hierarchy_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    unverified = proof.model_copy(update={"hierarchy_verified": False})
    context = context.model_copy(update={"budget_runtime_verification_proof": unverified})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_hierarchy_unverified"


def test_overlapping_budget_period_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    unverified = proof.model_copy(update={"period_non_overlapping_verified": False})
    context = context.model_copy(update={"budget_runtime_verification_proof": unverified})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_period_overlap_unverified"


def test_inactive_budget_account_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    inactive = proof.model_copy(update={"all_accounts_active": False})
    context = context.model_copy(update={"budget_runtime_verification_proof": inactive})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_account_inactive"


def test_incomplete_budget_account_closure_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    incomplete = proof.model_copy(
        update={"expected_account_count": proof.expected_account_count + 1}
    )
    context = context.model_copy(update={"budget_runtime_verification_proof": incomplete})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_account_closure_incomplete"


def test_duplicate_budget_accounts_fail_closed() -> None:
    case, context, proof = _budget_bound_case()
    duplicated = proof.model_copy(
        update={"canonical_account_ids": (proof.canonical_account_ids[0],) * 3}
    )
    context = context.model_copy(update={"budget_runtime_verification_proof": duplicated})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_account_closure_ambiguous"


def test_expired_budget_runtime_proof_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    expired = proof.model_copy(update={"expires_at": case[0].evaluated_at})
    context = context.model_copy(update={"budget_runtime_verification_proof": expired})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_verification_proof_expired"


def test_inactive_budget_period_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    inactive = proof.model_copy(update={"period_ends_at": case[0].evaluated_at})
    context = context.model_copy(update={"budget_runtime_verification_proof": inactive})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_period_inactive"


def test_budget_exhaustion_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    exhausted = proof.model_copy(update={"minimum_remaining_amount": 4})
    context = context.model_copy(update={"budget_runtime_verification_proof": exhausted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_exhausted"


def test_runtime_exhaustion_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    exhausted = proof.model_copy(update={"runtime_consumed_ms": proof.runtime_limit_ms})
    context = context.model_copy(update={"budget_runtime_verification_proof": exhausted})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "runtime_exhausted"


def test_unsolicited_budget_evidence_fails_closed() -> None:
    _, _, proof = _budget_bound_case()
    case = _exact_allow_case()
    context = _valid_authority_context(case[0]).model_copy(
        update={"budget_runtime_verification_proof": proof}
    )

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_evidence_unsolicited"


def test_duplicate_budget_snapshot_claims_fail_closed() -> None:
    case, context, proof = _budget_bound_case()
    duplicate_id = case[0].budget_snapshot_ids[0]
    request = case[0].model_copy(update={"budget_snapshot_ids": (duplicate_id, duplicate_id)})
    case = (request, case[1], case[2], case[3], case[4], case[5])
    duplicated = proof.model_copy(update={"budget_snapshot_ids": request.budget_snapshot_ids})
    context = context.model_copy(update={"budget_runtime_verification_proof": duplicated})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_snapshot_set_ambiguous"


def test_future_budget_runtime_proof_fails_closed() -> None:
    case, context, proof = _budget_bound_case()
    future = proof.model_copy(update={"observed_at": case[0].evaluated_at + timedelta(seconds=1)})
    context = context.model_copy(update={"budget_runtime_verification_proof": future})

    result = _evaluate_direct_case(case, context)

    assert result.decision is AuthorizationDecision.DENY
    assert result.reason_code == "budget_runtime_verification_proof_not_yet_valid"
