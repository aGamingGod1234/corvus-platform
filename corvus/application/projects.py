from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from corvus.application.ports import (
    ProjectAuditEvent,
    ProjectAuditPort,
    ProjectAuthorizationPort,
    ProjectAuthorizationRequest,
    ProjectCreateLifecycleError,
    ProjectCreateLifecyclePort,
    ProjectStorePort,
)
from corvus.domain.client import ClientSurface
from corvus.domain.identity import Project
from corvus.infrastructure.repositories.projects import ProjectRepository


class CreateProjectCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    workspace_id: UUID
    requester_id: UUID
    acting_agent_id: UUID
    client_context_id: UUID
    client_surface: ClientSurface
    transport_principal_id: UUID
    project: Project


class GetProjectQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    workspace_id: UUID
    requester_id: UUID
    acting_agent_id: UUID
    client_context_id: UUID
    client_surface: ClientSurface
    transport_principal_id: UUID
    project_id: UUID


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID
    ok: bool
    reason_code: str
    project: Project | None = None


class ProjectRepositoryAdapter:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def create(self, project: Project) -> None:
        self.repository.add(project)

    def get(self, workspace_id: UUID, project_id: UUID) -> Project | None:
        return self.repository.get(workspace_id=workspace_id, project_id=project_id)


class ProjectService:
    def __init__(
        self,
        *,
        store: ProjectStorePort,
        authorization: ProjectAuthorizationPort,
        audit: ProjectAuditPort,
        create_lifecycle: ProjectCreateLifecyclePort | None = None,
    ) -> None:
        self.store = store
        self.authorization = authorization
        self.audit = audit
        self.create_lifecycle = create_lifecycle

    def create(self, command: CreateProjectCommand) -> ProjectResponse:
        if command.project.workspace_id != command.workspace_id:
            return ProjectResponse(
                request_id=command.request_id,
                ok=False,
                reason_code="project_workspace_mismatch",
            )
        return self._execute(
            request_id=command.request_id,
            workspace_id=command.workspace_id,
            requester_id=command.requester_id,
            acting_agent_id=command.acting_agent_id,
            client_context_id=command.client_context_id,
            client_surface=command.client_surface,
            transport_principal_id=command.transport_principal_id,
            action="project.create",
            project_id=command.project.id,
            project=command.project,
        )

    def get(self, query: GetProjectQuery) -> ProjectResponse:
        return self._execute(
            request_id=query.request_id,
            workspace_id=query.workspace_id,
            requester_id=query.requester_id,
            acting_agent_id=query.acting_agent_id,
            client_context_id=query.client_context_id,
            client_surface=query.client_surface,
            transport_principal_id=query.transport_principal_id,
            action="project.read",
            project_id=query.project_id,
            project=None,
        )

    def _execute(
        self,
        *,
        request_id: UUID,
        workspace_id: UUID,
        requester_id: UUID,
        acting_agent_id: UUID,
        client_context_id: UUID,
        client_surface: ClientSurface,
        transport_principal_id: UUID,
        action: Literal["project.create", "project.read"],
        project_id: UUID,
        project: Project | None,
    ) -> ProjectResponse:
        request = ProjectAuthorizationRequest(
            request_id=request_id,
            workspace_id=workspace_id,
            requester_id=requester_id,
            acting_agent_id=acting_agent_id,
            client_context_id=client_context_id,
            client_surface=client_surface,
            transport_principal_id=transport_principal_id,
            action=action,
            project_id=project_id,
        )
        try:
            decision = self.authorization.authorize(request)
        except Exception:
            return ProjectResponse(
                request_id=request_id,
                ok=False,
                reason_code="authorization_unavailable",
            )
        audit_event = ProjectAuditEvent(
            request_id=request_id,
            workspace_id=workspace_id,
            requester_id=requester_id,
            acting_agent_id=acting_agent_id,
            client_context_id=client_context_id,
            client_surface=client_surface,
            transport_principal_id=transport_principal_id,
            authorization_snapshot_id=decision.authorization_snapshot_id,
            action=action,
            project_id=project_id,
            decision="allow" if decision.allowed else "deny",
            reason_code=decision.reason_code,
        )
        if not decision.allowed:
            try:
                self.audit.record(audit_event)
            except Exception:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="audit_persistence_failed",
                )
            return ProjectResponse(
                request_id=request_id,
                ok=False,
                reason_code=decision.reason_code,
            )
        result: Project | None
        if action == "project.create":
            if project is None:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="project_missing",
                )
            if self.create_lifecycle is None:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="project_authority_lifecycle_unavailable",
                )
            try:
                self.create_lifecycle.create(project, audit_event)
            except ProjectCreateLifecycleError as exc:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code=exc.reason_code,
                )
            except Exception:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="project_persistence_failed",
                )
            result = project
        else:
            try:
                self.audit.record(audit_event)
            except Exception:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="audit_persistence_failed",
                )
            try:
                result = self.store.get(workspace_id, project_id)
            except Exception:
                return ProjectResponse(
                    request_id=request_id,
                    ok=False,
                    reason_code="project_persistence_failed",
                )
        if result is None:
            return ProjectResponse(
                request_id=request_id,
                ok=False,
                reason_code="project_not_found",
            )
        return ProjectResponse(
            request_id=request_id,
            ok=True,
            reason_code="project_created" if action == "project.create" else "project_found",
            project=result,
        )


class InProcessProjectClient:
    def __init__(self, service: ProjectService) -> None:
        self.service = service

    def create_project(self, command: CreateProjectCommand) -> ProjectResponse:
        return self.service.create(command)

    def get_project(self, query: GetProjectQuery) -> ProjectResponse:
        return self.service.get(query)
