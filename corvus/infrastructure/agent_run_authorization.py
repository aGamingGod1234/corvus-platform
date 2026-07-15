from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import Field

from corvus.application.authorization import (
    AuthorizationDecision,
    evaluate_capability_intersection,
    verify_authorization_decision_snapshot,
)
from corvus.application.ports import (
    AgentRunAuthorizationDecision,
    AgentRunAuthorizationRequest,
)
from corvus.domain.agent_runtime import (
    AutonomyGrant,
    ProviderBinding,
    ProviderStatus,
    compute_autonomy_grant_digest,
    compute_provider_binding_digest,
)
from corvus.infrastructure.project_authorization import (
    AuthorizationSnapshotRepository,
    CapabilityIntersectionEvaluator,
    VerifiedProjectAuthorizationInputs,
)


class VerifiedAgentRunAuthorizationInputs(VerifiedProjectAuthorizationInputs):
    autonomy_grant: AutonomyGrant
    provider_binding: ProviderBinding
    credential_proof_id: UUID
    credential_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_proof_id: UUID
    budget_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kill_switch_proof_id: UUID
    kill_switch_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerifiedAgentRunAuthorizationInputProvider(Protocol):
    def resolve(
        self, request: AgentRunAuthorizationRequest
    ) -> VerifiedAgentRunAuthorizationInputs: ...


