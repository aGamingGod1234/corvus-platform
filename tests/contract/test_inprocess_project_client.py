from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from corvus.application.ports import (
    ProjectAuthorizationDecision,
    ProjectCreateLifecycleError,
)
from corvus.application.projects import (
    CreateProjectCommand,
    GetProjectQuery,
    InProcessProjectClient,
    ProjectResponse,
    ProjectService,
)
from corvus.domain.client import ClientSurface
from corvus.domain.identity import Project

_NOW = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)
_WORKSPACE_ID = UUID("10000000-0000-0000-0000-000000000001")
_PROJECT_ID = UUID("10000000-0000-0000-0000-000000000002")
_REQUESTER_ID = UUID("10000000-0000-0000-0000-000000000003")
_AGENT_ID = UUID("10000000-0000-0000-0000-000000000004")
_CLIENT_CONTEXT_ID = UUID("10000000-0000-0000-0000-000000000005")
_TRANSPORT_ID = UUID("10000000-0000-0000-0000-000000000006")


class ContractStore:
    def __init__(self) -> None:
        self.projects: dict[tuple[UUID, UUID], Project] = {}
        self.create_count = 0

    def create(self, project: Project) -> None:
        self.projects[(project.workspace_id, project.id)] = project
        self.create_count += 1

    def get(self, workspace_id: UUID, project_id: UUID) -> Project | None:
        return self.projects.get((workspace_id, project_id))


class ContractAudit:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


class SurfaceAuthorization:
    def __init__(self) -> None:
        self.enabled = {ClientSurface.CLI, ClientSurface.DESKTOP}
        self.expected_transport = _TRANSPORT_ID
        self.revoked = False
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        if request.client_surface not in self.enabled:
            allowed, reason = False, "client_surface_disabled"
        elif request.transport_principal_id != self.expected_transport:
            allowed, reason = False, "transport_principal_mismatch"
        elif self.revoked:
            allowed, reason = False, "requester_grant_revoked"
        else:
            allowed, reason = True, "authorized"
        return ProjectAuthorizationDecision(
            allowed=allowed,
            reason_code=reason,
            authorization_snapshot_id=UUID("10000000-0000-0000-0000-000000000099"),
        )


class IdempotentCreateLifecycle:
    def __init__(self, store: ContractStore, audit: ContractAudit) -> None:
        self.store = store
        self.audit = audit
        self.requests: dict[UUID, Project] = {}

    def create(self, project: Project, event) -> None:
        existing = self.requests.get(event.request_id)
        if existing is not None:
            if existing != project:
                raise ProjectCreateLifecycleError("project_replay_mismatch")
            return
        self.audit.record(event)
        self.store.create(project)
        self.requests[event.request_id] = project


