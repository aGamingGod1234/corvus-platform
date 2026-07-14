from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

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
from corvus.domain.request import RequestContext
from corvus.infrastructure.repositories.projects import ProjectRepository


class CreateProjectCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: RequestContext
    client_surface: ClientSurface
    project: Project

    @model_validator(mode="after")
    def validate_context_binding(self) -> CreateProjectCommand:
        if (
            self.context.workspace_id != self.project.workspace_id
            or self.context.scope_kind != "project"
            or self.context.scope_id != self.project.id
        ):
            raise ValueError("project_request_context_mismatch")
        if self.context.transport_principal_id is None:
            raise ValueError("project_transport_principal_missing")
        return self

    @property
    def request_id(self) -> UUID:
        return self.context.id

    @property
    def workspace_id(self) -> UUID:
        return self.context.workspace_id


class GetProjectQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: RequestContext
    client_surface: ClientSurface
    project_id: UUID

    @model_validator(mode="after")
    def validate_context_binding(self) -> GetProjectQuery:
        if self.context.scope_kind != "project" or self.context.scope_id != self.project_id:
            raise ValueError("project_request_context_mismatch")
        if self.context.transport_principal_id is None:
            raise ValueError("project_transport_principal_missing")
        return self

    @property
    def request_id(self) -> UUID:
        return self.context.id

    @property
    def workspace_id(self) -> UUID:
        return self.context.workspace_id


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
        return self._execute(
            context=command.context,
            client_surface=command.client_surface,
            action="project.create",
            project_id=command.project.id,
            project=command.project,
        )

    def get(self, query: GetProjectQuery) -> ProjectResponse:
        return self._execute(
            context=query.context,
            client_surface=query.client_surface,
            action="project.read",
            project_id=query.project_id,
            project=None,
        )

    def _execute(
        self,
        *,
        context: RequestContext,
        client_surface: ClientSurface,
        action: Literal["project.create", "project.read"],
        project_id: UUID,
        project: Project | None,
    ) -> ProjectResponse:
        request = ProjectAuthorizationRequest(
            context=context,
            client_surface=client_surface,
            action=action,
            project_id=project_id,
        )
        try:
            decision = self.authorization.authorize(request)
        except Exception:
            return ProjectResponse(
                request_id=context.id,
                ok=False,
                reason_code="authorization_unavailable",
            )
        if decision.authorization_snapshot_id != context.authorization_snapshot_id:
            return ProjectResponse(
                request_id=context.id,
                ok=False,
                reason_code="authorization_snapshot_mismatch",
            )
        audit_event = ProjectAuditEvent(
            context=context,
            client_surface=client_surface,
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
                    request_id=context.id,
                    ok=False,
                    reason_code="audit_persistence_failed",
                )
            return ProjectResponse(
                request_id=context.id,
                ok=False,
                reason_code=decision.reason_code,
            )
        result: Project | None
        if action == "project.create":
            if project is None:  # pragma: no cover - internal invariant
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code="project_missing",
                )
            if self.create_lifecycle is None:
                try:
                    self.audit.record(audit_event)
                except Exception:
                    return ProjectResponse(
                        request_id=context.id,
                        ok=False,
                        reason_code="audit_persistence_failed",
                    )
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code="project_authority_lifecycle_unavailable",
                )
            try:
                self.create_lifecycle.create(project, audit_event)
            except ProjectCreateLifecycleError as exc:
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code=exc.reason_code,
                )
            except Exception:
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code="project_persistence_failed",
                )
            result = project
        else:
            try:
                self.audit.record(audit_event)
            except Exception:
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code="audit_persistence_failed",
                )
            try:
                result = self.store.get(context.workspace_id, project_id)
            except Exception:
                return ProjectResponse(
                    request_id=context.id,
                    ok=False,
                    reason_code="project_persistence_failed",
                )
        if result is None:
            return ProjectResponse(
                request_id=context.id,
                ok=False,
                reason_code="project_not_found",
            )
        return ProjectResponse(
            request_id=context.id,
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