class VerifiedAgentRunAuthorizationAdapter:
    def __init__(
        self,
        *,
        inputs: VerifiedAgentRunAuthorizationInputProvider,
        snapshots: AuthorizationSnapshotRepository,
        evaluator: CapabilityIntersectionEvaluator = evaluate_capability_intersection,
    ) -> None:
        self.inputs = inputs
        self.snapshots = snapshots
        self.evaluator = evaluator

    def authorize(self, request: AgentRunAuthorizationRequest) -> AgentRunAuthorizationDecision:
        resolved = self.inputs.resolve(request)
        binding_denial = self._binding_denial(request, resolved)
        if binding_denial is not None:
            return self._decision(request, resolved, allowed=False, reason_code=binding_denial)

        result = self.evaluator(
            resolved.request,
            authority_context=resolved.authority_context,
            requester_bundle=resolved.requester_bundle,
            requester_grants=list(resolved.requester_grants),
            agent_grant=resolved.agent_grant,
            agent_bundle=resolved.agent_bundle,
            agent_capabilities=list(resolved.agent_capabilities),
            delegation_grants=list(resolved.delegation_grants),
        )
        if result.decision is not AuthorizationDecision.ALLOW:
            return self._decision(
                request,
                resolved,
                allowed=False,
                reason_code=result.reason_code,
            )

        snapshot_denial = self._snapshot_denial(request, resolved, result.reason_code)
        if snapshot_denial is not None:
            return self._decision(
                request,
                resolved,
                allowed=False,
                reason_code=snapshot_denial,
            )
        return self._decision(
            request,
            resolved,
            allowed=True,
            reason_code=result.reason_code,
        )

    @staticmethod
    def _binding_denial(
        agent_request: AgentRunAuthorizationRequest,
        inputs: VerifiedAgentRunAuthorizationInputs,
    ) -> str | None:
        context = agent_request.context
        request = inputs.request
        run_request = agent_request.request
        if context.transport_principal_id is None:
            return "agent_run_transport_principal_missing"
        if (
            request.workspace_id != context.workspace_id
            or request.request_context_id != context.id
            or request.deployment_instance_id != context.deployment_instance_id
            or request.workspace_authority_epoch != context.workspace_authority_epoch
            or request.workspace_authority_generation != context.workspace_authority_generation
            or request.authority_state_root != context.authority_state_root
            or request.authority_epoch_credential_id != context.authority_epoch_credential_id
            or request.authority_commit_receipt_id != context.authority_commit_receipt_id
            or request.authority_proof_digest != context.authority_proof_digest
            or request.scope_kind != context.scope_kind
            or request.scope_id != context.scope_id
            or request.scope_digest != context.scope_digest
            or request.audience_policy_snapshot_id != context.audience_policy_snapshot_id
            or request.audience_policy_digest != context.audience_policy_digest
            or request.requester_id != context.requester_id
            or request.client_context_id != context.client_context_id
            or request.client_surface is not agent_request.client_surface
            or request.transport_principal_id != context.transport_principal_id
            or request.acting_agent_id != context.agent_id
            or request.resource_kind != "agent_run"
            or request.resource_id != run_request.run_id
            or request.action != agent_request.operation.value
            or inputs.requester_bundle.id != context.access_bundle_id
            or inputs.requester_bundle.policy_digest != context.policy_digest
        ):
            return "agent_run_authorization_input_mismatch"
        if inputs.agent_grant is not None and inputs.agent_grant.id != context.agent_grant_id:
            return "agent_run_agent_grant_mismatch"

        autonomy = inputs.autonomy_grant
        if (
            autonomy.id != run_request.autonomy_grant_id
            or autonomy.workspace_id != run_request.workspace_id
            or autonomy.project_id != run_request.project_id
            or compute_autonomy_grant_digest(autonomy) != run_request.autonomy_grant_digest
            or autonomy.revoked_at is not None
            or autonomy.expires_at <= request.evaluated_at
            or autonomy.wall_clock_deadline < run_request.deadline
            or autonomy.credential_grant_ids != run_request.credential_grant_ids
            or autonomy.max_output_tokens < run_request.max_output_tokens
        ):
            return "stale_autonomy_grant"

        provider = inputs.provider_binding
        if (
            provider.id != run_request.provider_binding_id
            or provider.workspace_id != run_request.workspace_id
            or provider.project_id != run_request.project_id
            or provider.model != run_request.model
            or provider.version != run_request.provider_binding_version
            or compute_provider_binding_digest(provider) != run_request.provider_binding_digest
        ):
            return "provider_binding_digest_mismatch"
        if provider.status is not ProviderStatus.AVAILABLE:
            return "agent_run_provider_unavailable"

        current_kill_id = (
            agent_request.current_kill_switch_proof_id or run_request.kill_switch_proof_id
        )
        current_kill_digest = (
            agent_request.current_kill_switch_proof_digest or run_request.kill_switch_proof_digest
        )
        if (
            inputs.credential_proof_id != run_request.credential_proof_id
            or inputs.credential_proof_digest != run_request.credential_proof_digest
        ):
            return "stale_credential_proof"
        if (
            inputs.budget_proof_id != run_request.budget_proof_id
            or inputs.budget_proof_digest != run_request.budget_proof_digest
        ):
            return "agent_run_over_budget"
        if (
            inputs.kill_switch_proof_id != current_kill_id
            or inputs.kill_switch_proof_digest != current_kill_digest
        ):
            return "agent_run_kill_switch_active"
        return None

    def _snapshot_denial(
        self,
        request: AgentRunAuthorizationRequest,
        inputs: VerifiedAgentRunAuthorizationInputs,
        current_reason_code: str,
    ) -> str | None:
        snapshot = inputs.snapshot
        context = request.context
        persisted = self.snapshots.get_snapshot(
            workspace_id=context.workspace_id,
            snapshot_id=context.authorization_snapshot_id,
        )
        if persisted != snapshot:
            return "authorization_snapshot_missing"
        if (
            snapshot.id != context.authorization_snapshot_id
            or inputs.snapshot_expected.authorization_snapshot_digest
            != context.authorization_snapshot_digest
            or inputs.signing_key.id != context.authorization_signing_key_version_id
            or snapshot.request_context_id != context.id
            or snapshot.workspace_id != context.workspace_id
            or snapshot.scope_kind != context.scope_kind
            or snapshot.scope_id != context.scope_id
            or snapshot.requester_id != context.requester_id
            or snapshot.transport_principal_id != context.transport_principal_id
            or snapshot.decision != AuthorizationDecision.ALLOW.value
            or snapshot.reason_code != current_reason_code
        ):
            return "authorization_snapshot_decision_mismatch"
        verification = verify_authorization_decision_snapshot(
            snapshot,
            expected=inputs.snapshot_expected,
            signing_key=inputs.signing_key,
            verification_proof=inputs.snapshot_verification,
            verified_at=inputs.snapshot_expected.verified_at,
        )
        if verification.decision is not AuthorizationDecision.ALLOW:
            return verification.reason_code
        return None

    @staticmethod
    def _decision(
        request: AgentRunAuthorizationRequest,
        inputs: VerifiedAgentRunAuthorizationInputs,
        *,
        allowed: bool,
        reason_code: str,
    ) -> AgentRunAuthorizationDecision:
        run_request = request.request
        return AgentRunAuthorizationDecision(
            allowed=allowed,
            reason_code=reason_code,
            authorization_snapshot_id=request.context.authorization_snapshot_id,
            canonical_request_digest=request.canonical_request_digest,
            immutable_request_digest=run_request.immutable_request_digest,
            provider_binding_version=run_request.provider_binding_version,
            provider_binding_digest=run_request.provider_binding_digest,
            autonomy_grant_digest=run_request.autonomy_grant_digest,
            credential_proof_digest=run_request.credential_proof_digest,
            budget_proof_digest=run_request.budget_proof_digest,
            kill_switch_proof_id=(
                request.current_kill_switch_proof_id or run_request.kill_switch_proof_id
            ),
            kill_switch_proof_digest=(
                request.current_kill_switch_proof_digest or run_request.kill_switch_proof_digest
            ),
            evaluated_at=inputs.request.evaluated_at,
        )