def _project(*, name: str = "Contract Corvus") -> Project:
    return Project(
        id=_PROJECT_ID,
        workspace_id=_WORKSPACE_ID,
        name=name,
        root_locator="workspace://contract-corvus",
        privacy="private",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _command(
    project: Project,
    *,
    surface: ClientSurface = ClientSurface.CLI,
    transport_id: UUID = _TRANSPORT_ID,
) -> CreateProjectCommand:
    return CreateProjectCommand(
        request_id=UUID("10000000-0000-0000-0000-000000000007"),
        workspace_id=_WORKSPACE_ID,
        requester_id=_REQUESTER_ID,
        acting_agent_id=_AGENT_ID,
        client_context_id=_CLIENT_CONTEXT_ID,
        client_surface=surface,
        transport_principal_id=transport_id,
        project=project,
    )


def _query(
    *,
    surface: ClientSurface,
    transport_id: UUID = _TRANSPORT_ID,
) -> GetProjectQuery:
    return GetProjectQuery(
        request_id=UUID("10000000-0000-0000-0000-000000000008"),
        workspace_id=_WORKSPACE_ID,
        requester_id=_REQUESTER_ID,
        acting_agent_id=_AGENT_ID,
        client_context_id=_CLIENT_CONTEXT_ID,
        client_surface=surface,
        transport_principal_id=transport_id,
        project_id=_PROJECT_ID,
    )


def _client() -> tuple[
    InProcessProjectClient,
    ContractStore,
    ContractAudit,
    SurfaceAuthorization,
    IdempotentCreateLifecycle,
]:
    store = ContractStore()
    audit = ContractAudit()
    authorization = SurfaceAuthorization()
    lifecycle = IdempotentCreateLifecycle(store, audit)
    client = InProcessProjectClient(
        ProjectService(
            store=store,
            authorization=authorization,
            audit=audit,
            create_lifecycle=lifecycle,
        )
    )
    return client, store, audit, authorization, lifecycle


def test_command_query_and_response_envelopes_are_stable_and_secret_free() -> None:
    project = _project()
    command = _command(project)
    query = _query(surface=ClientSurface.CLI)
    response = ProjectResponse(
        request_id=command.request_id,
        ok=True,
        reason_code="project_created",
        project=project,
    )

    assert set(command.model_dump(mode="json")) == {
        "request_id",
        "workspace_id",
        "requester_id",
        "acting_agent_id",
        "client_context_id",
        "client_surface",
        "transport_principal_id",
        "project",
    }
    assert set(query.model_dump(mode="json")) == {
        "request_id",
        "workspace_id",
        "requester_id",
        "acting_agent_id",
        "client_context_id",
        "client_surface",
        "transport_principal_id",
        "project_id",
    }
    assert set(response.model_dump(mode="json")) == {
        "request_id",
        "ok",
        "reason_code",
        "project",
    }
    assert command.model_dump(mode="json")["client_surface"] == "cli"
    assert GetProjectQuery.model_validate_json(query.model_dump_json()) == query
    assert CreateProjectCommand.model_validate_json(command.model_dump_json()) == command
    assert ProjectResponse.model_validate_json(response.model_dump_json()) == response

    forbidden = {"secret", "password", "token", "credential", "private_key", "api_key"}
    schemas = (
        CreateProjectCommand.model_json_schema(),
        GetProjectQuery.model_json_schema(),
        ProjectResponse.model_json_schema(),
    )
    serialized_schema = " ".join(str(schema).lower() for schema in schemas)
    assert all(field not in serialized_schema for field in forbidden)


def test_currently_authorized_replay_is_idempotent_and_rechecks_revocation() -> None:
    client, store, audit, authorization, lifecycle = _client()
    command = _command(_project())

    created = client.create_project(command)
    replayed = client.create_project(command)
    mismatched = client.create_project(
        command.model_copy(update={"project": _project(name="Substituted")})
    )
    authorization.revoked = True
    revoked = client.create_project(command)

    assert replayed == created
    assert store.create_count == 1
    assert len(lifecycle.requests) == 1
    assert mismatched.ok is False
    assert mismatched.reason_code == "project_replay_mismatch"
    assert revoked.ok is False
    assert revoked.reason_code == "requester_grant_revoked"
    assert len(audit.events) == 2
    assert audit.events[-1].decision == "deny"


def test_enabled_surfaces_are_equivalent_and_transport_claims_fail_closed() -> None:
    client, store, audit, authorization, _ = _client()
    store.create(_project())

    cli = client.get_project(_query(surface=ClientSurface.CLI))
    desktop = client.get_project(_query(surface=ClientSurface.DESKTOP))
    disabled = client.get_project(_query(surface=ClientSurface.WEB))
    mismatched = client.get_project(
        _query(
            surface=ClientSurface.CLI,
            transport_id=UUID("10000000-0000-0000-0000-000000000088"),
        )
    )

    assert (cli.ok, cli.reason_code, cli.project) == (
        desktop.ok,
        desktop.reason_code,
        desktop.project,
    )
    assert disabled.ok is False
    assert disabled.reason_code == "client_surface_disabled"
    assert mismatched.ok is False
    assert mismatched.reason_code == "transport_principal_mismatch"
    assert [request.client_surface for request in authorization.requests] == [
        ClientSurface.CLI,
        ClientSurface.DESKTOP,
        ClientSurface.WEB,
        ClientSurface.CLI,
    ]
    assert [event.decision for event in audit.events] == ["allow", "allow", "deny", "deny"]
