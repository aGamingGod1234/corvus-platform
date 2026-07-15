from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from corvus.application.ports import (
    AgentRunAuditEvent,
    AgentRunAuditPort,
    AgentRunAuthorizationDecision,
    AgentRunAuthorizationPort,
    AgentRunAuthorizationRequest,
    AgentRunOperation,
    AgentRuntimePort,
)
from corvus.domain.agent_runtime import (
    AgentRunHandle,
    AgentRunRequest,
    CancellationResult,
    compute_agent_run_request_digest,
)
from corvus.domain.client import ClientSurface
from corvus.domain.request import RequestContext


class AgentRunOperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    request_context_id: UUID
    operation: AgentRunOperation
    ok: bool
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", max_length=200)
    handle: AgentRunHandle | None = None
    cancellation_result: CancellationResult | None = None
    identical_start_replayed: bool | None = None


class AgentRuntimeCoordinator:
    def __init__(
        self,
        *,
        runtime: AgentRuntimePort,
        authorization: AgentRunAuthorizationPort,
        audit: AgentRunAuditPort,
        clock: Callable[[], datetime],
    ) -> None:
        self._runtime = runtime
        self._authorization = authorization
        self._audit = audit
        self._clock = clock

    async def start(
        self,
        context: RequestContext,
        client_surface: ClientSurface,
        request: AgentRunRequest,
    ) -> AgentRunOperationResult:
        authorization_request, failure = self._authorization_gate(
            context=context,
            client_surface=client_surface,
            operation=AgentRunOperation.START,
            request=request,
        )
        if failure is not None:
            return failure
        assert authorization_request is not None
        try:
            handle = await self._runtime.start(request)
        except Exception as exc:
            reason_code = (
                "agent_run_idempotency_mismatch"
                if getattr(exc, "reason_code", None) == "agent_run_idempotency_mismatch"
                else "agent_run_start_failed"
            )
            self._record_outcome_best_effort(
                authorization_request,
                outcome="failure",
                reason_code=reason_code,
            )
            return self._failure(context, AgentRunOperation.START, reason_code)
        self._record_outcome_best_effort(
            authorization_request,
            outcome="success",
            reason_code="agent_run_started",
            handle=handle,
        )
        return AgentRunOperationResult(
            request_context_id=context.id,
            operation=AgentRunOperation.START,
            ok=True,
            reason_code="agent_run_started",
            handle=handle,
        )

    async def resume(
        self,
        context: RequestContext,
        client_surface: ClientSurface,
        handle: AgentRunHandle,
        request_with_fresh_proofs: AgentRunRequest,
    ) -> AgentRunOperationResult:
        authorization_request, failure = self._authorization_gate(
            context=context,
            client_surface=client_surface,
            operation=AgentRunOperation.RESUME,
            request=request_with_fresh_proofs,
            handle=handle,
        )
        if failure is not None:
            return failure
        assert authorization_request is not None
        try:
            resumed_handle = await self._runtime.resume(
                handle,
                request_with_fresh_proofs,
            )
        except Exception:
            reason_code = "agent_run_resume_failed"
            self._record_outcome_best_effort(
                authorization_request,
                outcome="failure",
                reason_code=reason_code,
                handle=handle,
            )
            return self._failure(context, AgentRunOperation.RESUME, reason_code)
        self._record_outcome_best_effort(
            authorization_request,
            outcome="success",
            reason_code="agent_run_resumed",
            handle=resumed_handle,
        )
        return AgentRunOperationResult(
            request_context_id=context.id,
            operation=AgentRunOperation.RESUME,
            ok=True,
            reason_code="agent_run_resumed",
            handle=resumed_handle,
        )

    async def cancel(
        self,
        context: RequestContext,
        client_surface: ClientSurface,
        handle: AgentRunHandle,
        request: AgentRunRequest,
        current_kill_switch_proof_id: UUID,
        current_kill_switch_proof_digest: str,
    ) -> AgentRunOperationResult:
        authorization_request, failure = self._authorization_gate(
            context=context,
            client_surface=client_surface,
            operation=AgentRunOperation.CANCEL,
            request=request,
            handle=handle,
            current_kill_switch_proof_id=current_kill_switch_proof_id,
            current_kill_switch_proof_digest=current_kill_switch_proof_digest,
        )
        if failure is not None:
            return failure
        assert authorization_request is not None
        try:
            cancellation_result = await self._runtime.cancel(
                handle,
                current_kill_switch_proof_id,
            )
        except Exception:
            reason_code = "agent_run_cancel_failed"
            self._record_outcome_best_effort(
                authorization_request,
                outcome="failure",
                reason_code=reason_code,
                handle=handle,
            )
            return self._failure(context, AgentRunOperation.CANCEL, reason_code)
        self._record_outcome_best_effort(
            authorization_request,
            outcome="success",
            reason_code=cancellation_result.reason_code,
            handle=handle,
        )
        return AgentRunOperationResult(
            request_context_id=context.id,
            operation=AgentRunOperation.CANCEL,
            ok=True,
            reason_code=cancellation_result.reason_code,
            handle=handle,
            cancellation_result=cancellation_result,
        )

    def _authorization_gate(
        self,
        *,
        context: RequestContext,
        client_surface: ClientSurface,
        operation: AgentRunOperation,
        request: AgentRunRequest,
        handle: AgentRunHandle | None = None,
        current_kill_switch_proof_id: UUID | None = None,
        current_kill_switch_proof_digest: str | None = None,
    ) -> tuple[AgentRunAuthorizationRequest | None, AgentRunOperationResult | None]:
        try:
            authorization_request = AgentRunAuthorizationRequest(
                context=context,
                client_surface=client_surface,
                operation=operation,
                request=request,
                handle=handle,
                canonical_request_digest=compute_agent_run_request_digest(request),
                current_kill_switch_proof_id=current_kill_switch_proof_id,
                current_kill_switch_proof_digest=current_kill_switch_proof_digest,
            )
        except ValidationError as exc:
            return None, self._denial_from_validation(context, operation, exc)
        try:
            decision = self._authorization.authorize(authorization_request)
        except Exception:
            return None, self._failure(
                context,
                operation,
                "agent_run_authorization_unavailable",
            )
        binding_mismatch = self._decision_binding_mismatch(
            authorization_request,
            decision,
        )
        authorization_outcome: Literal["allow", "deny"] = (
            "allow" if decision.allowed and binding_mismatch is None else "deny"
        )
        authorization_reason = binding_mismatch or decision.reason_code
        try:
            self._audit.record(
                self._audit_event(
                    authorization_request,
                    phase="authorization",
                    outcome=authorization_outcome,
                    reason_code=authorization_reason,
                )
            )
        except Exception:
            return None, self._failure(
                context,
                operation,
                "agent_run_audit_unavailable",
            )
        if binding_mismatch is not None or not decision.allowed:
            return None, self._failure(context, operation, authorization_reason)
        return authorization_request, None

    @staticmethod
    def _decision_binding_mismatch(
        request: AgentRunAuthorizationRequest,
        decision: AgentRunAuthorizationDecision,
    ) -> str | None:
        expected = request.request
        checks: tuple[tuple[bool, str], ...] = (
            (
                decision.authorization_snapshot_id == request.context.authorization_snapshot_id,
                "agent_run_authorization_snapshot_mismatch",
            ),
            (
                decision.canonical_request_digest == request.canonical_request_digest,
                "agent_run_request_digest_mismatch",
            ),
            (
                decision.autonomy_grant_digest == expected.autonomy_grant_digest,
                "agent_run_autonomy_grant_digest_mismatch",
            ),
            (
                decision.credential_proof_digest == expected.credential_proof_digest,
                "agent_run_credential_proof_digest_mismatch",
            ),
            (
                decision.budget_proof_digest == expected.budget_proof_digest,
                "agent_run_budget_proof_digest_mismatch",
            ),
            (
                decision.kill_switch_proof_id
                == (request.current_kill_switch_proof_id or expected.kill_switch_proof_id),
                "agent_run_kill_switch_proof_id_mismatch",
            ),
            (
                decision.kill_switch_proof_digest
                == (request.current_kill_switch_proof_digest or expected.kill_switch_proof_digest),
                "agent_run_kill_switch_proof_digest_mismatch",
            ),
        )
        return next((reason_code for matches, reason_code in checks if not matches), None)

    def _record_outcome_best_effort(
        self,
        request: AgentRunAuthorizationRequest,
        *,
        outcome: Literal["success", "failure"],
        reason_code: str,
        handle: AgentRunHandle | None = None,
    ) -> None:
        try:
            self._audit.record(
                self._audit_event(
                    request,
                    phase="outcome",
                    outcome=outcome,
                    reason_code=reason_code,
                    handle=handle,
                )
            )
        except Exception:
            return

    @staticmethod
    def _failure(
        context: RequestContext,
        operation: AgentRunOperation,
        reason_code: str,
    ) -> AgentRunOperationResult:
        return AgentRunOperationResult(
            request_context_id=context.id,
            operation=operation,
            ok=False,
            reason_code=reason_code,
        )

    def _denial_from_validation(
        self,
        context: RequestContext,
        operation: AgentRunOperation,
        error: ValidationError,
    ) -> AgentRunOperationResult:
        first_error = error.errors()[0]
        error_context = first_error.get("ctx") or {}
        reason_code = str(error_context.get("reason_code", "agent_run_request_invalid"))
        return self._failure(context, operation, reason_code)

    def _audit_event(
        self,
        request: AgentRunAuthorizationRequest,
        *,
        phase: Literal["authorization", "outcome"],
        outcome: Literal["allow", "deny", "success", "failure"],
        reason_code: str,
        handle: AgentRunHandle | None = None,
    ) -> AgentRunAuditEvent:
        run_request = request.request
        return AgentRunAuditEvent(
            context=request.context,
            client_surface=request.client_surface,
            operation=request.operation,
            run_id=run_request.run_id,
            handle_id=(
                handle.id
                if handle is not None
                else request.handle.id
                if request.handle is not None
                else None
            ),
            provider_binding_id=run_request.provider_binding_id,
            authorization_snapshot_id=request.context.authorization_snapshot_id,
            authorization_snapshot_digest=(request.context.authorization_snapshot_digest),
            canonical_request_digest=request.canonical_request_digest,
            autonomy_grant_id=run_request.autonomy_grant_id,
            autonomy_grant_digest=run_request.autonomy_grant_digest,
            credential_proof_id=run_request.credential_proof_id,
            credential_proof_digest=run_request.credential_proof_digest,
            budget_proof_id=run_request.budget_proof_id,
            budget_proof_digest=run_request.budget_proof_digest,
            kill_switch_proof_id=(
                request.current_kill_switch_proof_id or run_request.kill_switch_proof_id
            ),
            kill_switch_proof_digest=(
                request.current_kill_switch_proof_digest or run_request.kill_switch_proof_digest
            ),
            phase=phase,
            outcome=outcome,
            reason_code=reason_code,
            timestamp=self._clock(),
        )
