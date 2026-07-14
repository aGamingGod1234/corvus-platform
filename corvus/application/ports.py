from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from corvus.domain.agent_runtime import (
    AgentCapabilities,
    AgentRunEvent,
    AgentRunHandle,
    AgentRunRequest,
    CancellationResult,
    ProviderBinding,
    ProviderStatus,
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
