from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from corvus.domain.client import ClientSurface
from corvus.domain.identity import Project


class ProjectAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    workspace_id: UUID
    requester_id: UUID
    acting_agent_id: UUID
    client_context_id: UUID
    client_surface: ClientSurface
    transport_principal_id: UUID
    action: Literal["project.create", "project.read"]
    project_id: UUID


class ProjectAuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason_code: str = Field(min_length=1, max_length=200)
    authorization_snapshot_id: UUID


class ProjectAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    workspace_id: UUID
    requester_id: UUID
    acting_agent_id: UUID
    client_context_id: UUID
    client_surface: ClientSurface
    transport_principal_id: UUID
    authorization_snapshot_id: UUID
    action: Literal["project.create", "project.read"]
    project_id: UUID
    decision: Literal["allow", "deny"]
    reason_code: str = Field(min_length=1, max_length=200)


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


class ProjectAuditPort(Protocol):
    def record(self, event: ProjectAuditEvent) -> None: ...
