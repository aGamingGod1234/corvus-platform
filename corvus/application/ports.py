from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from corvus.domain.agent_runtime import (
    AgentCapabilities,
    AgentRunEvent,
    AgentRunHandle,
    AgentRunRequest,
    CancellationResult,
    ProviderBinding,
    ProviderStatus,
    compute_agent_run_request_digest,
)
from corvus.domain.client import ClientSurface
from corvus.domain.identity import Project
from corvus.domain.request import IdempotencyEnvelope, RequestContext


class _ProjectContextBound(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: RequestContext
    client_surface: ClientSurface

    @model_validator(mode="after")
    def validate_transport_binding(self) -> _ProjectContextBound:
        if self.context.transport_principal_id is None:
            raise ValueError("project_transport_principal_missing")
        return self

    @property
    def request_id(self) -> UUID:
        return self.context.id

    @property
    def workspace_id(self) -> UUID:
        return self.context.workspace_id

    @property
    def requester_id(self) -> UUID:
        return self.context.requester_id

    @property
    def acting_agent_id(self) -> UUID:
        return self.context.agent_id

    @property
    def client_context_id(self) -> UUID:
        return self.context.client_context_id

    @property
    def transport_principal_id(self) -> UUID:
        principal_id = self.context.transport_principal_id
        if principal_id is None:  # pragma: no cover - guarded by model validation
            raise ValueError("project_transport_principal_missing")
        return principal_id


class ProjectAuthorizationRequest(_ProjectContextBound):
    action: Literal["project.create", "project.read"]
    project_id: UUID


class ProjectAuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason_code: str = Field(min_length=1, max_length=200)
    authorization_snapshot_id: UUID


class ProjectAuditEvent(_ProjectContextBound):
    authorization_snapshot_id: UUID
    action: Literal["project.create", "project.read"]
    project_id: UUID
    decision: Literal["allow", "deny"]
    reason_code: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_snapshot_binding(self) -> ProjectAuditEvent:
        if self.authorization_snapshot_id != self.context.authorization_snapshot_id:
            raise ValueError("project_authorization_snapshot_mismatch")
        return self

    @property
    def authority_proof_digest(self) -> str:
        return self.context.authority_proof_digest


class ProjectCreateLifecycleError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class ProjectCreateLifecyclePort(Protocol):
    def create(self, project: Project, event: ProjectAuditEvent) -> None: ...


class ProjectStorePort(Protocol):
    def create(self, project: Project) -> None: ...

    def get(self, workspace_id: UUID, project_id: UUID) -> Project | None: ...


class ProjectAuthorizationPort(Protocol):
    def authorize(self, request: ProjectAuthorizationRequest) -> ProjectAuthorizationDecision: ...


class ProjectIdempotencyPort(Protocol):
    def claim_idempotency(self, envelope: IdempotencyEnvelope) -> IdempotencyEnvelope: ...

    def complete_idempotency(self, envelope: IdempotencyEnvelope) -> None: ...


class ProjectAuditPort(Protocol):
    def record(self, event: ProjectAuditEvent) -> None: ...


class AgentRunOperation(StrEnum):
    START = "agent_run.start"
    RESUME = "agent_run.resume"
    CANCEL = "agent_run.cancel"


def _raise_agent_run_contract_error(reason_code: str) -> None:
    raise PydanticCustomError(
        "invalid_agent_run_authorization_request",
        "reason_code={reason_code}",
        {"reason_code": reason_code},
    )


def _validate_agent_run_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        _raise_agent_run_contract_error("agent_run_timestamp_must_be_timezone_aware")
    return value


class AgentRunAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    context: RequestContext
    client_surface: ClientSurface
    operation: AgentRunOperation
    request: AgentRunRequest
    handle: AgentRunHandle | None = None
    canonical_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_kill_switch_proof_id: UUID | None = None
    current_kill_switch_proof_digest: str | None = None

    @model_validator(mode="after")
    def validate_authority_binding(self) -> AgentRunAuthorizationRequest:
        if self.context.workspace_id != self.request.workspace_id:
            _raise_agent_run_contract_error("agent_run_workspace_mismatch")
        if self.context.scope_kind == "project":
            if self.context.scope_id != self.request.project_id:
                _raise_agent_run_contract_error("agent_run_project_scope_mismatch")
        elif self.context.scope_kind == "workspace":
            if (
                self.context.scope_id != self.context.workspace_id
                or self.request.project_id is not None
            ):
                _raise_agent_run_contract_error("agent_run_workspace_scope_mismatch")
        if self.context.idempotency_key != self.request.idempotency_key:
            _raise_agent_run_contract_error("agent_run_idempotency_key_mismatch")
        if (
            self.context.authorization_snapshot_id != self.request.authorization_proof_id
            or self.context.authorization_snapshot_digest != self.request.authorization_proof_digest
        ):
            _raise_agent_run_contract_error("agent_run_authorization_snapshot_mismatch")
        return self

    @model_validator(mode="after")
    def validate_operation_binding(self) -> AgentRunAuthorizationRequest:
        if self.canonical_request_digest != compute_agent_run_request_digest(self.request):
            _raise_agent_run_contract_error("agent_run_request_digest_mismatch")
        if self.handle is not None:
            if self.handle.run_id != self.request.run_id:
                _raise_agent_run_contract_error("agent_run_handle_run_mismatch")
            if self.handle.provider_binding_id != self.request.provider_binding_id:
                _raise_agent_run_contract_error("agent_run_handle_provider_mismatch")
        if self.operation is AgentRunOperation.RESUME:
            if self.handle is None or self.request.resume_handle_id != self.handle.id:
                _raise_agent_run_contract_error("agent_run_resume_handle_mismatch")
        if self.operation is AgentRunOperation.CANCEL:
            if self.handle is None:
                _raise_agent_run_contract_error("agent_run_handle_run_mismatch")
            if (
                self.current_kill_switch_proof_id is None
                or self.current_kill_switch_proof_digest is None
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    self.current_kill_switch_proof_digest,
                )
                is None
            ):
                _raise_agent_run_contract_error("agent_run_current_kill_switch_proof_required")
        return self


class AgentRunAuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", max_length=200)
    authorization_snapshot_id: UUID
    canonical_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    autonomy_grant_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    credential_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kill_switch_proof_id: UUID
    kill_switch_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_evaluated_at(self) -> AgentRunAuthorizationDecision:
        _validate_agent_run_timestamp(self.evaluated_at)
        return self


class AgentRunAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    context: RequestContext
    client_surface: ClientSurface
    operation: AgentRunOperation
    run_id: UUID
    handle_id: UUID | None = None
    provider_binding_id: UUID
    authorization_snapshot_id: UUID
    authorization_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    autonomy_grant_id: UUID
    autonomy_grant_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    credential_proof_id: UUID
    credential_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_proof_id: UUID
    budget_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kill_switch_proof_id: UUID
    kill_switch_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: Literal["authorization", "outcome"]
    outcome: Literal["allow", "deny", "success", "failure"]
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", max_length=200)
    timestamp: datetime

    @model_validator(mode="after")
    def validate_audit_binding(self) -> AgentRunAuditEvent:
        if (
            self.authorization_snapshot_id != self.context.authorization_snapshot_id
            or self.authorization_snapshot_digest != self.context.authorization_snapshot_digest
        ):
            _raise_agent_run_contract_error("agent_run_authorization_snapshot_mismatch")
        valid_phase_outcomes = {
            "authorization": {"allow", "deny"},
            "outcome": {"success", "failure"},
        }
        if self.outcome not in valid_phase_outcomes[self.phase]:
            _raise_agent_run_contract_error("agent_run_audit_phase_outcome_mismatch")
        _validate_agent_run_timestamp(self.timestamp)
        return self


@runtime_checkable
class AgentRunAuthorizationPort(Protocol):
    def authorize(
        self,
        request: AgentRunAuthorizationRequest,
    ) -> AgentRunAuthorizationDecision: ...


@runtime_checkable
class AgentRunAuditPort(Protocol):
    def record(self, event: AgentRunAuditEvent) -> None: ...


@runtime_checkable
class AgentRuntimePort(Protocol):
    def discover(self) -> tuple[ProviderBinding, ...]: ...

    def capabilities(self, binding: ProviderBinding) -> AgentCapabilities: ...

    def health(self, binding: ProviderBinding) -> ProviderStatus: ...

    async def start(self, request: AgentRunRequest) -> AgentRunHandle: ...

    def events(
        self,
        handle: AgentRunHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[AgentRunEvent]: ...

    async def cancel(
        self,
        handle: AgentRunHandle,
        current_kill_switch_proof_id: UUID,
    ) -> CancellationResult: ...

    async def resume(
        self,
        handle: AgentRunHandle,
        request_with_fresh_proofs: AgentRunRequest,
    ) -> AgentRunHandle: ...
